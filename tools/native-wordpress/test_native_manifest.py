import copy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compile_native_manifest import compile_manifest, main


class NativeManifestTests(unittest.TestCase):
    def setUp(self):
        self.allocation = {"page_target": 360, "families": [{"code": "DEV", "pages": 360}]}
        self.registry = [{"campaign_key": f"BSRE-C{i:04d}", "landing_page_id": f"BSRE-LP{i:04d}",
                          "proposed_path": f"/lp/bsre-c{i:04d}/", "family_code": "DEV",
                          "actual_url": None, "google_campaign_id": None, "page_version": None,
                          "cms_content_or_native_route_id": None, "budget_approved": False,
                          "release_approved": False, "website_scope": "EXISTING_MAIN_SITE_NATIVE_PAGE",
                          "visibility": "UNLISTED_NOINDEX_PUBLIC_URL", "status": "PLANNED_SOURCE_REQUIRED"}
                         for i in range(1, 361)]

    def test_preserves_all_identities_without_generating_content_or_urls(self):
        result = compile_manifest(self.registry, self.allocation)
        self.assertEqual(360, result["page_count"])
        self.assertEqual([r["campaign_key"] for r in self.registry],
                         [r["campaign_key"] for r in result["pages"]])
        self.assertFalse(result["native_policy"]["apply_supported"])
        self.assertTrue(all(r["actual_url"] is None and r["cms_page_id"] is None for r in result["pages"]))
        self.assertNotIn("post_content", str(result))

    def test_missing_slot_rejected(self):
        with self.assertRaises(ValueError):
            compile_manifest(self.registry[:-1], self.allocation)

    def test_duplicate_campaign_and_page_rejected(self):
        for field in ("campaign_key", "landing_page_id"):
            registry = copy.deepcopy(self.registry)
            registry[1][field] = registry[0][field]
            with self.assertRaises(ValueError):
                compile_manifest(registry, self.allocation)

    def test_unsafe_or_changed_route_rejected(self):
        for path in ("https://other.invalid/page", "/lp/../admin/", "/lp/%2e%2e/", "/another-slug/"):
            self.registry[0]["proposed_path"] = path
            with self.assertRaises(ValueError):
                compile_manifest(self.registry, self.allocation)

    def test_family_mismatch_rejected(self):
        self.registry[0]["family_code"] = "RNT"
        with self.assertRaises(ValueError):
            compile_manifest(self.registry, self.allocation)

    def test_existing_or_approved_state_requires_reconciliation(self):
        for field, value in (("actual_url", "https://blackswanrealestate.ae/existing/"),
                             ("cms_content_or_native_route_id", 100), ("google_campaign_id", "123"),
                             ("release_approved", True), ("budget_approved", True),
                             ("website_scope", "STANDALONE")):
            registry = copy.deepcopy(self.registry)
            registry[0][field] = value
            with self.assertRaises(ValueError):
                compile_manifest(registry, self.allocation)

    def test_digest_stable_and_source_not_mutated(self):
        before = copy.deepcopy(self.registry)
        a = compile_manifest(self.registry, self.allocation)
        b = compile_manifest(self.registry, self.allocation)
        self.assertEqual(a, b)
        self.assertEqual(before, self.registry)

    def test_cli_cannot_overwrite_authoritative_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "registry.json"
            allocation = Path(folder) / "allocation.json"
            registry.write_text(json.dumps(self.registry), encoding="utf-8")
            allocation.write_text(json.dumps(self.allocation), encoding="utf-8")
            originals = [registry.read_bytes(), allocation.read_bytes()]
            for output in (registry, allocation):
                with patch("sys.argv", ["compiler", "--registry", str(registry), "--allocation",
                                         str(allocation), "--output", str(output)]), redirect_stdout(io.StringIO()):
                    self.assertEqual(2, main())
                self.assertEqual(originals, [registry.read_bytes(), allocation.read_bytes()])


if __name__ == "__main__":
    unittest.main()
