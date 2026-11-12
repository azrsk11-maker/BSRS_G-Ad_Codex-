"""Reconcile two pinned discovery captures without admitting any keyword.

Both source occurrences and original preview assessments survive canonical
deduplication. This module has no current-library, Google or deployment writer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from keyword_audit import normalize, parse_json_bytes
from supplemental_discovery import _batch, _exact, MASTER

ROOT = Path(__file__).resolve().parents[2]
MAX_INPUT_BYTES = 2_000_000
SCOPE = "FOLLOWUP_CAPTURE_PREVIEW_RECONCILIATION_NOT_ADMISSION"
SOURCES = {
    "followup-1": {
        "folder": "docs/audit/keyword-employment-followup-2026-11-11",
        "batch_file": "employment-followup.json",
        "pins": {
            "capture.json": "3f9b864bf9db426696f4af2d901f8f767280ec596325fe8417720cd0ca646249",
            "employment-followup.json": "860733d2098bef9447b2ffd36fb2246a7380873a22e2ef0dbe9c6028960d84fe",
            "semantic-review-preview.json": "e983b3eaacf26f076b819db65bed552cca05b3b2fc0fe6e0957551ffc7d54c34",
        },
        # The first historical preview labels its batch-byte digest as a
        # projection digest. Preserve that fact; never rewrite the original.
        "preview_binding": "860733d2098bef9447b2ffd36fb2246a7380873a22e2ef0dbe9c6028960d84fe",
    },
    "followup-2": {
        "folder": "docs/audit/keyword-employment-followup-2026-11-11-batch2",
        "batch_file": "employment-followup-batch2.json",
        "pins": {
            "capture.json": "47127cdbae1656ee8904a5486d8a500206ade837892d56b9be8b9143e628798e",
            "employment-followup-batch2.json": "a39cb137570e71e64c50081d8019268d30ee96498cdb651f66bfc3a99f4a1189",
            "semantic-review-preview.json": "d9694957f42bd4ef115bd300383f3016ed11b2556d8d681a99bceabf00fb09e5",
        },
        "preview_binding": "124f99b2f16fdc42759eeb134eb30b7eef1d43647dcd739d6b4149fef751762d",
    },
}
CONTROLS = {
    "research_only": True,
    "semantic_review_complete": False,
    "human_review_verified": False,
    "campaign_mapping_verified": False,
    "scope_approval_granted": False,
    "admission_authorized": False,
    "deployment_authorized": False,
    "production_authorized": False,
    "current_library_overlap_verified": False,
}
REVIEW_SCOPE = "PRELIMINARY_AI_FOLLOWUP_SEMANTIC_REVIEW_NOT_ADMISSION"
REVIEW_CONTROLS = {key: False for key in (
    "human_review_verified", "campaign_mapping_verified", "scope_approval_granted",
    "exclusion_approval_granted", "positive_admission_granted", "negative_admission_granted",
    "production_authorized", "deployed")}
BASELINE_REPORT = {
    "file": "docs/audit/keyword-negative-vendor-admission-2026-11-11/library-report.json",
    "sha256": "0108165b9fedac03dde1aee5b89e6482dcf958521aa45c702fb77cf2252e76b6",
}
# Immutable observation of the 11-November review's ID/membership pairs. This
# detects relabeling a protected identity as novel; it is never a fresh audit.
BASELINE_MEMBERSHIP_SHA256 = "59159aea236186725cf268a74ef19f6c61a687a13c687c1f98da861ff5dd3782"


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def canonical_id(keyword: str) -> str:
    return "KW-" + sha256(normalize(keyword).encode("utf-8"))


def _linked(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def load_sources(root: Path = ROOT) -> dict:
    """Read only the six bounded public files; raw exports are never opened."""
    root = Path(root).resolve()
    result = {}
    for key, spec in SOURCES.items():
        folder = root / spec["folder"]
        result[key] = {}
        for name in spec["pins"]:
            path = folder / name
            need(path.resolve().is_relative_to(root) and not _linked(path)
                 and not any(_linked(p) for p in path.parents if p != root.parent),
                 "SOURCE_PATH")
            try:
                with path.open("rb") as stream:
                    blob = stream.read(MAX_INPUT_BYTES + 1)
            except OSError:
                raise ValueError("SOURCE_READ_FAILED") from None
            need(len(blob) <= MAX_INPUT_BYTES, "SOURCE_SIZE")
            result[key][name] = blob
    return result


def _verify_source(key, documents):
    spec = SOURCES[key]
    need(isinstance(documents, dict) and set(documents) == set(spec["pins"]), "SOURCE_FILES")
    parsed = {}
    for name, pin in spec["pins"].items():
        blob = documents[name]
        need(type(blob) is bytes and len(blob) <= MAX_INPUT_BYTES
             and sha256(blob) == pin, "SOURCE_BYTES_CHANGED")
        parsed[name] = parse_json_bytes(blob)
    capture, batch, preview = (parsed["capture.json"], parsed[spec["batch_file"]],
                               parsed["semantic-review-preview.json"])
    _batch(batch)
    projection = batch["source_projection"]
    expected_item = {"file": spec["batch_file"], "batch_id": batch["batch_id"],
        "sha256": spec["pins"][spec["batch_file"]], "bytes": len(documents[spec["batch_file"]]),
        "records": projection["record_count"], "distinct_normalized": projection["distinct_normalized_count"],
        "source_bytes": projection["source_bytes"], "source_sha256": projection["source_sha256"]}
    need(capture["scope"] == "AUTHENTIC_UNREVIEWED_DISCOVERY_ONLY"
         and capture["account_id"] == "573-038-4686"
         and _exact(capture["source_files"], [expected_item])
         and _exact(capture["master_contribution"], MASTER), "MANIFEST_BINDING")
    need(preview["scope"] == "AI_REVIEW_PREVIEW_NOT_ADMISSION"
         and preview["source_batch"] == batch["batch_id"]
         and preview["source_projection_sha256"] == spec["preview_binding"], "PREVIEW_BINDING")
    rows = projection["records"]
    assessments = preview["records"]
    need(len(rows) == len(assessments) == 444, "ROW_COUNT")
    need([(r["source_line"], r["values"]["Keyword"]) for r in rows]
         == [(r["source_line"], r["keyword"]) for r in assessments], "PREVIEW_SOURCE_BINDING")
    counts = Counter(r["disposition"] for r in assessments)
    need(set(counts) <= {"HOLD", "NEGATIVE_EXACT_REVIEW"}
         and preview["counts"]["rows"] == len(rows)
         and preview["counts"]["negative_exact_review"] == counts["NEGATIVE_EXACT_REVIEW"]
         and preview["counts"]["hold"] == counts["HOLD"]
         and all(preview["counts"][k] == 0 for k in ("positive_review", "approved_negative", "deployed")),
         "PREVIEW_COUNTS")
    need(all(r["human_review_required"] is True for r in assessments)
         and all(preview["controls"][k] is False for k in
                 ("campaign_mapping_verified", "scope_approval_granted", "human_review_verified", "production_authorized")),
         "PREVIEW_AUTHORITY")
    return batch, preview


def reconcile_sources(documents: dict) -> dict:
    """Pure function over pinned public bytes; never resolve preview conflicts."""
    need(isinstance(documents, dict) and set(documents) == set(SOURCES), "SOURCE_SET")
    records, sources, memberships = {}, [], []
    cohort = None
    for key, spec in SOURCES.items():
        batch, preview = _verify_source(key, documents[key])
        projection = batch["source_projection"]
        context = {"input_seeds": batch["input_seeds"], "ui_context": batch["ui_context"],
                   "date_header": projection["date_header"]}
        if cohort is None:
            cohort = context
        need(_exact(context, cohort), "CAPTURE_COHORT_CHANGED")
        membership = set()
        for row, assessment in zip(projection["records"], preview["records"]):
            text = row["values"]["Keyword"]
            normalized = normalize(text)
            need(normalized and normalized not in membership, "DUPLICATE_SOURCE_IDENTITY")
            membership.add(normalized)
            record = records.setdefault(normalized, {"canonical_id": canonical_id(normalized),
                "normalized_keyword": normalized, "keyword_variants": [],
                "provenance_occurrences": [], "preview_assessments": [],
                "semantic_review_required": True})
            if text not in record["keyword_variants"]:
                record["keyword_variants"].append(text)
            record["provenance_occurrences"].append({"source_key": key,
                "batch_id": batch["batch_id"], "source_sha256": projection["source_sha256"],
                "batch_sha256": spec["pins"][spec["batch_file"]],
                "source_line": row["source_line"], "keyword": text})
            record["preview_assessments"].append({"source_key": key,
                "preview_sha256": spec["pins"]["semantic-review-preview.json"],
                "original_assessment": deepcopy(assessment)})
        memberships.append(membership)
        sources.append({"source_key": key, "folder": spec["folder"], "batch_id": batch["batch_id"],
            "source_sha256": projection["source_sha256"], "pins": deepcopy(spec["pins"])})
    need(memberships[0] == memberships[1], "CAPTURE_COHORT_MEMBERSHIP_CHANGED")
    for record in records.values():
        assessments = [r["original_assessment"] for r in record["preview_assessments"]]
        decisions = {r["disposition"] for r in assessments}
        record["preview_state"] = ("DISAGREEMENT_HOLD" if len(decisions) > 1 else
            "AGREEMENT_NEGATIVE_REVIEW" if decisions == {"NEGATIVE_EXACT_REVIEW"} else "AGREEMENT_HOLD")
        record["assessment_content_differs"] = assessments[0] != assessments[1]
    ordered = [records[k] for k in sorted(records)]
    states = Counter(r["preview_state"] for r in ordered)
    return {"version": 1, "scope": SCOPE, "account_id": "573-038-4686",
        "sources": sources, "counts": {"source_occurrences": sum(len(r["provenance_occurrences"]) for r in ordered),
            "canonical_phrases": len(ordered), "agreement_negative_review": states["AGREEMENT_NEGATIVE_REVIEW"],
            "agreement_hold": states["AGREEMENT_HOLD"], "disagreement_hold": states["DISAGREEMENT_HOLD"],
            "assessment_content_differences": sum(r["assessment_content_differs"] for r in ordered)},
        "records": ordered, "controls": deepcopy(CONTROLS), "master_contribution": deepcopy(MASTER)}


def write_new_report(report: dict, destination: Path, root: Path = ROOT) -> None:
    """Create one explicitly requested new artifact, never overwrite any file."""
    need(isinstance(report, dict) and report.get("scope") == SCOPE
         and _exact(report.get("controls"), CONTROLS)
         and _exact(report.get("master_contribution"), MASTER), "REPORT_AUTHORITY")
    destination = Path(destination).absolute()
    resolved = destination.resolve()
    root = Path(root).resolve()
    need(not destination.exists() and not _linked(destination), "OUTPUT_EXISTS")
    need(not any(resolved.is_relative_to(root / spec["folder"]) for spec in SOURCES.values()),
         "SOURCE_OVERWRITE_FORBIDDEN")
    need(destination.parent.is_dir() and not any(_linked(p) for p in destination.parents), "OUTPUT_PARENT")
    blob = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        with destination.open("xb") as stream:
            stream.write(blob)
    except FileExistsError:
        raise ValueError("OUTPUT_EXISTS") from None


def validate_preliminary_review(review: dict, reconciled: dict, baseline_report: bytes) -> dict:
    """Validate a dated review snapshot against already verified source bytes.

    Does not reconstruct today's library, approve intent, or grant admission.
    A later admission must use the existing complete current-library checks.
    """
    fields = {"version", "scope", "reviewed_on", "reviewer", "source_refs", "baseline",
              "counts", "decision_basis", "provenance_binding", "records", "controls", "master_contribution"}
    need(isinstance(review, dict) and set(review) == fields, "REVIEW_FIELDS")
    need(_exact(review["version"], 1) and review["scope"] == REVIEW_SCOPE
         and review["reviewed_on"] == "2026-11-11", "REVIEW_SCOPE")
    need(_exact(review["reviewer"], {"type": "AI", "name": "Codex", "human_review_verified": False})
         and _exact(review["controls"], REVIEW_CONTROLS)
         and _exact(review["master_contribution"], MASTER), "REVIEW_AUTHORITY")
    need(isinstance(reconciled, dict) and reconciled.get("scope") == SCOPE
         and _exact(reconciled.get("controls"), CONTROLS)
         and _exact(review["source_refs"], reconciled["sources"]), "REVIEW_SOURCE_REFS")
    need(type(baseline_report) is bytes and len(baseline_report) <= MAX_INPUT_BYTES
         and sha256(baseline_report) == BASELINE_REPORT["sha256"], "BASELINE_REPORT_CHANGED")
    report = parse_json_bytes(baseline_report)
    baseline = review["baseline"]
    baseline_fields = {"method", "verified_on_dubai", "eligible_negative", "protected_queries",
        "verification_elapsed_seconds", "library_report", "membership_is_observed_snapshot",
        "current_membership_requires_fresh_verification"}
    need(isinstance(baseline, dict) and set(baseline) == baseline_fields
         and baseline["method"] == "current_negative_library.reconstruct() with complete source/cohort/index/protection checks"
         and baseline["verified_on_dubai"] == "2026-11-11"
         and _exact(baseline["library_report"], BASELINE_REPORT)
         and _exact(baseline["eligible_negative"], report["reviewed_eligible_rows"])
         and _exact(baseline["protected_queries"], report["protected_queries_indexed"])
         and baseline["membership_is_observed_snapshot"] is True
         and baseline["current_membership_requires_fresh_verification"] is True
         and type(baseline["verification_elapsed_seconds"]) in (int, float)
         and math.isfinite(baseline["verification_elapsed_seconds"])
         and baseline["verification_elapsed_seconds"] >= 0, "REVIEW_BASELINE_SNAPSHOT")
    need(all(isinstance(review[k], str) and 0 < len(review[k]) <= 4000
             for k in ("decision_basis", "provenance_binding")), "REVIEW_EXPLANATION")
    rows = review["records"]
    source_rows = reconciled["records"]
    need(isinstance(rows, list) and len(rows) == len(source_rows) == 444, "REVIEW_ROWS")
    row_fields = {"canonical_id", "normalized_keyword", "original_text", "baseline_membership",
        "disposition", "reason_code", "rationale", "preview_state", "human_review_required",
        "match_type_proposal", "scope_proposal"}
    memberships, dispositions = Counter(), Counter()
    membership_pairs = []
    for row, source in zip(rows, source_rows):
        need(isinstance(row, dict) and set(row) == row_fields, "REVIEW_ROW_FIELDS")
        need(row["canonical_id"] == source["canonical_id"]
             and row["normalized_keyword"] == source["normalized_keyword"]
             and row["original_text"] in source["keyword_variants"]
             and row["preview_state"] == source["preview_state"], "REVIEW_IDENTITY_BINDING")
        membership = row["baseline_membership"]
        decision = row["disposition"]
        need(isinstance(membership, str) and isinstance(decision, str)
             and membership in {"NOVEL_UNPROTECTED", "EXISTING_NEGATIVE", "EXISTING_PROTECTED"}
             and decision in {"NEGATIVE_EXACT_REVIEW", "HOLD", "EXISTING_NEGATIVE_NO_NEW_ROW"},
             "REVIEW_DISPOSITION")
        need(row["human_review_required"] is True and row["scope_proposal"] is None,
             "REVIEW_ROW_AUTHORITY")
        need(row["match_type_proposal"] == ("EXACT" if decision == "NEGATIVE_EXACT_REVIEW" else None),
             "REVIEW_MATCH_TYPE")
        need(source["preview_state"] != "DISAGREEMENT_HOLD" or decision == "HOLD",
             "PREVIEW_DISAGREEMENT_BYPASS")
        need(membership != "EXISTING_PROTECTED" or decision == "HOLD", "PROTECTED_NEGATIVE_BYPASS")
        need(decision != "NEGATIVE_EXACT_REVIEW" or membership == "NOVEL_UNPROTECTED",
             "NONNOVEL_PROPOSAL")
        need(decision != "EXISTING_NEGATIVE_NO_NEW_ROW" or membership == "EXISTING_NEGATIVE",
             "EXISTING_NEGATIVE_BINDING")
        need(isinstance(row["reason_code"], str)
             and re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", row["reason_code"])
             and isinstance(row["rationale"], str) and 0 < len(row["rationale"]) <= 2000,
             "REVIEW_REASON")
        memberships[membership] += 1
        dispositions[decision] += 1
        membership_pairs.append([row["canonical_id"], membership])
    encoded = json.dumps(membership_pairs, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    need(sha256(encoded) == BASELINE_MEMBERSHIP_SHA256, "BASELINE_MEMBERSHIP_SNAPSHOT_CHANGED")
    counts = {"canonical_phrases": len(rows), "source_occurrences": reconciled["counts"]["source_occurrences"],
        "novel_unprotected": memberships["NOVEL_UNPROTECTED"],
        "existing_negative_overlaps": memberships["EXISTING_NEGATIVE"],
        "existing_protected_overlaps": memberships["EXISTING_PROTECTED"],
        "novel_ai_reviewed": memberships["NOVEL_UNPROTECTED"],
        "negative_exact_review": dispositions["NEGATIVE_EXACT_REVIEW"], "hold": dispositions["HOLD"],
        "existing_negative_no_new_row": dispositions["EXISTING_NEGATIVE_NO_NEW_ROW"],
        "preview_disagreement_holds": reconciled["counts"]["disagreement_hold"],
        "positive_review": 0, "unassessed": 0, "master_rows_added": 0, "approved": 0, "deployed": 0}
    need(_exact(review["counts"], counts), "REVIEW_COUNTS")
    return {"scope": REVIEW_SCOPE, "source_bound_review_valid": True, "counts": counts,
        "membership_is_observed_snapshot": True, "current_library_membership_verified": False,
        "master_contribution": deepcopy(MASTER), "production_authorized": False}


def load_review(path: Path) -> dict:
    path = Path(path).absolute()
    need(path.is_file() and not _linked(path) and not any(_linked(p) for p in path.parents),
         "REVIEW_PATH")
    with path.open("rb") as stream:
        blob = stream.read(MAX_INPUT_BYTES + 1)
    need(len(blob) <= MAX_INPUT_BYTES, "REVIEW_SIZE")
    return parse_json_bytes(blob)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review", type=Path, help="Validate one prepared source-bound preliminary review")
    args = parser.parse_args()
    try:
        report = reconcile_sources(load_sources())
        review_summary = None
        if args.review:
            review_summary = validate_preliminary_review(load_review(args.review), report,
                (ROOT / BASELINE_REPORT["file"]).read_bytes())
        write_new_report(report, args.output)
        summary = {"scope": SCOPE, "counts": report["counts"],
            "master_contribution": report["master_contribution"], "production_authorized": False}
        if review_summary is not None:
            summary["preliminary_review"] = review_summary
        print(json.dumps(summary, sort_keys=True))
    except (ValueError, OSError):
        # Do not echo inputs, source text or caller paths through diagnostics.
        print(json.dumps({"passed": False, "error": "FOLLOWUP_RECONCILIATION_FAILED", "production_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
