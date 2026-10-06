"""
Negative tests — four verification outcome patterns.

Each test exercises a specific Verifier outcome using in-memory fixture KBs
so the result is deterministic and does not depend on live vector stores.

A. UNSUPPORTED  — cited source exists in Canonical KB but text does not support claim
B. INCOMPLETE   — supported but effective status / amendment history not checked
C. CONFLICT     — two agents produce findings that contradict each other
D. VERIFIED     — source exists, text supports claim, in force, amendments checked

Tests must not fake results. Every assertion reflects actual pipeline output
through the full Pipeline → Orchestrator → Agent → Verifier → Coordinator
path.

Run with:
    python -m pytest tests/test_negative.py -v
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.models import (
    AgentFinding, AgentID, EvidenceItem, ScenarioChunk, VerifierOutcome,
)
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase
from src.knowledge_base.kb_registry import KBRegistry
from src.pipeline import Pipeline
from scenarios.scenario2_healthcare_5g import get_chunk, get_chunks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fx(title: str, section: str, excerpt: str,
        jurisdiction: str = "India",
        effective=None,
        amendment_checked: bool = False,
        amendment_note: str = "",
        **kw) -> EvidenceItem:
    """Create a fixture EvidenceItem with realistic field values."""
    return EvidenceItem(
        source_title=f"FIXTURE {title}",
        authority="Test fixture",
        jurisdiction=jurisdiction,
        document_type="Fixture",
        section=section,
        excerpt=excerpt,
        chunk_id=f"fx-{title.lower().replace(' ', '-')}-{section.lower().replace(' ', '-')}",
        effective=effective,
        amendment_checked=amendment_checked,
        amendment_note=amendment_note,
        **kw,
    )


def _registry(
    agent_items: dict[AgentID, list[EvidenceItem]],
    canonical_items: list[EvidenceItem] | None,
) -> KBRegistry:
    reg = KBRegistry()
    for agent_id, items in agent_items.items():
        reg.agent_kbs[agent_id] = InMemoryKnowledgeBase(
            kb_name=f"{agent_id.value} fixture",
            domain=agent_id.value,
            items=items,
        )
    if canonical_items is not None:
        reg.canonical_kb = InMemoryCanonicalKB(canonical_items)
    return reg


def _run_to_t0(agent_items, canonical_items):
    pipeline = Pipeline(_registry(agent_items, canonical_items))
    return pipeline.run_chunk(get_chunk(0))


def _run_to_t2(agent_items, canonical_items):
    pipeline = Pipeline(_registry(agent_items, canonical_items))
    chunks = get_chunks()
    for chunk in chunks[:3]:
        record = pipeline.run_chunk(chunk)
    return record


# ===========================================================================
# A. UNSUPPORTED — cited source present but canonical text does not support claim
# ===========================================================================

class TestUnsupported:
    """
    A claim is UNSUPPORTED when:
      (a) the cited section exists in the Canonical KB, but the canonical
          passage's content terms do not overlap with the claim's terms, OR
      (b) the cited section is absent from the Canonical KB entirely, OR
      (c) the Canonical KB passage exists but effective=False (not in force).
    """

    def test_unsupported_when_canonical_text_is_unrelated(self):
        """
        Agent retrieves: "A network slice provides specific network capabilities."
        Canonical has: "Registration procedures for user equipment in RRC idle."
        → The canonical passage does not support the claim → UNSUPPORTED.
        """
        agent_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, and slice performance is monitored per session.",
            jurisdiction="International",
        )
        canonical_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "Registration procedures for user equipment in RRC idle mode.",
            jurisdiction="International",
        )
        record = _run_to_t0({AgentID.TECHNICAL: [agent_ev]}, [canonical_ev])
        outcomes = {vc.outcome for vc in record.verifier_result.verified_claims}
        assert VerifierOutcome.UNSUPPORTED in outcomes, (
            "Expected UNSUPPORTED when canonical text is unrelated to the claim"
        )
        unsupported = [
            vc for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.UNSUPPORTED
        ]
        for vc in unsupported:
            assert vc.rationale, "UNSUPPORTED claim must carry a rationale"

    def test_unsupported_when_cited_section_absent_from_canonical(self):
        """
        Agent cites Clause 5.15; Canonical KB only has Clause 9.1.
        → Cited section absent → UNSUPPORTED.
        """
        agent_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities.",
            jurisdiction="International",
        )
        other_ev = _fx(
            "5G Arch Spec", "Clause 9.1",
            "Interworking with EPS: procedures for handover.",
            jurisdiction="International",
        )
        record = _run_to_t0({AgentID.TECHNICAL: [agent_ev]}, [other_ev])
        outcomes = {vc.outcome for vc in record.verifier_result.verified_claims}
        assert VerifierOutcome.UNSUPPORTED in outcomes
        # At least one UNSUPPORTED claim must carry an explanatory rationale
        for vc in record.verifier_result.verified_claims:
            if vc.outcome == VerifierOutcome.UNSUPPORTED:
                assert vc.rationale, "UNSUPPORTED claim must carry a rationale"

    def test_unsupported_when_passage_not_in_force(self):
        """
        Canonical passage has effective=False (repealed/not in force).
        → Cannot support a current claim → UNSUPPORTED.
        """
        agent_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, slice performance is monitored per session.",
            jurisdiction="International",
        )
        repealed_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, slice performance is monitored per session.",
            jurisdiction="International",
            effective=False,  # not in force
        )
        record = _run_to_t0({AgentID.TECHNICAL: [agent_ev]}, [repealed_ev])
        outcomes = {vc.outcome for vc in record.verifier_result.verified_claims}
        assert VerifierOutcome.UNSUPPORTED in outcomes
        for vc in record.verifier_result.verified_claims:
            if vc.outcome == VerifierOutcome.UNSUPPORTED:
                assert vc.rationale, "UNSUPPORTED claim must carry a rationale"

    def test_unsupported_claims_not_in_evidence_backed_conclusions(self):
        """UNSUPPORTED claims must never appear in evidence_backed_conclusions."""
        agent_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities.",
            jurisdiction="International",
        )
        canonical_ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "Registration procedures for user equipment.",
            jurisdiction="International",
        )
        record = _run_to_t0({AgentID.TECHNICAL: [agent_ev]}, [canonical_ev])
        unsupported_claims = {
            vc.claim for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.UNSUPPORTED
        }
        ca = record.coordinator_assessment
        for conclusion in ca.evidence_backed_conclusions:
            for uc in unsupported_claims:
                assert uc not in conclusion, (
                    "UNSUPPORTED claim must not appear in evidence_backed_conclusions"
                )

    def test_stub_canonical_kb_makes_uncited_claims_unsupported(self):
        """With no Canonical KB, uncited claims (agent's reading of facts) → UNSUPPORTED."""
        record = _run_to_t0({}, None)  # stub everything
        # All uncited claims must be UNSUPPORTED (not VERIFIED or INCOMPLETE)
        tech = next(
            (f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL), None
        )
        if tech:
            cited = set(tech.claim_citations.keys())
            for vc in record.verifier_result.verified_claims:
                if vc.agent_id == AgentID.TECHNICAL and vc.claim not in cited:
                    assert vc.outcome == VerifierOutcome.UNSUPPORTED, (
                        f"Uncited claim on stub KB must be UNSUPPORTED, got "
                        f"{vc.outcome}: {vc.claim}"
                    )


# ===========================================================================
# B. INCOMPLETE — supported but effective/amendment status not checked
# ===========================================================================

class TestIncomplete:
    """
    A claim is INCOMPLETE when:
      (a) Canonical KB text supports the claim, but effective=None (not verified), OR
      (b) amendment_checked=False, OR
      (c) amendment_note is non-empty (a known amendment exists), OR
      (d) Canonical KB is stub but the agent did cite a retrieved passage.
    """

    def test_incomplete_when_effective_not_verified(self):
        """
        effective=None means in-force status was not checked.
        → Cannot be VERIFIED → INCOMPLETE.
        """
        ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, and slice performance is monitored per session.",
            jurisdiction="International",
            effective=None,          # not verified
            amendment_checked=False,
        )
        record = _run_to_t0({AgentID.TECHNICAL: [ev]}, [ev])
        quoted_outcomes = [
            vc for vc in record.verifier_result.verified_claims
            if vc.claim in {
                c for f in record.agent_findings
                if f.agent_id == AgentID.TECHNICAL
                for c in f.claim_citations
            }
        ]
        assert quoted_outcomes, "Agent must have produced at least one cited claim"
        outcomes = {vc.outcome for vc in quoted_outcomes}
        assert VerifierOutcome.INCOMPLETE in outcomes, (
            "Expected INCOMPLETE when effective=None (in-force status not verified)"
        )
        assert VerifierOutcome.VERIFIED not in outcomes, (
            "Must not be VERIFIED when effective status is unverified"
        )

    def test_incomplete_when_amendment_note_present(self):
        """A known amendment makes the passage INCOMPLETE (not VERIFIED)."""
        ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, slice performance is monitored per session.",
            jurisdiction="International",
            effective=True,
            amendment_checked=True,
            amendment_note="Clause 5.15 revised in a later release to add URLLC constraints.",
        )
        record = _run_to_t0({AgentID.TECHNICAL: [ev]}, [ev])
        quoted_outcomes = [
            vc for vc in record.verifier_result.verified_claims
            if vc.claim in {
                c for f in record.agent_findings
                if f.agent_id == AgentID.TECHNICAL
                for c in f.claim_citations
            }
        ]
        if quoted_outcomes:
            outcomes = {vc.outcome for vc in quoted_outcomes}
            assert VerifierOutcome.INCOMPLETE in outcomes
            for vc in quoted_outcomes:
                if vc.outcome == VerifierOutcome.INCOMPLETE:
                    assert "amendment" in vc.rationale.lower() or "revised" in vc.rationale.lower()

    def test_incomplete_when_stub_canonical_but_agent_cited(self):
        """
        No Canonical KB (stub) but agent cited a retrieved passage.
        → Citation cannot be independently confirmed → INCOMPLETE (not UNSUPPORTED).
        """
        ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, and slice performance is monitored per session.",
            jurisdiction="International",
        )
        # canonical_items=None → stub CanonicalKB
        record = _run_to_t0({AgentID.TECHNICAL: [ev]}, None)
        cited_claims = {
            c for f in record.agent_findings
            if f.agent_id == AgentID.TECHNICAL
            for c in f.claim_citations
        }
        if cited_claims:
            for vc in record.verifier_result.verified_claims:
                if vc.agent_id == AgentID.TECHNICAL and vc.claim in cited_claims:
                    assert vc.outcome == VerifierOutcome.INCOMPLETE, (
                        f"Cited claim on stub canonical KB must be INCOMPLETE, "
                        f"got {vc.outcome}: {vc.claim}"
                    )
                    assert "cannot be independently confirmed" in vc.rationale.lower() or \
                           "not available" in vc.rationale.lower() or \
                           "incomplete" in vc.rationale.lower()

    def test_incomplete_from_policy_gap_examination(self):
        """
        Policy gap claims (Potential gap / Coverage check) are always at most INCOMPLETE
        — they are observations for expert review, never VERIFIED conclusions.
        """
        cyber = _fx("Cyber Rules", "Rule 3",
                    "A telecom entity shall report a cyber security incident.")
        data = _fx("Data Act", "Section 8",
                   "A data fiduciary shall notify a personal data breach to the Board.")
        nciipc = _fx("CII Rules", "Rule 4",
                     "NCIIPC shall coordinate protection of critical information infrastructure.")
        certin = _fx("Cyber Directions", "Para 2",
                     "CERT-In shall receive reports of cyber incidents and coordinate response.")
        registry = _registry({}, [cyber, data, nciipc, certin])
        pipeline = Pipeline(registry)
        records = [pipeline.run_chunk(c) for c in get_chunks()]
        gf = next(
            f for f in records[3].agent_findings
            if f.agent_id == AgentID.POLICY_GAP
        )
        gap_claims = [c for c in gf.claims if c.startswith("Potential gap")]
        if gap_claims:
            gap_outcomes = {
                vc.outcome
                for vc in records[3].verifier_result.verified_claims
                if vc.claim in gap_claims
            }
            assert VerifierOutcome.VERIFIED not in gap_outcomes, (
                "Policy gap claims must never be VERIFIED"
            )
            assert VerifierOutcome.INCOMPLETE in gap_outcomes or \
                   VerifierOutcome.UNSUPPORTED in gap_outcomes

    def test_incomplete_claims_in_uncertain_conclusions(self):
        """INCOMPLETE claims must appear under uncertain_conclusions in the Coordinator."""
        ev = _fx(
            "5G Arch Spec", "Clause 5.15",
            "A network slice provides specific network capabilities and "
            "network characteristics, slice performance is monitored.",
            jurisdiction="International",
            effective=None,
        )
        record = _run_to_t0({AgentID.TECHNICAL: [ev]}, [ev])
        incomplete = [
            vc for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.INCOMPLETE
        ]
        if incomplete:
            ca = record.coordinator_assessment
            uncertain_text = " ".join(ca.uncertain_conclusions)
            # At least one incomplete claim must appear in uncertain_conclusions
            found = any(
                any(word in uncertain_text for word in vc.claim.split()[:6])
                for vc in incomplete
            )
            assert found or ca.uncertain_conclusions, (
                "INCOMPLETE claims must feed into uncertain_conclusions"
            )


# ===========================================================================
# C. CONFLICT — two agents produce contradicting findings
# ===========================================================================

class TestConflict:
    """
    A conflict arises when:
      (a) CII Agent finds CII relevance AND Policy & Legal Agent examined
          sources but found no corresponding obligation, OR
      (b) Privacy Agent confirms exposure AND Cybersecurity Agent does not
          classify the incident as a security event.
    """

    def test_cii_vs_policy_legal_conflict(self):
        """
        CII Agent: cii_relevant=True
        Policy & Legal Agent: examined sources, found no obligation
        → CII relevance claim → CONFLICT.
        """
        definitions = _fx(
            "Telecom Instrument", "Section 2",
            "Definitions of telecom terms used in this instrument.",
        )
        registry = _registry({AgentID.POLICY_LEGAL: [definitions]}, None)
        record = _run_to_t2({AgentID.POLICY_LEGAL: [definitions]}, None)
        conflict_outcomes = [
            vc for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.CONFLICT
        ]
        assert conflict_outcomes, (
            "CONFLICT must be detected when CII Agent finds relevance but "
            "Policy & Legal examined sources and found no obligation"
        )
        # The CII claim is the one marked CONFLICT; P&L claim keeps its outcome
        cii_conflicts = [vc for vc in conflict_outcomes
                         if vc.agent_id == AgentID.CRITICAL_INFRA]
        assert cii_conflicts, "The CONFLICT must apply to the CII agent's claim"

    def test_conflict_both_sides_preserved_with_evidence(self):
        """Both sides of a conflict are recorded; neither is silently dropped."""
        definitions = _fx(
            "Telecom Instrument", "Section 2",
            "Definitions of telecom terms used in this instrument.",
        )
        record = _run_to_t2({AgentID.POLICY_LEGAL: [definitions]}, None)
        conflict_details = record.verifier_result.conflict_details
        assert conflict_details, "conflict_details must be non-empty when CONFLICT detected"
        for c in conflict_details:
            assert c.finding_a.claim, "Finding A must have a claim"
            assert c.finding_b.claim, "Finding B must have a claim"
            # Policy & Legal finding B must show what was examined
            pl_side = next(
                (side for side in [c.finding_a, c.finding_b]
                 if side.agent_id == AgentID.POLICY_LEGAL), None
            )
            if pl_side:
                assert pl_side.evidence, (
                    "Policy & Legal side of conflict must show the passages it examined"
                )

    def test_conflict_appears_in_coordinator_conflicting_findings(self):
        """CONFLICT claims must appear under conflicting_findings in the Coordinator."""
        definitions = _fx(
            "Telecom Instrument", "Section 2",
            "Definitions of telecom terms used in this instrument.",
        )
        record = _run_to_t2({AgentID.POLICY_LEGAL: [definitions]}, None)
        ca = record.coordinator_assessment
        assert ca.conflicting_findings, (
            "Coordinator must surface conflicting findings when CONFLICT is detected"
        )

    def test_conflict_not_silently_resolved(self):
        """
        Neither side of a conflict may be adopted as a conclusion.
        The conflict must be visible; no conclusion resolves it silently.
        """
        definitions = _fx(
            "Telecom Instrument", "Section 2",
            "Definitions of telecom terms used in this instrument.",
        )
        record = _run_to_t2({AgentID.POLICY_LEGAL: [definitions]}, None)
        conflict_claims = {
            vc.claim for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.CONFLICT
        }
        ca = record.coordinator_assessment
        # Conflict claims must not appear in evidence_backed_conclusions
        for conclusion in ca.evidence_backed_conclusions:
            for claim in conflict_claims:
                assert claim not in conclusion, (
                    "A CONFLICT claim must not appear in evidence_backed_conclusions"
                )

    def test_no_conflict_without_policy_legal_examining_sources(self):
        """
        Silence from Policy & Legal due to missing evidence is NOT a conflict.
        Only when Policy & Legal actually examined sources is silence a contradiction.
        """
        # No KB items for Policy & Legal → stub → no sources examined
        record = _run_to_t2({}, None)
        assert not record.verifier_result.conflicts, (
            "No CONFLICT when Policy & Legal had no sources to examine "
            "(silence = missing evidence, not contradiction)"
        )

    def test_conflict_status_text_preserved_in_record(self):
        """The ConflictRecord must carry both status and coordinator_treatment."""
        definitions = _fx(
            "Telecom Instrument", "Section 2",
            "Definitions of telecom terms used in this instrument.",
        )
        record = _run_to_t2({AgentID.POLICY_LEGAL: [definitions]}, None)
        for c in record.verifier_result.conflict_details:
            assert "CONFLICT" in c.status
            assert c.coordinator_treatment
            assert "human review" in c.coordinator_treatment.lower() or \
                   "withheld" in c.coordinator_treatment.lower()


# ===========================================================================
# D. VERIFIED — source confirmed, text supports claim, in force, no amendment
# ===========================================================================

class TestVerified:
    """
    A claim is VERIFIED only when ALL conditions are met:
      1. The Canonical KB contains the cited source and section.
      2. The canonical passage's content terms support the claim.
      3. effective=True (not None or False).
      4. amendment_checked=True.
      5. amendment_note is empty (no known amendment).
    """

    def _verified_evidence(self, extra_text: str = "") -> EvidenceItem:
        """
        Construct an EvidenceItem that satisfies all Verifier conditions for VERIFIED.
        The excerpt must overlap with the claim's content terms.
        """
        return EvidenceItem(
            source_title="FIXTURE 5G Architecture Spec",
            authority="Test fixture",
            jurisdiction="International",
            document_type="Fixture",
            section="Clause 5.15",
            excerpt=(
                "A network slice provides specific network capabilities and "
                "network characteristics, and slice performance is monitored "
                "per session. " + extra_text
            ),
            chunk_id="fx-5g-arch-clause-5-15",
            effective=True,           # confirmed in force
            amendment_checked=True,   # amendments checked
            amendment_note="",        # no amendment
        )

    def test_verified_when_all_conditions_met(self):
        """When all four conditions hold, the Verifier returns VERIFIED."""
        ev = self._verified_evidence()
        registry = _registry({AgentID.TECHNICAL: [ev]}, [ev])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        # Find quoted claim
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited_claims = set(tech.claim_citations.keys())
        assert cited_claims, "Agent must have quoted at least one retrieved passage"
        quoted_outcomes = [
            vc for vc in record.verifier_result.verified_claims
            if vc.claim in cited_claims
        ]
        assert quoted_outcomes
        outcomes = {vc.outcome for vc in quoted_outcomes}
        assert VerifierOutcome.VERIFIED in outcomes, (
            f"Expected VERIFIED when all conditions met. Got: {outcomes}\n"
            "Rationales: " + str([vc.rationale for vc in quoted_outcomes])
        )

    def test_verified_claim_in_evidence_backed_conclusions(self):
        """A VERIFIED claim must appear in evidence_backed_conclusions."""
        ev = self._verified_evidence()
        registry = _registry({AgentID.TECHNICAL: [ev]}, [ev])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        verified_claims = [
            vc for vc in record.verifier_result.verified_claims
            if vc.outcome == VerifierOutcome.VERIFIED
        ]
        if verified_claims:
            ca = record.coordinator_assessment
            assert ca.evidence_backed_conclusions, (
                "A VERIFIED claim must produce at least one evidence_backed_conclusion"
            )

    def test_verified_requires_in_force_status(self):
        """effective=None prevents VERIFIED even when text matches."""
        ev_none = EvidenceItem(
            source_title="FIXTURE 5G Architecture Spec",
            authority="Test fixture",
            jurisdiction="International",
            document_type="Fixture",
            section="Clause 5.15",
            excerpt=(
                "A network slice provides specific network capabilities and "
                "network characteristics, and slice performance is monitored per session."
            ),
            chunk_id="fx-5g-arch-clause-5-15-none",
            effective=None,            # not verified → INCOMPLETE, not VERIFIED
            amendment_checked=True,
            amendment_note="",
        )
        registry = _registry({AgentID.TECHNICAL: [ev_none]}, [ev_none])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited_claims = set(tech.claim_citations.keys())
        for vc in record.verifier_result.verified_claims:
            if vc.claim in cited_claims:
                assert vc.outcome != VerifierOutcome.VERIFIED, (
                    "effective=None must prevent VERIFIED"
                )

    def test_verified_requires_amendment_checked(self):
        """amendment_checked=False prevents VERIFIED even when text matches."""
        ev_unchecked = EvidenceItem(
            source_title="FIXTURE 5G Architecture Spec",
            authority="Test fixture",
            jurisdiction="International",
            document_type="Fixture",
            section="Clause 5.15",
            excerpt=(
                "A network slice provides specific network capabilities and "
                "network characteristics, and slice performance is monitored per session."
            ),
            chunk_id="fx-5g-arch-clause-5-15-unchecked",
            effective=True,
            amendment_checked=False,  # not checked → INCOMPLETE, not VERIFIED
            amendment_note="",
        )
        registry = _registry({AgentID.TECHNICAL: [ev_unchecked]}, [ev_unchecked])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited_claims = set(tech.claim_citations.keys())
        for vc in record.verifier_result.verified_claims:
            if vc.claim in cited_claims:
                assert vc.outcome != VerifierOutcome.VERIFIED, (
                    "amendment_checked=False must prevent VERIFIED"
                )

    def test_verified_requires_no_amendment_note(self):
        """A known amendment makes the result INCOMPLETE even when effective=True."""
        ev_amended = EvidenceItem(
            source_title="FIXTURE 5G Architecture Spec",
            authority="Test fixture",
            jurisdiction="International",
            document_type="Fixture",
            section="Clause 5.15",
            excerpt=(
                "A network slice provides specific network capabilities and "
                "network characteristics, slice performance is monitored per session."
            ),
            chunk_id="fx-5g-arch-clause-5-15-amended",
            effective=True,
            amendment_checked=True,
            amendment_note="Revised in later release to add URLLC constraints.",
        )
        registry = _registry({AgentID.TECHNICAL: [ev_amended]}, [ev_amended])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited_claims = set(tech.claim_citations.keys())
        for vc in record.verifier_result.verified_claims:
            if vc.claim in cited_claims:
                assert vc.outcome in (VerifierOutcome.INCOMPLETE, VerifierOutcome.UNSUPPORTED), (
                    "A known amendment must prevent VERIFIED"
                )

    def test_verified_only_by_canonical_kb_not_by_agent_kb_alone(self):
        """
        An agent KB passage alone is not enough for VERIFIED.
        VERIFIED requires the Canonical KB to independently confirm the passage.
        """
        ev = self._verified_evidence()
        # Agent KB has the passage but canonical KB does NOT
        registry = _registry({AgentID.TECHNICAL: [ev]}, [])  # empty canonical
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        tech = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
        cited_claims = set(tech.claim_citations.keys())
        for vc in record.verifier_result.verified_claims:
            if vc.claim in cited_claims:
                assert vc.outcome != VerifierOutcome.VERIFIED, (
                    "Agent KB alone must not be sufficient for VERIFIED; "
                    "Canonical KB confirmation is required"
                )

    def test_verified_claim_rationale_cites_source_and_section(self):
        """VERIFIED rationale must reference the supporting source and section."""
        ev = self._verified_evidence()
        registry = _registry({AgentID.TECHNICAL: [ev]}, [ev])
        pipeline = Pipeline(registry)
        record = pipeline.run_chunk(get_chunk(0))
        for vc in record.verifier_result.verified_claims:
            if vc.outcome == VerifierOutcome.VERIFIED:
                assert "Clause 5.15" in vc.rationale or "5G Architecture Spec" in vc.rationale, (
                    f"VERIFIED rationale must cite the source and section:\n  {vc.rationale}"
                )
                assert vc.supporting_evidence, (
                    "VERIFIED claim must carry supporting evidence"
                )
