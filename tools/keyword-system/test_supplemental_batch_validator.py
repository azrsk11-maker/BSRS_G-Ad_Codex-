import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from supplemental_batch_validator import validate

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs/audit/keyword-employment-followup-2026-11-11-batch2"

class SupplementalBatchValidatorTests(unittest.TestCase):
    def test_current_batch_passes(self):
        result = validate(FOLDER)
        self.assertEqual(result["rows"], 444)
        self.assertFalse(result["approved"])

    def test_manifest_hash_tamper_fails_closed(self):
        manifest = json.loads((FOLDER / "capture.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["source_files"]), 1)
        batch_name = manifest["source_files"][0]["file"]
        original_glob = Path.glob
        for first_name in ("semantic-review-preview.json", batch_name):
            def ordered_glob(folder, pattern):
                return iter(sorted(original_glob(folder, pattern),
                    key=lambda path: (path.name != first_name, path.name)))
            with self.subTest(first_file=first_name), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(Path, "glob", ordered_glob):
                target = Path(tmp)
                for source in FOLDER.glob("*.json"):
                    (target / source.name).write_bytes(source.read_bytes())
                # Filesystem enumeration may put the unpinned preview first.
                # The source manifest, rather than directory order, owns this test.
                self.assertEqual(next(p for p in target.glob("*.json")
                    if p.name != "capture.json").name, first_name)
                batch = target / batch_name
                self.assertEqual(batch.parent, target)
                original = batch.read_bytes()
                batch.write_bytes(original + b"\n")
                self.assertEqual(json.loads(batch.read_bytes()), json.loads(original))
                with self.assertRaisesRegex(ValueError, "^BATCH_HASH_BINDING$"):
                    validate(target)

    def test_preview_source_binding_passes(self):
        result = validate(FOLDER)
        self.assertEqual(result["rows"], 444)

if __name__ == "__main__":
    unittest.main()
