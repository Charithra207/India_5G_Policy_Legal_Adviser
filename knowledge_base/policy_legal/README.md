# Policy & Legal KB

## Purpose
Provides Indian telecommunications law and regulatory framework evidence
to the Policy & Legal Agent.

## Agent
**Policy & Legal Agent** — activated at T2 (when CII or data-exposure is
flagged) and T3 (final consolidated assessment). Identifies applicable
legal provisions, obligations, and institutional responsibilities under
Indian law.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `telecom_act_2023` | The Telecommunications Act, 2023 | Government of India (Ministry of Law and Justice) | Act | 24 December 2023 | Ingested |
| `trai_act_1997` | The Telecom Regulatory Authority of India Act, 1997 (as amended, TDSAT compilation) | Government of India | Act | 1997 | Ingested |
| `ndcp_2018` | National Digital Communications Policy 2018 | Government of India (DoT) | Policy | 2018 | Ingested |
| `ncsp_2013` | National Cyber Security Policy – 2013 | Government of India (DEITY) | Policy | 2013 | Ingested |

**KB basis:** DOCX §4.2 row 1; §7.3 Laws and regulations;
§7.3 Institutional mandates.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 274
- `ncsp_2013`: 45 chunks (41 sections)
- `ndcp_2018`: 46 chunks (13 sections)
- `telecom_act_2023`: 105 chunks (66 sections)
- `trai_act_1997`: 78 chunks (55 sections)

## Jurisdiction
India (all four sources). All are authoritative Indian instruments.

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/policy_legal/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered
- Telecommunications Act 2023: authorisation, spectrum, infrastructure
  sharing, critical telecommunication infrastructure, digital Bharat nidhi
- TRAI Act 1997: TRAI mandate, directions, recommendations, TDSAT
- NDCP 2018: connectivity targets, digital communications policy objectives
- NCSP 2013: national cybersecurity policy objectives and strategies

## Important Limitations
- **Effective status not verified** for any provision. Commencement of
  individual sections of the Telecommunications Act 2023 is notified
  separately and was not checked.
- **Amendments not checked** for TRAI Act 1997 (the TDSAT compilation
  does not state the consolidation date).
- The Verifier will mark supporting claims as **INCOMPLETE** (not VERIFIED)
  because in-force status and amendment history were not verified.
- NCSP 2013 is a policy document, not subordinate legislation; it does not
  by itself impose enforceable obligations.

## Sources Not Yet Ingested
- Indian Telegraph Act, 1885 (related to TRAI Act; not separately ingested)
- DoT and TRAI subordinate directions and notifications (not in this KB)
