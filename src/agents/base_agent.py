"""
Abstract base class for all specialist agents.

Design rules (from DOCX §3.3, §3.7)
-------------------------------------
* Each agent speaks ONLY for its defined analytical mandate.
* Each agent has its own domain KB and retrieval mechanism.
* Agents receive (a) the current scenario chunk and (b) the structured
  incident state — nothing more.
* Agents return structured AgentFinding objects with evidence references
  and stated uncertainty.
* Agents do NOT directly override another agent's finding.
* Agents do NOT act as general-purpose chatbots.

The `analyze` method is the single entry point called by the Orchestrator.
It calls `_build_queries` → `_retrieve_evidence` → `_produce_finding`
so that the RAG/KB layer can integrate real retrieval by overriding
`_retrieve_evidence` without touching the analysis logic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase, StubKnowledgeBase

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for the seven specialist agents.

    Parameters
    ----------
    agent_id : the AgentID enum value for this agent
    kb       : the domain-specific KnowledgeBase instance (injected).
               Pass a real KnowledgeBase subclass to enable live RAG.
    """

    def __init__(self, agent_id: AgentID, kb: Optional[KnowledgeBase] = None) -> None:
        self.agent_id = agent_id
        self.kb       = kb or StubKnowledgeBase(
            kb_name = f"{agent_id.value}_stub",
            domain  = agent_id.value,
        )
        logger.debug("Agent %s initialised with KB: %s", agent_id.value, self.kb.kb_name)

    # ------------------------------------------------------------------
    # Public entry point — called by the Orchestrator
    # ------------------------------------------------------------------

    def analyze(self, chunk: ScenarioChunk, incident_state: dict) -> AgentFinding:
        """
        Full analysis pipeline for one scenario chunk.

        Parameters
        ----------
        chunk          : the current ScenarioChunk
        incident_state : the Orchestrator's running structured state dict

        Returns
        -------
        AgentFinding with claims, evidence, and uncertainty clearly separated.
        """
        logger.info("Agent %s -> analyzing chunk %s", self.agent_id.value, chunk.chunk_id)

        queries  = self._build_queries(chunk, incident_state)
        evidence = self._retrieve_evidence(queries)
        finding  = self._produce_finding(chunk, incident_state, evidence)
        finding.agent_id = self.agent_id
        finding.chunk_id = chunk.chunk_id

        logger.info(
            "Agent %s -> produced %d claim(s), %d evidence item(s)",
            self.agent_id.value, len(finding.claims), len(finding.evidence),
        )
        return finding

    # ------------------------------------------------------------------
    # Steps that subclasses implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        """
        Construct the retrieval queries appropriate for this agent's mandate.

        Queries are framed from the agent's perspective:
          - Policy & Legal: "which provisions apply?"
          - Privacy: "is personal data involved?"
          - Technical: "what are the affected components?"
        """

    @abstractmethod
    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        """
        Produce the structured AgentFinding for this chunk.

        IMPORTANT: claims must be grounded in the supplied `evidence`.
        If the evidence is empty or stub-only, claims must be flagged as
        uncertain.  Do not invent legal requirements.
        """

    # ------------------------------------------------------------------
    # Evidence retrieval — RAG/KB integration point
    # ------------------------------------------------------------------

    def _retrieve_evidence(self, queries: list[str]) -> list[EvidenceItem]:
        """
        Run each query against this agent's KB and deduplicate results.

        The default implementation calls `self.kb.retrieve`.  Override
        this method in a subclass for custom retrieval logic such as
        hybrid search or re-ranking.
        """
        seen_chunks: set[str] = set()
        evidence: list[EvidenceItem] = []

        for query in queries:
            items = self.kb.retrieve(query, top_k=5)
            for item in items:
                key = item.chunk_id or f"{item.source_title}::{item.section}"
                if key not in seen_chunks:
                    seen_chunks.add(key)
                    evidence.append(item)

        return evidence

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _evidence_is_real(evidence: list[EvidenceItem]) -> bool:
        """Return True if at least one non-stub evidence item is present."""
        return any(e.chunk_id != "stub-000" and e.authority != "STUB" for e in evidence)

    def _uncertainty_note_if_stub(self, evidence: list[EvidenceItem]) -> list[str]:
        """Return an uncertainty note when only stub evidence is available."""
        if not self._evidence_is_real(evidence):
            return [
                f"[RAG NOT LIVE] {self.agent_id.value} agent findings are "
                "based on scenario text only; no KB evidence was retrieved. "
                "Claims should be treated as preliminary until RAG is integrated."
            ]
        return []
