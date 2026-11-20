import json, tempfile, unittest
from pathlib import Path
from validate_planning_registry import validate

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs/google-ads/planned_campaign_page_registry.json"

class PlanningRegistryTests(unittest.TestCase):
    def test_current_registry_passes(self):
        self.assertEqual(validate(REGISTRY)["planned_slots"], 360)

    def test_live_binding_fails_closed(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        data[0]["actual_url"] = "https://blackswanrealestate.ae/lp/bsre-c0001/"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as f:
            json.dump(data, f); path = Path(f.name)
        try:
            with self.assertRaises(ValueError):
                validate(path)
        finally:
            path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
