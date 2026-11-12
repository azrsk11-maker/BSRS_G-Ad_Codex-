"""Focused synthetic runner/evidence failures; never rerun the actual suites."""
import copy
from pathlib import Path
import subprocess
import threading
import unittest
from unittest.mock import patch

import benchmark_check_groups as benchmark


class CheckGroupTests(unittest.TestCase):
    def test_complete_json_evidence_retains_all_values_and_bytes(self):
        check = benchmark.CHECKS[0]
        first = benchmark.outcome(check, 0, b'{"passed":true,"rows":5}', b"")
        changed = benchmark.outcome(check, 0, b'{"passed":true,"rows":6}', b"")
        whitespace = benchmark.outcome(check, 0, b'{"passed": true,"rows":5}', b"")
        self.assertNotEqual(first, changed)
        self.assertNotEqual(first, whitespace)
        for rc, body in ((1, b'{"passed":true}'), (0, b'{"passed":false}'), (0, b'incomplete')):
            with self.subTest(rc=rc, body=body), self.assertRaises(benchmark.BenchmarkError):
                benchmark.outcome(check, rc, body, b"")

    def test_unittest_only_elapsed_is_ignored(self):
        check = benchmark.CHECKS[1]
        first = b"..s\n----------------------------------------------------------------------\nRan 3 tests in 1.234s\n\nOK (skipped=1)\n"
        second = first.replace(b"1.234s", b"7.890s")
        expected = benchmark.outcome(check, 0, b"", first)
        self.assertEqual(expected, benchmark.outcome(check, 0, b"", second))
        for changed in (first.replace(b"3 tests", b"4 tests"), first.replace(b"skipped=1", b"skipped=2"),
                        first.replace(b"..s", b".ss")):
            self.assertNotEqual(expected, benchmark.outcome(check, 0, b"", changed))
        for changed in (first.replace(b"OK (skipped=1)", b"FAILED (failures=1)"), first + b"late data\n",
                        first.replace(b"3 tests", b"0 tests")):
            with self.assertRaises(benchmark.BenchmarkError):
                benchmark.outcome(check, 0, b"", changed)

    def test_runner_keeps_complete_streams_exit_and_existing_timeout(self):
        check = benchmark.CHECKS[0]
        completed = subprocess.CompletedProcess([], 0, b'{"passed":true,"rows":3}', b'notice\n')
        with patch.object(benchmark.subprocess, "run", return_value=completed) as child:
            result = benchmark.run_command(check, Path.cwd())
        self.assertEqual(child.call_args.kwargs, {"cwd": Path.cwd(), "capture_output": True, "check": False, "timeout": 120})
        self.assertEqual(result["stdout_bytes"], len(completed.stdout))
        self.assertEqual(result["complete_stderr_sha256"], benchmark.sha256(completed.stderr))
        self.assertEqual(result["outcome"]["exit"], 0)

    def test_spawn_failure_timeout_and_nonzero_cannot_pass(self):
        for failure in (OSError("synthetic"), subprocess.TimeoutExpired("synthetic", 120)):
            with self.subTest(failure=type(failure).__name__), patch.object(benchmark.subprocess, "run", side_effect=failure):
                with self.assertRaises(benchmark.BenchmarkError):
                    benchmark.run_command(benchmark.CHECKS[0], Path.cwd())
        with patch.object(benchmark.subprocess, "run", return_value=subprocess.CompletedProcess([], 7, b'{"passed":true}', b"")):
            with self.assertRaises(benchmark.BenchmarkError):
                benchmark.run_command(benchmark.CHECKS[0], Path.cwd())

    def test_two_worker_phase_runs_both_and_preserves_submission_order(self):
        barrier = threading.Barrier(2)
        def observed(check, root):
            barrier.wait(timeout=5)
            return {"check": check["name"]}
        with patch.object(benchmark, "run_command", side_effect=observed):
            phase = benchmark.run_phase(Path.cwd(), 2)
        self.assertEqual([r["check"] for r in phase["runs"]], [c["name"] for c in benchmark.CHECKS])

    def test_changed_source_stops_before_concurrent_phase(self):
        with patch.object(benchmark, "source_snapshot", side_effect=[{"hash": "a"}, {"hash": "b"}]), \
                patch.object(benchmark, "run_phase", return_value={}) as phase:
            with self.assertRaisesRegex(benchmark.BenchmarkError, "not started"):
                benchmark.benchmark()
        self.assertEqual(phase.call_args_list[0].args[1], 1)
        self.assertEqual(phase.call_count, 1)

    def test_outcome_mismatch_cannot_be_a_benchmark_success(self):
        serial = {"elapsed_seconds": 2, "runs": [{"outcome": {"exit": 0, "tests": 3}}]}
        changed = copy.deepcopy(serial)
        changed["runs"][0]["outcome"]["tests"] = 4
        with patch.object(benchmark, "source_snapshot", return_value={"hash": "stable"}), \
                patch.object(benchmark, "run_phase", side_effect=[serial, changed]):
            with self.assertRaisesRegex(benchmark.BenchmarkError, "outcomes differ"):
                benchmark.benchmark()


if __name__ == "__main__":
    unittest.main()
