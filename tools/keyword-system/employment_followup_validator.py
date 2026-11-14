"""Fail-closed checks for the bounded employment follow-up artifacts.

This validator checks provenance and approval controls only. It does not admit
keywords, resolve semantic conflicts, or write to Google Ads.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


REQUIRED = {
    "capture.json",
    "employment-followup.json",
    "semantic-review-preview.json",
    "protected-overlap-report.json",
}


def _load(folder: Path, name: str):
    try:
        return json.loads((folder / name).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"INVALID_{name.replace('.', '_').upper()}") from exc


def validate(folder: Path) -> dict:
    folder = Path(folder)
    capture = _load(folder, "capture.json")
    batch = _load(folder, "employment-followup.json")
    review = _load(folder, "semantic-review-preview.json")
    overlap = _load(folder, "protected-overlap-report.json")

    if capture.get("scope") != "AUTHENTIC_UNREVIEWED_DISCOVERY_ONLY":
        raise ValueError("CAPTURE_SCOPE")
    if batch.get("scope") != "AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED":
        raise ValueError("BATCH_SCOPE")
    if review.get("scope") != "AI_REVIEW_PREVIEW_NOT_ADMISSION":
        raise ValueError("REVIEW_SCOPE")
    if overlap.get("scope") != "CURRENT_CORPUS_OVERLAP_DIAGNOSTIC_NOT_ADMISSION":
        raise ValueError("OVERLAP_SCOPE")

    records = batch.get("source_projection", {}).get("records")
    reviewed = review.get("records")
    if not isinstance(records, list) or not isinstance(reviewed, list):
        raise ValueError("RECORDS_REQUIRED")
    source_keys = [(r.get("source_line"), r.get("values", {}).get("Keyword")) for r in records]
    review_keys = [(r.get("source_line"), r.get("keyword")) for r in reviewed]
    if len(source_keys) != 444 or len(set(source_keys)) != len(source_keys):
        raise ValueError("SOURCE_ROWS_NOT_UNIQUE")
    if review_keys != source_keys:
        raise ValueError("REVIEW_ROWS_NOT_BOUND")

    counts = review.get("counts", {})
    observed = {state: sum(r.get("disposition") == state for r in reviewed)
                for state in ("NEGATIVE_EXACT_REVIEW", "HOLD", "POSITIVE_REVIEW")}
    if counts.get("rows") != len(reviewed):
        raise ValueError("REVIEW_COUNT")
    if counts.get("negative_exact_review") != observed["NEGATIVE_EXACT_REVIEW"] or counts.get("hold") != observed["HOLD"]:
        raise ValueError("REVIEW_DISPOSITION_COUNTS")
    if any(value != 0 for key, value in counts.items() if key in {"positive_review", "approved_negative", "deployed"}):
        raise ValueError("REVIEW_AUTHORITY")
    controls = review.get("controls", {})
    if any(controls.get(k) is not False for k in ("campaign_mapping_verified", "scope_approval_granted", "human_review_verified", "production_authorized")):
        raise ValueError("REVIEW_CONTROLS")
    if overlap.get("counts", {}).get("admitted") != 0 or overlap.get("counts", {}).get("deployed") != 0:
        raise ValueError("OVERLAP_AUTHORITY")
    if capture.get("source_files", [{}])[0].get("source_sha256") != batch.get("source_projection", {}).get("source_sha256"):
        raise ValueError("SOURCE_HASH_BINDING")

    return {"passed": True, "rows": len(records), "negative_exact_review": observed["NEGATIVE_EXACT_REVIEW"],
            "hold": observed["HOLD"], "admitted": 0, "deployed": 0}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.folder), sort_keys=True))
