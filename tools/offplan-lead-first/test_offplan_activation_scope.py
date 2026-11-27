"""Exercise cohort stage verification with synthetic readbacks."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

import check_ads_settings_readback as settings
import check_offplan_activation_scope as check
from check_uae_activation_scope import CHILD_SCHEMA as UAE_CHILD_SCHEMA


BASELINE = "2026-11-27 17:40:19 UTC"
WINDOWS = {
    "staged": ("19:00:00", "19:01:00", "19:02:00"),
    "serving": ("19:03:00", "19:04:00", "19:05:00"),
    "rollback": ("19:06:00", "19:07:00", "19:08:00"),
}
USE_MATCHED_STAGE = object()


def utc(time):
    return f"2026-11-27 {time} UTC"


def pin(value):
    return sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


class OffplanActivationScopeTest(TestCase):
    def setUp(self):
        plan, applied = settings.read_plan()
        self.account = plan["account_id"]
        self.resale = plan["resale_ad_group_keep_paused"]
        self.pools = {row["country"]: row for row in applied["campaigns"]}
        self.groups = {country: [str(990000000001 + index)] for index, country in enumerate(self.pools)}
        self.groups["AE"] = [next(m["offplan_ad_group_id"] for m in plan["markets"] if m["country_code"] == "AE")]
        self.groups["DE"].append("990000000010")
        rows = []
        for market in plan["markets"]:
            pool = self.pools[market["country_code"]]
            rows.append({
                "campaign_id": pool["id"], "campaign_name": pool["name"], "campaign_state": "Paused",
                "daily_amount_display": f"AED{pool['average_daily_budget_AED']:,.2f}/day",
                "campaign_type": "Search", "bidding_strategy": "Maximize clicks", "networks": "Google search",
                "location_display": market["country_name"], "positive_bid_adjustment_display": "None",
                **dict.fromkeys(settings.DISABLED, "Off"),
            })
        rows.extend({"campaign_id": str(9000000000 + index), "campaign_state": "Paused" if index < 16 else "Removed"}
                    for index in range(19))
        self.reference = {"capture": settings.FORMAT, "account_id": self.account, "captured_at_utc": BASELINE,
                          "no_ads_running": True, "observed_campaign_states": {"Paused": 21, "Removed": 3},
                          "campaigns": rows}

    def fixture(self, stage, *countries):
        scope = {"schema": check.SCOPE_SCHEMA, "account_id": self.account, "markets": {
            country: {"campaign_id": self.pools[country]["id"], "offplan_ad_group_ids": self.groups[country].copy()}
            for country in countries
        }}
        captured = utc(WINDOWS[stage][1])
        current = dict(deepcopy(self.reference), captured_at_utc=captured)
        enabled = {self.pools[country]["id"] for country in countries} if stage == "serving" else set()
        for row in current["campaigns"]:
            if row["campaign_id"] in enabled:
                row["campaign_state"] = "Enabled"
        current["observed_campaign_states"] = dict(Counter(row["campaign_state"] for row in current["campaigns"]))
        children = {}
        for country in set(countries) | {"AE"}:
            parent_id = self.pools[country]["id"]
            state = "Enabled" if country in countries and stage != "rollback" else "Paused"
            groups = [(group, state) for group in self.groups[country]]
            if country == "AE":
                groups.append((self.resale, "Paused"))
            elif country == "DE":
                groups.append(("990000000020", "Removed"))
            children[country] = {
                "schema": UAE_CHILD_SCHEMA if country == "AE" else check.CHILD_SCHEMA,
                "account_id": self.account, "captured_at_utc": captured, "campaign_or_ad_group_changes": False,
                "view_total": len(groups),
                "view": {"campaign_id": parent_id, "ad_group_statuses": list(check.AD_GROUP_STATUSES), "other_filters": []},
                "ad_groups": [{"campaign_id": parent_id, "ad_group_id": group, "explicit_status": state}
                              for group, state in groups],
            }
        return current, children, scope

    def verify(self, stage, fixture, reference=None, *, prior=USE_MATCHED_STAGE):
        current, children, scope = fixture
        reference = self.reference if reference is None else reference
        if prior is USE_MATCHED_STAGE:
            prior = self.verify("staged", self.fixture("staged", *scope["markets"]), reference) if stage != "staged" else None
        start, _, now = WINDOWS[stage]
        return check.verify(stage, current, children, reference, scope, utc(start), scope_sha256=pin(scope),
                            reference_sha256=pin(reference), prior=prior, now=check.timestamp(utc(now)))

    def test_all_stages_keep_allocations_and_authority(self):
        for stage, budget in (("staged", 0), ("serving", 1350), ("rollback", 0)):
            with self.subTest(stage=stage):
                result = self.verify(stage, self.fixture(stage, "AE", "DE"))
                self.assertEqual(result["status"], "MATCHED_OFFPLAN_ACTIVATION_SCOPE")
                self.assertIs(result["scope_match"], True)
                self.assertIs(result["launch_authorized"], False)
                self.assertIs(result["actual_serving_verified"], False)
                self.assertIs(result["staffed_weekly_schedule_verified"], False)
                self.assertEqual(result["campaigns_compared"], 24)
                self.assertEqual(result["selected_markets"], ["AE", "DE"])
                self.assertEqual(result["uae_resale_ad_group_state"], "Paused")
                self.assertEqual(result["configured_daily_budget_aed"], 2500)
                self.assertEqual(result["enabled_daily_budget_aed"], budget)
        all_markets = self.verify("serving", self.fixture("serving", *self.pools))
        self.assertEqual(all_markets["enabled_daily_budget_aed"], 2500)

    def test_later_windows_require_the_exact_prior_scope_and_reference(self):
        staged = self.verify("staged", self.fixture("staged", "AE", "DE"))
        self.assertEqual(staged["reference_sha256"], pin(self.reference))
        for stage in ("serving", "rollback"):
            with self.subTest(stage=stage):
                fixture = self.fixture(stage, "AE", "DE")
                self.assertEqual(staged["scope_sha256"], pin(fixture[2]))
                with self.assertRaisesRegex(ValueError, "matched prior stage receipt"):
                    self.verify(stage, fixture, prior=None)
                with self.assertRaisesRegex(ValueError, "differs from the prior stage"):
                    self.verify(stage, self.fixture(stage, "AE"), prior=staged)
                with self.assertRaisesRegex(ValueError, "differs from the prior stage"):
                    self.verify(stage, fixture, prior=dict(staged, reference_sha256="f" * 64))
                with self.assertRaisesRegex(ValueError, "must follow the prior stage"):
                    self.verify(stage, fixture, prior=dict(staged, latest_readback_utc=fixture[0]["captured_at_utc"]))
        serving = self.verify("serving", self.fixture("serving", "AE", "DE"), prior=staged)
        rolled_back = self.verify("rollback", self.fixture("rollback", "AE", "DE"), prior=serving)
        self.assertEqual(rolled_back["scope_sha256"], staged["scope_sha256"])
        with self.assertRaisesRegex(ValueError, "matched prior stage receipt"):
            self.verify("serving", self.fixture("serving", "AE", "DE"), prior=rolled_back)

    def test_foreign_only_scope_still_checks_the_uae_groups(self):
        fixture = self.fixture("serving", "TW")
        result = self.verify("serving", fixture)
        self.assertEqual(result["child_readback_markets"], ["AE", "TW"])
        self.assertEqual(result["enabled_daily_budget_aed"], 350)
        children = fixture[1]
        children["AE"]["ad_groups"][1]["explicit_status"] = "Enabled"
        with self.assertRaisesRegex(ValueError, "Resale child must be explicitly paused"):
            self.verify("serving", fixture)
        del children["AE"]
        with self.assertRaisesRegex(ValueError, "Complete child readbacks"):
            self.verify("serving", fixture)

    def test_rejects_unknown_markets_parents_and_child_scope(self):
        for replacement, message in (
            ({}, "nonempty subset"), ({"PK": {}}, "five applied markets"),
            ({"DE": {"campaign_id": self.pools["FR"]["id"], "offplan_ad_group_ids": self.groups["DE"]}}, "parent identity"),
            ({"AE": {"campaign_id": self.pools["AE"]["id"], "offplan_ad_group_ids": [self.resale]}}, "retained off-plan"),
            ({"DE": {"campaign_id": self.pools["DE"]["id"], "offplan_ad_group_ids": [self.resale]}}, "another scope"),
        ):
            with self.subTest(replacement=replacement):
                fixture = self.fixture("staged", "DE")
                fixture[2]["markets"] = replacement
                with self.assertRaisesRegex(ValueError, message):
                    self.verify("staged", fixture)

    def test_rejects_filtered_incomplete_and_wrong_parent_child_rows(self):
        for field, value, message in (("view_total", 4, "Incomplete"),
                                      ("schema", "bsre.offplan.ad-group-inventory.v1", "All-status market"),
                                      ("campaign_or_ad_group_changes", True, "write recorded")):
            with self.subTest(field=field):
                fixture = self.fixture("staged", "DE")
                fixture[1]["DE"][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.verify("staged", fixture)
        fixture = self.fixture("staged", "DE")
        child = fixture[1]["DE"]
        child["view"]["ad_group_statuses"].remove("Removed")
        with self.assertRaisesRegex(ValueError, "all-status ad-group view"):
            self.verify("staged", fixture)
        child["view"]["ad_group_statuses"].append("Removed")
        child["ad_groups"][0]["campaign_id"] = self.pools["FR"]["id"]
        with self.assertRaisesRegex(ValueError, "Invalid ad-group identity or status"):
            self.verify("staged", fixture)
        child["ad_groups"][0]["campaign_id"] = self.pools["DE"]["id"]
        child["ad_groups"][0]["ad_group_id"] = child["ad_groups"][1]["ad_group_id"]
        with self.assertRaisesRegex(ValueError, "duplicate ad-group rows"):
            self.verify("staged", fixture)

    def test_rejects_extra_enabled_children_and_missing_allowlist_rows(self):
        for stage in check.STAGES:
            with self.subTest(stage=stage):
                fixture = self.fixture(stage, "DE")
                capture = fixture[1]["DE"]
                capture["ad_groups"][-1]["explicit_status"] = "Enabled"
                with self.assertRaisesRegex(ValueError, "Unexpected enabled group"):
                    self.verify(stage, fixture)
                capture["ad_groups"][-1]["explicit_status"] = "Removed"
                capture["ad_groups"].pop(0)
                capture["view_total"] -= 1
                with self.assertRaisesRegex(ValueError, "approved off-plan group is missing"):
                    self.verify(stage, fixture)

    def test_rejects_legacy_status_identity_and_unselected_enablement_drift(self):
        fixture = self.fixture("serving", "DE")
        current = fixture[0]
        rows = current["campaigns"]
        rows[-4]["campaign_state"], rows[-1]["campaign_state"] = "Removed", "Paused"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            self.verify("serving", fixture)
        rows[-4]["campaign_state"], rows[-1]["campaign_state"] = "Paused", "Removed"
        rows[-1]["campaign_id"] = "9999999999"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            self.verify("serving", fixture)
        rows[-1]["campaign_id"] = self.reference["campaigns"][-1]["campaign_id"]
        rows[0]["campaign_state"] = "Enabled"
        current["observed_campaign_states"] = {"Paused": 19, "Removed": 3, "Enabled": 2}
        with self.assertRaisesRegex(ValueError, "state drift"):
            self.verify("serving", fixture)
        rows.pop()
        with self.assertRaisesRegex(ValueError, "Incomplete campaign roster"):
            self.verify("serving", fixture)

    def test_rejects_changed_funds_names_or_nonpaused_reference(self):
        fixture = self.fixture("staged", "AE")
        rows = fixture[0]["campaigns"]
        rows[0]["daily_amount_display"], rows[1]["daily_amount_display"] = "AED950.00/day", "AED400.00/day"
        with self.assertRaisesRegex(ValueError, "allocation differs"):
            self.verify("staged", fixture)
        fixture = self.fixture("staged", "AE")
        fixture[0]["campaigns"][1]["campaign_name"] = "Changed"
        with self.assertRaisesRegex(ValueError, "identity or state differs"):
            self.verify("staged", fixture)
        reference = deepcopy(self.reference)
        reference["campaigns"][0]["campaign_state"], reference["campaigns"][-1]["campaign_state"] = "Removed", "Paused"
        with self.assertRaisesRegex(ValueError, "must be paused in the frozen reference"):
            self.verify("staged", self.fixture("staged", "AE"), reference)

    def test_rejects_visible_search_drift_for_selected_markets(self):
        for field, value in (("location_display", "Worldwide"), ("ai_max", "On"),
                             ("networks", "Google search, Search partners")):
            with self.subTest(field=field):
                fixture = self.fixture("serving", "AE", "DE")
                de = next(row for row in fixture[0]["campaigns"] if row["campaign_id"] == self.pools["DE"]["id"])
                de[field] = value
                with self.assertRaisesRegex(ValueError, "DE visible Search settings differ"):
                    self.verify("serving", fixture)

    def test_rejects_stale_future_and_wrong_account_readbacks(self):
        for captured_at in (BASELINE, utc("19:03:00")):
            with self.subTest(captured_at=captured_at):
                fixture = self.fixture("staged", "DE")
                fixture[1]["DE"]["captured_at_utc"] = captured_at
                with self.assertRaisesRegex(ValueError, "within the verification window"):
                    self.verify("staged", fixture)
        fixture = self.fixture("staged", "DE")
        fixture[1]["DE"]["account_id"] = "999-999-9999"
        with self.assertRaisesRegex(ValueError, "Wrong child readback account"):
            self.verify("staged", fixture)

    def test_pinned_inputs_reject_digest_mismatch_and_duplicate_fields(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scope.json"
            body = b'{"schema":"value","schema":"other"}'
            path.write_bytes(body)
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                settings.pinned_capture(path, "0" * 64)
            with self.assertRaisesRegex(ValueError, "Duplicate capture field"):
                settings.pinned_capture(path, sha256(body).hexdigest())
