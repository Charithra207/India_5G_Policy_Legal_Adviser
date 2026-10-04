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

pipeline = Pipeline()   # create once; reuse across chunks

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
│   │           cross_domain_flag, cross_domain_note
│   ├── cross_domain_links      list[str]
│   ├── conflicts               list[str]
│   └── missing_evidence        list[str]
│
└── agent_findings              list[AgentFinding]
    └── each: agent_id, summary, claims, evidence,
              uncertainty_notes, missing_facts
```

Enum values are plain strings via `.value`, e.g.
`AgentID.TECHNICAL.value == "technical"`.

---

## Running a multi-chunk scenario

```python
from src.pipeline import Pipeline
from scenarios.scenario2_healthcare_5g import get_chunks

pipeline = Pipeline()
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

Show which knowledge bases are live vs stub:

```python
from src.knowledge_base.kb_registry import KBRegistry
status = KBRegistry().status_report()
# {'canonical': False, 'technical': False, ...}
# False = stub; True = real RAG active
```

Display a warning when any KB is not live so users understand that
claims may be `UNSUPPORTED`.

---

## Verifier outcome display

| Outcome | Suggested treatment |
|---|---|
| `VERIFIED` | Green — supported by authoritative source |
| `INCOMPLETE` | Amber — supported but amendment/exception may apply |
| `UNSUPPORTED` | Red — not verified; treat as preliminary |
| `CONFLICT` | Orange — contradicted by another source or agent |

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
python -m pytest tests/test_pipeline.py -v

# Run a full scenario and view output
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

## Integration checklist

- [ ] All five Coordinator categories displayed in Table A1 order
- [ ] Human review notice always visible (not hidden or collapsible)
- [ ] Verifier outcomes colour-coded per the table above
- [ ] Changes-from-prior banner displayed between chunks
- [ ] Cross-domain relationships visually annotated
- [ ] KB status display shows live vs stub for each domain
- [ ] Standards claims show `[REFERENCE ONLY — not Indian law]` label
- [ ] Policy gap statements use non-conclusive language
- [ ] `python -m pytest tests/test_pipeline.py -v` passes after changes
