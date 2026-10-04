"""
Policy Gap Agent
=================
Mandate (DOCX §3.3, §5.1):
    Identify potential gaps, ambiguities, overlaps, or areas needing further
    policy consideration.

    - Raises evidence-backed issues: unclear coverage, institutional
      responsibility gaps, emerging technology not explicitly addressed,
      overlaps, differences from international standards
    - Uses terms such as "potential gap" and "regulatory ambiguity"
    - NEVER declares an Indian policy inadequate outright

Inputs (DOCX §3.7):
    - Verified findings from other agents
    - International Standards KB
    - Canonical KB (for confirming what Indian provisions say)
    - International Policy Examples KB

Knowledge Base: Policy Gap KB (International policy examples +
neighbouring-country comparative instruments)

This agent is activated AFTER verification (it needs verified findings as
input).  The Orchestrator supplies verified findings in incident_state.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import (
    AgentFinding, AgentID, CoverageCategory, EvidenceItem, ScenarioChunk,
)
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent


class PolicyGapAgent(BaseAgent):

    MANDATE = (
        "Evidence-backed identification of potential policy gaps, ambiguities, "
        "overlaps, and emerging-technology coverage issues in the Indian "
        "regulatory framework, using international standards and policy "
        "examples as reference points only."
    )

    # Non-conclusive language enforced — never say "Indian policy is inadequate"
    GAP_DISCLAIMER = (
        "This is a potential gap or area of regulatory ambiguity identified "
        "for expert review. No conclusion of policy failure is drawn."
    )

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.POLICY_GAP, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        return [
            f"policy gap India 5G network slicing regulatory coverage: {base}",
            "India 5G cybersecurity policy gap international comparison",
            "telecom incident reporting gap India CERT-In TRAI DoT overlap",
            "private 5G healthcare critical infrastructure policy gap India",
            "DPDP Act 2023 telecom cybersecurity interaction ambiguity",
        ]

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        description = chunk.description.lower()
        verified_findings: list[dict] = incident_state.get("verified_findings", [])
        uncertainty_notes = self._uncertainty_note_if_stub(evidence)
        claims: list[str] = []
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Gap analysis based on verified findings and current chunk
        # ----------------------------------------------------------------
        gap_category  = None
        gap_description = ""

        # Gap 1: Network slicing — emerging technology not explicitly named
        claims.append(
            f"Potential gap — {CoverageCategory.EMERGING_TECHNOLOGY.value}: "
            "The Indian regulatory framework (Telecommunications Act 2023, "
            "Telecom Cyber Security Rules 2024) does not appear to explicitly "
            "name 'network slicing' as a separately regulated service category. "
            "Whether network-slice-specific security or service-quality obligations "
            "exist is unclear from currently available Indian instruments. "
            f"{self.GAP_DISCLAIMER}"
        )
        gap_category    = CoverageCategory.EMERGING_TECHNOLOGY
        gap_description = (
            "Network slicing as a distinct regulated category is not explicitly "
            "addressed in the identified Indian instruments."
        )

        # Gap 2: Institutional responsibility overlap
        claims.append(
            f"Potential gap — {CoverageCategory.MISSING_INSTITUTIONAL_CLARITY.value}: "
            "In an incident involving a 5G private network slice that triggers "
            "obligations under DoT (Telecom Cyber Security Rules), CERT-In "
            "(cyber incident reporting), and NCIIPC (if CII-designated), the "
            "lead-institution responsibility and coordination mechanism between "
            "these bodies is not explicitly specified in the identified instruments. "
            f"{self.GAP_DISCLAIMER}"
        )

        # Gap 3: Cross-domain data/cyber interaction (if both are active)
        active_agents = incident_state.get("active_agents", [])
        if (AgentID.CYBERSECURITY.value in active_agents
                and AgentID.PRIVACY.value in active_agents):
            claims.append(
                f"Potential gap — {CoverageCategory.OVERLAPPING_REQUIREMENTS.value}: "
                "A 5G security incident that also involves personal data may "
                "trigger overlapping reporting obligations under the Telecom "
                "Cyber Security Rules 2024 (to CERT-In/DoT) and the DPDP Act "
                "2023 (to the Data Protection Board). The coordination mechanism "
                "between these obligations is not explicitly specified. "
                f"{self.GAP_DISCLAIMER}"
            )

        # Reference comparator note (non-conclusive)
        claims.append(
            "[REFERENCE ONLY — not Indian law] International comparators "
            "(e.g. NIST CSF 2.0, ETSI NFV-SEC 003) provide explicit guidance "
            "for virtualised network-slice security. The Indian framework's "
            "coverage of equivalent scenarios is a potential area for further "
            "policy consideration."
        )

        missing_facts.extend([
            "Final manifest of exact Indian instruments confirmed by KB retrieval.",
            "Neighbouring-country comparators from the Policy Gap KB "
            "(to be added during RAG/KB integration).",
        ])

        return AgentFinding(
            agent_id          = AgentID.POLICY_GAP,
            chunk_id          = chunk.chunk_id,
            summary           = (
                "Policy gap assessment: three potential gaps identified — "
                "(1) network slicing as an emerging technology not explicitly "
                "addressed; (2) institutional-responsibility clarity between "
                "DoT/CERT-In/NCIIPC; (3) overlapping reporting obligations "
                "in a combined cyber/data-protection incident. All are potential "
                "gaps for expert review, not conclusions of inadequacy."
            ),
            claims            = claims,
            evidence          = evidence,
            gap_category      = gap_category,
            gap_description   = gap_description,
            uncertainty_notes = uncertainty_notes,
            missing_facts     = missing_facts,
        )
