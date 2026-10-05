"""
Extraction: source file → ordered text blocks with page provenance.

PDF   — PyMuPDF text layer, one block per line, tagged with its page.
        Bilingual Gazette copies keep English lines only (`english_only`).
        A PDF without a text layer yields nothing; OCR is not attempted, so
        such a source is reported as not ingested rather than guessed at.
DOCX  — body paragraphs in document order; Word heading styles are kept
        as headings (3GPP clause structure).  Tables and figures are not
        extracted (recorded in the manifest provenance note).
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from src.rag.manifest import SourceDocument


@dataclass
class Block:
    text: str
    page: int                 # 1-based page (PDF) or 0 (DOCX: no pages)
    heading_level: int = 0    # >0 for DOCX heading styles


def _ascii_ratio(text: str) -> float:
    letters = [c for c in text if not c.isspace()]
    return sum(c.isascii() for c in letters) / len(letters) if letters else 1.0


def extract_pdf(path: Path, page_range=None, english_only=False) -> list[Block]:
    import pymupdf

    blocks: list[Block] = []
    with pymupdf.open(path) as doc:
        first, last = (page_range or [1, len(doc)])
        for page_no in range(first, last + 1):
            text = doc[page_no - 1].get_text()
            if english_only and _ascii_ratio(text) < 0.85:
                continue      # Hindi half of a bilingual Gazette notification
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if english_only and _ascii_ratio(line) < 0.6:
                    continue
                blocks.append(Block(line, page_no))
    return blocks


def pdf_outline(path: Path) -> list[tuple[int, str, int]]:
    """The PDF's own bookmark outline: (level, title, page)."""
    import pymupdf

    with pymupdf.open(path) as doc:
        return [(lvl, title, page) for lvl, title, page in doc.get_toc()]


_HEADING_STYLE = re.compile(r"^heading\s*(\d)$", re.IGNORECASE)


def extract_docx(path: Path) -> list[Block]:
    import docx

    document = docx.Document(str(path))
    blocks: list[Block] = []
    for para in document.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style = (para.style.name or "") if para.style is not None else ""
        if style.lower().startswith("toc"):
            continue              # table of contents
        match = _HEADING_STYLE.match(style)
        blocks.append(Block(text, 0, int(match.group(1)) if match else 0))
    return blocks


def raw_docx_text(path: Path) -> str:
    """All text runs in the document XML, including text boxes (cover page)."""
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    # Word splits a line into runs ("V19" + ".9.0"): join runs directly and
    # put a space only at paragraph, tab and line breaks.
    xml = re.sub(r"</w:p>|<w:tab/>|<w:br/>", " ", xml)
    return " ".join(re.sub(r"<[^>]+>", "", xml).split())


def extract(doc: SourceDocument) -> list[Block]:
    if doc.file_format == "pdf":
        return extract_pdf(doc.path, doc.page_range, doc.english_only)
    if doc.file_format == "docx":
        return extract_docx(doc.path)
    raise ValueError(f"{doc.id}: unsupported file format {doc.file_format!r}")
