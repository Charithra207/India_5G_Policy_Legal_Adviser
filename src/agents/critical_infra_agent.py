"""
Critical Infrastructure Agent
===============================
Mandate (DOCX §3.3):
    Analyse critical-infrastructure implications.
    - Determine whether critical-infrastructure provisions are relevant
    - Identify additional obligations, institutional responsibilities,
      and security implications

Knowledge Base: Critical Infrastructure KB
    Information Technology (NCIIPC and Manner of Performing Functions
    and Duties) Rules, 2013;
    Telecommunications Act, 2023 (critical telecommunication infrastructure
    provisions).

This agent speaks ONLY about critical-infrastructure relevance and the
additional obligations that arise from it.  It does NOT perform cybersecurity
classification, data-protection analysis, or general telecom-law analysis.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent


class CriticalInfraAgent(BaseAgent):

    MANDATE = (
        "Critical-infrastructure relevance and additional obligations and "
        "institutional responsibilities under Indian critical-infrastructure "
        "provisions."
    )

    INSTRUMENTS = [
        "Information Technology (NCIIPC and Manner of Performing Functions "
        "and Duties) Rules, 2013",
        "Telecommunications Act, 2023 — critical telecommunication "
        "infrastructure provisions",
    ]

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.CRITICAL_INFRA, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        return [
            base,
            "notification of critical telecommunication infrastructure and measures for its protection",
            "designation and protection of critical information infrastructure",
            "standards and measures for security of telecommunication networks",
        ]

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        description = chunk.description.lower()
        uncertainty_notes = self._uncertainty_note_if_stub(evidence)
        claims: list[str] = []
        institutions: list[str] = ["NCIIPC", "Department of Telecommunications (DoT)"]
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Determine CII relevance from the facts released so far
        # ----------------------------------------------------------------
        cii_keywords = ["healthcare", "health", "critical service", "critical application",
                        "critical infrastructure", "government", "essential service",
                        "emergency", "hospital"]
        matched = [kw for kw in cii_keywords if kw in description]
        cii_relevant = bool(matched) or bool(incident_state.get("cii_flagged"))

        citations: dict[str, list[EvidenceItem]] = {}
        if cii_relevant:
            service = (
                "a healthcare application" if any(k in matched for k in ("healthcare", "health", "hospital"))
                else "a critical service" if matched
                else "a service flagged as critical in an earlier chunk"
            )
            claims.append(
                f"The incident facts indicate that the affected 5G slice supports "
                f"{service}, so critical-infrastructure provisions are relevant to "
                "examine. Formal CII designation status is not established by the facts."
            )
            uncertainty_notes.append(
                "CII designation is UNCONFIRMED at this stage. The service may or may "
                "not be formally designated. This uncertainty must be carried through "
                "the assessment."
            )
            # What the CII instruments say — quoted from retrieved passages only
            source_claims, citations = self._evidence_or_scope_claims(
                evidence, self.INSTRUMENTS,
            )
            claims.extend(source_claims)
        else:
            claims.append(
                "No critical-service indicators are present in the facts released so "
                "far. CII relevance cannot be established."
            )

        obligations = self._duty_passages(evidence) if cii_relevant else []

        missing_facts.extend([
            "Formal CII designation status of the affected service/network.",
            "Whether NCIIPC has been notified of the incident.",
            "Whether the affected entity is listed under any critical sector designation.",
        ])

        return AgentFinding(
            agent_id                 = AgentID.CRITICAL_INFRA,
            chunk_id                 = chunk.chunk_id,
            summary                  = (
                "Critical infrastructure assessment: "
                + ("critical-service relevance indicated by the facts; formal CII "
                   "designation unconfirmed. " if cii_relevant else
                   "no critical-service indicators. ")
                + (f"{len(citations)} provision(s) quoted from the {self.kb.kb_name}."
                   if citations else
                   "No CII provisions retrieved; additional obligations are not assessed.")
            ),
            claims                   = claims,
            evidence                 = evidence,
            claim_citations          = citations,
            obligations              = obligations,
            responsible_institutions = institutions,
            cii_relevant             = cii_relevant,
            uncertainty_notes        = uncertainty_notes,
            missing_facts            = missing_facts,
        )
