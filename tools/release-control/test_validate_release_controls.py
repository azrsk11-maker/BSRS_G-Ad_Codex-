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

    def assert_invalid_json(self, content):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as stream:
            stream.write(content)
            path = Path(stream.name)
        try:
            with self.assertRaises(ValueError):
                validate(path)
        finally:
            path.unlink(missing_ok=True)

    def test_boolean_integer_float_substitutions_fail_closed(self):
        mutations = [
            lambda value: value.update(schema_version=True),
            lambda value: value.update(schema_version=1.0),
            lambda value: value.update(aggregate_average_daily_budget=2000.0),
            lambda value: value["campaigns"][0].update(average_daily_budget=1200.0),
            lambda value: value["targeting"].update(ai_max=0),
            lambda value: value["targeting"].update(search_partners=0),
            lambda value: value["bidding"].update(positive_bid_adjustments_percent=False),
            lambda value: value["bidding"].update(service_campaign_cpc_limit_aed=20.0),
        ]
        for number, mutate in enumerate(mutations):
            with self.subTest(number=number):
                value = json.loads(CONTROLS.read_text(encoding="utf-8"))
                mutate(value)
                self.assert_invalid_json(json.dumps(value))

    def test_duplicate_keys_rejected_at_root_and_nested_levels(self):
        source = json.dumps(json.loads(CONTROLS.read_text(encoding="utf-8")))
        self.assert_invalid_json(source.replace('"schema_version": 1', '"schema_version": true, "schema_version": 1', 1))
        self.assert_invalid_json(source.replace('"ai_max": false', '"ai_max": true, "ai_max": false', 1))

    def test_nonfinite_values_and_nonobject_documents_fail_closed(self):
        source = json.dumps(json.loads(CONTROLS.read_text(encoding="utf-8")))
        for value in ("NaN", "Infinity", "-Infinity", "1e999"):
            self.assert_invalid_json(source[:-1] + ', "unrecognized": ' + value + '}')
        for value in ([], None, True, 1):
            self.assert_invalid_json(json.dumps(value))

    def test_valid_object_key_reordering_preserves_held_result(self):
        value = json.loads(CONTROLS.read_text(encoding="utf-8"))
        value["targeting"] = dict(reversed(list(value["targeting"].items())))
        value["bidding"] = dict(reversed(list(value["bidding"].items())))
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", encoding="utf-8", delete=False) as stream:
            json.dump(value, stream)
            path = Path(stream.name)
        try:
            self.assertEqual(validate(path), {"passed": True, "campaigns": 4,
                "aggregate_average_daily_budget": 2000, "activation_authorized": False})
        finally:
            path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
