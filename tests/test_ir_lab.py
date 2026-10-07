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
    assert sim.get_metrics("amf")["cpu"] == 100
    top = sim.get_top_talkers("amf")["top"][0]
    assert top["source"] == "ue-range-404-45-77xx" and not top["blocked"]
    assert any("registration request burst" in line for line in sim.get_logs("amf")["lines"])
    sim.rate_limit_nf("amf", 1000)
    sim.scale_out("amf", 2)
    assert sim.get_metrics("amf")["cpu"] < 70 and sim.get_nf_health("amf") == {"amf": "ok"}
    sim.block_source("amf", top["source"])
    assert sim.get_top_talkers("amf")["top"][0]["blocked"] is True


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

def test_catalog_has_the_ten_attacks_and_validates(catalog):
    assert [a["id"] for a in catalog["attacks"]] == list(ATTACKS)
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
    ("signalling_storm_amf", "intermediate"), ("core_ddos_upf", "basic"),
    ("rogue_base_station", "intermediate"), ("subscriber_cred_compromise", "advanced"),
    ("sba_api_abuse_nef", "intermediate"), ("subscriber_data_exfiltration", "intermediate"),
    ("nf_host_ransomware", "advanced"), ("exposed_mgmt_interface", "intermediate"),
    ("n2_n3_mitm", "intermediate"), ("supply_chain_rogue_nf", "intermediate")])
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
    "basic": [("get_top_talkers", {"nf": "amf"}),
              ("block_source", {"nf": "amf", "source": "ue-range-404-45-77xx"}),   # not auto-safe
              ("rate_limit_nf", {"nf": "amf", "limit": 1000}),
              ("rate_limit_nf", {"nf": "amf", "limit": 5}),                        # wrong args
              ("scale_out", {"nf": "amf", "replicas": 2})],
    "intermediate": [("block_source", {"nf": "amf", "source": "ue-range-404-45-77xx"})],
}


def test_basic_refuses_non_auto_safe_actions_then_gate_to_intermediate(catalog):
    llm, human = MockLLM(STORM_PLAN), Operator(["agent"])
    inc = Incident("signalling_storm_amf", provider=llm, human=human, catalog=catalog, search=no_search)
    report = inc.run()
    refused = [fn for t, fn, r in llm.calls if t == "basic" and r.get("ok") is False]
    assert refused == ["block_source", "rate_limit_nf"]                   # not auto-safe; wrong args
    assert inc.sim.get_metrics("amf")["rate_limit"] == 1000
    assert human.asked == ["Basic steps did not resolve it. Intermediate tier?"]
    assert len(human.confirmations) == 1 and human.confirmations[0].startswith("block_source(")
    assert report["resolved"] and report["data"]["resolved_in"] == "intermediate"
    assert "## What fixed it" in report["markdown"] and "block_source" in report["markdown"]
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

    inc = Incident("signalling_storm_amf", provider=OfflineProvider(), catalog=catalog, search=no_search,
                   human=Operator(["manual"], run_manual=operator_runs))
    report = inc.run()
    assert report["resolved"] and inc.tier_outcomes["intermediate"]["mode"] == "manual"
    assert inc.human.confirmations == []                       # the agent changed nothing itself


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
            _block("tool_use", id="t1", name="get_top_talkers", input={"nf": "amf"})]),
        SimpleNamespace(stop_reason="tool_use", content=[
            _block("tool_use", id="t2", name="block_source", input={"nf": "amf", "source": "ue-range-404-45-77xx"}),
            _block("tool_use", id="t3", name="search_kb", input={"query": "AMF overload"})]),
        SimpleNamespace(stop_reason="tool_use", content=[
            _block("tool_use", id="t4", name="report_tier_outcome", input={"resolved": True, "summary": "blocked"})]),
    ]
    provider = AnthropicProvider.__new__(AnthropicProvider)
    fake = FakeMessages(responses)
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=fake))
    human = Operator()
    inc = Incident("signalling_storm_amf", provider=provider, human=human, catalog=catalog,
                   search=lambda q, categories, k: [{"doc": "ts_123501.pdf", "page_start": 360, "page_end": 360, "score": 0.8,
                                                    "category": categories[0], "text": "AMF overload"}])
    inc.start()
    inc.sim.rate_limit_nf("amf", 1000)
    inc.sim.scale_out("amf", 2)
    out = provider.run_tier(inc, "intermediate")
    assert out["summary"] == "blocked" and inc.resolved()
    assert human.confirmations and human.confirmations[0].startswith("block_source(")
    results = [m["content"] for m in fake.requests[-1]["messages"]
               if m["role"] == "user" and isinstance(m["content"], list)]
    second_turn = results[1]
    assert [r["tool_use_id"] for r in second_turn] == ["t2", "t3"]       # all results in one message
    assert "ts_123501.pdf, p. 360" in second_turn[1]["content"]
    assert fake.requests[0]["model"] and "tools" in fake.requests[0]


def test_anthropic_refusal_falls_back_to_offline_playbook(catalog):
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(
        [SimpleNamespace(stop_reason="refusal", content=[])])))
    inc = Incident("core_ddos_upf", provider=provider, human=Operator(), catalog=catalog, search=no_search)
    inc.start()
    out = provider.run_tier(inc, "basic")
    assert "offline" in out["provider"] and inc.resolved()
