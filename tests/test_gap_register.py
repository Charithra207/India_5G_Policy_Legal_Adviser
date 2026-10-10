"""
Step 4 of the build-a-thon plan: gap analysis with global and neighbouring-
region examples — regions and roles of sources, region-labelled comparators,
the domain-framed policy-gap register, and the UI pages.
"""

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.policy_gap_agent import PolicyGapAgent  # noqa: E402
from src.core.models import EvidenceItem  # noqa: E402
from src.gap.register import (LISTED, NOT_FOUND, PENDING, VERIFIED, Corpus, RegisterError,  # noqa: E402
                              build, check_anchor, main, render_markdown)
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase  # noqa: E402
from src.rag.manifest import load_manifest  # noqa: E402
from src.rag.regions import comparator_tag, region_of  # noqa: E402
from scenarios.scenario2_healthcare_5g import get_chunks  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INDEX_BUILT = (ROOT / "kb" / "index" / "chunks.jsonl.gz").exists()


# ---------------------------------------------------------------------------
# Regions and roles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("jurisdiction, region", [
    ("India", "india"), ("Sri Lanka", "south_asia"), ("Bangladesh", "south_asia"), ("Nepal", "south_asia"),
    ("European Union", "europe"), ("United Kingdom", "europe"), ("Singapore", "asia_pacific"),
    ("United States", "americas"), ("International", "global"), ("", "global"),
    ("European Union (ENISA)", "europe"),
])
def test_region_of(jurisdiction, region):
    assert region_of(jurisdiction) == region


def test_explicit_region_wins_and_tags():
    assert region_of("International", "south_asia") == "south_asia"
    assert comparator_tag("Sri Lanka") == "[Neighbouring-region example — Sri Lanka]"
    assert comparator_tag("European Union") == "[Global example — European Union]"
    assert comparator_tag("India") == ""


def test_manifest_accepts_region_and_role_and_rejects_unknown(tmp_path):
    docs = load_manifest()                                   # the committed manifest still loads
    assert docs and all(d.effective_region for d in docs)
    enisa = next(d for d in docs if d.id == "enisa_5g_security_controls_matrix")
    assert enisa.effective_region == "global"
    base = {"id": "x", "title": "X", "status": "downloaded", "kbs": ["policy_gap"], "jurisdiction": "Sri Lanka"}
    for extra, ok in (({"region": "south_asia", "role": "regional_example"}, True),
                      ({"region": "atlantis"}, False), ({"role": "gossip"}, False)):
        path = tmp_path / "m.json"
        path.write_text(json.dumps({"documents": [{**base, **extra}]}), encoding="utf-8")
        if ok:
            assert load_manifest(path)[0].effective_region == "south_asia"
        else:
            with pytest.raises(ValueError):
                load_manifest(path)


# ---------------------------------------------------------------------------
# Policy Gap Agent: region-labelled comparators, a neighbour first
# ---------------------------------------------------------------------------

def _item(title, jurisdiction, excerpt, chunk_id):
    return EvidenceItem(source_title=title, authority="fixture", jurisdiction=jurisdiction,
                        document_type="Policy", section="p. 1", excerpt=excerpt, chunk_id=chunk_id, page="1")


def test_comparators_are_region_labelled_with_a_neighbour_first():
    eu = _item("EU incident policy", "European Union",
               "Coordination between agencies for cyber security incident response policy 5G.", "eu:1")
    lk = _item("Sri Lanka incident policy", "Sri Lanka",
               "Coordination between agencies for cyber security incident response policy.", "lk:1")
    india = _item("Indian Rules", "India", "telecommunication network security incident reporting", "in:1")
    agent = PolicyGapAgent(InMemoryKnowledgeBase("Policy Gap KB", "policy_gap", [eu, lk]),
                           canonical_kb=InMemoryCanonicalKB([india]))
    state = {"verified_findings": [{"agent_id": "technical", "claim": "The network slice is degraded",
                                    "outcome": "UNSUPPORTED"}], "chunks_processed": ["T0"]}
    finding = agent.analyze(get_chunks()[3], state)
    comparators = [c for c in finding.claims if c.startswith("Comparator — ")]
    assert comparators and "Potential gap" in finding.gap_description
    assert comparators[0].startswith("Comparator — [REFERENCE ONLY — not Indian law] "
                                     "[Neighbouring-region example — Sri Lanka]")
    assert any("[Global example — European Union]" in c for c in comparators)
    assert not any("neighbouring-country comparator" in m.lower() for m in finding.missing_facts)


def test_missing_neighbour_is_stated():
    eu = _item("EU incident policy", "European Union",
               "Coordination between agencies for cyber security incident response.", "eu:1")
    agent = PolicyGapAgent(InMemoryKnowledgeBase("Policy Gap KB", "policy_gap", [eu]),
                           canonical_kb=InMemoryCanonicalKB([_item("Indian Rules", "India", "network", "in:1")]))
    finding = agent.analyze(get_chunks()[3], {"verified_findings": [], "chunks_processed": ["T0"]})
    assert any("No neighbouring-country comparator" in m for m in finding.missing_facts)


# ---------------------------------------------------------------------------
# Gap register
# ---------------------------------------------------------------------------

def _corpus():
    c = Corpus()
    c.kb_docs["eu_gdpr_2016_679"] = [{"chunk_id": "gdpr:p52:1", "doc_id": "eu_gdpr_2016_679",
                                      "source_title": "Regulation (EU) 2016/679 (GDPR)", "section": "p. 52",
                                      "page": "52", "excerpt": "… without undue delay and, where feasible, not later "
                                                               "than 72 hours after having become aware of it …"}]
    c.index_docs["rules.pdf"] = [{"doc": "rules.pdf", "page_start": 3, "page_end": 3,
                                  "text": "report within six hours of becoming aware of a security incident"}]
    return c


def test_anchor_statuses():
    c = _corpus()
    assert check_anchor({"cite_as": "R7", "index_doc": "rules.pdf",
                         "phrase": "within six hours of becoming aware"}, c, False)["status"] == VERIFIED
    hit = check_anchor({"cite_as": "GDPR 33", "title_contains": ["GDPR"], "jurisdiction": "European Union",
                        "phrase": "not later than 72 hours after having become aware of it"}, c, True)
    assert hit["status"] == VERIFIED and hit["corpus"] == "knowledge_base" and hit["region"] == "europe"
    assert hit["page"] == "52" and "72 hours" in hit["passage"]
    assert check_anchor({"cite_as": "x", "index_doc": "rules.pdf", "phrase": "twelve hours"},
                        c, False)["status"] == NOT_FOUND
    assert check_anchor({"cite_as": "y", "source": "absent", "phrase": "z"}, c, True)["status"] == PENDING
    assert check_anchor({"cite_as": "z", "phrase": None}, c, True)["status"] == LISTED


def test_theme_file_is_validated(tmp_path):
    bad = {"themes": [{"id": "G1", "domain": "d", "theme": "t", "category": "nonsense", "why_it_matters": "w",
                       "coordination_problem": "c", "indian_anchors": [], "global_examples": []}]}
    path = tmp_path / "t.yaml"
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(RegisterError, match="unknown category"):
        build(path, Corpus())
    bad["themes"][0]["category"] = "overlapping_requirements"
    bad["themes"][0]["indian_anchors"] = [{"cite_as": "x", "phrase": "y"}]
    path.write_text(yaml.safe_dump(bad), encoding="utf-8")
    with pytest.raises(RegisterError, match="names no document"):
        build(path, Corpus())


@pytest.mark.skipif(not INDEX_BUILT, reason="kb/index not present")
def test_committed_themes_against_the_committed_index():
    reg = build()
    themes = {t["id"]: t for t in reg["themes"]}
    assert set(themes) == {"G1", "G2", "G3", "G4", "G5"}
    g1 = themes["G1"]
    assert all(a["status"] == VERIFIED for a in g1["indian_provisions"])
    assert {a["region"] for a in g1["global_examples"]} == {"europe"}
    for t in reg["themes"]:
        assert t["status"].endswith("potential gap")
        for a in t["indian_provisions"]:
            if a["status"] == VERIFIED:
                assert a["passage"] and a["page"]
    md = render_markdown(reg)
    assert "Potential gaps and regulatory ambiguities" in md and "## G1" in md
    for word in ("inadequate", "failure of policy", "fails to"):
        assert word not in md.lower().replace("no conclusion of policy failure", "")


@pytest.mark.skipif(not INDEX_BUILT, reason="kb/index not present")
def test_register_cli_writes_both_files(tmp_path):
    out = tmp_path / "reg.json"
    assert main(["--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["themes"]
    assert out.with_suffix(".md").read_text(encoding="utf-8").startswith("# Policy-gap register")


def test_committed_register_matches_the_theme_file():
    reg = json.loads((ROOT / "knowledge_base" / "gap_register.json").read_text(encoding="utf-8"))
    themes = yaml.safe_load((ROOT / "knowledge_base" / "policy_gap" / "gap_themes.yaml").read_text(encoding="utf-8"))
    assert [t["id"] for t in reg["themes"]] == [t["id"] for t in themes["themes"]]


# ---------------------------------------------------------------------------
# UI pages
# ---------------------------------------------------------------------------

def test_ui_pipeline_and_gap_pages_render():
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "src" / "ui" / "app.py"), default_timeout=120).run()
    at.sidebar.radio[0].set_value("Y.3172 pipeline").run()
    assert not at.exception
    if (ROOT / "outputs" / "y3172" / "examples").exists():
        assert "Attacks detected within deadline" in [m.label for m in at.metric]
    at.sidebar.radio[0].set_value("Gap register").run()
    assert not at.exception and len(at.expander) == 5
