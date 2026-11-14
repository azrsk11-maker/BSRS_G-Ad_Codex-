"""Bounded read-only intake of official published Ofqual qualification titles.

Titles are public reference metadata, not observed searches, reviewed negatives,
search-volume evidence, UAE credentials or current course-delivery claims.
This module has no HTTP client, filesystem writer or admission integration.
"""
from __future__ import annotations

from collections import Counter
import csv
from datetime import date, datetime
import hashlib
import io
import json
from pathlib import Path
import re

from keyword_audit import normalize, parse_json_bytes

MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_PUBLIC_BYTES = 1024 * 1024
MAX_SOURCE_ROWS = 100_000
MAX_MATCH_ROWS = 1_000
MAX_FIELD_BYTES = 16_384
SOURCE_URL = "https://downloads.find-a-qualification.services.ofqual.gov.uk/extracts/Qualifications.csv"
INDEX_URL = "https://www.gov.uk/find-a-regulated-qualification"
NOTICE_URL = "https://find-a-qualification.services.ofqual.gov.uk/find-regulated-qualifications"
LICENCE_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."
LEXICAL_PATTERN = r"\b(real[ -]estate|property|housing|valuation|survey(?:ing|or)|lettings?|mortgage|conveyancing)\b"
LEXICAL = re.compile(LEXICAL_PATTERN, re.IGNORECASE)
HEADERS = (
    "Qualification Number", "Qualification Title", "Owner Organisation Recognition Number",
    "Owner Organisation Name", "Owner Organisation Acronym", "Qualification Level",
    "Qualification Sub Level", "EQF Level", "Qualification Type", "Total Credits",
    "Qualification SSA", "Qualification Status", "Regulation Start Date",
    "Operational Start Date", "Operational End Date", "Certification End Date",
    "Minimum Guided Learning Hours", "Maximum Guided Learning Hours",
    "Total Qualification Time", "Guided Learning Hours", "Offered In England",
    "Offered In Northern Ireland", "Overall Grading Type", "Assessment Methods",
    "NI Discount Code", "GCE Size Equivalence", "GCSE Size Equivalence",
    "Entitlement Framework Designation", "Grading Scale", "Specialisms", "Pathways",
    "Approved For DEL Funded Programme", "Link To Specification",
    "Currently and / or will consider offering internationally",
    "Apprenticeship Standard Reference Number", "Apprenticeship Standard Title",
)
PUBLIC_FIELDS = (
    "Qualification Number", "Qualification Title", "Owner Organisation Name",
    "Qualification Level", "Qualification Type", "Qualification SSA",
    "Qualification Status", "Operational Start Date", "Operational End Date",
    "Certification End Date",
)
STATUSES = ("Available to learners", "No longer available to new learners",
            "No longer awarded", "Not yet available to learners")
CONTROLS = {
    "source_supply_only": True, "published_titles_not_observed_queries": True,
    "reviewed": False, "approved": False, "deployed": False,
    "semantic_review_complete": False, "current_membership_verified": False,
    "research_registry_entry_created": False, "master_rows_added": 0,
    "live_campaign_changes": False, "raw_source_committed": False,
    "measured_volume": None, "measured_cpc": None,
}
MASTER = {"reviewed_positive": 0, "reviewed_negative": 0,
          "approved_positive": 0, "approved_negative": 0, "deployed": 0}
PROJECTION_FIELDS = {
    "version", "scope", "source_url", "source_type_compatibility", "source_encoding",
    "source_bytes", "source_sha256", "source_headers", "header_source_line_start",
    "header_source_line_end", "source_record_count", "source_status_counts",
    "lexical_pattern", "public_fields", "records", "summary", "controls",
}


def _need(ok, code):
    if not ok:
        raise ValueError(code)


def _exact(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(_exact(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(_exact(a, b) for a, b in zip(actual, expected))
    return actual == expected


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _read(path, bound):
    try:
        with Path(path).open("rb") as stream:
            content = stream.read(bound + 1)
    except OSError:
        raise ValueError("INPUT_UNAVAILABLE") from None
    _need(0 < len(content) <= bound, "INPUT_BYTE_BOUND")
    return content


def _cell(value):
    _need(type(value) is str, "CELL_TYPE")
    try:
        valid = len(value.encode("utf-8")) <= MAX_FIELD_BYTES
    except UnicodeError:
        valid = False
    _need(valid and not any(ord(c) < 32 and c not in "\t\r\n" for c in value), "CELL_FORMAT_OR_BOUND")


def _metadata(values):
    for value in values.values():
        _cell(value)
    _need(re.fullmatch(r"(?:[0-9]{3}/[0-9]{4}/[0-9Xx]|Q[0-9]{7,10})",
                       values["Qualification Number"]) is not None, "QUALIFICATION_ID")
    _need(bool(normalize(values["Qualification Title"])), "EMPTY_TITLE")
    _need(values["Qualification Status"] in STATUSES, "STATUS_SCHEMA")
    for field in ("Operational Start Date", "Operational End Date", "Certification End Date"):
        value = values[field]
        if value:
            try:
                valid = (re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}", value)
                         and datetime.fromisoformat(value))
            except ValueError:
                valid = False
            _need(bool(valid), "SOURCE_DATE_FORMAT")


def _csv_quoting(text):
    """Reject stray unquoted quotes that csv.reader(strict=True) accepts."""
    state = "start"
    for char in text:
        if state == "quoted":
            if char == '"':
                state = "closed"
        elif state == "closed":
            if char == '"':
                state = "quoted"
            elif char in ",\r\n":
                state = "start"
            else:
                raise ValueError("CSV_QUOTING")
        elif char == '"':
            _need(state == "start", "CSV_QUOTING")
            state = "quoted"
        elif char in ",\r\n":
            state = "start"
        else:
            state = "unquoted"
    _need(state != "quoted", "CSV_QUOTING")


def _summary(records):
    groups = {}
    titles = []
    statuses = Counter()
    for record in records:
        title = record["values"]["Qualification Title"]
        titles.append(title)
        groups.setdefault(normalize(title), []).append(record["source_record_ordinal"])
        statuses[record["values"]["Qualification Status"]] += 1
    return {
        "lexical_rows": len(records), "distinct_literal_titles": len(set(titles)),
        "distinct_normalized_titles": len(groups),
        "rows_at_most_80_characters": sum(len(t) <= 80 for t in titles),
        "rows_over_80_characters": sum(len(t) > 80 for t in titles),
        "repeated_normalized_occurrences": len(records) - len(groups),
        "duplicate_normalized_groups": [
            {"normalized_title": key, "source_record_ordinals": ordinals}
            for key, ordinals in groups.items() if len(ordinals) > 1],
        "published_status_counts": {s: statuses[s] for s in STATUSES},
    }


def parse_source(path, *, expected_source_sha256):
    """Freshly read a complete pinned private CSV; return public metadata only."""
    _need(_hash(expected_source_sha256), "EXPECTED_SOURCE_HASH")
    raw = _read(path, MAX_SOURCE_BYTES)
    _need(hashlib.sha256(raw).hexdigest() == expected_source_sha256, "SOURCE_HASH_MISMATCH")
    try:
        decoded = raw.decode("utf-8-sig", errors="strict")
    except UnicodeError:
        raise ValueError("SOURCE_ENCODING") from None
    _csv_quoting(decoded)
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        headers = next(reader, None)
        _need(headers == list(HEADERS), "EXACT_SOURCE_HEADERS")
        header_end = reader.line_num
        records, ids, statuses = [], set(), Counter()
        ordinal = 0
        while True:
            start = reader.line_num + 1
            row = next(reader, None)
            if row is None:
                break
            ordinal += 1
            _need(ordinal <= MAX_SOURCE_ROWS, "SOURCE_ROW_BOUND")
            _need(len(row) == len(HEADERS), "SOURCE_RECORD_WIDTH")
            for value in row:
                _cell(value)
            original = dict(zip(HEADERS, row))
            values = {field: original[field] for field in PUBLIC_FIELDS}
            _metadata(values)
            identity = values["Qualification Number"]
            _need(identity not in ids, "DUPLICATE_QUALIFICATION_ID")
            ids.add(identity)
            statuses[values["Qualification Status"]] += 1
            if LEXICAL.search(values["Qualification Title"]):
                _need(len(records) < MAX_MATCH_ROWS, "MATCH_ROW_BOUND")
                records.append({"source_record_ordinal": ordinal, "source_line_start": start,
                                "source_line_end": reader.line_num, "values": values})
    except (csv.Error, OverflowError):
        raise ValueError("SOURCE_CSV_FORMAT") from None
    _need(ordinal > 0, "EMPTY_SOURCE")
    projection = {
        "version": 1, "scope": "OFFICIAL_PUBLISHED_QUALIFICATION_TITLES_UNREVIEWED",
        "source_url": SOURCE_URL, "source_type_compatibility": "official_reference",
        "source_encoding": "UTF-8 with BOM" if raw.startswith(b"\xef\xbb\xbf") else "UTF-8 without BOM",
        "source_bytes": len(raw), "source_sha256": expected_source_sha256,
        "source_headers": list(HEADERS), "header_source_line_start": 1,
        "header_source_line_end": header_end, "source_record_count": ordinal,
        "source_status_counts": {s: statuses[s] for s in STATUSES},
        "lexical_pattern": LEXICAL_PATTERN, "public_fields": list(PUBLIC_FIELDS),
        "records": records, "summary": _summary(records), "controls": dict(CONTROLS),
    }
    validate_projection(projection)
    return projection


def validate_projection(data):
    """Structural consistency only; public metadata cannot prove raw coverage."""
    _need(type(data) is dict and set(data) == PROJECTION_FIELDS, "PROJECTION_FIELDS")
    _need(_exact(data["version"], 1)
          and data["scope"] == "OFFICIAL_PUBLISHED_QUALIFICATION_TITLES_UNREVIEWED"
          and data["source_url"] == SOURCE_URL
          and data["source_type_compatibility"] == "official_reference", "SOURCE_SCOPE")
    _need(_exact(data["controls"], CONTROLS), "AUTHORITY_BOUNDARY")
    _need(type(data["source_bytes"]) is int and 0 < data["source_bytes"] <= MAX_SOURCE_BYTES
          and _hash(data["source_sha256"]), "SOURCE_PROVENANCE")
    _need(type(data["source_encoding"]) is str
          and data["source_encoding"] in {"UTF-8 with BOM", "UTF-8 without BOM"}
          and _exact(data["source_headers"], list(HEADERS))
          and _exact(data["public_fields"], list(PUBLIC_FIELDS))
          and data["lexical_pattern"] == LEXICAL_PATTERN, "SOURCE_SCHEMA")
    _need(type(data["source_record_count"]) is int
          and 0 < data["source_record_count"] <= MAX_SOURCE_ROWS
          and _exact(data["header_source_line_start"], 1)
          and _exact(data["header_source_line_end"], 1), "SOURCE_HEADER_PROVENANCE")
    statuses = data["source_status_counts"]
    _need(type(statuses) is dict and set(statuses) == set(STATUSES)
          and all(type(n) is int and n >= 0 for n in statuses.values())
          and sum(statuses.values()) == data["source_record_count"], "SOURCE_STATUS_COUNTS")
    records = data["records"]
    _need(type(records) is list and len(records) <= min(MAX_MATCH_ROWS, data["source_record_count"]), "RECORD_BOUND")
    previous_ordinal, previous_end, ids = 0, data["header_source_line_end"], set()
    for record in records:
        _need(type(record) is dict and set(record) == {
            "source_record_ordinal", "source_line_start", "source_line_end", "values"}, "RECORD_FIELDS")
        ordinal, start, end = (record[k] for k in ("source_record_ordinal", "source_line_start", "source_line_end"))
        _need(all(type(n) is int for n in (ordinal, start, end))
              and previous_ordinal < ordinal <= data["source_record_count"]
              and previous_end < start <= end <= data["source_bytes"]
              and start - previous_end >= ordinal - previous_ordinal, "ROW_PROVENANCE")
        values = record["values"]
        _need(type(values) is dict and list(values) == list(PUBLIC_FIELDS), "PUBLIC_COLUMNS")
        _metadata(values)
        _need(LEXICAL.search(values["Qualification Title"]) is not None, "LEXICAL_MEMBERSHIP")
        _need(values["Qualification Number"] not in ids, "DUPLICATE_QUALIFICATION_ID")
        ids.add(values["Qualification Number"])
        previous_ordinal, previous_end = ordinal, end
    summary = _summary(records)
    _need(_exact(data["summary"], summary), "SUMMARY_OR_GROUPS")
    _need(all(summary["published_status_counts"][s] <= statuses[s] for s in STATUSES), "STATUS_COVERAGE")
    return summary


def _manifest(projection, projection_bytes, metadata):
    _need(type(metadata) is dict and set(metadata) == {
        "capture_date_utc", "http_date", "http_last_modified", "content_type"}, "CAPTURE_METADATA_FIELDS")
    try:
        capture_day = date.fromisoformat(metadata["capture_date_utc"])
        http_day = datetime.fromisoformat(metadata["http_date"].replace("Z", "+00:00"))
        modified = datetime.fromisoformat(metadata["http_last_modified"].replace("Z", "+00:00"))
        valid = (capture_day.isoformat() == metadata["capture_date_utc"]
                 and http_day.tzinfo is not None and modified.tzinfo is not None
                 and http_day.utcoffset().total_seconds() == 0
                 and modified.utcoffset().total_seconds() == 0
                 and modified <= http_day and http_day.date() == capture_day)
    except (TypeError, ValueError, AttributeError):
        valid = False
    _need(valid and metadata["content_type"] == "application/octet-stream", "CAPTURE_METADATA_FORMAT")
    return {
        "version": 1, "scope": "OFFICIAL_SOURCE_INTAKE_ONLY_UNREVIEWED",
        "capture_metadata": dict(metadata),
        "source": {"url": SOURCE_URL, "download_index_url": INDEX_URL,
                   "sha256": projection["source_sha256"], "bytes": projection["source_bytes"],
                   "encoding": projection["source_encoding"], "records": projection["source_record_count"]},
        "licence": {"name": "Open Government Licence v3.0, except where otherwise stated",
                    "url": LICENCE_URL, "notice_url": NOTICE_URL, "attribution": ATTRIBUTION,
                    "third_party_exceptions_preserved": True},
        "projection": {"file": "qualifications.json", "sha256": hashlib.sha256(projection_bytes).hexdigest(),
                       "bytes": len(projection_bytes), "records": len(projection["records"]),
                       "distinct_normalized_titles": projection["summary"]["distinct_normalized_titles"]},
        "master_contribution": dict(MASTER), "controls": dict(CONTROLS),
    }


def assemble_capture(projection, *, metadata):
    """Return deterministic public bytes; callers separately choose persistence."""
    validate_projection(projection)
    encode = lambda value: (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    projected = encode(projection)
    manifest = encode(_manifest(projection, projected, metadata))
    _need(len(projected) <= MAX_PUBLIC_BYTES and len(manifest) <= MAX_PUBLIC_BYTES, "PUBLIC_BYTE_BOUND")
    return {"qualifications.json": projected, "capture.json": manifest}


def verify_capture(folder, pins, source=None):
    """Pinned public checks; optional complete raw reprojection is freshly read."""
    _need(type(pins) is dict and set(pins) == {"qualifications.json", "capture.json"}
          and all(_hash(pin) for pin in pins.values()), "PUBLIC_PINS")
    blobs, parsed = {}, {}
    for name, expected in pins.items():
        blob = _read(Path(folder) / name, MAX_PUBLIC_BYTES)
        _need(hashlib.sha256(blob).hexdigest() == expected, "PUBLIC_PIN_MISMATCH")
        try:
            parsed[name] = parse_json_bytes(blob)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ValueError("PUBLIC_JSON_INVALID") from None
        blobs[name] = blob
    projection, manifest = parsed["qualifications.json"], parsed["capture.json"]
    summary = validate_projection(projection)
    _need(type(manifest) is dict and "capture_metadata" in manifest, "MANIFEST_FIELDS")
    _need(_exact(manifest, _manifest(projection, blobs["qualifications.json"], manifest["capture_metadata"])), "MANIFEST_CONSISTENCY")
    if source is not None:
        _need(_exact(parse_source(source, expected_source_sha256=projection["source_sha256"]), projection), "RAW_PROJECTION_MISMATCH")
    return {"passed": True, "scope": "PRIVATE_RAW_EQUIVALENCE" if source is not None else "PUBLIC_CONSISTENCY_ONLY",
            "source_records": projection["source_record_count"], "lexical_rows": summary["lexical_rows"],
            "distinct_normalized_titles": summary["distinct_normalized_titles"],
            "rows_at_most_80_characters": summary["rows_at_most_80_characters"],
            "reviewed": False, "master_rows_added": 0, "deployment_authorized": False}
