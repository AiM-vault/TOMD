"""Base class and shared exceptions for TOMD parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from ..models import ParseError, ParseResult, SourceKind


class ParserError(Exception):
    """Raised internally when a parser cannot make sense of a file."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

    def to_parse_error(self) -> ParseError:
        return ParseError(self.reason)


class BaseParser(ABC):
    """Abstract interface every document parser implements.

    Subclasses are responsible for producing the markdown *scaffold* (headings,
    tables, figure placeholders) — the cleaner then normalises it downstream.
    """

    kind: SourceKind

    @abstractmethod
    def parse(self, source_path: str, relative_path: str) -> ParseResult:
        """Return a ParseResult for one file.  Raise ParseError on hard failure.

        Hard failures (corrupt/encrypted/unreadable) should raise ParseError;
        recoverable oddities should be recorded as warnings on the result.
        """
        ...


class ParserFactory(Protocol):
    def get_parser(self, kind: SourceKind) -> BaseParser: ...