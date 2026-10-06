"""
Output Formatter
================
Renders an AuditRecord into human-readable text and JSON for:
  - Console output (test runner)
  - File output (outputs/ directory)
  - UI layer consumption

All five Coordinator categories are rendered with clear section headers
and verification outcome labels so the epistemic weight of each statement
is immediately visible.
"""

from __future__ import annotations

import json

from src.core.models import (
    AuditRecord, VerifierOutcome, VerifierResult,
)


SEPARATOR = "=" * 72
THIN_SEP  = "-" * 72


def format_audit_record(record: AuditRecord, include_raw_findings: bool = False) -> str:
    """
    Render a full audit record as a human-readable string.

    Parameters
    ----------
    record               : the AuditRecord to format
    include_raw_findings : if True, include full per-agent finding text
    """
    lines: list[str] = []

    lines.append(SEPARATOR)
    lines.append("INDIA 5G POLICY & LEGAL ADVISER — ASSESSMENT REPORT")
    lines.append(SEPARATOR)
    lines.append(f"Chunk ID   : {record.chunk_id}")
    lines.append(f"Timestamp  : {record.timestamp}")
    lines.append(
        "Active Agents: "
        + ", ".join(a.value for a in record.active_agents)
    )
    lines.append("")

    # ----------------------------------------------------------------
    # Scenario chunk
    # ----------------------------------------------------------------
    lines.append("SCENARIO INFORMATION RELEASED THIS CHUNK")
    lines.append(THIN_SEP)
    lines.append(f"Description: {record.raw_chunk.description}")
    if record.raw_chunk.new_facts:
        lines.append("New facts:")
        for fact in record.raw_chunk.new_facts:
            lines.append(f"  • {fact}")
    lines.append("")

    # ----------------------------------------------------------------
    # Changes from prior chunk
    # ----------------------------------------------------------------
    a = record.coordinator_assessment
    if a.changes_from_prior:
        lines.append("CHANGES FROM PRIOR ASSESSMENT")
        lines.append(THIN_SEP)
        for change in a.changes_from_prior:
            lines.append(f"  ▶ {change}")
        lines.append("")

    # ----------------------------------------------------------------
    # Coordinator Assessment — five categories
    # ----------------------------------------------------------------
    lines.append("COORDINATOR ASSESSMENT")
    lines.append(SEPARATOR)

    _render_category(lines, "1. CONFIRMED FACTS", a.confirmed_facts,
                     empty_msg="No confirmed facts at this stage.")

    _render_category(lines, "2. EVIDENCE-BACKED CONCLUSIONS", a.evidence_backed_conclusions,
                     empty_msg="No evidence-backed conclusions at this stage.")

    _render_category(lines, "3. UNCERTAIN CONCLUSIONS", a.uncertain_conclusions,
                     empty_msg="No uncertain conclusions at this stage.")

    _render_category(lines, "4. CONFLICTING FINDINGS", a.conflicting_findings,
                     empty_msg="No conflicting findings identified.")

    _render_category(lines, "5. POTENTIAL POLICY GAPS", a.potential_policy_gaps,
                     empty_msg="No policy gaps identified at this stage.")

    # ----------------------------------------------------------------
    # Cross-domain relationships
    # ----------------------------------------------------------------
    if a.cross_domain_relationships:
        lines.append("CROSS-DOMAIN RELATIONSHIPS")
        lines.append(THIN_SEP)
        for rel in a.cross_domain_relationships:
            lines.append(f"  ⇌ {rel}")
        lines.append("")

    # ----------------------------------------------------------------
    # Relevant institutions
    # ----------------------------------------------------------------
    if a.relevant_institutions:
        lines.append("RELEVANT INSTITUTIONS")
        lines.append(THIN_SEP)
        for inst in a.relevant_institutions:
            lines.append(f"  • {inst}")
        lines.append("")

    # ----------------------------------------------------------------
    # Verifier summary
    # ----------------------------------------------------------------
    lines.append("VERIFICATION SUMMARY")
    lines.append(THIN_SEP)
    _render_verifier_summary(lines, record.verifier_result)
    lines.append("")

    # ----------------------------------------------------------------
    # Human review note — always present
    # ----------------------------------------------------------------
    lines.append("HUMAN REVIEW NOTICE")
    lines.append(THIN_SEP)
    lines.append(a.human_review_required)
    lines.append("")

    # ----------------------------------------------------------------
    # Optional: raw agent findings
    # ----------------------------------------------------------------
    if include_raw_findings:
        lines.append("RAW AGENT FINDINGS (for audit)")
        lines.append(THIN_SEP)
        for finding in record.agent_findings:
            lines.append(f"\n  [{finding.agent_id.value.upper()}]")
            lines.append(f"  Summary: {finding.summary}")
            if finding.claims:
                lines.append("  Claims:")
                for c in finding.claims:
                    lines.append(f"    – {c}")
            if finding.uncertainty_notes:
                lines.append("  Uncertainty notes:")
                for u in finding.uncertainty_notes:
                    lines.append(f"    ⚠ {u}")
            if finding.missing_facts:
                lines.append("  Missing facts:")
                for m in finding.missing_facts:
                    lines.append(f"    ? {m}")
        lines.append("")

    lines.append(SEPARATOR)
    return "\n".join(lines)


def _render_category(
    lines: list[str],
    title: str,
    items: list[str],
    empty_msg: str = "None.",
) -> None:
    lines.append(title)
    lines.append(THIN_SEP)
    if items:
        for item in items:
            lines.append(f"  • {item}")
    else:
        lines.append(f"  {empty_msg}")
    lines.append("")


def _render_verifier_summary(lines: list[str], result: VerifierResult) -> None:
    counts = {o: 0 for o in VerifierOutcome}
    for vc in result.verified_claims:
        counts[vc.outcome] += 1

    lines.append(
        f"  Claims checked : {len(result.verified_claims)}"
    )
    lines.append(
        f"  VERIFIED       : {counts[VerifierOutcome.VERIFIED]}"
    )
    lines.append(
        f"  INCOMPLETE     : {counts[VerifierOutcome.INCOMPLETE]}"
    )
    lines.append(
        f"  UNSUPPORTED    : {counts[VerifierOutcome.UNSUPPORTED]}"
    )
    lines.append(
        f"  CONFLICT       : {counts[VerifierOutcome.CONFLICT]}"
    )
    if result.missing_evidence:
        lines.append("  Missing evidence notes:")
        for me in result.missing_evidence[:5]:   # cap for readability
            lines.append(f"    ⚠ {me}")
    if result.cross_domain_links:
        lines.append(f"  Cross-domain links flagged: {len(result.cross_domain_links)}")


def save_assessment_text(record: AuditRecord, output_dir: str = "outputs") -> str:
    """Save the formatted assessment to a .txt file. Returns the file path."""
    import os
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{record.chunk_id}_assessment.txt"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write(format_audit_record(record, include_raw_findings=True))
    return filepath


def save_audit_json(record: AuditRecord, output_dir: str = "outputs") -> str:
    """
    Save a JSON audit record for replay and downstream processing.

    Each agent finding includes the full evidence metadata for every
    retrieved EvidenceItem (DOCX §7.6 audit requirement).  The serialised
    fields are exactly those defined on EvidenceItem in src/core/models.py:
        source_title, authority, jurisdiction, document_type, section,
        excerpt, date_issued, effective, amendment_note, url,
        chunk_id, relevance_score.

    No hidden chain-of-thought or private model reasoning is stored.
    Returns the file path.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{record.chunk_id}_audit.json"
    filepath = os.path.join(output_dir, filename)

    def _serialise_evidence(e) -> dict:
        """Serialise one EvidenceItem to a dict with all required fields."""
        return {
            "source_title"   : e.source_title,
            "authority"      : e.authority,
            "jurisdiction"   : e.jurisdiction,
            "document_type"  : e.document_type,
            "section"        : e.section,
            "excerpt"        : e.excerpt,
            "date_issued"    : e.date_issued,
            "effective"      : e.effective,
            "amendment_note" : e.amendment_note,
            "url"            : e.url,
            "chunk_id"       : e.chunk_id,
            "relevance_score": e.relevance_score,
        }

    data = {
        "chunk_id"             : record.chunk_id,
        "timestamp"            : record.timestamp,
        "active_agents"        : [a.value for a in record.active_agents],
        "scenario_description" : record.raw_chunk.description,
        "new_facts"            : record.raw_chunk.new_facts,
        "coordinator_assessment": {
            "confirmed_facts"            : record.coordinator_assessment.confirmed_facts,
            "evidence_backed_conclusions": record.coordinator_assessment.evidence_backed_conclusions,
            "uncertain_conclusions"      : record.coordinator_assessment.uncertain_conclusions,
            "conflicting_findings"       : record.coordinator_assessment.conflicting_findings,
            "potential_policy_gaps"      : record.coordinator_assessment.potential_policy_gaps,
            "cross_domain_relationships" : record.coordinator_assessment.cross_domain_relationships,
            "relevant_institutions"      : record.coordinator_assessment.relevant_institutions,
            "changes_from_prior"         : record.coordinator_assessment.changes_from_prior,
        },
        "verifier_summary": {
            "total_claims"      : len(record.verifier_result.verified_claims),
            "VERIFIED"          : sum(1 for v in record.verifier_result.verified_claims
                                      if v.outcome == VerifierOutcome.VERIFIED),
            "INCOMPLETE"        : sum(1 for v in record.verifier_result.verified_claims
                                      if v.outcome == VerifierOutcome.INCOMPLETE),
            "UNSUPPORTED"       : sum(1 for v in record.verifier_result.verified_claims
                                      if v.outcome == VerifierOutcome.UNSUPPORTED),
            "CONFLICT"          : sum(1 for v in record.verifier_result.verified_claims
                                      if v.outcome == VerifierOutcome.CONFLICT),
            "cross_domain_links": record.verifier_result.cross_domain_links,
            "conflicts"         : record.verifier_result.conflicts,
            "missing_evidence"  : record.verifier_result.missing_evidence,
        },
        # Per-claim outcome and the authoritative passages behind it (DOCX §7.6)
        "verified_claims": [
            {
                "agent_id"            : v.agent_id.value,
                "claim"               : v.claim,
                "outcome"             : v.outcome.value,
                "rationale"           : v.rationale,
                "supporting_evidence" : [_serialise_evidence(e) for e in v.supporting_evidence],
                "conflicting_evidence": [_serialise_evidence(e) for e in v.conflicting_evidence],
                "cross_domain_flag"   : v.cross_domain_flag,
            }
            for v in record.verifier_result.verified_claims
        ],
        "agent_findings": [
            {
                "agent_id"         : f.agent_id.value,
                "summary"          : f.summary,
                "claims"           : f.claims,
                "claim_citations"  : {
                    claim: [f"{e.source_title}, {e.section}" for e in items]
                    for claim, items in f.claim_citations.items()
                },
                "uncertainty_notes": f.uncertainty_notes,
                "missing_facts"    : f.missing_facts,
                "evidence_count"   : len(f.evidence),
                "evidence"         : [_serialise_evidence(e) for e in f.evidence],
            }
            for f in record.agent_findings
        ],
    }

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return filepath
