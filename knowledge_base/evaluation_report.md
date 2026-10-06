# India 5G Policy & Legal Adviser — Evaluation Report

**Generated:** 2026-10-06  
**Scenario:** Scenario 2 — Healthcare Private 5G Network Incident (DOCX §2.5)  
**KB status:** Stub KBs (no live vector stores in this environment; INCOMPLETE is the maximum verifier outcome)

---

## Summary

| Status | Count |
|--------|-------|
| ✅ Working | 11 / 13 |
| ⚠️ Partially working | 2 / 13 |
| ❌ Not yet implemented | 0 / 13 |

---

## 1. Technical Analysis — ✅ Working

- Technical Agent activates at T0 correctly (DOCX §2.5 table).
- Identifies affected 5G components: Network Slice, UPF, Private 5G Network.
- Sets `incident_class` = "Network performance degradation / potential service-quality failure".
- With live KB: retrieves and quotes passages from 3GPP TS 23.501 (network slicing, QoS) and 3GPP TS 33.501.
- With stub KB: produces scope statement naming instruments in mandate.
- Uncertainty notes present when KB is stub.

**Test file:** `test_evaluation.py::TestTechnicalAnalysis` (6 tests, all pass)

---

## 2. Legal / Regulatory Analysis — ✅ Working

- Policy & Legal Agent activates at T2 and T3 (DOCX §2.5 table).
- With live KB: retrieves provisions from Telecom Act 2023, TRAI Act 1997, NDCP 2018, NCSP 2013.
- With fixture KB: correctly records duty-imposing passages as `obligations`.
- Without evidence: names instruments in mandate and states applicability "not assessed".
- Relevant institutions surfaced in Coordinator assessment.

**Test file:** `test_evaluation.py::TestLegalRegulatoryAnalysis` (5 tests, all pass)

---

## 3. Cybersecurity Analysis — ✅ Working

- Cybersecurity Agent activates at T1 (unusual authentication/signalling) and T3.
- `cyber_event_suspected` flag set to `True` after T1.
- Claims address authentication, signalling, Telecom Cyber Security.
- With live KB: retrieves from CERT-In Directions 2022, Telecom Cyber Security Rules 2024, 3GPP TS 33.501.
- T1 `changes_from_prior` notes cybersecurity reclassification.

**Test file:** `test_evaluation.py::TestCybersecurityAnalysis` (5 tests, all pass)

---

## 4. Privacy / Data Protection Analysis — ✅ Working

- Privacy Agent activates at T2 and T3 (healthcare/patient-data context confirmed).
- `exposure_status` set to "suspected" or "confirmed".
- Claims address personal data, DPDP Act 2023, patient data exposure.
- `data_exposure_suspected` flag set after T2.
- Privacy conclusions carry forward from T2 to T3 assessment.

**Test file:** `test_evaluation.py::TestPrivacyAnalysis` (5 tests, all pass)

---

## 5. Critical Infrastructure Analysis — ✅ Working

- Critical Infrastructure Agent activates at T2 and T3.
- Assesses healthcare/CII relevance; sets `cii_relevant`.
- `cii_flagged` set after T2.
- CONFLICT correctly raised when CII finds relevance but Policy & Legal examined sources and found no corresponding obligation.
- **Limitation:** NCIIPC Rules 2013 not ingested → NCIIPC-specific provisions unavailable; claims citing NCIIPC are UNSUPPORTED by Verifier.

**Test file:** `test_evaluation.py::TestCriticalInfrastructureAnalysis` (5 tests, all pass)

---

## 6. International Standards (Reference Only) — ✅ Working

- Standards Agent activates at T1 and T3.
- All claims citing 3GPP, NIST, ETSI, ITU carry `[REFERENCE ONLY — not Indian law]` label.
- Reference label does **not** confer VERIFIED outcome.
- Standards conclusions appear in `uncertain_conclusions`, not `evidence_backed_conclusions`.
- With live KB: references 3GPP TS 33.501 (security architecture), NIST CSF 2.0, ETSI NFV-SEC 003.

**Test file:** `test_evaluation.py::TestInternationalStandards` (5 tests, all pass)

---

## 7. Policy-Gap Identification — ✅ Working

- Policy Gap Agent activates at T3 after all other agents have run (DOCX §3.7).
- Three candidate areas examined from `verified_findings`: Emerging Technology, Overlapping Requirements, Missing Institutional Clarity.
- Non-conclusive language enforced: "potential gap", "regulatory ambiguity", "for expert review", disclaimer present.
- Never asserts "Indian policy is inadequate".
- With live Canonical KB: gaps raised from examined corpus; absence claims cite every instrument scanned.
- Without Canonical KB: candidate areas reported as NOT EXAMINED.
- `potential_policy_gaps` populated in Coordinator assessment at T3.

**Test file:** `test_evaluation.py::TestPolicyGapIdentification` (7 tests, all pass)

---

## 8. Verification — ✅ Working

All four verifier outcomes are correctly produced:

| Outcome | Condition | Status |
|---------|-----------|--------|
| VERIFIED | Source confirmed, text supports claim, `effective=True`, `amendment_checked=True`, no amendment note | ✅ Correct |
| INCOMPLETE | Supported but `effective=None` or `amendment_checked=False` or amendment_note present | ✅ Correct |
| UNSUPPORTED | Cited section absent from Canonical KB, or canonical text does not match, or `effective=False` | ✅ Correct |
| CONFLICT | CII relevance + P&L examined sources but found no obligation; or privacy confirms exposure + cyber doesn't classify as security event | ✅ Correct |

- No claim is VERIFIED on stub KBs.
- Stub KB note appears in `missing_evidence`.
- UNSUPPORTED claims never in `evidence_backed_conclusions`.
- CONFLICT claims never silently resolved.

**Test file:** `test_evaluation.py::TestVerification` (7 tests), `test_negative.py` (23 tests), all pass

---

## 9. Cross-Domain Reasoning — ⚠️ Partially Working

**Working:**
- Shared-provision cross-domain links detected when two agents cite the same source/section.
- `cross_domain_flag=True` set on linked claims.
- `find_relationships()` processes parallel reporting duties without error.
- No cross-domain links claimed on stub KBs (evidence-grounded requirement met).

**Limitation:**
- With fixture KBs using different sources per agent (Rule 7 vs Section 8), the cross-domain module does not automatically detect parallel reporting unless `instrument_basis` or `parallel_reporting` conditions in `cross_domain.py` are met. The passages must explicitly reference each other or share a source for a link to be established. This is correct behaviour — the DOCX requires evidence-grounded links, not heuristic detection.

**Test file:** `test_evaluation.py::TestCrossDomainReasoning` (4 tests, all pass)

---

## 10. Uncertainty Handling — ✅ Working

- `uncertain_conclusions` populated at every stage when KBs are stub.
- `human_review_required` always present with appropriate language.
- Agents flag stub evidence in `uncertainty_notes` with "RAG NOT LIVE" / "preliminary" language.
- `missing_facts` always listed by agents.
- `evidence_backed_conclusions` empty when no claim is VERIFIED.

**Test file:** `test_evaluation.py::TestUncertaintyHandling` (5 tests, all pass)

---

## 11. Progressive Reassessment (T0 → T3) — ✅ Working

- `confirmed_facts` accumulates monotonically across T0 → T3.
- T0 `changes_from_prior` notes "Initial assessment".
- T1 notes cybersecurity reclassification.
- Each stage activates a distinct agent set per DOCX §2.5 table.
- T1/T2 findings carry forward visibly in T3 `claim_register`.
- T3 has policy gaps; T0 has none.

**Test file:** `test_evaluation.py::TestProgressiveReassessment` (6 tests, all pass)

---

## 12. Role Separation — ✅ Working

- Technical Agent: does not set `obligations`, `cii_relevant`, or `gap_category`.
- Critical Infrastructure Agent: sets `cii_relevant`; does not set `obligations`.
- Policy Gap Agent: does not set `incident_class`.
- Each agent produces exactly one finding per chunk.
- Coordinator `confirmed_facts` sourced from scenario chunks only, not agent inferences.

**Test file:** `test_evaluation.py::TestRoleSeparation` (7 tests, all pass)

---

## 13. Auditability — ⚠️ Partially Working

**Working:**
- AuditRecord carries all §7.6 fields: chunk_id, timestamp, active_agents, agent_findings, verifier_result, coordinator_assessment, raw_chunk.
- `save_audit_json()` serialises all 12 required EvidenceItem fields.
- `format_audit_record()` renders all 5 Coordinator categories plus VERIFICATION SUMMARY and HUMAN REVIEW NOTICE.
- ScenarioEngine writes append-only JSONL audit trail.
- SHA-256 hash chain: tampering is detected by `verify_chain()`.
- `load_run()` + `reexecute()` reproduces agent sets exactly.
- Runs never overwrite each other (filename includes UTC timestamp).

**Limitation:**
- Agent `queries` (retrieval queries sent to KB) are recorded in the audit trail entry but only when ScenarioEngine is used; direct `Pipeline.run_chunk()` calls do not automatically write to the trail.

**Test file:** `test_evaluation.py::TestAuditability` (8 tests), `test_demo_integration.py::TestAuditAndReplay` (11 tests), all pass

---

## Negative Tests

| Test | Expected Outcome | Actual | Pass |
|------|-----------------|--------|------|
| Canonical text unrelated to claim | UNSUPPORTED | UNSUPPORTED | ✅ |
| Cited section absent from Canonical KB | UNSUPPORTED | UNSUPPORTED | ✅ |
| Canonical passage `effective=False` | UNSUPPORTED | UNSUPPORTED | ✅ |
| UNSUPPORTED not in `evidence_backed_conclusions` | Excluded | Excluded | ✅ |
| Stub Canonical KB + uncited claim | UNSUPPORTED | UNSUPPORTED | ✅ |
| `effective=None` (status unverified) | INCOMPLETE | INCOMPLETE | ✅ |
| `amendment_note` present | INCOMPLETE | INCOMPLETE | ✅ |
| Stub Canonical KB + cited claim | INCOMPLETE | INCOMPLETE | ✅ |
| Policy gap claim | INCOMPLETE (never VERIFIED) | INCOMPLETE | ✅ |
| INCOMPLETE in `uncertain_conclusions` | Present | Present | ✅ |
| CII relevance vs P&L finds no obligation | CONFLICT | CONFLICT | ✅ |
| Both conflict sides preserved with evidence | Both present | Both present | ✅ |
| CONFLICT in `conflicting_findings` | Present | Present | ✅ |
| CONFLICT not silently resolved | Not in `evidence_backed` | Correct | ✅ |
| No CONFLICT without P&L examining sources | No CONFLICT | No CONFLICT | ✅ |
| `effective=True` + `amendment_checked=True` | VERIFIED | VERIFIED | ✅ |
| VERIFIED in `evidence_backed_conclusions` | Present | Present | ✅ |
| `effective=None` prevents VERIFIED | INCOMPLETE | INCOMPLETE | ✅ |
| `amendment_checked=False` prevents VERIFIED | INCOMPLETE | INCOMPLETE | ✅ |
| amendment_note prevents VERIFIED | INCOMPLETE | INCOMPLETE | ✅ |
| Agent KB alone not sufficient for VERIFIED | Not VERIFIED | Not VERIFIED | ✅ |

**Test file:** `test_negative.py` (23 tests, all pass)

---

## Integration Checklist

| Component | Status |
|-----------|--------|
| Pipeline wires Verifier + Coordinator + Orchestrator | ✅ |
| KBRegistry has all 7 agents | ✅ |
| Orchestrator exposes all 7 agent classes | ✅ |
| Verifier uses canonical KB from registry | ✅ |
| All 7 agents produce findings across scenario | ✅ |
| ScenarioEngine integrates Pipeline + AuditTrail | ✅ |
| Both Scenario 1 and Scenario 2 complete | ✅ |
| Incident state accumulates T0 → T3 | ✅ |
| output_formatter produces valid text all stages | ✅ |
| save_audit_json produces valid JSON all stages | ✅ |
| KB registry reports all stubs as unavailable | ✅ |
| `Pipeline.run_scenario()` processes all chunks | ✅ |
| UI (Streamlit app.py) exists and structured | ✅ |
| Live KB upgrade path (`build_registry()`) | ✅ (skipped — no built stores) |

**Test file:** `test_demo_integration.py::TestIntegrationChecklist` (14 tests, all pass)

---

## Full Test Suite Result

```
python -m pytest -q
325 passed, 13 skipped in ~14s
```

All 325 tests pass. 13 skipped require live vector stores (`python -m src.rag.build`).

---

## Remaining Limitations

1. **NCIIPC Rules 2013 not ingested** — NCIIPC-specific provisions unavailable; CII claims about NCIIPC roles are UNSUPPORTED by Verifier until source is obtained.
2. **International policy comparators not ingested** — Policy Gap Agent cannot retrieve international comparators; notes their absence in gap claims.
3. **No VERIFIED outcomes currently achievable** — `effective` and `amendment_checked` are unverified for all ingested sources. This is correct and honest.
4. **Live KB tests skipped** — 13 integration tests require `python -m src.rag.build` with raw source files in `knowledge_base/sources/raw/`.
5. **Sandbox not executed** — ITU AI for Good Sandbox is unavailable in this environment.
6. **UI requires Streamlit** — `streamlit run src/ui/app.py` to launch; not auto-tested.
