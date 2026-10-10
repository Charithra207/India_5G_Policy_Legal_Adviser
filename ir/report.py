"""Final incident report: timeline, what fixed it (or escalation), policy recap."""

from __future__ import annotations

import json


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    return "".join(items) if len(items) <= 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _sentence(text: str) -> str:
    text = " ".join(str(text).split()).rstrip(".")
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


def incident_narrative(incident) -> dict:
    """
    Two paragraphs for the end of the report: what happened, and what follows.
    Every sentence restates the timeline, the resolution checks or the Policy
    panel; nothing is concluded beyond them.
    """
    a = incident.attack
    resolved, checks = incident.resolution()
    timeline = incident.timeline
    alerts = []
    for e in timeline:
        if e.action == "inject" and isinstance(e.result, dict):
            alerts = e.result.get("alerts", [])
    tiers_run = [t for t in incident.tier_outcomes]
    diagnostics = [e for e in timeline if e.actor in ("agent", "operator") and not e.state_changing
                   and e.action not in ("gate", "pasted results")]
    fixes = [e for e in timeline if e.state_changing and e.approved and e.action != "inject"]
    refused = [e for e in timeline if e.state_changing and e.approved is False]
    resolving = next((t for t, o in incident.tier_outcomes.items() if o.get("resolved")), None)
    obligations = incident.policy_panel.get("obligations", [])
    found = [o for o in obligations if o.get("found")]

    summary = (
        f"The simulated attack \"{a['name']}\" was injected into the contained 5G core, affecting "
        f"{_join([n.upper() for n in a.get('affected_nf', [])])}. "
        + (f"It was first visible as: {_sentence(alerts[0])}. " if alerts else "")
        + f"The response agent ({getattr(incident.provider, 'name', 'agent')}) worked through the "
          f"{_join(tiers_run) or 'basic'} tier{'s' if len(tiers_run) > 1 else ''}, running "
          f"{len(diagnostics)} diagnostic step{'s' if len(diagnostics) != 1 else ''}"
        + (f" and {len(fixes)} approved fix{'es' if len(fixes) != 1 else ''} "
           f"({_join(sorted({f.action for f in fixes}))})" if fixes else " and no fix")
        + (f"; {len(refused)} state-changing step{'s were' if len(refused) != 1 else ' was'} refused or "
           "declined at a safety gate" if refused else "")
        + ". The Policy panel listed "
        + f"{len(obligations)} Indian obligation{'s' if len(obligations) != 1 else ''} for this kind of "
          f"incident, {len(found)} confirmed word for word in the cited documents."
    )
    if resolved:
        outcome = (f"The incident was resolved in the {resolving} tier: every resolution check passes "
                   "against the simulator (not on the agent's own say-so). ")
    elif incident.phase == "stopped":
        outcome = "The operator stopped the response before the incident was resolved. "
    else:
        failing = [f"{c['fn']} {c.get('path', '')}".strip() for c in checks if not c["ok"]]
        outcome = (f"The playbook tiers did not resolve it ({_join(failing[:3])} still failing), so it "
                   "must be escalated to the security operations lead and the vendor with the logs preserved. ")
    clocks = [o["summary"] for o in found][:3]
    conclusion = (
        outcome
        + (f"Whatever the technical outcome, the Indian obligations listed still apply, among them: "
           f"{'; '.join(_sentence(c) for c in clocks)}. " if clocks else "")
        + "Every action, approval and refusal is in the timeline and the saved report. "
          "This is a training simulation and decision support, not legal advice."
    )
    return {"summary": summary, "conclusion": conclusion}


def build_report(incident) -> dict:
    a, ok = incident.attack, incident.resolved()
    resolved_ok, checks = incident.resolution()
    changes = [e for e in incident.timeline
               if e.state_changing and e.approved is not False and e.action != "inject"]
    resolving_tier = next((t for t, o in incident.tier_outcomes.items() if o.get("resolved")), None)
    lines = [f"# Incident report — {a['name']}", "",
             f"- Attack id: `{a['id']}` (simulated, contained lab)",
             f"- Outcome: **{'RESOLVED' if ok else incident.phase.upper()}**"
             + (f" in the {resolving_tier} tier" if resolving_tier else ""),
             f"- Provider: {getattr(incident.provider, 'name', '?')}", ""]
    story = incident_narrative(incident)
    lines += ["## Summary", "", story["summary"], "", "## Conclusion", "", story["conclusion"], "",
              "## Timeline", "", "| time | tier | actor | action | approved | result / note |",
             "|---|---|---|---|---|---|"]
    for e in incident.timeline:
        res = e.result if isinstance(e.result, str) else json.dumps(e.result, default=str)
        lines.append(f"| {e.at} | {e.tier} | {e.actor} | `{e.action}` {json.dumps(e.args) if e.args else ''} | "
                     f"{'' if e.approved is None else ('yes' if e.approved else 'no')} | "
                     f"{(res or '')[:140].replace('|', '/')} {e.note[:120].replace('|', '/')} |")
    lines += ["", "## What fixed it" if ok else "## Escalation", ""]
    if ok:
        lines += [f"- `{e.action}` {json.dumps(e.args)} ({e.tier})" for e in changes] or ["- (no change needed)"]
    else:
        lines += ["The playbook tiers did not resolve the incident. Escalate to the security operations "
                  "lead and the platform vendor; preserve logs from sim/logs/ and this report.",
                  "", "Checks still failing:"]
        lines += [f"- {c['fn']} {c.get('path', '')} {c['op']} {c.get('value')} (actual: {c['actual']})"
                  for c in checks if not c["ok"]]
    lines += ["", "## Policy obligations recap", ""]
    for ob in incident.policy_panel.get("obligations", []):
        lines.append(f"- **{ob['summary']}**" + (f" — when {ob['applies_when']}" if ob["applies_when"] else "")
                     + f"  \n  Source: {ob['citation']}")
    lines += ["", "_Decision support for a training lab; not legal advice._"]
    data = {"attack": a["id"], "outcome": "resolved" if ok else incident.phase, **story,
            "resolved_in": resolving_tier, "checks": checks, "tier_outcomes": incident.tier_outcomes,
            "timeline": [e.__dict__ for e in incident.timeline], "policy": incident.policy_panel}
    return {"markdown": "\n".join(lines) + "\n", "data": data, "resolved": resolved_ok}
