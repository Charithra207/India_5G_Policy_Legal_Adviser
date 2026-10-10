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
            base,
            "measures to protect telecommunication networks and services and their security",
            "authorisation to provide telecommunication services and operate networks",
            "functions and powers of the Telecom Regulatory Authority of India",
        ]
        if incident_state.get("cii_flagged"):
            queries.append(
                "notification of critical telecommunication infrastructure and rules for it"
            )
        if any(w in base.lower() for w in ("report", "notif", "escalat", "intimat")):
            queries.append(
                "intimation of a security incident to the Central Government within hours"
            )
        return queries

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        uncertainty_notes = self._uncertainty_note_if_stub(evidence)
        institutions: list[str] = [
            "Department of Telecommunications (DoT)",
            "Telecom Regulatory Authority of India (TRAI)",
        ]
        missing_facts: list[str] = []

        # What Indian telecom law says — quoted from retrieved passages only
        claims, citations = self._evidence_or_scope_claims(evidence, self.INSTRUMENTS)
        provisions  = [f"{e.source_title}, {e.section}"
                       for items in citations.values() for e in items]
        obligations = self._duty_passages(evidence)

        if incident_state.get("cii_flagged"):
            institutions.append(
                "National Critical Information Infrastructure Protection Centre (NCIIPC)"
            )
            uncertainty_notes.append(
                "Critical-service relevance has been flagged. Whether the Telecommunications "
                "Act, 2023 critical telecommunication infrastructure provisions apply "
                "depends on retrieved provisions and formal designation."
            )

        if incident_state.get("data_exposure_suspected"):
            uncertainty_notes.append(
                "Personal data may be involved. Any interaction between telecom "
                "obligations and data-protection obligations is for the Privacy Agent "
                "and the Verifier's cross-domain check, not this agent."
            )

        if not citations:
            missing_facts.append(
                "Applicable sections, thresholds and timelines under the Indian telecom "
                f"instruments require retrieval from the {self.kb.kb_name}."
            )

        return AgentFinding(
            agent_id                  = AgentID.POLICY_LEGAL,
            chunk_id                  = chunk.chunk_id,
            summary                   = (
                f"Policy & Legal assessment: {len(citations)} provision(s) quoted from "
                f"the {self.kb.kb_name}"
                + (f", {len(obligations)} of which impose duties." if citations else
                   "; applicable provisions and obligations are not assessed.")
            ),
            claims                    = claims,
            evidence                  = evidence,
            claim_citations           = citations,
            applicable_provisions     = provisions,
            responsible_institutions  = institutions,
            obligations               = obligations,
            uncertainty_notes         = uncertainty_notes,
            missing_facts             = missing_facts,
        )
