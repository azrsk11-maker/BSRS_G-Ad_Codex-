"""Synthetic-only Discovery parsing, bounds and privacy regression checks."""
from contextlib import redirect_stdout
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import planner_discovery as pd

DATE = "October 1, 2025 - September 30, 2026"
LABELS = list(pd.BASE_COLUMNS) + pd._monthly_columns(DATE)
PRIVATE_SENTINEL = "SYNTHETIC_PRIVATE_ACCOUNT_CELL_DO_NOT_PUBLISH"


def fixture_row(keyword="Synthetic property enquiry"):
    values = {label: "" for label in LABELS}
    values.update({"Keyword": keyword, "Currency": "AED", "Avg. monthly searches": "1,000",
                   "Three month change": "-100%", "YoY change": "∞", "Competition": "High",
                   "Competition (indexed value)": "89", "Top of page bid (low range)": "1.20",
                   "Top of page bid (high range)": "9.00", "Searches: Oct 2025": "0"})
    values.update({label: PRIVATE_SENTINEL for label in pd.EXCLUDED_COLUMNS})
    return [values[label] for label in LABELS]


def fixture(rows=None, labels=None, date=DATE):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter="\t", lineterminator="\r\n")
    writer.writerow(["Keyword Stats 2026-11-08 at 12_00_00"])
    writer.writerow([date])
    writer.writerow(LABELS if labels is None else labels)
    writer.writerows([fixture_row()] if rows is None else rows)
    return stream.getvalue().encode("utf-16")


class PlannerDiscoveryTests(unittest.TestCase):
    def test_count_only_cli_does_not_print_paths_or_source_cells(self):
        with tempfile.TemporaryDirectory() as folder:
            good = Path(folder) / "private-path-marker.csv"
            bad = Path(folder) / "another-private-marker.csv"
            good.write_bytes(fixture())
            bad.write_bytes(b"bad encoding")
            stdout = io.StringIO()
            with patch("sys.argv", ["planner_discovery.py", str(good), str(bad)]), redirect_stdout(stdout):
                self.assertEqual(pd.main(), 2)
            output = stdout.getvalue()
            result = json.loads(output)
            self.assertFalse(result["passed"])
            self.assertIsNone(result["combined"])
            self.assertFalse(result["account_context_verified"])
            self.assertEqual(result["inputs"][0]["rows"], 1)
            self.assertEqual(result["inputs"][1]["error"], "INVALID_DISCOVERY_EXPORT")
            for value in ("private-path-marker", "another-private-marker", PRIVATE_SENTINEL, "Synthetic property enquiry"):
                self.assertNotIn(value, output)

    def test_count_only_cli_combines_normalized_identities_across_exports(self):
        with tempfile.TemporaryDirectory() as folder:
            first = Path(folder) / "first.csv"
            second = Path(folder) / "second.csv"
            first.write_bytes(fixture([fixture_row("One phrase"), fixture_row("ONE PHRASE")]))
            second.write_bytes(fixture([fixture_row("[one phrase]"), fixture_row("Another phrase")]))
            stdout = io.StringIO()
            with patch("sys.argv", ["planner_discovery.py", str(first), str(second)]), redirect_stdout(stdout):
                self.assertEqual(pd.main(), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["combined"], {"distinct": 2, "present_in_multiple_inputs": 1})
            self.assertNotIn("one phrase", stdout.getvalue().lower())

    def parse(self, raw):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic-discovery.csv"
            path.write_bytes(raw)
            result = pd.parse_discovery(path)
            self.assertEqual(path.read_bytes(), raw)
            return result

    def reject(self, raw):
        with self.assertRaises(ValueError) as caught:
            self.parse(raw)
        self.assertNotIn(PRIVATE_SENTINEL, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_exact_projection_and_same_bytes_provenance(self):
        raw = fixture()
        result = self.parse(raw)
        self.assertEqual(result["source_basename"], "synthetic-discovery.csv")
        self.assertEqual(result["source_bytes"], len(raw))
        self.assertEqual(result["source_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["date_header"], DATE)
        self.assertEqual(result["column_labels"], LABELS)
        self.assertEqual(len(result["public_columns"]), 21)
        self.assertEqual(set(result["excluded_columns"]), pd.EXCLUDED_COLUMNS)
        self.assertEqual(result["records"][0]["source_line"], 4)
        expected = {label: (value or None) for label, value in zip(LABELS, fixture_row())
                    if label not in pd.EXCLUDED_COLUMNS}
        self.assertEqual(result["records"][0]["values"], expected)
        self.assertNotIn(PRIVATE_SENTINEL, json.dumps(result))
        for excluded in pd.EXCLUDED_COLUMNS:
            self.assertNotIn(excluded, result["records"][0]["values"])
        self.assertFalse({"approved", "reviewed", "campaign", "cpc", "total_searches"} & result.keys())

    def test_nfkc_casefold_whitespace_duplicates_are_retained(self):
        rows = [fixture_row(text) for text in (
            "  ＳＹＮＴＨＥＴＩＣ   Property ENQUIRY  ", "synthetic property enquiry",
            "Synthetic\u00a0property enquiry", "different synthetic keyword",
            "[synthetic property enquiry]", '"synthetic property enquiry"')]
        result = self.parse(fixture(rows))
        self.assertEqual(result["record_count"], 6)
        self.assertEqual(result["distinct_normalized_count"], 2)
        self.assertEqual(result["duplicate_groups"], [{"normalized_keyword": "synthetic property enquiry",
                                                        "source_lines": [4, 5, 6, 8, 9]}])
        self.assertEqual([r["values"]["Keyword"] for r in result["records"]], [r[0] for r in rows])

    def test_nonempty_metric_whitespace_is_not_coerced(self):
        row = fixture_row()
        row[2] = "  "
        self.assertEqual(self.parse(fixture([row]))["records"][0]["values"][LABELS[2]], "  ")

    def test_physical_start_lines_across_quoted_metric_newlines(self):
        row = fixture_row()
        row[2] = "synthetic\nmetric"
        result = self.parse(fixture([row, fixture_row("different synthetic")]))
        self.assertEqual([r["source_line"] for r in result["records"]], [4, 6])
        self.assertEqual(result["records"][0]["values"][LABELS[2]], "synthetic\nmetric")

    def test_missing_duplicate_unknown_and_wrong_month_headers_rejected(self):
        for labels in (LABELS[:-1], LABELS + ["unknown"], LABELS[:-1] + [LABELS[0]],
                       LABELS[:-1] + ["Searches: Sep 2027"]):
            with self.subTest(labels=len(labels)):
                self.reject(fixture(labels=labels))

    def test_reordered_known_columns_preserve_source_order(self):
        labels = list(reversed(LABELS))
        result = self.parse(fixture([list(reversed(fixture_row()))], labels=labels))
        self.assertEqual(result["column_labels"], labels)
        self.assertEqual(list(result["records"][0]["values"]), result["public_columns"])
        self.assertEqual(result["records"][0]["values"]["Keyword"], fixture_row()[0])

    def test_invalid_keyword_blanks_and_controls_fail_closed(self):
        for keyword in ("", "  ", "[]", '""', "\u00a0", "a\tb", "a\nb", "a\x00b", "a\u200bb", "a\ufeffb"):
            with self.subTest(keyword=repr(keyword)):
                self.reject(fixture([fixture_row(keyword)]))

    def test_bad_dates_fail_closed(self):
        for header in ("", PRIVATE_SENTINEL, "Oct 1, 2025 - Sep 30, 2026",
                       "October 2, 2025 - September 30, 2026",
                       "October 1, 2025 - September 31, 2026",
                       "October 1, 2025 - August 31, 2026",
                       "October 1, 2026 - September 30, 2025"):
            with self.subTest(header=header):
                self.reject(fixture(date=header))

    def test_missing_preamble_invalid_title_and_width_fail_closed(self):
        self.reject("".encode("utf-16"))
        self.reject(fixture().decode("utf-16").splitlines()[0].encode("utf-16"))
        self.reject(fixture().decode("utf-16").replace("Keyword Stats", PRIVATE_SENTINEL).encode("utf-16"))
        for rows in ([fixture_row()[:-1]], [fixture_row() + [PRIVATE_SENTINEL]], [[]]):
            self.reject(fixture(rows))

    def test_encoding_and_csv_errors_are_generic(self):
        raw = fixture()
        self.reject(raw[2:])
        self.reject(raw[:-1])
        self.reject(b"\xff\xfe\x00\xd8")
        self.reject(raw + ('"' + PRIVATE_SENTINEL).encode("utf-16-le"))
        self.reject(raw + ('"a"' + PRIVATE_SENTINEL).encode("utf-16-le"))
        big_endian = b"\xfe\xff" + raw.decode("utf-16").encode("utf-16-be")
        self.assertEqual(self.parse(big_endian)["record_count"], 1)

    def test_byte_bound_is_inclusive_and_oversize_fails(self):
        raw = fixture()
        with patch.object(pd, "MAX_BYTES", len(raw)):
            self.assertEqual(self.parse(raw)["record_count"], 1)
            self.reject(raw + b"\x00\x00")
        self.reject(b"x" * (pd.MAX_BYTES + 1))

    def test_record_bound_is_inclusive(self):
        with patch.object(pd, "MAX_RECORDS", 2):
            self.assertEqual(self.parse(fixture([fixture_row()] * 2))["record_count"], 2)
            self.reject(fixture([fixture_row()] * 3))
        self.assertEqual(pd.MAX_RECORDS, 20_000)

    def test_empty_export_has_explicit_zero_counts(self):
        result = self.parse(fixture([]))
        self.assertEqual(result["record_count"], 0)
        self.assertEqual(result["distinct_normalized_count"], 0)
        self.assertEqual(result["duplicate_groups"], [])

    def test_missing_source_does_not_leak_path(self):
        with self.assertRaises(ValueError) as caught:
            pd.parse_discovery(Path(tempfile.gettempdir()) / PRIVATE_SENTINEL / "missing.csv")
        self.assertEqual(str(caught.exception), "Cannot read Discovery source")


if __name__ == "__main__":
    unittest.main()
