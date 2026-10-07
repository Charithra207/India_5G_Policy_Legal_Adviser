"""Final incident report: timeline, what fixed it (or escalation), policy recap."""

from __future__ import annotations

import json


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
             f"- Provider: {getattr(incident.provider, 'name', '?')}", "",
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
    data = {"attack": a["id"], "outcome": "resolved" if ok else incident.phase,
            "resolved_in": resolving_tier, "checks": checks, "tier_outcomes": incident.tier_outcomes,
            "timeline": [e.__dict__ for e in incident.timeline], "policy": incident.policy_panel}
    return {"markdown": "\n".join(lines) + "\n", "data": data, "resolved": resolved_ok}
