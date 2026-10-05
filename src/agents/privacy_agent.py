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
            base,
            "intimation of a personal data breach to the Board and to affected Data Principals",
            "reasonable security safeguards a Data Fiduciary must take to prevent personal data breach",
            "meaning of personal data and personal data breach",
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
        elif incident_state.get("data_exposure_suspected"):
            # Released in an earlier chunk; nothing in this chunk resolves it
            exposure_status = "suspected"
            uncertainty_notes.append(
                "Exposure status carried forward from an earlier chunk; this chunk "
                "releases no new personal-data facts."
            )

        # ----------------------------------------------------------------
        # Claims — exposure status is read from the released facts only
        # ----------------------------------------------------------------
        if exposure_status == "confirmed":
            claims.append(
                "Personal data exposure is CONFIRMED by the incident facts released "
                "in this chunk."
            )
        elif exposure_status == "suspected":
            claims.append(
                "Personal data exposure is SUSPECTED: the affected slice may carry "
                "identifiable patient or subscriber information. Confirmed exposure "
                "cannot be established from current facts — further investigation required."
            )
            uncertainty_notes.append(
                "Whether patient/subscriber data has actually been accessed or exfiltrated "
                "is UNKNOWN at this stage. Data-protection obligations that depend on "
                "confirmed exposure must not be reported as triggered."
            )
        else:
            claims.append(
                "Personal data involvement is UNKNOWN at this stage. "
                "No direct indicators of personal data exposure are present in the "
                "current chunk."
            )
            uncertainty_notes.append(
                "Privacy Agent will reassess when further incident facts are released."
            )

        # What the DPDP framework says — quoted from retrieved passages only
        citations: dict[str, list[EvidenceItem]] = {}
        if exposure_status in ("confirmed", "suspected"):
            source_claims, citations = self._evidence_or_scope_claims(
                evidence, self.INSTRUMENTS,
            )
            claims.extend(source_claims)
            obligations.extend(self._duty_passages(evidence))
            if exposure_status == "suspected" and obligations:
                uncertainty_notes.append(
                    "Obligation passages are quoted for review; exposure is only "
                    "suspected, so whether they are triggered is not established."
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
                f"'{exposure_status}'. "
                + (f"{len(citations)} DPDP provision(s) quoted from the {self.kb.kb_name}."
                   if citations else
                   "No DPDP provisions retrieved; data-protection obligations are not assessed.")
            ),
            claims                   = claims,
            evidence                 = evidence,
            claim_citations          = citations,
            obligations              = obligations,
            responsible_institutions = institutions,
            exposure_status          = exposure_status,
            uncertainty_notes        = uncertainty_notes,
            missing_facts            = missing_facts,
        )
