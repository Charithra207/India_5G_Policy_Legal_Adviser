"""
Attacks shown as they unfold, plain-language summaries, and the agent-focus
fixes from the run review:

* each agent searches first for the facts released to it alone, and a
  question is not searched as if it were a fact;
* passages are quoted by relevance to the incident, duties with a time limit
  first; a title page is never quoted;
* "missing information" that the agent's own facts answer is dropped;
* one entry per institution; international comparators named by authority;
* Ollama's "model not found" is explained; the readiness check names the fix;
* the attack lab replays the attack step by step (CLI and web page), and the
  adviser, the lab and the Y.3172 page end with a summary and a conclusion.
"""

import io
import json
import os
import sys
import threading
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scenarios.scenario2_healthcare_5g import get_chunks  # noqa: E402
from src.agents.cybersecurity_agent import CybersecurityAgent  # noqa: E402
from src.agents.technical_agent import TechnicalAgent  # noqa: E402
from src.audit.narrative import adviser_narrative, duties_in, notifications, pipeline_narrative  # noqa: E402
from src.audit.trail import read_entries  # noqa: E402
from src.core.models import EvidenceItem  # noqa: E402
from src.knowledge_base.in_memory_kb import InMemoryKnowledgeBase  # noqa: E402
from src.llm.provider import OllamaLLM  # noqa: E402
from src.pipeline import Pipeline  # noqa: E402
from src.rag.regions import comparator_tag  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RECORDED = ROOT / "outputs" / "audit" / "day2_scenario2_full_T0_T3.jsonl"
EXAMPLE = ROOT / "outputs" / "y3172" / "examples" / "amf_signalling_storm"


def _item(title, section, excerpt, chunk_id, score=0.0):
    return EvidenceItem(source_title=title, authority="fixture", jurisdiction="India", document_type="Rule",
                        section=section, excerpt=excerpt, chunk_id=chunk_id, relevance_score=score)


# ---------------------------------------------------------------------------
# Agent focus
# ---------------------------------------------------------------------------

def test_view_is_searched_first_and_a_question_is_not_searched():
    t3 = get_chunks()[3]
    agent = CybersecurityAgent()
    agent.analyze(t3, {"chunks_processed": ["T0", "T1", "T2"], "cyber_event_suspected": True})
    view = t3.agent_views["cybersecurity"]
    assert agent.last_queries[: len(view)] == view
    assert t3.description not in agent.last_queries


def test_duty_on_the_incident_is_quoted_before_an_off_topic_passage_and_headings_are_skipped():
    off_topic = _item("National Digital Communications Policy 2018", "Para 8",
                      "Improvement in regulation and ongoing structural reforms are the pillars of a sound policy "
                      "initiative. Regulatory reform is not a one-off effort, but a dynamic, long-term and "
                      "multidisciplinary process for the telecommunication sector.", "ndcp:8", score=0.9)
    logs = _item("CERT-In Directions (28 April 2022)", "Direction (iv)",
                 "All service providers shall mandatorily enable logs of all their ICT systems and maintain them "
                 "securely for a rolling period of 180 days within the Indian jurisdiction; logs for the period "
                 "shall be provided to CERT-In.", "certin:iv")
    heading = _item("ENISA 5G Cybersecurity Standards", "p. 1",
                    "5G CYBERSECURITY STANDARDS Analysis of standardisation requirements", "enisa:1")
    kb = InMemoryKnowledgeBase("Cybersecurity KB", "cybersecurity", [off_topic, heading, logs])
    finding = CybersecurityAgent(kb).analyze(get_chunks()[3], {"cyber_event_suspected": True})
    quoted = [c for c in finding.claims if " states: " in c]
    assert quoted[0].startswith("CERT-In Directions (28 April 2022), Direction (iv)")
    assert not any("5G CYBERSECURITY STANDARDS" in c for c in quoted)


def test_missing_information_answered_by_the_agents_own_facts_is_dropped():
    t1 = get_chunks()[1]
    finding = TechnicalAgent().analyze(t1, {"chunks_processed": ["T0"]})
    assert not any("AMF/SMF logs" in m for m in finding.missing_facts)
    assert any("AMF logs were released to this agent" in m for m in finding.missing_facts)
    # Without a view nothing changes
    plain = TechnicalAgent().analyze(get_chunks()[0].__class__(**{**get_chunks()[1].__dict__, "agent_views": {}}),
                                     {"chunks_processed": ["T0"]})
    assert any("AMF/SMF logs" in m for m in plain.missing_facts)


def test_institutions_are_listed_once():
    pipeline = Pipeline()
    for chunk in get_chunks():
        record = pipeline.run_chunk(chunk)
    names = record.coordinator_assessment.relevant_institutions
    assert sum("NCIIPC" in n for n in names) == 1
    assert "National Critical Information Infrastructure Protection Centre (NCIIPC)" in names


def test_international_comparator_named_by_authority():
    assert comparator_tag("International", authority="European Union Agency for Cybersecurity (ENISA)") == \
        "[International reference — European Union Agency for Cybersecurity (ENISA)]"
    assert comparator_tag("Sri Lanka", authority="x") == "[Neighbouring-region example — Sri Lanka]"


# ---------------------------------------------------------------------------
# Ollama: a clear reason when the model is not pulled
# ---------------------------------------------------------------------------

class _Ollama404(BaseHTTPRequestHandler):
    def do_POST(self):                                        # noqa: N802
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b'{"error":"model not found"}')

    def do_GET(self):                                         # noqa: N802
        body = json.dumps({"models": [{"name": "llama3.2:latest"}]}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def test_ollama_missing_model_is_explained():
    server = HTTPServer(("127.0.0.1", 0), _Ollama404)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        llm = OllamaLLM(model="qwen2.5:7b-instruct", host=f"http://127.0.0.1:{server.server_port}")
        assert llm.complete("s", "u") is None
        assert "ollama pull qwen2.5:7b-instruct" in llm.last_error
        ready, problem = llm.check()
        assert not ready and "ollama pull qwen2.5:7b-instruct" in problem and "llama3.2:latest" in problem
        assert OllamaLLM(model="llama3.2", host=f"http://127.0.0.1:{server.server_port}").check() == (True, "")
    finally:
        server.shutdown()
    ready, problem = OllamaLLM(host="http://127.0.0.1:9").check()
    assert not ready and "not reachable" in problem


# ---------------------------------------------------------------------------
# Summary and conclusion
# ---------------------------------------------------------------------------

def test_duties_in_reads_recipient_and_time_limits():
    text = ("(j) implement mechanisms to ensure intimation of security incident(s) to the Central Government, "
            "no later than six hours of occurrence of such incident; the entity shall comply.")
    assert duties_in(text) == [("Central Government", ["no later than six hours"])]
    assert duties_in("report to CERT-In within 6 hours") == []          # no duty word: not a duty


@pytest.mark.skipif(not RECORDED.exists(), reason="recorded run not present")
def test_adviser_narrative_of_the_recorded_run():
    stages = [e for e in read_entries(RECORDED) if e["type"] == "stage"]
    story = adviser_narrative(stages)
    assert "T0–T3" in story["summary"] and "matching the official stage table at 4 of 4" in story["summary"]
    rows = notifications(stages)
    assert any(r["recipient"] == "CERT-In" and "within 6 hours" in r["limits"] for r in rows)
    assert all(r["condition"] for r in rows)
    dpdp = [r for r in rows if "Data Protection" in r["source"]]
    assert dpdp and all("currently only suspected" in r["condition"] for r in dpdp)
    assert rows.index(dpdp[0]) > max(rows.index(r) for r in rows if r not in dpdp)   # conditional duties last
    conclusion = story["conclusion"]
    assert "decision support" in conclusion and "qualified" in conclusion
    for word in ("inadequate", "fails to", "failure of policy"):
        assert word not in (story["summary"] + conclusion).lower()
    one = adviser_narrative(stages[:1])
    assert one["summary"].startswith("So far one stage") and not one["notifications"]


@pytest.mark.skipif(not (EXAMPLE / "report.json").exists(), reason="example run not present")
def test_pipeline_narrative_of_the_example_run():
    data = json.loads((EXAMPLE / "report.json").read_text(encoding="utf-8"))
    story = pipeline_narrative(data)
    assert "SRC → C → PP → M → P → D → SINK" in story["summary"] and "blocking mode" in story["summary"]
    assert "contained simulator" in story["conclusion"]


# ---------------------------------------------------------------------------
# Attack lab: step by step
# ---------------------------------------------------------------------------

@pytest.fixture
def lab(tmp_path, monkeypatch):
    monkeypatch.setenv("LAB_WORK_DIR", str(tmp_path / "work"))
    import kb.retriever
    monkeypatch.setattr(kb.retriever, "search", lambda *a, **k: [])      # no embedding model needed
    return tmp_path


def test_incident_records_how_the_attack_unfolded(lab):
    from ir.engine import Incident
    from ir.llm import OfflineProvider
    inc = Incident("signalling_storm_amf", provider=OfflineProvider())
    inc.start()
    assert set(inc.baseline_health.values()) == {"ok"}
    assert inc.detected_health["amf"] != "ok"
    logs = [s for s in inc.attack_story if s["kind"] == "log"]
    assert logs[0]["message"].startswith("NG setup request from gnb-207")
    assert any(s["count"] == 5 for s in logs)                          # a burst is one step
    assert inc.attack_story[-1]["kind"] == "alert"
    report = inc.run()
    assert "## Summary" in report["markdown"] and "## Conclusion" in report["markdown"]
    assert "resolved in the basic tier" in report["data"]["conclusion"]


def test_cli_shows_the_attack_in_sequence_and_ends_with_summary(lab):
    import run
    out = io.StringIO()
    with redirect_stdout(out):
        code = run.main(["--attack", "1", "--provider", "offline", "--auto", "--fast"])
    text = out.getvalue()
    assert code == 0
    order = [text.index(h) for h in ("1. THE NETWORK BEFORE THE ATTACK", "2. THE ATTACK UNFOLDS",
                                     "3. DETECTED", "POLICY PANEL", "BASIC tier", "SUMMARY", "CONCLUSION")]
    assert order == sorted(order)
    assert "## Timeline" not in text                                    # full report only with --full-report


def test_cli_step_mode_does_not_hang_without_a_terminal(lab, monkeypatch):
    import run
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    with redirect_stdout(io.StringIO()):
        assert run.main(["--attack", "core_ddos_upf", "--provider", "offline", "--auto", "--step"]) == 0


def test_lab_web_page_plays_the_attack_step_by_step(lab):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "ir" / "ui.py"), default_timeout=120).run()
    at.sidebar.selectbox[0].set_value("rogue_base_station")
    at.sidebar.radio[0].set_value("offline")
    at.sidebar.button[0].click().run()
    assert not at.exception
    assert len(at.info) + len(at.warning) + len(at.error) + len(at.success) == 1   # one step shown
    [b for b in at.button if b.label.startswith("Next")][0].click().run()
    assert len(at.info) + len(at.warning) + len(at.error) + len(at.success) == 2
    for _ in range(5):                                                   # story, then Basic tier
        shown_all = [b for b in at.button if b.label == "Show all"]
        if not shown_all:
            break
        shown_all[0].click().run()
    assert any(b.label.startswith("[1]") for b in at.button)             # gate before Intermediate
    [b for b in at.button if b.label.startswith("[1]")][0].click().run()
    for _ in range(5):
        shown_all = [b for b in at.button if b.label == "Show all"]
        if not shown_all:
            break
        shown_all[0].click().run()
    assert not at.exception
    assert [h.value for h in at.header] == ["Summary", "Conclusion"]


def test_adviser_and_pipeline_pages_end_with_summary():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "src" / "ui" / "app.py"), default_timeout=120).run()
    at.sidebar.radio[0].set_value("Replay").run()
    assert not at.exception
    if RECORDED.exists():
        assert any(h.value.startswith("Summary") for h in at.header)
        assert any(h.value == "Conclusion" for h in at.header)
    if (EXAMPLE / "report.json").exists():
        at.sidebar.radio[0].set_value("Y.3172 pipeline").run()
        assert not at.exception
        assert not any(h.value == "Conclusion" for h in at.header)       # not until the run is shown
        [b for b in at.button if b.label == "Show all"][0].click().run()
        assert not at.exception and any(h.value == "Conclusion" for h in at.header)
