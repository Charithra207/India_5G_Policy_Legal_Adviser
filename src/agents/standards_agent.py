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
            base,
            "network slice isolation, quality of service and service level",
        ]
        if any(w in base.lower() for w in ["authentication", "signalling", "suspicious", "unusual"]):
            queries.extend([
                "primary authentication procedure and protection against signalling attacks",
                "detecting and analysing a cybersecurity incident and responding to it",
            ])
        if any(w in base.lower() for w in ["nfv", "virtualised", "orchestration"]):
            queries.append("security and trust of virtualised network functions")
        return queries

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        description = chunk.description.lower()
        uncertainty_notes = self._uncertainty_note_if_stub(evidence)
        missing_facts: list[str] = []

        # ----------------------------------------------------------------
        # Which reference standards are in scope for the released facts
        # (DOCX §4.1 "Application in Proposed System" column)
        # ----------------------------------------------------------------
        in_scope = ["3GPP TS 23.501"]
        if any(w in description for w in ["authentication", "signalling", "suspicious",
                                           "unusual", "control-plane", "control plane"]):
            in_scope.append("3GPP TS 33.501")
        if any(w in description for w in ["authentication", "signalling", "suspicious",
                                           "incident", "attack"]):
            in_scope.append("NIST SP 800-61 Rev. 3")
        if any(w in description for w in ["nfv", "virtual", "cloud", "orchestrat"]):
            in_scope.append("ETSI GR NFV-SEC 003")

        # Content of the standards — quoted from retrieved passages only.
        # Every claim carries the reference-only label (DOCX §4).
        claims, quoted = self._evidence_or_scope_claims(
            evidence,
            [f"{std} ({self.STANDARDS[std]})" for std in in_scope],
            label=f"{_REF_LABEL} ",
        )
        citations: dict[str, list[EvidenceItem]] = {}
        labelled: list[str] = []
        for claim in claims:
            text = claim if claim.startswith("[REFERENCE ONLY") else f"{_REF_LABEL} {claim}"
            labelled.append(text)
            if claim in quoted:
                citations[text] = quoted[claim]

        missing_facts.extend([
            "Exact version of 3GPP specifications implemented by the affected network.",
            "Whether the private 5G network uses NFV/virtualised infrastructure.",
        ])

        return AgentFinding(
            agent_id           = AgentID.STANDARDS,
            chunk_id           = chunk.chunk_id,
            summary            = (
                f"Standards assessment: in scope for comparison — {', '.join(in_scope)}. "
                + (f"{len(citations)} passage(s) quoted. " if citations else
                   "No passages retrieved; no comparison is made. ")
                + "All standards are reference points only, not Indian law."
            ),
            claims             = labelled,
            evidence           = evidence,
            claim_citations    = citations,
            standards_compared = in_scope,
            uncertainty_notes  = uncertainty_notes,
            missing_facts      = missing_facts,
        )
