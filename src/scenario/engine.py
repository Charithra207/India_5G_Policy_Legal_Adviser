"""
Scenario engine
===============
Releases a staged DOCX incident one chunk at a time into Member 1's pipeline
and records each stage in the audit trail.  It makes no decisions of its
own: agent selection, retrieval, verification and the assessment all come
from `Pipeline.run_chunk` (Orchestrator → agents → RAG → Verifier →
Coordinator).

    engine = ScenarioEngine("scenario2", registry=build_registry())
    engine.next_stage()          # T0
    engine.next_stage()          # T1
    engine.state()               # current scenario state (see `scenario_state`)

The same stage entries drive the live UI and replay, so what is shown live
is exactly what is recorded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.audit.trail import AuditTrail, stage_entry
from src.core.models import ScenarioChunk
from src.pipeline import Pipeline
from src.scenario.catalog import DEFAULT_SCENARIO, ScenarioSpec, get_scenario


class ScenarioEngine:
    """
    Parameters
    ----------
    scenario_id : key in `src.scenario.catalog.SCENARIOS`
    registry    : KBRegistry (live: `src.rag.registry.build_registry()`);
                  None runs on the core's stub KBs
    audit_dir   : where the run's JSONL audit trail is written (default
                  outputs/audit/, or $ADVISER_AUDIT_DIR)
    record      : False keeps the stage entries in memory only
    run_id      : optional fixed run ID (default: scenario + UTC time)
    """

    def __init__(self, scenario_id: str = DEFAULT_SCENARIO, registry=None,
                 audit_dir: Optional[Path] = None, run_id: Optional[str] = None,
                 record: bool = True) -> None:
        self.spec: ScenarioSpec = get_scenario(scenario_id)
        self.chunks: list[ScenarioChunk] = self.spec.load_chunks()
        if len(self.chunks) != len(self.spec.stages):
            raise ValueError(f"{scenario_id}: {len(self.chunks)} chunks but "
                             f"{len(self.spec.stages)} DOCX stages")
        self.pipeline = Pipeline(registry)
        self.kb_status = self.pipeline.registry.status_report()
        self.trail: Optional[AuditTrail] = (
            AuditTrail.start(self.spec, self.kb_status, audit_dir, run_id)
            if record else None
        )
        self.records = []           # pipeline AuditRecords, in stage order
        self.stages: list[dict] = []  # audit stage entries, in stage order

    # ------------------------------------------------------------------

    @property
    def stage_count(self) -> int:
        return len(self.chunks)

    @property
    def stages_run(self) -> int:
        return len(self.stages)

    def has_next(self) -> bool:
        return self.stages_run < self.stage_count

    def next_stage(self) -> dict:
        """Release the next chunk to the pipeline; return its audit stage entry."""
        if not self.has_next():
            raise RuntimeError("All stages of the scenario have been released.")
        i = self.stages_run
        record = self.pipeline.run_chunk(self.chunks[i])
        previous = self.stages[-1]["orchestrator"]["active_agents"] if self.stages else []
        if self.trail is not None:
            entry = self.trail.record_stage(record, self.spec.scenario_id,
                                            self.spec.stages[i], previous)
        else:
            entry = stage_entry(record, self.spec.scenario_id, self.spec.stages[i], previous)
        self.records.append(record)
        self.stages.append(entry)
        if self.trail is not None and not self.has_next():
            self.trail.complete()
        return entry

    def run_until(self, stage_count: int) -> list[dict]:
        """Run stages until `stage_count` have been released."""
        while self.stages_run < min(stage_count, self.stage_count):
            self.next_stage()
        return self.stages

    def state(self) -> dict:
        return scenario_state(self.spec, self.stages, self.stages_run - 1)

    @property
    def audit_path(self) -> Optional[Path]:
        return self.trail.path if self.trail else None


def scenario_state(spec: ScenarioSpec, stages: list[dict], index: int) -> dict:
    """
    What the system knows at stage `index` (live or replayed):
    current scenario and stage, activated agents, previous and current
    findings, evidence retrieved, verification result, cross-domain
    relationships and policy-gap findings.
    """
    if index < 0 or not stages:
        return {"scenario_id": spec.scenario_id, "scenario_title": spec.title,
                "stages_total": len(spec.stages), "current_stage": None}
    current = stages[index]
    coordinator = current["coordinator"]
    return {
        "scenario_id": spec.scenario_id,
        "scenario_title": spec.title,
        "stages_total": len(spec.stages),
        "current_stage": current["stage"],
        "activated_agents": current["orchestrator"]["active_agents"],
        "newly_activated": current["orchestrator"]["newly_activated"],
        "matches_docx_table": current["orchestrator"]["matches_docx_table"],
        "previous_findings": [
            {"stage": s["stage"]["label"], "agent_id": a["agent_id"],
             "summary": a["decision_summary"],
             "claims": [(c["claim"], c["verifier_outcome"]) for c in a["claims"]]}
            for s in stages[:index] for a in s["agents"]
        ],
        "current_findings": current["agents"],
        "evidence_retrieved": [
            {"agent_id": a["agent_id"], **p}
            for a in current["agents"] for p in a["retrieved_passages"]
        ],
        "verification": current["verifier"],
        "cross_domain_relationships": coordinator["cross_domain_relationships"],
        "policy_gap_findings": coordinator["potential_policy_gaps"],
        "coordinator": coordinator,
    }
