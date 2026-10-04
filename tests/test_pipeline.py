"""
Pipeline end-to-end tests.

Tests the full pipeline for Scenario 2 (DOCX Â§2.5), all four chunks.

Expected agent activations (DOCX Annex-1 A.4 / Â§2.5):
    T0: Technical
    T1: Technical + Cybersecurity + Standards
    T2: Critical Infrastructure + Privacy + Policy & Legal
    T3: Policy & Legal + Cybersecurity + Privacy + Critical Infrastructure
        + Policy Gap

All test functions return None so pytest does not emit
PytestReturnNotNoneWarning.

Run with:
    python -m pytest tests/test_pipeline.py -v
or:
    python tests/test_pipeline.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import logging
logging.basicConfig(level=logging.WARNING)

from src.pipeline import Pipeline
from src.core.models import AgentID, VerifierOutcome, AuditRecord
from scenarios.scenario2_healthcare_5g import get_chunk


# -----------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------

def _run(pipeline: Pipeline, index: int) -> AuditRecord:
    return pipeline.run_chunk(get_chunk(index))


def _active(record: AuditRecord) -> set[AgentID]:
    return set(record.active_agents)


def _assert_exact_agents(record: AuditRecord, expected: set[AgentID]) -> None:
    """Assert the active agent set matches expected exactly â€” no more, no less."""
    active = _active(record)
    extra   = active - expected
    missing = expected - active
    assert not extra and not missing, (
        f"Agent set mismatch at {record.chunk_id}.\n"
        f"  Expected : {sorted(a.value for a in expected)}\n"
        f"  Active   : {sorted(a.value for a in active)}\n"
        f"  Extra    : {sorted(a.value for a in extra)}\n"
        f"  Missing  : {sorted(a.value for a in missing)}"
    )


def _assert_no_false_verified(record: AuditRecord) -> None:
    """
    With stub KBs, no claim may be VERIFIED.
    The [REFERENCE ONLY] label is NOT evidence â€” it does not confer VERIFIED.
    """
    for vc in record.verifier_result.verified_claims:
        assert vc.outcome != VerifierOutcome.VERIFIED, (
            f"Claim incorrectly marked VERIFIED without Canonical KB evidence.\n"
            f"  Agent   : {vc.agent_id.value}\n"
            f"  Claim   : {vc.claim[:120]}\n"
            f"  Rationale: {vc.rationale[:120]}\n"
            "  A claim requires actual KB evidence to be VERIFIED."
        )


def _assert_no_fake_citations(record: AuditRecord) -> None:
    forbidden = ["[FABRICATED]", "[FAKE]", "invented_source", "made_up_law"]
    text = " ".join(c for f in record.agent_findings for c in f.claims)
    for bad in forbidden:
        assert bad not in text, f"Forbidden fabricated text found: {bad!r}"


# -----------------------------------------------------------------------
# T0: Technical only
# -----------------------------------------------------------------------

def test_t0_exact_agent_set() -> None:
    """T0 must activate Technical and nothing else."""
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    _assert_exact_agents(record, {AgentID.TECHNICAL})


def test_t0_no_false_verified() -> None:
    """T0: no claim may be VERIFIED without real KB evidence."""
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    _assert_no_false_verified(record)


def test_t0_confirmed_facts_present() -> None:
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    a = record.coordinator_assessment
    assert any(
        "latency" in f.lower() or "session drops" in f.lower()
        for f in a.confirmed_facts
    ), "T0 confirmed_facts must include the scenario description"


def test_t0_technical_lists_components() -> None:
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    tech = next((f for f in record.agent_findings
                 if f.agent_id == AgentID.TECHNICAL), None)
    assert tech is not None, "No Technical Agent finding at T0"
    assert tech.affected_components, "Technical Agent must list affected components"


def test_t0_five_coordinator_categories_present() -> None:
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    a = record.coordinator_assessment
    assert hasattr(a, "confirmed_facts")
    assert hasattr(a, "evidence_backed_conclusions")
    assert hasattr(a, "uncertain_conclusions")
    assert hasattr(a, "conflicting_findings")
    assert hasattr(a, "potential_policy_gaps")


def test_t0_human_review_present() -> None:
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    assert record.coordinator_assessment.human_review_required


def test_t0_initial_assessment_note() -> None:
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    assert any("Initial" in c for c in
               record.coordinator_assessment.changes_from_prior), (
        "First chunk must note it is the initial assessment"
    )


def test_t0_no_fake_citations() -> None:
    pipeline = Pipeline()
    record   = _run(pipeline, 0)
    _assert_no_fake_citations(record)


# -----------------------------------------------------------------------
# T1: Technical + Cybersecurity + Standards
# -----------------------------------------------------------------------

def test_t1_exact_agent_set() -> None:
    """T1 must activate exactly Technical, Cybersecurity, Standards."""
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    _assert_exact_agents(record, {
        AgentID.TECHNICAL,
        AgentID.CYBERSECURITY,
        AgentID.STANDARDS,
    })


def test_t1_no_false_verified() -> None:
    """T1: no claim may be VERIFIED without real KB evidence."""
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    _assert_no_false_verified(record)


def test_t1_cybersecurity_addresses_signalling() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    cf = next((f for f in record.agent_findings
               if f.agent_id == AgentID.CYBERSECURITY), None)
    assert cf is not None, "No Cybersecurity Agent finding at T1"
    text = " ".join(cf.claims).lower()
    assert any(kw in text for kw in
               ["authentication", "signalling", "cyber", "telecom cyber security"]), (
        "Cybersecurity Agent must address authentication/signalling at T1"
    )


def test_t1_standards_references_33501() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    sf = next((f for f in record.agent_findings
               if f.agent_id == AgentID.STANDARDS), None)
    assert sf is not None, "No Standards Agent finding at T1"
    text = " ".join(sf.claims)
    assert "33.501" in text or "3gpp" in text.lower(), (
        "Standards Agent must reference 3GPP TS 33.501 at T1"
    )


def test_t1_standards_claims_carry_reference_label() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    sf = next((f for f in record.agent_findings
               if f.agent_id == AgentID.STANDARDS), None)
    assert sf is not None
    for claim in sf.claims:
        if any(std in claim for std in ["3GPP", "NIST", "ETSI", "ITU"]):
            assert "[REFERENCE ONLY" in claim, (
                f"Standards claim missing reference-only label:\n  {claim}"
            )


def test_t1_reclassification_in_changes() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    text = " ".join(record.coordinator_assessment.changes_from_prior).lower()
    assert any(kw in text for kw in
               ["cyber", "security", "reclass", "newly activated"]), (
        "T1 changes_from_prior must note cyber/security reclassification"
    )


def test_t1_cyber_event_flag_set() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    assert pipeline.incident_state["cyber_event_suspected"] is True


def test_t1_no_fake_citations() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)
    _assert_no_fake_citations(record)


# -----------------------------------------------------------------------
# T2: Critical Infrastructure + Privacy + Policy & Legal
# -----------------------------------------------------------------------

def test_t2_exact_agent_set() -> None:
    """T2 must activate exactly Critical Infrastructure, Privacy, Policy & Legal."""
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    _assert_exact_agents(record, {
        AgentID.CRITICAL_INFRA,
        AgentID.PRIVACY,
        AgentID.POLICY_LEGAL,
    })


def test_t2_no_false_verified() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    _assert_no_false_verified(record)


def test_t2_privacy_agent_addresses_exposure() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    pf = next((f for f in record.agent_findings
               if f.agent_id == AgentID.PRIVACY), None)
    assert pf is not None, "No Privacy Agent finding at T2"
    assert pf.exposure_status in ("confirmed", "suspected", "unknown"), (
        f"Privacy Agent must set exposure_status, got: {pf.exposure_status!r}"
    )
    text = " ".join(pf.claims).lower()
    assert any(kw in text for kw in ["personal data", "dpdp", "patient", "exposure"]), (
        "Privacy Agent must address personal data at T2"
    )


def test_t2_cii_agent_assesses_healthcare() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    ci = next((f for f in record.agent_findings
               if f.agent_id == AgentID.CRITICAL_INFRA), None)
    assert ci is not None, "No Critical Infrastructure Agent finding at T2"
    text = " ".join(ci.claims).lower()
    assert any(kw in text for kw in ["healthcare", "critical", "cii", "nciipc"]), (
        "Critical Infra Agent must assess healthcare/CII relevance at T2"
    )


def test_t2_policy_legal_agent_present() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    pl = next((f for f in record.agent_findings
               if f.agent_id == AgentID.POLICY_LEGAL), None)
    assert pl is not None, "No Policy & Legal Agent finding at T2"
    assert pl.claims, "Policy & Legal Agent must produce claims at T2"


def test_t2_human_review_present() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    assert record.coordinator_assessment.human_review_required


def test_t2_no_fake_citations() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    record = _run(pipeline, 2)
    _assert_no_fake_citations(record)


# -----------------------------------------------------------------------
# T3: Policy & Legal + Cybersecurity + Privacy + Critical Infra + Policy Gap
# -----------------------------------------------------------------------

def test_t3_exact_agent_set() -> None:
    """T3 must activate exactly the five DOCX-specified agents."""
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    _assert_exact_agents(record, {
        AgentID.POLICY_LEGAL,
        AgentID.CYBERSECURITY,
        AgentID.PRIVACY,
        AgentID.CRITICAL_INFRA,
        AgentID.POLICY_GAP,
    })


def test_t3_no_false_verified() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    _assert_no_false_verified(record)


def test_t3_policy_gap_agent_runs() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    gf = next((f for f in record.agent_findings
               if f.agent_id == AgentID.POLICY_GAP), None)
    assert gf is not None, "Policy Gap Agent must produce a finding at T3"
    assert gf.claims, "Policy Gap Agent must produce claims at T3"


def test_t3_policy_gap_uses_non_conclusive_language() -> None:
    """
    Policy gap statements must use non-conclusive language (DOCX Â§5.1).

    The agent must NOT assert that Indian policy IS inadequate.
    The DOCX-required disclaimer "does not constitute a conclusion that Indian
    policy is inadequate" is correct non-conclusive language and must be
    present.  We check for direct assertions of inadequacy, not for the
    disclaimer phrase that negates it.
    """
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    gf = next((f for f in record.agent_findings
               if f.agent_id == AgentID.POLICY_GAP), None)
    assert gf is not None

    # The agent must not make direct assertions of inadequacy.
    # Permitted: "No conclusion of policy failure is drawn"
    # Forbidden: "Indian policy is inadequate" / "the policy is inadequate" (direct assertion)
    direct_inadequacy_patterns = [
        "indian policy is inadequate",
        "the policy is inadequate",
        "framework is inadequate",
        "regulation is inadequate",
        "policy is inadequate",
    ]
    for claim in gf.claims:
        claim_lower = claim.lower()
        for pattern in direct_inadequacy_patterns:
            assert pattern not in claim_lower, (
                f"Policy Gap claim must not directly assert policy inadequacy.\n"
                f"  Forbidden pattern: {pattern!r}\n"
                f"  Claim: {claim}"
            )

    # Must use non-conclusive gap language
    gap_text = " ".join(gf.claims).lower()
    assert any(kw in gap_text for kw in
               ["potential gap", "regulatory ambiguity", "not explicitly",
                "unclear", "overlapping", "missing institutional",
                "reference only", "for expert review"]), (
        "Policy Gap Agent must use non-conclusive gap language"
    )


def test_t3_policy_gap_receives_prior_verified_findings() -> None:
    """
    Policy Gap Agent must have prior verified_findings available in
    incident_state (i.e. Pass-1 verification completed before Pass-2).
    """
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    _run(pipeline, 3)
    state = pipeline.incident_state
    assert state["verified_findings"], (
        "verified_findings must be non-empty at T3 â€” "
        "Policy Gap Agent needs prior verified context"
    )


def test_t3_coordinator_has_policy_gaps() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    assert record.coordinator_assessment.potential_policy_gaps, (
        "Coordinator must surface potential policy gaps at T3"
    )


def test_t3_cross_domain_links_flagged() -> None:
    """T3 has multiple overlapping domains â€” cross-domain links must be flagged."""
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    assert record.verifier_result.cross_domain_links, (
        "Verifier must flag cross-domain relationships at T3"
    )


def test_t3_human_review_present() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    assert record.coordinator_assessment.human_review_required


def test_t3_no_fake_citations() -> None:
    pipeline = Pipeline()
    _run(pipeline, 0)
    _run(pipeline, 1)
    _run(pipeline, 2)
    record = _run(pipeline, 3)
    _assert_no_fake_citations(record)


# -----------------------------------------------------------------------
# Standards regression: [REFERENCE ONLY] label is NOT evidence
# -----------------------------------------------------------------------

def test_standards_reference_label_does_not_confer_verified() -> None:
    """
    Regression test for FIX 3.

    A Standards Agent claim that carries the [REFERENCE ONLY â€” not Indian law]
    label but has no supporting evidence from the Canonical KB must be
    UNSUPPORTED (or INCOMPLETE if agent evidence exists), never VERIFIED.

    This test runs T1 where Standards claims are produced, confirms the
    label is present, then confirms none of them are VERIFIED.
    """
    pipeline = Pipeline()
    _run(pipeline, 0)
    record = _run(pipeline, 1)

    std_findings = [f for f in record.agent_findings
                    if f.agent_id == AgentID.STANDARDS]
    assert std_findings, "Standards Agent must run at T1"

    # Confirm the reference-only label is present in at least one claim
    all_claims = [c for f in std_findings for c in f.claims]
    has_label = any("[REFERENCE ONLY" in c for c in all_claims)
    assert has_label, (
        "Standards Agent must use [REFERENCE ONLY] label â€” "
        "label must be present to test the regression"
    )

    # Now confirm none of those labelled claims are VERIFIED
    verified_claims = record.verifier_result.verified_claims
    for vc in verified_claims:
        if vc.agent_id == AgentID.STANDARDS:
            assert vc.outcome != VerifierOutcome.VERIFIED, (
                f"Standards claim incorrectly marked VERIFIED.\n"
                f"  Claim    : {vc.claim[:120]}\n"
                f"  Rationale: {vc.rationale[:120]}\n"
                "  The [REFERENCE ONLY] label is a disclaimer, not evidence. "
                "VERIFIED requires actual Canonical KB support."
            )


# -----------------------------------------------------------------------
# Standalone runner (not pytest)
# -----------------------------------------------------------------------

if __name__ == "__main__":
    import traceback
    from src.utils.output_formatter import (
        format_audit_record, save_assessment_text, save_audit_json,
    )

    TESTS = [
        # T0
        test_t0_exact_agent_set,
        test_t0_no_false_verified,
        test_t0_confirmed_facts_present,
        test_t0_technical_lists_components,
        test_t0_five_coordinator_categories_present,
        test_t0_human_review_present,
        test_t0_initial_assessment_note,
        test_t0_no_fake_citations,
        # T1
        test_t1_exact_agent_set,
        test_t1_no_false_verified,
        test_t1_cybersecurity_addresses_signalling,
        test_t1_standards_references_33501,
        test_t1_standards_claims_carry_reference_label,
        test_t1_reclassification_in_changes,
        test_t1_cyber_event_flag_set,
        test_t1_no_fake_citations,
        # T2
        test_t2_exact_agent_set,
        test_t2_no_false_verified,
        test_t2_privacy_agent_addresses_exposure,
        test_t2_cii_agent_assesses_healthcare,
        test_t2_policy_legal_agent_present,
        test_t2_human_review_present,
        test_t2_no_fake_citations,
        # T3
        test_t3_exact_agent_set,
        test_t3_no_false_verified,
        test_t3_policy_gap_agent_runs,
        test_t3_policy_gap_uses_non_conclusive_language,
        test_t3_policy_gap_receives_prior_verified_findings,
        test_t3_coordinator_has_policy_gaps,
        test_t3_cross_domain_links_flagged,
        test_t3_human_review_present,
        test_t3_no_fake_citations,
        # Regression
        test_standards_reference_label_does_not_confer_verified,
    ]

    passed, failed = 0, 0
    for fn in TESTS:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL  {fn.__name__}: {exc}")
            traceback.print_exc()
            failed += 1

    # Save full assessment outputs for T0-T3
    print("\nGenerating assessment outputs...")
    pipeline = Pipeline()
    for i in range(4):
        record = _run(pipeline, i)
        save_assessment_text(record)
        save_audit_json(record)
        print(f"  Saved outputs for {record.chunk_id}")

    print(f"\n{'='*60}")
    print(f"  {passed} passed  {failed} failed  ({passed + failed} total)")
    if failed:
        sys.exit(1)
    print("  ALL TESTS PASSED")

# -----------------------------------------------------------------------
# Audit JSON serialisation - evidence metadata completeness
# -----------------------------------------------------------------------

def test_audit_json_evidence_fields_complete() -> None:
    """
    save_audit_json() must serialise all required EvidenceItem fields for
    every agent finding (DOCX section 7.6 audit requirement).

    Required fields (all 12):
        source_title, authority, jurisdiction, document_type, section,
        excerpt, date_issued, effective, amendment_note, url,
        chunk_id, relevance_score

    The test injects a known EvidenceItem into an AgentFinding, builds a
    minimal AuditRecord, serialises it with save_audit_json(), reads the
    resulting JSON, and asserts every required field is present with the
    correct value.
    """
    import json, os, tempfile
    from datetime import datetime, timezone
    from src.core.models import (
        EvidenceItem, AgentFinding, AgentID,
        VerifierResult, CoordinatorAssessment, AuditRecord,
    )
    from scenarios.scenario2_healthcare_5g import get_chunk
    from src.utils.output_formatter import save_audit_json

    REQUIRED_FIELDS = [
        "source_title", "authority", "jurisdiction", "document_type",
        "section", "excerpt", "date_issued", "effective",
        "amendment_note", "url", "chunk_id", "relevance_score",
    ]

    ev = EvidenceItem(
        source_title    = "Telecommunications Act, 2023",
        authority       = "Government of India",
        jurisdiction    = "India",
        document_type   = "Act",
        section         = "Section 22(1)",
        excerpt         = "A telecommunication entity shall...",
        date_issued     = "2023-12-26",
        effective       = True,
        amendment_note  = "",
        url             = "https://indiacode.nic.in/handle/123456789/18676",
        chunk_id        = "test-chunk-001",
        relevance_score = 0.87,
    )

    finding = AgentFinding(
        agent_id  = AgentID.TECHNICAL,
        chunk_id  = "scenario2_T0",
        summary   = "Test finding with real evidence.",
        claims    = ["Test claim backed by evidence."],
        evidence  = [ev],
    )

    chunk = get_chunk(0)
    record = AuditRecord(
        chunk_id               = "scenario2_T0",
        timestamp              = datetime.now(timezone.utc).isoformat(),
        active_agents          = [AgentID.TECHNICAL],
        agent_findings         = [finding],
        verifier_result        = VerifierResult(chunk_id="scenario2_T0"),
        coordinator_assessment = CoordinatorAssessment(
            chunk_id      = "scenario2_T0",
            active_agents = [AgentID.TECHNICAL],
        ),
        raw_chunk = chunk,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        path = save_audit_json(record, output_dir=tmpdir)
        assert os.path.isfile(path), f"Audit JSON file not created at {path}"
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)

    findings_json = data.get("agent_findings", [])
    assert findings_json, "agent_findings must be present in the JSON"

    tech = next(
        (f for f in findings_json if f.get("agent_id") == "technical"), None
    )
    assert tech is not None, "Technical agent finding not found in JSON"

    ev_list = tech.get("evidence", [])
    assert ev_list, (
        "agent_findings[technical].evidence must be serialised and non-empty. "
        "save_audit_json() must include full evidence metadata, not just a count."
    )

    item = ev_list[0]

    for field in REQUIRED_FIELDS:
        assert field in item, (
            f"Required EvidenceItem field '{field}' missing from audit JSON. "
            f"Present keys: {sorted(item.keys())}"
        )

    assert item["source_title"]    == "Telecommunications Act, 2023"
    assert item["authority"]       == "Government of India"
    assert item["jurisdiction"]    == "India"
    assert item["document_type"]   == "Act"
    assert item["section"]         == "Section 22(1)"
    assert item["excerpt"]         == "A telecommunication entity shall..."
    assert item["date_issued"]     == "2023-12-26"
    assert item["effective"]       is True
    assert item["amendment_note"]  == ""
    assert item["url"]             == "https://indiacode.nic.in/handle/123456789/18676"
    assert item["chunk_id"]        == "test-chunk-001"
    assert abs(item["relevance_score"] - 0.87) < 1e-9

    assert "evidence_count" in tech, (
        "evidence_count must be retained alongside the full evidence list"
    )
    assert tech["evidence_count"] == 1
