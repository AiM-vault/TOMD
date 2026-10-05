"""PDF parser: text extraction, layout awareness and ruff cleanup for papers.

Uses pdfplumber.  Responsibilities:
  * two-tier scanned-detection (no text layer -> mark SCANNED, never OCR)
  * optional light-weight multi-column detection (word x0 gutter heuristic)
  * cross-page repeated header/footer & page-number removal (page 1 protected)
  * line reflow into paragraphs, with line-break dehyphenation
  * table extraction to markdown (degrades merged/complex tables to text)
  * figure placeholders and formula markers

This is deliberately a *noise reducer*, not a layout forensics tool — see
DECISIONS D2.  Quality is bounded by what pdfplumber exposes.  Column split
happens at the *word* level (before line grouping) so that two columns sharing
a baseline never get fused into a single visual line.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import pdfplumber  # type: ignore
from pdfplumber.page import Page  # type: ignore

from ..models import ParseResult, SourceKind
from .base import BaseParser, ParserError

_INDENT_TOL_PT = 4.0           # paragraph indent signal
_MIN_HEADER_REPEAT_FRAC = 0.5   # a line repeated on >=50% of pages => header
_PAGE_NUM = re.compile(r"^\s*\d{1,4}\s*$")
_FORMULA_CHARS = re.compile(r"[≤≥∑√∫≠≈±−∞θσΔ×]")
_HEADINGISH = re.compile(
    r"^(?:\d{1,2}[\.\)]\s*)?[A-Z][A-Za-z0-9\s&/:()\-–—]{0,60}[:]?$")


@dataclass
class _Line:
    top: float
    x0: float
    x1: float
    text: str


@dataclass
class _Block:
    top: float
    kind: str
    content: str


class PdfParser(BaseParser):
    kind = SourceKind.PDF

    def __init__(self, no_columns: bool = False, no_table: bool = False) -> None:
        self.no_columns = no_columns
        self.no_table = no_table

    # ------------------------------------------------------------------ parse
    def parse(self, source_path: str, relative_path: str) -> ParseResult:
        result = ParseResult(relative_path=relative_path, source_kind=self.kind)
        try:
            with pdfplumber.open(source_path) as pdf:
                return self._parse_pdf(pdf, result)
        except ParserError:
            raise
        except Exception as exc:  # everything else: corrupt / encrypted / etc.
            raise ParserError(f"cannot open/parse PDF: {exc}") from exc

    def _parse_pdf(self, pdf, result: ParseResult) -> ParseResult:  # type: ignore[override]
        pages = pdf.pages

        # ---- tier 1: any extractable text? ----------------------------------
        page_texts: list[str] = [p.extract_text() or "" for p in pages]

        # ---- tier 2: any words at all? --------------------------------------
        total_words = sum(len(p.extract_words()) for p in pages)
        if not any(t.strip() for t in page_texts) and total_words == 0:
            result.is_scanned = True
            result.scanned_reason = "no text layer found (image-only document)"
            result.body = "**【SCANNED DOCUMENT: 无法提取文本】** 此 PDF 为扫描版或纯图像，本版本不包含 OCR。"
            result.add_warning("scanned PDF — no OCR applied (by design)")
            return result

        # ---- header/footer fingerprint across pages -------------------------
        page_lines = [self._page_lines(p) for p in pages]
        header_set, footer_set = self._detect_runners(page_lines)

        blocks: list[_Block] = []
        for idx, p in enumerate(pages):
            self._render_page(p, idx, header_set, footer_set, blocks)
        body = self._assemble(blocks)
        result.body = self._mark_formulas(body)
        return result

    def _render_page(self, page: Page, idx: int,
                     header_set: set[str], footer_set: set[str],
                     blocks: list[_Block]) -> None:
        words = page.extract_words()
        collections = self._partition_words(words, page.width) if not self.no_columns else [words]

        column_blocks: list[_Block] = []
        for col_words in collections:
            lines = self._words_to_lines(col_words)
            if not lines:
                continue
            lines = self._drop_runners(lines, header_set, footer_set, is_first_page=(idx == 0))
            if not lines:
                continue
            column_blocks += self._reflow_paragraphs([lines])

        page_blocks = column_blocks + self._tables_to_blocks(page) + self._figures_to_blocks(page)
        page_blocks.sort(key=lambda b: b.top)
        blocks.extend(page_blocks)

    # ------------------------------------------------------------------ lines
    @staticmethod
    def _words_to_lines(word_list: list[dict]) -> list[_Line]:
        """Group *single-column* words into visual lines (top -> bottom)."""
        if not word_list:
            return []
        rows: dict[int, list[dict]] = {}
        for w in word_list:
            rows.setdefault(round(w["top"] / 5), []).append(w)
        lines: list[_Line] = []
        for top_bucket in sorted(rows):
            words = sorted(rows[top_bucket], key=lambda w: w["x0"])
            text = " ".join(w["text"] for w in words).strip()
            if not text:
                continue
            lines.append(_Line(
                top=min(w["top"] for w in words),
                x0=min(w["x0"] for w in words),
                x1=max(w["x1"] for w in words),
                text=text,
            ))
        return lines

    @staticmethod
    def _page_lines(page: Page) -> list[_Line]:
        """Whole-page lines (used only for header/footer fingerprinting)."""
        return PdfParser._words_to_lines(page.extract_words())

    # ---------------------------------------------------------------- columns
    def _partition_words(self, words: list[dict], page_width: float) -> list[list[dict]]:
        """Split words into 1 or 2 columns based on an x0 gutter histogram.

        The gutter is where word *centre* density is low in the middle band of
        the page.  A few spanning caption words won't push the band over the
        (relative) threshold, so genuine single-column pages stay undivided.
        """
        if len(words) < 24:
            return [words]
        lo = min(w["x0"] for w in words)
        hi = max(w["x1"] for w in words)
        span = hi - lo
        if span <= 0:
            return [words]
        BINS = 80
        cnt = [0] * BINS
        for w in words:
            c = (w["x0"] + w["x1"]) / 2
            b = int((c - lo) / span * BINS)
            cnt[min(BINS - 1, max(0, b))] += 1
        peak = max(cnt) or 1
        thresh = max(2, int(peak * 0.08))
        mid_lo, mid_hi = int(0.35 * BINS), int(0.65 * BINS)

        best_w = 0
        best_start = best_end = -1
        run_start: int | None = None
        for b in range(mid_lo, mid_hi + 1):
            low = cnt[b] < thresh
            if low and run_start is None:
                run_start = b
            elif not low and run_start is not None:
                width = b - run_start
                if width > best_w:
                    best_w, best_start, best_end = width, run_start, b
                run_start = None
        if run_start is not None:
            width = (mid_hi + 1) - run_start
            if width > best_w:
                best_w, best_start, best_end = width, run_start, mid_hi + 1

        if best_start < 0 or best_w < int(0.05 * BINS):
            return [words]
        split = lo + ((best_start + best_end) / 2.0 / BINS) * span

        left = [w for w in words if (w["x0"] + w["x1"]) / 2 < split]
        right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= split]
        if not left or not right:
            return [words]
        # physical gutter check: min. gap between column right/left edges
        if min(w["x0"] for w in right) - max(w["x1"] for w in left) < page_width * 0.03:
            return [words]
        return [left, right]

    # --------------------------------------------------- headers / footers
    @staticmethod
    def _detect_runners(page_lines: list[list[_Line]]) -> tuple[set[str], set[str]]:
        """Find line texts repeated as first/last lines on >=50% of pages."""
        n = len(page_lines)
        if n == 0:
            return set(), set()
        first_counter: Counter[str] = Counter()
        last_counter: Counter[str] = Counter()
        for lines in page_lines:
            if not lines:
                continue
            first_counter[lines[0].text] += 1
            last_counter[lines[-1].text] += 1
        threshold = max(2, int(n * _MIN_HEADER_REPEAT_FRAC))
        header_set = {t for t, c in first_counter.items() if c >= threshold}
        footer_set = {t for t, c in last_counter.items() if c >= threshold}
        return header_set, footer_set

    @staticmethod
    def _drop_runners(lines: list[_Line], header_set: set[str],
                      footer_set: set[str], is_first_page: bool) -> list[_Line]:
        """Remove header/footer/page-number lines (page 1 is protected)."""
        kept: list[_Line] = []
        for pos, line in enumerate(lines):
            if _PAGE_NUM.match(line.text):
                continue  # a lone page number is always noise
            if is_first_page:
                kept.append(line)
                continue
            is_edge = pos < 2 or pos >= len(lines) - 2
            if is_edge and line.text in (header_set | footer_set):
                continue
            kept.append(line)
        return kept

    # ---------------------------------------------------------------- reflow
    @staticmethod
    def _reflow_paragraphs(columns: list[list[_Line]]) -> list[_Block]:
        """Merge each column's visual lines into paragraphs (conservative).

        A new paragraph starts only when there's a positive signal: the line is
        heading-like, the line starts with an indent, or the previous line was
        short.  Otherwise lines are joined (with dehyphenation) — deliberately
        erring *towards* fewer, longer paragraphs (see PENDING #1).
        """
        blocks: list[_Block] = []
        for col in columns:
            if not col:
                continue
            left_margin = Counter(l.x0 for l in col).most_common(1)[0][0]
            right_edge = max(l.x1 for l in col)
            col_width = max(1.0, right_edge - left_margin)
            paras: list[tuple[float, list[str]]] = []
            cur: list[str] = []
            cur_top: float | None = None
            cur_last_x1: float | None = None

            def flush() -> None:
                nonlocal cur, cur_top
                if cur:
                    paras.append((cur_top or 0.0, cur))
                    cur, cur_top = [], None

            for line in col:
                text = line.text.strip()
                if PdfParser._is_heading(line):
                    flush()
                    paras.append((line.top, [text]))
                    cur_last_x1 = None
                    continue
                new_para = False
                if cur_top is not None and cur_last_x1 is not None:
                    if line.x0 > left_margin + _INDENT_TOL_PT:
                        new_para = True
                    else:
                        fill = (cur_last_x1 - left_margin) / col_width
                        if fill < 0.55 and cur:
                            new_para = True
                if new_para:
                    flush()
                if cur_top is None:
                    cur_top = line.top
                cur = PdfParser._merge(cur, text)
                cur_last_x1 = line.x1
            flush()

            for top, words in paras:
                blocks.append(_Block(top=top, kind="para", content=" ".join(words)))
        return blocks

    @staticmethod
    def _merge(accum: list[str], next_line: str) -> list[str]:
        """Join a line onto the current paragraph with line-break dehyphenation."""
        if not accum:
            return [next_line]
        joined = accum[-1]
        if joined.endswith("-") and next_line[:1].islower():
            # soft line-break: "meth-" + "od" -> "method" (no space)
            accum[-1] = joined[:-1].rstrip() + next_line
        else:
            accum[-1] = joined + " " + next_line
        return accum

    @staticmethod
    def _is_heading(line: _Line) -> bool:
        text = line.text.strip()
        if not (0 < len(text) < 90):
            return False
        return bool(_HEADINGISH.match(text))

    # ------------------------------------------------------- tables / figures
    def _tables_to_blocks(self, page: Page) -> list[_Block]:
        try:
            found = page.find_tables()
        except Exception:
            return []
        blocks: list[_Block] = []
        for table in found:
            top = table.bbox[1] if table.bbox else 0.0
            if self.no_table:
                blocks.append(_Block(top=top, kind="table_placeholder",
                                      content="<!-- TABLE: 原表格已按 --no-table 省略 -->"))
                continue
            data = table.extract() or []
            blocks.append(_Block(top=top, kind="table", content=self._render_table(data)))
        return blocks

    @staticmethod
    def _render_table(data: list[list[str | None]]) -> str:
        if not data or not data[0]:
            return "<!-- TABLE: 空表格 -->"
        grid: list[list[str]] = [[(c or "").replace("\n", " ").strip() for c in row] for row in data]
        widths = max(len(r) for r in grid)
        for r in grid:
            while len(r) < widths:
                r.append("")
        out = ["| " + " | ".join(grid[0]) + " |", "|" + "---|" * widths]
        for row in grid[1:]:
            out.append("| " + " | ".join(row) + " |")
        return "\n".join(out)

    @staticmethod
    def _figures_to_blocks(page: Page) -> list[_Block]:
        try:
            images = page.images or []
        except Exception:
            return []
        blocks: list[_Block] = []
        for img in images:
            area = img.get("width", 0.0) * img.get("height", 0.0)
            if area < 1500.0:  # tiny inline ornaments are not figures
                continue
            blocks.append(_Block(top=img.get("top", 0.0), kind="figure",
                                 content="<!-- FIGURE: PDF页面图片 -->"))
        return blocks

    # --------------------------------------------------------------- assemble
    @staticmethod
    def _assemble(blocks: list[_Block]) -> str:
        out: list[str] = []
        for b in blocks:
            if b.kind == "para":
                out.append(b.content)
            else:
                out.append("")
                out.append(b.content)
                out.append("")
        text = "\n".join(out)
        return re.sub(r"\n{3,}", "\n\n", text).strip()

    @staticmethod
    def _mark_formulas(text: str) -> str:
        """Wrap formula-looking lines with a FORMULA marker (best-effort)."""
        lines = text.split("\n")
        out: list[str] = []
        prev_formula = False
        for line in lines:
            if _FORMULA_CHARS.search(line) and len(line) > 2:
                marker = "<!-- FORMULA -->"
                if not prev_formula:
                    out.append(marker)
                out.append(line)
                prev_formula = True
            else:
                out.append(line)
                prev_formula = False
        return "\n".join(out)