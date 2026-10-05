"""
Swarm Orchestrator
==================
Implements the orchestration logic described in DOCX §3.3 and §3.7.

Responsibilities
----------------
1. Receive the current scenario chunk and maintain the running incident state.
2. Determine which specialist agents are relevant to the current chunk.
3. Activate ONLY the required agents (no fixed sequence — swarm behaviour).
4. Pass the current chunk + structured incident state to each active agent.
5. Collect structured AgentFindings from each active agent.
6. Preserve evidence and source information.
7. Forward findings to the Verifier.
8. Forward verified results to the Coordinator.
9. Record a full AuditRecord for each chunk.

Agent-selection rules (DOCX §3.2, §3.3, §2.5, Annex-1 A.4)
-----------------------------------------------------------
The swarm has no fixed sequence (§3.2): the Orchestrator activates only
the specialists justified by the information released in the current
chunk (§2.5), read against the current incident state (§3.3).  Selection
uses the chunk's released information (`description`) — never its
position in the scenario.

    Information released in this chunk          Agents activated
    ------------------------------------------  ------------------------------
    performance symptom / security indicator    Technical
    security indicator                          + Cybersecurity + Standards
    critical service                            Critical Infrastructure
                                                + Policy & Legal
    personal data involved                      Privacy + Policy & Legal
    possible data exposure                      + Cybersecurity
    reporting / escalation question             Policy & Legal, plus each
                                                domain already flagged in the
                                                incident state (Cybersecurity,
                                                Privacy, Critical Infrastructure)
    policy-gap question                         Policy Gap

Accumulated incident context is otherwise NOT used for selection: a domain
flagged in an earlier chunk is re-activated only when the current chunk
asks a reporting/escalation question that spans the whole incident.

These rules reproduce both DOCX staged scenarios:

    Annex-1 A.4 (Scenario 1)                §2.5 (Scenario 2)
    C1 Technical                            T0 Technical
    C2 Technical + Cyber + Standards        T1 Technical + Cyber + Standards
    C3 Critical Infra + Policy & Legal      T2 Critical Infra + Privacy + P&L
    C4 Privacy + Policy & Legal + Cyber     T3 P&L + Cyber + Privacy
                                               + Critical Infra + Policy Gap

Policy Gap execution order (FIX 2)
------------------------------------
The Policy Gap Agent requires VERIFIED findings as input (DOCX §3.7).
It therefore runs in a second pass AFTER the other active specialists
have been verified:

    Pass 1: run all active non-PolicyGap specialists
         → Verifier checks Pass-1 findings
         → verified findings added to incident_state
    Pass 2: run Policy Gap Agent (receives verified Pass-1 findings)
         → Verifier checks Policy Gap findings
    Combine all findings → Coordinator

This guarantees the Policy Gap Agent never receives unverified
current-chunk findings as though they were verified.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.core.models import (
    AgentFinding, AgentID, AuditRecord,
    CoordinatorAssessment, ScenarioChunk, VerifierResult,
)
from src.agents import (
    TechnicalAgent, PolicyLegalAgent, CybersecurityAgent,
    PrivacyAgent, CriticalInfraAgent, StandardsAgent, PolicyGapAgent,
)
from src.knowledge_base.base_kb import KnowledgeBase, StubKnowledgeBase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage detection — keyword sets for NEW chunk content only
# ---------------------------------------------------------------------------

_TECHNICAL_SYMPTOM_KEYWORDS = frozenset([
    "latency", "packet loss", "session drop", "degradation", "outage",
    "throughput", "jitter",
])

_SECURITY_KEYWORDS = frozenset([
    "authentication", "signalling", "suspicious", "unusual", "anomal",
    "unauthori", "attack", "intrusion", "cyber", "security event",
    "control-plane", "control plane",
])

_PRIVACY_KEYWORDS = frozenset([
    "personal data", "patient", "subscriber", "identifiable", "healthcare",
    "health", "data exposed", "data breach", "user data",
])

_CII_KEYWORDS = frozenset([
    "critical service", "healthcare", "health", "hospital", "emergency",
    "government application", "critical application", "critical infrastructure",
    "essential service",
])

# Data may have left the operator's control — a security question as well
# as a privacy one (Annex-1 A.4 chunk 4: "reporting/response questions")
_EXPOSURE_KEYWORDS = frozenset([
    "exposed", "exposure", "exfiltrat", "leak", "data breach",
])

_REPORTING_KEYWORDS = frozenset([
    "report", "escalat", "notif",
])

_GAP_KEYWORDS = frozenset([
    "policy gap", "gap remains", "regulatory gap",
])


class SwarmOrchestrator:
    """
    The Swarm Orchestrator manages the full per-chunk pipeline.

    Parameters
    ----------
    verifier    : Verifier instance (injected)
    coordinator : Coordinator instance (injected)
    agent_kbs   : optional dict mapping AgentID → KnowledgeBase; if omitted,
                  stub KBs are used.  Inject real KBs here for live RAG.

    Usage
    -----
        orchestrator = SwarmOrchestrator(verifier, coordinator)
        audit_record = orchestrator.process_chunk(chunk)
    """

    def __init__(
        self,
        verifier,
        coordinator,
        agent_kbs: Optional[dict[AgentID, KnowledgeBase]] = None,
    ) -> None:
        self.verifier    = verifier
        self.coordinator = coordinator
        self._kbs        = agent_kbs or {}

        # Instantiate all 7 specialist agents
        self._agents: dict[AgentID, object] = {
            AgentID.TECHNICAL:      TechnicalAgent(self._kb(AgentID.TECHNICAL)),
            AgentID.POLICY_LEGAL:   PolicyLegalAgent(self._kb(AgentID.POLICY_LEGAL)),
            AgentID.CYBERSECURITY:  CybersecurityAgent(self._kb(AgentID.CYBERSECURITY)),
            AgentID.PRIVACY:        PrivacyAgent(self._kb(AgentID.PRIVACY)),
            AgentID.CRITICAL_INFRA: CriticalInfraAgent(self._kb(AgentID.CRITICAL_INFRA)),
            AgentID.STANDARDS:      StandardsAgent(self._kb(AgentID.STANDARDS)),
            # Read-only Canonical + Standards KB access for comparison (DOCX §7.1)
            AgentID.POLICY_GAP:     PolicyGapAgent(
                self._kb(AgentID.POLICY_GAP),
                canonical_kb = getattr(verifier, "canonical_kb", None),
                standards_kb = self._kb(AgentID.STANDARDS),
            ),
        }

        # Accumulated incident context — preserved across chunks for reasoning.
        # NOTE: these flags inform agent reasoning and coordinator change-tracking
        # but do NOT drive agent selection.  Agent selection uses _select_agents()
        # which applies the DOCX stage-specific sets.
        self._incident_state: dict = {
            "chunks_processed":        [],
            "active_agents_history":   {},   # chunk_id → list[AgentID]
            "cii_flagged":             False,
            "data_exposure_suspected": False,
            "cyber_event_suspected":   False,
            "verified_findings":       [],   # compact summaries from ALL prior chunks
            "active_agents":           [],   # agent IDs active in CURRENT chunk
        }

        logger.info("SwarmOrchestrator initialised with %d agents.", len(self._agents))

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def process_chunk(self, chunk: ScenarioChunk) -> AuditRecord:
        """
        Run the full pipeline for one scenario chunk.

        Flow (two-pass for Policy Gap correctness):

        Pass 1:
            chunk → select specialist agents (excl. Policy Gap)
                  → run Pass-1 agents
                  → Verifier (Pass-1 findings)
                  → verified findings → incident_state

        Pass 2 (only if Policy Gap is in the active set):
            → run Policy Gap Agent (receives verified Pass-1 findings)
            → Verifier (Policy Gap findings)

        Combined:
            All findings + both verifier results → Coordinator → AuditRecord
        """
        logger.info("=" * 60)
        logger.info("Orchestrator: processing chunk %s (index=%d)",
                    chunk.chunk_id, chunk.chunk_index)

        # 1. Update accumulated incident context flags
        self._update_incident_flags(chunk)

        # 2. Select agents for this chunk stage (exact DOCX sets)
        active_agent_ids = self._select_agents(chunk)
        self._incident_state["active_agents"] = [a.value for a in active_agent_ids]
        self._incident_state["active_agents_history"][chunk.chunk_id] = active_agent_ids

        logger.info("Active agents for %s: %s",
                    chunk.chunk_id, [a.value for a in active_agent_ids])

        policy_gap_active = AgentID.POLICY_GAP in active_agent_ids
        pass1_agent_ids   = [a for a in active_agent_ids if a != AgentID.POLICY_GAP]

        # ----------------------------------------------------------------
        # Pass 1: run all non-PolicyGap specialists
        # ----------------------------------------------------------------
        pass1_findings: list[AgentFinding] = self._run_agents(chunk, pass1_agent_ids)

        pass1_verifier_result: VerifierResult = self.verifier.verify(
            chunk_id       = chunk.chunk_id,
            findings       = pass1_findings,
            incident_state = self._incident_state,
        )

        # Absorb Pass-1 verified findings into incident_state so Policy Gap
        # Agent (and future chunks) can reference them
        self._absorb_verified_findings(pass1_verifier_result)

        # ----------------------------------------------------------------
        # Pass 2: Policy Gap Agent (only at T3 / when selected)
        # ----------------------------------------------------------------
        all_findings:          list[AgentFinding] = list(pass1_findings)
        combined_verifier_result: VerifierResult  = pass1_verifier_result

        if policy_gap_active:
            logger.info("Orchestrator: running Policy Gap Agent (Pass 2) for %s",
                        chunk.chunk_id)
            gap_findings: list[AgentFinding] = self._run_agents(
                chunk, [AgentID.POLICY_GAP]
            )
            gap_verifier_result: VerifierResult = self.verifier.verify(
                chunk_id       = chunk.chunk_id,
                findings       = gap_findings,
                incident_state = self._incident_state,
            )
            self._absorb_verified_findings(gap_verifier_result)

            # Merge Pass-2 results into the combined view
            all_findings.extend(gap_findings)
            combined_verifier_result = VerifierResult(
                chunk_id           = chunk.chunk_id,
                verified_claims    = (pass1_verifier_result.verified_claims
                                      + gap_verifier_result.verified_claims),
                cross_domain_links = (pass1_verifier_result.cross_domain_links
                                      + gap_verifier_result.cross_domain_links),
                conflicts          = (pass1_verifier_result.conflicts
                                      + gap_verifier_result.conflicts),
                missing_evidence   = (pass1_verifier_result.missing_evidence
                                      + gap_verifier_result.missing_evidence),
            )

        # ----------------------------------------------------------------
        # Coordinate
        # ----------------------------------------------------------------
        prior_assessment = self._incident_state.get("last_assessment")
        assessment: CoordinatorAssessment = self.coordinator.synthesize(
            chunk            = chunk,
            findings         = all_findings,
            verifier_result  = combined_verifier_result,
            incident_state   = self._incident_state,
            prior_assessment = prior_assessment,
        )
        self._incident_state["last_assessment"] = assessment

        # ----------------------------------------------------------------
        # Build audit record
        # ----------------------------------------------------------------
        record = AuditRecord(
            chunk_id               = chunk.chunk_id,
            timestamp              = datetime.now(timezone.utc).isoformat(),
            active_agents          = active_agent_ids,
            agent_findings         = all_findings,
            verifier_result        = combined_verifier_result,
            coordinator_assessment = assessment,
            raw_chunk              = chunk,
        )

        self._incident_state["chunks_processed"].append(chunk.chunk_id)
        logger.info("Orchestrator: chunk %s complete.", chunk.chunk_id)
        return record

    # ------------------------------------------------------------------
    # Agent selection — information released + incident state
    # ------------------------------------------------------------------

    def _select_agents(self, chunk: ScenarioChunk) -> list[AgentID]:
        """
        Select the specialists justified by the information released in
        this chunk (DOCX §2.5), read against the incident state (§3.3).

        Only `chunk.description` — the DOCX "Information released" text —
        is read.  The chunk's position in the scenario is never used, so the
        same rules serve any staged scenario (see module docstring).

        Must be called after _update_incident_flags(chunk).
        """
        released = chunk.description.lower()
        state    = self._incident_state
        selected: set[AgentID] = set()

        def mentions(keywords: frozenset[str]) -> bool:
            return any(kw in released for kw in keywords)

        security = mentions(_SECURITY_KEYWORDS)

        if mentions(_TECHNICAL_SYMPTOM_KEYWORDS) or security:
            selected.add(AgentID.TECHNICAL)

        if security:
            selected.update([AgentID.CYBERSECURITY, AgentID.STANDARDS])

        if mentions(_CII_KEYWORDS):
            selected.update([AgentID.CRITICAL_INFRA, AgentID.POLICY_LEGAL])

        if mentions(_PRIVACY_KEYWORDS):
            selected.update([AgentID.PRIVACY, AgentID.POLICY_LEGAL])

        if mentions(_EXPOSURE_KEYWORDS):
            selected.add(AgentID.CYBERSECURITY)

        # A reporting/escalation question spans the whole incident: bring in
        # every domain the incident state has already flagged.
        if mentions(_REPORTING_KEYWORDS):
            selected.add(AgentID.POLICY_LEGAL)
            if state["cyber_event_suspected"]:
                selected.add(AgentID.CYBERSECURITY)
            if state["data_exposure_suspected"]:
                selected.add(AgentID.PRIVACY)
            if state["cii_flagged"]:
                selected.add(AgentID.CRITICAL_INFRA)

        # Policy Gap requires prior verified findings (DOCX §3.7)
        if mentions(_GAP_KEYWORDS):
            if state["chunks_processed"]:
                selected.add(AgentID.POLICY_GAP)
            else:
                logger.debug("Policy Gap Agent deselected: no prior verified findings.")

        if not selected:
            # Nothing in the released information matches a mandate yet;
            # technical triage is the only analysis the facts can support.
            logger.warning(
                "Chunk %s matched no specialist mandate; activating Technical "
                "Agent for initial triage.", chunk.chunk_id,
            )
            selected.add(AgentID.TECHNICAL)

        logger.info("Chunk %s: selected agents %s",
                    chunk.chunk_id, sorted(a.value for a in selected))
        return sorted(selected, key=lambda a: a.value)

    # ------------------------------------------------------------------
    # Agent runner
    # ------------------------------------------------------------------

    def _run_agents(
        self,
        chunk: ScenarioChunk,
        agent_ids: list[AgentID],
    ) -> list[AgentFinding]:
        """Run each listed agent sequentially and collect findings."""
        findings: list[AgentFinding] = []
        for agent_id in agent_ids:
            agent = self._agents[agent_id]
            try:
                finding = agent.analyze(chunk, self._incident_state)
                findings.append(finding)
                logger.debug("Agent %s produced %d claim(s).",
                             agent_id.value, len(finding.claims))
            except Exception as exc:  # noqa: BLE001
                logger.error("Agent %s raised an exception: %s",
                             agent_id.value, exc, exc_info=True)
                findings.append(AgentFinding(
                    agent_id=agent_id,
                    chunk_id=chunk.chunk_id,
                    summary=f"[ERROR] Agent failed: {exc}",
                    uncertainty_notes=[f"Agent execution error: {exc}"],
                ))
        return findings

    async def _run_agents_parallel(
        self,
        chunk: ScenarioChunk,
        agent_ids: list[AgentID],
    ) -> list[AgentFinding]:  # pragma: no cover
        """
        Parallel version of _run_agents using asyncio.
        Implement using asyncio.gather over async agent.analyze calls.
        """
        raise NotImplementedError(
            "Parallel agent execution not yet implemented. "
            "Use _run_agents for sequential execution."
        )

    # ------------------------------------------------------------------
    # Incident context management
    # ------------------------------------------------------------------

    def _update_incident_flags(self, chunk: ScenarioChunk) -> None:
        """
        Update accumulated incident context flags from the current chunk.

        These flags are used by agents for reasoning context and by the
        Coordinator for change tracking.  They do NOT drive agent selection.
        """
        combined = (chunk.description + " " + " ".join(chunk.new_facts)).lower()

        if any(kw in combined for kw in _SECURITY_KEYWORDS):
            self._incident_state["cyber_event_suspected"] = True

        if any(kw in combined for kw in _CII_KEYWORDS):
            self._incident_state["cii_flagged"] = True

        if any(kw in combined for kw in _PRIVACY_KEYWORDS):
            self._incident_state["data_exposure_suspected"] = True

    def _absorb_verified_findings(self, verifier_result: VerifierResult) -> None:
        """
        Store compact summaries of verified claims into incident_state.
        The Policy Gap Agent reads these in its pass-2 run.
        """
        for vc in verifier_result.verified_claims:
            self._incident_state["verified_findings"].append({
                "agent_id": vc.agent_id.value,
                "claim":    vc.claim,
                "outcome":  vc.outcome.value,
            })

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _kb(self, agent_id: AgentID) -> KnowledgeBase:
        return self._kbs.get(agent_id, StubKnowledgeBase(
            kb_name=f"{agent_id.value}_stub",
            domain=agent_id.value,
        ))

    @property
    def incident_state(self) -> dict:
        """Read-only view of the current accumulated incident context."""
        return dict(self._incident_state)

    def get_agent(self, agent_id: AgentID):
        """Return the agent instance (for testing)."""
        return self._agents[agent_id]
