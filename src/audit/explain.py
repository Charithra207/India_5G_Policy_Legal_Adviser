"""
Replay explanation
==================
For one recorded stage, answers the reviewer's questions from the audit
entry alone (DOCX §7.6: "a judge can replay a scenario by loading the chunk
sequence and matching each record to retrieved evidence and the final
assessment"):

  1. What happened?            the information released, and what it changed
  2. Which agent acted?        the agents the Orchestrator selected, and why
  3. What evidence was retrieved?  per agent: passages, sources, sections
  4. What was concluded?       each agent's decision summary and quoted claims
  5. How was it verified?      verifier outcomes, with the rationale of each kind
  6. How did the Coordinator reach the assessment?
                               the five categories, cross-domain links,
                               conflicts, open questions, what changed

Nothing is inferred: every line is read from the recorded entry.
"""

from __future__ import annotations

from collections import Counter

OUTCOME_ORDER = ("VERIFIED", "INCOMPLETE", "UNSUPPORTED", "CONFLICT")
CATEGORIES = (
    ("confirmed_facts", "confirmed facts"),
    ("evidence_backed_conclusions", "evidence-backed conclusions"),
    ("uncertain_conclusions", "uncertain conclusions"),
    ("conflicting_findings", "conflicting findings"),
    ("potential_policy_gaps", "potential policy gaps"),
)


def _ref(p: dict) -> str:
    return f"{p['source_title']}, {p['section']}" + (f" (p. {p['page']})" if p.get("page") else "")


def explain_stage(entry: dict) -> dict[str, list[str]]:
    stage, orch = entry["stage"], entry["orchestrator"]
    coord, verifier = entry["coordinator"], entry["verifier"]

    happened = [f"{stage['label']} ({stage['chunk_id']}): \"{stage['information_released']}\""]
    happened += [f"New fact: {f}" for f in stage["new_facts"]]
    if stage.get("docx_expected_change"):
        happened.append(f"DOCX expected change: {stage['docx_expected_change']}")

    acted = [f"Active: {', '.join(orch['active_agents'])}"]
    if orch["newly_activated"]:
        acted.append(f"Newly activated: {', '.join(orch['newly_activated'])}")
    if orch.get("no_longer_active"):
        acted.append(f"Not active at this stage: {', '.join(orch['no_longer_active'])}")
    if orch.get("matches_docx_table") is not None:
        acted.append("Selection " + ("matches" if orch["matches_docx_table"] else "differs from")
                     + f" the DOCX stage table ({', '.join(orch['docx_primary_agents'])}).")

    evidence, concluded = [], []
    for agent in entry["agents"]:
        real = [p for p in agent["retrieved_passages"] if not p.get("is_stub")]
        if real:
            sources = Counter(p["source_title"] for p in real)
            evidence.append(f"{agent['agent_id']}: {len(real)} passage(s) from its own KB — "
                            + "; ".join(f"{s} ×{n}" for s, n in sources.most_common(3)))
        else:
            evidence.append(f"{agent['agent_id']}: no passage retrieved")
        concluded.append(f"{agent['agent_id']}: {agent['decision_summary']}")
        for claim in agent["claims"]:
            if claim["citations"]:
                concluded.append(f"  quotes {_ref(claim['citations'][0])} → {claim['verifier_outcome']}")

    counts = verifier["outcome_counts"]
    verified = ["Outcomes: " + ", ".join(f"{o} {counts.get(o, 0)}" for o in OUTCOME_ORDER)]
    seen = set()
    for agent in entry["agents"]:
        for claim in agent["claims"]:
            outcome = claim["verifier_outcome"]
            if outcome not in seen:
                seen.add(outcome)
                verified.append(f"{outcome} — e.g. [{agent['agent_id']}] {claim['verifier_rationale']}")

    coordinator = ["Five categories (DOCX Table A1): " + "; ".join(
        f"{label} {len(coord[key])}" for key, label in CATEGORIES)]
    coordinator += [f"Changed: {c}" for c in coord["changes_from_prior"]]
    links = verifier.get("cross_domain_details", [])
    if links:
        kinds = Counter(f"{l['agents'][0]} ↔ {l['agents'][1]} ({l['kind'].replace('_', ' ')})" for l in links)
        coordinator.append(f"Cross-domain links established from evidence: {len(links)} — "
                           + "; ".join(kinds))
    for c in verifier.get("conflict_details", []):
        coordinator.append(f"Conflict: {c['basis']} Treatment: {c['coordinator_treatment']}")
    questions = coord.get("open_questions", [])
    if questions:
        coordinator.append(f"Open questions: {len(questions)} (first: {questions[0]})")
    coordinator.append(f"Human review: {coord['human_review_required']}")

    return {
        "What happened?": happened,
        "Which agent acted?": acted,
        "What evidence was retrieved?": evidence,
        "What was concluded?": concluded,
        "How was it verified?": verified,
        "How did the Coordinator reach the assessment?": coordinator,
    }
