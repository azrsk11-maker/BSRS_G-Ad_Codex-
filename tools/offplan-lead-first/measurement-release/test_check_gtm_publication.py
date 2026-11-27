from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from check_gtm_exports import VerificationError
from check_gtm_publication import OBSERVATION_SCOPE, verify_publication
from test_check_gtm_exports import ACCOUNT_ID, CONTAINER_ID, CONTAINER_PATH, UI, put_json, synthetic_export


class PublishedBootstrapTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        root = Path(directory)
        self.export_path = root / "version.json"
        self.live_observation = root / "live-observation.json"
        self.original_capture = root / "original-capture.json"
        self.identity = {"account_id": ACCOUNT_ID, "container_id": CONTAINER_ID, "public_id": "GTM-NW8WXKRF"}
        self.original_sha256 = put_json(self.original_capture, {
            **self.identity, "scope": "OFFPLAN_GTM_NATIVE_EXPORT_CAPTURE",
            "live_version_id": "1", "draft_workspace_id": "2", "live_export_sha256": "a" * 64,
            "draft_export_sha256": "b" * 64, "candidate_zip_sha256": "c" * 64,
        })
        self.observation = {
            **self.identity, "scope": OBSERVATION_SCOPE, "observed_at_utc": "2000-01-01T00:01:00Z",
            "live_version_id": "2",
        }
        self.export = synthetic_export(draft=True)
        version_path = f"{CONTAINER_PATH}/versions/2"
        self.export["containerVersion"].update({
            "containerVersionId": "2", "path": version_path,
            "tagManagerUrl": f"{UI}/versions/{version_path}?apiLink=version", "name": "Reviewed bootstrap",
        })

    def reconcile(self):
        self.observation["live_export_sha256"] = put_json(self.export_path, self.export)
        self.observation_hash = put_json(self.live_observation, self.observation)
        return self.verify()

    def verify(self):
        return verify_publication(self.export_path, self.live_observation, self.observation_hash,
                                  self.original_capture, self.original_sha256)

    def test_published_match_is_configuration_evidence_only(self):
        result = self.reconcile()
        self.assertEqual(result["status"], "MATCHED_PUBLISHED_BOOTSTRAP_EXPORT")
        self.assertEqual((result["live_version_id"], result["tags"], result["triggers"]), ("2", 1, 1))
        self.assertFalse(result["provider_live_status_independently_checked"])
        self.assertFalse(result["provider_conversion_verified"])
        self.assertFalse(result["activation_authorized"])

    def test_empty_rollback_cannot_be_published_bootstrap_evidence(self):
        self.export = synthetic_export(draft=False)
        for invalid in ("1", "0", "", None):
            with self.subTest(version=invalid):
                self.observation["live_version_id"] = invalid
                with self.assertRaisesRegex(VerificationError, "version"):
                    self.reconcile()

    def test_draft_or_another_real_version_cannot_match_live_observation(self):
        for version in ("0", "3"):
            with self.subTest(version=version):
                version_path = f"{CONTAINER_PATH}/versions/{version}"
                self.export["containerVersion"].update({
                    "containerVersionId": version, "path": version_path,
                    "tagManagerUrl": f"{UI}/versions/{version_path}?apiLink=version",
                })
                with self.assertRaisesRegex(VerificationError, "version identity"):
                    self.reconcile()

    def test_pinned_but_different_live_container_fails(self):
        self.observation["container_id"] = "999999999"
        with self.assertRaisesRegex(VerificationError, "container identity"):
            self.reconcile()

    def test_edited_export_cannot_replace_pinned_bytes(self):
        self.reconcile()
        self.export["exportTime"] = "2000-01-01 00:02:00"
        put_json(self.export_path, self.export)
        with self.assertRaisesRegex(VerificationError, "live export SHA-256 mismatch"):
            self.verify()

    def test_live_version_must_retain_reviewed_bootstrap(self):
        self.export["containerVersion"]["tag"][0]["parameter"][0]["value"] = "<script>other()</script>"
        with self.assertRaisesRegex(VerificationError, "differs from the guarded reviewed bootstrap"):
            self.reconcile()
