"""Small synthetic module/identity/containment guards; no real keyword tests."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import keyword_modules as runner
import owned_process as owned


class KeywordModuleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="keyword-runner-test-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def source(self, name, body):
        (self.folder / (name + ".py")).write_bytes(body.encode("utf-8"))

    def run_suite(self, timeout=10):
        completed = owned.run_owned([sys.executable, "-B", str(Path(runner.__file__)),
                         "--supervised", "--suite", str(self.folder)], cwd=runner.ROOT, timeout=timeout)
        return completed, json.loads(completed.stdout)

    def test_two_real_workers_overlap_preserve_class_fixture_order_and_skip(self):
        for own, other in (("alpha", "beta"), ("beta", "alpha")):
            self.source("test_" + own, f'''import pathlib,time,unittest
ROOT=pathlib.Path({str(self.folder)!r})
class Cases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p=ROOT/{(own + '.setup')!r}
        p.write_bytes(p.read_bytes()+b'x' if p.exists() else b'x')
    def test_a_overlap(self):
        (ROOT/{own!r}).write_bytes(b'ready')
        end=time.monotonic()+4
        while not (ROOT/{other!r}).exists() and time.monotonic()<end: time.sleep(.01)
        self.assertTrue((ROOT/{other!r}).exists(), 'workers did not overlap')
    @unittest.skip('synthetic capability skip')
    def test_b_skip(self): pass
''')
        completed, report = self.run_suite()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(report["summary"], {"discovered_modules": 2, "completed_modules": 2,
            "discovered": 4, "started": 4, "finished": 4, "skipped": 2,
            "coverage_verified": True, "timed_out": False, "passed": True})
        self.assertEqual(report["workers"], 2)
        for name in ("alpha", "beta"):
            self.assertEqual((self.folder / (name + ".setup")).read_bytes(), b"x")
        self.assertTrue(all(item["coverage_verified"] for item in report["modules"]))

    def test_identity_coverage_rejects_duplicates_missing_unknown_order_and_outcomes(self):
        expected = ["module.Case.test_one", "module.Case.test_two"]
        events = [{"event": kind, "id": identity, **({"status": "passed"} if kind == "finish" else {})}
                  for identity in expected for kind in ("start", "finish")]
        self.assertTrue(runner.validate_coverage(expected, expected, events))
        bad = [events + [events[0]], events[:-1], list(reversed(events)),
               [{**event, "id": "UNKNOWN"} for event in events],
               [{**event, "status": "UNKNOWN"} for event in events],
               events + [{"event": "outcome", "id": expected[0]}]]
        for altered in bad:
            with self.subTest(events=altered):
                self.assertFalse(runner.validate_coverage(expected, expected, altered))
        self.assertFalse(runner.validate_coverage(expected + expected[:1], expected, events))
        self.assertFalse(runner.validate_coverage(expected, expected[:-1], events))

    def test_import_error_cannot_be_successful_discovery(self):
        self.source("test_broken", "raise RuntimeError('SYNTHETIC import error')\n")
        completed, report = self.run_suite()
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(report["summary"]["passed"])
        self.assertEqual(report["summary"]["error"], "DISCOVERY_OR_PROTOCOL_FAILURE")

    def test_class_setup_failure_preserves_unstarted_missing_cases(self):
        self.source("test_setup", '''import unittest
class Cases(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError('SYNTHETIC setup failure')
    def test_one(self): pass
    def test_two(self): pass
''')
        completed, report = self.run_suite()
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(report["summary"]["discovered"], 2)
        self.assertEqual(report["summary"]["started"], 0)
        self.assertFalse(report["summary"]["coverage_verified"])

    def test_crash_does_not_hide_started_unfinished_case(self):
        self.source("test_crash", '''import os,unittest
class Cases(unittest.TestCase):
    def test_one(self): os._exit(7)
''')
        completed, report = self.run_suite()
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(report["summary"]["started"], 1)
        self.assertEqual(report["summary"]["finished"], 0)
        self.assertFalse(report["summary"]["coverage_verified"])
        self.assertEqual(report["modules"][0]["exit"], 7)

    def test_subtest_failure_and_unexpected_success_are_failures_with_complete_coverage(self):
        self.source("test_outcomes", '''import unittest
class Cases(unittest.TestCase):
    def test_subtest(self):
        with self.subTest(label='synthetic'): self.assertEqual(1,2)
    @unittest.expectedFailure
    def test_unexpected_success(self): pass
''')
        completed, report = self.run_suite()
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(report["summary"]["coverage_verified"])
        self.assertFalse(report["summary"]["passed"])
        self.assertEqual(report["modules"][0]["outcomes"], {"failure": 1, "unexpected_success": 1})

    def test_inconsistent_success_receipt_cannot_hide_failure_outcome(self):
        identity = "test_synthetic.Cases.test_one"
        paths = {key: self.folder / key for key in ("stdout", "stderr", "events", "receipt")}
        for key in ("stdout", "stderr"):
            paths[key].write_bytes(b"")
        start = {"event": "start", "id": identity}
        finish = {"event": "finish", "id": identity, "status": "failure", "failures": 1,
                  "errors": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
        paths["events"].write_bytes(runner.encoded(start) + b"\n" + runner.encoded(finish) + b"\n")
        receipt = {"discovered": [identity], "successful": True, "tests_run": 1,
                   "failures": 0, "errors": 0, "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
        paths["receipt"].write_bytes(runner.encoded(receipt))
        result = runner.collect("test_synthetic", [identity], SimpleNamespace(returncode=0), paths)
        self.assertFalse(result["complete"])
        self.assertFalse(result["passed"])

    def test_status_specific_counts_cannot_claim_pass_skip_or_expected_failure(self):
        zero = {key: 0 for key in runner.COUNTS}
        for status, counts in (("passed", {"skipped": 1}), ("skipped", {}),
                               ("expected_failure", {}), ("failure", {"errors": 1}),
                               ("unexpected_success", {"unexpected_successes": 2})):
            with self.subTest(status=status):
                self.assertFalse(runner.consistent_outcome({"status": status, **zero, **counts}))

    def test_full_identity_receipts_are_unique_ignored_files_with_bound_digests(self):
        report = {"modules": [], "summary": {"passed": False}}
        with patch.object(runner, "ROOT", self.folder):
            first = runner.retain_report(report)
            second = runner.retain_report(report)
        self.assertNotEqual(first["evidence_file"], second["evidence_file"])
        for item in (first, second):
            blob = (self.folder / item["evidence_file"]).read_bytes()
            self.assertEqual(json.loads(blob), report)
            self.assertEqual(runner.hashlib.sha256(blob).hexdigest(), item["evidence_sha256"])

    def test_nested_cli_completes_before_suite_deadline(self):
        self.source("test_nested_complete", '''import subprocess,sys,unittest
class Cases(unittest.TestCase):
    def test_cli(self):
        result=subprocess.run([sys.executable,'-B','-c','print("synthetic")'],capture_output=True,check=True)
        self.assertEqual(result.stdout.strip(),b'synthetic')
''')
        completed, report = self.run_suite()
        self.assertEqual(completed.returncode, 0)
        self.assertTrue(report["summary"]["passed"])

    def test_supervised_runner_requires_gate_before_importing_test_module(self):
        marker = self.folder / "must-not-import"
        self.source("test_gate", f"from pathlib import Path\nPath({str(marker)!r}).write_bytes(b'bad')\n")
        completed = subprocess.run([sys.executable, "-B", str(Path(runner.__file__)),
            "--supervised", "--suite", str(self.folder)], cwd=runner.ROOT,
            input=b"{}\n", capture_output=True, timeout=5)
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse(marker.exists())

    def test_deadline_is_one_aggregate_bound_not_fresh_per_module(self):
        for name in ("one", "two", "three", "four"):
            self.source("test_" + name, "import time,unittest\nclass Cases(unittest.TestCase):\n    def test_wait(self): time.sleep(2)\n")
        tick = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired) as failure:
            self.run_suite(timeout=0.6)
        self.assertEqual(failure.exception.timeout, 0.6)
        self.assertLess(time.monotonic() - tick, 4)


class OwnedProcessTests(unittest.TestCase):
    def test_failed_job_assignment_never_releases_gate_and_reaps_child(self):
        job = Mock()
        job.assign.side_effect = owned.ContainmentError("synthetic assignment refused")
        process = Mock()
        process.poll.return_value = None
        with patch.object(owned, "IS_WINDOWS", True), patch.object(owned, "WindowsJob", return_value=job), \
                patch.object(owned.subprocess, "Popen", return_value=process):
            with self.assertRaises(owned.ContainmentError):
                owned.run_owned(["synthetic"], cwd="synthetic", timeout=300)
        process.communicate.assert_not_called()
        process.kill.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=5)
        job.close.assert_called_once_with()

    def test_failed_job_creation_never_starts_child(self):
        with patch.object(owned, "IS_WINDOWS", True), \
                patch.object(owned, "WindowsJob", side_effect=owned.ContainmentError("synthetic job refused")), \
                patch.object(owned.subprocess, "Popen") as child:
            with self.assertRaises(owned.ContainmentError):
                owned.run_owned(["synthetic"], cwd="synthetic", timeout=300)
        child.assert_not_called()

    def test_posix_owned_group_is_used_and_killed_even_after_success(self):
        process = Mock(pid=123, returncode=0)
        process.communicate.return_value = (b"complete", b"")
        process.poll.return_value = 0
        with patch.object(owned, "IS_WINDOWS", False), \
                patch.object(owned.subprocess, "Popen", return_value=process) as child, \
                patch.object(owned.os, "killpg", create=True) as killgroup:
            completed = owned.run_owned(["synthetic"], cwd="synthetic", timeout=300)
        self.assertTrue(child.call_args.kwargs["start_new_session"])
        self.assertTrue(child.call_args.kwargs["close_fds"])
        killgroup.assert_called_once_with(123, getattr(signal, "SIGKILL", 9))
        self.assertEqual(completed.stdout, "complete")
        gate = json.loads(process.communicate.call_args.kwargs["input"])
        self.assertEqual(gate["gate"], owned.GATE)

    def test_timeout_kills_group_and_cannot_accept_complete_looking_output(self):
        process = Mock(pid=123, returncode=0)
        process.communicate.side_effect = [subprocess.TimeoutExpired("synthetic", 300), (b'{"passed":true}', b"")]
        process.poll.return_value = 0
        with patch.object(owned, "IS_WINDOWS", False), \
                patch.object(owned.subprocess, "Popen", return_value=process), \
                patch.object(owned.os, "killpg", create=True) as killgroup:
            with self.assertRaises(subprocess.TimeoutExpired) as failure:
                owned.run_owned(["synthetic"], cwd="synthetic", timeout=300)
        self.assertEqual(failure.exception.timeout, 300)
        self.assertEqual(failure.exception.output, b'{"passed":true}')
        self.assertTrue(killgroup.called)

    def nested_child_cleanup(self, windows):
        with tempfile.TemporaryDirectory(prefix="keyword-nested-tree-") as temporary:
            folder = Path(temporary)
            marker = folder / "nested.pid"
            (folder / "test_nested.py").write_bytes(f'''import pathlib,subprocess,sys,time,unittest
class Cases(unittest.TestCase):
    def test_nested(self):
        child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
        pathlib.Path({str(marker)!r}).write_text(str(child.pid),encoding='ascii')
        child.wait()
'''.encode("utf-8"))
            outcomes = []
            def run():
                try:
                    owned.run_owned([sys.executable, "-B", str(Path(runner.__file__)),
                        "--supervised", "--suite", str(folder)], cwd=runner.ROOT, timeout=1.5)
                except BaseException as exc:
                    outcomes.append(exc)
            thread = threading.Thread(target=run)
            thread.start()
            handle = None
            try:
                deadline = time.monotonic() + 1.2
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(marker.exists(), "Synthetic nested child did not start")
                pid = int(marker.read_text(encoding="ascii"))
                if windows:
                    from ctypes import wintypes as w
                    api = ctypes.WinDLL("kernel32", use_last_error=True)
                    api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
                    api.OpenProcess.restype = w.HANDLE
                    api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
                    api.WaitForSingleObject.restype = w.DWORD
                    api.CloseHandle.argtypes = [w.HANDLE]
                    api.CloseHandle.restype = w.BOOL
                    handle = api.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
                    self.assertTrue(handle)
                    self.assertEqual(api.WaitForSingleObject(handle, 0), 258)  # WAIT_TIMEOUT
                thread.join(timeout=7)
                self.assertFalse(thread.is_alive())
                self.assertEqual(len(outcomes), 1)
                self.assertIsInstance(outcomes[0], subprocess.TimeoutExpired)
                if windows:
                    self.assertEqual(api.WaitForSingleObject(handle, 3000), 0)
                else:
                    # Linux may retain a killed orphan as a zombie briefly.
                    status = Path(f"/proc/{pid}/stat")
                    self.assertTrue(not status.exists() or status.read_text(encoding="ascii").split()[2] == "Z")
            finally:
                thread.join(timeout=7)
                if handle:
                    api.CloseHandle(handle)

    @unittest.skipUnless(os.name == "nt", "Windows job-object capability; requires Windows execution")
    def test_windows_outer_timeout_kills_nested_child_with_retained_process_handle(self):
        self.nested_child_cleanup(windows=True)

    @unittest.skipUnless(os.name == "nt", "Windows job-object capability; requires Windows execution")
    def test_windows_killed_supervisor_closes_job_and_kills_worker_and_grandchild(self):
        from ctypes import wintypes as w
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
        api.OpenProcess.restype = w.HANDLE
        api.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
        api.WaitForSingleObject.restype = w.DWORD
        api.CloseHandle.argtypes = [w.HANDLE]
        api.CloseHandle.restype = w.BOOL
        with tempfile.TemporaryDirectory(prefix="keyword-owner-death-") as temporary:
            folder = Path(temporary)
            marker = folder / "descendants.json"
            (folder / "test_descendants.py").write_bytes(f'''import json,os,pathlib,subprocess,sys,unittest
class Cases(unittest.TestCase):
    def test_descendants(self):
        child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(60)'])
        pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid]),encoding='ascii')
        child.wait()
'''.encode("utf-8"))
            script = ("import sys;sys.path.insert(0," + repr(str(Path(owned.__file__).parent)) + ");"
                      "from owned_process import run_owned;"
                      "run_owned(" + repr([sys.executable, "-B", str(Path(runner.__file__)), "--supervised", "--suite", str(folder)])
                      + ",cwd=" + repr(str(runner.ROOT)) + ",timeout=30)")
            supervisor = subprocess.Popen([sys.executable, "-B", "-c", script], stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
            handles = []
            try:
                deadline = time.monotonic() + 5
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(marker.exists(), "Synthetic job descendants did not start")
                for pid in json.loads(marker.read_text(encoding="ascii")):
                    handle = api.OpenProcess(0x00100000, False, pid)
                    self.assertTrue(handle)
                    handles.append(handle)
                    self.assertEqual(api.WaitForSingleObject(handle, 0), 258)
                supervisor.kill()
                supervisor.wait(timeout=5)
                for handle in handles:
                    self.assertEqual(api.WaitForSingleObject(handle, 3000), 0)
            finally:
                if supervisor.poll() is None:
                    supervisor.kill()
                    supervisor.wait(timeout=5)
                for handle in handles:
                    api.CloseHandle(handle)

    @unittest.skipUnless(os.name == "posix" and Path("/proc").exists(), "POSIX group cleanup requires Linux/native CI execution")
    def test_posix_outer_timeout_kills_nested_child(self):
        self.nested_child_cleanup(windows=False)


if __name__ == "__main__":
    unittest.main()
