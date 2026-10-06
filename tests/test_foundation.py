"""
Knowledge-foundation artefacts are backed by the data (Day-2 Member 2).

Re-checks the committed artefacts written by `python -m src.rag.foundation`:
every quotation is found in a stored passage, every cited file exists,
DOCX tables are reproduced verbatim, nothing is scored.  Store-dependent
checks are skipped when the knowledge bases are not built.

Run with:
    python -m pytest tests/test_foundation.py -v
"""

import json
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.rag.manifest import ALL_KBS, KB_ROOT
from src.rag.vector_store import VectorStore

ROOT = KB_ROOT.parent
SOURCE_MANIFEST = KB_ROOT / "source_manifest.json"
READINESS = KB_ROOT / "itu_ai_readiness_mapping.json"
Y3172 = KB_ROOT / "y3172_pipeline_traceability.json"
HOST = KB_ROOT / "host_country_corpus.json"
GAPS = KB_ROOT / "policy_gap" / "policy_gap_categories.json"
CANONICAL = KB_ROOT / "canonical" / "canonical_metadata.json"

built = pytest.mark.skipif(not all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS),
                           reason="knowledge bases not built")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def stored():
    rows = {}
    for kb in ALL_KBS:
        for line in (KB_ROOT / kb / "chunks.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            rows[r["chunk_id"]] = r
    return rows


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _flat(text: str) -> str:
    return " ".join(text.split())


# -----------------------------------------------------------------------
# Every quotation and every cited file is real
# -----------------------------------------------------------------------

@built
@pytest.mark.parametrize("path", [READINESS, HOST, Y3172], ids=lambda p: p.name)
def test_every_quote_is_in_the_stored_passage(path, stored) -> None:
    for node in _walk(load(path)):
        if "chunk_id" in node and ("quote" in node or "phrase_quoted" in node):
            passage = stored[node["chunk_id"]]
            text = _flat(passage["excerpt"])
            quoted = node.get("phrase_quoted") or node["quote"].strip("…")
            assert quoted in text, f"{path.name}: quote not in {node['chunk_id']}"
            if "section" in node:
                assert node["section"] == passage["section"]


@pytest.mark.parametrize("path", [READINESS, Y3172, GAPS], ids=lambda p: p.name)
def test_every_cited_project_file_exists(path) -> None:
    for node in _walk(load(path)):
        for f in node.get("files", []) + ([node["agent_module"]] if "agent_module" in node else []):
            assert (ROOT / f).exists(), f"{path.name} cites missing file {f}"


# -----------------------------------------------------------------------
# DOCX tables reproduced verbatim
# -----------------------------------------------------------------------

DOCX_PERSPECTIVES = [
    "Open data and open-source management",
    "Generative AI content ecosystem",
    "Contextualization of AI solutions and regional development",
    "AI integration in domains and cross-domain analysis",
    "Human interaction and supervision",
    "AI policy and implementation opportunity identification",
    "AI for social inclusion",
    "Digital infrastructure and energy",
]

DOCX_HOST_CATEGORIES = [
    "Laws and regulations", "National AI strategy and AI mission",
    "Digital and cybersecurity strategies", "Institutional mandates",
    "Economic and industrial characteristics", "Labour-market conditions",
    "Intellectual property", "Multilateral and treaty obligations",
    "Energy and infrastructure constraints", "Regional and global comparators",
]


def test_readiness_uses_the_docx_eight_perspectives() -> None:
    data = load(READINESS)
    assert [d["dimension_name"] for d in data["dimensions"]] == DOCX_PERSPECTIVES
    for d in data["dimensions"]:
        assert d["docx_project_mapping"] and d["docx_evidence_status"]
        assert d["evidence_items"], f"{d['dimension_name']}: no evidence"


def test_readiness_assigns_no_score() -> None:
    text = json.dumps(load(READINESS)).lower()
    assert not re.search(r'"(score|rating|maturity_level|level)"\s*:', text)
    assert not re.search(r"\b\d{1,3}\s?%", text)
    assert "not a formal" in load(READINESS)["methodology_disclaimer"].lower()


def test_host_corpus_follows_docx_table() -> None:
    cats = load(HOST)["categories"]
    assert [c["docx_heading"] for c in cats] == DOCX_HOST_CATEGORIES
    for c in cats:
        assert c["docx_material_covered"] and c["docx_kb_assignment"]
        if c["coverage_status"].startswith("NOT COVERED"):
            assert c["sources_ingested"] == []


def test_policy_gap_meanings_are_docx_and_examples_are_real() -> None:
    data = load(GAPS)
    assert len(data["categories"]) == 6
    assert {c["docx_meaning"] for c in data["categories"]} >= {
        "Several provisions apply and their relationship is unclear.",
        "The technology or scenario is not named in the framework."}
    run = [json.loads(l) for l in (ROOT / data["recorded_run"]).open(encoding="utf-8")]
    claims = {cl["claim"] for e in run if e["type"] == "stage"
              for a in e["agents"] if a["agent_id"] == "policy_gap" for cl in a["claims"]}
    for c in data["categories"]:
        for ex in c["observed_in_recorded_run"]:
            assert ex["claim"] in claims
    assert data["distinction_potential_gap_vs_law_does_not_exist"]["example_correct"] in claims


# -----------------------------------------------------------------------
# Source manifest and canonical metadata agree with the build
# -----------------------------------------------------------------------

def test_source_manifest_matches_ingestion() -> None:
    manifest = load(SOURCE_MANIFEST)
    ingestion = {d["id"]: d for d in load(KB_ROOT / "ingestion_manifest.json")["documents"]}
    curated = {d["id"] for d in load(KB_ROOT / "sources" / "manifest.json")["documents"]}
    assert {d["id"] for d in manifest["documents"]} == curated
    for d in manifest["documents"]:
        rep = ingestion[d["id"]]
        if rep["status"] == "ingested":
            assert d["sha256"] == rep["sha256"] and d["chunk_count"] == rep["chunks"]
            assert d["embedding_model"] == manifest["embedding_model"]
            assert d["vector_index"], d["id"]
            assert d["effective_status"].startswith("not")
        else:
            assert d["sha256"] is None and d["chunk_count"] == 0


@built
def test_licence_statements_are_quoted_from_the_document(stored) -> None:
    by_doc = {}
    for r in stored.values():
        by_doc.setdefault(r["doc_id"], []).append(_flat(r["excerpt"]))
    for d in load(SOURCE_MANIFEST)["documents"]:
        statement = d["licence"]["statement_in_document"]
        if statement:
            assert any(statement in t for t in by_doc[d["id"]]), d["id"]


@built
def test_canonical_kb_holds_every_agent_document() -> None:
    meta = load(CANONICAL)
    assert meta["notes"]["agent_kbs_beneath_canonical"] is True
    ingested = [d for d in meta["documents"] if d["sha256"]]
    assert ingested and all(d["in_canonical_kb"] and d["canonical_passages"] for d in ingested)


# -----------------------------------------------------------------------
# Retrieval quality
# -----------------------------------------------------------------------

@built
def test_retrieval_quality_on_labelled_queries() -> None:
    from src.rag.retrieval_quality import PROBES, evaluate
    report = evaluate()
    s = report["summary"]
    assert set(s["agents"]) == {p.agent.value for p in PROBES} and len(s["agents"]) == 7
    assert s["isolated_to_agent_kb"] == s["queries"], "an agent received another KB's passage"
    assert s["metadata_complete"] == s["queries"], "a result lacks required metadata"
    assert s["expected_source_in_results"] == s["queries"]
    assert s["hit_at_5"] >= s["queries"] - 1, s["misses"]
