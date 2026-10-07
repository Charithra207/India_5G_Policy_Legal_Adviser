"""
Build the incident-response knowledge-base index — ONCE.
=========================================================
    python -m kb.build_index [--src "knowledge base"]

Run by one person; the result in kb/index/ is committed and everyone else
only loads it (kb/retriever.py).  Nobody else needs the PDFs, Tesseract or a
rebuild.

Steps
-----
1. Every PDF in the source folder (default: data/knowledge_base/ if present,
   else "knowledge base/"), de-duplicated by SHA-256.
2. Text per page with PyMuPDF; lines containing Devanagari are dropped (the
   Hindi half of bilingual Gazette notifications).  A document with no text
   layer is OCR'd with Tesseract (pytesseract), page by page.
3. Chunks of ~450 tokens with ~80 tokens overlap (bge-small-en-v1.5 reads at
   most 512 tokens), each with its source file and page range.
4. One primary category per document (kb/categories.py), stored on every chunk.
5. Embeddings: BAAI/bge-small-en-v1.5 (fastembed, CPU, 384-d, L2-normalised).
6. One FAISS inner-product index per category (kb/index/<category>.faiss), so
   a search touches only the categories asked for; chunk text and metadata in
   kb/index/chunks.jsonl.gz; kb/index/manifest.json with the document →
   category map, counts, file hashes and an overall index hash.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from kb.categories import CATEGORIES, classify

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "kb" / "index"
MODEL_ID = "BAAI/bge-small-en-v1.5"
CHUNK_WORDS, OVERLAP_WORDS = 340, 60          # ≈ 450 and ≈ 80 tokens
MIN_CHARS = 80
OCR_DPI = 200
_DEVANAGARI = re.compile(r"[\u0900-\u097F]")


def default_source() -> Path:
    for candidate in (ROOT / "data" / "knowledge_base", ROOT / "knowledge base"):
        if candidate.is_dir():
            return candidate
    raise SystemExit("No source folder: put the PDFs in data/knowledge_base/ or pass --src")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _clean(text: str) -> str:
    lines = [l for l in text.splitlines() if l.strip() and not _DEVANAGARI.search(l)]
    return " ".join(" ".join(lines).split())


def _ocr_pages(doc) -> list[str]:
    import pymupdf
    import pytesseract
    from PIL import Image

    cmd = os.environ.get("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if Path(cmd).exists():
        pytesseract.pytesseract.tesseract_cmd = cmd
    pages = []
    for page in doc:
        pix = page.get_pixmap(matrix=pymupdf.Matrix(OCR_DPI / 72, OCR_DPI / 72))
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        pages.append(_clean(pytesseract.image_to_string(image, lang="eng")))
    return pages


def extract(path: Path) -> tuple[list[str], int, str]:
    """(page texts, OCR'd page count, head text for classification)."""
    import pymupdf

    with pymupdf.open(path) as doc:
        pages = [_clean(p.get_text()) for p in doc]
        ocr = 0
        if sum(len(p) for p in pages) < 100 * max(1, len(pages)) * 0.2:   # no usable text layer
            try:
                pages = _ocr_pages(doc)
                ocr = len(pages)
            except Exception as exc:  # noqa: BLE001 — recorded in the manifest
                print(f"   OCR failed for {path.name}: {exc}")
    return pages, ocr, " ".join(pages[:3])


def chunk(pages: list[str]) -> list[tuple[str, int, int]]:
    """(text, first page, last page) windows of CHUNK_WORDS words."""
    words: list[tuple[str, int]] = [(w, i + 1) for i, text in enumerate(pages) for w in text.split()]
    out, step = [], CHUNK_WORDS - OVERLAP_WORDS
    for start in range(0, max(1, len(words)), step):
        window = words[start:start + CHUNK_WORDS]
        if not window:
            break
        text = " ".join(w for w, _ in window)
        if len(text) >= MIN_CHARS:
            out.append((text, window[0][1], window[-1][1]))
        if start + CHUNK_WORDS >= len(words):
            break
    return out


def build(src: Path) -> dict:
    import faiss
    from src.rag.embedding import get_embedder

    started = time.time()
    pdfs = sorted(p for p in src.iterdir() if p.suffix.lower() == ".pdf")
    seen: dict[str, str] = {}
    documents, chunks = [], []
    for i, path in enumerate(pdfs, 1):
        data = path.read_bytes()
        sha = _sha256(data)
        if sha in seen:
            documents.append({"file": path.name, "sha256": sha, "status": f"duplicate of {seen[sha]}"})
            continue
        seen[sha] = path.name
        pages, ocr, head = extract(path)
        category, rule = classify(path.name, head)
        pieces = chunk(pages)
        for text, p1, p2 in pieces:
            chunks.append({"doc": path.name, "category": category, "page_start": p1, "page_end": p2,
                           "text": text})
        documents.append({"file": path.name, "sha256": sha, "category": category, "rule": rule,
                          "pages": len(pages), "ocr_pages": ocr, "chunks": len(pieces),
                          "status": "indexed" if pieces else "no text extracted"})
        print(f"[{i}/{len(pdfs)}] {category:<24} {len(pieces):>5} chunks {'(OCR)' if ocr else ''} {path.name}")

    print(f"Embedding {len(chunks)} chunks with {MODEL_ID} (CPU) ...")
    embedder = get_embedder(MODEL_ID)
    vectors = np.zeros((len(chunks), 384), dtype=np.float32)
    batch = 512
    for s in range(0, len(chunks), batch):
        vectors[s:s + batch] = embedder.embed_passages([c["text"] for c in chunks[s:s + batch]])
        print(f"   embedded {min(s + batch, len(chunks))}/{len(chunks)}", flush=True)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    rows: dict[str, list[int]] = defaultdict(list)
    for idx, c in enumerate(chunks):
        c["id"] = idx
        c["row"] = len(rows[c["category"]])
        rows[c["category"]].append(idx)
    files: dict[str, str] = {}
    for category in CATEGORIES:
        index = faiss.IndexFlatIP(384)
        if rows[category]:
            index.add(vectors[rows[category]])
        path = INDEX_DIR / f"{category}.faiss"
        faiss.write_index(index, str(path))
        files[path.name] = _sha256(path.read_bytes())
    chunk_path = INDEX_DIR / "chunks.jsonl.gz"
    with gzip.open(chunk_path, "wt", encoding="utf-8", compresslevel=9) as fh:
        for c in chunks:
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    files[chunk_path.name] = _sha256(chunk_path.read_bytes())

    manifest = {
        "_about": "Built once by `python -m kb.build_index`; load with kb/retriever.py. Do not rebuild "
                  "to use it.",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "build_seconds": round(time.time() - started, 1),
        "source_folder": src.name,
        "embedding_model": MODEL_ID, "dimension": 384, "similarity": "cosine (inner product)",
        "chunking": {"words": CHUNK_WORDS, "overlap_words": OVERLAP_WORDS,
                     "approx_tokens": 450, "approx_overlap_tokens": 80},
        "categories": {c: {"documents": sum(1 for d in documents if d.get("category") == c),
                           "chunks": len(rows[c])} for c in CATEGORIES},
        "documents": documents,
        "files": files,
        "index_hash": _sha256("".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()),
    }
    (INDEX_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
    print(f"Wrote kb/index/ ({len(chunks)} chunks) in {manifest['build_seconds']} s; "
          f"index_hash {manifest['index_hash'][:16]}…")
    print(Counter(c["category"] for c in chunks))
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=None)
    args = ap.parse_args(argv)
    build(args.src or default_source())
    return 0


if __name__ == "__main__":
    sys.exit(main())
