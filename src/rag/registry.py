"""
Live KBRegistry for the core pipeline.

    from src.rag.registry import build_registry
    pipeline = Pipeline(build_registry())

Each agent gets the vector store for its own KB; the Verifier gets the
Canonical KB.  A KB whose store has not been built (or is empty) keeps the
core's stub, which reports itself as not available — the pipeline then says
"no passage retrieved" instead of pretending.
"""

from __future__ import annotations

from pathlib import Path

from src.core.models import AgentID
from src.knowledge_base.kb_registry import KBRegistry
from src.rag.manifest import KB_ROOT
from src.rag.vector_store import VectorStore

# Display names follow DOCX §7.1
KB_NAMES = {
    AgentID.TECHNICAL:      "Technical KB",
    AgentID.POLICY_LEGAL:   "Indian Legal/Regulatory KB",
    AgentID.CYBERSECURITY:  "Cybersecurity KB",
    AgentID.PRIVACY:        "Privacy KB",
    AgentID.CRITICAL_INFRA: "Critical Infrastructure KB",
    AgentID.STANDARDS:      "International Standards KB",
    AgentID.POLICY_GAP:     "International Policy Examples KB",
}


def build_registry(kb_root: Path = KB_ROOT) -> KBRegistry:
    from src.rag.vector_kb import VectorCanonicalKB, VectorKnowledgeBase

    registry = KBRegistry()
    for agent_id, name in KB_NAMES.items():
        directory = kb_root / agent_id.value
        if VectorStore.exists(directory):
            kb = VectorKnowledgeBase(directory, kb_name=name, domain=agent_id.value)
            if kb.is_available():
                registry.agent_kbs[agent_id] = kb
    canonical_dir = kb_root / "canonical"
    if VectorStore.exists(canonical_dir):
        canonical = VectorCanonicalKB(canonical_dir)
        if canonical.is_available():
            registry.canonical_kb = canonical
    return registry
