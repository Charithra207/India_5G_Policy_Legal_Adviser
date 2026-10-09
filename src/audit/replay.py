"""
Replay (DOCX §7.6)
==================
"A judge can replay a scenario by loading the chunk sequence and matching
each record to retrieved evidence and the final assessment."

Two forms:

* `load_run(path)` — read a recorded run, check its hash chain, and step
  through the recorded stages in order (the UI's Replay mode shows each
  stage exactly as it was recorded: chunk → agents → evidence → verifier →
  Coordinator).
* `reexecute(run, registry)` — load the chunk sequence FROM THE RECORD, run it
  through a fresh pipeline, and compare each stage with what was recorded:
  activated agents, retrieved passages (chunk IDs), claims and verifier
  outcomes, and the Coordinator's five categories.  Differences mean the
  code or the knowledge bases changed since the recording; the run header
  records the commit and the KB build to explain which.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.audit.trail import audit_dir, read_entries, stage_entry, verify_chain
from src.core.models import ScenarioChunk

COORDINATOR_CATEGORIES = (
    "confirmed_facts", "evidence_backed_conclusions", "uncertain_conclusions",
    "conflicting_findings", "potential_policy_gaps",
)


@dataclass
class ReplayRun:
    path      : Path
    header    : dict
    stages    : list[dict]
    completed : Optional[dict]
    integrity_problems : list[str] = field(default_factory=list)

    @property
    def intact(self) -> bool:
        return not self.integrity_problems

    def chunks(self) -> list[ScenarioChunk]:
        """The chunk sequence, rebuilt from the recorded stages."""
        return [ScenarioChunk(
            chunk_index  = s["stage"]["index"],
            chunk_id     = s["stage"]["chunk_id"],
            timestamp    = s["stage"]["scenario_time"],
            description  = s["stage"]["information_released"],
            new_facts    = list(s["stage"]["new_facts"]),
            prior_chunks = list(s["stage"]["prior_chunks"]),
            agent_views  = {k: list(v) for k, v in s["stage"].get("agent_views", {}).items()},
        ) for s in self.stages]


def list_runs(directory: Optional[Path] = None) -> list[Path]:
    """Recorded runs, newest first."""
    return sorted(Path(directory or audit_dir()).glob("*.jsonl"),
                  key=lambda p: p.stat().st_mtime, reverse=True)


def load_run(path: Path) -> ReplayRun:
    entries = read_entries(Path(path))
    if not entries or entries[0].get("type") != "run_started":
        raise ValueError(f"{path} is not an audit trail (no run_started header)")
    completed = [e for e in entries if e["type"] == "run_completed"]
    return ReplayRun(
        path      = Path(path),
        header    = entries[0],
        stages    = [e for e in entries if e["type"] == "stage"],
        completed = completed[-1] if completed else None,
        integrity_problems = verify_chain(entries),
    )


# ---------------------------------------------------------------------------
# Re-execution
# ---------------------------------------------------------------------------

def _fingerprint(stage: dict) -> dict:
    """What a re-run must reproduce for the record to match."""
    return {
        "active_agents": stage["orchestrator"]["active_agents"],
        "passages": {a["agent_id"]: [p["chunk_id"] for p in a["retrieved_passages"]]
                     for a in stage["agents"]},
        "claims": {a["agent_id"]: [(c["claim"], c["verifier_outcome"]) for c in a["claims"]]
                   for a in stage["agents"]},
        **{cat: stage["coordinator"][cat] for cat in COORDINATOR_CATEGORIES},
        "cross_domain_relationships": stage["coordinator"]["cross_domain_relationships"],
    }


def compare_stage(recorded: dict, rerun: dict) -> list[str]:
    a, b = _fingerprint(recorded), _fingerprint(rerun)
    label = recorded["stage"]["label"]
    diffs = []
    for key in a:
        if a[key] != b[key]:
            diffs.append(f"{label}: {key.replace('_', ' ')} differ "
                         f"(recorded {_short(a[key])}; re-run {_short(b[key])})")
    return diffs


def _short(value) -> str:
    if isinstance(value, dict):
        return "{" + ", ".join(f"{k}: {len(v)}" for k, v in value.items()) + "}"
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    return str(value)


def reexecute(run: ReplayRun, registry=None) -> list[str]:
    """
    Re-run the recorded chunk sequence through a fresh pipeline and return
    the differences from the record (empty list = reproduced exactly).
    """
    from src.pipeline import Pipeline
    from src.scenario.catalog import SCENARIOS

    from src import llm
    spec = SCENARIOS.get(run.header["scenario_id"])
    pipeline = Pipeline(registry)
    diffs: list[str] = []
    previous: list[str] = []
    # A run recorded without a model is re-executed without one, whatever is
    # configured now, so the comparison stays exact.  A run recorded with a
    # model cannot be reproduced exactly: its LLM-assisted claims may differ.
    recorded_llm = (run.header.get("llm") or {}).get("provider", "offline")
    configured = llm.active()
    if recorded_llm == "offline":
        llm.configure("offline")
    else:
        diffs.append(f"note: recorded with LLM {recorded_llm}; LLM-assisted claims are not "
                     "deterministic and may differ on re-execution")
    try:
        for recorded, chunk in zip(run.stages, run.chunks()):
            record = pipeline.run_chunk(chunk)
            stage_spec = spec.stages[chunk.chunk_index] if spec else None
            rerun = stage_entry(record, run.header["scenario_id"], stage_spec, previous)
            previous = rerun["orchestrator"]["active_agents"]
            diffs.extend(compare_stage(recorded, rerun))
    finally:
        llm.configure(provider=configured)
    return diffs
