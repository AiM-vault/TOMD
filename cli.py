"""TOMD command-line interface (Typer).

Usage::

    python cli.py --source samplepapers --dest out
    python cli.py --source samplepapers --dest all --out-mode 2 --workers 4
    python cli.py --source samplepapers --out-mode 1          # next to sources
"""

from __future__ import annotations

from typing import Optional

import typer

from tomd.config import (OUT_MODE_FLAT, OUT_MODE_MIRROR, OUT_MODE_SRC,
                         Options, configure_logging)
from tomd.pipeline import BatchRunner
from tomd.report import build_report

app = typer.Typer(
    name="tomd",
    help="Academic PDF/DOCX -> AI-friendly Markdown batch preprocessor.",
    add_completion=False,
)

_OUT_HELP = (
    "Where to write output .md files: "
    f"{OUT_MODE_SRC}=next to each source file, "
    f"{OUT_MODE_FLAT}=all flattened into --dest, "
    f"{OUT_MODE_MIRROR}=into --dest mirroring source folders (default)."
)


@app.command()
def convert(
    source: str = typer.Option(..., "--source", "-s", help="Source directory to scan recursively."),
    dest: Optional[str] = typer.Option(None, "--dest", "-d", help="Destination directory (needed for --out-mode 2/3)."),
    out_mode: int = typer.Option(OUT_MODE_MIRROR, "--out-mode", help=_OUT_HELP),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing .md (default: skip)."),
    strip_reference: bool = typer.Option(False, "--strip-reference", help="Remove the reference back-matter."),
    skip_scanned: bool = typer.Option(False, "--skip-scanned", help="Skip scanned PDFs entirely."),
    no_table: bool = typer.Option(False, "--no-table", help="Replace tables with a placeholder comment."),
    no_columns: bool = typer.Option(False, "--no-columns", help="Disable multi-column detection."),
    workers: int = typer.Option(0, "--workers", "-w", help="Parallel workers (0 = auto)."),
    cache: Optional[str] = typer.Option(None, "--cache", help="Cache parsed text here to skip re-extraction on re-runs."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Debug-level logging."),
) -> None:
    """Convert every supported file under SOURCE into Markdown."""
    if out_mode in (OUT_MODE_FLAT, OUT_MODE_MIRROR) and not dest:
        typer.echo("error: --dest is required when --out-mode is 2 or 3.", err=True)
        raise typer.Exit(code=2)

    options = Options(
        source=source,
        dest=dest or "",
        out_mode=out_mode,
        overwrite=overwrite,
        strip_reference=strip_reference,
        skip_scanned=skip_scanned,
        no_table=no_table,
        no_columns=no_columns,
        workers=workers,
        cache=cache or "",
        verbose=verbose,
    )
    configure_logging(verbose)
    runner = BatchRunner(options)
    stats = runner.run()
    typer.echo(build_report(stats))


if __name__ == "__main__":
    app()