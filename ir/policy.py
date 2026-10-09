"""
Policy panel: the Indian obligations that apply to an attack, with citations.
=============================================================================
For each obligation tagged in the catalog, the exact phrase it relies on is
looked up in the cited document in the prebuilt index (kb.retriever.find_passage,
an exhaustive check).  Found → shown with file and page and the passage.
Not found → shown as NOT FOUND, never presented as fact.  Related passages
from the attack's policy categories are added by similarity search.

Decision support for a training lab, not legal advice.
"""

from __future__ import annotations

from typing import Callable


def _quote(text: str, phrase: str, width: int = 220) -> str:
    flat = " ".join(text.split())
    i = flat.lower().find(" ".join(phrase.lower().split()))
    if i < 0:
        return flat[:2 * width]
    s, e = max(0, i - width), min(len(flat), i + len(phrase) + width)
    return ("…" if s else "") + flat[s:e] + ("…" if e < len(flat) else "")


def build_policy_panel(attack: dict, search: Callable | None = None) -> dict:
    try:
        from kb.retriever import cite, find_passage
        from kb.retriever import search as kb_search
    except ImportError as exc:                     # pragma: no cover
        return {"error": f"retriever unavailable: {exc}", "obligations": [], "related": []}
    search = search or kb_search
    tags = attack["policy_tags"]
    obligations, error = [], ""
    for ob in tags.get("obligations", []):
        try:
            hit = find_passage(ob["doc"], ob["phrase"])
            missing = f"{ob['doc']} — phrase NOT FOUND in the index; do not rely on it"
        except FileNotFoundError as exc:          # index not built / not mounted
            hit, error = None, f"index not available ({exc}); obligations shown UNVERIFIED"
            missing = f"{ob['doc']} — UNVERIFIED (index not loaded)"
        obligations.append({
            "id": ob["id"], "summary": ob["summary"], "applies_when": ob.get("applies_when", ""),
            "doc": ob["doc"], "found": hit is not None,
            "citation": cite(hit) if hit else missing,
            "passage": _quote(hit["text"], ob["phrase"]) if hit else "",
        })
    try:
        related = [{"citation": cite(h), "category": h["category"], "score": h["score"],
                    "text": " ".join(h["text"].split())[:500]}
                   for h in search(tags.get("query", attack["name"]), categories=tags["categories"], k=5)]
    except FileNotFoundError as exc:
        error, related = error or f"index not available ({exc})", []
    except Exception as exc:                       # noqa: BLE001 — e.g. embedding model not downloadable offline
        error, related = error or (f"similarity search unavailable ({type(exc).__name__}: {exc}); the "
                                   "obligations above were still checked word for word"), []
    if error:
        return {"error": error, "categories": tags["categories"], "obligations": obligations, "related": []}
    return {"categories": tags["categories"], "obligations": obligations, "related": related,
            "note": "Citations come from the prebuilt index. Decision support only — not legal advice."}
