"""Complete unittest modules in two contained processes, under one 300s bound.

No test verdict, source check, fixture or acceptance result is reused. Whole
modules retain ordinary unittest class fixtures/order. Discovery remains dynamic.
"""
import argparse
from collections import Counter, deque
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from owned_process import GATE, ContainmentError, run_owned


ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = 300
MAX_OUTPUT = 4_000_000
STATUSES = {"passed", "skipped", "subtest_skips", "failure", "error", "expected_failure", "unexpected_success"}
COUNTS = ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")


def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def discover(folder):
    loader = unittest.TestLoader()
    suite = loader.discover(str(folder), pattern="test_*.py")
    if loader.errors:
        raise ValueError("Test discovery failed")
    modules = {}
    for test in flatten(suite):
        modules.setdefault(type(test).__module__, []).append(test.id())
    ids = [identity for values in modules.values() for identity in values]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate discovered test identities")
    return modules


def validate_coverage(expected, discovered, events):
    """Require one ordered start/finish/outcome for every discovered test."""
    if not expected or len(expected) != len(set(expected)) or Counter(expected) != Counter(discovered):
        return False
    starts, finishes = [], []
    active = set()
    for event in events:
        if not isinstance(event, dict) or event.get("id") not in expected:
            return False
        identity = event["id"]
        if event.get("event") == "start":
            if identity in starts or active:
                return False
            starts.append(identity)
            active.add(identity)
        elif event.get("event") == "finish":
            if identity not in active or event.get("status") not in STATUSES:
                return False
            active.remove(identity)
            finishes.append(identity)
        else:
            return False
    return not active and starts == expected == finishes


def consistent_outcome(event):
    if any(type(event.get(key)) is not int or event[key] < 0 for key in COUNTS):
        return False
    status = event["status"]
    f, e, s, x, u = (event[key] for key in COUNTS)
    if status == "passed":
        return f == e == s == x == u == 0
    if status == "skipped":
        return s == 1 and f == e == x == u == 0
    if status == "subtest_skips":
        return s > 0 and f == e == x == u == 0
    if status == "expected_failure":
        return x == 1 and f == e == s == u == 0
    if status == "unexpected_success":
        return u == 1 and f == e == s == x == 0
    if status == "failure":
        return f > 0 and e == x == u == 0
    return status == "error" and e > 0 and x == u == 0


class ObservedResult(unittest.TextTestResult):
    def __init__(self, *args, events, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = events
        self.states = {}
        self.active_id = None

    def emit(self, value):
        self.events.write(encoded(value) + b"\n")
        self.events.flush()

    def startTest(self, test):
        super().startTest(test)
        self.active_id = test.id()
        self.states[test.id()] = {"status": "passed", "failures": 0, "errors": 0,
                                 "skipped": 0, "expected_failures": 0, "unexpected_successes": 0}
        self.emit({"event": "start", "id": test.id()})

    def stopTest(self, test):
        state = self.states[test.id()]
        if state["status"] == "passed" and state["skipped"]:
            state["status"] = "subtest_skips"
        self.emit({"event": "finish", "id": test.id(), **self.states[test.id()]})
        self.active_id = None
        super().stopTest(test)

    def addSkip(self, test, reason):
        identity = test.id() if test.id() in self.states else self.active_id
        if identity in self.states:
            state = self.states[identity]
            state["skipped"] += 1
            state.setdefault("skip_reasons", []).append(reason)
            if identity == test.id() and state["status"] == "passed":
                state["status"] = "skipped"
        super().addSkip(test, reason)

    def addFailure(self, test, err):
        state = self.states[test.id()]
        state["failures"] += 1
        if state["status"] != "error":
            state["status"] = "failure"
        super().addFailure(test, err)

    def addError(self, test, err):
        if test.id() in self.states:
            self.states[test.id()]["status"] = "error"
            self.states[test.id()]["errors"] += 1
        super().addError(test, err)

    def addExpectedFailure(self, test, err):
        self.states[test.id()]["status"] = "expected_failure"
        self.states[test.id()]["expected_failures"] += 1
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.states[test.id()]["status"] = "unexpected_success"
        self.states[test.id()]["unexpected_successes"] += 1
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            state = self.states[test.id()]
            kind = "failures" if issubclass(err[0], test.failureException) else "errors"
            state[kind] += 1
            state["status"] = "error" if state["errors"] else "failure"
        super().addSubTest(test, subtest, err)


def worker(folder, module, event_path, receipt_path):
    sys.path.insert(0, str(folder))
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module)
    discovered = [test.id() for test in flatten(suite)]
    with event_path.open("wb") as events:
        runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=1,
                    resultclass=lambda *a, **k: ObservedResult(*a, events=events, **k))
        result = runner.run(suite)
    receipt = {"discovered": discovered, "successful": result.wasSuccessful() and not loader.errors,
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
               "unexpected_successes": len(result.unexpectedSuccesses)}
    receipt_path.write_bytes(encoded(receipt) + b"\n")
    return 0 if receipt["successful"] else 1


def read_bounded(path):
    with path.open("rb") as stream:
        value = stream.read(MAX_OUTPUT + 1)
    if len(value) > MAX_OUTPUT:
        raise ValueError("Oversized worker evidence")
    return value


def collect(module, expected, process, paths):
    stdout, stderr = (read_bounded(paths[key]) for key in ("stdout", "stderr"))
    events = []
    receipt = {}
    try:
        events = [json.loads(line) for line in read_bounded(paths["events"]).splitlines()]
        receipt = json.loads(read_bounded(paths["receipt"]))
        coverage = validate_coverage(expected, receipt["discovered"], events)
        finishes = [event for event in events if event["event"] == "finish"]
        consistent = all(consistent_outcome(event) for event in finishes)
        consistent = consistent and all(type(receipt.get(key)) is int and
                         receipt[key] == sum(event[key] for event in finishes) for key in COUNTS)
        successful = not any(receipt[key] for key in ("failures", "errors", "unexpected_successes"))
        consistent = consistent and type(receipt.get("successful")) is bool and receipt["successful"] == successful
        complete = coverage and consistent and type(receipt["tests_run"]) is int and receipt["tests_run"] == len(expected)
        passed = complete and process.returncode == 0 and successful
    except (OSError, ValueError, KeyError, TypeError):
        coverage = complete = passed = False
    return {"module": module, "expected": expected, "events": events, "receipt": receipt,
            "exit": process.returncode, "coverage_verified": coverage, "complete": complete, "passed": passed,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "output_tail": (stdout + stderr)[-1800:].decode("utf-8", errors="replace")}


def run_modules(folder, deadline, workers=2):
    if workers not in (1, 2):
        raise ValueError("Only one or two module workers are allowed")
    folder = Path(folder).resolve(strict=True)
    expected = discover(folder)
    pending = deque(sorted(expected))
    active, results = {}, {}
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="keyword-modules-") as temporary:
        try:
            while pending or active:
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                while pending and len(active) < workers and time.monotonic() < deadline:
                    module = pending.popleft()
                    base = Path(temporary) / str(len(results) + len(active))
                    paths = {key: base.with_suffix("." + key) for key in ("stdout", "stderr", "events", "receipt")}
                    with paths["stdout"].open("wb") as stdout, paths["stderr"].open("wb") as stderr:
                        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
                            "--suite", str(folder), "--worker", module, "--events", str(paths["events"]),
                            "--receipt", str(paths["receipt"])], cwd=ROOT, stdin=subprocess.DEVNULL,
                            stdout=stdout, stderr=stderr, close_fds=True)
                    active[module] = (process, paths)
                for module, (process, paths) in list(active.items()):
                    if process.poll() is not None:
                        results[module] = collect(module, expected[module], process, paths)
                        del active[module]
                if pending or active:
                    time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        finally:
            for process, _ in active.values():
                if process.poll() is None:
                    process.kill()
            for process, _ in active.values():
                process.wait(timeout=5)
            for module, (process, paths) in active.items():
                results[module] = collect(module, expected[module], process, paths)
    ids = [identity for values in expected.values() for identity in values]
    finished = [event for result in results.values() for event in result["events"] if event.get("event") == "finish"]
    started = [event for result in results.values() for event in result["events"] if event.get("event") == "start"]
    complete = len(results) == len(expected) and all(r["complete"] for r in results.values())
    return {"version": 1, "workers": workers, "aggregate_timeout_seconds": TIMEOUT,
            "expected_ids_sha256": hashlib.sha256(encoded(ids)).hexdigest(),
            "modules": [results[name] for name in sorted(results)],
            "summary": {"discovered_modules": len(expected), "completed_modules": len(results),
                "discovered": len(ids), "started": len(started), "finished": len(finished),
                "skipped": sum(event.get("skipped", 0) for event in finished),
                "coverage_verified": complete, "timed_out": timed_out,
                "passed": complete and not timed_out and all(r["passed"] for r in results.values())}}


def public_report(report):
    """Keep complete identity/outcome checks internally; expose bounded metadata."""
    modules = []
    for item in report["modules"]:
        events = item["events"]
        finishes = [event for event in events if event.get("event") == "finish"]
        metadata = {key: item[key] for key in
                    ("module", "exit", "coverage_verified", "complete", "passed", "stdout_sha256", "stderr_sha256")}
        metadata.update(expected=len(item["expected"]), started=sum(e.get("event") == "start" for e in events),
                        finished=len(finishes), outcomes=dict(Counter(e["status"] for e in finishes)),
                        skipped=sum(e.get("skipped", 0) for e in finishes),
                        expected_ids_sha256=hashlib.sha256(encoded(item["expected"])).hexdigest(),
                        complete_events_sha256=hashlib.sha256(encoded(events)).hexdigest())
        if not item["passed"]:
            metadata["output_tail"] = item["output_tail"]
        modules.append(metadata)
    result = {**report, "modules": modules}
    if len(encoded(result)) > MAX_OUTPUT:
        raise ValueError("Oversized aggregate evidence")
    return result


def retain_report(report):
    """Unique ignored evidence, written once; never read for acceptance reuse."""
    body = encoded(report) + b"\n"
    if len(body) > MAX_OUTPUT:
        raise ValueError("Oversized complete aggregate evidence")
    public = public_report(report)
    directory = ROOT / "test-output"
    directory.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="wb", prefix="keyword-modules-", suffix=".json",
                                     dir=directory, delete=False) as stream:
        stream.write(body)
        filename = Path(stream.name).name
    public["evidence_file"] = "test-output/" + filename
    public["evidence_sha256"] = hashlib.sha256(body).hexdigest()
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "tools/keyword-system")
    parser.add_argument("--supervised", action="store_true")
    parser.add_argument("--worker")
    parser.add_argument("--events", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.suite, args.worker, args.events, args.receipt)
    if not args.supervised:
        try:
            completed = run_owned([sys.executable, "-B", str(Path(__file__).resolve()), "--supervised",
                                   "--suite", str(args.suite)], cwd=ROOT, timeout=TIMEOUT)
            sys.stdout.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            return completed.returncode
        except (ContainmentError, subprocess.TimeoutExpired):
            print(json.dumps({"summary": {"passed": False, "error": "CONTAINMENT_OR_TIMEOUT"}}))
            return 1
    try:
        # Nothing can discover/import tests or spawn descendants before this gate.
        gate = json.loads(sys.stdin.buffer.readline(512))
        deadline = gate["deadline"]
        if (gate.get("gate") != GATE or type(deadline) not in (int, float)
                or not math.isfinite(deadline) or deadline <= time.monotonic()):
            raise ValueError("Missing owned-tree startup gate")
        report = run_modules(args.suite, deadline)
        print(json.dumps(retain_report(report), ensure_ascii=True, separators=(",", ":")))
        return 0 if report["summary"]["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"summary": {"passed": False, "error": "DISCOVERY_OR_PROTOCOL_FAILURE"}}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
