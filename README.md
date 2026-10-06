# India 5G Policy & Legal Adviser

**An Agentic AI System for Evidence-Backed Analysis of Evolving 5G Incidents**

Team: Harshini K (lead), Arshitha S, Charithra H S | Mentor: Rajat Duggal | Org: Nokia  
Build-a-thon role: Policy and Legal Adviser | Evaluation environment: ITU AI for Good Sandbox

---

## Purpose

Understanding an evolving 5G incident requires simultaneous analysis across
telecommunications regulation, cybersecurity, personal data protection,
critical infrastructure, and international standards.  A single incident
can trigger obligations under multiple Indian instruments, involve several
institutions, and expose gaps in the current framework — often all at once.

This system provides structured, evidence-linked decision support for such
incidents.  It does not replace legal counsel, regulators, or government
decision-makers.

---

## Architecture

```
Scenario Chunk
      |
      v
Swarm Orchestrator  --- selects relevant agents for this stage ---+
      |                                                            |
      |    Pass 1: specialist agents                               |
      |    +-----------+  +-------------+  +--------------+       |
      |    | Technical |  | Policy &    |  | Cybersecurity|       |
      |    |   Agent   |  | Legal Agent |  |    Agent     |       |
      |    |   (RAG)   |  |   (RAG)     |  |    (RAG)     |       |
      |    +-----------+  +-------------+  +--------------+       |
      |    +-----------+  +-------------+  +--------------+       |
      |    |  Privacy  |  | Critical    |  |  Standards   |       |
      |    |   Agent   |  | Infra Agent |  |    Agent     |       |
      |    |   (RAG)   |  |   (RAG)     |  |    (RAG)     |       |
      |    +-----------+  +-------------+  +--------------+       |
      |                                                            |
      |<-- Pass-1 AgentFindings <----------------------------------+
      |
      v
  Verifier (Pass 1)  <-- Canonical KB (independent verification corpus)
      |
      | verified findings -> incident_state
      |
      v
  Pass 2: Policy Gap Agent (T3 only, receives verified findings)
      |
      v
  Verifier (Pass 2)
      |
      v
  Coordinator
      |
      v
  CoordinatorAssessment
  +-- Confirmed facts
  +-- Evidence-backed conclusions  (VERIFIED)
  +-- Uncertain conclusions        (INCOMPLETE / UNSUPPORTED)
  +-- Conflicting findings         (CONFLICT)
  +-- Potential policy gaps
      |
      v
  AuditRecord  ->  outputs/  (text + JSON)
```

---

## Specialist agents

| Agent | Mandate | Indian instruments |
|---|---|---|
| Technical | 5G radio, core, slicing, network functions | 3GPP TS 23.501, TS 33.501 (reference) |
| Policy & Legal | Indian telecom law and regulation | Telecom Act 2023, TRAI Act 1997, NDCP-2018 |
| Cybersecurity | Cyber incident classification and response | Telecom Cyber Security Rules 2024, CERT-In Directions 2022, NCSP-2013 |
| Privacy | Personal data and data-protection implications | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infrastructure | CII designation and additional obligations | IT (NCIIPC) Rules 2013, Telecom Act 2023 |
| Standards | International technical/security comparison | ITU-T Y.3172, 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61 Rev.3 |
| Policy Gap | Potential gaps, ambiguities, overlaps | All above + international policy examples |

Each agent speaks only within its defined mandate.  International standards
are always labelled as reference points, never as Indian law.

---

## Swarm Orchestrator

The swarm has no fixed sequence (DOCX §3.2).  For each chunk the
Orchestrator activates only the specialists justified by the information
released in that chunk (§2.5), read against the incident state (§3.3).
The chunk's position in the scenario is never used.

| Information released in the chunk | Agents activated |
|---|---|
| Performance symptom or security indicator | Technical |
| Security indicator | + Cybersecurity + Standards |
| Critical service | Critical Infrastructure + Policy & Legal |
| Personal data involved | Privacy + Policy & Legal |
| Possible data exposure | + Cybersecurity |
| Reporting / escalation question | Policy & Legal, plus each domain already flagged in the incident state (Cybersecurity, Privacy, Critical Infrastructure) |
| Policy-gap question | Policy Gap (only after earlier chunks have verified findings) |

These rules reproduce both staged scenarios in the DOCX:

| Chunk | Scenario 1 (§2.4, Annex-1 A.4) | Scenario 2 (§2.5) |
|---|---|---|
| 1 / T0 | Technical | Technical |
| 2 / T1 | Technical + Cybersecurity + Standards | Technical + Cybersecurity + Standards |
| 3 / T2 | Critical Infrastructure + Policy & Legal | Critical Infrastructure + Privacy + Policy & Legal |
| 4 / T3 | Privacy + Policy & Legal + Cybersecurity | Policy & Legal + Cybersecurity + Privacy + Critical Infrastructure + Policy Gap |

Accumulated incident context (whether a cybersecurity event has been
suspected, whether CII is flagged, etc.) is preserved across chunks for
agent reasoning.  It re-activates earlier domains only when the current
chunk asks a reporting/escalation question that spans the whole incident.

---

## Knowledge bases

Each specialist agent has its own domain KB and retrieval mechanism.
A separate Canonical KB is used exclusively by the Verifier for independent
claim verification (DOCX §7.2).

| KB | Ingested sources | Passages |
|---|---|---|
| Technical KB | 3GPP TS 23.501, TS 33.501 | 3,739 |
| Policy & Legal KB | Telecommunications Act 2023 + commencement notifications S.O. 2408(E), S.O. 2623(E); TRAI Act 1997; NDCP-2018; NCSP-2013; CTI Rules 2024; NITI Aayog National Strategy for AI | 603 |
| Cybersecurity KB | Telecom Cyber Security Rules 2024 (official DoT copy) + Amendment Rules 2025, CERT-In Directions 2022, NCSP-2013, NDCP-2018; reference: 3GPP TS 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 | 1,680 |
| Privacy KB | DPDP Act 2023, DPDP Rules 2025 | 159 |
| Critical Infra KB | Telecommunications Act 2023, Critical Telecommunication Infrastructure Rules 2024 (**NCIIPC Rules 2013 not ingested**) | 126 |
| Standards KB | ITU-T Y.3172, 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 | 4,259 |
| Policy Gap KB | TRAI AI & Big Data Recommendations 2023, NCSP-2013, NDCP-2018, NITI Aayog National Strategy for AI, Right of Way Rules 2024; EU policy examples: ENISA 5G Security Controls Matrix, ENISA 5G Cybersecurity Standards | 1,029 |
| Canonical KB | All 23 ingested sources (separate verification corpus) | 5,710 |

Sources, provenance and what was not ingested: `knowledge_base/sources/manifest.json`
(curated) and `knowledge_base/ingestion_manifest.json` (generated). Details:
`INTEGRATION_RAG_KB.md`.

In-force status and amendment history have not been checked for any source,
so a claim fully supported by its cited text is **INCOMPLETE, not VERIFIED**.

---

## Verification

Agents state what a law or standard says only by quoting a passage
retrieved from their own KB, and record it as the claim's citation
(`AgentFinding.claim_citations`).  With no passages, an agent names the
instruments in its mandate and states that their applicability is not
assessed — it never supplies their content from memory.

The Verifier checks every claim against the Canonical KB: does the cited
source/section exist there, and does the authoritative text support the
claim?  Support is decided by text, never by retrieval similarity, model
confidence, or a disclaimer label.

| Outcome | Meaning |
|---|---|
| VERIFIED | The canonical text of the cited section supports the claim; in force; no amendment recorded |
| INCOMPLETE | Supported, but an amendment applies — or the claim matches its cited passage while the Canonical KB is not yet populated |
| UNSUPPORTED | Cited section not in the Canonical KB, text does not support the claim, passage not in force, or no evidence |
| INCOMPLETE (live corpus) | Supported by the cited text, but in-force status / amendments not checked — currently every quoted provision |
| CONFLICT | Another finding or source contradicts the claim; both sides kept with their evidence |

The support check is pluggable (`Verifier(..., support_judge=...)`); the
default `LexicalSupportJudge` is deterministic so runs can be replayed.

**Cross-domain verification** (`src/core/cross_domain.py`) links findings of
different domains only where the evidence establishes it — never because
two agents are active:

| Relationship | Established when | Live example (Scenario 2) |
|---|---|---|
| shared provision | both domains cite the same source and section | Critical Infrastructure and Policy & Legal both cite Telecommunications Act, 2023, Section 22 |
| instrument basis | an instrument cited in one domain names, in its own Canonical KB text, an Act cited in the other | Telecom Cyber Security Rules (Cybersecurity) are made "in exercise of the powers conferred by … section 22 … of the Telecommunications Act, 2023" (Critical Infrastructure / Policy & Legal) |
| parallel reporting | both domains cite Indian legal duties to report the same incident, to different recipients | TCS Rules Rule 7 (Central Government, six hours) and CERT-In Direction (ii) (CERT-In, 6 hours) vs DPDP Rules Rule 7 (Data Principal and Board, without delay) |

Findings of agents that ran in an earlier chunk take part (a T2 privacy
finding links to a T1 cybersecurity finding).

**Conflicts** are recorded as `ConflictRecord`s: Finding A and Finding B,
each with its evidence, the basis, the status ("unresolved; requires
qualified human review") and the Coordinator's treatment.  Rules:

- *reporting deadline* — two cited duties to report the same incident to
  the same recipient within different time limits;
- *CII obligations* — CII relevance found, but Policy & Legal examined its
  sources and found no corresponding obligation;
- *exposure classification* — exposure confirmed by Privacy, but
  Cybersecurity does not treat the incident as a security event.

The ingested corpus contains no disagreeing provisions, so the live run has
no conflict — correctly.  The conflict path is demonstrated with labelled
synthetic passages (`src/scenario/conflict_fixture.py`,
`python -m src.scenario.run --conflict-demo`, recorded in
`outputs/audit/day2_conflict_demo_FIXTURE.jsonl`).

---

## Coordinator

The Coordinator combines verified multi-agent findings into one unified
assessment with five strictly separated categories (DOCX Annex-1 Table A1):

1. **Confirmed facts** — raw incident facts from the scenario
2. **Evidence-backed conclusions** — VERIFIED by Canonical KB
3. **Uncertain conclusions** — INCOMPLETE or UNSUPPORTED
4. **Conflicting findings** — contradictions between agents or sources
5. **Potential policy gaps** — areas of unclear or absent coverage, for expert review

**Progressive reassessment.** Each chunk's assessment covers the whole
incident so far:

- confirmed facts accumulate across chunks;
- conclusions of agents not active in this chunk are carried forward under
  their last outcome, tagged `[carried forward from <chunk> — not re-examined]`;
- `changes_from_prior` is computed by comparison: newly active / inactive
  agents, incident flags that became true in this chunk, newly cited
  provisions, re-rated claims, superseded claims, new cross-domain links,
  conflicts and policy gaps.

**Conflicts** are shown with both findings and their evidence; neither is
adopted, and both are withheld from the other categories.

**Uncertainty.** UNSUPPORTED claims are labelled "insufficient evidence;
preliminary only"; `open_questions` lists the evidence the agents and the
Verifier found missing, and states explicitly when no conclusion is
evidence-backed.

Policy gaps use non-conclusive language ("potential gap", "regulatory
ambiguity").  No conclusion of policy failure is drawn.

---

## Audit and replay

Every pipeline run produces an `AuditRecord` containing:
- Timestamp and chunk ID
- Active agent IDs
- All agent findings with claims, evidence references, and uncertainty notes
- Verifier outcomes per claim
- Cross-domain links and conflicts
- Coordinator assessment (all five categories)

The scenario engine (`src/scenario/`) writes each run to an append-only,
hash-chained audit trail, `outputs/audit/<run_id>.jsonl` (`src/audit/`), with
the DOCX §7.6 fields per agent: visible input, retrieval queries, retrieved
passages with source/section/page, decision summary, citations, verifier
outcome, cross-domain flags and the Coordinator decision.  A run can be
replayed stage by stage (UI Replay mode, or `--replay`), its hash chain
checked, and its recorded chunk sequence re-executed and compared with the
record.

---

## Scenario workflow

The system is evaluated against staged scenario chunks in which facts are
released progressively so that later facts are not visible to earlier agent
runs (DOCX §2.5).

Two scenarios are provided:
- `scenarios/scenario1_slicing_incident.py` — 5G network-slicing incident (DOCX §2.4)
- `scenarios/scenario2_healthcare_5g.py` — Healthcare 5G private network incident (DOCX §2.5)

---

## How to run

```powershell
pip install -r requirements.txt

# Build the knowledge bases from knowledge_base/sources (~6 min on CPU)
python -m src.rag.build

# One retrieval test per agent -> knowledge_base/retrieval_tests.md
python -m src.rag.retrieval_demo

# Run the test suite
python -m pytest tests -v

# Demonstration UI: live run (chunk by chunk) and replay
streamlit run src/ui/app.py

# Command line: release T0 and T1, record the audit trail; then replay it
python -m src.scenario.run --stages 2
python -m src.scenario.run --replay outputs/audit/<run_id>.jsonl --reexecute
python -m src.scenario.run --conflict-demo       # conflict handling (labelled fixtures)
python -m src.scenario.run --replay outputs/audit/<run_id>.jsonl --explain  # decision path per stage
python -m src.audit.evaluation_report            # evaluation summary from a real test run

# Run Scenario 2 (T0-T3) with the live knowledge bases
python -c "
import sys; sys.path.insert(0, '.')
from src.pipeline import Pipeline
from src.rag.registry import build_registry
from src.utils.output_formatter import format_audit_record
from scenarios.scenario2_healthcare_5g import get_chunks
pipeline = Pipeline(build_registry())
for chunk in get_chunks():
    record = pipeline.run_chunk(chunk)
    print(format_audit_record(record))
"
```

---

## Integration interfaces

- **RAG / Knowledge Base layer:** `INTEGRATION_RAG_KB.md`
- **UI layer:** `INTEGRATION_UI.md`
- **Whole-project run steps:** `INTEGRATION_CHECKLIST.md`
- **Evaluation summary:** `knowledge_base/evaluation_report.md`
- **Technical explanation (presentation):** `TECHNICAL_EXPLANATION.md`
- **Final handoff — sources, evidence examples, claims not to make:** `FINAL_HANDOFF.md`
- **Golden demo script (8–10 min) and failure fallbacks:** `DEMO_SCRIPT.md`
- **Rehearsal log and final team check:** `REHEARSAL_LOG.md`
- **Evidence audit:** `knowledge_base/evidence_audit.md` (`python -m src.rag.evidence_audit`)
- **Core freeze:** `CORE_FREEZE.json` (`python -m src.core.freeze --check`)

---

## Project structure

```
India_5G_Policy_Legal_Adviser/
├── src/
│   ├── core/
│   │   ├── models.py          # Data contracts (EvidenceItem, AgentFinding, ...)
│   │   ├── orchestrator.py    # Swarm Orchestrator
│   │   ├── verifier.py        # Verifier (4 outcomes)
│   │   ├── cross_domain.py    # Evidence-based cross-domain links and conflicts
│   │   └── coordinator.py     # Coordinator (5-category synthesis)
│   ├── agents/
│   │   ├── base_agent.py      # Abstract base — RAG integration point
│   │   ├── technical_agent.py
│   │   ├── policy_legal_agent.py
│   │   ├── cybersecurity_agent.py
│   │   ├── privacy_agent.py
│   │   ├── critical_infra_agent.py
│   │   ├── standards_agent.py
│   │   └── policy_gap_agent.py
│   ├── knowledge_base/
│   │   ├── base_kb.py         # Abstract KB interface
│   │   ├── in_memory_kb.py    # Dependency-free KB for tests and early integration
│   │   ├── text_match.py      # Deterministic text helpers (support check)
│   │   └── kb_registry.py     # Maps AgentID to KB instance
│   ├── rag/                   # RAG / knowledge-base layer
│   │   ├── manifest.py        # Source manifest loading; KB names
│   │   ├── extract.py         # PDF / DOCX extraction with page provenance
│   │   ├── sections.py        # Cleaning, section detection, chunking
│   │   ├── embedding.py       # bge-small-en-v1.5 embeddings
│   │   ├── vector_store.py    # One store per KB
│   │   ├── vector_kb.py       # Live KnowledgeBase / CanonicalKnowledgeBase
│   │   ├── build.py           # python -m src.rag.build
│   │   ├── registry.py        # build_registry() -> live KBRegistry
│   │   ├── interface.py       # run_agent(agent_id, chunk) -> AgentFinding
│   │   └── retrieval_demo.py  # python -m src.rag.retrieval_demo
│   ├── scenario/
│   │   ├── catalog.py         # DOCX stage tables (display/check only)
│   │   ├── engine.py          # ScenarioEngine: chunk-by-chunk release + state
│   │   ├── conflict_fixture.py # Labelled synthetic KBs for the conflict demonstration
│   │   └── run.py             # python -m src.scenario.run
│   ├── audit/
│   │   ├── trail.py           # Append-only, hash-chained JSONL audit trail
│   │   └── replay.py          # Load, verify, step through, re-execute
│   ├── ui/
│   │   └── app.py             # streamlit run src/ui/app.py
│   ├── utils/
│   │   └── output_formatter.py
│   └── pipeline.py            # Top-level entry point
├── scenarios/
│   ├── scenario1_slicing_incident.py
│   └── scenario2_healthcare_5g.py
├── knowledge_base/
│   ├── sources/
│   │   ├── manifest.json      # Curated source manifest (in git)
│   │   └── raw/               # Downloaded source files (git-ignored)
│   ├── ingestion_manifest.json  # What was actually ingested (generated, in git)
│   ├── retrieval_tests.md     # One retrieval test per agent (generated, in git)
│   ├── canonical/ technical/ policy_legal/ cybersecurity/ privacy/
│   │   critical_infrastructure/ standards/ policy_gap/   # vector stores (git-ignored)
├── outputs/                   # Assessment text/JSON; audit/ holds recorded runs
├── tests/
│   ├── test_pipeline.py
│   ├── test_verification_evidence.py
│   ├── test_rag.py
│   ├── test_scenario_audit.py
│   └── test_cross_domain.py
├── requirements.txt
├── INTEGRATION_RAG_KB.md
├── INTEGRATION_UI.md
└── README.md
```

---

## Implementation status

| Component | Status |
|---|---|
| Project structure | Complete |
| 7 specialist agents | Complete (role-bounded; source content only from cited retrieved passages) |
| Swarm Orchestrator | Complete (selection from released information; matches both DOCX scenario tables) |
| Two-pass Policy Gap execution | Complete |
| Verifier (4 outcomes) | Complete (citation + canonical-text support check; pluggable judge) |
| Coordinator (5 categories) | Complete |
| Scenario chunks T0-T3 | Complete |
| RAG / vector store | Complete — 14 of 16 DOCX sources ingested, 8 KBs, one retrieval test per agent passing |
| Not ingested | IT (NCIIPC) Rules 2013 (source unreachable); international policy examples (not specified in DOCX) |
| In-force / amendment checks | Not done for any source — quoted claims are INCOMPLETE, not VERIFIED |
| Scenario engine, audit trail, replay | Complete — stage tables checked against the DOCX; hash-chained JSONL; re-execution compare |
| Demonstration UI | Day-1 functional UI (Streamlit): live run and replay |
| Cross-domain verification | Complete — evidence-based (shared provision, instrument basis, parallel reporting), across chunks |
| Conflict handling | Complete — structured Finding A / Finding B with evidence; demonstrated with labelled fixtures (the live corpus has no conflicting provisions) |
| Progressive reassessment | Complete — cumulative facts, carried-forward conclusions, computed changes |
| Full 4-stage run | Recorded: `outputs/audit/day2_scenario2_full_T0_T3.jsonl` (replays and re-executes exactly) |
| Tests | All passing — see `knowledge_base/evaluation_report.md` for per-area counts and status (Working / Partially working / Not yet implemented) |

---

## Key design rules

1. No cross-agent role bleed — each agent speaks only within its mandate
2. No fake verification — claims are UNSUPPORTED until the Canonical KB confirms them
3. Standards are reference points only — never stated as Indian law
4. Uncertainty preserved — DOCX Table A1 categories are strictly separated
5. Non-conclusive gap language — policy gaps use "potential gap", never assert failure
6. Human review notice present — in every output, unconditionally
