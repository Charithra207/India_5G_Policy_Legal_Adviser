"""
Regulatory-notice SINK: draft notices with deadlines (decision support)
=======================================================================
For each obligation the policy node attached to an incident, a draft notice
for its recipient with the deadline counted from the detection time.  Every
deadline rests on a phrase that is looked up word for word in its source in
the committed index (kb/index); the draft shows the file and page, or says
UNVERIFIED.  Drafts are never sent: each says it needs human review and
sign-off.

Deadline rules (text checked in the documents, 2026-10):
  Telecom Cyber Security Rules, 2024, rule 7(1)   Central Government: 6 h after becoming
                                                  aware (report), 24 h (details (i)-(vi))
  CERT-In Directions (28.04.2022), direction (ii) CERT-In: 6 h after noticing
  CTI Rules, 2024, rule 7(1)(j)                   Central Government: 6 h after OCCURRENCE —
                                                  only if the element is notified as CTI
  DPDP Rules, 2025, rule 7                        each affected Data Principal and the
                                                  Board: without delay; Board: details
                                                  within 72 h — in force only 18 months
                                                  after G.S.R. 843(E) (13 Nov 2025)
  CERT-In Directions, direction (iv)              preserve ICT logs (rolling 180 days)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

DPDP_PUBLICATION = date(2025, 11, 13)          # G.S.R. 843(E), Gazette of India, 13 Nov 2025
DPDP_BREACH_DUTIES_FROM = date(2027, 5, 13)    # "eighteen months from the date of publication"

# obligation id -> notices it produces
RULES: dict[str, list[dict]] = {
    "tcs_rules_rule7_6h": [
        {"key": "dot_initial", "recipient": "Central Government (Department of Telecommunications)",
         "what": "Report of the security incident with relevant details of the affected system and a "
                 "description of the incident",
         "hours": 6, "from": "becoming aware", "instrument": "Telecom Cyber Security Rules, 2024, rule 7(1)(a)",
         "doc": "cybersecurity-rules-2024.pdf",
         "phrase": "within six hours of becoming aware of a security incident"},
        {"key": "dot_details", "recipient": "Central Government (Department of Telecommunications)",
         "what": "Details: (i) users affected, (ii) duration, (iii) geographical area, (iv) extent to which "
                 "the network or service is affected, (v) remedial measures, (vi) other relevant information",
         "hours": 24, "from": "becoming aware", "instrument": "Telecom Cyber Security Rules, 2024, rule 7(1)(b)",
         "doc": "cybersecurity-rules-2024.pdf", "phrase": "within twenty-four hours of becoming aware"},
    ],
    "certin_6h": [
        {"key": "certin", "recipient": "CERT-In (incident@cert-in.org.in)",
         "what": "Report of the cyber incident (if it is of a type listed in Annexure I of the Directions)",
         "hours": 6, "from": "noticing", "instrument": "CERT-In Directions under s.70B(6) IT Act, direction (ii)",
         "doc": "CERT-In_Directions_70B_28.04.2022.pdf", "phrase": "within 6 hours of noticing such incidents"},
    ],
    "cti_rules_reporting": [
        {"key": "cti", "recipient": "Central Government (Critical Telecommunication Infrastructure)",
         "what": "Intimation of the security incident in the form and manner specified on the portal",
         "hours": 6, "from": "occurrence", "condition": "only if the affected element is notified as "
                                                         "Critical Telecommunication Infrastructure",
         "instrument": "Telecommunications (Critical Telecommunication Infrastructure) Rules, 2024, rule 7(1)(j)",
         "doc": "Critical Telecommunication Infrastructure Rules, 2024_0.pdf",
         "phrase": "no later than six hours of occurrence of such incident"},
    ],
    "dpdp_act_s8_6": [
        {"key": "dpdp_principals", "recipient": "Each affected Data Principal",
         "what": "Description of the breach, likely consequences, mitigation, safety measures and a contact",
         "hours": None, "from": "becoming aware", "instrument": "DPDP Act, 2023 s.8(6); DPDP Rules, 2025, rule 7(1)",
         "doc": "53450e6e5dc0bfa85ebd78686cadad39.pdf", "phrase": "intimate to each affected Data Principal",
         "dpdp": True},
        {"key": "dpdp_board_initial", "recipient": "Data Protection Board of India",
         "what": "Without delay: description of the breach — nature, extent, timing, location, likely impact",
         "hours": None, "from": "becoming aware", "instrument": "DPDP Rules, 2025, rule 7(2)(a)",
         "doc": "53450e6e5dc0bfa85ebd78686cadad39.pdf", "phrase": "shall intimate to the Board", "dpdp": True},
    ],
    "dpdp_rules_rule7_72h": [
        {"key": "dpdp_board_details", "recipient": "Data Protection Board of India",
         "what": "Updated and detailed information, facts and reasons, mitigation, findings about the person "
                 "responsible, remedial measures, report of intimations to Data Principals",
         "hours": 72, "from": "becoming aware", "instrument": "DPDP Rules, 2025, rule 7(2)(b)",
         "doc": "53450e6e5dc0bfa85ebd78686cadad39.pdf",
         "phrase": "within seventy-two hours of becoming aware of the breach", "dpdp": True},
    ],
}

ACTIONS = {
    "certin_logs_180d": {"what": "Preserve the ICT system logs of the incident (CERT-In direction (iv): rolling "
                                 "180 days, within Indian jurisdiction); provide them to CERT-In with the "
                                 "incident report or on request",
                         "doc": "CERT-In_Directions_70B_28.04.2022.pdf", "phrase": "rolling period of 180 days"},
}


def _verify(doc: str, phrase: str) -> str:
    try:
        from kb.retriever import cite, find_passage
        hit = find_passage(doc, phrase)
    except (ImportError, FileNotFoundError) as exc:
        return f"UNVERIFIED — index not available ({exc})"
    return f"verified in {cite(hit)}" if hit else f"UNVERIFIED — phrase not found in {doc}"


def draft_notices(decision, detected_at: datetime, facts: dict, out_dir: Path | None,
                  confirmed: bool = True) -> list[dict]:
    """
    Draft notices for the obligations in `decision` (a PolicyDecision).
    `facts`: what the lab knows (affected NFs, users, area, remedial measures,
    alerts) to pre-fill the drafts.  `confirmed` is False when the operator
    declined the policy node's hold: the drafts are then marked ON HOLD.
    Writes one markdown file per notice to `out_dir` when given.
    """
    ids = {o["id"] for o in decision.obligations}
    dpdp_in_force = detected_at.date() >= DPDP_BREACH_DUTIES_FROM
    notices = []
    for ob_id, specs in RULES.items():
        if ob_id not in ids:
            continue
        for spec in specs:
            if spec["key"] == "dpdp_board_details" and "dpdp_act_s8_6" not in ids and "dpdp_rules_rule7_72h" not in ids:
                continue
            deadline = detected_at + timedelta(hours=spec["hours"]) if spec["hours"] else None
            status = "DRAFT — requires human review and sign-off; not sent"
            notes = []
            if spec.get("dpdp") and not dpdp_in_force:
                status = "PREPAREDNESS DRAFT — duty not yet in force on the incident date"
                notes.append(f"DPDP breach duties come into force on {DPDP_BREACH_DUTIES_FROM:%d %b %Y} "
                             f"(eighteen months after G.S.R. 843(E), {DPDP_PUBLICATION:%d %b %Y}); "
                             f"incident date {detected_at:%d %b %Y}.")
            if spec.get("condition"):
                status = "CONDITIONAL DRAFT — " + spec["condition"]
            if not confirmed:
                status = ("ON HOLD (the operator did not confirm the incident; complete and send only if it is "
                          "confirmed) — " + status)
            if spec["from"] == "occurrence":
                notes.append("This deadline runs from OCCURRENCE, which may be earlier than detection; "
                             "establish the occurrence time from the logs. The deadline shown is the latest "
                             "possible.")
            notices.append({
                "incident_id": decision.incident_id, "key": spec["key"], "recipient": spec["recipient"],
                "what": spec["what"], "instrument": spec["instrument"], "status": status,
                "deadline": deadline.isoformat() if deadline else "without delay",
                "counted_from": f"{spec['from']} ({detected_at:%d %b %Y %H:%M} simulated clock)",
                "source_check": _verify(spec["doc"], spec["phrase"]), "phrase": spec["phrase"], "notes": notes,
            })
    actions = [{"incident_id": decision.incident_id, "obligation": k, "action": v["what"],
                "source_check": _verify(v["doc"], v["phrase"])} for k, v in ACTIONS.items() if k in ids]
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        for n in notices:
            (out_dir / f"{n['key']}.md").write_text(_markdown(n, decision, facts), encoding="utf-8")
    return notices + [{"key": f"action_{a['obligation']}", **a} for a in actions]


def _markdown(n: dict, decision, facts: dict) -> str:
    lines = [f"# {n['status']}", "", f"**To:** {n['recipient']}  ",
             f"**Deadline:** {n['deadline']} (counted from {n['counted_from']})  ",
             f"**Legal basis:** {n['instrument']} — “{n['phrase']}” ({n['source_check']})", "",
             f"**Required content:** {n['what']}", "", "## Incident", "",
             f"- Incident: `{decision.incident_id}` — {facts.get('name', decision.label)} (simulated, contained lab)",
             f"- Detected by: {facts.get('detected_by', '')}",
             f"- Affected network functions: {', '.join(facts.get('affected_nf', []))}",
             f"- Alerts: {'; '.join(facts.get('alerts', [])) or 'none'}",
             f"- Users potentially affected: {facts.get('users', 'to be established')}",
             f"- Geographical area: {facts.get('area', 'to be established')}",
             f"- Remedial measures so far: {'; '.join(facts.get('remedial_measures', [])) or 'none yet'}", ""]
    if n["notes"]:
        lines += ["## Notes", ""] + [f"- {x}" for x in n["notes"]] + [""]
    lines += ["_Draft generated by the Y.3172 pipeline's notice SINK. Decision support for a training lab; "
              "not legal advice. A qualified person must review, complete and send it._"]
    return "\n".join(lines) + "\n"
