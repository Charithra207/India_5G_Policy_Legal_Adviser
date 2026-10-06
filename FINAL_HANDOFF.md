# Final handoff — knowledge base and evidence

For the team preparing and giving the demonstration. Every statement in the
demo should be traceable to a passage.

The evidence audit (`python -m src.rag.evidence_audit`) traces every cited
passage in the demo run
(`outputs/audit/day2_scenario2_full_T0_T3.jsonl`) along source → authority
→ document → section → passage → retrieval → agent conclusion. It checked
60 claims, 53 cited passages and 3 potential gaps, and found **0 problems**.

The audit is tested against planted fabrications, and catches each of these:

- an altered quote;
- a missing "not Indian law" label;
- a standard called Indian law;
- an "Indian law has no provision" gap;
- an uncited legal requirement;
- a passage from another agent's KB;
- a false VERIFIED.

## Where things are

| What | File |
|---|---|
| Final source manifest (DOCX §7.2: authority, jurisdiction, type, date, effective/amendment status, sections, URL, licence, SHA-256, chunks, vector index, models) | `knowledge_base/source_manifest.json` |
| Evidence audit, sources used in the demo, one traced example per agent | `knowledge_base/evidence_audit.md` / `.json` |
| Retrieval quality (12 labelled queries, all 7 agents) | `knowledge_base/retrieval_quality.md` |
| Evaluation status (Working / Partially / Not implemented) and core checklist | `knowledge_base/evaluation_report.md` |
| Technical explanation for the presentation | `TECHNICAL_EXPLANATION.md` |

## Final KB status

| KB | Passages | Documents |
|---|---|---|
| Technical | 3,739 | 3GPP TS 23.501 V19.9.0, TS 33.501 V19.7.0 |
| Policy & Legal | 274 | Telecommunications Act 2023, TRAI Act 1997 (TDSAT compilation), NDCP-2018, NCSP-2013 |
| Cybersecurity | 1,675 | Telecom Cyber Security Rules 2024, CERT-In Directions 2022, NCSP-2013, NDCP-2018; references: 3GPP TS 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 |
| Privacy | 159 | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infrastructure | 105 | Telecommunications Act 2023 only — **IT (NCIIPC) Rules 2013 not ingested** |
| Standards | 4,259 | ITU-T Y.3172, 3GPP TS 23.501 / 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 |
| Policy Gap | 459 | TRAI AI & Big Data Recommendations 2023, NCSP-2013, NDCP-2018 — **no international policy examples** |
| Canonical (verification) | 5,112 | All 15 ingested documents |

**Every passage carries `effective = null` and `amendment_checked = false`.**
In-force status and amendments were not checked for any source.

## Sources used in the presentation (cited in the demo run)

| Indian sources | International sources (reference only) |
|---|---|
| Telecommunications Act 2023 | ITU-T Y.3172 |
| TRAI Act 1997 | 3GPP TS 23.501 |
| NDCP-2018 | 3GPP TS 33.501 |
| Telecom Cyber Security Rules 2024 | NIST SP 800-61r3 |
| CERT-In Directions 2022 | |
| NCSP-2013 | |
| DPDP Act 2023 | |
| DPDP Rules 2025 | |
| TRAI AI & Big Data Recommendations 2023 (recommendations, not law) | |

**Ingested but not cited in the demo:** ETSI GR NFV-SEC 003 and NIST CSF 2.0.

**Not ingested:**
- IT (NCIIPC) Rules 2013 — official sites unreachable.
- International policy examples — the DOCX names none.

Every source URL is in `knowledge_base/source_manifest.json`, and each
downloaded file's SHA-256 matches the ingestion record.

## Evidence examples, one per agent

Full text is in `knowledge_base/evidence_audit.md`. All are **INCOMPLETE**:
the text supports the claim, but in-force status and amendments were not
checked.

| Agent | Stage | Source and section | What it shows |
|---|---|---|---|
| Technical | T0 | 3GPP TS 23.501, Clause 5.37.7.1 | Packet-delay monitoring (reference only) |
| Policy & Legal | T2 | Telecommunications Act 2023, Section 22 | Central Government rules for telecom cyber security |
| Cybersecurity | T1 | Telecom Cyber Security Rules 2024, Rule 7 | Report a security incident to the Central Government within six hours |
| Privacy | T2 | DPDP Rules 2025, Rule 7 | Intimation of a personal data breach to the Data Principal and the Board, without delay |
| Critical Infrastructure | T2 | Telecommunications Act 2023, Section 22 | Same provision, read for critical telecommunication infrastructure |
| Standards | T1 | 3GPP TS 33.501, Clause B.1 | EAP authentication in private networks (reference only) |
| Policy Gap | T3 | Potential gap from examining all 485 Indian legal/policy passages | Network slicing is not named in them; it is named only in TRAI recommendations (Para 3.30), which are not law |

## Known limitations

1. **Nothing is VERIFIED on the real sources.** In-force status and
   amendment history were not checked, so quoted provisions are INCOMPLETE.
   The live run gives 50 INCOMPLETE and 10 UNSUPPORTED claims.
2. **Missing sources:**
   - the NCIIPC Rules, so NCIIPC's role can't be quoted;
   - international policy examples;
   - IndiaAI and national AI strategy documents;
   - sources for six DOCX §7.3 categories (economic, labour, IP,
     multilateral, energy, comparators).
3. **The Policy Gap agent examines only three of the six categories:**
   overlap, institutional clarity and emerging technology. Explicit and
   partial coverage are left to experts, and unclear coverage is not
   produced.
4. **No real conflict exists in the corpus.** The conflict demonstration
   uses labelled synthetic FIXTURE passages.
5. **Other limits:**
   - support is judged by a deterministic term-coverage check, not a
     language model;
   - there is no generative model;
   - agents run sequentially;
   - the ITU Sandbox step was not executed.
6. **The TRAI Act text is from TDSAT's compilation**, whose consolidation
   date is not stated. NDCP-2018 and the Telecom Cyber Security Rules are
   from government mirror sites; each is noted in the manifest.
7. **3GPP tables and figures were not ingested.** For 3GPP TS 23.501, no
   copyright statement was captured in the ingested text.

## Claims that should NOT be made in the presentation

| Do not say | Why | Say instead |
|---|---|---|
| "The system verifies Indian law" / "claims are verified" | Nothing on the real corpus is VERIFIED | "Each claim is checked against the authoritative text; with in-force status unchecked, the best outcome is INCOMPLETE" |
| "Indian law has no provision for network slicing" | Only the 15 ingested documents were examined | "None of the 485 passages of the Indian legal and policy instruments we ingested names network slicing — a potential gap for expert review" |
| "Indian policy is inadequate / there is a gap in the law" | The DOCX forbids conclusive gap claims | "potential gap", "regulatory ambiguity", "for expert review" |
| "3GPP / NIST / ETSI / ITU require the operator to …" | Standards are not Indian law | "As a reference point, 3GPP TS 33.501 describes …" |
| "The operator must report to NCIIPC" | NCIIPC Rules not ingested; no passage supports it | "NCIIPC's role could not be assessed; its Rules are not in the corpus" |
| "The provision is in force" | Not checked | "In-force status not verified" |
| "Patient data was exposed" | The scenario says it *may* carry identifiable data | "Possible personal-data involvement (suspected, not confirmed)" |
| "The system detected a conflict between Indian laws" | The conflict demo uses synthetic fixtures | "With labelled test passages, the system shows how a conflict is kept unresolved for human review" |
| "Uses generative AI / an LLM to analyse" | No generative model is used | "Agents quote retrieved passages; the Coordinator organises verified claims" |
| "Validated in the ITU AI for Good Sandbox" / "Y.3172 compliant" | Not executed; compliance not assessed | "Mapped to the Y.3172 pipeline stages; Sandbox stage not executed" |
| "Accuracy of X %" / readiness score | No such measurement exists | Quote the labelled retrieval results: right section first in 8/12 queries, in the top 5 in 12/12 |
| "Legal advice" | Decision support only | "Decision support; legal interpretation requires qualified human judgment" |

## Regenerating after any change

Run these in order:

```powershell
python -m src.scenario.run --run-id day2_scenario2_full_T0_T3   # delete the old file first
python -m src.rag.foundation
python -m src.rag.evidence_audit          # must report 0 problems
python -m src.audit.evaluation_report     # all tests must pass
```
