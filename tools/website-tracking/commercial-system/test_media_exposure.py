import unittest

from media_exposure import standard_search_exposure


class MediaExposureTests(unittest.TestCase):
    def test_historical_four_campaign_scope(self):
        pools = [("buyers", 120_000), ("owners", 40_000), ("tenants", 30_000), ("brand", 10_000)]
        report = standard_search_exposure(pools, 200_000, unchanged_full_month=True)
        self.assertEqual(report["modeled_daily_media_fils"], 400_000)
        self.assertEqual(report["modeled_monthly_media_fils"], 6_080_000)
        self.assertEqual(report["monthly_media_comparison"]["status"], "UNKNOWN")
        self.assertEqual(report["monthly_cash_comparison"]["status"], "UNKNOWN")

    def test_five_prepared_pools(self):
        pools = [("AE", 100_000), ("DE", 35_000), ("FR", 30_000), ("IN", 50_000), ("TW", 35_000)]
        report = standard_search_exposure(pools, 250_000, unchanged_full_month=True)
        self.assertEqual(report["modeled_daily_media_fils"], 500_000)
        self.assertEqual(report["modeled_monthly_media_fils"], 7_600_000)
        self.assertFalse(report["release_authorized_by_calculation"])

    def test_cash_and_net_media_have_separate_comparisons(self):
        report = standard_search_exposure(
            [("pool", 1_000)], 1_000, unchanged_full_month=True,
            approved_monthly_media_fils=30_400,
            approved_monthly_cash_risk_fils=31_000,
            verified_monthly_cash_exposure_fils=32_000,
        )
        self.assertEqual(report["monthly_media_comparison"], {"status": "WITHIN_CEILING", "headroom_fils": 0})
        self.assertEqual(report["monthly_cash_comparison"], {"status": "EXCEEDS_CEILING", "headroom_fils": -1_000})

    def test_cash_ceiling_does_not_turn_media_into_cash_estimate(self):
        report = standard_search_exposure(
            [("pool", 1_000)], 1_000, unchanged_full_month=True, approved_monthly_cash_risk_fils=31_000,
        )
        self.assertIsNone(report["verified_monthly_cash_exposure_fils"])
        self.assertEqual(report["monthly_cash_comparison"], {"status": "UNKNOWN", "headroom_fils": None})

    def test_edited_or_partial_month_has_no_projection(self):
        report = standard_search_exposure(
            [("pool", 1_000)], 1_000, unchanged_full_month=False, approved_monthly_media_fils=30_400,
        )
        self.assertIsNone(report["modeled_daily_media_fils"])
        self.assertIsNone(report["modeled_monthly_media_fils"])
        self.assertEqual(report["monthly_media_comparison"]["status"], "UNKNOWN")

    def test_fractional_fils_are_rounded_up_per_pool(self):
        report = standard_search_exposure([("one", 1), ("two", 1)], 2, unchanged_full_month=True)
        self.assertEqual(report["modeled_monthly_media_fils"], 62)

    def test_duplicate_or_incomplete_pool_coverage_fails(self):
        with self.assertRaisesRegex(ValueError, "duplicate budget pool"):
            standard_search_exposure([("shared", 500), ("shared", 500)], 1_000, unchanged_full_month=True)
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            standard_search_exposure([("pool", 500)], 1_000, unchanged_full_month=True)
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            pools = [("AE", 100_000), ("DE", 35_000), ("FR", 35_000), ("IN", 50_000), ("TW", 35_000)]
            standard_search_exposure(pools, 250_000, unchanged_full_month=True)

    def test_invalid_amounts_or_assumptions_fail(self):
        for invalid in (True, -1, 0, 1.0, "1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                standard_search_exposure([("pool", invalid)], 1, unchanged_full_month=True)
        with self.assertRaisesRegex(ValueError, "must be boolean"):
            standard_search_exposure([("pool", 1)], 1, unchanged_full_month=1)
        with self.assertRaisesRegex(ValueError, "approved_monthly_media_fils"):
            standard_search_exposure([("pool", 1)], 1, unchanged_full_month=True, approved_monthly_media_fils=True)

    def test_independently_verified_zero_cash_exposure_is_distinct_from_unknown(self):
        report = standard_search_exposure(
            [("pool", 1)], 1, unchanged_full_month=False,
            approved_monthly_cash_risk_fils=1_000, verified_monthly_cash_exposure_fils=0,
        )
        self.assertEqual(report["monthly_cash_comparison"], {"status": "WITHIN_CEILING", "headroom_fils": 1_000})


if __name__ == "__main__":
    unittest.main()
