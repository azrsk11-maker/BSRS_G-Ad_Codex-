"""Actual historical seeds; negative checks cannot invent business acceptance."""
import copy
import json
import unittest
from unittest import mock

import positive_service_packet as packet


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


class PositiveServicePacketTests(unittest.TestCase):
    def test_registered_packet_has_no_master_or_deployment_authority(self):
        result = packet.verify_packet((packet.ROOT / packet.PACKET).read_bytes())
        self.assertEqual((result["selected_canonical_seeds"], result["historical_occurrences"]), (2, 4))
        self.assertEqual((result["reviewed_positive_contribution"], result["approved_contribution"], result["deployed_contribution"]), (0, 0, 0))
        self.assertFalse(result["master_admission_allowed"])
        self.assertFalse(result["business_evidence_accepted"])
        self.assertFalse(result["deployment_export_allowed"])

    def test_actual_seeds_and_every_occurrence_are_preserved_without_default_bindings(self):
        value = packet.build_packet()
        self.assertEqual([row["original_text"] for row in value["rows"]], list(packet.SEEDS.values()))
        for row in value["rows"]:
            self.assertEqual(len(row["historical_occurrences"]), 2)
            self.assertEqual({p["historical_match_type"] for p in row["historical_occurrences"]}, {"Exact", "Phrase"})
            self.assertTrue(all(value is None for value in row["binding_overlay_required"].values()))
            self.assertEqual(set(row["admission_reviews_required"]), packet.keyword_audit.ADMISSION_PURPOSES)
            self.assertTrue(all(r["status"] == "NOT_REVIEWED" and r["subject_sha256"] is None for r in row["admission_reviews_required"].values()))

    def test_historical_source_changes_rejected_even_if_json_still_valid(self):
        content = (packet.ROOT / packet.HISTORY).read_bytes()
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            packet.load_history(content + b"\n")

    def test_original_source_validator_runs_after_raw_pin(self):
        with mock.patch.object(packet.historical_intake, "validate_intake", side_effect=ValueError("invalid provenance")):
            with self.assertRaisesRegex(ValueError, "invalid provenance"):
                packet.build_packet()

    def test_forged_review_and_runtime_binding_are_rejected(self):
        base = packet.build_packet()
        for edit in (lambda v: v["rows"][0]["admission_reviews_required"]["claims"].update(status="PASS"),
                     lambda v: v["rows"][0]["binding_overlay_required"].update(primary_campaign_key="BSRE-C0001"),
                     lambda v: v.update(deployment_export_allowed=True),
                     lambda v: v["counts"].update(reviewed_positive_contribution=2)):
            value = copy.deepcopy(base)
            edit(value)
            with self.assertRaisesRegex(ValueError, "differs"):
                packet.verify_packet(encoded(value))

    def test_lost_or_duplicated_provenance_is_rejected(self):
        base = packet.build_packet()
        for occurrences in ([], [base["rows"][0]["historical_occurrences"][0]] * 2):
            value = copy.deepcopy(base)
            value["rows"][0]["historical_occurrences"] = occurrences
            with self.assertRaisesRegex(ValueError, "differs"):
                packet.verify_packet(encoded(value))

    def test_source_contract_drift_is_rejected_by_real_validator(self):
        with mock.patch.object(packet.keyword_audit, "load_positive_contract", side_effect=ValueError("source hash mismatch")):
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                packet.build_packet()

    def test_duplicate_keys_and_invalid_numbers_are_rejected(self):
        for value in (b'{"schema":1,"schema":2}', b'{"value":NaN}'):
            with self.assertRaises(ValueError):
                packet.verify_packet(value)


if __name__ == "__main__":
    unittest.main()
