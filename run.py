"""
Contained 5G incident-response lab — command line (the source of truth).
=======================================================================
    python run.py --list
    python run.py --attack signalling_storm_amf
    python run.py --attack nf_host_ransomware --provider offline
    python run.py --attack core_ddos_upf --auto        # approve everything, agent at every gate
    python run.py --attack 1 --step                    # presenting: Enter to move to each next phase
    python run.py --attack 1 --pace 2 --auto           # unfold with 2 s between steps; --fast: no pauses

ITU-T Y.3172 ML pipeline (src/y3172/) driven by an ML Intent:
    python run.py --intent intents/amf_signalling_storm.yaml
    python run.py --intent intents/amf_signalling_storm.yaml --auto --mode advisory

The MLFO trains and selects a model in the ML sandbox, deploys it to a live
simulated network, and on each detection runs the policy & legal adviser as
the P node before any remediation; see src/y3172/__init__.py.

Resets the simulated core, injects the attack, prints the Policy panel
(Indian obligations with file and page) and the Technical panel, runs the
Basic tier automatically and asks before every further tier:

    Basic steps did not resolve it. Intermediate tier?
      [1] Agent runs it   [2] I'll run it   [3] Stop

In agent mode each state-changing step is shown and needs y/n.  In manual
mode the commands are printed (python -m sim.cli ...), you run them in
another terminal and paste the output; the agent interprets it.

Everything happens inside a local Python simulation.  Nothing is sent to
any network except, if LLM_PROVIDER=anthropic and a key is set, the calls
to the Claude API.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time

W = 100

# Pacing: an attack is shown as it unfolds, one step at a time, rather than
# all at once.  PACE seconds between steps (0 = no pause); STEP = wait for
# Enter at each phase.  Set from --pace / --step / --fast in main().
PACE = 0.0
STEP = False


def _pause(weight: float = 1.0, phase: str = "") -> None:
    """Pause between steps; with --step, wait for Enter at the start of each phase."""
    sys.stdout.flush()
    if STEP and phase:
        try:
            input(f"\n  ⏎  Enter to continue: {phase} ")
        except EOFError:
            pass
    elif PACE > 0:
        time.sleep(PACE * weight)


def _rule(title: str = "", ch: str = "=") -> str:
    return f"{ch * 3} {title} {ch * max(3, W - len(title) - 5)}" if title else ch * W


def _wrap(text: str, indent: str = "    ") -> str:
    return textwrap.fill(" ".join(str(text).split()), W, initial_indent=indent, subsequent_indent=indent)


class CliHuman:
    """The operator at the terminal. --auto answers 'agent' and 'yes' to everything."""

    def __init__(self, auto: bool = False) -> None:
        self.auto = auto

    def _ask(self, prompt: str, valid: dict[str, str]) -> str:
        while True:
            try:
                answer = input(prompt).strip().lower()
            except EOFError:                        # no terminal: stop safely
                return valid.get("3", "stop") if "3" in valid else "n"
            if answer in valid:
                return valid[answer]
            print(f"    please answer one of: {', '.join(valid)}")

    def gate(self, tier: str, message: str) -> str:
        print("\n" + _rule(f"GATE before {tier.upper()}", "#"))
        print(f"  {message}\n    [1] Agent runs it\n    [2] I'll run it\n    [3] Stop")
        if self.auto:
            print("  > 1 (--auto)")
            return "agent"
        return self._ask("  > ", {"1": "agent", "2": "manual", "3": "stop"})

    def confirm(self, description: str) -> bool:
        print(f"\n  The agent wants to run a STATE-CHANGING step:\n{_wrap(description, '      ')}")
        if self.auto:
            print("  Approve? [y/n] y (--auto)")
            return True
        return self._ask("  Approve? [y/n] ", {"y": True, "yes": True, "n": False, "no": False})

    def manual(self, tier: str, commands: list[str]) -> str:
        print(f"\n  Run these {tier} steps yourself, in order, in another terminal (same folder):\n")
        for c in commands:
            print(textwrap.indent(c, "    "))
        if self.auto:
            return ""
        print("\n  Paste the output here, then a line containing only END:")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "END":
                break
            lines.append(line)
        return "\n".join(lines)


def print_policy(panel: dict) -> None:
    print("\n" + _rule("POLICY PANEL — Indian obligations (decision support, not legal advice)"))
    if panel.get("error"):
        print(f"  ! {panel['error']}")
    for ob in panel.get("obligations", []):
        mark = "✔" if ob["found"] else "✘"
        print(f"  {mark} {ob['summary']}")
        if ob["applies_when"]:
            print(_wrap(f"when: {ob['applies_when']}", "      "))
        print(f"      source: {ob['citation']}")
        if ob["passage"]:
            print(_wrap(f"“{ob['passage'][:300]}”", "      "))
    if panel.get("related"):
        print("\n  Related passages (similarity search in " + ", ".join(panel.get("categories", [])) + "):")
        for r in panel["related"][:3]:
            print(f"    · {r['citation']}  [{r['category']}, {r['score']:.2f}]")


def print_technical(panel: dict) -> None:
    a = panel["attack"]
    print("\n" + _rule("TECHNICAL PANEL — simulated 5G core"))
    print(f"  Incident: {a['name']}  ({a['id']})")
    print(_wrap(a["description"]))
    print(f"  Affected: {', '.join(a['affected_nf'])}")
    print("  Health:   " + "  ".join(f"{k}={v}" for k, v in panel["health"].items()))
    for al in panel["alerts"]:
        print(f"  ALERT:    {al}")
    for tier, steps in panel["tiers"].items():
        print(f"  {tier.upper():<12} " + ", ".join(
            s["fn"] + ("*" if s["auto_safe"] else "!" if s["state_changing"] else "") for s in steps))
    print("               (* auto-safe fix   ! needs your approval   others are read-only diagnostics)")


def print_event(e) -> None:
    if e.action in ("inject",):
        return
    _pause(0.6)
    if e.action == "resolution check":
        ok = e.result["resolved"]
        print(f"  [{e.tier}] RESOLUTION CHECK: {'RESOLVED' if ok else 'not resolved'}")
        for c in e.result["checks"]:
            print(f"      {'✔' if c['ok'] else '✘'} {c['fn']}.{c.get('path', '')} {c['op']} "
                  f"{c.get('value', '')}  (actual: {c['actual']})")
        return
    if e.action == "gate":
        return
    tag = "FIX " if e.state_changing else "    " if e.actor != "system" else "SYS "
    args = json.dumps(e.args) if e.args else ""
    status = "" if e.approved is None else ("approved" if e.approved else "NOT RUN")
    result = e.result if isinstance(e.result, str) else json.dumps(e.result, default=str)
    print(f"  [{e.tier}] {tag}{e.actor}: {e.action} {args} {status}")
    if e.note:
        print(_wrap(e.note, "        # "))
    if result and result != "null":
        print(_wrap(result[:400], "        → "))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Contained 5G incident-response lab.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--attack", help="attack id from catalog/attacks.yaml")
    ap.add_argument("--list", action="store_true", help="list attack ids")
    ap.add_argument("--provider", choices=["anthropic", "ollama", "offline"], help="overrides LLM_PROVIDER")
    ap.add_argument("--auto", action="store_true", help="non-interactive: agent at every gate, approve all")
    ap.add_argument("--intent", help="ML Intent (YAML) for the Y.3172 pipeline, e.g. intents/amf_signalling_storm.yaml")
    ap.add_argument("--mode", choices=["advisory", "blocking"], help="with --intent: override the P-node mode")
    ap.add_argument("--out", help="with --intent: run folder (default outputs/y3172/<run id>)")
    ap.add_argument("--pace", type=float, default=None,
                    help="seconds between steps as the attack unfolds (default 1.0 in a terminal, 0 otherwise)")
    ap.add_argument("--step", action="store_true", help="wait for Enter at each phase (presenting live)")
    ap.add_argument("--fast", action="store_true", help="no pauses")
    ap.add_argument("--full-report", action="store_true", help="also print the full report at the end")
    ap.add_argument("--llm", choices=["offline", "ollama", "anthropic"],
                    help="with --intent: reasoning model of the P node's specialist agents (default ADVISER_LLM)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    global PACE, STEP
    PACE = 0.0 if args.fast else (args.pace if args.pace is not None else
                                  (1.0 if sys.stdout.isatty() else 0.0))
    STEP = args.step and not args.fast
    _load_dotenv()
    if args.intent:
        return run_intent(args)
    from catalog.loader import load_catalog
    catalog = load_catalog()
    ids = [a["id"] for a in catalog["attacks"]]
    if args.list or not args.attack:
        for n, a in enumerate(catalog["attacks"], 1):
            print(f"{n:>3}  {a['id']:<30} {a['name']}")
        return 0
    if args.attack.strip().isdigit() and 1 <= int(args.attack) <= len(ids):   # menu number
        args.attack = ids[int(args.attack) - 1]
    if args.attack not in ids:
        print(f"Unknown attack {args.attack!r}. Type a number 1-{len(ids)} or one of these ids:")
        for n, aid in enumerate(ids, 1):
            print(f"{n:>3}  {aid}")
        return 1
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    from ir.engine import Incident
    incident = Incident(args.attack, human=CliHuman(args.auto), catalog=catalog, on_event=print_event)
    print(_rule(f"CONTAINED LAB — {incident.attack['name']} — provider: {incident.provider.name}"))
    panels = incident.start()
    print_attack_story(incident)
    _pause(1.5, "the Indian obligations that now apply")
    print_policy(panels["policy"])
    _pause(1.5, "the technical picture")
    print_technical(panels["technical"])
    _pause(1.5, "the response")
    print("\n" + _rule("BASIC tier — agent runs diagnostics and auto-safe fixes"))
    report = incident.run()
    _pause(1.5, "the summary")
    print("\n" + _rule("SUMMARY"))
    print(_wrap(report["data"]["summary"], "  "))
    print("\n" + _rule("CONCLUSION"))
    print(_wrap(report["data"]["conclusion"], "  "))
    if args.full_report:
        print("\n" + _rule("FULL REPORT"))
        print(report["markdown"])
    print("\nFull report (timeline, what fixed it, policy recap) saved:", *report["paths"], sep="\n  ")
    return 0 if report["resolved"] else 2


def print_attack_story(incident) -> None:
    """The network before the attack, then the attack as it unfolds, line by line."""
    icon = {"ok": "🟢", "degraded": "🟠", "down": "🔴", "isolated": "⚪"}
    health = lambda h: "  ".join(f"{icon.get(v, '?')} {k.upper()}" for k, v in h.items())   # noqa: E731
    print("\n" + _rule("1. THE NETWORK BEFORE THE ATTACK"))
    print("  " + health(incident.baseline_health))
    _pause(1.5, "the attack")
    print("\n" + _rule(f"2. THE ATTACK UNFOLDS — {incident.attack['name']}"))
    for s in incident.attack_story:
        _pause(1.0)
        if s["kind"] == "alert":
            print(f"  🚨 ALERT  {s['message']}")
        else:
            count = f"  (×{s['count']})" if s["count"] > 1 else ""
            print(f"  {s['at'][6:]}  [{s['nf'].upper()}] {s['level']:<7} {s['message']}{count}")
    _pause(1.0)
    print("\n" + _rule("3. DETECTED — network functions now"))
    print("  " + health(incident.detected_health))


def print_pipeline_event(e: dict) -> None:
    """One line (or a short block) per MLFO event."""
    k = e["kind"]
    _pause(0.25 if k in ("tick", "candidate_evaluated") else 1.0)
    if k == "instantiated":
        print("\n" + _rule("MLFO — pipeline instantiated from the ML Intent"))
        print(f"  {e['chain']}   ({e['feature_count']} features; levels {', '.join(e['levels'])})")
        for n in e["nodes"]:
            extra = ", ".join(n.get("telemetry", [])) or n.get("mode", "") or ", ".join(n.get("candidates", []))
            print(f"    {n['node']:<5} {n['id']:<26} {n['level']:<11} {extra}")
    elif k == "sandbox_data":
        print("\n" + _rule("ML SANDBOX — training and selection"))
        print(f"  {e['samples']} labelled samples, {e['features']} features, {e['classes']} classes, "
              f"background load {list(e['load'])} ({e['seconds']} s)")
    elif k == "candidate_evaluated":
        m = e["metrics"]
        print(f"    {e['model_id']:<20} macro-F1 {m['macro_f1']:<6}  detection-F1 {m['detection_f1']:<6}  "
              f"false alarms {m['false_alarm_rate']:<6}  p95 {m['inference_ms_p95']} ms  "
              f"{'meets intent' if e['eligible'] else 'does NOT meet intent'}")
    elif k == "model_selected":
        print(f"  → selected {e['selected']} ({e['reason']}){'' if e['meets_intent'] else '  !! below intent'}")
    elif k == "sandbox_validated":
        print("\n" + _rule("ML SANDBOX — effect of each playbook evaluated before live use"))
        for r in e["rows"]:
            print(f"    {r['incident']:<28} detected as {r['detected_as']:<28} playbook resolved: "
                  f"{'yes (' + r['resolved_in'] + ')' if r['playbook_resolved'] else 'no'}")
    elif k == "deployed":
        print("\n" + _rule(f"LIVE — {e['model_id']} deployed to the live simulated network"))
        print(f"  operator commands for this network need LAB_WORK_DIR={e['live']}")
    elif k == "tick":
        mark = "" if e["prediction"] == e["scored_truth"] else "  ✘"
        ev = f"  [{'; '.join(e['events'])}]" if e["events"] else ""
        print(f"  t{e['tick']:>3} {e['clock']}  {e['prediction']:<28} {e['confidence']:<6} "
              f"truth={e['truth']}{mark}{ev}")
    elif k == "detection":
        p = e["prediction"]
        print("\n" + _rule(f"DETECTION {e['incident_id']}", "-"))
        print(f"  M: {p['label']} (confidence {p['confidence']}, model {p['model_id']})")
        for ev in p["evidence"][:4]:
            print(f"     {ev['feature']} = {ev['value']}  (normal ≈ {ev['normal_mean']}, z {ev['z']})")
    elif k == "policy":
        d = e["decision"]
        print(f"  P: {d['decision']} ({d['mode']} mode)")
        for r in d["reasons"]:
            print(textwrap.fill(" ".join(r.split()), W, initial_indent="     - ", subsequent_indent="       "))
        for o in d["obligations"]:
            print(f"     {'✔' if o['verified'] else '✘'} {o['summary'][:95]}")
            print(f"        {o['citation']}")
        a = d.get("adviser") or {}
        if a and "error" not in a:
            print(f"     specialist agents {a['active_agents']}: verifier {a['verifier_outcomes']}")
    elif k == "dispatch":
        for s in e["sinks"]:
            print(f"  SINK {s['sink']}: {s['status']} — {s.get('detail', '')[:150]}")
            for n in s.get("notices", []):
                if "recipient" in n:
                    print(f"       · {n['recipient'][:55]:<55} deadline {n['deadline']:<20} {n['status'][:40]}")
        print("-" * W)
    elif k == "reselecting":
        print("\n" + _rule("MONITORING — score below the intent's minimum: re-calibrate and re-select", "!"))
        print(f"  rolling {e['score']}; estimated live background load {e['estimated_load']}; "
              f"new training load {list(e['new_training_load'])}")


def run_intent(args) -> int:
    from dataclasses import replace
    from pathlib import Path

    from src.y3172.intent import IntentError, load_intent
    from src.y3172.mlfo import MLFO
    try:
        intent = load_intent(args.intent)
    except (IntentError, OSError) as exc:
        print(f"intent error: {exc}")
        return 1
    if args.mode:
        intent = replace(intent, policy=replace(intent.policy, mode=args.mode))
    if args.provider:
        intent = replace(intent, remediation_agent=args.provider)
        os.environ["LLM_PROVIDER"] = args.provider
    from src import llm
    adviser_llm = llm.configure(args.llm) if args.llm else llm.active()
    if getattr(adviser_llm, "notice", ""):
        print("NOTE:", adviser_llm.notice)
    mlfo = MLFO(intent, run_dir=Path(args.out) if args.out else None, human=CliHuman(args.auto),
                on_event=print_pipeline_event, incident_event=print_event)
    os.environ["LAB_WORK_DIR"] = str(mlfo.run_dir / "live")      # operator commands (manual tiers)
    print(_rule(f"Y.3172 PIPELINE — {intent.title} — P node: {intent.policy.mode}"))
    print(f"Agents' reasoning model (P node): {adviser_llm.describe()}")
    report = mlfo.run()
    print("\n" + _rule("RUN SUMMARY"))
    for k, v in report["data"]["summary"].items():
        print(f"  {k.replace('_', ' '):<34} {v}")
    from src.audit.narrative import pipeline_narrative
    story = pipeline_narrative(report["data"])
    print("\n" + _rule("SUMMARY"))
    print(_wrap(story["summary"], "  "))
    print("\n" + _rule("CONCLUSION"))
    print(_wrap(story["conclusion"], "  "))
    print("\nSaved:", *[f"{k}: {v}" for k, v in report["paths"].items()], sep="\n  ")
    return 0


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from .env (never committed) without overriding the environment."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    sys.exit(main())
