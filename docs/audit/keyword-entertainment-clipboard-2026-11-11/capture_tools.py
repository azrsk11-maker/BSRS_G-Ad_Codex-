"""Bounded, read-only clipboard evidence checks; no platform or admission writer."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import unicodedata

RAW_SHA256 = "3c2c8b015097200e3648f2f9d04c467ec6d447d4ea187d5cabd4be030bedb3ac"
CANONICAL_SHA256 = "ceb01d1cc6c052279eabce3cdb8d3fa36122c2e7827d53939b8f2a40357d3244"
RAW_BYTES = 13639
ROW_COUNT = 518
MAX_BYTES = 512 * 1024


def need(condition, code):
    if not condition:
        raise ValueError(code)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse_json(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, "JSON_BOUNDS")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)


def canonical(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode("utf-8")


def parse_source(raw):
    need(type(raw) is bytes and len(raw) == RAW_BYTES, "RAW_BYTE_COUNT")
    need(hashlib.sha256(raw).hexdigest() == RAW_SHA256, "RAW_HASH_CHANGED")
    rows = raw.decode("utf-8").splitlines()
    need(len(rows) == ROW_COUNT and len(set(rows)) == ROW_COUNT, "RAW_ROW_COUNT_OR_DUPLICATE")
    need(all(row and row == row.strip() and len(row) <= 256 for row in rows), "RAW_LITERAL_INVALID")
    normal = ("\n".join(rows) + "\n").encode("utf-8")
    need(hashlib.sha256(normal).hexdigest() == CANONICAL_SHA256, "CANONICAL_HASH_CHANGED")
    return [{"ordinal": ordinal, "keyword": text} for ordinal, text in enumerate(rows, 1)]


def normalize(text):
    value = unicodedata.normalize("NFKC", text).strip()
    if len(value) >= 2 and (value[0], value[-1]) in {("[", "]"), ('"', '"')}:
        value = value[1:-1].strip()
    return " ".join(value.casefold().split())


def lexical(rows, proposal_ids):
    bags, closed, normalized = defaultdict(list), defaultdict(list), defaultdict(list)
    for row in rows:
        text, ordinal = normalize(row["keyword"]), row["ordinal"]
        normalized[text].append(ordinal)
        bags[tuple(sorted(re.findall(r"\w+", text, flags=re.UNICODE)))].append(ordinal)
        closed[re.sub(r"[\W_]", "", text, flags=re.UNICODE)].append(ordinal)
    groups = [members for members in bags.values() if len(members) > 1]
    aliases = [members for members in closed.values() if len(members) > 1]
    bag_ids = {ordinal for members in groups for ordinal in members}
    return {
        "scope": "WITHIN_SOURCE_DIAGNOSTIC_NOT_GOOGLE_EQUIVALENCE",
        "normalization": "NFKC, one matching wrapper, casefold, whitespace collapse; token bags use Unicode word tokens",
        "normalized_identity_count": len(normalized),
        "normalized_duplicate_groups": [members for members in normalized.values() if len(members) > 1],
        "equal_token_bag_groups": [{"group": index, "ordinals": members, "status": "UNRESOLVED_DISTINCT_CONCEPT_AND_GOOGLE_EQUIVALENCE"} for index, members in enumerate(groups, 1)],
        "equal_token_bag_occurrences": sum(map(len, groups)),
        "semantic_proposal_occurrences_in_equal_token_bag_groups": len(set(proposal_ids) & bag_ids),
        "closed_string_alias_groups": [{"group": index, "ordinals": members, "status": "UNRESOLVED_SPACING_OR_ALIAS"} for index, members in enumerate(aliases, 1)],
        "closed_string_alias_occurrences": sum(map(len, aliases)),
        "maximum_original_characters": max(len(row["keyword"]) for row in rows),
        "maximum_whitespace_words": max(len(row["keyword"].split()) for row in rows),
        "platform_compatibility_verified": False,
        "full_current_membership_verified": False,
    }


def validate_bundle(blobs, pins, source_raw=None):
    need(set(blobs) == set(pins), "PINNED_FILE_SET_CHANGED")
    for name, raw in blobs.items():
        need(type(raw) is bytes and len(raw) <= MAX_BYTES, "ARTIFACT_BOUNDS")
        need(hashlib.sha256(raw).hexdigest() == pins[name], "PIN_CHANGED")
    projection, capture, review, saved_lexical = (parse_json(blobs[name]) for name in ("keywords.json", "capture.json", "review.json", "lexical.json"))
    rows = projection["records"]
    need(len(rows) == ROW_COUNT, "PROJECTION_ROW_COUNT")
    need([row["ordinal"] for row in rows] == list(range(1, ROW_COUNT + 1)), "ORDINALS_CHANGED")
    need(all(set(row) == {"ordinal", "keyword"} and type(row["ordinal"]) is int and type(row["keyword"]) is str and row["keyword"] for row in rows), "PROJECTION_SCHEMA")
    need(len({row["keyword"] for row in rows}) == ROW_COUNT, "DUPLICATE_LITERAL")
    normal = ("\n".join(row["keyword"] for row in rows) + "\n").encode("utf-8")
    need(hashlib.sha256(normal).hexdigest() == CANONICAL_SHA256, "PROJECTED_LITERALS_CHANGED")
    need(projection["source_raw_sha256"] == capture["source_raw_sha256"] == RAW_SHA256, "RAW_PIN_CHANGED")
    need(capture["source_raw_bytes"] == RAW_BYTES and capture["account_id"] == "573-038-4686", "SOURCE_IDENTITY_CHANGED")
    need(capture["metrics_status"] == "NOT_CAPTURED_UNKNOWN" and capture["is_csv_export"] is False and capture["observed_served_queries"] is False, "SOURCE_KIND_OR_METRICS_CHANGED")
    need(capture["master_contribution"] == capture["approved_contribution"] == capture["deployed_contribution"] == 0, "CAPTURE_AUTHORITY_CHANGED")
    assessed = review["assessments"]
    need([row["ordinal"] for row in assessed] == list(range(1, ROW_COUNT + 1)), "REVIEW_COVERAGE_CHANGED")
    need(all(set(row) == {"ordinal", "disposition", "reason_code"} and type(row["ordinal"]) is int for row in assessed), "REVIEW_DUPLICATES_SOURCE_METADATA")
    need(all(row["disposition"] in {"PROPOSE_EXACT", "HOLD"} and row["reason_code"] in review["reason_definitions"] for row in assessed), "REVIEW_DISPOSITION_CHANGED")
    counts = Counter(row["disposition"] for row in assessed)
    need(counts["PROPOSE_EXACT"] == review["proposed_exact"] == 318 and counts["HOLD"] == review["held"] == 200, "REVIEW_COUNTS_CHANGED")
    need(review["unassessed"] == review["master_contribution"] == review["approved_contribution"] == review["deployed_contribution"] == 0, "REVIEW_AUTHORITY_CHANGED")
    proposal_ids = [row["ordinal"] for row in assessed if row["disposition"] == "PROPOSE_EXACT"]
    need(lexical(rows, proposal_ids) == saved_lexical, "LEXICAL_DIAGNOSTIC_CHANGED")
    if source_raw is not None:
        need(parse_source(source_raw) == rows, "RAW_PROJECTION_MISMATCH")
    return {"passed": True, "source_records": ROW_COUNT, "proposed_exact": 318, "held": 200, "unassessed": 0, "private_raw_equality_verified": source_raw is not None, "full_current_membership_verified": False, "master_contribution": 0, "deployment_authorized": False}
