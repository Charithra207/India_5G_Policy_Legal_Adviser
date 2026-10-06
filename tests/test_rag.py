"""
RAG / knowledge-base layer tests.

Unit tests need nothing but the code.  Integration tests use the built
knowledge bases (`python -m src.rag.build`) and are skipped if they are
absent.

Run with:
    python -m pytest tests/test_rag.py -v
"""

import json
import os
import sys
import tempfile
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
warnings.filterwarnings("ignore")

from src.core.models import AgentID, VerifierOutcome
from src.rag.extract import Block
from src.rag.manifest import ALL_KBS, KB_ROOT, SourceDocument, load_manifest
from src.rag.sections import (
    chunk_sections, remove_running_lines, split_by_outline, split_sections,
)
from src.rag.vector_store import VectorStore


def _blocks(lines, page=1):
    return [Block(text, page) for text in lines]


def _labels(lines, style, label):
    return [s.label for s in split_sections(_blocks(lines), style, label)]


# -----------------------------------------------------------------------
# Section detection — labels come only from printed headings
# -----------------------------------------------------------------------

def test_numbered_sections_increase_and_ignore_inner_lists() -> None:
    lines = [
        "1. Short title and commencement.—(1) These rules may be called the X Rules.",
        "2.",                                   # number printed alone
        "Definitions. — (1) In these rules,",
        "1. a numbered list item inside rule 2 is not a new rule",
        "[3. Inserted by an amending Act.— text of the inserted section",
        "3A. Inserted section with a letter suffix.— text",
        "THE FIRST SCHEDULE",
        "1. schedule item, not a section",
    ]
    assert _labels(lines, "numbered", "Rule") == [
        "Rule 1", "Rule 2", "Rule 3", "Rule 3A", "The First Schedule",
    ]


def test_roman_items_and_annexures_must_be_in_sequence() -> None:
    lines = [
        "(i) All service providers shall connect to the NTP server for clock sync.",
        "(ii) Any service provider shall report incidents within 6 hours of noticing.",
        "procedures as amended from time to time may be referred to as per",
        "Annexure III.",                        # a wrapped sentence, not a heading
        "(iii)When required by order of CERT-In the provider shall furnish details.",
        "Annexure I",
        "Types of cyber security incidents mandatorily to be reported",
    ]
    assert _labels(lines, "roman_items", "Direction") == [
        "Direction (i)", "Direction (ii)", "Direction (iii)", "Annexure I",
    ]


def test_outline_next_letter_i_is_not_part_i() -> None:
    lines = ["IV. Strategies"] + [f"{c}. Strategy heading {c}" for c in "ABCDEFGH"]
    lines += ["1) To promote awareness among citizens of cyber threats.",
              "I. Information sharing and cooperation",
              "1) To develop bilateral and multilateral relationships."]
    assert _labels(lines, "outline", "Part")[-4:] == [
        "Part IV H", "Part IV H item 1", "Part IV I", "Part IV I item 1",
    ]


def test_text_before_first_heading_is_labelled_by_page_not_guessed() -> None:
    blocks = _blocks(["Cover page text of a notification that precedes rule one."], page=3)
    blocks += _blocks(["1. Short title.— These rules may be called the Y Rules, 2024."], page=4)
    assert [s.label for s in split_sections(blocks, "numbered", "Rule")] == ["p. 3", "Rule 1"]


def test_clause_number_on_its_own_line_survives_cleaning() -> None:
    """Bare numbers are page numbers only at the top/bottom of a page."""
    blocks = []
    for page in range(1, 5):
        blocks += _blocks(["Running header", "body text one", "body text two",
                           "body text three", str(page)], page)
    blocks.insert(7, Block("4", 2))             # a clause number mid-page
    kept = [b.text for b in remove_running_lines(blocks)]
    assert "4" in kept and "Running header" not in kept and "3" not in kept


def test_outline_sections_follow_pdf_bookmarks() -> None:
    blocks = _blocks(["Cover"], 1) + _blocks(["4", "Network Function Virtualisation Security",
                                              "Body of clause four."], 2)
    blocks += _blocks(["4.1", "NFV High-Level Security Goals", "Body of 4.1."], 3)
    outline = [(1, "4 Network Function Virtualisation Security", 2),
               (2, "4.1 NFV High-Level Security Goals", 3),
               (2, "4.2 Not printed anywhere", 3)]
    sections, unmatched = split_by_outline(blocks, outline, "Clause")
    assert [s.label for s in sections] == ["p. 1", "Clause 4", "Clause 4.1"]
    assert unmatched == ["4.2 Not printed anywhere"]


def test_chunks_stay_within_one_section() -> None:
    long_body = ["Sentence number %d of the section body text. " % i for i in range(120)]
    sections = split_sections(_blocks(["1. Heading.— start"] + long_body), "numbered", "Section")
    chunks = chunk_sections(sections)
    assert len(chunks) > 1 and {c.section for c in chunks} == {"Section 1"}
    assert all(len(c.text) <= 1250 for c in chunks)


# -----------------------------------------------------------------------
# Manifest and ingestion safeguards
# -----------------------------------------------------------------------

def test_manifest_assignments_are_valid_and_unavailable_sources_are_explicit() -> None:
    docs = load_manifest()
    for d in docs:
        assert set(d.kbs) <= set(ALL_KBS) and d.kb_basis, d.id
        if d.status == "downloaded":
            assert d.source_url and d.file and d.title_evidence, d.id
            assert d.effective_status.startswith("not") or d.in_force, (
                f"{d.id}: in-force status claimed without an establishing document")
        else:
            assert "NOT INGESTED" in d.provenance_note, d.id
    assert {d.id for d in docs if d.status != "downloaded"} == {
        "nciipc_rules_2013", "international_policy_examples"}


def _tiny_pdf(text: str) -> Path:
    import pymupdf
    path = Path(tempfile.mkdtemp()) / "doc.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    doc.save(path)
    return path


def _doc(path: Path, **kw) -> SourceDocument:
    base = dict(id="t", title="T", status="downloaded", kbs=["policy_legal"],
                file=str(path), file_format="pdf", section_style="numbered",
                section_label="Section", title_evidence="THE TEST ACT, 2024",
                date_issued="1st January, 2024", date_evidence="[1st January, 2024.]")
    base.update(kw)
    return SourceDocument(**base)


def test_wrong_file_is_refused_by_title_evidence(monkeypatch) -> None:
    from src.rag import build
    path = _tiny_pdf("Annexure-A List of activities of a department")
    doc = _doc(path)
    monkeypatch.setattr(SourceDocument, "path", property(lambda self: Path(self.file)))
    records, report = build.process_document(doc)
    assert records == [] and report["status"].startswith("REFUSED")


def test_date_kept_only_when_stated_in_text(monkeypatch) -> None:
    from src.rag import build
    monkeypatch.setattr(SourceDocument, "path", property(lambda self: Path(self.file)))
    path = _tiny_pdf("THE TEST ACT, 2024\n1. Short title.— This Act may be called the Test Act.")
    records, report = build.process_document(_doc(path))
    assert report["date_issued"] == "" and not report["date_verified_in_text"]
    assert records and all(r["effective"] is None and r["amendment_checked"] is False
                           for r in records)


# -----------------------------------------------------------------------
# Integration — built knowledge bases
# -----------------------------------------------------------------------

built = pytest.mark.skipif(
    not all(VectorStore.exists(KB_ROOT / kb) for kb in ALL_KBS),
    reason="knowledge bases not built (run: python -m src.rag.build)",
)


@pytest.fixture(scope="module")
def registry():
    from src.rag.registry import build_registry
    return build_registry()


@built
def test_each_agent_kb_holds_only_its_assigned_documents(registry) -> None:
    assigned = {kb: {d.id for d in load_manifest() if kb in d.kbs and d.status == "downloaded"}
                for kb in ALL_KBS}
    for agent_id, kb in registry.agent_kbs.items():
        docs_in_store = {c["doc_id"] for c in kb.store.chunks}
        assert docs_in_store == assigned[agent_id.value], agent_id.value
    assert {c["doc_id"] for c in registry.canonical_kb.store.chunks} == assigned["canonical"]


@built
def test_one_retrieval_per_agent_with_source_and_section(registry) -> None:
    from scenarios.scenario2_healthcare_5g import get_chunks
    from src.rag.interface import run_agent
    chunks = get_chunks()
    state = {"cyber_event_suspected": True, "cii_flagged": True,
             "data_exposure_suspected": True,
             "verified_findings": [{"agent_id": "technical", "claim": "network slice", "outcome": "X"}]}
    stage = {AgentID.TECHNICAL: 0, AgentID.CYBERSECURITY: 1, AgentID.STANDARDS: 1,
             AgentID.CRITICAL_INFRA: 2, AgentID.PRIVACY: 2, AgentID.POLICY_LEGAL: 2,
             AgentID.POLICY_GAP: 3}
    for agent_id, i in stage.items():
        finding = run_agent(agent_id, chunks[i], state, registry)
        real = [e for e in finding.evidence if e.authority != "STUB"]
        assert real, f"{agent_id.value}: no passage retrieved"
        allowed = {c["doc_id"] for c in registry.agent_kbs[agent_id].store.chunks}
        for e in real:
            assert e.source_title and e.section and e.url and e.chunk_id.split(":")[0] in allowed
        if agent_id != AgentID.POLICY_GAP:
            assert finding.claim_citations, f"{agent_id.value}: no claim quotes a passage"


@built
def test_canonical_scan_is_exhaustive_and_filterable(registry) -> None:
    india = registry.canonical_kb.scan({"jurisdiction": "India"})
    total = registry.canonical_kb.scan()
    assert india and len(india) < len(total)
    assert all(e.jurisdiction == "India" for e in india)


@built
def test_section_lookup_finds_cited_provision(registry) -> None:
    hits = registry.canonical_kb.retrieve(
        "reporting of security incidents", top_k=5,
        filters={"source_title": "Telecommunications (Telecom Cyber Security) Rules, 2024",
                 "section": "Rule 7"})
    assert hits and all(h.section == "Rule 7" for h in hits)
    assert "Reporting of security incidents" in hits[0].excerpt


@built
def test_pipeline_with_live_kbs_never_verifies_unchecked_sources(registry) -> None:
    """In-force status and amendments are unchecked, so nothing can be VERIFIED."""
    from scenarios.scenario2_healthcare_5g import get_chunks
    from src.pipeline import Pipeline
    pipeline = Pipeline(registry)
    incomplete = 0
    for chunk in get_chunks():
        record = pipeline.run_chunk(chunk)
        for vc in record.verifier_result.verified_claims:
            assert vc.outcome != VerifierOutcome.VERIFIED, vc.claim
            incomplete += vc.outcome == VerifierOutcome.INCOMPLETE
    assert incomplete, "quoted passages confirmed in the Canonical KB should be INCOMPLETE"


@built
def test_ingestion_manifest_records_what_was_ingested() -> None:
    data = json.loads((KB_ROOT / "ingestion_manifest.json").read_text(encoding="utf-8"))
    status = {d["id"]: d["status"] for d in data["documents"]}
    assert status["nciipc_rules_2013"].startswith("not ingested")
    assert data["embedding_model"] and "not executed" in data["sandbox"]
    for d in data["documents"]:
        if d["status"] == "ingested":
            assert len(d["sha256"]) == 64 and d["chunks"] > 0
