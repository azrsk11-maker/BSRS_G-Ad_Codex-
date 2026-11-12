import json, tempfile, unittest
from pathlib import Path
from supplemental_batch_validator import validate

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs/audit/keyword-employment-followup-2026-11-11-batch2"

class SupplementalBatchValidatorTests(unittest.TestCase):
    def test_current_batch_passes(self):
        result = validate(FOLDER)
        self.assertEqual(result["rows"], 444)
        self.assertFalse(result["approved"])

    def test_manifest_hash_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            for source in FOLDER.glob("*.json"):
                (target / source.name).write_bytes(source.read_bytes())
            batch = next(p for p in target.glob("*.json") if p.name != "capture.json")
            data = json.loads(batch.read_text(encoding="utf-8"))
            data["batch_id"] = "tampered"
            batch.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate(target)

    def test_preview_source_binding_passes(self):
        result = validate(FOLDER)
        self.assertEqual(result["rows"], 444)

if __name__ == "__main__":
    unittest.main()
