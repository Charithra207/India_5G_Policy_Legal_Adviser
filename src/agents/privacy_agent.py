"""
Privacy / Data Protection Agent
================================
Mandate (DOCX §3.3):
    Analyse personal-data and privacy implications.
    - Determine whether personal data may be involved
    - Identify Indian data-protection requirements
    - Distinguish confirmed from suspected exposure
    - Flag uncertainty

Knowledge Base: Privacy KB
    Digital Personal Data Protection Act, 2023;
    Digital Personal Data Protection Rules, 2025.

IMPORTANT: This agent explicitly distinguishes:
    - confirmed exposure (evidence establishes that personal data was accessed)
    - suspected exposure (circumstances suggest it is possible)
    - unknown (insufficient information to determine)

It does NOT claim exposure without evidence and does NOT perform
legal/regulatory or cybersecurity analysis outside the privacy domain.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent


class PrivacyAgent(BaseAgent):

    MANDATE = (
        "Personal-data and privacy implications under Indian data-protection law. "
        "Distinction between confirmed, suspected, and unknown exposure."
    )

    INSTRUMENTS = [
        "Digital Personal Data Protection Act, 2023",
        "Digital Personal Data Protection Rules, 2025",
    ]

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.PRIVACY, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        return [
            f"personal data exposure data protection obligations: {base}",
            "Digital Personal Data Protection Act 2023 breach notification requirements",
            "DPDP Rules 2025 data fiduciary obligations security incident",
            "personal data involvement telecom 5G network slice breach",
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
        institutions: list[str] = ["Data Protection Board of India (once operational)"]
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Determine exposure status from current chunk
        # ----------------------------------------------------------------
        data_keywords_confirmed = ["data exposed", "data breach", "personal data accessed",
                                    "subscriber data exposed"]
        data_keywords_suspected  = ["patient information", "subscriber", "personal data",
                                     "identifiable", "healthcare", "health", "user data"]

        exposure_status = "unknown"
        if any(kw in description for kw in data_keywords_confirmed):
            exposure_status = "confirmed"
        elif any(kw in description for kw in data_keywords_suspected):
            exposure_status = "suspected"

        # ----------------------------------------------------------------
        # Claims
        # ----------------------------------------------------------------
        if exposure_status == "confirmed":
            claims.append(
                "Personal data exposure is CONFIRMED based on current incident facts. "
                "The DPDP Act 2023 obligations for data breaches are triggered."
            )
            obligations.extend([
                "Notify the Data Protection Board of India of the personal data breach "
                "as required under the DPDP Act, 2023 (exact timeline requires KB retrieval).",
                "Notify affected data principals as required under DPDP Act 2023.",
                "Take remedial action to contain the breach.",
            ])
        elif exposure_status == "suspected":
            claims.append(
                "Personal data exposure is SUSPECTED: the affected slice may carry "
                "identifiable patient or subscriber information. Confirmed exposure "
                "cannot be established from current facts — further investigation required."
            )
            uncertainty_notes.append(
                "Whether patient/subscriber data has actually been accessed or exfiltrated "
                "is UNKNOWN at this stage. The DPDP Act 2023 obligations are contingent "
                "on confirmed exposure — they should be prepared but not yet reported "
                "as triggered."
            )
            obligations.extend([
                "Investigate whether identifiable personal data was accessible on the "
                "affected slice.",
                "Prepare for DPDP Act 2023 notification obligations pending confirmation.",
            ])
        else:
            claims.append(
                "Personal data involvement is UNKNOWN at this stage. "
                "No direct indicators of personal data exposure are present in the "
                "current chunk."
            )
            uncertainty_notes.append(
                "Privacy Agent will reassess when further incident facts are released."
            )

        # DPDP Act always in scope once a healthcare/subscriber slice is mentioned
        if exposure_status in ("confirmed", "suspected"):
            claims.append(
                "The Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025 "
                "are the primary Indian instruments governing this potential data "
                "exposure. Exact notification thresholds require KB retrieval."
            )

        missing_facts.extend([
            "Confirmation of whether patient/subscriber data is processed on the affected slice.",
            "Whether the slice operator is a 'data fiduciary' under DPDP Act 2023.",
            "Volume and category of personal data potentially exposed.",
        ])

        return AgentFinding(
            agent_id                 = AgentID.PRIVACY,
            chunk_id                 = chunk.chunk_id,
            summary                  = (
                f"Privacy assessment: personal data exposure status is "
                f"'{exposure_status}'. DPDP Act 2023 obligations "
                f"{'are triggered' if exposure_status == 'confirmed' else 'may be triggered pending confirmation'}."
            ),
            claims                   = claims,
            evidence                 = evidence,
            obligations              = obligations,
            responsible_institutions = institutions,
            exposure_status          = exposure_status,
            uncertainty_notes        = uncertainty_notes,
            missing_facts            = missing_facts,
        )
