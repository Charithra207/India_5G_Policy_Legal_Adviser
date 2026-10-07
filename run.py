"""
Contained 5G incident-response lab — command line (the source of truth).
=======================================================================
    python run.py --list
    python run.py --attack signalling_storm_amf
    python run.py --attack nf_host_ransomware --provider offline
    python run.py --attack core_ddos_upf --auto        # approve everything, agent at every gate

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

W = 100


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
    ap.add_argument("--provider", choices=["anthropic", "offline"], help="overrides LLM_PROVIDER")
    ap.add_argument("--auto", action="store_true", help="non-interactive: agent at every gate, approve all")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    _load_dotenv()
    from catalog.loader import load_catalog
    catalog = load_catalog()
    if args.list or not args.attack:
        for a in catalog["attacks"]:
            print(f"{a['id']:<30} {a['name']}")
        return 0
    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider

    from ir.engine import Incident
    incident = Incident(args.attack, human=CliHuman(args.auto), catalog=catalog, on_event=print_event)
    print(_rule(f"CONTAINED LAB — {incident.attack['name']} — provider: {incident.provider.name}"))
    panels = incident.start()
    print_policy(panels["policy"])
    print_technical(panels["technical"])
    print("\n" + _rule("BASIC tier — agent runs diagnostics and auto-safe fixes"))
    report = incident.run()
    print("\n" + _rule("FINAL REPORT"))
    print(report["markdown"])
    print("Saved:", *report["paths"], sep="\n  ")
    return 0 if report["resolved"] else 2


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
