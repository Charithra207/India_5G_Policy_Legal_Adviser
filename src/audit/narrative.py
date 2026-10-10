"""
Plain-language summary and conclusion for judges and decision-makers.
======================================================================
The stage pages show everything an agent saw, retrieved, claimed and how
each claim was verified.  That is the audit record; it is a lot to read.
This module condenses a run into two paragraphs — what happened, and what
follows from it — plus a table of the notifications the retrieved Indian
provisions may require.

Built only from what was recorded (the audit-trail entries of the adviser,
the incident of the attack lab, the report of a Y.3172 run), so a live run
and its replay read the same.  Nothing here adds a legal conclusion: every
sentence restates a recorded fact, a quoted provision or a Verifier outcome,
and the conditions under which a duty applies are kept.

    adviser_narrative(stage_entries)  -> {"summary", "conclusion", "notifications"}
    pipeline_narrative(report_data)   -> {"summary", "conclusion"}   (Y.3172 run)
"""

from __future__ import annotations

import re
from collections import Counter

# ---------------------------------------------------------------------------
# Reporting duties: recipient and time limit, from quoted Indian provisions
# ---------------------------------------------------------------------------

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8, "twelve": 12,
            "twenty-four": 24, "twenty four": 24, "forty-eight": 48, "forty eight": 48,
            "seventy-two": 72, "seventy two": 72}
_NUM = "|".join(sorted(map(re.escape, _NUMBERS), key=len, reverse=True))
_LIMIT = re.compile(rf"\b(?:within|no later than|not later than)\s+(\d+|{_NUM})\s+hours?\b"
                    r"|\bwithout\s+(?:undue\s+)?delay\b", re.IGNORECASE)
_RECIPIENT = re.compile(
    r"\b(?:report|intimat|notif|inform|furnish)\w*\b[^;.]{0,160}?\bto\s+"
    r"(?:the\s+|each\s+affected\s+|each\s+|an?\s+)?"
    r"((?:[A-Z][\w\-]*)(?:\s+(?:of\s+)?[A-Z][\w\-]*)*)")
_WINDOW = 400

# The condition under which a duty applies, by instrument, as far as the
# scenario facts go.  Shown with every row so that no duty reads as settled.
_CONDITIONS = (
    ("critical telecommunication infrastructure",
     "only if the network or slice is notified as Critical Telecommunication Infrastructure, "
     "which is not confirmed"),
    ("data protection", "if a personal-data breach is confirmed, which is currently only suspected"),
    ("cert-in", "cyber incident of a type listed in Annexure I"),
    ("cyber security", "security incident affecting the telecommunication network or service"),
)


def _hours(phrase: str) -> int:
    m = re.search(rf"(\d+|{_NUM})\s+hours?", phrase, re.IGNORECASE)
    if not m:
        return 0                                      # "without delay"
    word = m.group(1).lower()
    return int(word) if word.isdigit() else _NUMBERS[word]


def duties_in(text: str) -> list[tuple[str, list[str]]]:
    """(recipient, time limits) stated in a passage that imposes a duty ("shall")."""
    text = " ".join(text.split())
    if " shall" not in text.lower():
        return []
    recipients = [(m.start(1), m.group(1)) for m in _RECIPIENT.finditer(text)]
    if not recipients:
        return []
    found: dict[str, list[tuple[int, str]]] = {r: [] for _, r in recipients}
    for m in _LIMIT.finditer(text):
        nearest = min(recipients, key=lambda r: abs(r[0] - m.start()))
        if abs(nearest[0] - m.start()) <= _WINDOW:
            found[nearest[1]].append((_hours(m.group(0)), m.group(0)))
    return [(r, [p for _, p in sorted(set(v))]) for r, v in found.items() if v]


_RECIPIENT_NAMES = {"board": "the Data Protection Board", "data principal": "each affected Data Principal",
                    "central government": "the Central Government"}


def _recipient(name: str) -> str:
    return _RECIPIENT_NAMES.get(name.strip().lower(), name.strip())


def short_title(title: str) -> str:
    """'3GPP TS 23.501 V19.9.0 (2026-09) System architecture…' → '3GPP TS 23.501'."""
    m = re.match(r"(3GPP TS [\d.]+|ETSI \w+ [\w-]+ [\d-]+|NIST [\w.\- ]+?\d[\w.\-]*)\b", title)
    if m:
        return m.group(1).strip()
    if title.startswith("CERT-In Directions"):
        return "CERT-In Directions (28 April 2022)"
    return re.split(r"\s+[—–]\s+|:\s", title, maxsplit=1)[0].strip()


def _condition(source: str) -> str:
    low = source.lower()
    return next((c for key, c in _CONDITIONS if key in low), "as stated in the provision")


def notifications(stages: list[dict]) -> list[dict]:
    """
    Every notification duty with a time limit stated in an Indian passage the
    agents retrieved, across all stages so far: recipient, time limit, source.
    """
    rows: dict[tuple, dict] = {}
    for entry in stages:
        for agent in entry.get("agents", []):
            for p in agent.get("retrieved_passages", []):
                if str(p.get("jurisdiction", "")).strip().lower() != "india":
                    continue
                for recipient, limits in duties_in(p.get("excerpt", "")):
                    key = (recipient.lower(), p.get("source_title"), p.get("section"))
                    row = rows.setdefault(key, {
                        "recipient": _recipient(recipient), "limits": [],
                        "source": short_title(p.get("source_title", "")),
                        "section": p.get("section", ""), "page": p.get("page", ""),
                        "condition": _condition(p.get("source_title", "")),
                        "agents": [], "stage": entry["stage"]["label"],
                    })
                    row["limits"] = list(dict.fromkeys([*row["limits"], *limits]))
                    if agent["agent_id"] not in row["agents"]:
                        row["agents"].append(agent["agent_id"])
    return sorted(rows.values(), key=lambda r: (r["condition"].startswith(("if ", "only if")),
                                                min(_hours(x) for x in r["limits"]),
                                                r["recipient"].lower(), r["source"]))


def _limits_text(row: dict) -> str:
    first, *rest = row["limits"]
    return first + (f" (then {', '.join(rest)})" if rest else "")


# ---------------------------------------------------------------------------
# Adviser (Live run and Replay)
# ---------------------------------------------------------------------------

_AGENT_NAMES = {"technical": "Technical", "policy_legal": "Policy & Legal", "cybersecurity": "Cybersecurity",
                "privacy": "Privacy", "critical_infrastructure": "Critical Infrastructure",
                "standards": "Standards", "policy_gap": "Policy Gap"}


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _sentence(text: str) -> str:
    text = " ".join(str(text).split()).rstrip(".")
    return text[:1].lower() + text[1:] if text[:2] != text[:2].upper() else text


def _gap_title(gap: str) -> str:
    m = re.search(r"Potential gap\s*[—-]\s*([^:]+):", gap)
    return m.group(1).strip().lower() if m else ""


def adviser_narrative(stages: list[dict]) -> dict:
    """Summary and conclusion of the stages recorded so far (audit-trail stage entries)."""
    if not stages:
        return {"summary": "", "conclusion": "", "notifications": []}
    last = stages[-1]
    coord = last.get("coordinator", {})
    flags = coord.get("incident_flags", {}) or {}
    labels = [s["stage"]["label"] for s in stages]

    # How the incident developed, stage by stage
    steps = []
    for s in stages:
        released = s["stage"].get("information_released", "").strip()
        released = re.sub(r"^The question asks:\s*", "the question became: ", released)
        new = [_AGENT_NAMES.get(a, a) for a in s.get("orchestrator", {}).get("newly_activated", [])]
        steps.append(f"at {s['stage']['label']} {_sentence(released)}"
                     + (f" ({_join(new)} {'joined' if len(new) > 1 else 'joined'})" if new else ""))
    matches = sum(1 for s in stages if s.get("orchestrator", {}).get("matches_docx_table"))

    outcomes: Counter = Counter()
    sources: Counter = Counter()
    for s in stages:
        outcomes.update(s.get("verifier", {}).get("outcome_counts", {}))
        for a in s.get("agents", []):
            for c in a.get("claims", []):
                for cit in c.get("citations", []):
                    sources[short_title(cit.get("source_title", ""))] += 1
    top_sources = [t for t, _ in sources.most_common(5) if t]

    raised = []
    if flags.get("cyber_event_suspected"):
        raised.append("a possible cybersecurity incident")
    if flags.get("cii_flagged"):
        raised.append("relevance to a critical (healthcare) service")
    if flags.get("data_exposure_suspected"):
        raised.append("possible personal-data involvement")

    links = coord.get("cross_domain_relationships", [])
    parallel = [l for l in links if "parallel reporting" in l]
    gaps = [g for g in coord.get("potential_policy_gaps", []) if "Potential gap" in g and "GAP SUMMARY" not in g]
    gap_titles = list(dict.fromkeys(t for t in (_gap_title(g) for g in gaps) if t))

    summary = (
        (f"Across {len(stages)} stages ({labels[0]}–{labels[-1]}) the incident was released piece by piece: "
         if len(stages) > 1 else "So far one stage has been released: ")
        + f"{'; '.join(steps)}. "
        f"The Orchestrator chose the specialist agents from what each stage revealed, matching the "
        f"official stage table at {matches} of {len(stages)} stages. "
        + (f"The assessment was progressively raised to {_join(raised)}. " if raised else
           "No security, critical-service or personal-data indicator has been raised yet. ")
        + (f"The agents quoted provisions mainly from {_join(top_sources)}. " if top_sources else
           "No provision was retrieved from the knowledge bases. ")
        + "The Verifier checked every claim against the separate Canonical KB: "
        + _join([f"{n} {o}" for o, n in sorted(outcomes.items())]) + ". "
        + (f"The Coordinator linked the domains in {len(links)} evidence-based relationship"
           f"{'s' if len(links) != 1 else ''}" + (f", including {len(parallel)} case"
                                                  f"{'s' if len(parallel) != 1 else ''} of parallel "
                                                  "reporting to different authorities" if parallel else "")
           + ". " if links else "")
        + (f"Potential policy gaps raised for expert review: {_join(gap_titles)}." if gap_titles else "")
    ).strip()

    rows = notifications(stages)
    evidence_backed = coord.get("evidence_backed_conclusions", [])
    verified = outcomes.get("VERIFIED", 0)
    duty_text = "; ".join(
        f"{_limits_text(r)} to {r['recipient']} under {r['source']}, {r['section']}"
        + (f" ({r['condition']})" if r["condition"].startswith(("if ", "only if")) else "")
        for r in rows[:6])
    open_q, seen_agents = [], set()
    for q in coord.get("open_questions", []):
        m = re.match(r"\[(\w+)\]\s*(.*)", q)
        if m and m.group(1) not in seen_agents | {"policy_gap"}:   # one per agent, facts only
            seen_agents.add(m.group(1))
            open_q.append(m.group(2))
    conclusion = (
        ("On the evidence retrieved, the incident is "
         + (raised[0] + (f", with {_join(raised[1:])}" if raised[1:] else "") if raised else
            "a network performance problem; no security indicator has been released")
         + ". ")
        + (f"The quoted Indian provisions point to these notifications, each to be confirmed by a "
           f"qualified person before it is sent: {duty_text}. " if rows else
           "No notification duty with a time limit was found in the retrieved Indian provisions at this "
           "stage. ")
        + ("Time-critical: the earliest limits are counted in hours from when the entity becomes "
           "aware of the incident, so the decision on reporting should not wait for the open questions. "
           if any(_hours(x) and _hours(x) <= 24 for r in rows for x in r["limits"]) else "")
        + (f"{len(evidence_backed)} conclusion(s) are evidence-backed. " if evidence_backed else
           "No conclusion is yet fully evidence-backed"
           + (": quotes match the authoritative text, but the in-force and amendment status of the "
              "sources has not been confirmed. " if not verified else ". "))
        + (f"Still open: {'; '.join(_sentence(q) for q in open_q[:4])}. " if open_q else "")
        + (f"The {len(gap_titles)} potential gap{'s' if len(gap_titles) != 1 else ''} "
           f"({_join(gap_titles)}) are for policy experts, not findings of failure. " if gap_titles else "")
        + "This is decision support: legal interpretation and any regulatory action remain with "
          "qualified people."
    )
    return {"summary": summary, "conclusion": conclusion, "notifications": rows}


# ---------------------------------------------------------------------------
# Y.3172 ML pipeline run
# ---------------------------------------------------------------------------

def pipeline_narrative(data: dict) -> dict:
    """Summary and conclusion of a Y.3172 pipeline run (report.json 'data')."""
    s = data.get("summary", {})
    intent = data.get("intent", {}) or {}
    title = intent.get("title") or data.get("intent_title") or "the ML Intent"
    mode = s.get("policy_mode") or (intent.get("policy") or {}).get("mode", "")
    summary = (
        f"The MLFO built the Y.3172 pipeline (SRC → C → PP → M → P → D → SINK) from the intent "
        f"\"{title}\", trained and compared candidate models in the ML sandbox, deployed "
        f"{s.get('final_model', 'a model')} to the simulated live network and monitored it"
        + (f", re-selecting the model {s['reselections']} time(s) when its score fell" if s.get("reselections")
           else "")
        + f". It detected {s.get('attacks_detected_within_deadline', '?')} of "
          f"{s.get('attacks_injected', '?')} injected attack(s) within the deadline "
          f"(live detection F1 {s.get('live_detection_f1', '?')}, {s.get('false_alarm_ticks', 0)} false-alarm "
          f"tick(s)). Each detection went to the policy (P) node — the legal adviser — "
          + (f"in {mode} mode " if mode else "")
        + f"before any action: {s.get('incidents_dispatched', 0)} incident(s) were dispatched, "
          f"{s.get('notices_drafted', 0)} regulatory notice(s) drafted and {s.get('escalations', 0)} "
          "escalated."
    )
    wrong = s.get("remediations_applied_on_wrong_classification", 0)
    conclusion = (
        ("The pipeline met its detection deadline for every injected attack. "
         if s.get("attacks_detected_within_deadline") == s.get("attacks_injected") else
         "Not every injected attack was detected within the deadline; the intent is not fully met. ")
        + (f"{wrong} remediation(s) went to incidents the model had misclassified (false alarms under "
           "changed load): " + ("each was first held by the P node for human approval — the point where a "
                               "reviewer should stop it. " if mode == "blocking" else
                               "in advisory mode nothing held them, which is why blocking mode is the safer "
                               "setting. ") if wrong else "")
        + "The drafted notices carry verified deadlines and stay drafts until a person approves them. "
          "This runs on a contained simulator, not a live network."
    )
    return {"summary": summary, "conclusion": conclusion}
