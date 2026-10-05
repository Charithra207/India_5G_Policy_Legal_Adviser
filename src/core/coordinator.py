"""
Coordinator
===========
Implements the Coordinator's synthesis role described in DOCX §3.6 and
Annex-1 A.1 Table A1.

Responsibilities
----------------
After the Verifier produces its result, the Coordinator:
  1. Receives specialist findings, verified evidence, cross-domain
     relationships, conflicts, uncertainties, and policy-gap observations.
  2. Combines them into ONE unified CoordinatorAssessment.
  3. Keeps the five output categories STRICTLY SEPARATE:
       - Confirmed facts
       - Evidence-backed conclusions
       - Uncertain conclusions
       - Conflicting findings
       - Potential policy gaps
  4. Preserves uncertainty rather than inventing certainty.
  5. When incident information changes, re-issues the assessment and
     makes earlier conclusions VISIBLY updated rather than silently
     discarded.
  6. Surfaces relevant institutions.
  7. Attaches an evidence trail linking each major conclusion to the
     incident fact, source document, and section.
  8. Always includes a human-review note (DOCX A.2).

Output categories map
---------------------
VERIFIED claims     → evidence_backed_conclusions
INCOMPLETE claims   → uncertain_conclusions
UNSUPPORTED claims  → uncertain_conclusions (with explicit "unverified" note)
CONFLICT claims     → conflicting_findings
Policy Gap findings → potential_policy_gaps
Scenario facts      → confirmed_facts (not claims — raw incident facts)
"""

from __future__ import annotations

import logging
from typing import Optional

from src.core.models import (
    AgentFinding, AgentID, CoordinatorAssessment,
    ScenarioChunk, VerifiedClaim, VerifierOutcome, VerifierResult,
)

logger = logging.getLogger(__name__)


class Coordinator:
    """
    Combines verified multi-agent findings into a single unified assessment.

    Design note: The Coordinator does NOT generate new analysis.  It
    organises what the Verifier has validated into the five DOCX categories.
    Uncertainty is preserved, never papered over.
    """

    # ------------------------------------------------------------------
    # Public entry point — called by Orchestrator
    # ------------------------------------------------------------------

    def synthesize(
        self,
        chunk: ScenarioChunk,
        findings: list[AgentFinding],
        verifier_result: VerifierResult,
        incident_state: dict,
        prior_assessment: Optional[CoordinatorAssessment] = None,
    ) -> CoordinatorAssessment:
        """
        Produce the unified policy assessment for this chunk.

        Parameters
        ----------
        chunk            : current ScenarioChunk
        findings         : raw AgentFindings (for supplementary context)
        verifier_result  : VerifierResult from the Verifier
        incident_state   : shared incident state
        prior_assessment : previous chunk's assessment (for change tracking)

        Returns
        -------
        CoordinatorAssessment with five separated categories.
        """
        logger.info("Coordinator: synthesizing assessment for chunk %s", chunk.chunk_id)

        active_agents = [f.agent_id for f in findings]

        # ----------------------------------------------------------------
        # Category 1: Confirmed facts — raw incident facts, not inferences
        # ----------------------------------------------------------------
        confirmed_facts = self._extract_confirmed_facts(chunk)

        # ----------------------------------------------------------------
        # Category 2 & 3: Evidence-backed vs Uncertain conclusions
        # ----------------------------------------------------------------
        evidence_backed, uncertain = self._classify_by_verifier_outcome(
            verifier_result.verified_claims
        )

        # ----------------------------------------------------------------
        # Category 4: Conflicting findings
        # ----------------------------------------------------------------
        conflicting = self._extract_conflicting(
            verifier_result.verified_claims,
            verifier_result.conflicts,
        )

        # ----------------------------------------------------------------
        # Category 5: Potential policy gaps
        # ----------------------------------------------------------------
        policy_gaps = self._extract_policy_gaps(findings, verifier_result)

        # ----------------------------------------------------------------
        # Institutions
        # ----------------------------------------------------------------
        institutions = self._collect_institutions(findings)

        # ----------------------------------------------------------------
        # What changed from the prior chunk
        # ----------------------------------------------------------------
        changes = self._compute_changes(
            active_agents, prior_assessment, incident_state
        )

        # ----------------------------------------------------------------
        # Cross-domain relationships
        # ----------------------------------------------------------------
        cross_domain = verifier_result.cross_domain_links

        assessment = CoordinatorAssessment(
            chunk_id                    = chunk.chunk_id,
            active_agents               = active_agents,
            confirmed_facts             = confirmed_facts,
            evidence_backed_conclusions = evidence_backed,
            uncertain_conclusions       = uncertain,
            conflicting_findings        = conflicting,
            potential_policy_gaps       = policy_gaps,
            cross_domain_relationships  = cross_domain,
            relevant_institutions       = institutions,
            changes_from_prior          = changes,
        )

        logger.info(
            "Coordinator: chunk %s — "
            "confirmed_facts=%d  evidence_backed=%d  uncertain=%d  "
            "conflicting=%d  policy_gaps=%d",
            chunk.chunk_id,
            len(confirmed_facts),
            len(evidence_backed),
            len(uncertain),
            len(conflicting),
            len(policy_gaps),
        )
        return assessment

    # ------------------------------------------------------------------
    # Category builders
    # ------------------------------------------------------------------

    def _extract_confirmed_facts(self, chunk: ScenarioChunk) -> list[str]:
        """
        Confirmed facts = the raw incident facts released in this chunk.
        These are what the scenario actually states — not agent inferences.

        Agent inferences (e.g. the Technical Agent's affected components,
        which are inferred from symptoms rather than observed in telemetry)
        are NOT confirmed facts.  They reach the assessment only as agent
        claims, classified by their Verifier outcome.
        """
        facts: list[str] = [
            f"[Incident fact — {chunk.chunk_id}] {chunk.description}"
        ]
        for nf in chunk.new_facts:
            facts.append(f"[New fact — {chunk.chunk_id}] {nf}")
        return facts

    def _classify_by_verifier_outcome(
        self,
        verified_claims: list[VerifiedClaim],
    ) -> tuple[list[str], list[str]]:
        """
        Split claims into evidence-backed (VERIFIED) and uncertain
        (INCOMPLETE or UNSUPPORTED).

        CONFLICT claims are excluded here — they go to conflicting_findings.
        """
        evidence_backed: list[str] = []
        uncertain:       list[str] = []

        for vc in verified_claims:
            if vc.outcome == VerifierOutcome.CONFLICT:
                continue  # handled separately

            # Build a labelled statement
            label   = f"[{vc.agent_id.value.upper()} | {vc.outcome.value}]"
            statement = f"{label} {vc.claim}"

            if vc.outcome == VerifierOutcome.VERIFIED:
                evidence_backed.append(statement)
            else:
                # INCOMPLETE or UNSUPPORTED — goes to uncertain with rationale
                rationale_tag = (
                    f" (Verification note: {vc.rationale[:120]}…)"
                    if len(vc.rationale) > 120
                    else f" (Verification note: {vc.rationale})"
                )
                uncertain.append(statement + rationale_tag)

        return evidence_backed, uncertain

    def _extract_conflicting(
        self,
        verified_claims: list[VerifiedClaim],
        conflict_notes: list[str],
    ) -> list[str]:
        """
        Collect CONFLICT-outcome claims and orchestrator-level conflict notes.
        """
        conflicting: list[str] = []

        for vc in verified_claims:
            if vc.outcome == VerifierOutcome.CONFLICT:
                conflicting.append(
                    f"[{vc.agent_id.value.upper()} | CONFLICT] {vc.claim}"
                    f"\n  → Conflict note: {vc.rationale}"
                )

        for note in conflict_notes:
            conflicting.append(f"[VERIFIER CONFLICT NOTE] {note}")

        return conflicting

    def _extract_policy_gaps(
        self,
        findings: list[AgentFinding],
        verifier_result: VerifierResult,
    ) -> list[str]:
        """
        Collect policy gap statements from the Policy Gap Agent's findings.
        Gaps are stated as potential — never as conclusive inadequacy.
        """
        gaps: list[str] = []

        for finding in findings:
            if finding.agent_id != AgentID.POLICY_GAP:
                continue
            for claim in finding.claims:
                # Raised gaps rest on Canonical KB examination; candidate areas
                # that could not be examined are listed separately so they are
                # never mistaken for evidence-backed gaps.
                if claim.startswith("Potential gap"):
                    gaps.append(f"[POLICY GAP — for expert review] {claim}")
                elif claim.startswith("Candidate area NOT EXAMINED"):
                    gaps.append(f"[CANDIDATE GAP AREA — not examined] {claim}")
            if finding.gap_description:
                gaps.append(
                    f"[GAP SUMMARY — {finding.gap_category.value if finding.gap_category else 'unclassified'}] "
                    f"{finding.gap_description}"
                )

        return gaps

    def _collect_institutions(self, findings: list[AgentFinding]) -> list[str]:
        """Deduplicate institutions from all findings."""
        seen: set[str] = set()
        institutions: list[str] = []
        for finding in findings:
            for inst in finding.responsible_institutions:
                if inst not in seen:
                    seen.add(inst)
                    institutions.append(inst)
        return institutions

    def _compute_changes(
        self,
        active_agents:    list[AgentID],
        prior_assessment: Optional[CoordinatorAssessment],
        incident_state:   dict,
    ) -> list[str]:
        """
        Describe what changed from the previous chunk's assessment.
        Makes reassessment visible rather than silent (DOCX §3.6).
        """
        changes: list[str] = []

        if prior_assessment is None:
            changes.append("Initial assessment — no prior chunk to compare against.")
            return changes

        # Newly activated agents
        prior_agents = set(prior_assessment.active_agents)
        new_agents   = set(active_agents) - prior_agents
        if new_agents:
            changes.append(
                "Newly activated agents: "
                + ", ".join(a.value for a in sorted(new_agents, key=lambda x: x.value))
                + " (triggered by new facts in this chunk)."
            )

        # Incident flags that changed
        if incident_state.get("cyber_event_suspected") and not any(
            a == AgentID.CYBERSECURITY for a in prior_assessment.active_agents
        ):
            changes.append(
                "Incident reclassified: cybersecurity indicators emerged in "
                "this chunk, triggering Cybersecurity and Standards Agents."
            )

        if incident_state.get("cii_flagged") and AgentID.CRITICAL_INFRA not in prior_agents:
            changes.append(
                "Critical infrastructure relevance identified for the first time "
                "in this chunk."
            )

        if incident_state.get("data_exposure_suspected") and AgentID.PRIVACY not in prior_agents:
            changes.append(
                "Personal data exposure suspected for the first time in this chunk, "
                "activating the Privacy Agent."
            )

        if not changes:
            changes.append(
                "Assessment updated with new chunk facts; no new agents activated."
            )

        return changes
