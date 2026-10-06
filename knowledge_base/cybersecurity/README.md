# Cybersecurity KB

## Purpose
Provides cybersecurity incident-reporting obligations, security
architecture requirements, and incident-response frameworks to the
Cybersecurity Agent.

## Agent
**Cybersecurity Agent** — activated at T1 (when a cyber event is
suspected) and T3 (final assessment). Identifies applicable cyber
security obligations, reporting duties, and response requirements.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `3gpp_ts_33501` | 3GPP TS 33.501 V19.7.0 — Security architecture for 5G | 3GPP | Standard | 2026-06 | Ingested |
| `certin_directions_2022` | CERT-In Directions under s.70B of IT Act, 2000 (28 April 2022) | CERT-In, MeitY | Direction | 28 April 2022 | Ingested |
| `etsi_gr_nfv_sec_003` | ETSI GR NFV-SEC 003 V1.3.1 — NFV Security and Trust Guidance | ETSI | Standard | 2024-12 | Ingested |
| `ncsp_2013` | National Cyber Security Policy – 2013 | Government of India (DEITY) | Policy | 2013 | Ingested |
| `ndcp_2018` | National Digital Communications Policy 2018 | Government of India (DoT) | Policy | 2018 | Ingested |
| `nist_csf_2_0` | NIST CSWP 29: The NIST Cybersecurity Framework (CSF) 2.0 | NIST | Framework | 26 February 2024 | Ingested |
| `nist_sp_800_61r3` | NIST SP 800-61r3: Incident Response Recommendations | NIST | Guidance | April 2025 | Ingested |
| `telecom_cyber_security_rules_2024` | Telecommunications (Telecom Cyber Security) Rules, 2024 | Government of India (DoT) | Rules | 21 November 2024 | Ingested |

**KB basis:** DOCX §4.2 row 2; §7.3 Digital and cybersecurity strategies.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 1,675
- `3gpp_ts_33501`: 1,091 chunks (572 sections)
- `certin_directions_2022`: 18 chunks (11 sections)
- `etsi_gr_nfv_sec_003`: 258 chunks (165 sections)
- `ncsp_2013`: 45 chunks (41 sections)
- `ndcp_2018`: 46 chunks (13 sections)
- `nist_csf_2_0`: 74 chunks (18 sections)
- `nist_sp_800_61r3`: 109 chunks (24 sections)
- `telecom_cyber_security_rules_2024`: 34 chunks (11 sections)

## Jurisdiction Mix
- **Indian law:** `certin_directions_2022`, `telecom_cyber_security_rules_2024`,
  `ncsp_2013`, `ndcp_2018`
- **International reference:** `3gpp_ts_33501`, `etsi_gr_nfv_sec_003`,
  `nist_csf_2_0`, `nist_sp_800_61r3`

International-source claims carry `[REFERENCE ONLY — not Indian law]`.

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/cybersecurity/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered
- Telecom Cyber Security Rules 2024: mandatory reporting to DoT within 6
  hours of noticing a security incident (Rule 7)
- CERT-In Directions 2022: mandatory 6-hour incident reporting to CERT-In,
  log retention, NTP synchronisation
- NCSP 2013: national cybersecurity objectives and institutional roles
- 3GPP TS 33.501: 5G security architecture, authentication (5G-AKA, EAP-AKA'),
  signalling protection, NAS/AS security
- ETSI GR NFV-SEC 003: NFV-specific security threats and trust guidance
- NIST CSF 2.0: Govern, Identify, Protect, Detect, Respond, Recover
- NIST SP 800-61r3: Incident response lifecycle (Preparation, Detection,
  Analysis, Containment, Eradication, Recovery)

## Important Limitations
- **Effective status not verified** for any provision.
- **Amendments not checked** — a later CERT-In clarification notice
  (27 June 2022) exists and was not ingested.
- The Verifier will mark supporting claims as **INCOMPLETE** for
  Indian-law sources and the claim unsupported if the canonical passage
  is not found.
