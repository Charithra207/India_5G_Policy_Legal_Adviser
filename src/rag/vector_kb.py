"""
Live knowledge bases backed by the vector stores built by src.rag.build.

These implement the core's KnowledgeBase / CanonicalKnowledgeBase contract
(src/knowledge_base/base_kb.py), so the orchestrator, agents and Verifier
use them unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.core.models import EvidenceItem
from src.knowledge_base.base_kb import CanonicalKnowledgeBase, KnowledgeBase
from src.rag.embedding import get_embedder
from src.rag.vector_store import VectorStore

# Cosine similarity below which an unfiltered search result is not returned.
# With bge-small-en-v1.5 the agents' queries score 0.67–0.85 against their
# own KBs, relevant or not, so this floor only removes clear noise: it is
# not a relevance judgement, and passing it does not make a passage evidence
# for a claim — that is the Verifier's job.
DEFAULT_MIN_SCORE = 0.6

_EVIDENCE_FIELDS = set(EvidenceItem.__dataclass_fields__)


def to_evidence(chunk: dict, score: float) -> EvidenceItem:
    data = {k: v for k, v in chunk.items() if k in _EVIDENCE_FIELDS}
    data["relevance_score"] = round(score, 4)
    return EvidenceItem(**data)


class _VectorRetrieval:
    def _init_store(self, directory: Path, min_score: float) -> None:
        self.store = VectorStore(directory)
        self.min_score = min_score
        self.embedder = get_embedder(self.store.info["embedding_model"])

    def retrieve(self, query: str, top_k: int = 5,
                 filters: Optional[dict] = None) -> list[EvidenceItem]:
        """
        Top-k passages by cosine similarity.  With `filters` (e.g. a cited
        source and section) every matching passage is eligible, ranked by
        similarity; without filters, passages below `min_score` are dropped.
        """
        hits = self.store.search(self.embedder.embed_query(query), top_k, filters)
        return [to_evidence(chunk, score) for chunk, score in hits
                if filters or score >= self.min_score]

    def is_available(self) -> bool:
        return bool(self.store.chunks)

    @property
    def documents(self) -> list[str]:
        return self.store.info.get("documents", [])


class VectorKnowledgeBase(_VectorRetrieval, KnowledgeBase):
    """One agent's domain KB: retrieval is restricted to this KB's directory."""

    def __init__(self, directory: Path, kb_name: str, domain: str,
                 min_score: float = DEFAULT_MIN_SCORE) -> None:
        KnowledgeBase.__init__(self, kb_name, domain)
        self._init_store(directory, min_score)


class VectorCanonicalKB(_VectorRetrieval, CanonicalKnowledgeBase):
    """The separate verification corpus (DOCX §7.2)."""

    def __init__(self, directory: Path, kb_name: str = "Canonical KB",
                 min_score: float = DEFAULT_MIN_SCORE) -> None:
        CanonicalKnowledgeBase.__init__(self, kb_name, "canonical")
        self._init_store(directory, min_score)

    def scan(self, filters: Optional[dict] = None) -> list[EvidenceItem]:
        """Exhaustive: every passage matching `filters` (no ranking, no cut-off)."""
        mask = self.store._mask(filters)
        return [to_evidence(c, 0.0) for c, keep in zip(self.store.chunks, mask) if keep]
