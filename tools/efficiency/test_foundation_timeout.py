"""Synthetic timeout observability; never run real Foundation subprocesses."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SPEC = importlib.util.spec_from_file_location("foundation_timeout", Path(__file__).resolve().parents[1] / "check_repository.py")
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)
RESOURCE_SPEC = importlib.util.spec_from_file_location('timeout_keyword_resources', CHECKER.ROOT/'tools/efficiency/keyword_resources.py')
RESOURCES = importlib.util.module_from_spec(RESOURCE_SPEC)
RESOURCE_SPEC.loader.exec_module(RESOURCES)


def tap():
    return ("TAP version 13\n# PRIVATE_SYNTHETIC_OUTPUT\n1..1\n"
            "# tests 1\n# suites 0\n# pass 1\n# fail 0\n"
            "# cancelled 0\n# skipped 0\n# todo 0\n# duration_ms 1.25\n")


class FoundationTimeoutTests(unittest.TestCase):
    def test_timeout_keeps_each_existing_bound_and_returns_failed_evidence(self):
        for name, timeout in (("keyword-system-behavior", 300), ("ordinary-synthetic-check", 120)):
            failure = subprocess.TimeoutExpired("PRIVATE_TEST_ONLY_COMMAND", timeout,
                                                output="partial synthetic output")
            with self.subTest(check=name), patch.object(CHECKER.subprocess, "run", side_effect=failure) as child, \
                    patch.object(CHECKER.time, "perf_counter", side_effect=[10, 10 + timeout + 0.125]):
                result = CHECKER.execute_check(name, ["synthetic-command"], cwd=Path("synthetic-cwd"))
            child.assert_called_once_with(["synthetic-command"], cwd=Path("synthetic-cwd"),
                                          capture_output=True, text=True, timeout=timeout)
            self.assertEqual(result, {"check": name, "passed": False, "details": {
                "exit": None, "elapsed_seconds": timeout + 0.125, "timed_out": True,
                "error_type": "TimeoutExpired", "output_tail": "partial synthetic output"}})
            self.assertNotIn("PRIVATE_TEST_ONLY_COMMAND", json.dumps(result))

    def test_partial_bytes_text_and_absent_streams_have_a_bounded_decoded_tail(self):
        def decoded(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
        cases = ((None, None), (b"first\xff", b"last\xe2\x82"),
                 ("prefix" + "x" * 1900, b"END"), (b"a" * 2000, "text stderr"))
        for stdout, stderr in cases:
            failure = subprocess.TimeoutExpired("synthetic-command", 120, output=stdout, stderr=stderr)
            with self.subTest(stdout_type=type(stdout).__name__, stderr_type=type(stderr).__name__), \
                    patch.object(CHECKER.subprocess, "run", side_effect=failure), \
                    patch("sys.stdout", new_callable=io.StringIO) as printed:
                result = CHECKER.execute_check("ordinary-synthetic-check", ["synthetic-command"])
            self.assertEqual(result["details"]["output_tail"], (decoded(stdout) + decoded(stderr))[-1800:])
            self.assertLessEqual(len(result["details"]["output_tail"]), 1800)
            self.assertFalse(result["passed"])
            self.assertEqual(printed.getvalue(), "")

    def test_timeout_cannot_accept_even_a_complete_successful_tap_trailer(self):
        failure = subprocess.TimeoutExpired("synthetic-node", 120, output=tap().encode("utf-8"),
                                            stderr=b"PRIVATE_SYNTHETIC_STDERR")
        with patch.object(CHECKER.subprocess, "run", side_effect=failure):
            result = CHECKER.execute_check(CHECKER.TAP_CHECK, ["synthetic-node"])
        self.assertFalse(result["passed"])
        self.assertIsNone(result["details"]["tap_summary"])
        self.assertEqual(result["details"]["tap_evidence_status"], "INCOMPLETE_TIMEOUT")
        public = CHECKER.public_test_summary(result)
        self.assertEqual(public, {"check": CHECKER.TAP_CHECK, "status": "MISSING_OR_INVALID",
                                  "release_authorized": False})
        self.assertNotIn("PRIVATE", json.dumps(public))

    def test_normal_command_results_keep_their_existing_details_and_exit_semantics(self):
        for exit_code in (0, 7):
            completed = subprocess.CompletedProcess(["synthetic-command"], exit_code, "normal output", "normal stderr")
            with self.subTest(exit_code=exit_code), patch.object(CHECKER.subprocess, "run", return_value=completed) as child, \
                    patch.object(CHECKER.time, "perf_counter", side_effect=[1, 1.5]):
                result = CHECKER.execute_check("ordinary-synthetic-check", ["synthetic-command"])
            child.assert_called_once_with(["synthetic-command"], cwd=CHECKER.ROOT,
                                          capture_output=True, text=True, timeout=120)
            self.assertEqual(result, {"check": "ordinary-synthetic-check", "passed": exit_code == 0,
                "details": {"exit": exit_code, "elapsed_seconds": 0.5,
                            "output_tail": "normal outputnormal stderr"}})

    def test_run_checks_keeps_prior_results_and_runs_remaining_checks_after_timeout(self):
        # All source reads/modules and subprocesses below are synthetic. This
        # exercises orchestration without executing any actual acceptance work.
        manifest = {"page_count": 360}
        audit = SimpleNamespace(audit=lambda *args: {"status": "PASS", "files_read": 15,
            "registry_rows_fully_checked": 360, "upstream_check_count": 38, "additional_check_count": 14})
        native = SimpleNamespace(compile_manifest=lambda *args: manifest)
        def read_text(path, *args, **kwargs):
            return json.dumps(manifest) if path.name == "native-page-manifest.json" else "{}"
        def child(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, tap() if "--test-reporter=tap" in args else "", "")
        owned = SimpleNamespace(run_owned=unittest.mock.Mock(side_effect=
            subprocess.TimeoutExpired("synthetic-keyword", 300, output=b"synthetic partial progress")))
        with patch.object(CHECKER.Path, "read_text", autospec=True, side_effect=read_text), \
                patch.object(CHECKER.Path, "glob", autospec=True,
                    return_value=[Path("synthetic-test-one.py"), Path("synthetic-test-two.py")]), \
                patch.object(CHECKER.Path, "rglob", autospec=True,
                    side_effect=lambda path, pattern: [Path("synthetic.test.mjs")] * 3 if pattern == "*.test.mjs" else []), \
                patch.object(CHECKER.shutil, "which", side_effect=lambda name: "synthetic-node" if name == "node" else None), \
                patch.object(CHECKER.subprocess, "run", side_effect=child), \
                patch.object(CHECKER, "module", side_effect=[audit, native, owned]):
            result = CHECKER.run_checks()
        checks = {check["check"]: check for check in result["checks"]}
        self.assertTrue(checks["keyword-research-capture-consistency"]["passed"])
        self.assertFalse(checks["keyword-system-behavior"]["passed"])
        self.assertTrue(checks["keyword-system-behavior"]["details"]["timed_out"])
        self.assertTrue(checks["efficiency-behavior"]["passed"])
        self.assertTrue(checks["tracking-and-commercial-behavior"]["passed"])
        self.assertTrue(checks["ci-has-no-production-secret-or-deployer"]["passed"])
        self.assertEqual([check["check"] for check in result["checks"] if check["passed"] is False],
                         ["keyword-system-behavior"])
        self.assertFalse(result["passed"])
        self.assertFalse(result["release_authorized"])

    def test_owned_keyword_path_keeps_300s_bound_and_fail_closed_start(self):
        owned = SimpleNamespace(run_owned=unittest.mock.Mock(side_effect=OSError("synthetic containment unavailable")))
        with patch.object(CHECKER, "module", return_value=owned), patch.object(CHECKER.subprocess, "run") as ordinary:
            result = CHECKER.execute_check("keyword-system-behavior", ["synthetic-keyword"], owned_tree=True)
        ordinary.assert_not_called()
        owned.run_owned.assert_called_once_with(["synthetic-keyword"], cwd=CHECKER.ROOT, timeout=300,
                                                deadline=unittest.mock.ANY)
        self.assertFalse(result["passed"])
        self.assertEqual(result["details"]["error_type"], "OSError")

    def test_owned_keyword_zero_exit_requires_complete_counted_evidence(self):
        valid = {"workers": 2, "aggregate_timeout_seconds": 300,
            'worker_resources':RESOURCES.select('2',{'cpu_count':2,'memory_available_bytes':8*1024**3}),
            "expected_ids_sha256": "a" * 64, "evidence_sha256": "b" * 64,
            "evidence_file": "test-output/keyword-modules-synthetic.json",
            "summary": {"discovered_modules": 1, "completed_modules": 1, "discovered": 2,
                "started": 2, "finished": 2, "skipped": 0, "coverage_verified": True,
                "timed_out": False, "passed": True}}
        incomplete = json.loads(json.dumps(valid))
        incomplete["summary"]["finished"] = 1
        unattested = json.loads(json.dumps(valid));del unattested['worker_resources']
        for body, expected in ((valid, True), (incomplete, False), (unattested,False), ({}, False)):
            owned = SimpleNamespace(run_owned=unittest.mock.Mock(return_value=
                subprocess.CompletedProcess([], 0, json.dumps(body), "")))
            with self.subTest(body=body), patch.object(CHECKER, "module", side_effect=lambda name,path:
                    RESOURCES if name=='foundation_keyword_resources' else owned):
                result = CHECKER.execute_check("keyword-system-behavior", ["synthetic-keyword"], owned_tree=True)
            self.assertEqual(result["passed"], expected)
            self.assertEqual(result["details"]["keyword_evidence_status"],
                             "COMPLETE" if expected else "INCOMPLETE_OR_INVALID")


if __name__ == "__main__":
    unittest.main()
