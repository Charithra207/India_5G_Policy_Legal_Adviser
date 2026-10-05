"""
Deterministic text helpers shared by the KB layer, the agents and the
Verifier.  Kept free of model calls so verification outcomes are
reproducible and replayable (DOCX §7.6).
"""

from __future__ import annotations

import re

# Words that carry no evidential content, plus the framing words agents use
# around quoted passages ("... states: ..."), so that support is measured on
# the substance of a claim only.
_STOPWORDS = frozenset("""
a an and are as at be been being by can could did do does for from had has
have if in into is it its may might must not of on or shall should such
than that the their there these this those to under upon was were which
while who will with within would also any each other per via
states stated section sections passage retrieved reference only indian law
formal certification
""".split())

_BRACKETED = re.compile(r"\[[^\]]*\]")
_WORD      = re.compile(r"[a-z0-9]+(?:\.[0-9]+)*")


def content_terms(text: str) -> set[str]:
    """Lower-cased content words (len ≥ 3, or containing digits), minus
    stopwords and bracketed labels such as "[REFERENCE ONLY — ...]"."""
    text = _BRACKETED.sub(" ", text.lower())
    return {
        w for w in _WORD.findall(text)
        if w not in _STOPWORDS and (len(w) >= 3 or any(c.isdigit() for c in w))
    }


def term_coverage(claim: str, passage_text: str) -> float:
    """Fraction of the claim's content terms that appear in the passage."""
    claim_terms = content_terms(claim)
    if not claim_terms:
        return 0.0
    return len(claim_terms & content_terms(passage_text)) / len(claim_terms)


def normalise_section(section: str) -> str:
    """'Section 22 (1)' and 'section 22(1)' compare equal."""
    return re.sub(r"\s+", "", section.lower())


def mentions(text: str, phrase: str) -> bool:
    """Case-insensitive phrase containment."""
    return phrase.lower() in text.lower()
