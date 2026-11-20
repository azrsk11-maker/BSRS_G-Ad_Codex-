"""Current strict JSON/CSV intake over the frozen historical validation core.

Use this module/CLI for new intake. keyword_audit.py retains its exact reviewed
historical bytes; its CSV reader is not the current untrusted-input interface.
No network, Ads exporter, approval or production writer is provided.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

# Explicit delegation preserves the reviewed validation/matching implementation.
from keyword_audit import (
    JSON_FIELDS, LIST_FIELDS, NULL_FIELDS, POSITIVE_FIELDS,
    audit, duplicate_safe_object, ensure_output_is_not_input, iso_day,
    negative_matches, normalize, proposed_capacity, release_gate,
    tokens,
)
import keyword_audit as historical


def _require_finite_numbers(value):
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("Invalid number: non-finite decoded value")
        if isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return value


def parse_json_bytes(content: bytes):
    return _require_finite_numbers(historical.parse_json_bytes(content))


def load_json(path: Path):
    return parse_json_bytes(path.read_bytes())


def read_records(path: Path, *, content=None):
    """Parse one snapshot; CSV never calls the historical permissive CSV reader."""
    content = path.read_bytes() if content is None else content
    if path.suffix.lower() == ".json":
        result = parse_json_bytes(content)
        if not isinstance(result, list):
            raise ValueError("JSON input must be an array of record objects")
        if not all(isinstance(row, dict) for row in result):
            raise ValueError("Every input row must be an object")
        return result
    if path.suffix.lower() != ".csv":
        raise ValueError("Only JSON and CSV inputs are supported")
    with io.StringIO(content.decode("utf-8-sig"), newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(set(fields)) != len(fields):
            raise ValueError("Duplicate CSV header")
        result = []
        for record in reader:
            if None in record or any(value is None for value in record.values()):
                raise ValueError("CSV row has mismatched column count")
            for key in JSON_FIELDS & record.keys():
                record[key] = json.loads(record[key] or ("[]" if key in LIST_FIELDS else "{}"),
                    object_pairs_hook=duplicate_safe_object,
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Invalid number " + value)))
            for key in NULL_FIELDS & record.keys():
                if record[key] == "":
                    record[key] = None
            for key in {"volume", "cpc"} & record.keys():
                if record[key] is not None:
                    record[key] = float(record[key])
            result.append(record)
    return _require_finite_numbers(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=["positive", "negative"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--campaigns", type=Path, required=True)
    parser.add_argument("--campaign-context", type=Path, required=True)
    parser.add_argument("--protected", type=Path, required=True)
    parser.add_argument("--as-of", type=iso_day, required=True)
    parser.add_argument("--scope-bindings", type=Path)
    parser.add_argument("--positive-library", type=Path, help="Complete supplied positive master for negative coverage; never the unapproved historical staging intake")
    parser.add_argument("--coverage-review", type=Path, help="Dated reviewed corpus manifest with exact canonical input hashes")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inputs = [args.input, args.sources, args.campaigns, args.campaign_context, args.protected]
    if args.scope_bindings:
        inputs.append(args.scope_bindings)
    if bool(args.positive_library) != bool(args.coverage_review) or args.positive_library and args.kind != "negative":
        parser.error("--positive-library and --coverage-review are required together for a negative audit")
    if args.positive_library:
        inputs.extend([args.positive_library, args.coverage_review])
    roles = ["records", "sources", "campaigns", "campaign_context", "protected_queries"] + (["scope_bindings"] if args.scope_bindings else [])
    if args.positive_library:
        roles.extend(["positive_library", "coverage_review"])
    try:
        ensure_output_is_not_input(args.output, inputs)
        # One read per input. Parsing and report provenance use these same bytes.
        snapshots = {role: path.read_bytes() for role, path in zip(roles, inputs)}
        report = audit(args.kind, read_records(args.input, content=snapshots["records"]),
                       parse_json_bytes(snapshots["sources"]), parse_json_bytes(snapshots["campaigns"]),
                       parse_json_bytes(snapshots["campaign_context"]), parse_json_bytes(snapshots["protected_queries"]), args.as_of,
                       parse_json_bytes(snapshots["scope_bindings"]) if args.scope_bindings else None,
                       read_records(args.positive_library, content=snapshots["positive_library"]) if args.positive_library else None,
                       parse_json_bytes(snapshots["coverage_review"]) if args.coverage_review else None)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    report["input_sha256"] = {role: {"filename": path.name, "sha256": hashlib.sha256(snapshots[role]).hexdigest()}
                              for role, path in zip(roles, inputs)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {key: value for key, value in report.items() if key not in {"records", "input_sha256", "protected_conflicts", "supplied_library_coverage"}}
    if "supplied_library_coverage" in report:
        coverage = report["supplied_library_coverage"]
        summary["supplied_library_coverage"] = {key: coverage[key] for key in (
            "status", "evaluation_complete", "conflict_free_coverage_verified", "positive_library_rows",
            "negative_library_rows", "protected_query_rows", "positives_with_long_tail", "indexed_cases",
            "applicable_case_pairs", "lexical_comparisons_executed", "pairs_pruned_by_token_index")}
        summary["supplied_library_coverage"].update(error_count=len(coverage["errors"]), conflict_count=len(coverage["conflicts"]))
    print(json.dumps(summary, indent=2))
    return 0 if report["structural_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
