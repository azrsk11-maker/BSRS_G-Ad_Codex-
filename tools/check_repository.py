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


def execute_check(name, args, cwd=ROOT):
    require_tap = name == TAP_CHECK
    tick = time.perf_counter()
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
    details = {"exit": proc.returncode, "elapsed_seconds": round(time.perf_counter()-tick, 6),
               "output_tail": (proc.stdout + proc.stderr)[-1800:]}
    summary = node_tap_summary(proc.stdout) if require_tap else None
    if require_tap:
        details["tap_summary"] = summary
        details["tap_evidence_status"] = "OBSERVED" if summary else "MISSING_OR_INVALID"
    return {"check": name, "passed": proc.returncode == 0 and (not require_tap or summary is not None
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
    def run(name, args, cwd=ROOT):
        results.append(execute_check(name, args, cwd))
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
    run("keyword-employment-education-consistency", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-education-2026-11-10/verify_capture.py")])
    run("keyword-employment-education-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-education-2026-11-10/verify_triage.py")])
    run("keyword-employment-broad-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-broad-2026-11-10/verify_capture.py")])
    run("keyword-employment-broad-triage", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-employment-broad-2026-11-10/verify_triage.py")])
    run("keyword-four-pool-capture", [sys.executable, "-B", str(ROOT / "docs/audit/keyword-exclusions-2026-11-10/verify_capture.py")])
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
        tests = sorted((ROOT/"tools/website-tracking").rglob("*.test.mjs"))
        record("tracking-tests-present", len(tests) >= 3, len(tests))
        run("tracking-and-commercial-behavior", [node, "--test", *map(str, tests)])
        run("runtime-evidence-honesty", [node, str(ROOT/"tools/website-tracking/validate_tracking_evidence.mjs"),
            str(specdir/"website_tracking_contract.json"), str(specdir/"website_tracking_acceptance_tests.json"),
            str(ROOT/"tools/website-tracking/tracking-evidence-2026-11-07.json")])
    php = shutil.which("php")
    if require_php and php:
        for path in sorted((ROOT/"tools/native-wordpress").rglob("*.php")):
            run("php-lint-" + path.name, [php, "-l", str(path)])
        run("linkage-reconciliation-behavior", [php, str(ROOT/"tools/consent-retention/linkage.test.php")])
        run("retirement-ledger-compaction-behavior", [php, str(ROOT/"tools/consent-retention/compaction.test.php")])
        run("per-choice-retention-planning", [php, str(ROOT/"tools/consent-retention/per-choice/test_per_choice.php")])
        for name in ("SelectiveChoiceRetirement.php", "selective-choice.test.php", "selective-native.php"):
            run("php-lint-" + name, [php, "-l", str(ROOT/"tools/consent-retention/per-choice"/name)])
        run("selective-choice-retirement-guards", [php, str(ROOT/"tools/consent-retention/per-choice/selective-choice.test.php")])
        for name in ("PurposeChoicePlanner.php", "purpose-choice.test.php", "purpose-selective-native.php"):
            run("php-lint-" + name, [php, "-l", str(ROOT/"tools/consent-retention/per-choice"/name)])
        run("purpose-choice-retirement-planning", [php, str(ROOT/"tools/consent-retention/per-choice/purpose-choice.test.php")])
        run("php-lint-retirement-compaction-native", [php, "-l", str(ROOT/"tools/consent-retention/compaction-native.php")])
        run("native-wordpress-isolated-behavior", [php, str(ROOT/"tools/native-wordpress/tests/native-draft-preview-test.php")])
        run("property-decision-shortcode-behavior", [php, str(ROOT/"tools/property-decision-tools/php.test.php")])
        for path in sorted((ROOT/"tools/owner-mail-review").glob("*.php")):
            run("php-lint-owner-mail-" + path.name, [php, "-l", str(path)])
        run("owner-mail-review-behavior", [php, str(ROOT/"tools/owner-mail-review/test_owner_mail_review.php")])
        run("owner-mail-guard-behavior", [php, str(ROOT/"tools/owner-mail-review/guard.test.php")])
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
