"""
Cleaning, section detection and chunking.

Section labels are taken only from headings printed in the document.  Text
before the first detected heading is labelled by page ("p. 3"), never by a
guessed section number — a wrong section label would become a wrong
citation (DOCX §7.6 audit trail).

Detectors (manifest `section_style`):
    numbered       "22. Protection of ..." / "7. Intimation of ..."  (Acts, Rules)
                   numbers must increase, so list items inside a section
                   are not mistaken for new sections; Schedules end the run
    roman_items    "(ii) Any service provider ..."          (CERT-In Directions)
    outline        "IV. Strategies" / "A. ..." / "3) ..."    (NCSP-2013)
    clauses        "5.2.1 Security of ..." / "Annex A"       (ITU, ETSI, NIST PDFs)
    numbered_paras "3.12 The Authority ..."                  (TRAI recommendations)
    docx_headings  Word heading styles                       (3GPP specifications)
    page           page number only
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from src.rag.extract import Block

MAX_CHARS     = 1200
OVERLAP_CHARS = 150


@dataclass
class Section:
    label: str               # citation label, e.g. "Section 22", "Clause 5.15.2"
    title: str               # heading text as printed ("" if none)
    lines: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)


@dataclass
class Chunk:
    section: str
    section_title: str
    text: str
    page: str                # "3" or "3-4"; "" for DOCX


# ---------------------------------------------------------------------------
# Cleaning
# ---------------------------------------------------------------------------

_PAGE_FOOTER = re.compile(r"^(page\s*\|?\s*\d+(\s+of\s+\d+)?|\d{1,4}|[ivxlc]{1,6})$", re.IGNORECASE)


def _shape(line: str) -> str:
    return re.sub(r"\d+", "#", " ".join(line.lower().split()))


def remove_running_lines(blocks: list[Block]) -> list[Block]:
    """
    Drop page numbers and lines repeated on many pages (headers/footers).

    A bare number is treated as a page number only in the first or last two
    lines of a page — elsewhere it may be a clause number printed on its own
    line (ITU/ETSI layout) and must survive for section detection.
    """
    by_page: dict[int, list[int]] = defaultdict(list)
    for i, b in enumerate(blocks):
        by_page[b.page].append(i)
    edge = {i for idxs in by_page.values() if idxs and blocks[idxs[0]].page
            for i in idxs[:2] + idxs[-2:]}

    pages = {b.page for b in blocks if b.page}
    running: set[str] = set()
    if len(pages) >= 3:
        seen_on: dict[str, set[int]] = defaultdict(set)
        for b in blocks:
            if b.page and len(b.text) < 120:
                seen_on[_shape(b.text)].add(b.page)
        threshold = max(3, int(0.25 * len(pages)))
        running = {shape for shape, on in seen_on.items() if len(on) >= threshold}

    kept = []
    for i, b in enumerate(blocks):
        if i in edge and _PAGE_FOOTER.match(b.text):
            continue
        if _shape(b.text) in running and not re.fullmatch(r"#(\.#)*\.?", _shape(b.text)):
            continue
        kept.append(b)
    return kept


def join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        if text.endswith("-") and line[:1].islower():
            text = text[:-1] + line          # re-join a hyphenated word
        else:
            text = f"{text} {line}" if text else line
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Detectors — each returns (label, title) for a heading line, else None
# ---------------------------------------------------------------------------

class _Numbered:
    """
    Acts and Rules: '22. Heading.—(1) ...' with increasing numbers.
    Also '[4. ...' (text inserted by an amending Act) and a number printed
    alone on its line ('2.' then 'Definitions. — (1) ...').
    """
    _line     = re.compile(r"^\[?(\d{1,3})([A-Z]{0,2})\.\s+(\S.*)$")
    _alone    = re.compile(r"^\[?(\d{1,3})([A-Z]{0,2})\.$")
    _schedule = re.compile(r"^(THE\s+)?((FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH)\s+)?SCHEDULE\b")
    # 'Heading.—' / 'Heading. — (1)' : the heading is the text before the dash
    _title    = re.compile(r"^([^(—–]{3,120}?)\.\s*[—–-]")

    def __init__(self, label: str):
        self.label, self.last, self.in_schedule = label, 0, False
        self.pending: tuple[int, str] | None = None

    def _next(self, n: int, suffix: str) -> bool:
        return (n == self.last and bool(suffix)) or (self.last < n <= self.last + 3)

    def _heading(self, n: int, suffix: str, rest: str):
        self.last = n
        m = self._title.match(rest)
        return (f"{self.label} {n}{suffix}", m.group(1).strip() if m else "")

    def __call__(self, line: str):
        if self._schedule.match(line):
            self.in_schedule = True
            return (" ".join(line.split()[:4]).title(), line)
        if self.in_schedule:
            return None
        if self.pending:
            (n, suffix), self.pending = self.pending, None
            if self._next(n, suffix):
                return self._heading(n, suffix, line)
        if m := self._alone.match(line):
            self.pending = (int(m.group(1)), m.group(2))
            return None
        m = self._line.match(line)
        if m and self._next(int(m.group(1)), m.group(2)):
            return self._heading(int(m.group(1)), m.group(2), m.group(3))
        return None


class _RomanItems:
    """'(i)', '(ii)', ... in sequence; 'Annexure I', 'Annexure II' ... in sequence.

    A heading must be the whole line and the next in sequence, so a sentence
    that wraps onto a line starting 'Annexure III.' is not a heading.
    """
    _item  = re.compile(r"^\(([ivxl]+)\)\s*(\S.*)$")
    _annex = re.compile(r"^Annexure[\s-]+([IVX]+)$", re.IGNORECASE)
    _ROMANS = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
               "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"]

    def __init__(self, label: str):
        self.label, self.next, self.next_annex, self.in_annex = label, 0, 0, False

    def __call__(self, line: str):
        m = self._annex.match(line.strip())
        if m and m.group(1).lower() == self._ROMANS[self.next_annex]:
            self.in_annex, self.next_annex = True, self.next_annex + 1
            return (f"Annexure {m.group(1).upper()}", line)
        if self.in_annex:
            return None
        m = self._item.match(line)
        if m and self.next < len(self._ROMANS) and m.group(1) == self._ROMANS[self.next]:
            self.next += 1
            return (f"{self.label} ({m.group(1)})", m.group(2)[:120])
        return None


class _Outline:
    """NCSP-2013: 'IV. Strategies' → 'A. ...' → '3)' items; preamble '2.' paras."""
    _part   = re.compile(r"^([IVX]{1,4})\.\s+(\S.*)$")
    _letter = re.compile(r"^([A-Z])\.\s+(\S.*)$")
    _item   = re.compile(r"^(\d{1,2})\)\s*(.*)$")
    _para   = re.compile(r"^(\d{1,2})\.\s+(\S.*)$")

    def __init__(self, label: str):
        self.part, self.part_title, self.letter, self.item, self.para = "", "", "", 0, 0

    def _label(self) -> str:
        label = f"Part {self.part}" if self.part else "Preamble"
        if self.letter:
            label += f" {self.letter}"
        if self.item:
            label += f" item {self.item}"
        elif self.para and not self.part:
            label += f" para {self.para}"
        return label

    def __call__(self, line: str):
        # 'I. ...' after 'H. ...' is the next lettered strategy, not Part I
        expected = chr(ord(self.letter) + 1) if self.letter else "A"
        is_next_letter = bool(self.part) and line.startswith(f"{expected}. ")
        if not is_next_letter and (m := self._part.match(line)):
            self.part, self.part_title, self.letter, self.item = m.group(1), m.group(2), "", 0
            return (self._label(), self.part_title)
        if self.part and (m := self._letter.match(line)) and m.group(1) == expected:
            self.letter, self.item = m.group(1), 0
            return (self._label(), m.group(2)[:120])
        if (m := self._item.match(line)) and int(m.group(1)) == self.item + 1:
            self.item = int(m.group(1))
            return (self._label(), "")
        if not self.part and (m := self._para.match(line)) and int(m.group(1)) == self.para + 1:
            self.para = int(m.group(1))
            return (self._label(), "")
        return None


class _Clauses:
    """Numbered clause headings with increasing numbers; Annex/Appendix headings."""
    _clause = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\.?\s+([A-Z][^\n]{1,110})$")
    _num    = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,4})\.?$")
    _annex  = re.compile(r"^(Annex|Appendix)\s+([A-Z])\b(.*)$")
    _annexc = re.compile(r"^([A-Z](?:\.\d{1,2}){1,4})\s+([A-Z][^\n]{1,110})$")

    def __init__(self, label: str, allow_long: bool = False, min_depth: int = 1):
        self.label, self.allow_long, self.min_depth = label, allow_long, min_depth
        self.current: tuple[int, ...] = ()
        self.annex = ""
        self.pending_number = ""

    def _accept(self, number: str) -> bool:
        parts = tuple(int(p) for p in number.split("."))
        if len(parts) < self.min_depth or parts <= self.current:
            return False
        first_now = self.current[0] if self.current else 0
        if not 1 <= parts[0] <= first_now + 1:
            return False
        if len(parts) > 1 and self.current[:1] != parts[:1] and parts[1:] != (1,) * (len(parts) - 1):
            return False          # a new top-level number must start at x.1
        self.current = parts
        return True

    def __call__(self, line: str):
        if "...." in line or (not self.allow_long and re.search(r"\s\d+$", line)):
            self.pending_number = ""       # table-of-contents entry
            return None
        if self.pending_number:            # number and title on separate lines
            number, self.pending_number = self.pending_number, ""
            short = len(line) < 110
            if line[:1].isupper() and (short or self.allow_long) and self._accept(number):
                return (f"{self.label} {number}", line if short else "")
        if m := self._annex.match(line):
            self.annex = m.group(2)
            return (f"{m.group(1)} {m.group(2)}", line)
        if self.annex:
            if m := self._annexc.match(line):
                if m.group(1).startswith(self.annex + "."):
                    return (f"{self.label} {m.group(1)}", m.group(2))
            return None
        if m := self._num.match(line):
            self.pending_number = m.group(1)
            return None
        if m := self._clause.match(line):
            if len(line) > 110 and not self.allow_long:
                return None
            if self._accept(m.group(1)):
                title = m.group(2) if len(m.group(2)) <= 110 else ""
                return (f"{self.label} {m.group(1)}", title)
        return None


class _NumberedParas(_Clauses):
    """TRAI recommendations: paragraphs open with 'x.y' numbers; long lines allowed."""
    _clause = re.compile(r"^(\d{1,2}(?:\.\d{1,3}){1,3})\.?\s+(\S.*)$")

    def __init__(self, label: str):
        super().__init__(label, allow_long=True, min_depth=2)

    def __call__(self, line: str):
        found = super().__call__(line)
        if found:
            label, title = found
            return (label, title if len(title) <= 110 else "")
        return None


_DOCX_HEADING = re.compile(r"^((?:\d+(?:\.\d+)*)|(?:[A-Z]{1,2}(?:\.\d+)+)|(?:Annex [A-Z]{1,2}))\s*(?:\([^)]*\))?:?\s*(.*)$")


def _make_detector(style: str, label: str):
    return {
        "numbered":       lambda: _Numbered(label),
        "roman_items":    lambda: _RomanItems(label),
        "outline":        lambda: _Outline(label),
        "clauses":        lambda: _Clauses(label),
        "numbered_paras": lambda: _NumberedParas(label),
        "page":           lambda: (lambda line: None),
    }[style]()


# ---------------------------------------------------------------------------
# PDF bookmark outline (ITU, ETSI, NIST)
# ---------------------------------------------------------------------------

_OUTLINE_NUMBER = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
_OUTLINE_ANNEX  = re.compile(r"^(Annex|Appendix)\s+([A-Z]{1,2}|[IVX]+)\b[.:]?\s*(.*)$")


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _outline_label(title: str, label: str) -> tuple[str, str]:
    title = " ".join(title.split())
    if m := _OUTLINE_NUMBER.match(title):
        return f"{label} {m.group(1)}", m.group(2)
    if m := _OUTLINE_ANNEX.match(title):
        return f"{m.group(1)} {m.group(2)}", m.group(3)
    return title[:80], title


def split_by_outline(blocks: list[Block], outline, label: str) -> tuple[list[Section], list[str]]:
    """
    Start a new section where each bookmark's heading is printed: the first
    line (or line pair, when the number and title are printed on separate
    lines) on or after the bookmark's page whose text matches the title.
    Returns the sections and the bookmarks that could not be located.
    """
    starts: dict[int, tuple[str, str]] = {}
    unmatched: list[str] = []
    cursor = 0
    for _level, title, page in outline:
        target = _norm(title)
        if len(target) < 3:
            continue
        found = None
        for i in range(cursor, len(blocks)):
            if blocks[i].page < page:
                continue
            if blocks[i].page > page + 1:
                break
            one = _norm(blocks[i].text)
            two = one + (_norm(blocks[i + 1].text) if i + 1 < len(blocks) else "")
            if one and (target.startswith(one) and len(one) >= min(len(target), 12)
                        or one.startswith(target) or two.startswith(target)):
                found = i
                break
        if found is None:
            unmatched.append(title)
            continue
        starts[found] = _outline_label(title, label)
        cursor = found + 1

    sections: list[Section] = []
    current: Section | None = None
    for i, b in enumerate(blocks):
        if i in starts:
            current = Section(*starts[i])
            sections.append(current)
        elif current is None or (current.label.startswith("p. ") and b.page not in current.pages):
            current = Section(f"p. {b.page}", "")
            sections.append(current)
        current.lines.append(b.text)
        if b.page and b.page not in current.pages:
            current.pages.append(b.page)
    return [s for s in sections if s.lines], unmatched


# ---------------------------------------------------------------------------
# Sectioning
# ---------------------------------------------------------------------------

def split_sections(blocks: list[Block], style: str, label: str) -> list[Section]:
    sections: list[Section] = []
    current: Section | None = None

    def start(lbl: str, title: str, page: int) -> Section:
        sec = Section(lbl, title)
        sections.append(sec)
        return sec

    if style == "docx_headings":
        for b in blocks:
            if b.heading_level:
                m = _DOCX_HEADING.match(b.text.replace("\t", " "))
                if m and m.group(1):
                    number = m.group(1)
                    lbl = number if number.startswith("Annex") else f"{label} {number}"
                    current = start(lbl, m.group(2).strip(), 0)
                else:
                    current = start(b.text.strip()[:80], b.text.strip(), 0)
                continue
            if current is None:
                current = start("Front matter", "", 0)
            current.lines.append(b.text)
        return [s for s in sections if s.lines]

    detect = _make_detector(style, label)
    for b in blocks:
        found = detect(b.text)
        if found:
            current = start(found[0], found[1], b.page)
        elif current is None or (current.label.startswith("p. ") and b.page not in current.pages):
            current = start(f"p. {b.page}", "", b.page)
        current.lines.append(b.text)
        if b.page and b.page not in current.pages:
            current.pages.append(b.page)
    return [s for s in sections if s.lines]


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _windows(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    out, start = [], 0
    while start < len(text):
        end = min(start + MAX_CHARS, len(text))
        if end < len(text):
            cut = max(text.rfind(". ", start + MAX_CHARS // 2, end),
                      text.rfind("; ", start + MAX_CHARS // 2, end))
            end = cut + 1 if cut > 0 else (text.rfind(" ", start, end) or end)
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - OVERLAP_CHARS, start + 1)
        start = text.find(" ", start) + 1 or start      # don't start mid-word
    return [w for w in out if w]


def chunk_sections(sections: list[Section]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for sec in sections:
        text = join_lines(sec.lines)
        if len(text) < 40:
            continue                   # stray heading with no body
        pages = sorted(sec.pages)
        page = "" if not pages else (str(pages[0]) if pages[0] == pages[-1] else f"{pages[0]}-{pages[-1]}")
        for window in _windows(text):
            chunks.append(Chunk(sec.label, sec.title, window, page))
    return chunks
