from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from staff_timing import main, summarize, summarize_capacity


class StaffTimingTests(unittest.TestCase):
    def measure(self, *attempts):
        return summarize({
            "as_of_utc": "2026-11-10T07:00:00Z",
            "cases": [
                {"case_key": str(i), "accepted_at_utc": accepted, "first_attempt_at_utc": attempt}
                for i, (accepted, attempt) in enumerate(attempts)
            ],
        })

    def test_capacity_reconciles_daily_and_adjacent_backlog(self):
        days = [
            {"dubai_date": "2026-11-09", "opening_backlog": 4, "arrivals": 7, "completed": 8, "closing_backlog": 3},
            {"dubai_date": "2026-11-10", "opening_backlog": 3, "arrivals": 9, "completed": 6, "closing_backlog": 6},
        ]
        result = summarize_capacity({"days": list(reversed(days))})
        self.assertEqual(result["total_completed"], 14)
        self.assertEqual(result["min_daily_completions_observed"], 6)
        self.assertEqual(result["days_with_backlog_growth"], 1)
        self.assertFalse(result["sample_representativeness_verified"])
        with self.assertRaisesRegex(ValueError, "overnight"):
            summarize_capacity({"days": [days[0], dict(days[1], opening_backlog=4, closing_backlog=7)]})
        with self.assertRaisesRegex(ValueError, "daily"):
            summarize_capacity({"days": [dict(days[0], completed=9)]})
        self.assertEqual(summarize_capacity({"days": [days[0], dict(days[1], dubai_date="2026-11-12")]})["sample_date_gaps"], 1)

    def test_capacity_rejects_duplicate_dates_and_boolean_counts(self):
        day = {"dubai_date": "2026-11-09", "opening_backlog": 0, "arrivals": 1, "completed": 1, "closing_backlog": 0}
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarize_capacity({"days": [day, day]})
        with self.assertRaisesRegex(ValueError, "capacity count"):
            summarize_capacity({"days": [dict(day, completed=True)]})

    def test_shift_boundary_ignores_overnight_hours(self):
        result = self.measure(("2026-11-09T14:50:00Z", "2026-11-10T06:20:00Z"))
        self.assertEqual(result["peak_first_contact_max_seconds"], 1800)
        self.assertTrue(result["within_target_for_supplied_sample"])

    def test_late_and_missing_cases_remain_separate(self):
        result = self.measure(("2026-11-10T06:00:00Z", "2026-11-10T06:30:01Z"),
                              ("2026-11-10T06:10:00Z", None),
                              ("2026-11-10T06:50:00Z", None))
        self.assertEqual(result["peak_first_contact_sample_count"], 1)
        self.assertEqual(result["missing_first_attempt_count"], 2)
        self.assertEqual(result["late_first_attempt_count"], 2)
        self.assertFalse(result["within_target_for_supplied_sample"])

    def test_rejects_attempt_before_acceptance(self):
        with self.assertRaisesRegex(ValueError, "Invalid event order"):
            self.measure(("2026-11-10T06:10:00Z", "2026-11-10T06:00:00Z"))

    def test_cli_rejects_duplicate_timestamp_without_disclosing_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "private-timing.json"
            path.write_text(
                '{"as_of_utc":"2026-11-10T07:00:00Z","cases":[{"case_key":"private-case",'
                '"accepted_at_utc":"2026-11-10T06:00:00Z","first_attempt_at_utc":null,'
                '"first_attempt_at_utc":"2026-11-10T06:10:00Z"}]}',
                encoding="utf-8",
            )
            output = io.StringIO()
            with patch("sys.argv", ["staff_timing.py", str(path)]), redirect_stdout(output):
                self.assertEqual(main(), 2)
            self.assertEqual(output.getvalue().strip(), '{"error": "INVALID_PRIVATE_TIMING_EVIDENCE"}')
