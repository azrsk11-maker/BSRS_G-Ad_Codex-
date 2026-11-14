"""Synthetic binary parity and control-failure checks for the benchmark only."""
import copy
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

import benchmark_worktree as benchmark


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "core.autocrlf", "false")
        (self.root / "raw bytes.bin").write_bytes(b"\x00\xfforiginal\r\nbytes\n")
        (self.root / "duplicate.bin").write_bytes(b"\x00\xfforiginal\r\nbytes\n")
        self.git("add", ".")
        self.git("commit", "-qm", "Synthetic pinned raw bytes")
        self.commit = self.git("rev-parse", "HEAD").decode().strip()

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def test_full_binary_parity_and_measured_process_counts(self):
        deadline = time.perf_counter() + 30
        batch = benchmark.observed_run(self.root, self.commit, "existing_batch", deadline)
        baseline = benchmark.observed_run(self.root, self.commit, "constructed_per_file", deadline)
        for key in ("report", "report_sha256", "local_bytes_sha256", "git_bytes_sha256", "compared_bytes", "compared_files"):
            self.assertEqual(batch[key], baseline[key], key)
        self.assertEqual(batch["git_process_count"], 5)
        self.assertEqual(baseline["git_process_count"], 6)
        self.assertEqual(batch["unique_git_blob_bytes"] * 2, batch["compared_bytes"])
        self.assertEqual(baseline["git_command_counts"]["cat-file"], 2)

    def test_changed_raw_line_endings_cannot_establish_a_benchmark(self):
        (self.root / "raw bytes.bin").write_bytes(b"\x00\xfforiginal\nbytes\n")
        for method in ("existing_batch", "constructed_per_file"):
            with self.subTest(method=method), self.assertRaisesRegex(benchmark.BenchmarkError, "byte-equal"):
                benchmark.observed_run(self.root, self.commit, method, time.perf_counter() + 30)

    def test_input_change_between_methods_stops_before_another_pair(self):
        sample = {"compared_files": 2, "compared_bytes": 4, "local_bytes_sha256": "a", "git_bytes_sha256": "a",
                  "report_sha256": "b", "report": {"test_only": True}, "elapsed_seconds": 0.1, "git_process_count": 5}
        changed = copy.deepcopy(sample)
        changed["local_bytes_sha256"] = "c"
        with patch.object(benchmark, "observed_run", side_effect=[sample, changed]) as observed:
            with self.assertRaisesRegex(benchmark.BenchmarkError, "changed between runs"):
                benchmark.benchmark(self.root, self.commit)
        self.assertEqual(observed.call_count, 2)

    def test_deadline_and_report_overwrite_guard(self):
        with self.assertRaisesRegex(benchmark.BenchmarkError, "budget"):
            benchmark.observed_run(self.root, self.commit, "existing_batch", time.perf_counter() - 1)
        with self.assertRaisesRegex(benchmark.BenchmarkError, "never overwritten"):
            benchmark.report_destination(self.root, self.root / "raw bytes.bin")
        with self.assertRaisesRegex(benchmark.BenchmarkError, "ignored output"):
            benchmark.report_destination(self.root, self.root / "new-report.json")

    def test_git_call_that_exhausts_budget_cannot_return_a_pass(self):
        with patch.object(benchmark.verifier, "git", return_value=b""), patch.object(benchmark.time, "perf_counter", side_effect=[0, 0, 0, 2]):
            with self.assertRaisesRegex(benchmark.BenchmarkError, "budget"):
                benchmark.observed_run(self.root, self.commit, "existing_batch", 1)

    def test_explicit_full_ref_and_bounded_repetition_required(self):
        for ref, pairs, seconds in (("HEAD", 3, 180), (self.commit, 2, 180), (self.commit, 3, 601)):
            with self.subTest(ref=ref, pairs=pairs, seconds=seconds), self.assertRaises(benchmark.BenchmarkError):
                benchmark.benchmark(self.root, ref, pairs=pairs, max_seconds=seconds)


if __name__ == "__main__":
    unittest.main()
