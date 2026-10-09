"""
Scenario 2 — Healthcare 5G Private Network Incident
=====================================================
Source: DOCX §2.5 (Second staged 5G incident).

A 5G private-network service supporting a healthcare application experiences
intermittent service degradation.  The event is released in four
time-separated chunks so that later facts are not visible to earlier agent
runs.

Chunk indices match the DOCX table:
    T0 = chunk_index 0
    T1 = chunk_index 1
    T2 = chunk_index 2
    T3 = chunk_index 3

Usage
-----
    from scenarios.scenario2_healthcare_5g import get_chunks, get_chunk
    all_chunks = get_chunks()          # all four, in order
    t0 = get_chunk(0)                  # T0 only
"""

from __future__ import annotations

from src.core.models import ScenarioChunk

# ---------------------------------------------------------------------------
# Chunk definitions — text taken verbatim from DOCX §2.5 table
# ---------------------------------------------------------------------------

_CHUNKS: list[ScenarioChunk] = [

    ScenarioChunk(
        chunk_index = 0,
        chunk_id    = "scenario2_T0",
        timestamp   = "2024-10-04T09:00:00Z",
        description = (
            "Intermittent latency and session drops in the private 5G slice."
        ),
        new_facts   = [
            "A private 5G network slice is experiencing intermittent latency spikes.",
            "Session drops are occurring on the affected slice.",
            "The degradation is intermittent rather than a complete outage.",
            "No additional context about the cause or the service supported "
            "by the slice is available at this stage.",
        ],
        prior_chunks = [],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "technical": [
                'NOC dashboard: one-way latency on the private slice peaks at 180 ms against a 20 ms target; about 3% of PDU sessions on the slice were released abnormally in the last hour.',
            ],
        },
    ),

    ScenarioChunk(
        chunk_index  = 1,
        chunk_id     = "scenario2_T1",
        timestamp    = "2024-10-04T10:30:00Z",
        description  = (
            "Unusual authentication and signalling attempts are observed "
            "on the affected private 5G slice."
        ),
        new_facts    = [
            "Unusual authentication attempts have been detected on the "
            "5G network slice control plane.",
            "Abnormal signalling patterns are being observed alongside "
            "the performance degradation.",
            "The combination of performance issues and security indicators "
            "suggests the incident may have a cybersecurity dimension.",
        ],
        prior_chunks = ["scenario2_T0"],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "technical": [
                'AMF logs: bursts of initial registration requests with repeated SUCIs from one tracking area, without follow-up service requests.',
            ],
            "cybersecurity": [
                'SOC ticket: authentication failures for a small set of subscription identities are about 40 times the baseline, outside business hours; no successful unauthorised access is confirmed yet.',
            ],
            "standards": [
                "The operator's security baseline cites 3GPP TS 33.501 for primary authentication on the slice.",
            ],
        },
    ),

    ScenarioChunk(
        chunk_index  = 2,
        chunk_id     = "scenario2_T2",
        timestamp    = "2024-10-04T12:00:00Z",
        description  = (
            "The slice supports a healthcare application and may carry "
            "identifiable patient information."
        ),
        new_facts    = [
            "The private 5G network slice has been confirmed to support "
            "a healthcare application.",
            "The healthcare application may carry identifiable patient "
            "information.",
            "This introduces critical-infrastructure relevance and potential "
            "personal-data protection implications.",
            "Prior performance and security observations from T0 and T1 "
            "remain unresolved.",
        ],
        prior_chunks = ["scenario2_T0", "scenario2_T1"],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "critical_infrastructure": [
                'Hospital IT confirms the slice carries remote patient-monitoring telemetry for an intensive-care unit.',
            ],
            "privacy": [
                "The hospital's data-protection officer says the telemetry records include patient names and bed numbers.",
            ],
            "policy_legal": [
                "The hospital is a private entity; the slice is provided under the operator's enterprise service agreement.",
            ],
        },
    ),

    ScenarioChunk(
        chunk_index  = 3,
        chunk_id     = "scenario2_T3",
        timestamp    = "2024-10-04T14:00:00Z",
        description  = (
            "The question asks: what should be reported or escalated, "
            "and what policy gap remains?"
        ),
        new_facts    = [
            "No new technical facts; the question is now about reporting, "
            "escalation, and policy gaps.",
            "All prior observations (performance, security indicators, "
            "healthcare/CII relevance, possible personal-data exposure) "
            "are in scope for this assessment.",
            "The assessment must identify what should be reported to which "
            "institution, under which Indian instrument, and flag any "
            "remaining policy gaps or ambiguities.",
        ],
        prior_chunks = ["scenario2_T0", "scenario2_T1", "scenario2_T2"],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "policy_legal": [
                'Management asks which notifications are due today, to whom, and by when.',
            ],
            "cybersecurity": [
                'Core-network logs for the period are kept for 30 days under the current retention setting.',
            ],
            "privacy": [
                "It is not yet confirmed whether any patient record left the operator's network.",
            ],
            "critical_infrastructure": [
                'The operator does not know whether the hospital network or the slice is notified as critical infrastructure.',
            ],
        },
    ),
]


def get_chunks() -> list[ScenarioChunk]:
    """Return all four chunks in chronological order."""
    return list(_CHUNKS)


def get_chunk(index: int) -> ScenarioChunk:
    """Return a single chunk by T-index (0–3)."""
    if index < 0 or index >= len(_CHUNKS):
        raise ValueError(f"Chunk index must be 0–3, got {index}")
    return _CHUNKS[index]
