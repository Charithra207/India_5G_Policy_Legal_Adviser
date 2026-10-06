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
    date_issued     : date as stated in the document, e.g. "24th December, 2023"
    effective       : True = in force, False = not in force, None = in-force
                      status NOT verified (the honest default for ingested text)
    amendment_note  : any known amendment that changes the passage
    amendment_checked: True only if someone actually checked for amendments
    url             : canonical URL for the source (empty string if not available)
    chunk_id        : vector-store chunk identifier (set by the RAG/KB layer)
    relevance_score : retrieval similarity score (0.0 – 1.0); 0.0 until RAG is live
    section_title   : heading text of the section, as printed in the document
    page            : page(s) of the source file the passage came from
    related_documents: documents the source itself refers to (e.g. parent Act)
    institutions    : institutions with roles under the document
    domains         : subject areas (DOCX §7.2 "Domain")
    provenance_note : where the copy came from, and any caveat about it
    effective_status: the in-force status text and the document establishing it
    """
    source_title    : str
    authority       : str
    jurisdiction    : str
    document_type   : str
    section         : str
    excerpt         : str
    date_issued     : str         = ""
    effective       : Optional[bool] = True
    amendment_note  : str         = ""
    url             : str         = ""
    chunk_id        : str         = ""
    relevance_score : float       = 0.0
    amendment_checked : bool      = True
    section_title   : str         = ""
    page            : str         = ""
    related_documents : list[str] = field(default_factory=list)
    institutions    : list[str]   = field(default_factory=list)
    domains         : list[str]   = field(default_factory=list)
    provenance_note : str         = ""
    # In-force status as established by an obtained document (e.g. "in force
    # from 26 June 2024 (S.O. 2408(E))"); empty when not verified
    effective_status : str        = ""


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
    # claim text → the retrieved passages that claim cites.  A claim about
    # what a source says MUST appear here; the Verifier checks each cited
    # source/section against the Canonical KB.  Claims absent from this map
    # are the agent's own reading of the incident facts.
    claim_citations   : dict[str, list[EvidenceItem]] = field(default_factory=dict)

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
class ClaimRef:
    """One agent's finding as one side of a relationship or conflict."""
    agent_id  : AgentID
    chunk_id  : str                               # the chunk in which the agent made it
    claim     : str
    evidence  : list[EvidenceItem] = field(default_factory=list)


@dataclass
class CrossDomainLink:
    """
    A relationship between findings of two domains (DOCX §3.5), established
    from evidence — never from the mere fact that both agents are active.

    kind:
      shared_provision    – both findings cite the same source and section
      instrument_basis    – an instrument cited in one domain names, in its
                            own text, an Act cited in the other
      parallel_reporting  – both findings cite reporting duties triggered by
                            the same incident (different recipients/limits)
    """
    agents    : tuple[AgentID, AgentID]
    kind      : str
    note      : str
    members   : list[ClaimRef]      = field(default_factory=list)
    evidence  : list[EvidenceItem]  = field(default_factory=list)  # the passage(s) establishing the link


@dataclass
class ConflictRecord:
    """
    Two findings that disagree (DOCX §3.5 check 7).  Both sides are kept with
    their evidence; the Coordinator never picks one.
    """
    rule                  : str
    basis                 : str
    finding_a             : ClaimRef
    finding_b             : ClaimRef
    status                : str = "CONFLICT — unresolved; requires qualified human review"
    coordinator_treatment : str = (
        "Neither finding is adopted. Both are withheld from evidence-backed "
        "conclusions and shown side by side with their evidence; which one "
        "governs (e.g. a later or more specific instrument) is for human review."
    )


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
    # Structured forms of cross_domain_links / conflicts (same content)
    cross_domain_details: list[CrossDomainLink]    = field(default_factory=list)
    conflict_details    : list[ConflictRecord]     = field(default_factory=list)


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

    # Evidence the agents or the Verifier found missing; kept visible so an
    # uncertain conclusion is never presented as settled (DOCX A.2)
    open_questions          : list[str]            = field(default_factory=list)

    # Every claim in the assessment with its current outcome and the chunk
    # it was last assessed in — the basis for carrying earlier conclusions
    # forward visibly and for reporting re-rated claims.
    # Each: {"agent_id", "claim", "outcome", "chunk_id", "carried_forward"}
    claim_register          : list[dict]           = field(default_factory=list)

    # Incident flags as of this chunk, so the next chunk can report what
    # became true in it
    incident_flags          : dict                 = field(default_factory=dict)

    # Cross-domain links behind cross_domain_relationships:
    # each {"note", "agents": [a, b], "chunk_id"}
    link_register           : list[dict]           = field(default_factory=list)

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
    # agent_id value → what that agent was given: the incident state it
    # could read (flags, prior verified findings) and the retrieval queries
    # it issued.  The chunk itself is raw_chunk.
    agent_inputs        : dict[str, dict] = field(default_factory=dict)
