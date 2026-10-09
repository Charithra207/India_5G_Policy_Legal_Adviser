"""
Policy-gap register: domain gaps × Indian provisions × global and regional examples
=================================================================================
    python -m src.gap.register            # -> knowledge_base/gap_register.json and .md

Reads knowledge_base/policy_gap/gap_themes.yaml and checks every quoted
phrase word for word in its document — first in the adviser's knowledge
bases (knowledge_base/<kb>/chunks.jsonl), then in the committed incident-
response index (kb/index).  Each anchor is reported as

    verified                         file, section/page and the passage
    phrase not found                 the document is present, the words are not
    pending: document not in corpus  add it (knowledge_base/ADDING_SOURCES.md)
    listed for comparison            an example named without a quotation

A theme is "evidence-backed" when all its Indian anchors and at least one
global example are verified; otherwise "partly evidenced".  Every theme is
a POTENTIAL gap for expert review (DOCX §5.1): no conclusion of policy
failure is drawn.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.core.models import CoverageCategory
from src.rag.manifest import ALL_KBS, KB_ROOT
from src.rag.regions import region_of

ROOT = KB_ROOT.parent
THEMES = KB_ROOT / "policy_gap" / "gap_themes.yaml"
OUT_JSON = KB_ROOT / "gap_register.json"
OUT_MD = KB_ROOT / "gap_register.md"
DISCLAIMER = ("Potential gaps and regulatory ambiguities identified for expert review. No conclusion "
              "of policy failure is drawn; international material is a reference point, not Indian law.")

VERIFIED, NOT_FOUND, PENDING, LISTED = ("verified", "phrase not found", "pending: document not in corpus",
                                        "listed for comparison")


class RegisterError(ValueError):
    pass


def _flat(text: str) -> str:
    return " ".join(text.split())


@dataclass
class Corpus:
    """Stored passages of both corpora, by document."""
    kb_docs: dict[str, list[dict]] = field(default_factory=dict)      # doc_id -> chunks
    index_docs: dict[str, list[dict]] = field(default_factory=dict)   # file name -> chunks

    @classmethod
    def load(cls, kb_root: Path = KB_ROOT, index_dir: Path | None = None) -> "Corpus":
        c, seen = cls(), set()
        for kb in ALL_KBS:
            path = kb_root / kb / "chunks.jsonl"
            if path.exists():
                for line in path.open(encoding="utf-8"):
                    row = json.loads(line)
                    if row["chunk_id"] not in seen:
                        seen.add(row["chunk_id"])
                        c.kb_docs.setdefault(row["doc_id"], []).append(row)
        if index_dir is None:
            from kb.retriever import index_dir as default_index
            index_dir = default_index()
        path = Path(index_dir) / "chunks.jsonl.gz"
        if path.exists():
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                for line in fh:
                    row = json.loads(line)
                    c.index_docs.setdefault(row["doc"], []).append(row)
        return c

    def candidates(self, anchor: dict) -> list[tuple[str, str, list[dict]]]:
        """(corpus, document, chunks) the anchor may be in, adviser KBs first."""
        out = []
        if anchor.get("source") in self.kb_docs:
            out.append(("knowledge_base", anchor["source"], self.kb_docs[anchor["source"]]))
        for needle in anchor.get("title_contains") or []:
            for doc_id, rows in self.kb_docs.items():
                if needle.lower() in rows[0].get("source_title", "").lower() and \
                        not any(d == doc_id for _, d, _ in out):
                    out.append(("knowledge_base", doc_id, rows))
        if anchor.get("index_doc") in self.index_docs:
            out.append(("kb_index", anchor["index_doc"], self.index_docs[anchor["index_doc"]]))
        return out


def _quote(text: str, phrase: str, width: int = 220) -> str:
    flat = _flat(text)
    i = flat.lower().find(_flat(phrase).lower())
    s, e = max(0, i - width), min(len(flat), i + len(phrase) + width)
    return ("…" if s else "") + flat[s:e] + ("…" if e < len(flat) else "")


def check_anchor(anchor: dict, corpus: Corpus, international: bool) -> dict:
    jurisdiction = anchor.get("jurisdiction") or ("India" if not international else "International")
    out = {"cite_as": anchor["cite_as"], "what": anchor.get("what", ""), "jurisdiction": jurisdiction,
           "region": region_of(jurisdiction), "url": anchor.get("url", ""), "phrase": anchor.get("phrase")}
    if anchor.get("phrase") is None:
        return {**out, "status": LISTED}
    want = _flat(anchor["phrase"]).lower()
    candidates = corpus.candidates(anchor)
    for kind, doc, rows in candidates:
        for row in rows:
            text = row.get("excerpt") if kind == "knowledge_base" else row.get("text")
            if want in _flat(text or "").lower():
                where = ({"section": row.get("section"), "page": row.get("page"), "source_title": row.get("source_title"),
                          "chunk_id": row.get("chunk_id")} if kind == "knowledge_base" else
                         {"page": (f"{row['page_start']}" if row["page_start"] == row["page_end"]
                                   else f"{row['page_start']}-{row['page_end']}")})
                return {**out, "status": VERIFIED, "corpus": kind, "document": doc, **where,
                        "passage": _quote(text, anchor["phrase"])}
    if candidates:
        return {**out, "status": NOT_FOUND, "documents_checked": [d for _, d, _ in candidates]}
    return {**out, "status": PENDING}


def _validate(data: dict) -> list[dict]:
    categories = {c.value for c in CoverageCategory}
    themes = data.get("themes") if isinstance(data, dict) else None
    if not themes:
        raise RegisterError("gap_themes.yaml: no themes")
    ids = set()
    for t in themes:
        for key in ("id", "domain", "theme", "category", "why_it_matters", "coordination_problem",
                    "indian_anchors", "global_examples"):
            if key not in t:
                raise RegisterError(f"theme {t.get('id')!r}: missing {key!r}")
        if t["id"] in ids:
            raise RegisterError(f"duplicate theme id {t['id']!r}")
        ids.add(t["id"])
        if t["category"] not in categories:
            raise RegisterError(f"theme {t['id']}: unknown category {t['category']!r}")
        for a in t["indian_anchors"] + t["global_examples"] + (t.get("regional_examples") or []):
            if "cite_as" not in a or "phrase" not in a:
                raise RegisterError(f"theme {t['id']}: every anchor needs cite_as and phrase")
            if a["phrase"] is not None and not (a.get("source") or a.get("index_doc") or a.get("title_contains")):
                raise RegisterError(f"theme {t['id']}: anchor {a['cite_as']!r} names no document")
    return themes


def build(themes_path: Path = THEMES, corpus: Corpus | None = None) -> dict:
    themes = _validate(yaml.safe_load(Path(themes_path).read_text(encoding="utf-8")))
    corpus = corpus or Corpus.load()
    out = []
    for t in themes:
        indian = [check_anchor(a, corpus, False) for a in t["indian_anchors"]]
        global_ = [check_anchor(a, corpus, True) for a in t["global_examples"]]
        regional = [check_anchor(a, corpus, True) for a in t.get("regional_examples") or []]
        backed = all(a["status"] == VERIFIED for a in indian) and any(a["status"] == VERIFIED for a in global_)
        out.append({
            "id": t["id"], "domain": t["domain"], "theme": t["theme"], "category": t["category"],
            "status": "evidence-backed potential gap" if backed else "partly evidenced potential gap",
            "why_it_matters": " ".join(t["why_it_matters"].split()),
            "coordination_problem": " ".join(t["coordination_problem"].split()),
            "conflicting_objectives": t.get("conflicting_objectives", ""),
            "indian_provisions": indian, "global_examples": global_, "regional_examples": regional,
            "y3172_link": " ".join(t.get("y3172_link", "").split()),
            "questions_for_experts": t.get("questions_for_experts", []),
        })
    all_anchors = [a for t in out for k in ("indian_provisions", "global_examples", "regional_examples") for a in t[k]]
    counts = {s: sum(a["status"] == s for a in all_anchors) for s in (VERIFIED, NOT_FOUND, PENDING, LISTED)}
    return {
        "_about": ["Domain-specific potential policy gaps for 5G incidents, each with Indian provisions and",
                   "global / neighbouring-region examples checked word for word in their sources.",
                   f"Generated by python -m src.gap.register from {THEMES.relative_to(ROOT).as_posix()}."],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "disclaimer": DISCLAIMER,
        "corpora": {"knowledge_base_documents": len(corpus.kb_docs), "kb_index_documents": len(corpus.index_docs)},
        "anchor_status_counts": counts,
        "themes": out,
    }


def _md_anchor(a: dict) -> str:
    where = ""
    if a["status"] == VERIFIED:
        loc = ", ".join(x for x in (a.get("section") or "", f"p. {a['page']}" if a.get("page") else "") if x)
        where = f" — {a['document']}{', ' + loc if loc else ''}"
    quote = f"<br>“{a['passage']}”" if a.get("passage") else ""
    flag = {VERIFIED: "✔", NOT_FOUND: "✘", PENDING: "…", LISTED: "·"}[a["status"]]
    return (f"| {flag} {a['cite_as']} | {a['jurisdiction']} | {a['what']} | "
            f"{a['status']}{where}{quote} |")


def render_markdown(reg: dict) -> str:
    c = reg["anchor_status_counts"]
    L = ["# Policy-gap register — 5G incidents (India and comparators)", "",
         f"> {reg['disclaimer']}", "",
         f"Generated {reg['generated_at']} by `python -m src.gap.register` from "
         "`knowledge_base/policy_gap/gap_themes.yaml`. Anchors: "
         + ", ".join(f"{v} {k}" for k, v in c.items()) + ". "
         "Pending anchors become verified when their document is added "
         "(`knowledge_base/ADDING_SOURCES.md`) and the knowledge bases are rebuilt.", "",
         "| id | domain | potential gap | category | status |", "|---|---|---|---|---|"]
    L += [f"| {t['id']} | {t['domain']} | {t['theme']} | {t['category'].replace('_', ' ')} | {t['status']} |"
          for t in reg["themes"]]
    for t in reg["themes"]:
        L += ["", f"## {t['id']} — {t['theme']}", "", f"**Domain:** {t['domain']} · **Category:** "
              f"{t['category'].replace('_', ' ')} · **Status:** {t['status']}", "",
              f"**Why it matters.** {t['why_it_matters']}", "",
              f"**Coordination problem.** {t['coordination_problem']}", ""]
        if t["conflicting_objectives"]:
            L += [f"**Objectives in tension.** {t['conflicting_objectives']}", ""]
        for title, key in (("Indian provisions", "indian_provisions"), ("Global examples", "global_examples"),
                           ("Neighbouring-region examples", "regional_examples")):
            if t[key]:
                L += [f"**{title}**", "", "| instrument | jurisdiction | what it does | check |", "|---|---|---|---|"]
                L += [_md_anchor(a) for a in t[key]] + [""]
        if t["y3172_link"]:
            L += [f"**Link to the Y.3172 pipeline.** {t['y3172_link']}", ""]
        if t["questions_for_experts"]:
            L += ["**Questions for expert review**", ""] + [f"- {q}" for q in t["questions_for_experts"]]
    L += ["", "_Decision support; not legal advice._"]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--themes", type=Path, default=THEMES)
    ap.add_argument("--out", type=Path, default=OUT_JSON, help="JSON output; the .md goes beside it")
    args = ap.parse_args(argv)
    try:
        reg = build(args.themes)
    except RegisterError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")
    args.out.with_suffix(".md").write_text(render_markdown(reg), encoding="utf-8")
    print(f"wrote {args.out} and {args.out.with_suffix('.md')}")
    for t in reg["themes"]:
        print(f"  {t['id']} {t['status']:<34} {t['theme']}")
    print("  anchors:", reg["anchor_status_counts"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
