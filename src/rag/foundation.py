"""
Knowledge-foundation artefacts (DOCX §5.1, §5.2, §4.3, §7.2, §7.3)
====================================================================
    python -m src.rag.foundation [--run outputs/audit/<run>.jsonl]

Generates, from the curated source manifest, the ingestion manifest, the
built vector stores, a recorded scenario run and the DOCX tables:

  knowledge_base/source_manifest.json              §7.2 final KB manifest (per document)
  knowledge_base/canonical/canonical_metadata.json §7.2 Canonical KB metadata
  knowledge_base/host_country_corpus.json          §7.3 host-country corpus categories
  knowledge_base/policy_gap/policy_gap_categories.json  §5.1 coverage categories
  knowledge_base/y3172_pipeline_traceability.json  §4.3 Y.3172 pipeline trace
  knowledge_base/itu_ai_readiness_mapping.json     §5.2 readiness perspectives

Nothing is typed in by hand that the data can supply.  Titles, authorities,
dates, URLs, hashes and chunk counts are copied from the manifests; every
quotation is located in a stored passage and the build fails if it is not
found; every project file cited must exist; examples come from the recorded
run, whose hash chain must be intact.  DOCX wording is reproduced verbatim
and labelled as such.  Values that were not obtained are written as such
("not verified", "not checked", "not stated in the document", null) — never
guessed.  No readiness score, maturity level or compliance claim is made.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from src.rag.manifest import ALL_KBS, CANONICAL_KB, KB_ROOT, MANIFEST_PATH

ROOT = KB_ROOT.parent
INGESTION = KB_ROOT / "ingestion_manifest.json"
DEFAULT_RUN = ROOT / "outputs" / "audit" / "day2_scenario2_full_T0_T3.jsonl"
SCHEMA_VERSION = "2.0"
GENERATOR = "python -m src.rag.foundation"

NOT_STATED = "not stated in the document"


class FoundationError(RuntimeError):
    """A claim in an artefact could not be backed by the data."""


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------

def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _flat(text: str) -> str:
    return " ".join(text.split())


class Corpus:
    """The manifests and every stored passage, read once."""

    def __init__(self) -> None:
        self.manifest = _json(MANIFEST_PATH)
        self.docs = {d["id"]: d for d in self.manifest["documents"]}
        self.ingestion = _json(INGESTION)
        self.ingested = {d["id"]: d for d in self.ingestion["documents"]}
        self.chunks: dict[str, list[dict]] = {}
        self.kb_of_chunk: dict[str, set[str]] = {}
        for kb in ALL_KBS:
            path = KB_ROOT / kb / "chunks.jsonl"
            if not path.exists():
                raise FoundationError(f"{path} missing — run python -m src.rag.build first")
            rows = [json.loads(line) for line in path.open(encoding="utf-8")]
            self.chunks[kb] = rows
            for r in rows:
                self.kb_of_chunk.setdefault(r["chunk_id"], set()).add(kb)
        self.by_doc: dict[str, list[dict]] = {}
        seen = set()
        for rows in self.chunks.values():
            for r in rows:
                if r["chunk_id"] not in seen:
                    seen.add(r["chunk_id"])
                    self.by_doc.setdefault(r["doc_id"], []).append(r)

    def passage(self, doc_id: str, section: str, phrase: str, width: int = 160) -> dict:
        """A stored passage of `doc_id`/`section` containing `phrase`, quoted."""
        for r in self.by_doc.get(doc_id, []):
            if r["section"] != section:
                continue
            text = _flat(r["excerpt"])
            i = text.lower().find(phrase.lower())
            if i >= 0:
                start, end = max(0, i - width), min(len(text), i + len(phrase) + width)
                return {
                    "source_id": doc_id,
                    "source_title": r["source_title"],
                    "authority": r["authority"],
                    "jurisdiction": r["jurisdiction"],
                    "document_type": r["document_type"],
                    "section": r["section"],
                    "section_title": r["section_title"],
                    "page": r["page"],
                    "chunk_id": r["chunk_id"],
                    "knowledge_bases": sorted(self.kb_of_chunk[r["chunk_id"]]),
                    "quote": ("…" if start else "") + text[start:end] + ("…" if end < len(text) else ""),
                }
        raise FoundationError(f"phrase {phrase!r} not found in {doc_id} {section}")

    def find(self, doc_id: str, phrase: str, width: int = 160) -> dict:
        """The first stored passage of `doc_id` (any section) containing `phrase`, quoted."""
        for r in self.by_doc.get(doc_id, []):
            if phrase.lower() in _flat(r["excerpt"]).lower():
                return self.passage(doc_id, r["section"], phrase, width)
        raise FoundationError(f"phrase {phrase!r} not found in {doc_id}")

    def licence_statement(self, doc_id: str) -> Optional[str]:
        """The document's own licence/copyright statement, verbatim, if it has one."""
        pattern = re.compile(
            r"(©[^.]{0,120}(?:All rights reserved)?\.?"
            r"|\b[A-Z][A-Za-z\-]{1,20} \d{4} All rights reserved\.[^.]{0,160}\."
            r"|Copyright Notification[^.]{0,220}\."
            r"|This publication is available free of charge from:?\s*\S+)", re.I)
        for r in self.by_doc.get(doc_id, []):
            m = pattern.search(_flat(r["excerpt"]))
            if m:
                return m.group(0).strip()
        return None


def _file(rel: str) -> str:
    """A project file cited as evidence must exist."""
    if not (ROOT / rel).exists():
        raise FoundationError(f"cited project file does not exist: {rel}")
    return rel


def _read_run(path: Path) -> dict:
    from src.audit.replay import load_run
    run = load_run(path)
    if not run.intact:
        raise FoundationError(f"{path}: audit hash chain broken: {run.integrity_problems}")
    if not run.stages:
        raise FoundationError(f"{path}: no recorded stages")
    return {"path": path.relative_to(ROOT).as_posix(), "header": run.header,
            "stages": run.stages}


def _header(about: list[str], docx: str) -> dict:
    return {"_about": about, "schema_version": SCHEMA_VERSION, "docx_section": docx,
            "generated_by": GENERATOR}


# ---------------------------------------------------------------------------
# §7.2 Source manifest — every document, ingested or not
# ---------------------------------------------------------------------------

def source_manifest(c: Corpus) -> dict:
    ing = c.ingestion
    documents = []
    for doc_id, d in c.docs.items():
        rep = c.ingested.get(doc_id, {})
        ingested = rep.get("status") == "ingested"
        rows = c.by_doc.get(doc_id, [])
        sections = Counter(r["section"] for r in rows)
        licence = c.licence_statement(doc_id) if ingested else None
        documents.append({
            "id": doc_id,
            "title": d["title"],
            "authority": d.get("authority") or NOT_STATED,
            "jurisdiction": d.get("jurisdiction") or NOT_STATED,
            "document_type": d.get("document_type") or NOT_STATED,
            "date_issued": rep.get("date_issued") or None,
            "date_verified_in_text": rep.get("date_verified_in_text", False),
            "effective_status": d.get("effective_status", "not verified"),
            "amendment_status": d.get("amendment_status", "not checked"),
            "section_information": {
                "section_style": d.get("section_style"),
                "section_label": d.get("section_label"),
                "sections_ingested": len(sections),
                "sections_labelled_by_page_only": sum(s.startswith("p. ") for s in sections),
                "unmatched_pdf_bookmarks": rep.get("unmatched_bookmarks", []),
            } if ingested else None,
            "url": d.get("source_url") or None,
            "attempted_urls": d.get("attempted_urls", []),
            "provenance_note": d.get("provenance_note", ""),
            "licence": {
                "statement_in_document": licence,
                "note": ("Quoted from the document text." if licence else
                         "No licence or copyright statement was found in the ingested text "
                         "(front matter may not have been ingested); licence not determined."),
                "open_access": (f"Downloaded without login from the URL above "
                                f"(retrieved {c.manifest.get('retrieved_on')})."
                                if ingested else None),
            },
            "status": rep.get("status", d.get("status")),
            "sha256": rep.get("sha256") if ingested else None,
            "chunk_count": rep.get("chunks", 0) if ingested else 0,
            "chunk_id_prefix": f"{doc_id}:" if ingested else None,
            "vector_index": {
                kb: {"store": f"knowledge_base/{kb}/",
                     "vectors": f"knowledge_base/{kb}/vectors.npy",
                     "passages": sum(1 for r in c.chunks[kb] if r["doc_id"] == doc_id)}
                for kb in d.get("kbs", []) if ingested
            },
            "status_established_by": {
                "in_force": rep.get("in_force_applied", []),
                "amendments": rep.get("amended_by_applied", []),
            } if ingested and (rep.get("in_force_applied") or rep.get("amended_by_applied")) else None,
            "knowledge_bases": d.get("kbs", []),
            "kb_basis": d.get("kb_basis", ""),
            "embedding_model": ing["embedding_model"] if ingested else None,
            "generator_model": ing["generator_model"],
        })
    return {
        **_header([
            "Final KB manifest (DOCX §7.2: title, authority, jurisdiction, document type,",
            "date/effective status, section, amendment status, URL, licence/open-access",
            "status, chunk count, vector index and model names). Generated from",
            "knowledge_base/sources/manifest.json, ingestion_manifest.json and the stores.",
        ], "§7.2"),
        "retrieved_on": c.manifest.get("retrieved_on"),
        "built_at": ing["built_at"],
        "embedding_model": ing["embedding_model"],
        "embedding_dimension": _json(KB_ROOT / CANONICAL_KB / "index.json").get("dimension"),
        "generator_model": ing["generator_model"],
        "vector_store": ing["vector_store"],
        "chunking": ing["chunking"],
        "sandbox": ing["sandbox"],
        "knowledge_bases": {kb: {"passages": len(c.chunks[kb]),
                                 "documents": sorted({r["doc_id"] for r in c.chunks[kb]})}
                            for kb in ALL_KBS},
        "documents": documents,
    }


# ---------------------------------------------------------------------------
# §7.2 Canonical KB metadata
# ---------------------------------------------------------------------------

def canonical_metadata(c: Corpus, manifest: dict) -> dict:
    canonical_docs = {r["doc_id"] for r in c.chunks[CANONICAL_KB]}
    documents = []
    for m in manifest["documents"]:
        d = c.docs[m["id"]]
        in_canonical = m["id"] in canonical_docs
        documents.append({
            "id": m["id"],
            "source_title": m["title"],
            "in_canonical_kb": in_canonical,
            # DOCX §7.2 metadata fields
            "source_and_authority": {"authority": m["authority"], "url": m["url"],
                                     "provenance_note": m["provenance_note"]},
            "jurisdiction": m["jurisdiction"],
            "document_type": m["document_type"],
            "date_issued": m["date_issued"],
            "date_evidence": d.get("date_evidence") if m["date_verified_in_text"] else None,
            "effective_status": m["effective_status"],
            "section": m["section_information"],
            "amendment": {"status": m["amendment_status"],
                          "passages_with_amendment_note": sum(
                              1 for r in c.by_doc.get(m["id"], []) if r.get("amendment_note"))},
            "passages_in_force": sum(1 for r in c.by_doc.get(m["id"], []) if r.get("effective")),
            "related_documents": d.get("related_documents", []),
            "institutions": d.get("institutions", []),
            "domains": d.get("domains", []),
            # build record
            "chunks": c.ingested.get(m["id"], {}).get("chunks", 0) if m["sha256"] else 0,
            "canonical_passages": m["vector_index"].get(CANONICAL_KB, {}).get("passages", 0),
            "sha256": m["sha256"],
            "provenance_note": m["provenance_note"],
        })
    return {
        **_header([
            "Canonical KB metadata (DOCX §7.2). The Canonical KB is the verification-only",
            "corpus beneath every agent KB; each passage carries these fields.",
        ], "§7.2"),
        "notes": {
            "effective_status": "Established only where an obtained document states it: the two "
                                "commencement notifications for the Telecommunications Act (sections "
                                "they name) and the commencement clauses of the TCS Rules, CTI Rules, "
                                "TCS Amendment Rules and Right of Way Rules. Every other passage has "
                                "effective=null (not verified).",
            "amendment_status": "Amendment notes are recorded where an obtained amendment names the "
                                "provision (TCS Rules rules 2, 3, 4, 5, 8, 10 by G.S.R. 771(E)). No "
                                "passage claims a complete amendment check (amendment_checked=false "
                                "everywhere), so the Verifier cannot return VERIFIED for real sources.",
            "fabrication_policy": "No metadata value is invented. Values not obtained are "
                                  "'not verified', 'not checked', 'not stated in the document' "
                                  "or null. Generated by " + GENERATOR + ".",
            "agent_kbs_beneath_canonical": all(
                {r["doc_id"] for r in c.chunks[kb]} <= canonical_docs for kb in ALL_KBS),
        },
        "documents": documents,
    }


# ---------------------------------------------------------------------------
# §7.3 Host-country corpus
# ---------------------------------------------------------------------------

# DOCX §7.3 table, verbatim: (corpus category, material covered, KB assignment)
_HOST_CATEGORIES = [
    ("Laws and regulations",
     "Telecommunications, cyber incident response, data protection, critical infrastructure",
     "Policy & Legal; Cybersecurity; Privacy; Critical Infrastructure; Canonical"),
    ("National AI strategy and AI mission",
     "National AI strategy/IndiaAI mission and responsible-AI policy context",
     "Policy Gap; Policy & Legal; Canonical"),
    ("Digital and cybersecurity strategies",
     "National digital communications and cybersecurity strategy/policy material",
     "Policy & Legal; Cybersecurity; Policy Gap"),
    ("Institutional mandates",
     "DoT, TRAI, CERT-In, NCIIPC and other relevant institutional mandates",
     "Policy & Legal; Cybersecurity; Critical Infrastructure"),
    ("Economic and industrial characteristics",
     "Telecom/5G industry and infrastructure context relevant to the incident domain",
     "Policy Gap; Technical"),
    ("Labour-market conditions",
     "Workforce and skills context relevant to AI/telecom deployment and supervision",
     "Policy Gap"),
    ("Intellectual property",
     "IP rules relevant to software, models, datasets and technology deployment",
     "Policy Gap; Policy & Legal"),
    ("Multilateral and treaty obligations",
     "Relevant international obligations used as policy context",
     "Policy Gap; Standards; Canonical"),
    ("Energy and infrastructure constraints",
     "Digital infrastructure, energy and deployment constraints relevant to 5G/AI systems",
     "Technical; Policy Gap"),
    ("Regional and global comparators",
     "Neighbouring-country and selected global policy instruments used for domain comparison",
     "Policy Gap"),
]

# Which obtained documents fall in which category, and why; unavailable ones.
_HOST_SOURCES = {
    "Laws and regulations": (
        ["telecom_act_2023", "telecom_act_commencement_so2408e_2024",
         "telecom_act_commencement_so2623e_2024", "trai_act_1997",
         "telecom_cyber_security_rules_2024", "tcs_amendment_rules_2025", "cti_rules_2024",
         "certin_directions_2022", "dpdp_act_2023", "dpdp_rules_2025"],
        ["nciipc_rules_2013"]),
    "National AI strategy and AI mission": (["niti_nsai_2018", "trai_ai_bigdata_recs_2023"], []),
    "Digital and cybersecurity strategies": (["ndcp_2018", "ncsp_2013"], []),
    "Institutional mandates": (
        ["telecom_act_2023", "trai_act_1997", "certin_directions_2022", "ncsp_2013", "cti_rules_2024"],
        ["nciipc_rules_2013"]),
    "Labour-market conditions": (["niti_nsai_2018"], []),
    "Intellectual property": (["niti_nsai_2018"], []),
    "Energy and infrastructure constraints": (["telecom_row_rules_2024"], []),
    "Regional and global comparators": (
        ["enisa_5g_security_controls_matrix", "enisa_5g_cybersecurity_standards_2022"],
        ["international_policy_examples"]),
}

# Passages showing why an obtained document bears on a category
_CATEGORY_EVIDENCE = {
    "Labour-market conditions": [("niti_nsai_2018", "skilling and reskilling of workforce")],
    "Intellectual property": [("niti_nsai_2018", "intellectual property framework is required")],
    "Energy and infrastructure constraints": [("telecom_row_rules_2024", "right of way")],
    "Regional and global comparators": [("enisa_5g_security_controls_matrix", "5G Cybersecurity toolbox"),
                                        ("enisa_5g_cybersecurity_standards_2022", "cybersecurity policy")],
    "National AI strategy and AI mission": [("niti_nsai_2018", "#AIforAll")],
}

# Passages showing the mandate each institution has in the obtained text
_MANDATE_EVIDENCE = [
    ("DoT / Central Government", "telecom_act_2023", "Section 3", "shall obtain an authorisation from the Central Government"),
    ("TRAI", "trai_act_1997", "Section 11", "Functions of Authority"),
    ("CERT-In", "certin_directions_2022", "Direction (ii)", "report cyber incidents"),
    ("NCIIPC", "ncsp_2013", "Part III item 5", "NCIIPC"),
]

_HOST_STATUS = {
    "Laws and regulations": "PARTIAL — the IT (NCIIPC) Rules, 2013 could not be obtained",
    "National AI strategy and AI mission": (
        "PARTIAL — NITI Aayog's National Strategy for AI and the TRAI Recommendations on AI and Big "
        "Data were obtained (neither is law); no IndiaAI Mission document was obtained"),
    "Labour-market conditions": (
        "PARTIAL — strategy-level discussion of AI skilling in NITI Aayog's National Strategy for AI; "
        "no labour-market data source was obtained"),
    "Intellectual property": (
        "PARTIAL — NITI Aayog's National Strategy for AI discusses an IP framework for AI; no IP "
        "legislation was obtained"),
    "Energy and infrastructure constraints": (
        "PARTIAL — the Telecommunications (Right of Way) Rules, 2024 cover infrastructure deployment; "
        "no energy source was obtained"),
    "Regional and global comparators": (
        "PARTIAL — two EU (ENISA) policy documents were obtained as international examples; no "
        "neighbouring-country instrument was obtained"),
    "Digital and cybersecurity strategies": (
        "COVERED by the instruments the DOCX names (NDCP-2018, NCSP-2013)"),
    "Institutional mandates": (
        "PARTIAL — DoT, TRAI and CERT-In mandates are in the obtained text; NCIIPC appears only "
        "in NCSP-2013 because the NCIIPC Rules could not be obtained"),
}


def host_country_corpus(c: Corpus, manifest: dict) -> dict:
    by_id = {m["id"]: m for m in manifest["documents"]}
    categories = []
    for i, (heading, material, kbs) in enumerate(_HOST_CATEGORIES, 1):
        ingested_ids, missing_ids = _HOST_SOURCES.get(heading, ([], []))
        entry = {
            "category_id": i,
            "docx_heading": heading,
            "docx_material_covered": material,
            "docx_kb_assignment": kbs,
            "coverage_status": _HOST_STATUS.get(
                heading, "NOT COVERED — no source for this category was obtained or ingested"),
            "sources_ingested": [{
                "id": s, "title": by_id[s]["title"], "authority": by_id[s]["authority"],
                "document_type": by_id[s]["document_type"], "date_issued": by_id[s]["date_issued"],
                "effective_status": by_id[s]["effective_status"],
                "chunks": by_id[s]["chunk_count"], "kbs": by_id[s]["knowledge_bases"],
                "url": by_id[s]["url"],
            } for s in ingested_ids],
            "sources_unavailable": [{
                "id": s, "title": by_id[s]["title"], "reason": by_id[s]["provenance_note"],
            } for s in missing_ids],
        }
        if heading in _CATEGORY_EVIDENCE:
            entry["category_evidence"] = [c.find(doc, phrase) for doc, phrase in _CATEGORY_EVIDENCE[heading]]
        if heading == "Institutional mandates":
            entry["mandate_evidence"] = [
                {"institution": inst, **c.passage(doc, sec, phrase)}
                for inst, doc, sec, phrase in _MANDATE_EVIDENCE]
        categories.append(entry)
    not_covered = [x["docx_heading"] for x in categories if x["coverage_status"].startswith("NOT COVERED")]
    return {
        **_header([
            "Host-country corpus (DOCX §7.3). Categories, material and KB assignment are the",
            "DOCX table verbatim; sources and counts come from the manifests. A category is",
            "NOT COVERED when no source for it was obtained — that records the state of this",
            "corpus, not the absence of Indian law or policy in the area.",
        ], "§7.3"),
        "categories": categories,
        "corpus_summary": {
            "categories_total": len(categories),
            "categories_covered": [x["docx_heading"] for x in categories if x["coverage_status"].startswith("COVERED")],
            "categories_partial": [x["docx_heading"] for x in categories if x["coverage_status"].startswith("PARTIAL")],
            "categories_not_covered": not_covered,
            "documents_ingested": sum(1 for m in manifest["documents"] if m["sha256"]),
            "documents_not_ingested": [m["id"] for m in manifest["documents"] if not m["sha256"]],
        },
    }


# ---------------------------------------------------------------------------
# §5.1 Policy Gap KB — six coverage categories
# ---------------------------------------------------------------------------

def policy_gap_categories(c: Corpus, run: dict) -> dict:
    from src.agents.policy_gap_agent import PolicyGapAgent, _CATEGORY_LABEL
    from src.core.models import CoverageCategory

    # DOCX §5.1 "Coverage category / Meaning", verbatim
    meaning = {
        CoverageCategory.EXPLICIT_COVERAGE: "A provision clearly addresses the situation.",
        CoverageCategory.PARTIAL_COVERAGE: "A provision addresses part of the situation.",
        CoverageCategory.UNCLEAR_COVERAGE: "It is uncertain whether any provision applies.",
        CoverageCategory.OVERLAPPING_REQUIREMENTS: "Several provisions apply and their relationship is unclear.",
        CoverageCategory.MISSING_INSTITUTIONAL_CLARITY: "It is unclear which institution is responsible.",
        CoverageCategory.EMERGING_TECHNOLOGY: "The technology or scenario is not named in the framework.",
    }
    method = {
        CoverageCategory.EXPLICIT_COVERAGE: {
            "examined_by_agent": "only as a coverage check",
            "how": "When an examination finds Indian passages that address the area, the agent "
                   "records a 'Coverage check' citing them and raises no gap. It does not decide "
                   "between explicit and partial coverage; that is left for expert review."},
        CoverageCategory.PARTIAL_COVERAGE: {
            "examined_by_agent": "only as a coverage check",
            "how": "As for explicit coverage: the agent cites the passages found and leaves "
                   "explicit-versus-partial to expert review."},
        CoverageCategory.UNCLEAR_COVERAGE: {
            "examined_by_agent": "no",
            "how": "No examination in the current agent produces this category."},
        CoverageCategory.OVERLAPPING_REQUIREMENTS: {
            "examined_by_agent": "yes",
            "trigger": "cyber_event_suspected and data_exposure_suspected in the incident state",
            "how": "Retrieves Indian reporting passages for a cybersecurity instrument and a "
                   "data-protection instrument from the Canonical KB and checks whether either "
                   "refers to the other; a potential gap only if neither does."},
        CoverageCategory.MISSING_INSTITUTIONAL_CLARITY: {
            "examined_by_agent": "yes",
            "trigger": "cyber_event_suspected and cii_flagged in the incident state",
            "how": "Exhaustive scan of every Indian Canonical KB passage for NCIIPC and CERT-In; "
                   "a potential gap only if passages name each but none names both."},
        CoverageCategory.EMERGING_TECHNOLOGY: {
            "examined_by_agent": "yes",
            "trigger": "a verified finding mentions a network slice",
            "how": "Exhaustive scan of every Indian Canonical KB passage for network slicing "
                   "(CanonicalKnowledgeBase.scan, not a top-k sample); a potential gap only if "
                   "no passage names it."},
    }
    final = run["stages"][-1]
    gap_agent = next((a for a in final["agents"] if a["agent_id"] == "policy_gap"), None)
    observed = [] if gap_agent is None else [
        {"claim": cl["claim"], "verifier_outcome": cl["verifier_outcome"],
         "citations": cl["citations"]} for cl in gap_agent["claims"]]

    categories = []
    for i, cat in enumerate(CoverageCategory, 1):
        label = _CATEGORY_LABEL[cat]
        examples = [o for o in observed if f"— {label}:" in o["claim"]]
        entry = {
            "category_id": i,
            "name": label,
            "enum_value": cat.value,
            "docx_reference": "DOCX §5.1 coverage category table",
            "docx_meaning": meaning[cat],
            "examination_method": method[cat],
            "outcome_label": f"Potential gap — {label}" if method[cat]["examined_by_agent"] == "yes"
                             else "Coverage check (no gap raised)" if "coverage check" in method[cat]["examined_by_agent"]
                             else None,
            "verifier_outcome": "At most INCOMPLETE — a potential gap is for expert review, never a verified conclusion",
            "observed_in_recorded_run": examples,
        }
        if cat == CoverageCategory.OVERLAPPING_REQUIREMENTS and examples:
            cites = examples[0]["citations"]
            entry["concrete_scenario_2_example"] = {
                "instrument_a": f"{cites[0]['source_title']}, {cites[0]['section']}",
                "instrument_b": f"{cites[1]['source_title']}, {cites[1]['section']}",
                "from_run": run["path"],
            }
        categories.append(entry)

    kb_docs = sorted({r["doc_id"] for r in c.chunks["policy_gap"]})
    return {
        **_header([
            "Policy Gap KB (DOCX §5.1 coverage categories; §7.1 Policy Gap KB). Category",
            "meanings are the DOCX table verbatim; methods describe src/agents/policy_gap_agent.py;",
            "examples are the agent's actual output in the recorded run.",
        ], "§5.1"),
        "agent": "Policy Gap Agent",
        "agent_module": _file("src/agents/policy_gap_agent.py"),
        "enum_class": "src.core.models.CoverageCategory",
        "knowledge_base": {
            "documents": [{"id": d, "title": c.docs[d]["title"],
                           "document_type": c.docs[d]["document_type"]} for d in kb_docs],
            "passages": len(c.chunks["policy_gap"]),
            "read_only_inputs": ["verified findings of the other agents",
                                 "International Standards KB", "Canonical KB"],
            "international_policy_examples": (
                "PARTIAL — two EU (ENISA) policy documents are ingested and used as comparators "
                "(labelled 'not Indian law'); the DOCX names no specific foreign instrument and no "
                "neighbouring-country instrument was obtained."),
        },
        "non_conclusive_language_rule": {
            "required_disclaimer": PolicyGapAgent.GAP_DISCLAIMER,
            "forbidden_phrases": ["Indian policy is inadequate", "the policy is inadequate",
                                  "framework is inadequate", "there is no law"],
            "docx_basis": "DOCX §5.1: 'The system identifies potential gaps and ambiguities; it "
                          "does not conclude that any Indian policy is inadequate.'",
        },
        "distinction_potential_gap_vs_law_does_not_exist": {
            "rule": "A potential gap states what the examined corpus does or does not say, and "
                    "names the instruments examined. It is never stated as 'the law does not "
                    "exist': the corpus is finite (the NCIIPC Rules and international examples "
                    "are not ingested), so absence from the corpus is not absence from Indian law.",
            "example_correct": next((o["claim"] for o in observed if o["claim"].startswith("Potential gap")),
                                    None),
            "example_incorrect": "There is no Indian law on network slicing.",
        },
        "categories": categories,
        "recorded_run": run["path"],
    }


# ---------------------------------------------------------------------------
# §4.3 Y.3172 pipeline traceability
# ---------------------------------------------------------------------------

_Y3172 = "itu_t_y3172"

# Y.3172 is an architecture for ML inside networks: its nodes read network
# data (UE, AN, CN functions) and push configuration back to the network.
# The project has two pipelines.  The adviser's document pipeline (the seven
# stages below, DOCX §4.3) corresponds to the Y.3172 nodes mostly by
# analogy; each stage states how it corresponds and how it differs.  The
# network ML pipeline (src/y3172/) implements the Y.3172 components over the
# contained simulated 5G core, with the adviser as its policy (P) node; it is
# listed under network_ml_pipeline.  What neither provides is listed under
# components_not_implemented.  Clause and NOTE numbers refer to Y.3172.
_Y3172_SCOPE_NOTE = (
    "ITU-T Y.3172 specifies an architecture for machine learning in networks: ML pipeline nodes "
    "read data from network functions (UE, access and core network) and apply ML output to "
    "network targets, managed by an ML function orchestrator (MLFO) from a declarative ML "
    "Intent. The project has two pipelines. (1) The policy and legal adviser's document pipeline, "
    "mapped stage by stage below: only preprocessing corresponds directly, the other stages by "
    "analogy. (2) The network ML pipeline in src/y3172/ (network_ml_pipeline below): an ML Intent, "
    "SRC/C/PP/M/P/D/SINK nodes, an MLFO and an ML sandbox, run over the contained simulated 5G core "
    "in sim/, with the adviser as its P node. The network is a simulation; what is simulated or only "
    "logical is listed under components_not_implemented."
)
_Y3172_DISCLAIMER = (
    "Architectural correspondence only. The document pipeline corresponds mostly by analogy (see "
    "correspondence per stage); the network ML pipeline implements the Y.3172 components over a "
    "simulated network, not a live one. Formal Y.3172 compliance has not been assessed and is not "
    "claimed."
)
_Y3172_CORRESPONDENCE = {
    "Source": ("analogy",
               "Y.3172 SRC nodes are network data sources such as UE, SMF or AF (clause 8.1, NOTE 2); "
               "here the sources are legal and standards documents. Network SRC nodes: see "
               "network_ml_pipeline."),
    "Collection": ("analogy",
                   "A Y.3172 collector may also configure its SRC nodes, e.g. via RRC or OAM "
                   "(clause 8.1, NOTE 3); document extraction configures nothing."),
    "Preprocessing": ("direct",
                      "Cleans and segments the collected data into the form the model consumes, as "
                      "clause 8.1 describes for PP."),
    "Model": ("analogy",
              "The embedding model only ranks passages for retrieval; it is not trained here and "
              "makes no prediction about a network. Agent selection (src/core/orchestrator.py) uses "
              "keyword rules and claim support (src/core/verifier.py) is a lexical term-coverage "
              "check, so neither decision is made by the model. The trained network models are in "
              "network_ml_pipeline."),
    "Policy": ("analogy",
               "The Y.3172 P node applies operator policies to model output to limit its impact "
               "before it is applied to a live network (clause 8.1, NOTE 5); in this pipeline the "
               "Verifier applies evidence rules to the agents' claims. In the network ML pipeline the "
               "whole adviser is the P node and does gate model output (network_ml_pipeline)."),
    "Distribution": ("analogy",
                     "The Y.3172 D node identifies SINK nodes and distributes the model output to "
                     "them (clause 8.1, NOTE 6); in this pipeline the output goes to a human reader "
                     "through the Coordinator, the audit trail and the UI. The network ML pipeline has "
                     "a D node and SINKs (network_ml_pipeline)."),
    "Sandbox": ("not implemented",
                "This document pipeline has no ML sandbox. The network ML pipeline has one: simulated "
                "underlay networks in which candidate models are trained, tested and their remediation "
                "effects evaluated (network_ml_pipeline)."),
}
_Y3172_NETWORK_PIPELINE = [
    {"component": "ML Intent", "y3172_reference": "Clauses 7.4, 8.1 (NOTE 12)",
     "implementation": "Declarative YAML: target incident classes, SRC nodes and their levels, candidate "
                       "models and selection rule, policy-node mode, SINKs, time constraints, "
                       "monitoring; validated on load.",
     "files": ["src/y3172/intent.py", "intents/amf_signalling_storm.yaml"]},
    {"component": "SRC, C, PP", "y3172_reference": "Clause 8.1",
     "implementation": "Simulated network functions as sources; the collector reads them only through "
                       "read-only diagnostics; the preprocessor builds a fixed-length feature vector "
                       "and its change since the previous poll.",
     "files": ["src/y3172/nodes.py", "sim/engine.py"]},
    {"component": "M (model)", "y3172_reference": "Clause 8.1",
     "implementation": "Two candidates trained in the sandbox: a z-score threshold / nearest-centroid "
                       "baseline and an IsolationForest + RandomForest model; each returns a class, "
                       "confidence, the deviating signals and the catalog remediation proposal.",
     "files": ["src/y3172/models.py"]},
    {"component": "P (policy)", "y3172_reference": "Clause 8.1 (NOTE 5)",
     "implementation": "Operator rules (unknown, low-confidence or out-of-intent detections go to a "
                       "human), the attack's Indian obligations checked word for word in their "
                       "sources, the specialist-agent swarm, and an advisory or blocking mode.",
     "files": ["src/y3172/policy_node.py"]},
    {"component": "D (distributor) and SINKs", "y3172_reference": "Clause 8.1",
     "implementation": "Evidence preservation (hashed) before any change, remediation through the "
                       "incident-response engine and its human gates, draft regulatory notices with "
                       "verified deadlines, escalation to a human.",
     "files": ["src/y3172/distributor.py", "src/y3172/notices.py", "ir/engine.py"]},
    {"component": "MLFO", "y3172_reference": "Clauses 3.2.2, 8.1, 8.2",
     "implementation": "Instantiates and places the nodes from the intent, trains and selects a model "
                       "in the sandbox, deploys it, monitors live performance and re-selects after "
                       "re-calibrating the sandbox; every decision in a hash-chained audit trail.",
     "files": ["src/y3172/mlfo.py", "src/audit/trail.py"]},
    {"component": "ML sandbox and simulated ML underlay networks", "y3172_reference": "Clauses 3.2.6, 8.2",
     "implementation": "Seeded simulations with background load, benign look-alikes, attack intensity "
                       "and post-remediation states generate labelled data; each playbook's effect is "
                       "evaluated in a sandbox simulation before live use.",
     "files": ["sim/datagen.py", "src/y3172/mlfo.py"]},
]
_Y3172_NOT_IMPLEMENTED = [
    {"component": "ML underlay network (live)", "y3172_reference": "Clauses 3.2.7, 8.1",
     "y3172_role": "The operator network whose functions provide data to, and receive output from, "
                   "the ML pipeline.",
     "project_status": "Simulated. The 'live' network of the network ML pipeline is a separate "
                       "instance of the contained simulator; no real network is read or changed.",
     "files": ["sim/engine.py"]},
    {"component": "Reference points 1-9 and service-based interfaces", "y3172_reference": "Clauses 8.1, 8.2",
     "y3172_role": "Interfaces between the ML pipeline, sandbox and management subsystems, the "
                   "underlay networks, and pipeline nodes on different levels.",
     "project_status": "Logical only. The network ML pipeline names the reference points it uses, but "
                       "its components call each other in one Python process, not over SBA."},
    {"component": "Multilevel distribution of pipeline nodes", "y3172_reference": "Clause 8.2; REQ-ML-COR-003",
     "y3172_role": "Pipeline nodes instantiated at different levels (e.g. UE, AN, CN).",
     "project_status": "Logical only. The intent places each node on a level and the MLFO records the "
                       "placement, but every node runs in a single process."},
    {"component": "Standardised intent metalanguage", "y3172_reference": "Clause 7.4 (REQ-ML-SPEC-001), 8.1 (NOTE 12)",
     "y3172_role": "A standard way to represent ML applications that third parties can also use.",
     "project_status": "Project-specific. The ML Intent is a validated YAML schema of this project, "
                       "not a standardised metalanguage."},
]
_GENERATOR_SCOPE = (
    "Applies to the policy adviser (src/). The separate incident-response lab (ir/llm.py) can "
    "use a Claude model through the Anthropic API (LLM_PROVIDER=anthropic); without a key or the "
    "SDK it falls back to the deterministic offline playbook."
)


def _y3172_sandbox_description(ing: dict) -> str:
    return (
        "NOT EXECUTED — " + ing["sandbox"] + ". The Y.3172 ML sandbox (clauses 3.2.6, 8.2) is a "
        "different thing from the ITU AI for Good Sandbox platform: a subsystem of ML pipelines and "
        "simulated ML underlay networks, managed by the MLFO, in which ML models are trained and "
        "tested before deployment. This document pipeline has none; the network ML pipeline has one "
        "(sim/datagen.py, src/y3172/mlfo.py). Replay of recorded runs (src/audit/replay.py) re-tests "
        "recorded document-pipeline runs but is not an ML sandbox."
    )


def y3172_traceability(c: Corpus, run: dict) -> dict:
    ing = c.ingestion
    # A worked trace: the first quoted Indian provision in the recorded run
    trace_stage, trace_agent, trace_claim = None, None, None
    for stage in run["stages"]:
        for agent in stage["agents"]:
            for claim in agent["claims"]:
                if claim["citations"] and not claim["claim"].startswith("[REFERENCE ONLY"):
                    trace_stage, trace_agent, trace_claim = stage, agent, claim
                    break
            if trace_claim:
                break
        if trace_claim:
            break
    if trace_claim is None:
        raise FoundationError("recorded run has no quoted Indian provision to trace")
    cite = trace_claim["citations"][0]
    doc_id = cite["chunk_id"].split(":")[0]
    passage = next(p for p in trace_agent["retrieved_passages"] if p["chunk_id"] == cite["chunk_id"])
    rep = c.ingested[doc_id]
    coordinator_category = next(
        (cat for cat in ("evidence_backed_conclusions", "uncertain_conclusions", "conflicting_findings")
         if any(trace_claim["claim"][:120] in s for s in trace_stage["coordinator"][cat])), None)

    def node(section: str, phrase: str) -> dict:
        p = c.passage(_Y3172, section, phrase, width=0)
        return {"clause": p["section"], "chunk_id": p["chunk_id"], "phrase_quoted": phrase}

    stages = [
        ("Source", node("Clause 8.1", "SRC (source): This node is the source of data that can be used as input to the ML pipeline."),
         {"description": "Official source documents listed with provenance in the source manifest.",
          "files": [_file("knowledge_base/sources/manifest.json"), _file("knowledge_base/source_manifest.json")],
          "evidence_preserved": "title evidence string, URL, SHA-256, retrieval date, provenance note"},
         {"document": doc_id, "title": c.docs[doc_id]["title"], "url": c.docs[doc_id]["source_url"],
          "sha256": rep["sha256"]}, "IMPLEMENTED"),
        ("Collection", node("Clause 8.1", "C (collector): This node is responsible for collecting data from one or more SRC nodes."),
         {"description": "Text extraction with page provenance (PyMuPDF; python-docx for 3GPP); a file is "
                         "refused if its title evidence is absent.",
          "files": [_file("src/rag/extract.py"), _file("src/rag/build.py")],
          "evidence_preserved": "extracted character count, page numbers, refusal on wrong file"},
         {"extracted_chars": rep.get("extracted_chars"), "file": c.docs[doc_id]["file"]}, "IMPLEMENTED"),
        ("Preprocessing", node("Clause 8.1", "PP (preprocessor): This node is responsible for cleaning data"),
         {"description": "Running headers/footers removed, sections detected from printed headings or PDF "
                         "bookmarks, chunked within one section.",
          "files": [_file("src/rag/sections.py")],
          "parameters": {"max_chars_per_chunk": ing["chunking"]["max_chars"],
                         "overlap_chars": ing["chunking"]["overlap_chars"],
                         "unit": ing["chunking"]["unit"]},
          "evidence_preserved": "section label, section heading, page, chunk ID"},
         {"section": passage["section"], "section_title": passage["section_title"],
          "page": passage["page"], "chunk_id": passage["chunk_id"]}, "IMPLEMENTED"),
        ("Model", node("Clause 8.1", "M (model): This is a machine learning model, in a form which is usable in a machine learning pipeline."),
         {"description": "Sentence-embedding model for retrieval within each agent's own KB. No generative "
                         "model: agents quote retrieved passages.",
          "model_id": ing["embedding_model"],
          "generator_model": ing["generator_model"],
          "generator_model_scope": _GENERATOR_SCOPE,
          "files": [_file("src/rag/embedding.py"), _file("src/rag/vector_kb.py")],
          "evidence_preserved": "query, cosine similarity, knowledge base searched"},
         {"agent": trace_agent["agent_id"], "queries": trace_agent["queries"],
          "relevance_score": passage["relevance_score"]}, "IMPLEMENTED"),
        ("Policy", node("Clause 8.1", "P (policy): This node enables the application of policies to the output of the model node."),
         {"description": "The Verifier checks each claim against the Canonical KB (cited source/section "
                         "exists, text supports the claim, in-force and amendment status) and assigns "
                         "VERIFIED / INCOMPLETE / UNSUPPORTED / CONFLICT; cross-domain links and conflicts.",
          "files": [_file("src/core/verifier.py"), _file("src/core/cross_domain.py")],
          "evidence_preserved": "verifier outcome and rationale per claim"},
         {"verifier_outcome": trace_claim["verifier_outcome"],
          "verifier_rationale": trace_claim["verifier_rationale"]}, "IMPLEMENTED"),
        ("Distribution", node("Clause 8.1", "D (distributor): This node is responsible for identifying the SINK(s) and distributing the output of the M node"),
         {"description": "The Coordinator places each verified claim in one of the five DOCX Table A1 "
                         "categories; the assessment is written to the hash-chained audit trail and shown "
                         "in the UI.",
          "files": [_file("src/core/coordinator.py"), _file("src/audit/trail.py"), _file("src/ui/app.py")],
          "evidence_preserved": "Coordinator category, audit entry sequence number and hash"},
         {"coordinator_category": coordinator_category, "audit_file": run["path"],
          "audit_entry_seq": trace_stage["seq"], "audit_entry_hash": trace_stage["hash"]}, "IMPLEMENTED"),
        ("Sandbox", node("Clause 3.2", "machine learning sandbox: An environment in which machine learning models can be trained, tested and their effects on the network evaluated."),
         {"description": _y3172_sandbox_description(ing),
          "files": [_file("knowledge_base/ingestion_manifest.json"), _file("src/audit/replay.py")],
          "evidence_preserved": "'sandbox' entry in the ingestion manifest"},
         None, "NOT EXECUTED"),
    ]
    return {
        **_header([
            "ITU-T Y.3172 pipeline traceability (DOCX §4.3 / §7.4). Each stage quotes the",
            "Y.3172 definition from the ingested Recommendation, names the project components",
            "that perform it, and follows one quoted provision of a recorded run through it.",
            "Each stage also states how it corresponds to the Y.3172 node (direct or by",
            "analogy). network_ml_pipeline lists the Y.3172 components implemented over the",
            "simulated network (src/y3172/); what is simulated or logical only is listed separately.",
        ], "§4.3"),
        "standard": c.docs[_Y3172]["title"],
        "standard_authority": c.docs[_Y3172]["authority"],
        "standard_url": c.docs[_Y3172]["source_url"],
        "compliance_disclaimer": _Y3172_DISCLAIMER,
        "scope_note": _Y3172_SCOPE_NOTE,
        "pipeline_stages": [{
            "stage": name, "y3172_definition": defn, "project_implementation": impl,
            "worked_trace": trace, "status": status,
            "correspondence": _Y3172_CORRESPONDENCE[name][0],
            "difference_from_y3172": _Y3172_CORRESPONDENCE[name][1],
        } for name, defn, impl, trace, status in stages],
        "network_ml_pipeline": {
            "description": "ITU-T Y.3172 components implemented in src/y3172/ over the contained "
                           "simulated 5G core, with the policy and legal adviser as the P node. Run: "
                           "python run.py --intent intents/amf_signalling_storm.yaml",
            "components": [{**item, "files": [_file(f) for f in item["files"]]}
                           for item in _Y3172_NETWORK_PIPELINE],
        },
        "components_not_implemented": [
            {**item, "files": [_file(f) for f in item["files"]]} if "files" in item else dict(item)
            for item in _Y3172_NOT_IMPLEMENTED
        ],
        "worked_trace_claim": {"run": run["path"], "stage": trace_stage["stage"]["label"],
                               "agent": trace_agent["agent_id"], "claim": trace_claim["claim"]},
        "pipeline_traceability_matrix": {
            "rows": [{"y3172_stage": name, "status": status,
                      "correspondence": _Y3172_CORRESPONDENCE[name][0],
                      "components": impl["files"]} for name, _, impl, _, status in stages],
        },
    }


# ---------------------------------------------------------------------------
# §5.2 ITU AI Readiness mapping — the DOCX's eight perspectives
# ---------------------------------------------------------------------------

def itu_readiness(c: Corpus, manifest: dict, run: dict) -> dict:
    final = run["stages"][-1]
    stage_by_label = {s["stage"]["label"]: s for s in run["stages"]}
    link_kinds = Counter(l["kind"] for s in run["stages"]
                         for l in s["verifier"].get("cross_domain_details", []))
    gaps = final["coordinator"]["potential_policy_gaps"]
    ingested = [m for m in manifest["documents"] if m["sha256"]]
    licensed = [m for m in ingested if m["licence"]["statement_in_document"]]

    def artefact(claim: str, *files: str) -> dict:
        return {"evidence_type": "project artefact", "claim": claim,
                "files": [_file(f) for f in files]}

    def corpus(claim: str, doc: str, section: str, phrase: str) -> dict:
        return {"evidence_type": "corpus passage", "claim": claim, **c.passage(doc, section, phrase)}

    # DOCX §5.2 table: perspective, project mapping, evidence/status — verbatim
    perspectives = [
        ("Open data and open-source management",
         "Uses published/open Indian legal, regulatory and standards material and is designed for a source-linked open package.",
         "Repository/KB URLs were not supplied; insert actual public links before submission.",
         [artefact(f"{len(ingested)} source documents were downloaded from public URLs without login; "
                   f"each is recorded with URL, SHA-256 and provenance.", "knowledge_base/source_manifest.json"),
          artefact(f"{len(licensed)} documents carry a licence/copyright statement in their ingested "
                   "text, quoted in the manifest; for the others none was found in the ingested text.",
                   "knowledge_base/source_manifest.json"),
          artefact("The KB build is reproducible from the manifest; downloaded files and stores are not "
                   "redistributed in the repository.", "src/rag/build.py", ".gitignore")],
         ["Public repository and KB URLs for the submission (DOCX placeholders) are not recorded in the corpus.",
          "Licence terms were not determined for documents whose ingested text carries no statement."]),
        ("Generative AI content ecosystem",
         "Generative AI synthesizes verified multi-domain findings while preserving citations and uncertainty.",
         "Addressed architecturally; exact generator model name must be added.",
         [artefact("The policy adviser (src/) uses no generative model: its agents quote retrieved "
                   "passages and the Coordinator organises verified claims; generator_model is "
                   "recorded as 'none'.",
                   "knowledge_base/ingestion_manifest.json", "src/agents/base_agent.py"),
          artefact("The separate incident-response lab (ir/) can use a Claude model through the "
                   "Anthropic API for tool use (LLM_PROVIDER=anthropic, model set by "
                   "ANTHROPIC_MODEL); without a key or the SDK it falls back to the deterministic "
                   "offline playbook.", "ir/llm.py")],
         ["The policy adviser uses no generator model, so none is recorded for it.",
          "No evaluation of the lab's generative agent is recorded."]),
        ("Contextualization of AI solutions and regional development",
         "India-specific legal, regulatory and institutional context with a regional comparison layer.",
         "Addressed in scope; neighbouring-country corpus should be included in the final Policy Gap KB.",
         [corpus("Telecom authorisation by the Central Government.", "telecom_act_2023", "Section 3",
                 "shall obtain an authorisation from the Central Government"),
          corpus("Six-hour security-incident reporting by telecommunication entities.",
                 "telecom_cyber_security_rules_2024", "Rule 7", "within six hours"),
          corpus("Cyber-incident reporting to CERT-In.", "certin_directions_2022", "Direction (ii)",
                 "report cyber incidents"),
          corpus("Personal-data breach intimation by a Data Fiduciary.", "dpdp_rules_2025", "Rule 7",
                 "Intimation of personal data breach"),
          {"evidence_type": "corpus passage",
           "claim": "An EU policy example used for comparison (not Indian law).",
           **c.find("enisa_5g_security_controls_matrix", "5G Cybersecurity toolbox")}],
         ["No neighbouring-country instrument was obtained; the regional comparison layer has EU "
          "examples only."]),
        ("AI integration in domains and cross-domain analysis",
         "Seven specialist agents cover technical, legal/policy, cyber, privacy, critical infrastructure, standards and policy gaps; Verifier checks cross-domain effects.",
         "Addressed at workflow level.",
         [artefact("Seven agent KBs plus the Canonical KB: " + ", ".join(
                       f"{kb} {len(c.chunks[kb])}" for kb in ALL_KBS) + " passages.",
                   "knowledge_base/source_manifest.json"),
          artefact("Cross-domain links established from evidence in the recorded run: " + ", ".join(
                       f"{k.replace('_', ' ')} {n}" for k, n in sorted(link_kinds.items())) + ".",
                   run["path"], "src/core/cross_domain.py")],
         ["No empirical evaluation of cross-domain accuracy by domain experts."]),
        ("Human interaction and supervision",
         "Decision support only; legal interpretation and final institutional decisions remain with qualified humans.",
         "Addressed by design; formal human-evaluation scores are not claimed.",
         [artefact("Every assessment carries the human-review notice: "
                   f"\"{final['coordinator']['human_review_required']}\"", run["path"], "src/core/models.py"),
          artefact("The UI shows the notice permanently and keeps conflicts unresolved for human review.",
                   "src/ui/app.py")],
         ["No human-evaluation study or score."]),
        ("AI policy and implementation opportunity identification",
         "Policy Gap Agent classifies explicit, partial, unclear, overlapping, institutional-clarity and emerging-technology coverage.",
         "Addressed with evidence-linked potential gaps.",
         [artefact(f"{len(gaps)} potential-gap entries in the final stage of the recorded run, each "
                   "naming the instruments examined.", run["path"], "src/agents/policy_gap_agent.py"),
          corpus("TRAI recommendations on AI and Big Data in telecom, used as policy reference.",
                 "trai_ai_bigdata_recs_2023", "p. 1", "Leveraging Artificial Intelligence and Big Data")],
         ["Unclear coverage is not produced by the current agent; explicit/partial coverage is left "
          "to expert review.", "No neighbouring-country policy examples are ingested."]),
        ("AI for social inclusion",
         "Makes complex policy evidence available through a structured decision-support interface for multiple stakeholder groups.",
         "Potential contribution; no quantitative inclusion study is claimed.",
         [artefact("Structured interface showing each finding with its source, section and passage.",
                   "src/ui/app.py")],
         ["No inclusion study or user data."]),
        ("Digital infrastructure and energy",
         "Software decision-support layer tested in an isolated Windows environment; deployment footprint can be measured separately.",
         "Operational energy measurements are not reported.",
         [artefact(f"CPU-only embedding model ({c.ingestion['embedding_model']}); the full KB build took "
                   f"{c.ingestion['build_seconds']} s of wall-clock time on this machine.",
                   "knowledge_base/ingestion_manifest.json")],
         ["No energy measurement."]),
    ]
    dimensions = [{
        "dimension_id": f"D{i}",
        "dimension_name": name,
        "docx_project_mapping": mapping,
        "docx_evidence_status": status,
        "evidence_items": items,
        "evidence_unavailable": missing,
    } for i, (name, mapping, status, items, missing) in enumerate(perspectives, 1)]
    return {
        **_header([
            "ITU AI Readiness mapping (DOCX §5.2 and §5.1 mapping 13). The eight perspectives,",
            "project mappings and evidence/status texts are the DOCX table verbatim; evidence",
            "items are corpus passages located in the stores or project files that exist.",
        ], "§5.2"),
        "methodology_disclaimer": "This is an evidence mapping, not a formal ITU AI Readiness "
                                  "assessment and not ITU certification. No score or maturity "
                                  "level is assigned.",
        "recorded_run": run["path"],
        "dimensions": dimensions,
        "overall_evidence_summary": {
            "no_readiness_score_assigned": "true — the DOCX claims none and none is computed",
            "no_maturity_level_claimed": "true",
            "perspectives": len(dimensions),
            "stages_in_recorded_run": list(stage_by_label),
        },
    }


# ---------------------------------------------------------------------------

OUTPUTS = {
    "source_manifest": KB_ROOT / "source_manifest.json",
    "canonical_metadata": KB_ROOT / "canonical" / "canonical_metadata.json",
    "host_country_corpus": KB_ROOT / "host_country_corpus.json",
    "policy_gap_categories": KB_ROOT / "policy_gap" / "policy_gap_categories.json",
    "y3172": KB_ROOT / "y3172_pipeline_traceability.json",
    "itu_readiness": KB_ROOT / "itu_ai_readiness_mapping.json",
}


def generate(run_path: Path = DEFAULT_RUN) -> dict[str, dict]:
    c = Corpus()
    run = _read_run(run_path)
    manifest = source_manifest(c)
    OUTPUTS["source_manifest"].write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    out = {
        "source_manifest": manifest,
        "canonical_metadata": canonical_metadata(c, manifest),
        "host_country_corpus": host_country_corpus(c, manifest),
        "policy_gap_categories": policy_gap_categories(c, run),
        "y3172": y3172_traceability(c, run),
        "itu_readiness": itu_readiness(c, manifest, run),
    }
    for key, data in out.items():
        OUTPUTS[key].write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"wrote {OUTPUTS[key].relative_to(ROOT)}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, default=DEFAULT_RUN,
                    help="recorded scenario run used for examples and the worked trace")
    args = ap.parse_args(argv)
    try:
        generate(args.run)
    except FoundationError as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
