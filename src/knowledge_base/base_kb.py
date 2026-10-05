"""
Abstract Knowledge Base interface.

The RAG/KB layer must subclass KnowledgeBase for each domain KB and for
the Canonical KB.  The core pipeline calls only the methods defined here —
no other KB internals are visible to agents or the verifier.

Integration points
------------------
1.  For each agent KB (7 total):  subclass KnowledgeBase, override `retrieve`.
2.  For the Canonical KB:         subclass CanonicalKnowledgeBase, override
    `retrieve` and optionally `verify_claim`.
3.  Register each concrete KB instance in KBRegistry
    (see src/knowledge_base/kb_registry.py).
4.  The orchestrator calls `agent.retrieve(query)` via the agent, never
    directly against the KB.

The stub implementations in this module return clearly labelled placeholder
results so the core pipeline runs end-to-end without real vector stores.
Replace them with live ChromaDB / FAISS calls via the integration interface
described in INTEGRATION_RAG_KB.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.core.models import EvidenceItem


class KnowledgeBase(ABC):
    """
    Abstract base class for all domain and canonical knowledge bases.

    Parameters
    ----------
    kb_name : str
        Human-readable name used in logs and audit records.
    domain  : str
        The domain this KB covers, e.g. "policy_legal", "cybersecurity".
    """

    def __init__(self, kb_name: str, domain: str) -> None:
        self.kb_name = kb_name
        self.domain  = domain

    @abstractmethod
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[EvidenceItem]:
        """
        Retrieve the top-k most relevant EvidenceItems for `query`.

        Parameters
        ----------
        query   : the agent's retrieval query (framed for its mandate)
        top_k   : maximum number of items to return
        filters : optional metadata filters, e.g. {"jurisdiction": "India"}

        Returns
        -------
        list[EvidenceItem] sorted by descending relevance_score.
        """

    def is_available(self) -> bool:
        """Return True if the underlying vector store is accessible."""
        return True


class StubKnowledgeBase(KnowledgeBase):
    """
    Stub KB used when the real vector store has not yet been integrated.

    Returns a single clearly-labelled placeholder EvidenceItem so the
    pipeline can demonstrate end-to-end flow without real RAG.

    Replace this class (or subclass KnowledgeBase directly) with real
    ChromaDB/FAISS retrieval.  Do NOT change the method signatures.
    See INTEGRATION_RAG_KB.md for step-by-step instructions.
    """

    STUB_NOTE = (
        "[STUB — RAG not yet integrated. "
        "Replace StubKnowledgeBase with a real KnowledgeBase subclass. "
        "See INTEGRATION_RAG_KB.md and src/knowledge_base/base_kb.py.]"
    )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[EvidenceItem]:
        """Return one stub evidence item that makes the stub status visible."""
        return [
            EvidenceItem(
                source_title    = f"[STUB] {self.kb_name} placeholder",
                authority       = "STUB",
                jurisdiction    = "N/A",
                document_type   = "stub",
                section         = "N/A",
                excerpt         = self.STUB_NOTE,
                relevance_score = 0.0,
                chunk_id        = "stub-000",
            )
        ]

    def is_available(self) -> bool:
        return False  # signals to the verifier that RAG is not live


class CanonicalKnowledgeBase(KnowledgeBase):
    """
    Canonical KB used exclusively by the Verifier for claim verification.

    This is a separate corpus from the agent-specific KBs (DOCX §7.2).
    Subclass this and implement `retrieve` with real vector-store calls.
    See INTEGRATION_RAG_KB.md for the required implementation.
    """

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[dict] = None,
    ) -> list[EvidenceItem]:
        """Stub: returns empty list until the real Canonical KB is integrated."""
        return []

    def is_available(self) -> bool:
        """
        Stub: False until the real Canonical KB is integrated, so the
        Verifier reports that verification was impossible rather than that
        a live corpus held no support.  Real subclasses return True.
        """
        return False

    def scan(self, filters: Optional[dict] = None) -> Optional[list[EvidenceItem]]:
        """
        Every passage matching `filters`, or None if this KB cannot enumerate
        its passages.  Used for absence checks ("no Indian passage mentions
        X"), which a top-k search cannot support.
        """
        return None

    def verify_claim(
        self,
        claim: str,
        cited_source: Optional[str] = None,
        cited_section: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Check whether `claim` is supported by a canonical source.

        Returns
        -------
        (supported: bool, rationale: str)

        Implement by retrieving the cited_source/cited_section from the
        Canonical KB and comparing the passage semantically or lexically
        against the claim.  See INTEGRATION_RAG_KB.md.
        """
        return False, (
            "[STUB] Canonical KB not yet populated. "
            "Claim cannot be verified against authoritative sources. "
            "Implement CanonicalKnowledgeBase.verify_claim — see INTEGRATION_RAG_KB.md."
        )
