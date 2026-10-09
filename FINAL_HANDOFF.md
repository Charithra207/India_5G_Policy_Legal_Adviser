# Final handoff — knowledge base and evidence

For the team preparing and giving the demonstration. Every statement in the
demo should be traceable to a passage.

The evidence audit (`python -m src.rag.evidence_audit`) traces every cited
passage in the demo run
(`outputs/audit/day2_scenario2_full_T0_T3.jsonl`) along source → authority
→ document → section → passage → retrieval → agent conclusion. It checked
60 claims, 53 cited passages and 3 potential gaps, and traced 13 in-force
statuses to their notifications and 2 amendment notes to the amendment rules.
It found **0 problems**.

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
| Policy & Legal | 603 | Telecommunications Act 2023 + commencement notifications S.O. 2408(E) and S.O. 2623(E), TRAI Act 1997 (TDSAT compilation), NDCP-2018, NCSP-2013, CTI Rules 2024, NITI Aayog National Strategy for AI |
| Cybersecurity | 1,680 | Telecom Cyber Security Rules 2024 (official DoT copy) + Amendment Rules 2025, CERT-In Directions 2022, NCSP-2013, NDCP-2018; references: 3GPP TS 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 |
| Privacy | 159 | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infrastructure | 126 | Telecommunications Act 2023, **Critical Telecommunication Infrastructure Rules 2024** — IT (NCIIPC) Rules 2013 still not ingested |
| Standards | 4,259 | ITU-T Y.3172, 3GPP TS 23.501 / 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 |
| Policy Gap | 1,029 | TRAI AI & Big Data Recommendations 2023, NCSP-2013, NDCP-2018, NITI Aayog National Strategy for AI, Right of Way Rules 2024; **international examples: ENISA 5G Security Controls Matrix, ENISA 5G Cybersecurity Standards (EU)** |
| Canonical (verification) | 5,710 | All 23 ingested documents |

**In-force status** is set only where an obtained document establishes it,
and the build checks the document's own wording first:

| Instrument | In force | Established by |
|---|---|---|
| Telecommunications Act 2023, ss. 1, 2, 10–30, 42–44, 46, 47, 50–58, 61, 62 | from 26 June 2024 | S.O. 2408(E) |
| Telecommunications Act 2023, ss. 6–8, 48 | from 5 July 2024 | S.O. 2623(E) (59(b) not marked: only one clause) |
| Telecom Cyber Security Rules 2024 | from 21 Nov 2024 | rule 1(2) |
| CTI Rules 2024 | from 22 Nov 2024 | rule 1(2) |
| TCS Amendment Rules 2025 | from 22 Oct 2025 | rule 1(2) |
| Right of Way Rules 2024 | from 1 Jan 2025 | rule 1(2) |

**Amendments:** TCS Rules rules 2, 3, 4, 5, 8 and 10 carry the note
"amended by G.S.R. 771(E)". Rule 7, the reporting rule, is not amended
by it.

**Every other passage is `effective = null` (not verified).** For example,
Telecommunications Act s. 3 is named by neither notification obtained.

**`amendment_checked = false` everywhere.** One known amendment does not
prove there is no other, so nothing on real sources can be VERIFIED.

## Sources used in the presentation (cited in the demo run)

| Indian sources | International sources (reference only) |
|---|---|
| Telecommunications Act 2023 | 3GPP TS 23.501 |
| TRAI Act 1997 | 3GPP TS 33.501 |
| NDCP-2018 | NIST SP 800-61r3 |
| Telecom Cyber Security Rules 2024 | ENISA 5G Cybersecurity Standards (EU policy example) |
| CTI Rules 2024 | |
| CERT-In Directions 2022 | |
| NCSP-2013 | |
| DPDP Act 2023 | |
| DPDP Rules 2025 | |
| NITI Aayog National Strategy for AI (strategy, not law) | |
| TRAI AI & Big Data Recommendations 2023 (recommendations, not law) | |

**Ingested and used for status or coverage, not quoted:**
- the two Telecommunications Act commencement notifications;
- the TCS Amendment Rules 2025;
- the Right of Way Rules 2024;
- the ENISA 5G Security Controls Matrix;
- ITU-T Y.3172;
- ETSI GR NFV-SEC 003;
- NIST CSF 2.0.

**Not ingested:**
- IT (NCIIPC) Rules 2013 — not in the team folder, and the official sites
  were unreachable.
- Neighbouring-country instruments.
- The UNESCO Recommendation on the Ethics of AI — no official copy
  matching the file could be found online.

**Added from the team folder:** 8 documents. Each was used only after an
official URL served a byte-identical file. The Right of Way Rules are the
exception: the team's copy differed, so DoT's own download was used. The
other ~270 files in the folder are outside the DOCX scope (consultation
papers, other 3GPP specifications, a job notice) and were not ingested.

## Evidence examples, one per agent

Full text is in `knowledge_base/evidence_audit.md`. All are **INCOMPLETE**. The text supports the
claim, but the amendment history is not shown to be complete. Where an
obtained notification establishes it, the rationale names the in-force date,
for example "in force from 26 June 2024 (S.O. 2408(E))".

| Agent | Stage | Source and section | What it shows |
|---|---|---|---|
| Technical | T0 | 3GPP TS 23.501, Clause 5.37.7.1 | Packet-delay monitoring (reference only) |
| Policy & Legal | T2 | Telecommunications Act 2023, Section 22 | Central Government rules for telecom cyber security |
| Cybersecurity | T1 | Telecom Cyber Security Rules 2024, Rule 7 | Report a security incident to the Central Government within six hours |
| Privacy | T2 | DPDP Rules 2025, Rule 7 | Intimation of a personal data breach to the Data Principal and the Board, without delay |
| Critical Infrastructure | T2 | CTI Rules 2024, Rule 3 | Critical telecommunication infrastructure provision (in force from 22 Nov 2024) |
| Standards | T1 | 3GPP TS 33.501, Clause B.1 | EAP authentication in private networks (reference only) |
| Policy Gap | T3 | Potential gap from examining all 886 Indian legal/policy passages | Network slicing is not named in them; it is named only in TRAI recommendations (Para 3.30), which are not law |

## Known limitations

1. **Nothing is VERIFIED on the real sources.** In-force status is
   established for the Telecommunications Act sections named in the two
   notifications and for four Rules, but no amendment history is shown to be
   complete. The live run gives 50 INCOMPLETE and 10 UNSUPPORTED claims.
2. **Missing sources:**
   - the NCIIPC Rules, so NCIIPC's role can't be quoted;
   - IndiaAI Mission documents;
   - neighbouring-country instruments;
   - sources for the economic and multilateral categories.

   Labour, IP, infrastructure and comparators are now **partial**: the NITI
   Aayog strategy, the Right of Way Rules and the ENISA documents cover part
   of each.
3. **The Policy Gap agent examines only three of the six categories:**
   overlap, institutional clarity and emerging technology. Explicit and
   partial coverage are left to experts, and unclear coverage is not
   produced.
4. **No real conflict exists in the corpus.** The conflict demonstration
   uses labelled synthetic FIXTURE passages.
5. **Other limits:**
   - support is judged by a deterministic term-coverage check, not a
     language model;
   - the adviser uses no generative model (only the separate incident-response
     lab can optionally use one);
   - agents run sequentially;
   - the ITU AI for Good Sandbox was not available, so everything runs locally;
   - the Y.3172 mapping is mostly by analogy; SINK, MLFO, ML Intent and the ML
     sandbox are not implemented.
6. **The TRAI Act text is from TDSAT's compilation**, whose consolidation
   date is not stated. NDCP-2018 and the Telecom Cyber Security Rules are
   from government mirror sites; each is noted in the manifest.
7. **3GPP tables and figures were not ingested.** For 3GPP TS 23.501, no
   copyright statement was captured in the ingested text.

## Claims that should NOT be made in the presentation

| Do not say | Why | Say instead |
|---|---|---|
| "The system verifies Indian law" / "claims are verified" | Nothing on the real corpus is VERIFIED | "Each claim is checked against the authoritative text; with in-force status unchecked, the best outcome is INCOMPLETE" |
| "Indian law has no provision for network slicing" | Only the ingested documents were examined | "None of the 886 passages of the Indian legal and policy instruments we ingested names network slicing — a potential gap for expert review" |
| "Indian policy is inadequate / there is a gap in the law" | The DOCX forbids conclusive gap claims | "potential gap", "regulatory ambiguity", "for expert review" |
| "3GPP / NIST / ETSI / ITU require the operator to …" | Standards are not Indian law | "As a reference point, 3GPP TS 33.501 describes …" |
| "The operator must report to NCIIPC" | NCIIPC Rules not ingested; no passage supports it | "NCIIPC's role could not be assessed; its Rules are not in the corpus" |
| "The provision is in force" (unqualified) | Only some provisions have an established status | Name the source shown on screen: "in force from 26 June 2024 by S.O. 2408(E)"; otherwise "in-force status not verified" |
| "Telecommunications Act section 3 is in force" | Neither notification obtained names it | "Not established from the notifications we obtained" |
| "The quoted Rule 5 / Rule 8 text is current" | Amended by G.S.R. 771(E); we quote the original | "As originally published; amended in 2025" |
| "Patient data was exposed" | The scenario says it *may* carry identifiable data | "Possible personal-data involvement (suspected, not confirmed)" |
| "The system detected a conflict between Indian laws" | The conflict demo uses synthetic fixtures | "With labelled test passages, the system shows how a conflict is kept unresolved for human review" |
| "Uses generative AI / an LLM to analyse" | The adviser uses no generative model; only the separate incident-response lab can optionally use one | "Adviser agents quote retrieved passages; the Coordinator organises verified claims" |
| "Validated in the ITU AI for Good Sandbox" / "Y.3172 compliant" / "implements the Y.3172 pipeline" | Sandbox access was not available; compliance not assessed; most stages correspond only by analogy and SINK, MLFO, ML Intent and the ML sandbox do not exist | "Our document pipeline is mapped to the Y.3172 node vocabulary, mostly by analogy; the gaps are listed in the traceability file" |
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
