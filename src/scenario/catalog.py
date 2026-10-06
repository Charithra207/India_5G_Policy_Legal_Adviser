"""
Scenario catalogue
==================
The staged incidents in the DOCX, with the stage table each one is checked
against.

The chunks themselves (the information released at each stage) live in
`scenarios/`.  The tables below are copied from the DOCX: "Primary agents"
and "Expected assessment change" per stage.  They are DISPLAY and CHECK data
only — the Orchestrator selects agents from the released information
(`SwarmOrchestrator._select_agents`) and never reads these tables.  The UI
and the audit trail show both, so a reviewer can see whether the live
selection matches the DOCX.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.core.models import AgentID, ScenarioChunk

_T, _C, _S = AgentID.TECHNICAL, AgentID.CYBERSECURITY, AgentID.STANDARDS
_CII, _P, _PL, _G = (AgentID.CRITICAL_INFRA, AgentID.PRIVACY,
                     AgentID.POLICY_LEGAL, AgentID.POLICY_GAP)


@dataclass(frozen=True)
class StageSpec:
    """One row of a DOCX stage table."""
    label                : str              # "T0" / "Chunk 1"
    information_released : str              # DOCX wording
    primary_agents       : tuple[AgentID, ...]
    expected_change      : str              # DOCX wording


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id   : str
    title         : str
    docx_section  : str
    summary       : str                     # DOCX wording
    stages        : tuple[StageSpec, ...]
    load_chunks   : Callable[[], list[ScenarioChunk]]


def _scenario2_chunks() -> list[ScenarioChunk]:
    from scenarios.scenario2_healthcare_5g import get_chunks
    return get_chunks()


def _scenario1_chunks() -> list[ScenarioChunk]:
    from scenarios.scenario1_slicing_incident import get_chunks
    return get_chunks()


SCENARIOS: dict[str, ScenarioSpec] = {
    "scenario2": ScenarioSpec(
        scenario_id  = "scenario2",
        title        = "Second staged 5G incident — healthcare private 5G slice",
        docx_section = "§2.5",
        summary      = (
            "A 5G private-network service supporting a healthcare application "
            "experiences intermittent service degradation. The event is "
            "deliberately released in four time-separated chunks so that later "
            "facts are not visible to earlier agent runs."
        ),
        stages = (
            StageSpec("T0",
                      "Intermittent latency and session drops in the private 5G slice.",
                      (_T,),
                      "Classify radio/core/slicing/service-quality symptoms; "
                      "identify missing telemetry."),
            StageSpec("T1",
                      "Unusual authentication and signalling attempts are observed.",
                      (_T, _C, _S),
                      "Reassess as a possible security event and retrieve relevant "
                      "5GS/NFV security references."),
            StageSpec("T2",
                      "The slice supports a healthcare application and may carry "
                      "identifiable patient information.",
                      (_CII, _P, _PL),
                      "Assess critical-service relevance, personal-data implications "
                      "and institutional responsibilities."),
            StageSpec("T3",
                      "The question asks what should be reported/escalated and what "
                      "policy gap remains.",
                      (_PL, _C, _P, _CII, _G),
                      "Produce a verified, source-linked assessment, identify "
                      "uncertainty and classify any potential gap without treating "
                      "international standards as Indian law."),
        ),
        load_chunks = _scenario2_chunks,
    ),
    "scenario1": ScenarioSpec(
        scenario_id  = "scenario1",
        title        = "Worked staged 5G incident — network-slicing service",
        docx_section = "§2.4, Annex-1 A.4",
        summary      = (
            "A 5G network-slicing service shows abnormal latency and packet loss."
        ),
        stages = (
            StageSpec("Chunk 1", "High latency and packet loss in a 5G slice",
                      (_T,),
                      "Classify radio/core/slicing performance issue; identify "
                      "missing facts."),
            StageSpec("Chunk 2", "Suspicious control-plane traffic observed",
                      (_T, _C, _S),
                      "Reclassify as possible cyber incident; identify "
                      "response/security references."),
            StageSpec("Chunk 3", "Slice supports a critical service",
                      (_CII, _PL),
                      "Assess critical-infrastructure relevance and institutional "
                      "obligations."),
            StageSpec("Chunk 4", "Subscriber-related data may have been exposed",
                      (_P, _PL, _C),
                      "Assess personal-data implications, reporting/response "
                      "questions and unresolved uncertainty."),
        ),
        load_chunks = _scenario1_chunks,
    ),
}

DEFAULT_SCENARIO = "scenario2"


def get_scenario(scenario_id: str) -> ScenarioSpec:
    try:
        return SCENARIOS[scenario_id]
    except KeyError:
        raise ValueError(f"Unknown scenario {scenario_id!r}; "
                         f"choose from {sorted(SCENARIOS)}") from None
