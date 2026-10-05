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
            base,
            "telecommunication entity reporting of a security incident and the time limit",
            "types of cyber security incidents that must be reported to CERT-In",
            "measures a telecommunication entity must take to protect telecom cyber security",
        ]
        if any(w in base.lower() for w in ["authentication", "signalling", "suspicious", "unusual"]):
            queries.append(
                "unauthorised access attempts and attacks on network infrastructure"
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
        institutions: list[str] = ["CERT-In", "Department of Telecommunications (DoT)"]
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Cybersecurity event classification — from the released facts
        # ----------------------------------------------------------------
        is_cyber_event = any(
            w in description
            for w in ["authentication", "signalling", "suspicious", "unusual",
                      "attack", "intrusion", "anomal", "unauthori", "control-plane",
                      "control plane"]
        )
        is_exposure = any(
            w in description for w in ["exposed", "exposure", "exfiltrat", "leak", "breach"]
        )

        if is_cyber_event:
            claims.append(
                "The security indicators released in this chunk "
                f"(\"{chunk.description.strip()}\") are consistent with a possible "
                "cybersecurity incident affecting the 5G network, such as an "
                "unauthorised access attempt, a signalling attack, or an exploited "
                "misconfiguration. The cause is not established."
            )
        if is_exposure:
            claims.append(
                "The possible data exposure released in this chunk is a potential "
                "security breach. Whether it resulted from unauthorised access is "
                "not established."
            )
        if not (is_cyber_event or is_exposure):
            if incident_state.get("cyber_event_suspected"):
                claims.append(
                    "A possible cybersecurity incident was identified in an earlier "
                    "chunk; this chunk releases no new security indicators."
                )
            else:
                claims.append(
                    "Current chunk does not contain direct indicators of a cybersecurity "
                    "event. Assessment will be updated if security indicators emerge."
                )
                uncertainty_notes.append(
                    "Performance degradation alone is not classified as a cybersecurity "
                    "event at this stage. Monitoring for additional indicators."
                )

        # What the instruments say — quoted from retrieved passages only.
        # International frameworks are labelled per passage jurisdiction.
        source_claims, citations = self._evidence_or_scope_claims(
            evidence, self.INSTRUMENTS + self.REFERENCE_FRAMEWORKS,
        )
        claims.extend(source_claims)
        obligations = self._duty_passages(evidence)

        if incident_state.get("cii_flagged"):
            institutions.append("NCIIPC (if critical infrastructure is confirmed)")

        missing_facts.extend([
            "Whether the telecommunication entity has reported the anomaly to "
            "CERT-In or DoT is unknown.",
            "Exact nature of the security indicators (protocol, volume, source) "
            "has not been released.",
        ])

        n_cited = len(citations)
        return AgentFinding(
            agent_id             = AgentID.CYBERSECURITY,
            chunk_id             = chunk.chunk_id,
            summary              = (
                "Cybersecurity assessment: "
                + ("possible cybersecurity incident indicated by the released facts. "
                   if (is_cyber_event or is_exposure) else
                   "no new security indicators in this chunk. ")
                + (f"{n_cited} provision(s) quoted from the {self.kb.kb_name}."
                   if n_cited else
                   f"No provisions retrieved from the {self.kb.kb_name}; "
                   "reporting obligations are not assessed.")
            ),
            claims               = claims,
            evidence             = evidence,
            claim_citations      = citations,
            obligations          = obligations,
            responsible_institutions = institutions,
            uncertainty_notes    = uncertainty_notes,
            missing_facts        = missing_facts,
        )
