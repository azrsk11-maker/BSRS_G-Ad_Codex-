"""Read-only pinned supplemental Discovery verification and occurrence overlap.

No metric aggregation, classification inheritance, admission or platform writer.
Original capture verification and triage remain separate, unchanged contracts.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path
import re

from keyword_audit import normalize, parse_json_bytes
from planner_discovery import (BASE_COLUMNS, EXCLUDED_COLUMNS, MAX_BYTES,
                               MAX_RECORDS, _monthly_columns, _normalized_keyword,
                               parse_discovery)

CONTROLS = {"reviewed": False, "approved": False, "deployed": False,
            "master_rows_added": 0, "live_campaign_changes": False,
            "raw_export_committed": False}
MASTER = {"reviewed_positive": 0, "reviewed_negative": 0,
          "approved_positive": 0, "approved_negative": 0, "deployed": 0}
CONTEXT = {"account_id": "573-038-4686", "location": "United Arab Emirates",
           "language": "English", "network_display": "Google",
           "date_preset": "Last 12 months", "exclude_adult_ideas": True,
           "website_filter": None}
BATCH_FIELDS = {"version", "scope", "batch_id", "topic", "input_seeds",
                "ui_context", "source_projection", "seed_reconciliation", "controls"}
PROJECTION_FIELDS = {"source_basename", "source_bytes", "source_sha256", "date_header",
                     "column_labels", "public_columns", "excluded_columns", "record_count",
                     "distinct_normalized_count", "duplicate_groups", "records"}


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _exact(actual, expected):
    """Unlike ordinary equality, booleans cannot stand in for integer counts."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _name(value, suffix=None):
    return (isinstance(value, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value))
            and (suffix is None or value.endswith(suffix)))


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _batch(batch):
    _need(isinstance(batch, dict) and set(batch) == BATCH_FIELDS, "BATCH_FIELDS")
    _need(_exact(batch["version"], 1) and batch["scope"] == "AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED", "BATCH_SCOPE")
    _need(_name(batch["batch_id"]) and _name(batch["topic"]), "BATCH_IDENTITY")
    _need(_exact(batch["controls"], CONTROLS), "AUTHORITY_BOUNDARY")
    data = batch["source_projection"]
    _need(isinstance(data, dict) and set(data) == PROJECTION_FIELDS, "PROJECTION_FIELDS")
    basename = data["source_basename"]
    _need(isinstance(basename, str) and 0 < len(basename) <= 255
          and basename not in {".", ".."} and not any(c in basename for c in '/\\\r\n\x00')
          and type(data["source_bytes"]) is int
          and 0 < data["source_bytes"] <= MAX_BYTES and data["source_bytes"] % 2 == 0
          and _hash(data["source_sha256"]), "RAW_PROVENANCE")
    labels = data["column_labels"]
    _need(isinstance(labels, list) and all(isinstance(c, str) for c in labels), "SOURCE_SCHEMA")
    _need(isinstance(data["date_header"], str), "SOURCE_DATE")
    _need(len(labels) == len(set(labels)) and set(labels) == set(BASE_COLUMNS) | set(_monthly_columns(data["date_header"])), "SOURCE_SCHEMA")
    public = [c for c in labels if c not in EXCLUDED_COLUMNS]
    excluded = [c for c in labels if c in EXCLUDED_COLUMNS]
    _need(len(public) == 21 and _exact(data["public_columns"], public)
          and _exact(data["excluded_columns"], excluded), "PRIVACY_COLUMNS")
    records = data["records"]
    _need(isinstance(records, list) and len(records) <= MAX_RECORDS, "RECORD_BOUND")
    expected_context = dict(CONTEXT, ui_idea_count=len(records))
    _need(_exact(batch["ui_context"], expected_context), "RESEARCH_CONTEXT")
    seeds = batch["input_seeds"]
    _need(isinstance(seeds, list) and 1 <= len(seeds) <= 10
          and all(isinstance(s, str) and bool(_normalized_keyword(s)) for s in seeds)
          and len(set(seeds)) == len(set(map(normalize, seeds))) == len(seeds), "SEED_IDENTITIES")
    groups = {}
    previous = 3
    for record in records:
        _need(isinstance(record, dict) and set(record) == {"source_line", "values"}, "RECORD_FIELDS")
        line = record["source_line"]
        # Public cells cannot prove how many newlines occurred in excluded cells.
        # Preserve physical starts; optional private equality verifies exact gaps.
        _need(type(line) is int and previous < line <= data["source_bytes"], "SOURCE_LINE")
        _need(previous != 3 or line == 4, "FIRST_SOURCE_LINE")
        previous = line
        values = record["values"]
        _need(isinstance(values, dict) and list(values) == public
              and all(v is None or isinstance(v, str) for v in values.values()), "EXACT_PUBLIC_CELLS")
        key = _normalized_keyword(values["Keyword"])
        groups.setdefault(key, []).append(line)
    duplicates = [{"normalized_keyword": key, "source_lines": lines}
                  for key, lines in groups.items() if len(lines) > 1]
    _need(_exact(data["record_count"], len(records))
          and _exact(data["distinct_normalized_count"], len(groups))
          and _exact(data["duplicate_groups"], duplicates), "COUNTS_OR_DUPLICATES")
    missing = [{"seed": seed, "grouped_under": None} for seed in seeds if normalize(seed) not in groups]
    _need(_exact(batch["seed_reconciliation"], {"exact_returned": len(seeds) - len(missing),
                                              "without_separate_exact_row": missing}), "SEED_RECONCILIATION")
    return Counter({key: len(lines) for key, lines in groups.items()})


def project_discovery(raw_path: Path, *, topic: str, batch_id: str,
                      input_seeds: list, ui_context: dict,
                      expected_source_sha256: str) -> dict:
    """Propose an unreviewed batch using separately observed UI context.

    Never derive the UI count from the export to make a mismatch pass. This
    reads one private export; it writes nothing and confers no review authority.
    """
    _need(_hash(expected_source_sha256), "EXPECTED_SOURCE_HASH")
    _need(isinstance(input_seeds, list) and isinstance(ui_context, dict), "PROJECTION_INPUTS")
    data = parse_discovery(raw_path)
    _need(data["source_sha256"] == expected_source_sha256, "SOURCE_HASH_MISMATCH")
    returned = {_normalized_keyword(r["values"]["Keyword"]) for r in data["records"]}
    # Validate seed types before normalization; never print source cells/errors.
    _need(all(isinstance(s, str) for s in input_seeds), "SEED_IDENTITIES")
    missing = [{"seed": seed, "grouped_under": None}
               for seed in input_seeds if normalize(seed) not in returned]
    batch = {"version": 1, "scope": "AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED",
             "batch_id": batch_id, "topic": topic, "input_seeds": list(input_seeds),
             "ui_context": dict(ui_context), "source_projection": data,
             "seed_reconciliation": {"exact_returned": len(input_seeds) - len(missing),
                                     "without_separate_exact_row": missing},
             "controls": dict(CONTROLS)}
    _batch(batch)
    return batch


def assemble_capture(batches: list, *, capture_date_dubai: str) -> dict[str, bytes]:
    """Return canonical public capture bytes, without a filesystem/network writer.

    Callers must separately verify actual UI evidence, privacy and source pins.
    The unchanged verifier remains the acceptance boundary after serialization.
    """
    _need(isinstance(batches, list) and 1 <= len(batches) <= 32, "SOURCE_FILES")
    _need(isinstance(capture_date_dubai, str)
          and date.fromisoformat(capture_date_dubai).isoformat() == capture_date_dubai, "CAPTURE_DATE")
    def encode(value):
        return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output, items, ids, topics = {}, [], set(), set()
    keys, presence = Counter(), Counter()
    for batch in batches:
        local = _batch(batch)
        topic, identity = batch["topic"], batch["batch_id"]
        filename = topic + ".json"
        _need(_name(filename, ".json") and filename != "capture.json", "SOURCE_FILE_IDENTITY")
        _need(identity not in ids and topic not in topics, "DUPLICATE_BATCH_OR_TOPIC")
        ids.add(identity); topics.add(topic)
        blob = encode(batch)
        output[filename] = blob
        data = batch["source_projection"]
        items.append({"file": filename, "batch_id": identity,
                      "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob),
                      "records": data["record_count"], "distinct_normalized": len(local),
                      "source_bytes": data["source_bytes"], "source_sha256": data["source_sha256"]})
        keys.update(local); presence.update(local.keys())
    total = sum(keys.values())
    output["capture.json"] = encode({"version": 1, "scope": "AUTHENTIC_UNREVIEWED_DISCOVERY_ONLY",
        "account_id": CONTEXT["account_id"], "capture_date_dubai": capture_date_dubai,
        "source_files": items, "totals": {"export_rows": total,
            "distinct_normalized_phrases": len(keys), "repeated_occurrences": total - len(keys),
            "duplicate_phrase_groups": sum(v > 1 for v in keys.values()),
            "cross_batch_overlap_groups": sum(v > 1 for v in presence.values())},
        "master_contribution": dict(MASTER)})
    return output


def verify_capture(folder: Path, pins: dict, sources: dict | None = None) -> dict:
    """Verify pinned public batches, optionally exact private TSV projections.

    ``sources`` maps declared topic to private raw path. Output contains counts
    and topic names only; no private paths, cells or metric aggregation.
    """
    folder = Path(folder).resolve()
    _need(isinstance(pins, dict) and 2 <= len(pins) <= 33
          and "capture.json" in pins and all(_name(k, ".json") and _hash(v) for k, v in pins.items()), "PINS")
    loaded, sizes = {}, {}
    for filename, expected in pins.items():
        path = folder / filename
        _need(path.resolve().parent == folder, "CAPTURE_PATH")
        try:
            with path.open("rb") as stream:
                blob = stream.read(MAX_BYTES * 8 + 1)
        except OSError:
            raise ValueError("CAPTURE_READ_FAILED") from None
        _need(len(blob) <= MAX_BYTES * 8 and hashlib.sha256(blob).hexdigest() == expected, "CAPTURE_BYTES_CHANGED")
        loaded[filename] = parse_json_bytes(blob)
        sizes[filename] = len(blob)
    index = loaded["capture.json"]
    required = {"version", "scope", "account_id", "capture_date_dubai", "source_files", "totals", "master_contribution"}
    _need(isinstance(index, dict) and required <= set(index) <= required | {"notes", "normalization"}, "MANIFEST_FIELDS")
    _need(_exact(index["version"], 1) and index["scope"] == "AUTHENTIC_UNREVIEWED_DISCOVERY_ONLY"
          and index["account_id"] == CONTEXT["account_id"], "MANIFEST_CONTEXT")
    _need(isinstance(index["capture_date_dubai"], str)
          and date.fromisoformat(index["capture_date_dubai"]).isoformat() == index["capture_date_dubai"], "CAPTURE_DATE")
    _need(_exact(index["master_contribution"], MASTER), "MASTER_PROMOTION_FORBIDDEN")
    items = index["source_files"]
    _need(isinstance(items, list) and 1 <= len(items) <= 32, "SOURCE_FILES")
    seen_files, seen_ids, seen_topics = set(), set(), set()
    keys, batch_presence, total, batches = Counter(), Counter(), 0, []
    item_fields = {"file", "batch_id", "sha256", "bytes", "records", "distinct_normalized", "source_bytes", "source_sha256"}
    for item in items:
        _need(isinstance(item, dict) and set(item) == item_fields, "SOURCE_MANIFEST_FIELDS")
        filename = item["file"]
        _need(_name(filename, ".json") and filename != "capture.json" and filename in loaded
              and filename not in seen_files, "SOURCE_FILE_IDENTITY")
        batch = loaded[filename]
        local = _batch(batch)
        _need(batch["batch_id"] == item["batch_id"] and batch["batch_id"] not in seen_ids
              and batch["topic"] not in seen_topics, "DUPLICATE_BATCH_OR_TOPIC")
        data = batch["source_projection"]
        expected = {"file": filename, "batch_id": batch["batch_id"], "sha256": pins[filename],
                    "bytes": sizes[filename], "records": data["record_count"],
                    "distinct_normalized": data["distinct_normalized_count"],
                    "source_bytes": data["source_bytes"], "source_sha256": data["source_sha256"]}
        _need(_exact(item, expected), "INDEX_BINDING")
        seen_files.add(filename); seen_ids.add(batch["batch_id"]); seen_topics.add(batch["topic"])
        keys.update(local); batch_presence.update(local.keys())
        total += data["record_count"]; batches.append(batch)
    _need(set(pins) == seen_files | {"capture.json"}, "UNDECLARED_PINNED_FILE")
    _need(_exact(index["totals"], {"export_rows": total, "distinct_normalized_phrases": len(keys),
          "repeated_occurrences": total - len(keys),
          "duplicate_phrase_groups": sum(v > 1 for v in keys.values()),
          "cross_batch_overlap_groups": sum(v > 1 for v in batch_presence.values())}), "UNION_COUNTS")
    if sources is None:
        sources = {}
    _need(isinstance(sources, dict) and set(sources) <= seen_topics, "UNKNOWN_PRIVATE_TOPIC")
    private = []
    for batch in batches:
        topic = batch["topic"]
        if topic in sources:
            raw = parse_discovery(sources[topic])
            raw["source_basename"] = batch["source_projection"]["source_basename"]
            _need(_exact(raw, batch["source_projection"]), "PRIVATE_RAW_PROJECTION_MISMATCH")
            private.append(topic)
    scope = ("PRIVATE_RAW_EQUIVALENCE" if len(private) == len(batches) else
             "PARTIAL_PRIVATE_RAW_EQUIVALENCE" if private else "PUBLIC_CONSISTENCY_ONLY")
    return {"passed": True, "scope": scope, "raw_batches_verified": sorted(private),
            "export_rows": total, "distinct_phrases": len(keys), **MASTER,
            "deployment_authorized": False}


def overlap_report(original_batches: list, supplemental_batches: list) -> dict:
    """Compare separately verified batches; retain every occurrence, never metrics.

    Inputs are capture batch documents. This validates structure but does not
    authenticate their bytes; callers must verify each capture's pins first.
    """
    _need(isinstance(original_batches, list) and isinstance(supplemental_batches, list)
          and bool(original_batches) and bool(supplemental_batches)
          and len(original_batches) + len(supplemental_batches) <= 64, "BATCH_LISTS")
    seen, phrases, sets, counts = set(), {}, [], []
    for label, batches in (("original", original_batches), ("supplemental", supplemental_batches)):
        keys, occurrences = set(), 0
        for batch in batches:
            _batch(batch)
            identity = batch["batch_id"]
            _need(identity not in seen, "DUPLICATE_BATCH_ID")
            seen.add(identity)
            data = batch["source_projection"]
            for record in data["records"]:
                text = record["values"]["Keyword"]; key = normalize(text)
                entry = phrases.setdefault(key, {"normalized_text": key, "original_forms": [],
                                                  "original_refs": [], "supplemental_refs": []})
                if text not in entry["original_forms"]:
                    entry["original_forms"].append(text)
                entry[label + "_refs"].append({"batch_id": identity, "topic": batch["topic"],
                    "source_basename": data["source_basename"], "source_sha256": data["source_sha256"],
                    "source_line": record["source_line"]})
                keys.add(key); occurrences += 1
        sets.append(keys); counts.append(occurrences)
    old, new = sets
    return {"scope": "OBSERVED_CAPTURE_OVERLAP_ONLY", "counts": {
        "original_unique": len(old), "supplemental_unique": len(new),
        "overlap_unique": len(old & new), "original_only_unique": len(old - new),
        "supplemental_only_unique": len(new - old), "combined_unique": len(old | new),
        "original_occurrences": counts[0], "supplemental_occurrences": counts[1],
        "combined_occurrences": sum(counts), "repeated_occurrences": sum(counts) - len(old | new)},
        "phrases": [phrases[key] for key in sorted(phrases)],
        "classification_inherited": False, "deployment_authorized": False}
