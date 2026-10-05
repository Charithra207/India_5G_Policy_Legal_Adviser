"""
Source manifest loading (knowledge_base/sources/manifest.json).

The manifest is the curated record of what each source is and where it
came from.  Nothing here asserts a fact the document does not state; see
the "_about" block in the manifest itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

PROJECT_ROOT  = Path(__file__).resolve().parents[2]
KB_ROOT       = PROJECT_ROOT / "knowledge_base"
SOURCES_DIR   = KB_ROOT / "sources"
MANIFEST_PATH = SOURCES_DIR / "manifest.json"

# Knowledge bases defined in DOCX §7.1 / §7.2 — directory name per KB
AGENT_KBS = [
    "technical", "policy_legal", "cybersecurity", "privacy",
    "critical_infrastructure", "standards", "policy_gap",
]
CANONICAL_KB = "canonical"
ALL_KBS = AGENT_KBS + [CANONICAL_KB]


@dataclass
class SourceDocument:
    id: str
    title: str
    status: str
    kbs: list[str]
    kb_basis: str = ""
    authority: str = ""
    jurisdiction: str = ""
    document_type: str = ""
    date_issued: str = ""
    date_evidence: str = ""
    title_evidence: str = ""
    effective_status: str = "not verified"
    amendment_status: str = "not checked"
    provenance_note: str = ""
    related_documents: list[str] = field(default_factory=list)
    institutions: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    source_url: str = ""
    file: str = ""
    file_format: str = ""
    page_range: Optional[list[int]] = None
    english_only: bool = False
    section_style: str = "page"
    section_label: str = "Section"
    attempted_urls: list[str] = field(default_factory=list)

    @property
    def path(self) -> Path:
        return SOURCES_DIR / self.file

    @property
    def ingestible(self) -> bool:
        return self.status == "downloaded" and bool(self.file)


def load_manifest(path: Path = MANIFEST_PATH) -> list[SourceDocument]:
    data = json.loads(path.read_text(encoding="utf-8"))
    known = set(SourceDocument.__dataclass_fields__)
    docs = []
    for raw in data["documents"]:
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"Manifest entry {raw.get('id')} has unknown fields: {sorted(unknown)}")
        bad_kbs = set(raw.get("kbs", [])) - set(ALL_KBS)
        if bad_kbs:
            raise ValueError(f"Manifest entry {raw['id']} assigns unknown KBs: {sorted(bad_kbs)}")
        docs.append(SourceDocument(**raw))
    return docs
