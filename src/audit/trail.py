"""
Audit trail (DOCX §7.6)
=======================
One JSON Lines file per scenario run, written append-only:

    {"type": "run_started", ...}      run header: scenario, KB status, build
    {"type": "stage", ...}            one per released chunk
    {"type": "run_completed", ...}    written when every stage has run

Each stage entry holds the §7.6 fields — timestamp, scenario chunk ID, agent
ID, the inputs visible to that agent, the retrieved passages with document
and section identifiers, the agent's decision summary, its citations, the
verifier outcome per claim, cross-domain flags and the Coordinator decision —
taken from the pipeline's own AuditRecord.  Nothing is computed here that the
pipeline did not produce, apart from counts and the comparison with the DOCX
stage table.

Append-only: the file is only ever opened in append mode, and every entry
carries `prev_hash` and `hash` (SHA-256 over the entry), so an edited,
removed or reordered entry is detected by `verify_chain`.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from src.core.models import AgentFinding, AuditRecord, EvidenceItem, VerifiedClaim

SCHEMA_VERSION = "1.0"
GENESIS_HASH   = "0" * 64
PROJECT_ROOT   = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_DIR = PROJECT_ROOT / "outputs" / "audit"


def audit_dir() -> Path:
    """Where runs are recorded; ADVISER_AUDIT_DIR overrides (used by tests)."""
    return Path(os.environ.get("ADVISER_AUDIT_DIR", DEFAULT_AUDIT_DIR))

# AgentFinding fields that only some mandates fill (DOCX §3.7)
_MANDATE_FIELDS = (
    "incident_class", "affected_components", "applicable_provisions",
    "responsible_institutions", "obligations", "exposure_status",
    "cii_relevant", "standards_compared", "gap_category", "gap_description",
)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def _plain(value):
    """dataclasses / enums → JSON-ready values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(_plain(k)): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_plain(v) for v in value]
    return value


def entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_chain(entries: list[dict]) -> list[str]:
    """Return integrity problems; an empty list means the chain is intact."""
    problems: list[str] = []
    prev = GENESIS_HASH
    for i, entry in enumerate(entries, 1):
        if entry.get("prev_hash") != prev:
            problems.append(f"entry {i} ({entry.get('type')}): prev_hash does not "
                            "match the previous entry — an entry was removed, "
                            "inserted or reordered")
        if entry.get("hash") != entry_hash(entry):
            problems.append(f"entry {i} ({entry.get('type')}): content does not "
                            "match its hash — the entry was edited")
        prev = entry.get("hash", "")
    return problems


# ---------------------------------------------------------------------------
# Record → stage entry
# ---------------------------------------------------------------------------

def passage(e: EvidenceItem) -> dict:
    """A retrieved passage with every identifier the reader needs."""
    return {
        "source_title": e.source_title, "authority": e.authority,
        "jurisdiction": e.jurisdiction, "document_type": e.document_type,
        "section": e.section, "section_title": e.section_title, "page": e.page,
        "excerpt": e.excerpt, "date_issued": e.date_issued,
        "effective": e.effective, "amendment_checked": e.amendment_checked,
        "amendment_note": e.amendment_note, "url": e.url,
        "provenance_note": e.provenance_note, "chunk_id": e.chunk_id,
        "relevance_score": round(e.relevance_score, 4),
        "is_stub": e.authority == "STUB" or e.chunk_id == "stub-000",
    }


def _citation(e: EvidenceItem) -> dict:
    return {"source_title": e.source_title, "section": e.section,
            "page": e.page, "chunk_id": e.chunk_id}


def _claim_entry(claim: str, finding: AgentFinding,
                 verdict: Optional[VerifiedClaim]) -> dict:
    return {
        "claim": claim,
        "citations": [_citation(e) for e in finding.claim_citations.get(claim, [])],
        "verifier_outcome": verdict.outcome.value if verdict else None,
        "verifier_rationale": verdict.rationale if verdict else
                              "No verifier result was recorded for this claim.",
        "verifier_supporting": [_citation(e) for e in verdict.supporting_evidence]
                               if verdict else [],
        "verifier_conflicting": [_citation(e) for e in verdict.conflicting_evidence]
                                if verdict else [],
        "cross_domain_flag": bool(verdict and verdict.cross_domain_flag),
        "cross_domain_note": verdict.cross_domain_note if verdict else "",
    }


def _agent_entry(record: AuditRecord, finding: AgentFinding) -> dict:
    chunk = record.raw_chunk
    verdicts = {vc.claim: vc for vc in record.verifier_result.verified_claims
                if vc.agent_id == finding.agent_id}
    inputs = record.agent_inputs.get(finding.agent_id.value, {})
    mandate = {f: _plain(getattr(finding, f)) for f in _MANDATE_FIELDS
               if getattr(finding, f) not in (None, "", [])}
    return {
        "agent_id": finding.agent_id.value,
        "visible_input": {
            "chunk_id": chunk.chunk_id,
            "information_released": chunk.description,
            "new_facts": list(chunk.new_facts),
            "prior_chunk_ids": list(chunk.prior_chunks),
            "incident_state": inputs.get("incident_state"),
        },
        "queries": inputs.get("queries", []),
        "retrieved_passages": [passage(e) for e in finding.evidence],
        "decision_summary": finding.summary,
        "mandate_output": mandate,
        "claims": [_claim_entry(c, finding, verdicts.get(c)) for c in finding.claims],
        "uncertainty_notes": list(finding.uncertainty_notes),
        "missing_facts": list(finding.missing_facts),
    }


def stage_entry(record: AuditRecord, scenario_id: str, stage_spec,
                previous_agents: list[str]) -> dict:
    """Build the §7.6 stage entry for one pipeline AuditRecord."""
    chunk = record.raw_chunk
    active = [a.value for a in record.active_agents]
    expected = [a.value for a in stage_spec.primary_agents] if stage_spec else []
    outcomes: dict[str, int] = {}
    for vc in record.verifier_result.verified_claims:
        outcomes[vc.outcome.value] = outcomes.get(vc.outcome.value, 0) + 1

    return {
        "type": "stage",
        "scenario_id": scenario_id,
        "pipeline_timestamp": record.timestamp,
        "stage": {
            "index": chunk.chunk_index,
            "label": stage_spec.label if stage_spec else str(chunk.chunk_index),
            "chunk_id": chunk.chunk_id,
            "scenario_time": chunk.timestamp,
            "information_released": chunk.description,
            "new_facts": list(chunk.new_facts),
            "prior_chunks": list(chunk.prior_chunks),
            "docx_information_released": stage_spec.information_released if stage_spec else "",
            "docx_expected_change": stage_spec.expected_change if stage_spec else "",
        },
        "orchestrator": {
            "active_agents": active,
            "newly_activated": [a for a in active if a not in previous_agents],
            "no_longer_active": [a for a in previous_agents if a not in active],
            "docx_primary_agents": expected,
            "matches_docx_table": sorted(active) == sorted(expected) if expected else None,
        },
        "agents": [_agent_entry(record, f) for f in record.agent_findings],
        "verifier": {
            "outcome_counts": outcomes,
            "cross_domain_links": list(record.verifier_result.cross_domain_links),
            "conflicts": list(record.verifier_result.conflicts),
            "missing_evidence": list(record.verifier_result.missing_evidence),
        },
        "coordinator": _plain(asdict(record.coordinator_assessment)),
    }


# ---------------------------------------------------------------------------
# Run provenance
# ---------------------------------------------------------------------------

def _git_commit() -> dict:
    def git(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], cwd=PROJECT_ROOT, capture_output=True,
                                  text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    return {"commit": git("rev-parse", "HEAD"),
            "uncommitted_changes": bool(git("status", "--porcelain"))}


def _kb_build() -> dict:
    path = PROJECT_ROOT / "knowledge_base" / "ingestion_manifest.json"
    if not path.exists():
        return {"ingestion_manifest": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "ingestion_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "built_at": data.get("built_at"),
        "embedding_model": data.get("embedding_model"),
        "generator_model": data.get("generator_model"),
        "not_ingested": [d["id"] for d in data.get("documents", [])
                         if d.get("status") != "ingested"],
        "sandbox": data.get("sandbox"),
    }


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

class AuditTrail:
    """Append-only JSONL writer for one scenario run."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.entries: list[dict] = []

    @classmethod
    def start(cls, scenario, kb_status: dict[str, bool],
              directory: Optional[Path] = None,
              run_id: Optional[str] = None) -> "AuditTrail":
        now = datetime.now(timezone.utc)
        run_id = run_id or f"{scenario.scenario_id}_{now.strftime('%Y%m%dT%H%M%SZ')}"
        directory = Path(directory) if directory is not None else audit_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{run_id}.jsonl"
        if path.exists():
            raise FileExistsError(f"{path} exists; an audit trail is never overwritten")
        trail = cls(path)
        trail._append({
            "type": "run_started",
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "scenario_id": scenario.scenario_id,
            "scenario_title": scenario.title,
            "docx_section": scenario.docx_section,
            "stage_count": len(scenario.stages),
            "knowledge_bases_live": kb_status,
            "knowledge_base_build": _kb_build(),
            "code": _git_commit(),
        })
        return trail

    @property
    def run_id(self) -> str:
        return self.entries[0]["run_id"]

    def record_stage(self, record: AuditRecord, scenario_id: str, stage_spec,
                     previous_agents: list[str]) -> dict:
        return self._append(stage_entry(record, scenario_id, stage_spec, previous_agents))

    def complete(self) -> dict:
        stages = [e for e in self.entries if e["type"] == "stage"]
        return self._append({"type": "run_completed",
                             "stages_recorded": len(stages),
                             "final_chunk_id": stages[-1]["stage"]["chunk_id"] if stages else None})

    def _append(self, entry: dict) -> dict:
        entry = {"seq": len(self.entries) + 1, "run_id": self.entries[0]["run_id"]
                 if self.entries else entry["run_id"],
                 "recorded_at": datetime.now(timezone.utc).isoformat(), **entry}
        entry["prev_hash"] = self.entries[-1]["hash"] if self.entries else GENESIS_HASH
        entry["hash"] = entry_hash(entry)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.entries.append(entry)
        return entry


def read_entries(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
