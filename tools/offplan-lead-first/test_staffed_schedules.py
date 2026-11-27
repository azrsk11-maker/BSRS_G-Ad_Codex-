"""Verify the review-only paused Search schedule workflow."""

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import check_staffed_schedules as check
import test_ads_settings_readback as grid_fixture


class StaffedSchedulesTest(TestCase):
    def setUp(self):
        fixture = grid_fixture.AdsSettingsReadbackTest()
        fixture.setUp()
        self.grid = fixture.capture
        self.reference = deepcopy(self.grid)
        self.grid_pin = "a" * 64
        self.reference_pin = "d" * 64
        self.reference["captured_at_utc"] = "2026-11-26 17:40:19 UTC"
        self.evidence = {"detail_sha256": "e" * 64, "original_source_sha256": "f" * 64,
                         "not_before_utc": "2026-11-27 17:38:00 UTC"}
        self.now = datetime(2026, 11, 27, 17, 44, tzinfo=timezone.utc)
        self.full_week = [{"day": day, "start": "10:00", "end": "19:00", "bid_adjustment_percent": 0}
                          for day in check.DAYS]

    def detail(self):
        return {
            "format": check.DETAIL_FORMAT, "account_id": self.grid["account_id"],
            "account_time_zone": "Asia/Dubai", "settings_sha256": self.grid_pin,
            "readback_sources": dict(check.SOURCES), "original_source_sha256": self.evidence["original_source_sha256"],
            "captured_at_utc": "2026-11-27 17:41:00 UTC",
            "campaigns": [{"campaign_id": row["campaign_id"], "schedule": deepcopy(self.full_week)}
                          for row in self.grid["campaigns"][:5]],
        }

    def report(self, detail=None):
        return check.build(self.grid, self.reference, self.grid_pin, self.reference_pin,
                           detail=detail, evidence=self.evidence if detail else None, now=self.now)

    def test_distinguishes_cached_summary_from_uncovered_hours(self):
        report = self.report()
        finding = {row["country"]: row["state"] for row in report["campaigns"]}
        self.assertEqual(finding, {"AE": "WEEKLY_DETAIL_REQUIRED", "DE": "ALL_DAY_IN_CAPTURE",
                                   "FR": "ALL_DAY_IN_CAPTURE", "IN": "ALL_DAY_IN_CAPTURE",
                                   "TW": "ALL_DAY_IN_CAPTURE"})
        self.assertEqual(report["average_daily_budget_aed"], 2500)
        self.assertFalse(report["launch_authorized"])
        self.assertEqual(report["reviewed_week"], self.full_week)

    def test_exact_independent_week_and_grid_match_remain_review_only(self):
        for row in self.grid["campaigns"][:5]:
            row["schedule_display"] = "All days, 10:00 AM - 7:00 PM"
        details = self.detail()
        details["campaigns"][0]["schedule"].reverse()
        report = self.report(details)
        self.assertEqual({row["state"] for row in report["campaigns"]}, {"EXACT_WEEK_MATCHED"})
        self.assertEqual(report["launch_readiness"], "HOLD")
        self.assertFalse(report["launch_authorized"])
        self.assertEqual(report["reference_sha256"], self.reference_pin)
        self.assertEqual(report["weekly_detail_evidence"],
                         self.evidence | {"captured_at_utc": details["captured_at_utc"]})

    def test_rejects_wrong_account_time_zone_or_capture(self):
        for key, value in (("account_id", "000-000-0000"), ("account_time_zone", "Europe/Berlin"),
                           ("settings_sha256", "b" * 64), ("readback_sources", {}),
                           ("original_source_sha256", "a" * 64)):
            with self.subTest(key=key):
                detail = self.detail()
                detail[key] = value
                with self.assertRaisesRegex(ValueError, "Detail account"):
                    self.report(detail)

    def test_rejects_stale_or_future_details(self):
        for date in ("2026-11-26 17:41:00 UTC", "2026-11-27 17:39:00 UTC", "2026-11-27 17:45:00 UTC"):
            with self.subTest(date=date):
                detail = self.detail()
                detail["captured_at_utc"] = date
                with self.assertRaisesRegex(ValueError, "verification window"):
                    self.report(detail)

    def test_rejects_a_window_preceding_the_frozen_reference(self):
        self.evidence["not_before_utc"] = self.reference["captured_at_utc"]
        with self.assertRaisesRegex(ValueError, "verification window"):
            self.report(self.detail())

    def test_rejects_duplicate_or_unowned_campaign(self):
        for campaign_id in (self.grid["campaigns"][1]["campaign_id"], self.grid["campaigns"][-1]["campaign_id"]):
            with self.subTest(campaign_id=campaign_id):
                detail = self.detail()
                detail["campaigns"][0]["campaign_id"] = campaign_id
                with self.assertRaisesRegex(ValueError, "Detail campaign identity"):
                    self.report(detail)

    def test_holds_empty_missing_or_duplicate_days_or_nonzero_adjustment(self):
        for update in ({}, {"day": "Monday"}, {"start": "09:00"}, {"end": "20:00"}, {"bid_adjustment_percent": 5},
                       {"bid_adjustment_percent": False}):
            with self.subTest(update=update):
                detail = self.detail()
                sunday = detail["campaigns"][0]["schedule"][-1]
                if update:
                    sunday.update(update)
                else:
                    detail["campaigns"][0]["schedule"].pop()
                self.assertEqual(self.report(detail)["campaigns"][0]["state"], "GRID_OR_WEEKLY_DETAIL_DIFFERS")

    def test_holds_detail_conflicting_with_all_day_grid(self):
        report = self.report(self.detail())
        findings = {row["country"]: row["state"] for row in report["campaigns"]}
        self.assertEqual(findings["AE"], "EXACT_WEEK_MATCHED")
        self.assertEqual(set(findings.values()), {"EXACT_WEEK_MATCHED", "GRID_OR_WEEKLY_DETAIL_DIFFERS"})

    def test_rejects_legacy_roster_drift_at_same_counts(self):
        self.grid["campaigns"][-1]["campaign_id"] = "9999999999"
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            self.report()

    def test_cli_rejects_original_readback_byte_drift(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            def save(name, raw):
                path = root / name
                path.write_bytes(raw)
                return [str(path), sha256(raw).hexdigest()]

            grid = save("grid.json", json.dumps(self.grid).encode())
            reference = save("reference.json", json.dumps(self.reference).encode())
            original = save("original.txt", b"synthetic account zone and seven-day review")
            detail = self.detail()
            detail["settings_sha256"] = grid[1]
            detail["original_source_sha256"] = original[1]
            detail_path, detail_pin = save("detail.json", json.dumps(detail).encode())
            args = ["check_staffed_schedules.py", *grid, "--reference", reference[0],
                    "--reference-sha256", reference[1], "--detail", detail_path, "--detail-sha256", detail_pin,
                    "--original-detail", original[0], "--original-detail-sha256", original[1],
                    "--not-before-utc", self.evidence["not_before_utc"]]
            with patch("sys.argv", args), redirect_stdout(StringIO()) as output:
                self.assertEqual(check.main(), 0)
            self.assertEqual(json.loads(output.getvalue())["weekly_detail_evidence"]["detail_sha256"], detail_pin)
            Path(original[0]).write_bytes(b"changed")
            with patch("sys.argv", args), redirect_stdout(StringIO()) as output:
                self.assertEqual(check.main(), 1)
            self.assertIn("SHA-256 mismatch", json.loads(output.getvalue())["reason"])
