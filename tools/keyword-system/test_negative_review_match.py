"""Synthetic controls for the opt-in negative keyword review API."""

from contextlib import redirect_stdout
from io import BytesIO, StringIO
import json
import unittest

from keyword_audit import negative_matches
from negative_review_match import ReviewResult, main, review_negative_match


class NegativeReviewMatchTests(unittest.TestCase):
    def test_cli_reports_hold_without_echoing_the_input(self):
        output = StringIO()
        with redirect_stdout(output):
            main(["PHRASE"], BytesIO("投資\n杜拜投資查詢\n".encode("utf-8")))
        self.assertEqual(json.loads(output.getvalue()), {"review": "HOLD_UNSEGMENTED_HAN",
                                                        "provider_verified": False, "deployment_authorized": False})

    def test_legacy_english_normalization_and_match_modes(self):
        cases = (
            ("[OFFICE RENT]", "EXACT", "office-rent"),
            ('"villa pool"', "PHRASE", "large villa, pool and garden"),
            ("rent office", "PHRASE", "office for rent"),
            ("office rent", "BROAD", "rent an office"),
            ("office", "EXACT", "offices"),
            ("office rent", "EXACT", "office rent dubai"),
            ("villa villa", "BROAD", "villa"),
            ("villa villa", "PHRASE", "large villa"),
            ("villa_1", "EXACT", "villa 1"),
            ("ｖｉｌｌａ", "EXACT", "villa"),
        )
        for text, match, query in cases:
            with self.subTest(text=text, match=match, query=query):
                expected = ReviewResult.LEXICAL_MATCH if negative_matches(text, match, query) else ReviewResult.NO_LEXICAL_MATCH
                self.assertIs(review_negative_match(text, match, query), expected)

    def test_hindi_vowel_signs_across_match_modes(self):
        for mode, query in (("EXACT", "की"), ("PHRASE", "घर की"), ("BROAD", "की घर")):
            with self.subTest(mode=mode):
                self.assertTrue(negative_matches("कि", mode, query))
                self.assertIs(review_negative_match("कि", mode, query), ReviewResult.NO_LEXICAL_MATCH)
                distinct_query = query.replace("की", "कि")
                self.assertIs(review_negative_match("कि", mode, distinct_query), ReviewResult.LEXICAL_MATCH)

    def test_same_accent_canonical_equivalence_and_distinct_accents(self):
        self.assertIs(review_negative_match("café", "EXACT", "cafe\u0301"), ReviewResult.LEXICAL_MATCH)
        self.assertIs(review_negative_match("café", "EXACT", "cafe"), ReviewResult.NO_LEXICAL_MATCH)
        self.assertIs(review_negative_match("بَيت", "PHRASE", "مدينة بَيت"), ReviewResult.LEXICAL_MATCH)
        self.assertIs(review_negative_match("بَيت", "PHRASE", "مدينة بِيت"), ReviewResult.NO_LEXICAL_MATCH)

    def test_han_word_boundary_ambiguity_is_a_hold(self):
        cases = (("海外 不動產", "EXACT", "海外不動產"),
                 ("投資", "PHRASE", "杜拜投資查詢"),
                 ("投資 杜拜", "BROAD", "杜拜房產投資"),
                 ("𠮷野", "PHRASE", "找𠮷野房產"),
                 ("〇號", "PHRASE", "查閱〇號資料"))
        for text, mode, query in cases:
            with self.subTest(mode=mode, query=query):
                self.assertFalse(negative_matches(text, mode, query))
                self.assertIs(review_negative_match(text, mode, query), ReviewResult.HOLD_UNSEGMENTED_HAN)

    def test_han_respects_whole_query_phrase_order_and_broad_terms(self):
        cases = (("投資", "EXACT", "杜拜投資"),
                 ("投資 杜拜", "PHRASE", "杜拜投資"),
                 ("投資", "BROAD", "投房資"),
                 ("投資 business", "BROAD", "杜拜投資 enquiry"),
                 ("投\ufe00資", "PHRASE", "杜拜投資查詢"),
                 ("房產", "PHRASE", "杜拜投資"))
        for text, mode, query in cases:
            with self.subTest(mode=mode, query=query):
                self.assertIs(review_negative_match(text, mode, query), ReviewResult.NO_LEXICAL_MATCH)
        self.assertIs(review_negative_match("投資", "EXACT", "投資"), ReviewResult.LEXICAL_MATCH)
        self.assertIs(review_negative_match("投資", "PHRASE", "杜拜 投資 房產"), ReviewResult.LEXICAL_MATCH)

    def test_validation_and_explicit_review_comparison(self):
        with self.assertRaisesRegex(ValueError, "Unsupported negative match type"):
            review_negative_match("villa", "UNKNOWN", "villa")
        with self.assertRaisesRegex(ValueError, "Keyword text must be a string"):
            review_negative_match(None, "EXACT", "villa")
        self.assertIs(review_negative_match("!!!", "EXACT", "villa"), ReviewResult.NO_LEXICAL_MATCH)
        with self.assertRaisesRegex(TypeError, "Compare review results explicitly"):
            bool(review_negative_match("投資", "PHRASE", "杜拜投資"))


if __name__ == "__main__":
    unittest.main()
