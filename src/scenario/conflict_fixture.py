"""
Conflict demonstration fixture (DOCX §3.5 check 7)
==================================================
The ingested corpus contains no pair of provisions that disagree: the
reporting duties it holds go to different recipients (Central Government,
CERT-In, the Data Protection Board) and are linked as parallel obligations.
To show how the system handles a real disagreement, this module builds
knowledge bases in which two agents retrieve passages that require the
initial report of the same incident to the same recipient within different
time limits.

Every passage here is SYNTHETIC: titles start with "FIXTURE" and authority is
"Test fixture".  They are not quotations of any instrument and must never be
loaded into a real knowledge base.  The scenario, agents, Verifier and
Coordinator are the real ones; only the passages are fixtures.
"""

from __future__ import annotations

from src.core.models import AgentID, EvidenceItem
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase
from src.knowledge_base.kb_registry import KBRegistry

FIXTURE_LABEL = ("FIXTURE knowledge bases — synthetic passages for the conflict "
                 "demonstration; not real instruments")


def _fx(title: str, section: str, excerpt: str) -> EvidenceItem:
    return EvidenceItem(
        source_title=f"FIXTURE {title}", authority="Test fixture", jurisdiction="India",
        document_type="Fixture", section=section, excerpt=excerpt,
        chunk_id=f"fixture:{title}:{section}".replace(" ", "-").lower(),
        provenance_note="Synthetic test passage — not a real instrument.",
    )


# Cybersecurity KB: initial report to CERT-In within 6 hours
REPORTING_DIRECTION = _fx(
    "Incident Reporting Direction (synthetic)", "Direction 4",
    "4. Reporting of security incidents. — Every telecommunication entity shall "
    "report any security incident affecting its network to CERT-In within six "
    "hours of becoming aware of the security incident.",
)

# Policy & Legal KB: initial report of the same incident to CERT-In within 24 hours
REPORTING_CIRCULAR = _fx(
    "Telecom Incident Circular (synthetic)", "Para 3",
    "3. Reporting of security incidents. — A telecommunication entity shall "
    "report a security incident affecting its telecommunication service to "
    "CERT-In within twenty-four hours of becoming aware of the incident.",
)


def conflict_registry() -> KBRegistry:
    """Registry whose Cybersecurity and Policy & Legal KBs disagree."""
    registry = KBRegistry()
    registry.agent_kbs[AgentID.CYBERSECURITY] = InMemoryKnowledgeBase(
        "Cybersecurity fixture KB", "cybersecurity", [REPORTING_DIRECTION])
    registry.agent_kbs[AgentID.POLICY_LEGAL] = InMemoryKnowledgeBase(
        "Policy & Legal fixture KB", "policy_legal", [REPORTING_CIRCULAR])
    registry.canonical_kb = InMemoryCanonicalKB([REPORTING_DIRECTION, REPORTING_CIRCULAR])
    return registry
