import unittest

from staff_timing import summarize


class StaffTimingTests(unittest.TestCase):
    def measure(self, *attempts):
        return summarize({
            "as_of_utc": "2026-11-10T07:00:00Z",
            "cases": [
                {"case_key": str(i), "accepted_at_utc": accepted, "first_attempt_at_utc": attempt}
                for i, (accepted, attempt) in enumerate(attempts)
            ],
        })

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
