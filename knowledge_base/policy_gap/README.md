# Policy Gap KB

## Purpose
Provides international policy examples, comparative instruments, and
TRAI AI/data recommendations as reference inputs for the Policy Gap Agent's
coverage analysis.

## Agent
**Policy Gap Agent** — activated at T3 (final assessment, after all other
agents have run). Identifies potential gaps, ambiguities, overlaps, and
emerging-technology coverage issues in the Indian regulatory framework,
using international comparators as reference points only.

The Policy Gap Agent also directly queries the **Canonical KB** (not only
this KB) to examine what Indian instruments say about candidate areas.

## Assigned Sources (from `sources/manifest.json`)

| Document ID | Title | Authority | Type | Date | Status |
|---|---|---|---|---|---|
| `ncsp_2013` | National Cyber Security Policy – 2013 | Government of India (DEITY) | Policy | 2013 | Ingested |
| `ndcp_2018` | National Digital Communications Policy 2018 | Government of India (DoT) | Policy | 2018 | Ingested |
| `trai_ai_bigdata_recs_2023` | TRAI Recommendations on Leveraging AI and Big Data in Telecom | TRAI | Recommendations | 20 July 2023 | Ingested |
| `international_policy_examples` | International policy examples and neighbouring-country comparators | Various | Policy | — | **NOT INGESTED** |

**KB basis:** DOCX §4.3.1; §5.1 mappings 9–11; §7.3 Policy Gap KB;
§7.3 Regional and global comparators.

## Chunk Statistics (from `ingestion_manifest.json`)
- **Total chunks:** 459
- `ncsp_2013`: 45 chunks (41 sections)
- `ndcp_2018`: 46 chunks (13 sections)
- `trai_ai_bigdata_recs_2023`: 368 chunks (285 sections)
- `international_policy_examples`: 0 chunks — **not ingested**

## IMPORTANT: International Comparators Not Yet Available
`international_policy_examples` — neighbouring-country and global policy
comparators — **were not ingested**.

The DOCX states that the exact foreign instruments "must be added to the
final manifest" but does not name them; selecting the comparator
instruments is a project-team decision.

**Consequence:** The Policy Gap Agent cannot yet retrieve international
comparators. When it raises a potential gap, it notes: *"No international
comparator was retrieved for the raised gap(s); the Policy Gap KB holds
no international policy examples yet."*

**Path to resolution:**
1. Identify and download the comparator instruments (team decision)
2. Add entries to `knowledge_base/sources/manifest.json` under the
   `"policy_gap"` KB with appropriate provenance notes
3. Re-run `python -m src.rag.build`
4. No code changes required

## Six Coverage Categories (DOCX §5.1)
The Policy Gap Agent classifies findings into exactly these categories:

| Category | Description |
|---|---|
| `explicit_coverage` | The relevant area is explicitly and unambiguously addressed |
| `partial_coverage` | The area is partially addressed but with significant gaps |
| `unclear_coverage` | Coverage exists but applicability is ambiguous |
| `overlapping_requirements` | Two instruments impose duties for the same trigger without cross-referencing |
| `missing_institutional_clarity` | Unclear which institution leads on an issue |
| `emerging_technology_not_explicitly_addressed` | The technology is not explicitly addressed in Indian instruments |

## Non-Conclusive Language Requirement (DOCX §5.1)
Every potential-gap claim from this agent **must**:
- Use language such as "potential gap", "regulatory ambiguity",
  "not explicitly addressed", "unclear coverage"
- Include the disclaimer:
  *"This is a potential gap or area of regulatory ambiguity identified for
  expert review. No conclusion of policy failure is drawn."*
- **Never** assert "Indian policy is inadequate" or equivalent

## Embedding Model
`BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384 dimensions).

## Vector Store
`knowledge_base/policy_gap/` — built by `python -m src.rag.build`.
Files: `chunks.jsonl`, `vectors.npy`, `index.json`.

## Key Topics Covered (from ingested sources)
- TRAI AI/Big Data Recommendations 2023: AI governance in telecom,
  algorithmic accountability, data sharing frameworks, spectrum management
  with AI, network slicing recommendations (368 chunks across 285 sections)
- NDCP 2018: national digital communications policy objectives; no 5G-specific
  network-slicing provisions found
- NCSP 2013: cybersecurity policy objectives; institution roles (CERT-In,
  NCIIPC) addressed separately, not jointly

## Important Limitations
- International comparators are absent; this is explicitly recorded.
- TRAI recommendations are not law; the agent labels them accordingly.
- In-force and amendment status are not verified for any passage.
