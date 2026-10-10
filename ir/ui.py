"""
Minimal local web UI for the contained incident-response lab.
=============================================================
    streamlit run ir/ui.py

The incident is played as it unfolds, one step at a time — the network
before the attack, each log line and alert the attack causes, detection, the
Indian obligations that now apply, every response step, the gates — with
**Next step** or **Auto-play**, and ends with a summary and a conclusion.
Policy panel and Technical panel side by side, the timeline below, and the
tier gates as buttons.  The CLI (python run.py) is the source of truth; this
page drives the same Incident object.  Difference: a browser cannot pause
mid-tier for a y/n, so before the agent runs a tier you tick which of that
tier's state-changing actions it may perform; anything else it attempts is
declined and recorded.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from catalog.loader import TIERS, load_catalog  # noqa: E402
from ir.engine import Incident  # noqa: E402
from ir.llm import AnthropicProvider, OfflineProvider, get_provider  # noqa: E402


class WebHuman:
    """Answers from what the operator chose on the page."""

    def __init__(self) -> None:
        self.approved_fns: set[str] = set()
        self.pasted = ""

    def gate(self, tier: str, message: str) -> str:      # gates are buttons; not called
        return "stop"

    def confirm(self, description: str) -> bool:
        return description.split("(", 1)[0] in self.approved_fns

    def manual(self, tier: str, commands: list[str]) -> str:
        return self.pasted


def _provider(choice: str):
    if choice == "offline":
        return OfflineProvider()
    try:
        return AnthropicProvider() if choice == "anthropic" else get_provider()
    except Exception as exc:                              # no key / no SDK
        st.warning(f"Claude provider unavailable ({exc}); using the offline playbook.")
        return OfflineProvider()


def policy_panel(panel: dict) -> None:
    st.subheader("Policy — Indian obligations")
    st.caption("Decision support for a training lab, not legal advice.")
    if panel.get("error"):
        st.warning(panel["error"])
    for ob in panel.get("obligations", []):
        with st.container(border=True):
            st.markdown(f"{'✅' if ob['found'] else '⚠️'} **{ob['summary']}**")
            if ob["applies_when"]:
                st.caption(f"When: {ob['applies_when']}")
            st.markdown(f"`{ob['citation']}`")
            if ob["passage"]:
                st.caption(f"“{ob['passage'][:400]}”")
    if panel.get("related"):
        with st.expander("Related passages"):
            for r in panel["related"]:
                st.markdown(f"**{r['citation']}** · {r['category']} · {r['score']:.2f}")
                st.caption(r["text"][:350])


def technical_panel(inc: Incident) -> None:
    t = inc.technical_panel()
    st.subheader("Technical — simulated 5G core")
    st.markdown(f"**{t['attack']['name']}** — {t['attack']['description']}")
    cols = st.columns(len(t["health"]))
    icon = {"ok": "🟢", "degraded": "🟠", "down": "🔴", "isolated": "⚪"}
    for col, (nf, h) in zip(cols, t["health"].items()):
        col.markdown(f"{icon.get(h, '❔')}<br>**{nf.upper()}**<br><small>{h}</small>", unsafe_allow_html=True)
    for a in t["alerts"]:
        st.error(a, icon="🚨")
    ok, checks = inc.resolution()
    st.markdown("**Resolution checks**")
    for c in checks:
        st.markdown(f"{'✅' if c['ok'] else '❌'} `{c['fn']}.{c.get('path', '')} {c['op']} "
                    f"{c.get('value', '')}` — actual `{c['actual']}`")
    with st.expander("Playbook"):
        for tier, steps in t["tiers"].items():
            st.markdown(f"**{tier.title()}**")
            for s in steps:
                tag = " · auto-safe" if s["auto_safe"] else " · needs approval" if s["state_changing"] else ""
                st.markdown(f"- `{s['fn']}` — {s['description']}{tag}")


def timeline(inc: Incident) -> None:
    st.subheader("Timeline")
    rows = [{"time": e.at, "tier": e.tier, "actor": e.actor, "action": e.action,
             "args": json.dumps(e.args) if e.args else "",
             "approved": "" if e.approved is None else ("yes" if e.approved else "no"),
             "result / note": ((e.result if isinstance(e.result, str) else json.dumps(e.result, default=str))
                               or "")[:200] + (f"  # {e.note}" if e.note else "")}
            for e in inc.timeline]
    st.dataframe(rows, width="stretch", hide_index=True)


def gate(inc: Incident, human: WebHuman, tier: str) -> None:
    st.subheader(f"Gate — {inc.gate_message(tier)}")
    fns = sorted({s["action"]["fn"] for s in inc.attack["playbook"][tier] if s["is_state_changing"]})
    approved = st.multiselect("State-changing actions the agent may perform in this tier", fns, default=fns,
                              key=f"approve_{tier}")
    c1, c2, c3 = st.columns(3)
    if c1.button("[1] Agent runs it", type="primary", key=f"agent_{tier}"):
        human.approved_fns = set(approved)
        with st.spinner(f"Agent running the {tier} tier…"):
            inc.advance(tier, "agent")
        st.rerun()
    if c2.button("[2] I'll run it", key=f"manual_{tier}"):
        st.session_state.manual_tier = tier
        st.rerun()
    if c3.button("[3] Stop", key=f"stop_{tier}"):
        inc.advance(tier, "stop")
        st.rerun()


def manual(inc: Incident, human: WebHuman, tier: str) -> None:
    st.subheader(f"{tier.title()} tier — you run it")
    st.markdown("Run these in a terminal in the repository folder (same `LAB_WORK_DIR`), in order:")
    st.code("\n\n".join(inc.manual_commands(tier)), language="bash")
    pasted = st.text_area("Paste the output here", height=200, key=f"paste_{tier}")
    if st.button("Submit results", type="primary"):
        human.pasted = pasted
        st.session_state.manual_tier = None
        with st.spinner("Interpreting your results…"):
            inc.advance(tier, "manual")
        st.rerun()


# ---------------------------------------------------------------------------
# Step-by-step playback
# ---------------------------------------------------------------------------

_ICON = {"ok": "🟢", "degraded": "🟠", "down": "🔴", "isolated": "⚪"}


def _health_line(health: dict) -> str:
    return "  ".join(f"{_ICON.get(v, '❔')} **{k.upper()}** {v}" for k, v in health.items())


def _event_step(e) -> dict | None:
    """One timeline event as one step of the story (None: not shown)."""
    if e.action in ("inject", "gate"):
        return None
    if e.action == "resolution check":
        ok = e.result["resolved"]
        failing = [f"`{c['fn']}.{c.get('path', '')}` (actual `{c['actual']}`)"
                   for c in e.result["checks"] if not c["ok"]]
        return {"phase": e.tier, "kind": "success" if ok else "warning",
                "title": f"{e.tier.title()} tier — resolution check: {'RESOLVED' if ok else 'not resolved'}",
                "body": "All checks pass against the simulator." if ok else "Still failing: " + ", ".join(failing)}
    args = ", ".join(f"{k}={v}" for k, v in e.args.items()) if e.args else ""
    if e.state_changing:
        kind = "error" if e.approved is False else "success"
        what = "Fix NOT run" if e.approved is False else "Fix applied"
    else:
        kind, what = "info", "Diagnostic" if e.actor != "system" else "System"
    result = e.result if isinstance(e.result, str) else json.dumps(e.result, default=str)
    body = (f"_{e.note}_  \n" if e.note else "") + (f"→ `{result[:300]}`" if result and result != "null" else "")
    return {"phase": e.tier, "kind": kind, "title": f"{e.tier.title()} tier — {what}: `{e.action}({args})`",
            "body": body}


def build_steps(inc: Incident) -> list[dict]:
    """The whole story so far, in order; the page reveals it one step at a time."""
    steps = [{"phase": "before", "kind": "info", "title": "The network before the attack",
              "body": _health_line(inc.baseline_health)}]
    for s in inc.attack_story:
        if s["kind"] == "alert":
            steps.append({"phase": "attack", "kind": "error", "title": "🚨 Alert raised", "body": s["message"]})
        else:
            count = f" (×{s['count']})" if s["count"] > 1 else ""
            steps.append({"phase": "attack", "kind": "warning" if s["level"] != "INFO" else "info",
                          "title": f"The attack unfolds — {s['at'][6:]} [{s['nf'].upper()}] {s['level']}",
                          "body": s["message"] + count})
    steps.append({"phase": "detected", "kind": "warning", "title": "Detected — network functions now",
                  "body": _health_line(inc.detected_health)})
    obligations = inc.policy_panel.get("obligations", [])
    steps.append({"phase": "policy", "kind": "info",
                  "title": f"Indian obligations that now apply ({len(obligations)})",
                  "body": "  \n".join(f"{'✅' if o['found'] else '⚠️'} {o['summary']} — `{o['citation']}`"
                                      for o in obligations) or "None listed."})
    for e in inc.timeline:
        step = _event_step(e)
        if step:
            steps.append(step)
    return steps


def render_step(step: dict, current: bool) -> None:
    box = {"info": st.info, "warning": st.warning, "error": st.error, "success": st.success}[step["kind"]]
    box(f"**{step['title']}**  \n{step['body']}" if step["body"] else f"**{step['title']}**")


def summary_block(inc: Incident) -> None:
    if st.session_state.get("report") is None:
        st.session_state.report = inc.final_report()
    report = st.session_state.report
    (st.success if inc.phase == "resolved" else st.warning)(f"Incident {inc.phase.upper()}.")
    st.header("Summary")
    st.write(report["data"]["summary"])
    st.header("Conclusion")
    st.write(report["data"]["conclusion"])
    with st.expander("Full report (timeline, what fixed it, policy recap)"):
        st.markdown(report["markdown"])
        st.caption("Saved: " + " · ".join(report["paths"]))


def main() -> None:
    st.set_page_config(page_title="5G IR Lab", layout="wide")
    st.title("Contained 5G incident-response lab")
    st.caption("Everything runs against a local Python simulation. Nothing reaches a real network.")
    catalog = load_catalog()
    ids = [a["id"] for a in catalog["attacks"]]
    with st.sidebar:
        attack_id = st.selectbox("Attack", ids, format_func=lambda i: next(
            a["name"] for a in catalog["attacks"] if a["id"] == i))
        provider = st.radio("Agent", ["auto (LLM_PROVIDER)", "offline", "anthropic"])
        if st.button("Reset and inject the attack", type="primary"):
            human = WebHuman()
            inc = Incident(attack_id, provider=_provider(provider.split()[0]), human=human, catalog=catalog)
            with st.spinner("Resetting the simulated core and injecting the attack…"):
                inc.start()
            st.session_state.update(incident=inc, human=human, manual_tier=None, report=None, shown=1,
                                    basic_done=False)
        st.divider()
        st.subheader("Playback")
        autoplay = st.toggle("Auto-play", value=False, help="Reveal the next step automatically")
        delay = st.slider("Seconds per step", 0.5, 5.0, 1.5, 0.5)
        show_panels = st.toggle("Show Policy and Technical panels", value=False)
    inc: Incident | None = st.session_state.get("incident")
    if inc is None:
        st.info("Choose an attack and press **Reset and inject the attack**. The incident is then shown "
                "step by step: press **Next step**, or switch on **Auto-play**.")
        return
    human: WebHuman = st.session_state.human
    st.caption(f"Provider: {inc.provider.name} · phase: **{inc.phase}**")

    steps = build_steps(inc)
    shown = min(st.session_state.get("shown", 1), len(steps))
    at_end = shown >= len(steps)
    # The Basic tier starts once the story so far has been shown (it is automatic, as in the CLI)
    if at_end and not st.session_state.get("basic_done"):
        st.session_state.basic_done = True
        with st.spinner("Basic tier: the agent runs diagnostics and auto-safe fixes…"):
            if inc.run_tier("basic", "agent"):
                inc.phase = "resolved"
        st.rerun()

    st.progress(shown / len(steps), text=f"Step {shown} of {len(steps)}")
    for i, step in enumerate(steps[:shown]):
        render_step(step, current=i == shown - 1)
    c1, c2, _ = st.columns([1, 1, 4])
    if not at_end:
        if c1.button("Next step ▶", type="primary"):
            st.session_state.shown = shown + 1
            st.rerun()
        if c2.button("Show all"):
            st.session_state.shown = len(steps)
            st.rerun()

    if show_panels:
        left, right = st.columns(2)
        with left:
            policy_panel(inc.policy_panel)
        with right:
            technical_panel(inc)
        timeline(inc)

    if not at_end:
        if autoplay:
            time.sleep(delay)
            st.session_state.shown = shown + 1
            st.rerun()
        return
    if inc.phase in ("resolved", "stopped", "exhausted"):
        summary_block(inc)
    elif st.session_state.get("manual_tier"):
        manual(inc, human, st.session_state.manual_tier)
    else:
        nxt = TIERS[TIERS.index(inc.phase) + 1]
        gate(inc, human, nxt)


main()
