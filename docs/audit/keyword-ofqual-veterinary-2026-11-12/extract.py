"""Bounded veterinary-title source extraction; no admission or network client.

Public-only verification checks structure and local provenance pins. Supply the
original private CSV for a fresh complete hash and deterministic reprojection.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
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
import keyword_text_compatibility as tc
import ofqual_discovery as od

SOURCE_SHA256 = "ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5"
SOURCE_BYTES = 23984795
SOURCE_RECORDS = 53175
CAPTURE = "docs/audit/keyword-ofqual-discovery-2026-11-11/capture.json"
CAPTURE_SHA256 = "40563540ed29d76e03e2bea8be1a46aca960d888c138fcc2f9ac2f54dec2e9f7"
PREVIOUS = (
    ("docs/audit/keyword-ofqual-discovery-2026-11-11/qualifications.json",
     "2869cab8a06a76fa113ef430b28d09c53a324b72555cd0b3b36d3bdf82de4ccc", 338),
    ("docs/audit/keyword-ofqual-occupational-2026-11-12/qualifications.json",
     "8cdd1a1e0475857b1fc7473734756da9bb20b2229890c61d639ee41ed6dac91c", 524),
)
TOPIC_PATTERN = r"\bveterinary\b"
TOPIC = re.compile(TOPIC_PATTERN, re.IGNORECASE)
STATUS = "Available to learners"
TOPIC_STATUS_COUNTS = dict(zip(od.STATUSES, (51, 8, 35, 0)))
SELECTED_ORDINALS = (
    10746, 10764, 39023, 39024, 39089, 39117, 39123, 44484, 44489,
    44490, 44492, 44498, 44499, 44502, 44503, 44504, 44505, 44506,
    44507, 44508, 44509, 44510, 44691, 45219, 45220, 45221, 45228,
    45323, 48069, 48080, 48081, 48086, 48087, 48092, 48093, 48094,
    48095, 48098, 48113, 48120, 49191, 49199, 49206, 49213, 49214,
    49215, 49216, 49217, 49218, 51813, 53002,
)
MAX_PUBLIC_BYTES = 256 * 1024
DEPENDENCIES = (
    "tools/keyword-system/keyword_audit.py",
    "tools/keyword-system/ofqual_discovery.py",
    "tools/keyword-system/keyword_text_compatibility.py",
)
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
    "volume": None, "cpc": None, "competition": None,
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


def prior_projections():
    capture = read_bound(ROOT / CAPTURE, 128 * 1024)
    need(sha(capture) == CAPTURE_SHA256, "ORIGINAL_CAPTURE_PIN")
    previous, excluded = [], set()
    for name, digest, count in PREVIOUS:
        content = read_bound(ROOT / name, 1024 * 1024)
        need(sha(content) == digest, "PREVIOUS_PROJECTION_PIN")
        value = ka.parse_json_bytes(content)
        need(len(value["records"]) == count and value["source_sha256"] == SOURCE_SHA256,
             "PREVIOUS_SOURCE_OR_COUNT")
        ordinals = [row["source_record_ordinal"] for row in value["records"]]
        need(len(set(ordinals)) == count, "PREVIOUS_ORDINAL_UNIQUENESS")
        excluded.update(ordinals)
        previous.append((value, {"file": name, "sha256": digest,
                                 "excluded_source_record_ordinals": ordinals}))
    return previous, excluded


def decorate(record):
    title = record["values"]["Qualification Title"]
    reasons = []
    if len(title) > 80:
        reasons.append("OVER_80_CHARACTERS_COMPLETE_TITLE_HELD")
    if len(title.split()) > 10:
        reasons.append("OVER_10_WHITESPACE_WORDS_COMPLETE_TITLE_HELD")
    return {
        **record,
        "normalized_title": ka.normalize(title),
        "topic_matches": ["veterinary"],
        "characters": len(title),
        "whitespace_words": len(title.split()),
        "local_length_word_precheck_pass": not reasons,
        "local_precheck_holds": reasons,
        "text_compatibility": tc.profile_text(title)["original"],
        "semantic_review": "PENDING",
        "proposed_matching_limit": "COMPLETE_ORIGINAL_LITERAL_ONLY_FOR_LATER_EXACT_REVIEW",
        "campaign_page_and_protected_scope": "PENDING_NOT_SELECTED",
    }


def summary(records):
    groups = {}
    for row in records:
        groups.setdefault(row["normalized_title"], []).append(row["source_record_ordinal"])
    candidates = [row for row in records if row["local_length_word_precheck_pass"]]
    clear = [row for row in records if row["text_compatibility"]["classification"] ==
             "NO_KNOWN_INCOMPATIBILITY_DETECTED"]
    return {
        "all_source_topic_occurrences": 94,
        "all_source_topic_status_counts": TOPIC_STATUS_COUNTS,
        "outside_selected_source_status_occurrences": 43,
        "prior_projection_ordinal_overlap_count": 0,
        "already_projected_occurrences_omitted": 0,
        "retained_source_occurrences": len(records),
        "retained_distinct_normalized_titles": len(groups),
        "precheck_candidate_occurrences": len(candidates),
        "precheck_candidate_distinct_normalized_titles": len({r["normalized_title"] for r in candidates}),
        "length_or_word_count_held_occurrences": len(records) - len(candidates),
        "over_80_characters_occurrences": sum(r["characters"] > 80 for r in records),
        "over_10_whitespace_words_occurrences": sum(r["whitespace_words"] > 10 for r in records),
        "text_compatibility_classification_occurrences": dict(sorted(Counter(
            r["text_compatibility"]["classification"] for r in records).items())),
        "text_compatibility_reason_occurrences_overlap": dict(sorted(Counter(
            reason for r in records for reason in r["text_compatibility"]["reason_codes"]).items())),
        "no_known_incompatibility_distinct_normalized_titles": len({r["normalized_title"] for r in clear}),
        "duplicate_normalized_groups": [{"normalized_title": key, "source_record_ordinals": values}
                                         for key, values in groups.items() if len(values) > 1],
        "distinctness_limit": "Normalized-title grouping only; route, provider-prefix, alias, concept and Google matching equivalence remain unreviewed.",
        "current_library_novel_candidate_count": None,
        "admissible_candidate_count": None,
    }


def make_projection(records, previous):
    original = previous[0][0]
    return {
        "version": 1,
        "scope": "OFFICIAL_VETERINARY_TITLES_SOURCE_EXTRACTION_UNREVIEWED_NOT_ADMISSION",
        "extraction_date_dubai": "2026-11-12",
        "original_capture_date_utc": "2026-11-11",
        "source_url": od.SOURCE_URL,
        "source_type_compatibility": "official_reference",
        "source_sha256": SOURCE_SHA256, "source_bytes": SOURCE_BYTES,
        "source_record_count": SOURCE_RECORDS,
        "source_encoding": "UTF-8 with BOM",
        "source_headers": list(od.HEADERS),
        "header_source_line_start": 1,
        "header_source_line_end": original["header_source_line_end"],
        "source_status_counts": original["source_status_counts"],
        "previous_projections": [pin for _, pin in previous],
        "selection": {
            "meaning_boundary": "Complete officially published veterinary qualification titles with the literal veterinary word and source-published Available to learners status.",
            "topic_patterns": {"veterinary": TOPIC_PATTERN},
            "topic_matching": "CASE_INSENSITIVE_LITERAL_WORD_BOUNDARY",
            "published_status": STATUS,
            "all_matching_selected_status_rows_retained_without_quota_truncation": True,
            "historical_and_other_status_rows_counted_but_not_selected": True,
            "prior_projection_ordinals_excluded_and_zero_overlap_required": True,
            "selected_source_ordinal_pin_is_observed_capture_identity_not_quota": True,
            "local_screen": {"maximum_characters": 80, "maximum_whitespace_words": 10,
                             "held_full_titles_retained": True, "rewriting_or_shortening": False,
                             "platform_acceptance_claimed": False},
            "normalization": "Existing keyword_audit.normalize unchanged; NFKC, one matching-wrapper removal, casefold and whitespace collapse.",
            "research_pool_or_target_change": False,
        },
        "public_fields": list(od.PUBLIC_FIELDS),
        "records": records,
        "summary": summary(records),
        "controls": CONTROLS,
    }


def extract(source):
    previous, excluded = prior_projections()
    raw = read_bound(source, SOURCE_BYTES)
    need(len(raw) == SOURCE_BYTES and sha(raw) == SOURCE_SHA256, "EXACT_RAW_CAPTURE_PIN")
    need(raw.startswith(b"\xef\xbb\xbf"), "SOURCE_BOM")
    decoded = raw.decode("utf-8-sig", errors="strict")
    od._csv_quoting(decoded)
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    need(next(reader, None) == list(od.HEADERS), "EXACT_SOURCE_HEADERS")
    need(reader.line_num == previous[0][0]["header_source_line_end"], "HEADER_LINES")
    rows, qualification_ids = [], set()
    all_statuses, topic_statuses = Counter(), Counter()
    ordinal = 0
    overlap = 0
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
        need(values["Qualification Number"] not in qualification_ids, "DUPLICATE_QUALIFICATION_ID")
        qualification_ids.add(values["Qualification Number"])
        all_statuses[values["Qualification Status"]] += 1
        if not TOPIC.search(values["Qualification Title"]):
            continue
        topic_statuses[values["Qualification Status"]] += 1
        overlap += ordinal in excluded
        if values["Qualification Status"] == STATUS:
            need(len(rows) < 2000, "SELECTED_ROW_BOUND_NO_TRUNCATION")
            rows.append(decorate({"source_record_ordinal": ordinal, "source_line_start": start,
                                  "source_line_end": reader.line_num, "values": values}))
    need(ordinal == SOURCE_RECORDS, "COMPLETE_SOURCE_RECORD_COUNT")
    need(dict(all_statuses) == previous[0][0]["source_status_counts"], "COMPLETE_SOURCE_STATUS_COUNTS")
    need({status: topic_statuses[status] for status in od.STATUSES} == TOPIC_STATUS_COUNTS,
         "COMPLETE_TOPIC_STATUS_COUNTS")
    need(overlap == 0, "PRIOR_TOPIC_ORDINAL_OVERLAP")
    projection = make_projection(rows, previous)
    validate_projection(projection)
    return projection


def validate_projection(projection):
    previous, excluded = prior_projections()
    need(type(projection) is dict and type(projection.get("records")) is list, "PUBLIC_STRUCTURE")
    records = projection["records"]
    need(0 < len(records) <= 2000 and len(encoded(projection)) <= MAX_PUBLIC_BYTES, "PUBLIC_BOUND")
    need([r["source_record_ordinal"] for r in records] == list(SELECTED_ORDINALS), "EXACT_SELECTED_SOURCE_ORDINALS")
    ids = set()
    for record in records:
        ordinal = record["source_record_ordinal"]
        need(type(ordinal) is int and ordinal not in excluded, "PREVIOUS_OR_INVALID_ORDINAL")
        start, end = record["source_line_start"], record["source_line_end"]
        need(type(start) is int and type(end) is int and ordinal + 1 <= start <= end, "PHYSICAL_SOURCE_LINES")
        values = record["values"]
        need(type(values) is dict and set(values) == set(od.PUBLIC_FIELDS), "EXACT_PUBLIC_FIELDS")
        od._metadata(values)
        need(values["Qualification Number"] not in ids, "PUBLIC_QUALIFICATION_ID_UNIQUE")
        ids.add(values["Qualification Number"])
        need(values["Qualification Status"] == STATUS and TOPIC.search(values["Qualification Title"]),
             "MEANING_STATUS_BOUNDARY")
        original = {key: record[key] for key in ("source_record_ordinal", "source_line_start", "source_line_end", "values")}
        need(od._exact(record, decorate(original)), "FULL_LITERAL_OR_PRECHECK_DRIFT")
    need(od._exact(projection, make_projection(records, previous)), "PUBLIC_STRUCTURE_OR_COUNT_DRIFT")


def manifest(projection_blob):
    projection = ka.parse_json_bytes(projection_blob)
    return {
        "version": 1,
        "scope": "PINNED_PUBLIC_VETERINARY_SOURCE_EXTRACTION_NOT_RESEARCH_ADMISSION",
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
        "dependencies": [{"file": path, "sha256": sha((ROOT / path).read_bytes())} for path in DEPENDENCIES],
        "private_source_path_published": False,
        "controls": CONTROLS,
    }


def verify(source=None):
    blob = read_bound(HERE / "qualifications.json", MAX_PUBLIC_BYTES)
    projection = ka.parse_json_bytes(blob)
    validate_projection(projection)
    capture = ka.parse_json_bytes(read_bound(HERE / "capture.json", 128 * 1024))
    need(od._exact(capture, manifest(blob)), "CAPTURE_OR_DEPENDENCY_PIN_DRIFT")
    if source is not None:
        need(encoded(extract(source)) == blob, "FRESH_COMPLETE_RAW_REPROJECTION_EQUALITY")
    return {"passed": True, "scope": "SOURCE_EXTRACTION_ONLY_NOT_ADMISSION",
            "private_raw_hash_and_exact_reprojection_verified": source is not None,
            "source_occurrences": len(projection["records"]),
            "precheck_candidate_titles": projection["summary"]["precheck_candidate_distinct_normalized_titles"],
            "text_compatibility_clear_titles": projection["summary"]["no_known_incompatibility_distinct_normalized_titles"],
            "reviewed_for_admission": 0, "master_rows_added": 0, "deployment_authorized": False}


def self_check():
    original = ka.parse_json_bytes(read_bound(HERE / "qualifications.json", MAX_PUBLIC_BYTES))
    validate_projection(original)
    mutations = (
        ("ALTER_TITLE_WITHOUT_REDECORATION", lambda p: p["records"][0]["values"].__setitem__("Qualification Title", "Altered Veterinary Diploma")),
        ("PRIOR_SOURCE_ORDINAL", lambda p: p["records"][0].__setitem__("source_record_ordinal", 49184)),
        ("WRONG_PUBLISHED_STATUS", lambda p: p["records"][0]["values"].__setitem__("Qualification Status", "No longer awarded")),
        ("DROPPED_COMPLETE_OCCURRENCE", lambda p: p["records"].pop()),
        ("PRODUCTION_AUTHORITY_FLIP", lambda p: p["controls"].__setitem__("deployment_authorized", True)),
        ("BOOLEAN_REPLACED_WITH_NUMBER", lambda p: p["controls"].__setitem__("deployment_authorized", 0)),
        ("STATUS_COUNT_DRIFT", lambda p: p["summary"]["all_source_topic_status_counts"].__setitem__(STATUS, 50)),
        ("SYMBOL_HOLD_REMOVED", lambda p: p["records"][23]["text_compatibility"].__setitem__("classification", "NO_KNOWN_INCOMPATIBILITY_DETECTED")),
        ("UNKNOWN_PUBLIC_FIELD", lambda p: p["records"][0]["values"].__setitem__("Invented Field", "not source metadata")),
        ("REVERSED_SOURCE_ORDER", lambda p: p["records"].reverse()),
        ("NORMALIZED_TITLE_DRIFT", lambda p: p["records"][0].__setitem__("normalized_title", "invented veterinary title")),
        ("TOPIC_BOUNDARY_DRIFT", lambda p: p["selection"].__setitem__("topic_patterns", {"veterinary": "animal"})),
    )
    rejected = []
    for name, mutate in mutations:
        value = copy.deepcopy(original)
        mutate(value)
        try:
            validate_projection(value)
        except (ValueError, KeyError, TypeError):
            rejected.append(name)
        else:
            raise ValueError("TAMPER_NOT_REJECTED")
    return {"passed": True, "tamper_mutations_rejected": len(rejected), "checks": rejected,
            "scope": "IN_MEMORY_SOURCE_STRUCTURE_DIAGNOSTIC_NOT_ADMISSION"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, metavar="PRIVATE_PATH")
    parser.add_argument("--write-new", action="store_true", help="Exclusively create the two new public JSON files.")
    parser.add_argument("--self-check", action="store_true", help="Reject twelve in-memory public-structure mutations.")
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        if args.write_new:
            need(args.source is not None and not args.self_check, "PRIVATE_SOURCE_REQUIRED_OR_MODE_CONFLICT")
            need(not (HERE / "qualifications.json").exists() and not (HERE / "capture.json").exists(), "REFUSE_EXISTING_OUTPUT")
            blob = encoded(extract(args.source))
            for name, content in (("qualifications.json", blob), ("capture.json", encoded(manifest(blob)))):
                with (HERE / name).open("xb") as stream:
                    stream.write(content)
        result = verify(args.source)
        if args.self_check:
            result["tamper_diagnostic"] = self_check()
        result["measured_elapsed_seconds"] = round(time.perf_counter() - started, 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__,
                          "scope": "SOURCE_EXTRACTION_VERIFICATION_FAILED", "deployment_authorized": False}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
