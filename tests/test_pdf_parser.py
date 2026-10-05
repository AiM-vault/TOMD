# -*- coding: utf-8 -*-
"""Unit tests for tomd.parsers.pdf_parser using synthetic pdfplumber-style
word dicts (no real PDF/files needed for the pure layout logic)."""

import unittest

from tomd.parsers.pdf_parser import PdfParser, _HEADINGISH


def word(text: str, x0: float, top: float, size: float = 10.0) -> dict:
    return {"text": text, "x0": x0, "x1": x0 + size * len(text) * 0.5,
            "top": top, "bottom": top + size}


def two_column_page() -> list[dict]:
    """Build a fake 595pt-wide 2-column page of words.

    Left column x0 ~ 60..260, right column x0 ~ 340..535.  Rows share baselines
    deliberately so we can prove word-level splitting prevents column fusion.
    """
    words: list[dict] = []
    for row in range(20):
        top = 50 + row * 14
        words += [word(f"L{row}", 60, top), word("text", 90, top), word("end", 160, top)]
        words += [word(f"R{row}", 340, top), word("text", 370, top), word("end", 460, top)]
    return words


class HeadingTest(unittest.TestCase):
    def test_matches_numbered_heading(self) -> None:
        self.assertTrue(_HEADINGISH.match("3. Methodology"))

    def test_does_not_match_long_prose(self) -> None:
        self.assertFalse(_HEADINGISH.match(
            "The prior literature suggests that politicians award more and larger "
            "contracts to politically connected firms when they have discretion."))


class MergeTest(unittest.TestCase):
    def test_hyphen_join(self) -> None:
        got = PdfParser._merge(["meth-"], "od")
        self.assertEqual(got, ["method"])

    def test_space_join(self) -> None:
        got = PdfParser._merge(["alpha"], "beta")
        self.assertEqual(got, ["alpha beta"])


class PartitionsTest(unittest.TestCase):
    def test_two_column_detected(self) -> None:
        parser = PdfParser()
        cols = parser._partition_words(two_column_page(), page_width=595.0)
        self.assertEqual(len(cols), 2)

    def test_single_wide_column_undivided(self) -> None:
        words = []
        for row in range(20):
            top = 50 + row * 14
            # continuous text across the whole width -> no gutter
            words += [word("a", 40 + (row % 3) * 20, top) for _ in range(40)]
        cols = PdfParser()._partition_words(words, page_width=612.0)
        self.assertEqual(len(cols), 1)


class ReflowIntegrationTest(unittest.TestCase):
    def test_no_column_interleaving_after_reflow(self) -> None:
        parser = PdfParser()
        words = two_column_page()
        collections = parser._partition_words(words, 595.0)
        lines_by_col = [PdfParser._words_to_lines(c) for c in collections]
        # each column should only reference its own words
        left_text = " ".join(l.text for c in lines_by_col[:1] for l in c)
        right_text = " ".join(l.text for c in lines_by_col[1:] for l in c)
        self.assertIn("L0", left_text)
        self.assertNotIn("R0", left_text)
        self.assertIn("R0", right_text)


if __name__ == "__main__":
    unittest.main()