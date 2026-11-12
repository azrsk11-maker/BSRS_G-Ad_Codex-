"""Exercise PHP subprocess isolation without executing Foundation or PHP."""
import importlib.util
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("foundation_php", Path(__file__).resolve().parents[1] / "check_repository.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class FoundationPhpIsolationTests(unittest.TestCase):
    def orchestrate(self, required, available=True):
        manifest = {"page_count": 360}
        audit = SimpleNamespace(audit=lambda *args: {"status": "PASS", "files_read": 15,
            "registry_rows_fully_checked": 360, "upstream_check_count": 38, "additional_check_count": 14})
        native = SimpleNamespace(compile_manifest=lambda *args: manifest)
        actual_glob, actual_rglob = Path.glob, Path.rglob
        def glob(path, pattern, **kwargs):
            # Python 3.14 rglob delegates **/*.php and keyword options to glob.
            return list(actual_glob(path, pattern, **kwargs)) if pattern in ("*.php", "**/*.php") else [Path("synthetic-one.py"), Path("synthetic-two.py")]
        def rglob(path, pattern, **kwargs):
            if pattern == "*.php":
                return list(actual_rglob(path, pattern, **kwargs))
            return [Path("synthetic.test.mjs")] * 3 if pattern == "*.test.mjs" else []
        def child(args, **kwargs):
            tap = ("TAP version 13\n1..1\n# tests 1\n# suites 0\n# pass 1\n# fail 0\n"
                   "# cancelled 0\n# skipped 0\n# todo 0\n# duration_ms 1\n")
            return subprocess.CompletedProcess(args, 0, tap if "--test-reporter=tap" in args else "", "")
        def which(name):
            return {"node": "synthetic-node", "php": "synthetic-php" if available else None}.get(name)
        keyword = {"workers": 2, "aggregate_timeout_seconds": 300,
            "expected_ids_sha256": "a" * 64, "evidence_sha256": "b" * 64,
            "evidence_file": "test-output/keyword-modules-synthetic.json",
            "summary": {"discovered_modules": 1, "completed_modules": 1, "discovered": 2,
                "started": 2, "finished": 2, "skipped": 0, "coverage_verified": True,
                "timed_out": False, "passed": True}}
        owned = SimpleNamespace(run_owned=lambda args, **kwargs:
            subprocess.CompletedProcess(args, 0, json.dumps(keyword), ""))
        with patch.object(CHECKER, "module", side_effect=[audit, native, owned]), \
                patch.object(Path, "read_text", autospec=True,
                    side_effect=lambda p, *a, **k: json.dumps(manifest) if p.name == "native-page-manifest.json" else "{}"), \
                patch.object(Path, "glob", autospec=True, side_effect=glob), \
                patch.object(Path, "rglob", autospec=True, side_effect=rglob), \
                patch.object(CHECKER.shutil, "which", side_effect=which), \
                patch.object(CHECKER.subprocess, "run", side_effect=child) as process:
            result = CHECKER.run_checks(require_php=required)
        return result, process.call_args_list

    def test_required_php_isolates_all_existing_lints_and_behavior_checks(self):
        result, calls = self.orchestrate(True)
        php_calls = [call for call in calls if call.args[0][0] == "synthetic-php"]
        self.assertEqual(len(php_calls), 48)
        self.assertEqual(sum("-l" in call.args[0] for call in php_calls), 34)
        lint_paths = [Path(call.args[0][-1]).relative_to(CHECKER.ROOT).as_posix()
                      for call in php_calls if "-l" in call.args[0]]
        self.assertEqual(lint_paths, [
            "tools/native-wordpress/" + name for name in ["native-draft-preview.php",
                "native-draft-writer.php", "paid-entry-search.php", "tests/native-draft-preview-test.php",
                "tests/native-draft-writer-test.php"]] + [
            "tools/consent-retention/per-choice/" + name for name in ["SelectiveChoiceRetirement.php",
                "selective-choice.test.php", "selective-native.php", "PurposeChoicePlanner.php",
                "purpose-choice.test.php", "purpose-selective-native.php"]] + [
            "tools/consent-retention/compaction-native.php"] + [
            "tools/owner-mail-review/" + name for name in sorted(["Cleanup.php", "OwnerClosure.php", "OwnerCollection.php", "OwnerMailReview.php", "OwnerRetirement.php",
                "TestDoubles.php", "WordPress.php", "guard.test.php", "native-test.php",
                "collection-native.php", "retirement-native.php", "test_owner_collection.php", "test_owner_closure.php", "test_owner_mail_review.php", "test_owner_retirement.php"], key=Path)] + [
            "tools/closed-enquiry-retention/" + name for name in ["WpCaptureResource.php", "capture-native.php", "test_wp_capture_guard.php",
                "admission-capture-native.php", "test_wp_capture_purpose.php", "intake-custody-native.php",
                "combined-native.php"]])
        behavior = [Path(call.args[0][-1]).relative_to(CHECKER.ROOT).as_posix()
                    for call in php_calls if "-l" not in call.args[0]]
        self.assertEqual(behavior, [
            "tools/consent-retention/linkage.test.php", "tools/consent-retention/compaction.test.php",
            "tools/consent-retention/per-choice/test_per_choice.php",
            "tools/consent-retention/per-choice/selective-choice.test.php",
            "tools/consent-retention/per-choice/purpose-choice.test.php",
            "tools/native-wordpress/tests/native-draft-preview-test.php",
            "tools/property-decision-tools/php.test.php", "tools/owner-mail-review/test_owner_mail_review.php",
            "tools/owner-mail-review/test_owner_closure.php",
            "tools/owner-mail-review/test_owner_retirement.php",
            "tools/owner-mail-review/test_owner_collection.php",
            "tools/owner-mail-review/guard.test.php",
            "tools/closed-enquiry-retention/test_wp_capture_guard.php",
            "tools/closed-enquiry-retention/test_wp_capture_purpose.php"])
        for call in php_calls:
            args = call.args[0]
            self.assertEqual(args[1], "-n")
            self.assertEqual(args[1:14:2], ["-n", "zend.assertions=1", "assert.active=1",
                "assert.exception=1", "allow_url_fopen=0", "allow_url_include=0",
                "disable_functions=mail,exec,shell_exec,system,passthru,popen,proc_open,"
                "fsockopen,pfsockopen,stream_socket_client,stream_socket_server,socket_create,socket_connect"])
            self.assertEqual(args[:14], CHECKER.php_command_prefix("synthetic-php"))
            self.assertEqual(call.kwargs["timeout"], 120)
            self.assertNotIn("env", call.kwargs)
        self.assertFalse(any(c["check"] == "native-php-runtime" for c in result["checks"]))
        self.assertFalse(result["release_authorized"])

    def test_optional_php_never_executes_even_when_available_and_non_php_is_unchanged(self):
        required, required_calls = self.orchestrate(True)
        for available in (True, False):
            result, optional_calls = self.orchestrate(False, available)
            self.assertFalse(any(call.args[0][0] == "synthetic-php" for call in optional_calls))
            marker = [c for c in result["checks"] if c["check"] == "native-php-runtime"]
            self.assertEqual(len(marker), 1)
            self.assertIsNone(marker[0]["passed"])
            self.assertIn("--require-php", marker[0]["details"])
            self.assertEqual(optional_calls,
                [call for call in required_calls if call.args[0][0] != "synthetic-php"])

    def test_required_missing_php_fails_without_php_execution(self):
        result, calls = self.orchestrate(True, False)
        self.assertFalse(any(call.args[0][0] == "synthetic-php" for call in calls))
        failure = [c for c in result["checks"] if c["check"] == "php-runtime-required"]
        self.assertEqual(failure, [{"check": "php-runtime-required", "passed": False,
                                    "details": "PHP runtime unavailable"}])
        self.assertFalse(result["passed"])
        self.assertFalse(result["release_authorized"])

    def test_rglob_keyword_delegation_preserves_actual_php_walk_and_all_commands(self):
        # Exercise the newer pathlib delegation while running on Python 3.12 too.
        delegated_patterns = []
        def recursive_via_glob(path, pattern, **kwargs):
            delegated_patterns.append(pattern)
            return path.glob("**/" + pattern, case_sensitive=kwargs.get("case_sensitive"))
        with patch.object(Path, "rglob", new=recursive_via_glob):
            result, delegated_calls = self.orchestrate(True)
        self.assertEqual(delegated_patterns, ["*.php"])
        baseline, baseline_calls = self.orchestrate(True)
        self.assertEqual(delegated_calls, baseline_calls)
        self.assertEqual(sum(call.args[0][0] == "synthetic-php" for call in delegated_calls), 48)
        self.assertEqual(result["passed"], baseline["passed"])
        self.assertFalse(result["release_authorized"])


if __name__ == "__main__":
    unittest.main()
