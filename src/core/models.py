"""
Core data models for the India 5G Policy & Legal Adviser.

These models define the structured data contracts exchanged between every
component in the pipeline: scenario chunks, agent findings, evidence items,
verifier outcomes, and the Coordinator's final assessment.

All structures are intentionally plain dataclasses so that the RAG/KB layer
can slot retrieved evidence directly into EvidenceItem without altering the
rest of the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class AgentID(str, Enum):
    """Canonical identifiers for every agent in the swarm, as listed in the DOCX."""
    TECHNICAL           = "technical"
    POLICY_LEGAL        = "policy_legal"
    CYBERSECURITY       = "cybersecurity"
    PRIVACY             = "privacy"
    CRITICAL_INFRA      = "critical_infrastructure"
    STANDARDS           = "standards"
    POLICY_GAP          = "policy_gap"


class VerifierOutcome(str, Enum):
    """
    The four outcomes the Verifier can assign to any claim (DOCX §3.5, Annex-1 A.1).

    VERIFIED    – the cited source exists and the relevant section supports the claim.
    UNSUPPORTED – the source does not support the claim or the source was not found.
    INCOMPLETE  – the source supports the claim but an amendment, exception, or
                  related provision is missing from the analysis.
    CONFLICT    – another finding or another source contradicts the claim.
    """
    VERIFIED     = "VERIFIED"
    UNSUPPORTED  = "UNSUPPORTED"
    INCOMPLETE   = "INCOMPLETE"
    CONFLICT     = "CONFLICT"


class CoverageCategory(str, Enum):
    """
    Policy-gap coverage categories used by the Policy Gap Agent (DOCX §5.1).
    """
    EXPLICIT_COVERAGE            = "explicit_coverage"
    PARTIAL_COVERAGE             = "partial_coverage"
    UNCLEAR_COVERAGE             = "unclear_coverage"
    OVERLAPPING_REQUIREMENTS     = "overlapping_requirements"
    MISSING_INSTITUTIONAL_CLARITY = "missing_institutional_clarity"
    EMERGING_TECHNOLOGY          = "emerging_technology_not_explicitly_addressed"


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """
    A single piece of retrieved evidence returned by an agent's RAG layer.

    The RAG/knowledge-base layer populates this from vector-store retrieval.
    The pipeline treats it as the ground truth against which the Verifier
    checks claims.

    Fields
    ------
    source_title    : human-readable document title
    authority       : the body that published the document (e.g. "Government of India")
    jurisdiction    : "India" or an international body name
    document_type   : "Act" | "Rule" | "Direction" | "Standard" | "Policy" | ...
    section         : specific provision or section number cited
    excerpt         : the verbatim or summarised passage retrieved
    date_issued     : ISO-8601 date string, e.g. "2023-12-26"
    effective       : whether the provision is currently in force
    amendment_note  : any known amendment that changes the passage
    url             : canonical URL for the source (empty string if not available)
    chunk_id        : vector-store chunk identifier (set by the RAG/KB layer)
    relevance_score : retrieval similarity score (0.0 – 1.0); 0.0 until RAG is live
    """
    source_title    : str
    authority       : str
    jurisdiction    : str
    document_type   : str
    section         : str
    excerpt         : str
    date_issued     : str         = ""
    effective       : bool        = True
    amendment_note  : str         = ""
    url             : str         = ""
    chunk_id        : str         = ""
    relevance_score : float       = 0.0


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------

@dataclass
class ScenarioChunk:
    """
    One time-separated chunk of incident information released to the swarm.

    The DOCX (§2.5, Annex-1 A.4) describes a four-chunk scenario.
    chunk_index is zero-based (T0 = 0, T1 = 1, T2 = 2, T3 = 3).
    """
    chunk_index     : int
    chunk_id        : str          # e.g. "scenario2_T0"
    timestamp       : str          # ISO-8601 datetime string
    description     : str          # the human-readable incident text released at this stage
    new_facts       : list[str]    = field(default_factory=list)
    prior_chunks    : list[str]    = field(default_factory=list)  # IDs of earlier chunks


# ---------------------------------------------------------------------------
# Agent findings
# ---------------------------------------------------------------------------

@dataclass
class AgentFinding:
    """
    The structured output produced by a single specialist agent for one chunk.

    An agent MUST populate only the fields within its defined mandate.
    Fields outside a mandate are left as empty string / empty list.
    The Verifier reads `claims` and checks each against `evidence`.
    """
    agent_id          : AgentID
    chunk_id          : str

    # Core analysis
    summary           : str                      = ""  # ≤ 3 sentences in the agent's mandate
    claims            : list[str]                = field(default_factory=list)  # discrete verifiable statements
    evidence          : list[EvidenceItem]       = field(default_factory=list)  # evidence retrieved from the agent's KB

    # Mandate-specific structured fields
    affected_components : list[str]             = field(default_factory=list)  # Technical
    incident_class      : str                   = ""                          # Technical
    applicable_provisions: list[str]            = field(default_factory=list)  # Policy & Legal
    responsible_institutions: list[str]         = field(default_factory=list)  # Policy & Legal / CII
    obligations         : list[str]             = field(default_factory=list)  # Policy & Legal / Cyber / Privacy / CII
    exposure_status     : str                   = ""                          # Privacy ("confirmed" | "suspected" | "unknown")
    cii_relevant        : Optional[bool]        = None                        # Critical Infrastructure
    standards_compared  : list[str]             = field(default_factory=list)  # Standards
    gap_category        : Optional[CoverageCategory] = None                  # Policy Gap
    gap_description     : str                   = ""                          # Policy Gap

    # Uncertainty
    uncertainty_notes   : list[str]             = field(default_factory=list)
    missing_facts       : list[str]             = field(default_factory=list)


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

@dataclass
class VerifiedClaim:
    """
    The Verifier's assessment of one claim from one agent's findings.
    """
    agent_id        : AgentID
    chunk_id        : str
    claim           : str
    outcome         : VerifierOutcome
    rationale       : str                          # why this outcome was assigned
    supporting_evidence : list[EvidenceItem]       = field(default_factory=list)
    conflicting_evidence: list[EvidenceItem]       = field(default_factory=list)
    cross_domain_flag   : bool                     = False  # True if this claim interacts with another domain
    cross_domain_note   : str                      = ""


@dataclass
class VerifierResult:
    """
    The complete output of the Verifier for one orchestration round.
    """
    chunk_id            : str
    verified_claims     : list[VerifiedClaim]      = field(default_factory=list)
    cross_domain_links  : list[str]                = field(default_factory=list)
    conflicts           : list[str]                = field(default_factory=list)
    missing_evidence    : list[str]                = field(default_factory=list)


# ---------------------------------------------------------------------------
# Coordinator output
# ---------------------------------------------------------------------------

@dataclass
class CoordinatorAssessment:
    """
    The Coordinator's unified policy assessment (DOCX §3.6, Annex-1 A.1 Table A1).

    The five categories are kept strictly separate so the reader can see the
    epistemic weight of each statement.
    """
    chunk_id                : str
    active_agents           : list[AgentID]

    # Table A1 categories
    confirmed_facts         : list[str]            = field(default_factory=list)
    evidence_backed_conclusions : list[str]        = field(default_factory=list)
    uncertain_conclusions   : list[str]            = field(default_factory=list)
    conflicting_findings    : list[str]            = field(default_factory=list)
    potential_policy_gaps   : list[str]            = field(default_factory=list)

    # Cross-domain relationships surfaced by the Verifier
    cross_domain_relationships : list[str]         = field(default_factory=list)

    # Institutional responsibilities
    relevant_institutions   : list[str]            = field(default_factory=list)

    # What changed relative to the previous chunk
    changes_from_prior      : list[str]            = field(default_factory=list)

    # Human-review note (always present per DOCX A.2)
    human_review_required   : str = (
        "Legal interpretation, regulatory decisions, and institutional "
        "action require qualified human judgment. This assessment is "
        "decision support only and does not replace legal counsel, "
        "regulators, or government decision-makers."
    )


# ---------------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------------

@dataclass
class AuditRecord:
    """
    Full audit trail for one chunk's pipeline run (DOCX §7.6).

    Stores enough information for a judge to replay the scenario: chunk ID,
    agent IDs active, inputs visible to each agent, retrieved passages,
    reasoning summaries, citations, verifier outcomes, cross-domain flags,
    and the Coordinator decision.
    """
    chunk_id            : str
    timestamp           : str
    active_agents       : list[AgentID]
    agent_findings      : list[AgentFinding]
    verifier_result     : VerifierResult
    coordinator_assessment : CoordinatorAssessment
    raw_chunk           : ScenarioChunk
