"""Run bounded offline foundation acceptance; never contact production or deploy."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TAP_CHECK = "synthetic-local-expiry-journal"
TAP_COUNTS = ("tests", "suites", "pass", "fail", "cancelled", "skipped", "todo")


# Offline PHP scripts must not inherit host INI, disabled assertions or network/mail helpers.
PHP_ISOLATED_OPTIONS = (
    "-n", "-d", "zend.assertions=1", "-d", "assert.active=1", "-d", "assert.exception=1",
    "-d", "allow_url_fopen=0", "-d", "allow_url_include=0",
    "-d", "disable_functions=mail,exec,shell_exec,system,passthru,popen,proc_open,"
    "fsockopen,pfsockopen,stream_socket_client,stream_socket_server,socket_create,socket_connect",
)


def php_command_prefix(executable):
    """Process-local CLI isolation; no host settings, services or PATH changes."""
    return [executable, *PHP_ISOLATED_OPTIONS]


def valid_tap_summary(summary):
    if not isinstance(summary, dict) or set(summary) != {*TAP_COUNTS, "duration_ms"}:
        return False
    if any(type(summary[k]) is not int or not 0 <= summary[k] <= 1000000 for k in TAP_COUNTS):
        return False
    duration = summary["duration_ms"]
    return (summary["tests"] > 0 and sum(summary[k] for k in
            ("pass", "fail", "cancelled", "skipped", "todo")) == summary["tests"]
            and type(duration) in (int, float) and math.isfinite(duration) and 0 <= duration <= 86400000)


def node_tap_summary(output):
    """Read only Node's complete numeric TAP trailer; never expose test text."""
    if not isinstance(output, str):
        return None
    output = output.replace("\r\n", "\n")
    if not output.startswith("TAP version 13\n"):
        return None
    pattern = "".join(r"^# " + field + r" ([0-9]{1,7})\n" for field in TAP_COUNTS)
    pattern += r"^# duration_ms ([0-9]{1,8}(?:\.[0-9]{1,9})?)\n?\Z"
    match = re.search(pattern, output[-2048:], re.MULTILINE)
    if not match:
        return None
    counts = dict(zip(TAP_COUNTS, map(int, match.groups()[:-1])))
    duration = float(match.group(8))
    summary = {**counts, "duration_ms": duration}
    return summary if valid_tap_summary(summary) else None


def execute_check(name, args, cwd=ROOT, *, owned_tree=False):
    require_tap = name == TAP_CHECK
    tick = time.perf_counter()
    # The growing actual-source keyword suite exceeded 120s on the local host.
    # Keep other checks at their existing bound; never turn a timeout into PASS.
    timeout = 300 if name == "keyword-system-behavior" else 120
    try:
        if owned_tree:
            deadline = time.monotonic() + timeout - (time.perf_counter() - tick)
            supervisor = module("foundation_owned_process", ROOT / "tools/efficiency/owned_process.py")
            proc = supervisor.run_owned(args, cwd=cwd, timeout=timeout, deadline=deadline)
        else:
            proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        # TimeoutExpired can retain bytes even when text=True. Keep partial
        # output only in the ignored report, never as complete test evidence.
        def partial_text(value):
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value if isinstance(value, str) else ""
        details = {"exit": None, "elapsed_seconds": round(time.perf_counter()-tick, 6),
                   "timed_out": True, "error_type": "TimeoutExpired",
                   "output_tail": (partial_text(exc.stdout) + partial_text(exc.stderr))[-1800:]}
        if require_tap:
            details["tap_summary"] = None
            details["tap_evidence_status"] = "INCOMPLETE_TIMEOUT"
        return {"check": name, "passed": False, "details": details}
    except OSError as exc:
        if not owned_tree:
            raise
        return {"check": name, "passed": False, "details": {
            "exit": None, "elapsed_seconds": round(time.perf_counter()-tick, 6),
            "error_type": type(exc).__name__, "output_tail": "Owned process containment/start failed"}}
    details = {"exit": proc.returncode, "elapsed_seconds": round(time.perf_counter()-tick, 6),
               "output_tail": (proc.stdout + proc.stderr)[-1800:]}
    keyword_complete = True
    if owned_tree:
        try:
            report = json.loads(proc.stdout)
            summary = report["summary"]
            counts = ("discovered_modules", "completed_modules", "discovered", "started", "finished", "skipped")
            keyword_complete = (all(type(summary[key]) is int and summary[key] >= 0 for key in counts)
                and summary["discovered_modules"] == summary["completed_modules"] > 0
                and summary["discovered"] == summary["started"] == summary["finished"] > 0
                and summary["coverage_verified"] is True and summary["passed"] is True
                and summary["timed_out"] is False and type(report["workers"]) is int
                and 1 <= report["workers"] <= 2 and report["aggregate_timeout_seconds"] == timeout
                and re.fullmatch(r"test-output/keyword-modules-[A-Za-z0-9_-]+\.json", report["evidence_file"]) is not None
                and all(re.fullmatch(r"[0-9a-f]{64}", report[key]) is not None
                        for key in ("evidence_sha256", "expected_ids_sha256")))
            details["keyword_summary"] = {key: summary[key] for key in (*counts, "coverage_verified", "timed_out", "passed")}
            details["keyword_evidence"] = {key: report[key] for key in
                ("evidence_file", "evidence_sha256", "expected_ids_sha256")}
        except (ValueError, KeyError, TypeError):
            keyword_complete = False
        details["keyword_evidence_status"] = "COMPLETE" if keyword_complete else "INCOMPLETE_OR_INVALID"
    summary = node_tap_summary(proc.stdout) if require_tap else None
    if require_tap:
        details["tap_summary"] = summary
        details["tap_evidence_status"] = "OBSERVED" if summary else "MISSING_OR_INVALID"
    return {"check": name, "passed": proc.returncode == 0 and keyword_complete and (not require_tap or summary is not None
            and summary["pass"] > 0 and summary["fail"] == summary["cancelled"] == 0),
            "details": details}


def public_test_summary(check):
    """Revalidate the fixed allowlist before printing an existing check receipt."""
    if check.get("check") != TAP_CHECK or not isinstance(check.get("details"), dict):
        return None
    details = check["details"]
    summary = details.get("tap_summary")
    if (details.get("tap_evidence_status") != "OBSERVED" or not valid_tap_summary(summary)
            or type(details.get("exit")) is not int or not -255 <= details["exit"] <= 255):
        return {"check": TAP_CHECK, "status": "MISSING_OR_INVALID", "release_authorized": False}
    return {"check": TAP_CHECK, "status": "OBSERVED", "runner_platform": sys.platform,
            "process_exit": details["exit"], **summary, "release_authorized": False}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run_checks(require_php=False):
    started = time.perf_counter()
    results = []
    def record(name, passed, details):
        results.append({"check": name, "passed": bool(passed), "details": details})
    def run(name, args, cwd=ROOT, *, owned_tree=False):
        results.append(execute_check(name, args, cwd, owned_tree=owned_tree))
    specdir = ROOT / "docs/google-ads"
    audit = module("spec_audit", ROOT / "tools/audit_specification.py")
    with tempfile.TemporaryDirectory() as temp:
        report = audit.audit(specdir, Path(temp))
        record("entire-source-integrity", report["status"] == "PASS",
               {k: report[k] for k in ("files_read", "registry_rows_fully_checked", "upstream_check_count", "additional_check_count")})
    native = module("native_manifest", ROOT / "tools/native-wordpress/compile_native_manifest.py")
    compiled = native.compile_manifest(json.loads((specdir/"planned_campaign_page_registry.json").read_text(encoding="utf-8-sig")),
                                       json.loads((specdir/"page_family_allocation.json").read_text(encoding="utf-8-sig")))
    saved = json.loads((ROOT/"tools/native-wordpress/native-page-manifest.json").read_text(encoding="utf-8-sig"))
    record("native-page-manifest-build", compiled == saved, {"pages": compiled["page_count"], "apply_supported": False})
    run("keyword-research-capture-consistency", [sys.executable, "-B", str(
        ROOT / "docs/audit/keyword-research-2026-11-07/verify_capture.py")])
    # Both following checks verify the original Discovery capture before using it.
    run("keyword-supply-discovery-consistency", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-discovery-supply-2026-11-08/verify_capture.py")])
    run("keyword-supply-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-discovery-supply-2026-11-08/verify_triage.py")])
    run("keyword-employment-education-consistency", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-education-2026-11-10/verify_capture.py")])
    run("keyword-employment-education-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-education-2026-11-10/verify_triage.py")])
    run("keyword-employment-broad-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-broad-2026-11-10/verify_capture.py")])
    run("keyword-employment-broad-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-broad-2026-11-10/verify_triage.py")])
    run("keyword-four-pool-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-exclusions-2026-11-10/verify_capture.py")])
    run("keyword-four-pool-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-exclusions-2026-11-10/verify_triage.py")])
    run("keyword-property-readiness-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-property-readiness-2026-11-11/verify_capture.py")])
    run("keyword-property-readiness-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-property-readiness-2026-11-11/verify_triage.py")])
    run("keyword-northern-emirates-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-northern-emirates-2026-11-11/verify_capture.py")])
    run("keyword-northern-emirates-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-northern-emirates-2026-11-11/verify_triage.py")])
    run("keyword-abu-sharjah-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-abu-dhabi-sharjah-2026-11-11/verify_capture.py")])
    run("keyword-abu-sharjah-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-abu-dhabi-sharjah-2026-11-11/verify_triage.py")])
    run("keyword-developer-employment-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-developer-employment-2026-11-11/verify_capture.py")])
    run("keyword-developer-employment-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-developer-employment-2026-11-11/verify_triage.py")])
    run("keyword-occupational-education-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-occupational-education-2026-11-11/verify_capture.py")])
    run("keyword-occupational-education-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-occupational-education-2026-11-11/verify_triage.py")])
    run("keyword-employment-lifecycle-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-lifecycle-2026-11-11/verify_capture.py")])
    run("keyword-employment-lifecycle-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-lifecycle-2026-11-11/verify_triage.py")])
    run("keyword-gap-research-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-gap-research-2026-11-11/verify_capture.py")])
    run("keyword-role-exam-assets-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-role-exam-assets-2026-11-11/verify_capture.py")])
    run("keyword-vendor-operations-commercial-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-vendor-operations-commercial-2026-11-11/verify_capture.py")])
    run("keyword-veterinary-source-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-ofqual-veterinary-2026-11-12/extract.py"), "--self-check"])
    run("keyword-bank-access-navigation-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-bank-access-navigation-2026-11-12/verify_capture.py"), "--self-check"])
    run("keyword-bank-support-semantic-review", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-bank-support-review-2026-11-12/verify_review.py"), "--self-check"])
    run("keyword-entertainment-clipboard-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-entertainment-clipboard-2026-11-11/verify_capture.py")])
    run("keyword-entertainment-clipboard-guards", [sys.executable, "-B", "-m", "unittest", "discover", "-s",
                                               str(ROOT / "docs/audit/keyword-entertainment-clipboard-2026-11-11"), "-p", "test_*.py"])
    run("keyword-vendor-operations-commercial-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-vendor-operations-commercial-2026-11-11/verify_triage.py")])
    run("keyword-vendor-review-reconciliation", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-vendor-review-coverage-2026-11-11/verify_coverage.py")])
    run("keyword-role-exam-assets-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-role-exam-assets-2026-11-11/verify_triage.py")])
    run("keyword-role-review-reconciliation", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-role-review-coverage-2026-11-11/verify_coverage.py")])
    run("keyword-gap-research-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-gap-research-2026-11-11/verify_triage.py")])
    run("keyword-observed-review-reconciliation", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-review-coverage-2026-11-11/verify_coverage.py")])
    run("keyword-gap-review-reconciliation", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-gap-review-coverage-2026-11-11/verify_coverage.py")])
    run("keyword-negative-research-admission", [sys.executable, "-B", str(ROOT / "tools/keyword-system/negative_admission.py")])
    run("keyword-employment-followup-artifacts", [sys.executable, "-B", str(ROOT / "tools/keyword-system/employment_followup_validator.py"),
                                                   str(ROOT / "docs/audit/keyword-employment-followup-2026-11-11")])
    run("keyword-employment-followup-batch2", [sys.executable, "-B", str(ROOT / "tools/keyword-system/supplemental_batch_validator.py"),
                                                str(ROOT / "docs/audit/keyword-employment-followup-2026-11-11-batch2")])
    run("planning-registry-360-safety", [sys.executable, "-B", str(ROOT / "tools/website-tracking/validate_planning_registry.py"),
                                          str(ROOT / "docs/google-ads/planned_campaign_page_registry.json")])
    run("release-controls-budget-safety", [sys.executable, "-B", str(ROOT / "tools/release-control/validate_release_controls.py"),
                                            str(ROOT / "config/release_controls.json")])
    # The current driver verifies the entire historical base before extensions.
    run("keyword-negative-research-composition", [sys.executable, "-B", str(ROOT / "tools/keyword-system/current_negative_library.py")])
    run("keyword-triage-source-coverage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-triage-2026-11-08/verify_workbench.py")])
    run("historical-search-term-count-audit", [sys.executable, "-B", str(ROOT / "docs/audit/search-terms-2026-11-08/verify_audit.py")])
    run("private-query-triage-count-integrity", [sys.executable, "-B", str(ROOT / "docs/audit/private-query-triage-counts-2026-11-08/verify_counts.py")])
    run("primary-plugin-fixture-provenance", [sys.executable, "-B", str(
        ROOT / "tools/staging-lab/verify_fixture.py")])
    for folder in ("native-wordpress", "keyword-system", "efficiency", "qualification-history", "qualified-export-source", "github-governance", "content-evidence", "creative-validation", "release-control", "staging-lab"):
        target = ROOT / "tools" / folder
        tests = list(target.glob("test_*.py"))
        record(folder + "-tests-present", len(tests) > 0, len(tests))
        if tests:
            if folder == "keyword-system":
                run(folder + "-behavior", [sys.executable, "-B", str(ROOT / "tools/efficiency/keyword_modules.py"),
                    "--supervised", "--suite", str(target)], owned_tree=True)
            else:
                run(folder + "-behavior", [sys.executable, "-B", "-m", "unittest", "discover", "-s", str(target), "-p", "test_*.py"])
    node = shutil.which("node")
    record("node-runtime", bool(node), "required for tracking/privacy/HTTP safety checks")
    if node:
        run("encrypted-recovery-package", [node, "--test", str(ROOT / "tools/recovery-package/package.test.mjs")])
        run("synthetic-recovery-expiry-runner", [node, "--test", str(ROOT / "tools/recovery-package/expiry-runner/runner.test.mjs")])
        run(TAP_CHECK, [node, "--test", "--test-reporter=tap", str(ROOT / "tools/recovery-package/expiry-runner/local-journal.test.mjs")])
        decision_tests = sorted((ROOT / "tools/property-decision-tools").glob("*.test.*js"))
        record("property-decision-tests-present", bool(decision_tests), len(decision_tests))
        if decision_tests:
            run("property-decision-behavior", [node, "--test", *map(str, decision_tests)])
        run("retention-candidate-source-pin", [node, "--test", str(ROOT / "tools/consent-retention/candidate.test.mjs")])
        run("pinned-receiver-idempotency-outbox", [node, "--test", str(ROOT / "tools/staging-lab/receiver.test.mjs")])
        run("closed-enquiry-no-mail-source-receiver", [node, "--test", str(ROOT / "tools/closed-enquiry-retention/receiver-fence/candidate.test.mjs")])
        tests = sorted((ROOT/"tools/website-tracking").rglob("*.test.mjs"))
        record("tracking-tests-present", len(tests) >= 3, len(tests))
        run("tracking-and-commercial-behavior", [node, "--test", *map(str, tests)])
        run("runtime-evidence-honesty", [node, str(ROOT/"tools/website-tracking/validate_tracking_evidence.mjs"),
            str(specdir/"website_tracking_contract.json"), str(specdir/"website_tracking_acceptance_tests.json"),
            str(ROOT/"tools/website-tracking/tracking-evidence-2026-11-07.json")])
        run("native-form-contract-readback", [node, str(ROOT/"tools/website-tracking/validate_form_contract.mjs"),
            str(ROOT/"docs/audit/NATIVE_ENQUIRY_FORM_CONTRACT_READBACK_2026-11-11.json")])
        run("current-gate-matrix", [node, str(ROOT/"tools/release-control/validate_gate_matrix.mjs"),
            str(ROOT/"docs/audit/CURRENT_GATE_MATRIX_2026-11-11.json")])
        run("current-gate-matrix-20261112", [node, str(ROOT/"tools/release-control/validate_gate_matrix.mjs"),
            str(ROOT/"docs/audit/CURRENT_GATE_MATRIX_2026-11-12.json")])
        release_node_tests = sorted((ROOT/"tools/release-control").glob("*.test.mjs"))
        record("release-control-node-tests-present", len(release_node_tests) >= 2, len(release_node_tests))
        run("release-control-node-behavior", [node, "--test", *map(str, release_node_tests)])
    php = shutil.which("php")
    if require_php and php:
        php_prefix = php_command_prefix(php)
        for path in sorted((ROOT/"tools/native-wordpress").rglob("*.php")):
            run("php-lint-" + path.name, [*php_prefix, "-l", str(path)])
        run("linkage-reconciliation-behavior", [*php_prefix, str(ROOT/"tools/consent-retention/linkage.test.php")])
        run("retirement-ledger-compaction-behavior", [*php_prefix, str(ROOT/"tools/consent-retention/compaction.test.php")])
        run("per-choice-retention-planning", [*php_prefix, str(ROOT/"tools/consent-retention/per-choice/test_per_choice.php")])
        for name in ("SelectiveChoiceRetirement.php", "selective-choice.test.php", "selective-native.php"):
            run("php-lint-" + name, [*php_prefix, "-l", str(ROOT/"tools/consent-retention/per-choice"/name)])
        run("selective-choice-retirement-guards", [*php_prefix, str(ROOT/"tools/consent-retention/per-choice/selective-choice.test.php")])
        for name in ("PurposeChoicePlanner.php", "purpose-choice.test.php", "purpose-selective-native.php"):
            run("php-lint-" + name, [*php_prefix, "-l", str(ROOT/"tools/consent-retention/per-choice"/name)])
        run("purpose-choice-retirement-planning", [*php_prefix, str(ROOT/"tools/consent-retention/per-choice/purpose-choice.test.php")])
        run("php-lint-retirement-compaction-native", [*php_prefix, "-l", str(ROOT/"tools/consent-retention/compaction-native.php")])
        run("native-wordpress-isolated-behavior", [*php_prefix, str(ROOT/"tools/native-wordpress/tests/native-draft-preview-test.php")])
        run("property-decision-shortcode-behavior", [*php_prefix, str(ROOT/"tools/property-decision-tools/php.test.php")])
        for path in sorted((ROOT/"tools/owner-mail-review").glob("*.php")):
            run("php-lint-owner-mail-" + path.name, [*php_prefix, "-l", str(path)])
        run("owner-mail-review-behavior", [*php_prefix, str(ROOT/"tools/owner-mail-review/test_owner_mail_review.php")])
        run("owner-closure-amendment-behavior", [*php_prefix, str(ROOT/"tools/owner-mail-review/test_owner_closure.php")])
        run("owner-sender-retirement-behavior", [*php_prefix, str(ROOT/"tools/owner-mail-review/test_owner_retirement.php")])
        run("owner-initial-closure-collection-behavior", [*php_prefix, str(ROOT/"tools/owner-mail-review/test_owner_collection.php")])
        run("owner-mail-guard-behavior", [*php_prefix, str(ROOT/"tools/owner-mail-review/guard.test.php")])
        for name in ("WpCaptureResource.php", "capture-native.php", "test_wp_capture_guard.php",
                     "admission-capture-native.php", "test_wp_capture_purpose.php", "intake-custody-native.php",
                     "combined-native.php"):
            run("php-lint-capture-provider-" + name, [*php_prefix, "-l", str(ROOT/"tools/closed-enquiry-retention"/name)])
        run("wp-capture-provider-guards", [*php_prefix, str(ROOT/"tools/closed-enquiry-retention/test_wp_capture_guard.php")])
        run("wp-capture-purpose-bindings", [*php_prefix, str(ROOT/"tools/closed-enquiry-retention/test_wp_capture_purpose.php")])
    elif require_php:
        record("php-runtime-required", False, "PHP runtime unavailable")
    else:
        results.append({"check":"native-php-runtime", "passed":None, "details":"Delegated to mandatory native-wordpress-check CI job; use --require-php to run here"})
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in (".git", "__pycache__", "test-output", ".cache") for part in path.parts):
            continue
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix in (".pem", ".key", ".sqlite", ".jsonl") or path.name == ".env":
            record("public-file-hygiene", False, relative)
    workflow = (ROOT/".github/workflows/validate.yml").read_text(encoding="utf-8")
    record("ci-has-no-production-secret-or-deployer", not any(s in workflow for s in ("secrets.", "pull_request_target", "workflow_dispatch", "environment:", "contents: write")), "validation-only workflow")
    return {"scope":"OFFLINE_FOUNDATION_NOT_PRODUCTION_ACCEPTANCE", "passed":all(r["passed"] is not False for r in results),
            "release_authorized":False, "elapsed_seconds":round(time.perf_counter()-started, 6), "checks":results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-php", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT/"test-output/foundation-checks.json")
    args = parser.parse_args()
    destination = args.output.resolve()
    if not destination.is_relative_to((ROOT/"test-output").resolve()):
        parser.error("Output must stay inside ignored test-output/; source overwrite is forbidden")
    try:
        result = run_checks(args.require_php)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"passed":False, "release_authorized":False, "error_type":type(exc).__name__, "error":str(exc)}
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "checks"}))
    for check in result.get("checks", []):
        print(("PASS" if check["passed"] is True else "NOT_EXECUTED" if check["passed"] is None else "FAIL") + " " + check["check"])
        summary = public_test_summary(check)
        if summary is not None:
            print("TEST_SUMMARY " + json.dumps(summary, sort_keys=True))
    raise SystemExit(0 if result["passed"] else 1)
