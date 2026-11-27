"""Offline regressions with synthetic provider exports and a synthetic package."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import check_gtm_exports as verifier


ACCOUNT_ID = "1000000000"
CONTAINER_ID = "200000000"
CONTAINER_PATH = f"accounts/{ACCOUNT_ID}/containers/{CONTAINER_ID}"
UI = "https://tagmanager.google.com/#"
IDENTITY = {"accountId": ACCOUNT_ID, "containerId": CONTAINER_ID}
BUILT_INS = [
    {**IDENTITY, "type": key, "name": name}
    for key, name in [
        ("PAGE_URL", "Page URL"), ("PAGE_HOSTNAME", "Page Hostname"), ("PAGE_PATH", "Page Path"),
        ("REFERRER", "Referrer"), ("EVENT", "Event"),
    ]
]


def synthetic_export(*, draft):
    version_id = "0" if draft else "1"
    version_path = f"{CONTAINER_PATH}/versions/{version_id}"
    version = {
        **IDENTITY,
        "containerVersionId": version_id,
        "path": version_path,
        "tagManagerUrl": f"{UI}/versions/{version_path}?apiLink=version",
        "fingerprint": "101",
        "container": {
            **IDENTITY,
            "path": CONTAINER_PATH,
            "tagManagerUrl": f"{UI}/container/{CONTAINER_PATH}/workspaces?apiLink=container",
            "publicId": "GTM-NW8WXKRF",
            "tagIds": ["GTM-NW8WXKRF"],
            "name": "BSRE Owned Funnels | blackswanrealestate.ae",
            "fingerprint": "100",
            "usageContext": ["WEB"],
            "features": dict(verifier.FEATURES),
        },
        "builtInVariable": deepcopy(BUILT_INS),
    }
    if draft:
        version.update({
            "tag": [{
                **IDENTITY,
                "tagId": "4",
                "type": "html",
                "name": "BSRE | Reviewed local runtime bootstrap",
                "fingerprint": "102",
                "parameter": [
                    {
                        "key": "html", "type": "TEMPLATE",
                        "value": (
                            "<script>\n"
                            "if (window.BSREGoogleRuntime && typeof window.BSREGoogleRuntime.activate === 'function') {\n"
                            "  window.BSREGoogleRuntime.activate();\n"
                            "}\n"
                            "</script>\n"
                        ),
                    },
                    {"key": "supportDocumentWrite", "type": "BOOLEAN", "value": "false"},
                ],
                "firingTriggerId": ["3"],
                "tagFiringOption": "ONCE_PER_LOAD",
                "consentSettings": {"consentStatus": "NOT_NEEDED"},
            }],
            "trigger": [{
                **IDENTITY,
                "triggerId": "3",
                "type": "PAGEVIEW",
                "name": "BSRE | Runtime pageview",
                "fingerprint": "103",
            }],
        })
    else:
        version["name"] = "Empty Container"
    return {
        "exportFormatVersion": 2,
        "exportTime": "2000-01-01 00:00:00",
        "containerVersion": version,
    }


def put_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8", newline="\n")
    return sha256(path.read_bytes()).hexdigest()


class ExportVerificationTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.root = Path(directory)
        self.live_path = self.root / "live.json"
        self.draft_path = self.root / "draft.json"
        self.checkpoint = self.root / "capture.json"
        self.candidate = self.root / "candidate.zip"
        self.candidate.write_bytes(b"synthetic package bytes")
        candidate_sha = sha256(self.candidate.read_bytes()).hexdigest()
        self.enterContext(patch.object(verifier, "CANDIDATE_SHA256", candidate_sha))
        self.capture = {
            "scope": "OFFPLAN_GTM_NATIVE_EXPORT_CAPTURE",
            "account_id": ACCOUNT_ID,
            "container_id": CONTAINER_ID,
            "public_id": "GTM-NW8WXKRF",
            "live_version_id": "1",
            "draft_workspace_id": "2",
            "candidate_zip_sha256": candidate_sha,
        }
        self.live = synthetic_export(draft=False)
        self.draft = synthetic_export(draft=True)
        self.write_bound_files()

    def write_bound_files(self):
        self.capture["live_export_sha256"] = put_json(self.live_path, self.live)
        self.capture["draft_export_sha256"] = put_json(self.draft_path, self.draft)
        self.checkpoint_sha = put_json(self.checkpoint, self.capture)

    def verify(self):
        return verifier.verify_exports(
            self.live_path, self.draft_path, self.candidate, self.checkpoint, self.checkpoint_sha.upper(),
        )

    def assert_bound_failure(self, message):
        self.write_bound_files()
        with self.assertRaisesRegex(verifier.VerificationError, message):
            self.verify()

    def test_exact_pair_returns_sanitized_receipt(self):
        self.draft["containerVersion"]["builtInVariable"].reverse()
        self.draft["containerVersion"]["tag"][0]["parameter"].reverse()
        self.write_bound_files()
        result = self.verify()
        self.assertEqual(result["status"], "OFFLINE_EXPORT_CONTENT_VERIFIED")
        self.assertEqual(result["rollback"], {
            "tags": 0, "triggers": 0, "built_in_variables": 5, "sha256": self.capture["live_export_sha256"],
        })
        self.assertEqual(result["draft"], {
            "tags": 1, "triggers": 1, "built_in_variables": 5, "sha256": self.capture["draft_export_sha256"],
        })
        self.assertEqual(result["candidate_zip_sha256"], self.capture["candidate_zip_sha256"])
        self.assertEqual(result["checkpoint_sha256"], self.checkpoint_sha)
        self.assertFalse(result["provider_state_checked_here"])
        self.assertFalse(result["publication_authorized"])
        for value in (ACCOUNT_ID, CONTAINER_ID, "activate", "accountId", "containerId"):
            self.assertNotIn(value, json.dumps(result))

    def test_unpinned_capture_change_fails(self):
        self.checkpoint.write_bytes(self.checkpoint.read_bytes() + b"\n")
        with self.assertRaisesRegex(verifier.VerificationError, "capture checkpoint SHA-256 mismatch"):
            self.verify()

    def test_unpinned_export_change_fails(self):
        self.draft_path.write_bytes(self.draft_path.read_bytes() + b"\n")
        with self.assertRaisesRegex(verifier.VerificationError, "native export SHA-256 mismatch"):
            self.verify()

    def test_changed_candidate_fails_even_if_checkpoint_rebound(self):
        self.candidate.write_bytes(b"alternate synthetic package bytes")
        self.capture["candidate_zip_sha256"] = sha256(self.candidate.read_bytes()).hexdigest()
        self.assert_bound_failure("candidate ZIP SHA-256 mismatch")

    def test_capture_workspace_must_match_observed_workspace(self):
        self.capture["draft_workspace_id"] = "3"
        self.assert_bound_failure("unexpected capture checkpoint")

    def test_provider_workspace_export_cannot_substitute_for_live_version(self):
        self.live["containerVersion"]["containerVersionId"] = "0"
        self.assert_bound_failure("unexpected GTM export version identity")

    def test_references_to_other_containers_fail(self):
        self.draft["containerVersion"]["tag"][0]["containerId"] = "300000000"
        self.assert_bound_failure("GTM account or container mismatch")

    def test_rollback_extra_tag_fails(self):
        self.live["containerVersion"]["tag"] = deepcopy(self.draft["containerVersion"]["tag"])
        self.assert_bound_failure("rollback contains tags or triggers")

    def test_unknown_fields_fail_closed_even_if_empty(self):
        self.draft["containerVersion"]["unreviewedSettings"] = []
        self.assert_bound_failure("unexpected GTM fields")

    def test_other_actionable_collections_fail(self):
        for key in ("variable", "folder", "zone", "customTemplate", "client", "gtagConfig", "transformation"):
            with self.subTest(key=key):
                self.draft = synthetic_export(draft=True)
                self.draft["containerVersion"][key] = [{"name": "Synthetic object"}]
                self.assert_bound_failure("unexpected GTM objects")

    def test_builtin_mutations_fail(self):
        for key, replacement in [("type", "CLICK_URL"), ("type", "PAGE_PATH"), ("name", "Other hostname")]:
            with self.subTest(key=key, replacement=replacement):
                self.draft = synthetic_export(draft=True)
                self.draft["containerVersion"]["builtInVariable"][1][key] = replacement
                self.assert_bound_failure("unexpected built-in variable")

    def test_trigger_identity_type_or_filter_mutation_fails(self):
        for key, value, error in [
            ("triggerId", "8", "unexpected draft page-view trigger"),
            ("type", "INIT", "unexpected draft page-view trigger"),
            ("filter", [{}], "unexpected GTM fields"),
        ]:
            with self.subTest(key=key):
                self.draft = synthetic_export(draft=True)
                self.draft["containerVersion"]["trigger"][0][key] = value
                self.assert_bound_failure(error)

    def test_tag_firing_options_and_references_fail(self):
        for key, value, error in [
            ("tagId", "5", "unexpected draft bootstrap or firing options"),
            ("type", "gaawc", "unexpected draft bootstrap or firing options"),
            ("firingTriggerId", ["3", "8"], "unexpected draft bootstrap or firing options"),
            ("tagFiringOption", "UNLIMITED", "unexpected draft bootstrap or firing options"),
            ("consentSettings", {"consentStatus": "NOT_SET"}, "unexpected draft bootstrap or firing options"),
            ("setupTag", [{"tagName": "Synthetic tag"}], "unexpected GTM fields"),
        ]:
            with self.subTest(key=key):
                self.draft = synthetic_export(draft=True)
                self.draft["containerVersion"]["tag"][0][key] = value
                self.assert_bound_failure(error)

    def test_guard_and_additional_script_are_rejected(self):
        for source_change in [
            lambda html: html.replace(" && ", " || "),
            lambda html: html.replace("window.BSREGoogleRuntime.activate();", "void 0;"),
            lambda html: html + "<script>void 0;</script>",
        ]:
            with self.subTest(source_change=source_change):
                self.draft = synthetic_export(draft=True)
                parameter = self.draft["containerVersion"]["tag"][0]["parameter"][0]
                parameter["value"] = source_change(parameter["value"])
                self.assert_bound_failure("custom HTML differs")

    def test_document_write_and_duplicate_parameter_are_rejected(self):
        for key, value in [("value", "true"), ("key", "html")]:
            with self.subTest(key=key):
                self.draft = synthetic_export(draft=True)
                self.draft["containerVersion"]["tag"][0]["parameter"][1][key] = value
                self.assert_bound_failure("custom HTML differs")

    def test_duplicate_json_keys_fail_before_comparison(self):
        raw = self.draft_path.read_bytes().replace(b'"exportFormatVersion": 2,',
                                                   b'"exportFormatVersion": 2, "exportFormatVersion": 2,', 1)
        self.draft_path.write_bytes(raw)
        self.capture["draft_export_sha256"] = sha256(raw).hexdigest()
        self.checkpoint_sha = put_json(self.checkpoint, self.capture)
        with self.assertRaisesRegex(verifier.VerificationError, "duplicate JSON object key"):
            self.verify()


if __name__ == "__main__":
    unittest.main()
