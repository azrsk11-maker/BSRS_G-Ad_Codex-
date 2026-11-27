"""Synthetic evidence only. These fixtures never contact any provider."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import check_provider_receipt as checker
from check_gtm_publication import OBSERVATION_SCOPE
from test_check_gtm_exports import ACCOUNT_ID, CONTAINER_ID, CONTAINER_PATH, UI, put_json, synthetic_export


class ProviderReceiptTests(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        self.config_path = root / "config.json"
        self.paid_path = root / "paid.json"
        self.export_path = root / "published.json"
        self.observation_path = root / "observation.json"
        self.original_path = root / "original.json"
        self.excluded_path = root / "excluded.json"
        self.test_event_id = "synthetic-delivery-test-event"
        excluded_hash = put_json(self.excluded_path, {
            "status": "ACCEPTED", "optional_purposes_denied": True, "measurement_eligible": False,
            "browser_conversion_code_executed": False, "event_id": self.test_event_id,
        })
        self.enterContext(patch.object(checker, "TEST_CAPTURE_SHA256", excluded_hash))
        scope = checker.reviewed_scope()
        identity = {"account_id": ACCOUNT_ID, "container_id": CONTAINER_ID, "public_id": "GTM-NW8WXKRF"}
        original_hash = put_json(self.original_path, {
            **identity, "scope": "OFFPLAN_GTM_NATIVE_EXPORT_CAPTURE", "live_version_id": "1",
            "draft_workspace_id": "2", "live_export_sha256": "a" * 64,
            "draft_export_sha256": "b" * 64, "candidate_zip_sha256": "c" * 64,
        })
        self.enterContext(patch.object(checker, "GTM_CAPTURE_SHA256", original_hash))
        self.export = synthetic_export(draft=True)
        version_path = f"{CONTAINER_PATH}/versions/2"
        self.export["containerVersion"].update({
            "containerVersionId": "2", "path": version_path,
            "tagManagerUrl": f"{UI}/versions/{version_path}?apiLink=version", "name": "Synthetic bootstrap",
        })
        self.observation = {
            **identity, "scope": OBSERVATION_SCOPE, "observed_at_utc": "2020-01-01T00:02:00Z",
            "live_version_id": "2",
        }
        self.config = {
            "schema": checker.CONFIG_SCHEMA,
            "wordpress": {"provenance": "AUTHENTICATED_HOST_AND_WORDPRESS_READBACK",
                          "observed_at_utc": "2020-01-01T00:00:00Z", "source_evidence_sha256": "1" * 64,
                          "url": scope["url"], "page_id": checker.PAGE_ID,
                          "archive_sha256": checker.FORWARD_SHA256, "advertising_enabled": True},
            "ads": {"provenance": "AUTHENTICATED_GOOGLE_ADS_CONFIGURATION",
                    "observed_at_utc": "2020-01-01T00:01:00Z", "source_evidence_sha256": "2" * 64,
                    "account": scope["account"], "action_id": scope["action_id"], "optimization": "SECONDARY",
                    "count": "ONE", "fallback_aed": 0, "duplicate_ga4_import": False,
                    "destination_sha256": checker.DESTINATION_SHA256, "auto_tagging": True,
                    "website_source": True, "account_level_goal": False},
            "gtm": {"provenance": "AUTHENTICATED_GTM_VERSIONS_READBACK",
                    "observed_at_utc": self.observation["observed_at_utc"]},
        }
        self.paid = {
            "schema": checker.PAID_SCHEMA,
            "paid_click": {"provenance": "AUTHENTICATED_GOOGLE_ADS_PAID_CLICK_READBACK",
                           "observed_at_utc": "2020-01-01T00:03:00Z", "source_evidence_sha256": "3" * 64,
                           **{key: scope[key] for key in ("account", "campaign_id", "ad_group_id", "ad_id", "url")},
                           "clicked_at_utc": "2020-01-01T00:03:00Z", "click_id_kind": "gclid", "click_id_sha256": "4" * 64},
            "receipt": {"provenance": "VERIFIED_SIGNED_INTAKE_RECEIPT", "observed_at_utc": "2020-01-01T00:04:00Z",
                        "source_evidence_sha256": "5" * 64, "url": scope["url"], "page_id": checker.PAGE_ID,
                        "archive_sha256": checker.FORWARD_SHA256, "click_id_kind": "gclid", "click_id_sha256": "4" * 64,
                        "transaction_id_sha256": "6" * 64, "accepted_at_utc": "2020-01-01T00:04:00Z",
                        "record_kind": "GENUINE_ENQUIRY", "measurement_eligible": True, "replayed": False},
            "provider": {"provenance": "AUTHENTICATED_GOOGLE_ADS_ATTRIBUTION_AND_DEDUPLICATION",
                         "observed_at_utc": "2020-01-01T00:05:00Z", "source_evidence_sha256": "7" * 64,
                         "account": scope["account"], "action_id": scope["action_id"],
                         "destination_sha256": checker.DESTINATION_SHA256, "live_gtm_version": "2",
                         "click_id_kind": "gclid", "click_id_sha256": "4" * 64, "transaction_id_sha256": "6" * 64,
                         "conversion_at_utc": "2020-01-01T00:04:01Z",
                         "producer": "NATIVE_WEBSITE_ACTION", "attributed_count": 1, "duplicate_count": 0},
        }

    def review(self, *, config=None, paid=None, with_paid=True, bad_paid_pin=False, with_exclusion=True):
        config = deepcopy(self.config if config is None else config)
        self.observation["live_export_sha256"] = put_json(self.export_path, self.export)
        config["gtm"]["source_evidence_sha256"] = put_json(self.observation_path, self.observation)
        config_hash = put_json(self.config_path, config)
        paid_args = {}
        if with_paid:
            paid = deepcopy(self.paid if paid is None else paid)
            paid.setdefault("configuration_sha256", config_hash)
            paid_hash = put_json(self.paid_path, paid)
            paid_args = {"paid_receipt": self.paid_path, "paid_sha256": "f" * 64 if bad_paid_pin else paid_hash}
        return checker.review(self.config_path, config_hash, gtm_export=self.export_path,
                              gtm_observation=self.observation_path, gtm_capture=self.original_path,
                              excluded_test_capture=self.excluded_path if with_exclusion else None, **paid_args)

    def assert_held(self, result, *, configured=False):
        self.assertEqual(result["status"], "HOLD")
        self.assertIs(result["configuration_evidence_matched"], configured)
        self.assertFalse(result["paid_attribution_evidence_matched"])
        self.assertFalse(result["launch_ready"])
        self.assertFalse(result["activation_authorized"])

    def test_configuration_alone_is_held(self):
        result = self.review(with_paid=False)
        self.assert_held(result, configured=True)
        self.assertEqual(result["configuration_sha256"], sha256(self.config_path.read_bytes()).hexdigest())
        self.assertNotIn("paid_sha256", result)

    def test_full_evidence_joins_without_allowing_activation(self):
        result = self.review()
        self.assertEqual(result["status"], "MATCHED_GENUINE_PAID_RECEIPT_EVIDENCE")
        self.assertTrue(result["configuration_evidence_matched"])
        self.assertTrue(result["paid_attribution_evidence_matched"])
        for key in ("provider_independently_checked", "launch_ready", "activation_authorized"):
            self.assertFalse(result[key])
        self.assertEqual({key for key in result if key.endswith("sha256")}, {"configuration_sha256", "paid_sha256"})
        self.assertEqual(result["configuration_sha256"], sha256(self.config_path.read_bytes()).hexdigest())
        self.assertEqual(result["paid_sha256"], sha256(self.paid_path.read_bytes()).hexdigest())

    def test_provider_records_can_be_reviewed_after_the_event(self):
        self.paid["paid_click"]["observed_at_utc"] = "2020-01-02T00:00:00Z"
        self.paid["receipt"]["observed_at_utc"] = "2020-01-02T00:00:00Z"
        self.paid["paid_click"]["source_evidence_sha256"] = self.paid["provider"]["source_evidence_sha256"]
        self.assertTrue(self.review()["paid_attribution_evidence_matched"])

    def test_aggregate_report_cannot_supply_a_transaction_row(self):
        self.paid["provider"]["provenance"] = checker.AGGREGATE_PROVENANCE
        result = self.review()
        self.assert_held(result, configured=True)
        self.assertEqual(result["reason"], checker.AGGREGATE_HOLD)
        self.assertNotIn("paid_sha256", result)

    def test_pinned_aggregate_scope_is_recognized_as_hold_only(self):
        aggregate = {
            "schema": checker.AGGREGATE_SCHEMA,
            "aggregate": {**{key: self.paid["provider"][key] for key in
                             ("account", "action_id", "observed_at_utc", "source_evidence_sha256")},
                          "provenance": checker.AGGREGATE_PROVENANCE},
        }
        result = self.review(paid=aggregate, with_exclusion=False)
        self.assert_held(result, configured=True)
        self.assertFalse(result["provider_independently_checked"])
        self.assertEqual(result["reason"], checker.AGGREGATE_HOLD)
        self.assertEqual(result["aggregate_report_projection_sha256"], sha256(self.paid_path.read_bytes()).hexdigest())
        self.assertNotIn("paid_sha256", result)
        for field, invalid in (("action_id", "7859602954"), ("transaction_id_sha256", "a" * 64)):
            with self.subTest(field=field):
                modified = aggregate | {"aggregate": aggregate["aggregate"] | {field: invalid}}
                result = self.review(paid=modified)
                self.assert_held(result, configured=True)
                self.assertNotIn("aggregate_report_projection_sha256", result)
        self.assertNotIn("aggregate_report_projection_sha256", self.review(paid=aggregate, bad_paid_pin=True))

    def test_dated_r5_schema_and_invalid_pins_stay_held(self):
        pin = put_json(self.config_path, {"schema": "bsre.private.offplan-current-release-preflight.v5", "status": "HOLD"})
        self.assert_held(checker.review(self.config_path, pin))
        self.assert_held(checker.review(self.config_path, "e" * 64))
        self.assert_held(self.review(bad_paid_pin=True), configured=True)

    def test_wrong_hosted_or_ads_configuration_is_held(self):
        for section, field, invalid in (
            ("wordpress", "archive_sha256", "b" * 64), ("wordpress", "page_id", 99999),
            ("wordpress", "advertising_enabled", False), ("ads", "account", "000-000-0000"),
            ("ads", "action_id", "7859602954"), ("ads", "duplicate_ga4_import", True),
            ("ads", "destination_sha256", "e" * 64), ("gtm", "observed_at_utc", "2020-01-01T00:02:01Z"),
        ):
            with self.subTest(section=section, field=field):
                config = deepcopy(self.config)
                config[section][field] = invalid
                self.assert_held(self.review(config=config))

    def test_empty_live_gtm_export_is_held(self):
        self.export = synthetic_export(draft=False)
        self.observation["live_version_id"] = "1"
        self.assert_held(self.review())

    def test_retained_delivery_test_is_held_even_if_relabelled(self):
        excluded = sha256(self.test_event_id.encode("utf-8")).hexdigest()
        self.paid["receipt"]["transaction_id_sha256"] = excluded
        self.paid["provider"]["transaction_id_sha256"] = excluded
        self.assertEqual(self.review()["reason"], "The approved delivery TEST is excluded")
        self.assert_held(self.review(with_exclusion=False), configured=True)
        put_json(self.excluded_path, {"event_id": "wrong"})
        self.assert_held(self.review(), configured=True)

    def test_ineligible_tests_replays_and_other_scopes_are_held(self):
        for section, field, invalid in (
            ("receipt", "record_kind", "TEST"), ("receipt", "replayed", True),
            ("receipt", "measurement_eligible", False), ("receipt", "url", "https://other.example/"),
            ("paid_click", "ad_group_id", "204397706314"), ("paid_click", "ad_id", "1"),
            ("provider", "action_id", "7859602954"), ("provider", "account", "000-000-0000"),
            ("provider", "producer", "GA4_IMPORT"), ("provider", "live_gtm_version", "3"),
        ):
            with self.subTest(section=section, field=field):
                paid = deepcopy(self.paid)
                paid[section][field] = invalid
                self.assert_held(self.review(paid=paid), configured=True)

    def test_missing_links_provenance_chronology_or_deduplication_are_held(self):
        for section, field, invalid in (
            ("provider", "duplicate_count", 1), ("provider", "attributed_count", True),
            ("provider", "transaction_id_sha256", "8" * 64), ("provider", "click_id_sha256", "8" * 64),
            ("provider", "click_id_kind", "gbraid"), ("provider", "conversion_at_utc", "2020-01-01T00:03:00Z"),
            ("paid_click", "clicked_at_utc", "2020-01-01T00:01:00Z"),
            ("receipt", "accepted_at_utc", "2020-01-01T00:02:00Z"),
            ("provider", "observed_at_utc", "2999-01-01T00:01:00Z"),
            ("provider", "observed_at_utc", "2020-01-01T00:01:00Z"),
            ("provider", "observed_at_utc", "2020-01-01"), ("provider", "provenance", "LOCAL_STUB"),
            ("provider", "source_evidence_sha256", self.paid["receipt"]["source_evidence_sha256"]),
        ):
            with self.subTest(section=section, field=field):
                paid = deepcopy(self.paid)
                paid[section][field] = invalid
                self.assert_held(self.review(paid=paid), configured=True)
        self.assert_held(self.review(paid=self.paid | {"configuration_sha256": "e" * 64}), configured=True)
