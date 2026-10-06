"""
Final hardening: failure modes, Verifier and Coordinator validation, and
the full end-to-end run (release-candidate checks).

Every case runs through the real Pipeline (Orchestrator → agents → Verifier
→ Coordinator).  Fixture passages are SYNTHETIC (titles start with
"FIXTURE"); the live test uses the built knowledge bases and is skipped if
they are absent.

Run with:
    python -m pytest tests/test_hardening.py -v
"""

import logging
import os
import sys
from dataclasses import replace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)

from scenarios.scenario2_healthcare_5g import get_chunks
from src.core.models import AgentID, EvidenceItem, ScenarioChunk, VerifierOutcome
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase
from src.knowledge_base.kb_registry import KBRegistry
from src.pipeline import Pipeline
from src.scenario.conflict_fixture import REPORTING_DIRECTION, conflict_registry

T1 = get_chunks()[1]          # cybersecurity stage: the Cybersecurity Agent quotes its KB


def registry(cyber_items, canonical_items) -> KBRegistry:
    reg = KBRegistry()
    reg.agent_kbs[AgentID.CYBERSECURITY] = InMemoryKnowledgeBase(
        "Cybersecurity fixture KB", "cybersecurity", cyber_items)
    if canonical_items is not None:
        reg.canonical_kb = InMemoryCanonicalKB(canonical_items)
    return reg


def run_t0_t1(reg):
    pipeline = Pipeline(reg)
    pipeline.run_chunk(get_chunks()[0])
    return pipeline.run_chunk(T1)


def quoted(record, agent=AgentID.CYBERSECURITY):
    finding = next(f for f in record.agent_findings if f.agent_id == agent)
    assert finding.claim_citations, "the agent should quote its retrieved passage"
    return [vc for vc in record.verifier_result.verified_claims
            if vc.agent_id == agent and vc.claim in finding.claim_citations]


# =======================================================================
# Task 1 — failure modes: fail safely and explicitly
# =======================================================================

def test_1_no_evidence_is_stated_not_invented() -> None:
    """Stub KBs: no passage anywhere. No claim may be supported or VERIFIED."""
    pipeline = Pipeline()
    for chunk in get_chunks():
        record = pipeline.run_chunk(chunk)
        assert all(vc.outcome != VerifierOutcome.VERIFIED for vc in record.verifier_result.verified_claims)
        for f in record.agent_findings:
            assert not f.claim_citations, f"{f.agent_id.value} cited a passage it never retrieved"
        a = record.coordinator_assessment
        assert not a.evidence_backed_conclusions
        assert a.open_questions[0].startswith("No conclusion is evidence-backed")


def test_2_wrong_citation_is_unsupported() -> None:
    """The agent cites a passage the Canonical KB does not hold."""
    other = replace(REPORTING_DIRECTION, source_title="FIXTURE Different Instrument",
                    chunk_id="fixture:different:1")
    [vc] = quoted(run_t0_t1(registry([REPORTING_DIRECTION], [other])))
    assert vc.outcome == VerifierOutcome.UNSUPPORTED
    assert "not found in the Canonical KB" in vc.rationale


def test_3_missing_section_is_unsupported() -> None:
    """Same instrument in the Canonical KB, but not the cited section."""
    elsewhere = replace(REPORTING_DIRECTION, section="Direction 9", chunk_id="fixture:dir-9")
    [vc] = quoted(run_t0_t1(registry([REPORTING_DIRECTION], [elsewhere])))
    assert vc.outcome == VerifierOutcome.UNSUPPORTED
    assert "Direction 4" in vc.rationale


def test_4_conflicting_findings_are_conflict_and_unresolved() -> None:
    pipeline = Pipeline(conflict_registry())
    record = [pipeline.run_chunk(c) for c in get_chunks()][3]
    [conflict] = record.verifier_result.conflict_details
    for side in (conflict.finding_a, conflict.finding_b):
        vc = next(v for v in record.verifier_result.verified_claims
                  if (v.agent_id, v.claim) == (side.agent_id, side.claim))
        assert vc.outcome == VerifierOutcome.CONFLICT and side.evidence
    assert "unresolved" in conflict.status
    assert record.coordinator_assessment.conflicting_findings


def test_5_incomplete_information_is_incomplete() -> None:
    """Cited text found, but its in-force status was never checked."""
    unchecked = replace(REPORTING_DIRECTION, effective=None, amendment_checked=False)
    [vc] = quoted(run_t0_t1(registry([REPORTING_DIRECTION], [unchecked])))
    assert vc.outcome == VerifierOutcome.INCOMPLETE
    assert "in-force status not verified" in vc.rationale


def test_6_new_chunk_matching_no_mandate_is_handled_safely() -> None:
    """A chunk outside the scenario: technical triage only, nothing invented."""
    pipeline = Pipeline()
    chunk = ScenarioChunk(chunk_index=0, chunk_id="adhoc_1", timestamp="2026-10-07T09:00:00Z",
                          description="A routine status update was received.", new_facts=[])
    record = pipeline.run_chunk(chunk)
    assert [a.value for a in record.active_agents] == ["technical"]
    assert record.coordinator_assessment.confirmed_facts == [
        "[Incident fact — adhoc_1] A routine status update was received."]
    assert all(vc.outcome != VerifierOutcome.VERIFIED for vc in record.verifier_result.verified_claims)


def test_6b_new_chunk_mid_scenario_triggers_reassessment() -> None:
    pipeline = Pipeline()
    pipeline.run_chunk(get_chunks()[0])
    record = pipeline.run_chunk(T1)
    changes = " ".join(record.coordinator_assessment.changes_from_prior)
    assert "Newly activated agents: cybersecurity, standards" in changes
    assert "possible security event" in changes


def test_7_agent_failure_is_explicit_and_isolated() -> None:
    """One agent raises: the others still run, and the assessment says so."""
    pipeline = Pipeline()
    pipeline.run_chunk(get_chunks()[0])
    cyber = pipeline.orchestrator.get_agent(AgentID.CYBERSECURITY)

    def outage(*args, **kwargs):
        raise RuntimeError("simulated retrieval outage")
    cyber.analyze = outage
    record = pipeline.run_chunk(T1)

    failed = next(f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY)
    assert failed.summary.startswith("[ERROR]") and not failed.claims
    others = [f for f in record.agent_findings if f.agent_id != AgentID.CYBERSECURITY]
    assert others and all(f.claims for f in others), "other agents must still run"
    questions = " ".join(record.coordinator_assessment.open_questions)
    assert "AGENT FAILURE — the cybersecurity analysis did not run" in questions


def test_8_empty_retrieval_result_is_explicit() -> None:
    """The KB is available but returns nothing for the agent's queries."""
    unrelated = EvidenceItem(source_title="FIXTURE Unrelated", authority="Test fixture",
                             jurisdiction="India", document_type="Fixture", section="Part 1",
                             excerpt="Zzzz qqqq xxxx.", chunk_id="fixture:unrelated:1")
    reg = registry([unrelated], [unrelated])
    assert reg.agent_kbs[AgentID.CYBERSECURITY].retrieve("security incident reporting") == []
    record = run_t0_t1(reg)
    cyber = next(f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY)
    assert not cyber.claim_citations
    assert any("not assessed" in c for c in cyber.claims)
    for vc in record.verifier_result.verified_claims:
        if vc.agent_id == AgentID.CYBERSECURITY:
            assert vc.outcome == VerifierOutcome.UNSUPPORTED


# =======================================================================
# Task 2 — Verifier validation, through the full pipeline
# =======================================================================

def test_verifier_valid_evidence_is_verified() -> None:
    [vc] = quoted(run_t0_t1(registry([REPORTING_DIRECTION], [REPORTING_DIRECTION])))
    assert vc.outcome == VerifierOutcome.VERIFIED
    assert vc.supporting_evidence[0].section == "Direction 4"


def test_verifier_is_not_weakened_by_agent_kb_alone() -> None:
    """The agent's own KB never confers VERIFIED: without a Canonical KB, at most INCOMPLETE."""
    [vc] = quoted(run_t0_t1(registry([REPORTING_DIRECTION], None)))
    assert vc.outcome == VerifierOutcome.INCOMPLETE


def test_verifier_amendment_prevents_verified() -> None:
    amended = replace(REPORTING_DIRECTION, amendment_note="Direction 4 substituted by a later notice")
    [vc] = quoted(run_t0_t1(registry([REPORTING_DIRECTION], [amended])))
    assert vc.outcome == VerifierOutcome.INCOMPLETE and "amendment" in vc.rationale


# =======================================================================
# Task 3 — Coordinator validation: the five categories
# =======================================================================

@pytest.fixture(scope="module")
def fixture_run():
    pipeline = Pipeline(conflict_registry())
    return [pipeline.run_chunk(c) for c in get_chunks()]


def test_coordinator_confirmed_facts_are_released_facts_only(fixture_run) -> None:
    released = {f"[Incident fact — {c.chunk_id}] {c.description}" for c in get_chunks()}
    released |= {f"[New fact — {c.chunk_id}] {f}" for c in get_chunks() for f in c.new_facts}
    final = fixture_run[3].coordinator_assessment.confirmed_facts
    assert set(final) == released


def test_coordinator_evidence_backed_holds_only_verified(fixture_run) -> None:
    t1 = fixture_run[1]
    verified = [vc.claim for vc in t1.verifier_result.verified_claims
                if vc.outcome == VerifierOutcome.VERIFIED]
    backed = t1.coordinator_assessment.evidence_backed_conclusions
    assert verified and len(backed) == len(verified)
    assert all("| VERIFIED]" in b for b in backed)


def test_coordinator_uncertain_holds_incomplete_and_unsupported(fixture_run) -> None:
    for record in fixture_run:
        for u in record.coordinator_assessment.uncertain_conclusions:
            assert "| INCOMPLETE]" in u or "| UNSUPPORTED" in u


def test_coordinator_conflicting_withholds_both_sides(fixture_run) -> None:
    t2 = fixture_run[2]
    a = t2.coordinator_assessment
    assert a.conflicting_findings and "Finding A" in a.conflicting_findings[0]
    # The T1 side was VERIFIED; while in conflict it is no longer evidence-backed
    assert not a.evidence_backed_conclusions


def test_coordinator_policy_gaps_are_potential_not_conclusive(fixture_run) -> None:
    gaps = fixture_run[3].coordinator_assessment.potential_policy_gaps
    assert gaps
    for g in gaps:
        assert g.startswith(("[POLICY GAP — for expert review]", "[CANDIDATE GAP AREA",
                             "[GAP SUMMARY"))
        assert "inadequate" not in g.lower() or "no conclusion" in g.lower()


# =======================================================================
# Task 4 — full end-to-end on the live knowledge bases
# =======================================================================

def _built() -> bool:
    from src.rag.manifest import ALL_KBS, KB_ROOT
    from src.rag.vector_store import VectorStore
    return all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS)


@pytest.mark.skipif(not _built(), reason="knowledge bases not built")
def test_end_to_end_assessment_evolves_with_context() -> None:
    from src.rag.registry import build_registry
    pipeline = Pipeline(build_registry())
    t0, t1, t2, t3 = (pipeline.run_chunk(c) for c in get_chunks())
    a = [r.coordinator_assessment for r in (t0, t1, t2, t3)]
    changes = [" ".join(x.changes_from_prior) for x in a]

    # Agents follow the information released (DOCX §2.5)
    assert [sorted(x.value for x in r.active_agents) for r in (t0, t1, t2, t3)] == [
        ["technical"], ["cybersecurity", "standards", "technical"],
        ["critical_infrastructure", "policy_legal", "privacy"],
        ["critical_infrastructure", "cybersecurity", "policy_gap", "policy_legal", "privacy"]]
    # Each stage changes the assessment for the reason the new chunk gives
    assert changes[0].startswith("Initial assessment")
    assert "possible security event" in changes[1]
    assert "Critical-service relevance" in changes[2] and "personal-data" in changes[2]
    assert "Potential policy gaps raised" in changes[3]
    # Context accumulates; earlier conclusions are carried, not dropped
    assert len(a[0].confirmed_facts) < len(a[1].confirmed_facts) < len(a[2].confirmed_facts) < len(a[3].confirmed_facts)
    assert any(r["carried_forward"] and r["agent_id"] == "technical" for r in a[3].claim_register)
    # Evidence is real, cross-domain links appear, nothing unchecked is VERIFIED
    assert t2.verifier_result.cross_domain_details and t3.verifier_result.cross_domain_details
    assert a[3].potential_policy_gaps
    for r in (t0, t1, t2, t3):
        assert all(vc.outcome != VerifierOutcome.VERIFIED for vc in r.verifier_result.verified_claims)
        assert not r.verifier_result.conflict_details
        for f in r.agent_findings:
            for items in f.claim_citations.values():
                assert all(e.authority != "STUB" and e.chunk_id and e.url for e in items)
