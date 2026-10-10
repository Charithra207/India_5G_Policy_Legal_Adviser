"""
Abstract base class for all specialist agents.

Design rules (from DOCX §3.3, §3.7)
-------------------------------------
* Each agent speaks ONLY for its defined analytical mandate.
* Each agent has its own domain KB and retrieval mechanism.
* Agents receive (a) the current scenario chunk and (b) the structured
  incident state — nothing more.
* Agents return structured AgentFinding objects with evidence references
  and stated uncertainty.
* Agents do NOT directly override another agent's finding.
* Agents do NOT act as general-purpose chatbots.

The `analyze` method is the single entry point called by the Orchestrator.
It calls `_build_queries` → `_retrieve_evidence` → `_produce_finding`
so that the RAG/KB layer can integrate real retrieval by overriding
`_retrieve_evidence` without touching the analysis logic.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from src.core.models import AgentFinding, AgentID, EvidenceItem, ScenarioChunk
from src.knowledge_base.base_kb import KnowledgeBase, StubKnowledgeBase
from src.knowledge_base.text_match import content_terms

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for the seven specialist agents.

    Parameters
    ----------
    agent_id : the AgentID enum value for this agent
    kb       : the domain-specific KnowledgeBase instance (injected).
               Pass a real KnowledgeBase subclass to enable live RAG.
    """

    def __init__(self, agent_id: AgentID, kb: Optional[KnowledgeBase] = None) -> None:
        self.agent_id = agent_id
        self.kb       = kb or StubKnowledgeBase(
            kb_name = f"{agent_id.value}_stub",
            domain  = agent_id.value,
        )
        logger.debug("Agent %s initialised with KB: %s", agent_id.value, self.kb.kb_name)

    # ------------------------------------------------------------------
    # Public entry point — called by the Orchestrator
    # ------------------------------------------------------------------

    def analyze(self, chunk: ScenarioChunk, incident_state: dict) -> AgentFinding:
        """
        Full analysis pipeline for one scenario chunk.

        Parameters
        ----------
        chunk          : the current ScenarioChunk
        incident_state : the Orchestrator's running structured state dict

        Returns
        -------
        AgentFinding with claims, evidence, and uncertainty clearly separated.
        """
        logger.info("Agent %s -> analyzing chunk %s", self.agent_id.value, chunk.chunk_id)

        view     = list(getattr(chunk, "agent_views", {}).get(self.agent_id.value, []))
        queries  = self._focus_queries(chunk, self._build_queries(chunk, incident_state), view)
        self.last_queries = list(queries)      # recorded in the audit trail (DOCX §7.6)
        # Words of this incident (released facts, and what only this agent
        # was told) decide which retrieved passages are quoted first.
        self._focus_terms = content_terms(" ".join([*view, *chunk.new_facts])) if view else set()
        evidence = self._retrieve_evidence(queries)
        finding  = self._produce_finding(chunk, incident_state, evidence)
        finding.agent_id = self.agent_id
        finding.chunk_id = chunk.chunk_id
        finding.missing_facts = self._reconcile_missing(finding.missing_facts, view)
        # Optional LLM reasoning over the same retrieved passages; a no-op
        # unless a model is configured (src/llm).  Its claims cite passages
        # and are verified like any other claim.
        from src.llm.synthesis import enrich
        enrich(self, chunk, incident_state, evidence, finding)
        # Citations may only point at claims the finding actually makes
        finding.claim_citations = {
            c: items for c, items in finding.claim_citations.items()
            if c in finding.claims
        }

        logger.info(
            "Agent %s -> produced %d claim(s), %d evidence item(s)",
            self.agent_id.value, len(finding.claims), len(finding.evidence),
        )
        return finding

    # ------------------------------------------------------------------
    # Steps that subclasses implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _build_queries(
        self, chunk: ScenarioChunk, incident_state: dict
    ) -> list[str]:
        """
        Construct the retrieval queries appropriate for this agent's mandate.

        Queries are framed from the agent's perspective:
          - Policy & Legal: "which provisions apply?"
          - Privacy: "is personal data involved?"
          - Technical: "what are the affected components?"
        """

    @abstractmethod
    def _produce_finding(
        self,
        chunk: ScenarioChunk,
        incident_state: dict,
        evidence: list[EvidenceItem],
    ) -> AgentFinding:
        """
        Produce the structured AgentFinding for this chunk.

        IMPORTANT: claims must be grounded in the supplied `evidence`.
        If the evidence is empty or stub-only, claims must be flagged as
        uncertain.  Do not invent legal requirements.
        """

    # ------------------------------------------------------------------
    # Evidence retrieval — RAG/KB integration point
    # ------------------------------------------------------------------

    def _retrieve_evidence(self, queries: list[str]) -> list[EvidenceItem]:
        """
        Run each query against this agent's KB and deduplicate results.

        The default implementation calls `self.kb.retrieve`.  Override
        this method in a subclass for custom retrieval logic such as
        hybrid search or re-ranking.
        """
        seen_chunks: set[str] = set()
        evidence: list[EvidenceItem] = []

        # Interleave by rank: every query's best passage comes before any
        # query's second best, so one strong query cannot crowd out the
        # agent's other questions.
        per_query = [self.kb.retrieve(query, top_k=5) for query in queries]
        for rank in range(max((len(r) for r in per_query), default=0)):
            for results in per_query:
                if rank >= len(results):
                    continue
                item = results[rank]
                key = item.chunk_id or f"{item.source_title}::{item.section}"
                if key not in seen_chunks:
                    seen_chunks.add(key)
                    evidence.append(item)

        return evidence

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_real(item: EvidenceItem) -> bool:
        return item.chunk_id != "stub-000" and item.authority != "STUB"

    @classmethod
    def _evidence_is_real(cls, evidence: list[EvidenceItem]) -> bool:
        """Return True if at least one non-stub evidence item is present."""
        return any(cls._is_real(e) for e in evidence)

    @classmethod
    def _real_evidence(cls, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        """Non-stub evidence, in retrieval order (each query's best first)."""
        return [e for e in evidence if cls._is_real(e)]

    # ------------------------------------------------------------------
    # Focus: the facts of this incident, including what only this agent saw
    # ------------------------------------------------------------------

    @staticmethod
    def _focus_queries(chunk: ScenarioChunk, queries: list[str], view: list[str]) -> list[str]:
        """
        The facts released to this agent alone are searched first.  A chunk
        description that is a question (e.g. "The question asks: what should
        be reported…?") states no fact, so it is not searched as one.
        """
        description = chunk.description.strip()
        kept = [q for q in queries if not (q.strip() == description and "?" in description)]
        return list(dict.fromkeys([*view, *kept]))

    # A short passage with no sentence in it is a title page or a heading,
    # not a provision (e.g. a report's cover: "5G CYBERSECURITY STANDARDS …").
    MIN_QUOTABLE_CHARS = 150

    @classmethod
    def _is_heading(cls, item: EvidenceItem) -> bool:
        text = " ".join(item.excerpt.split())
        return len(text) < cls.MIN_QUOTABLE_CHARS and not re.search(r"[.;:]", text)

    # Time limits mark the duties an incident responder needs first.
    _DEADLINE = re.compile(r"\b(?:hours?|days?|without (?:undue )?delay|forthwith|immediately)\b", re.I)

    def _quotable(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        """
        Real passages long enough to state something, in the order they are
        quoted.  Without facts released to this agent the retrieval order is
        kept.  With them, the selection stays the retrieval's top passages,
        except that a passage sharing (almost) no words with the incident's
        facts gives way to a later one that does — a duty with a time limit
        first — and time-limited duties are quoted first.  So "logs are kept
        30 days" brings the log-retention direction in, and a passage on an
        unrelated topic that a generic query happened to return drops out.
        """
        items = [e for e in self._real_evidence(evidence) if not self._is_heading(e)]
        focus = getattr(self, "_focus_terms", set())
        if not focus:
            return items

        def text(item: EvidenceItem) -> str:
            return f"{item.section_title} {item.excerpt}".lower()

        def overlap(item: EvidenceItem) -> int:
            return len(focus & content_terms(text(item)))

        def timed_duty(item: EvidenceItem) -> bool:
            return any(w in text(item) for w in self._DUTY_WORDS) and bool(self._DEADLINE.search(text(item)))

        n = self.MAX_CITED_PASSAGES
        top, rest = items[:n], items[n:]
        spare = sorted((r for r in rest if overlap(r) >= self.MIN_SHARED_TERMS),
                       key=lambda r: (not timed_duty(r), -overlap(r), rest.index(r)))
        for weak in sorted((i for i in top if overlap(i) < self.MIN_SHARED_TERMS and not timed_duty(i)),
                           key=overlap):
            if not spare:
                break
            top[top.index(weak)] = spare.pop(0)
        top = sorted(top, key=lambda i: not timed_duty(i))           # stable: otherwise retrieval order
        return top + [r for r in rest if r not in top]

    # A quoted passage should share at least this many words with the facts.
    MIN_SHARED_TERMS = 2

    # Missing-information notes answered by what this agent was told: (words
    # in the note, words in the agent's own facts, replacement or None to drop).
    _ANSWERED_BY_VIEW = (
        (("amf/smf logs",), ("amf", "smf"),
         "SMF and UPF telemetry has not been released; AMF logs were released to this agent."),
        (("radio access network",), ("gnb", "ran ", "radio"), None),
        (("protocol, volume, source",), ("baseline", "times", "failures", "burst"),
         "Protocol and source of the security indicators have not been released; their volume "
         "was released to this agent."),
        (("whether patient/subscriber data is processed",), ("patient names",), None),
    )

    def _reconcile_missing(self, missing: list[str], view: list[str]) -> list[str]:
        """Drop or narrow a 'missing' note that this agent's own facts already answer."""
        if not view:
            return missing
        seen = " ".join(view).lower()
        out: list[str] = []
        for note in missing:
            low = note.lower()
            for note_words, view_words, replacement in self._ANSWERED_BY_VIEW:
                if any(w in low for w in note_words) and any(w in seen for w in view_words):
                    if replacement:
                        out.append(replacement)
                    break
            else:
                out.append(note)
        return list(dict.fromkeys(out))

    # ------------------------------------------------------------------
    # Evidence-grounded claims
    # ------------------------------------------------------------------
    #
    # Rule: an agent states what a law, rule or standard SAYS only by
    # quoting a passage retrieved from its own KB, and records that passage
    # as the claim's citation.  Without retrieved passages the agent names
    # the instruments in its mandate (DOCX §4.2) and states that nothing was
    # assessed — it never supplies their content from memory.

    MAX_CITED_PASSAGES = 4
    EXCERPT_CHARS      = 400

    # Words that mark a passage as imposing a duty (DOCX §3.3: agents
    # "identify obligations").  Detection only — the passage is quoted, not
    # interpreted.
    _DUTY_WORDS = ("shall", "must", "required to", "obliged", "report", "notify")

    @staticmethod
    def _reference_label(item: EvidenceItem) -> str:
        """International material is labelled as a reference point (DOCX §4)."""
        if item.jurisdiction.strip().lower() == "india":
            return ""
        return "[REFERENCE ONLY — not Indian law] "

    def _quote_claim(self, item: EvidenceItem) -> str:
        excerpt = " ".join(item.excerpt.split())
        if len(excerpt) > self.EXCERPT_CHARS:
            excerpt = excerpt[: self.EXCERPT_CHARS].rsplit(" ", 1)[0] + " …"
        return (
            f'{self._reference_label(item)}{item.source_title}, {item.section} '
            f'states: "{excerpt}"'
        )

    def _cited_claims(
        self, evidence: list[EvidenceItem],
    ) -> tuple[list[str], dict[str, list[EvidenceItem]]]:
        """One quoted claim per top retrieved passage, each with its citation."""
        claims: list[str] = []
        citations: dict[str, list[EvidenceItem]] = {}
        for item in self._quotable(evidence)[: self.MAX_CITED_PASSAGES]:
            claim = self._quote_claim(item)
            if claim not in citations:
                claims.append(claim)
                citations[claim] = [item]
        return claims, citations

    def _duty_passages(self, evidence: list[EvidenceItem]) -> list[str]:
        """Retrieved passages whose text imposes a duty, quoted with their source."""
        return [
            self._quote_claim(e)
            for e in self._quotable(evidence)[: self.MAX_CITED_PASSAGES]
            if any(w in e.excerpt.lower() for w in self._DUTY_WORDS)
        ]

    def _not_assessed_claim(self, instruments: list[str], label: str = "") -> str:
        """Scope statement used when the KB returned no passages."""
        return (
            f"{label}No passage was retrieved from the {self.kb.kb_name}. "
            f"Instruments in this agent's mandate (DOCX §4): "
            f"{'; '.join(instruments)}. Their applicability to this incident "
            "is not assessed."
        )

    def _evidence_or_scope_claims(
        self,
        evidence: list[EvidenceItem],
        instruments: list[str],
        label: str = "",
    ) -> tuple[list[str], dict[str, list[EvidenceItem]]]:
        """Cited claims when passages were retrieved, else the scope statement."""
        claims, citations = self._cited_claims(evidence)
        if not claims:
            claims = [self._not_assessed_claim(instruments, label)]
        return claims, citations

    def _uncertainty_note_if_stub(self, evidence: list[EvidenceItem]) -> list[str]:
        """Return an uncertainty note when only stub evidence is available."""
        if not self._evidence_is_real(evidence):
            return [
                f"[RAG NOT LIVE] {self.agent_id.value} agent findings are "
                "based on scenario text only; no KB evidence was retrieved. "
                "Claims should be treated as preliminary until RAG is integrated."
            ]
        return []
