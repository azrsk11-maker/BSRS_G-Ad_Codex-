"""Reconcile the private 0.2.17 release evidence in one offline readback."""

from argparse import ArgumentParser
import json
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile

from check_gtm_exports import BOOTSTRAP, CANDIDATE_SHA256, read_json, verify_exports
from check_hostinger_preimage import HASH, ROLLBACK_SHA256, digest, read_pinned_zip, verify as verify_host_export
from compose_country_review import compose


PROFILE = "gtm-nonce-0217"
PROFILE_SHA256 = "ab63679bcee472b5fe1eac494d7244f37f424bb90439e337f92a354be62beffd"
PREDECESSOR_SHA256 = "8d248292812b04bc5faf69cbd0f0a2db69e02e1cf71bab5e98e279031894b466"
SCOPE = "OFFPLAN_0217_PRIVATE_EVIDENCE"
ACCOUNT = "573-038-4686"
PARENT_IDS = {"AE": "24372566774", "DE": "24546407422", "FR": "24546407401",
              "IN": "24540258368", "TW": "24546407404"}
REQUIRED = {"candidate", "predecessor", "rollback", "gtm_live", "gtm_draft", "gtm_capture",
            "browser", "exported_bootstrap", "native_installer", "native_retry", "https_retry",
            "saved_scope", "market_review"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def evidence_paths(workspace, capture, capture_sha256):
    manifest, actual_hash = read_json(capture)
    require(actual_hash == capture_sha256.lower(), "Release evidence manifest SHA-256 mismatch")
    require(set(manifest) == {"scope", "files"} and manifest["scope"] == SCOPE,
            "Unexpected release evidence scope")
    entries = manifest["files"]
    require(isinstance(entries, dict) and REQUIRED <= entries.keys() <= REQUIRED | {"host_export"},
            "Unexpected release evidence roster")
    workspace = workspace.resolve(strict=True)
    entries_by_key = {}
    locations = set()
    for key, record in entries.items():
        require(isinstance(record, dict) and set(record) == {"path", "sha256"}
                and isinstance(record["path"], str) and "\\" not in record["path"]
                and isinstance(record["sha256"], str) and HASH.fullmatch(record["sha256"]) is not None,
                "Invalid evidence path or SHA-256")
        relative = PurePosixPath(record["path"])
        require(not relative.is_absolute() and relative.as_posix() == record["path"]
                and bool(relative.parts) and not any(part.startswith(".") or ":" in part for part in relative.parts),
                "Evidence path is outside the workspace scope")
        requested = workspace / relative
        resolved = requested.resolve(strict=True)
        require(resolved.is_relative_to(workspace) and resolved.is_file() and not requested.is_symlink()
                and str(resolved).casefold() not in locations, "Invalid or duplicate release evidence file")
        locations.add(str(resolved).casefold())
        entries_by_key[key] = (resolved, record["sha256"])
    return entries_by_key


def pinned_json(entry):
    path, expected_hash = entry
    value, actual_hash = read_json(path)
    require(expected_hash == actual_hash, "Saved release receipt differs from its pin")
    return value


def all_checks_pass(checks, expected_count):
    return isinstance(checks, dict) and len(checks) == expected_count and all(v is True for v in checks.values())


def check_local_verification(browser, exported, installer, retries):
    require(browser["status"] == "PASS" and browser["driver_exit"] == 0
            and browser["package_sha256"] == CANDIDATE_SHA256 and browser["manifest_sha256"] == PROFILE_SHA256
            and browser["candidate_members"] == 53 and browser["vendor_transmissions"] == 0
            and all_checks_pass(browser["checks"], 11), "Exact native Chrome verification changed")
    exported_body = BOOTSTRAP.strip().removeprefix("<script>").removesuffix("</script>")
    checks = exported["checks"]
    require(exported["status"] == "PASS" and exported["driver_exit"] == 0
            and exported["archive_sha256"] == CANDIDATE_SHA256 and exported["vendor_transmissions"] == 0
            and exported["bootstrap_inline_body_sha256"] == digest(exported_body.encode("utf-8"))
            and len(checks) == 7 and sum(len(group) for group in checks.values()) == 46
            and all(all_checks_pass(group, len(group)) for group in checks.values()),
            "Exact exported bootstrap verification changed")
    require(installer["status"] == "VERIFIED_LOCAL_0217_NATIVE_UPGRADE_AND_ROLLBACK"
            and installer["candidate_sha256"] == CANDIDATE_SHA256 and installer["rollback_sha256"] == ROLLBACK_SHA256
            and installer["manifest_sha256"] == PROFILE_SHA256 and installer["common_rotated_asset_count"] == 6
            and installer["local_only"] is True and installer["production_or_provider_writes"] == 0
            and installer["hostinger_installed_preimage_verified"] is False,
            "Exact native installation or rollback verification changed")
    require(retry_checks_pass(retries) and retries["transport"] ==
            "WordPress core in-process REST dispatch under pinned PHP CLI, no listening sockets",
            "Direct REST retry and receipt preservation verification changed")


def retry_checks_pass(retries):
    return (retries["status"] == "PASS" and len(retries["requests"]) == 17
            and all_checks_pass(retries["checks"], 25) and retries["external_transmissions"] == 0
            and retries["synthetic_fixture_removed"] is True
            and retries["archives"] == {"0.2.17": {"sha256": CANDIDATE_SHA256, "members": 53},
                                        "0.2.12": {"sha256": ROLLBACK_SHA256, "members": 30}})


def check_https_retry(retries):
    require(retry_checks_pass(retries) and retries["transport"] ==
            "verified loopback TLS to a guarded PHP built-in web server, native WordPress REST over HTTP"
            and retries["listener_closed"] is True and retries["front_errors"] == []
            and all(request["tls"] == "TLSv1.3" for request in retries["requests"]),
            "Loopback HTTPS retry verification changed")


def check_saved_scope(saved, review):
    ads, test = saved["ads"], saved["test"]
    counts = review["summary"]
    require(saved["status"] == "HOLD" and saved["launch_ready"] is False and ads["account"] == ACCOUNT
            and ads["prepared_parent_ids"] == PARENT_IDS and ads["average_daily_aed"] == 2500
            and ads["locally_bound_action"] == "7873290954" and ads["test_conversion"] is False,
            "Saved campaign scope or conversion action changed")
    require(test == {"one_delivery_reconciled": True, "eligible_for_measurement": False, "replay_requested": False},
            "Approved TEST delivery boundary changed")
    require(review["status"] == "HOLD" and review["account"] == ACCOUNT
            and counts["markets"] == 5 and counts["prepared_average_daily_aed"] == 2500
            and counts["new_destinations_accepted"] == counts["operational_coverage_gates_closed"] == 0
            and counts["new_keyword_admissions"] == 0, "Frozen market review acceptance changed")


def verify(workspace, capture, capture_sha256):
    entries = evidence_paths(workspace, capture, capture_sha256)
    profile_file = Path(__file__).with_name("GTM_NONCE_0217_REVIEW.json")
    profile = pinned_json((profile_file, PROFILE_SHA256))
    base = read_pinned_zip(*entries["predecessor"])
    candidate = read_pinned_zip(*entries["candidate"])
    read_pinned_zip(*entries["rollback"])
    require(entries["predecessor"][1] == PREDECESSOR_SHA256 and entries["candidate"][1] == CANDIDATE_SHA256
            and entries["rollback"][1] == ROLLBACK_SHA256
            and compose(base, profile, PROFILE) == candidate,
            "Exact release archive pair or Source profile changed")
    tags = verify_exports(entries["gtm_live"][0], entries["gtm_draft"][0], entries["candidate"][0],
                          *entries["gtm_capture"])
    require(tags["rollback"]["sha256"] == entries["gtm_live"][1]
            and tags["draft"]["sha256"] == entries["gtm_draft"][1], "GTM exports disagree with the release evidence pins")
    check_local_verification(*(pinned_json(entries[key]) for key in
                               ("browser", "exported_bootstrap", "native_installer", "native_retry")))
    check_https_retry(pinned_json(entries["https_retry"]))
    check_saved_scope(pinned_json(entries["saved_scope"]), pinned_json(entries["market_review"]))
    host_capture = entries.get("host_export")
    host = verify_host_export(host_capture[0], entries["rollback"][0], host_capture[1]) if host_capture else None
    return {
        "status": "OFFLINE_RELEASE_EVIDENCE_VERIFIED",
        "launch_status": "HOLD",
        "launch_authorized": False,
        "provider_state_checked_here": False,
        "release_evidence_sha256": capture_sha256.lower(),
        "candidate_sha256": CANDIDATE_SHA256,
        "rollback_sha256": ROLLBACK_SHA256,
        "verified_local_checks": {"native_browser": 11, "exact_export_bootstrap": 46, "direct_rest_retry": 25,
                                  "loopback_https_retry": 25},
        "gtm_exports": {"draft_tags": tags["draft"]["tags"], "rollback_tags": tags["rollback"]["tags"]},
        "hostinger_capture_comparison": host,
        "saved_launch_scope": {"paused_markets": 5, "aggregate_average_daily_aed": 2500, "test_conversion": False},
        "live_acceptance": "Separate scoped provider, review, privacy, destination and operating evidence required",
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--capture-sha256", required=True)
    parser.add_argument("--require-launch-ready", action="store_true")
    options = parser.parse_args()
    try:
        report = verify(options.workspace, options.capture, options.capture_sha256)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError, BadZipFile):
        parser.exit(1, "HOLD. Release evidence is missing, altered or outside the verified scope.\n")
    print(json.dumps(report, indent=2))
    return 3 if options.require_launch_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
