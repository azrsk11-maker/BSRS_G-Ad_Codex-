"""Complete unittest modules in contained processes, under one 300s bound.

Whole modules retain unittest order and independent verdicts. A pinned pair
may share freshly verified history under single-worker scheduling.
"""
import argparse
from collections import Counter, deque
from contextlib import nullcontext, redirect_stderr, redirect_stdout
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
from keyword_history_reuse import BANK_MODULE, BANK_SAVED_CASE_ID, FRONT_MODULE, pair_sources_match, reuse_bank_history
from keyword_progress import Progress, read_diagnostic
from keyword_resources import select as select_workers


ROOT = Path(__file__).resolve().parents[2]
TIMEOUT = 300
MAX_OUTPUT = 4_000_000
STATUSES = {"passed", "skipped", "subtest_skips", "failure", "error", "expected_failure", "unexpected_success"}
COUNTS = ("failures", "errors", "skipped", "expected_failures", "unexpected_successes")
# Only scheduling hints from actual timing diagnostics; no verdict or source
# acceptance is reused. Every discovered module remains in the queue.
SLOW_MODULES = ('test_front_office_document_admission','test_bank_channel_login_admission',
    'test_ofqual_veterinary_admission','test_bank_support_admission',
    'test_ofqual_animal_care_admission','test_bank_credential_admission',
    'test_ofqual_occupational_admission','test_negative_library',
    'test_apprenticeship_admission','test_current_negative_library')


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


def worker(folder, module, event_path, receipt_path, *, bank_history=None):
    begin = time.perf_counter()
    sys.path.insert(0, str(folder))
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(module)
    discovered = [test.id() for test in flatten(suite)]
    context = nullcontext(False)
    if bank_history is not None and discovered == bank_history[1]:
        context = reuse_bank_history(folder, *bank_history)
    with context as reused, event_path.open("wb") as events:
        runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=1,
                    resultclass=lambda *a, **k: ObservedResult(*a, events=events, **k))
        result = runner.run(suite)
    receipt = {"discovered": discovered, "successful": result.wasSuccessful() and not loader.errors,
               "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
               "skipped": len(result.skipped), "expected_failures": len(result.expectedFailures),
               "unexpected_successes": len(result.unexpectedSuccesses),
               "elapsed_seconds": round(time.perf_counter() - begin, 6), "history_reused": reused}
    receipt_path.write_bytes(encoded(receipt) + b"\n")
    return 0 if receipt["successful"] else 1


def read_bounded(path):
    with path.open("rb") as stream:
        value = stream.read(MAX_OUTPUT + 1)
    if len(value) > MAX_OUTPUT:
        raise ValueError("Oversized worker evidence")
    return value


def collect(module, expected, returncode, paths):
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
        passed = complete and returncode == 0 and successful
    except (OSError, ValueError, KeyError, TypeError):
        coverage = complete = passed = False
    return {"module": module, "expected": expected, "events": events,
            "receipt": receipt if isinstance(receipt, dict) else {},
            "exit": returncode, "coverage_verified": coverage, "complete": complete, "passed": passed,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
            "output_tail": (stdout + stderr)[-1800:].decode("utf-8", errors="replace")}


def job_paths(base, module):
    return {key: base / f"{module}.{key}" for key in ("stdout", "stderr", "events", "receipt", "started")}


HISTORY_PAIR = (BANK_MODULE, FRONT_MODULE)


def bank_history_verified(bank):
    return (bank["passed"] and BANK_SAVED_CASE_ID in bank["expected"]
            and bank["receipt"]["skipped"] == bank["receipt"]["expected_failures"] == 0)


def history_pair_member(folder, base, module, *, bank_history=None):
    paths = job_paths(base, module)
    with paths["stdout"].open("w", encoding="utf-8") as stdout, paths["stderr"].open("w", encoding="utf-8") as stderr:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            paths["started"].write_bytes(encoded(time.perf_counter()))
            return worker(folder, module, paths["events"], paths["receipt"], bank_history=bank_history)


def history_pair_worker(folder, base):
    expected = json.loads(read_bounded(base / "expected.json"))
    if not isinstance(expected, dict) or set(expected) != set(HISTORY_PAIR) or not pair_sources_match(folder):
        raise ValueError("History pair inputs changed before startup")
    bank_paths = job_paths(base, BANK_MODULE)
    bank_exit = history_pair_member(folder, base, BANK_MODULE)
    bank = collect(BANK_MODULE, expected[BANK_MODULE], bank_exit, bank_paths)
    front_exit = history_pair_member(folder, base, FRONT_MODULE,
        bank_history=(bank_history_verified(bank), expected[FRONT_MODULE]))
    (base / "finished.json").write_bytes(encoded(dict(zip(HISTORY_PAIR, (bank_exit, front_exit)))))
    return int(bool(bank_exit or front_exit))


def scheduled_jobs(folder, expected, workers):
    order = sorted(expected, key=lambda name:
                   (SLOW_MODULES.index(name) if name in SLOW_MODULES else len(SLOW_MODULES), name))
    if (workers == 1 and folder == ROOT / "tools/keyword-system"
            and all(name in expected for name in HISTORY_PAIR) and pair_sources_match(folder)):
        return deque([HISTORY_PAIR, *((name,) for name in order if name not in HISTORY_PAIR)])
    return deque((name,) for name in order)


def collect_job(base, members, expected, returncode, elapsed):
    exit_codes = dict.fromkeys(members, returncode)
    if len(members) > 1:
        try:
            exits = json.loads(read_bounded(base / "finished.json"))
            if (not isinstance(exits, dict) or set(exits) != set(members)
                    or any(type(code) is not int or code not in (0, 1) for code in exits.values())
                    or returncode != int(any(exits.values()))):
                raise ValueError("Incomplete history pair")
            exit_codes = exits
        except (OSError, ValueError, TypeError):
            exit_codes = dict.fromkeys(members, returncode or -1)
    results = {}
    for name in members:
        paths = job_paths(base, name)
        result = collect(name, expected[name], exit_codes[name], paths)
        member_elapsed = result["receipt"].get("elapsed_seconds")
        result["elapsed_seconds"] = member_elapsed if (
            members == HISTORY_PAIR and type(member_elapsed) in (int, float) and 0 <= member_elapsed <= elapsed
        ) else elapsed
        results[name] = result
    if members == HISTORY_PAIR:
        front = results[FRONT_MODULE]
        if front["receipt"].get("history_reused") is True and not bank_history_verified(results[BANK_MODULE]):
            front["passed"] = False
    return results


def checkpoint(progress, expected, active, results, starts, *, force=False, status='RUNNING'):
    if progress is None or progress.disabled or (not force and not progress.due()):
        return
    now = time.perf_counter()
    rows = []
    for module in sorted(expected):
        events = []
        state = 'PENDING'
        elapsed = 0
        if module in results:
            result = results[module]
            events = result['events']
            state = 'COMPLETE' if result['complete'] else 'INCOMPLETE'
            elapsed = result['elapsed_seconds']
        elif module in active:
            state = 'ACTIVE'
            paths = active[module]
            start = starts[module]
            if paths.get('paired'):
                try:
                    observed = json.loads(read_bounded(paths['started']))
                    if type(observed) not in (int, float) or not start <= observed <= now:
                        raise ValueError("Invalid member start")
                    start = observed
                except (OSError, ValueError, TypeError):
                    state = 'PENDING'
            elapsed = round(now - start, 6) if state == 'ACTIVE' else 0
            path = paths['events']
            try:
                # Ignore a partially written final JSONL record; no verdict is read.
                body = read_bounded(path) if path.is_file() else b''
            except (OSError, ValueError):
                body = b''
            if body:
                for line in body.split(b'\n')[:-1]:
                    try:
                        event = json.loads(line)
                        if event.get('event') in ('start', 'finish'):
                            events.append(event)
                    except (ValueError, AttributeError):
                        pass
            if paths.get('paired') and state == 'ACTIVE':
                try:
                    observed = json.loads(read_bounded(paths['receipt'])).get('elapsed_seconds')
                    if type(observed) in (int, float) and 0 <= observed <= elapsed:
                        elapsed = observed
                        state = 'COMPLETE' if sum(e['event'] == 'finish' for e in events) == len(expected[module]) else 'INCOMPLETE'
                except (OSError, ValueError, TypeError, AttributeError):
                    pass
        rows.append({'module': module, 'state': state, 'expected': len(expected[module]),
                     'started': sum(e.get('event') == 'start' for e in events),
                     'finished': sum(e.get('event') == 'finish' for e in events),
                     'elapsed_seconds': elapsed})
    try:
        progress.write(rows, status)
    except (OSError, ValueError):
        # Diagnostics cannot change test selection, verdicts or process cleanup.
        # Do not repeatedly retry an inaccessible/oversized diagnostic file.
        progress.disabled = True


def run_modules(folder, deadline, workers='auto'):
    resources=select_workers(str(workers))
    workers=resources['selected_workers']
    folder = Path(folder).resolve(strict=True)
    expected = discover(folder)
    pending = scheduled_jobs(folder, expected, workers)
    jobs, active, results = {}, {}, {}
    starts = {}
    try:
        progress = Progress(ROOT)
    except (OSError, ValueError):
        progress = None
    checkpoint(progress, expected, active, results, starts, force=True)
    if progress is not None:
        print(progress.reference(), file=sys.stderr, flush=True)
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="keyword-modules-") as temporary:
        try:
            while pending or jobs:
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                while pending and len(jobs) < workers and time.monotonic() < deadline:
                    members = pending.popleft()
                    module = members[0]
                    base = Path(temporary) / str(len(results) + len(active))
                    base.mkdir()
                    paths = job_paths(base, module)
                    command = [sys.executable, "-B", str(Path(__file__).resolve()), "--suite", str(folder)]
                    if members == HISTORY_PAIR:
                        (base / "expected.json").write_bytes(encoded({name: expected[name] for name in members}))
                        command.extend(("--history-pair", str(base)))
                        for name in members:
                            member_paths = job_paths(base, name)
                            member_paths["stdout"].touch()
                            member_paths["stderr"].touch()
                        paths = job_paths(base, "pair")
                    else:
                        command.extend(("--worker", module, "--events", str(paths["events"]),
                                        "--receipt", str(paths["receipt"])))
                    now = time.perf_counter()
                    with paths["stdout"].open("wb") as stdout, paths["stderr"].open("wb") as stderr:
                        process = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                            stdout=stdout, stderr=stderr, close_fds=True)
                    jobs[base] = (process, members)
                    for name in members:
                        active[name] = job_paths(base, name)
                        active[name]["paired"] = members == HISTORY_PAIR
                        starts[name] = now
                    checkpoint(progress, expected, active, results, starts, force=True)
                for base, (process, members) in list(jobs.items()):
                    if process.poll() is not None:
                        elapsed = round(time.perf_counter() - starts[members[0]], 6)
                        results.update(collect_job(base, members, expected, process.returncode, elapsed))
                        for name in members:
                            del active[name]
                        del jobs[base]
                        checkpoint(progress, expected, active, results, starts, force=True)
                checkpoint(progress, expected, active, results, starts)
                if pending or jobs:
                    time.sleep(min(0.02, max(0, deadline - time.monotonic())))
        finally:
            for process, _ in jobs.values():
                if process.poll() is None:
                    process.kill()
            for process, _ in jobs.values():
                process.wait(timeout=5)
            for base, (process, members) in jobs.items():
                elapsed = round(time.perf_counter() - starts[members[0]], 6)
                results.update(collect_job(base, members, expected, process.returncode, elapsed))
            checkpoint(progress, expected, {}, results, starts, force=True,
                       status='TIMED_OUT' if timed_out else 'FINISHED')
    ids = [identity for values in expected.values() for identity in values]
    finished = [event for result in results.values() for event in result["events"] if event.get("event") == "finish"]
    started = [event for result in results.values() for event in result["events"] if event.get("event") == "start"]
    complete = len(results) == len(expected) and all(r["complete"] for r in results.values())
    return {"version": 1, "workers": workers, "worker_resources": resources, "aggregate_timeout_seconds": TIMEOUT,
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
        metadata['elapsed_seconds'] = item.get('elapsed_seconds')
        if item["receipt"].get("history_reused") is True:
            metadata["history_reused"] = True
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
    parser.add_argument("--history-pair", type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--workers',choices=('auto','1','2','3','4'),default='auto')
    parser.add_argument("--events", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(args.suite, args.worker, args.events, args.receipt)
    if args.history_pair:
        return history_pair_worker(args.suite, args.history_pair)
    if not args.supervised:
        try:
            completed = run_owned([sys.executable, "-B", str(Path(__file__).resolve()), "--supervised",
                                   "--suite", str(args.suite),'--workers',args.workers], cwd=ROOT, timeout=TIMEOUT)
            sys.stdout.write(completed.stdout)
            sys.stderr.write(completed.stderr)
            return completed.returncode
        except subprocess.TimeoutExpired as exc:
            diagnostic = read_diagnostic(ROOT, exc.stderr)
            print(json.dumps({'keyword_diagnostic': diagnostic}), file=sys.stderr)
            print(json.dumps({"summary": {"passed": False, "error": "CONTAINMENT_OR_TIMEOUT"}}))
            return 1
        except ContainmentError:
            print(json.dumps({"summary": {"passed": False, "error": "CONTAINMENT_OR_TIMEOUT"}}))
            return 1
    try:
        # Nothing can discover/import tests or spawn descendants before this gate.
        gate = json.loads(sys.stdin.buffer.readline(512))
        deadline = gate["deadline"]
        if (gate.get("gate") != GATE or type(deadline) not in (int, float)
                or not math.isfinite(deadline) or deadline <= time.monotonic()):
            raise ValueError("Missing owned-tree startup gate")
        report = run_modules(args.suite, deadline, workers=args.workers)
        print(json.dumps(retain_report(report), ensure_ascii=True, separators=(",", ":")))
        return 0 if report["summary"]["passed"] else 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"summary": {"passed": False, "error": "DISCOVERY_OR_PROTOCOL_FAILURE"}}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
