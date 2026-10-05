"""End-to-end orchestration: scan -> parse (parallel+cached) -> clean -> write -> report."""

from __future__ import annotations

import hashlib
import logging
import pickle
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from . import section
from .cleaner import clean_text
from .config import OUT_MODE_FLAT, OUT_MODE_MIRROR, Options
from .models import FileRecord, ParseError, ParseResult, SourceKind
from .parsers.docx_parser import DocxParser
from .parsers.pdf_parser import PdfParser
from .report import ConversionStats, write_report
from .scanner import already_processed, discover, output_target

log = logging.getLogger("tomd.pipeline")


# ---------------------------------------------------------------- worker
def process_one_task(opts: Options, source_path: str, relative_path: str,
                     kind_value: str) -> dict:
    """Parse + clean a single file in a worker process.

    Returns a fully serializable dict so the main process can write the .md
    and tally the report.  Never raises for per-file problems — it encodes
    them in the returned status.
    """
    kind = SourceKind(kind_value)
    record = FileRecord(source_path=source_path, relative_path=relative_path, kind=kind)
    result: dict = {"relative_path": relative_path, "kind": kind_value,
                    "status": "ok", "content": "", "reason": "",
                    "warnings": [], "reference_stripped": False,
                    "stats": {}}

    try:
        parsed = _parse_cached(opts, record)
    except ParseError as exc:
        result["status"] = "failed"; result["reason"] = str(exc)
        return result
    except Exception as exc:
        result["status"] = "failed"; result["reason"] = f"unexpected: {exc}"
        return result

    if parsed.is_scanned:
        result["status"] = "scanned"
        result["content"] = parsed.body
        return result

    cleaned = _clean(parsed, opts)
    result["content"] = _finalize_md(opts, parsed, cleaned)
    result["warnings"] = parsed.warnings
    result["reference_stripped"] = cleaned.reference_stripped
    result["stats"] = {
        "page_number_lines": cleaned.stats.page_number_lines,
        "sections_marked": cleaned.stats.sections_marked,
        "over_glued_lines": cleaned.stats.over_glued_lines,
    }
    return result


def _parse_cached(opts: Options, record: FileRecord) -> ParseResult:
    cache_dir = opts.resolved_cache()
    if cache_dir is not None:
        cached = _load_cache(cache_dir, opts, record)
        if cached is not None:
            return cached
    result = _parse_uncached(opts, record)
    if cache_dir is not None:
        _save_cache(cache_dir, opts, record, result)
    return result


def _parse_uncached(opts: Options, record: FileRecord) -> ParseResult:
    if record.kind == SourceKind.DOCX:
        parser = DocxParser()
    else:
        parser = PdfParser(no_columns=opts.no_columns, no_table=opts.no_table)
    return parser.parse(record.source_path, record.relative_path)


def _clean(parsed: ParseResult, opts: Options):
    cleaned = clean_text(parsed.body)
    sections = section.detect_sections(cleaned.body)
    cleaned.body = section.mark_sections(cleaned.body, sections)
    cleaned.sections = [{"name": s.name} for s in sections]
    cleaned.stats.sections_marked = len(sections)
    if opts.strip_reference:
        stripped, was = section.strip_references(cleaned.body)
        cleaned.body = stripped
        cleaned.reference_stripped = was
    return cleaned


def _finalize_md(opts: Options, parsed: ParseResult, cleaned) -> str:
    header = f"<!-- TOMD: {parsed.filename} ({parsed.source_kind.value}) -->\n"
    flags = []
    if opts.strip_reference:
        flags.append("strip-reference")
    if opts.no_table:
        flags.append("no-table")
    if flags:
        header += f"<!-- options: {', '.join(flags)} -->\n"
    payload = cleaned.body
    if cleaned.reference_stripped:
        payload += "\n\n<!-- 已按 --strip-reference 移除参考文献 -->\n"
    return header + payload


# ----------------------------------------------------------------- cache
def _cache_path(cache_dir: Path, opts: Options, record: FileRecord) -> Path:
    p = Path(record.source_path)
    digest = hashlib.sha256(
        f"{str(p.resolve())}|{p.stat().st_size}|{p.stat().st_mtime_ns}"
        f"|{record.kind.value}|{opts.no_table}|{opts.no_columns}".encode()
    ).hexdigest()
    return cache_dir / f"{digest}.pkl"


def _load_cache(cache_dir: Path, opts: Options, record: FileRecord) -> ParseResult | None:
    try:
        path = _cache_path(cache_dir, opts, record)
        if not path.exists():
            return None
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        return ParseResult(relative_path=record.relative_path,
                           source_kind=record.kind,
                           body=data["body"],
                           is_scanned=data.get("is_scanned", False),
                           scanned_reason=data.get("scanned_reason", ""),
                           warnings=data.get("warnings", []))
    except Exception:
        return None  # corrupt/absent cache => re-parse


def _save_cache(cache_dir: Path, opts: Options, record: FileRecord, result: ParseResult) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = _cache_path(cache_dir, opts, record)
        with open(path, "wb") as fh:
            pickle.dump({"body": result.body, "is_scanned": result.is_scanned,
                         "scanned_reason": result.scanned_reason,
                         "warnings": result.warnings}, fh, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception:
        pass  # cache is best-effort; a write failure must never fail the job


# --------------------------------------------------------------- runner
class BatchRunner:
    def __init__(self, options: Options) -> None:
        self.options = options
        self.stats = ConversionStats()
        self._scanned: list[str] = []

    def run(self) -> ConversionStats:
        opts = self.options
        source = opts.resolved_source()
        dest = opts.resolved_dest()
        cache_dir = opts.resolved_cache()

        # Mode "src" (out-mode 1) writes next to each source and has no --dest,
        # so the report must land somewhere sensible instead of the CWD.
        report_dir = dest if opts.out_mode in (OUT_MODE_FLAT, OUT_MODE_MIRROR) else source

        records = discover(source)
        log.info("found %d supported file(s) under %s", len(records), source)
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)

        # ---- resolve targets + decide skip (cheap, in main process) --------
        jobs: list[tuple[FileRecord, Path, bool]] = []
        for rec in records:
            target = output_target(opts, rec)
            skip = already_processed(target, opts.overwrite)
            jobs.append((rec, target, skip))

        n_skip = sum(1 for _, _, s in jobs if s)
        if n_skip:
            self.stats.skipped = n_skip
            self.stats.total = len(jobs)
            self.stats.targets += [(str(t), r.relative_path) for r, t, s in jobs if s]
            log.info("skip %d already-processed file(s)", n_skip)

        to_process = [(r, t) for r, t, s in jobs if not s]
        if not to_process:
            self._finish(report_dir)
            return self.stats

        self.stats.total = len(jobs)
        # ensure output parents exist before parallel writers
        all_targets = {t for _, t in to_process}
        for t in all_targets:
            t.parent.mkdir(parents=True, exist_ok=True)

        # ---- parallel parse+clean ------------------------------------------
        n_workers = min(opts.worker_count(), max(1, len(to_process)))
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {}
            for rec, target in to_process:
                future = pool.submit(process_one_task, opts, rec.source_path,
                                     rec.relative_path, rec.kind.value)
                futures[future] = (rec, target)
            for future in futures:
                rec, target = futures[future]
                try:
                    self._handle_result(rec, target, future.result())
                except Exception as exc:  # a worker itself died
                    self._fail(rec, f"worker crashed: {exc}")

        self._finish(report_dir)
        return self.stats

    # ------------------------------------------------------------ handling
    def _handle_result(self, rec: FileRecord, target: Path, res: dict) -> None:
        status = res.get("status")
        if status == "failed":
            self._fail(rec, res.get("reason", "unknown"))
            return
        if status == "scanned":
            self.stats.scanned_pdfs.append(rec.relative_path)
            if self.options.skip_scanned:
                self.stats.skipped += 1
            else:
                self._write(target, res.get("content", ""))
                self.stats.record_target(str(target.resolve()), rec.relative_path)
            return
        self._write(target, res.get("content", ""))
        self.stats.ok += 1
        self.stats.record_target(str(target.resolve()), rec.relative_path)
        log.info("ok: %s", rec.relative_path)

    def _write(self, target: Path, content: str) -> None:
        target.write_text(content, encoding="utf-8")

    def _fail(self, rec: FileRecord, reason: str) -> None:
        self.stats.failed += 1
        self.stats.failures.append((rec.relative_path, reason))
        log.error("FAILED: %s -> %s", rec.relative_path, reason)

    def _finish(self, dest: Path) -> None:
        report_path = write_report(dest, self.stats)
        log.info("done. %d ok / %d failed / %d skipped / %d scanned -> %s",
                 self.stats.ok, self.stats.failed, self.stats.skipped,
                 len(self.stats.scanned_pdfs), report_path)