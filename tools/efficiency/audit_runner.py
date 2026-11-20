"""Cache sanitized, bounded Codex log reports; never replay recorded commands.

Cache keys use file identity/metadata plus analyzer bytes and explicit options.
Use --refresh after an externally rewritten file with preserved metadata.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import codex_metrics

SCHEMA = "codex-audit-cache-v1"


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def fingerprint(paths, since, until, tail_bytes, max_line):
    sources = []
    for path in paths:
        stat = path.stat()
        sources.append({"path_sha256": hashlib.sha256(str(path).encode()).hexdigest(),
                        "device": stat.st_dev, "inode": stat.st_ino, "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns, "ctime_ns": stat.st_ctime_ns})
    return {"schema": SCHEMA, "sources": sources, "since": since.isoformat(),
            "until": until.isoformat(), "tail_bytes": tail_bytes, "max_line": max_line,
            "analyzer_sha256": hashlib.sha256(Path(codex_metrics.__file__).read_bytes()).hexdigest(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def report_view(result):
    report = codex_metrics.compact_summary(result)
    # Aggregate evidence only; do not copy path strings or raw input into cache.
    report["slowest_calls"] = result["slowest_calls"][:5]
    report["command_category_occurrences"] = result["shell"]["heuristic_category_occurrences"]
    report["most_repeated_command_groups"] = [
        {"calls": row["calls"], "categories": row["categories"]}
        for row in result["shell"]["top_exact_repeats"][:5]
    ]
    report["most_repeated_tool_groups"] = [
        {k: row[k] for k in ("tool", "calls", "call_to_output_latency_sum_seconds")}
        for row in result["tool_payload_repetition"]["top"][:5]
    ]
    return report


def run(paths, since, until, cache_dir, tail_bytes=8 * 1024 * 1024,
        max_line=32 * 1024 * 1024, refresh=False):
    started = time.perf_counter()
    paths = [Path(p).resolve(strict=True) for p in paths]
    if not paths or len(paths) != len(set(paths)) or any(not p.is_file() for p in paths):
        raise ValueError("Distinct regular files are required")
    if until < since or tail_bytes < 1 or max_line < 1:
        raise ValueError("Invalid audit bounds")
    before = fingerprint(paths, since, until, tail_bytes, max_line)
    key = hashlib.sha256(encode(before)).hexdigest()
    cache_file = Path(cache_dir) / (key + ".json")
    if not refresh and cache_file.is_file() and cache_file.stat().st_size <= 2 * 1024 * 1024:
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if (cached["schema"] == SCHEMA and cached["key"] == key
                    and cached["report_sha256"] == hashlib.sha256(encode(cached["report"])).hexdigest()
                    and before == fingerprint(paths, since, until, tail_bytes, max_line)):
                return {"report": cached["report"], "run": {
                    "cache_hit": True, "source_log_bytes_read_this_run": 0,
                    "elapsed_seconds": round(time.perf_counter() - started, 6),
                    "cache_written": False, "source_stable_during_run": True}}
        except (KeyError, ValueError, TypeError, OSError):
            pass  # Corrupt/incompatible cache is never treated as valid evidence.
    result = codex_metrics.analyze(paths, since, until, max_line, tail_bytes)
    report = report_view(result)
    stable = before == fingerprint(paths, since, until, tail_bytes, max_line)
    if stable:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        payload = {"schema": SCHEMA, "key": key, "report": report,
                   "report_sha256": hashlib.sha256(encode(report)).hexdigest()}
        temporary = cache_file.with_suffix(f".tmp-{os.getpid()}")
        temporary.write_bytes(encode(payload))
        temporary.replace(cache_file)
    return {"report": report, "run": {
        "cache_hit": False,
        "source_log_bytes_read_this_run": report["coverage"]["logical_bytes_read"],
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "cache_written": stable, "source_stable_during_run": stable}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--tail-mib", type=int, default=8)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        if not 1 <= args.tail_mib <= 1024:
            raise ValueError("Invalid tail bound")
        if args.report:
            output = args.report.resolve()
            inputs = [path.resolve() for path in args.files]
            if output in inputs or (output.exists() and any(output.samefile(path) for path in inputs)):
                raise ValueError("A report must never overwrite its source log")
        value = run(args.files, codex_metrics.instant(args.since), codex_metrics.instant(args.until),
                    args.cache_dir, tail_bytes=args.tail_mib * 1024 * 1024, refresh=args.refresh)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "OK", "run": value["run"],
                          "tool_calls": value["report"]["tool_calls"],
                          "report_written": bool(args.report)}))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"status": "ERROR", "error_type": type(error).__name__,
                          "detail": "Check explicit regular files, bounds and writable report/cache paths; no raw data emitted."}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
