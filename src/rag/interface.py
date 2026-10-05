"""
Single-agent interface for Member 1 (and for testing one agent in isolation).

    from src.rag.interface import run_agent
    finding = run_agent(AgentID.CYBERSECURITY, chunk)

Input : scenario chunk + agent identity (+ optional incident state)
Output: AgentFinding — claims, the retrieved evidence (source, section, page,
        date, provenance), claim → citation map, uncertainty notes and
        missing facts.  The same object the orchestrator collects.

The full pipeline does not need this: Pipeline(build_registry()) already
routes every agent to its own KB.  This is for running one agent directly.
"""

from __future__ import annotations

from typing import Optional

from src.agents import (
    CriticalInfraAgent, CybersecurityAgent, PolicyGapAgent, PolicyLegalAgent,
    PrivacyAgent, StandardsAgent, TechnicalAgent,
)
from src.core.models import AgentFinding, AgentID, ScenarioChunk
from src.knowledge_base.kb_registry import KBRegistry

_AGENT_CLASSES = {
    AgentID.TECHNICAL:      TechnicalAgent,
    AgentID.POLICY_LEGAL:   PolicyLegalAgent,
    AgentID.CYBERSECURITY:  CybersecurityAgent,
    AgentID.PRIVACY:        PrivacyAgent,
    AgentID.CRITICAL_INFRA: CriticalInfraAgent,
    AgentID.STANDARDS:      StandardsAgent,
}


def empty_incident_state() -> dict:
    """The orchestrator's incident-state shape, with nothing yet established."""
    return {
        "chunks_processed": [], "active_agents_history": {},
        "cii_flagged": False, "data_exposure_suspected": False,
        "cyber_event_suspected": False, "verified_findings": [],
        "active_agents": [],
    }


def make_agent(agent_id: AgentID, registry: KBRegistry):
    if agent_id == AgentID.POLICY_GAP:
        return PolicyGapAgent(
            registry.agent_kbs[AgentID.POLICY_GAP],
            canonical_kb=registry.canonical_kb,
            standards_kb=registry.agent_kbs[AgentID.STANDARDS],
        )
    return _AGENT_CLASSES[agent_id](registry.agent_kbs[agent_id])


def run_agent(
    agent_id: AgentID,
    chunk: ScenarioChunk,
    incident_state: Optional[dict] = None,
    registry: Optional[KBRegistry] = None,
) -> AgentFinding:
    if registry is None:
        from src.rag.registry import build_registry
        registry = build_registry()
    state = empty_incident_state()
    state.update(incident_state or {})
    return make_agent(agent_id, registry).analyze(chunk, state)
