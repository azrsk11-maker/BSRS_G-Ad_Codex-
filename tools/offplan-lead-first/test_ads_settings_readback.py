"""Regression checks for the saved off-plan Ads settings boundary."""

from copy import deepcopy
import json
from unittest import TestCase

import check_ads_settings_readback as check


class AdsSettingsReadbackTest(TestCase):
    def setUp(self):
        plan = json.loads((check.HERE / "launch.json").read_bytes())
        applied = json.loads((check.HERE / "native-paused/APPLIED.json").read_bytes())
        countries = {market["country_code"]: market["country_name"] for market in plan["markets"]}
        rows = []
        for campaign in applied["campaigns"]:
            country = campaign["country"]
            rows.append({
                "campaign_id": campaign["id"], "campaign_name": campaign["name"], "campaign_state": "Paused",
                "daily_amount_display": f"AED{campaign['average_daily_budget_AED']:,.2f}/day",
                "campaign_type": "Search", "bidding_strategy": "Maximize clicks", "networks": "Google search",
                "location_display": countries[country], "positive_bid_adjustment_display": "None",
                "language_display": "—", "schedule_display": "All day",
                "serving_status_display": "Paused Campaign has no ad groups",
                **dict.fromkeys(check.DISABLED, "Off"),
            })
        rows[0]["schedule_display"] = "All days, 10:00 AM - 7:00 PM"
        rows[0]["serving_status_display"] = "Paused All ad groups are paused"
        rows.extend({"campaign_id": str(9000000000 + index), "campaign_state": "Paused" if index < 16 else "Removed"}
                    for index in range(19))
        self.capture = {"capture": check.FORMAT, "account_id": plan["account_id"],
                        "captured_at_utc": "2026-11-27 17:40:19 UTC", "no_ads_running": True,
                        "observed_campaign_states": {"Paused": 21, "Removed": 3}, "campaigns": rows}

    def test_reports_exact_scope_and_open_schedule_and_languages(self):
        result = check.verify(self.capture)
        self.assertEqual(result["average_daily_budget_aed"], 2500)
        self.assertEqual([k for k, row in result["markets"].items() if row["schedule_matches_plan"]], ["AE"])
        self.assertTrue(all(row["language_display"] == "—" for row in result["markets"].values()))
        self.assertEqual(result["launch_readiness"], "HOLD")
        self.assertIs(result["launch_authorized"], False)

    def test_rejects_enabled_or_incomplete_roster(self):
        self.capture["campaigns"][-4]["campaign_state"] = "Enabled"
        with self.assertRaisesRegex(ValueError, "state drift"):
            check.verify(self.capture)
        self.capture["campaigns"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete campaign roster"):
            check.verify(self.capture)

    def test_rejects_same_counts_with_swapped_or_replaced_legacy_rows(self):
        reference = deepcopy(self.capture)
        rows = self.capture["campaigns"]
        rows[-4]["campaign_state"], rows[-1]["campaign_state"] = "Removed", "Paused"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            check.verify(self.capture, reference)
        rows[-4]["campaign_state"], rows[-1]["campaign_state"] = "Paused", "Removed"
        rows[-1]["campaign_id"] = "9999999999"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            check.verify(self.capture, reference)

    def test_rejects_sum_preserving_unapproved_reallocation(self):
        rows = self.capture["campaigns"]
        rows[0]["daily_amount_display"], rows[1]["daily_amount_display"] = "AED950.00/day", "AED400.00/day"
        with self.assertRaisesRegex(ValueError, "allocation differs"):
            check.verify(self.capture)

    def test_rejects_network_or_expansion_drift(self):
        for field, value in [("networks", "Google search, Search partners"), ("ai_max", "On")]:
            with self.subTest(field=field):
                capture = deepcopy(self.capture)
                capture["campaigns"][0][field] = value
                with self.assertRaisesRegex(ValueError, "Search settings differ"):
                    check.verify(capture)
