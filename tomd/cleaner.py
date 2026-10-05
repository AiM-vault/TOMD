"""AI-friendly text cleaning: whitespace, line-break dehyphenation, noise.

This module turns the parser's raw scaffold into a tidy, low-noise document
suitable for LLM ingestion.  It is intentionally *conservative*: it never
rewrites meaning, only normalises formatting.  Everything here is a pure
function of the input text, which keeps it easy to unit-test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A line-break hyphen takes the form: "meth-" followed by a newline, then the
# continuation.  We only merge when the continuation starts with a lowercase
# letter, so genuine hyphenated words ("self-referential") are preserved.
_LINE_BREAK_HYPHEN = re.compile(r"-\n([a-z]{2,})")

# Collapse runs of 3+ spaces and multiple consecutive blank lines.
_EXCESS_SPACES = re.compile(r"[ \t]{2,}")
_EXCESS_BLANKS = re.compile(r"\n{3,}")

# Lines that are pure page numbers / bullets / ornamentation (candidate noise).
_SOLITARY_NUMBER = re.compile(r"^\s*\d+\s*$")
_ORNAMENT = re.compile(r"^\s*[*•◦\-–—·\.\s]*\s*$")


@dataclass
class CleanStats:
    """Counters used as the objective acceptance metric (see D8)."""

    page_number_lines: int = 0   # junk page-number lines removed
    over_glued_lines: int = 0    # lines that look pathologically over-merged
    sections_marked: int = 0
    reference_stripped: bool = False


@dataclass
class CleanedDocument:
    body: str
    sections: list[dict] = field(default_factory=list)
    stats: CleanStats = field(default_factory=CleanStats)
    reference_stripped: bool = False


def dehyphenate(text: str) -> str:
    """Join soft line-break hyphens: ``meth-\\n od`` -> ``method``."""
    return _LINE_BREAK_HYPHEN.sub(r"\1", text)


def collapse_whitespace(text: str) -> str:
    """Remove excess spacing while preserving paragraph and line structure."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _EXCESS_SPACES.sub(" ", text)
    text = text.replace("  *", " *")  # common markdown bullet artifact
    text = _EXCESS_BLANKS.sub("\n\n", text)
    return text.strip()


def is_junk_line(line: str) -> bool:
    """True for lines that carry no information (page numbers, ornaments).

    Blank lines are *not* junk — they are the document's own paragraph
    separators (handled by :func:`collapse_whitespace`) and must not count.
    """
    stripped = line.strip()
    if not stripped:
        return False
    return bool(_SOLITARY_NUMBER.match(stripped)) or bool(_ORNAMENT.match(stripped))


def clean_text(body: str) -> CleanedDocument:
    """Apply the full deterministic cleaning chain to a raw scaffold."""
    text = dehyphenate(body)
    text = collapse_whitespace(text)

    stats = CleanStats()
    kept: list[str] = []
    for line in text.split("\n"):
        if is_junk_line(line):
            stats.page_number_lines += 1
            continue
        if len(line) > 900:
            stats.over_glued_lines += 1
        kept.append(line)
    text = "\n".join(kept)

    doc = CleanedDocument(body=text, stats=stats)
    return doc


def clean_result_body(body: str) -> CleanedDocument:
    """Convenience wrapper producing a CleanedDocument from a body string."""
    return clean_text(body)