"""Focused boundaries for the additive, read-only keyword text diagnostic."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import keyword_text_compatibility as compatibility


class KeywordTextCompatibilityTests(unittest.TestCase):
    def test_character_boundary(self):
        self.assertEqual(compatibility.profile_text("a" * 80)["original"]["reason_codes"], [])
        self.assertIn("DOCUMENTED_CHARACTER_LIMIT_EXCEEDED",
                      compatibility.profile_text("a" * 81)["original"]["reason_codes"])

    def test_word_boundary_is_review(self):
        for count in (10, 11):
            value = compatibility.profile_text(" ".join(["x"] * count))["original"]
            self.assertEqual(value["whitespace_word_count"], count)
            self.assertEqual(value["classification"], "REQUIRES_REVIEW" if count == 11
                             else "NO_KNOWN_INCOMPATIBILITY_DETECTED")

    def test_documented_symbols(self):
        for symbol in compatibility.INVALID_SYMBOLS:
            value = compatibility.profile_text("course" + symbol)["original"]
            self.assertEqual(value["invalid_symbols"], [symbol])
            self.assertIn("DOCUMENTED_INVALID_SYMBOLS", value["reason_codes"])

    def test_allowed_symbols_and_unicode(self):
        value = compatibility.profile_text("café & housing *")["original"]
        self.assertEqual(value["classification"], "NO_KNOWN_INCOMPATIBILITY_DETECTED")
        self.assertEqual(value["character_count"], 16)

    def test_match_syntax_remains_reviewed_and_preserved(self):
        for text in ('course [level]', '[course]', '"course"'):
            value = compatibility.profile_text(text)["original"]
            self.assertEqual(value["text"], text)
            self.assertIn("MATCH_SYNTAX_REQUIRES_REVIEW", value["reason_codes"])

    def test_operator_observations(self):
        value = compatibility.profile_text("-course +study site:example.org OR diploma")["original"]
        self.assertEqual(len(value["observations"]), 5)
        self.assertEqual(value["reason_codes"], [])

    def test_unicode_whitespace_and_no_normalization(self):
        text = " A\tB\nC\u00a0D\u2003E  "
        value = compatibility.profile_text(text)["original"]
        self.assertEqual(value["text"], text)
        self.assertEqual(value["whitespace_word_count"], 5)
        self.assertEqual(compatibility.profile_text("Ａ")["original"]["text"], "Ａ")

    def test_canonical_is_supplied_separately(self):
        value = compatibility.profile_text("[Course]", canonical_text="course")
        self.assertEqual(value["original"]["text"], "[Course]")
        self.assertEqual(value["provided_canonical"]["text"], "course")
        self.assertNotEqual(value["original"]["classification"],
                            value["provided_canonical"]["classification"])

    def test_summary_nonmutation_and_overlapping_counts(self):
        rows = [{"title": "(" + "long " * 20, "canonical": "course", "private": "unused"}]
        before = deepcopy(rows)
        result = compatibility.summarize(rows, text_field="title", canonical_field="canonical",
                                         context_purpose="ARCHIVED_ORIGINALS")
        self.assertEqual(rows, before)
        self.assertEqual(result["context_purpose"], "ARCHIVED_ORIGINALS")
        self.assertEqual(len(result["totals"]["original"]["reason_counts"]), 3)
        self.assertNotIn("private", result["rows"][0])
        for key in ("admission_performed", "deployment_export_allowed", "platform_validation_performed"):
            self.assertIs(result[key], False)

    def test_malformed_inputs(self):
        for text in (None, 1, [], "\ud800"):
            with self.assertRaises(ValueError):
                compatibility.profile_text(text)
        for rows in (None, {}, [None], [{}], [{"original_text": 1}]):
            with self.assertRaises(ValueError):
                compatibility.summarize(rows)
        with self.assertRaises(ValueError):
            compatibility.summarize([{"original_text": "course"}], canonical_field="absent")

    def test_bounds(self):
        with self.assertRaises(ValueError):
            compatibility.profile_text("x" * (compatibility.MAX_TEXT_CHARACTERS + 1))
        with patch.object(compatibility, "MAX_ROWS", 1):
            with self.assertRaises(ValueError):
                compatibility.summarize([{"original_text": "a"}] * 2)
        with patch.object(compatibility, "MAX_COLLECTION_CHARACTERS", 2):
            with self.assertRaises(ValueError):
                compatibility.summarize([{"original_text": "abc"}])

    def test_blank_and_empty_collection(self):
        self.assertIn("BLANK_TEXT_REQUIRES_REVIEW",
                      compatibility.profile_text(" \t")["original"]["reason_codes"])
        result = compatibility.summarize([])
        self.assertEqual(result["totals"]["original"]["rows"], 0)
        self.assertEqual(result["rows"], [])


if __name__ == "__main__":
    unittest.main()
