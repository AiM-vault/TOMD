"""TOMD — Academic PDF/DOCX → AI-friendly Markdown batch preprocessor.

A lightweight, engineering-oriented CLI that recursively scans a directory
for academic PDF/DOCX files, parses their text, cleans it for downstream LLM
consumption (literature reviews, information extraction), and writes matching
Markdown files while mirroring the source directory structure.

Deliberately *not* an OCR or layout-forensics tool: the goal is noise
reduction and text quality, not perfect reproduction of the printed page.
"""

from .config import Options
from .models import ParseResult, SourceKind

__version__ = "0.1.0"
__all__ = ["Options", "ParseResult", "SourceKind", "__version__"]