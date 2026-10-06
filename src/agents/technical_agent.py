"""
Technical Agent
===============
Mandate (DOCX §3.3):
    Understand what is technically happening.
    - Identify affected 5G components
    - Classify the technical incident and its impact
    - Provide technical context to other agents

Knowledge Base: Technical KB (5G architecture, network slicing, security,
incident-response technical study material; 3GPP TS 23.501, TS 33.501 used
as technical reference).

This agent stays strictly within its technical mandate.  It does NOT
interpret Indian law, data-protection requirements, or institutional
responsibilities — those belong to other agents.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase
from .base_agent import BaseAgent


class TechnicalAgent(BaseAgent):

    MANDATE = (
        "Technical diagnosis of 5G radio, core, network slicing, and "
        "network-function components. Incident classification and impact "
        "assessment from a purely technical perspective."
    )

    # Keywords that suggest 5G technical issues
    TECHNICAL_KEYWORDS = [
        "latency", "packet loss", "session drop", "slicing", "network slice",
        "control plane", "user plane", "authentication", "signalling",
        "radio", "core", "NF", "AMF", "SMF", "UPF", "gNB", "RAN",
        "NFV", "orchestration", "QoS", "throughput", "degradation",
    ]

    # Released-information terms that describe a technical symptom; without
    # one, the agent retrieves nothing
    SYMPTOM_TERMS = (
        "latency", "packet", "delay", "degradation", "quality of service", "qos",
        "session", "connectivity", "drop", "outage", "throughput", "authentication",
        "signalling", "signaling", "control-plane", "control plane", "slice", "radio",
    )

    # Technical references this agent may quote (DOCX §4.1 rows 2–3)
    REFERENCES = [
        "3GPP TS 23.501 (System architecture for the 5G System)",
        "3GPP TS 33.501 (Security architecture and procedures for 5G System)",
    ]

    def __init__(self, kb: Optional[KnowledgeBase] = None) -> None:
        super().__init__(AgentID.TECHNICAL, kb)

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        """
        Frame queries from the Technical Agent's perspective:
        "What are the affected 5G components and what is the technical
        classification of this incident?"
        """
        # The KB is already restricted to technical material, so queries
        # describe the technical question rather than name documents.
        # Symptom queries only for symptoms the released information reports:
        # otherwise passages about symptoms nobody observed would be quoted
        # as if they bore on the incident.
        base = chunk.description
        released = " ".join([base, *chunk.new_facts]).lower()
        # No technical symptom released → nothing technical to look up.
        # (Embedding similarity is not relevance: an unrelated description
        # can still score above the retrieval floor against some clause.)
        if not any(kw in released for kw in self.SYMPTOM_TERMS):
            return []
        queries = [base]
        if any(kw in released for kw in ["latency", "packet", "delay", "degradation", "quality of service", "qos"]):
            queries.append("network slice quality of service, latency and packet delay monitoring")
        if any(kw in released for kw in ["session", "connectivity", "drop"]):
            queries.append("PDU session release and loss of user plane connectivity")
        if any(kw in released for kw in ["authentication", "signalling", "control"]):
            queries.append(
                "authentication of the UE and protection of NAS and RRC signalling"
            )
        return queries

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        description = chunk.description.lower()

        # ----------------------------------------------------------------
        # Determine affected components from what is visible in this chunk
        # ----------------------------------------------------------------
        affected = []
        if any(w in description for w in ["latency", "packet loss", "session drop", "degradation"]):
            affected.extend(["Network Slice (performance layer)", "User Plane Function (UPF)"])
        if any(w in description for w in ["authentication", "signalling", "control-plane", "control plane"]):
            affected.extend(["Control Plane", "Access and Mobility Management Function (AMF)",
                              "Session Management Function (SMF)"])
        if "private 5g" in description or "private network" in description:
            affected.append("Private 5G Network (dedicated slice)")
        if not affected:
            affected.append("Unknown — insufficient telemetry in current chunk")

        # ----------------------------------------------------------------
        # Incident classification
        # ----------------------------------------------------------------
        if any(w in description for w in ["authentication", "signalling", "suspicious", "unusual"]):
            incident_class = "Possible security/cyber event affecting 5G control plane"
        elif any(w in description for w in ["latency", "packet loss", "session drop", "degradation"]):
            incident_class = "Network performance degradation / potential service-quality failure"
        else:
            incident_class = "Undetermined — requires additional telemetry"

        # ----------------------------------------------------------------
        # Claims — grounded in scenario facts, not invented
        # ----------------------------------------------------------------
        claims: list[str] = []
        missing_facts: list[str] = []
        uncertainty_notes: list[str] = self._uncertainty_note_if_stub(evidence)

        claims.append(
            f"The incident involves {', '.join(affected)}."
        )
        claims.append(
            f"Incident classification: {incident_class}."
        )
        if "healthcare" in description or "health" in description:
            claims.append(
                "The affected slice supports a healthcare application, "
                "increasing the criticality of service restoration."
            )
        if any(w in description for w in ["authentication", "signalling"]):
            claims.append(
                "Unusual authentication/signalling behaviour is consistent with "
                "potential 5G control-plane compromise or misconfiguration."
            )

        # What the technical references say — quoted from retrieved passages only
        source_claims, citations = self._evidence_or_scope_claims(
            evidence, self.REFERENCES, label="[REFERENCE ONLY — not Indian law] ",
        )
        claims.extend(source_claims)

        missing_facts.extend([
            "Core network telemetry (AMF/SMF logs) not yet released.",
            "Radio access network (RAN) performance counters not yet available.",
            "Whether the performance degradation is isolated to one slice or system-wide is unknown.",
        ])

        return AgentFinding(
            agent_id            = AgentID.TECHNICAL,
            chunk_id            = chunk.chunk_id,
            summary             = (
                f"Technical assessment: {incident_class}. "
                f"Affected components: {', '.join(affected)}. "
                "Further telemetry required to confirm root cause."
            ),
            claims              = claims,
            evidence            = evidence,
            claim_citations     = citations,
            affected_components = affected,
            incident_class      = incident_class,
            uncertainty_notes   = uncertainty_notes,
            missing_facts       = missing_facts,
        )
