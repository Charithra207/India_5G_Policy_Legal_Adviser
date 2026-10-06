# Privacy / Data Protection KB

## Purpose
Provides personal data protection law evidence to the Privacy Agent.

## Agent
**Privacy Agent** — activated at T2 (when personal data exposure is
suspected or confirmed) and T3 (final consolidated assessment).
Assesses data-protection obligations, breach-notification duties, and
data-fiduciary responsibilities under Indian law.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `dpdp_act_2023` | The Digital Personal Data Protection Act, 2023 | Government of India (Ministry of Law and Justice) | Act | 11 August 2023 | Ingested |
| `dpdp_rules_2025` | Digital Personal Data Protection Rules, 2025 | Government of India (MeitY) | Rules | 13 November 2025 | Ingested |

**KB basis:** DOCX §4.2 row 3; §7.3 Privacy.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 159
- `dpdp_act_2023`: 83 chunks (46 sections)
- `dpdp_rules_2025`: 76 chunks (30 sections)

## Jurisdiction
India (both sources are Indian law). Both are official Gazette notifications.

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/privacy/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered
- DPDP Act 2023: data fiduciary obligations, consent framework, personal
  data breach intimation (Section 8), Data Protection Board of India,
  data principal rights, significant data fiduciaries
- DPDP Rules 2025: implementation rules for the Act — notices, consent
  managers, breach intimation procedures (Rule 7), localisation, retention
- Intersection with telecom: 5G networks processing subscriber data
  are data fiduciaries under the DPDP Act

## Important Limitations
- **Effective status not verified.** Commencement of DPDP Act provisions
  is notified separately and was not checked.
- **Rules 2025 commence in phases** (stated in the Gazette notification);
  phase-level applicability per rule was not checked.
- **Amendments not checked** for either instrument.
- The Verifier will mark supporting claims as **INCOMPLETE** (not VERIFIED)
  because effective status was not verified.

## Sources Not Yet Available
No other privacy-relevant Indian instruments are currently in this KB.
Potential additions for future work:
- IT Act 2000, Section 43A and IT (Reasonable Security Practices) Rules 2011
  (overlap with data-security obligations — not ingested; team decision required)
