"""
Scenario 1 — 5G Network-Slicing Service Incident
==================================================
Source: DOCX §2.4 (Worked staged 5G incident).

A 5G network-slicing service shows abnormal latency and packet loss.
Chunk 1 contains only the performance symptom.
Subsequent chunks reveal cybersecurity, critical-service, and data-exposure dimensions.

Chunk indices:
    Chunk 1 = chunk_index 0
    Chunk 2 = chunk_index 1
    Chunk 3 = chunk_index 2
    Chunk 4 = chunk_index 3
"""

from __future__ import annotations

from src.core.models import ScenarioChunk

_CHUNKS: list[ScenarioChunk] = [

    ScenarioChunk(
        chunk_index = 0,
        chunk_id    = "scenario1_C1",
        timestamp   = "2024-10-04T08:00:00Z",
        description = (
            "A 5G network-slicing service shows abnormal latency and packet loss."
        ),
        new_facts   = [
            "Abnormal latency observed on a 5G network slice.",
            "Packet loss is occurring on the same slice.",
            "No further information about the cause is available at this stage.",
        ],
        prior_chunks = [],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "technical": [
                "Slice monitoring: latency four times the service-level target and 2% packet loss on the slice's user plane since 07:40.",
            ],
        },
    ),

    ScenarioChunk(
        chunk_index  = 1,
        chunk_id     = "scenario1_C2",
        timestamp    = "2024-10-04T09:00:00Z",
        description  = (
            "Suspicious control-plane traffic is observed on the affected slice."
        ),
        new_facts    = [
            "Suspicious control-plane traffic has been detected.",
            "The Cybersecurity Agent becomes relevant at this stage.",
            "The Orchestrator must update the assessment to include "
            "cybersecurity analysis.",
        ],
        prior_chunks = ["scenario1_C1"],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "technical": [
                'Signalling counters show NAS messages towards the AMF serving the slice from sources that are not registered.',
            ],
            "cybersecurity": [
                "Firewall alert: control-plane traffic from an IP range that is not on the operator's allow-list.",
            ],
            "standards": [
                "The slice's security design references 3GPP TS 33.501 for slice-specific authentication.",
            ],
        },
    ),

    ScenarioChunk(
        chunk_index  = 2,
        chunk_id     = "scenario1_C3",
        timestamp    = "2024-10-04T10:30:00Z",
        description  = (
            "The affected slice supports a critical service."
        ),
        new_facts    = [
            "The network slice has been confirmed to support a critical service.",
            "Critical Infrastructure Agent and Policy & Legal Agent are activated.",
        ],
        prior_chunks = ["scenario1_C1", "scenario1_C2"],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "critical_infrastructure": [
                'The critical service is an emergency-response dispatch application of a state agency.',
            ],
            "policy_legal": [
                'The slice is provided to the state agency under a service agreement with the operator.',
            ],
        },
    ),

    ScenarioChunk(
        chunk_index  = 3,
        chunk_id     = "scenario1_C4",
        timestamp    = "2024-10-04T12:00:00Z",
        description  = (
            "Subscriber-related data may have been exposed."
        ),
        new_facts    = [
            "Subscriber-related data may have been exposed during the incident.",
            "Privacy Agent is added to the active set.",
            "Personal-data protection implications must be assessed.",
        ],
        prior_chunks = ["scenario1_C1", "scenario1_C2", "scenario1_C3"],
        # Released to one agent only (not in the DOCX table; see ScenarioChunk.agent_views)
        agent_views  = {
            "privacy": [
                'The records that may have been exposed include subscriber names and phone numbers.',
            ],
            "policy_legal": [
                'The legal team asks whether the exposure must be reported, to whom and by when.',
            ],
            "cybersecurity": [
                "Exfiltration indicator: an outbound transfer of about 2 GB from the slice's data store to an unknown host.",
            ],
        },
    ),
]


def get_chunks() -> list[ScenarioChunk]:
    return list(_CHUNKS)


def get_chunk(index: int) -> ScenarioChunk:
    if index < 0 or index >= len(_CHUNKS):
        raise ValueError(f"Chunk index must be 0–3, got {index}")
    return _CHUNKS[index]
