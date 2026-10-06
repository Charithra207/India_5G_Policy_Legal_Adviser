"""
Scenario engine, audit trail, replay and UI tests (Member 3).

Stub-KB tests need nothing but the code.  The live test uses the built
knowledge bases and is skipped if they are absent.

Run with:
    python -m pytest tests/test_scenario_audit.py -v
"""

import json
import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)

from src.audit.replay import compare_stage, load_run, reexecute
from src.audit.trail import AuditTrail, read_entries, verify_chain
from src.scenario.catalog import SCENARIOS, get_scenario
from src.scenario.engine import ScenarioEngine


@pytest.fixture
def stub_run(tmp_path):
    engine = ScenarioEngine("scenario2", audit_dir=tmp_path)
    engine.run_until(4)
    return engine


# -----------------------------------------------------------------------
# Scenario engine
# -----------------------------------------------------------------------

@pytest.mark.parametrize("scenario_id", sorted(SCENARIOS))
def test_orchestrator_selection_matches_docx_stage_table(scenario_id, tmp_path) -> None:
    engine = ScenarioEngine(scenario_id, audit_dir=tmp_path)
    for stage, spec in zip(engine.run_until(4), engine.spec.stages):
        assert sorted(stage["orchestrator"]["active_agents"]) == \
            sorted(a.value for a in spec.primary_agents), stage["stage"]["label"]
        assert stage["orchestrator"]["matches_docx_table"] is True


def test_stage_one_then_two_updates_state(tmp_path) -> None:
    engine = ScenarioEngine("scenario2", audit_dir=tmp_path)
    engine.next_stage()
    t0 = engine.state()
    assert t0["current_stage"]["label"] == "T0"
    assert t0["activated_agents"] == ["technical"] and not t0["previous_findings"]
    engine.next_stage()
    t1 = engine.state()
    assert t1["current_stage"]["label"] == "T1"
    assert sorted(t1["newly_activated"]) == ["cybersecurity", "standards"]
    assert {f["stage"] for f in t1["previous_findings"]} == {"T0"}
    assert t1["coordinator"]["changes_from_prior"]


def test_engine_stops_after_last_stage(stub_run) -> None:
    assert not stub_run.has_next()
    with pytest.raises(RuntimeError):
        stub_run.next_stage()


def test_unknown_scenario_is_refused() -> None:
    with pytest.raises(ValueError):
        get_scenario("scenario9")


# -----------------------------------------------------------------------
# Audit trail (DOCX §7.6 fields, append-only)
# -----------------------------------------------------------------------

def test_stage_entry_has_docx_7_6_fields(stub_run) -> None:
    entries = read_entries(stub_run.audit_path)
    assert [e["type"] for e in entries] == ["run_started"] + ["stage"] * 4 + ["run_completed"]
    for stage in entries[1:5]:
        assert stage["recorded_at"] and stage["stage"]["chunk_id"] and stage["coordinator"]
        for agent in stage["agents"]:
            assert agent["agent_id"] and agent["decision_summary"]
            assert agent["visible_input"]["information_released"]
            assert agent["visible_input"]["incident_state"] is not None
            assert agent["queries"] and agent["retrieved_passages"]
            for claim in agent["claims"]:
                assert claim["verifier_outcome"] in {"VERIFIED", "INCOMPLETE",
                                                     "UNSUPPORTED", "CONFLICT"}
                assert "cross_domain_flag" in claim and "citations" in claim


def test_policy_gap_agent_sees_earlier_verified_findings(stub_run) -> None:
    t3 = stub_run.stages[3]
    gap = next(a for a in t3["agents"] if a["agent_id"] == "policy_gap")
    assert gap["visible_input"]["incident_state"]["verified_findings"]


def test_stub_run_never_verifies(stub_run) -> None:
    for stage in stub_run.stages:
        assert "VERIFIED" not in stage["verifier"]["outcome_counts"]


def test_edited_entry_is_detected(stub_run) -> None:
    lines = stub_run.audit_path.read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[2])
    entry["agents"][0]["claims"][0]["verifier_outcome"] = "VERIFIED"
    lines[2] = json.dumps(entry)
    entries = [json.loads(line) for line in lines]
    assert any("edited" in p for p in verify_chain(entries))


def test_removed_entry_is_detected(stub_run) -> None:
    entries = read_entries(stub_run.audit_path)
    assert verify_chain(entries) == []
    del entries[2]
    assert any("removed" in p for p in verify_chain(entries))


def test_audit_file_is_never_overwritten(tmp_path) -> None:
    ScenarioEngine("scenario2", audit_dir=tmp_path, run_id="fixed")
    with pytest.raises(FileExistsError):
        AuditTrail.start(get_scenario("scenario2"), {}, tmp_path, "fixed")


# -----------------------------------------------------------------------
# Replay
# -----------------------------------------------------------------------

def test_replay_loads_stages_in_order_and_reexecutes(stub_run) -> None:
    run = load_run(stub_run.audit_path)
    assert run.intact and run.completed
    assert [s["stage"]["label"] for s in run.stages] == ["T0", "T1", "T2", "T3"]
    assert [c.chunk_id for c in run.chunks()] == [c.chunk_id for c in stub_run.chunks]
    assert reexecute(run) == []


def test_replay_reports_a_changed_outcome(stub_run) -> None:
    run = load_run(stub_run.audit_path)
    altered = json.loads(json.dumps(run.stages[1]))
    altered["agents"][0]["claims"][0]["verifier_outcome"] = "VERIFIED"
    assert any("claims differ" in d for d in compare_stage(run.stages[1], altered))


# -----------------------------------------------------------------------
# UI — chunk 1 then chunk 2, on stub KBs
# -----------------------------------------------------------------------

def test_ui_updates_between_chunk_one_and_two(tmp_path, monkeypatch) -> None:
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("ADVISER_AUDIT_DIR", str(tmp_path))
    app = os.path.join(os.path.dirname(__file__), "..", "src", "ui", "app.py")
    at = AppTest.from_file(app, default_timeout=120).run()
    at.sidebar.toggle[0].set_value(False).run()          # stub KBs: fast

    def click(label):
        next(b for b in at.sidebar.button if b.label.startswith(label)).click().run()
        assert not at.exception

    click("Start run")
    click("Release next chunk")
    headers = [h.value for h in at.header]
    assert "Current chunk — T0" in headers and "Previous findings" not in headers
    click("Release next chunk")
    headers = [h.value for h in at.header]
    assert "Current chunk — T1" in headers and "Previous findings" in headers
    assert any("Cybersecurity** · NEW" in m.value for m in at.markdown)
    assert any("What changed" in i.value for i in at.info)
    assert len(list(tmp_path.glob("*.jsonl"))) == 1

    at.sidebar.radio[0].set_value("Replay").run()
    assert not at.exception
    assert any("Hash chain intact" in s.value for s in at.sidebar.success)


# -----------------------------------------------------------------------
# Live knowledge bases
# -----------------------------------------------------------------------

def _built() -> bool:
    from src.rag.manifest import ALL_KBS, KB_ROOT
    from src.rag.vector_store import VectorStore
    return all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS)


@pytest.mark.skipif(not _built(), reason="knowledge bases not built")
def test_live_chunk_two_records_retrieved_provisions(tmp_path) -> None:
    from src.rag.registry import build_registry
    engine = ScenarioEngine("scenario2", registry=build_registry(), audit_dir=tmp_path)
    engine.run_until(2)
    cyber = next(a for a in engine.stages[1]["agents"] if a["agent_id"] == "cybersecurity")
    sections = {(p["source_title"], p["section"]) for p in cyber["retrieved_passages"]}
    assert ("Telecommunications (Telecom Cyber Security) Rules, 2024", "Rule 7") in sections
    assert all(not p["is_stub"] and p["url"] for p in cyber["retrieved_passages"])
    assert all(c["verifier_outcome"] != "VERIFIED" for c in cyber["claims"])
    assert load_run(engine.audit_path).intact
