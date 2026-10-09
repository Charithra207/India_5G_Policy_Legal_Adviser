"""
Step 3 of the build-a-thon plan: real agents.
  - optional LLM reasoning per specialist agent (src/llm): providers, the
    citation guardrail, the Verifier as the gate, the audit-trail trace;
  - agent-specific information ("each receiving different information");
  - the incident-response lab's Ollama agent (ir/llm.py).

Ollama is exercised over real HTTP against a local fake server; Claude
against a fake client.  No test needs a network connection or a key.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src import llm  # noqa: E402
from src.audit.replay import load_run, reexecute  # noqa: E402
from src.audit.trail import AuditTrail, stage_entry  # noqa: E402
from src.core.models import AgentID, EvidenceItem  # noqa: E402
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase  # noqa: E402
from src.knowledge_base.kb_registry import KBRegistry  # noqa: E402
from src.llm.provider import AnthropicLLM, OfflineLLM, OllamaLLM, make_provider  # noqa: E402
from src.llm.synthesis import parse_json  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from scenarios.scenario2_healthcare_5g import get_chunks  # noqa: E402


# ---------------------------------------------------------------------------
# A fake Ollama server (real HTTP)
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):                                   # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append(body)
        reply = self.server.replies.pop(0) if self.server.replies else {"message": {"content": "{}"}}
        data = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture
def ollama():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.requests, server.replies = [], []
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield server
    server.shutdown()


@pytest.fixture(autouse=True)
def offline_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("ADVISER_LLM", raising=False)
    monkeypatch.setenv("ADVISER_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("LAB_WORK_DIR", str(tmp_path / "work"))
    llm.configure("offline")
    yield
    llm.configure("offline")


def content(obj) -> dict:
    return {"message": {"role": "assistant", "content": json.dumps(obj)},
            "prompt_eval_count": 900, "eval_count": 120}


# ---------------------------------------------------------------------------
# A small live-like corpus: TCS Rules rule 7 in the Cybersecurity KB and the Canonical KB
# ---------------------------------------------------------------------------

RULE7 = EvidenceItem(
    source_title="Telecommunications (Telecom Cyber Security) Rules, 2024", authority="Government of India",
    jurisdiction="India", document_type="Rules", section="Rule 7", section_title="Reporting of security incidents",
    excerpt=("7. Reporting of security incidents. (1) The telecommunication entity shall (a) within six hours of "
             "becoming aware of a security incident affecting its telecommunication network or telecommunication "
             "service, report the same to the Central Government with relevant details of the affected system."),
    chunk_id="tcs_rules:rule-7:1", page="12")
NIST = EvidenceItem(
    source_title="NIST SP 800-61r3", authority="NIST", jurisdiction="International", document_type="Standard",
    section="p. 9", excerpt="Incident response activities include preparation, detection and analysis.",
    chunk_id="nist:p9:1", page="9")


def live_like_registry() -> KBRegistry:
    registry = KBRegistry()
    registry.agent_kbs[AgentID.CYBERSECURITY] = InMemoryKnowledgeBase("Cybersecurity KB", "cybersecurity",
                                                                      [RULE7, NIST])
    registry.canonical_kb = InMemoryCanonicalKB([RULE7, NIST])
    return registry


GOOD = ("The telecommunication entity shall report a security incident affecting its telecommunication network "
        "to the Central Government within six hours of becoming aware of it.")
INVENTED = "Operators must notify the Prime Minister's Office within one hour of any outage."


def cyber_reply(cites_good=("tcs_rules:rule-7:1",)) -> dict:
    return content({
        "reasoning_summary": "Rule 7 sets a six-hour reporting duty; the SOC ticket suggests a security incident.",
        "claims": [{"text": GOOD, "cites": list(cites_good)},
                   {"text": INVENTED, "cites": ["tcs_rules:rule-7:1"]},
                   {"text": "Something with no citation.", "cites": ["not-a-retrieved-id"]}],
        "uncertainties": ["Whether unauthorised access occurred is not confirmed."],
        "missing_information": ["Time at which the operator became aware."]})


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def test_ollama_provider_over_http(ollama):
    ollama.replies.append(content({"ok": True}))
    resp = OllamaLLM(host=ollama.url, model="m1").complete("sys", "user")
    assert resp.text == '{"ok": true}' and resp.provider == "ollama" and resp.usage["output_tokens"] == 120
    sent = ollama.requests[0]
    assert sent["format"] == "json" and sent["options"]["temperature"] == 0 and sent["model"] == "m1"
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]


def test_ollama_unreachable_returns_none():
    provider = OllamaLLM(host="http://127.0.0.1:9", timeout=2)
    assert provider.complete("s", "u") is None and provider.last_error


def test_make_provider(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert isinstance(make_provider(), OfflineLLM)
    fallback = make_provider("anthropic")
    assert isinstance(fallback, OfflineLLM) and "ANTHROPIC_API_KEY" in fallback.notice
    assert isinstance(make_provider("ollama"), OllamaLLM)
    with pytest.raises(ValueError):
        make_provider("gpt")


def _fake_claude(stop_reason="end_turn", text='{"claims": []}'):
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(stop_reason=stop_reason, model="fake-model",
                               content=[SimpleNamespace(type="text", text=text)],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))
    provider = object.__new__(AnthropicLLM)
    provider.model, provider.last_error = "configured-model", ""
    provider.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return provider, calls


def test_anthropic_provider_request_and_refusal():
    pytest.importorskip("anthropic")
    provider, calls = _fake_claude()
    resp = provider.complete("system text", "user text")
    assert resp.text == '{"claims": []}' and resp.model == "fake-model"
    sent = calls[0]
    assert sent["system"] == "system text" and sent["messages"] == [{"role": "user", "content": "user text"}]
    assert sent["extra_body"] == {"fallbacks": "default"} and "server-side-fallback-2026-07-01" in sent["betas"]
    assert "temperature" not in sent
    refused, _ = _fake_claude(stop_reason="refusal")
    assert refused.complete("s", "u") is None and "declined" in refused.last_error


@pytest.mark.parametrize("text, ok", [('{"a": 1}', True), ('```json\n{"a": 1}\n```', True),
                                      ('Here you go: {"a": 1} thanks', True), ("no json", False),
                                      ("[1, 2]", False)])
def test_parse_json(text, ok):
    assert (parse_json(text) == {"a": 1}) is ok


# ---------------------------------------------------------------------------
# The LLM proposes, the text verifies
# ---------------------------------------------------------------------------

def _run_t1(registry):
    pipeline = Pipeline(registry)
    chunks = get_chunks()
    pipeline.run_chunk(chunks[0])
    return pipeline.run_chunk(chunks[1])


def test_llm_claims_are_cited_filtered_and_verified(ollama):
    llm.configure(provider=OllamaLLM(host=ollama.url, model="m1"))
    ollama.replies += [cyber_reply()] * 3                       # T1 runs three agents
    record = _run_t1(live_like_registry())
    cyber = next(f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY)
    trace = cyber.reasoning_trace
    assert trace["provider"] == "ollama" and trace["reasoning_summary"].startswith("Rule 7")
    accepted = [c["claim"] for c in trace["accepted_claims"]]
    assert len(accepted) == 2                                   # GOOD and INVENTED cite a retrieved id
    assert trace["rejected_claims"][0]["reason"] == "cites no retrieved passage id"
    outcomes = {vc.claim: vc.outcome.value for vc in record.verifier_result.verified_claims}
    good = next(c for c in accepted if GOOD in c)
    invented = next(c for c in accepted if INVENTED in c)
    assert good.startswith("[LLM-assisted — ollama:m1]")
    assert outcomes[good] in ("VERIFIED", "INCOMPLETE")       # supported by the canonical text
    assert outcomes[invented] == "UNSUPPORTED"                  # the guardrail: text does not support it
    assert cyber.claim_citations[good][0].chunk_id == "tcs_rules:rule-7:1"
    assert any("Time at which" in m for m in cyber.missing_facts)
    # the prompt carried this agent's own view and only retrieved passages
    prompt = trace["user_prompt"]
    assert "Information only you received:" in prompt and "SOC ticket" in prompt
    assert "[tcs_rules:rule-7:1]" in prompt


def test_reference_only_label_on_international_llm_claims(ollama):
    llm.configure(provider=OllamaLLM(host=ollama.url, model="m1"))
    ollama.replies += [content({"reasoning_summary": "x", "claims": [
        {"text": "Incident response includes preparation, detection and analysis.", "cites": ["nist:p9:1"]}]})] * 3
    record = _run_t1(live_like_registry())
    cyber = next(f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY)
    claim = cyber.reasoning_trace["accepted_claims"][0]["claim"]
    assert "[REFERENCE ONLY — not Indian law]" in claim


def test_model_unavailable_keeps_the_deterministic_finding():
    offline = _run_t1(live_like_registry())
    llm.configure(provider=OllamaLLM(host="http://127.0.0.1:9", timeout=2))
    record = _run_t1(live_like_registry())
    for a, b in zip(offline.agent_findings, record.agent_findings):
        assert a.claims == b.claims
    cyber = next(f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY)
    assert cyber.reasoning_trace["status"].startswith("model unavailable")
    assert any("LLM reasoning not available" in n for n in cyber.uncertainty_notes)


def test_offline_adds_nothing():
    record = _run_t1(live_like_registry())
    assert all(f.reasoning_trace == {} for f in record.agent_findings)
    assert not any(c.startswith("[LLM-assisted") for f in record.agent_findings for c in f.claims)


# ---------------------------------------------------------------------------
# Agent-specific information
# ---------------------------------------------------------------------------

def test_each_agent_receives_only_its_own_view():
    chunks = get_chunks()
    pipeline = Pipeline()
    pipeline.run_chunk(chunks[0])
    record = pipeline.run_chunk(chunks[1])
    views = {a: inp["agent_view"] for a, inp in record.agent_inputs.items()}
    assert any("SOC ticket" in f for f in views["cybersecurity"])
    assert not any("SOC ticket" in f for f in views["technical"] + views["standards"])
    assert any("AMF logs" in f for f in views["technical"])
    # selection is unchanged by views (still the DOCX T1 set)
    assert sorted(a.value for a in record.active_agents) == ["cybersecurity", "standards", "technical"]


def test_views_are_not_used_for_incident_flags():
    chunk = get_chunks()[1]
    from dataclasses import replace
    loud = replace(chunk, agent_views={"technical": ["patient data, hospital, data breach"]})
    pipeline = Pipeline()
    pipeline.run_chunk(get_chunks()[0])
    pipeline.run_chunk(loud)
    state = pipeline.incident_state
    assert state["data_exposure_suspected"] is False and state["cii_flagged"] is False


def test_audit_trail_records_views_and_llm_trace_and_replays(ollama, tmp_path):
    from src.scenario.catalog import get_scenario
    spec = get_scenario("scenario2")
    llm.configure(provider=OllamaLLM(host=ollama.url, model="m1"))
    ollama.replies += [cyber_reply()] * 6
    trail = AuditTrail.start(spec, {}, directory=tmp_path, run_id="llm_run")
    pipeline, previous = Pipeline(live_like_registry()), []
    for i, chunk in enumerate(get_chunks()[:2]):
        record = pipeline.run_chunk(chunk)
        entry = trail.record_stage(record, "scenario2", spec.stages[i], previous)
        previous = entry["orchestrator"]["active_agents"]
    trail.complete()
    run = load_run(trail.path)
    assert run.intact and run.header["llm"] == {"provider": "ollama", "model": "m1"}
    t1 = run.stages[1]
    assert t1["stage"]["agent_views"]["cybersecurity"]
    cyber = next(a for a in t1["agents"] if a["agent_id"] == "cybersecurity")
    assert cyber["visible_input"]["agent_view"] and cyber["llm_reasoning"]["accepted_claims"]
    assert run.chunks()[1].agent_views == get_chunks()[1].agent_views
    diffs = reexecute(run, live_like_registry())
    assert diffs and diffs[0].startswith("note: recorded with LLM ollama")


def test_offline_record_reexecutes_exactly_even_with_a_model_configured(ollama, tmp_path):
    from src.scenario.catalog import get_scenario
    spec = get_scenario("scenario2")
    trail = AuditTrail.start(spec, {}, directory=tmp_path, run_id="offline_run")
    pipeline, previous = Pipeline(live_like_registry()), []
    for i, chunk in enumerate(get_chunks()):
        entry = trail.record_stage(pipeline.run_chunk(chunk), "scenario2", spec.stages[i], previous)
        previous = entry["orchestrator"]["active_agents"]
    trail.complete()
    configured = OllamaLLM(host=ollama.url, model="m1")
    llm.configure(provider=configured)
    assert reexecute(load_run(trail.path), live_like_registry()) == []
    assert llm.active() is configured and ollama.requests == []   # restored; the model was never called


def test_stage_entry_without_views_or_trace_is_backward_compatible():
    record = Pipeline().run_chunk(get_chunks()[0])
    entry = stage_entry(record, "scenario2", None, [])
    agent = entry["agents"][0]
    assert agent["llm_reasoning"] == {} and "agent_view" in agent["visible_input"]


# ---------------------------------------------------------------------------
# Incident-response lab: the Ollama tool-calling agent
# ---------------------------------------------------------------------------

def _call(name, **args):
    return {"function": {"name": name, "arguments": args}}


def test_ir_ollama_agent_resolves_the_storm_through_the_gates(ollama):
    from catalog.loader import load_catalog
    from ir.engine import Incident
    from ir.llm import OllamaProvider
    ollama.replies += [
        {"message": {"role": "assistant", "content": "", "tool_calls": [_call("list_gnbs")]}},
        {"message": {"role": "assistant", "content": "", "tool_calls": [
            _call("disconnect_gnb", gnb_id="gnb-207"),
            _call("block_source", nf="amf", source="ue-range-404-45-77xx")]}},
        {"message": {"role": "assistant", "content": "", "tool_calls": [
            _call("report_tier_outcome", resolved=True, summary="rogue gNB disconnected, range blocked")]}},
    ]
    incident = Incident("signalling_storm_amf", provider=OllamaProvider(host=ollama.url, model="m1"),
                        catalog=load_catalog(), search=lambda *a, **k: [])
    incident.start()
    assert incident.run_tier("basic", "agent")
    assert incident.tier_outcomes["basic"]["summary"].startswith("rogue gNB")
    tools = {t["function"]["name"] for t in ollama.requests[0]["tools"]}
    assert {"list_gnbs", "disconnect_gnb", "report_tier_outcome", "search_kb"} <= tools
    assert ollama.requests[1]["messages"][-1]["role"] == "tool"


def test_ir_ollama_refused_steps_stay_refused(ollama):
    from catalog.loader import load_catalog
    from ir.engine import Incident
    from ir.llm import OllamaProvider
    ollama.replies += [{"message": {"role": "assistant", "content": "",
                                    "tool_calls": [_call("isolate_nf", nf="amf")]}},
                       {"message": {"role": "assistant", "content": "done"}}]
    incident = Incident("signalling_storm_amf", provider=OllamaProvider(host=ollama.url),
                        catalog=load_catalog(), search=lambda *a, **k: [])
    incident.start()
    incident.run_tier("basic", "agent")
    refused = [e for e in incident.timeline if e.action == "isolate_nf"]
    assert refused and refused[0].approved is False                 # not auto-safe in Basic
    assert incident.sim.state["nfs"]["amf"]["isolated"] is False


def test_ir_ollama_unreachable_falls_back_to_the_playbook():
    from catalog.loader import load_catalog
    from ir.engine import Incident
    from ir.llm import OllamaProvider
    incident = Incident("signalling_storm_amf", provider=OllamaProvider(host="http://127.0.0.1:9", timeout=2),
                        catalog=load_catalog(), search=lambda *a, **k: [])
    incident.start()
    assert incident.run_tier("basic", "agent")
    assert incident.tier_outcomes["basic"]["provider"].startswith("ollama→offline")


def test_get_provider_ollama(monkeypatch):
    from ir.llm import OllamaProvider, get_provider
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert isinstance(get_provider(), OllamaProvider)
