"""
Embedding models.

Default: BAAI/bge-small-en-v1.5 via fastembed (ONNX, CPU, 384 dimensions).
The model id is recorded in every index so retrieval always uses the model
the index was built with (DOCX §7.4: record the embedding model).
"""

from __future__ import annotations

import os
from typing import Protocol

import numpy as np

from src.rag.manifest import KB_ROOT

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
MODEL_CACHE   = KB_ROOT / ".model_cache"


class Embedder(Protocol):
    model_id: str

    def embed_passages(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


class FastEmbedEmbedder:
    """L2-normalised embeddings, so a dot product is cosine similarity."""

    def __init__(self, model_id: str = DEFAULT_MODEL) -> None:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed import TextEmbedding

        self.model_id = model_id
        self._model = TextEmbedding(model_id, cache_dir=str(MODEL_CACHE))

    @staticmethod
    def _normalise(vectors) -> np.ndarray:
        arr = np.asarray(list(vectors), dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        return arr / np.clip(norms, 1e-12, None)

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        return self._normalise(self._model.passage_embed(texts, batch_size=64))

    def embed_query(self, text: str) -> np.ndarray:
        return self._normalise(self._model.query_embed([text]))[0]


_CACHE: dict[str, FastEmbedEmbedder] = {}


def get_embedder(model_id: str = DEFAULT_MODEL) -> FastEmbedEmbedder:
    """One loaded model per process (loading takes a few seconds)."""
    if model_id not in _CACHE:
        _CACHE[model_id] = FastEmbedEmbedder(model_id)
    return _CACHE[model_id]
