"""Synthetic checks of the shared-parent Ads scope verifier."""

from copy import deepcopy
from unittest import TestCase

import check_uae_activation_scope as check
from check_ads_settings_readback import FORMAT


ACCOUNT = "573-038-4686"
PARENT = "24372566774"
OFFPLAN = "204397706154"
RESALE = "204397706314"
OTHER_CAMPAIGN = "9000000000"
START = "2026-11-27 19:00:00 UTC"
CAPTURED = "2026-11-27 19:01:00 UTC"
NOW = check.timestamp("2026-11-27 19:02:00 UTC")


class UAEActivationScopeTest(TestCase):
    def setUp(self):
        self.reference = {
            "account_id": ACCOUNT, "capture": FORMAT, "captured_at_utc": "2026-11-27 17:40:19 UTC",
            "no_ads_running": True, "observed_campaign_states": {"Paused": 21, "Removed": 3},
            "campaigns": [{"campaign_id": PARENT, "campaign_state": "Paused"}, *[
                {"campaign_id": str(9000000000 + index), "campaign_state": "Paused" if index < 20 else "Removed"}
                for index in range(23)
            ]],
        }
        self.current = deepcopy(self.reference)
        self.current["captured_at_utc"] = CAPTURED
        self.children = {
            "schema": check.CHILD_SCHEMA, "account_id": ACCOUNT, "captured_at_utc": CAPTURED,
            "campaign_or_ad_group_changes": False, "view_total": 2,
            "view": {"campaign_id": PARENT, "ad_group_statuses": ["Enabled", "Paused", "Removed"], "other_filters": []},
            "ad_groups": [
                {"campaign_id": PARENT, "ad_group_id": OFFPLAN, "explicit_status": "Enabled"},
                {"campaign_id": PARENT, "ad_group_id": RESALE, "explicit_status": "Paused"},
            ],
        }

    def verify(self, stage="staged"):
        return check.verify(stage, self.current, self.children, self.reference, START, now=NOW)

    def enable_campaign(self, campaign_id):
        row = next(row for row in self.current["campaigns"] if row["campaign_id"] == campaign_id)
        row["campaign_state"] = "Enabled"
        self.current["observed_campaign_states"] = {"Paused": 20, "Removed": 3, "Enabled": 1}

    def test_exact_staged_enabled_and_rollback_scope(self):
        staged = self.verify()
        self.enable_campaign(PARENT)
        enabled = self.verify("enabled")
        self.current["no_ads_running"] = False
        self.assertEqual(self.verify("enabled"), enabled)
        self.current = dict(deepcopy(self.reference), captured_at_utc=CAPTURED)
        self.children["ad_groups"][0]["explicit_status"] = "Paused"
        rollback = self.verify("rollback")

        for result, states in ((staged, ("Paused", "Enabled")), (enabled, ("Enabled", "Enabled")),
                               (rollback, ("Paused", "Paused"))):
            self.assertEqual(result["status"], "MATCHED_UAE_ACTIVATION_SCOPE")
            self.assertIs(result["scope_match"], True)
            self.assertIs(result["launch_authorized"], False)
            self.assertEqual((result["campaign_state"], result["offplan_ad_group_state"]), states)
            self.assertEqual(result["resale_ad_group_state"], "Paused")
            self.assertEqual(result["campaigns_compared"], 24)

    def test_rejects_extra_or_unexpected_child(self):
        rows = self.children["ad_groups"]
        original = deepcopy(rows)
        new = {"campaign_id": PARENT, "ad_group_id": "204397706999", "explicit_status": "Removed"}
        for changed in ([*original, new], [original[0], new], [original[0], dict(original[1], campaign_id=OTHER_CAMPAIGN)]):
            with self.subTest(changed=changed):
                self.children.update(ad_groups=changed, view_total=len(changed))
                with self.assertRaisesRegex(ValueError, "Unexpected or missing UAE child identity"):
                    self.verify()

    def test_rejects_missing_zero_duplicate_or_count_mismatch(self):
        rows = self.children["ad_groups"]
        for changed, total in (([], 0), (rows[:1], 1), ([rows[0], rows[0]], 2), (rows, 3)):
            with self.subTest(changed=changed, total=total):
                self.children.update(ad_groups=changed, view_total=total)
                with self.assertRaisesRegex(ValueError, "ad-group rows|UAE child identity"):
                    self.verify()

    def test_rejects_resale_or_offplan_state_drift(self):
        self.children["ad_groups"][1]["explicit_status"] = "Enabled"
        with self.assertRaisesRegex(ValueError, "Resale child must be explicitly paused"):
            self.verify()
        self.children["ad_groups"][1]["explicit_status"] = "Paused"
        with self.assertRaisesRegex(ValueError, "Off-plan child state differs"):
            self.verify("rollback")

    def test_rejects_account_or_legacy_roster_drift(self):
        for capture in (self.current, self.children, self.reference):
            with self.subTest(capture_schema=capture.get("schema")):
                capture["account_id"] = "999-999-9999"
                with self.assertRaisesRegex(ValueError, "Account identity|readback account"):
                    self.verify()
                capture["account_id"] = ACCOUNT
        rows = self.current["campaigns"]
        rows[1]["campaign_state"], rows[-1]["campaign_state"] = "Removed", "Paused"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            self.verify()
        rows[1]["campaign_state"], rows[-1]["campaign_state"] = "Paused", "Removed"
        rows[-1]["campaign_id"] = "9999999999"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            self.verify()

    def test_rejects_enabling_a_different_or_second_campaign(self):
        self.enable_campaign(OTHER_CAMPAIGN)
        with self.assertRaisesRegex(ValueError, "Intended campaign"):
            self.verify("enabled")
        self.enable_campaign(PARENT)
        with self.assertRaisesRegex(ValueError, "state drift"):
            self.verify("enabled")

    def test_rejects_filtered_historical_or_stale_evidence(self):
        self.children["view"]["ad_group_statuses"].remove("Removed")
        with self.assertRaisesRegex(ValueError, "all-status ad-group view"):
            self.verify()
        self.children["view"]["ad_group_statuses"].append("Removed")
        self.children["view"]["other_filters"] = ["Search"]
        with self.assertRaisesRegex(ValueError, "all-status ad-group view"):
            self.verify()
        self.children["view"]["other_filters"] = []
        for capture in (self.children, self.current):
            capture["captured_at_utc"] = self.reference["captured_at_utc"]
            with self.assertRaisesRegex(ValueError, "current verification window"):
                self.verify()
            capture["captured_at_utc"] = CAPTURED
        for schema in ("bsre.offplan.ad-group-inventory.v1", "bsre.offplan.uae-child-readback.v1"):
            self.children["schema"] = schema
            with self.assertRaisesRegex(ValueError, "All-status UAE child readback required"):
                self.verify()
