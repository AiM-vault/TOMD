"""CLI option container and pure helpers shared across the pipeline."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path


# Output placement modes (see --out-mode).
OUT_MODE_SRC = 1   # alongside each source file
OUT_MODE_FLAT = 2  # all outputs flattened into --dest
OUT_MODE_MIRROR = 3  # --dest, mirroring the source sub-directory structure


@dataclass
class Options:
    """Resolution of every CLI flag, passed through the whole pipeline.

    Keeping this as one plain dataclass (instead of threading many keyword
    arguments) makes each stage testable in isolation and keeps the CLI
    surface decoupled from the internals.
    """

    source: str
    dest: str = ""
    overwrite: bool = False
    strip_reference: bool = False
    skip_scanned: bool = False
    no_table: bool = False
    no_columns: bool = False
    out_mode: int = OUT_MODE_MIRROR   # 1=src, 2=flat, 3=mirror
    workers: int = 0                  # 0 => auto (cpu count)
    cache: str = ""                   # optional cache dir for parsed text
    verbose: bool = False
    warnings: list[str] = field(default_factory=list)

    def resolved_source(self) -> Path:
        return Path(self.source).expanduser().resolve()

    def resolved_dest(self) -> Path:
        return Path(self.dest).expanduser().resolve()

    def resolved_cache(self) -> Path | None:
        return Path(self.cache).expanduser().resolve() if self.cache else None

    def worker_count(self) -> int:
        if self.workers > 0:
            return self.workers
        import os
        return max(1, min(os.cpu_count() or 1, 8))


def configure_logging(verbose: bool) -> None:
    """Set up the stdlib logger used by every module.

    Info/error lines go to stderr, leaving stdout clean for Typer's own
    rendering; verbose turns on DEBUG for the parser internals.
    """
    import logging

    # Force UTF-8 on stdio so Chinese log/report lines render correctly on
    # Windows consoles that default to cp936/GBK (files are always UTF-8).
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def safe_stem(relative_path: str) -> str:
    """Return the stem of a forward-slash relative path (used for mirrors)."""
    return relative_path.rsplit("/", 1)[-1].rsplit(".", 1)[0] if "/" in relative_path or "." in relative_path else relative_path