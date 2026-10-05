"""Conversion statistics and the generated conversion_report.md."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConversionStats:
    total: int = 0
    ok: int = 0
    failed: int = 0
    skipped: int = 0
    scanned_pdfs: list[str] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)
    targets: list[tuple[str, str]] = field(default_factory=list)  # (output_path, rel)
    started: float = field(default_factory=time.time)

    def record_target(self, output: str, rel: str) -> None:
        self.targets.append((output, rel))


def _total_failures_message(stats: ConversionStats) -> str:
    if stats.failed == 0:
        return "无失败文件"
    return f"{stats.failed} 个文件失败："


def build_report(stats: ConversionStats) -> str:
    """Render the ASCII markdown report body (used by tests too)."""
    elapsed = time.time() - stats.started
    lines: list[str] = []
    lines.append("# Conversion Report")
    lines.append("")
    lines.append(f"- 生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 耗时: {elapsed:.1f}s")
    lines.append("")
    lines.append("## 统计")
    lines.append("")
    lines.append(f"- 总文件数: {stats.total}")
    lines.append(f"- 成功: {stats.ok}")
    lines.append(f"- 失败: {stats.failed}")
    lines.append(f"- 跳过: {stats.skipped}")
    lines.append(f"- 扫描版 PDF: {len(stats.scanned_pdfs)}")
    lines.append("")
    lines.append(f"- 计数自洽: {('是' if stats.total == stats.ok + stats.failed + stats.skipped else '否(请检查!)')}")
    lines.append("")

    lines.append("## 成功文件")
    lines.append("")
    if stats.targets:
        for out, rel in stats.targets:
            lines.append(f"- `{rel}` -> `{out}`")
    else:
        lines.append("(无)")

    lines.append("")
    lines.append("## 失败文件 + 原因")
    lines.append("")
    if stats.failures:
        for rel, reason in stats.failures:
            lines.append(f"- `{rel}`: {reason}")
    else:
        lines.append(_total_failures_message(stats))

    lines.append("")
    lines.append("## 扫描版 PDF 清单")
    lines.append("")
    if stats.scanned_pdfs:
        for rel in stats.scanned_pdfs:
            lines.append(f"- `{rel}`")
    else:
        lines.append("(无)")
    lines.append("")
    return "\n".join(lines)


def write_report(dest: Path, stats: ConversionStats) -> Path:
    path = dest / "conversion_report.md"
    path.write_text(build_report(stats), encoding="utf-8")
    return path