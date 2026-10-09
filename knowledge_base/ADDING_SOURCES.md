# Adding source documents to the knowledge bases

Use this when you add documents — for example the ITU Sandbox India set
(IndiaAI Governance Guidelines, IT Rules Amendment 2026, TRAI TCCCPR draft,
Bharat 6G documents), global examples (GDPR, NIS2, EU AI Act) or
neighbouring-country instruments.

## 1. Put the file in `knowledge_base/sources/raw/`

PDF or DOCX, the official copy. Raw files are git-ignored; the manifest
records where each came from.

## 2. Add one entry per document to `knowledge_base/sources/manifest.json`

```json
{
  "id": "eu_nis2_directive_2022_2555",
  "title": "Directive (EU) 2022/2555 (NIS2 Directive)",
  "authority": "European Parliament and Council of the European Union",
  "jurisdiction": "European Union",
  "region": "europe",
  "role": "global_example",
  "document_type": "Directive (EU)",
  "date_issued": "14 December 2022",
  "date_evidence": "of 14 December 2022",
  "title_evidence": "DIRECTIVE (EU) 2022/2555",
  "effective_status": "not applicable (EU law; not Indian law)",
  "amendment_status": "not checked",
  "provenance_note": "Official EUR-Lex PDF. Global policy example for comparison only.",
  "related_documents": [],
  "institutions": ["ENISA", "CSIRTs", "competent authorities"],
  "domains": ["incident reporting", "critical entities"],
  "kbs": ["policy_gap", "canonical"],
  "kb_basis": "DOCX 7.1 Policy Gap KB — international policy examples",
  "source_url": "https://eur-lex.europa.eu/eli/dir/2022/2555/oj",
  "file": "raw/eu_nis2_directive_2022_2555.pdf",
  "file_format": "pdf",
  "section_style": "page",
  "section_label": "p.",
  "status": "downloaded"
}
```

Field rules (the build checks them):

| field | rule |
|---|---|
| `title_evidence` | words printed in the document; the build **refuses** a file whose text does not contain them (protects against the wrong file) |
| `date_issued` | kept only if `date_evidence` is found verbatim in the text |
| `jurisdiction` | `India` for Indian instruments; otherwise the country or body — international material is always labelled "reference only, not Indian law" |
| `region` | `india`, `south_asia` (neighbours), `asia_pacific`, `middle_east`, `europe`, `americas`, `africa`, `global` — derived from `jurisdiction` when empty |
| `role` | `indian_law`, `indian_policy`, `indian_guidance`, `standard`, `global_example`, `regional_example`, `reference` |
| `kbs` | which agent KBs get it (`technical`, `policy_legal`, `cybersecurity`, `privacy`, `critical_infrastructure`, `standards`, `policy_gap`) — always add `canonical` so the Verifier can check claims against it |
| `section_style` | `page` is always safe; Indian Acts and Rules can use the section styles already used in the manifest |

Suggested KBs: Indian law and rules → `policy_legal` (+ `cybersecurity` / `privacy` /
`critical_infrastructure` as the topic requires); AI policy and guidelines →
`policy_legal`, `policy_gap`; global and neighbouring-country examples →
`policy_gap`; standards → `standards`.

**IDs the gap register already looks for** (use them and those anchors verify
automatically): `eu_gdpr_2016_679`, `eu_nis2_directive_2022_2555`,
`eu_ai_act_2024_1689`. Other documents are matched by title too
(`title_contains` in `knowledge_base/policy_gap/gap_themes.yaml`).

## 3. Rebuild and regenerate (in this order)

```bash
python -m src.rag.build             # knowledge bases (~10-15 min on CPU)
python -m src.rag.foundation        # manifests, readiness and Y.3172 artefacts
python -m src.rag.evidence_audit    # every citation re-checked against the stores
python -m src.gap.register          # policy-gap register: pending anchors become verified
python -m src.rag.retrieval_demo    # one retrieval test per agent
python -m pytest tests -q
```

To compare a new document in the gap register, add an anchor (with an exact
`phrase` from the document) to `knowledge_base/policy_gap/gap_themes.yaml`
and rerun `python -m src.gap.register`.
