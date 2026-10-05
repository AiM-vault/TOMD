"""Parser package for source documents (PDF and DOCX)."""

from .base import BaseParser, ParserError
from .docx_parser import DocxParser
from .pdf_parser import PdfParser

__all__ = ["BaseParser", "ParserError", "DocxParser", "PdfParser"]