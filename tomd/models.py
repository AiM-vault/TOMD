"""Shared data structures used across TOMD modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class SourceKind(str, Enum):
    """Kind of source document a parser understands."""

    PDF = "pdf"
    DOCX = "docx"


class ParseError(Exception):
    """Raised when a source file cannot be opened or parsed.

    This is distinct from a normal scan result and always carries a
    human-readable reason so the report can log *why* a file failed
    without aborting the whole batch.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Section:
    """A detected bibliographic section (Abstract, Methods, ...)."""

    name: str                # logical name, e.g. "Abstract"
    heading: str             # the raw heading text matched in the document
    start: int               # character offset (start) into the body text
    end: int                 # character offset (end) into the body text


@dataclass
class ParseResult:
    """Normal output of a parser for one source document.

    ``body`` is the raw-ish markdown text produced by the parser *before*
    the AI-friendly cleaner runs. Headings, tables and figure placeholders
    are already scaffolded at this point; whitespace/dehyphenation/section
    marking happen later in the cleaner pipeline.
    """

    relative_path: str                 # e.g. "procurement/Boland-2021.pdf"
    source_kind: SourceKind
    body: str = ""                       # markdown scaffold (pre-clean)
    is_scanned: bool = False             # PDF had no text layer
    scanned_reason: str = ""             # detail for the report
    warnings: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        """Basename of the source relative path."""
        return self.relative_path.rsplit("/", 1)[-1]

    def add_warning(self, message: str) -> None:
        """Attach a non-fatal note (e.g. degraded table) to the result."""
        self.warnings.append(message)


@dataclass
class FileRecord:
    """A single file discovered by the scanner."""

    source_path: str          # absolute path on disk
    relative_path: str        # path relative to the source root (forward slashes)
    kind: SourceKind