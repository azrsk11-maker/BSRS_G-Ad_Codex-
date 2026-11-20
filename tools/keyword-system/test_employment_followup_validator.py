import json
from pathlib import Path
import tempfile
import unittest

import employment_followup_validator as validator


ROOT = Path(__file__).parents[2]
FOLDER = ROOT / "docs/audit/keyword-employment-followup-2026-11-11"


class EmploymentFollowupValidatorTests(unittest.TestCase):
    def test_current_artifacts_pass(self):
        result = validator.validate(FOLDER)
        self.assertEqual(result, {"passed": True, "rows": 444,
                                  "negative_exact_review": 109,
                                  "hold": 335, "admitted": 0, "deployed": 0})

    def test_duplicate_review_row_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            for name in validator.REQUIRED:
                (target / name).write_bytes((FOLDER / name).read_bytes())
            path = target / "semantic-review-preview.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["records"].append(data["records"][0])
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "REVIEW_ROWS_NOT_BOUND"):
                validator.validate(target)


if __name__ == "__main__":
    unittest.main()
