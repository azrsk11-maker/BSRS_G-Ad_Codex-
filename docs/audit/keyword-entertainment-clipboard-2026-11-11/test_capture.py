"""Small integrity tests over the actual pinned clipboard projection."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import capture_tools as tools
import verify_capture as verifier


class ClipboardCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.blobs = {name: (HERE / name).read_bytes() for name in verifier.PINS}
        cls.rows = json.loads(cls.blobs["keywords.json"])["records"]
        # The actual pinned source uses CRLF and a final newline. Its raw hash
        # authenticates this round trip; the separate CLI also reads private raw.
        cls.raw = ("\r\n".join(row["keyword"] for row in cls.rows) + "\r\n").encode("utf-8")

    def modified(self, name, value):
        blobs, pins = dict(self.blobs), dict(verifier.PINS)
        blobs[name] = tools.canonical(value)
        pins[name] = hashlib.sha256(blobs[name]).hexdigest()
        return blobs, pins

    def test_actual_public_and_source_round_trip(self):
        self.assertTrue(verifier.verify()["passed"])
        result = tools.validate_bundle(self.blobs, verifier.PINS, self.raw)
        self.assertTrue(result["private_raw_equality_verified"])
        self.assertEqual((result["proposed_exact"], result["held"]), (318, 200))

    def test_same_size_raw_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError, "RAW_HASH_CHANGED"):
            tools.parse_source(b"x" + self.raw[1:])

    def test_resealed_reordered_projection_rejected(self):
        value = json.loads(self.blobs["keywords.json"])
        value["records"][0]["keyword"], value["records"][1]["keyword"] = value["records"][1]["keyword"], value["records"][0]["keyword"]
        blobs, pins = self.modified("keywords.json", value)
        with self.assertRaisesRegex(ValueError, "PROJECTED_LITERALS_CHANGED"):
            tools.validate_bundle(blobs, pins)

    def test_resealed_invented_metric_rejected(self):
        value = json.loads(self.blobs["keywords.json"])
        value["records"][0]["average_monthly_searches"] = 0
        blobs, pins = self.modified("keywords.json", value)
        with self.assertRaisesRegex(ValueError, "PROJECTION_SCHEMA"):
            tools.validate_bundle(blobs, pins)

    def test_resealed_missing_held_assessment_rejected(self):
        value = json.loads(self.blobs["review.json"])
        value["assessments"] = [row for row in value["assessments"] if row["ordinal"] != 6]
        blobs, pins = self.modified("review.json", value)
        with self.assertRaisesRegex(ValueError, "REVIEW_COVERAGE_CHANGED"):
            tools.validate_bundle(blobs, pins)

    def test_changed_semantic_review_rejected_by_fixed_pin(self):
        value = json.loads(self.blobs["review.json"])
        value["assessments"][5]["disposition"] = "PROPOSE_EXACT"
        blobs, _ = self.modified("review.json", value)
        with self.assertRaisesRegex(ValueError, "PIN_CHANGED"):
            tools.validate_bundle(blobs, verifier.PINS)

    def test_resealed_missing_variant_group_rejected(self):
        value = json.loads(self.blobs["lexical.json"])
        value["equal_token_bag_groups"].pop()
        blobs, pins = self.modified("lexical.json", value)
        with self.assertRaisesRegex(ValueError, "LEXICAL_DIAGNOSTIC_CHANGED"):
            tools.validate_bundle(blobs, pins)

    def test_duplicate_json_keys_and_oversize_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
            tools.parse_json(b'{"rows": 518, "rows": 0}')
        with self.assertRaisesRegex(ValueError, "JSON_BOUNDS"):
            tools.parse_json(b"x" * (tools.MAX_BYTES + 1))


if __name__ == "__main__":
    unittest.main()
