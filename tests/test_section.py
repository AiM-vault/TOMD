# -*- coding: utf-8 -*-
"""Unit tests for tomd.section — section detection and reference stripping."""

import unittest

from tomd.section import (detect_sections, find_references_boundary,
                          mark_sections, strip_references)


class DetectSectionsTest(unittest.TestCase):
    def test_abstract_and_introduction(self) -> None:
        body = "This is preamble.\nABSTRACT\nWe study X.\n1. Introduction\nWe motivate."
        names = [s.name for s in detect_sections(body)]
        self.assertIn("Abstract", names)
        self.assertIn("Introduction", names)

    def test_numbered_and_no_number(self) -> None:
        body = "3 Methodology\nWe model.\nDiscussion\nThe findings suggest."
        names = [s.name for s in detect_sections(body)]
        self.assertIn("Methodology", names)
        self.assertIn("Discussion", names)

    def test_mid_sentence_keyword_not_matched(self) -> None:
        # 'results' appears mid-line -> must not be flagged
        body = "We find that the results are mixed. discussion here is omitted."
        self.assertEqual(detect_sections(body), [])


class MarkSectionsTest(unittest.TestCase):
    def test_inserts_markers(self) -> None:
        body = "ABSTRACT\nWe study."
        out = mark_sections(body)
        self.assertIn("<!-- SECTION: Abstract -->", out)
        self.assertIn("<!-- SECTION: Abstract -->\nABSTRACT", out)


class StripReferencesTest(unittest.TestCase):
    def _ref_body(self) -> str:
        return (
            "We conclude.\n\n"
            "References\n"
            "[1] Boland, M. (2021). Bureaucratic discretion.\n"
            "[2] Godsell, D. (2021). Contracting outcomes.\n"
        )

    def test_strips_when_reference_shaped(self) -> None:
        out, was = strip_references(self._ref_body())
        self.assertTrue(was)
        self.assertNotIn("Boland", out)
        self.assertIn("We conclude", out)

    def test_does_not_strip_without_reference_pattern(self) -> None:
        # 'References' heading but body text below is not reference-shaped
        body = "Body\nReferences\nThe exact results are discussed in depth here.\n"
        out, was = strip_references(body)
        self.assertFalse(was)
        self.assertEqual(out, body)

    def test_find_boundary_returns_offset(self) -> None:
        i = find_references_boundary(self._ref_body())
        self.assertIsInstance(i, int)
        self.assertEqual(self._ref_body()[i:].splitlines()[0], "References")


if __name__ == "__main__":
    unittest.main()