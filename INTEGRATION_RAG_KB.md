# RAG / Knowledge Base Layer

**Project:** India 5G Policy & Legal Adviser
**Component:** specialist agents' knowledge bases, ingestion and retrieval (`src/rag/`)
**Status:** implemented. 23 sources ingested — 15 from the DOCX inventory plus 8 added from the team's source folder (each with an official URL serving a byte-identical file); the NCIIPC Rules and neighbouring-country instruments are not (see [Not ingested](#not-ingested)).

---

## Build and run

```powershell
pip install -r requirements.txt

python -m src.rag.build              # ingest knowledge_base/sources → 8 vector stores (~6–12 min on CPU)
python -m src.rag.retrieval_demo     # one retrieval test per agent → knowledge_base/retrieval_tests.md
python -m src.rag.retrieval_quality  # labelled queries, all 7 agents → knowledge_base/retrieval_quality.md
python -m src.scenario.run --run-id <id>   # record a full run (used by the foundation artefacts)
python -m src.rag.foundation --run outputs/audit/<id>.jsonl   # regenerate the artefacts below
python -m pytest tests -v            # live-KB tests skip if the stores are not built
```

### Knowledge-foundation artefacts (generated — do not edit by hand)

`python -m src.rag.foundation` writes these from the manifests, the built
stores, a recorded run and the DOCX tables. Every quotation is located in a
stored passage and every cited file must exist, or generation fails; DOCX
tables are reproduced verbatim; values not obtained are written as such.

| File | DOCX | Contents |
|---|---|---|
| `knowledge_base/source_manifest.json` | §7.2 final KB manifest | Per document: title, authority, jurisdiction, type, date, effective status, section information, amendment status, URL, licence statement quoted from the document (or "not stated"), open-access note, SHA-256, chunk count, vector index per KB, embedding and generator model |
| `knowledge_base/canonical/canonical_metadata.json` | §7.2 | The §7.2 metadata fields per document; whether it is in the Canonical KB |
| `knowledge_base/host_country_corpus.json` | §7.3 | The ten corpus categories (verbatim), sources obtained, coverage status, institutional-mandate passages |
| `knowledge_base/policy_gap/policy_gap_categories.json` | §5.1 | Six coverage categories (DOCX meanings verbatim), how the agent examines each, the agent's actual output in the recorded run, gap-vs-"no law" rule |
| `knowledge_base/y3172_pipeline_traceability.json` | §4.3 | Each Y.3172 stage: its definition quoted from the ingested Recommendation, the components that perform it, and one quoted provision traced through it |
| `knowledge_base/itu_ai_readiness_mapping.json` | §5.2 | The DOCX's eight readiness perspectives (verbatim) with corpus passages and project artefacts as evidence; no score |

The downloaded source files (`knowledge_base/sources/raw/`), the built
stores and the embedding-model cache are git-ignored. Several sources forbid
redistribution (ITU, 3GPP, ETSI: "no part may be reproduced"), so the
repository holds the manifest, not the files. Download them with
`python -m src.rag.fetch_sources`, which fetches every source from its
official URL and checks it against the recorded SHA-256. Then run the
build.

---

## For Member 1: using the live knowledge bases

The core pipeline does not change. Pass the live registry:

```python
from src.pipeline import Pipeline
from src.rag.registry import build_registry

pipeline = Pipeline(build_registry())   # every agent gets its own KB; the Verifier gets the Canonical KB
record   = pipeline.run_chunk(chunk)
```

To run **one agent** on one chunk (scenario chunk + agent identity → finding):

```python
from src.core.models import AgentID
from src.rag.interface import run_agent

finding = run_agent(AgentID.CYBERSECURITY, chunk, incident_state=None)
finding.claims            # what the agent says
finding.claim_citations   # claim → the passages it quotes (source, section, page, date, URL)
finding.evidence          # every passage retrieved, in retrieval order
finding.uncertainty_notes, finding.missing_facts
```

`build_registry()` falls back to the core's stub for any KB whose store is
missing, so the pipeline still runs; it then reports "no passage retrieved"
rather than pretending.

---

## Pipeline (DOCX §4.3 / §7.4)

| DOCX stage | Implementation | File |
|---|---|---|
| Source | Curated source manifest + official files | `knowledge_base/sources/manifest.json` |
| Collection / extraction | PDF text layer with page numbers (PyMuPDF); 3GPP `.docx` paragraphs and heading styles; English pages only for bilingual Gazette copies | `src/rag/extract.py` |
| Preprocessing / cleaning | Running headers, footers and page numbers removed; hyphenation re-joined | `src/rag/sections.py` |
| Chunking | Within one detected section; ≤ 1,200 characters, 150 overlap | `src/rag/sections.py` |
| Metadata | Every passage carries the full provenance below | `src/rag/build.py` |
| Embedding | `BAAI/bge-small-en-v1.5` (fastembed, ONNX, CPU, 384-d, L2-normalised) | `src/rag/embedding.py` |
| Vector store | One directory per KB: `chunks.jsonl` + `vectors.npy` + `index.json` | `src/rag/vector_store.py` |
| Retrieval | Cosine top-k within the agent's own KB; exact source/section lookups for the Verifier | `src/rag/vector_kb.py` |
| Policy | Canonical KB, used by the Verifier and (read-only) the Policy Gap Agent | `src/core/verifier.py` |
| Distribution | Coordinator assessment | `src/core/coordinator.py` |
| Sandbox | **Not executed.** The ITU AI for Good Sandbox was not available; everything runs locally. The Y.3172 ML sandbox (simulated underlay networks for training and testing ML models) is not implemented either | — |

No generative model is used in the adviser. Agents quote the passages they
retrieve; they do not paraphrase, and they do not answer from model knowledge.

These stage names follow the DOCX. Against ITU-T Y.3172 itself the mapping is
mostly by analogy (only preprocessing corresponds directly), and the SINK,
MLFO, ML Intent, ML sandbox and reference points have no counterpart; see
`knowledge_base/y3172_pipeline_traceability.json`.

---

## The 8 knowledge bases

Each agent KB is a separate store, so **retrieval is restricted to the
agent's own corpus by construction** (DOCX §3.4). The assignments follow the
DOCX; each document's `kb_basis` field in the manifest cites the section.

| KB (directory) | Documents | Passages |
|---|---|---|
| Technical (`technical/`) | 3GPP TS 23.501, TS 33.501 | 3,739 |
| Indian Legal/Regulatory (`policy_legal/`) | Telecommunications Act 2023 + commencement notifications S.O. 2408(E), S.O. 2623(E); TRAI Act 1997; NDCP-2018; NCSP-2013; CTI Rules 2024; NITI Aayog National Strategy for AI | 603 |
| Cybersecurity (`cybersecurity/`) | Telecom Cyber Security Rules 2024 (official DoT copy) + Amendment Rules 2025, CERT-In Directions 2022, NCSP-2013, NDCP-2018; reference: 3GPP TS 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 | 1,680 |
| Privacy (`privacy/`) | DPDP Act 2023, DPDP Rules 2025 | 159 |
| Critical Infrastructure (`critical_infrastructure/`) | Telecommunications Act 2023, Critical Telecommunication Infrastructure Rules 2024 (**NCIIPC Rules 2013 not ingested**) | 126 |
| International Standards (`standards/`) | ITU-T Y.3172, 3GPP TS 23.501, TS 33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61r3 | 4,259 |
| Policy Gap (`policy_gap/`) | TRAI AI & Big Data Recommendations 2023, NCSP-2013, NDCP-2018, NITI Aayog National Strategy for AI, Right of Way Rules 2024; EU policy examples: ENISA 5G Security Controls Matrix, ENISA 5G Cybersecurity Standards | 1,029 |
| Canonical (`canonical/`) | All 23 ingested sources — the common reference beneath every agent KB (DOCX §7.2) | 5,710 |

Open searches skip boilerplate sections (front matter, forewords, reference
and abbreviation lists). Exact section lookups still find them.

---

## Passage metadata (`EvidenceItem`)

| Field | Meaning | Source of the value |
|---|---|---|
| `source_title`, `authority`, `jurisdiction`, `document_type` | What the document is | Manifest |
| `section`, `section_title` | Citation label and printed heading | Detected from the document's own headings or PDF bookmarks |
| `page` | Page(s) of the source file | Extraction |
| `excerpt` | The passage text, verbatim after whitespace clean-up | Extraction |
| `date_issued` | Date as printed in the document | Manifest, **kept only if found verbatim in the text** |
| `effective` | `None` = in-force status **not verified** | Not checked for any source |
| `amendment_checked` / `amendment_note` | `False` / empty: later amendments **not checked** | Not checked for any source |
| `related_documents`, `institutions`, `domains` | As stated by the document | Manifest |
| `url`, `provenance_note` | Where the copy came from, with any caveat | Manifest |
| `chunk_id`, `relevance_score` | Store ID; cosine similarity | Build / retrieval |

**Consequence:** because in-force status and amendments are unchecked, the
Verifier rates a claim fully supported by its cited text as **INCOMPLETE,
never VERIFIED**. To allow VERIFIED for a source, someone must check its
commencement and amendment history. Record that in the manifest, and set
`effective`/`amendment_checked` in `src/rag/build.py` from it; do not set
them by default.

### Section labels

Labels come only from headings printed in the document: "Section 22" (Acts),
"Rule 7" (Rules), "Direction (ii)" / "Annexure I" (CERT-In), "Part IV G"
(NCSP-2013), "Para 3.12" (TRAI recommendations), "Clause 5.15.1" (3GPP Word
headings), and PDF bookmarks (ITU, ETSI, NIST). Text before the first heading
is labelled by page ("p. 2"); no section number is ever inferred.
`ingestion_manifest.json` records, per document, how many sections are
page-only and how many PDF bookmarks could not be located. For example, 31
of ETSI's 189 bookmarks are "x.y.0 General" sub-clauses; their text stays
under the parent clause.

---

## Source manifest and safeguards

- `knowledge_base/sources/manifest.json`: the curated record of every
  source, including the 2 that are not ingested and the URLs tried.
- `knowledge_base/ingestion_manifest.json`: generated by the build. Records
  what was actually ingested: SHA-256, chunk counts, dates confirmed in the
  text, embedding model, and passage counts per KB.

The build **refuses** a file whose `title_evidence` is not in its extracted
text. This rejected a DoT PDF that search results described as the Telecom
Cyber Security Rules; it was an allocation-of-business document.

Provenance caveats recorded in the manifest:

| Source | Caveat |
|---|---|
| TRAI Act 1997 | Taken from TDSAT's "bare acts" compilation, pages 7–52, marked "[AMENDED]"; consolidation date not stated. TRAI's own PDF is a scan with no text; India Code returned HTTP 504 |
| NDCP-2018 | Copy on the Government S3WaaS platform; the dot.gov.in viewer gave no downloadable file |
| Telecom Cyber Security Rules 2024 | Now the official DoT copy (eservices.dot.gov.in); amended by G.S.R. 771(E) — rules 2, 3, 4, 5, 8, 10 carry amendment notes |
| 3GPP TS 23.501 / 33.501 | Latest Release 19 versions on 2026-10-05 (V19.9.0, V19.7.0); the DOCX fixes no version. Tables and figures not ingested |

### Not ingested

| Source | Why | Effect |
|---|---|---|
| IT (NCIIPC) Rules, 2013 | India Code returned HTTP 504 three times; nciipc.gov.in did not respond; not in the team folder | NCIIPC's role cannot be quoted; the Critical Infrastructure KB has the Telecommunications Act and the CTI Rules |
| Neighbouring-country instruments | None obtained; the DOCX names no specific foreign instrument | Policy Gap comparators are EU (ENISA) examples only |

### In-force status and amendments

The manifest's `in_force` and `amended_by` entries quote the authorising
text. The build checks that wording in the obtained document before
applying it, and refuses otherwise. It then sets `effective = true` and an
`effective_status` such as "in force from 26 June 2024 (S.O. 2408(E))",
or an `amendment_note`, on the named sections or rules only.
`amendment_checked` stays false everywhere, so nothing real is VERIFIED.
The evidence audit traces every such status back to its entry.

To add a source: download it to `knowledge_base/sources/raw/`, add a
manifest entry (with `title_evidence`, `date_evidence`, `kbs`, `kb_basis`,
`section_style`), and run the build.

---

## How the Verifier uses the evidence

Agents never state what a law or standard says from memory: each such claim
quotes a passage retrieved from the agent's own KB and records it in
`AgentFinding.claim_citations`. For each claim the Verifier then:

**Cited claim:** looks up the cited source and section in the Canonical KB
(`filters={"source_title": ..., "section": ...}`):

| Canonical KB result | Outcome |
|---|---|
| Cited source/section not found | UNSUPPORTED |
| Found, but the text does not support the claim | UNSUPPORTED |
| Supports, but `effective is False` | UNSUPPORTED |
| Supports, but in-force status or amendments unchecked | INCOMPLETE |
| Supports, `amendment_note` present | INCOMPLETE |
| Supports, in force, amendments checked, none recorded | **VERIFIED** |

**Uncited claim** (an agent's reading of the incident facts): the same
checks against `canonical_kb.retrieve(claim, top_k=5)`.

**Policy Gap examination** ("Potential gap — …", "Coverage check — …"):
every passage it relies on must exist in the Canonical KB. Then it is at
most INCOMPLETE, because a potential gap is for expert review. Absence
claims ("no Indian passage mentions network slicing") use
`CanonicalKnowledgeBase.scan()`, which examines every Indian passage rather
than a top-k sample.

"Supports" is decided by `LexicalSupportJudge` (≥ 60 % of the claim's
content terms occur in the passage). A stronger judge, e.g. an LLM
entailment check, can be passed as `Verifier(canonical_kb, support_judge=...)`.

---

## Retrieval tests

`python -m src.rag.retrieval_demo` runs Scenario 2 through the full pipeline
and writes `knowledge_base/retrieval_tests.md`. For each of the 7 agents it
shows the query, retrieved passage, source, section, page, why it matched,
and the agent's structured output with verifier outcomes. "Why it matched" is
computed: the query that returned the passage, its cosine similarity, and
the query terms that occur in it. Whether a passage *supports* a claim is
shown only by the verifier outcome.

Similarity scores from bge-small cluster at 0.67–0.85 for these queries,
relevant or not. The 0.6 cut-off removes clear noise only; it is not a
relevance judgement.
