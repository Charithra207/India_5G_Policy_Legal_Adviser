# International Standards KB

## Purpose
Provides international technical and security standards evidence to the
Standards Agent. These are reference points only — not Indian law.

## Agent
**Standards Agent** — activated at T1 (when a cyber/technical event is
suspected) and T3 (final assessment). Compares the incident situation
and applicable Indian obligations against relevant international
standards, always labelling results as `[REFERENCE ONLY — not Indian law]`.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `3gpp_ts_23501` | 3GPP TS 23.501 V19.9.0 — 5G System Architecture, Release 19 | 3GPP | Standard | 2026-09 | Ingested |
| `3gpp_ts_33501` | 3GPP TS 33.501 V19.7.0 — 5G Security Architecture, Release 19 | 3GPP | Standard | 2026-06 | Ingested |
| `etsi_gr_nfv_sec_003` | ETSI GR NFV-SEC 003 V1.3.1 — NFV Security and Trust Guidance | ETSI | Standard | 2024-12 | Ingested |
| `itu_t_y3172` | ITU-T Y.3172 (06/2019) — Architectural framework for ML in future networks | ITU-T | Standard | June 2019 | Ingested |
| `nist_csf_2_0` | NIST CSWP 29: The NIST Cybersecurity Framework (CSF) 2.0 | NIST | Framework | 26 February 2024 | Ingested |
| `nist_sp_800_61r3` | NIST SP 800-61r3: Incident Response Recommendations (CSF 2.0 Community Profile) | NIST | Guidance | April 2025 | Ingested |

**KB basis:** DOCX §4.1 rows 1–6; §7.3 Standards KB.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 4,259
- `3gpp_ts_23501`: 2,648 chunks (930 sections)
- `3gpp_ts_33501`: 1,091 chunks (572 sections)
- `etsi_gr_nfv_sec_003`: 258 chunks (165 sections)
- `itu_t_y3172`: 79 chunks (27 sections)
- `nist_csf_2_0`: 74 chunks (18 sections)
- `nist_sp_800_61r3`: 109 chunks (24 sections)

## Jurisdiction
All international. No Indian law is in this KB.
All Standards Agent claims **must** carry `[REFERENCE ONLY — not Indian law]`.

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/standards/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered
- 3GPP TS 23.501: 5GS architecture, network slicing (NSSF, S-NSSAI),
  PDU session, QoS, service-based architecture
- 3GPP TS 33.501: 5G-AKA, EAP-AKA', NAS/AS security, network slice
  security, SEPP, inter-PLMN security
- ETSI GR NFV-SEC 003: NFV security threats, trust anchors, virtual
  machine isolation, hypervisor security
- ITU-T Y.3172: ML pipeline in future networks (Collection, Preprocessing,
  Model, Policy, Distribution, Sandbox) — the Y.3172-oriented pipeline
  referenced in the DOCX
- NIST CSF 2.0: Govern-Identify-Protect-Detect-Respond-Recover framework;
  organisational cybersecurity risk management
- NIST SP 800-61r3: Incident response lifecycle; integration with CSF 2.0

## Important Limitations
- Standards are international; they are not Indian law and have no direct
  legal force in India.
- In-force/amendment status is not applicable in the same way as Indian
  statutes — these are living standards revised on release cycles.
- The Verifier marks Standards Agent claims as **INCOMPLETE** (never
  VERIFIED) because effective status is not verified and amendment
  history is not checked.
