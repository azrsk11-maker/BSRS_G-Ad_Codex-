"""Synthetic single-snapshot and explicit-delegation checks for current intake."""
from pathlib import Path
import json
import unittest

import current_keyword_audit as current
import keyword_audit as historical


class ChangingInput:
    def __init__(self, suffix, first):
        self.suffix = suffix
        self.first = first
        self.reads = 0

    def read_bytes(self):
        self.reads += 1
        return self.first if self.reads == 1 else b"corrupted second read"


class CurrentIntakeTests(unittest.TestCase):
    def test_strict_csv_reads_once_and_explicit_snapshot_reads_zero_times(self):
        raw = b'keyword_id,scope_target\nQA-N1,"{""campaign_key"":""QA-C1""}"\n'
        path = ChangingInput(".csv", raw)
        expected = [{"keyword_id": "QA-N1", "scope_target": {"campaign_key": "QA-C1"}}]
        self.assertEqual(current.read_records(path), expected)
        self.assertEqual(path.reads, 1)
        path = ChangingInput(".csv", b"unread")
        self.assertEqual(current.read_records(path, content=raw), expected)
        self.assertEqual(path.reads, 0)
        with self.assertRaisesRegex(ValueError, "Invalid number"):
            current.read_records(Path("fixture.csv"), content=b'scope_target\n"{""value"":NaN}"\n')

    def test_json_reads_once_and_explicit_snapshot_reads_zero_times(self):
        raw = b'[{"keyword_id":"QA-N1","scope_target":{"campaign_key":"QA-C1"}}]'
        path = ChangingInput(".json", raw)
        self.assertEqual(current.read_records(path), historical.read_records(Path("fixture.json"), content=raw))
        self.assertEqual(path.reads, 1)
        path = ChangingInput(".json", b"unread")
        self.assertEqual(current.read_records(path, content=raw)[0]["keyword_id"], "QA-N1")
        self.assertEqual(path.reads, 0)

    def test_matching_validation_delegates_and_current_json_parser_is_strict(self):
        for name in ("normalize", "tokens", "negative_matches", "audit", "release_gate", "proposed_capacity"):
            with self.subTest(name=name):
                self.assertIs(getattr(current, name), getattr(historical, name))
        self.assertIsNot(current.read_records, historical.read_records)
        self.assertIsNot(current.main, historical.main)
        self.assertIsNot(current.parse_json_bytes, historical.parse_json_bytes)
        finite = b'{"metadata":[1e308,-1e308,"1e400",null,true]}'
        self.assertEqual(current.parse_json_bytes(finite), historical.parse_json_bytes(finite))
        with self.assertRaisesRegex(ValueError, "Invalid number"):
            current.parse_json_bytes(b'{"metadata":[1e400]}')

    def test_overflow_in_every_structured_field_is_rejected_for_json_and_csv(self):
        import csv
        import io
        for field in sorted(current.JSON_FIELDS):
            for literal in ("1e400", "-1e400"):
                for nested in (literal, '{"metadata":[' + literal + ']}', '[{"metadata":' + literal + '}]'):
                    with self.subTest(field=field, literal=literal, nested=nested):
                        raw_json = ('[{"' + field + '":' + nested + '}]').encode("utf-8")
                        with self.assertRaisesRegex(ValueError, "Invalid number"):
                            current.read_records(Path("fixture.json"), content=raw_json)
                        handle = io.StringIO(newline="")
                        writer = csv.writer(handle)
                        writer.writerow([field])
                        writer.writerow([nested])
                        with self.assertRaisesRegex(ValueError, "Invalid number"):
                            current.read_records(Path("fixture.csv"), content=handle.getvalue().encode("utf-8"))

    def test_public_json_and_config_loader_reject_nested_overflow_in_one_read(self):
        for literal in ("1e400", "-1e400"):
            raw = b"\xef\xbb\xbf" + ('{"config":[{"metadata":' + literal + '}]}').encode("utf-8")
            with self.subTest(literal=literal):
                with self.assertRaisesRegex(ValueError, "Invalid number"):
                    current.parse_json_bytes(raw)
                path = ChangingInput(".json", raw)
                with self.assertRaisesRegex(ValueError, "Invalid number"):
                    current.load_json(path)
                self.assertEqual(path.reads, 1)

    def test_large_finite_values_strings_and_utf8_bom_match_legacy(self):
        import csv
        import io
        value = {"metadata": [1e308, -1e308, 1e-308, 10 ** 100, "1e400", "NaN", "دبي", None, True]}
        raw = b"\xef\xbb\xbf" + json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.assertEqual(current.parse_json_bytes(raw), historical.parse_json_bytes(raw))
        path = ChangingInput(".json", raw)
        self.assertEqual(current.load_json(path), value)
        self.assertEqual(path.reads, 1)
        handle = io.StringIO(newline="")
        writer = csv.writer(handle)
        writer.writerow(["scope_target"])
        writer.writerow([json.dumps(value, ensure_ascii=False)])
        raw_csv = b"\xef\xbb\xbf" + handle.getvalue().encode("utf-8")
        self.assertEqual(current.read_records(Path("fixture.csv"), content=raw_csv),
                         historical.read_records(Path("fixture.csv"), content=raw_csv))

    def test_csv_scalar_metric_overflow_is_rejected_before_audit(self):
        for field in ("volume", "cpc"):
            for literal in ("1e400", "-1e400", "NaN", "Infinity", "-Infinity"):
                with self.subTest(field=field, literal=literal):
                    with self.assertRaisesRegex(ValueError, "Invalid number"):
                        current.read_records(Path("fixture.csv"), content=(field + "\n" + literal + "\n").encode("utf-8"))

    def test_current_cli_rejects_overflow_for_both_kinds_formats_and_outputs(self):
        import contextlib
        import csv
        import io
        import sys
        import tempfile
        from unittest.mock import patch
        import test_keyword_audit as fixtures
        for kind in ("positive", "negative"):
            for suffix in ("json", "csv"):
                for literal in ("1e400", "-1e400"):
                    for existing_output in (False, True):
                        with self.subTest(kind=kind, suffix=suffix, literal=literal, existing_output=existing_output), tempfile.TemporaryDirectory() as folder:
                            root = Path(folder)
                            row = fixtures.positive() if kind == "positive" else fixtures.negative()
                            metadata = row["admission_reviews"]["inventory_service"] if kind == "positive" else row["scope_target"]
                            metadata["overflow_metadata"] = [{"nested": "OVERFLOW_TOKEN"}]
                            records = root / ("records." + suffix)
                            if suffix == "json":
                                records.write_text(json.dumps([row]).replace('"OVERFLOW_TOKEN"', literal), encoding="utf-8")
                            else:
                                encoded = {key: json.dumps(value).replace('"OVERFLOW_TOKEN"', literal) if key in current.JSON_FIELDS
                                           else "" if value is None else value for key, value in row.items()}
                                with records.open("w", encoding="utf-8", newline="") as handle:
                                    writer = csv.DictWriter(handle, fieldnames=list(encoded))
                                    writer.writeheader()
                                    writer.writerow(encoded)
                            argv = ["current_keyword_audit.py", "--kind", kind, "--input", str(records), "--as-of", str(fixtures.TODAY)]
                            for flag, value in (("sources", fixtures.SOURCES), ("campaigns", fixtures.CAMPAIGNS), ("campaign-context", fixtures.CONTEXT),
                                                ("protected", fixtures.PROTECTED), ("scope-bindings", fixtures.SCOPE_BINDINGS)):
                                path = root / (flag + ".json")
                                path.write_text(json.dumps(value), encoding="utf-8")
                                argv.extend(["--" + flag, str(path)])
                            output = root / "report.json"
                            if existing_output:
                                output.write_bytes(b"existing-output-must-survive")
                            argv.extend(["--output", str(output)])
                            diagnostic = io.StringIO()
                            with patch.object(sys, "argv", argv), contextlib.redirect_stderr(diagnostic), contextlib.redirect_stdout(io.StringIO()):
                                with self.assertRaises(SystemExit) as failure:
                                    current.main()
                            self.assertEqual(failure.exception.code, 2)
                            self.assertIn("Invalid number", diagnostic.getvalue())
                            self.assertNotIn("Traceback", diagnostic.getvalue())
                            if existing_output:
                                self.assertEqual(output.read_bytes(), b"existing-output-must-survive")
                            else:
                                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
