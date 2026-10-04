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

The Orchestrator selects the exact specialist set for each scenario stage
(DOCX Annex-1 A.4):

| Stage | Agents activated |
|---|---|
| T0 — performance symptom | Technical |
| T1 — security indicators | Technical + Cybersecurity + Standards |
| T2 — critical service / data risk | Critical Infrastructure + Privacy + Policy & Legal |
| T3 — reporting / gap question | Policy & Legal + Cybersecurity + Privacy + Critical Infrastructure + Policy Gap |

Accumulated incident context (whether a cybersecurity event has been
suspected, whether CII is flagged, etc.) is preserved across chunks for
agent reasoning, but it does **not** automatically activate previously
active agents.  Stage selection is based solely on the DOCX table above.

---

## Knowledge bases

Each specialist agent has its own domain KB and retrieval mechanism.
A separate Canonical KB is used exclusively by the Verifier for independent
claim verification (DOCX §7.2).

| KB | Sources |
|---|---|
| Technical KB | 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, 5G technical material |
| Policy & Legal KB | Telecom Act 2023, TRAI Act 1997, NDCP-2018, DoT/TRAI directions |
| Cybersecurity KB | Telecom Cyber Security Rules 2024, CERT-In Directions 2022, NCSP-2013 |
| Privacy KB | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infra KB | IT (NCIIPC) Rules 2013, Telecom Act 2023 critical infra provisions |
| Standards KB | ITU-T Y.3172, 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61 Rev.3 |
| Policy Gap KB | International policy examples, neighbouring-country comparators |
| Canonical KB | Authoritative copies of all of the above (separate verification corpus) |

**Current state:** all KBs are stubs.  See `INTEGRATION_RAG_KB.md` to
integrate real vector-store retrieval.

---

## Verification

The Verifier checks every agent claim against the Canonical KB.
A claim is NEVER marked VERIFIED because an LLM generated it or because
it carries a disclaimer label.

| Outcome | Meaning |
|---|---|
| VERIFIED | Canonical KB passage found with relevance > 0.5 and no amendment conflict |
| INCOMPLETE | Canonical KB supports the claim but an amendment or exception applies |
| UNSUPPORTED | No supporting canonical passage found (or KB not yet populated) |
| CONFLICT | Another finding or source contradicts the claim |

Cross-domain verification flags relationships where one domain's finding
changes the reading of another (e.g. a telecom obligation + a privacy
obligation triggered by the same incident).

---

## Coordinator

The Coordinator combines verified multi-agent findings into one unified
assessment with five strictly separated categories (DOCX Annex-1 Table A1):

1. **Confirmed facts** — raw incident facts from the scenario
2. **Evidence-backed conclusions** — VERIFIED by Canonical KB
3. **Uncertain conclusions** — INCOMPLETE or UNSUPPORTED
4. **Conflicting findings** — contradictions between agents or sources
5. **Potential policy gaps** — areas of unclear or absent coverage, for expert review

When incident facts change between chunks, the assessment is re-issued and
earlier conclusions are updated visibly.

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

Records are saved as `.txt` (human-readable) and `.json` (machine-readable)
under `outputs/`.  A reviewer can reconstruct the decision path from scenario
chunk through retrieved evidence to final assessment.

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
# Run the test suite (33 tests)
python -m pytest tests/test_pipeline.py -v

# Run Scenario 2 (T0-T3) and print full assessments
python -c "
import sys; sys.path.insert(0, '.')
from src.pipeline import Pipeline
from src.utils.output_formatter import format_audit_record
from scenarios.scenario2_healthcare_5g import get_chunks
pipeline = Pipeline()
for chunk in get_chunks():
    record = pipeline.run_chunk(chunk)
    print(format_audit_record(record))
"
```

---

## Integration interfaces

- **RAG / Knowledge Base layer:** `INTEGRATION_RAG_KB.md`
- **UI layer:** `INTEGRATION_UI.md`

---

## Project structure

```
India_5G_Policy_Legal_Adviser/
├── src/
│   ├── core/
│   │   ├── models.py          # Data contracts (EvidenceItem, AgentFinding, ...)
│   │   ├── orchestrator.py    # Swarm Orchestrator
│   │   ├── verifier.py        # Verifier (4 outcomes)
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
│   │   └── kb_registry.py     # Maps AgentID to KB instance
│   ├── utils/
│   │   └── output_formatter.py
│   └── pipeline.py            # Top-level entry point
├── scenarios/
│   ├── scenario1_slicing_incident.py
│   └── scenario2_healthcare_5g.py
├── knowledge_base/            # Vector store data (populated via RAG integration)
│   ├── canonical/
│   ├── technical/
│   ├── policy_legal/
│   ├── cybersecurity/
│   ├── privacy/
│   ├── critical_infrastructure/
│   ├── standards/
│   └── policy_gap/
├── outputs/                   # Assessment text and audit JSON files
├── tests/
│   └── test_pipeline.py
├── INTEGRATION_RAG_KB.md
├── INTEGRATION_UI.md
└── README.md
```

---

## Implementation status

| Component | Status |
|---|---|
| Project structure | Complete |
| 7 specialist agents | Complete (role-bounded, no cross-role bleed) |
| Swarm Orchestrator | Complete (exact DOCX stage-specific agent sets) |
| Two-pass Policy Gap execution | Complete |
| Verifier (4 outcomes) | Complete (evidence-based, no LLM confidence shortcuts) |
| Coordinator (5 categories) | Complete |
| KB integration interface | Complete (stubs in place, ready for real vector stores) |
| Scenario chunks T0-T3 | Complete |
| Pipeline tests (33) | Passing |
| RAG / vector store | Not yet integrated — see INTEGRATION_RAG_KB.md |
| UI layer | Not yet integrated — see INTEGRATION_UI.md |

---

## Key design rules

1. No cross-agent role bleed — each agent speaks only within its mandate
2. No fake verification — claims are UNSUPPORTED until the Canonical KB confirms them
3. Standards are reference points only — never stated as Indian law
4. Uncertainty preserved — DOCX Table A1 categories are strictly separated
5. Non-conclusive gap language — policy gaps use "potential gap", never assert failure
6. Human review notice present — in every output, unconditionally
