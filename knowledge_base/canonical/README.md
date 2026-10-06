# Canonical KB

## Purpose
The Canonical KB is the **independent verification corpus** used
exclusively by the Verifier (DOCX §7.1, §7.2). It is NOT used for
agent retrieval — agents query their own domain KBs.

The Verifier cross-checks every agent claim against the Canonical KB:
- Does the cited source and section exist in the Canonical KB?
- Does the canonical text support the claim?
- Is the provision recorded as not-in-force or subject to an amendment?

## Verifier Outcomes (DOCX §3.5 / Annex-1 A.1)

| Outcome | Condition |
|---|---|
| `VERIFIED` | Cited source/section found; canonical text supports the claim; in force; no amendment recorded |
| `INCOMPLETE` | Supported by canonical text but in-force status unverified or amendment not checked |
| `UNSUPPORTED` | Source/section not found in Canonical KB, or canonical text does not support the claim |
| `CONFLICT` | Another finding or source contradicts the claim |

**Current status:** Because effective status was not verified for any
ingested source, the maximum outcome currently achievable is **INCOMPLETE**
(never VERIFIED). This is honest: the sources were ingested as retrieved,
not verified as in force.

## Assigned Sources (from `sources/manifest.json`)
The Canonical KB contains **all ingested documents** — it is the union of
every agent KB, so the Verifier can independently confirm any citation.

| Document ID | Title | Jurisdiction | Status |
|---|---|---|---|
| `telecom_act_2023` | The Telecommunications Act, 2023 | India | Ingested |
| `trai_act_1997` | TRAI Act 1997 (as amended, TDSAT compilation) | India | Ingested |
| `ndcp_2018` | National Digital Communications Policy 2018 | India | Ingested |
| `telecom_cyber_security_rules_2024` | Telecom Cyber Security Rules 2024 | India | Ingested |
| `certin_directions_2022` | CERT-In Directions 2022 (s.70B, IT Act) | India | Ingested |
| `ncsp_2013` | National Cyber Security Policy 2013 | India | Ingested |
| `dpdp_act_2023` | Digital Personal Data Protection Act 2023 | India | Ingested |
| `dpdp_rules_2025` | Digital Personal Data Protection Rules 2025 | India | Ingested |
| `trai_ai_bigdata_recs_2023` | TRAI AI & Big Data Recommendations 2023 | India | Ingested |
| `itu_t_y3172` | ITU-T Y.3172 (06/2019) — ML in future networks | International | Ingested |
| `3gpp_ts_23501` | 3GPP TS 23.501 V19.9.0 — 5G System Architecture | International | Ingested |
| `3gpp_ts_33501` | 3GPP TS 33.501 V19.7.0 — 5G Security Architecture | International | Ingested |
| `etsi_gr_nfv_sec_003` | ETSI GR NFV-SEC 003 V1.3.1 — NFV Security | International | Ingested |
| `nist_csf_2_0` | NIST CSF 2.0 | International | Ingested |
| `nist_sp_800_61r3` | NIST SP 800-61r3 | International | Ingested |
| `nciipc_rules_2013` | IT (NCIIPC) Rules 2013 | India | **NOT INGESTED** |
| `international_policy_examples` | International policy comparators | International | **NOT INGESTED** |

**KB basis:** DOCX §7.2 — the Canonical KB is distinct from the
agent-specific KBs and is used only by the Verifier and the Policy Gap Agent.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 5,112 (all 15 ingested documents, including the TRAI recommendations, which are labelled as recommendations, not law)

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/canonical/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

The `VectorCanonicalKB` class (`src/rag/vector_kb.py`) also provides a
`scan(filters)` method that returns **every** matching passage without
a top-k cut, needed by the Policy Gap Agent for absence checks ("none of
the Indian passages mention network slicing").

## Important Limitations
- `effective` is `null` (Python `None`) for every passage — in-force status
  was not verified. The Verifier treats `effective=None` as unchecked and
  cannot return VERIFIED.
- `amendment_checked` is `False` for every passage — no amendments were
  checked. The Verifier treats this as INCOMPLETE, not VERIFIED.
- The two unavailable sources (`nciipc_rules_2013`,
  `international_policy_examples`) are absent from this KB. Claims citing
  them will be marked UNSUPPORTED.
- This is an intentional design: the system reports honestly rather than
  fabricating verification it cannot perform.
