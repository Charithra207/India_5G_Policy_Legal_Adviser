# Critical Infrastructure KB

## Purpose
Provides critical (information) infrastructure protection law evidence
to the Critical Infrastructure Agent.

## Agent
**Critical Infrastructure Agent** — activated at T2 (when a CII-relevant
service is involved) and T3 (final assessment). Assesses whether the
affected network or service qualifies as critical telecommunication
infrastructure or critical information infrastructure, and identifies
applicable protection obligations.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `telecom_act_2023` | The Telecommunications Act, 2023 | Government of India (Ministry of Law and Justice) | Act | 24 December 2023 | Ingested |
| `nciipc_rules_2013` | IT (NCIIPC and Manner of Performing Functions and Duties) Rules, 2013 | Government of India | Rules | 2013 | **NOT INGESTED** |

**KB basis:** DOCX §4.2 row 4; §7.3 Critical Infrastructure.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 105
- `telecom_act_2023`: 105 chunks (66 sections)
- `nciipc_rules_2013`: 0 chunks — **not ingested** (source unavailable)

## Jurisdiction
India (both assigned sources are Indian law).

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/critical_infrastructure/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered (from ingested source)
- Telecommunications Act 2023: critical telecommunication infrastructure
  designation, government powers over telecom infrastructure in security
  emergencies, interconnection obligations

## IMPORTANT: Missing Source
`nciipc_rules_2013` — the IT (NCIIPC) Rules 2013 — **could not be ingested**.
Both IndiaCode and the NCIIPC website were unresponsive at retrieval time.

**Consequence:** The Critical Infrastructure KB currently cannot confirm:
- The formal NCIIPC designation criteria for Critical Information
  Infrastructure (CII)
- NCIIPC's statutory functions and authority
- Operator obligations to NCIIPC as designated CII owners

The agent's claims about NCIIPC roles are marked **UNSUPPORTED** by the
Verifier until this source becomes available.

**What the agent can confirm from ingested text:**
- Critical telecommunication infrastructure under the Telecommunications
  Act 2023 (from the 105 ingested chunks)

## Important Limitations
- **Effective status not verified** for any provision.
- **Amendments not checked.**
- The NCIIPC gap is explicitly recorded in `sources/manifest.json` and
  `ingestion_manifest.json`.

## Path to Resolution
When the NCIIPC Rules 2013 become retrievable:
1. Download and save to `knowledge_base/sources/raw/nciipc_rules_2013.pdf`
2. Update `knowledge_base/sources/manifest.json`: change `status` to
   `"downloaded"` and add `file`, `file_format`, `title_evidence`,
   `date_issued`, `date_evidence`, `section_style`, `section_label`
3. Re-run `python -m src.rag.build` to rebuild all KBs
4. No code changes required — the pipeline picks up the new source
   automatically via the manifest.
