from copy import deepcopy
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import check_offplan_release_evidence as release


def passes(count):
    return {f"check-{index}": True for index in range(count)}


BROWSER = {"status": "PASS", "driver_exit": 0, "package_sha256": release.CANDIDATE_SHA256,
           "manifest_sha256": release.PROFILE_SHA256, "candidate_members": 53, "vendor_transmissions": 0,
           "checks": passes(11)}
EXPORTED = {"status": "PASS", "driver_exit": 0, "archive_sha256": release.CANDIDATE_SHA256,
            "vendor_transmissions": 0,
            "bootstrap_inline_body_sha256": "26bf027b7e03d0897b7450d47e6e07390e5e59e0d66a4f82531d9cb8cb2b33d7",
            "checks": {f"case-{index}": passes(7 if index < 6 else 4) for index in range(7)}}
INSTALLER = {"status": "VERIFIED_LOCAL_0217_NATIVE_UPGRADE_AND_ROLLBACK", "local_only": True,
             "candidate_sha256": release.CANDIDATE_SHA256, "rollback_sha256": release.ROLLBACK_SHA256,
             "manifest_sha256": release.PROFILE_SHA256, "common_rotated_asset_count": 6,
             "production_or_provider_writes": 0, "hostinger_installed_preimage_verified": False}
RETRY = {"status": "PASS", "requests": [{}] * 17, "checks": passes(25), "external_transmissions": 0,
         "synthetic_fixture_removed": True,
         "transport": "WordPress core in-process REST dispatch under pinned PHP CLI, no listening sockets",
         "archives": {"0.2.17": {"sha256": release.CANDIDATE_SHA256, "members": 53},
                      "0.2.12": {"sha256": release.ROLLBACK_SHA256, "members": 30}}}
HTTPS_RETRY = RETRY | {
    "transport": "verified loopback TLS to a guarded PHP built-in web server, native WordPress REST over HTTP",
    "requests": [{"tls": "TLSv1.3"}] * 17, "listener_closed": True, "front_errors": []}
SAVED_SCOPE = {"status": "HOLD", "launch_ready": False, "ads": {
    "account": release.ACCOUNT, "prepared_parent_ids": release.PARENT_IDS, "average_daily_aed": 2500,
    "locally_bound_action": "7873290954", "test_conversion": False}, "test": {
    "one_delivery_reconciled": True, "eligible_for_measurement": False, "replay_requested": False}}
MARKETS = {"status": "HOLD", "account": release.ACCOUNT, "summary": {
    "markets": 5, "prepared_average_daily_aed": 2500, "new_destinations_accepted": 0,
    "operational_coverage_gates_closed": 0, "new_keyword_admissions": 0}}


def chrome_fixture(version="0.2.17", candidate_hash=release.CANDIDATE_SHA256):
    assets, archives = [], []
    for release_version in ("0.2.12", version):
        target = BytesIO()
        with ZipFile(target, "w") as archive:
            for name in release.FORM_ASSETS:
                body = f"Synthetic {release_version} {name}".encode()
                archive.writestr("bsre-enquiries/" + name, body)
                assets.append({"release": release_version, "asset": name, "sha256": release.digest(body)})
        archives.append(target.getvalue())
    requests = [{"method": "POST", "route": "/wp-json/bsre/v1/lead", "release": release_version,
                 "backend_release": release_version, "status": status, "mail_count": "0"} for release_version, status in
                (("0.2.12", 503), (version, 200), (version, 503), ("0.2.12", 200))]
    requests += [requests[0] | {"method": "GET", "route": "/enquire/off-plan/", "status": 200}] * 6
    receipt = {"status": "PASS", "driver_exit": 0, "checks": passes(7), "phases": [{}] * 6,
               "fixture_removed": True, "chrome_stopped": True, "proxy_closed": True, "tls_closed": True,
               "external_transmissions": 0, "network_errors": [], "unserved_local_paths": [],
               "transitions": [{"old_version": "0.2.12", "installed_version": version, "members": 53,
                                "sha256": candidate_hash},
                               {"old_version": version, "installed_version": "0.2.12", "members": 30,
                                "sha256": release.ROLLBACK_SHA256}],
               "assets": assets, "requests": requests}
    return receipt, *archives


class LocalEvidenceTests(unittest.TestCase):
    def test_verified_proofs_keep_their_local_scope(self):
        release.check_local_verification(BROWSER, EXPORTED, INSTALLER, RETRY)

    def test_changed_local_archive_or_vendor_traffic_is_rejected(self):
        for record, message in ((BROWSER | {"package_sha256": "changed"}, "Chrome"),
                                (BROWSER | {"vendor_transmissions": 1}, "Chrome")):
            with self.subTest(record=record), self.assertRaisesRegex(ValueError, message):
                release.check_local_verification(record, EXPORTED, INSTALLER, RETRY)

    def test_exported_inline_body_and_failed_case_are_rejected(self):
        changed_checks = deepcopy(EXPORTED["checks"])
        changed_checks["case-0"]["check-0"] = False
        for record in (EXPORTED | {"bootstrap_inline_body_sha256": "different"},
                       EXPORTED | {"checks": changed_checks}):
            with self.subTest(record=record), self.assertRaisesRegex(ValueError, "bootstrap"):
                release.check_local_verification(BROWSER, record, INSTALLER, RETRY)

    def test_replaced_rollback_and_relabelled_transport_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "rollback"):
            release.check_local_verification(BROWSER, EXPORTED, INSTALLER | {"rollback_sha256": "different"}, RETRY)
        with self.assertRaisesRegex(ValueError, "retry"):
            release.check_local_verification(BROWSER, EXPORTED, INSTALLER, RETRY | {"transport": "hosted HTTP"})

    def test_removed_retry_check_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "retry"):
            release.check_local_verification(BROWSER, EXPORTED, INSTALLER, RETRY | {"checks": passes(24)})

    def test_https_retry_verifies_local_transport_and_cleanup(self):
        release.check_https_retry(HTTPS_RETRY)
        for fields in ({"listener_closed": False}, {"requests": [{"tls": None}] * 17},
                       {"transport": RETRY["transport"]}):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "HTTPS retry"):
                release.check_https_retry(HTTPS_RETRY | fields)

    def test_chrome_retry_binds_both_archive_assets(self):
        receipt, old, new = chrome_fixture()
        release.check_chrome_retry(receipt, old, new)
        with self.assertRaisesRegex(ValueError, "assets"):
            release.check_chrome_retry(receipt, old, old)

    def test_chrome_retry_rejects_an_additional_lead_post(self):
        receipt, old, new = chrome_fixture()
        receipt["requests"].append(receipt["requests"][0])
        with self.assertRaisesRegex(ValueError, "request sequence"):
            release.check_chrome_retry(receipt, old, new)

    def test_successor_requires_its_own_rollback_receipt(self):
        receipt, old, new = chrome_fixture("0.2.18", release.SUCCESSOR_SHA)
        release.check_chrome_retry(receipt, old, new, version="0.2.18", candidate_hash=release.SUCCESSOR_SHA)
        with self.assertRaisesRegex(ValueError, "archive binding"):
            release.check_chrome_retry(receipt, old, new)

    def test_saved_delivery_and_media_scope_remain_held(self):
        release.check_saved_scope(SAVED_SCOPE, MARKETS)
        for field, value in (("average_daily_aed", 2501), ("locally_bound_action", "unapproved"),
                             ("test_conversion", True), ("prepared_parent_ids", {"AE": "other"})):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "campaign scope"):
                release.check_saved_scope(SAVED_SCOPE | {"ads": SAVED_SCOPE["ads"] | {field: value}}, MARKETS)
        with self.assertRaisesRegex(ValueError, "TEST delivery"):
            release.check_saved_scope(SAVED_SCOPE | {"test": SAVED_SCOPE["test"] | {"replay_requested": True}}, MARKETS)

    def test_market_review_cannot_claim_new_acceptance(self):
        review = MARKETS | {"summary": MARKETS["summary"] | {"operational_coverage_gates_closed": 1}}
        with self.assertRaisesRegex(ValueError, "market review"):
            release.check_saved_scope(SAVED_SCOPE, review)


class SuccessorEvidenceTests(unittest.TestCase):
    def setUp(self):
        target = BytesIO()
        with ZipFile(target, "w") as archive:
            for name in (*release.FORM_ASSETS, "assets/google-runtime.js", "assets/hub.css"):
                archive.writestr("bsre-enquiries/" + name, name.encode())
        self.archive = target.getvalue()

    def test_successor_browser_checks_runtime_bytes_and_receipt_count(self):
        browser = BROWSER | {"package_sha256": release.SUCCESSOR_SHA, "manifest_sha256": release.SUCCESSOR_PROFILE_SHA,
                             "served_asset_digests": release.asset_hashes(self.archive, (*release.FORM_ASSETS, "assets/google-runtime.js")),
                             "browser_observations": [
                                 {"name": "opaque_probes_from_both_vendor_stubs", "value": []},
                                 {"name": "one_query_free_analytics_page_view", "value": True},
                                 {"name": "one_receipt_command_per_purpose_and_duplicate_blocked", "value": {
                                     "receiptNames": ["conversion", "generate_lead"], "count": 3, "accepted": True,
                                     "eligible": True, "matchedReceipt": True, "allowlistedQueryFreeCommands": True}},
                                 {"name": "withdrawal_retires_both_opaque_frames", "value": {
                                     "framesAbsent": True, "noExtraCommand": True}}]}
        release.check_successor_browser(browser, self.archive)
        changed = browser | {"served_asset_digests": browser["served_asset_digests"] | {"assets/lead.js": "different"}}
        with self.assertRaisesRegex(ValueError, "served assets"):
            release.check_successor_browser(changed, self.archive)
        browser["browser_observations"][2]["value"]["count"] = 4
        with self.assertRaisesRegex(ValueError, "receipt or consent"):
            release.check_successor_browser(browser, self.archive)

    def test_successor_navigation_rejects_altered_served_assets_or_vendor_traffic(self):
        assets = release.asset_hashes(self.archive, (*release.FORM_ASSETS, "assets/hub.css"))
        attribution = {"status": "VERIFIED_LOCAL_CONTINUATION", "driver_exit": 0, "release": "0.2.18",
                       "preparation": {"sha256": release.SUCCESSOR_SHA, "members": 53}, "external_transmissions": 0,
                       "fixture_removed": True, "chrome_stopped": True, "proxy_closed": True, "tls_closed": True,
                       "requests": [{}] * 18, "phases": [{}] * 9, "checks": passes(14),
                       "assets": [{"release": "0.2.18", "asset": path, "sha256": value} for path, value in assets.items()]}
        release.check_successor_attribution(attribution, self.archive)
        with self.assertRaisesRegex(ValueError, "receipt or cleanup"):
            release.check_successor_attribution(attribution | {"external_transmissions": 1}, self.archive)
        attribution["assets"][0]["release"] = "0.2.17"
        with self.assertRaisesRegex(ValueError, "navigation assets"):
            release.check_successor_attribution(attribution, self.archive)


class CapturePinsTests(unittest.TestCase):
    def setUp(self):
        self.workspace = Path(self.enterContext(TemporaryDirectory()))
        self.manifest = self.workspace / "capture.json"
        self.entries = {key: {"path": f"{key}.json", "sha256": "a" * 64} for key in release.REQUIRED}
        for entry in self.entries.values():
            (self.workspace / entry["path"]).write_bytes(b"{}")

    def capture(self):
        raw = json.dumps({"scope": release.SCOPE, "files": self.entries}).encode()
        self.manifest.write_bytes(raw)
        return release.digest(raw)

    def test_complete_roster_and_exact_capture_pin(self):
        pin = self.capture()
        self.assertEqual(set(release.evidence_paths(self.workspace, self.manifest, pin)), release.REQUIRED)
        self.manifest.write_bytes(self.manifest.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "manifest SHA-256"):
            release.evidence_paths(self.workspace, self.manifest, pin)

    def test_escaped_and_aliased_input_paths_are_rejected(self):
        for bad_path in ("../outside.json", "browser.json"):
            with self.subTest(path=bad_path):
                self.entries["market_review"]["path"] = bad_path
                with self.assertRaises(ValueError):
                    release.evidence_paths(self.workspace, self.manifest, self.capture())

    def test_successor_receipts_must_be_complete(self):
        for key in release.SUCCESSOR:
            self.entries[key] = {"path": f"{key}.json", "sha256": "a" * 64}
            (self.workspace / self.entries[key]["path"]).write_bytes(b"{}")
        self.assertEqual(set(release.evidence_paths(self.workspace, self.manifest, self.capture())),
                         release.REQUIRED | release.SUCCESSOR)
        del self.entries["successor_retry"]
        with self.assertRaisesRegex(ValueError, "Incomplete successor"):
            release.evidence_paths(self.workspace, self.manifest, self.capture())

    def test_json_pin_prevents_receipt_substitution(self):
        path = self.workspace / "browser.json"
        pin = release.digest(path.read_bytes())
        path.write_bytes(b'{"status":"invented"}')
        with self.assertRaisesRegex(ValueError, "receipt differs"):
            release.pinned_json((path, pin))

    def test_cli_require_ready_blocks_even_a_good_offline_bundle(self):
        argv = ["release", "--workspace", ".", "--capture", "capture.json", "--capture-sha256", "a" * 64,
                "--require-launch-ready"]
        with patch.object(sys, "argv", argv), patch.object(sys, "stdout", StringIO()), patch.object(
                release, "verify", return_value={"launch_status": "HOLD", "launch_authorized": False}):
            self.assertEqual(release.main(), 3)


if __name__ == "__main__":
    unittest.main()
