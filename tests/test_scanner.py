# -*- coding: utf-8 -*-
"""Unit tests for tomd.scanner — discovery, mirroring, modes and skip logic."""

import tempfile
import unittest
from pathlib import Path

from tomd.config import OUT_MODE_FLAT, OUT_MODE_MIRROR, OUT_MODE_SRC, Options
from tomd.models import FileRecord, SourceKind
from tomd.scanner import already_processed, discover, md_name, output_target


def _make_tree(root: Path) -> None:
    (root / "a" / "sub").mkdir(parents=True, exist_ok=True)
    (root / "a" / "x.pdf").write_bytes(b"pdf")
    (root / "a" / "sub" / "y.docx").write_bytes(b"docx")
    (root / "a" / "notes.txt").write_bytes(b"txt")  # unsupported
    (root / "a" / "z.PDF").write_bytes(b"pdf")        # case-insensitive


def _record(rel: str, kind: SourceKind, source_abs: Path) -> FileRecord:
    return FileRecord(source_path=str(source_abs), relative_path=rel, kind=kind)


class DiscoverTest(unittest.TestCase):
    def test_finds_only_supported_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tree = Path(td) / "src"
            tree.mkdir()
            _make_tree(tree)
            files = discover(tree)
            rels = sorted(r.relative_path for r in files)
            self.assertEqual(rels, ["a/sub/y.docx", "a/x.pdf", "a/z.PDF"])
            kinds = {r.kind for r in files}
            self.assertEqual(kinds, {SourceKind.PDF, SourceKind.DOCX})

    def test_missing_source_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            discover(Path("/no/such/dir"))


class MdNameTest(unittest.TestCase):
    def test_naming_scheme(self) -> None:
        self.assertEqual(md_name("a/paper.pdf", SourceKind.PDF), "tomd_paper_pdf.md")
        self.assertEqual(md_name("paper.docx", SourceKind.DOCX), "tomd_paper_docx.md")


class OutputTargetTest(unittest.TestCase):
    def _opts(self, mode: int, dest: str, source: str = "src") -> Options:
        return Options(source=source, dest=dest, out_mode=mode)

    def test_mode_src_alongside(self) -> None:
        rec = _record("a/paper.pdf", SourceKind.PDF, Path("srcdir/a/paper.pdf"))
        target = output_target(self._opts(OUT_MODE_SRC, ""), rec)
        self.assertEqual(target, Path("srcdir/a/tomd_paper_pdf.md"))

    def test_mode_flat(self) -> None:
        rec = _record("a/sub/paper.pdf", SourceKind.PDF, Path("srcdir/a/sub/paper.pdf"))
        target = output_target(self._opts(OUT_MODE_FLAT, "dest"), rec)
        self.assertEqual(target, Path("dest/tomd_paper_pdf.md").resolve())

    def test_mode_mirror_nested(self) -> None:
        rec = _record("a/sub/paper.docx", SourceKind.DOCX, Path("srcdir/a/sub/paper.docx"))
        target = output_target(self._opts(OUT_MODE_MIRROR, "dest"), rec)
        self.assertEqual(target, Path("dest/a/sub/tomd_paper_docx.md").resolve())

    def test_mode_mirror_root(self) -> None:
        rec = _record("paper.pdf", SourceKind.PDF, Path("srcdir/paper.pdf"))
        target = output_target(self._opts(OUT_MODE_MIRROR, "dest"), rec)
        self.assertEqual(target, Path("dest/tomd_paper_pdf.md").resolve())


class AlreadyProcessedTest(unittest.TestCase):
    def test_skip_when_exists_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "p.md"
            f.write_text("x")
            self.assertTrue(already_processed(f, overwrite=False))

    def test_no_skip_with_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "p.md"
            f.write_text("x")
            self.assertFalse(already_processed(f, overwrite=True))

    def test_not_skipped_when_absent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(already_processed(Path(td) / "p.md", overwrite=False))


if __name__ == "__main__":
    unittest.main()