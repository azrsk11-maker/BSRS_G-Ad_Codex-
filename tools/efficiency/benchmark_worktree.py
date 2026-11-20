"""Measure existing Git batching against a constructed per-file baseline.

Both readers compare the same pinned complete working tree as raw bytes. This is
local efficiency evidence for an existing feature, not a new optimization or an
acceptance cache. No Git mutation, network, API or production action is performed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time
from unittest.mock import patch

import verify_worktree as verifier


class BenchmarkError(ValueError):
    """The paired comparison could not establish controlled evidence."""


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def digest_map(values):
    result = hashlib.sha256()
    for name, value in sorted(values.items()):
        result.update(len(name).to_bytes(4, "big"))
        result.update(name)
        result.update(value)
    return result.hexdigest()


def compare_per_file(root, ref, remote_hashes):
    """Constructed baseline: same discovery/guards, one Git process per path."""
    root = Path(root).resolve(strict=True)
    actual = Path(os.fsdecode(verifier.git(root, "rev-parse", "--show-toplevel").rstrip(b"\r\n"))).resolve()
    if actual != root:
        raise verifier.VerificationError("Choose the repository root for verification.")
    commit_bytes = verifier.git(root, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").strip()
    if not verifier.OBJECT_ID.fullmatch(commit_bytes):
        raise verifier.VerificationError("Invalid pinned commit.")
    commit = commit_bytes.decode("ascii")
    local = set(verifier.nul_records(verifier.git(root, "ls-files", "--cached", "--others", "--exclude-standard", "--full-name", "-z")))
    remote = verifier.tree_records(verifier.git(root, "ls-tree", "-rzl", "--full-tree", commit))
    shared = sorted(local & remote.keys())
    if sum(remote[name][1] for name in shared) > verifier.MAX_BATCH_BYTES:
        raise BenchmarkError("Full comparison exceeds the benchmark byte bound.")
    different = []
    for name in shared:
        object_id, size = remote[name]
        body = verifier.git(root, "cat-file", "blob", object_id.decode("ascii"))
        if len(body) != size:
            raise verifier.VerificationError("Unexpected Git blob size.")
        remote_hashes[object_id] = hashlib.sha256(body).digest()
        if verifier.local_hash(root, name) != remote_hashes[object_id]:
            different.append(name)
    return {
        "ref": ref, "commit": commit, "local_files": len(local), "remote_files": len(remote),
        "missing_remote": sorted(map(os.fsdecode, local - remote.keys())),
        "unexpected_remote": sorted(map(os.fsdecode, remote.keys() - local)),
        "different": sorted(map(os.fsdecode, different)),
        "byte_equal": len(shared) - len(different), "production_changes": False,
    }


def observed_run(root, ref, method, deadline):
    calls = []
    local_hashes, remote_hashes, tree = {}, {}, {}
    original_git, original_local, original_batch = verifier.git, verifier.local_hash, verifier.batch_hashes

    def observed_git(directory, *args, **kwargs):
        if time.perf_counter() >= deadline:
            raise BenchmarkError("Benchmark elapsed-time budget reached.")
        with patch.object(verifier, "GIT_TIMEOUT_SECONDS", min(verifier.GIT_TIMEOUT_SECONDS, deadline - time.perf_counter())):
            value = original_git(directory, *args, **kwargs)
        if time.perf_counter() >= deadline:
            raise BenchmarkError("Benchmark elapsed-time budget reached.")
        calls.append({"command": args[0], "stdout_bytes": len(value)})
        if args[:1] == ("ls-tree",):
            tree.update(verifier.tree_records(value))
        return value

    def observed_local(directory, name):
        value = original_local(directory, name)
        local_hashes[name] = value
        return value

    def observed_batch(data, objects):
        values = original_batch(data, objects)
        remote_hashes.update(values)
        return values

    tick = time.perf_counter()
    with patch.object(verifier, "git", observed_git), patch.object(verifier, "local_hash", observed_local), patch.object(verifier, "batch_hashes", observed_batch):
        report = (verifier.compare(root, ref) if method == "existing_batch" else
                  compare_per_file(root, ref, remote_hashes))
    elapsed = time.perf_counter() - tick
    if time.perf_counter() >= deadline:
        raise BenchmarkError("Benchmark elapsed-time budget reached.")
    remote_paths = {name: remote_hashes[tree[name][0]] for name in local_hashes}
    if report["missing_remote"] or report["unexpected_remote"] or report["different"] or report["byte_equal"] != report["remote_files"]:
        raise BenchmarkError("Benchmark requires the complete byte-equal pinned tree.")
    if digest_map(local_hashes) != digest_map(remote_paths):
        raise BenchmarkError("Local and Git byte digests differ.")
    return {
        "method": method, "elapsed_seconds": round(elapsed, 6),
        "git_process_count": len(calls),
        "git_stdout_bytes": sum(call["stdout_bytes"] for call in calls),
        "git_command_counts": {command: sum(call["command"] == command for call in calls) for command in sorted({call["command"] for call in calls})},
        "compared_files": len(local_hashes),
        "compared_bytes": sum(tree[name][1] for name in local_hashes),
        "unique_git_blob_bytes": sum({tree[name][0]: tree[name][1] for name in local_hashes}.values()),
        "local_bytes_sha256": digest_map(local_hashes),
        "git_bytes_sha256": digest_map(remote_paths),
        "report_sha256": hashlib.sha256(encoded(report)).hexdigest(), "report": report,
    }


def benchmark(root, ref, *, pairs=3, max_seconds=180, progress=None):
    if not 3 <= pairs <= 7 or not 1 <= max_seconds <= 600:
        raise BenchmarkError("Use three to seven pairs and a bounded time budget.")
    root = Path(root).resolve(strict=True)
    if not verifier.OBJECT_ID.fullmatch(ref.encode("ascii")):
        raise BenchmarkError("Use an explicit full pinned commit ID.")
    started = time.perf_counter()
    deadline = started + max_seconds
    source_before = {"benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                     "verifier_sha256": hashlib.sha256(Path(verifier.__file__).read_bytes()).hexdigest()}
    warmup = observed_run(root, ref, "existing_batch", deadline)
    expected = {key: warmup[key] for key in ("compared_files", "compared_bytes", "local_bytes_sha256", "git_bytes_sha256", "report_sha256", "report")}
    if progress:
        progress({"phase": "warmup_complete", "seconds": warmup["elapsed_seconds"], "files": warmup["compared_files"]})
    trials = []
    for index in range(pairs):
        order = ["constructed_per_file", "existing_batch"] if index % 2 == 0 else ["existing_batch", "constructed_per_file"]
        runs = []
        for method in order:
            run = observed_run(root, ref, method, deadline)
            if any(run[key] != value for key, value in expected.items()):
                raise BenchmarkError("Inputs or full comparison reports changed between runs.")
            runs.append(run)
            if progress:
                progress({"phase": "trial_complete", "pair": index + 1, "method": method,
                          "seconds": run["elapsed_seconds"], "git_processes": run["git_process_count"]})
        trials.append({"pair": index + 1, "order": order, "runs": runs})
    source_after = {"benchmark_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    "verifier_sha256": hashlib.sha256(Path(verifier.__file__).read_bytes()).hexdigest()}
    if source_before != source_after:
        raise BenchmarkError("Benchmark or verifier source changed during measurement.")
    if time.perf_counter() >= deadline:
        raise BenchmarkError("Benchmark elapsed-time budget reached.")
    medians = {method: statistics.median(run["elapsed_seconds"] for trial in trials for run in trial["runs"] if run["method"] == method)
               for method in ("constructed_per_file", "existing_batch")}
    return {
        "schema_version": 1, "measured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "scope": "CONTROLLED_LOCAL_REMEASUREMENT_OF_EXISTING_BATCHING_NOT_NEW_IMPLEMENTATION",
        "baseline": "Constructed same-guard per-path Git cat-file blob reader; not a recovered historical implementation.",
        "reference_commit": ref, "sources": source_before,
        "environment": {"platform": platform.system(), "python_version": platform.python_version()},
        "warmup": warmup, "pairs": trials, "all_full_reports_and_byte_digests_equal": True,
        "medians_seconds": medians,
        "median_ratio": round(medians["constructed_per_file"] / medians["existing_batch"], 6),
        "median_difference_seconds": round(medians["constructed_per_file"] - medians["existing_batch"], 6),
        "benchmark_elapsed_seconds": round(time.perf_counter() - started, 6),
        "limits": [
            "One Windows checkout and one pinned full tree; three or more alternating warmed pairs, not a population estimate.",
            "Comparators execute in the same Python process; timings include actual Git subprocesses, byte guards and digest observation, but exclude the outer tool/Python startup.",
            "One existing-batch warmup reads all files and Git objects before measured pairs; no cold-start claim is made.",
            "Git stdout bytes include metadata and framing; compared_bytes counts raw bytes per shared path, including duplicate blob content.",
            "Process counts are measured local Git invocations, not provider API requests; no network, API, production or authorization changes occur.",
            "No token, billing, whole-project or newly implemented optimization saving is established.",
        ],
    }


def report_destination(root, path):
    root, path = Path(root).resolve(strict=True), Path(path).resolve()
    if path.exists():
        raise BenchmarkError("Choose a new report file; existing files are never overwritten.")
    if path.is_relative_to(root):
        relative = path.relative_to(root)
        if relative.parts[0] not in {"test-output", ".cache"}:
            raise BenchmarkError("A report inside the checked tree must use an ignored output directory.")
        result = subprocess.run(["git", "check-ignore", "--quiet", "--", relative.as_posix()], cwd=root, capture_output=True, timeout=10, check=False)
        if result.returncode:
            raise BenchmarkError("Report destination must be ignored by Git.")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--ref", required=True)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = report_destination(args.root, args.report)
        result = benchmark(args.root, args.ref, pairs=args.pairs, max_seconds=args.max_seconds,
                           progress=lambda value: print(json.dumps(value), flush=True))
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(json.dumps(result, indent=2).encode("utf-8") + b"\n")
        print(json.dumps({"status": "PASS", "pairs": args.pairs, "files": result["warmup"]["compared_files"],
                          "medians_seconds": result["medians_seconds"], "median_ratio": result["median_ratio"]}))
        return 0
    except (BenchmarkError, verifier.VerificationError, OSError, UnicodeError, subprocess.SubprocessError):
        print(json.dumps({"status": "ERROR", "detail": "No controlled benchmark established; check pinned tree, stable bytes, output path and time budget."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
