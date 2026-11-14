"""Opt-in serial/2-worker experiment for two fixed offline Foundation checks.

This never changes the Foundation runner, its selection, or its 120s bounds.
The only writes made by the checks are unique synthetic OS temporary fixtures.
No report writer, acceptance cache, production action, or network client exists.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
OWN_FILES = {
    "tools/efficiency/benchmark_check_groups.py",
    "tools/efficiency/test_benchmark_check_groups.py",
    "tools/efficiency/check-group-concurrency-2026-11-11.json",
}
CHECKS = (
    {"name": "keyword-vendor-review-reconciliation", "kind": "json",
     "args": ["-B", "docs/audit/keyword-vendor-review-coverage-2026-11-11/verify_coverage.py"]},
    {"name": "release-control-behavior", "kind": "unittest",
     "args": ["-B", "-m", "unittest", "discover", "-s", "tools/release-control", "-p", "test_*.py"]},
)
TIMEOUT_SECONDS = 120  # Exact existing bound for both selected Foundation checks.
UNITTEST_TIME = re.compile(rb"(?m)^(Ran [0-9]+ tests? in )[0-9]+(?:\.[0-9]+)?(s\r?$)")
UNITTEST_END = re.compile(rb"Ran ([0-9]+) tests? in [0-9]+(?:\.[0-9]+)?s\r?\n\r?\n(OK(?: \(skipped=([0-9]+)\))?)\r?\n\Z")


class BenchmarkError(ValueError):
    """No complete controlled comparison was established."""


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def source_snapshot(root):
    """Hash all nonignored source, not just guessed transitive dependencies."""
    names = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=True, timeout=10,
    ).stdout.split(b"\0")
    entries, total = [], 0
    for name in sorted(set(names) - {b""}):
        relative = os.fsdecode(name)
        if relative in OWN_FILES:
            continue
        target = root / relative
        if target.is_symlink() or not target.is_file():
            raise BenchmarkError("Source paths must remain ordinary existing files.")
        body = target.read_bytes()
        total += len(body)
        entries.append([relative, len(body), sha256(body)])
    observers = {name: sha256((root / name).read_bytes()) for name in sorted(OWN_FILES)
                 if name.endswith(".py")}
    return {"files": len(entries), "bytes": total, "source_manifest_sha256": sha256(encoded(entries)),
            "observer_sha256": observers, "python_executable_sha256": sha256(Path(sys.executable).read_bytes())}


def command(check, root):
    # Match Foundation's absolute script/discovery paths without shell parsing.
    args = [str(root / value) if value.startswith(("docs/", "tools/")) else value for value in check["args"]]
    return [sys.executable, *args]


def outcome(check, returncode, stdout, stderr):
    """Compare complete evidence; normalize only unittest's elapsed number."""
    if check["kind"] == "json":
        try:
            summary = json.loads(stdout.decode("utf-8"))
        except (UnicodeError, ValueError):
            raise BenchmarkError("Missing complete JSON outcome.") from None
        if not isinstance(summary, dict) or summary.get("passed") is not True:
            raise BenchmarkError("Selected JSON check did not pass.")
        normalized_stdout, normalized_stderr = stdout, stderr
    elif check["kind"] == "unittest":
        match = UNITTEST_END.search(stderr)
        if not match or int(match[1]) < 1 or len(UNITTEST_TIME.findall(stderr)) != 1:
            raise BenchmarkError("Missing complete successful unittest outcome.")
        summary = {"tests": int(match[1]), "skipped": int(match[3] or 0), "failures": 0, "errors": 0,
                   "status": match[2].decode("ascii")}
        normalized_stdout = stdout
        normalized_stderr = UNITTEST_TIME.sub(rb"\1<elapsed>\2", stderr)
    else:
        raise BenchmarkError("Unknown evidence kind.")
    if returncode != 0:
        raise BenchmarkError("Selected check returned a failing exit code.")
    return {"exit": returncode, "summary": summary,
            "complete_stdout_normalized_sha256": sha256(normalized_stdout),
            "complete_stderr_normalized_sha256": sha256(normalized_stderr)}


def run_command(check, root):
    tick = time.perf_counter()
    try:
        result = subprocess.run(command(check, root), cwd=root, capture_output=True,
                                check=False, timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        raise BenchmarkError("Selected check exceeded its unchanged 120s bound.") from None
    except OSError:
        raise BenchmarkError("Selected check could not start.") from None
    elapsed = time.perf_counter() - tick
    if len(result.stdout) + len(result.stderr) > 4_000_000:
        raise BenchmarkError("Unexpectedly large complete check output.")
    evidence = outcome(check, result.returncode, result.stdout, result.stderr)
    return {"check": check["name"], "elapsed_seconds": round(elapsed, 6),
            "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr),
            "complete_stdout_sha256": sha256(result.stdout), "complete_stderr_sha256": sha256(result.stderr),
            "outcome": evidence}


def run_phase(root, workers):
    if workers not in (1, 2):
        raise BenchmarkError("Only serial and two-worker phases are supported.")
    tick = time.perf_counter()
    if workers == 1:
        runs = [run_command(check, root) for check in CHECKS]
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run_command, check, root) for check in CHECKS]
            # Submission order is evidence order even if completion is reversed.
            runs = [future.result() for future in futures]
    return {"workers": workers, "elapsed_seconds": round(time.perf_counter() - tick, 6), "runs": runs}


def benchmark(root=ROOT, progress=None):
    root = Path(root).resolve(strict=True)
    tick = time.perf_counter()
    before = source_snapshot(root)
    serial = run_phase(root, 1)
    after_serial = source_snapshot(root)
    if before != after_serial:
        raise BenchmarkError("Source changed during serial measurement; concurrent phase not started.")
    if progress:
        progress({"phase": "serial_complete", "elapsed_seconds": serial["elapsed_seconds"]})
    concurrent = run_phase(root, 2)
    after = source_snapshot(root)
    if before != after:
        raise BenchmarkError("Source changed during concurrent measurement.")
    if [r["outcome"] for r in serial["runs"]] != [r["outcome"] for r in concurrent["runs"]]:
        raise BenchmarkError("Complete check outcomes differ between phases.")
    delta = serial["elapsed_seconds"] - concurrent["elapsed_seconds"]
    return {
        "schema_version": 1,
        "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "scope": "OPT_IN_TWO_CHECK_EXPERIMENT_NOT_FOUNDATION_ADOPTION_OR_ACCEPTANCE",
        "environment": {"platform": platform.system(), "python_version": platform.python_version(),
                        "logical_cpu_count": os.cpu_count()},
        "commands": [{"check": c["name"], "argv": ["$PYTHON", *c["args"]], "timeout_seconds": TIMEOUT_SECONDS,
                      "fingerprint_sha256": sha256(encoded(["$PYTHON", *c["args"]]))} for c in CHECKS],
        "source_before": before, "source_after_serial": after_serial, "source_after": after,
        "phases": [serial, concurrent], "all_complete_outcomes_equal": True,
        "observed_difference_seconds": round(delta, 6),
        "observed_serial_over_two_worker_ratio": round(serial["elapsed_seconds"] / concurrent["elapsed_seconds"], 6),
        "benchmark_elapsed_seconds": round(time.perf_counter() - tick, 6),
        "foundation_default_changed": False, "production_changed": False, "advertising_changed": False,
        "limitations": [
            "One ordered pair only: serial first, two workers second. Source hashing and serial execution warm filesystem/OS caches; no cold-start or causal estimate.",
            "Same unchanged complete nonignored source in one Windows checkout. Observer files are separately pinned; receipt is excluded from source manifest.",
            "Only two existing checks were rerun, each at its existing 120s timeout. No skipped check, acceptance cache or timeout increase.",
            "Complete stdout/stderr and exit outcomes must match; only the anchored unittest elapsed number is normalized. Test/skip/failure counts are retained.",
            "Vendor reconciliation reads public pinned inputs; release tests write unique OS temporary synthetic fixtures and invoke the stdin-only local Node validator.",
            "Times include selected Python startup and Node child work. CPU load, scheduling, contention, filesystem temperature and Node binary stability are not measured or controlled.",
            "Four top-level check invocations; descendant Node process count is unavailable. Snapshot overhead is excluded from phase times but included in total benchmark time.",
            "No full Foundation, largest keyword-suite, token, API, billing, production, network or general concurrency benefit is established. No automatic adoption.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="explicitly execute this one serial/2-worker pair")
    args = parser.parse_args(argv)
    if not args.run:
        parser.error("Opt in with --run; importing this module runs no checks.")
    try:
        result = benchmark(progress=lambda event: print(json.dumps(event), file=sys.stderr, flush=True))
        print(json.dumps(result, indent=2))
        return 0
    except (BenchmarkError, OSError, subprocess.SubprocessError):
        print(json.dumps({"status": "ERROR", "controlled_comparison_established": False,
                          "detail": "Check execution, complete outcomes or stable-source guard failed."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
