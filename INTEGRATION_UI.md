# UI Integration

**Project:** India 5G Policy & Legal Adviser  
**Component:** User interface / presentation layer  

---

## Overview

The pipeline is fully operational.  The UI layer calls one method and
receives a complete, structured assessment object.  No pipeline internals
are needed.

---

## The single entry point

```python
from src.pipeline import Pipeline
from src.core.models import ScenarioChunk
from src.rag.registry import build_registry

# create once; reuse across chunks.  build_registry() loads the live
# knowledge bases (build them first: python -m src.rag.build).
# Pipeline() with no argument runs on stubs: every claim UNSUPPORTED.
pipeline = Pipeline(build_registry())

chunk = ScenarioChunk(
    chunk_index  = 0,
    chunk_id     = "incident_chunk_1",
    timestamp    = "2024-10-04T09:00:00Z",
    description  = "Intermittent latency and session drops in the private 5G slice.",
    new_facts    = ["Latency spikes detected.", "Session drops occurring."],
    prior_chunks = [],
)
record = pipeline.run_chunk(chunk)
```

`record` is an `AuditRecord` containing everything the UI needs.

---

## `AuditRecord` structure

```
AuditRecord
├── chunk_id                    str
├── timestamp                   str (ISO-8601)
├── active_agents               list[AgentID]   — which agents ran
├── raw_chunk                   ScenarioChunk   — what was released
│
├── coordinator_assessment      CoordinatorAssessment
│   ├── confirmed_facts             list[str]
│   ├── evidence_backed_conclusions list[str]
│   ├── uncertain_conclusions       list[str]
│   ├── conflicting_findings        list[str]
│   ├── potential_policy_gaps       list[str]
│   ├── cross_domain_relationships  list[str]
│   ├── relevant_institutions       list[str]
│   ├── changes_from_prior          list[str]
│   └── human_review_required       str
│
├── verifier_result             VerifierResult
│   ├── verified_claims         list[VerifiedClaim]
│   │   └── each: agent_id, claim, outcome, rationale,
│   │           supporting_evidence, conflicting_evidence,
│   │           cross_domain_flag, cross_domain_note
│   ├── cross_domain_links      list[str]
│   ├── conflicts               list[str]
│   └── missing_evidence        list[str]
│
└── agent_findings              list[AgentFinding]
    └── each: agent_id, summary, claims, evidence,
              claim_citations, uncertainty_notes, missing_facts
```

`claim_citations` maps a claim's text to the passages it quotes.  A claim
present there states what a source says; show its citation
(`source_title, section`) next to it.  A claim absent from it is the
agent's own reading of the incident facts.

`potential_policy_gaps` entries carry one of two tags — keep them visually
distinct:

| Tag | Meaning |
|---|---|
| `[POLICY GAP — for expert review]` | Raised after examining the Canonical KB; has cited passages |
| `[CANDIDATE GAP AREA — not examined]` | Arises from the incident, but could not be examined (e.g. Canonical KB not populated) — not a finding |

The audit JSON (`save_audit_json`) also includes `verified_claims` (per-claim
outcome, rationale and supporting passages) and each finding's
`claim_citations`.

Enum values are plain strings via `.value`, e.g.
`AgentID.TECHNICAL.value == "technical"`.

---

## Running a multi-chunk scenario

```python
from src.pipeline import Pipeline
from src.rag.registry import build_registry
from scenarios.scenario2_healthcare_5g import get_chunks

pipeline = Pipeline(build_registry())
chunks   = get_chunks()   # all four T0–T3 chunks

for chunk in chunks:
    record = pipeline.run_chunk(chunk)
    # render record here

```

**Important:** use the **same `pipeline` instance** for all chunks in a
scenario.  The Orchestrator accumulates incident context between chunks.

---

## Pre-built text and JSON output

```python
from src.utils.output_formatter import (
    format_audit_record,   # -> human-readable string
    save_assessment_text,  # -> writes outputs/<chunk_id>_assessment.txt
    save_audit_json,       # -> writes outputs/<chunk_id>_audit.json
)

text = format_audit_record(record, include_raw_findings=True)
print(text)

save_assessment_text(record, output_dir="outputs")
save_audit_json(record, output_dir="outputs")
```

---

## KB status display

Show which knowledge bases are live vs stub, and which sources are missing:

```python
import json
from src.rag.registry import build_registry

status = build_registry().status_report()
# {'canonical': True, 'technical': True, ...}   False = stub (no retrieval)

ingested = json.load(open("knowledge_base/ingestion_manifest.json", encoding="utf-8"))
missing = [d for d in ingested["documents"] if d["status"] != "ingested"]
# currently: IT (NCIIPC) Rules 2013; international policy examples
```

Display a warning when any KB is not live, and list the missing sources,
so users know, for example, that the Critical Infrastructure agent has no
NCIIPC Rules to draw on.

---

## Evidence display (from Member 2)

The priority is that a reader can see **exactly what was retrieved, from
where, and what has not been checked**.

**For every quoted claim**, i.e. every claim in `finding.claim_citations`,
show the passage it quotes, not just the claim:

| Show | Field (`EvidenceItem`) | Notes |
|---|---|---|
| Source | `source_title`, `authority` | e.g. "Telecommunications (Telecom Cyber Security) Rules, 2024" |
| Section and heading | `section`, `section_title` | e.g. "Rule 7 — Reporting of security incidents" |
| Page | `page` | page of the downloaded file; empty for 3GPP Word files |
| Passage | `excerpt` | verbatim; render as a quotation |
| Date | `date_issued` | as printed in the document; blank means not stated |
| Link | `url` | the exact file that was ingested |
| Provenance | `provenance_note` | **show it**: some copies are not from the issuing ministry's site (TRAI Act from TDSAT, NDCP-2018 from S3WaaS, Telecom Cyber Security Rules from thc.nic.in) |
| In force? | `effective` | `None` → show **"in-force status not verified"**; never show as in force |
| Amendments | `amendment_checked` | `False` → show **"amendments not checked"** |
| Jurisdiction | `jurisdiction` | non-India → the claim already carries `[REFERENCE ONLY — not Indian law]`; also badge it |

**Claims not in `claim_citations`** are the agent's own reading of the
incident facts, e.g. "Personal data exposure is SUSPECTED". Show them as
such, separately from quoted provisions.

**Do not show `relevance_score` as confidence.** It is retrieval similarity
and clusters at 0.67–0.85 whether or not a passage is relevant. If it is
shown at all, put it in an audit/debug view.

**Policy gaps:** each raised gap names the instruments or sections it
examined. Absence claims (e.g. "none of the 485 Indian passages … mentions
network slicing") cite no passage, by design; show the examined-instruments
list instead.

The audit JSON (`save_audit_json`) has all of this per claim under
`verified_claims[].supporting_evidence`. `knowledge_base/retrieval_tests.md`
shows a rendered example for every agent.

---

## Scenario engine, demonstration UI, audit trail and replay (Member 3)

Status: Day 1 delivered. All of it calls `Pipeline.run_chunk`; nothing here
selects agents, retrieves, verifies or assesses.

```powershell
streamlit run src/ui/app.py                     # Live run + Replay
python -m src.scenario.run --stages 2           # Day-1 test: T0 then T1
python -m src.scenario.run --replay outputs/audit/<run_id>.jsonl --reexecute
```

| Piece | File | What it does |
|---|---|---|
| Scenario catalogue | `src/scenario/catalog.py` | DOCX §2.5 and Annex-1 A.4 stage tables, copied verbatim. Used only to **check and display** the Orchestrator's selection, never to drive it |
| Scenario engine | `src/scenario/engine.py` | `ScenarioEngine(scenario_id, registry)`: `next_stage()` releases one chunk to the pipeline and records it; `state()` gives scenario, stage, activated agents, previous and current findings, evidence, verification, cross-domain links, policy gaps |
| Audit trail | `src/audit/trail.py` | `outputs/audit/<run_id>.jsonl`: `run_started` header (scenario, KB status, KB build hash, git commit), one `stage` entry per chunk, `run_completed`. Append-only; each entry carries `prev_hash`/`hash` so edits, removals and reordering are detected |
| Replay | `src/audit/replay.py` | `load_run` (checks the hash chain), step through stages, `reexecute` (re-runs the chunk sequence **from the record** and compares agents, passages, claims, outcomes, Coordinator categories) |
| UI | `src/ui/app.py` | Streamlit. Shows each stage in the order Scenario → Current chunk → Active agents → Agent findings → Evidence/sources → Verifier → Coordinator → Policy gap/cross-domain → Previous findings → Audit entry |

**Stage entry (DOCX §7.6).** Per agent: `agent_id`, `visible_input`
(released text, new facts, earlier chunk IDs, and the incident state the
agent could read, including prior verified findings), `queries`,
`retrieved_passages` (source, section, heading, page, verbatim excerpt,
URL, provenance, `effective`, `amendment_checked`), `decision_summary`,
`mandate_output`, `claims` (each with citations, verifier outcome and
rationale, cross-domain flag/note), uncertainty and missing facts. Per stage:
timestamps, chunk, Orchestrator selection vs the DOCX table, verifier counts,
conflicts, missing evidence, and the full Coordinator assessment.

To capture what each agent saw, the core now records it (additive only):
`BaseAgent.analyze` keeps `last_queries`, and `AuditRecord.agent_inputs`
holds each agent's visible incident state and queries.

The live UI and replay render the same stage entries, so what is shown live
is exactly what is recorded.

**Day-1 test (recorded):** `outputs/audit/archive/day1_scenario2_T0_T1.jsonl` (archived).
T0 → Technical; T1 → Technical + Cybersecurity + Standards, both matching the
DOCX table. The Coordinator reports the reclassification, and re-execution
reproduces both stages.

**Day-2 additions (core).** Stage entries now also carry
`verifier.cross_domain_details` (kind, agents, linked findings, establishing
passages) and `verifier.conflict_details` (Finding A / Finding B with
evidence, basis, status, Coordinator treatment); the Coordinator assessment
adds `open_questions`, `claim_register` and `link_register`. The UI shows
conflicts side by side, carried-forward conclusions greyed and tagged, and
the "no conclusion is evidence-backed" notice. A run on fixture KBs records
`knowledge_base_note` in its header and the UI shows it as a warning.

Recorded runs: `day2_scenario2_full_T0_T3.jsonl` (live KBs, all four
stages) and `day2_conflict_demo_FIXTURE.jsonl` (labelled synthetic passages).

### Remaining Member 3 work

- Visual polish: cross-domain links drawn between agent panels; a
  side-by-side stage diff (claims added/removed/re-rated between stages).
- Collapse repetitive evidence: the same passage retrieved by several agents
  is currently shown once per agent.
- Export a replay as a single HTML/PDF evidence report for judges.
- Y.3172 pipeline trace view (source → collection → preprocessing → model →
  policy → distribution; Sandbox marked "not executed").
- Store audit runs with the ITU AI for Good Sandbox artefacts (§7.6), once
  the Sandbox is available.
- Show the DOCX wording beside the scenario file's wording where they differ
  (T1 adds "on the affected private 5G slice").

---

## Verifier outcome display

| Outcome | Suggested treatment |
|---|---|
| `VERIFIED` | Green — supported by the authoritative text, in force, amendments checked |
| `INCOMPLETE` | Amber — supported, but an amendment applies **or in-force status / amendments were not checked** (currently true of every ingested source), or a potential policy gap |
| `UNSUPPORTED` | Red — not verified; treat as preliminary |
| `CONFLICT` | Orange — contradicted by another source or agent |

With the current knowledge bases no claim can be VERIFIED, because no
source's in-force status or amendment history has been checked. Expect amber
for every quoted provision. That is the correct result, not a fault.

```python
from src.core.models import VerifierOutcome

for vc in record.verifier_result.verified_claims:
    if vc.outcome == VerifierOutcome.VERIFIED:
        # render green
    elif vc.outcome == VerifierOutcome.UNSUPPORTED:
        # render red
```

---

## Coordinator categories — required display order

Display in this order (DOCX Annex-1 Table A1):

1. **Confirmed facts** — raw incident facts
2. **Evidence-backed conclusions** — VERIFIED by Canonical KB
3. **Uncertain conclusions** — INCOMPLETE or UNSUPPORTED; show caution note
4. **Conflicting findings** — needs human review
5. **Potential policy gaps** — for expert review; never frame as "policy is inadequate"

---

## Cross-domain relationships

```python
for rel in record.coordinator_assessment.cross_domain_relationships:
    display_as_linked_annotation(rel)
```

Visually connect the two domain panels the relationship names.
The text already names both domains:
`"CROSS-DOMAIN [cybersecurity <-> privacy]: ..."`.

---

## Human review notice

**Must always be visible — not collapsible, not behind a click:**

```python
record.coordinator_assessment.human_review_required
```

> Legal interpretation, regulatory decisions, and institutional action require
> qualified human judgment. This assessment is decision support only and does
> not replace legal counsel, regulators, or government decision-makers.

---

## Changes from prior chunk

```python
for change in record.coordinator_assessment.changes_from_prior:
    display_change_banner(change)
```

Provides a visible "what changed" summary between chunks, e.g.:
- "Newly activated agents: cybersecurity, standards"
- "Incident reclassified: cybersecurity indicators emerged in this chunk"

---

## Async / parallel execution

The Orchestrator's `_run_agents_parallel` async stub is in
`src/core/orchestrator.py`.  Once the RAG/KB layer is live, replace the
`_run_agents` call in `process_chunk` with `await _run_agents_parallel(...)`
and make `process_chunk` async.  The rest of the pipeline is unchanged.

---

## What NOT to change

- `src/core/models.py` — field names are the data contract
- `src/core/verifier.py` — verification logic
- `src/core/orchestrator.py` — agent selection
- `src/agents/*.py` — agent mandate logic
- `src/knowledge_base/base_kb.py` — KB interface

Add new files under `src/utils/` for UI-specific helpers.

---

## Quick start

```powershell
# Confirm the pipeline runs
python -m pytest tests -v

# Run a full scenario and view output
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

## Integration checklist

Checked against `src/ui/app.py`; the UI tests in `tests/test_scenario_audit.py`
drive the live four-stage run and a conflict replay.

- [x] All five Coordinator categories displayed in Table A1 order
- [x] Human review notice always visible (not hidden or collapsible)
- [x] Verifier outcomes colour-coded per the table above
- [x] Changes-from-prior banner displayed between chunks
- [x] Cross-domain relationships listed with the findings they link (drawn links between panels: not yet)
- [x] KB status display shows live vs stub for each domain, and the sources not ingested
- [x] Every quoted claim shows source, section, page, passage, URL and provenance
- [x] `effective is None` shown as "in-force status not verified"; `amendment_checked` False shown as "amendments not checked"
- [x] `relevance_score` not presented as confidence
- [x] Standards claims show `[REFERENCE ONLY — not Indian law]` label
- [x] Policy gap statements use non-conclusive language
- [x] Uncertainty section: uncertain conclusions, agents' notes, open questions
- [x] Conflicts shown side by side (Finding A / Finding B, evidence, status, treatment)
- [x] Replay: decision path per stage (what happened, who acted, evidence, conclusion, verification, Coordinator)
- [x] Scenario engine releases the DOCX stages one chunk at a time
- [x] Audit trail with DOCX §7.6 fields; replay with integrity check
- [x] `python -m pytest tests -v` passes after changes

Whole-project run steps: `INTEGRATION_CHECKLIST.md`.
