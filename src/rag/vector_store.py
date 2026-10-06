"""
Vector store: one directory per knowledge base.

    knowledge_base/<kb>/
        chunks.jsonl     one passage per line: text + full provenance metadata
        vectors.npy      float32 [n_chunks, dim], L2-normalised, same order
        index.json       embedding model, dimension, documents, chunk count

Each agent KB is a separate directory, so an agent's retrieval is restricted
to its own corpus by construction (DOCX §3.4); the Canonical KB is its own
directory, used only by the Verifier and the Policy Gap Agent (§7.1, §7.2).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

import numpy as np

from src.knowledge_base.text_match import normalise_section


# Sections that describe the document rather than say anything about the
# incident (front matter, reference lists, abbreviation lists).  They stay
# in the store — the Verifier can look them up by exact section — but are
# not returned by open searches, where they would crowd out substance.
_BOILERPLATE = re.compile(
    r"^(front matter|foreword|table of contents|contents|intellectual property rights|"
    r"modal verbs terminology|history|keywords|references|normative references|"
    r"informative references|abbreviations( and acronyms)?|symbols|"
    r"list of symbols, abbreviations, and acronyms|change log|"
    r"(terms|definitions)?,? ?symbols and abbreviations)$",
    re.IGNORECASE,
)


# A passage this short is a heading fragment or a cross-reference pointer
# ("… is described in clause 5.8.2.19"); its embedding is close to
# meaningless, so it can score above the retrieval floor for unrelated
# queries.  Kept for exact section lookups, excluded from open searches.
MIN_SUBSTANTIVE_CHARS = 80


def is_boilerplate(chunk: dict) -> bool:
    title = (chunk.get("section_title") or "").strip().rstrip(".:")
    label = (chunk.get("section") or "").strip()
    if len(" ".join((chunk.get("excerpt") or "").split())) < MIN_SUBSTANTIVE_CHARS:
        return True
    return bool(_BOILERPLATE.match(title) or _BOILERPLATE.match(label))


class VectorStore:
    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.info = json.loads((self.directory / "index.json").read_text(encoding="utf-8"))
        with open(self.directory / "chunks.jsonl", encoding="utf-8") as fh:
            self.chunks = [json.loads(line) for line in fh]
        self.vectors = np.load(self.directory / "vectors.npy")
        if len(self.chunks) != len(self.vectors):
            raise ValueError(f"{directory}: {len(self.chunks)} chunks but {len(self.vectors)} vectors")
        self.substantive = np.array([not is_boilerplate(c) for c in self.chunks], dtype=bool)

    @staticmethod
    def exists(directory: Path) -> bool:
        return all((Path(directory) / f).exists() for f in ("index.json", "chunks.jsonl", "vectors.npy"))

    @staticmethod
    def write(directory: Path, chunks: list[dict], vectors: np.ndarray, info: dict) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / "chunks.jsonl", "w", encoding="utf-8") as fh:
            for chunk in chunks:
                fh.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        np.save(directory / "vectors.npy", vectors.astype(np.float32))
        (directory / "index.json").write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    def _mask(self, filters: Optional[dict]) -> np.ndarray:
        mask = np.ones(len(self.chunks), dtype=bool)
        for key, wanted in (filters or {}).items():
            if key == "section":
                want = normalise_section(str(wanted))
                values = [normalise_section(c.get("section", "")) == want for c in self.chunks]
            elif isinstance(wanted, str):
                want = wanted.strip().lower()
                values = [str(c.get(key, "")).strip().lower() == want for c in self.chunks]
            else:
                values = [c.get(key) == wanted for c in self.chunks]
            mask &= np.array(values, dtype=bool)
        return mask

    def search(self, query_vector: np.ndarray, top_k: int = 5,
               filters: Optional[dict] = None) -> list[tuple[dict, float]]:
        """
        Top-k (chunk, cosine similarity) among chunks matching `filters`.
        Open searches (no filters) skip boilerplate sections.
        """
        mask = self._mask(filters)
        if not filters:
            mask &= self.substantive
        if not mask.any():
            return []
        idx = np.flatnonzero(mask)
        scores = self.vectors[idx] @ query_vector
        order = np.argsort(-scores)[:top_k]
        return [(self.chunks[idx[i]], float(scores[i])) for i in order]
