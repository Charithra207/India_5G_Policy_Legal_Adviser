"""
Evidence-path tests: the pipeline with populated knowledge bases.

These tests prove the Verifier's VERIFIED / INCOMPLETE / UNSUPPORTED /
CONFLICT paths and the evidence-grounded agent claims, using in-memory KBs.

All passages are synthetic FIXTURES (source titles start with "FIXTURE").
They are not quotations of any real instrument and must never be loaded
into a real knowledge base.

Run with:
    python -m pytest tests/test_verification_evidence.py -v
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.basicConfig(level=logging.WARNING)

from src.core.models import AgentID, EvidenceItem, VerifierOutcome
from src.knowledge_base.in_memory_kb import InMemoryCanonicalKB, InMemoryKnowledgeBase
from src.knowledge_base.kb_registry import KBRegistry
from src.pipeline import Pipeline
from src.utils.output_formatter import save_audit_json
from scenarios.scenario2_healthcare_5g import get_chunks


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

def fx(title, section, excerpt, jurisdiction="India", chunk_id=None, **kw) -> EvidenceItem:
    return EvidenceItem(
        source_title  = f"FIXTURE {title}",
        authority     = "Test fixture",
        jurisdiction  = jurisdiction,
        document_type = "Fixture",
        section       = section,
        excerpt       = excerpt,
        chunk_id      = chunk_id or f"fx-{title}-{section}".replace(" ", "-"),
        **kw,
    )


SLICE_SPEC = fx(
    "5G Architecture Spec", "Clause 5.15",
    "A network slice provides specific network capabilities and network "
    "characteristics, and slice performance is monitored per session.",
    jurisdiction="International",
)


def _registry(agent_items: dict[AgentID, list[EvidenceItem]],
              canonical_items: list[EvidenceItem] | None) -> KBRegistry:
    registry = KBRegistry()
    for agent_id, items in agent_items.items():
        registry.agent_kbs[agent_id] = InMemoryKnowledgeBase(
            kb_name=f"{agent_id.value} fixture KB", domain=agent_id.value, items=items,
        )
    if canonical_items is not None:
        registry.canonical_kb = InMemoryCanonicalKB(canonical_items)
    return registry


def _run_t0(agent_items, canonical_items):
    pipeline = Pipeline(_registry(agent_items, canonical_items))
    return pipeline.run_chunk(get_chunks()[0])


def _quoted_outcomes(record, agent_id=AgentID.TECHNICAL):
    """Outcomes of the claims that quote a retrieved passage."""
    finding = next(f for f in record.agent_findings if f.agent_id == agent_id)
    cited = set(finding.claim_citations)
    assert cited, f"{agent_id.value} should have quoted at least one retrieved passage"
    return [vc for vc in record.verifier_result.verified_claims if vc.claim in cited]


# -----------------------------------------------------------------------
# Agents: claims about sources come from retrieved passages
# -----------------------------------------------------------------------

def test_agent_quotes_retrieved_passage_with_citation() -> None:
    record  = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, None)
    finding = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)

    quoted = [c for c in finding.claims if c in finding.claim_citations]
    assert len(quoted) == 1
    assert "Clause 5.15" in quoted[0] and "network slice provides" in quoted[0]
    assert quoted[0].startswith("[REFERENCE ONLY"), "International passages must be labelled"
    assert finding.claim_citations[quoted[0]][0].chunk_id == SLICE_SPEC.chunk_id


def test_stub_kbs_produce_no_unsourced_instrument_content() -> None:
    """
    Without retrieved passages, a claim that names an instrument must say its
    applicability is not assessed — agents never supply legal or standards
    content from memory.
    """
    instruments = ["Telecommunications Act", "TRAI Act", "Cyber Security) Rules",
                   "CERT-In Directions", "DPDP", "Digital Personal Data Protection",
                   "NCIIPC and Manner", "3GPP TS", "NIST", "ETSI", "ITU-T"]
    pipeline = Pipeline()
    for chunk in get_chunks():
        record = pipeline.run_chunk(chunk)
        for finding in record.agent_findings:
            for claim in finding.claims:
                if any(name in claim for name in instruments):
                    assert claim in finding.claim_citations or "not assessed" in claim, (
                        f"{finding.agent_id.value} states instrument content without a "
                        f"citation:\n  {claim}"
                    )


# -----------------------------------------------------------------------
# Verifier outcomes with a live Canonical KB
# -----------------------------------------------------------------------

def test_verified_when_canonical_confirms_cited_section() -> None:
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [SLICE_SPEC])
    outcomes = _quoted_outcomes(record)
    assert [vc.outcome for vc in outcomes] == [VerifierOutcome.VERIFIED]
    assert outcomes[0].supporting_evidence[0].section == "Clause 5.15"

    backed = record.coordinator_assessment.evidence_backed_conclusions
    assert any("Clause 5.15" in c for c in backed), (
        "A VERIFIED claim must appear under evidence-backed conclusions"
    )


def test_incomplete_when_canonical_records_amendment() -> None:
    amended = EvidenceItem(**{**SLICE_SPEC.__dict__,
                              "amendment_note": "Clause 5.15 revised in a later release"})
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [amended])
    [vc] = _quoted_outcomes(record)
    assert vc.outcome == VerifierOutcome.INCOMPLETE
    assert "revised in a later release" in vc.rationale


def test_unsupported_when_cited_section_absent_from_canonical() -> None:
    other = fx("5G Architecture Spec", "Clause 9.1", "Unrelated clause text.",
               jurisdiction="International")
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [other])
    [vc] = _quoted_outcomes(record)
    assert vc.outcome == VerifierOutcome.UNSUPPORTED
    assert "not found in the Canonical KB" in vc.rationale


def test_unsupported_when_canonical_text_differs_from_quote() -> None:
    """The agent's KB copy says something the authoritative copy does not."""
    canonical = EvidenceItem(**{**SLICE_SPEC.__dict__,
                                "excerpt": "Registration procedures for user equipment."})
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [canonical])
    [vc] = _quoted_outcomes(record)
    assert vc.outcome == VerifierOutcome.UNSUPPORTED
    assert "does not support" in vc.rationale


def test_unsupported_when_canonical_passage_not_in_force() -> None:
    repealed = EvidenceItem(**{**SLICE_SPEC.__dict__, "effective": False})
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [repealed])
    [vc] = _quoted_outcomes(record)
    assert vc.outcome == VerifierOutcome.UNSUPPORTED
    assert "not in force" in vc.rationale


def test_incomplete_when_canonical_stub_but_agent_cited() -> None:
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, None)
    [vc] = _quoted_outcomes(record)
    assert vc.outcome == VerifierOutcome.INCOMPLETE
    assert "cannot be independently confirmed" in vc.rationale


def test_agent_reading_of_facts_not_verified_by_unrelated_passage() -> None:
    """Uncited inferences are UNSUPPORTED unless an authoritative passage backs them."""
    record  = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [SLICE_SPEC])
    finding = next(f for f in record.agent_findings if f.agent_id == AgentID.TECHNICAL)
    for vc in record.verifier_result.verified_claims:
        if vc.claim not in finding.claim_citations:
            assert vc.outcome == VerifierOutcome.UNSUPPORTED, vc.claim


def test_support_judge_is_pluggable() -> None:
    """A stricter judge (e.g. an LLM entailment check) can replace the default."""
    registry = _registry({AgentID.TECHNICAL: [SLICE_SPEC]}, [SLICE_SPEC])
    pipeline = Pipeline(registry)
    pipeline.verifier.support_judge = lambda claim, passage: False
    record = pipeline.run_chunk(get_chunks()[0])
    assert all(vc.outcome != VerifierOutcome.VERIFIED
               for vc in record.verifier_result.verified_claims)


# -----------------------------------------------------------------------
# CONFLICT
# -----------------------------------------------------------------------

def _run_to_t2(agent_items):
    pipeline = Pipeline(_registry(agent_items, None))
    chunks = get_chunks()
    pipeline.run_chunk(chunks[0])
    pipeline.run_chunk(chunks[1])
    return pipeline.run_chunk(chunks[2])


def test_conflict_when_policy_legal_examined_sources_but_found_no_obligation() -> None:
    definitions = fx("Telecom Instrument", "Section 2",
                     "Definitions of telecom terms used in this instrument.")
    record = _run_to_t2({AgentID.POLICY_LEGAL: [definitions]})

    cii = [vc for vc in record.verifier_result.verified_claims
           if vc.agent_id == AgentID.CRITICAL_INFRA]
    # Only the disputed claim — CII relevance — becomes CONFLICT
    relevance = next(vc for vc in cii if "critical-infrastructure provisions" in vc.claim)
    assert relevance.outcome == VerifierOutcome.CONFLICT
    assert all(vc.outcome != VerifierOutcome.CONFLICT for vc in cii if vc is not relevance)
    [conflict] = record.verifier_result.conflict_details
    assert conflict.finding_a.claim == relevance.claim
    assert conflict.finding_b.agent_id == AgentID.POLICY_LEGAL
    assert conflict.finding_b.evidence, "Finding B shows the passages Policy & Legal examined"
    assert record.coordinator_assessment.conflicting_findings


def test_no_conflict_when_policy_legal_had_no_sources() -> None:
    """Silence for lack of evidence is missing evidence, not disagreement."""
    record = _run_to_t2({})
    assert not record.verifier_result.conflicts
    assert all(vc.outcome != VerifierOutcome.CONFLICT
               for vc in record.verifier_result.verified_claims)


def test_duty_passage_recorded_as_obligation() -> None:
    duty = fx("Telecom Instrument", "Section 7",
              "A telecom entity shall report a security incident affecting its network.")
    record = _run_to_t2({AgentID.POLICY_LEGAL: [duty]})
    pl = next(f for f in record.agent_findings if f.agent_id == AgentID.POLICY_LEGAL)
    assert any("Section 7" in o for o in pl.obligations)
    assert not record.verifier_result.conflicts


# -----------------------------------------------------------------------
# Policy Gap: gaps rest on Canonical KB examination (DOCX §7.1)
# -----------------------------------------------------------------------

CYBER_REPORTING = fx("Cyber Rules", "Rule 3",
                     "A telecom entity shall report a cyber security incident to the authority.")
DATA_NOTIFY     = fx("Data Act", "Section 8",
                     "A data fiduciary shall notify a personal data breach to the Board.")
NCIIPC_ROLE     = fx("CII Rules", "Rule 4",
                     "NCIIPC shall coordinate protection of critical information infrastructure.")
CERTIN_ROLE     = fx("Cyber Directions", "Para 2",
                     "CERT-In shall receive reports of cyber incidents and coordinate response.")


def _gap_finding(canonical_items):
    pipeline = Pipeline(_registry({}, canonical_items))
    for chunk in get_chunks():
        record = pipeline.run_chunk(chunk)
    return record, next(f for f in record.agent_findings if f.agent_id == AgentID.POLICY_GAP)


def test_policy_gaps_raised_only_from_examined_corpus() -> None:
    record, gap = _gap_finding([CYBER_REPORTING, DATA_NOTIFY, NCIIPC_ROLE, CERTIN_ROLE])
    raised = [c for c in gap.claims if c.startswith("Potential gap")]

    assert any("Emerging technology not explicitly addressed" in c for c in raised)
    assert any("Overlapping requirements" in c and "Rule 3" in c and "Section 8" in c
               for c in raised)
    assert any("Missing institutional clarity" in c for c in raised)
    for claim in raised:
        if "Emerging technology" in claim:
            # An absence claim cites no passage; it names what was examined
            assert "every one examined" in claim and "instruments examined:" in claim, claim
        else:
            assert gap.claim_citations.get(claim), f"Raised gap without cited passages: {claim}"
        assert "No conclusion of policy failure is drawn" in claim

    outcomes = {vc.claim: vc.outcome for vc in record.verifier_result.verified_claims}
    for claim in raised:
        assert outcomes[claim] == VerifierOutcome.INCOMPLETE, (
            f"A potential gap is never VERIFIED and, when its passages exist, not "
            f"UNSUPPORTED; got {outcomes[claim]} for: {claim}"
        )

    listed = record.coordinator_assessment.potential_policy_gaps
    assert sum("[POLICY GAP — for expert review]" in g for g in listed) == len(raised)


def test_no_gap_when_corpus_covers_the_area() -> None:
    slicing = fx("Telecom Instrument", "Section 12",
                 "Network slicing services offered by a telecom entity are subject to "
                 "the security conditions of its authorisation.")
    _, gap = _gap_finding([slicing, CYBER_REPORTING])
    assert not any(c.startswith("Potential gap — Emerging") for c in gap.claims)
    assert any(c.startswith("Coverage check — network slicing") for c in gap.claims)


def test_no_gap_raised_without_canonical_kb() -> None:
    record, gap = _gap_finding(None)
    assert not any(c.startswith("Potential gap") for c in gap.claims)
    assert all(c.startswith("Candidate area NOT EXAMINED") for c in gap.claims)
    assert all("[CANDIDATE GAP AREA — not examined]" in g
               for g in record.coordinator_assessment.potential_policy_gaps
               if not g.startswith("[GAP SUMMARY"))


# -----------------------------------------------------------------------
# Audit record: per-claim outcomes and citations are replayable (DOCX §7.6)
# -----------------------------------------------------------------------

def test_audit_json_records_per_claim_outcome_and_citation() -> None:
    record = _run_t0({AgentID.TECHNICAL: [SLICE_SPEC]}, [SLICE_SPEC])
    with tempfile.TemporaryDirectory() as tmp:
        with open(save_audit_json(record, output_dir=tmp), encoding="utf-8") as fh:
            data = json.load(fh)

    verified = [c for c in data["verified_claims"] if c["outcome"] == "VERIFIED"]
    assert verified and verified[0]["supporting_evidence"][0]["section"] == "Clause 5.15"

    tech = next(f for f in data["agent_findings"] if f["agent_id"] == "technical")
    assert any(refs == ["FIXTURE 5G Architecture Spec, Clause 5.15"]
               for refs in tech["claim_citations"].values())
