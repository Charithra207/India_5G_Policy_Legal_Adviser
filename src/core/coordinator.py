"""
Coordinator
===========
Implements the Coordinator's synthesis role described in DOCX §3.6 and
Annex-1 A.1 Table A1.

Responsibilities
----------------
After the Verifier produces its result, the Coordinator:
  1. Receives specialist findings, verified evidence, cross-domain
     relationships, conflicts, uncertainties, and policy-gap observations.
  2. Combines them into ONE unified CoordinatorAssessment.
  3. Keeps the five output categories STRICTLY SEPARATE:
       - Confirmed facts
       - Evidence-backed conclusions
       - Uncertain conclusions
       - Conflicting findings
       - Potential policy gaps
  4. Preserves uncertainty rather than inventing certainty.
  5. When incident information changes, re-issues the assessment and
     makes earlier conclusions VISIBLY updated rather than silently
     discarded.
  6. Surfaces relevant institutions.
  7. Attaches an evidence trail linking each major conclusion to the
     incident fact, source document, and section.
  8. Always includes a human-review note (DOCX A.2).

Output categories map
---------------------
VERIFIED claims     → evidence_backed_conclusions
INCOMPLETE claims   → uncertain_conclusions
UNSUPPORTED claims  → uncertain_conclusions (marked "insufficient evidence")
CONFLICT claims     → conflicting_findings (both sides, with evidence)
Policy Gap findings → potential_policy_gaps
Scenario facts      → confirmed_facts (not claims — raw incident facts,
                      accumulated over the chunks released so far)

Progressive reassessment
------------------------
Each chunk's assessment covers the whole incident so far.  Claims of agents
that ran in an earlier chunk and not in this one are carried forward under
their last outcome, tagged "[carried forward from <chunk> — not
re-examined]".  Claims an agent no longer makes when it runs again are
reported as superseded.  `changes_from_prior` is computed by comparing this
assessment with the previous one: agents, incident flags, newly cited
provisions, re-rated claims, cross-domain links, conflicts and gaps.
"""

from __future__ import annotations

import re

import logging
from typing import Optional

from src.core.models import (
    AgentFinding, AgentID, ClaimRef, ConflictRecord, CoordinatorAssessment,
    ScenarioChunk, VerifierOutcome, VerifierResult,
)

logger = logging.getLogger(__name__)

_FLAG_CHANGES = (
    ("cyber_event_suspected",
     "Incident reassessed as a possible security event: security indicators "
     "appear in the information released in this chunk."),
    ("cii_flagged",
     "Critical-service relevance appears for the first time in this chunk."),
    ("data_exposure_suspected",
     "Possible personal-data involvement appears for the first time in this chunk."),
)



_ACRONYM = re.compile(r"\(([A-Z][A-Za-z\-]{1,11})\)")


def _institution_key(name: str) -> str:
    """'National … Centre (NCIIPC)', 'NCIIPC' and 'NCIIPC (if …)' share the key 'nciipc'."""
    m = _ACRONYM.search(name)
    return (m.group(1) if m else name.split(" (", 1)[0]).strip().lower()


class Coordinator:
    """
    Combines verified multi-agent findings into a single unified assessment.

    Design note: The Coordinator does NOT generate new analysis.  It
    organises what the Verifier has validated into the five DOCX categories.
    Uncertainty is preserved, never papered over.
    """

    # ------------------------------------------------------------------
    # Public entry point — called by Orchestrator
    # ------------------------------------------------------------------

    def synthesize(
        self,
        chunk: ScenarioChunk,
        findings: list[AgentFinding],
        verifier_result: VerifierResult,
        incident_state: dict,
        prior_assessment: Optional[CoordinatorAssessment] = None,
    ) -> CoordinatorAssessment:
        """
        Produce the unified policy assessment for this chunk.

        Parameters
        ----------
        chunk            : current ScenarioChunk
        findings         : raw AgentFindings (for supplementary context)
        verifier_result  : VerifierResult from the Verifier
        incident_state   : shared incident state
        prior_assessment : previous chunk's assessment (for reassessment)

        Returns
        -------
        CoordinatorAssessment with five separated categories.
        """
        logger.info("Coordinator: synthesizing assessment for chunk %s", chunk.chunk_id)

        active_agents = [f.agent_id for f in findings]
        register = self._build_register(chunk, active_agents,
                                        verifier_result.verified_claims, prior_assessment)
        current = [r for r in register if not r["carried_forward"]]
        carried = [r for r in register if r["carried_forward"]]

        # Category 1: confirmed facts — the incident facts released so far
        confirmed_facts = self._confirmed_facts(chunk, prior_assessment)

        # Categories 2 & 3: by Verifier outcome (current, then carried forward).
        # A finding on either side of a conflict — including an earlier one
        # carried forward — is withheld from both: it appears only as a side
        # of the conflict.
        in_conflict = {(side.agent_id.value, side.claim)
                       for r in verifier_result.conflict_details
                       for side in (r.finding_a, r.finding_b)}
        for entry in register:
            entry["in_conflict"] = (entry["agent_id"], entry["claim"]) in in_conflict
        evidence_backed, uncertain = self._classify(current + carried)

        # Category 4: conflicts — both sides kept, neither adopted
        conflicting = self._conflicting(verifier_result.conflict_details, carried)

        # Category 5: potential policy gaps
        policy_gaps = self._extract_policy_gaps(findings)
        if AgentID.POLICY_GAP not in active_agents and prior_assessment:
            policy_gaps = [g for g in prior_assessment.potential_policy_gaps]

        # Cross-domain relationships: this chunk's, plus earlier ones between
        # agents that have not run again (still the latest reading)
        links = [{"note": l.note, "agents": [a.value for a in l.agents],
                  "chunk_id": chunk.chunk_id}
                 for l in verifier_result.cross_domain_details]
        if prior_assessment:
            seen = {l["note"] for l in links}
            for old in prior_assessment.link_register:
                if (not set(old["agents"]) & {a.value for a in active_agents}
                        and old["note"] not in seen):
                    links.append({**old})
        cross_domain = [
            l["note"] if l["chunk_id"] == chunk.chunk_id
            else f"[carried forward from {l['chunk_id']}] {l['note']}"
            for l in links
        ]

        flags = {key: bool(incident_state.get(key)) for key, _ in _FLAG_CHANGES}
        open_questions = self._open_questions(verifier_result, evidence_backed)

        assessment = CoordinatorAssessment(
            chunk_id                    = chunk.chunk_id,
            active_agents               = active_agents,
            confirmed_facts             = confirmed_facts,
            evidence_backed_conclusions = evidence_backed,
            uncertain_conclusions       = uncertain,
            conflicting_findings        = conflicting,
            potential_policy_gaps       = policy_gaps,
            cross_domain_relationships  = cross_domain,
            relevant_institutions       = self._collect_institutions(findings, prior_assessment),
            open_questions              = open_questions,
            claim_register              = register,
            incident_flags              = flags,
            link_register               = links,
        )
        assessment.changes_from_prior = self._compute_changes(
            assessment, prior_assessment, verifier_result)

        logger.info(
            "Coordinator: chunk %s — confirmed_facts=%d evidence_backed=%d "
            "uncertain=%d conflicting=%d policy_gaps=%d carried_forward=%d",
            chunk.chunk_id, len(confirmed_facts), len(evidence_backed),
            len(uncertain), len(conflicting), len(policy_gaps), len(carried),
        )
        return assessment

    # ------------------------------------------------------------------
    # Claim register — what is asserted now, and what is carried forward
    # ------------------------------------------------------------------

    def _build_register(self, chunk, active_agents, verified_claims,
                        prior: Optional[CoordinatorAssessment]) -> list[dict]:
        register = [{
            "agent_id": vc.agent_id.value,
            "claim": vc.claim,
            "outcome": vc.outcome.value,
            "rationale": vc.rationale,
            "citations": sorted({f"{e.source_title}, {e.section}"
                                 for e in vc.supporting_evidence}),
            "chunk_id": chunk.chunk_id,
            "carried_forward": False,
        } for vc in verified_claims]
        if prior:
            active = {a.value for a in active_agents}
            register += [{**r, "carried_forward": True} for r in prior.claim_register
                         if r["agent_id"] not in active]
        return register

    # ------------------------------------------------------------------
    # Category builders
    # ------------------------------------------------------------------

    def _confirmed_facts(self, chunk: ScenarioChunk,
                         prior: Optional[CoordinatorAssessment]) -> list[str]:
        """
        Confirmed facts = the raw incident facts released so far.  These are
        what the scenario actually states — not agent inferences (e.g. the
        Technical Agent's inferred components), which reach the assessment
        only as claims classified by their Verifier outcome.
        """
        facts = list(prior.confirmed_facts) if prior else []
        facts.append(f"[Incident fact — {chunk.chunk_id}] {chunk.description}")
        facts += [f"[New fact — {chunk.chunk_id}] {nf}" for nf in chunk.new_facts]
        return facts

    @staticmethod
    def _statement(entry: dict) -> str:
        outcome = entry["outcome"]
        label = (f"{outcome} — insufficient evidence; preliminary only"
                 if outcome == VerifierOutcome.UNSUPPORTED.value else outcome)
        prefix = (f"[carried forward from {entry['chunk_id']} — not re-examined] "
                  if entry["carried_forward"] else "")
        return f"{prefix}[{entry['agent_id'].upper()} | {label}] {entry['claim']}"

    def _classify(self, register: list[dict]) -> tuple[list[str], list[str]]:
        """VERIFIED → evidence-backed; INCOMPLETE / UNSUPPORTED → uncertain."""
        evidence_backed: list[str] = []
        uncertain: list[str] = []
        for entry in register:
            if entry["outcome"] == VerifierOutcome.CONFLICT.value or entry.get("in_conflict"):
                continue
            statement = self._statement(entry)
            if entry["outcome"] == VerifierOutcome.VERIFIED.value:
                if entry["citations"]:
                    statement += f" (Evidence: {'; '.join(entry['citations'])})"
                evidence_backed.append(statement)
            else:
                note = entry["rationale"]
                note = note if len(note) <= 160 else note[:160] + "…"
                uncertain.append(f"{statement} (Verification note: {note})")
        return evidence_backed, uncertain

    def _conflicting(self, records: list[ConflictRecord],
                     carried: list[dict]) -> list[str]:
        """Each conflict with both findings, their evidence and its treatment."""
        out = [render_conflict_block(r) for r in records]
        out += [self._statement(e) + f"\n  → Conflict note: {e['rationale']}"
                for e in carried
                if e["outcome"] == VerifierOutcome.CONFLICT.value and not e.get("in_conflict")]
        return out

    def _extract_policy_gaps(self, findings: list[AgentFinding]) -> list[str]:
        """
        Collect policy gap statements from the Policy Gap Agent's findings.
        Gaps are stated as potential — never as conclusive inadequacy.
        """
        gaps: list[str] = []
        for finding in findings:
            if finding.agent_id != AgentID.POLICY_GAP:
                continue
            for claim in finding.claims:
                # Raised gaps rest on Canonical KB examination; candidate areas
                # that could not be examined are listed separately so they are
                # never mistaken for evidence-backed gaps.
                if claim.startswith("Potential gap"):
                    gaps.append(f"[POLICY GAP — for expert review] {claim}")
                elif claim.startswith("Candidate area NOT EXAMINED"):
                    gaps.append(f"[CANDIDATE GAP AREA — not examined] {claim}")
            if finding.gap_description:
                gaps.append(
                    f"[GAP SUMMARY — {finding.gap_category.value if finding.gap_category else 'unclassified'}] "
                    f"{finding.gap_description}"
                )
        return gaps

    def _collect_institutions(self, findings: list[AgentFinding],
                              prior: Optional[CoordinatorAssessment]) -> list[str]:
        """Institutions named so far, deduplicated, in order of appearance."""
        names = list(prior.relevant_institutions) if prior else []
        for finding in findings:
            names += finding.responsible_institutions
        # One entry per institution: "NCIIPC", "National Critical Information
        # Infrastructure Protection Centre (NCIIPC)" and "NCIIPC (if critical
        # infrastructure is confirmed)" are the same body; the full name wins.
        chosen: dict[str, str] = {}
        for name in dict.fromkeys(names):
            key = _institution_key(name)
            if key not in chosen or (_ACRONYM.search(name) and not _ACRONYM.search(chosen[key])):
                chosen[key] = name
        return list(chosen.values())

    def _open_questions(self, result: VerifierResult, evidence_backed: list[str]) -> list[str]:
        questions = []
        if not evidence_backed:
            questions.append(
                "No conclusion is evidence-backed at this stage: no claim was found "
                "supported by an authoritative source whose in-force status and "
                "amendments have been checked. Every conclusion below is uncertain "
                "or preliminary."
            )
        questions += list(dict.fromkeys(result.missing_evidence))
        return questions

    # ------------------------------------------------------------------
    # Reassessment
    # ------------------------------------------------------------------

    def _compute_changes(self, now: CoordinatorAssessment,
                         prior: Optional[CoordinatorAssessment],
                         result: VerifierResult) -> list[str]:
        """
        What changed from the previous chunk's assessment, computed by
        comparison — never assumed (DOCX §3.6: earlier conclusions are
        updated visibly rather than silently discarded).
        """
        if prior is None:
            return ["Initial assessment — no prior chunk to compare against."]
        changes: list[str] = []
        before_agents = {a.value for a in prior.active_agents}
        now_agents = {a.value for a in now.active_agents}

        if now_agents - before_agents:
            changes.append("Newly activated agents: " + ", ".join(sorted(now_agents - before_agents))
                           + " (selected from the information released in this chunk).")
        if before_agents - now_agents:
            changes.append("Not active in this chunk: " + ", ".join(sorted(before_agents - now_agents))
                           + "; their latest conclusions are carried forward, not re-examined.")

        for key, text in _FLAG_CHANGES:
            if now.incident_flags.get(key) and not prior.incident_flags.get(key):
                changes.append(text)

        cited_before = {c for r in prior.claim_register for c in r["citations"]}
        cited_now = {c for r in now.claim_register if not r["carried_forward"]
                     for c in r["citations"]}
        if cited_now - cited_before:
            new = sorted(cited_now - cited_before)
            changes.append(f"New evidence considered ({len(new)} provision(s)): "
                           + "; ".join(new[:8]) + (" …" if len(new) > 8 else ""))

        before = {(r["agent_id"], r["claim"]): r for r in prior.claim_register}
        current = [r for r in now.claim_register if not r["carried_forward"]]
        for r in current:
            old = before.get((r["agent_id"], r["claim"]))
            if old and old["outcome"] != r["outcome"]:
                changes.append(f"Re-rated: [{r['agent_id']}] {r['outcome']} (was "
                               f"{old['outcome']} at {old['chunk_id']}) — {r['claim'][:140]}")
        now_keys = {(r["agent_id"], r["claim"]) for r in current}
        superseded = [r for r in prior.claim_register
                      if r["agent_id"] in now_agents and (r["agent_id"], r["claim"]) not in now_keys]
        if superseded:
            by_agent: dict[str, int] = {}
            for r in superseded:
                by_agent[r["agent_id"]] = by_agent.get(r["agent_id"], 0) + 1
            changes.append("Superseded on reassessment (no longer asserted): "
                           + ", ".join(f"{a} {n} claim(s)" for a, n in sorted(by_agent.items())))

        old_links = {l["note"] for l in prior.link_register}
        new_links = [l for l in result.cross_domain_details if l.note not in old_links]
        if new_links:
            kinds = sorted({f"{l.agents[0].value} ↔ {l.agents[1].value} ({l.kind.replace('_', ' ')})"
                            for l in new_links})
            changes.append(f"New cross-domain relationships ({len(new_links)}): " + "; ".join(kinds))
        if result.conflict_details:
            changes.append(f"Conflicts detected in this chunk: {len(result.conflict_details)} "
                           "— both findings shown; none resolved by the Coordinator.")
        elif prior.conflicting_findings and not now.conflicting_findings:
            changes.append("Conflicts reported earlier are no longer present in the "
                           "reassessed findings.")

        new_gaps = [g for g in now.potential_policy_gaps if g not in prior.potential_policy_gaps]
        if new_gaps:
            changes.append(f"Potential policy gaps raised for expert review: {len(new_gaps)}.")

        if not changes:
            changes.append("Assessment re-issued with the new chunk facts; no agent, "
                           "evidence or outcome changed.")
        return changes


# ---------------------------------------------------------------------------
# Conflict rendering
# ---------------------------------------------------------------------------

def _side(label: str, ref: ClaimRef) -> list[str]:
    lines = [f"  {label}: [{ref.agent_id.value}, {ref.chunk_id}] {ref.claim}"]
    if ref.evidence:
        for e in ref.evidence[:3]:
            excerpt = " ".join(e.excerpt.split())
            excerpt = excerpt if len(excerpt) <= 220 else excerpt[:220] + "…"
            lines.append(f"    Evidence: {e.source_title}, {e.section}: \"{excerpt}\"")
    else:
        lines.append("    Evidence: none cited")
    return lines


def render_conflict_block(record: ConflictRecord) -> str:
    """A conflict as the Coordinator presents it: A, B, evidence, status, treatment."""
    return "\n".join(
        [f"[CONFLICT — {record.rule}] {record.basis}"]
        + _side("Finding A", record.finding_a)
        + _side("Finding B", record.finding_b)
        + [f"  Status: {record.status}",
           f"  Coordinator treatment: {record.coordinator_treatment}"]
    )
