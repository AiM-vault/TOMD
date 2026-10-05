"""DOCX parser: maps paragraphs, heading styles, tables and figures to markdown.

Labels are mapped to Markdown heading levels via the paragraph's ``style``
name.  Because python-docx documents already exclude the running headers and
footers when you walk the body, repeated headers/footers/page numbers are
silently excluded — no separate pass is needed.
"""

from __future__ import annotations

from docx import Document  # type: ignore
from docx.document import Document as DocxDocument  # type: ignore
from docx.enum.style import WD_STYLE_TYPE  # type: ignore
from docx.opc.constants import RELATIONSHIP_TYPE as RT  # type: ignore
from docx.table import Table as DocxTable  # type: ignore
from docx.text.paragraph import Paragraph as DocxParagraph  # type: ignore

from ..models import ParseResult, SourceKind
from .base import BaseParser, ParserError

# Map Word heading style names to markdown depth.
_HEADING_LEVEL = {
    "Title": 1,
    "Heading 1": 2,
    "Heading 2": 3,
    "Heading 3": 4,
    "Heading 4": 5,
    "Heading 5": 6,
}


class DocxParser(BaseParser):
    kind = SourceKind.DOCX

    def parse(self, source_path: str, relative_path: str) -> ParseResult:
        result = ParseResult(relative_path=relative_path, source_kind=self.kind)
        try:
            document = Document(source_path)
        except Exception as exc:  # corrupt / password-protected / not a docx
            raise ParserError(f"cannot open .docx: {exc}") from exc

        lines: list[str] = []
        for child in document.element.body:
            tag = child.tag.split("}")[-1]
            if tag == "p":
                para = DocxParagraph(child, document)
                lines.append(self._render_paragraph(para))
            elif tag == "tbl":
                table = DocxTable(child, document)
                lines.append(self._render_table(table))
            # anything else (sectPr, altChunk...) is skipped

        result.body = "\n\n".join(l for l in lines if l.strip())
        return result

    # -- helpers -------------------------------------------------------------
    def _render_paragraph(self, para: DocxParagraph) -> str:
        text = "".join(run.text for run in para.runs).strip()
        has_picture = self._has_image(para)
        if not text and not has_picture:
            return ""
        parts: list[str] = []
        level = self._heading_level(para)
        if level:
            parts.append("#" * level + " " + text if text else "")
        else:
            parts.append(text)
        if has_picture:
            parts.append("<!-- FIGURE: 原文档图片 -->")
        return "\n".join(p for p in parts if p)

    @staticmethod
    def _heading_level(para: DocxParagraph) -> int:
        style = (para.style.name if para.style is not None else "") or ""
        return _HEADING_LEVEL.get(style, 0)

    @staticmethod
    def _has_image(para: DocxParagraph) -> bool:
        xml = para._p.xml
        # detect inline picture/drawing blip reference r:embed / a:blip
        return "graphic" in xml and ("blipFill" in xml or "pic:pic" in xml)

    @staticmethod
    def _render_table(table: DocxTable) -> str:
        """Render a table to markdown.  Merged/empty cells degrade to text."""
        rows: list[list[str]] = []
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                cell_text = " ".join(
                    p.text.strip() for p in cell.paragraphs if p.text.strip()
                ).strip()
                cell_text = cell_text.replace("\n", " ")
                cells.append(cell_text)
            rows.append(cells)
        if not rows:
            return "<!-- TABLE: 空表格 -->"
        widths = max(len(r) for r in rows)
        for r in rows:
            while len(r) < widths:
                r.append("")
        header = rows[0]
        out = ["| " + " | ".join(header) + " |", "|" + "---|" * widths]
        for row in rows[1:]:
            out.append("| " + " | ".join(row) + " |")
        return "\n".join(out)