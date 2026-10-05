"""Recursive source-file discovery and destination-path mirroring."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from .config import OUT_MODE_FLAT, OUT_MODE_MIRROR, OUT_MODE_SRC, Options
from .models import FileRecord, SourceKind

_SUPPORTED = {SourceKind.PDF: ".pdf", SourceKind.DOCX: ".docx"}


def _kind_for(suffix: str) -> SourceKind | None:
    suffix = suffix.lower()
    for kind, ext in _SUPPORTED.items():
        if suffix == ext:
            return kind
    return None


def discover(source: Path) -> list[FileRecord]:
    """Recursively collect every supported file under ``source``.

    Returns records sorted deterministically (by relative path) so runs are
    reproducible.  ``relative_path`` always uses forward slashes, which we also
    use to mirror the directory structure into the destination.
    """
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"source directory does not exist: {source}")
    files: list[FileRecord] = []
    for root, _dirs, names in os.walk(source):
        for name in sorted(names):
            suffix = Path(name).suffix
            kind = _kind_for(suffix)
            if kind is None:
                continue
            full = Path(root) / name
            rel = full.relative_to(source).as_posix()
            files.append(FileRecord(source_path=str(full), relative_path=rel, kind=kind))
    files.sort(key=lambda r: r.relative_path)
    return files


def md_name(relative_path: str, kind: SourceKind) -> str:
    """Build the output filename ``tomd_<stem>_<pdf|docx>.md``."""
    stem = relative_path.rsplit(".", 1)[0].rsplit("/", 1)[-1]
    return f"tomd_{stem}_{kind.value}.md"


def output_target(opts: Options, record: FileRecord) -> Path:
    """Resolve where a record's ``.md`` should be written for the active mode.

    * OUT_MODE_SRC   — next to the source file itself.
    * OUT_MODE_FLAT  — all outputs flattened into ``--dest``.
    * OUT_MODE_MIRROR — into ``--dest`` mirroring the source folder tree.
    """
    name = md_name(record.relative_path, record.kind)
    if opts.out_mode == OUT_MODE_SRC:
        return Path(record.source_path).parent / name
    if opts.out_mode == OUT_MODE_FLAT:
        return opts.resolved_dest() / name
    # OUT_MODE_MIRROR (default)
    parent = record.relative_path.rsplit("/", 1)[0] if "/" in record.relative_path else ""
    return (opts.resolved_dest() / parent / name) if parent else opts.resolved_dest() / name


def already_processed(target: Path, overwrite: bool) -> bool:
    """True if the target .md already exists and we must not overwrite it."""
    if not target.exists():
        return False
    return not overwrite


def iter_files(source: Path) -> Iterable[FileRecord]:
    """Lazy variant of :func:`discover` for streaming large corpora."""
    yield from discover(source)