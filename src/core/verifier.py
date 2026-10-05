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

Verification requires authoritative text from the Canonical KB that
supports the claim (DOCX §3.5: does the cited source exist, does the cited
section support the claim, does an amendment apply).

  (a) Canonical KB live
      Cited claim (the agent quoted a retrieved passage):
        cited source/section absent from Canonical KB      → UNSUPPORTED
        canonical text does not support the claim          → UNSUPPORTED
        supported, but recorded as not in force            → UNSUPPORTED
        supported, amendment recorded                      → INCOMPLETE
        supported, in force, no amendment                  → VERIFIED
      Uncited claim (an agent's reading of the incident facts):
        the same checks against any retrieved canonical passage.

  (b) Canonical KB stub (not yet populated):
      Claim backed by the passage the agent cited          → INCOMPLETE
      Otherwise                                            → UNSUPPORTED

"Supports" is decided by a support judge.  The default, LexicalSupportJudge,
requires that most of the claim's content terms appear in the passage
(retrieval similarity alone is never enough).  A stronger judge — e.g. an
LLM entailment check — can be injected without changing the Verifier.

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
from typing import Callable, Optional

from src.core.models import (
    AgentFinding, AgentID, EvidenceItem,
    VerifiedClaim, VerifierOutcome, VerifierResult,
)
from src.knowledge_base.base_kb import CanonicalKnowledgeBase
from src.knowledge_base.text_match import normalise_section, term_coverage

# (claim, passage) -> does the passage support the claim?
SupportJudge = Callable[[str, EvidenceItem], bool]


class LexicalSupportJudge:
    """
    Default support judge: the passage supports the claim when at least
    `threshold` of the claim's content terms occur in the passage's source
    title, section and text.  Deterministic and replayable.
    """

    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold

    def __call__(self, claim: str, passage: EvidenceItem) -> bool:
        text = f"{passage.source_title} {passage.section} {passage.excerpt}"
        return term_coverage(claim, text) >= self.threshold

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
    support_judge : optional callable (claim, passage) -> bool deciding
                   whether a passage supports a claim.  Defaults to
                   LexicalSupportJudge.
    """

    def __init__(
        self,
        canonical_kb: Optional[CanonicalKnowledgeBase] = None,
        support_judge: Optional[SupportJudge] = None,
    ) -> None:
        self.canonical_kb = canonical_kb or CanonicalKnowledgeBase(
            kb_name="canonical_stub",
            domain="canonical",
        )
        self.support_judge: SupportJudge = support_judge or LexicalSupportJudge()
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

        # Step 3: Conflict detection between agents.  Each rule names the
        # exact (agent, claim) pairs it disputes; only those are marked.
        conflicts = self._detect_conflicts(findings)
        all_conflicts.extend(note for note, _ in conflicts)

        for vc in verified_claims:
            for note, disputed in conflicts:
                if (vc.agent_id, vc.claim) in disputed:
                    if vc.outcome != VerifierOutcome.CONFLICT:
                        vc.outcome   = VerifierOutcome.CONFLICT
                        vc.rationale += f" | CONFLICT detected: {note}"

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

        Outcomes are determined solely by authoritative passages and the
        support judge.  Disclaimer labels ("[REFERENCE ONLY]", "[STUB]",
        "[ERROR]") are metadata only and never confer VERIFIED.
        """
        def result(outcome: VerifierOutcome, rationale: str,
                   support: Optional[list[EvidenceItem]] = None,
                   against: Optional[list[EvidenceItem]] = None) -> VerifiedClaim:
            return VerifiedClaim(
                agent_id             = finding.agent_id,
                chunk_id             = finding.chunk_id,
                claim                = claim,
                outcome              = outcome,
                rationale            = rationale,
                supporting_evidence  = support or [],
                conflicting_evidence = against or [],
            )

        # Error or stub placeholders — no analytical content
        if claim.startswith("[ERROR]") or claim.startswith("[STUB]"):
            return result(
                VerifierOutcome.UNSUPPORTED,
                "Claim originates from an error or stub state and has no verifiable content.",
            )

        cited = [e for e in finding.claim_citations.get(claim, [])
                 if e.authority != "STUB" and e.chunk_id != "stub-000"]

        # Policy Gap examination results ("Potential gap — ...", "Coverage
        # check — ...") describe what the examined corpus does or does not
        # say; they quote nothing, so text support does not apply.  Check
        # that every passage they rely on exists in the Canonical KB; the
        # outcome is at most INCOMPLETE — a potential gap is for expert
        # review, never a verified conclusion (DOCX §5.1).
        if (finding.agent_id == AgentID.POLICY_GAP
                and claim.startswith(("Potential gap", "Coverage check"))):
            if not canonical_live:
                return result(VerifierOutcome.UNSUPPORTED,
                              "Gap examination cannot be re-checked: Canonical KB not available.")
            missing = [e for e in cited if not self._canonical_section(e.excerpt, e)]
            if missing:
                refs = "; ".join(f"{e.source_title}, {e.section}" for e in missing)
                return result(VerifierOutcome.UNSUPPORTED,
                              f"Gap examination relies on passages not found in the Canonical KB ({refs}).")
            basis = ("cited passages confirmed in the Canonical KB"
                     if cited else "an examination of the Canonical KB with no passage to cite")
            return result(
                VerifierOutcome.INCOMPLETE,
                f"Policy-gap examination based on {basis}. A potential gap or coverage "
                "check is an observation for expert review, not a verified conclusion.",
                support=cited,
            )

        # ------------------------------------------------------------------
        # Path B — Canonical KB not yet available
        # ------------------------------------------------------------------
        if not canonical_live:
            backed = [e for e in cited if self.support_judge(claim, e)]
            if backed:
                return result(
                    VerifierOutcome.INCOMPLETE,
                    "The claim matches the passage the agent cited, but the Canonical "
                    "KB is not available, so the citation cannot be independently "
                    "confirmed. Status: INCOMPLETE pending Canonical KB integration.",
                    support=backed,
                )
            return result(
                VerifierOutcome.UNSUPPORTED,
                "Canonical KB not yet available and the claim is not backed by a "
                "retrieved passage it cites. Claim cannot be verified. "
                "Status: UNSUPPORTED pending RAG and Canonical KB integration.",
            )

        # ------------------------------------------------------------------
        # Path A1 — cited claim: does the cited source/section exist in the
        # Canonical KB, and does the canonical text support the claim?
        # ------------------------------------------------------------------
        if cited:
            canonical_matches: list[EvidenceItem] = []
            for citation in cited:
                canonical_matches.extend(self._canonical_section(claim, citation))
            if not canonical_matches:
                refs = "; ".join(f"{e.source_title}, {e.section}" for e in cited)
                return result(
                    VerifierOutcome.UNSUPPORTED,
                    f"Cited source/section not found in the Canonical KB ({refs}).",
                )
            return self._judge_against(claim, canonical_matches, result,
                                       basis="the cited section in the Canonical KB")

        # ------------------------------------------------------------------
        # Path A2 — uncited claim (an agent's reading of the incident facts):
        # is any authoritative passage found that supports it?
        # ------------------------------------------------------------------
        hits = [e for e in self.canonical_kb.retrieve(claim, top_k=5)
                if e.authority != "STUB"]
        return self._judge_against(claim, hits, result,
                                   basis="any retrieved Canonical KB passage")

    def _canonical_section(self, claim: str, citation: EvidenceItem) -> list[EvidenceItem]:
        """Canonical passages for exactly the cited source and section."""
        hits = self.canonical_kb.retrieve(
            claim, top_k=10,
            filters={"source_title": citation.source_title, "section": citation.section},
        )
        # Filter again in case the KB implementation ignores `filters`
        return [
            e for e in hits
            if e.authority != "STUB"
            and e.source_title.strip().lower() == citation.source_title.strip().lower()
            and normalise_section(e.section) == normalise_section(citation.section)
        ]

    def _judge_against(self, claim, passages, result, basis: str) -> VerifiedClaim:
        """Apply the support judge, then the in-force and amendment checks."""
        supporting = [e for e in passages if self.support_judge(claim, e)]
        if not supporting:
            if passages:
                return result(
                    VerifierOutcome.UNSUPPORTED,
                    f"Checked against {basis}: the authoritative text does not support "
                    "the claim (the claim's content is not found in the passage).",
                    against=passages[:3],
                )
            return result(
                VerifierOutcome.UNSUPPORTED,
                f"Checked against {basis}: no authoritative passage supports this claim.",
            )

        if all(e.effective is False for e in supporting):
            return result(
                VerifierOutcome.UNSUPPORTED,
                "The supporting passage is recorded as not in force, so it cannot "
                "support a current conclusion.",
                against=supporting,
            )
        in_force = [e for e in supporting if e.effective is not False]

        # DOCX §3.5: "whether an amendment or exception applies".  A passage
        # whose in-force status or amendment history was never checked cannot
        # be VERIFIED — the check has not been done, so it is not claimed.
        unchecked = [e for e in in_force
                     if e.effective is None or not e.amendment_checked]
        if len(unchecked) == len(in_force):
            gaps = []
            if any(e.effective is None for e in unchecked):
                gaps.append("in-force status not verified")
            if any(not e.amendment_checked for e in unchecked):
                gaps.append("amendments not checked")
            sources = "; ".join(f"{e.source_title}, {e.section}" for e in unchecked[:2])
            return result(
                VerifierOutcome.INCOMPLETE,
                f"Supported by the authoritative text ({sources}), but "
                f"{' and '.join(gaps)} for this source.",
                support=in_force,
            )
        in_force = [e for e in in_force if e not in unchecked]

        amended = [e for e in in_force if e.amendment_note]
        if amended:
            notes = "; ".join(f"{e.source_title}, {e.section}: {e.amendment_note}" for e in amended)
            return result(
                VerifierOutcome.INCOMPLETE,
                "Supported by the authoritative text, but an amendment applies that "
                f"the claim does not address ({notes}).",
                support=in_force,
            )

        sources = "; ".join(f"{e.source_title}, {e.section}" for e in in_force[:2])
        return result(
            VerifierOutcome.VERIFIED,
            f"Supported by the authoritative text ({sources}); in force; no amendment recorded.",
            support=in_force,
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
        findings: list[AgentFinding],
    ) -> list[tuple[str, set[tuple[AgentID, str]]]]:
        """
        Detect contradictions between agent findings (DOCX §3.5 check 7).

        Returns (note, disputed) pairs, where `disputed` is the set of
        (agent_id, claim) pairs whose outcome becomes CONFLICT.

        Extend these rules once real KB evidence enables semantic comparison.
        """
        conflicts: list[tuple[str, set[tuple[AgentID, str]]]] = []
        findings_by_agent: dict[AgentID, AgentFinding] = {
            f.agent_id: f for f in findings
        }

        # Rule 1: CII relevance vs Policy & Legal obligations
        cii_f = findings_by_agent.get(AgentID.CRITICAL_INFRA)
        pl_f  = findings_by_agent.get(AgentID.POLICY_LEGAL)
        # Policy & Legal can only disagree if it examined sources: with no
        # retrieved passages its silence is missing evidence, not a conflict.
        if (cii_f and pl_f
                and cii_f.cii_relevant is True
                and pl_f.claim_citations
                and not pl_f.obligations):
            # The CII Agent's claims all rest on the disputed CII relevance
            conflicts.append((
                "CONFLICT: Critical Infrastructure Agent identified CII relevance "
                "but Policy & Legal Agent did not surface corresponding additional "
                "obligations. Requires manual review.",
                {(cii_f.agent_id, c) for c in cii_f.claims},
            ))

        # Rule 2: Privacy confirmed exposure vs Cybersecurity classification
        priv_f  = findings_by_agent.get(AgentID.PRIVACY)
        cyber_f = findings_by_agent.get(AgentID.CYBERSECURITY)
        if (priv_f and cyber_f
                and priv_f.exposure_status == "confirmed"
                and not any(
                    "cyber" in c.lower() or "security" in c.lower()
                    for c in cyber_f.claims
                )):
            # Disputed: the Privacy claims asserting exposure.  The Cybersecurity
            # side is an omission, not a claim, so none of its claims are marked.
            conflicts.append((
                "CONFLICT: Privacy Agent confirmed personal data exposure but "
                "Cybersecurity Agent does not classify this as a security event. "
                "Requires reconciliation.",
                {(priv_f.agent_id, c) for c in priv_f.claims if "exposure" in c.lower()},
            ))

        return conflicts
