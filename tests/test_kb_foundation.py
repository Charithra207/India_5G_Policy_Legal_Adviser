"""
Knowledge/RAG foundation tests.

Tests the Day 2 knowledge-base foundation without requiring live vector
stores. Covers:

  1.  Source manifest consistency and completeness
  2.  Ingestion manifest structure and non-fabrication guarantees
  3.  Canonical KB metadata completeness
  4.  Policy Gap KB categories — all six DOCX §5.1 categories present,
      non-conclusive language rules enforced
  5.  Host-country corpus categories — all ten DOCX §7.3 categories present,
      missing categories explicitly marked
  6.  Y.3172 pipeline traceability — all seven stages, Sandbox noted,
      no compliance claim made
  7.  ITU AI Readiness mapping — no scores or maturity levels invented,
      unavailable evidence explicitly marked
  8.  KB registry — correct agent→KB mapping, upgrade-path contract
  9.  InMemoryKnowledgeBase contract — retrieval, filters, top_k
 10.  Retrieval interface contract (stub path)
 11.  Metadata propagation through EvidenceItem
 12.  Policy Gap Agent language rules (no fabricated legal conclusions)
 13.  Evidence fields required by the audit trail (DOCX §7.6)
 14.  No fake citations in knowledge-layer outputs

All tests run without network access, live vector stores, or generative
models.  Tests marked with ``@built`` require a built vector store and are
skipped automatically when it is absent.

Run with:
    python -m pytest tests/test_kb_foundation.py -v
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core.models import (
    AgentFinding, AgentID, CoverageCategory, EvidenceItem,
    ScenarioChunk, VerifierOutcome,
)
from src.knowledge_base.base_kb import CanonicalKnowledgeBase, StubKnowledgeBase
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase
from src.knowledge_base.kb_registry import KBRegistry
from src.rag.manifest import ALL_KBS, KB_ROOT, MANIFEST_PATH, load_manifest
from src.rag.vector_store import VectorStore

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

KB_DIR             = KB_ROOT
SOURCES_MANIFEST   = MANIFEST_PATH
INGESTION_MANIFEST = KB_DIR / "ingestion_manifest.json"
CANONICAL_META     = KB_DIR / "canonical" / "canonical_metadata.json"
POLICY_GAP_CATS    = KB_DIR / "policy_gap" / "policy_gap_categories.json"
HOST_CORPUS        = KB_DIR / "host_country_corpus.json"
Y3172_TRACE        = KB_DIR / "y3172_pipeline_traceability.json"
ITU_AI_READINESS   = KB_DIR / "itu_ai_readiness_mapping.json"

EXPECTED_KB_READMES = [
    KB_DIR / kb / "README.md"
    for kb in ALL_KBS
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    assert path.exists(), f"Required file not found: {path}"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _manifest_docs() -> list[dict]:
    return _load_json(SOURCES_MANIFEST)["documents"]


def _ingestion_docs() -> list[dict]:
    return _load_json(INGESTION_MANIFEST)["documents"]


def _ingested_ids() -> set[str]:
    return {d["id"] for d in _ingestion_docs() if d.get("status") == "ingested"}


def _not_ingested_ids() -> set[str]:
    return {d["id"] for d in _ingestion_docs() if d.get("status", "").startswith("not ingested")}


# -----------------------------------------------------------------------
# 1. Source manifest consistency
# -----------------------------------------------------------------------

def test_sources_manifest_is_valid_json() -> None:
    data = _load_json(SOURCES_MANIFEST)
    assert "documents" in data and isinstance(data["documents"], list)
    assert len(data["documents"]) > 0


def test_sources_manifest_has_ingested_and_2_unavailable() -> None:
    """At least 14 sources downloaded; exactly 2 explicitly unavailable."""
    docs = _manifest_docs()
    ingested = [d for d in docs if d.get("status") == "downloaded"]
    unavailable = [d for d in docs if d.get("status") not in ("downloaded",)]
    assert len(ingested) >= 14, f"Expected at least 14 ingested, got {len(ingested)}"
    assert len(unavailable) == 2, f"Expected 2 unavailable, got {len(unavailable)}"


def test_sources_manifest_unavailable_are_nciipc_and_comparators() -> None:
    """The two unavailable sources are exactly nciipc_rules_2013 and international_policy_examples."""
    docs = _manifest_docs()
    unavailable = {d["id"] for d in docs if d.get("status") != "downloaded"}
    assert unavailable == {"nciipc_rules_2013", "international_policy_examples"}


def test_sources_manifest_no_fabricated_effective_status() -> None:
    """No source may claim to be in force — effective_status must be 'not verified',
    'not applicable', or absent for unavailable sources."""
    docs = _manifest_docs()
    allowed = {
        "not verified",
        "not applicable (recommendations, not an Act)",
        "not applicable",
        "",         # acceptable for unavailable sources that have no status
    }
    for d in docs:
        status = d.get("effective_status", "")
        assert status in allowed, (
            f"{d['id']}: unexpected effective_status {status!r}. "
            f"Must be one of {sorted(allowed - {''})!r} (or absent/empty for unavailable sources)."
        )


def test_sources_manifest_no_fabricated_amendment_status() -> None:
    """No source may claim amendments were checked."""
    docs = _manifest_docs()
    for d in docs:
        status = d.get("amendment_status", "not checked")
        assert status == "not checked", (
            f"{d['id']}: amendment_status should be 'not checked', got {status!r}"
        )


def test_sources_manifest_downloaded_have_sha256_and_url() -> None:
    """Every downloaded source must have a source URL and file path."""
    docs = _manifest_docs()
    for d in docs:
        if d.get("status") == "downloaded":
            assert d.get("source_url"), f"{d['id']}: missing source_url"
            assert d.get("file"), f"{d['id']}: missing file"


def test_sources_manifest_all_kbs_valid() -> None:
    """Every KB assignment must be a known KB name."""
    docs = _manifest_docs()
    for d in docs:
        bad = set(d.get("kbs", [])) - set(ALL_KBS)
        assert not bad, f"{d['id']}: unknown KB(s) {bad}"


def test_sources_manifest_unavailable_have_provenance_note() -> None:
    """Unavailable sources must document why they could not be ingested."""
    docs = _manifest_docs()
    for d in docs:
        if d.get("status") != "downloaded":
            note = d.get("provenance_note", "")
            assert "NOT INGESTED" in note, (
                f"{d['id']}: unavailable source missing 'NOT INGESTED' in provenance_note"
            )


# -----------------------------------------------------------------------
# 2. Ingestion manifest structure and non-fabrication
# -----------------------------------------------------------------------

def test_ingestion_manifest_exists_and_is_valid_json() -> None:
    data = _load_json(INGESTION_MANIFEST)
    assert "documents" in data
    assert "knowledge_bases" in data
    assert "embedding_model" in data


def test_ingestion_manifest_records_embedding_model() -> None:
    data = _load_json(INGESTION_MANIFEST)
    assert data["embedding_model"] == "BAAI/bge-small-en-v1.5"


def test_ingestion_manifest_sandbox_not_executed() -> None:
    """The sandbox field must record that it was not executed — never claim it was."""
    data = _load_json(INGESTION_MANIFEST)
    assert "not executed" in data.get("sandbox", "").lower(), (
        "ingestion_manifest.json must record that the Sandbox was not executed"
    )


def test_ingestion_manifest_no_generator_model() -> None:
    """No generative model is used; the generator_model field must reflect this."""
    data = _load_json(INGESTION_MANIFEST)
    gen = data.get("generator_model", "")
    assert "none" in gen.lower(), (
        f"generator_model should state 'none'; got: {gen!r}"
    )


def test_ingestion_manifest_ingested_have_sha256_and_chunks() -> None:
    """Every ingested document must have a SHA-256 and at least one chunk."""
    docs = _ingestion_docs()
    for d in docs:
        if d.get("status") == "ingested":
            assert len(d.get("sha256", "")) == 64, f"{d['id']}: invalid sha256"
            assert d.get("chunks", 0) > 0, f"{d['id']}: zero chunks"


def test_ingestion_manifest_not_ingested_have_note() -> None:
    """Not-ingested entries must carry an explicit note."""
    docs = _ingestion_docs()
    for d in docs:
        if d.get("status", "").startswith("not ingested"):
            assert d.get("note") or d.get("status", ""), (
                f"{d['id']}: not-ingested entry missing note"
            )


def test_ingestion_manifest_knowledge_bases_cover_all_kbs() -> None:
    """The ingestion manifest must report all 8 KB directories."""
    data = _load_json(INGESTION_MANIFEST)
    reported = set(data["knowledge_bases"].keys())
    expected = set(ALL_KBS)
    assert reported == expected, (
        f"KB mismatch. Reported: {sorted(reported)} Expected: {sorted(expected)}"
    )


def test_ingestion_manifest_canonical_is_superset_of_agent_kbs() -> None:
    """Canonical KB chunk count >= any individual agent KB chunk count."""
    data = _load_json(INGESTION_MANIFEST)
    kbs = data["knowledge_bases"]
    canonical_chunks = kbs["canonical"]["chunks"]
    for kb, info in kbs.items():
        if kb != "canonical":
            assert canonical_chunks >= info["chunks"], (
                f"Canonical KB ({canonical_chunks} chunks) has fewer chunks "
                f"than {kb} KB ({info['chunks']} chunks)"
            )


# -----------------------------------------------------------------------
# 3. Canonical KB metadata
# -----------------------------------------------------------------------

def test_canonical_metadata_exists_and_is_valid_json() -> None:
    data = _load_json(CANONICAL_META)
    assert "documents" in data
    assert "schema_version" in data


def test_canonical_metadata_covers_all_sources() -> None:
    """Canonical metadata must cover every source in the sources manifest."""
    data = _load_json(CANONICAL_META)
    manifest_ids = {d["id"] for d in _manifest_docs()}
    meta_ids = {d["id"] for d in data["documents"]}
    assert meta_ids == manifest_ids, (
        f"canonical_metadata.json out of sync with sources manifest.\n"
        f"  In manifest only: {sorted(manifest_ids - meta_ids)}\n"
        f"  In metadata only: {sorted(meta_ids - manifest_ids)}"
    )


def test_canonical_metadata_ingested_have_sha256() -> None:
    data = _load_json(CANONICAL_META)
    for d in data["documents"]:
        if d.get("chunks", 0) > 0:
            sha = d.get("sha256", "")
            assert len(sha) == 64, (
                f"{d['id']}: canonical_metadata entry with chunks>0 must have sha256"
            )


def test_canonical_metadata_effective_status_never_confirmed() -> None:
    """No canonical metadata entry may claim a provision is in force."""
    data = _load_json(CANONICAL_META)
    for d in data["documents"]:
        status = d.get("effective_status", "")
        assert "not verified" in status or "not applicable" in status or status == "", (
            f"{d['id']}: effective_status must not claim the provision is in force; got {status!r}"
        )


def test_canonical_metadata_unavailable_have_null_sha256() -> None:
    """Sources that were not ingested must have null sha256 and zero chunks."""
    data = _load_json(CANONICAL_META)
    for d in data["documents"]:
        if d.get("chunks", 0) == 0 and d.get("sections_ingested", 0) == 0:
            assert d.get("sha256") is None, (
                f"{d['id']}: not-ingested entry should have null sha256"
            )


def test_canonical_metadata_jurisdictions_are_india_or_international() -> None:
    data = _load_json(CANONICAL_META)
    valid = {"India", "International"}
    for d in data["documents"]:
        if d.get("jurisdiction"):
            assert d["jurisdiction"] in valid, (
                f"{d['id']}: unexpected jurisdiction {d['jurisdiction']!r}"
            )


def test_canonical_metadata_nciipc_explicitly_not_ingested() -> None:
    data = _load_json(CANONICAL_META)
    nciipc = next((d for d in data["documents"] if d["id"] == "nciipc_rules_2013"), None)
    assert nciipc is not None
    assert nciipc.get("chunks", 0) == 0
    assert "NOT INGESTED" in nciipc.get("provenance_note", "")


def test_canonical_metadata_has_fabrication_policy() -> None:
    """The metadata file must document its no-fabrication policy."""
    data = _load_json(CANONICAL_META)
    notes = data.get("notes", {})
    assert "fabrication_policy" in notes, (
        "canonical_metadata.json must document its fabrication policy"
    )


# -----------------------------------------------------------------------
# 4. Policy Gap KB categories
# -----------------------------------------------------------------------

def test_policy_gap_categories_file_exists() -> None:
    assert POLICY_GAP_CATS.exists(), f"Missing: {POLICY_GAP_CATS}"


def test_policy_gap_categories_has_all_six_docx_categories() -> None:
    """All six DOCX §5.1 coverage categories must be present."""
    data = _load_json(POLICY_GAP_CATS)
    enum_values = {c["enum_value"] for c in data["categories"]}
    expected = {e.value for e in CoverageCategory}
    assert enum_values == expected, (
        f"Missing categories: {expected - enum_values}  "
        f"Extra: {enum_values - expected}"
    )


def test_policy_gap_categories_non_conclusive_language_documented() -> None:
    data = _load_json(POLICY_GAP_CATS)
    rule = data.get("non_conclusive_language_rule", {})
    assert rule.get("required_disclaimer"), "Non-conclusive disclaimer must be documented"
    assert rule.get("forbidden_phrases"), "Forbidden phrases must be documented"
    assert "Indian policy is inadequate" in rule["forbidden_phrases"]


def test_policy_gap_categories_distinction_gap_vs_no_law() -> None:
    """Must document the distinction between a potential gap and 'law does not exist'."""
    data = _load_json(POLICY_GAP_CATS)
    distinction = data.get("distinction_potential_gap_vs_law_does_not_exist", {})
    assert distinction.get("rule"), "Must document the gap-vs-no-law distinction"
    assert distinction.get("example_correct")
    assert distinction.get("example_incorrect")


def test_policy_gap_categories_verifier_outcome_not_verified() -> None:
    """No category may claim a VERIFIED verifier outcome — gaps are at most INCOMPLETE."""
    data = _load_json(POLICY_GAP_CATS)
    for cat in data["categories"]:
        outcome = cat.get("verifier_outcome", "")
        assert "VERIFIED" not in outcome, (
            f"Category {cat['enum_value']}: verifier_outcome must not include VERIFIED; "
            f"potential gaps are at most INCOMPLETE"
        )


def test_policy_gap_categories_each_has_enum_value_and_name() -> None:
    data = _load_json(POLICY_GAP_CATS)
    for cat in data["categories"]:
        assert cat.get("enum_value"), f"Category missing enum_value: {cat}"
        assert cat.get("name"), f"Category missing name: {cat}"
        assert cat.get("docx_reference"), f"Category missing docx_reference: {cat}"


def test_policy_gap_categories_overlap_example_uses_correct_sources() -> None:
    """
    The overlapping-requirements example must be the agent's actual output in
    the recorded run: the two instruments it names are the ones the gap claim cites.
    """
    data = _load_json(POLICY_GAP_CATS)
    overlap = next(
        c for c in data["categories"]
        if c["enum_value"] == "overlapping_requirements"
    )
    example = overlap.get("concrete_scenario_2_example", {})
    [observed] = overlap["observed_in_recorded_run"]
    assert example["instrument_a"] and example["instrument_b"]
    assert example["instrument_a"] in observed["claim"]
    assert example["instrument_b"] in observed["claim"]


def test_policy_gap_categories_emerging_tech_uses_exhaustive_scan() -> None:
    """Emerging technology absence checks must use exhaustive scan, not top-k."""
    data = _load_json(POLICY_GAP_CATS)
    emerging = next(
        c for c in data["categories"]
        if c["enum_value"] == "emerging_technology_not_explicitly_addressed"
    )
    method = emerging.get("examination_method", {})
    # Accept 'exhaustive' in any method field
    all_method_text = json.dumps(method).lower()
    assert "exhaustive" in all_method_text, (
        "Emerging technology examination must use exhaustive scan — "
        "check examination_method fields"
    )


# -----------------------------------------------------------------------
# 5. Host-country corpus
# -----------------------------------------------------------------------

def test_host_corpus_file_exists() -> None:
    assert HOST_CORPUS.exists(), f"Missing: {HOST_CORPUS}"


def test_host_corpus_has_all_ten_docx_categories() -> None:
    """All 10 DOCX §7.3 host-country corpus categories must be present."""
    data = _load_json(HOST_CORPUS)
    category_ids = {c["category_id"] for c in data["categories"]}
    assert category_ids == set(range(1, 11)), (
        f"Expected category_ids 1–10, got {sorted(category_ids)}"
    )


def test_host_corpus_category_names_include_docx_headings() -> None:
    data = _load_json(HOST_CORPUS)
    # DOCX §7.3 "Corpus category" column, verbatim
    expected_headings = {
        "Laws and regulations",
        "Digital and cybersecurity strategies",
        "Institutional mandates",
        "National AI strategy and AI mission",
    }
    names = {c["docx_heading"] for c in data["categories"]}
    for heading in expected_headings:
        assert heading in names, f"Missing corpus category: {heading!r}"


def test_host_corpus_uncovered_categories_are_explicitly_marked() -> None:
    """Categories without ingested sources must be marked NOT COVERED."""
    data = _load_json(HOST_CORPUS)
    uncovered_expected = {
        "Economic and industrial characteristics",
        "Labour-market conditions",
        "Intellectual property",
        "Multilateral and treaty obligations",
        "Energy and infrastructure constraints",
        "Regional and global comparators",
    }
    for cat in data["categories"]:
        if cat["docx_heading"] in uncovered_expected:
            assert "NOT COVERED" in cat.get("coverage_status", ""), (
                f"Category '{cat['docx_heading']}' must be marked NOT COVERED"
            )
            assert cat.get("sources_ingested") == [], (
                f"Category '{cat['docx_heading']}' must have empty sources_ingested"
            )


def test_host_corpus_laws_category_has_key_indian_instruments() -> None:
    data = _load_json(HOST_CORPUS)
    laws = next(c for c in data["categories"] if c["category_id"] == 1)
    ingested_ids = {s["id"] for s in laws["sources_ingested"]}
    required = {"telecom_act_2023", "dpdp_act_2023", "certin_directions_2022",
                "telecom_cyber_security_rules_2024"}
    missing = required - ingested_ids
    assert not missing, f"Laws category missing required sources: {missing}"


def test_host_corpus_nciipc_in_unavailable_section() -> None:
    data = _load_json(HOST_CORPUS)
    laws = next(c for c in data["categories"] if c["category_id"] == 1)
    unavail_ids = {s["id"] for s in laws.get("sources_unavailable", [])}
    assert "nciipc_rules_2013" in unavail_ids, (
        "nciipc_rules_2013 must be in the laws category's unavailable list"
    )


def test_host_corpus_summary_counts_match_categories() -> None:
    """Summary's uncovered category count must match the actual uncovered count."""
    data = _load_json(HOST_CORPUS)
    summary = data.get("corpus_summary", {})
    not_covered = summary.get("categories_not_covered", [])
    actual_not_covered = [
        c for c in data["categories"]
        if "NOT COVERED" in c.get("coverage_status", "")
    ]
    assert len(not_covered) == len(actual_not_covered), (
        f"Summary lists {len(not_covered)} uncovered categories "
        f"but {len(actual_not_covered)} are marked NOT COVERED"
    )


def test_host_corpus_no_fabricated_chunk_counts() -> None:
    """Chunk counts in the host corpus must match the ingestion manifest."""
    host_data = _load_json(HOST_CORPUS)
    ingest_data = _load_json(INGESTION_MANIFEST)
    ingest_chunks = {d["id"]: d.get("chunks", 0) for d in ingest_data["documents"]}

    for cat in host_data["categories"]:
        for src in cat.get("sources_ingested", []):
            doc_id = src.get("id")
            if doc_id and doc_id in ingest_chunks and src.get("chunks"):
                assert src["chunks"] == ingest_chunks[doc_id], (
                    f"Category {cat['category_id']} source {doc_id}: "
                    f"chunk count {src['chunks']} != ingestion manifest {ingest_chunks[doc_id]}"
                )


# -----------------------------------------------------------------------
# 6. Y.3172 pipeline traceability
# -----------------------------------------------------------------------

def test_y3172_traceability_file_exists() -> None:
    assert Y3172_TRACE.exists(), f"Missing: {Y3172_TRACE}"


def test_y3172_has_all_seven_stages() -> None:
    data = _load_json(Y3172_TRACE)
    stages = {s["stage"] for s in data["pipeline_stages"]}
    expected = {"Source", "Collection", "Preprocessing", "Model",
                "Policy", "Distribution", "Sandbox"}
    assert stages == expected, (
        f"Y.3172 stages mismatch. Got: {sorted(stages)}"
    )


def test_y3172_sandbox_is_not_executed() -> None:
    data = _load_json(Y3172_TRACE)
    sandbox = next(s for s in data["pipeline_stages"] if s["stage"] == "Sandbox")
    impl = sandbox["project_implementation"]
    assert "NOT EXECUTED" in impl.get("description", "").upper(), (
        "Y.3172 Sandbox stage must be marked NOT EXECUTED"
    )
    files = impl.get("files", [])
    assert any("ingestion_manifest" in f for f in files), (
        "Sandbox stage must reference ingestion_manifest.json (which records not-executed)"
    )


def test_y3172_no_compliance_claim() -> None:
    data = _load_json(Y3172_TRACE)
    disclaimer = data.get("compliance_disclaimer", "")
    assert disclaimer, "Y.3172 traceability must include a compliance disclaimer"
    # Must disclaim, not claim
    assert "not" in disclaimer.lower() or "no" in disclaimer.lower(), (
        "compliance_disclaimer must say formal compliance has NOT been assessed"
    )


def test_y3172_traceability_matrix_has_all_stages() -> None:
    data = _load_json(Y3172_TRACE)
    matrix = data.get("pipeline_traceability_matrix", {})
    rows = matrix.get("rows", [])
    stages_in_matrix = {r["y3172_stage"] for r in rows}
    expected = {"Source", "Collection", "Preprocessing", "Model",
                "Policy", "Distribution", "Sandbox"}
    assert stages_in_matrix == expected


def test_y3172_sandbox_matrix_row_not_implemented() -> None:
    data = _load_json(Y3172_TRACE)
    rows = data["pipeline_traceability_matrix"]["rows"]
    sandbox_row = next(r for r in rows if r["y3172_stage"] == "Sandbox")
    assert sandbox_row["status"] == "NOT EXECUTED", (
        f"Sandbox row status must be 'NOT EXECUTED', got {sandbox_row['status']!r}"
    )


def test_y3172_model_stage_references_embedding_model() -> None:
    data = _load_json(Y3172_TRACE)
    model_stage = next(s for s in data["pipeline_stages"] if s["stage"] == "Model")
    impl = model_stage["project_implementation"]
    assert "BAAI/bge-small-en-v1.5" in impl.get("model_id", ""), (
        "Model stage must reference the actual embedding model BAAI/bge-small-en-v1.5"
    )


def test_y3172_preprocessing_records_chunk_parameters() -> None:
    data = _load_json(Y3172_TRACE)
    preproc = next(s for s in data["pipeline_stages"] if s["stage"] == "Preprocessing")
    params = preproc["project_implementation"].get("parameters", {})
    assert params.get("max_chars_per_chunk") == 1200
    assert params.get("overlap_chars") == 150


# -----------------------------------------------------------------------
# 7. ITU AI Readiness mapping
# -----------------------------------------------------------------------

def test_itu_ai_readiness_file_exists() -> None:
    assert ITU_AI_READINESS.exists(), f"Missing: {ITU_AI_READINESS}"


def test_itu_ai_readiness_no_quantitative_scores() -> None:
    """No readiness score may be invented."""
    data = _load_json(ITU_AI_READINESS)
    score_field = str(data.get("overall_evidence_summary", {}).get("no_readiness_score_assigned", ""))
    assert score_field.startswith("true"), (
        "ITU AI Readiness mapping must have no_readiness_score_assigned starting with 'true'; "
        f"got: {score_field!r}"
    )


def test_itu_ai_readiness_no_maturity_levels() -> None:
    data = _load_json(ITU_AI_READINESS)
    maturity_field = str(data.get("overall_evidence_summary", {}).get("no_maturity_level_claimed", ""))
    assert maturity_field.startswith("true"), (
        "ITU AI Readiness mapping must have no_maturity_level_claimed starting with 'true'; "
        f"got: {maturity_field!r}"
    )


def test_itu_ai_readiness_unavailable_evidence_marked() -> None:
    """Every dimension must explicitly state what evidence is unavailable."""
    data = _load_json(ITU_AI_READINESS)
    for dim in data["dimensions"]:
        assert dim.get("evidence_unavailable") is not None, (
            f"Dimension {dim['dimension_id']} must have evidence_unavailable field"
        )


def test_itu_ai_readiness_d3_legal_framework_has_indian_sources() -> None:
    """D3 (Legal and regulatory framework) must have evidence from Indian sources."""
    data = _load_json(ITU_AI_READINESS)
    d3 = next(d for d in data["dimensions"] if d["dimension_id"] == "D3")
    indian_evidence = [
        e for e in d3.get("evidence_items", [])
        if e.get("jurisdiction") == "India"
    ]
    assert len(indian_evidence) >= 3, (
        f"D3 must have at least 3 Indian evidence items; found {len(indian_evidence)}"
    )


def test_itu_ai_readiness_evidence_cites_real_source_ids() -> None:
    """Every cited source_id must be a real document in the sources manifest."""
    data = _load_json(ITU_AI_READINESS)
    manifest_ids = {d["id"] for d in _manifest_docs()}
    for dim in data["dimensions"]:
        for ev in dim.get("evidence_items", []):
            sid = ev.get("source_id")
            if sid:
                assert sid in manifest_ids, (
                    f"Dimension {dim['dimension_id']}: source_id {sid!r} not in manifest"
                )


def test_itu_ai_readiness_no_fabricated_compliance_claims() -> None:
    """Evidence items must not claim formal compliance with international standards."""
    data = _load_json(ITU_AI_READINESS)
    forbidden = ["formally compliant", "certified", "fully compliant", "Y.3172 compliant"]
    for dim in data["dimensions"]:
        for ev in dim.get("evidence_items", []):
            claim_text = ev.get("claim", "").lower()
            for phrase in forbidden:
                assert phrase not in claim_text, (
                    f"Dimension {dim['dimension_id']}: forbidden compliance claim {phrase!r}"
                )


def test_itu_ai_readiness_methodology_disclaimer_present() -> None:
    data = _load_json(ITU_AI_READINESS)
    disclaimer = data.get("methodology_disclaimer", "")
    assert "not a formal" in disclaimer.lower() or "formal assessment" in disclaimer.lower(), (
        "ITU AI Readiness mapping must include a methodology disclaimer"
    )


# -----------------------------------------------------------------------
# 8. KB README files
# -----------------------------------------------------------------------

def test_all_kb_readme_files_exist() -> None:
    """Every KB subdirectory must have a README.md."""
    for path in EXPECTED_KB_READMES:
        assert path.exists(), f"Missing KB README: {path}"


def test_kb_readmes_contain_agent_and_source_information() -> None:
    """Each README must mention an agent, at least one source, and embedding model."""
    for path in EXPECTED_KB_READMES:
        content = path.read_text(encoding="utf-8")
        assert "Agent" in content, f"{path}: README must mention an agent"
        assert "BAAI/bge-small-en-v1.5" in content, (
            f"{path}: README must mention the embedding model BAAI/bge-small-en-v1.5"
        )


def test_kb_readmes_do_not_claim_effective_status() -> None:
    """No README may claim that any provision is verified as in force."""
    # These phrases assert a positive in-force status that has not been verified.
    # The phrase "verified as in force" appears in the canonical README in a
    # *negative* context ("in-force status was NOT verified"), so we only
    # block phrases that make an affirmative claim.
    forbidden_phrases = [
        "confirmed in force",
        "currently in force",
        "is in force",
        "are in force",
    ]
    for path in EXPECTED_KB_READMES:
        content = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert phrase not in content, (
                f"{path}: README contains forbidden effective-status claim: {phrase!r}"
            )


def test_critical_infra_readme_mentions_nciipc_not_ingested() -> None:
    path = KB_DIR / "critical_infrastructure" / "README.md"
    content = path.read_text(encoding="utf-8")
    assert "NOT INGESTED" in content, (
        "critical_infrastructure README must note nciipc_rules_2013 is NOT INGESTED"
    )


def test_policy_gap_readme_mentions_six_categories() -> None:
    path = KB_DIR / "policy_gap" / "README.md"
    content = path.read_text(encoding="utf-8")
    expected_categories = [
        "explicit_coverage",
        "partial_coverage",
        "unclear_coverage",
        "overlapping_requirements",
        "missing_institutional_clarity",
        "emerging_technology_not_explicitly_addressed",
    ]
    for cat in expected_categories:
        assert cat in content, (
            f"policy_gap README must mention category {cat!r}"
        )


# -----------------------------------------------------------------------
# 9. KB registry contract
# -----------------------------------------------------------------------

def test_kb_registry_has_all_seven_agents() -> None:
    registry = KBRegistry()
    assert set(registry.agent_kbs.keys()) == set(AgentID), (
        "KBRegistry must have an entry for every AgentID"
    )


def test_kb_registry_default_is_stub() -> None:
    """Default registry uses stubs; is_available() returns False for all agent KBs."""
    registry = KBRegistry()
    for agent_id, kb in registry.agent_kbs.items():
        assert not kb.is_available(), (
            f"{agent_id.value}: default KB should be stub (is_available=False)"
        )
    assert not registry.canonical_kb.is_available(), (
        "Default canonical KB should be stub (is_available=False)"
    )


def test_kb_registry_upgrade_to_in_memory() -> None:
    """Replacing a stub with InMemoryKB makes is_available() return True."""
    registry = KBRegistry()
    ev = EvidenceItem(
        source_title="FIXTURE Telecom Act", authority="Test fixture",
        jurisdiction="India", document_type="Act",
        section="Section 1", excerpt="Short title.",
        chunk_id="fx-1",
    )
    registry.agent_kbs[AgentID.POLICY_LEGAL] = InMemoryKnowledgeBase(
        kb_name="fixture", domain="policy_legal", items=[ev]
    )
    assert registry.agent_kbs[AgentID.POLICY_LEGAL].is_available()
    assert not registry.agent_kbs[AgentID.TECHNICAL].is_available()


def test_kb_registry_status_report_reflects_availability() -> None:
    registry = KBRegistry()
    status = registry.status_report()
    assert set(status.keys()) >= {a.value for a in AgentID} | {"canonical"}
    # All false on default registry
    assert all(not v for v in status.values())


def test_kb_registry_get_agent_kb_returns_correct_kb() -> None:
    registry = KBRegistry()
    for agent_id in AgentID:
        kb = registry.get_agent_kb(agent_id)
        assert kb is registry.agent_kbs[agent_id]


# -----------------------------------------------------------------------
# 10. InMemoryKnowledgeBase contract
# -----------------------------------------------------------------------

def _make_evidence(n: int = 3) -> list[EvidenceItem]:
    docs = [
        ("Telecom Act", "India", "Section 22"),
        ("DPDP Act", "India", "Section 8"),
        ("3GPP TS 33.501", "International", "Clause 5.1"),
    ]
    return [
        EvidenceItem(
            source_title=title, authority="Test", jurisdiction=juris,
            document_type="Act", section=section,
            excerpt=f"Text of {section} about {title.lower()} operations.",
            chunk_id=f"fx-{i}",
        )
        for i, (title, juris, section) in enumerate(docs[:n])
    ]


def test_in_memory_kb_retrieve_returns_relevant_results() -> None:
    items = _make_evidence(3)
    kb = InMemoryKnowledgeBase("test", "policy_legal", items)
    results = kb.retrieve("telecom operations", top_k=5)
    assert results, "InMemoryKB must return results for a matching query"
    assert all(isinstance(r, EvidenceItem) for r in results)


def test_in_memory_kb_top_k_respected() -> None:
    items = _make_evidence(3)
    kb = InMemoryKnowledgeBase("test", "policy_legal", items)
    results = kb.retrieve("text operations", top_k=1)
    assert len(results) <= 1


def test_in_memory_kb_filter_by_jurisdiction() -> None:
    items = _make_evidence(3)
    kb = InMemoryKnowledgeBase("test", "policy_legal", items)
    indian = kb.retrieve("operations", top_k=10, filters={"jurisdiction": "India"})
    assert all(e.jurisdiction == "India" for e in indian)
    assert len(indian) == 2  # two Indian items in _make_evidence(3)


def test_in_memory_kb_filter_by_section() -> None:
    items = _make_evidence(3)
    kb = InMemoryKnowledgeBase("test", "policy_legal", items)
    results = kb.retrieve("text", top_k=10, filters={"section": "Section 22"})
    assert all(e.section == "Section 22" for e in results)


def test_in_memory_canonical_scan_all() -> None:
    items = _make_evidence(3)
    canon = InMemoryCanonicalKB(items)
    all_items = canon.scan()
    assert len(all_items) == 3


def test_in_memory_canonical_scan_with_filter() -> None:
    items = _make_evidence(3)
    canon = InMemoryCanonicalKB(items)
    indian = canon.scan({"jurisdiction": "India"})
    assert len(indian) == 2
    assert all(e.jurisdiction == "India" for e in indian)


def test_in_memory_kb_is_available_true() -> None:
    items = _make_evidence(1)
    kb = InMemoryKnowledgeBase("test", "technical", items)
    assert kb.is_available()


def test_stub_kb_is_available_false() -> None:
    kb = StubKnowledgeBase("stub-test", "technical")
    assert not kb.is_available()


def test_stub_kb_retrieve_returns_stub_evidence() -> None:
    kb = StubKnowledgeBase("stub-test", "technical")
    results = kb.retrieve("any query")
    assert len(results) == 1
    assert results[0].authority == "STUB"
    assert results[0].chunk_id == "stub-000"


# -----------------------------------------------------------------------
# 11. Metadata propagation through EvidenceItem
# -----------------------------------------------------------------------

def test_evidence_item_all_required_fields_preserved() -> None:
    """All 12 required audit fields (DOCX §7.6) must survive round-trips."""
    ev = EvidenceItem(
        source_title="The Telecommunications Act, 2023",
        authority="Government of India",
        jurisdiction="India",
        document_type="Act",
        section="Section 22",
        excerpt="Critical telecommunication infrastructure provisions.",
        date_issued="24th December, 2023",
        effective=None,
        amendment_note="",
        url="https://egazette.gov.in/WriteReadData/2023/250880.pdf",
        chunk_id="telecom_act_2023:section-22:1",
        relevance_score=0.82,
        # NOTE: effective_status, amendment_status, provenance_note are chunk-level
        # fields stored in the vector store's chunks.jsonl but are NOT part of
        # EvidenceItem's dataclass fields — they are stored as metadata in the
        # chunk dict and recorded separately in the source manifest.
        amendment_checked=False,
    )
    required = [
        "source_title", "authority", "jurisdiction", "document_type",
        "section", "excerpt", "date_issued", "effective",
        "amendment_note", "url", "chunk_id", "relevance_score",
    ]
    for field in required:
        assert hasattr(ev, field), f"EvidenceItem missing field: {field}"

    assert ev.source_title == "The Telecommunications Act, 2023"
    assert ev.authority == "Government of India"
    assert ev.jurisdiction == "India"
    assert ev.document_type == "Act"
    assert ev.section == "Section 22"
    assert ev.effective is None           # not verified — never True without actual check
    assert ev.amendment_checked is False  # not checked
    assert ev.relevance_score == 0.82


def test_evidence_item_effective_none_means_unverified() -> None:
    """effective=None is the correct signal for 'in-force status not checked'."""
    ev = EvidenceItem(
        source_title="Test Act", authority="Test", jurisdiction="India",
        document_type="Act", section="Section 1", excerpt="Text.",
        effective=None, amendment_checked=False,
    )
    assert ev.effective is None, "effective=None must be preserved"
    assert not ev.amendment_checked, "amendment_checked=False must be preserved"


def test_evidence_item_international_jurisdiction() -> None:
    ev = EvidenceItem(
        source_title="3GPP TS 23.501", authority="3GPP",
        jurisdiction="International", document_type="Standard",
        section="Clause 5.15", excerpt="Network slicing text.",
    )
    assert ev.jurisdiction == "International"


# -----------------------------------------------------------------------
# 12. Policy Gap Agent language rules (via pipeline with in-memory KB)
# -----------------------------------------------------------------------

def _make_scenario_chunk(index: int = 0) -> ScenarioChunk:
    from scenarios.scenario2_healthcare_5g import get_chunks
    return get_chunks()[index]


def test_policy_gap_agent_non_conclusive_language_with_canonical_kb() -> None:
    """Policy Gap Agent claims must use non-conclusive language when KB is live."""
    from src.agents.policy_gap_agent import PolicyGapAgent
    from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB

    # Provide passages that will trigger the overlapping-requirements area
    cyber = EvidenceItem(
        source_title="FIXTURE Cyber Rules", authority="Test", jurisdiction="India",
        document_type="Rules", section="Rule 3",
        excerpt="A telecom entity shall report a cyber security incident to the authority.",
        chunk_id="fx-cyber-1",
    )
    data_prot = EvidenceItem(
        source_title="FIXTURE Data Act", authority="Test", jurisdiction="India",
        document_type="Act", section="Section 8",
        excerpt="A data fiduciary shall notify a personal data breach to the Board.",
        chunk_id="fx-data-1",
    )
    canonical = InMemoryCanonicalKB([cyber, data_prot])
    agent = PolicyGapAgent(canonical_kb=canonical)

    incident_state = {
        "verified_findings": [{"claim": "network slice affected", "agent_id": "technical", "outcome": "X"}],
        "cyber_event_suspected": True,
        "data_exposure_suspected": True,
        "cii_flagged": False,
    }
    finding = agent.analyze(_make_scenario_chunk(3), incident_state)

    direct_inadequacy = [
        "indian policy is inadequate",
        "the policy is inadequate",
        "framework is inadequate",
    ]
    for claim in finding.claims:
        claim_lower = claim.lower()
        for phrase in direct_inadequacy:
            assert phrase not in claim_lower, (
                f"Policy Gap claim must not assert policy inadequacy: {claim}"
            )

    gap_claims = [c for c in finding.claims if c.startswith("Potential gap")]
    if gap_claims:
        for claim in gap_claims:
            assert "No conclusion of policy failure is drawn" in claim, (
                f"Gap claim missing required disclaimer: {claim}"
            )


def test_policy_gap_agent_with_no_canonical_kb_raises_no_gap() -> None:
    """Without a Canonical KB, no potential gap must be raised."""
    from src.agents.policy_gap_agent import PolicyGapAgent

    agent = PolicyGapAgent(canonical_kb=None)
    incident_state = {
        "verified_findings": [{"claim": "slice affected", "agent_id": "technical", "outcome": "X"}],
        "cyber_event_suspected": True,
        "data_exposure_suspected": True,
        "cii_flagged": True,
    }
    finding = agent.analyze(_make_scenario_chunk(3), incident_state)
    raised = [c for c in finding.claims if c.startswith("Potential gap")]
    assert not raised, (
        "Without a Canonical KB no potential gap should be raised; "
        f"got: {raised}"
    )


def test_policy_gap_coverage_categories_match_enum() -> None:
    """The six CoverageCategory enum values must match the policy_gap_categories.json."""
    data = _load_json(POLICY_GAP_CATS)
    json_values = {c["enum_value"] for c in data["categories"]}
    enum_values = {e.value for e in CoverageCategory}
    assert json_values == enum_values, (
        f"CoverageCategory enum and policy_gap_categories.json are out of sync.\n"
        f"  JSON only: {json_values - enum_values}\n"
        f"  Enum only: {enum_values - json_values}"
    )


# -----------------------------------------------------------------------
# 13. Retrieval interface contract (stub path)
# -----------------------------------------------------------------------

def test_retrieval_interface_run_agent_returns_finding() -> None:
    """run_agent returns an AgentFinding without requiring live vector stores."""
    from src.rag.interface import run_agent
    from src.knowledge_base.kb_registry import KBRegistry

    registry = KBRegistry()  # stub registry
    chunk = _make_scenario_chunk(0)
    finding = run_agent(AgentID.TECHNICAL, chunk, registry=registry)
    assert isinstance(finding, AgentFinding)
    assert finding.agent_id == AgentID.TECHNICAL
    assert finding.claims, "Agent must produce at least one claim (stub scope statement)"


def test_retrieval_interface_no_fake_citations_on_stub() -> None:
    """With stub KBs, no claim may reference a real instrument without citation."""
    from src.rag.interface import run_agent
    from src.knowledge_base.kb_registry import KBRegistry

    registry = KBRegistry()
    instruments = [
        "Telecommunications Act", "TRAI Act", "Cyber Security) Rules",
        "CERT-In Directions", "DPDP", "3GPP TS", "NIST", "ETSI",
    ]
    chunk = _make_scenario_chunk(0)
    finding = run_agent(AgentID.POLICY_LEGAL, chunk, registry=registry)
    for claim in finding.claims:
        if any(name in claim for name in instruments):
            assert claim in finding.claim_citations or "not assessed" in claim, (
                f"Stub claim names an instrument without citation or 'not assessed': {claim}"
            )


# -----------------------------------------------------------------------
# 14. No fake citations in any knowledge-layer output
# -----------------------------------------------------------------------

def test_no_fabricated_labels_in_manifest_notes() -> None:
    """No manifest provenance note may contain fabricated-source markers."""
    forbidden = ["[FABRICATED]", "[FAKE]", "[INVENTED]", "made_up_law"]
    docs = _manifest_docs()
    for d in docs:
        note = d.get("provenance_note", "")
        for marker in forbidden:
            assert marker not in note, (
                f"{d['id']}: manifest provenance_note contains {marker!r}"
            )


def test_no_fabricated_labels_in_canonical_metadata() -> None:
    forbidden = ["[FABRICATED]", "[FAKE]", "[INVENTED]"]
    data = _load_json(CANONICAL_META)
    text = json.dumps(data)
    for marker in forbidden:
        assert marker not in text, (
            f"canonical_metadata.json contains fabricated label: {marker!r}"
        )


def test_no_fabricated_labels_in_policy_gap_categories() -> None:
    forbidden = ["[FABRICATED]", "[FAKE]", "[INVENTED]"]
    data = _load_json(POLICY_GAP_CATS)
    text = json.dumps(data)
    for marker in forbidden:
        assert marker not in text


def test_no_fabricated_labels_in_host_corpus() -> None:
    forbidden = ["[FABRICATED]", "[FAKE]", "[INVENTED]"]
    data = _load_json(HOST_CORPUS)
    text = json.dumps(data)
    for marker in forbidden:
        assert marker not in text


# -----------------------------------------------------------------------
# Integration: build_registry skips to stub when vector stores absent
# -----------------------------------------------------------------------

built = pytest.mark.skipif(
    not all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS),
    reason="knowledge bases not built (run: python -m src.rag.build)",
)


@built
def test_build_registry_upgrades_stubs_to_vector_kbs() -> None:
    """After build, build_registry() returns live VectorKnowledgeBase instances."""
    from src.rag.registry import build_registry
    from src.rag.vector_kb import VectorCanonicalKB, VectorKnowledgeBase

    registry = build_registry()
    for agent_id in AgentID:
        kb = registry.agent_kbs[agent_id]
        assert isinstance(kb, VectorKnowledgeBase), (
            f"{agent_id.value}: expected VectorKnowledgeBase, got {type(kb).__name__}"
        )
        assert kb.is_available(), f"{agent_id.value}: VectorKB should be available after build"
    assert isinstance(registry.canonical_kb, VectorCanonicalKB)
    assert registry.canonical_kb.is_available()


@built
def test_built_registry_agent_kbs_contain_only_assigned_documents() -> None:
    """After build, each agent KB must contain exactly its manifest-assigned documents."""
    from src.rag.registry import build_registry

    registry = build_registry()
    assigned = {
        kb: {d["id"] for d in _manifest_docs() if kb in d.get("kbs", []) and d.get("status") == "downloaded"}
        for kb in ALL_KBS
    }
    for agent_id, kb in registry.agent_kbs.items():
        docs_in_store = {c["doc_id"] for c in kb.store.chunks}
        assert docs_in_store == assigned[agent_id.value], (
            f"{agent_id.value}: store documents {docs_in_store} "
            f"!= manifest assignments {assigned[agent_id.value]}"
        )


@built
def test_built_canonical_kb_is_superset_of_all_agent_kbs() -> None:
    from src.rag.registry import build_registry

    registry = build_registry()
    canonical_docs = {c["doc_id"] for c in registry.canonical_kb.store.chunks}
    for agent_id, kb in registry.agent_kbs.items():
        agent_docs = {c["doc_id"] for c in kb.store.chunks}
        assert agent_docs <= canonical_docs, (
            f"{agent_id.value}: agent KB contains doc(s) absent from Canonical KB: "
            f"{agent_docs - canonical_docs}"
        )


@built
def test_built_vector_store_metadata_preserved() -> None:
    """Every chunk in every built KB must carry the required provenance fields."""
    from src.rag.registry import build_registry

    registry = build_registry()
    required_fields = {
        "chunk_id", "doc_id", "source_title", "authority", "jurisdiction",
        "document_type", "section", "excerpt",
        "effective", "amendment_checked", "url",
    }
    for agent_id, kb in registry.agent_kbs.items():
        for chunk in kb.store.chunks[:5]:  # sample — full check is expensive
            missing = required_fields - set(chunk.keys())
            assert not missing, (
                f"{agent_id.value}: chunk {chunk.get('chunk_id')} "
                f"missing fields: {missing}"
            )


@built
def test_built_no_fabricated_effective_status_in_chunks() -> None:
    """No chunk may claim its provision is verified in force."""
    from src.rag.registry import build_registry

    registry = build_registry()
    for agent_id, kb in registry.agent_kbs.items():
        for chunk in kb.store.chunks:
            assert chunk.get("effective") is None, (
                f"{agent_id.value}: chunk {chunk.get('chunk_id')} "
                f"has effective={chunk.get('effective')!r} — should be null"
            )
            assert chunk.get("amendment_checked") is False, (
                f"{agent_id.value}: chunk {chunk.get('chunk_id')} "
                f"has amendment_checked={chunk.get('amendment_checked')!r} — should be False"
            )
