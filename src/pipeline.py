"""
Pipeline Entry Point
====================
Wires together the KBRegistry, Verifier, Coordinator, and SwarmOrchestrator
into a single callable pipeline.

Usage
-----
    from src.pipeline import Pipeline
    pipeline = Pipeline()
    record   = pipeline.run_chunk(chunk)

To enable live RAG, pass a KBRegistry instance populated with real
KnowledgeBase subclasses.  See INTEGRATION_RAG_KB.md.
The UI layer calls pipeline.run_chunk() for each scenario chunk.
See INTEGRATION_UI.md.
"""

from __future__ import annotations

import logging

from src.core.models import AuditRecord, ScenarioChunk
from src.core.verifier     import Verifier
from src.core.coordinator  import Coordinator
from src.core.orchestrator import SwarmOrchestrator
from src.knowledge_base.kb_registry import KBRegistry

logger = logging.getLogger(__name__)


class Pipeline:
    """
    Top-level pipeline for the India 5G Policy & Legal Adviser.

    Parameters
    ----------
    kb_registry : KBRegistry instance.  Pass a custom registry with real
                  KBs to enable live RAG.  Defaults to stub registry.
    """

    def __init__(self, kb_registry: KBRegistry | None = None) -> None:
        self.registry    = kb_registry or KBRegistry()
        self.verifier    = Verifier(canonical_kb=self.registry.canonical_kb)
        self.coordinator = Coordinator()
        self.orchestrator = SwarmOrchestrator(
            verifier    = self.verifier,
            coordinator = self.coordinator,
            agent_kbs   = self.registry.agent_kbs,
        )

        kb_status = self.registry.status_report()
        live_kbs  = [k for k, v in kb_status.items() if v]
        stub_kbs  = [k for k, v in kb_status.items() if not v]
        logger.info("Pipeline initialised.")
        logger.info("  Live KBs : %s", live_kbs or "none")
        logger.info("  Stub KBs : %s", stub_kbs)

    def run_chunk(self, chunk: ScenarioChunk) -> AuditRecord:
        """
        Process a single scenario chunk end-to-end.

        chunk → Orchestrator → Agents → Verifier → Coordinator → AuditRecord
        """
        return self.orchestrator.process_chunk(chunk)

    def run_scenario(self, chunks: list[ScenarioChunk]) -> list[AuditRecord]:
        """
        Process all chunks in a scenario in order.
        Each chunk's results feed into the incident state for the next.
        """
        records: list[AuditRecord] = []
        for chunk in chunks:
            record = self.run_chunk(chunk)
            records.append(record)
        return records

    @property
    def incident_state(self) -> dict:
        """Current accumulated incident state across all processed chunks."""
        return self.orchestrator.incident_state
