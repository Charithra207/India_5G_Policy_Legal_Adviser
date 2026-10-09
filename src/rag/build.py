"""
Build the knowledge bases from the source manifest.

    python -m src.rag.build

Y.3172-oriented stages (DOCX §4.3) as implemented here:
    Source         knowledge_base/sources/manifest.json + raw/ files
    Collection     extraction with page provenance (src/rag/extract.py)
    Preprocessing  cleaning, section detection, chunking, metadata (sections.py)
    Model          embedding (embedding.py) → vector stores (vector_store.py);
                   retrieval by the seven agents (vector_kb.py)
    Policy         Canonical KB, used by the Verifier (src/core/verifier.py)
    Distribution   Coordinator output (src/core/coordinator.py)
    Sandbox        ITU AI for Good Sandbox — not available in this environment;
                   recorded as not executed in the ingestion manifest

Safeguards against fabricated metadata
--------------------------------------
* A document is ingested only if its `title_evidence` string is found in the
  extracted text — this catches a wrong file saved under the right name.
* `date_issued` is kept only if `date_evidence` is found verbatim.
* Every passage carries effective=None and amendment_checked=False unless an
  obtained document establishes otherwise:
    - `in_force` sets effective=True only for the sections/rules a commencement
      notification (or the instrument's own commencement clause) names, and
      only if the quoted `evidence` is found verbatim in that document;
    - `amended_by` records an amendment note on the amended sections/rules,
      on the same condition.
  amendment_checked stays False everywhere: having one amendment does not
  show there is no other, so no passage claims a complete amendment check.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

from src.rag.embedding import DEFAULT_MODEL, get_embedder
from src.rag.extract import extract, pdf_outline, raw_docx_text
from src.rag.manifest import ALL_KBS, KB_ROOT, SourceDocument, load_manifest
from src.rag.sections import chunk_sections, remove_running_lines, split_by_outline, split_sections
from src.rag.vector_store import VectorStore

INGESTION_MANIFEST = KB_ROOT / "ingestion_manifest.json"


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _squash(text: str) -> str:
    return " ".join(text.split())


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


def process_document(doc: SourceDocument) -> tuple[list[dict], dict]:
    """Extract → clean → section → chunk → metadata.  Returns (chunks, report)."""
    report: dict = {"id": doc.id, "title": doc.title, "file": doc.file,
                    "source_url": doc.source_url, "kbs": doc.kbs}
    report["sha256"] = _sha256(doc.path)

    blocks = extract(doc)
    full_text = _squash(" ".join(b.text for b in blocks))
    if doc.file_format == "docx":
        full_text += " " + raw_docx_text(doc.path)       # cover page text boxes
    report["extracted_chars"] = len(full_text)
    report["_text"] = full_text                       # for status evidence; not written

    if not blocks:
        report["status"] = "not ingested: no extractable text (OCR not attempted)"
        return [], report
    if doc.title_evidence and _squash(doc.title_evidence) not in full_text:
        report["status"] = (f"REFUSED: title evidence {doc.title_evidence!r} not found in "
                            "the extracted text — the file may not be the expected document")
        return [], report

    date = doc.date_issued if doc.date_evidence and _squash(doc.date_evidence) in full_text else ""
    report["date_issued"] = date
    report["date_verified_in_text"] = bool(date)

    blocks = remove_running_lines(blocks)
    if doc.section_style == "pdf_outline":
        sections, unmatched = split_by_outline(blocks, pdf_outline(doc.path), doc.section_label)
        report["outline_bookmarks_not_located"] = len(unmatched)
    else:
        sections = split_sections(blocks, doc.section_style, doc.section_label)
    chunks = chunk_sections(sections)

    labels = [s.label for s in sections]
    report["sections"] = len(sections)
    report["sections_labelled_by_page_only"] = sum(l.startswith("p. ") for l in labels)

    counters: dict[str, int] = defaultdict(int)
    records = []
    for chunk in chunks:
        counters[chunk.section] += 1
        records.append({
            "chunk_id":          f"{doc.id}:{_slug(chunk.section)}:{counters[chunk.section]}",
            "doc_id":            doc.id,
            "source_title":      doc.title,
            "authority":         doc.authority,
            "jurisdiction":      doc.jurisdiction,
            "region":            doc.effective_region,
            "role":              doc.role,
            "document_type":     doc.document_type,
            "section":           chunk.section,
            "section_title":     chunk.section_title,
            "page":              chunk.page,
            "excerpt":           chunk.text,
            "date_issued":       date,
            "effective":         None,
            "effective_status":  "",                 # set only where an obtained document establishes it
            "amendment_note":    "",
            "amendment_checked": False,
            "amendment_status":  doc.amendment_status,
            "url":               doc.source_url,
            "related_documents": doc.related_documents,
            "institutions":      doc.institutions,
            "domains":           doc.domains,
            "provenance_note":   doc.provenance_note,
        })
    report["chunks"] = len(records)
    report["status"] = "ingested" if records else "not ingested: no chunks produced"
    return records, report


_UNIT = re.compile(r"^(?:Section|Rule|Regulation)\s+(\d+[A-Z]?)\b")


def apply_status(docs: list[SourceDocument], chunks: list[dict], reports: list[dict]) -> None:
    """
    Apply in-force status and amendment notes that obtained documents
    establish.  Refuses (raises) if the quoted evidence is not in the
    authorising document's extracted text, or that document was not ingested.
    """
    texts = {r["id"]: r.get("_text", "") for r in reports if r.get("status") == "ingested"}
    by_id = {r["id"]: r for r in reports}
    for doc in docs:
        if not (doc.in_force or doc.amended_by) or doc.id not in texts:
            continue
        own = [c for c in chunks if c["doc_id"] == doc.id]
        for kind, entries in (("in_force", doc.in_force), ("amended_by", doc.amended_by)):
            for entry in entries:
                source_text = texts.get(entry["by"])
                if source_text is None:
                    raise ValueError(f"{doc.id}.{kind}: {entry['by']} was not ingested")
                if _squash(entry["evidence"]) not in source_text:
                    raise ValueError(f"{doc.id}.{kind}: evidence not found in {entry['by']}: "
                                     f"{entry['evidence'][:80]!r}")
                units = set(entry["units"])
                applied = 0
                for c in own:
                    m = _UNIT.match(c["section"])
                    if "*" not in units and not (m and m.group(1) in units):
                        continue
                    if "*" in units and c["section"].startswith("p. "):
                        continue                      # front matter: not a provision
                    if kind == "in_force":
                        c["effective"] = True
                        c["effective_status"] = entry["status"]
                    else:
                        c["amendment_note"] = (c["amendment_note"] + "; " if c["amendment_note"] else "") + entry["note"]
                    applied += 1
                by_id[doc.id].setdefault(f"{kind}_applied", []).append(
                    {"by": entry["by"], "units": sorted(units), "passages": applied})
                print(f"     {doc.id}: {kind} from {entry['by']} applied to {applied} passages")


def build(model_id: str = DEFAULT_MODEL) -> dict:
    started = time.time()
    docs = load_manifest()
    all_chunks: list[dict] = []
    doc_reports: list[dict] = []

    for doc in docs:
        if not doc.ingestible:
            doc_reports.append({
                "id": doc.id, "title": doc.title, "kbs": doc.kbs,
                "status": f"not ingested: {doc.status}",
                "attempted_urls": doc.attempted_urls,
                "note": doc.provenance_note,
            })
            print(f"  -- {doc.id}: not ingested ({doc.status})")
            continue
        records, report = process_document(doc)
        doc_reports.append(report)
        all_chunks.extend(records)
        print(f"  {'OK' if records else '!!'} {doc.id}: {report['status']}, "
              f"{report.get('chunks', 0)} chunks")

    apply_status(docs, all_chunks, doc_reports)

    print(f"Embedding {len(all_chunks)} passages with {model_id} ...")
    embedder = get_embedder(model_id)
    vectors = embedder.embed_passages([c["excerpt"] for c in all_chunks]) if all_chunks else np.zeros((0, 384))
    by_doc_kbs = {d.id: d.kbs for d in docs}

    kb_reports = {}
    built_at = datetime.now(timezone.utc).isoformat()
    for kb in ALL_KBS:
        rows = [i for i, c in enumerate(all_chunks) if kb in by_doc_kbs[c["doc_id"]]]
        documents = sorted({all_chunks[i]["doc_id"] for i in rows})
        info = {
            "kb": kb,
            "embedding_model": model_id,
            "dimension": int(vectors.shape[1]) if len(vectors) else 0,
            "similarity": "cosine (L2-normalised dot product)",
            "chunk_count": len(rows),
            "documents": documents,
            "built_at": built_at,
        }
        VectorStore.write(KB_ROOT / kb, [all_chunks[i] for i in rows], vectors[rows], info)
        kb_reports[kb] = {"chunks": len(rows), "documents": documents}
        print(f"  KB {kb:<24} {len(rows):>5} chunks from {len(documents)} document(s)")

    manifest = {
        "_about": "Generated by `python -m src.rag.build`. Records what was actually ingested.",
        "built_at": built_at,
        "build_seconds": round(time.time() - started, 1),
        "embedding_model": model_id,
        "generator_model": "none — agents quote retrieved passages; no generative model is used",
        "vector_store": "local numpy store, one directory per KB (knowledge_base/<kb>/)",
        "chunking": {"max_chars": 1200, "overlap_chars": 150, "unit": "within one detected section"},
        "sandbox": "not executed — the ITU AI for Good Sandbox is not available in this environment",
        "knowledge_bases": kb_reports,
        "documents": [{k: v for k, v in r.items() if k != "_text"} for r in doc_reports],
    }
    INGESTION_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {INGESTION_MANIFEST.relative_to(KB_ROOT.parent)} in {manifest['build_seconds']} s")
    return manifest


if __name__ == "__main__":
    sys.exit(0 if build() else 1)
