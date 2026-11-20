"""Full literal coverage, meaningful context and zero-admission boundaries."""
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

import buyer_full_intent_review as full


class BuyerCompleteIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = full.load_material()
        cls.outputs = full.assemble(*cls.material)
        cls.review = cls.outputs["review.json"]
        cls.queue = cls.outputs["canonical-queue.json"]
        cls.old_pins = {p: hashlib.sha256((full.ROOT / p).read_bytes()).hexdigest()
                        for p in (full.prior.MANUAL, full.prior.REPORT, full.prior.screen.REPORT)}

    @classmethod
    def tearDownClass(cls):
        for path, expected in cls.old_pins.items():
            if hashlib.sha256((full.ROOT / path).read_bytes()).hexdigest() != expected:
                raise AssertionError("Prior source/review changed")

    def reject(self, mutate):
        changed = deepcopy(self.outputs)
        mutate(changed)
        with self.assertRaisesRegex(ValueError, "FULL_REVIEW_DIFFERS"):
            full.validate_outputs(changed)

    def row(self, ordinal):
        return self.review["records"][ordinal - 1]

    def test_saved_full_review_replays_with_exact_counts(self):
        result = full.verify_saved()
        self.assertEqual(result["counts"]["complete_literals_preliminarily_reviewed"], 3195)
        self.assertEqual(result["counts"]["outside_cohort_occurrences_unassessed"], 0)
        self.assertEqual(result["counts"]["conditional_buyer_research"], 1331)
        self.assertEqual(result["counts"]["other_review_holds"], 1864)
        self.assertIs(result["deployment_authorized"], False)

    def test_all_3195_occurrences_lines_originals_and_public_cells_bound(self):
        source = self.material[1]["source_projection"]["records"]
        self.assertEqual([r["source_ordinal"] for r in self.review["records"]], list(range(1, 3196)))
        self.assertEqual(sum(len(r["values"]) for r in source), 67095)
        for original, reviewed in zip(source, self.review["records"]):
            self.assertEqual(original["source_line"], reviewed["source_line"])
            self.assertEqual(original["values"]["Keyword"], reviewed["original_literal"])
            self.assertEqual(full.prior.buyer.digest(original["values"]), reviewed["complete_public_values_sha256"])

    def test_prior_400_decisions_survive_only_declared_broader_labels(self):
        previous = self.material[4]
        for old, new in zip(previous["records"], self.review["records"]):
            self.assertEqual(new["retained_prior_decision"], old["decision"])
            self.assertEqual(new["decision"], full.RENAMES.get(old["decision"], old["decision"]))
        self.assertEqual(sum(r["decision"] == full.DEFAULT for r in self.review["records"][:400]), 254)
        self.assertTrue(all(r["retained_prior_decision"] is None for r in self.review["records"][400:]))

    def test_seven_complete_source_order_cohorts_have_no_gaps(self):
        self.assertEqual([(c["first"], c["last"]) for c in self.review["review_cohorts"]],
                         [(1, 400), (401, 900), (901, 1400), (1401, 1900),
                          (1901, 2400), (2401, 2900), (2901, 3195)])

    def test_tenancy_in_a_purchase_is_not_a_tenant_or_exclusion_label(self):
        for ordinal in (779, 856, 1887, 1948, 1986, 2370, 2672):
            self.assertEqual(self.row(ordinal)["decision"], full.DEFAULT)
            self.assertIs(self.row(ordinal)["admitted"], False)

    def test_locality_words_do_not_become_wrong_service_or_foreign_destination(self):
        for ordinal in (2538, 2539, 2540, 2843, 3082):
            self.assertEqual(self.row(ordinal)["decision"], "TENANT_RENTAL_RESEARCH_HOLD")
        for ordinal in (1251, 1321, 1328, 1519, 2581, 2740):
            self.assertEqual(self.row(ordinal)["decision"], full.DEFAULT)
            self.assertIsNone(self.row(ordinal)["asset_family"])

    def test_company_acquisition_is_outside_property_transaction_scope(self):
        for ordinal in (2138, 3000):
            self.assertEqual(self.row(ordinal)["decision"], "NON_PROPERTY_TRANSACTION_SCOPE_HOLD")
            self.assertIsNone(self.row(ordinal)["primary_campaign"])

    def test_event_holiday_and_daily_rentals_need_separate_service_producer(self):
        for ordinal in (1359, 1861, 3021, 3133):
            self.assertEqual(self.row(ordinal)["decision"], "EVENT_PURPOSE_OR_SHORT_STAY_SERVICE_HOLD")
            self.assertIs(self.row(ordinal)["business_evidence_verified"], False)
        self.assertEqual(self.review["counts"]["categories"]["EVENT_PURPOSE_OR_SHORT_STAY_SERVICE_HOLD"], 4)

    def test_named_context_profiles_and_unqualified_entity_do_not_invent_buyers(self):
        for ordinal in (1433, 1952, 2990, 3006, 3041, 3102):
            self.assertEqual(self.row(ordinal)["decision"], "AMBIGUOUS_PROPERTY_ENTITY_OR_PRICE_HOLD")
            self.assertIsNone(self.row(ordinal)["asset_family"])

    def test_direct_owner_buyer_is_not_seller_and_rental_keeps_its_role(self):
        for ordinal in (96, 102, 714, 900, 1098, 2981):
            self.assertEqual(self.row(ordinal)["decision"], "DIRECT_OWNER_COMMERCIAL_FIT_HOLD")
        self.assertEqual(self.row(939)["decision"], "TENANT_RENTAL_RESEARCH_HOLD")

    def test_all_queue_joins_preserve_every_source_peer_and_historical_reference(self):
        original = self.material[3]["source_occurrences"]
        expected = [r["source_ordinal"] for r in self.review["records"] if r["decision"] == full.DEFAULT]
        self.assertEqual([r["source_ordinal"] for r in self.queue["candidate_occurrences"]], expected)
        for row in self.queue["candidate_occurrences"]:
            self.assertEqual(row["joins"], original[row["source_ordinal"] - 1]["joins"])
        self.assertEqual((self.queue["prior_literal_context_rows"], self.queue["variant_context_rows"],
                          self.queue["unassessed_canonical_context_rows"]), (9, 181, 1141))

    def test_queue_items_never_count_as_novel_canonical_or_admitted_keywords(self):
        self.assertEqual(len(self.queue["candidate_occurrences"]), 1331)
        self.assertIsNone(self.queue["confirmed_novel_canonicals"])
        for row in self.queue["candidate_occurrences"]:
            self.assertIsNone(row["confirmed_novel_canonical"])
            self.assertIs(row["positive_admission_granted"], False)

    def test_complete_literal_review_is_not_complete_business_or_canonical_review(self):
        controls = self.review["controls"]
        self.assertIs(controls["all_complete_literals_preliminarily_assessed"], True)
        for key in ("semantic_canonicalization_complete", "full_admission_review_complete",
                    "independent_human_review_complete", "business_evidence_verified",
                    "five_subject_bound_reviews_complete", "fresh_applicable_exclusion_scope_acceptance"):
            self.assertIs(controls[key], False)

    def test_every_mapping_and_actual_metric_remains_unknown(self):
        for row in self.review["records"]:
            for key in ("asset_family", "primary_campaign", "ad_group", "native_page", "actual_volume", "actual_cpc"):
                self.assertIsNone(row[key])
            self.assertEqual(row["source_kind"], "RESEARCH_HYPOTHESIS")

    def test_fabricated_canonical_total_rejected(self):
        self.reject(lambda o: o["canonical-queue.json"].__setitem__("confirmed_novel_canonicals", 1331))

    def test_numeric_false_and_admission_authority_changes_rejected(self):
        self.reject(lambda o: o["review.json"]["controls"].__setitem__("deployment_authorized", 0))
        self.reject(lambda o: o["review.json"]["controls"].__setitem__("full_admission_review_complete", True))

    def test_dropped_reordered_or_reclassified_sources_fail(self):
        self.reject(lambda o: o["review.json"]["records"].reverse())
        self.reject(lambda o: o["review.json"]["records"][2137].__setitem__("decision", full.DEFAULT))

    def test_changed_metric_or_observed_query_claim_rejected(self):
        self.reject(lambda o: o["review.json"]["records"][0].__setitem__("actual_cpc", 0))
        self.reject(lambda o: o["review.json"]["records"][0].__setitem__("source_kind", "OBSERVED_QUERY"))

    def test_omitted_queue_peer_or_unapproved_page_mapping_rejected(self):
        self.reject(lambda o: o["canonical-queue.json"]["candidate_occurrences"][0]["joins"].clear())
        self.reject(lambda o: o["review.json"]["records"][0].__setitem__("native_page", "/unapproved/"))

    def test_dependency_is_freshly_read_before_any_old_material_is_accepted(self):
        original = full.prior.buyer.read_bound
        target = full.ROOT / next(iter(full.DEPENDENCIES))
        with patch.object(full.prior.buyer, "read_bound", side_effect=lambda p: original(p) + (b" " if Path(p) == target else b"")), \
                patch.object(full.prior, "load_material") as load:
            with self.assertRaisesRegex(ValueError, "DEPENDENCY_PIN_CHANGED"):
                full.load_material()
            load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
