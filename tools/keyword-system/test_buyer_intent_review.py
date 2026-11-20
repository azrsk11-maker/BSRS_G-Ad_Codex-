"""Bounded literal review must never become fabricated full admission."""
from copy import deepcopy
import json
import unittest

import buyer_intent_review as intent


class BuyerIntentReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.review = intent.build_review()

    def reject(self, mutate):
        changed = deepcopy(self.review)
        mutate(changed)
        with self.assertRaisesRegex(ValueError, "REVIEW_DIFFERS"):
            intent.validate_review(changed)

    def test_saved_review_has_exact_bounded_counts(self):
        result = intent.verify_saved()
        self.assertEqual(result["counts"]["complete_literals_preliminarily_reviewed"], 400)
        self.assertEqual(result["counts"]["conditional_buyer_research"], 254)
        self.assertEqual(result["counts"]["held_for_other_review"], 146)
        self.assertEqual(result["counts"]["outside_cohort_occurrences_unassessed"], 2795)
        self.assertIs(result["full_capture_semantic_review_complete"], False)

    def test_every_reviewed_literal_and_complete_public_values_remain_bound(self):
        _, batch, _, _ = intent.load_material()
        self.assertEqual(len(batch["source_projection"]["records"]), 3195)
        self.assertEqual([r["source_ordinal"] for r in self.review["records"]], list(range(1, 401)))
        for original, reviewed in zip(batch["source_projection"]["records"], self.review["records"]):
            self.assertEqual(original["values"]["Keyword"], reviewed["original_literal"])
            self.assertEqual(original["source_line"], reviewed["source_line"])
            self.assertEqual(intent.buyer.digest(original["values"]), reviewed["complete_public_values_sha256"])

    def test_rental_owner_and_other_family_wording_not_silently_mapped_to_buyers(self):
        expected = {16: "TENANT_RENTAL_RESEARCH_HOLD", 186: "OWNER_SELLER_RESEARCH_HOLD",
                    237: "COMMERCIAL_LAND_OR_BUILDING_SCOPE_HOLD",
                    38: "PORTAL_OR_PROVIDER_NAVIGATION_REVIEW_HOLD"}
        for ordinal, decision in expected.items():
            row = self.review["records"][ordinal - 1]
            self.assertEqual(row["decision"], decision)
            self.assertIsNone(row["primary_campaign"])
            self.assertIsNone(row["native_page"])

    def test_owner_direct_buyer_is_not_misclassified_as_seller(self):
        for ordinal in (96, 102):
            self.assertEqual(self.review["records"][ordinal - 1]["decision"], "DIRECT_OWNER_COMMERCIAL_FIT_HOLD")

    def test_finance_foreign_buyer_and_old_year_context_held_without_exclusion(self):
        for ordinal in (90, 95, 126, 185, 214, 271, 293, 311, 397, 398):
            self.assertEqual(self.review["records"][ordinal - 1]["decision"], "FINANCE_INTERNATIONAL_OR_STALE_CONTEXT_HOLD")
        self.assertEqual(self.review["counts"]["exclusions_proposed"], 0)

    def test_conditional_buyer_language_does_not_grant_factual_or_admission_authority(self):
        row = self.review["records"][0]
        self.assertEqual(row["decision"], intent.DEFAULT)
        for key in ("five_subject_bound_reviews_complete", "admitted", "approved", "deployed"):
            self.assertIs(row[key], False)
        self.assertEqual(row["source_kind"], "RESEARCH_HYPOTHESIS")
        self.assertIsNone(row["actual_volume"])
        self.assertIsNone(row["actual_cpc"])

    def test_known_prior_variants_and_legacy_overlap_are_not_novel_canonicals(self):
        legacy = [r["source_ordinal"] for r in self.review["records"] if r["known_normalized_literal_matches_historical"]]
        earlier = [r["source_ordinal"] for r in self.review["records"] if r["known_normalized_literal_matches_prior_capture"]]
        self.assertEqual(legacy, [3, 135, 324])
        self.assertEqual(earlier, [193, 228, 390])
        self.assertTrue(all(r["canonical_novelty"] == "UNRESOLVED_NOT_COUNTED" for r in self.review["records"]))

    def test_full_source_semantic_completion_claim_rejected(self):
        self.reject(lambda r: r["controls"].__setitem__("full_capture_semantic_review_complete", True))

    def test_numeric_false_and_admission_authority_changes_rejected(self):
        self.reject(lambda r: r["records"][0].__setitem__("admitted", 0))

    def test_changed_metric_or_observed_query_claim_rejected(self):
        self.reject(lambda r: r["records"][0].__setitem__("source_kind", "OBSERVED_QUERY"))

    def test_dropped_reordered_or_reclassified_source_fails(self):
        self.reject(lambda r: r["records"].reverse())
        self.reject(lambda r: r["records"][15].__setitem__("decision", intent.DEFAULT))

    def test_outside_cohort_claim_or_unapproved_mapping_fails(self):
        self.reject(lambda r: r["counts"].__setitem__("outside_cohort_occurrences_unassessed", 0))
        self.reject(lambda r: r["records"][0].__setitem__("native_page", "/invented-page/"))


if __name__ == "__main__":
    unittest.main()
