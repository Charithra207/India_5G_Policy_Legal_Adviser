"""
Full 4-stage demo and integration tests.

Covers:
  - Complete Scenario 2 run (T0 → T3)
  - Correct agent activation at each stage (matches DOCX table)
  - Audit trail written, chain intact, replayable
  - Replay: chunk sequence rebuilt from audit trail matches original
  - Replay: re-execution reproduces same agent sets and coordinator categories
  - ScenarioEngine state() returns full structured state
  - UI rendering (output_formatter and audit trail entry structure)
  - Integration checklist: all seven agents, KB registry, Verifier, Coordinator,
    Orchestrator, Pipeline, ScenarioEngine, AuditTrail, Replay

Run with:
    python -m pytest tests/test_demo_integration.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.core.models import AgentID, VerifierOutcome
from src.pipeline import Pipeline
from src.utils.output_formatter import format_audit_record, save_audit_json
from scenarios.scenario2_healthcare_5g import get_chunk, get_chunks


# ---------------------------------------------------------------------------
# Expected DOCX stage table for Scenario 2 (§2.5)
# ---------------------------------------------------------------------------

DOCX_STAGE_TABLE = {
    0: {AgentID.TECHNICAL},
    1: {AgentID.TECHNICAL, AgentID.CYBERSECURITY, AgentID.STANDARDS},
    2: {AgentID.CRITICAL_INFRA, AgentID.PRIVACY, AgentID.POLICY_LEGAL},
    3: {AgentID.POLICY_LEGAL, AgentID.CYBERSECURITY, AgentID.PRIVACY,
        AgentID.CRITICAL_INFRA, AgentID.POLICY_GAP},
}


# ===========================================================================
# TASK 1 — FULL 4-STAGE DEMO (Scenario 2 end-to-end)
# ===========================================================================

class TestFullFourStageDemo:
    """Complete Scenario 2 (DOCX §2.5) run through stub pipeline."""

    def test_all_four_stages_run_without_error(self):
        pipeline = Pipeline()
        for i, chunk in enumerate(get_chunks()):
            record = pipeline.run_chunk(chunk)
            assert record, f"Stage T{i} must produce an AuditRecord"
            assert record.chunk_id == f"scenario2_T{i}"

    def test_agent_sets_match_docx_table_exactly(self):
        pipeline = Pipeline()
        for i, chunk in enumerate(get_chunks()):
            record = pipeline.run_chunk(chunk)
            actual = set(record.active_agents)
            expected = DOCX_STAGE_TABLE[i]
            extra = actual - expected
            missing = expected - actual
            assert not extra and not missing, (
                f"T{i} agent mismatch.\n"
                f"  Expected: {sorted(a.value for a in expected)}\n"
                f"  Actual:   {sorted(a.value for a in actual)}\n"
                f"  Extra:    {sorted(a.value for a in extra)}\n"
                f"  Missing:  {sorted(a.value for a in missing)}"
            )

    def test_t0_describes_latency_and_session_drops(self):
        pipeline = Pipeline()
        record = pipeline.run_chunk(get_chunk(0))
        chunk_text = record.raw_chunk.description.lower()
        assert "latency" in chunk_text or "session" in chunk_text, (
            "T0 scenario description must mention latency or session drops"
        )

    def test_t1_describes_authentication_signalling(self):
        record_desc = get_chunk(1).description.lower()
        assert "authentication" in record_desc or "signalling" in record_desc, (
            "T1 scenario description must mention authentication or signalling"
        )

    def test_t2_describes_healthcare_and_patient_data(self):
        desc = get_chunk(2).description.lower()
        assert "healthcare" in desc or "patient" in desc or "identifiable" in desc, (
            "T2 scenario description must mention healthcare or patient data"
        )

    def test_t3_describes_reporting_and_policy_gap(self):
        desc = get_chunk(3).description.lower()
        assert "report" in desc or "policy gap" in desc or "escalat" in desc, (
            "T3 scenario description must mention reporting or policy gap"
        )

    def test_no_false_verified_on_stub_kbs(self):
        pipeline = Pipeline()
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            for vc in record.verifier_result.verified_claims:
                assert vc.outcome != VerifierOutcome.VERIFIED, (
                    f"No claim may be VERIFIED on stub KBs:\n"
                    f"  {vc.agent_id.value}: {vc.claim[:80]}"
                )

    def test_t3_has_all_required_agent_finding_types(self):
        pipeline = Pipeline()
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
        t3 = record
        agent_ids = {f.agent_id for f in t3.agent_findings}
        assert AgentID.POLICY_LEGAL in agent_ids
        assert AgentID.CYBERSECURITY in agent_ids
        assert AgentID.PRIVACY in agent_ids
        assert AgentID.CRITICAL_INFRA in agent_ids
        assert AgentID.POLICY_GAP in agent_ids

    def test_five_coordinator_categories_always_present(self):
        pipeline = Pipeline()
        for i, chunk in enumerate(get_chunks()):
            record = pipeline.run_chunk(chunk)
            ca = record.coordinator_assessment
            assert hasattr(ca, "confirmed_facts"), f"T{i}: missing confirmed_facts"
            assert hasattr(ca, "evidence_backed_conclusions"), f"T{i}: missing evidence_backed"
            assert hasattr(ca, "uncertain_conclusions"), f"T{i}: missing uncertain"
            assert hasattr(ca, "conflicting_findings"), f"T{i}: missing conflicting"
            assert hasattr(ca, "potential_policy_gaps"), f"T{i}: missing policy_gaps"

    def test_human_review_note_present_all_stages(self):
        pipeline = Pipeline()
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            assert record.coordinator_assessment.human_review_required

    def test_no_fake_citations_all_stages(self):
        forbidden = ["[FABRICATED]", "[FAKE]", "invented_source", "made_up_law"]
        pipeline = Pipeline()
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            text = " ".join(c for f in record.agent_findings for c in f.claims)
            for bad in forbidden:
                assert bad not in text, f"Forbidden fabricated text: {bad!r}"


# ===========================================================================
# TASK 5 — AUDIT / REPLAY
# ===========================================================================

class TestAuditAndReplay:
    """Complete 4-stage scenario audit trail + replay functionality."""

    def _run_engine(self, tmp_dir: str):
        from src.scenario.engine import ScenarioEngine
        engine = ScenarioEngine(
            "scenario2",
            audit_dir=Path(tmp_dir),
            record=True,
        )
        stages = []
        for _ in range(4):
            stages.append(engine.next_stage())
        return engine, stages

    def test_audit_trail_file_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            assert engine.audit_path
            assert engine.audit_path.exists()
            assert engine.audit_path.suffix == ".jsonl"

    def test_audit_trail_has_run_started_and_run_completed(self):
        from src.audit.trail import read_entries
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            entries = read_entries(engine.audit_path)
        types = [e["type"] for e in entries]
        assert "run_started" in types
        assert "run_completed" in types
        assert types.count("stage") == 4

    def test_audit_trail_hash_chain_intact(self):
        from src.audit.replay import load_run
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            run = load_run(engine.audit_path)
        assert run.intact, f"Integrity problems: {run.integrity_problems}"

    def test_audit_trail_four_stages_recorded(self):
        from src.audit.replay import load_run
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            run = load_run(engine.audit_path)
        assert len(run.stages) == 4

    def test_audit_stage_entries_have_required_fields(self):
        """Every stage entry must carry the §7.6 audit fields."""
        required_stage_fields = {
            "stage", "orchestrator", "agents", "verifier", "coordinator",
        }
        required_agent_fields = {
            "agent_id", "decision_summary", "claims", "retrieved_passages",
            "uncertainty_notes", "missing_facts", "queries",
        }
        with tempfile.TemporaryDirectory() as tmp:
            engine, stages = self._run_engine(tmp)
        for i, entry in enumerate(stages):
            missing_stage = required_stage_fields - set(entry.keys())
            assert not missing_stage, f"T{i} stage entry missing fields: {missing_stage}"
            for agent in entry["agents"]:
                missing_agent = required_agent_fields - set(agent.keys())
                assert not missing_agent, (
                    f"T{i} agent {agent.get('agent_id')} missing fields: {missing_agent}"
                )

    def test_audit_stage_entry_records_agent_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine, stages = self._run_engine(tmp)
        for i, (entry, expected) in enumerate(zip(stages, DOCX_STAGE_TABLE.values())):
            recorded_agents = {a["agent_id"] for a in entry["agents"]}
            expected_values = {a.value for a in expected}
            assert recorded_agents == expected_values, (
                f"T{i}: recorded agent IDs {recorded_agents} != expected {expected_values}"
            )

    def test_replay_chunks_match_scenario(self):
        """Chunks rebuilt from the audit trail must match the original scenario."""
        from src.audit.replay import load_run
        original = get_chunks()
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            run = load_run(engine.audit_path)
        replayed = run.chunks()
        assert len(replayed) == 4
        for orig, rep in zip(original, replayed):
            assert orig.chunk_id == rep.chunk_id
            assert orig.chunk_index == rep.chunk_index
            assert orig.description == rep.description

    def test_replay_load_run_returns_correct_scenario_id(self):
        from src.audit.replay import load_run
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            run = load_run(engine.audit_path)
        assert run.header["scenario_id"] == "scenario2"

    def test_replay_reexecute_matches_original(self):
        """Re-executing the recorded chunks must reproduce the same agent sets."""
        from src.audit.replay import load_run, reexecute
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            run = load_run(engine.audit_path)
        # Re-execute with stub KBs (same as original run)
        diffs = reexecute(run, registry=None)
        # Only agent sets, not passages (passages are empty on stub KBs), should match
        agent_diffs = [d for d in diffs if "active agents" in d.lower()]
        assert not agent_diffs, (
            f"Re-execution produced agent-set differences:\n"
            + "\n".join(agent_diffs)
        )

    def test_tampering_detected(self):
        """Modifying a stage entry breaks the hash chain."""
        from src.audit.trail import read_entries, verify_chain
        with tempfile.TemporaryDirectory() as tmp:
            engine, _ = self._run_engine(tmp)
            # Read while temp dir is still alive
            content = engine.audit_path.read_text(encoding="utf-8")

        lines = content.splitlines()
        entries = [json.loads(line) for line in lines]
        stage_indices = [i for i, e in enumerate(entries) if e.get("type") == "stage"]
        assert stage_indices, "Must have at least one stage entry to tamper with"
        entries[stage_indices[0]]["stage"]["information_released"] = "TAMPERED DATA"
        problems = verify_chain(entries)
        assert problems, "Tampering must be detected by verify_chain"

    def test_scenario_engine_state_contains_full_structure(self):
        """ScenarioEngine.state() must return structured state for the UI."""
        from src.scenario.engine import ScenarioEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=False)
            engine.next_stage()
            state = engine.state()
        required_keys = {
            "scenario_id", "scenario_title", "stages_total",
            "current_stage", "activated_agents",
        }
        for key in required_keys:
            assert key in state, f"ScenarioEngine.state() missing key: {key}"
        assert state["scenario_id"] == "scenario2"
        assert state["stages_total"] == 4

    def test_audit_trail_not_overwritten_on_second_run(self):
        """Each run must create a new file; existing runs are never overwritten."""
        import time
        from src.scenario.engine import ScenarioEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine1 = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine1.next_stage()
            time.sleep(1.1)  # ensure timestamp differs by at least 1 second
            engine2 = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine2.next_stage()
            files = list(Path(tmp).glob("*.jsonl"))
        assert len(files) == 2, (
            f"Each run must create a separate file; found {len(files)}"
        )

    def test_list_runs_returns_newest_first(self):
        import time
        from src.audit.replay import list_runs
        from src.scenario.engine import ScenarioEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine1 = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine1.next_stage()
            time.sleep(1.1)
            engine2 = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine2.next_stage()
            # list_runs while tempdir still exists
            runs = list_runs(Path(tmp))
            assert len(runs) >= 2
            assert runs[0].stat().st_mtime >= runs[1].stat().st_mtime


# ===========================================================================
# TASK 2 — UI: output_formatter produces all required sections
# ===========================================================================

class TestUIOutputStructure:
    """UI must display all required information sections."""

    def _full_record(self):
        pipeline = Pipeline()
        record = None
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
        return record

    def test_formatted_output_contains_scenario_chunk_info(self):
        record = Pipeline().run_chunk(get_chunk(0))
        text = format_audit_record(record)
        assert "SCENARIO INFORMATION" in text
        assert record.raw_chunk.description in text

    def test_formatted_output_contains_active_agents(self):
        record = Pipeline().run_chunk(get_chunk(0))
        text = format_audit_record(record)
        assert "Active Agents" in text
        assert "technical" in text.lower()

    def test_formatted_output_contains_all_coordinator_categories(self):
        record = Pipeline().run_chunk(get_chunk(0))
        text = format_audit_record(record)
        for section in [
            "1. CONFIRMED FACTS",
            "2. EVIDENCE-BACKED CONCLUSIONS",
            "3. UNCERTAIN CONCLUSIONS",
            "4. CONFLICTING FINDINGS",
            "5. POTENTIAL POLICY GAPS",
        ]:
            assert section in text

    def test_formatted_output_contains_verification_summary(self):
        record = Pipeline().run_chunk(get_chunk(0))
        text = format_audit_record(record)
        assert "VERIFICATION SUMMARY" in text
        assert "VERIFIED" in text
        assert "INCOMPLETE" in text
        assert "UNSUPPORTED" in text

    def test_formatted_output_contains_human_review_notice(self):
        record = Pipeline().run_chunk(get_chunk(0))
        text = format_audit_record(record)
        assert "HUMAN REVIEW NOTICE" in text

    def test_formatted_output_with_raw_findings_shows_agent_claims(self):
        record = Pipeline().run_chunk(get_chunk(0))
        text = format_audit_record(record, include_raw_findings=True)
        assert "RAW AGENT FINDINGS" in text
        assert "TECHNICAL" in text

    def test_audit_json_contains_verified_claims_list(self):
        record = Pipeline().run_chunk(get_chunk(0))
        with tempfile.TemporaryDirectory() as tmp:
            path = save_audit_json(record, output_dir=tmp)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        assert "verified_claims" in data
        assert "agent_findings" in data
        assert "coordinator_assessment" in data
        assert "verifier_summary" in data

    def test_audit_stage_entry_has_docx_expected_change(self):
        """The stage entry must record the DOCX-expected assessment change for the UI."""
        from src.scenario.engine import ScenarioEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=False)
            entry = engine.next_stage()
        assert entry["stage"]["docx_expected_change"], (
            "Stage entry must include docx_expected_change from the DOCX stage table"
        )

    def test_stage_entry_has_retrieval_metadata_for_ui(self):
        """Every retrieved passage must carry source_title, section, and url."""
        from src.knowledge_base.in_memory_kb import InMemoryKnowledgeBase
        from src.core.models import EvidenceItem
        from src.knowledge_base.kb_registry import KBRegistry
        from src.scenario.engine import ScenarioEngine

        ev = EvidenceItem(
            source_title="FIXTURE 5G Spec", authority="Test", jurisdiction="International",
            document_type="Fixture", section="Clause 5.15",
            excerpt="A network slice provides network capabilities.",
            chunk_id="fx-clause-5-15", url="https://example.com",
        )
        registry = KBRegistry()
        registry.agent_kbs[AgentID.TECHNICAL] = InMemoryKnowledgeBase(
            "tech fixture", "technical", [ev]
        )
        with tempfile.TemporaryDirectory() as tmp:
            engine = ScenarioEngine("scenario2", registry=registry,
                                    audit_dir=Path(tmp), record=False)
            entry = engine.next_stage()
        tech_agent = next(a for a in entry["agents"] if a["agent_id"] == "technical")
        real_passages = [p for p in tech_agent["retrieved_passages"] if not p["is_stub"]]
        for passage in real_passages:
            assert passage["source_title"], "Passage must have source_title"
            assert passage["section"], "Passage must have section"


# ===========================================================================
# TASK 7 — INTEGRATION CHECKLIST
# ===========================================================================

class TestIntegrationChecklist:
    """
    Verifies that all components are wired together correctly.
    This is the integration checklist for the complete system.
    """

    def test_pipeline_wires_all_components(self):
        """Pipeline must create Verifier, Coordinator, and Orchestrator."""
        pipeline = Pipeline()
        assert pipeline.verifier is not None
        assert pipeline.coordinator is not None
        assert pipeline.orchestrator is not None
        assert pipeline.registry is not None

    def test_kb_registry_has_all_seven_agents(self):
        from src.knowledge_base.kb_registry import KBRegistry
        registry = KBRegistry()
        assert set(registry.agent_kbs.keys()) == set(AgentID)

    def test_orchestrator_exposes_all_seven_agent_classes(self):
        """The Orchestrator must be able to retrieve every agent by ID."""
        pipeline = Pipeline()
        for agent_id in AgentID:
            agent = pipeline.orchestrator.get_agent(agent_id)
            assert agent is not None, f"Orchestrator must have agent for {agent_id.value}"
            assert agent.agent_id == agent_id

    def test_verifier_uses_canonical_kb_from_registry(self):
        """Verifier must be initialised with the canonical KB from the registry."""
        pipeline = Pipeline()
        assert pipeline.verifier.canonical_kb is pipeline.registry.canonical_kb

    def test_all_seven_agents_produce_findings_across_scenario(self):
        """Every agent must produce at least one finding across the full scenario."""
        pipeline = Pipeline()
        found_agents = set()
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            found_agents.update(record.active_agents)
        assert found_agents == set(AgentID), (
            f"Missing agents: {set(AgentID) - found_agents}"
        )

    def test_scenario_engine_integrates_pipeline_and_audit(self):
        """ScenarioEngine must run all four stages and write a valid audit trail."""
        from src.audit.replay import load_run
        from src.scenario.engine import ScenarioEngine
        with tempfile.TemporaryDirectory() as tmp:
            engine = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine.next_stage()
            run = load_run(engine.audit_path)
        assert run.intact
        assert len(run.stages) == 4

    def test_both_scenarios_run_correctly(self):
        """Scenario 1 and Scenario 2 must both complete without error."""
        from src.scenario.catalog import SCENARIOS
        for scenario_id in SCENARIOS:
            pipeline = Pipeline()
            spec = SCENARIOS[scenario_id]
            chunks = spec.load_chunks()
            for chunk in chunks:
                record = pipeline.run_chunk(chunk)
                assert record

    def test_pipeline_incident_state_accumulates_correctly(self):
        """Incident state flags must accumulate from T0 → T3."""
        pipeline = Pipeline()
        assert not pipeline.incident_state.get("cyber_event_suspected")
        pipeline.run_chunk(get_chunk(0))
        assert not pipeline.incident_state.get("cyber_event_suspected")
        pipeline.run_chunk(get_chunk(1))
        assert pipeline.incident_state.get("cyber_event_suspected") is True
        pipeline.run_chunk(get_chunk(2))
        assert pipeline.incident_state.get("cii_flagged") is True
        assert pipeline.incident_state.get("data_exposure_suspected") is True
        pipeline.run_chunk(get_chunk(3))
        assert pipeline.incident_state.get("verified_findings")

    def test_output_formatter_produces_valid_text_for_all_stages(self):
        """format_audit_record must not raise for any stage."""
        pipeline = Pipeline()
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            text = format_audit_record(record, include_raw_findings=True)
            assert text and len(text) > 100

    def test_save_audit_json_produces_valid_json_for_all_stages(self):
        """save_audit_json must produce parseable JSON for every stage."""
        pipeline = Pipeline()
        with tempfile.TemporaryDirectory() as tmp:
            for chunk in get_chunks():
                record = pipeline.run_chunk(chunk)
                path = save_audit_json(record, output_dir=tmp)
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                assert data["chunk_id"] == record.chunk_id

    def test_kb_registry_status_report_all_false_on_stub(self):
        """Default stub registry must report all KBs as unavailable."""
        from src.knowledge_base.kb_registry import KBRegistry
        registry = KBRegistry()
        status = registry.status_report()
        assert all(not v for v in status.values()), (
            "Default stub registry must report all KBs as unavailable"
        )

    def test_full_pipeline_run_scenario_method(self):
        """Pipeline.run_scenario() must process all chunks and return AuditRecords."""
        pipeline = Pipeline()
        records = pipeline.run_scenario(get_chunks())
        assert len(records) == 4
        for i, record in enumerate(records):
            assert record.chunk_id == f"scenario2_T{i}"
