"""Synthetic privacy/bounds regressions for the read-only inspection helper."""
import io
import json
from pathlib import Path
import tempfile
import unittest

import inspect_json as reader


class InspectJsonTests(unittest.TestCase):
    def read(self, content, limit=reader.DEFAULT_INPUT_BYTES):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.json"
            path.write_bytes(content)
            return reader.read_json(path, limit)

    def test_default_structure_never_descends_into_nested_values(self):
        value = {"source_projection": {"records": [{"secret": "SYNTHETIC_PRIVATE"}]},
                 "rows": ["SYNTHETIC_PRIVATE"], "label": "SYNTHETIC_PRIVATE", "flag": True}
        output = reader.inspect(value)
        self.assertNotIn(b"SYNTHETIC_PRIVATE", output)
        fields = json.loads(output)["root"]["fields"]
        self.assertEqual(fields["source_projection"], {"type": "object", "items": 1})
        self.assertEqual(fields["rows"], {"type": "array", "items": 1})
        self.assertEqual(fields["flag"], {"type": "boolean"})

    def test_exact_selected_count_and_array_index_preserve_values(self):
        value = {"source_projection": {"record_count": 865}, "seeds": ["first", "second"]}
        output = json.loads(reader.inspect(value, ["source_projection.record_count", "seeds.1"]))
        self.assertEqual(output, {"mode": "selected", "fields": {
            "source_projection.record_count": 865, "seeds.1": "second"}})

    def test_whole_utf8_bound_includes_unicode_and_newline(self):
        value = {"text": "\u20ac" * 100}
        output = reader.inspect(value, ["text"], 1000)
        self.assertEqual(reader.inspect(value, ["text"], len(output)), output)
        with self.assertRaisesRegex(reader.InspectionError, "OUTPUT_LIMIT_EXCEEDED"):
            reader.inspect(value, ["text"], len(output) - 1)

    def test_large_nested_selection_fails_instead_of_truncating(self):
        with self.assertRaisesRegex(reader.InspectionError, "OUTPUT_LIMIT_EXCEEDED"):
            reader.inspect({"rows": ["x" * 1000] * 20}, ["rows"])

    def test_bad_selectors_do_not_include_raw_input_in_errors(self):
        for selectors in (["SYNTHETIC_PRIVATE"], ["a..b"], ["a.-1"], ["a.01"], ["a.2"], ["a.0.x"]):
            with self.subTest(selectors=selectors), self.assertRaises(reader.InspectionError) as error:
                reader.inspect({"a": [4]}, selectors)
            self.assertNotIn("SYNTHETIC_PRIVATE", str(error.exception))
        for selectors in (["a", "a"], [None], ["a"] * 33, "a"):
            with self.assertRaisesRegex(reader.InspectionError, "INVALID_SELECTOR"):
                reader.inspect({"a": 1}, selectors)

    def test_strict_duplicate_nonfinite_and_malformed_inputs(self):
        for content in (b'{"a":1,"a":2}', b'{"a":{"x":1,"x":2}}', b'{"a":NaN}',
                        b'{"a":Infinity}', b'{"a":1e10000}', b'{"SYNTHETIC_PRIVATE":', b'\xff'):
            with self.subTest(content=content), self.assertRaisesRegex(reader.InspectionError, "INVALID_JSON"):
                self.read(content)

    def test_input_read_is_bounded_and_utf8_bom_is_supported(self):
        self.assertEqual(self.read(b'\xef\xbb\xbf{"a":4}'), {"a": 4})
        self.assertEqual(self.read(b'{"a":4}', 7), {"a": 4})
        with self.assertRaisesRegex(reader.InspectionError, "INPUT_LIMIT_EXCEEDED"):
            self.read(b'{"a":4}', 6)

    def test_invalid_bounds_rejected(self):
        for bound in (0, -1, True, reader.MAX_OUTPUT_BYTES + 1):
            with self.assertRaisesRegex(reader.InspectionError, "INVALID_BOUND"):
                reader.inspect({}, max_output_bytes=bound)
        with self.assertRaisesRegex(reader.InspectionError, "INVALID_BOUND"):
            self.read(b'{}', reader.MAX_INPUT_BYTES + 1)

    def test_root_scalars_expose_only_type_and_size(self):
        for value in (None, True, 42, "SYNTHETIC_PRIVATE", ["SYNTHETIC_PRIVATE"]):
            output = reader.inspect(value)
            self.assertNotIn(b"SYNTHETIC_PRIVATE", output)
            self.assertNotIn(b'"value"', output)

    def test_cli_has_sanitized_failure_and_no_partial_stdout(self):
        output, errors = io.BytesIO(), io.StringIO()
        status = reader.main(["SYNTHETIC_PRIVATE_MISSING"], output, errors)
        self.assertEqual(status, 2)
        self.assertEqual(output.getvalue(), b"")
        self.assertEqual(errors.getvalue(), "inspect_json: INPUT_UNAVAILABLE\n")
        output, errors = io.BytesIO(), io.StringIO()
        self.assertEqual(reader.main(["--SYNTHETIC_PRIVATE"], output, errors), 2)
        self.assertEqual(errors.getvalue(), "inspect_json: INVALID_ARGUMENTS\n")

    def test_successful_cli_selects_only_requested_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.json"
            path.write_bytes(b'{"count":4,"rows":["SYNTHETIC_PRIVATE"]}')
            output, errors = io.BytesIO(), io.StringIO()
            self.assertEqual(reader.main([str(path), "--select", "count"], output, errors), 0)
            self.assertEqual(json.loads(output.getvalue())["fields"], {"count": 4})
            self.assertEqual(errors.getvalue(), "")

    def test_unpaired_unicode_and_recursive_structures_fail_safely(self):
        with self.assertRaisesRegex(reader.InspectionError, "INVALID_JSON"):
            reader.inspect({"a": "\ud800"}, ["a"])
        value = []
        value.append(value)
        with self.assertRaisesRegex(reader.InspectionError, "INVALID_JSON"):
            reader.inspect({"a": value}, ["a"])


if __name__ == "__main__":
    unittest.main()
