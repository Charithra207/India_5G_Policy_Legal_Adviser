"""
Contained incident-response lab: retrieval filtering, simulator, catalog and
the tiered state machine (with a mocked LLM and a scripted operator).

Nothing here needs the network or the prebuilt index; the one test that uses
the real kb/index/ is skipped when it is not present.
"""

import gzip
import hashlib
import json
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from catalog.loader import CatalogError, load_catalog, resolve_args, validate  # noqa: E402
from ir.engine import Incident  # noqa: E402
from ir.llm import AnthropicProvider, OfflineProvider  # noqa: E402
from sim.cli import format_args, parse_args  # noqa: E402
from sim.engine import Sim, call, check  # noqa: E402
from sim.inject import ATTACKS, inject  # noqa: E402


@pytest.fixture(autouse=True)
def lab_work_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_WORK_DIR", str(tmp_path / "work"))
    return tmp_path / "work"


@pytest.fixture(scope="module")
def catalog():
    return load_catalog()


def no_search(*args, **kwargs):
    return []


class Operator:
    """Scripted human: gate answers in order, approves unless told otherwise."""

    def __init__(self, gates=(), approve=True, run_manual=None):
        self.gates, self.approve, self.run_manual = list(gates), approve, run_manual
        self.asked, self.confirmations = [], []

    def gate(self, tier, message):
        self.asked.append(message)
        return self.gates.pop(0) if self.gates else "stop"

    def confirm(self, description):
        self.confirmations.append(description)
        return self.approve

    def manual(self, tier, commands):
        return self.run_manual(commands) if self.run_manual else ""


# ---------------------------------------------------------------------------
# Retrieval: only the requested category indexes are searched
# ---------------------------------------------------------------------------

@pytest.fixture
def tiny_index(tmp_path, monkeypatch):
    faiss = pytest.importorskip("faiss")
    import kb.retriever as r
    folder = tmp_path / "index"
    folder.mkdir()
    chunks = {"cyber_incident_rules": [("certin.pdf", "report incidents within 6 hours", [1, 0, 0, 0])],
              "gpp_security": [("ts33501.pdf", "AMF overload control signalling storm", [0, 1, 0, 0]),
                               ("ts33501.pdf", "SUCI null-scheme", [0, 0, 1, 0])]}
    files, lines = {}, []
    for cat, items in chunks.items():
        index = faiss.IndexFlatIP(4)
        index.add(np.array([v for *_, v in items], dtype=np.float32))
        faiss.write_index(index, str(folder / f"{cat}.faiss"))
        for row, (doc, text, _) in enumerate(items):
            lines.append(json.dumps({"id": f"{cat}-{row}", "category": cat, "row": row, "doc": doc,
                                     "page_start": row + 1, "page_end": row + 1, "text": text}))
    with gzip.open(folder / "chunks.jsonl.gz", "wt", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    for f in folder.iterdir():
        files[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    (folder / "manifest.json").write_text(json.dumps({
        "embedding_model": "fake", "categories": {c: {"chunks": len(v)} for c, v in chunks.items()},
        "files": files}), encoding="utf-8")
    monkeypatch.setenv("KB_INDEX_DIR", str(folder))
    for fn in (r.manifest, r._chunks, r._index):
        fn.cache_clear()
    # every query points at the AMF chunk's direction, slightly towards the CERT-In one
    query = np.array([0.3, 0.95, 0, 0], dtype=np.float32)
    monkeypatch.setattr(r, "_embedder", lambda: SimpleNamespace(embed_query=lambda text: query))
    yield r
    for fn in (r.manifest, r._chunks, r._index):
        fn.cache_clear()


def test_search_only_returns_requested_categories(tiny_index):
    r = tiny_index
    assert {h["category"] for h in r.search("x", ["cyber_incident_rules"], k=5)} == {"cyber_incident_rules"}
    assert {h["category"] for h in r.search("x", ["gpp_security"], k=5)} == {"gpp_security"}
    everything = r.search("x", None, k=5)
    assert everything[0]["doc"] == "ts33501.pdf" and len(everything) == 3
    with pytest.raises(ValueError):
        r.search("x", ["no_such_category"])


def test_find_passage_cite_and_verify(tiny_index):
    r = tiny_index
    hit = r.find_passage("certin.pdf", "within  6 HOURS")
    assert hit and r.cite(hit) == "certin.pdf, p. 1"
    assert r.find_passage("certin.pdf", "72 hours") is None
    assert r.verify() == []
    (r.index_dir() / "gpp_security.faiss").write_bytes(b"tampered")
    assert r.verify() == ["gpp_security.faiss: hash differs from manifest"]


def test_real_index_category_filter_if_built():
    import kb.retriever as r
    if not (r.ROOT / "kb" / "index" / "manifest.json").exists() or os.environ.get("KB_INDEX_DIR"):
        pytest.skip("prebuilt kb/index not present")
    hits = r.search("report a security incident within six hours", ["cyber_incident_rules"], k=5)
    assert hits and all(h["category"] == "cyber_incident_rules" for h in hits)


# ---------------------------------------------------------------------------
# Simulator: inject -> diagnose -> fix, for the reference attack
# ---------------------------------------------------------------------------

def test_sim_signalling_storm_inject_diagnose_fix():
    sim = Sim()
    assert sim.get_nf_health("amf") == {"amf": "ok"}
    inject(sim, "signalling_storm_amf")
    assert sim.get_nf_health("amf") == {"amf": "degraded"}
    assert sim.get_metrics("amf")["registration_failure_pct"] > 80          # legitimate devices fail too
    assert sim.list_gnbs()["unauthorised_connected"] == ["gnb-207"]
    top = sim.get_top_talkers("amf")["top"][0]
    assert top["source"] == "ue-range-404-45-77xx" and top["via"] == "gnb-207" and not top["blocked"]
    assert any("registration request burst" in line for line in sim.get_logs("amf")["lines"])
    sim.rate_limit_nf("amf", 1000)                                         # mitigation is not a fix:
    assert sim.get_metrics("amf")["registration_failure_pct"] > 80         # the limit rejects legit UEs too
    sim.disconnect_gnb("gnb-207")
    sim.block_source("amf", top["source"])
    assert sim.get_metrics("amf")["registration_failure_pct"] < 2
    assert sim.get_nf_health("amf") == {"amf": "ok"}


def test_logs_use_open5gs_layout():
    import re
    sim = Sim(persist=False)
    inject(sim, "gtpu_spoofing_upf")
    line = sim.get_logs("upf", 1)["lines"][0]
    assert re.match(r"^\d\d/\d\d \d\d:\d\d:\d\d\.\d{3}: \[upf\] (INFO|WARNING|ERROR): ", line), line


def test_sim_fake_base_station_statistical_evidence_and_containment():
    sim = Sim(persist=False)
    inject(sim, "rogue_base_station")
    kpis = sim.get_ran_kpis()
    assert kpis["fallback_to_lte_ues"] > 0 and kpis["unknown_cells_reported"][0]["in_cell_inventory"] is False
    assert sim.check_auth_config()["suci_protection"] == "profile_A"      # SUCI still hides the identity
    sim.flag_cell_hostile("gnb-666")
    assert sim.get_ran_kpis()["fallback_to_lte_ues"] > 0                  # devices still camp until told
    sim.push_device_policy("gnb-666")
    sim.dispatch_field_team("gnb-666")
    kpis = sim.get_ran_kpis()
    assert kpis["fallback_to_lte_ues"] == 0 and kpis["field_ticket_cells"] == ["gnb-666"]


def test_sim_rogue_nf_evidence_is_lost_if_isolated_first():
    sim = Sim(persist=False)
    inject(sim, "supply_chain_rogue_nf")
    assert sim.list_registered_nfs()["unexpected_hosts"] == ["nf-x9"]
    assert sim.get_metrics("udm")["bulk_reads_active"] == 1 and sim.get_egress_flows()["active"]
    sim.deregister_nf("nf-x9")
    assert sim.get_metrics("udm")["bulk_reads_active"] == 0                # queries stop ...
    assert sim.get_egress_flows()["active"]                               # ... the upload does not
    sim.isolate_instance("nf-x9")
    assert sim.capture_evidence("nf-x9")["ok"] is False                   # wrong order: evidence gone


def test_sim_profile_tampering_and_restore():
    sim = Sim(persist=False)
    inject(sim, "subscriber_profile_tampering")
    bad = sim.check_slice_sessions("urllc-hospital")["not_on_allow_list"]
    assert [x["id"] for x in bad] == ["pdu-9001"]
    change = sim.get_subscriber_changes()["unreverted"][0]
    assert change["by"] == "admin" and change["from"] == "10.20.30.77"
    sim.end_session("pdu-9001")
    sim.restore_profile(change["supi"])
    assert sim.state["subscribers"][change["supi"]]["slices"] == ["embb"]
    assert sim.get_subscriber_changes()["unreverted"] == []


def test_sim_gtpu_spoofing_needs_more_than_sav():
    sim = Sim(persist=False)
    inject(sim, "gtpu_spoofing_upf")
    flows = sim.get_upf_flows()
    assert flows["spoofed"][0]["inner_src"] != flows["spoofed"][0]["assigned_ip"]
    sim.patch_config("upf", "source_address_validation", "enabled")
    assert sim.get_upf_flows()["spoofed"] == [] and sim.get_upf_flows()["to_internal_ranges"]
    sim.block_route("10.45.0.0/16", "10.10.0.0/16")
    assert sim.get_upf_flows()["to_internal_ranges"] == []


def test_sim_botnet_separate_infected_from_healthy():
    sim = Sim(persist=False)
    inject(sim, "iot_botnet_mmtc")
    assert sim.get_service_health("hospital-portal")["status"] == "degraded"
    stats = sim.get_device_stats("mmtc")
    assert len(stats["anomalous"]) == 24 and stats["devices"] == 40
    assert sim.get_flow_logs()["c2_candidates"] == ["203.0.113.66:23"]   # not the 2-device distractor
    sim.quarantine_devices(list(sim.state["devices"]))                    # over-reaction
    assert sim.get_device_stats("mmtc")["healthy_quarantined"] == 16


def test_sim_state_persists_for_operator_commands(lab_work_dir):
    sim = Sim()
    inject(sim, "core_ddos_upf")
    again = Sim.resume()                       # what python -m sim.cli does
    assert again.state["attack"] == "core_ddos_upf"
    assert again.get_metrics("upf")["packet_drop_pct"] > 5
    assert (lab_work_dir / "logs" / "upf.log").read_text(encoding="utf-8")


def test_every_attack_changes_health_or_alerts():
    for attack in ATTACKS:
        sim = Sim(persist=False)
        before = (sim.get_nf_health(), sim.get_alerts())
        inject(sim, attack)
        assert (sim.get_nf_health(), sim.get_alerts()) != before, attack


def test_check_and_call_guard_rails():
    sim = Sim(persist=False)
    assert call(sim, "rm_rf", {})["ok"] is False
    assert call(sim, "get_metrics", {"bogus": 1})["ok"] is False
    with pytest.raises(ValueError):
        check(sim, {"fn": "isolate_nf", "args": {"nf": "amf"}, "op": "=="})
    assert check(sim, {"fn": "get_metrics", "args": {"nf": "amf"}, "path": "cpu", "op": "contains", "value": 1}) \
        == (False, sim.get_metrics("amf")["cpu"])


def test_sim_cli_arguments_round_trip():
    args = {"nf": "amf", "limit": 1000, "value": True, "source": "ue-range-404-45-77xx"}
    assert parse_args(format_args(args).split(" ")) == args
    assert parse_args(['{"nf": "amf"}']) == {"nf": "amf"}


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

def test_catalog_has_the_thirteen_attacks_and_validates(catalog):
    assert [a["id"] for a in catalog["attacks"]] == list(ATTACKS) and len(ATTACKS) == 13
    for a in catalog["attacks"]:
        assert 5 <= len(a["playbook"]["basic"]) <= 10
        assert a["policy_tags"]["obligations"], a["id"]


def test_catalog_rejects_bad_entries(catalog):
    import copy
    bad = copy.deepcopy(catalog)
    bad["attacks"][0]["playbook"]["basic"][0]["is_state_changing"] = True      # a diagnostic
    with pytest.raises(CatalogError):
        validate(bad)
    bad = copy.deepcopy(catalog)
    bad["attacks"][0]["playbook"]["basic"][0]["action"]["fn"] = "format_disk"
    with pytest.raises(CatalogError):
        validate(bad)


def test_arg_references_resolve_from_live_findings():
    sim = Sim(persist=False)
    inject(sim, "signalling_storm_amf")
    ref = {"nf": "amf", "source": {"from": {"fn": "get_top_talkers", "args": {"nf": "amf"}, "path": "top.0.source"}}}
    assert resolve_args(sim, ref) == {"nf": "amf", "source": "ue-range-404-45-77xx"}


@pytest.mark.parametrize("attack,tier", [
    ("signalling_storm_amf", "basic"), ("core_ddos_upf", "basic"),
    ("rogue_base_station", "intermediate"), ("subscriber_cred_compromise", "advanced"),
    ("sba_api_abuse_nef", "intermediate"), ("subscriber_data_exfiltration", "intermediate"),
    ("nf_host_ransomware", "advanced"), ("exposed_mgmt_interface", "intermediate"),
    ("n2_n3_mitm", "intermediate"), ("supply_chain_rogue_nf", "advanced"),
    # the attacks from the team's attack sheet resolve at its difficulty level
    ("subscriber_profile_tampering", "advanced"), ("gtpu_spoofing_upf", "intermediate"),
    ("iot_botnet_mmtc", "advanced")])
def test_offline_playbook_resolves_each_attack_in_its_tier(catalog, attack, tier):
    inc = Incident(attack, provider=OfflineProvider(), human=Operator(["agent", "agent"]),
                   catalog=catalog, search=no_search)
    report = inc.run()
    assert report["resolved"] and report["data"]["resolved_in"] == tier


# ---------------------------------------------------------------------------
# State machine with a mocked LLM
# ---------------------------------------------------------------------------

class MockLLM:
    """Plays a fixed list of tool calls per tier through Incident.execute."""
    name = "mock"

    def __init__(self, plan):
        self.plan, self.calls = plan, []

    def run_tier(self, incident, tier):
        for fn, args in self.plan.get(tier, []):
            self.calls.append((tier, fn, incident.execute(tier, fn, args, reason="mock")))
        return {"summary": f"mock {tier}"}

    def interpret(self, incident, tier, pasted):
        return f"mock read {len(pasted)} chars"


STORM_PLAN = {
    "basic": [("list_gnbs", {}),
              ("block_source", {"nf": "amf", "source": "ue-range-404-45-77xx"}),   # auto-safe step, same args
              ("disconnect_gnb", {"gnb_id": "gnb-101"}),                           # wrong args: a real cell
              ("rate_limit_nf", {"nf": "amf", "limit": 1000})],                    # not a Basic step
    "intermediate": [("disconnect_gnb", {"gnb_id": "gnb-207"})],
}


def test_basic_refuses_non_auto_safe_actions_then_gate_to_intermediate(catalog):
    llm, human = MockLLM(STORM_PLAN), Operator(["agent"])
    inc = Incident("signalling_storm_amf", provider=llm, human=human, catalog=catalog, search=no_search)
    report = inc.run()
    refused = [fn for t, fn, r in llm.calls if t == "basic" and r.get("ok") is False]
    assert refused == ["disconnect_gnb", "rate_limit_nf"]                 # wrong args; not auto-safe
    assert inc.sim.get_top_talkers("amf")["top"][0]["blocked"] is True     # the auto-safe step ran
    assert all(g["connected"] for g in inc.sim.state["gnbs"] if g["id"] == "gnb-101")
    assert human.asked == ["Basic steps did not resolve it. Intermediate tier?"]
    assert len(human.confirmations) == 1 and human.confirmations[0].startswith("disconnect_gnb(")
    assert report["resolved"] and report["data"]["resolved_in"] == "intermediate"
    assert "## What fixed it" in report["markdown"] and "disconnect_gnb" in report["markdown"]
    assert len(report["paths"]) == 2 and all(os.path.exists(p) for p in report["paths"])


def test_declined_actions_lead_to_second_gate_then_stop(catalog):
    llm = MockLLM({"basic": [], "intermediate": STORM_PLAN["intermediate"]})
    human = Operator(["agent", "stop"], approve=False)
    inc = Incident("signalling_storm_amf", provider=llm, human=human, catalog=catalog, search=no_search)
    report = inc.run()
    assert human.asked == ["Basic steps did not resolve it. Intermediate tier?",
                           "Intermediate steps did not resolve it. Advanced tier?"]
    assert llm.calls[0][2] == {"ok": False, "error": "operator declined this action"}
    assert inc.phase == "stopped" and not report["resolved"]
    assert "## Escalation" in report["markdown"]


def test_stop_at_first_gate(catalog):
    inc = Incident("subscriber_cred_compromise", provider=MockLLM({}), human=Operator(["stop"]),
                   catalog=catalog, search=no_search)
    report = inc.run()
    assert inc.phase == "stopped" and report["data"]["outcome"] == "stopped"
    assert [e.action for e in inc.timeline if e.state_changing and e.action != "inject"] == []


def test_exhausted_when_no_tier_resolves(catalog):
    inc = Incident("nf_host_ransomware", provider=MockLLM({}), human=Operator(["agent", "agent"]),
                   catalog=catalog, search=no_search)
    inc.run()
    assert inc.phase == "exhausted" and set(inc.tier_outcomes) == {"basic", "intermediate", "advanced"}


def test_manual_mode_operator_runs_cli_commands(catalog):
    from sim.cli import main as sim_cli

    def operator_runs(commands):
        for c in commands:
            line = c.splitlines()[-1]
            assert line.startswith("python -m sim.cli ")
            sim_cli(line.split()[3:])
        return "done"

    inc = Incident("rogue_base_station", provider=OfflineProvider(), catalog=catalog, search=no_search,
                   human=Operator(["manual"], run_manual=operator_runs))
    report = inc.run()
    assert report["resolved"] and inc.tier_outcomes["intermediate"]["mode"] == "manual"
    assert inc.human.confirmations == []                       # the agent changed nothing itself


def test_rogue_nf_evidence_decision_declined_still_contains(catalog):
    class KillFirst(Operator):                  # declines only the evidence decision
        def confirm(self, description):
            self.confirmations.append(description)
            return not description.startswith("capture_evidence(")

    human = KillFirst(["agent", "agent"])
    inc = Incident("supply_chain_rogue_nf", provider=OfflineProvider(), human=human, catalog=catalog,
                   search=no_search)
    report = inc.run()
    assert report["resolved"] and report["data"]["resolved_in"] == "advanced"
    assert inc.sim.get_egress_flows()["evidence"] == []                   # the operator chose speed
    assert any("DECISION" in c for c in human.confirmations)


def test_profile_tampering_basic_changes_nothing(catalog):
    inc = Incident("subscriber_profile_tampering", provider=OfflineProvider(), human=Operator(["stop"]),
                   catalog=catalog, search=no_search)
    inc.run()
    assert [e for e in inc.timeline if e.state_changing and e.action != "inject"] == []
    assert inc.phase == "stopped"


def test_policy_panel_marks_obligations_unverified_without_index(catalog, monkeypatch, tmp_path):
    import kb.retriever as r
    monkeypatch.setenv("KB_INDEX_DIR", str(tmp_path / "missing"))
    for fn in (r.manifest, r._chunks, r._index):
        fn.cache_clear()
    try:
        from ir.policy import build_policy_panel
        panel = build_policy_panel(next(a for a in catalog["attacks"] if a["id"] == "signalling_storm_amf"))
    finally:
        for fn in (r.manifest, r._chunks, r._index):
            fn.cache_clear()
    assert panel["error"] and panel["obligations"]
    assert all(not o["found"] and "UNVERIFIED" in o["citation"] for o in panel["obligations"])


# ---------------------------------------------------------------------------
# Anthropic provider loop, with a fake client (no network)
# ---------------------------------------------------------------------------

def _block(kind, **kw):
    return SimpleNamespace(type=kind, **kw)


class FakeMessages:
    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def test_anthropic_provider_tool_loop_with_fake_client(catalog):
    responses = [
        SimpleNamespace(stop_reason="tool_use", content=[
            _block("text", text="Checking talkers."),
            _block("tool_use", id="t1", name="list_gnbs", input={})]),
        SimpleNamespace(stop_reason="tool_use", content=[
            _block("tool_use", id="t2", name="disconnect_gnb", input={"gnb_id": "gnb-207"}),
            _block("tool_use", id="t3", name="block_source", input={"nf": "amf", "source": "ue-range-404-45-77xx"}),
            _block("tool_use", id="t4", name="search_kb", input={"query": "AMF overload"})]),
        SimpleNamespace(stop_reason="tool_use", content=[
            _block("tool_use", id="t5", name="report_tier_outcome", input={"resolved": True, "summary": "blocked"})]),
    ]
    provider = AnthropicProvider.__new__(AnthropicProvider)
    fake = FakeMessages(responses)
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    human = Operator()
    inc = Incident("signalling_storm_amf", provider=provider, human=human, catalog=catalog,
                   search=lambda q, categories, k: [{"doc": "ts_123501.pdf", "page_start": 360, "page_end": 360, "score": 0.8,
                                                    "category": categories[0], "text": "AMF overload"}])
    inc.start()
    out = provider.run_tier(inc, "intermediate")
    assert out["summary"] == "blocked" and inc.resolved()
    assert [c.split("(")[0] for c in human.confirmations] == ["disconnect_gnb", "block_source"]
    results = [m["content"] for m in fake.requests[-1]["messages"]
               if m["role"] == "user" and isinstance(m["content"], list)]
    second_turn = results[1]
    assert [r["tool_use_id"] for r in second_turn] == ["t2", "t3", "t4"]   # all results in one message
    assert "ts_123501.pdf, p. 360" in second_turn[2]["content"]
    assert fake.requests[0]["model"] and "tools" in fake.requests[0]


def test_anthropic_refusal_falls_back_to_offline_playbook(catalog):
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(
        [SimpleNamespace(stop_reason="refusal", content=[])])))
    inc = Incident("core_ddos_upf", provider=provider, human=Operator(), catalog=catalog, search=no_search)
    inc.start()
    out = provider.run_tier(inc, "basic")
    assert "offline" in out["provider"] and inc.resolved()
