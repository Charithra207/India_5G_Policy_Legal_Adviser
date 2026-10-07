"""
Category-filtered retrieval over the prebuilt index (kb/index/).
================================================================
    from kb.retriever import search
    hits = search("report a cyber security incident within six hours",
                  categories=["cyber_incident_rules"], k=5)

    python -m kb.retriever "signalling storm on the AMF" --categories gpp_security,threat_frameworks -k 5

Only the FAISS indexes of the requested categories are searched (one index
per category), so each attack searches its own subset of the corpus.  The
index is loaded, never rebuilt; `verify()` checks the files against the
hashes in kb/index/manifest.json.  Set KB_INDEX_DIR to load it from another
folder (e.g. a read-only mount in Windows Sandbox).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def index_dir() -> Path:
    return Path(os.environ.get("KB_INDEX_DIR", ROOT / "kb" / "index"))


@lru_cache(maxsize=1)
def manifest() -> dict:
    path = index_dir() / "manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"{path} missing — the index has not been built "
                                "(python -m kb.build_index, once) or not mounted")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _chunks() -> dict[str, list[dict]]:
    by_category: dict[str, list[dict]] = {}
    with gzip.open(index_dir() / "chunks.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            c = json.loads(line)
            by_category.setdefault(c["category"], []).append(c)
    return by_category


@lru_cache(maxsize=None)
def _index(category: str):
    import faiss
    return faiss.read_index(str(index_dir() / f"{category}.faiss"))


@lru_cache(maxsize=1)
def _embedder():
    import src.rag.embedding as embedding
    if os.environ.get("KB_MODEL_CACHE"):          # e.g. a writable copy inside Windows Sandbox
        embedding.MODEL_CACHE = Path(os.environ["KB_MODEL_CACHE"])
    return embedding.get_embedder(manifest()["embedding_model"])


def categories() -> list[str]:
    return list(manifest()["categories"])


def verify() -> list[str]:
    """Index files whose SHA-256 differs from the manifest (empty = intact)."""
    problems = []
    for name, expected in manifest()["files"].items():
        path = index_dir() / name
        if not path.exists():
            problems.append(f"{name}: missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append(f"{name}: hash differs from manifest")
    return problems


def search(query: str, categories: list[str] | None = None, k: int = 5,
           min_score: float = 0.0) -> list[dict]:
    """
    Top-k chunks for `query`, searching only `categories` (all if None).
    Each hit: score, category, doc, page_start, page_end, text.
    """
    wanted = categories or list(manifest()["categories"])
    unknown = [c for c in wanted if c not in manifest()["categories"]]
    if unknown:
        raise ValueError(f"unknown categories: {unknown}")
    vector = _embedder().embed_query(query).reshape(1, -1)
    hits = []
    for category in wanted:
        index = _index(category)
        if index.ntotal == 0:
            continue
        scores, rows = index.search(vector, min(k, index.ntotal))
        chunks = _chunks().get(category, [])
        for score, row in zip(scores[0], rows[0]):
            if row >= 0 and score >= min_score:
                c = chunks[row]
                hits.append({"score": round(float(score), 4), "category": category, "doc": c["doc"],
                             "page_start": c["page_start"], "page_end": c["page_end"],
                             "text": c["text"]})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]


def find_passage(doc: str, phrase: str) -> dict | None:
    """
    The first chunk of `doc` whose text contains `phrase` (case and spacing
    ignored) — an exhaustive check, not a similarity search, used to confirm
    that a cited obligation really is in the cited document.
    """
    want = " ".join(phrase.lower().split())
    for chunks in _chunks().values():
        for c in chunks:
            if c["doc"] == doc and want in " ".join(c["text"].lower().split()):
                return {"score": None, "category": c["category"], "doc": c["doc"],
                        "page_start": c["page_start"], "page_end": c["page_end"], "text": c["text"]}
    return None


def cite(hit: dict) -> str:
    pages = (f"p. {hit['page_start']}" if hit["page_start"] == hit["page_end"]
             else f"pp. {hit['page_start']}–{hit['page_end']}")
    return f"{hit['doc']}, {pages}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Search the prebuilt incident-response KB index.")
    ap.add_argument("query")
    ap.add_argument("--categories", default="", help="comma-separated; default all")
    ap.add_argument("-k", type=int, default=5)
    args = ap.parse_args(argv)
    cats = [c for c in args.categories.split(",") if c] or None
    for h in search(args.query, cats, args.k):
        print(f"{h['score']:.3f}  [{h['category']}]  {cite(h)}")
        print(f"       {h['text'][:220]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
