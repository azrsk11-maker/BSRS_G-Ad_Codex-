import copy
import json
import unittest
import selected_owner_packet as packet

def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')

class SelectedOwnerPacketTests(unittest.TestCase):
    def test_verify_rejects_boolean_number_type_substitution(self):
        ids = ["LEGACY-POS-0031"]
        base = packet.build_packet(candidate_ids=ids)
        for change in (lambda v: v.update(deployment_export_allowed=0),
                       lambda v: v['counts'].update(approved_contribution=False),
                       lambda v: v['counts'].update(selected_canonical_seeds=1.0)):
            value = copy.deepcopy(base)
            change(value)
            with self.assertRaises(ValueError):
                packet.verify_packet(encoded(value), candidate_ids=ids)

    def test_selected_owner_workorder_preserves_source_and_empty_reviews(self):
        ids = ["LEGACY-POS-0031", "LEGACY-POS-0030"]
        value = packet.build_packet(candidate_ids=ids)
        self.assertEqual([r["candidate_id"] for r in value["rows"]], sorted(ids))
        self.assertEqual(value["counts"]["historical_occurrences"], 4)
        self.assertTrue(all(v is None for r in value["rows"] for v in r["binding_overlay_required"].values()))
        self.assertTrue(all(v["status"] == "NOT_REVIEWED" for r in value["rows"] for v in r["admission_reviews_required"].values()))
        result = packet.verify_packet(encoded(value), candidate_ids=ids)
        self.assertFalse(result["master_admission_allowed"])
        self.assertFalse(result["deployment_export_allowed"])

    def test_selection_rejects_unknown_duplicate_empty_wrong_role_and_wrong_types(self):
        for ids in ([], ["UNKNOWN"], ["LEGACY-POS-0030"]*2,
                    ["LEGACY-POS-0001"], "LEGACY-POS-0030", [None], [{}]):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                packet.build_packet(candidate_ids=ids)

    def test_selected_verifier_cannot_trust_its_own_selection_or_forged_reviews(self):
        ids = ["LEGACY-POS-0031"]
        value = packet.build_packet(candidate_ids=ids)
        with self.assertRaises(ValueError):
            packet.verify_packet(encoded(value), candidate_ids=["LEGACY-POS-0030"])
        value["rows"][0]["admission_reviews_required"]["claims"]["status"] = "PASS"
        with self.assertRaises(ValueError):
            packet.verify_packet(encoded(value), candidate_ids=ids)

