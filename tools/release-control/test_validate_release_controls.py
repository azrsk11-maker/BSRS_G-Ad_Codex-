import json, tempfile, unittest
from pathlib import Path
from validate_release_controls import validate

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = ROOT / "config/release_controls.json"

class ReleaseControlTests(unittest.TestCase):
    def test_current_controls_pass(self):
        result = validate(CONTROLS)
        self.assertEqual(result["campaigns"], 4)
        self.assertFalse(result["activation_authorized"])

    def test_budget_drift_fails_closed(self):
        data = json.loads(CONTROLS.read_text(encoding="utf-8"))
        data["campaigns"][0]["average_daily_budget"] = 1300
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as f:
            json.dump(data, f); path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                validate(path)
        finally:
            path.unlink(missing_ok=True)

    def test_expansion_toggle_fails_closed(self):
        data = json.loads(CONTROLS.read_text(encoding="utf-8"))
        data["targeting"]["ai_max"] = True
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as f:
            json.dump(data, f); path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                validate(path)
        finally:
            path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
