"""
Final knowledge-base and evidence audit.

* The recorded demonstration run passes the evidence audit with no problems.
* The audit is not vacuous: each kind of fabrication, planted in a re-hashed
  copy of the run (so the hash chain alone would not reveal it), is caught.
* Final RAG test: empty and irrelevant retrieval never produce an answer.

Requires the built knowledge bases; skipped otherwise.

Run with:
    python -m pytest tests/test_evidence_audit.py -v
"""

import json
import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)

from src.audit.trail import GENESIS_HASH, entry_hash
from src.core.models import AgentID, ScenarioChunk, VerifierOutcome
from src.rag.manifest import ALL_KBS, KB_ROOT
from src.rag.vector_store import VectorStore

ROOT = KB_ROOT.parent
RUN = ROOT / "outputs" / "audit" / "day2_scenario2_full_T0_T3.jsonl"

pytestmark = pytest.mark.skipif(
    not all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS) or not RUN.exists(),
    reason="knowledge bases not built or demonstration run missing")


def audit(path: Path) -> list[str]:
    """The audit's trace, legal, standards, policy-gap and manifest checks."""
    from src.rag.evidence_audit import Audit
    a = Audit(path)
    for st in a.run.stages:
        a.check_stage(st)
    cited = {c["chunk_id"].split(":")[0] for s in a.run.stages for ag in s["agents"]
             for cl in ag["claims"] for c in cl["citations"]}
    a.check_manifest(cited)
    return a.problems


def tampered(tmp_path: Path, edit) -> Path:
    """A copy of the run with `edit` applied and every hash recomputed."""
    entries = [json.loads(l) for l in RUN.open(encoding="utf-8")]
    edit(entries)
    prev = GENESIS_HASH
    for e in entries:
        e["prev_hash"] = prev
        e["hash"] = entry_hash(e)
        prev = e["hash"]
    out = tmp_path / "tampered.jsonl"
    out.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8")
    return out


def stage(entries, label):
    return next(e for e in entries if e.get("type") == "stage" and e["stage"]["label"] == label)


def agent(st, agent_id):
    return next(a for a in st["agents"] if a["agent_id"] == agent_id)


def cited_claim(ag, international=None):
    for c in ag["claims"]:
        if c["citations"] and "states:" in c["claim"]:
            if international is None or c["claim"].startswith("[REFERENCE ONLY") == international:
                return c
    raise AssertionError("no cited claim")


# -----------------------------------------------------------------------
# The demonstration run is fully traceable
# -----------------------------------------------------------------------

def test_demo_run_passes_evidence_audit() -> None:
    from src.rag.evidence_audit import Audit
    report = Audit(RUN).run_all()
    assert report["problems"] == []
    assert report["checks"]["cited passages checked"] > 0
    assert {e["agent"] for e in report["agent_examples"] if e.get("source")} == {
        "technical", "policy_legal", "cybersecurity", "privacy",
        "critical_infrastructure", "standards", "policy_gap"}
    for e in report["agent_examples"]:
        assert e["verification_status"] != "VERIFIED"
        if e["agent"] in ("technical", "standards"):
            assert e["jurisdiction"] != "India" and e["conclusion"].startswith("[REFERENCE ONLY")
        if e["agent"] != "policy_gap":
            assert e["question"], f"{e['agent']}: retrieval query not reproduced"


def test_every_demo_source_is_a_real_manifest_document() -> None:
    from src.rag.evidence_audit import Audit
    report = Audit(RUN).run_all()
    manifest = {s["id"]: s for s in report["sources"]}
    for doc_id in report["sources_used_in_demo"]:
        s = manifest[doc_id]
        assert s["status"] == "ingested" and s["url"].startswith("https://")
        assert s["sha256_matches_file"] in (True, None)   # None: raw file not on this machine


# -----------------------------------------------------------------------
# The audit catches each kind of fabrication
# -----------------------------------------------------------------------

def test_catches_altered_quote(tmp_path) -> None:
    def edit(entries):
        c = cited_claim(agent(stage(entries, "T1"), "cybersecurity"), international=False)
        c["claim"] = c["claim"].replace("six hours", "seventy-two hours")
    assert any("quoted words are not in the stored passage" in p for p in audit(tampered(tmp_path, edit)))


def test_catches_standard_without_reference_label(tmp_path) -> None:
    def edit(entries):
        c = cited_claim(agent(stage(entries, "T1"), "standards"), international=True)
        c["claim"] = c["claim"].replace("[REFERENCE ONLY — not Indian law] ", "")
    assert any("without the reference-only label" in p for p in audit(tampered(tmp_path, edit)))


def test_catches_standard_presented_as_indian_law(tmp_path) -> None:
    def edit(entries):
        stage(entries, "T1")["coordinator"]["uncertain_conclusions"].append(
            "3GPP TS 33.501 is binding in India for every operator.")
    assert any("international standard as Indian law" in p for p in audit(tampered(tmp_path, edit)))


def test_catches_unsupported_absence_claim(tmp_path) -> None:
    def edit(entries):
        stage(entries, "T3")["coordinator"]["potential_policy_gaps"].append(
            "Indian law has no provision for network slicing.")
    assert any("unsupported absence/inadequacy claim" in p for p in audit(tampered(tmp_path, edit)))


def test_catches_uncited_legal_requirement(tmp_path) -> None:
    def edit(entries):
        agent(stage(entries, "T2"), "privacy")["claims"].append({
            "claim": "The operator must notify every patient within 24 hours.", "citations": [],
            "verifier_outcome": "UNSUPPORTED", "verifier_rationale": "", "verifier_supporting": [],
            "verifier_conflicting": [], "cross_domain_flag": False, "cross_domain_note": ""})
    assert any("uncited claim states a requirement" in p for p in audit(tampered(tmp_path, edit)))


def test_catches_passage_from_another_agents_kb(tmp_path) -> None:
    def edit(entries):
        privacy_cite = cited_claim(agent(stage(entries, "T2"), "privacy"))["citations"][0]
        cited_claim(agent(stage(entries, "T0"), "technical"))["citations"] = [privacy_cite]
    assert any("outside the KBs it may search" in p for p in audit(tampered(tmp_path, edit)))


def test_catches_false_verified(tmp_path) -> None:
    def edit(entries):
        cited_claim(agent(stage(entries, "T1"), "cybersecurity"))["verifier_outcome"] = "VERIFIED"
    assert any("VERIFIED although" in p for p in audit(tampered(tmp_path, edit)))


# -----------------------------------------------------------------------
# Final RAG test — no answer is manufactured
# -----------------------------------------------------------------------

@pytest.fixture(scope="module")
def registry():
    from src.rag.registry import build_registry
    return build_registry()


@pytest.mark.parametrize("query", ["chocolate cake recipe with butter and sugar",
                                   "football world cup final score", "cricket match result",
                                   "weather forecast for tomorrow"])
def test_irrelevant_query_retrieves_nothing_in_any_kb(registry, query) -> None:
    for agent_id, kb in registry.agent_kbs.items():
        assert kb.retrieve(query, top_k=5) == [], f"{agent_id.value} returned passages for {query!r}"


def test_irrelevant_chunk_produces_no_quoted_answer(registry) -> None:
    from src.pipeline import Pipeline
    record = Pipeline(registry).run_chunk(ScenarioChunk(
        chunk_index=0, chunk_id="irrelevant_1", timestamp="2026-10-07T09:00:00Z",
        description="A routine status update was received.", new_facts=[]))
    for f in record.agent_findings:
        assert not f.claim_citations, f"{f.agent_id.value} quoted a passage for an irrelevant chunk"
        assert any("not assessed" in c for c in f.claims)
    assert all(vc.outcome != VerifierOutcome.VERIFIED for vc in record.verifier_result.verified_claims)
    assert record.coordinator_assessment.open_questions[0].startswith("No conclusion is evidence-backed")


def test_empty_retrieval_for_technical_agent_without_symptoms(registry) -> None:
    from src.pipeline import Pipeline
    pipeline = Pipeline(registry)
    agent_obj = pipeline.orchestrator.get_agent(AgentID.TECHNICAL)
    chunk = ScenarioChunk(chunk_index=0, chunk_id="x", timestamp="t",
                          description="A routine status update was received.", new_facts=[])
    assert agent_obj._build_queries(chunk, {}) == []
    assert agent_obj._retrieve_evidence([]) == []


# -----------------------------------------------------------------------
# In-force status and amendments come only from obtained documents
# -----------------------------------------------------------------------

def _stored(doc_id, section):
    from src.rag.manifest import KB_ROOT as root
    for line in (root / "canonical" / "chunks.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r["doc_id"] == doc_id and r["section"] == section:
            return r
    raise AssertionError(f"{doc_id} {section} not stored")


def test_in_force_status_follows_the_commencement_notifications() -> None:
    s22 = _stored("telecom_act_2023", "Section 22")
    assert s22["effective"] is True and "S.O. 2408(E)" in s22["effective_status"]
    s7 = _stored("telecom_act_2023", "Section 7")
    assert s7["effective"] is True and "S.O. 2623(E)" in s7["effective_status"]
    s3 = _stored("telecom_act_2023", "Section 3")          # named by neither notification
    assert s3["effective"] is None and s3["effective_status"] == ""
    assert all(not r["amendment_checked"] for r in (s22, s7, s3))


def test_amendment_notes_follow_the_amendment_rules() -> None:
    rule7 = _stored("telecom_cyber_security_rules_2024", "Rule 7")
    rule5 = _stored("telecom_cyber_security_rules_2024", "Rule 5")
    assert rule7["effective"] is True and rule7["amendment_note"] == ""   # G.S.R. 771(E) leaves rule 7 alone
    assert "G.S.R. 771(E)" in rule5["amendment_note"]
    assert not rule7["amendment_checked"] and not rule5["amendment_checked"]


def test_verifier_reports_established_status_but_stays_incomplete(registry) -> None:
    from scenarios.scenario2_healthcare_5g import get_chunks
    from src.pipeline import Pipeline
    pipeline = Pipeline(registry)
    pipeline.run_chunk(get_chunks()[0])
    t1 = pipeline.run_chunk(get_chunks()[1])
    rule7 = next(vc for vc in t1.verifier_result.verified_claims
                 if "Cyber Security) Rules, 2024, Rule 7 states" in vc.claim)
    assert rule7.outcome == VerifierOutcome.INCOMPLETE
    assert "in force from 21 November 2024" in rule7.rationale and "amendments not checked" in rule7.rationale


def test_catches_unbacked_in_force_status() -> None:
    from src.rag.evidence_audit import Audit
    a = Audit(RUN)
    cid = next(cid for cid, r in a.stored.items()
               if r["doc_id"] == "dpdp_rules_2025" and r["section"] == "Rule 7")
    a.stored[cid] = {**a.stored[cid], "effective": True, "effective_status": "in force"}
    for st in a.run.stages:
        a.check_stage(st)
    assert any("not established by an obtained document" in p for p in a.problems)
