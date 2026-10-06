# Technical KB

## Purpose
Provides 5G architecture and standards evidence to the Technical Agent.

## Agent
**Technical Agent** — activated at T0 (initial incident detection) and T1
(when a cyber event is suspected). Analyses affected components, traffic
flows, and system-architecture implications.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `3gpp_ts_23501` | 3GPP TS 23.501 V19.9.0 — System architecture for the 5G System (5GS), Release 19 | 3GPP | Standard | 2026-09 | Ingested |
| `3gpp_ts_33501` | 3GPP TS 33.501 V19.7.0 — Security architecture and procedures for 5G system, Release 19 | 3GPP | Standard | 2026-06 | Ingested |

**KB basis:** DOCX §4.1 rows 2–3; §7.3 Technical KB.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 3,739
- `3gpp_ts_23501`: 2,648 chunks (930 sections)
- `3gpp_ts_33501`: 1,091 chunks (572 sections)

## Jurisdiction
International (reference standards — not Indian law).
All claims citing these documents carry the label
`[REFERENCE ONLY — not Indian law]`.

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/technical/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered
- 5G System (5GS) architecture: AMF, SMF, UPF, PCF, UDM, NRF, AUSF
- Network slicing (NSSF, NSI, S-NSSAI, network slice selection)
- PDU Session management and user-plane connectivity
- QoS monitoring, packet-delay variation, URLLC
- 5G security architecture, authentication, and signalling protection
- Non-3GPP access and inter-system mobility

## Limitations
- Tables and figures in the 3GPP `.docx` files are not ingested (body
  paragraphs only — recorded in `sources/manifest.json` provenance notes).
- In-force and amendment status are **not verified** for any passage
  (these are living standards updated on a release cycle).
- These are international standards, not Indian regulations. The
  Verifier will mark supporting claims as **INCOMPLETE** (not VERIFIED)
  because effective status was not checked.
