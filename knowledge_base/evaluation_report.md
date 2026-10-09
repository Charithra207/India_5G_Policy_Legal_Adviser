# Evaluation summary (internal)

Generated 2026-10-06T16:45:15 UTC by `python -m src.audit.evaluation_report` — statuses follow the rules in that module; counts are from the test run and the recorded runs.

**Test suite:** 392 passed, 0 failed, 0 skipped.

**Live 4-stage run** (`outputs/audit/day2_scenario2_full_T0_T3.jsonl`): T0: technical; T1: cybersecurity, standards, technical; T2: critical_infrastructure, policy_legal, privacy; T3: critical_infrastructure, cybersecurity, policy_gap, policy_legal, privacy. Agent sets match the DOCX table: yes. Verifier outcomes: INCOMPLETE 50, UNSUPPORTED 10. Cross-domain links: instrument basis 12, parallel reporting 4, shared provision 7. Conflicts: 0 (none expected — no real provisions disagree). Potential policy gaps at T3: 4. Conflict demonstration on labelled fixtures (`outputs/audit/day2_conflict_demo_FIXTURE.jsonl`): 2 conflict records.

## DOCX evaluation areas

| Capability | Status | Tests (pass/fail) | Why |
|---|---|---|---|
| Technical analysis | Working | 6/0 | T0 classifies the symptom and quotes 3GPP TS 23.501 clauses from the Technical KB. |
| Legal / regulatory analysis | Working | 5/0 | Telecommunications Act, TRAI Act and NDCP-2018 provisions retrieved and quoted; duty passages recorded as obligations. |
| Cybersecurity analysis | Working | 5/0 | T1 reclassifies as a possible security event; TCS Rules Rule 7 and CERT-In Direction (ii) quoted. |
| Privacy / data protection analysis | Working | 5/0 | Suspected (not confirmed) exposure kept distinct; DPDP Act and DPDP Rules Rules 6–7 quoted. |
| Critical infrastructure analysis | Partially working | 5/0 | Critical-service relevance assessed from the Telecommunications Act and the Critical Telecommunication Infrastructure Rules, 2024; the IT (NCIIPC) Rules, 2013 could not be obtained, so NCIIPC provisions cannot be quoted or verified. |
| International standards (reference only) | Working | 5/0 | 3GPP, ETSI, NIST and ITU passages quoted with the reference-only label; never treated as Indian law. |
| Policy-gap identification | Partially working | 7/0 | Three of the six DOCX categories are examined (overlapping requirements, institutional clarity, emerging technology); explicit/partial coverage are left to expert review, unclear coverage is not produced; international comparators are two EU (ENISA) documents, with no neighbouring-country instrument. |
| Verification | Partially working | 24/0 | All four outcomes are produced by the real Verifier. In-force status is now established for the Telecommunications Act sections named in two commencement notifications and for four Rules, but no source's amendment history is shown to be complete, so nothing on the live corpus is VERIFIED; no real provisions conflict. VERIFIED and CONFLICT are shown with labelled fixtures. |
| Cross-domain reasoning | Working | 20/0 | Links established from evidence on the live run (shared provision, instrument basis, parallel reporting), including across chunks. |
| Uncertainty handling | Working | 5/0 | Insufficient evidence stated explicitly; open questions and missing facts listed; human-review notice always present. |
| Progressive reassessment | Working | 6/0 | Each chunk re-issues the whole assessment: facts accumulate, earlier conclusions carried forward and tagged, changes computed by comparison. |
| Role separation | Working | 7/0 | Each agent searches only its own KB and fills only its mandate's fields; results never come from another agent's KB. |
| Auditability | Working | 38/0 | Append-only, hash-chained audit trail with the §7.6 fields; replay with integrity check, decision-path explanation and re-execution. |

## Other capabilities

| Capability | Status | Tests (pass/fail) | Why |
|---|---|---|---|
| Full 4-stage demo (live KBs) | Working | 11/0 | All four stages run end to end; agent sets match the DOCX table. |
| Demonstration UI | Working | 3/0 | Live 4-stage run, replay and conflict display driven by tests through Streamlit's AppTest; every required section checked. |
| Knowledge foundation / RAG | Partially working | 122/0 | 23 sources ingested, each with an official URL whose file hash matches; every artefact checked against the stores. Not obtained: NCIIPC Rules, IndiaAI Mission documents, neighbouring-country instruments, and sources for the economic and multilateral categories. |
| Failure handling | Working | 9/0 | No evidence, wrong citation, missing section, conflict, incomplete information, unexpected chunk, agent failure and empty retrieval all run safely and are stated in the output. |
| Core freeze | Working | 1/0 | Frozen core files fingerprinted in CORE_FREEZE.json; any change fails the test. |
| Team integration (Members 1–3) | Working | 51/0 | One pipeline from scenario to audit; checklist tests pass. |
| In-force / amendment checking | Partially working | 4/0 | In-force status established from obtained documents (S.O. 2408(E) and S.O. 2623(E) for the Telecommunications Act; the commencement clauses of the TCS, CTI, TCS Amendment and Right of Way Rules) and amendment notes from the TCS Amendment Rules 2025, each traced by the evidence audit. Amendment histories are not shown to be complete, so nothing real is VERIFIED. |
| Generative synthesis (DOCX §5.2 generative-AI perspective) | Not yet implemented | — | The policy adviser uses no generative model: agents quote passages and the Coordinator organises verified claims. Only the separate incident-response lab (ir/llm.py) can use one. |
| Parallel agent execution | Not yet implemented | — | Agents run sequentially; the asynchronous runner in the Orchestrator is a stub. |
| ITU AI for Good Sandbox stage | Not yet implemented | — | Access to the ITU AI for Good Sandbox was not available; builds and runs are local. The Y.3172 ML sandbox of the network ML pipeline is local (sim/datagen.py, src/y3172/mlfo.py). |

## Final core checklist

Ticked only when the item's tests ran in this test run and all passed.

- [x] 7 agents work (39 tests)
- [x] Orchestrator works (3 tests)
- [x] RAG integration works (17 tests)
- [x] Verifier works (26 tests)
- [x] Coordinator works (5 tests)
- [x] 4-stage scenario works (12 tests)
- [x] Cross-domain verification works (4 tests)
- [x] Conflict handling works (10 tests)
- [x] Uncertainty handling works (8 tests)
- [x] Audit trail works (3 tests)
- [x] Replay works (16 tests)
- [x] No fabricated evidence (14 tests)
- [x] No broken integration (14 tests)

## Negative tests

| Case | Passed | Failed |
|---|---|---|
| A. Unsupported citation → UNSUPPORTED | 5 | 0 |
| B. Missing/incomplete source information → INCOMPLETE | 5 | 0 |
| C. Conflicting findings → CONFLICT | 6 | 0 |
| D. Valid evidence-backed claim → VERIFIED | 7 | 0 |

VERIFIED and CONFLICT are reached through the real Verifier with labelled fixture passages; on the live corpus neither occurs, for the reasons given above.
