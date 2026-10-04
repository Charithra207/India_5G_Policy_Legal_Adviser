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
        base = chunk.description
        queries = [
            f"5G network slice performance degradation causes: {base}",
            "affected 5G components network function failure root cause",
            "3GPP TS 23.501 network slice architecture service quality",
        ]
        # Add query for control-plane anomalies if signalling is mentioned
        if any(kw in base.lower() for kw in ["authentication", "signalling", "control"]):
            queries.append(
                "5G control plane abnormal authentication signalling 3GPP TS 33.501"
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
                "potential 5G control-plane compromise or misconfiguration "
                "(reference: 3GPP TS 33.501 security procedures)."
            )

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
            affected_components = affected,
            incident_class      = incident_class,
            uncertainty_notes   = uncertainty_notes,
            missing_facts       = missing_facts,
        )
