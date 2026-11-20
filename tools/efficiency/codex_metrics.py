"""Read explicit Codex JSONL files; emit sanitized, time-bounded aggregates only.

No APIs, configuration changes, raw commands, tool payloads, prompts or outputs.
Usage: python -B tools/codex_metrics.py --since ISO --until ISO session.jsonl [...]
"""
from __future__ import annotations

import argparse
import ast
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import time
import warnings

UTC = dt.timezone.utc
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
              "output_tokens", "reasoning_output_tokens", "total_tokens")
FAILURES = {
    "timeout": r"timed out|TimeoutError|ETIMEDOUT|ERR_CONNECTION_TIMED_OUT",
    "syntax": r"SyntaxError|ParseError|unexpected token",
    "missing_or_long_path": r"FileNotFoundError|WinError [23]\b|cannot find path|path.{0,40}too long",
    "type_or_key": r"TypeError|KeyError|JSONDecodeError",
    "stale_or_unattached": r"Debugger.{0,20}unattached|stale.{0,20}(?:tab|handle)|TargetClosed",
    "truncation": r"output truncated|tokens truncated|truncated due",
}


def instant(value: str) -> dt.datetime:
    if not isinstance(value, str):
        raise ValueError("timestamps must be strings")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps require an explicit timezone")
    return parsed.astimezone(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", "replace")).hexdigest()[:16]


def safe_name(value: object) -> str:
    s = str(value or "unknown")
    return s if re.fullmatch(r"[A-Za-z0-9_./:-]{1,120}", s) else "opaque-" + digest(s)


def numeric_tokens(value: object) -> dict:
    if not isinstance(value, dict):
        return {}
    return {k: value[k] for k in TOKEN_KEYS
            if type(value.get(k)) is int and value[k] >= 0}


def stats(values: list[float]) -> dict:
    if not values:
        return {"count": 0}
    ordered = sorted(values)
    return {"count": len(values), "sum_seconds": round(sum(values), 3),
            "median_seconds": round(statistics.median(values), 3),
            "p95_nearest_rank_seconds": round(ordered[max(0, (95 * len(ordered) + 99) // 100 - 1)], 3),
            "max_seconds": round(ordered[-1], 3)}


def output_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(output_text(x) for x in value)
    if isinstance(value, dict):
        # Do not stringify image/base64/resource payloads or unrelated metadata.
        if isinstance(value.get("text"), str):
            return value["text"]
        return output_text(value.get("content", []))
    return ""


def js_mask(code: str) -> str:
    """Mask comments/string contents, retaining offsets and punctuation outside."""
    chars = list(code)
    i = 0
    while i < len(code):
        if code.startswith("//", i):
            end = code.find("\n", i)
            end = len(code) if end < 0 else end
        elif code.startswith("/*", i):
            end = code.find("*/", i + 2)
            end = len(code) if end < 0 else end + 2
        elif code[i] in "\"'`":
            quote = code[i]
            end = i + 1
            while end < len(code):
                if code[end] == "\\":
                    end += 2
                elif code[end] == quote:
                    end += 1
                    break
                else:
                    end += 1
        else:
            i += 1
            continue
        chars[i:end] = " " * (end - i)
        i = end
    return "".join(chars)


def literal_string(code: str, start: int) -> str | None:
    if start >= len(code) or code[start] not in "\"'`":
        return None
    quote = code[start]
    end = start + 1
    while end < len(code):
        if code[end] == "\\":
            end += 2
        elif code[end] == quote:
            token = code[start:end + 1]
            try:
                if quote == '"':
                    return json.loads(token)
                if quote == "'":
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        result = ast.literal_eval(token)
                    return result if isinstance(result, str) else None
                # Template substitution is intentionally unresolved, never evaluated.
                return None
            except (ValueError, SyntaxError, json.JSONDecodeError):
                return None
        else:
            end += 1
    return None


def nested_tools(code: str) -> list[tuple[str, str | None]]:
    """Static calls only. Dynamic names/variables/template expressions stay unresolved."""
    masked = js_mask(code)
    results = []
    for match in re.finditer(r"\btools\.([A-Za-z0-9_]+)\s*\(", masked):
        start = match.end()
        depth = 1
        end = start
        while end < len(masked) and depth:
            depth += (masked[end] == "(") - (masked[end] == ")")
            end += 1
        args = code[start:max(start, end - 1)]
        command = None
        if match.group(1) == "exec_command":
            # Resolve a literal cmd property only, without executing JavaScript.
            prop = re.search(r"(?:^|[,{}])\s*(?:cmd|\"cmd\"|'cmd')\s*:\s*", args)
            if prop:
                command = literal_string(args, prop.end())
        results.append((match.group(1), command))
    return results


def command_categories(command: str) -> list[str]:
    bounded_reader = r"(?<![\w.-])read_(?:memory|json)\.py(?![\w.-])"
    checks = {
        "search": r"\brg\b|\bSelect-String\b|\bgrep\b",
        "inventory": r"Get-ChildItem|\brg\s+--files|\brglob\(|\bglob\(",
        "read": r"Get-Content|read_bytes\(|read_text\(|open\([^\n]*[\"']r|" + bounded_reader,
        "bounded_read_candidate": bounded_reader,
        "hash_or_archive": r"Get-FileHash|sha256|ZipFile|zipfile|testzip",
        "syntax_check": r"node\s+--check|php[^\n]*\s-l\b|\bast\.parse|compileall",
        "test_runner_candidate": r"\bpytest\b|node\s+--test|python[^\n]*\s-m\s+unittest|run-combined|tests[/\\]run\.ps1",
        "inline_python": r"python[^\n]*\s-c\s",
        "package_builder_candidate": r"build[_-](?:checkpoint|context|package)|assemble_verified_delivery",
    }
    return [name for name, pattern in checks.items() if re.search(pattern, command, re.I)] or ["other"]


def analyze(paths: list[Path], since: dt.datetime, until: dt.datetime, max_line: int,
            tail_bytes: int | None = None) -> dict:
    if tail_bytes is not None and (type(tail_bytes) is not int or tail_bytes < 1):
        raise ValueError("tail bound must be a positive integer")
    calls = {}
    file_reports = []
    usage = {}
    usage_no_response_id = 0
    counters = collections.Counter()
    token_count = {}
    for index, path in enumerate(paths):
        file_key = str(index)
        snapshot_size = path.stat().st_size
        start = max(0, snapshot_size - tail_bytes) if tail_bytes is not None else 0
        consumed = start
        fr = {"path": str(path), "snapshot_bytes": snapshot_size, "lines_scanned": 0,
              "window_records": 0, "malformed_json": 0, "oversize_lines_skipped": 0,
              "partial_final_line_skipped": 0, "partial_initial_line_skipped": 0,
              "prefix_bytes_omitted": start, "logical_bytes_read": 0,
              "tail_limit_bytes": tail_bytes}
        with path.open("rb") as source:
            source.seek(start)
            if start:
                # One preceding byte preserves a record exactly on the boundary.
                source.seek(start - 1)
                preceding = source.read(1)
                if preceding != b"\n":
                    fr["partial_initial_line_skipped"] = 1
                    while consumed < snapshot_size:
                        fragment = source.readline(min(65536, snapshot_size - consumed))
                        if not fragment:
                            break
                        consumed += len(fragment)
                        if fragment.endswith(b"\n"):
                            break
            while consumed < snapshot_size:
                line = source.readline(min(max_line + 1, snapshot_size - consumed))
                if not line:
                    break
                consumed += len(line)
                if len(line) > max_line and not line.endswith(b"\n"):
                    fr["oversize_lines_skipped"] += 1
                    while consumed < snapshot_size and not line.endswith(b"\n"):
                        line = source.readline(min(1024 * 1024, snapshot_size - consumed))
                        consumed += len(line)
                    continue
                if not line.endswith(b"\n"):
                    fr["partial_final_line_skipped"] += 1
                    continue
                fr["lines_scanned"] += 1
                try:
                    # Fast timestamp filter avoids parsing huge out-of-window payloads.
                    head = re.match(rb'\s*\{\s*"timestamp"\s*:\s*"([^"\r\n]+)"', line[:200])
                    if head and not since <= instant(head.group(1).decode("ascii")) <= until:
                        continue
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("event must be an object")
                    when = instant(event.get("timestamp", ""))
                except (ValueError, TypeError, UnicodeError, json.JSONDecodeError):
                    fr["malformed_json"] += 1
                    continue
                if not since <= when <= until:
                    continue
                fr["window_records"] += 1
                payload = event.get("payload", {})
                if not isinstance(payload, dict):
                    continue
                kind = payload.get("type")
                if event.get("type") == "token_usage_record":
                    response = payload.get("response_id")
                    if isinstance(response, str) and response:
                        usage[(file_key, response)] = numeric_tokens(payload.get("usage"))
                    else:
                        usage_no_response_id += 1
                if event.get("type") == "event_msg" and kind == "token_count":
                    info = payload.get("info") or {}
                    if isinstance(info, dict):
                        tc = token_count.setdefault(file_key, {"records": 0, "first_total": {}, "last_total": {}})
                        tc["records"] += 1
                        total = numeric_tokens(info.get("total_token_usage"))
                        if total:
                            if not tc["first_total"]:
                                tc["first_total"] = total
                            tc["last_total"] = total
                if event.get("type") != "response_item":
                    continue
                call_id = payload.get("call_id")
                if not isinstance(call_id, str):
                    continue
                key = (file_key, call_id)
                if kind in ("function_call", "custom_tool_call"):
                    name = safe_name(payload.get("name"))
                    namespace = safe_name(payload.get("namespace")) if payload.get("namespace") else ""
                    tool = (namespace + "." if namespace else "") + name
                    raw = payload.get("input", payload.get("arguments", ""))
                    raw = raw if isinstance(raw, str) else json.dumps(raw, sort_keys=True)
                    nested = nested_tools(raw) if kind == "custom_tool_call" and name == "exec" else []
                    shell = [cmd for nested_name, cmd in nested if nested_name == "exec_command"]
                    if name == "exec_command":
                        try:
                            obj = json.loads(raw)
                            shell = [obj.get("cmd") if isinstance(obj.get("cmd"), str) else None]
                        except (ValueError, AttributeError):
                            shell = [None]
                    calls[key] = {"tool": tool, "start": when, "signature": digest(raw),
                                  "ref": digest(file_key + call_id), "nested": nested,
                                  "shell": shell, "input_chars": len(raw)}
                elif kind in ("function_call_output", "custom_tool_call_output"):
                    call = calls.get(key)
                    if call is None:
                        counters["outputs_without_window_call"] += 1
                        continue
                    text = output_text(payload.get("output"))
                    call["duration"] = max(0.0, (when - call["start"]).total_seconds())
                    call["output_chars"] = len(text)
                    call["output_utf8_escaped"] = False
                    try:
                        call["output_utf8_bytes"] = len(text.encode("utf-8"))
                    except UnicodeEncodeError:
                        call["output_utf8_bytes"] = len(text.encode("utf-8", errors="backslashreplace"))
                        call["output_utf8_escaped"] = True
                    call["markers"] = [label for label, pattern in FAILURES.items() if re.search(pattern, text, re.I)]
                    call["nonzero_exit_marker"] = bool(re.search(r'(?:Process exited with code\s+|"exit_code"\s*:\s*)(?:-[1-9]\d*|[1-9]\d*)\b', text))
                    explicit = re.findall(r'(?i)Wall time:\s*([0-9.]+)\s*seconds|"wall_time_seconds"\s*:\s*([0-9.]+)', text)
                    call["reported_seconds"] = [float(a or b) for a, b in explicit]
            fr["logical_bytes_read"] = source.tell() - start + (1 if start else 0)
        file_reports.append(fr)
    tools = collections.defaultdict(lambda: {"calls": 0, "durations": [], "reported_seconds": [], "output_chars": 0, "markers": collections.Counter()})
    nested_counts = collections.Counter()
    shell_categories = collections.Counter()
    shell_repeats = collections.defaultdict(list)
    repeats = collections.defaultdict(list)
    shell_durations = []
    literal_shell = unresolved_shell = 0
    slow = []
    for call in calls.values():
        t = tools[call["tool"]]
        t["calls"] += 1
        t["output_chars"] += call.get("output_chars", 0)
        t["reported_seconds"].extend(call.get("reported_seconds", []))
        t["markers"].update(call.get("markers", []))
        t["markers"]["nonzero_exit_lexical"] += int(call.get("nonzero_exit_marker", False))
        if "duration" in call:
            t["durations"].append(call["duration"])
            slow.append({"tool": call["tool"], "timestamp": call["start"].isoformat(),
                         "seconds": round(call["duration"], 3), "ref": call["ref"],
                         "markers": call.get("markers", [])})
        nested_counts.update(name for name, _ in call["nested"])
        repeats[(call["tool"], call["signature"])].append(call)
        if len(call["shell"]) == 1 and "duration" in call:
            shell_durations.append(call["duration"])
        for command in call["shell"]:
            if command is None:
                unresolved_shell += 1
                continue
            literal_shell += 1
            shell_categories.update(command_categories(command))
            shell_repeats[digest(command)].append(command_categories(command))
    by_tool = {name: {"calls": t["calls"], "call_to_output_latency": stats(t["durations"]),
                      "reported_wall_time_text_samples": stats(t["reported_seconds"]),
                      "output_text_chars": t["output_chars"], "lexical_marker_calls": dict(t["markers"])}
               for name, t in sorted(tools.items(), key=lambda item: -item[1]["calls"])}
    repeated = [{"tool": tool, "opaque_signature": sig, "calls": len(group),
                 "first": min(x["start"] for x in group).isoformat(),
                 "last": max(x["start"] for x in group).isoformat(),
                 "call_to_output_latency_sum_seconds": round(sum(x.get("duration", 0) for x in group), 3)}
                for (tool, sig), group in repeats.items() if len(group) > 1]
    repeated.sort(key=lambda x: (-x["calls"], -x["call_to_output_latency_sum_seconds"]))
    shell_repeat_rows = [{"opaque_signature": sig, "calls": len(group),
                          "categories": sorted(set(c for categories in group for c in categories))}
                         for sig, group in shell_repeats.items() if len(group) > 1]
    shell_repeat_rows.sort(key=lambda x: -x["calls"])
    summed_usage = {k: sum(v.get(k, 0) for v in usage.values()) for k in TOKEN_KEYS}
    paired = [call for call in calls.values() if "output_chars" in call]
    output_volume = {
        "paired_calls": len(paired),
        "text_characters": sum(call["output_chars"] for call in paired),
        "utf8_bytes": sum(call["output_utf8_bytes"] for call in paired),
        "calls_over_6000_characters": sum(call["output_chars"] > 6000 for call in paired),
        "calls_over_6000_utf8_bytes": sum(call["output_utf8_bytes"] > 6000 for call in paired),
        "calls_with_utf8_escapes": sum(call.get("output_utf8_escaped", False) for call in paired),
        "largest_output_utf8_bytes": max((call["output_utf8_bytes"] for call in paired), default=0),
    }
    return {"schema": "codex-sanitized-metrics-v1", "window": {"since": since.isoformat(), "until": until.isoformat()},
            "files": file_reports, "tool_calls": len(calls), "tools": by_tool,
            "output_volume": output_volume,
            "nested_static_tool_invocations": dict(nested_counts),
            "shell": {"literal_commands": literal_shell, "unresolved_static_invocations": unresolved_shell,
                      "heuristic_category_occurrences": dict(shell_categories),
                      "single_shell_outer_call_latency_proxy": stats(shell_durations),
                      "exact_repeat_groups": len(shell_repeat_rows),
                      "extra_exact_repeated_calls": sum(x["calls"] - 1 for x in shell_repeat_rows),
                      "top_exact_repeats": shell_repeat_rows[:15]},
            "tool_payload_repetition": {"groups": len(repeated), "extra_exact_repeated_calls": sum(x["calls"] - 1 for x in repeated), "top": repeated[:15]},
            "slowest_calls": sorted(slow, key=lambda x: -x["seconds"])[:15],
            "usage": {"unique_response_id_records": len(usage), "records_without_response_id_not_summed": usage_no_response_id,
                      "reported_per_response_usage_sum": summed_usage,
                      "cached_input_fraction": round(summed_usage["cached_input_tokens"] / summed_usage["input_tokens"], 5) if summed_usage["input_tokens"] else None,
                      "token_count_event_snapshots_not_summed": token_count},
            "diagnostics": dict(counters),
            "limitations": ["Call-to-output latency includes orchestration/queue time, not CPU time; concurrent sums are not elapsed time.",
                            "Single-shell latency is the containing tool call, not an independently measured full process lifetime or async-session total.",
                            "Static JavaScript extraction does not evaluate dynamic arguments/template substitutions or measure unlogged private API activity.",
                            "Command categories and failure markers are lexical hints; source/log text can contain the same words. Repetition is not proof of waste.",
                            "Usage sums last observed usage per unique (file,response_id); token_count cumulative snapshots are never added. Cached input is a subset, reasoning output may be a subset, not extra tokens to add.",
                            "Output volume uses the last recorded output per paired call. Invalid Unicode is counted with backslash escapes and flagged; required documentation is not automatically waste.",
                            "No monetary cost, savings or current billing percentage inferred. No raw command, output, prompt, credential or tool argument is emitted."] +
                           (["Tail scans omit a prefix; requested time-window completeness is not established. Missing activity is not zero activity. Logical bytes consumed exclude unmeasured buffered/OS read-ahead."]
                            if any(item["prefix_bytes_omitted"] for item in file_reports) else [])}


def compact_summary(result: dict) -> dict:
    """Small default view; analyze() remains the complete evidence schema."""
    coverage = result["files"]
    markers = collections.Counter()
    for values in result["tools"].values():
        markers.update(values["lexical_marker_calls"])
    return {
        "schema": "codex-sanitized-metrics-summary-v1",
        "window": result["window"],
        "coverage": {"input_files": len(coverage),
                     **{key: sum(item[key] for item in coverage) for key in
                        ("snapshot_bytes", "logical_bytes_read", "prefix_bytes_omitted",
                         "window_records", "malformed_json", "oversize_lines_skipped",
                         "partial_final_line_skipped", "partial_initial_line_skipped")},
                     "tail_limited_files": sum(item["prefix_bytes_omitted"] > 0 for item in coverage)},
        "tool_calls": result["tool_calls"],
        "output_volume": result["output_volume"],
        "top_five_tools": [{"tool": name, "calls": values["calls"],
                            "call_to_output_latency": values["call_to_output_latency"]}
                           for name, values in list(result["tools"].items())[:5]],
        "shell": {key: result["shell"][key] for key in
                  ("literal_commands", "unresolved_static_invocations",
                   "single_shell_outer_call_latency_proxy", "exact_repeat_groups",
                   "extra_exact_repeated_calls")},
        "extra_exact_repeated_tool_payloads": result["tool_payload_repetition"]["extra_exact_repeated_calls"],
        "lexical_marker_calls_not_confirmed_failures": dict(markers),
        "usage": {key: result["usage"][key] for key in
                  ("unique_response_id_records", "reported_per_response_usage_sum", "cached_input_fraction")},
        "limits": ["Concurrent latency sums are not elapsed time or CPU time; shell timing is an outer-call proxy.",
                   "Tail scans omit a prefix: requested time-window completeness is not established. Missing activity is not zero activity. Logical bytes consumed exclude unmeasured buffered/OS read-ahead.",
                   "Output volume uses the last recorded output per paired call; invalid Unicode is counted with backslash escapes and flagged. Required documentation is not automatically waste.",
                   "Repeated arguments and lexical markers are review candidates, not proof of waste or failure.",
                   "Usage is reported per-response evidence, not billing; cumulative snapshots are not added. Use --details for full sanitized evidence."],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True)
    parser.add_argument("--until", required=True)
    parser.add_argument("--max-line-mib", type=int, default=32)
    parser.add_argument("--tail-mib", type=int, help="scan only the final 1–1024 MiB per file, plus one boundary byte; coverage may be incomplete")
    parser.add_argument("--details", action="store_true", help="opt in to full sanitized aggregates; default is a compact summary")
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        since, until = instant(args.since), instant(args.until)
        if until < since or not 1 <= args.max_line_mib <= 128:
            raise ValueError("invalid window or line bound")
        if args.tail_mib is not None and not 1 <= args.tail_mib <= 1024:
            raise ValueError("invalid tail bound")
        paths = [p.resolve(strict=True) for p in args.files]
        if len(set(paths)) != len(paths) or any(not p.is_file() for p in paths):
            raise ValueError("inputs must be distinct regular files")
        started = time.perf_counter()
        result = analyze(paths, since, until, args.max_line_mib * 1024 * 1024,
                         None if args.tail_mib is None else args.tail_mib * 1024 * 1024)
        parse_elapsed = time.perf_counter() - started
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({"status": "ERROR", "error_type": type(error).__name__, "detail": "Check explicit input files and timezone-aware bounds; no raw input emitted."}))
        return 2
    view = result if args.details else compact_summary(result)
    view["parser_elapsed_seconds"] = round(parse_elapsed, 4)
    print(json.dumps(view, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
