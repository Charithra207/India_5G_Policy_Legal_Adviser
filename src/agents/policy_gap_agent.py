"""
Policy Gap Agent
=================
Mandate (DOCX §3.3, §5.1):
    Identify potential gaps, ambiguities, overlaps, or areas needing further
    policy consideration.

    - Raises evidence-backed issues: unclear coverage, institutional
      responsibility gaps, emerging technology not explicitly addressed,
      overlaps, differences from international standards
    - Uses terms such as "potential gap" and "regulatory ambiguity"
    - NEVER declares an Indian policy inadequate outright

Inputs (DOCX §3.7):
    - Verified findings from other agents
    - International Standards KB
    - Canonical KB (for confirming what Indian provisions say)
    - International Policy Examples KB

Knowledge Base: Policy Gap KB (International policy examples +
neighbouring-country comparative instruments)

This agent is activated AFTER verification (it needs verified findings as
input).  The Orchestrator supplies verified findings in incident_state.
"""

from __future__ import annotations

from typing import Optional

from dataclasses import dataclass

from src.core.models import (
    AgentFinding, AgentID, CoverageCategory, EvidenceItem, ScenarioChunk,
)
from src.knowledge_base.base_kb import CanonicalKnowledgeBase, KnowledgeBase
from src.knowledge_base.text_match import mentions
from .base_agent import BaseAgent


_CATEGORY_LABEL = {
    CoverageCategory.EXPLICIT_COVERAGE:             "Explicit coverage",
    CoverageCategory.PARTIAL_COVERAGE:              "Partial coverage",
    CoverageCategory.UNCLEAR_COVERAGE:              "Unclear coverage",
    CoverageCategory.OVERLAPPING_REQUIREMENTS:      "Overlapping requirements",
    CoverageCategory.MISSING_INSTITUTIONAL_CLARITY: "Missing institutional clarity",
    CoverageCategory.EMERGING_TECHNOLOGY:           "Emerging technology not explicitly addressed",
}

_REPORTING_WORDS = ("report", "notif", "inform")


@dataclass
class _GapResult:
    """Outcome of examining one candidate area against the Canonical KB."""
    claim     : str
    citations : list[EvidenceItem]
    raised    : Optional[CoverageCategory] = None   # set only when a potential gap is raised


class PolicyGapAgent(BaseAgent):

    MANDATE = (
        "Evidence-backed identification of potential policy gaps, ambiguities, "
        "overlaps, and emerging-technology coverage issues in the Indian "
        "regulatory framework, using international standards and policy "
        "examples as reference points only."
    )

    # Non-conclusive language enforced — never say "Indian policy is inadequate"
    GAP_DISCLAIMER = (
        "This is a potential gap or area of regulatory ambiguity identified "
        "for expert review. No conclusion of policy failure is drawn."
    )

    def __init__(
        self,
        kb: Optional[KnowledgeBase] = None,
        canonical_kb: Optional[CanonicalKnowledgeBase] = None,
        standards_kb: Optional[KnowledgeBase] = None,
    ) -> None:
        super().__init__(AgentID.POLICY_GAP, kb)
        # Read-only shared inputs (DOCX §7.1): the Canonical KB confirms what an
        # Indian provision says before anything is called unclear or not
        # explicitly addressed; the Standards KB supplies reference comparators.
        self.canonical_kb = canonical_kb
        self.standards_kb = standards_kb

    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        base = chunk.description
        return [
            base,
            "policy for 5G and next generation network technologies and their security",
            "coordination between agencies for cyber security incident response",
            "protection of critical information infrastructure as a national policy objective",
            "data protection and privacy in telecom and AI policy",
        ]

    # ------------------------------------------------------------------
    # Candidate areas — derived from verified findings, not assumed
    # ------------------------------------------------------------------

    @staticmethod
    def _candidate_areas(incident_state: dict) -> list[CoverageCategory]:
        findings = incident_state.get("verified_findings", [])
        text = " ".join(f["claim"] for f in findings).lower()
        areas: list[CoverageCategory] = []
        if "slice" in text or "slicing" in text:
            areas.append(CoverageCategory.EMERGING_TECHNOLOGY)
        if incident_state.get("cyber_event_suspected") and incident_state.get("data_exposure_suspected"):
            areas.append(CoverageCategory.OVERLAPPING_REQUIREMENTS)
        if incident_state.get("cyber_event_suspected") and incident_state.get("cii_flagged"):
            areas.append(CoverageCategory.MISSING_INSTITUTIONAL_CLARITY)
        return areas

    _AREA_WHY = {
        CoverageCategory.EMERGING_TECHNOLOGY:
            "verified findings involve a 5G network slice",
        CoverageCategory.OVERLAPPING_REQUIREMENTS:
            "the incident involves both a possible cybersecurity incident and "
            "possible personal-data exposure, which may each carry reporting duties",
        CoverageCategory.MISSING_INSTITUTIONAL_CLARITY:
            "the incident involves a possible cybersecurity incident on a service "
            "flagged as critical, which engages both CERT-In and NCIIPC",
    }

    # ------------------------------------------------------------------
    # Examination against the Canonical KB
    # ------------------------------------------------------------------

    def _indian_passages(self, query: str, top_k: int = 10) -> list[EvidenceItem]:
        hits = self.canonical_kb.retrieve(query, top_k=top_k, filters={"jurisdiction": "India"})
        return [e for e in self._real_evidence(hits)
                if e.jurisdiction.strip().lower() == "india"]

    @staticmethod
    def _ref(item: EvidenceItem) -> str:
        return f"{item.source_title}, {item.section}"

    @classmethod
    def _refs(cls, items: list[EvidenceItem]) -> str:
        """Distinct 'source, section' references, in order."""
        return "; ".join(dict.fromkeys(cls._ref(e) for e in items))

    @staticmethod
    def _distinct_sections(items: list[EvidenceItem]) -> list[EvidenceItem]:
        seen, out = set(), []
        for e in items:
            if (e.source_title, e.section) not in seen:
                seen.add((e.source_title, e.section))
                out.append(e)
        return out

    def _examine(self, area: CoverageCategory) -> _GapResult:
        label = _CATEGORY_LABEL[area]
        if area == CoverageCategory.EMERGING_TECHNOLOGY:
            # An absence claim needs every Indian passage, not a top-k sample
            corpus = self.canonical_kb.scan(filters={"jurisdiction": "India"})
            exhaustive = corpus is not None
            if not exhaustive:
                corpus = self._indian_passages("network slicing 5G slice")
            if not corpus:
                return self._not_examined(area, "no Indian passages were available for network slicing")
            naming = self._distinct_sections([e for e in corpus if mentions(e.excerpt, "slic")])
            if naming:
                return _GapResult(
                    claim=(
                        f"Coverage check — network slicing: {self._refs(naming[:5])} "
                        "mention network slicing. No potential gap is raised; whether the "
                        "coverage is explicit or partial is for expert review."
                    ),
                    citations=naming[:5],
                )
            sources = "; ".join(sorted({e.source_title for e in corpus}))
            scope = (f"the {len(corpus)} Indian passages in the Canonical KB (every one examined)"
                     if exhaustive else
                     f"the {len(corpus)} Indian passages most relevant to network slicing")
            return _GapResult(
                claim=(
                    f"Potential gap — {label}: none of {scope} mentions network slicing "
                    f"(instruments examined: {sources}). {self.GAP_DISCLAIMER}"
                ),
                citations=[], raised=area,
            )

        if area == CoverageCategory.OVERLAPPING_REQUIREMENTS:
            cyber = [e for e in self._indian_passages("cyber security incident reporting")
                     if any(w in e.excerpt.lower() for w in _REPORTING_WORDS)]
            data  = [e for e in self._indian_passages("personal data breach notification")
                     if any(w in e.excerpt.lower() for w in _REPORTING_WORDS)]
            pair = next(((c, d) for c in cyber for d in data
                         if c.source_title != d.source_title), None)
            if pair is None:
                return self._not_examined(
                    area, "reporting provisions were not retrieved for both the "
                          "cybersecurity and the data-protection instruments")
            c, d = pair
            cross_ref = mentions(c.excerpt, d.source_title) or mentions(d.excerpt, c.source_title)
            if cross_ref:
                return _GapResult(
                    claim=(
                        f"Coverage check — reporting: {self._ref(c)} and {self._ref(d)} both "
                        "carry reporting duties and one refers to the other. No potential gap "
                        "is raised; the relationship is for expert review."
                    ),
                    citations=[c, d],
                )
            return _GapResult(
                claim=(
                    f"Potential gap — {label}: {self._ref(c)} and {self._ref(d)} both carry "
                    "reporting duties for the same incident, and neither passage refers to "
                    "the other, so their relationship is unclear in the text examined. "
                    f"{self.GAP_DISCLAIMER}"
                ),
                citations=[c, d], raised=area,
            )

        # MISSING_INSTITUTIONAL_CLARITY — also an absence claim ("no passage
        # addresses both"), so scan every Indian passage when the KB allows it
        corpus = self.canonical_kb.scan(filters={"jurisdiction": "India"})
        exhaustive = corpus is not None
        if not exhaustive:
            corpus = self._indian_passages("NCIIPC CERT-In incident response coordination")
        both   = self._distinct_sections(
            [e for e in corpus if mentions(e.excerpt, "NCIIPC") and mentions(e.excerpt, "CERT-In")])
        nciipc = self._distinct_sections([e for e in corpus if mentions(e.excerpt, "NCIIPC")])
        certin = self._distinct_sections([e for e in corpus if mentions(e.excerpt, "CERT-In")])
        if both:
            return _GapResult(
                claim=(
                    f"Coverage check — institutional roles: {self._refs(both[:5])} "
                    "address NCIIPC and CERT-In together. No potential gap is raised; the "
                    "allocation of responsibility is for expert review."
                ),
                citations=both[:5],
            )
        if not (nciipc and certin):
            return self._not_examined(area, "passages naming both NCIIPC and CERT-In roles were not available")
        scope = (f"the {len(corpus)} Indian passages in the Canonical KB" if exhaustive
                 else f"the {len(corpus)} passages examined")
        return _GapResult(
            claim=(
                f"Potential gap — {label}: {self._ref(nciipc[0])} addresses NCIIPC and "
                f"{self._ref(certin[0])} addresses CERT-In, but none of {scope} "
                f"addresses both, so which institution leads is unclear in the text "
                f"examined. {self.GAP_DISCLAIMER}"
            ),
            citations=[nciipc[0], certin[0]], raised=area,
        )

    def _not_examined(self, area: CoverageCategory, reason: str) -> _GapResult:
        return _GapResult(
            claim=(
                f"Candidate area NOT EXAMINED — {_CATEGORY_LABEL[area]}: this area arises "
                f"because {self._AREA_WHY[area]}, but {reason}. No coverage "
                "classification is made; for expert review."
            ),
            citations=[],
        )

    # ------------------------------------------------------------------
    # Finding
    # ------------------------------------------------------------------

    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        uncertainty_notes = self._uncertainty_note_if_stub(evidence)
        claims: list[str] = []
        citations: dict[str, list[EvidenceItem]] = {}
        raised: list[_GapResult] = []

        canonical_live = bool(self.canonical_kb and self.canonical_kb.is_available())
        if not canonical_live:
            uncertainty_notes.append(
                "Canonical KB not populated: no candidate area can be examined, so no "
                "potential gap is raised (DOCX §7.1)."
            )

        areas = self._candidate_areas(incident_state)
        for area in areas:
            result = (self._examine(area) if canonical_live else
                      self._not_examined(area, "the Canonical KB is not populated"))
            claims.append(result.claim)
            if result.citations:
                citations[result.claim] = result.citations
            if result.raised:
                raised.append(result)

        if not areas:
            claims.append(
                "No candidate gap areas arise from the verified findings so far; "
                "for expert review as further facts are released."
            )

        # Reference comparators — only alongside a raised gap, and only
        # international material (Policy Gap KB or Standards KB).  Quoting adds
        # the "[REFERENCE ONLY — not Indian law]" label (DOCX §5.1 item 10).
        if raised:
            comparator_pool = list(evidence)
            if self.standards_kb is not None:
                for result in raised:
                    comparator_pool.extend(self.standards_kb.retrieve(result.claim, top_k=2))
            international = [e for e in comparator_pool
                             if e.jurisdiction.strip().lower() not in ("", "india")]
            comparator_claims, comparator_cites = self._cited_claims(international)
            for claim in comparator_claims[:2]:
                text = f"Comparator — {claim}"
                claims.append(text)
                citations[text] = comparator_cites[claim]
            if not comparator_claims:
                uncertainty_notes.append(
                    "No international comparator was retrieved for the raised gap(s); the "
                    "Policy Gap KB holds no international policy examples yet (see manifest)."
                )

        gap_category    = raised[0].raised if raised else None
        gap_description = " | ".join(r.claim.split(":", 1)[0] for r in raised)

        missing_facts = [
            "Final manifest of exact Indian instruments confirmed by KB retrieval.",
            "Neighbouring-country comparators from the Policy Gap KB "
            "(to be added during RAG/KB integration).",
        ]

        return AgentFinding(
            agent_id          = AgentID.POLICY_GAP,
            chunk_id          = chunk.chunk_id,
            summary           = (
                f"Policy gap assessment: {len(areas)} candidate area(s) from verified "
                f"findings; {len(raised)} potential gap(s) raised after Canonical KB "
                "examination. Potential gaps are for expert review, not conclusions "
                "of inadequacy."
            ),
            claims            = claims,
            evidence          = evidence,
            claim_citations   = citations,
            gap_category      = gap_category,
            gap_description   = gap_description,
            uncertainty_notes = uncertainty_notes,
            missing_facts     = missing_facts,
        )
