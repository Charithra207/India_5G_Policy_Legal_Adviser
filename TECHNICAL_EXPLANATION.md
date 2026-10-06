# India 5G Policy & Legal Adviser — technical explanation

Core release candidate. Figures come from the recorded live run
`outputs/audit/day2_scenario2_full_T0_T3.jsonl` and from
`knowledge_base/evaluation_report.md`, which is generated from a real test run.

## Problem

A 5G incident changes as facts arrive. A latency problem can become a
security event, then a critical-service and personal-data issue, then a
question of who must be told what. Each step brings in different Indian
law, institutions and standards. A single answer given at the start cannot
follow that, and ordinary document search finds provisions but doesn't
connect them across domains or check them. The adviser follows one
incident, chunk by chunk, and keeps every conclusion tied to the passage
it rests on. It is decision support only; legal judgment stays with
qualified people.

## Architecture

**Flow:** scenario chunk → Orchestrator → specialist agents, each searching
its own knowledge base → Verifier, which checks every claim against a
separate Canonical KB and links findings across domains → Coordinator →
assessment → append-only audit trail → replay.

- **Language and models:** Python. Retrieval uses the BAAI/bge-small-en-v1.5
  embedding model on CPU. **No generative model is used:** agents quote the
  passages they retrieve, and the Coordinator organises claims the Verifier
  has checked.
- **Execution:** sequential.
- **UI:** Streamlit.

## The 7 specialist agents

| Agent | Knowledge base (passages) | What it produces |
|---|---|---|
| Technical | 3GPP TS 23.501 and 33.501 (3,739) | Incident class, affected components, technical references |
| Policy & Legal | Telecommunications Act, TRAI Act, NDCP-2018, NCSP-2013 (274) | Applicable provisions, obligations, institutions |
| Cybersecurity | Telecom Cyber Security Rules, CERT-In Directions, plus security references (1,675) | Security classification, reporting duties |
| Privacy | DPDP Act 2023, DPDP Rules 2025 (159) | Exposure status (suspected and confirmed kept apart), data-protection duties |
| Critical Infrastructure | Telecommunications Act (105); **IT (NCIIPC) Rules 2013 could not be obtained** | Critical-service relevance; designation stated as unconfirmed |
| Standards | ITU-T Y.3172, 3GPP, ETSI NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 (4,259) | Reference points, always labelled "not Indian law" |
| Policy Gap | TRAI AI & Big Data Recommendations, NCSP, NDCP (459); **no international policy examples ingested** | Potential gaps for expert review |

An agent states what a law or standard says only by quoting a retrieved
passage, with source, section and page. If no passage is found, it says the
matter is not assessed.

## Agent-specific RAG

**Pipeline.** Documents from the official sources go through these steps:

1. Text extraction with page numbers. A file is refused if its own title
   text is missing.
2. Removal of running headers and footers.
3. Section detection from the printed headings or PDF bookmarks.
4. Chunking within one section.
5. Embedding.
6. One vector store per agent, plus the separate Canonical KB (5,112
   passages, 15 documents).

**Retrieval quality** on 12 labelled queries covering all 7 agents:

| Measure | Result |
|---|---|
| Expected section ranked first | 8 / 12 |
| Expected section in the top 5 | 12 / 12 |
| Results from the agent's own KB only | 12 / 12 |
| Required metadata on every result | 12 / 12 |

## Orchestrator

The Orchestrator selects agents from the information released in each chunk
and the accumulated incident state, never from the chunk's position. The
Policy Gap Agent runs last, on the verified findings of the others. In the
live run every stage selects exactly the agents in the DOCX table:

| Stage | Agents |
|---|---|
| T0 | Technical |
| T1 | + Cybersecurity, Standards |
| T2 | Critical Infrastructure, Privacy, Policy & Legal |
| T3 | + Policy Gap |

## Verification

For each claim, the Verifier checks three things against the Canonical KB:

1. The cited source and section exist.
2. The text supports the claim (a deterministic term-coverage judge).
3. The provision is in force and its amendments have been checked.

| Outcome | When |
|---|---|
| VERIFIED | All three checks pass |
| INCOMPLETE | Supported, but in-force status or amendments are unchecked, or an amendment applies |
| UNSUPPORTED | Section not found, text does not support the claim, or no evidence |
| CONFLICT | Another finding or source contradicts the claim |

**On the live corpus nothing is VERIFIED.** Nobody has checked the in-force
status or amendment history of any source, and that is reported, not hidden.
The live run gives 50 INCOMPLETE and 10 UNSUPPORTED. VERIFIED and CONFLICT
are shown with clearly labelled synthetic fixture passages through the same
Verifier.

## Cross-domain verification

Links between domains are established from evidence, never from two agents
simply being active. The live run produced 22 links:

- **Shared provision (8):** for example, Critical Infrastructure and
  Policy & Legal both cite Telecommunications Act s.22.
- **Instrument basis (10):** the Telecom Cyber Security Rules say they are
  made "in exercise of the powers conferred by … section 22 … of the
  Telecommunications Act, 2023".
- **Parallel reporting (4):**

  | Instrument | Reporting duty |
  |---|---|
  | TCS Rules, Rule 7 | Central Government, within six hours |
  | CERT-In Directions | CERT-In, within 6 hours |
  | DPDP Rules, Rule 7 | Data Principal and Data Protection Board, without delay |

Findings from earlier chunks take part, so a T2 privacy finding can be
linked to a T1 cybersecurity finding.

**Conflict rule.** If two cited duties give the same recipient different
time limits, both claims become CONFLICT. Each is shown with its own
evidence, and neither is adopted. No real provisions in this corpus conflict.

## Coordinator

The Coordinator sorts the assessment into the five DOCX Table A1 categories:

| Category | What goes in it |
|---|---|
| Confirmed facts | The released incident facts only |
| Evidence-backed conclusions | VERIFIED claims |
| Uncertain conclusions | INCOMPLETE and UNSUPPORTED claims; the latter marked "insufficient evidence" |
| Conflicting findings | Both sides, with their evidence |
| Potential policy gaps | Gaps raised by the Policy Gap Agent |

Each chunk re-issues the whole assessment:

- Facts accumulate across chunks.
- Conclusions from agents not active in the current chunk are carried
  forward and tagged.
- "What changed" is computed by comparing with the previous chunk.
- Open questions list the missing evidence, including any agent that
  failed to run.

The human-review notice is always present.

## Policy-gap identification

The Policy Gap Agent examines the Canonical KB for three of the six DOCX
categories:

| Category | How it is examined |
|---|---|
| Overlapping requirements | Two instruments' reporting duties, and whether either refers to the other |
| Missing institutional clarity | Exhaustive scan for NCIIPC and CERT-In |
| Emerging technology not explicitly addressed | Exhaustive scan for network slicing |

The other three are handled as follows:

- **Explicit and partial coverage:** recorded as "coverage checks", leaving
  the distinction to experts.
- **Unclear coverage:** not produced.

At T3 it raises three potential gaps. For example, none of the 485 passages
of Indian legal and policy instruments mentions network slicing; it is named
only in TRAI recommendations, which are not law. Gaps are phrased as
potential and for expert review, never as "the law does not exist" or
"policy is inadequate".

## Audit and replay

Every stage is written to an append-only JSONL file with a hash chain, so an
edited, removed or reordered entry is detected. Each entry records:

- the timestamp and chunk;
- each agent's visible input and queries;
- the retrieved passages, with source and section;
- the decision summary and citations;
- the verifier outcome and rationale;
- the cross-domain flags;
- the Coordinator's decision.

Replay, in the UI or on the command line, does four things:

1. Checks the hash chain.
2. Steps through the stages.
3. For each stage, shows what happened, who acted, the evidence, the
   conclusion, the verification and the Coordinator's path.
4. Can re-run the recorded chunk sequence and confirm it reproduces exactly.

## Not implemented / limits

- No in-force or amendment checking, so nothing is VERIFIED on real sources.
- IT (NCIIPC) Rules 2013 not ingested, because the official sites were
  unreachable.
- No IndiaAI or national AI strategy documents, international policy
  examples, or sources for six host-country categories.
- No generative synthesis.
- Agents run sequentially, not in parallel.
- The ITU AI for Good Sandbox stage was not executed.
- No human-evaluation study or energy measurement.

## Core status

**Tests:**
- 373 pass.
- All 13 items in the final core checklist are ticked by passing tests.
- The 8 failure modes (no evidence through empty retrieval, including agent
  failure) fail safely and are stated in the output.

**Freeze:** the core (Orchestrator, agents, Verifier, cross-domain logic,
Coordinator, data models, scenario logic) is frozen in `CORE_FREEZE.json`.
`tests/test_core_freeze.py` fails on any change. Bug fixes must be recorded
with `python -m src.core.freeze --record "<reason>"`.
