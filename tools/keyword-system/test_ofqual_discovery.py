"""Synthetic malformed-source, privacy and fresh-provenance acceptance tests."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ofqual_discovery as od

PRIVATE_SENTINEL = "PRIVATE_TEST_ONLY_DISCARDED_FIELD"
METADATA = {"capture_date_utc": "2026-11-11", "http_date": "2026-11-11T15:26:50Z",
            "http_last_modified": "2026-11-11T02:16:08Z", "content_type": "application/octet-stream"}


def row(identity, title, status="Available to learners", **changes):
    values = dict.fromkeys(od.HEADERS, "")
    values.update({"Qualification Number": identity, "Qualification Title": title,
                   "Owner Organisation Name": "TEST ONLY SYNTHETIC ORGANISATION",
                   "Qualification Level": "Level 3", "Qualification Type": "Diploma",
                   "Qualification SSA": "TEST ONLY", "Qualification Status": status,
                   "Specialisms": PRIVATE_SENTINEL})
    values.update(changes)
    return values


def fixture(rows, headers=od.HEADERS):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(headers)
    for values in rows:
        writer.writerow([values.get(field, "") for field in headers])
    return stream.getvalue().encode("utf-8-sig")


class OfqualDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder / "TEST_ONLY_PRIVATE.csv"
        self.rows = [
            row("100/0000/1", "TEST ONLY Catering Diploma"),
            row("100/0000/2", "[TEST ONLY Straße Housing Certificate]"),
            row("100/0000/3", '"TEST ONLY STRASSE Housing Certificate"', "No longer available to new learners"),
            row("100/0000/4", "TEST ONLY Housing Diploma " + "x" * 90, "No longer awarded"),
        ]
        self.source.write_bytes(fixture(self.rows))
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.projection = od.parse_source(self.source, expected_source_sha256=self.digest)
        self.save(self.projection)

    def save(self, projection):
        self.pins = {}
        for name, blob in od.assemble_capture(projection, metadata=METADATA).items():
            (self.folder / name).write_bytes(blob)
            self.pins[name] = hashlib.sha256(blob).hexdigest()

    def altered_public(self, mutate):
        changed = copy.deepcopy(self.projection)
        mutate(changed)
        blob = (json.dumps(changed, ensure_ascii=False) + "\n").encode("utf-8")
        (self.folder / "qualifications.json").write_bytes(blob)
        self.pins["qualifications.json"] = hashlib.sha256(blob).hexdigest()
        return changed

    def parse_bytes(self, blob):
        self.source.write_bytes(blob)
        return od.parse_source(self.source, expected_source_sha256=hashlib.sha256(blob).hexdigest())

    def test_roundtrip_preserves_exact_titles_ids_statuses_and_no_private_columns(self):
        before = self.source.read_bytes()
        self.assertEqual(self.projection["source_record_count"], 4)
        self.assertEqual([r["source_record_ordinal"] for r in self.projection["records"]], [2, 3, 4])
        self.assertEqual([r["values"]["Qualification Title"] for r in self.projection["records"]],
                         [r["Qualification Title"] for r in self.rows[1:]])
        for name in self.pins:
            self.assertNotIn(PRIVATE_SENTINEL.encode(), (self.folder / name).read_bytes())
            self.assertNotIn(str(self.source).encode(), (self.folder / name).read_bytes())
        with patch.object(Path, "write_bytes", side_effect=AssertionError("unexpected writer")):
            public = od.verify_capture(self.folder, self.pins)
            private = od.verify_capture(self.folder, self.pins, self.source)
        self.assertEqual(public["scope"], "PUBLIC_CONSISTENCY_ONLY")
        self.assertEqual(private["scope"], "PRIVATE_RAW_EQUIVALENCE")
        self.assertFalse(private["deployment_authorized"])
        self.assertEqual(self.source.read_bytes(), before)

    def test_normalization_uses_shared_casefold_and_wrappers_without_mutating_literals(self):
        summary = self.projection["summary"]
        self.assertEqual((summary["lexical_rows"], summary["distinct_literal_titles"],
                          summary["distinct_normalized_titles"]), (3, 3, 2))
        group = summary["duplicate_normalized_groups"][0]
        self.assertEqual(group["normalized_title"], "test only strasse housing certificate")
        self.assertEqual(group["source_record_ordinals"], [2, 3])
        self.assertEqual(summary["rows_over_80_characters"], 1)
        self.assertEqual(len(self.projection["records"]), 3)

    def test_quoted_multiline_cells_have_real_physical_ranges_and_exact_strings(self):
        rows = [row("100/0000/1", "TEST ONLY Unrelated Diploma", Specialisms="TEST ONLY first\r\nsecond"),
                row("100/0000/2", "TEST ONLY Housing\nDiploma", **{"Owner Organisation Name": 'TEST ONLY "Quoted", Org'})]
        projection = self.parse_bytes(fixture(rows))
        record = projection["records"][0]
        self.assertEqual((record["source_record_ordinal"], record["source_line_start"], record["source_line_end"]), (2, 4, 5))
        self.assertEqual(record["values"]["Qualification Title"], "TEST ONLY Housing\nDiploma")
        self.assertEqual(record["values"]["Owner Organisation Name"], 'TEST ONLY "Quoted", Org')

    def test_duplicate_reordered_missing_or_extra_headers_fail(self):
        variants = [od.HEADERS[:-1], od.HEADERS + ("TEST ONLY EXTRA",),
                    (od.HEADERS[0],) + od.HEADERS[:-1], tuple(reversed(od.HEADERS))]
        for headers in variants:
            with self.subTest(headers=headers[:2]), self.assertRaisesRegex(ValueError, "EXACT_SOURCE_HEADERS"):
                self.parse_bytes(fixture(self.rows, headers))

    def test_invalid_encoding_quoting_width_controls_and_empty_source_fail(self):
        good = fixture(self.rows)
        cases = [good + b"\xff", good.decode("utf-8-sig").encode("utf-16"),
                 good + b'"unclosed', good.replace(b"TEST ONLY Catering", b'TEST ONLY Cat"ering'),
                 good + b"one,two\r\n", fixture([row("100/0000/1", "TEST ONLY Housing\x00Diploma")]),
                 fixture([]), b""]
        for index, content in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.parse_bytes(content)

    def test_bad_ids_duplicate_ids_statuses_and_dates_fail_for_all_source_rows(self):
        cases = [row("BAD_TEST_ID", "TEST ONLY Housing Diploma"),
                 row("100/0000/1", "TEST ONLY Catering Diploma", "Invented status"),
                 row("100/0000/1", "TEST ONLY Housing Diploma", **{"Operational Start Date": "2026-02-30 00:00:00"})]
        for candidate in cases:
            with self.subTest(candidate=list(candidate)[:1]), self.assertRaises(ValueError):
                self.parse_bytes(fixture([candidate]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_QUALIFICATION_ID"):
            self.parse_bytes(fixture([self.rows[0], self.rows[0]]))

    def test_byte_row_match_and_field_bounds_fail(self):
        content = fixture(self.rows)
        for limit, bound in (("MAX_SOURCE_BYTES", 10), ("MAX_SOURCE_ROWS", 1),
                             ("MAX_MATCH_ROWS", 1), ("MAX_FIELD_BYTES", 10)):
            with self.subTest(limit=limit), patch.object(od, limit, bound), self.assertRaises(ValueError):
                self.parse_bytes(content)

    def test_unknown_public_cells_and_authority_flags_are_rejected_even_with_new_pins(self):
        mutations = [lambda p: p["records"][0]["values"].update(Specialisms=PRIVATE_SENTINEL),
                     lambda p: p["controls"].update(reviewed=True),
                     lambda p: p.update(observed_query="TEST ONLY fabricated query"),
                     lambda p: p["records"][0]["values"].update({"Qualification Status": "Invented status"}),
                     lambda p: p["summary"].update(lexical_rows=True),
                     lambda p: p.update(source_encoding=[])]
        for mutate in mutations:
            self.save(self.projection)
            self.altered_public(mutate)
            with self.subTest(mutation=repr(mutate)), self.assertRaises(ValueError):
                od.verify_capture(self.folder, self.pins)

    def test_provenance_order_types_ranges_and_provider_ids_are_rejected(self):
        mutations = [lambda p: p["records"][0].update(source_record_ordinal=True),
                     lambda p: p["records"][0].update(source_line_start=1),
                     lambda p: p["records"][0].update(source_line_end=999999),
                     lambda p: p["records"][1].update(source_record_ordinal=2),
                     lambda p: p["records"][1].update(source_line_start=3),
                     lambda p: p.update(header_source_line_end=2),
                     lambda p: p["records"][1]["values"].update({"Qualification Number": "100/0000/2"})]
        for mutate in mutations:
            self.save(self.projection)
            self.altered_public(mutate)
            with self.subTest(mutation=repr(mutate)), self.assertRaises(ValueError):
                od.verify_capture(self.folder, self.pins)

    def test_omitted_matching_row_can_only_be_proven_by_fresh_raw_equivalence(self):
        changed = copy.deepcopy(self.projection)
        changed["records"].pop()
        changed["summary"] = od._summary(changed["records"])
        self.save(changed)
        self.assertTrue(od.verify_capture(self.folder, self.pins)["passed"])
        with self.assertRaisesRegex(ValueError, "RAW_PROJECTION_MISMATCH"):
            od.verify_capture(self.folder, self.pins, self.source)

    def test_source_is_read_fresh_and_changed_bytes_never_use_a_cache(self):
        self.assertTrue(od.verify_capture(self.folder, self.pins, self.source)["passed"])
        self.source.write_bytes(self.source.read_bytes() + b"\r\n")
        with self.assertRaisesRegex(ValueError, "SOURCE_HASH_MISMATCH"):
            od.verify_capture(self.folder, self.pins, self.source)

    def test_duplicate_json_keys_invalid_numbers_and_private_error_text_are_sanitized(self):
        for blob in (b'{"PRIVATE_TEST_ONLY_SECRET":1,"PRIVATE_TEST_ONLY_SECRET":2}', b'{"value":NaN}'):
            (self.folder / "qualifications.json").write_bytes(blob)
            self.pins["qualifications.json"] = hashlib.sha256(blob).hexdigest()
            with self.assertRaisesRegex(ValueError, "^PUBLIC_JSON_INVALID$") as caught:
                od.verify_capture(self.folder, self.pins)
            self.assertNotIn("PRIVATE_TEST_ONLY", str(caught.exception))

    def test_manifest_changes_pin_changes_and_bad_metadata_fail(self):
        path = self.folder / "capture.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "PUBLIC_PIN_MISMATCH"):
            od.verify_capture(self.folder, self.pins)
        self.save(self.projection)
        manifest = json.loads(path.read_bytes())
        manifest["master_contribution"]["reviewed_negative"] = 3
        blob = json.dumps(manifest).encode()
        path.write_bytes(blob)
        self.pins["capture.json"] = hashlib.sha256(blob).hexdigest()
        with self.assertRaisesRegex(ValueError, "MANIFEST_CONSISTENCY"):
            od.verify_capture(self.folder, self.pins)
        for metadata in (dict(METADATA, content_type="text/html"),
                         dict(METADATA, http_last_modified="2026-11-12T02:16:08Z"),
                         dict(METADATA, http_date="2026-11-11T00:26:50+05:00",
                              http_last_modified="2026-11-10T00:00:00Z")):
            with self.assertRaises(ValueError):
                od.assemble_capture(self.projection, metadata=metadata)


if __name__ == "__main__":
    unittest.main()
