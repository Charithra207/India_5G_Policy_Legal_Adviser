"""
Cybersecurity Agent
===================
Mandate (DOCX §3.3):
    Analyse the cybersecurity aspects.
    - Classify the cybersecurity event
    - Identify cybersecurity requirements and incident-response obligations
    - Identify applicable frameworks and relevant institutions

Knowledge Base: Cybersecurity KB
    Telecom Cyber Security Rules 2024; CERT-In Directions 2022;
    National Cyber Security Policy-2013.

This agent speaks ONLY about cybersecurity classification, Indian
cyber-incident requirements, and relevant institutions.  It does NOT
perform data-protection analysis, technical root-cause diagnosis, or
legal/regulatory assessment beyond cybersecurity obligations.

International frameworks (NIST CSF 2.0, NIST SP 800-61 Rev. 3) are used
as reference/comparison points.  They are NEVER stated as Indian law.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent


class CybersecurityAgent(BaseAgent):

    MANDATE = (
        "Cybersecurity event classification, Indian cybersecurity and telecom-"
        "security obligations, incident-response requirements, and relevant "
        "institutions under Indian law."
    )

    INSTRUMENTS = [
        "Telecommunications (Telecom Cyber Security) Rules, 2024",
        "CERT-In Directions, 2022 (under Section 70B IT Act 2000)",
        "National Cyber Security Policy-2013",
    ]

    REFERENCE_FRAMEWORKS = [
        "NIST CSF 2.0 (reference only — not Indian law)",
        "NIST SP 800-61 Rev. 3 (reference only — not Indian law)",
    ]

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.CYBERSECURITY, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        queries = [
            f"Indian telecom cybersecurity incident classification obligations: {base}",
            "Telecom Cyber Security Rules 2024 incident reporting requirements",
            "CERT-In Directions 2022 cyber incident reporting Section 70B IT Act",
        ]
        if any(w in base.lower() for w in ["authentication", "signalling", "suspicious", "unusual"]):
            queries.append(
                "5G control plane attack authentication anomaly cybersecurity "
                "classification CERT-In reporting obligation"
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
        institutions: list[str] = ["CERT-In", "Department of Telecommunications (DoT)"]
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Cybersecurity event classification
        # ----------------------------------------------------------------
        is_cyber_event = any(
            w in description
            for w in ["authentication", "signalling", "suspicious", "unusual",
                      "attack", "intrusion", "anomal", "unauthori"]
        )

        if is_cyber_event:
            claims.append(
                "Unusual authentication/signalling attempts are consistent with "
                "a possible cybersecurity incident affecting the 5G network "
                "(e.g. unauthorised access attempt, signalling attack, or "
                "misconfiguration exploited by a threat actor)."
            )
            claims.append(
                "The Telecommunications (Telecom Cyber Security) Rules, 2024 "
                "impose obligations on telecommunication entities in the event "
                "of a telecom cybersecurity incident. Exact thresholds and "
                "timelines require KB retrieval to confirm."
            )
            claims.append(
                "The CERT-In Directions (28 April 2022, under Section 70B "
                "IT Act 2000) establish reporting requirements for cyber incidents. "
                "Applicability to this specific telecom event requires KB "
                "verification of the defined incident categories."
            )
            obligations.extend([
                "Report cyber incident to CERT-In within the prescribed timeline "
                "(exact timeline requires KB retrieval — CERT-In Directions 2022).",
                "Comply with Telecom Cyber Security Rules 2024 incident-handling "
                "obligations applicable to this telecommunication entity.",
                "Preserve logs and forensic evidence per incident-response requirements.",
            ])
            institutions.append("NCIIPC (if critical infrastructure is confirmed)")
        else:
            claims.append(
                "Current chunk does not contain direct indicators of a cybersecurity "
                "event. Assessment will be updated if security indicators emerge."
            )
            uncertainty_notes.append(
                "Performance degradation alone is not classified as a cybersecurity "
                "event at this stage. Monitoring for additional indicators."
            )

        # Reference-only note for international frameworks
        claims.append(
            "[REFERENCE ONLY — not Indian law] NIST CSF 2.0 Detect/Respond "
            "functions and NIST SP 800-61 Rev. 3 incident-response guidance "
            "provide comparable international reference points for structuring "
            "the incident response."
        )

        missing_facts.extend([
            "Whether the telecommunication entity has reported the anomaly to "
            "CERT-In or DoT is unknown.",
            "Exact nature of the signalling anomaly (protocol, volume, source) "
            "has not been released.",
        ])

        return AgentFinding(
            agent_id             = AgentID.CYBERSECURITY,
            chunk_id             = chunk.chunk_id,
            summary              = (
                "Cybersecurity assessment: unusual authentication/signalling "
                "activity warrants reclassification from performance event to "
                "possible cyber incident. Indian reporting obligations under "
                "Telecom Cyber Security Rules 2024 and CERT-In Directions 2022 "
                "may be triggered. Exact thresholds require KB confirmation."
            ),
            claims               = claims,
            evidence             = evidence,
            obligations          = obligations,
            responsible_institutions = institutions,
            uncertainty_notes    = uncertainty_notes,
            missing_facts        = missing_facts,
        )
