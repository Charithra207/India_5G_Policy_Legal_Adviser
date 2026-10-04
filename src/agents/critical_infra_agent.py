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
            f"critical infrastructure provisions India applicable: {base}",
            "NCIIPC Rules 2013 critical information infrastructure designation",
            "Telecommunications Act 2023 critical telecommunication infrastructure",
            "critical service healthcare government 5G network CII designation",
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
        obligations: list[str] = []
        institutions: list[str] = ["NCIIPC", "Department of Telecommunications (DoT)"]
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Determine CII relevance from current chunk
        # ----------------------------------------------------------------
        cii_keywords = ["healthcare", "health", "critical service", "critical application",
                        "critical infrastructure", "government", "essential service",
                        "emergency", "hospital"]

        cii_relevant = any(kw in description for kw in cii_keywords)

        if cii_relevant:
            claims.append(
                "The affected 5G private network slice supports a healthcare "
                "application. Healthcare and emergency services may qualify as "
                "Critical Information Infrastructure (CII) under the IT (NCIIPC) "
                "Rules, 2013, or as critical telecommunication infrastructure under "
                "the Telecommunications Act, 2023. Formal CII designation status "
                "must be confirmed."
            )
            claims.append(
                "If the slice is CII-designated, additional protective obligations, "
                "incident-reporting requirements, and institutional responsibilities "
                "under NCIIPC arise."
            )
            obligations.extend([
                "Confirm whether the healthcare application or its supporting network "
                "infrastructure is formally designated as Critical Information "
                "Infrastructure by NCIIPC.",
                "If CII-designated: comply with NCIIPC incident-reporting and "
                "protective-measures requirements.",
                "Notify NCIIPC and DoT if a CII-designated service is affected "
                "(exact thresholds require KB retrieval).",
            ])
            uncertainty_notes.append(
                "CII designation is UNCONFIRMED at this stage. The healthcare "
                "application may or may not be formally designated. This "
                "uncertainty must be carried through the assessment."
            )
        else:
            claims.append(
                "No explicit critical-infrastructure designation indicators are "
                "present in the current chunk. CII relevance cannot be confirmed."
            )
            cii_relevant = False

        missing_facts.extend([
            "Formal CII designation status of the healthcare application/network.",
            "Whether NCIIPC has been notified of the incident.",
            "Whether the affected entity is listed under any critical sector designation.",
        ])

        return AgentFinding(
            agent_id                 = AgentID.CRITICAL_INFRA,
            chunk_id                 = chunk.chunk_id,
            summary                  = (
                "Critical infrastructure assessment: healthcare application on "
                "the affected slice may qualify for CII designation under IT "
                "(NCIIPC) Rules 2013 or Telecommunications Act 2023 critical "
                "infrastructure provisions. Formal designation status unconfirmed."
            ),
            claims                   = claims,
            evidence                 = evidence,
            obligations              = obligations,
            responsible_institutions = institutions,
            cii_relevant             = cii_relevant,
            uncertainty_notes        = uncertainty_notes,
            missing_facts            = missing_facts,
        )
