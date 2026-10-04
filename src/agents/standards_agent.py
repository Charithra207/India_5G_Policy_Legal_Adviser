"""
Standards Agent
================
Mandate (DOCX §3.3):
    Identify relevant international standards and frameworks.
    - Draw on ITU, 3GPP, ETSI, NIST, and other standards organisations
    - Compare the incident with relevant standards
    - Highlight areas needing further consideration, with evidence

CRITICAL RULE (DOCX §4, §3.3, §5.1):
    Standards are REFERENCE POINTS only, not Indian law or formal
    certification.  Every finding from this agent MUST carry the label
    "reference only — not Indian law".

Knowledge Base: International Standards KB
    ITU-T Y.3172; 3GPP TS 23.501; 3GPP TS 33.501;
    ETSI GR NFV-SEC 003; NIST CSF 2.0; NIST SP 800-61 Rev. 3.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent

# Label appended to every claim from this agent
_REF_LABEL = "[REFERENCE ONLY — not Indian law or formal certification]"


class StandardsAgent(BaseAgent):

    MANDATE = (
        "Comparison of the incident with relevant international standards "
        "and frameworks as reference points. Standards are never stated "
        "as Indian legal requirements."
    )

    STANDARDS = {
        "3GPP TS 23.501": "System architecture for the 5G System (5GS)",
        "3GPP TS 33.501": "Security architecture and procedures for 5G System",
        "ETSI GR NFV-SEC 003": "NFV Security; Security and Trust Guidance",
        "NIST CSF 2.0":        "Cybersecurity Framework (reference)",
        "NIST SP 800-61 Rev. 3": "Incident Response Recommendations (reference)",
        "ITU-T Y.3172":        "ML architecture for future networks (reference)",
    }

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.STANDARDS, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        queries = [
            f"3GPP TS 23.501 network slice architecture service quality: {base}",
            "3GPP TS 33.501 5G security authentication signalling procedures",
        ]
        if any(w in base.lower() for w in ["authentication", "signalling", "suspicious"]):
            queries.append(
                "3GPP TS 33.501 security procedures 5G authentication anomaly "
                "NIST SP 800-61 incident response"
            )
        if any(w in base.lower() for w in ["nfv", "virtualised", "orchestration"]):
            queries.append("ETSI GR NFV-SEC 003 virtualised network function security")
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
        standards_compared: list[str] = []
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # 3GPP TS 23.501 — architecture reference
        # ----------------------------------------------------------------
        standards_compared.append("3GPP TS 23.501")
        claims.append(
            f"{_REF_LABEL} 3GPP TS 23.501 defines the 5G System architecture "
            "including network slicing. Intermittent latency and session drops "
            "in a private slice are consistent with service-quality degradation "
            "scenarios addressed in the standard's slice management framework."
        )

        # ----------------------------------------------------------------
        # 3GPP TS 33.501 — security reference (T1 onwards)
        # ----------------------------------------------------------------
        if any(w in description for w in ["authentication", "signalling", "suspicious", "unusual"]):
            standards_compared.append("3GPP TS 33.501")
            claims.append(
                f"{_REF_LABEL} 3GPP TS 33.501 specifies security architecture "
                "and procedures for the 5G System, including authentication "
                "(5G-AKA, EAP-AKA') and protection of control-plane signalling. "
                "Unusual authentication/signalling attempts are a pattern addressed "
                "in this standard's threat model."
            )

        # ----------------------------------------------------------------
        # NIST SP 800-61 Rev. 3 — incident response reference
        # ----------------------------------------------------------------
        if any(w in description for w in ["authentication", "signalling", "suspicious",
                                           "incident", "attack"]):
            standards_compared.append("NIST SP 800-61 Rev. 3")
            claims.append(
                f"{_REF_LABEL} NIST SP 800-61 Rev. 3 (2025) provides incident-"
                "response recommendations that are internationally recognised as "
                "a reference point. The response lifecycle (Detection → Containment → "
                "Eradication → Recovery → Post-incident) is applicable as a "
                "comparative framework."
            )

        # ----------------------------------------------------------------
        # ETSI GR NFV-SEC 003 — if virtualisation is indicated
        # ----------------------------------------------------------------
        if any(w in description for w in ["nfv", "virtual", "cloud", "orchestrat"]):
            standards_compared.append("ETSI GR NFV-SEC 003")
            claims.append(
                f"{_REF_LABEL} ETSI GR NFV-SEC 003 V1.3.1 (2024-12) provides "
                "security and trust guidance for virtualised network functions. "
                "If the affected slice uses NFV/virtualised infrastructure, "
                "this standard's threat categories are relevant as a reference."
            )

        missing_facts.extend([
            "Exact version of 3GPP specifications implemented by the affected network.",
            "Whether the private 5G network uses NFV/virtualised infrastructure.",
        ])

        return AgentFinding(
            agent_id           = AgentID.STANDARDS,
            chunk_id           = chunk.chunk_id,
            summary            = (
                "Standards assessment: 3GPP TS 23.501 and TS 33.501 are the "
                "primary technical reference standards. NIST SP 800-61 Rev. 3 "
                "provides incident-response reference guidance. All standards "
                "are reference points only, not Indian law."
            ),
            claims             = claims,
            evidence           = evidence,
            standards_compared = standards_compared,
            uncertainty_notes  = uncertainty_notes,
            missing_facts      = missing_facts,
        )
