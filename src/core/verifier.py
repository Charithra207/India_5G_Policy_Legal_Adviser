"""
Verifier
========
Implements the independent verification layer described in DOCX §3.5 and
Annex-1 A.1.

Core design rule
----------------
A claim is NEVER marked VERIFIED simply because an LLM generated it,
because the agent sounded confident, or because the claim carries a
disclaimer label such as "[REFERENCE ONLY — not Indian law]".

Verification requires actual authoritative evidence retrieved from the
Canonical KB that supports the claim.

  (a) Canonical KB live: the claim is checked against retrieved passages.
      Match (relevance_score > 0.5, no amendment conflict) → VERIFIED
      Match with amendment note                             → INCOMPLETE
      No match                                             → UNSUPPORTED

  (b) Canonical KB stub (not yet populated):
      Agent provided real non-stub evidence                → INCOMPLETE
      No real evidence                                     → UNSUPPORTED

The "[REFERENCE ONLY — not Indian law]" label is a classification
disclaimer.  It does NOT constitute evidence.  A Standards Agent claim
that carries this label but has no supporting canonical passage is
UNSUPPORTED, not VERIFIED.

Outcomes (Annex-1 A.1)
-----------------------
  VERIFIED    – source exists and section supports the claim.
  UNSUPPORTED – source does not support it, or source not found.
  INCOMPLETE  – supported but amendment / exception / related provision missing.
  CONFLICT    – another finding or source contradicts it.

Cross-domain verification
-------------------------
The Verifier has access to the full set of agent findings and flags
relationships where one domain's conclusion changes the reading of another
(DOCX §3.5).
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.models import (
    AgentFinding, AgentID, EvidenceItem,
    VerifiedClaim, VerifierOutcome, VerifierResult,
)
from src.knowledge_base.base_kb import CanonicalKnowledgeBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cross-domain relationship rules (DOCX §3.5)
# ---------------------------------------------------------------------------

_CROSS_DOMAIN_PAIRS: list[tuple[AgentID, AgentID, str]] = [
    (
        AgentID.POLICY_LEGAL,
        AgentID.CYBERSECURITY,
        "Telecom authorisation obligations (Policy & Legal) and cyber-incident "
        "reporting obligations (Cybersecurity) may both be triggered by the "
        "same incident — ensure reporting requirements are consistent.",
    ),
    (
        AgentID.CYBERSECURITY,
        AgentID.PRIVACY,
        "A cybersecurity event that involves personal data triggers both "
        "CERT-In / Telecom Cyber Security Rules reporting (Cybersecurity) "
        "and DPDP Act 2023 notification obligations (Privacy). "
        "These obligations overlap and must be coordinated.",
    ),
    (
        AgentID.CRITICAL_INFRA,
        AgentID.POLICY_LEGAL,
        "CII designation (Critical Infra) activates additional obligations "
        "under the Telecommunications Act 2023 that complement the "
        "general regulatory framework (Policy & Legal).",
    ),
    (
        AgentID.PRIVACY,
        AgentID.POLICY_LEGAL,
        "DPDP Act 2023 obligations (Privacy) interact with Telecommunications "
        "Act 2023 obligations (Policy & Legal) for telecom entities that are "
        "also data fiduciaries.",
    ),
]


class Verifier:
    """
    Independent verification layer for the India 5G Policy & Legal Adviser.

    Parameters
    ----------
    canonical_kb : CanonicalKnowledgeBase instance.
                   When it returns real evidence, claims are checked against it.
                   When it is a stub (returns empty), claims are marked
                   UNSUPPORTED or INCOMPLETE to preserve honesty.
    """

    def __init__(self, canonical_kb: Optional[CanonicalKnowledgeBase] = None) -> None:
        self.canonical_kb = canonical_kb or CanonicalKnowledgeBase(
            kb_name="canonical_stub",
            domain="canonical",
        )
        logger.info(
            "Verifier initialised. Canonical KB available: %s",
            self.canonical_kb.is_available(),
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def verify(
        self,
        chunk_id: str,
        findings: list[AgentFinding],
        incident_state: dict,
    ) -> VerifierResult:
        """
        Verify all claims from all active agents for this chunk.

        Returns VerifierResult with per-claim outcomes, cross-domain links,
        conflicts, and missing-evidence notes.
        """
        logger.info("Verifier: starting verification for chunk %s", chunk_id)

        canonical_live = self.canonical_kb.is_available()
        verified_claims: list[VerifiedClaim] = []
        all_cross_domain_links: list[str] = []
        all_conflicts: list[str] = []
        all_missing_evidence: list[str] = []

        # Step 1: Verify each claim in each finding
        for finding in findings:
            for claim in finding.claims:
                vc = self._verify_single_claim(
                    claim          = claim,
                    finding        = finding,
                    canonical_live = canonical_live,
                )
                verified_claims.append(vc)

        # Step 2: Cross-domain relationship detection
        active_agent_ids = {f.agent_id for f in findings}
        cross_domain_notes = self._check_cross_domain(active_agent_ids)
        all_cross_domain_links.extend(cross_domain_notes)

        for vc in verified_claims:
            for note in cross_domain_notes:
                if vc.agent_id.value in note:
                    vc.cross_domain_flag = True
                    if not vc.cross_domain_note:
                        vc.cross_domain_note = note

        # Step 3: Conflict detection between agents
        conflicts = self._detect_conflicts(findings, verified_claims)
        all_conflicts.extend(conflicts)

        for vc in verified_claims:
            for conflict in conflicts:
                if vc.claim[:40] in conflict:
                    if vc.outcome != VerifierOutcome.CONFLICT:
                        vc.outcome   = VerifierOutcome.CONFLICT
                        vc.rationale += f" | CONFLICT detected: {conflict}"

        # Step 4: Missing evidence notes
        for finding in findings:
            for mf in finding.missing_facts:
                all_missing_evidence.append(f"[{finding.agent_id.value}] {mf}")

        if not canonical_live:
            all_missing_evidence.insert(
                0,
                "[VERIFIER] Canonical KB not yet populated. All claims are "
                "UNSUPPORTED or INCOMPLETE pending KB integration. "
                "Populate CanonicalKnowledgeBase to enable real verification.",
            )

        result = VerifierResult(
            chunk_id           = chunk_id,
            verified_claims    = verified_claims,
            cross_domain_links = all_cross_domain_links,
            conflicts          = all_conflicts,
            missing_evidence   = all_missing_evidence,
        )

        logger.info(
            "Verifier: chunk %s — %d claims checked. "
            "Outcomes: VERIFIED=%d UNSUPPORTED=%d INCOMPLETE=%d CONFLICT=%d",
            chunk_id, len(verified_claims),
            sum(1 for v in verified_claims if v.outcome == VerifierOutcome.VERIFIED),
            sum(1 for v in verified_claims if v.outcome == VerifierOutcome.UNSUPPORTED),
            sum(1 for v in verified_claims if v.outcome == VerifierOutcome.INCOMPLETE),
            sum(1 for v in verified_claims if v.outcome == VerifierOutcome.CONFLICT),
        )
        return result

    # ------------------------------------------------------------------
    # Single-claim verification
    # ------------------------------------------------------------------

    def _verify_single_claim(
        self,
        claim: str,
        finding: AgentFinding,
        canonical_live: bool,
    ) -> VerifiedClaim:
        """
        Assign a verification outcome to one claim.

        Outcomes are determined solely by actual evidence retrieved from
        the Canonical KB (or, if the KB is not yet available, by the
        presence of real non-stub agent evidence).

        Disclaimer labels ("[REFERENCE ONLY]", "[STUB]", "[ERROR]") are
        treated as metadata only.  They do NOT confer a VERIFIED outcome.

        Special handling for error/stub claims
        ---------------------------------------
        Claims starting with "[ERROR]" or "[STUB]" have no analytical
        content and are always UNSUPPORTED.
        """
        # Error or stub placeholders — no analytical content
        if claim.startswith("[ERROR]") or claim.startswith("[STUB]"):
            return VerifiedClaim(
                agent_id  = finding.agent_id,
                chunk_id  = finding.chunk_id,
                claim     = claim,
                outcome   = VerifierOutcome.UNSUPPORTED,
                rationale = "Claim originates from an error or stub state and has no verifiable content.",
            )

        supporting_evidence: list[EvidenceItem] = []

        # ------------------------------------------------------------------
        # Path A — Canonical KB is live: check against actual evidence
        # ------------------------------------------------------------------
        if canonical_live:
            canonical_hits = self.canonical_kb.retrieve(claim, top_k=3)
            supporting_evidence = [
                e for e in canonical_hits
                if e.relevance_score > 0.5 and e.authority != "STUB"
            ]

            if supporting_evidence:
                has_amendment = any(bool(e.amendment_note) for e in supporting_evidence)
                if has_amendment:
                    outcome   = VerifierOutcome.INCOMPLETE
                    rationale = (
                        "Canonical KB evidence supports the claim, but one or "
                        "more retrieved passages carry amendment notes that may "
                        "affect the current reading."
                    )
                else:
                    outcome   = VerifierOutcome.VERIFIED
                    rationale = (
                        "Canonical KB evidence found that supports this claim. "
                        f"Sources: {', '.join(e.source_title for e in supporting_evidence[:2])}."
                    )
            else:
                outcome   = VerifierOutcome.UNSUPPORTED
                rationale = (
                    "Canonical KB is available but no passage with sufficient "
                    "relevance was retrieved to support this claim. The claim "
                    "may be inaccurate, the source may not be in the KB, or "
                    "the section identifier is incorrect."
                )

        # ------------------------------------------------------------------
        # Path B — Canonical KB not yet available: use agent evidence as proxy
        # ------------------------------------------------------------------
        else:
            real_evidence = [
                e for e in finding.evidence
                if e.authority != "STUB" and e.chunk_id != "stub-000"
            ]
            if real_evidence:
                outcome   = VerifierOutcome.INCOMPLETE
                rationale = (
                    "Agent provided evidence but Canonical KB is not yet "
                    "available for independent verification. Claim is supported "
                    "by agent-retrieved evidence only and cannot be independently "
                    "confirmed. Status: INCOMPLETE pending Canonical KB integration."
                )
                supporting_evidence = real_evidence
            else:
                outcome   = VerifierOutcome.UNSUPPORTED
                rationale = (
                    "Canonical KB not yet available and no real evidence was "
                    "retrieved (only stub placeholders). Claim cannot be verified. "
                    "Status: UNSUPPORTED pending RAG and Canonical KB integration."
                )

        return VerifiedClaim(
            agent_id            = finding.agent_id,
            chunk_id            = finding.chunk_id,
            claim               = claim,
            outcome             = outcome,
            rationale           = rationale,
            supporting_evidence = supporting_evidence,
        )

    # ------------------------------------------------------------------
    # Cross-domain checks
    # ------------------------------------------------------------------

    def _check_cross_domain(
        self,
        active_agent_ids: set[AgentID],
    ) -> list[str]:
        """Flag cross-domain pairs where both agents are active (DOCX §3.5)."""
        notes: list[str] = []
        for agent_a, agent_b, note in _CROSS_DOMAIN_PAIRS:
            if agent_a in active_agent_ids and agent_b in active_agent_ids:
                notes.append(
                    f"CROSS-DOMAIN [{agent_a.value} ↔ {agent_b.value}]: {note}"
                )
                logger.debug("Cross-domain flag: %s ↔ %s", agent_a.value, agent_b.value)
        return notes

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def _detect_conflicts(
        self,
        findings:        list[AgentFinding],
        verified_claims: list[VerifiedClaim],
    ) -> list[str]:
        """
        Detect contradictions between agent findings (DOCX §3.5 check 7).

        Extend these rules once real KB evidence enables semantic comparison.
        """
        conflicts: list[str] = []
        findings_by_agent: dict[AgentID, AgentFinding] = {
            f.agent_id: f for f in findings
        }

        # Rule 1: CII relevance vs Policy & Legal obligations
        cii_f = findings_by_agent.get(AgentID.CRITICAL_INFRA)
        pl_f  = findings_by_agent.get(AgentID.POLICY_LEGAL)
        if (cii_f and pl_f
                and cii_f.cii_relevant is True
                and not pl_f.obligations):
            conflicts.append(
                "CONFLICT: Critical Infrastructure Agent identified CII relevance "
                "but Policy & Legal Agent did not surface corresponding additional "
                "obligations. Requires manual review."
            )

        # Rule 2: Privacy confirmed exposure vs Cybersecurity classification
        priv_f  = findings_by_agent.get(AgentID.PRIVACY)
        cyber_f = findings_by_agent.get(AgentID.CYBERSECURITY)
        if (priv_f and cyber_f
                and priv_f.exposure_status == "confirmed"
                and not any(
                    "cyber" in c.lower() or "security" in c.lower()
                    for c in cyber_f.claims
                )):
            conflicts.append(
                "CONFLICT: Privacy Agent confirmed personal data exposure but "
                "Cybersecurity Agent does not classify this as a security event. "
                "Requires reconciliation."
            )

        return conflicts
