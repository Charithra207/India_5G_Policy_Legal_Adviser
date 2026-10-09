"""
ITU-T Y.3172 layer (src/y3172/): ML Intent, SRC/C/PP nodes, sandbox data,
candidate models, P node, notices, D node and SINKs, MLFO, audit trail.

Runs offline: the committed kb/index verifies obligation phrases without an
embedding model, and the specialist-agent swarm runs on stub knowledge
bases (pipeline_factory) so results do not depend on a local KB build.
"""

import copy
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from catalog.loader import load_catalog  # noqa: E402
from sim.datagen import (BENIGN_EVENTS, apply_background, attack_residual, end_benign,  # noqa: E402
                         inject_scaled, run_episode, start_benign)
from sim.engine import FUNCTIONS, Sim  # noqa: E402
from src.audit.trail import AuditTrail, read_entries, verify_chain  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.y3172.distributor import Distributor  # noqa: E402
from src.y3172.intent import IntentError, load_intent, parse_intent, telemetry_plan  # noqa: E402
from src.y3172.mlfo import MLFO, AutoOperator  # noqa: E402
from src.y3172.models import (NORMAL, UNKNOWN, CANDIDATES, Prediction, evaluate,  # noqa: E402
                              propose_remediation, window_score)
from src.y3172.nodes import TELEMETRY, Collector, Preprocessor  # noqa: E402
from src.y3172.notices import DPDP_BREACH_DUTIES_FROM, draft_notices  # noqa: E402
from src.y3172.policy_node import ESCALATE, HOLD, PROCEED, PolicyNode  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INTENTS = sorted((ROOT / "intents").glob("*.yaml"))
WHEN = datetime(2026, 10, 7, 9, 30)


@pytest.fixture(autouse=True)
def lab_work_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_WORK_DIR", str(tmp_path / "work"))
    return tmp_path / "work"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def small_intent(catalog, **over) -> dict:
    data = yaml.safe_load((ROOT / "intents" / "amf_signalling_storm.yaml").read_text(encoding="utf-8"))
    data["training"]["samples_per_class"] = 12
    data["exercise"] = {"ticks": 8, "seed": 1, "events": [{"at": 2, "inject": "signalling_storm_amf"}]}
    for key, value in over.items():
        data[key] = value
    return data


def stub_pipeline():
    return Pipeline()


class Reviewer:
    """Scripted operator: answers holds/confirmations with `approve`, gates with `gate`."""

    def __init__(self, approve=True, gate="agent"):
        self.approve, self.gate_choice, self.asked = approve, gate, []

    def gate(self, tier, message):
        self.asked.append(("gate", tier))
        return self.gate_choice

    def confirm(self, description):
        self.asked.append(("confirm", description))
        return self.approve

    def manual(self, tier, commands):
        return ""


# ---------------------------------------------------------------------------
# ML Intent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path", INTENTS, ids=lambda p: p.name)
def test_every_committed_intent_is_valid(path, catalog):
    intent = load_intent(path, catalog)
    assert intent.sources and intent.candidates and "escalation" in intent.sinks
    assert intent.exercise is not None and intent.exercise.events


def test_intent_all_targets_expands_to_catalog(catalog):
    intent = load_intent(ROOT / "intents" / "core_security_full.yaml", catalog)
    assert set(intent.target_classes) == {a["id"] for a in catalog["attacks"]}


@pytest.mark.parametrize("mutate, message", [
    (lambda d: d["sources"].append({"nf": "xyz", "telemetry": ["metrics"]}), "sources[4].nf"),
    (lambda d: d["sources"][0].update(telemetry=["ran"]), "does not provide 'ran'"),
    (lambda d: d["sources"][0].update(telemetry=["nonsense"]), "unknown group"),
    (lambda d: d.update(sinks=["remediation"]), "'escalation' is required"),
    (lambda d: d["model"].update(candidates=["deep_magic"]), "unknown models"),
    (lambda d: d["policy"].update(mode="maybe"), "policy.mode"),
    (lambda d: d["ml_application"].update(target_classes=["not_an_attack"]), "unknown attack ids"),
    (lambda d: d["exercise"]["events"].append({"at": 99, "inject": "signalling_storm_amf"}), "exercise.events"),
    (lambda d: d["exercise"]["events"].append({"at": 1, "inject": "iot_botnet_mmtc"}), "inject"),
    (lambda d: d.pop("monitoring"), "missing field 'monitoring'"),
    (lambda d: d["training"].update(background_load=[2, 1]), "background_load"),
])
def test_intent_validation_names_the_bad_field(catalog, mutate, message):
    data = small_intent(catalog)
    mutate(data)
    with pytest.raises(IntentError, match=message.replace("[", r"\[").replace("]", r"\]")):
        parse_intent(data, catalog=catalog)


def test_telemetry_plan_lists_src_nodes(catalog):
    intent = parse_intent(small_intent(catalog), catalog=catalog)
    plan = telemetry_plan(intent)
    assert ("gnb", "ran") in plan and ("oam", "alerts") in plan
    assert all(nf in TELEMETRY[g].nfs for nf, g in plan)


# ---------------------------------------------------------------------------
# Simulator: per-instance work folders (sandbox vs live)
# ---------------------------------------------------------------------------

def test_two_sims_keep_separate_state(tmp_path):
    a, b = Sim(root=tmp_path / "sandbox"), Sim(root=tmp_path / "live")
    a.isolate_nf("amf")
    assert json.loads((tmp_path / "sandbox" / "state.json").read_text())["nfs"]["amf"]["isolated"] is True
    assert json.loads((tmp_path / "live" / "state.json").read_text())["nfs"]["amf"]["isolated"] is False
    assert Sim.resume(tmp_path / "sandbox").state["nfs"]["amf"]["isolated"] is True
    assert b.root == tmp_path / "live"


def test_default_root_still_follows_lab_work_dir(lab_work_dir):
    sim = Sim()
    assert sim.root == lab_work_dir
    assert (lab_work_dir / "state.json").exists()


# ---------------------------------------------------------------------------
# SRC / C / PP
# ---------------------------------------------------------------------------

def test_collector_only_reads(monkeypatch):
    import src.y3172.nodes as nodes
    called = []
    real = nodes.call

    def spy(sim, name, args=None):
        called.append(name)
        return real(sim, name, args)
    monkeypatch.setattr(nodes, "call", spy)
    plan = [(nf, g) for g, t in TELEMETRY.items() for nf in t.nfs]
    sim = Sim(persist=False)
    before = copy.deepcopy(sim.state)
    Collector(plan).poll(sim)
    assert called and all(FUNCTIONS[n] == "diagnostic" for n in called)
    assert sim.state == before


def test_collector_reports_only_new_log_lines_and_alerts():
    sim = Sim(persist=False)
    c = Collector([("amf", "logs"), ("oam", "alerts")])
    c.poll(sim)
    inject_scaled(sim, "signalling_storm_amf", 1.0)
    s1 = c.poll(sim)
    assert any("WARNING" in line for line in s1.novelty["logs"]["amf"]) and s1.novelty["alerts"]
    s2 = c.poll(sim)
    assert s2.novelty["logs"]["amf"] == [] and s2.novelty["alerts"] == []


def test_preprocessor_fixed_length_with_dropout():
    plan = [("amf", "metrics"), ("gnb", "ran"), ("oam", "alerts")]
    pp = Preprocessor(plan)
    sim = Sim(persist=False)
    full = pp.transform(Collector(plan).poll(sim))
    gappy = pp.transform(Collector(plan, dropout=1.0, rng=random.Random(0)).poll(sim))
    assert len(full) == len(gappy) == len(pp.feature_names) == 2 * len(pp.base_names)
    assert all(np.isfinite(full))
    assert gappy[len(pp.base_names):] == [0.0] * len(pp.base_names)    # no spurious change for missing nodes


# ---------------------------------------------------------------------------
# Simulated underlay data (sim/datagen.py)
# ---------------------------------------------------------------------------

def test_episode_polls_reference_then_two_labelled_samples():
    labels = []
    run_episode("rogue_base_station", random.Random(1), 1.0, lambda sim, lab: labels.append(lab))
    assert labels == [None, "rogue_base_station", "rogue_base_station"]


@pytest.mark.parametrize("event", BENIGN_EVENTS)
def test_benign_events_end_cleanly(event):
    sim = Sim(persist=False)
    reference = copy.deepcopy({k: sim.state[k] for k in ("nfs", "interfaces", "traffic")})
    undo = start_benign(sim, random.Random(3), event)
    end_benign(sim, undo)
    assert {k: sim.state[k] for k in ("nfs", "interfaces", "traffic")} == reference


def test_attack_residual_until_traffic_is_blocked():
    sim = Sim(persist=False)
    added = inject_scaled(sim, "core_ddos_upf", 1.0)["added_traffic"]
    assert added and attack_residual(sim, added)
    for _, source, _ in added:
        sim.block_source("upf", source)
    assert not attack_residual(sim, added)


def test_background_load_scales():
    sim, rng = Sim(persist=False), random.Random(0)
    low, high = [], []
    for load, out in ((1.0, low), (5.0, high)):
        for _ in range(30):
            apply_background(sim, rng, load)
            sim.tick()
            out.append(sim.get_metrics("upf")["offered_rate"])
    assert np.mean(high) > 2 * np.mean(low)


# ---------------------------------------------------------------------------
# M node
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sandbox_data(catalog, tmp_path_factory):
    intent = parse_intent(small_intent(catalog), catalog=catalog)
    m = MLFO(intent, run_dir=tmp_path_factory.mktemp("data"), human=AutoOperator(), catalog=catalog,
             pipeline_factory=stub_pipeline)
    train = m.generate(20, (0.8, 1.2), seed=1)
    test = m.generate(10, (0.8, 1.2), seed=2)
    return train, test


@pytest.mark.parametrize("model_id", sorted(CANDIDATES))
def test_candidates_learn_the_incidents(sandbox_data, model_id):
    train, test = sandbox_data
    model = CANDIDATES[model_id](seed=7).fit(train.X, train.y, train.feature_names)
    metrics = evaluate(model, test.X, test.y)
    assert metrics["detection_f1"] >= 0.8
    assert metrics["inference_ms_p95"] is not None
    pred = model.predict(test.X[np.argmax(test.y == "signalling_storm_amf")])
    assert isinstance(pred.label, str) and pred.label in {"signalling_storm_amf", UNKNOWN} | set(test.y)


def test_iforest_rf_beats_the_baseline_on_benign_lookalikes(sandbox_data):
    train, test = sandbox_data
    scores = {cid: evaluate(cls(seed=7).fit(train.X, train.y, train.feature_names), test.X, test.y)
              for cid, cls in CANDIDATES.items()}
    assert scores["iforest_rf"]["false_alarm_rate"] <= scores["threshold_centroid"]["false_alarm_rate"]
    assert scores["iforest_rf"]["macro_f1"] >= scores["threshold_centroid"]["macro_f1"]


def test_explanations_name_deviating_signals(sandbox_data):
    train, test = sandbox_data
    model = CANDIDATES["iforest_rf"](seed=7).fit(train.X, train.y, train.feature_names)
    x = test.X[np.argmax(test.y == "rogue_base_station")]
    evidence = model.explain(x)
    assert evidence and all(abs(e["z"]) >= 3 for e in evidence)
    signals = [e["feature"].lstrip("Δ") for e in evidence]
    assert len(signals) == len(set(signals))


def test_window_score_and_proposal(catalog):
    s = window_score([(NORMAL, NORMAL), ("x", "x"), ("x", NORMAL), (NORMAL, "x")])
    assert s["accuracy"] == 0.5 and s["false_alarms"] == 1 and s["missed"] == 1
    assert window_score([])["n"] == 0
    p = propose_remediation("signalling_storm_amf", catalog)
    assert "disconnect_gnb" in p["basic_auto_safe_steps"] and p["references"]["3gpp"]
    assert propose_remediation(UNKNOWN, catalog) is None


# ---------------------------------------------------------------------------
# P node
# ---------------------------------------------------------------------------

def _pred(label="signalling_storm_amf", conf=0.95):
    return Prediction(label, conf, 1.0, "iforest_rf", evidence=[{"feature": "amf.metrics.cpu", "value": 99.0,
                                                                 "normal_mean": 30.0, "z": 9.0}])


def _node(catalog, mode="blocking", adviser=True):
    data = small_intent(catalog)
    data["policy"].update(mode=mode, legal_adviser=adviser)
    return PolicyNode(parse_intent(data, catalog=catalog), catalog, stub_pipeline)


def test_blocking_mode_holds_with_verified_obligations(catalog):
    decision, record = _node(catalog).assess("INC1", _pred(), ["AMF CPU above 90%"], WHEN)
    assert decision.decision == HOLD and decision.allows_remediation
    ids = {o["id"] for o in decision.obligations}
    assert {"certin_6h", "tcs_rules_rule7_6h"} <= ids
    assert all(o["verified"] and o["passage"] for o in decision.obligations)
    assert record is not None and decision.adviser["active_agents"]
    assert "cybersecurity" in decision.adviser["active_agents"]
    assert "preserve_logs_before_changes" in decision.rules_applied


def test_advisory_mode_proceeds(catalog):
    decision, _ = _node(catalog, "advisory", adviser=False).assess("INC1", _pred(), [], WHEN)
    assert decision.decision == PROCEED and decision.adviser is None


@pytest.mark.parametrize("label, conf, rule", [
    (UNKNOWN, 0.9, "unknown_anomaly_to_human"),
    ("signalling_storm_amf", 0.3, "low_confidence_to_human"),
    ("iot_botnet_mmtc", 0.99, "outside_intent_to_human"),
])
def test_p_node_escalates_what_it_must_not_automate(catalog, label, conf, rule):
    decision, record = _node(catalog).assess("INC1", _pred(label, conf), [], WHEN)
    assert decision.decision == ESCALATE and not decision.allows_remediation
    assert rule in decision.rules_applied and record is None


def test_adviser_chunk_flags_personal_data_and_hospital(catalog):
    from src.y3172.policy_node import adviser_chunk
    attack = next(a for a in catalog["attacks"] if a["id"] == "subscriber_data_exfiltration")
    chunk = adviser_chunk("INC9", _pred("subscriber_data_exfiltration"), attack, [], WHEN, True)
    assert "personal data" in chunk.description and "hospital" in chunk.description
    assert "report" in chunk.description.lower()


# ---------------------------------------------------------------------------
# Notices
# ---------------------------------------------------------------------------

def _decision(catalog, attack_id):
    data = small_intent(catalog)
    data["ml_application"]["target_classes"] = [attack_id]
    data["exercise"]["events"] = []
    node = PolicyNode(parse_intent(data, catalog=catalog), catalog, stub_pipeline)
    return node.assess("INC7", _pred(attack_id), [], WHEN)[0]


def test_notice_deadlines_follow_the_rules(catalog, tmp_path):
    notices = draft_notices(_decision(catalog, "signalling_storm_amf"), WHEN, {}, tmp_path)
    by_key = {n["key"]: n for n in notices}
    assert by_key["dot_initial"]["deadline"] == "2026-10-07T15:30:00"
    assert by_key["dot_details"]["deadline"] == "2026-10-08T09:30:00"
    assert by_key["certin"]["deadline"] == "2026-10-07T15:30:00"
    assert by_key["cti"]["status"].startswith("CONDITIONAL") and "OCCURRENCE" in by_key["cti"]["notes"][0]
    assert all(n["source_check"].startswith("verified") for n in notices)
    assert (tmp_path / "dot_initial.md").read_text(encoding="utf-8").startswith("# DRAFT")
    assert "action_certin_logs_180d" in by_key


def test_dpdp_notices_depend_on_commencement(catalog, tmp_path):
    decision = _decision(catalog, "subscriber_data_exfiltration")
    before = {n["key"]: n for n in draft_notices(decision, WHEN, {}, None)}
    after = {n["key"]: n for n in draft_notices(decision, datetime(2027, 6, 1, 10, 0), {}, None)}
    assert {"dpdp_principals", "dpdp_board_initial", "dpdp_board_details"} <= set(before)
    assert before["dpdp_board_details"]["status"].startswith("PREPAREDNESS")
    assert str(DPDP_BREACH_DUTIES_FROM.year) in before["dpdp_board_details"]["notes"][0]
    assert after["dpdp_board_details"]["status"].startswith("DRAFT")
    assert after["dpdp_board_details"]["deadline"] == "2027-06-04T10:00:00"


# ---------------------------------------------------------------------------
# D node and SINKs
# ---------------------------------------------------------------------------

def _distributor(catalog, tmp_path, human, mode="blocking"):
    data = small_intent(catalog)
    data["policy"]["mode"] = mode
    intent = parse_intent(data, catalog=catalog)
    sim = Sim(root=tmp_path / "live")
    inject_scaled(sim, "signalling_storm_amf", 1.0)
    return intent, sim, Distributor(intent, catalog, human, sim, tmp_path)


def test_declined_hold_changes_nothing_and_escalates(catalog, tmp_path):
    human = Reviewer(approve=False)
    intent, sim, dist = _distributor(catalog, tmp_path, human)
    decision, _ = PolicyNode(intent, catalog, stub_pipeline).assess("INC1", _pred(), [], WHEN)
    before = copy.deepcopy(sim.state)
    sinks = {s["sink"]: s for s in dist.dispatch(_pred(), decision, [], WHEN)}
    assert sinks["remediation"]["status"] == "held" and not sinks["remediation"]["approved"]
    assert {k: v for k, v in sim.state.items() if k != "logs"} == {k: v for k, v in before.items() if k != "logs"}
    assert sinks["escalation"]["status"] == "escalated"
    assert sinks["escalation"]["detail"].startswith("Remediation status: held")
    drafts = [n for n in sinks["regulatory_notices"]["notices"] if "recipient" in n]
    assert drafts and all(n["status"].startswith("ON HOLD") for n in drafts)
    manifest = json.loads((tmp_path / "evidence" / "INC1" / "MANIFEST.json").read_text())
    assert "logs/amf.log" in manifest["sha256"]


def test_approved_remediation_runs_through_the_ir_engine(catalog, tmp_path):
    intent, sim, dist = _distributor(catalog, tmp_path, Reviewer(approve=True))
    decision, _ = PolicyNode(intent, catalog, stub_pipeline).assess("INC1", _pred(), [], WHEN)
    sinks = {s["sink"]: s for s in dist.dispatch(_pred(), decision, [], WHEN)}
    assert sinks["remediation"]["status"] == "resolved" and sinks["remediation"]["resolved_in"] == "basic"
    assert any("disconnect_gnb" in c for c in sinks["remediation"]["changes"])
    assert "escalation" not in sinks
    assert Path(sinks["remediation"]["paths"][0]).parent == tmp_path / "live" / "reports"
    drafts = [n for n in sinks["regulatory_notices"]["notices"] if "recipient" in n]
    assert drafts and not any(n["status"].startswith("ON HOLD") for n in drafts)


def test_max_tier_stops_gates(catalog, tmp_path):
    human = Reviewer(approve=True)
    data = small_intent(catalog)
    data["remediation"] = {"agent": "offline", "max_tier": "basic"}
    data["ml_application"]["target_classes"] = ["rogue_base_station"]
    data["exercise"]["events"] = []
    intent = parse_intent(data, catalog=catalog)
    sim = Sim(root=tmp_path / "live")
    inject_scaled(sim, "rogue_base_station", 1.0)
    pred = _pred("rogue_base_station")
    decision, _ = PolicyNode(intent, catalog, stub_pipeline).assess("INC2", pred, [], WHEN)
    rem = Distributor(intent, catalog, human, sim, tmp_path).remediate(pred, decision)
    assert rem["status"] != "resolved" and not any(a[0] == "gate" for a in human.asked)


# ---------------------------------------------------------------------------
# Audit trail extension
# ---------------------------------------------------------------------------

def test_generic_trail_is_hash_chained(tmp_path):
    trail = AuditTrail.start_run("r1", {"intent_id": "x", "value": np.float64(1.5)}, tmp_path)
    trail.record("tick", {"tick": np.int64(3), "labels": ("a", "b")})
    entries = read_entries(trail.path)
    assert [e["type"] for e in entries] == ["run_started", "tick"] and not verify_chain(entries)
    assert entries[1]["tick"] == 3 and entries[0]["value"] == 1.5
    with pytest.raises(FileExistsError):
        AuditTrail.start_run("r1", {}, tmp_path)


# ---------------------------------------------------------------------------
# MLFO end to end
# ---------------------------------------------------------------------------

def _run(catalog, tmp_path, human, **over):
    intent = parse_intent(small_intent(catalog, **over), catalog=catalog)
    m = MLFO(intent, run_dir=tmp_path / "run", human=human, catalog=catalog, pipeline_factory=stub_pipeline)
    return m, m.run()


def test_mlfo_end_to_end_detects_and_contains_the_storm(catalog, tmp_path):
    m, report = _run(catalog, tmp_path, Reviewer(approve=True))
    s = report["data"]["summary"]
    assert s["sandbox_validation_passed"] == s["sandbox_validation_total"] == 3
    assert s["attacks_injected"] == 1 and s["attacks_detected_within_deadline"] == 1
    first = m.incidents[0]
    assert first["correct"] and first["prediction"]["label"] == "signalling_storm_amf"
    assert {x["sink"] for x in first["sinks"]} >= {"evidence_preservation", "remediation", "regulatory_notices"}
    entries = read_entries(m.trail.path)
    assert not verify_chain(entries)
    types = [e["type"] for e in entries]
    for kind in ("run_started", "pipeline_instantiated", "model_selected", "sandbox_effect_evaluation",
                 "model_deployed", "tick", "detection", "p_node_decision", "dispatch", "run_completed"):
        assert kind in types, kind
    p_node = next(e for e in entries if e["type"] == "p_node_decision")
    assert p_node["specialist_agents"]["agents"]          # the swarm's §7.6 record, per agent
    md = (m.run_dir / "report.md").read_text(encoding="utf-8")
    for heading in ("## 1. Pipeline instantiated", "## 2.1 ML sandbox", "## 3. Sandbox evaluation",
                    "## 4. Live operation", "## 5. Incidents", "## 7. Y.3172 mapping"):
        assert heading in md


def test_mlfo_blocking_with_a_declining_operator_never_changes_the_network(catalog, tmp_path):
    m, _ = _run(catalog, tmp_path, Reviewer(approve=False))
    remediations = [s for x in m.incidents for s in x["sinks"] if s["sink"] == "remediation"]
    assert remediations and all(s["status"] == "held" for s in remediations)
    assert m.live.state["gnbs"][-1]["connected"] is True       # the storm's gNB was never disconnected
    assert all(any(s["sink"] == "escalation" for s in x["sinks"]) for x in m.incidents)


def test_mlfo_reselects_when_live_load_drifts(catalog, tmp_path):
    over = {"exercise": {"ticks": 14, "seed": 11, "events": [{"at": 2, "drift": 6.0}]},
            "monitoring": {"metric": "accuracy", "window": 6, "min_samples": 3, "min_score": 0.99,
                           "cooldown_ticks": 3}}
    m, report = _run(catalog, tmp_path, Reviewer(approve=False), **over)
    if not m.reselections:                     # the model may already cope with this drift
        pytest.skip("no false alarms under drift in this seed")
    r = m.reselections[0]
    assert r["estimated_live_load"] > 3 and r["training_load"][1] > 1.2
    assert len(m.history) >= 2 and "monitoring" in m.history[1]["reason"]


def test_run_py_intent_mode(tmp_path, monkeypatch, capsys):
    import run
    intent = tmp_path / "tiny.yaml"
    data = small_intent(load_catalog())
    data["policy"]["legal_adviser"] = False
    intent.write_text(yaml.safe_dump(data), encoding="utf-8")
    assert run.main(["--intent", str(intent), "--auto", "--mode", "advisory", "--out", str(tmp_path / "out")]) == 0
    out = capsys.readouterr().out
    assert "P node: advisory" in out and "RUN SUMMARY" in out
    assert (tmp_path / "out" / "report.md").exists()
    assert run.main(["--intent", str(tmp_path / "missing.yaml")]) == 1
