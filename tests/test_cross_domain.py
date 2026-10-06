"""
Day-2 core tests: cross-domain verification, conflict handling, uncertainty
and progressive reassessment.

Fixture passages are SYNTHETIC (titles start with "FIXTURE") and exist only
to exercise the logic.  The live tests use the built knowledge bases and are
skipped if they are absent.

Run with:
    python -m pytest tests/test_cross_domain.py -v
"""

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.disable(logging.CRITICAL)

from scenarios.scenario2_healthcare_5g import get_chunks
from src.core.cross_domain import act_name, find_relationships, reporting_duties
from src.core.models import AgentFinding, AgentID, EvidenceItem, VerifierOutcome
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB
from src.pipeline import Pipeline
from src.scenario.conflict_fixture import (
    REPORTING_CIRCULAR, REPORTING_DIRECTION, conflict_registry,
)


def fx(title, section, excerpt, jurisdiction="India") -> EvidenceItem:
    return EvidenceItem(source_title=f"FIXTURE {title}", authority="Test fixture",
                        jurisdiction=jurisdiction, document_type="Fixture",
                        section=section, excerpt=excerpt,
                        chunk_id=f"fx:{title}:{section}".replace(" ", "-"))


def finding(agent_id, chunk_id, *items) -> AgentFinding:
    claims = [f"{i.source_title}, {i.section} states: \"{i.excerpt}\"" for i in items]
    return AgentFinding(agent_id=agent_id, chunk_id=chunk_id, claims=claims,
                        claim_citations={c: [i] for c, i in zip(claims, items)})


# -----------------------------------------------------------------------
# Extraction
# -----------------------------------------------------------------------

def test_reporting_duties_read_recipient_and_time_limits() -> None:
    [duty] = reporting_duties(REPORTING_DIRECTION)
    assert (duty.recipient, duty.hours) == ("CERT-In", 6)
    two = fx("Breach Rule", "Rule 7",
             "(1) The Data Fiduciary shall intimate to each affected Data Principal "
             "without delay. (2) It shall intimate to the Board,— (a) without delay, "
             "a description; (b) within seventy-two hours, updated information.")
    duties = {d.recipient: d for d in reporting_duties(two)}
    assert duties["Data Principal"].hours == 0
    assert duties["Board"].limits == ("without delay", "within seventy-two hours")


def test_standards_protocol_steps_are_not_legal_duties() -> None:
    spec = fx("5G Spec", "Clause 5", "The SMF shall report the event to the AMF within 6 hours.",
              jurisdiction="International")
    assert reporting_duties(spec) == []


def test_act_name_only_for_acts() -> None:
    assert act_name("The Telecommunications Act, 2023") == "Telecommunications Act, 2023"
    assert act_name("CERT-In Directions under sub-section (6) of section 70B of the "
                    "Information Technology Act, 2000 (28 April 2022)") is None
    assert act_name("Digital Personal Data Protection Rules, 2025") is None


# -----------------------------------------------------------------------
# Cross-domain relationships come from evidence
# -----------------------------------------------------------------------

def test_shared_provision_links_two_domains() -> None:
    sec = fx("Telecom Act, 2023", "Section 22", "Measures to protect cyber security.")
    links, conflicts = find_relationships(
        [finding(AgentID.CRITICAL_INFRA, "T2", sec), finding(AgentID.POLICY_LEGAL, "T2", sec)], [])
    assert [l.kind for l in links] == ["shared_provision"] and not conflicts
    assert {m.agent_id for m in links[0].members} == {AgentID.CRITICAL_INFRA, AgentID.POLICY_LEGAL}


def test_instrument_basis_quotes_the_canonical_text() -> None:
    act = fx("Telecom Act, 2023", "Section 22", "The Central Government may by rules provide measures.")
    rule = fx("Telecom Security Rules, 2024", "Rule 7", "The entity shall keep logs.")
    preamble = fx("Telecom Security Rules, 2024", "p. 1",
                  "In exercise of the powers conferred by section 22 of the FIXTURE Telecom Act, 2023, "
                  "the Central Government makes the following rules.")
    canonical = InMemoryCanonicalKB([act, rule, preamble])
    links, _ = find_relationships(
        [finding(AgentID.CYBERSECURITY, "T1", rule)],
        [finding(AgentID.CRITICAL_INFRA, "T0", act)], canonical)
    [link] = links
    assert link.kind == "instrument_basis" and link.evidence == [preamble]
    assert "powers conferred by section 22" in link.note and "from T0" in link.note


def test_parallel_reporting_to_different_recipients_is_not_a_conflict() -> None:
    cert = fx("Direction", "Direction 2", "A provider shall report incidents to CERT-In within 6 hours.")
    dot = fx("Rules", "Rule 7", "The entity shall report the incident to the Central Government within six hours.")
    links, conflicts = find_relationships(
        [finding(AgentID.CYBERSECURITY, "T3", cert), finding(AgentID.PRIVACY, "T3", dot)], [])
    assert [l.kind for l in links] == ["parallel_reporting"] and not conflicts


def test_no_link_between_unrelated_findings() -> None:
    a = fx("Act", "Section 3", "Any person providing services shall obtain an authorisation.")
    b = fx("Data Rules", "Rule 6", "A Data Fiduciary shall take reasonable security safeguards.")
    links, conflicts = find_relationships(
        [finding(AgentID.POLICY_LEGAL, "T2", a), finding(AgentID.PRIVACY, "T2", b)], [])
    assert links == [] and conflicts == []


# -----------------------------------------------------------------------
# Conflict handling — the real pipeline, two agents that disagree
# -----------------------------------------------------------------------

@pytest.fixture(scope="module")
def conflict_run():
    pipeline = Pipeline(conflict_registry())
    return [pipeline.run_chunk(c) for c in get_chunks()]


def test_conflict_shows_both_findings_with_evidence(conflict_run) -> None:
    t3 = conflict_run[3]
    [conflict] = t3.verifier_result.conflict_details
    assert conflict.rule == "reporting_deadline"
    sides = {conflict.finding_a.agent_id: conflict.finding_a,
             conflict.finding_b.agent_id: conflict.finding_b}
    assert set(sides) == {AgentID.CYBERSECURITY, AgentID.POLICY_LEGAL}
    assert [e.chunk_id for e in sides[AgentID.CYBERSECURITY].evidence] == [REPORTING_DIRECTION.chunk_id]
    assert sides[AgentID.POLICY_LEGAL].evidence[0].chunk_id == REPORTING_CIRCULAR.chunk_id
    assert "six hours" in conflict.basis and "twenty-four hours" in conflict.basis


def test_both_sides_rated_conflict_and_not_silently_resolved(conflict_run) -> None:
    t3 = conflict_run[3]
    disputed = {(s.agent_id, s.claim) for c in t3.verifier_result.conflict_details
                for s in (c.finding_a, c.finding_b)}
    outcomes = {(vc.agent_id, vc.claim): vc for vc in t3.verifier_result.verified_claims}
    for key in disputed:
        assert outcomes[key].outcome == VerifierOutcome.CONFLICT
        assert outcomes[key].conflicting_evidence, "each side records the other side's evidence"
    a = t3.coordinator_assessment
    block = "\n".join(a.conflicting_findings)
    for part in ("Finding A", "Finding B", "Evidence:", "Status:", "Coordinator treatment:"):
        assert part in block
    for _, claim in disputed:
        assert not any(claim in s for s in a.evidence_backed_conclusions + a.uncertain_conclusions), \
            "a disputed finding must not also appear as a conclusion"


def test_conflict_detected_across_chunks(conflict_run) -> None:
    """T2's Policy & Legal duty disagrees with the T1 Cybersecurity duty."""
    t2 = conflict_run[2]
    [conflict] = t2.verifier_result.conflict_details
    chunks = {conflict.finding_a.chunk_id, conflict.finding_b.chunk_id}
    assert chunks == {"scenario2_T1", "scenario2_T2"}
    # The earlier (T1, VERIFIED) side is withheld from evidence-backed conclusions
    assert not any("FIXTURE Incident Reporting Direction" in s
                   for s in t2.coordinator_assessment.evidence_backed_conclusions)


def test_no_conflict_without_disagreement(conflict_run) -> None:
    assert not conflict_run[0].verifier_result.conflict_details
    assert not conflict_run[1].verifier_result.conflict_details


# -----------------------------------------------------------------------
# Uncertainty
# -----------------------------------------------------------------------

def test_insufficient_evidence_is_stated_explicitly() -> None:
    pipeline = Pipeline()                      # stub KBs: nothing retrieved
    record = pipeline.run_chunk(get_chunks()[0])
    a = record.coordinator_assessment
    assert not a.evidence_backed_conclusions
    assert a.open_questions[0].startswith("No conclusion is evidence-backed")
    assert all("insufficient evidence" in u for u in a.uncertain_conclusions
               if "| UNSUPPORTED" in u)


# -----------------------------------------------------------------------
# Progressive reassessment
# -----------------------------------------------------------------------

@pytest.fixture(scope="module")
def stub_run():
    pipeline = Pipeline()
    return [pipeline.run_chunk(c).coordinator_assessment for c in get_chunks()]


def test_confirmed_facts_accumulate(stub_run) -> None:
    for earlier, later in zip(stub_run, stub_run[1:]):
        assert later.confirmed_facts[:len(earlier.confirmed_facts)] == earlier.confirmed_facts


def test_earlier_conclusions_are_carried_forward_visibly(stub_run) -> None:
    t2 = stub_run[2]                            # technical/cyber/standards not active
    carried = [r for r in t2.claim_register if r["carried_forward"]]
    assert {r["agent_id"] for r in carried} == {"technical", "cybersecurity", "standards"}
    assert any(u.startswith("[carried forward from scenario2_T1") for u in t2.uncertain_conclusions)
    assert any("carried forward, not re-examined" in c for c in t2.changes_from_prior)


def test_changes_report_only_what_changed(stub_run) -> None:
    t1, t2, t3 = (" ".join(a.changes_from_prior) for a in stub_run[1:])
    assert "possible security event" in t1
    assert "Critical-service relevance" in t2 and "personal-data" in t2
    # T3 releases no new security indicator: no reclassification may be claimed
    assert "possible security event" not in t3
    assert "Standards" not in t3


# -----------------------------------------------------------------------
# Live knowledge bases
# -----------------------------------------------------------------------

def _built() -> bool:
    from src.rag.manifest import ALL_KBS, KB_ROOT
    from src.rag.vector_store import VectorStore
    return all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS)


@pytest.mark.skipif(not _built(), reason="knowledge bases not built")
def test_live_four_stage_cross_domain_chain() -> None:
    from src.rag.registry import build_registry
    pipeline = Pipeline(build_registry())
    records = [pipeline.run_chunk(c) for c in get_chunks()]
    t3 = records[3].verifier_result

    kinds = {(l.kind, frozenset(a.value for a in l.agents)) for l in t3.cross_domain_details}
    # TCS Rules (Cybersecurity) are made under the Telecommunications Act (CII / Policy & Legal)
    assert ("instrument_basis", frozenset({"cybersecurity", "critical_infrastructure"})) in kinds
    # Telecom security-incident reporting and DPDP breach intimation run in parallel
    assert ("parallel_reporting", frozenset({"cybersecurity", "privacy"})) in kinds
    basis = next(l for l in t3.cross_domain_details if l.kind == "instrument_basis"
                 and AgentID.CYBERSECURITY in l.agents)
    assert "section 22" in basis.evidence[0].excerpt.lower()

    # Earlier chunks take part: T2 privacy findings link to T1 cybersecurity findings
    t2_links = records[2].verifier_result.cross_domain_details
    assert any(m.chunk_id == "scenario2_T1" for l in t2_links for m in l.members)

    # The corpus holds no disagreeing provisions, and nothing unchecked is VERIFIED
    for r in records:
        assert not r.verifier_result.conflict_details
        assert all(vc.outcome != VerifierOutcome.VERIFIED for vc in r.verifier_result.verified_claims)
    assert records[3].coordinator_assessment.potential_policy_gaps
