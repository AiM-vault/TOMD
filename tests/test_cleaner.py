# -*- coding: utf-8 -*-
"""Unit tests for tomd.cleaner — whitespace & line-break dehyphenation."""

import unittest

from tomd.cleaner import clean_text, collapse_whitespace, dehyphenate, is_junk_line


class DehyphenateTest(unittest.TestCase):
    def test_merges_line_break_hyphen(self) -> None:
        self.assertEqual(dehyphenate("meth-\nod"), "method")

    def test_genuine_compound_split_at_break_normalised(self) -> None:
        # A compound that happens to break exactly at its hyphen is merged too.
        # This is the documented limitation of a dictionary-free rejoin (D6);
        # soft line-breaks (the common case) are treated identically.
        self.assertEqual(dehyphenate("self-\nreferential"), "selfreferential")

    def test_uppercase_continuation_not_merged(self) -> None:
        # Uppercase continuation => starts a new sentence, not a continued word
        self.assertEqual(dehyphenate("The-\nEnd"), "The-\nEnd")


class WhitespaceTest(unittest.TestCase):
    def test_crlf_normalised(self) -> None:
        self.assertEqual(collapse_whitespace("a\r\nb\r\n\r\nc"), "a\nb\n\nc")

    def test_excess_spaces_collapsed(self) -> None:
        self.assertEqual(collapse_whitespace("a    b   c"), "a b c")

    def test_excess_blank_lines_collapsed(self) -> None:
        self.assertEqual(collapse_whitespace("a\n\n\n\n\nb"), "a\n\nb")


class JunkLineTest(unittest.TestCase):
    def test_page_number_is_junk(self) -> None:
        self.assertTrue(is_junk_line("12"))

    def test_ornament_is_junk(self) -> None:
        self.assertTrue(is_junk_line("• • •   "))

    def test_real_text_not_junk(self) -> None:
        self.assertFalse(is_junk_line("Introduction to results"))


class CleanTextPipelineTest(unittest.TestCase):
    def test_removes_page_number_lines(self) -> None:
        body = "Hello world\n14\n\nNext paragraph"
        doc = clean_text(body)
        self.assertNotIn("14", doc.body)
        self.assertEqual(doc.stats.page_number_lines, 1)

    def test_tracks_over_glued_lines(self) -> None:
        long_line = "x" * 1000
        doc = clean_text(long_line)
        self.assertEqual(doc.stats.over_glued_lines, 1)


if __name__ == "__main__":
    unittest.main()