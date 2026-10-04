# RAG / Knowledge Base Integration

**Project:** India 5G Policy & Legal Adviser  
**Component:** RAG layer and domain knowledge bases  

---

## Overview

The pipeline runs end-to-end with stub knowledge bases.  This document
describes how to replace the stubs with real vector-store retrieval.
No pipeline code needs to change — only the KB registry.

---

## The single integration contract

Every agent calls exactly one method on its KB:

```python
kb.retrieve(query: str, top_k: int = 5, filters: dict | None = None) -> list[EvidenceItem]
```

The `EvidenceItem` dataclass (defined in `src/core/models.py`) is the
data contract between the RAG layer and the rest of the pipeline:

```python
@dataclass
class EvidenceItem:
    source_title    : str        # e.g. "Telecommunications Act, 2023"
    authority       : str        # e.g. "Government of India"
    jurisdiction    : str        # e.g. "India" or "ITU"
    document_type   : str        # "Act" | "Rule" | "Direction" | "Standard" | "Policy"
    section         : str        # e.g. "Section 22" or "TS 33.501 §6.1"
    excerpt         : str        # the verbatim or summarised passage
    date_issued     : str        # ISO-8601, e.g. "2023-12-26"
    effective       : bool       # True if currently in force
    amendment_note  : str        # any known amendment affecting this passage
    url             : str        # canonical URL for the source
    chunk_id        : str        # your vector-store chunk ID
    relevance_score : float      # 0.0–1.0 similarity score
```

Fill every field you can.  The Verifier uses:
- `chunk_id` for deduplication
- `authority` to detect stub evidence (skips items where `authority == "STUB"`)
- `relevance_score` to filter weak matches (threshold 0.5 for Canonical KB)
- `amendment_note` to flag `INCOMPLETE` outcomes

---

## Step 1 — Subclass `KnowledgeBase` for each domain

```python
# src/knowledge_base/real_kbs.py  (create this file)

from src.knowledge_base.base_kb import KnowledgeBase, CanonicalKnowledgeBase
from src.core.models import EvidenceItem

class TechnicalKB(KnowledgeBase):
    def __init__(self, chroma_client, collection_name: str):
        super().__init__(kb_name="Technical KB", domain="technical")
        self.collection = chroma_client.get_collection(collection_name)

    def retrieve(self, query: str, top_k: int = 5, filters=None) -> list[EvidenceItem]:
        results = self.collection.query(query_texts=[query], n_results=top_k)
        items = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i]
            items.append(EvidenceItem(
                source_title    = meta.get("source_title", ""),
                authority       = meta.get("authority", ""),
                jurisdiction    = meta.get("jurisdiction", "India"),
                document_type   = meta.get("document_type", ""),
                section         = meta.get("section", ""),
                excerpt         = doc,
                date_issued     = meta.get("date_issued", ""),
                effective       = meta.get("effective", True),
                amendment_note  = meta.get("amendment_note", ""),
                url             = meta.get("url", ""),
                chunk_id        = results["ids"][0][i],
                relevance_score = 1 - results["distances"][0][i],
            ))
        return items

    def is_available(self) -> bool:
        return True
```

Repeat for each of the 7 domain KBs.

For the **Canonical KB**, subclass `CanonicalKnowledgeBase`:

```python
class RealCanonicalKB(CanonicalKnowledgeBase):
    def __init__(self, chroma_client, collection_name: str):
        super().__init__(kb_name="Canonical KB", domain="canonical")
        self.collection = chroma_client.get_collection(collection_name)

    def retrieve(self, query, top_k=5, filters=None) -> list[EvidenceItem]:
        # same pattern as above
        ...

    def is_available(self) -> bool:
        return True
```

The Canonical KB is used **exclusively by the Verifier** for independent
claim verification.  It must be stored in a separate collection from the
agent KBs (DOCX §7.2).

---

## Step 2 — Register real KBs in `KBRegistry`

Open `src/knowledge_base/kb_registry.py`.  Replace each `StubKnowledgeBase`
with your real implementation.  The `AgentID` keys must not change.

```python
from src.knowledge_base.real_kbs import (
    TechnicalKB, PolicyLegalKB, CybersecurityKB,
    PrivacyKB, CriticalInfraKB, StandardsKB, PolicyGapKB,
    RealCanonicalKB,
)
import chromadb

class KBRegistry:
    def __init__(self):
        client = chromadb.HttpClient(host="localhost", port=8000)

        self.canonical_kb = RealCanonicalKB(client, "canonical_kb")

        self.agent_kbs = {
            AgentID.TECHNICAL:      TechnicalKB(client, "technical_kb"),
            AgentID.POLICY_LEGAL:   PolicyLegalKB(client, "policy_legal_kb"),
            AgentID.CYBERSECURITY:  CybersecurityKB(client, "cybersecurity_kb"),
            AgentID.PRIVACY:        PrivacyKB(client, "privacy_kb"),
            AgentID.CRITICAL_INFRA: CriticalInfraKB(client, "critical_infra_kb"),
            AgentID.STANDARDS:      StandardsKB(client, "standards_kb"),
            AgentID.POLICY_GAP:     PolicyGapKB(client, "policy_gap_kb"),
        }
```

---

## Step 3 — Document metadata schema

Each chunk stored in the vector store must carry these metadata fields:

| Field | Type | Required | Example |
|---|---|---|---|
| `source_title` | str | ✓ | "Telecommunications Act, 2023" |
| `authority` | str | ✓ | "Government of India" |
| `jurisdiction` | str | ✓ | "India" |
| `document_type` | str | ✓ | "Act" |
| `section` | str | ✓ | "Section 22(1)" |
| `date_issued` | str | ✓ | "2023-12-26" |
| `effective` | bool | ✓ | true |
| `amendment_note` | str | optional | "Amended by Rule 7, 2025" |
| `url` | str | ✓ | "https://indiacode.nic.in/..." |

---

## Required document corpus per KB (DOCX §7.3)

| KB | Documents |
|---|---|
| Technical KB | 3GPP TS 23.501, TS 33.501, ETSI GR NFV-SEC 003, 5G technical material |
| Policy & Legal KB | Telecommunications Act 2023, TRAI Act 1997, NDCP-2018, DoT/TRAI directions |
| Cybersecurity KB | Telecom Cyber Security Rules 2024, CERT-In Directions 2022, NCSP-2013 |
| Privacy KB | DPDP Act 2023, DPDP Rules 2025 |
| Critical Infra KB | IT (NCIIPC) Rules 2013, Telecom Act 2023 critical infra provisions |
| Standards KB | ITU-T Y.3172, 3GPP TS 23.501/33.501, ETSI GR NFV-SEC 003, NIST CSF 2.0, NIST SP 800-61 Rev.3 |
| Policy Gap KB | Neighbouring-country comparative instruments, international policy examples |
| Canonical KB | Authoritative copies of ALL of the above (separate collection) |

---

## Step 4 — Verify integration

After populating your KBs, run the pipeline tests:

```powershell
python -m pytest tests/test_pipeline.py -v
```

With real KBs active, Indian law claims should move from `UNSUPPORTED`
to `VERIFIED` or `INCOMPLETE`.  Check KB status at any time:

```python
from src.knowledge_base.kb_registry import KBRegistry
registry = KBRegistry()
print(registry.status_report())
# {'canonical': True, 'technical': True, 'policy_legal': True, ...}
```

---

## How the Verifier uses your evidence

The Verifier calls `canonical_kb.retrieve(claim, top_k=3)` for each claim:

1. `relevance_score > 0.5` and no amendment note → **VERIFIED**
2. `relevance_score > 0.5` and amendment note present → **INCOMPLETE**
3. No passage with `relevance_score > 0.5` → **UNSUPPORTED**

---

## What NOT to change

Do not modify:

- `src/core/models.py` — `EvidenceItem` field names are the data contract
- `src/core/verifier.py` — verification logic
- `src/core/orchestrator.py` — agent selection and incident state
- `src/agents/*.py` — agent mandate logic
- `src/knowledge_base/base_kb.py` — the abstract interface

Only modify:

- `src/knowledge_base/kb_registry.py` — swap in real KB instances
- `src/knowledge_base/real_kbs.py` — your new file with real implementations

---

## Integration checklist

- [ ] All 7 domain KBs populated; `is_available()` returns `True`
- [ ] Canonical KB populated separately with authoritative copies
- [ ] `EvidenceItem.chunk_id` set to a real vector-store ID (not `"stub-000"`)
- [ ] `EvidenceItem.authority` is never `"STUB"`
- [ ] `EvidenceItem.relevance_score` populated from actual similarity scores
- [ ] `EvidenceItem.amendment_note` populated where known amendments exist
- [ ] `python -m pytest tests/test_pipeline.py -v` passes after integration
- [ ] At least one claim per agent upgrades from `UNSUPPORTED` to `VERIFIED`
- [ ] KB manifest recorded (title, authority, URL, chunk count, vector index, embedding model)
