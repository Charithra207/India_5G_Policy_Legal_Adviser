"""
Policy & Legal Agent
====================
Mandate (DOCX §3.3):
    Determine the applicable Indian legal and regulatory framework.
    - Identify relevant Acts, rules, regulations, government directions
      and notifications
    - Identify obligations and responsible institutions
    - Flag legal uncertainty
    - Supply evidence

Knowledge Base: Indian Legal/Regulatory KB
    Telecommunications Act 2023; TRAI Act 1997; NDCP-2018;
    government directions/notifications.

This agent speaks ONLY about Indian law and regulation.  It does NOT
perform cybersecurity classification, data-protection analysis, or
technical diagnosis.  International standards are referenced as comparison
points only and are never stated as Indian legal requirements.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent


class PolicyLegalAgent(BaseAgent):

    MANDATE = (
        "Indian telecommunications law, regulatory framework, authorisations, "
        "obligations, and institutional responsibilities under Indian Acts, "
        "rules, regulations, directions, and notifications."
    )

    # Instruments in scope for this agent's KB
    INSTRUMENTS = [
        "Telecommunications Act, 2023",
        "TRAI Act, 1997",
        "National Digital Communications Policy-2018",
        "Government directions and notifications under DoT/TRAI",
    ]

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.POLICY_LEGAL, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        queries = [
            f"Indian telecom law applicable provisions: {base}",
            "Telecommunications Act 2023 obligations network security incident",
            "TRAI Act 1997 regulatory responsibilities telecom incident",
            "DoT obligations telecommunication entities incident reporting",
        ]
        if incident_state.get("cii_flagged"):
            queries.append(
                "Telecommunications Act 2023 critical telecommunication "
                "infrastructure provisions obligations"
            )
        return queries

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        description = chunk.description.lower()
        uncertainty_notes = self._uncertainty_note_if_stub(evidence)
        claims: list[str] = []
        obligations: list[str] = []
        institutions: list[str] = []
        provisions: list[str] = []
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Provisions that are plausibly relevant at T0/T1 based on scenario text.
        # These are framed as "may be relevant" because without real RAG
        # they cannot be marked VERIFIED.
        # ----------------------------------------------------------------
        provisions.append(
            "Telecommunications Act, 2023 — general authorisation and "
            "network-security obligations for telecommunication entities "
            "(exact sections require KB retrieval to confirm)."
        )
        claims.append(
            "The Telecommunications Act, 2023 is the primary Indian statute "
            "governing licensed telecommunication entities and their obligations "
            "in an incident of this type."
        )
        institutions.append("Department of Telecommunications (DoT)")
        institutions.append("Telecom Regulatory Authority of India (TRAI)")

        if incident_state.get("cii_flagged"):
            provisions.append(
                "Telecommunications Act, 2023 — critical telecommunication "
                "infrastructure provisions (Sections to be confirmed by KB retrieval)."
            )
            claims.append(
                "If the affected slice qualifies as critical telecommunication "
                "infrastructure under the Telecommunications Act, 2023, "
                "additional obligations and institutional responsibilities arise."
            )
            institutions.append("National Critical Information Infrastructure Protection Centre (NCIIPC)")

        if incident_state.get("data_exposure_suspected"):
            claims.append(
                "Personal-data-protection obligations (DPDP Act 2023) may overlap "
                "with telecom authorisation obligations — cross-domain analysis "
                "with the Privacy Agent is required."
            )
            uncertainty_notes.append(
                "Exact interaction between Telecom Act 2023 and DPDP Act 2023 "
                "obligations in a combined telecom-security/data-exposure scenario "
                "requires KB verification."
            )

        obligations.extend([
            "Ensure network security and incident response under applicable "
            "telecom authorisation conditions (Telecommunications Act, 2023).",
            "Notify relevant authorities as required by applicable directions "
            "(exact thresholds require KB retrieval).",
        ])

        missing_facts.append(
            "Exact section numbers, thresholds, and timelines under the "
            "Telecommunications Act, 2023 require retrieval from the Policy & Legal KB."
        )

        return AgentFinding(
            agent_id                  = AgentID.POLICY_LEGAL,
            chunk_id                  = chunk.chunk_id,
            summary                   = (
                "The Telecommunications Act, 2023 and TRAI Act, 1997 are the "
                "primary Indian legal instruments relevant to this incident. "
                "Exact provisions and obligations require KB retrieval for confirmation."
            ),
            claims                    = claims,
            evidence                  = evidence,
            applicable_provisions     = provisions,
            responsible_institutions  = institutions,
            obligations               = obligations,
            uncertainty_notes         = uncertainty_notes,
            missing_facts             = missing_facts,
        )
