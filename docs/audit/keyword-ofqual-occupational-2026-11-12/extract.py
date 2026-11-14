"""Bounded official occupational-title extraction and fresh optional raw verification.

No network, admission, current-library reconstruction or existing-file writer.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tools/keyword-system"))
import keyword_audit as ka
import ofqual_discovery as od

SOURCE_SHA256 = "ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5"
SOURCE_BYTES = 23984795
SOURCE_RECORDS = 53175
PREVIOUS = "docs/audit/keyword-ofqual-discovery-2026-11-11/qualifications.json"
PREVIOUS_SHA256 = "2869cab8a06a76fa113ef430b28d09c53a324b72555cd0b3b36d3bdf82de4ccc"
CAPTURE = "docs/audit/keyword-ofqual-discovery-2026-11-11/capture.json"
CAPTURE_SHA256 = "40563540ed29d76e03e2bea8be1a46aca960d888c138fcc2f9ac2f54dec2e9f7"
STATUS = "Available to learners"
MAX_CANDIDATE_GROUPS = 600
MAX_CHARS = 80
MAX_WORDS = 10
TOPIC_PATTERNS = {
    "hair": r"\bhair(?:dressing|dresser)?\b",
    "beauty": r"\bbeauty\b",
    "barber": r"\bbarber(?:ing)?\b",
    "nail": r"\bnails?\b",
    "makeup": r"\bmake[ -]?up\b",
    "culinary": r"\bculinary\b",
    "catering": r"\bcatering\b",
    "food_safety": r"\bfood[ -]safety\b",
}
TOPICS = {key: re.compile(pattern, re.IGNORECASE) for key, pattern in TOPIC_PATTERNS.items()}
CONTROLS = {
    "source_supply_only": True,
    "semantic_review_complete": False,
    "independent_review_complete": False,
    "current_library_membership_verified": False,
    "protected_query_and_scope_clearance": False,
    "duplicate_and_variant_clearance": False,
    "source_status_is_local_delivery_or_recognition": False,
    "published_titles_are_observed_queries": False,
    "metrics_status": "NOT_OBSERVED_UNKNOWN",
    "volume": None,
    "cpc": None,
    "competition": None,
    "research_master_rows_added": 0,
    "approved_exclusions": 0,
    "deployments": 0,
    "registry_changed": False,
    "existing_evidence_changed": False,
    "raw_source_committed": False,
    "live_campaign_changes": False,
    "production_changed": False,
    "deployment_authorized": False,
}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def sha(content):
    return hashlib.sha256(content).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def read_bound(path, bound):
    with Path(path).open("rb") as stream:
        content = stream.read(bound + 1)
    need(0 < len(content) <= bound, "FILE_BYTE_BOUND")
    return content


def prior_projection():
    content = read_bound(ROOT / PREVIOUS, 1024 * 1024)
    need(sha(content) == PREVIOUS_SHA256, "PREVIOUS_PROJECTION_PIN")
    previous = ka.parse_json_bytes(content)
    need(len(previous["records"]) == 338, "PREVIOUS_ROW_COUNT")
    capture = read_bound(ROOT / CAPTURE, 1024 * 1024)
    need(sha(capture) == CAPTURE_SHA256, "PREVIOUS_CAPTURE_PIN")
    need(previous["source_sha256"] == SOURCE_SHA256, "PREVIOUS_RAW_PIN")
    return previous


def selected_topics(title):
    return [key for key, pattern in TOPICS.items() if pattern.search(title)]


def decorate(record):
    title = record["values"]["Qualification Title"]
    words = len(title.split())
    characters = len(title)
    reasons = []
    if characters > MAX_CHARS:
        reasons.append("OVER_80_CHARACTERS_COMPLETE_TITLE_HELD")
    if words > MAX_WORDS:
        reasons.append("OVER_10_WHITESPACE_WORDS_COMPLETE_TITLE_HELD")
    return {
        **record,
        "normalized_title": ka.normalize(title),
        "topic_matches": selected_topics(title),
        "characters": characters,
        "whitespace_words": words,
        "local_length_word_precheck_pass": not reasons,
        "local_precheck_holds": reasons,
        "semantic_review": "PENDING",
        "proposed_matching_limit": "COMPLETE_ORIGINAL_LITERAL_ONLY_FOR_LATER_EXACT_REVIEW",
        "campaign_page_and_protected_scope": "PENDING_NOT_SELECTED",
    }


def summary(records, topic_statuses, omitted_previous):
    eligible = [row for row in records if row["local_length_word_precheck_pass"]]
    held = [row for row in records if not row["local_length_word_precheck_pass"]]
    groups = {}
    for row in records:
        groups.setdefault(row["normalized_title"], []).append(row["source_record_ordinal"])
    candidate_groups = {row["normalized_title"] for row in eligible}
    need(len(candidate_groups) <= MAX_CANDIDATE_GROUPS, "CANDIDATE_GROUP_BOUND_NO_TRUNCATION")
    return {
        "all_source_topic_occurrences": sum(topic_statuses.values()),
        "all_source_topic_status_counts": {status: topic_statuses.get(status, 0) for status in od.STATUSES},
        "outside_selected_source_status_occurrences": sum(topic_statuses.values()) - topic_statuses.get(STATUS, 0),
        "already_projected_occurrences_omitted": omitted_previous,
        "retained_source_occurrences": len(records),
        "retained_distinct_normalized_titles": len(groups),
        "precheck_candidate_occurrences": len(eligible),
        "precheck_candidate_distinct_normalized_titles": len(candidate_groups),
        "length_or_word_count_held_occurrences": len(held),
        "length_or_word_count_held_distinct_normalized_titles": len({row["normalized_title"] for row in held}),
        "over_80_characters_occurrences": sum(row["characters"] > MAX_CHARS for row in records),
        "over_10_whitespace_words_occurrences": sum(row["whitespace_words"] > MAX_WORDS for row in records),
        "candidate_topic_occurrences": {topic: sum(topic in row["topic_matches"] for row in eligible) for topic in TOPICS},
        "duplicate_normalized_groups": [{"normalized_title": key, "source_record_ordinals": values}
                                        for key, values in groups.items() if len(values) > 1],
        "distinctness_limit": "Normalized-title grouping only; route, provider-prefix, alias, concept and Google matching equivalence remain unreviewed.",
        "current_library_novel_candidate_count": None,
        "admissible_candidate_count": None,
    }


def make_projection(records, topic_statuses, omitted_previous, previous):
    return {
        "version": 1,
        "scope": "OFFICIAL_OCCUPATIONAL_TITLES_SOURCE_EXTRACTION_UNREVIEWED_NOT_ADMISSION",
        "extraction_date_dubai": "2026-11-12",
        "original_capture_date_utc": "2026-11-11",
        "source_url": od.SOURCE_URL,
        "source_type_compatibility": "official_reference",
        "source_sha256": SOURCE_SHA256,
        "source_bytes": SOURCE_BYTES,
        "source_record_count": SOURCE_RECORDS,
        "source_encoding": "UTF-8 with BOM",
        "source_headers": list(od.HEADERS),
        "header_source_line_start": 1,
        "header_source_line_end": previous["header_source_line_end"],
        "source_status_counts": previous["source_status_counts"],
        "previous_projection": {"file": PREVIOUS, "sha256": PREVIOUS_SHA256,
                                "excluded_source_record_ordinals": [row["source_record_ordinal"] for row in previous["records"]]},
        "selection": {
            "meaning_boundary": "Complete officially published occupational-training qualification titles with an explicit selected hair/beauty/barber/nail/makeup/culinary/catering/food-safety expression, and source-published Available to learners status.",
            "topic_patterns": TOPIC_PATTERNS,
            "published_status": STATUS,
            "original_338_projection_ordinals_excluded": True,
            "all_matching_selected_status_rows_retained_without_quota_truncation": True,
            "historical_and_other_status_rows_counted_but_not_selected": True,
            "local_screen": {"maximum_characters": MAX_CHARS, "maximum_whitespace_words": MAX_WORDS,
                             "held_full_titles_retained": True, "rewriting_or_shortening": False,
                             "platform_acceptance_claimed": False},
            "normalization": "Existing keyword_audit.normalize unchanged; NFKC, one matching-wrapper removal, casefold and whitespace collapse.",
            "candidate_distinct_title_bound": MAX_CANDIDATE_GROUPS,
            "research_pool_or_target_change": False,
        },
        "public_fields": list(od.PUBLIC_FIELDS),
        "records": records,
        "summary": summary(records, topic_statuses, omitted_previous),
        "controls": CONTROLS,
    }


def extract(source):
    previous = prior_projection()
    excluded = {row["source_record_ordinal"] for row in previous["records"]}
    raw = read_bound(source, SOURCE_BYTES)
    need(len(raw) == SOURCE_BYTES and sha(raw) == SOURCE_SHA256, "EXACT_RAW_CAPTURE_PIN")
    need(raw.startswith(b"\xef\xbb\xbf"), "SOURCE_BOM")
    decoded = raw.decode("utf-8-sig", errors="strict")
    od._csv_quoting(decoded)
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    need(next(reader, None) == list(od.HEADERS), "EXACT_SOURCE_HEADERS")
    need(reader.line_num == previous["header_source_line_end"], "HEADER_LINES")
    rows, qualification_ids = [], set()
    all_statuses, topic_statuses = Counter(), Counter()
    ordinal = 0
    omitted = 0
    while True:
        start = reader.line_num + 1
        row = next(reader, None)
        if row is None:
            break
        ordinal += 1
        need(ordinal <= od.MAX_SOURCE_ROWS and len(row) == len(od.HEADERS), "SOURCE_RECORD_BOUND_OR_WIDTH")
        for cell in row:
            od._cell(cell)
        original = dict(zip(od.HEADERS, row))
        values = {field: original[field] for field in od.PUBLIC_FIELDS}
        od._metadata(values)
        identity = values["Qualification Number"]
        need(identity not in qualification_ids, "DUPLICATE_QUALIFICATION_ID")
        qualification_ids.add(identity)
        all_statuses[values["Qualification Status"]] += 1
        if not selected_topics(values["Qualification Title"]):
            continue
        topic_statuses[values["Qualification Status"]] += 1
        if values["Qualification Status"] != STATUS:
            continue
        if ordinal in excluded:
            omitted += 1
            continue
        need(len(rows) < 2000, "SELECTED_ROW_BOUND")
        rows.append(decorate({"source_record_ordinal": ordinal, "source_line_start": start,
                              "source_line_end": reader.line_num, "values": values}))
    need(ordinal == SOURCE_RECORDS, "COMPLETE_SOURCE_RECORD_COUNT")
    need(dict(all_statuses) == previous["source_status_counts"], "COMPLETE_SOURCE_STATUS_COUNTS")
    projection = make_projection(rows, topic_statuses, omitted, previous)
    validate_projection(projection)
    return projection


def validate_projection(projection):
    previous = prior_projection()
    excluded = {row["source_record_ordinal"] for row in previous["records"]}
    records = projection["records"]
    need(type(records) is list and 0 < len(records) <= 2000, "PUBLIC_RECORD_BOUND")
    need(len(encoded(projection)) <= 2 * 1024 * 1024, "PUBLIC_BYTE_BOUND")
    ids, ordinals = set(), set()
    last_ordinal = 0
    for record in records:
        ordinal = record["source_record_ordinal"]
        need(type(ordinal) is int and last_ordinal < ordinal <= SOURCE_RECORDS, "SOURCE_ORDER_OR_ORDINAL")
        last_ordinal = ordinal
        need(ordinal not in excluded and ordinal not in ordinals, "PREVIOUS_OR_DUPLICATE_ORDINAL")
        ordinals.add(ordinal)
        start, end = record["source_line_start"], record["source_line_end"]
        need(type(start) is int and type(end) is int and ordinal + 1 <= start <= end, "PHYSICAL_SOURCE_LINES")
        values = record["values"]
        need(set(values) == set(od.PUBLIC_FIELDS), "EXACT_PUBLIC_FIELDS")
        od._metadata(values)
        need(values["Qualification Number"] not in ids, "PUBLIC_QUALIFICATION_ID_UNIQUE")
        ids.add(values["Qualification Number"])
        need(values["Qualification Status"] == STATUS and selected_topics(values["Qualification Title"]), "MEANING_STATUS_BOUNDARY")
        original = {key: record[key] for key in ("source_record_ordinal", "source_line_start", "source_line_end", "values")}
        need(record == decorate(original), "FULL_LITERAL_OR_PRECHECK_DRIFT")
    topic_statuses = Counter(projection["summary"]["all_source_topic_status_counts"])
    expected = make_projection(records, topic_statuses, projection["summary"]["already_projected_occurrences_omitted"], previous)
    need(projection == expected, "PUBLIC_STRUCTURE_OR_COUNT_DRIFT")
    need(topic_statuses[STATUS] == len(records) + projection["summary"]["already_projected_occurrences_omitted"], "SELECTED_STATUS_COVERAGE")


def manifest(projection_blob):
    projection = ka.parse_json_bytes(projection_blob)
    return {
        "version": 1,
        "scope": "PINNED_PUBLIC_OCCUPATIONAL_SOURCE_EXTRACTION_NOT_RESEARCH_ADMISSION",
        "original_capture": {"file": CAPTURE, "sha256": CAPTURE_SHA256},
        "original_source": {"url": od.SOURCE_URL, "sha256": SOURCE_SHA256, "bytes": SOURCE_BYTES,
                            "records": SOURCE_RECORDS, "capture_date_utc": "2026-11-11",
                            "http_date": "2026-11-11T15:26:50Z", "http_last_modified": "2026-11-11T02:16:08Z"},
        "licence": {"name": "Open Government Licence v3.0, except where otherwise stated",
                    "url": od.LICENCE_URL, "notice_url": od.NOTICE_URL,
                    "attribution": od.ATTRIBUTION, "third_party_exceptions_preserved": True},
        "projection": {"file": "qualifications.json", "sha256": sha(projection_blob), "bytes": len(projection_blob),
                       "records": len(projection["records"]), "summary": projection["summary"]},
        "extractor": {"file": "extract.py", "sha256": sha(Path(__file__).read_bytes())},
        "dependencies": [{"file": path, "sha256": sha((ROOT / path).read_bytes())}
                         for path in ("tools/keyword-system/keyword_audit.py", "tools/keyword-system/ofqual_discovery.py")],
        "private_source_path_published": False,
        "controls": CONTROLS,
    }


def verify(source=None):
    blob = read_bound(HERE / "qualifications.json", 2 * 1024 * 1024)
    projection = ka.parse_json_bytes(blob)
    validate_projection(projection)
    capture_blob = read_bound(HERE / "capture.json", 128 * 1024)
    capture = ka.parse_json_bytes(capture_blob)
    need(capture == manifest(blob), "CAPTURE_OR_DEPENDENCY_PIN_DRIFT")
    if source is not None:
        need(encoded(extract(source)) == blob, "FRESH_COMPLETE_RAW_REPROJECTION_EQUALITY")
    return {"passed": True, "scope": "SOURCE_EXTRACTION_ONLY_NOT_ADMISSION",
            "private_raw_hash_and_exact_reprojection_verified": source is not None,
            "source_occurrences": len(projection["records"]),
            "precheck_candidate_titles": projection["summary"]["precheck_candidate_distinct_normalized_titles"],
            "precheck_held_occurrences": projection["summary"]["length_or_word_count_held_occurrences"],
            "reviewed_for_admission": 0, "master_rows_added": 0, "deployment_authorized": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, metavar="PRIVATE_PATH")
    parser.add_argument("--write-new", action="store_true", help="Exclusively create the two new public JSON files.")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        if args.write_new:
            need(args.source is not None, "PRIVATE_SOURCE_REQUIRED")
            need(not (HERE / "qualifications.json").exists() and not (HERE / "capture.json").exists(), "REFUSE_EXISTING_OUTPUT")
            blob = encoded(extract(args.source))
            capture_blob = encoded(manifest(blob))
            for name, content in (("qualifications.json", blob), ("capture.json", capture_blob)):
                with (HERE / name).open("xb") as stream:
                    stream.write(content)
            result = verify(args.source)
        else:
            result = verify(args.source)
        result["measured_elapsed_seconds"] = round(time.perf_counter() - started, 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        # Fixed type/code only: never serialize source records or private paths.
        print(json.dumps({"passed": False, "error_type": type(error).__name__,
                          "scope": "SOURCE_EXTRACTION_VERIFICATION_FAILED", "deployment_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
