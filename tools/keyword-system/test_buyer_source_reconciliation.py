"""Source custody, exhaustive joins and authority boundaries for buyer intake."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import buyer_source_reconciliation as buyer


class BuyerSourceReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ordinary in-module fixture only; every production verifier reads fresh.
        cls.inputs = buyer.load_inputs()
        cls.report = buyer._compute(*cls.inputs)
        cls.blob = buyer.read_bound(buyer.ROOT / buyer.REPORT)
        cls.original_pins = {p: hashlib.sha256((buyer.ROOT / p).read_bytes()).hexdigest()
                             for p in (buyer.PRIOR, buyer.historical.HISTORY)}

    @classmethod
    def tearDownClass(cls):
        for path, expected in cls.original_pins.items():
            if hashlib.sha256((buyer.ROOT / path).read_bytes()).hexdigest() != expected:
                raise AssertionError("Historical source was changed")

    def assert_rejected(self, mutate):
        changed = deepcopy(self.report)
        mutate(changed)
        with self.assertRaisesRegex(ValueError, "RECONCILIATION_DIFFERS"):
            buyer.validate_report(changed)

    def test_pinned_report_replays_from_fresh_complete_sources(self):
        result = buyer.verify_report(self.blob)
        self.assertTrue(result["passed"])
        self.assertFalse(result["deployment_authorized"])

    def test_all_occurrences_physical_lines_and_cells_bound(self):
        source = self.inputs[0]["source_projection"]["records"]
        compared = self.report["source_occurrences"]
        self.assertEqual(len(compared), 3195)
        self.assertEqual(sum(len(row["values"]) for row in source), 67095)
        self.assertEqual([r["source_ordinal"] for r in compared], list(range(1, 3196)))
        self.assertEqual([r["source_line"] for r in compared], list(range(4, 3199)))
        for left, right in zip(source, compared):
            self.assertEqual(right["original_literal"], left["values"]["Keyword"])
            self.assertEqual(right["complete_public_values_sha256"], buyer.digest(left["values"]))

    def test_historical_candidates_placements_and_prior_metrics_preserved(self):
        external = self.report["external_literal_references"]
        legacy = [r for r in external if r["population"] == "historical_candidate"]
        prior = [r for r in external if r["population"] == "prior_buyer_capture"]
        self.assertEqual(len(legacy), 41)
        self.assertEqual(len({p for r in legacy for p in r["placement_ids"]}), 82)
        self.assertEqual(len(prior), 6)
        for row, original in zip(prior, self.inputs[2]["rows"]):
            self.assertEqual(row["complete_cells_sha256"], buyer.digest(original["cells"]))

    def test_actual_normalized_literal_overlaps_not_new_admissions(self):
        self.assertEqual(self.report["ordinal_sets"]["normalized_literal_matches_historical"], [3, 135, 324, 841])
        self.assertEqual(self.report["ordinal_sets"]["normalized_literal_matches_prior_capture"], [193, 228, 390, 516, 1101])
        self.assertIsNone(self.report["counts"]["confirmed_novel_canonicals"])
        self.assertEqual(self.report["counts"]["positive_admissions_added"], 0)

    def test_preposition_variant_flags_both_originals_without_merging(self):
        a, b = (self.report["source_occurrences"][n - 1] for n in (390, 1101))
        self.assertNotEqual(a["original_literal"], b["original_literal"])
        self.assertEqual(a["joins"][0]["external_references"], ["prior-buyer:ordinal:4"])
        self.assertEqual(b["joins"][0]["external_references"], ["prior-buyer:ordinal:6"])
        self.assertEqual(a["joins"][4]["source_peer_ordinals"], [1101])
        self.assertEqual(b["joins"][4]["source_peer_ordinals"], [390])
        self.assertEqual(a["semantic_review"], "UNASSESSED_NOT_ADMITTED")

    def test_every_join_matches_independent_small_cartesian_oracle(self):
        # Distributed ordinals and known boundary cases; full coverage is separately tested.
        rows = self.report["source_occurrences"]
        external = self.report["external_literal_references"]
        for ordinal in sorted({1, 3, 324, 390, 1101, 3195, *range(1, 3196, 313)}):
            row = rows[ordinal - 1]
            for index, join in enumerate(row["joins"]):
                key = buyer.attention_keys(row["original_literal"])[index]
                expected_external = sorted(r["reference"] for r in external
                                           if buyer.attention_keys(r["original_literal"])[index] == key)
                expected_peers = [r["source_ordinal"] for r in rows
                                  if r["source_ordinal"] != ordinal
                                  and buyer.attention_keys(r["original_literal"])[index] == key]
                self.assertEqual(join["external_references"], expected_external)
                self.assertEqual(join["source_peer_ordinals"], expected_peers)

    def test_no_self_peers_and_all_groups_reciprocal(self):
        rows = self.report["source_occurrences"]
        for row in rows:
            for index, join in enumerate(row["joins"]):
                self.assertNotIn(row["source_ordinal"], join["source_peer_ordinals"])
                for peer in join["source_peer_ordinals"]:
                    self.assertIn(row["source_ordinal"], rows[peer - 1]["joins"][index]["source_peer_ordinals"])

    def test_unmatched_is_not_a_novelty_or_current_library_claim(self):
        self.assertEqual(len(self.report["ordinal_sets"]["unmatched_unassessed"]), 2864)
        for key in ("semantic_review_complete", "current_library_membership_verified",
                    "current_negative_conflicts_tested", "google_equivalence_verified",
                    "business_evidence_verified", "campaign_or_page_mapping_assigned"):
            self.assertIs(self.report["controls"][key], False)

    def test_admission_authority_tamper_rejected_even_with_resealed_report(self):
        self.assert_rejected(lambda r: r["controls"].__setitem__("admission_approved", True))

    def test_boolean_replaced_by_zero_rejected(self):
        self.assert_rejected(lambda r: r["controls"].__setitem__("deployment_authorized", 0))

    def test_invented_novel_canonical_total_rejected(self):
        self.assert_rejected(lambda r: r["counts"].__setitem__("confirmed_novel_canonicals", 3195))

    def test_dropped_or_reordered_occurrence_rejected(self):
        self.assert_rejected(lambda r: r["source_occurrences"].reverse())

    def test_changed_metric_binding_rejected(self):
        self.assert_rejected(lambda r: r["source_occurrences"][0].__setitem__("complete_public_values_sha256", "0" * 64))

    def test_false_join_and_removed_hold_rejected(self):
        self.assert_rejected(lambda r: r["source_occurrences"][389]["joins"][4]["source_peer_ordinals"].clear())

    def test_unknown_private_or_inferred_metric_field_rejected(self):
        self.assert_rejected(lambda r: r["source_occurrences"][0].__setitem__("actual_cpc", 0))

    def test_raw_byte_changes_rejected_before_report_acceptance(self):
        with self.assertRaisesRegex(ValueError, "REPORT_PIN_CHANGED"):
            buyer.verify_report(self.blob + b" ")

    def test_prior_source_freshly_rehashed(self):
        original = buyer.read_bound
        def changed(path):
            blob = original(path)
            return blob + b" " if Path(path) == buyer.ROOT / buyer.PRIOR else blob
        with patch.object(buyer, "read_bound", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "PRIOR_SOURCE_PIN_CHANGED"):
                buyer.build_report()

    def test_shared_dependency_freshness_failure_is_not_cached(self):
        original = buyer.read_bound
        path = buyer.ROOT / next(iter(buyer.DEPENDENCIES))
        with patch.object(buyer, "read_bound", side_effect=lambda p: original(p) + (b" " if Path(p) == path else b"")):
            with self.assertRaisesRegex(ValueError, "DEPENDENCY_PIN_CHANGED"):
                buyer.build_report()

    def test_capture_public_consistency_and_twelve_tamper_probes(self):
        path = buyer.ROOT / buyer.FOLDER / "verify_capture.py"
        spec = importlib.util.spec_from_file_location("buyer_capture_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module.verify()["export_rows"], 3195)
        self.assertEqual(module.self_check()["in_memory_mutations_rejected"], 12)


if __name__ == "__main__":
    unittest.main()
