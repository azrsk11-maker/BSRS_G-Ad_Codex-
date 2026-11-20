"""Verify this one authentic Planner capture; no API, master edit or uploader.

Without --raw-export, checks public projection consistency only. The complete
private download is needed to verify that the published values match the source.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import unicodedata

HERE = Path(__file__).resolve().parent
INTAKE = HERE.parents[2] / "tools/keyword-system/staging/historical-intake.json"
EXPORT_SHA256 = "9fad4616519cecd7756e3f32afc26172251d1f78cb117721160683652525e923"
INTAKE_SHA256 = "2fb4fc05496184628c6cab7e900f4bf4c62426e0a84f8c8f9c73302f3f76308e"
TITLE = "Keyword Stats 2026-11-07 at 11_23_21"
PERIOD = "October 1, 2025 - September 30, 2026"
EXCLUDED = ["Ad impression share", "Organic average position", "Organic impression share", "In Account"]
HEADERS = ["Keyword", "Currency", "Segmentation", "Avg. monthly searches", "Three month change", "YoY change", "Competition",
           "Competition (indexed value)", "Top of page bid (low range)", "Top of page bid (high range)", *EXCLUDED,
           *["Searches: " + month for month in ["Oct 2025", "Nov 2025", "Dec 2025", "Jan 2026", "Feb 2026", "Mar 2026",
                                               "Apr 2026", "May 2026", "Jun 2026", "Jul 2026", "Aug 2026", "Sep 2026"]]]
PUBLIC_COLUMNS = [column for column in HEADERS if column not in EXCLUDED]


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def canonical_sha256(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def strict_json(content):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("Non-finite JSON constant: " + value)

    return json.loads(content.decode("utf-8-sig"), object_pairs_hook=unique_object, parse_constant=reject_constant)


def normalize(value):
    text = unicodedata.normalize("NFKC", value).strip()
    if len(text) >= 2 and (text[0], text[-1]) in {("[", "]"), ('"', '"')}:
        text = text[1:-1].strip()
    return " ".join(text.casefold().split())


def load_intake():
    content = INTAKE.read_bytes()
    if sha256(content) != INTAKE_SHA256:
        raise ValueError("Historical input changed; do not reuse this capture's identity claims")
    result = strict_json(content)
    if len(result["candidates"]) != 41 or any(row["review_state"] != "CANDIDATE" for row in result["candidates"]):
        raise ValueError("Expected 41 unapproved historical candidates")
    return result


def public_projection(content):
    """Allowlist the actual export columns; never return account-specific cells."""
    lines = content.decode("utf-16").splitlines()
    if lines[:2] != [TITLE, '"' + PERIOD + '"']:
        raise ValueError("Unexpected export title or historical date window")
    reader = csv.DictReader(io.StringIO("\n".join(lines[2:])), delimiter="\t")
    if reader.fieldnames != HEADERS:
        raise ValueError("Unexpected export headers; review before projecting")
    kept, aggregate = [], []
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed export column count")
        line = reader.line_num + 2
        if not row["Keyword"]:
            aggregate.append({"source_line": line, "segmentation_label": row["Segmentation"], "reason": "NON_KEYWORD_AGGREGATE_ROW"})
            continue
        kept.append({"source_line": line, "cells": {column: row[column] if row[column] != "" else None for column in PUBLIC_COLUMNS}})
    return {"columns": PUBLIC_COLUMNS, "empty_cell_representation": None,
            "nonempty_cell_representation": "Exact exported strings, with no numeric conversion, estimation or rounding",
            "rows": kept, "excluded_aggregate_rows": aggregate}


def reconcile(projection, candidates):
    input_index = {}
    for row in candidates:
        key = normalize(row["original_text"])
        if key in input_index:
            raise ValueError("Duplicate normalized input candidate")
        input_index[key] = row
    output_index = {}
    for row in projection["rows"]:
        key = normalize(row["cells"]["Keyword"])
        if key in output_index:
            raise ValueError("Duplicate returned keyword; no automatic representative selection")
        output_index[key] = row
    matched, missing = [], []
    for key, candidate in input_index.items():
        item = {"candidate_id": candidate["candidate_id"], "submitted_text": candidate["original_text"]}
        if key in output_index:
            returned = output_index[key]
            matched.append({**item, "source_line": returned["source_line"], "returned_text": returned["cells"]["Keyword"],
                            "mapping": "EXACT_CANONICAL_TEXT"})
        else:
            missing.append({**item, "status": "NOT_RETURNED_AS_SEPARATE_EXACT_ROW", "grouped_under": None})
    extra = [{"source_line": row["source_line"], "returned_text": row["cells"]["Keyword"]}
             for key, row in output_index.items() if key not in input_index]
    return {"input_candidates": len(candidates), "returned_keyword_rows": len(output_index), "exact_matches": len(matched),
            "matched": matched, "not_returned_as_exact_rows": missing, "unrequested_returned_rows": extra,
            "grouping_assignments": [], "grouping_status": "NO_AUTHORITATIVE_GROUPING_EVIDENCE_NO_SEMANTIC_INFERENCE"}


def metadata():
    return {
        "version": "bsre-planner-observation-2026-11-07-v1",
        "scope": "AUTHENTIC_PLATFORM_HISTORICAL_METRICS_RESEARCH_ONLY",
        "ui_observation": {"observed_utc_start": "2026-11-07T07:22Z", "observed_utc_end": "2026-11-07T07:23Z",
                           "provenance": "Authenticated root operator UI readback; exact seconds were not recorded",
                           "account": "573-038-4686", "tool": "Google Keyword Planner — Get search volume and forecasts",
                           "location": "United Arab Emirates", "network_display": "Google",
                           "language_display": "All languages", "language_control_enabled": False, "english_only_verified": False,
                           "date_preset_display": "Last 12 months", "date_start": "2025-10-01", "date_end_inclusive": "2026-09-30",
                           "plan_id": "1444037307", "plan_state": "NON_SERVING_RESEARCH_PLAN_AUTOMATICALLY_CREATED",
                           "create_campaign_used": False, "live_campaign_changes": False},
        "private_source": {"basename": TITLE + ".csv", "bytes": 6708, "sha256": EXPORT_SHA256,
                           "encoding": "UTF-16 with BOM", "delimiter": "TAB", "date_header": PERIOD,
                           "raw_export_committed": False, "original_columns": HEADERS,
                           "excluded_columns": EXCLUDED,
                           "exclusion_reason": "Account-specific status, paid impression share and organic account metrics are omitted"},
        "historical_input": {"repository_path": "tools/keyword-system/staging/historical-intake.json", "sha256": INTAKE_SHA256,
                             "candidate_count": 41, "submitted_field": "original_text", "historical_state_unchanged": True},
        "interpretation": ["All languages observation; this is not verified English-only demand",
                           "Historical platform estimates, not Black Swan campaign performance or genuine customer search-term records",
                           "Top-of-page bid ranges are retained under their own labels, not relabeled as actual CPC",
                           "Empty cells remain null; a missing row is not zero demand",
                           "No attribution of the four missing exact rows to another term without authoritative grouping evidence",
                           "No summation of keyword estimates into unique demand, leads, qualifications or revenue",
                           "No inferred present inventory, ownership mapping, source expiry or business review"],
        "controls": {"reviewed_master_rows_added": 0, "approved_rows_added": 0, "deployed_rows_added": 0,
                     "master_files_changed": False, "historical_intake_changed": False,
                     "production_authorization": False, "deployment_export_allowed": False}
    }


def build_capture(raw_export, candidates):
    if len(raw_export) != 6708 or sha256(raw_export) != EXPORT_SHA256:
        raise ValueError("Private export bytes differ from the authenticated capture")
    projection = public_projection(raw_export)
    reconciliation = reconcile(projection, candidates)
    result = {**metadata(), "public_projection": projection, "reconciliation": reconciliation}
    result["integrity"] = {"public_projection_sha256": canonical_sha256(projection),
                           "reconciliation_sha256": canonical_sha256(reconciliation)}
    return result


def verify_public(capture, candidates):
    base = metadata()
    if set(capture) != set(base) | {"public_projection", "reconciliation", "integrity"} or any(capture.get(key) != value for key, value in base.items()):
        raise ValueError("Capture scope/context/source metadata changed")
    projection = capture["public_projection"]
    if set(projection) != {"columns", "empty_cell_representation", "nonempty_cell_representation", "rows", "excluded_aggregate_rows"} or projection["empty_cell_representation"] is not None:
        raise ValueError("Projection contains unreviewed structure or changed null semantics")
    if projection["columns"] != PUBLIC_COLUMNS or len(projection["rows"]) != 37:
        raise ValueError("Projection column/count mismatch")
    if projection["excluded_aggregate_rows"] != [{"source_line": 4, "segmentation_label": "All", "reason": "NON_KEYWORD_AGGREGATE_ROW"},
                                                {"source_line": 5, "segmentation_label": "United Arab Emirates", "reason": "NON_KEYWORD_AGGREGATE_ROW"}]:
        raise ValueError("Aggregate-row exclusions changed")
    if [row["source_line"] for row in projection["rows"]] != list(range(6, 43)):
        raise ValueError("Keyword source locators changed")
    for row in projection["rows"]:
        if set(row) != {"source_line", "cells"} or set(row["cells"]) != set(PUBLIC_COLUMNS):
            raise ValueError("Projection contains unreviewed or excluded fields")
        if any(value is not None and not isinstance(value, str) for value in row["cells"].values()):
            raise ValueError("Exported strings/nulls changed type")
        if row["cells"]["Currency"] != "AED":
            raise ValueError("Currency differs from this captured export")
    reconciliation = reconcile(projection, candidates)
    if capture["reconciliation"] != reconciliation or reconciliation["exact_matches"] != 37 or len(reconciliation["not_returned_as_exact_rows"]) != 4 or reconciliation["unrequested_returned_rows"]:
        raise ValueError("Input/output reconciliation changed")
    if capture["integrity"] != {"public_projection_sha256": canonical_sha256(projection), "reconciliation_sha256": canonical_sha256(reconciliation)}:
        raise ValueError("Projection/reconciliation digest mismatch")


def verify_discovery_matches(reconciliation):
    missing = {normalize(row["submitted_text"]): row["candidate_id"]
               for row in reconciliation["not_returned_as_exact_rows"]}
    matches = {candidate_id: [] for candidate_id in missing.values()}
    batches = {
        "keyword-discovery-2026-11-08": ("buyers", "tenants", "owners", "commercial"),
        "keyword-discovery-supply-2026-11-08": ("sellers", "landlords"),
    }
    rows_checked = 0
    for directory, names in batches.items():
        for name in names:
            path = HERE.parent / directory / (name + ".json")
            records = strict_json(path.read_bytes())["source_projection"]["records"]
            rows_checked += len(records)
            for record in records:
                candidate_id = missing.get(normalize(record["values"]["Keyword"]))
                if candidate_id is not None:
                    matches[candidate_id].append([name, record["source_line"]])
    expected = {
        "LEGACY-POS-0003": [],
        "LEGACY-POS-0024": [["tenants", 4]],
        "LEGACY-POS-0026": [["tenants", 5]],
        "LEGACY-POS-0028": [["buyers", 83], ["tenants", 10]],
    }
    if rows_checked != 8809 or matches != expected:
        raise ValueError("Option A discovery cross-check differs from the recorded source rows")
    return {"rows_checked": rows_checked, "candidate_matches": matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-export", type=Path, help="Private original download; never copied or modified")
    args = parser.parse_args()
    intake = load_intake()
    candidates = intake["candidates"]
    capture = strict_json((HERE / "capture.json").read_bytes())
    verify_public(capture, candidates)
    if args.raw_export and build_capture(args.raw_export.read_bytes(), candidates) != capture:
        raise ValueError("Public projection differs from the original private export")
    placements = {row["placement_id"]: row["original_keyword_fields"]["Campaign"] for row in intake["placements"]}
    exact_ids = {row["candidate_id"] for row in capture["reconciliation"]["matched"]}
    campaigns = {f"BSRE_SEARCH_{name}_EN": {"candidates": 0, "exact": 0, "missing": 0}
                 for name in ("BUYERS", "OWNERS", "TENANTS", "BRAND")}
    for row in candidates:
        owners = {placements[key] for key in row["placement_ids"]}
        if len(owners) != 1 or not owners.issubset(campaigns):
            raise ValueError("Historical candidate lacks a unique Option A campaign")
        counts = campaigns[owners.pop()]
        counts["candidates"] += 1
        counts["exact" if row["candidate_id"] in exact_ids else "missing"] += 1
    print(json.dumps({"public_integrity_pass": True, "private_source_verified": bool(args.raw_export),
                      "verification_scope": "SOURCE_BYTES_AND_PUBLIC_PROJECTION" if args.raw_export else "PUBLIC_PROJECTION_CONSISTENCY_ONLY",
                      "inputs": 41, "returned": 37, "exact_matches": 37, "not_returned_exactly": 4,
                      "historical_campaign_evidence": campaigns,
                      "separate_discovery_evidence": verify_discovery_matches(capture["reconciliation"]),
                      "master_rows_added": 0, "deployment_export_allowed": False}, indent=2))


if __name__ == "__main__":
    main()
