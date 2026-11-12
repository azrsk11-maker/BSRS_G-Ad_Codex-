"""Fail-closed validator for a single sanitized Planner discovery batch."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
from supplemental_discovery import _batch

def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("INVALID_JSON") from exc

def validate(folder: Path) -> dict:
    folder = Path(folder)
    capture = _load(folder / "capture.json")
    candidates = sorted(p for p in folder.glob("*.json") if p.name not in {"capture.json", "semantic-review-preview.json"})
    if len(candidates) != 1:
        raise ValueError("ONE_BATCH_REQUIRED")
    batch_path = candidates[0]
    batch = _load(batch_path)
    _batch(batch)
    preview_path = folder / "semantic-review-preview.json"
    preview = _load(preview_path) if preview_path.exists() else None
    if capture.get("scope") != "AUTHENTIC_UNREVIEWED_DISCOVERY_ONLY":
        raise ValueError("CAPTURE_SCOPE")
    if capture.get("master_contribution") != {"reviewed_positive": 0, "reviewed_negative": 0, "approved_positive": 0, "approved_negative": 0, "deployed": 0}:
        raise ValueError("CAPTURE_AUTHORITY")
    items = capture.get("source_files", [])
    if len(items) != 1 or items[0].get("file") != batch_path.name:
        raise ValueError("MANIFEST_BINDING")
    blob = batch_path.read_bytes()
    if hashlib.sha256(blob).hexdigest() != items[0].get("sha256"):
        raise ValueError("BATCH_HASH_BINDING")
    projection = batch["source_projection"]
    if items[0].get("records") != projection["record_count"] or capture.get("totals", {}).get("export_rows") != projection["record_count"]:
        raise ValueError("ROW_COUNT_BINDING")
    if preview is not None:
        if preview.get("scope") != "AI_REVIEW_PREVIEW_NOT_ADMISSION" or preview.get("source_projection_sha256") != projection["source_sha256"]:
            raise ValueError("PREVIEW_BINDING")
        rows = preview.get("records", [])
        if len(rows) != projection["record_count"]:
            raise ValueError("PREVIEW_ROW_COUNT")
        source_keys = [(r["source_line"], r["values"]["Keyword"]) for r in projection["records"]]
        preview_keys = [(r.get("source_line"), r.get("keyword")) for r in rows]
        if preview_keys != source_keys or any(r.get("human_review_required") is not True for r in rows):
            raise ValueError("PREVIEW_SOURCE_BINDING")
        counts = preview.get("counts", {})
        if counts.get("approved_negative") != 0 or counts.get("deployed") != 0 or preview.get("controls", {}).get("production_authorized") is not False:
            raise ValueError("PREVIEW_AUTHORITY")
    return {"passed": True, "rows": projection["record_count"], "distinct": projection["distinct_normalized_count"], "reviewed": False, "approved": False, "deployed": False}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.folder), sort_keys=True))
