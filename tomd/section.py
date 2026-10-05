"""Bibliographic section detection and reference-sheet stripping.

Marks common academic sections (Abstract, Introduction, Methods, Results,
Discussion, Conclusion, References) with ``<!-- SECTION: X -->`` comments and
can optionally remove the reference back-matter entirely to save tokens when
doing focused reading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Section:
    name: str
    start: int  # char offset where the section heading begins


# Ordered list; first match wins.  A section pattern is *anchored* to the start
# of a line so a mid-sentence "results" never triggers a false boundary.
_SECTIONS: list[tuple[str, re.Pattern]] = [
    ("Abstract", re.compile(r"^(?:abstract|summary)\b", re.I)),
    ("Introduction", re.compile(r"^(?:\d+[\.\)]?\s+)?introduction\b", re.I)),
    ("Methodology",
     re.compile(r"^(?:\d+[\.\)]?\s+)?(?:methods?|methodology|"
                r"materials\s+and\s+methods?|data\s+and\s+methods?|"
                r"empirical\s+(?:strategy|design|framework|specification)|"
                r"experimental\s+(?:design|setup|procedure))\b", re.I)),
    ("Results", re.compile(r"^(?:\d+[\.\)]?\s+)?(?:results?|findings|empirical\s+results?)\b", re.I)),
    ("Discussion", re.compile(r"^(?:\d+[\.\)]?\s+)?(?:discussion|results?\s+and\s+discussion)\b", re.I)),
    ("Conclusion", re.compile(r"^(?:\d+[\.\)]?\s+)?(?:conclusions?|concluding\s+remarks)\b", re.I)),
    ("Appendix", re.compile(r"^appendix(?:\s+[A-Z0-9])?\b", re.I)),
    ("References", re.compile(r"^(?:references|bibliography|works\s+cited)\b", re.I)),
]


def _each_line_start(body: str) -> list[int]:
    """Return the char offset of the start of every line (incl. offset 0)."""
    starts = [0]
    for m in re.finditer(r"\n", body):
        starts.append(m.end())
    return starts


def _line_at(body: str, start: int) -> str:
    end = body.find("\n", start)
    return body[start:] if end == -1 else body[start:end]


def detect_sections(body: str) -> list[Section]:
    """Return the ordered sections whose headings appear at line starts."""
    sections: list[Section] = []
    seen: set[str] = set()
    for start in _each_line_start(body):
        line = _line_at(body, start).strip()
        if not line:
            continue
        for name, pat in _SECTIONS:
            if pat.match(line) and name not in seen:
                seen.add(name)
                sections.append(Section(name=name, start=start))
                break
    return sections


def mark_sections(body: str, sections: list[Section] | None = None) -> str:
    """Insert ``<!-- SECTION: X -->`` markers above each detected heading.

    Insertion happens from the end backwards so earlier offsets stay valid.
    """
    if sections is None:
        sections = detect_sections(body)
    out = body
    for sec in reversed(sections):
        marker = f"<!-- SECTION: {sec.name} -->"
        out = out[:sec.start] + marker + "\n" + out[sec.start:]
    return out


# ---- Reference strip ------------------------------------------------------
# A "References" heading followed by something plausibly reference-shaped
# (numbered entries, or author names + years).  We only cut when this looks
# like a real reference back-matter to avoid eating the body of the paper.
_REF_ENTRY = re.compile(
    r"(?:\[\d+\]|\d{1,3}\s*[\.\)])\s|"
    r"^(?:[A-Z][\w’'\-]+\s,?\s+)+\((?:19\d{2}|20\d{2})\)",
    re.MULTILINE,
)


def find_references_boundary(body: str) -> int | None:
    """Return the char offset of the References heading, or None if unsure."""
    ref: Section | None = None
    for sec in detect_sections(body):
        if sec.name == "References":
            ref = sec
            break
    if ref is None:
        return None

    # Validate: within the next ~15 lines there should be reference-shaped
    # text (numbered entries or author+year) before we dare cut.
    tail = body[ref.start:]
    for _ in range(15):
        if not tail:
            break
        line = tail.split("\n", 1)[0]
        if _REF_ENTRY.search(line) or re.search(r"\b(?:19|20)\d{2}\b", line):
            return ref.start
        tail = tail.split("\n", 1)[1] if "\n" in tail else ""
    return None


def strip_references(body: str) -> tuple[str, bool]:
    """Remove the reference back-matter; return (new_body, was_stripped)."""
    boundary = find_references_boundary(body)
    if boundary is None:
        return body, False
    head = body[:boundary].rstrip()
    # Append the heading line itself is stripped too.
    return head, True