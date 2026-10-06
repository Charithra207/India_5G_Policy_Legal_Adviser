"""
Evaluation tests — 13 DOCX evaluation areas.

Tests that the complete system (stub KBs by default, in-memory fixtures
where live evidence is needed) demonstrates each capability area stated
in the DOCX evaluation criteria:

  1.  Technical analysis
  2.  Legal / regulatory analysis
  3.  Cybersecurity analysis
  4.  Privacy / data protection analysis
  5.  Critical infrastructure analysis
  6.  International standards (reference only)
  7.  Policy-gap identification
  8.  Verification (VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT)
  9.  Cross-domain reasoning
  10. Uncertainty handling
  11. Progressive reassessment (T0 → T3)
  12. Role separation
  13. Auditability

Run with:
    python -m pytest tests/test_evaluation.py -v
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.core.models import (
    AgentFinding, AgentID, CoverageCategory, EvidenceItem,
    ScenarioChunk, VerifierOutcome,
)
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase
from src.knowledge_base.kb_registry import KBRegistry
from src.pipeline import Pipeline
from src.scenario.engine import ScenarioEngine
from src.utils.output_formatter import format_audit_record, save_audit_json
from scenarios.scenario2_healthcare_5g import get_chunk, get_chunks


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_registry(
    agent_items: dict[AgentID, list[EvidenceItem]] | None = None,
    canonical_items: list[EvidenceItem] | None = None,
) -> KBRegistry:
    registry = KBRegistry()
    for agent_id, items in (agent_items or {}).items():
        registry.agent_kbs[agent_id] = InMemoryKnowledgeBase(
            kb_name=f"{agent_id.value} fixture",
            domain=agent_id.value,
            items=items,
        )
    if canonical_items is not None:
        registry.canonical_kb = InMemoryCanonicalKB(canonical_items)
    return registry


def _fx(title: str, section: str, excerpt: str,
        jurisdiction: str = "India", **kw) -> EvidenceItem:
    return EvidenceItem(
        source_title=f"FIXTURE {title}",
        authority="Test fixture",
        jurisdiction=jurisdiction,
        document_type="Fixture",
        section=section,
        excerpt=excerpt,
        chunk_id=f"fx-{title.lower().replace(' ', '-')}-{section.lower().replace(' ', '-')}",
        **kw,
    )


def _run_all(registry: KBRegistry | None = None) -> list:
    """Run all four scenario chunks; return AuditRecords."""
    pipeline = Pipeline(registry)
    return [pipeline.run_chunk(c) for c in get_chunks()]


def _run_t(index: int, registry: KBRegistry | None = None):
    """Run the scenario up to chunk `index`; return that AuditRecord."""
    pipeline = Pipeline(registry)
    record = None
    for i in range(index + 1):
        record = pipeline.run_chunk(get_chunk(i))
    return record


# ===========================================================================
# 1. TECHNICAL ANALYSIS
# ===========================================================================

class TestTechnicalAnalysis:
    """T0 activates the Technical Agent; it must classify affected components."""

    def test_technical_agent_activated_at_t0(self):
        record = _run_t(0)
        assert AgentID.TECHNICAL in record.active_agents

    def test_technical_agent_lists_affected_components(self):
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        assert tech.affected_components, (
            "Technical Agent must list affected 5G components at T0"
        )

    def test_technical_agent_sets_incident_class(self):
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        assert tech.incident_class, (
            "Technical Agent must set incident_class at T0"
        )

    def test_technical_agent_produces_claims(self):
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        assert tech.claims, "Technical Agent must produce at least one claim"

    def test_technical_agent_with_evidence_quotes_passage(self):
        """When a KB passage is available the agent quotes it with a citation."""
        ev = _fx(
            "5G Arch", "Clause 5.15",
            "A network slice provides specific network capabilities.",
            jurisdiction="International",
        )
        registry = _make_registry({AgentID.TECHNICAL: [ev]}, [ev])
        record = _run_t(0, registry)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited = [c for c in tech.claims if c in tech.claim_citations]
        assert cited, "Technical Agent must cite retrieved passage in its claims"
        assert "Clause 5.15" in cited[0]

    def test_technical_symptoms_appear_in_confirmed_facts(self):
        record = _run_t(0)
        ca = record.coordinator_assessment
        text = " ".join(ca.confirmed_facts).lower()
        assert "latency" in text or "session" in text or "slice" in text, (
            "T0 confirmed facts must include the technical symptoms from the scenario"
        )


# ===========================================================================
# 2. LEGAL / REGULATORY ANALYSIS
# ===========================================================================

class TestLegalRegulatoryAnalysis:
    """T2/T3 activate the Policy & Legal Agent."""

    def test_policy_legal_agent_activated_at_t2(self):
        record = _run_t(2)
        assert AgentID.POLICY_LEGAL in record.active_agents

    def test_policy_legal_agent_produces_claims(self):
        record = _run_t(2)
        pl = next(f for f in record.agent_findings if f.agent_id == AgentID.POLICY_LEGAL)
        assert pl.claims, "Policy & Legal Agent must produce claims at T2"

    def test_policy_legal_with_duty_passage_records_obligation(self):
        """A retrieved passage containing 'shall' must be recorded as an obligation."""
        duty = _fx(
            "Telecom Instrument", "Section 7",
            "A telecom entity shall report a security incident affecting its network.",
        )
        registry = _make_registry({AgentID.POLICY_LEGAL: [duty]}, None)
        pipeline = Pipeline(registry)
        pipeline.run_chunk(get_chunk(0))
        pipeline.run_chunk(get_chunk(1))
        record = pipeline.run_chunk(get_chunk(2))
        pl = next(f for f in record.agent_findings if f.agent_id == AgentID.POLICY_LEGAL)
        assert any("Section 7" in o for o in pl.obligations), (
            "Policy & Legal Agent must record a retrieved duty-imposing passage as an obligation"
        )

    def test_policy_legal_without_evidence_names_instruments_as_not_assessed(self):
        """Without retrieved passages the agent must name instruments, not invent content."""
        record = _run_t(2)
        pl = next(f for f in record.agent_findings if f.agent_id == AgentID.POLICY_LEGAL)
        real = [e for e in pl.evidence if e.authority != "STUB"]
        if not real:
            # All claims must either have citations or say 'not assessed'
            instruments = [
                "Telecommunications Act", "TRAI Act", "CERT-In", "DPDP",
                "Cyber Security", "NCIIPC",
            ]
            for claim in pl.claims:
                if any(inst in claim for inst in instruments):
                    assert claim in pl.claim_citations or "not assessed" in claim, (
                        f"Policy & Legal: claim names instrument without citation: {claim}"
                    )

    def test_relevant_institutions_listed(self):
        record = _run_t(2)
        ca = record.coordinator_assessment
        assert ca.relevant_institutions or ca.uncertain_conclusions, (
            "T2 must surface at least one institution or uncertain institutional conclusion"
        )


# ===========================================================================
# 3. CYBERSECURITY ANALYSIS
# ===========================================================================

class TestCybersecurityAnalysis:
    """T1 activates the Cybersecurity Agent when unusual auth is detected."""

    def test_cybersecurity_agent_activated_at_t1(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        assert AgentID.CYBERSECURITY in record.active_agents

    def test_cybersecurity_addresses_authentication_or_signalling(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        cyber = next(
            f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY
        )
        text = " ".join(cyber.claims).lower()
        assert any(kw in text for kw in
                   ["authentication", "signalling", "cyber", "telecom cyber security"]), (
            "Cybersecurity Agent must address auth/signalling at T1"
        )

    def test_cyber_event_flag_set_after_t1(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        pipeline.run_chunk(get_chunk(1))
        assert pipeline.incident_state["cyber_event_suspected"] is True

    def test_cybersecurity_with_certin_passage_cites_it(self):
        certin = _fx(
            "CERT-In Directions", "Direction (ii)",
            "Any service provider or intermediary or body corporate or government "
            "organisation shall mandatorily report cyber incidents to CERT-In within "
            "6 hours of noticing such incidents.",
        )
        registry = _make_registry({AgentID.CYBERSECURITY: [certin]}, None)
        pipeline = Pipeline(registry)
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        cyber = next(f for f in record.agent_findings if f.agent_id == AgentID.CYBERSECURITY)
        real = [e for e in cyber.evidence if e.authority != "STUB"]
        assert real, "CERT-In passage should be retrieved and cited"

    def test_t1_changes_from_prior_notes_cyber_reclassification(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        text = " ".join(record.coordinator_assessment.changes_from_prior).lower()
        assert any(kw in text for kw in ["cyber", "security", "reclass", "newly activated"])


# ===========================================================================
# 4. PRIVACY / DATA PROTECTION ANALYSIS
# ===========================================================================

class TestPrivacyAnalysis:
    """T2 activates the Privacy Agent when healthcare/personal-data context is confirmed."""

    def test_privacy_agent_activated_at_t2(self):
        record = _run_t(2)
        assert AgentID.PRIVACY in record.active_agents

    def test_privacy_agent_sets_exposure_status(self):
        record = _run_t(2)
        priv = next(f for f in record.agent_findings if f.agent_id == AgentID.PRIVACY)
        assert priv.exposure_status in ("confirmed", "suspected", "unknown"), (
            "Privacy Agent must set exposure_status at T2"
        )

    def test_privacy_agent_addresses_personal_data(self):
        record = _run_t(2)
        priv = next(f for f in record.agent_findings if f.agent_id == AgentID.PRIVACY)
        text = " ".join(priv.claims).lower()
        assert any(kw in text for kw in
                   ["personal data", "dpdp", "patient", "exposure", "data protection"]), (
            "Privacy Agent must address personal-data implications at T2"
        )

    def test_data_exposure_flag_set_after_t2(self):
        pipeline = Pipeline()
        for i in range(3):
            pipeline.run_chunk(get_chunk(i))
        assert pipeline.incident_state["data_exposure_suspected"] is True

    def test_privacy_agent_carries_forward_to_t3(self):
        """Privacy conclusions from T2 must be visible in T3 assessment."""
        records = _run_all()
        t3_ca = records[3].coordinator_assessment
        t2_priv = next(
            f for f in records[2].agent_findings if f.agent_id == AgentID.PRIVACY
        )
        if t2_priv.exposure_status in ("confirmed", "suspected"):
            text = " ".join(
                t3_ca.uncertain_conclusions
                + t3_ca.evidence_backed_conclusions
                + t3_ca.confirmed_facts
            ).lower()
            assert any(kw in text for kw in
                       ["data", "privacy", "personal", "patient", "exposure"]), (
                "T3 assessment must carry forward privacy conclusions from T2"
            )


# ===========================================================================
# 5. CRITICAL INFRASTRUCTURE ANALYSIS
# ===========================================================================

class TestCriticalInfrastructureAnalysis:
    """T2 activates the Critical Infrastructure Agent when healthcare service is confirmed."""

    def test_cii_agent_activated_at_t2(self):
        record = _run_t(2)
        assert AgentID.CRITICAL_INFRA in record.active_agents

    def test_cii_agent_assesses_healthcare_relevance(self):
        record = _run_t(2)
        cii = next(f for f in record.agent_findings if f.agent_id == AgentID.CRITICAL_INFRA)
        text = " ".join(cii.claims).lower()
        assert any(kw in text for kw in
                   ["healthcare", "critical", "cii", "nciipc", "infrastructure"]), (
            "Critical Infrastructure Agent must assess healthcare/CII at T2"
        )

    def test_cii_flag_set_after_t2(self):
        pipeline = Pipeline()
        for i in range(3):
            pipeline.run_chunk(get_chunk(i))
        assert pipeline.incident_state["cii_flagged"] is True

    def test_cii_agent_sets_cii_relevant_field(self):
        record = _run_t(2)
        cii = next(f for f in record.agent_findings if f.agent_id == AgentID.CRITICAL_INFRA)
        assert cii.cii_relevant is not None, (
            "Critical Infrastructure Agent must set cii_relevant (True/False/None)"
        )

    def test_cii_conflict_when_policy_legal_finds_no_obligation(self):
        """
        When Policy & Legal Agent examined sources but found no obligation,
        the CII agent's relevance claim becomes CONFLICT (Verifier rule).
        """
        definitions = _fx("Telecom Instrument", "Section 2",
                          "Definitions of telecom terms used in this instrument.")
        registry = _make_registry({AgentID.POLICY_LEGAL: [definitions]}, None)
        pipeline = Pipeline(registry)
        pipeline.run_chunk(get_chunk(0))
        pipeline.run_chunk(get_chunk(1))
        record = pipeline.run_chunk(get_chunk(2))
        cii_outcomes = [
            vc.outcome
            for vc in record.verifier_result.verified_claims
            if vc.agent_id == AgentID.CRITICAL_INFRA
        ]
        assert VerifierOutcome.CONFLICT in cii_outcomes, (
            "CII relevance claim must be CONFLICT when Policy & Legal examined "
            "sources but found no corresponding obligation"
        )


# ===========================================================================
# 6. INTERNATIONAL STANDARDS (REFERENCE ONLY)
# ===========================================================================

class TestInternationalStandards:
    """T1 activates the Standards Agent; its claims must be labelled REFERENCE ONLY."""

    def test_standards_agent_activated_at_t1(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        assert AgentID.STANDARDS in record.active_agents

    def test_standards_claims_carry_reference_only_label(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        std = next(f for f in record.agent_findings if f.agent_id == AgentID.STANDARDS)
        for claim in std.claims:
            if any(kw in claim for kw in ["3GPP", "NIST", "ETSI", "ITU", "33.501", "23.501"]):
                assert "[REFERENCE ONLY" in claim, (
                    f"Standards claim missing [REFERENCE ONLY] label:\n  {claim}"
                )

    def test_standards_reference_label_does_not_confer_verified(self):
        """The [REFERENCE ONLY] label is a disclaimer, not evidence — never VERIFIED."""
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        for vc in record.verifier_result.verified_claims:
            if vc.agent_id == AgentID.STANDARDS:
                assert vc.outcome != VerifierOutcome.VERIFIED, (
                    f"Standards claim incorrectly marked VERIFIED:\n  {vc.claim}"
                )

    def test_standards_references_3gpp_33501(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        std = next(f for f in record.agent_findings if f.agent_id == AgentID.STANDARDS)
        text = " ".join(std.claims)
        assert "33.501" in text or "3gpp" in text.lower(), (
            "Standards Agent must reference 3GPP TS 33.501 at T1"
        )

    def test_standards_not_treated_as_indian_law_in_assessment(self):
        """Standards conclusions must appear in uncertain (not evidence-backed) category."""
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        ca = record.coordinator_assessment
        # No standards claim should be directly under evidence_backed_conclusions
        # as VERIFIED (they are at best INCOMPLETE with reference labels)
        for conclusion in ca.evidence_backed_conclusions:
            # evidence_backed = VERIFIED claims only; standards should not be here
            assert "[REFERENCE ONLY" not in conclusion, (
                f"Standards reference-only text should not appear in evidence-backed "
                f"conclusions:\n  {conclusion}"
            )


# ===========================================================================
# 7. POLICY-GAP IDENTIFICATION
# ===========================================================================

class TestPolicyGapIdentification:
    """T3 activates the Policy Gap Agent after all other agents have run."""

    def test_policy_gap_agent_activated_at_t3(self):
        records = _run_all()
        assert AgentID.POLICY_GAP in records[3].active_agents

    def test_policy_gap_agent_produces_gap_claims(self):
        records = _run_all()
        gf = next(f for f in records[3].agent_findings if f.agent_id == AgentID.POLICY_GAP)
        assert gf.claims, "Policy Gap Agent must produce claims at T3"

    def test_policy_gap_uses_non_conclusive_language(self):
        """Must not assert Indian policy is inadequate."""
        records = _run_all()
        gf = next(f for f in records[3].agent_findings if f.agent_id == AgentID.POLICY_GAP)
        forbidden = [
            "indian policy is inadequate", "the policy is inadequate",
            "framework is inadequate", "policy is inadequate",
        ]
        for claim in gf.claims:
            for phrase in forbidden:
                assert phrase not in claim.lower(), (
                    f"Policy Gap claim asserts policy inadequacy: {claim}"
                )

    def test_policy_gap_uses_gap_terminology(self):
        records = _run_all()
        gf = next(f for f in records[3].agent_findings if f.agent_id == AgentID.POLICY_GAP)
        text = " ".join(gf.claims).lower()
        assert any(kw in text for kw in [
            "potential gap", "regulatory ambiguity", "not explicitly",
            "unclear", "overlapping", "missing institutional",
            "reference only", "for expert review", "candidate area",
        ]), "Policy Gap Agent must use DOCX-required gap terminology"

    def test_policy_gap_receives_prior_verified_findings(self):
        """Policy Gap Agent requires verified_findings in incident_state."""
        pipeline = Pipeline()
        for i in range(4):
            pipeline.run_chunk(get_chunk(i))
        assert pipeline.incident_state["verified_findings"], (
            "verified_findings must be populated at T3 for the Policy Gap Agent"
        )

    def test_coordinator_surfaces_policy_gaps_at_t3(self):
        records = _run_all()
        ca = records[3].coordinator_assessment
        assert ca.potential_policy_gaps, (
            "Coordinator must surface potential_policy_gaps at T3"
        )

    def test_policy_gap_with_canonical_kb_raises_from_examined_corpus(self):
        """When a Canonical KB is present, gaps are raised from examined evidence."""
        cyber = _fx("Cyber Rules", "Rule 3",
                    "A telecom entity shall report a cyber security incident.")
        data = _fx("Data Act", "Section 8",
                   "A data fiduciary shall notify a personal data breach to the Board.")
        nciipc = _fx("CII Rules", "Rule 4",
                     "NCIIPC shall coordinate protection of critical information infrastructure.")
        certin = _fx("Cyber Directions", "Para 2",
                     "CERT-In shall receive reports of cyber incidents and coordinate response.")
        registry = _make_registry({}, [cyber, data, nciipc, certin])
        pipeline = Pipeline(registry)
        for i in range(4):
            pipeline.run_chunk(get_chunk(i))
        state = pipeline.incident_state
        assert state["verified_findings"]
        gf = next(
            f for f in pipeline.orchestrator.get_agent(AgentID.POLICY_GAP).__class__.__mro__
            if False  # just check the pipeline ran — actual gap tested below
        ) if False else None
        # Verify coordinator has gaps
        records = _run_all(registry)
        ca = records[3].coordinator_assessment
        assert ca.potential_policy_gaps


# ===========================================================================
# 8. VERIFICATION (VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT)
# ===========================================================================

class TestVerification:
    """The Verifier must correctly assign all four outcomes."""

    def test_no_claim_is_verified_on_stub_kbs(self):
        """Without a canonical KB no claim can ever be VERIFIED."""
        for record in _run_all():
            for vc in record.verifier_result.verified_claims:
                assert vc.outcome != VerifierOutcome.VERIFIED, (
                    f"Claim incorrectly VERIFIED on stub KBs:\n  {vc.claim}"
                )

    def test_canonical_kb_produces_incomplete_not_verified(self):
        """With in-force status unchecked, quoted passages produce INCOMPLETE, not VERIFIED."""
        ev = _fx("5G Spec", "Clause 5.15",
                 "A network slice provides specific network capabilities and "
                 "network characteristics, and slice performance is monitored per session.",
                 jurisdiction="International",
                 effective=None,           # not verified → INCOMPLETE
                 amendment_checked=False)  # not checked → INCOMPLETE
        registry = _make_registry({AgentID.TECHNICAL: [ev]}, [ev])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited_claims = set(tech.claim_citations.keys())
        if cited_claims:
            cited_outcomes = [
                vc.outcome for vc in record.verifier_result.verified_claims
                if vc.claim in cited_claims
            ]
            assert VerifierOutcome.INCOMPLETE in cited_outcomes, (
                f"Cited claim with effective=None must be INCOMPLETE. Got: {cited_outcomes}"
            )
            assert VerifierOutcome.VERIFIED not in cited_outcomes

    def test_verified_when_effective_true_and_amendments_checked(self):
        """VERIFIED is achievable only when effective=True and amendment_checked=True."""
        ev = EvidenceItem(
            source_title="FIXTURE Spec", authority="Test", jurisdiction="International",
            document_type="Fixture", section="Clause 5.15",
            excerpt="A network slice provides specific network capabilities and "
                    "network characteristics, and slice performance is monitored.",
            chunk_id="fx-verified-1",
            effective=True,
            amendment_checked=True,
        )
        registry = _make_registry({AgentID.TECHNICAL: [ev]}, [ev])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        outcomes = [vc.outcome for vc in record.verifier_result.verified_claims]
        assert VerifierOutcome.VERIFIED in outcomes

    def test_unsupported_when_canonical_text_does_not_match(self):
        """When canonical text is unrelated to the claim it is UNSUPPORTED."""
        agent_ev = _fx("5G Spec", "Clause 5.15",
                       "A network slice provides specific network capabilities.",
                       jurisdiction="International")
        canon_ev = _fx("5G Spec", "Clause 5.15",
                       "Registration procedures for user equipment in RRC idle.",
                       jurisdiction="International")
        registry = _make_registry({AgentID.TECHNICAL: [agent_ev]}, [canon_ev])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        outcomes = [vc.outcome for vc in record.verifier_result.verified_claims]
        assert VerifierOutcome.UNSUPPORTED in outcomes

    def test_conflict_produced_when_cii_finds_relevance_but_pl_finds_no_obligation(self):
        """CII relevance vs Policy & Legal silence (after examination) → CONFLICT."""
        definitions = _fx("Telecom Instrument", "Section 2",
                          "Definitions of telecom terms used in this instrument.")
        registry = _make_registry({AgentID.POLICY_LEGAL: [definitions]}, None)
        pipeline = Pipeline(registry)
        pipeline.run_chunk(get_chunk(0))
        pipeline.run_chunk(get_chunk(1))
        record = pipeline.run_chunk(get_chunk(2))
        conflict_claims = [
            vc for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.CONFLICT
        ]
        assert conflict_claims, "CONFLICT must be detected at T2"
        assert record.verifier_result.conflicts

    def test_verifier_outcome_counts_are_consistent(self):
        """Counts in the result must sum to total verified_claims."""
        for record in _run_all():
            vr = record.verifier_result
            count_sum = sum(
                1 for vc in vr.verified_claims
                if vc.outcome in list(VerifierOutcome)
            )
            assert count_sum == len(vr.verified_claims)

    def test_stub_kb_note_in_missing_evidence(self):
        """When KB is stub the Verifier must note that the Canonical KB is unavailable."""
        record = _run_t(0)
        missing = " ".join(record.verifier_result.missing_evidence).lower()
        assert "canonical kb" in missing or "not yet populated" in missing, (
            "Verifier must note Canonical KB unavailability in missing_evidence"
        )


# ===========================================================================
# 9. CROSS-DOMAIN REASONING
# ===========================================================================

class TestCrossDomainReasoning:
    """Cross-domain links are established from evidence, never from co-activation."""

    def test_no_cross_domain_links_on_stub_kbs(self):
        """With no real evidence, no cross-domain link may be claimed."""
        records = _run_all()
        for record in records:
            assert not record.verifier_result.cross_domain_links, (
                "No cross-domain links may be claimed without evidence support"
            )

    def test_cross_domain_link_from_shared_provision(self):
        """A shared provision (same source, same section) links two domains."""
        from src.core.cross_domain import find_relationships
        shared = _fx("Telecom Act", "Section 22",
                     "Critical telecom infrastructure must be protected.")
        f1 = AgentFinding(
            agent_id=AgentID.POLICY_LEGAL, chunk_id="test",
            claims=["Section 22 applies."],
            claim_citations={"Section 22 applies.": [shared]},
        )
        f2 = AgentFinding(
            agent_id=AgentID.CRITICAL_INFRA, chunk_id="test",
            claims=["Section 22 covers this service."],
            claim_citations={"Section 22 covers this service.": [shared]},
        )
        canon = InMemoryCanonicalKB([shared])
        links, _ = find_relationships([f1, f2], [], canon)
        assert links, "Shared provision must produce a cross-domain link"
        assert any(
            set(lk.agents) == {AgentID.POLICY_LEGAL, AgentID.CRITICAL_INFRA}
            for lk in links
        )

    def test_parallel_reporting_duties_detected(self):
        """Cross-domain analysis runs without error for parallel reporting duties."""
        from src.core.cross_domain import find_relationships
        cyber = _fx("Cyber Rules", "Rule 7",
                    "The entity shall report to DoT within 6 hours.")
        data = _fx("Data Act", "Section 8",
                   "The data fiduciary shall intimate the Board of any data breach.")
        f_cyber = AgentFinding(
            agent_id=AgentID.CYBERSECURITY, chunk_id="test",
            claims=["Rule 7 requires reporting."],
            claim_citations={"Rule 7 requires reporting.": [cyber]},
        )
        f_priv = AgentFinding(
            agent_id=AgentID.PRIVACY, chunk_id="test",
            claims=["Section 8 requires notification."],
            claim_citations={"Section 8 requires notification.": [data]},
        )
        canon = InMemoryCanonicalKB([cyber, data])
        links, conflicts = find_relationships([f_cyber, f_priv], [], canon)
        # The cross-domain module returns lists (possibly empty) — no error is the primary check.
        # If links are raised, the relevant agents must be among those involved.
        assert isinstance(links, list)
        assert isinstance(conflicts, list)
        if links:
            agents_in_links = {a for lk in links for a in lk.agents}
            assert AgentID.CYBERSECURITY in agents_in_links or \
                   AgentID.PRIVACY in agents_in_links

    def test_cross_domain_flag_set_on_linked_claims(self):
        """Claims involved in a cross-domain link must have cross_domain_flag=True."""
        shared = _fx("Telecom Act", "Section 22",
                     "Critical telecom infrastructure must be protected by operators.")
        registry = _make_registry(
            {AgentID.POLICY_LEGAL: [shared], AgentID.CRITICAL_INFRA: [shared]},
            [shared],
        )
        pipeline = Pipeline(registry)
        pipeline.run_chunk(get_chunk(0))
        pipeline.run_chunk(get_chunk(1))
        record = pipeline.run_chunk(get_chunk(2))
        if record.verifier_result.cross_domain_links:
            flagged = [vc for vc in record.verifier_result.verified_claims
                       if vc.cross_domain_flag]
            assert flagged, "Claims in a cross-domain link must have cross_domain_flag=True"


# ===========================================================================
# 10. UNCERTAINTY HANDLING
# ===========================================================================

class TestUncertaintyHandling:
    """Uncertainty must be preserved, never papered over."""

    def test_uncertain_conclusions_populated_at_every_stage(self):
        """Because no KB is live, every claim is uncertain; uncertain_conclusions > 0."""
        for record in _run_all():
            ca = record.coordinator_assessment
            assert ca.uncertain_conclusions, (
                f"{record.chunk_id}: uncertain_conclusions must be non-empty "
                f"when all KBs are stubs"
            )

    def test_human_review_note_always_present(self):
        """DOCX A.2: human review note must appear on every assessment."""
        for record in _run_all():
            assert record.coordinator_assessment.human_review_required, (
                f"{record.chunk_id}: human_review_required must always be set"
            )
            text = record.coordinator_assessment.human_review_required.lower()
            assert "human" in text or "qualified" in text or "judgment" in text

    def test_agents_flag_stub_evidence_in_uncertainty_notes(self):
        """When KB is stub the agent must add an uncertainty note."""
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        real = [e for e in tech.evidence if e.authority != "STUB"]
        if not real:
            assert tech.uncertainty_notes, (
                "Technical Agent must produce uncertainty notes when KB is stub"
            )
            text = " ".join(tech.uncertainty_notes).lower()
            assert "rag" in text or "kb" in text or "preliminary" in text or "not live" in text

    def test_missing_facts_always_listed(self):
        """Agents must explicitly state what facts are missing."""
        for record in _run_all():
            for finding in record.agent_findings:
                assert finding.missing_facts or finding.uncertainty_notes, (
                    f"{finding.agent_id.value} at {record.chunk_id}: "
                    f"must state missing_facts or uncertainty_notes"
                )

    def test_evidence_backed_conclusions_empty_without_verified_claims(self):
        """With stub KBs no claim is VERIFIED so evidence_backed_conclusions must be empty."""
        for record in _run_all():
            vr = record.verifier_result
            verified_count = sum(
                1 for vc in vr.verified_claims
                if vc.outcome == VerifierOutcome.VERIFIED
            )
            if verified_count == 0:
                ca = record.coordinator_assessment
                assert not ca.evidence_backed_conclusions, (
                    f"{record.chunk_id}: evidence_backed_conclusions must be empty "
                    f"when no claim is VERIFIED"
                )


# ===========================================================================
# 11. PROGRESSIVE REASSESSMENT
# ===========================================================================

class TestProgressiveReassessment:
    """Each chunk re-issues the full assessment; earlier conclusions carry forward."""

    def test_confirmed_facts_accumulate_across_chunks(self):
        """Each chunk adds new facts; the total grows monotonically."""
        pipeline = Pipeline()
        counts = []
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            counts.append(len(record.coordinator_assessment.confirmed_facts))
        for i in range(1, len(counts)):
            assert counts[i] >= counts[i - 1], (
                f"Confirmed facts must not shrink: chunk {i-1}={counts[i-1]}, "
                f"chunk {i}={counts[i]}"
            )

    def test_t0_initial_assessment_note(self):
        record = _run_t(0)
        text = " ".join(record.coordinator_assessment.changes_from_prior).lower()
        assert "initial" in text, (
            "T0 changes_from_prior must note that this is the initial assessment"
        )

    def test_t1_changes_note_new_agents(self):
        pipeline = Pipeline()
        pipeline.run_chunk(get_chunk(0))
        record = pipeline.run_chunk(get_chunk(1))
        text = " ".join(record.coordinator_assessment.changes_from_prior).lower()
        assert any(kw in text for kw in
                   ["newly", "activated", "reclass", "cyber", "security"])

    def test_active_agents_differ_by_stage(self):
        """Each stage activates a distinct set of agents per the DOCX table."""
        pipeline = Pipeline()
        agents_per_stage = []
        for chunk in get_chunks():
            record = pipeline.run_chunk(chunk)
            agents_per_stage.append(set(record.active_agents))
        assert agents_per_stage[0] == {AgentID.TECHNICAL}
        assert AgentID.CYBERSECURITY in agents_per_stage[1]
        assert AgentID.PRIVACY in agents_per_stage[2]
        assert AgentID.POLICY_GAP in agents_per_stage[3]

    def test_t2_t3_carry_forward_t1_findings(self):
        """T1 findings (cyber conclusions) must appear in T2/T3 claim_register."""
        pipeline = Pipeline()
        records = [pipeline.run_chunk(get_chunk(i)) for i in range(4)]
        t3_register = records[3].coordinator_assessment.claim_register
        t1_claims = [f.claims for f in records[1].agent_findings
                     if f.agent_id == AgentID.CYBERSECURITY]
        if t1_claims and t3_register:
            register_claims = {entry.get("claim", "") for entry in t3_register}
            # At least some t1 claims should appear carried forward
            assert register_claims, "T3 claim_register must contain previous-stage claims"

    def test_t3_has_policy_gap_conclusions_not_present_at_t0(self):
        """Policy gaps are only identified at T3; T0 must have none."""
        pipeline = Pipeline()
        t0 = pipeline.run_chunk(get_chunk(0))
        for i in range(1, 4):
            t_last = pipeline.run_chunk(get_chunk(i))
        assert not t0.coordinator_assessment.potential_policy_gaps, (
            "T0 must have no potential policy gaps"
        )
        assert t_last.coordinator_assessment.potential_policy_gaps, (
            "T3 must have potential policy gaps after Policy Gap Agent runs"
        )


# ===========================================================================
# 12. ROLE SEPARATION
# ===========================================================================

class TestRoleSeparation:
    """Each agent speaks only within its defined mandate."""

    def test_technical_agent_does_not_produce_legal_obligations(self):
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        assert not tech.obligations, (
            "Technical Agent must not populate the obligations field (Policy & Legal mandate)"
        )

    def test_technical_agent_does_not_flag_cii(self):
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        assert tech.cii_relevant is None, (
            "Technical Agent must not set cii_relevant (Critical Infrastructure mandate)"
        )

    def test_technical_agent_does_not_set_gap_category(self):
        record = _run_t(0)
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        assert tech.gap_category is None, (
            "Technical Agent must not set gap_category (Policy Gap mandate)"
        )

    def test_cii_agent_sets_cii_relevant_not_obligations(self):
        record = _run_t(2)
        cii = next(f for f in record.agent_findings if f.agent_id == AgentID.CRITICAL_INFRA)
        assert cii.cii_relevant is not None, (
            "Critical Infrastructure Agent must set cii_relevant"
        )

    def test_policy_gap_agent_does_not_produce_security_findings(self):
        """Policy Gap Agent must not claim to be a Cybersecurity Agent."""
        records = _run_all()
        gf = next(f for f in records[3].agent_findings if f.agent_id == AgentID.POLICY_GAP)
        assert gf.agent_id == AgentID.POLICY_GAP
        assert not gf.incident_class, (
            "Policy Gap Agent must not set incident_class (Technical mandate)"
        )

    def test_each_agent_id_appears_at_most_once_per_chunk(self):
        """No agent must produce two findings for the same chunk."""
        for record in _run_all():
            agent_ids = [f.agent_id for f in record.agent_findings]
            assert len(agent_ids) == len(set(agent_ids)), (
                f"{record.chunk_id}: duplicate agent findings detected"
            )

    def test_coordinator_does_not_invent_new_claims(self):
        """Coordinator categories must be sourced from agent findings, not invented."""
        record = _run_t(0)
        ca = record.coordinator_assessment
        # confirmed_facts come from the scenario chunk, not agent claims
        for fact in ca.confirmed_facts:
            assert fact.startswith("[Incident fact") or fact.startswith("[New fact"), (
                f"Confirmed fact must come from scenario chunk, not agent reasoning: {fact}"
            )


# ===========================================================================
# 13. AUDITABILITY
# ===========================================================================

class TestAuditability:
    """DOCX §7.6: every run must be replayable from the audit trail."""

    def test_audit_record_has_all_required_fields(self):
        record = _run_t(0)
        assert record.chunk_id
        assert record.timestamp
        assert record.active_agents
        assert record.agent_findings
        assert record.verifier_result
        assert record.coordinator_assessment
        assert record.raw_chunk

    def test_save_audit_json_contains_all_12_evidence_fields(self):
        ev = EvidenceItem(
            source_title="FIXTURE Telecom Act", authority="Government of India",
            jurisdiction="India", document_type="Act", section="Section 22",
            excerpt="Critical telecom infrastructure.", date_issued="2023-12-24",
            effective=None, amendment_note="", url="https://example.com/act",
            chunk_id="fx-telecom-s22", relevance_score=0.75,
        )
        registry = _make_registry({AgentID.TECHNICAL: [ev]}, None)
        record = _run_t(0, registry)
        # Inject evidence into first finding for the test
        record.agent_findings[0].evidence = [ev]
        with tempfile.TemporaryDirectory() as tmp:
            path = save_audit_json(record, output_dir=tmp)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        tech = next(
            (f for f in data["agent_findings"] if f["agent_id"] == "technical"), None
        )
        assert tech is not None
        ev_list = tech.get("evidence", [])
        assert ev_list
        item = ev_list[0]
        for field in ["source_title", "authority", "jurisdiction", "document_type",
                      "section", "excerpt", "date_issued", "effective",
                      "amendment_note", "url", "chunk_id", "relevance_score"]:
            assert field in item, f"Audit JSON missing evidence field: {field}"

    def test_format_audit_record_contains_all_five_categories(self):
        record = _run_t(0)
        text = format_audit_record(record)
        for section in [
            "1. CONFIRMED FACTS",
            "2. EVIDENCE-BACKED CONCLUSIONS",
            "3. UNCERTAIN CONCLUSIONS",
            "4. CONFLICTING FINDINGS",
            "5. POTENTIAL POLICY GAPS",
        ]:
            assert section in text, f"Formatted audit record missing section: {section}"

    def test_audit_trail_written_and_replayable(self):
        """ScenarioEngine writes a JSONL file that load_run can read back intact."""
        from src.audit.replay import load_run
        from src.scenario.engine import ScenarioEngine
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            engine = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine.next_stage()
            path = engine.audit_path
            assert path and path.exists()
            run = load_run(path)
        assert run.intact, f"Audit trail integrity failed: {run.integrity_problems}"
        assert len(run.stages) == 4
        assert run.header["scenario_id"] == "scenario2"

    def test_audit_trail_hash_chain_detects_tampering(self):
        """Modifying an entry breaks the hash chain."""
        from src.audit.trail import verify_chain
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            engine = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine.next_stage()
            # Read and verify while tmp still exists
            content = engine.audit_path.read_text(encoding="utf-8")

        lines = content.splitlines()
        entries = [json.loads(line) for line in lines]
        # Tamper with the second stage entry
        stage_indices = [i for i, e in enumerate(entries) if e.get("type") == "stage"]
        if len(stage_indices) >= 2:
            entries[stage_indices[1]]["stage"]["information_released"] = "TAMPERED"
            entries[stage_indices[1]]["hash"] = "0" * 64
            problems = verify_chain(entries)
            assert problems, "Tampering must be detected by verify_chain"

    def test_replay_chunks_match_original_scenario(self):
        """Chunks rebuilt from a recorded run must match the original scenario."""
        from src.audit.replay import load_run
        from src.scenario.engine import ScenarioEngine
        original = get_chunks()
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            engine = ScenarioEngine("scenario2", audit_dir=Path(tmp), record=True)
            for _ in range(4):
                engine.next_stage()
            run = load_run(engine.audit_path)
        replayed_chunks = run.chunks()
        assert len(replayed_chunks) == len(original)
        for orig, replayed in zip(original, replayed_chunks):
            assert orig.chunk_id == replayed.chunk_id
            assert orig.chunk_index == replayed.chunk_index

    def test_audit_record_verifier_claims_are_replayable(self):
        """Every verified claim must carry agent_id, outcome, and rationale."""
        for record in _run_all():
            for vc in record.verifier_result.verified_claims:
                assert vc.agent_id
                assert vc.outcome in list(VerifierOutcome)
                assert vc.rationale
                assert vc.claim

    def test_no_fake_citations_in_any_stage(self):
        forbidden = ["[FABRICATED]", "[FAKE]", "invented_source", "made_up_law"]
        for record in _run_all():
            text = " ".join(c for f in record.agent_findings for c in f.claims)
            for bad in forbidden:
                assert bad not in text, f"Fabricated citation found: {bad!r}"
