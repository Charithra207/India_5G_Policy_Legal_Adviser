"""
Knowledge Base Registry
========================
Central registry that maps each AgentID to its domain KB instance, and
provides the Canonical KB to the Verifier.

Current state: all KBs are stubs.
RAG/KB integration: replace each StubKnowledgeBase with a real subclass
of KnowledgeBase backed by ChromaDB / FAISS.  The registry is the ONLY
place that needs to change — the rest of the pipeline is unaffected.
See INTEGRATION_RAG_KB.md for step-by-step instructions.

Usage
-----
    from src.knowledge_base.kb_registry import KBRegistry
    registry = KBRegistry()
    orchestrator = SwarmOrchestrator(
        verifier    = Verifier(canonical_kb=registry.canonical_kb),
        coordinator = Coordinator(),
        agent_kbs   = registry.agent_kbs,
    )
"""

from __future__ import annotations

from src.core.models import AgentID
from src.knowledge_base.base_kb import (
    CanonicalKnowledgeBase, KnowledgeBase, StubKnowledgeBase,
)


class KBRegistry:
    """
    Holds one KB instance per agent domain plus the Canonical KB.

    RAG/KB integration steps
    ------------------------
    1. Subclass KnowledgeBase (or CanonicalKnowledgeBase) for each domain.
    2. Implement `retrieve(query, top_k, filters)` using your vector store.
    3. Replace the StubKnowledgeBase / CanonicalKnowledgeBase instances
       below with your real implementations.
    4. Ensure `is_available()` returns True when the vector store is ready.

    The pipeline detects `is_available()` automatically and upgrades
    verification outcomes from UNSUPPORTED to VERIFIED as real evidence
    becomes available.
    """

    def __init__(self) -> None:
        # ------------------------------------------------------------------
        # Canonical KB  (used exclusively by the Verifier)
        # ------------------------------------------------------------------
        # Integration: replace with RealCanonicalKB(chroma_client, collection)
        self.canonical_kb: CanonicalKnowledgeBase = CanonicalKnowledgeBase(
            kb_name = "Canonical KB",
            domain  = "canonical",
        )

        # ------------------------------------------------------------------
        # Agent-specific KBs
        # ------------------------------------------------------------------
        # Integration: replace each entry with the real domain KB.
        # Keep the AgentID keys exactly as they are.
        self.agent_kbs: dict[AgentID, KnowledgeBase] = {

            AgentID.TECHNICAL: StubKnowledgeBase(
                kb_name = "Technical KB — 5G architecture & standards",
                domain  = "technical",
                # Sources: 3GPP TS 23.501, TS 33.501, NFV material,
                # 5G incident-response technical study material.
            ),

            AgentID.POLICY_LEGAL: StubKnowledgeBase(
                kb_name = "Indian Legal/Regulatory KB",
                domain  = "policy_legal",
                # Sources: Telecommunications Act 2023, TRAI Act 1997,
                # NDCP-2018, DoT/TRAI directions and notifications.
            ),

            AgentID.CYBERSECURITY: StubKnowledgeBase(
                kb_name = "Cybersecurity KB",
                domain  = "cybersecurity",
                # Sources: Telecom Cyber Security Rules 2024,
                # CERT-In Directions 2022, National Cyber Security Policy-2013.
            ),

            AgentID.PRIVACY: StubKnowledgeBase(
                kb_name = "Privacy KB — DPDP Act & Rules",
                domain  = "privacy",
                # Sources: DPDP Act 2023, DPDP Rules 2025.
            ),

            AgentID.CRITICAL_INFRA: StubKnowledgeBase(
                kb_name = "Critical Infrastructure KB",
                domain  = "critical_infrastructure",
                # Sources: IT (NCIIPC) Rules 2013, Telecommunications
                # Act 2023 critical infra provisions.
            ),

            AgentID.STANDARDS: StubKnowledgeBase(
                kb_name = "International Standards KB",
                domain  = "standards",
                # Sources: ITU-T Y.3172, 3GPP TS 23.501/33.501,
                # ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61 Rev.3.
            ),

            AgentID.POLICY_GAP: StubKnowledgeBase(
                kb_name = "Policy Gap KB — International Policy Examples",
                domain  = "policy_gap",
                # Sources: neighbouring-country comparative instruments,
                # global policy examples (exact instruments listed in manifest).
            ),
        }

    def get_agent_kb(self, agent_id: AgentID) -> KnowledgeBase:
        """Return the KB for the given agent."""
        return self.agent_kbs[agent_id]

    def status_report(self) -> dict[str, bool]:
        """
        Return availability status for each KB (True = live, False = stub).
        Useful for the status display in the UI layer.
        """
        report = {"canonical": self.canonical_kb.is_available()}
        for agent_id, kb in self.agent_kbs.items():
            report[agent_id.value] = kb.is_available()
        return report
