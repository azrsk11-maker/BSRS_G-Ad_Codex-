"""Run bounded offline foundation acceptance; never contact production or deploy."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


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
        tick = time.perf_counter()
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=120)
        record(name, proc.returncode == 0, {"exit": proc.returncode,
               "elapsed_seconds": round(time.perf_counter()-tick, 6),
               "output_tail": (proc.stdout + proc.stderr)[-1800:]})
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
    raise SystemExit(0 if result["passed"] else 1)
