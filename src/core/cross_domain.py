"""
Cross-domain verification (DOCX §3.5)
=====================================
"Because the Verifier has access to the whole Canonical KB it can recognise
… that a telecom obligation found by the Policy & Legal Agent, a
data-protection implication found by the Privacy Agent and an
incident-reporting requirement found by the Cybersecurity Agent concern the
same incident. It flags these relationships, including any provision in one
domain that changes the reading of another."

Every relationship here is established from the passages the agents cited
or from the Canonical KB text — never from the mere fact that two agents
are active.  Findings from agents that ran in an earlier chunk (and not in
this one) take part, so a T2 privacy finding can be linked to a T1
cybersecurity finding.

Relationships
-------------
shared_provision    two domains cite the same source and section
instrument_basis    an instrument cited in one domain names, in its own
                    Canonical KB text, an Act cited in the other domain
                    (e.g. Rules made under that Act)
parallel_reporting  two domains cite duties to report/intimate the same
                    incident, to different recipients or on different
                    time limits — obligations to be coordinated

Conflict
--------
reporting_deadline  two domains cite duties to make the initial report of
                    an incident to the SAME recipient within DIFFERENT
                    time limits.  Both cannot be the governing rule as
                    quoted; the Verifier marks both claims CONFLICT.

Extraction is deterministic (regular expressions over the quoted text), so
results are reproducible and replayable.  It reads only what the passages
say; nothing is inferred from outside knowledge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import combinations
from typing import Optional

from src.core.models import (
    AgentFinding, AgentID, ClaimRef, ConflictRecord, CrossDomainLink, EvidenceItem,
)
from src.knowledge_base.text_match import normalise_section

# ---------------------------------------------------------------------------
# Reporting duties quoted in a passage
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8,
    "twelve": 12, "twenty-four": 24, "twenty four": 24, "forty-eight": 48,
    "forty eight": 48, "seventy-two": 72, "seventy two": 72,
}
_DEADLINE = re.compile(
    r"\bwithin\s+(\d+|" + "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True))
    + r")\s+hours?\b|\bwithout\s+(?:undue\s+)?delay\b",
    re.IGNORECASE,
)
# "report … to the Central Government", "report … to CERT-In",
# "intimate to each affected Data Principal", "intimate to the Board"
_RECIPIENT = re.compile(
    r"\b(?:report|intimat|notif|inform|furnish)\w*\b[^;.]{0,160}?\bto\s+"
    r"(?:the\s+|each\s+affected\s+|each\s+|an?\s+)?"
    r"((?:[A-Z][\w\-]*)(?:\s+(?:of\s+)?[A-Z][\w\-]*)*)"
)
_WINDOW = 400   # a time limit is attributed to the nearest recipient within this many characters


@dataclass(frozen=True)
class ReportingDuty:
    recipient     : str             # as printed, e.g. "Central Government"
    hours         : Optional[int]   # initial time limit; 0 = "without delay"; None = none stated
    limits        : tuple[str, ...] # every time limit printed for this recipient

    @property
    def key(self) -> str:
        return self.recipient.lower()

    def describe(self) -> str:
        return f"to {self.recipient}" + (f" ({'; '.join(self.limits)})" if self.limits else "")


def reporting_duties(item: EvidenceItem) -> list[ReportingDuty]:
    """
    Reporting duties stated in a passage: recipient and time limits.  Only
    Indian legal text that imposes a duty ("shall") counts — a standard's
    "report to the AMF" is a protocol step, not a legal obligation.
    """
    text = " ".join(item.excerpt.split())
    if item.jurisdiction.strip().lower() != "india" or " shall" not in text.lower():
        return []
    recipients = [(m.start(1), m.group(1)) for m in _RECIPIENT.finditer(text)]
    if not recipients:
        return []
    limits: dict[str, list[tuple[int, str]]] = {r: [] for _, r in recipients}
    for m in _DEADLINE.finditer(text):
        pos, phrase = m.start(), m.group(0)
        nearest = min(recipients, key=lambda r: abs(r[0] - pos))
        if abs(nearest[0] - pos) <= _WINDOW:
            hours = 0 if m.group(1) is None else (
                int(m.group(1)) if m.group(1).isdigit() else _NUMBER_WORDS[m.group(1).lower()])
            limits[nearest[1]].append((hours, phrase))
    duties = []
    for recipient, found in limits.items():
        found.sort()
        duties.append(ReportingDuty(
            recipient = recipient,
            hours     = found[0][0] if found else None,
            limits    = tuple(dict.fromkeys(p for _, p in found)),
        ))
    return duties


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

@dataclass
class _Cited:
    """One cited passage of one claim of one finding."""
    finding : AgentFinding
    claim   : str
    item    : EvidenceItem


def _cited(findings: list[AgentFinding]) -> list[_Cited]:
    out = []
    for f in findings:
        for claim, items in f.claim_citations.items():
            for item in items:
                if item.authority != "STUB":
                    out.append(_Cited(f, claim, item))
    return out


def _ref(c: _Cited) -> ClaimRef:
    return ClaimRef(c.finding.agent_id, c.finding.chunk_id, c.claim, [c.item])


def _label(c: _Cited, current_chunk: str) -> str:
    where = "" if c.finding.chunk_id == current_chunk else f", from {c.finding.chunk_id}"
    return f"{c.finding.agent_id.value}{where}"


def _cite(item: EvidenceItem) -> str:
    return f"{item.source_title}, {item.section}"


_ACT = re.compile(r"^(?:The\s+)?(.+?\bAct,\s*\d{4})")


def act_name(source_title: str) -> Optional[str]:
    """'The Telecommunications Act, 2023' → 'Telecommunications Act, 2023'."""
    m = _ACT.match(source_title.strip())
    # "CERT-In Directions under … Act, 2000" is not itself an Act
    if not m or " under " in m.group(1) or " of section " in m.group(1):
        return None
    return m.group(1)


def _snippet(text: str, phrase: str, width: int = 140) -> str:
    flat = " ".join(text.split())
    i = flat.lower().find(phrase.lower())
    start, end = max(0, i - width), min(len(flat), i + len(phrase) + width)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def find_relationships(
    current: list[AgentFinding],
    prior: list[AgentFinding],
    canonical_kb=None,
) -> tuple[list[CrossDomainLink], list[ConflictRecord]]:
    """
    Cross-domain links and reporting-deadline conflicts between the current
    chunk's findings, and between them and earlier findings of agents not
    active in this chunk.  Every link involves at least one current finding.
    """
    current_chunk = current[0].chunk_id if current else ""
    now, before = _cited(current), _cited(prior)
    pairs = [(a, b) for a, b in combinations(now, 2)
             if a.finding.agent_id != b.finding.agent_id]
    pairs += [(a, b) for a in now for b in before
              if a.finding.agent_id != b.finding.agent_id]

    links: dict[tuple, CrossDomainLink] = {}
    conflicts: dict[tuple, ConflictRecord] = {}

    def add_link(key, a: _Cited, b: _Cited, kind: str, note: str,
                 evidence: list[EvidenceItem]) -> None:
        agents = (a.finding.agent_id, b.finding.agent_id)
        link = links.get(key)
        if link is None:
            link = links[key] = CrossDomainLink(
                agents=agents, kind=kind,
                note=f"CROSS-DOMAIN [{_label(a, current_chunk)} ↔ {_label(b, current_chunk)}] "
                     f"{kind.replace('_', ' ')}: {note}",
                evidence=evidence)
        for ref in (_ref(a), _ref(b)):
            if all((m.agent_id, m.claim) != (ref.agent_id, ref.claim) for m in link.members):
                link.members.append(ref)

    basis_cache: dict[tuple[str, str], Optional[EvidenceItem]] = {}

    for a, b in pairs:
        ia, ib = a.item, b.item
        agents_key = tuple(sorted((a.finding.agent_id.value, b.finding.agent_id.value)))
        # The Policy Gap Agent re-cites passages it examined; only a shared
        # provision says something new (which domain finding a gap rests on)
        gap_side = AgentID.POLICY_GAP in (a.finding.agent_id, b.finding.agent_id)

        # 1. Same provision cited in two domains
        if (ia.source_title == ib.source_title
                and normalise_section(ia.section) == normalise_section(ib.section)):
            add_link(("shared", agents_key, ia.source_title, normalise_section(ia.section)),
                     a, b, "shared_provision",
                     f"both findings cite {_cite(ia)}; the two domains' conclusions rest "
                     "on the same provision and must be read together.", [ia])
            continue
        if gap_side:
            continue

        # 2. A cited instrument names, in its own text, an Act cited in the other domain
        for x, y, first, second in ((a, b, ia, ib), (b, a, ib, ia)):
            act = act_name(second.source_title)
            if not act or act.lower() in first.source_title.lower() or canonical_kb is None:
                continue
            key = (first.source_title, act)
            if key not in basis_cache:
                basis_cache[key] = _passage_naming(canonical_kb, first.source_title, act)
            passage = basis_cache[key]
            if passage is not None:
                add_link(("basis", agents_key, first.source_title, second.source_title),
                         x, y, "instrument_basis",
                         f"{first.source_title} (cited by {x.finding.agent_id.value}) names "
                         f"the {act} (cited by {y.finding.agent_id.value}) at "
                         f"{passage.section}: \"{_snippet(passage.excerpt, act)}\" — "
                         "a provision in one domain bears on the reading of the other.",
                         [passage])

        # 3. Reporting duties for the same incident
        duties_a, duties_b = reporting_duties(ia), reporting_duties(ib)
        if not (duties_a and duties_b) or ia.chunk_id == ib.chunk_id:
            continue
        clash = [(da, db) for da in duties_a for db in duties_b
                 if da.key == db.key and da.hours and db.hours and da.hours != db.hours]
        if clash:
            da, db = clash[0]
            ckey = tuple(sorted((ia.chunk_id, ib.chunk_id)))
            if ckey not in conflicts:
                conflicts[ckey] = ConflictRecord(
                    rule  = "reporting_deadline",
                    basis = (f"Both findings cite a duty to report the incident to "
                             f"{da.recipient}, but within different time limits: "
                             f"{_cite(ia)} ({'; '.join(da.limits)}) and {_cite(ib)} "
                             f"({'; '.join(db.limits)})."),
                    finding_a = _ref(a), finding_b = _ref(b))
            continue
        add_link(("report", agents_key, ia.chunk_id, ib.chunk_id), a, b,
                 "parallel_reporting",
                 f"the same incident may trigger reporting under {_cite(ia)} "
                 f"({', '.join(d.describe() for d in duties_a)}) and under {_cite(ib)} "
                 f"({', '.join(d.describe() for d in duties_b)}); these obligations "
                 "run in parallel and must be coordinated.", [ia, ib])

    return list(links.values()), list(conflicts.values())


def _passage_naming(canonical_kb, source_title: str, phrase: str) -> Optional[EvidenceItem]:
    """First Canonical KB passage of `source_title` whose text names `phrase`."""
    passages = canonical_kb.scan({"source_title": source_title})
    if not passages:
        return None
    phrase = phrase.lower()
    for p in passages:
        if phrase in " ".join(p.excerpt.split()).lower():
            return p
    return None
