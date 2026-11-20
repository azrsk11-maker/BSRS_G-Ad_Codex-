"""Synthetic-only private Search terms intake tests; no account/query fixtures."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import search_terms_intake as st

PRIVATE_METRIC = "TEST_ONLY_FINANCIAL_CELL_DO_NOT_PROJECT"


def row(term="Synthetic property enquiry", campaign="TEST_ONLY_campaign", ad_group="TEST_ONLY_group"):
    values = [PRIVATE_METRIC] * len(st.COLUMNS)
    values[:5] = [term, "TEST_ONLY_match", "TEST_ONLY_status", campaign, ad_group]
    values[11] = "TEST_ONLY_campaign_type"
    return values


def footer(label):
    values = [PRIVATE_METRIC] * len(st.COLUMNS)
    values[:5] = [label, "--", "", "--", ""]
    values[11] = "TEST_ONLY_optional_type"
    return values


def fixture(rows=None, title=st.TITLE, date=st.DATE_HEADER, columns=st.COLUMNS, bom=False):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow([title]); writer.writerow([date]); writer.writerow(columns)
    writer.writerows([row()] if rows is None else rows)
    return stream.getvalue().encode("utf-8-sig" if bom else "utf-8")


class SearchTermsIntakeTests(unittest.TestCase):
    def parse(self, raw):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "TEST_ONLY_search_terms.csv"
            path.write_bytes(raw)
            result = st.parse_search_terms(path)
            self.assertEqual(path.read_bytes(), raw)
            self.assertNotIn(str(path), json.dumps(result))
            return result

    def reject(self, raw):
        with self.assertRaises(ValueError) as caught:
            self.parse(raw)
        self.assertNotIn(PRIVATE_METRIC, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_exact_provenance_whitelist_and_zero_authority(self):
        raw = fixture()
        result = self.parse(raw)
        self.assertEqual(result["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["source_bytes"], len(raw))
        self.assertEqual(result["records"][0]["source_line"], 4)
        self.assertEqual(result["records"][0]["search_term"], "Synthetic property enquiry")
        self.assertEqual(set(result["records"][0]["placement"]), set(st.PLACEMENT_COLUMNS))
        self.assertNotIn(PRIVATE_METRIC, json.dumps(result))
        for forbidden in ("Cost", "Clicks", "Conversions", "Avg. CPC", "Currency code"):
            self.assertNotIn(forbidden, json.dumps(result))
        for record in result["records"]:
            self.assertTrue(record["manual_disclosure_review_required"])
            self.assertTrue(all(record[key] is False for key in st.AUTHORITIES))
        self.assertTrue(all(result["controls"][key] is False for key in st.AUTHORITIES))
        self.assertEqual(self.parse(fixture(bom=True))["records"], result["records"])

    def test_multiline_raw_forms_normalization_and_repeated_placements(self):
        rows = [row("  ＳＹＮＴＨＥＴＩＣ\nquery  "), row("synthetic query"),
                row("synthetic query"), row("synthetic query", "TEST_ONLY_second", "")]
        result = self.parse(fixture(rows))
        self.assertEqual([r["source_line"] for r in result["records"]], [4, 6, 7, 8])
        self.assertEqual([r["search_term"] for r in result["records"]], [r[0] for r in rows])
        count = result["summary"]
        self.assertEqual(count["distinct_raw_search_terms"], 2)
        self.assertEqual(count["distinct_normalized_search_terms"], 1)
        self.assertEqual(count["repeated_raw_query_occurrences"], 2)
        self.assertEqual(count["repeated_normalized_query_occurrences"], 3)
        self.assertEqual(count["duplicate_query_placement_rows"], 1)
        self.assertEqual(count["distinct_campaign_labels"], 2)
        self.assertEqual(count["distinct_nonblank_campaign_ad_group_label_pairs"], 1)
        self.assertEqual(count["distinct_campaign_ad_group_label_pairs_including_blank"], 2)
        self.assertEqual(count["distinct_nonblank_ad_group_labels"], 1)
        self.assertEqual(count["blank_ad_group_rows"], 1)
        self.assertIn("control_character_candidate", result["records"][0]["privacy_flags"])

    def test_context_repeats_distinguish_match_types_and_literal_blank_labels(self):
        first = row("Synthetic repeated query")
        second = row("Synthetic repeated query"); second[1] = "TEST_ONLY_other_match"
        rows = [first, second, row("Synthetic repeated query", ad_group=""),
                row("Synthetic repeated query", ad_group="--")]
        count = self.parse(fixture(rows))["summary"]
        self.assertEqual(count["repeated_query_campaign_ad_group_context_rows"], 1)
        self.assertEqual(count["duplicate_query_placement_rows"], 0)
        self.assertEqual(count["distinct_campaign_labels"], 1)
        self.assertEqual(count["distinct_nonblank_campaign_ad_group_label_pairs"], 1)
        self.assertEqual(count["distinct_campaign_ad_group_label_pairs_including_blank"], 3)
        self.assertEqual(count["distinct_nonblank_ad_group_labels"], 1)
        self.assertEqual(count["blank_ad_group_rows"], 2)

    def test_footer_counts_and_real_query_label_collision(self):
        rows = [row(st.FOOTERS[0])] + [footer(label) for label in st.FOOTERS]
        result = self.parse(fixture(rows))
        self.assertEqual(result["summary"]["query_placement_rows"], 1)
        self.assertEqual(result["records"][0]["search_term"], st.FOOTERS[0])
        self.assertEqual(result["summary"]["footer_rows"], 5)
        self.assertTrue(all(n == 1 for n in result["summary"]["footer_counts"].values()))
        self.reject(fixture([footer("Total: TEST_ONLY_unknown")]))
        self.reject(fixture([footer(st.FOOTERS[0]), footer(st.FOOTERS[0])]))
        malformed = footer(st.FOOTERS[0]); malformed[1] = "TEST_ONLY_nonempty"
        self.reject(fixture([malformed]))
        self.reject(fixture([footer(" total : Search terms")]))

    def test_date_title_columns_width_encoding_and_bounds_fail_closed(self):
        for date in ("", "September 1, 2026 - September 30, 2026",
                     "October 2, 2026 - October 31, 2026"):
            self.reject(fixture(date=date))
        self.reject(fixture(title="TEST_ONLY_unknown"))
        self.reject(fixture(columns=st.COLUMNS[:-1]))
        self.reject(fixture(columns=(*st.COLUMNS[:-1], "TEST_ONLY_unknown")))
        self.reject(fixture(columns=(*st.COLUMNS[:-1], st.COLUMNS[0])))
        self.reject(fixture(columns=tuple(reversed(st.COLUMNS))))
        for values in (row()[:-1], row() + [PRIVATE_METRIC], []):
            self.reject(fixture([values]))
        self.reject(b"\xff\xfe" + fixture().decode().encode("utf-16-le"))
        self.reject(fixture() + b"\xff")
        self.reject(b"")
        self.reject(fixture() + b'"unterminated')
        with patch.object(st, "MAX_BYTES", len(fixture())):
            self.parse(fixture())
            self.reject(fixture() + b" ")
        with patch.object(st, "MAX_ROWS", 1):
            self.parse(fixture())
            self.reject(fixture([row(), row()]))

    def test_privacy_candidates_and_unflagged_are_always_manual_review(self):
        candidates = {"Synthetic person test@example.invalid": "email_candidate",
            "Synthetic contact +999 123 456 789": "phone_candidate",
            "Synthetic https://example.invalid/a": "url_candidate",
            "Synthetic token=TEST_ONLY_abcdef": "token_candidate",
            "Synthetic\x00query": "control_character_candidate",
            "  =TEST_ONLY_FORMULA()": "spreadsheet_formula_candidate"}
        result = self.parse(fixture([row(value) for value in candidates] + [row("Synthetic ordinary query")]))
        for record, expected in zip(result["records"], candidates.values()):
            self.assertIn(expected, record["privacy_flags"])
        # Heuristics miss identifiers: an empty flag list never confers safety.
        ordinary = result["records"][-1]
        self.assertEqual(ordinary["privacy_flags"], [])
        self.assertTrue(ordinary["manual_disclosure_review_required"])
        self.assertFalse(ordinary["public_disclosure_authorized"])
        self.assertTrue(result["controls"]["unflagged_records_are_not_verified_safe"])
        self.assertEqual(result["summary"]["manual_disclosure_review_required_records"], len(result["records"]))
        placement = row(); placement[3] = "test@example.invalid"
        self.assertIn("email_candidate", self.parse(fixture([placement]))["records"][0]["privacy_flags"])

    def test_empty_query_or_missing_placement_and_path_errors_are_generic(self):
        for values in (row(""), row("  "), row("[]"), row(campaign="--")):
            self.reject(fixture([values]))
        for column in (1, 2, 11):
            values = row(); values[column] = ""
            self.reject(fixture([values]))
        with self.assertRaisesRegex(ValueError, "^SEARCH_TERMS_SOURCE_UNREADABLE$"):
            st.parse_search_terms(Path(tempfile.gettempdir()) / PRIVATE_METRIC / "missing.csv")
        empty = self.parse(fixture([]))
        self.assertEqual(empty["summary"]["query_placement_rows"], 0)
        self.assertFalse(empty["controls"]["public_disclosure_authorized"])


if __name__ == "__main__":
    unittest.main()
