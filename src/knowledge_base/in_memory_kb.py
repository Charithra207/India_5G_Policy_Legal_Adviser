"""
In-memory Knowledge Base
========================
A small, dependency-free KnowledgeBase / CanonicalKnowledgeBase backed by
a list of EvidenceItems and lexical (term-overlap) scoring.

Uses
----
* Tests: exercise the full VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT
  paths without a vector store.
* RAG integration (Member 2): a reference for the `retrieve` contract —
  sorted by relevance, `top_k` respected, `filters` honoured — and a quick
  way to load a handful of real passages before the vector store is ready.

It is NOT a replacement for the vector-store KBs described in DOCX §7.
"""

from __future__ import annotations

from typing import Optional

from src.core.models import EvidenceItem
from src.knowledge_base.base_kb import CanonicalKnowledgeBase, KnowledgeBase
from src.knowledge_base.text_match import content_terms, normalise_section


def _matches_filters(item: EvidenceItem, filters: Optional[dict]) -> bool:
    if not filters:
        return True
    for key, wanted in filters.items():
        actual = getattr(item, key, None)
        if key == "section":
            if normalise_section(str(actual)) != normalise_section(str(wanted)):
                return False
        elif isinstance(actual, str) and isinstance(wanted, str):
            if actual.strip().lower() != wanted.strip().lower():
                return False
        elif actual != wanted:
            return False
    return True


def _score(query: str, item: EvidenceItem) -> float:
    query_terms = content_terms(query)
    if not query_terms:
        return 0.0
    item_terms = content_terms(f"{item.source_title} {item.section} {item.excerpt}")
    return len(query_terms & item_terms) / len(query_terms)


class _InMemoryRetrieval:
    """Shared retrieval logic for the domain and canonical variants."""

    def _init_items(self, items: list[EvidenceItem]) -> None:
        self._items = list(items)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[EvidenceItem]:
        scored: list[EvidenceItem] = []
        for item in self._items:
            if not _matches_filters(item, filters):
                continue
            score = _score(query, item)
            # Filtered lookups (e.g. "this source, this section") return the
            # passage even when the query words differ; unfiltered searches
            # return only passages that share at least one content term.
            if score > 0 or filters:
                scored.append(_with_score(item, score))
        scored.sort(key=lambda e: e.relevance_score, reverse=True)
        return scored[:top_k]

    def is_available(self) -> bool:
        return bool(self._items)


def _with_score(item: EvidenceItem, score: float) -> EvidenceItem:
    return EvidenceItem(**{**item.__dict__, "relevance_score": round(score, 4)})


class InMemoryKnowledgeBase(_InMemoryRetrieval, KnowledgeBase):
    """Domain KB over a fixed list of passages."""

    def __init__(self, kb_name: str, domain: str, items: list[EvidenceItem]) -> None:
        KnowledgeBase.__init__(self, kb_name, domain)
        self._init_items(items)


class InMemoryCanonicalKB(_InMemoryRetrieval, CanonicalKnowledgeBase):
    """Canonical (verification-only) KB over a fixed list of passages."""

    def __init__(self, items: list[EvidenceItem], kb_name: str = "Canonical KB") -> None:
        CanonicalKnowledgeBase.__init__(self, kb_name, "canonical")
        self._init_items(items)

    def scan(self, filters: Optional[dict] = None) -> list[EvidenceItem]:
        return [i for i in self._items if _matches_filters(i, filters)]
