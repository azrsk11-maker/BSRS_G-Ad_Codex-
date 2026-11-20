"""Recover a pinned historical draft into an unapproved research staging register.

Only three known CSV members are read. Nothing is extracted, executed, submitted,
or promoted into the reviewed masters. A source timestamp is not freshness proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import zipfile

from keyword_audit import ensure_output_is_not_input, normalize

SCHEMA = "bsre-historical-keyword-intake-v1"
ARCHIVE_SHA256 = "08a689590b812cd7eac46baf8a5e1fe23f2ced94168d8982012498e003c84794"
KEYWORDS = "black-swan-implementation/campaigns/keywords.csv"
METADATA = "black-swan-implementation/campaigns/keyword-metadata.csv"
DUPLICATE_COPY = "black-swan-implementation/full-scope/campaigns/keywords.csv"
MEMBERS = {
    KEYWORDS: {"sha256": "87eefba1d96fbdde0b7a83dee5d0bb36c4c3ad8516f5ca5ac37c7166a0e5646f", "bytes": 7863},
    METADATA: {"sha256": "80da168affeedbec3a81b6c035df605025b48b13f2ecb089f83e203727f1918e", "bytes": 24507},
    DUPLICATE_COPY: {"sha256": "87eefba1d96fbdde0b7a83dee5d0bb36c4c3ad8516f5ca5ac37c7166a0e5646f", "bytes": 7863},
}
KEYWORD_FIELDS = ["Campaign", "Campaign status", "Ad group", "Ad group status", "Keyword", "Criterion Type", "Status"]
METADATA_FIELDS = ["Campaign", "Ad group", "Keyword", "Match type", "Role", "Proposed final URL", "Readiness", "Reason", "Live-account evidence"]
NULL_FIELDS = ["language", "reviewer", "reviewed_on", "valid_until", "source_observed_on", "volume", "cpc",
               "primary_campaign_key", "ad_group_key", "landing_page_id", "approval_reference"]


def expected_source_envelope():
    return {"archive_basename": "black-swan-no-crm-implementation.zip", "archive_sha256": ARCHIVE_SHA256,
            "source_classification": "OWNER_SUPPLIED_HISTORICAL_DRAFT_NOT_CURRENT_ACCOUNT_EVIDENCE",
            "freshness_verified": False, "selected_members": [{"member": name, **pin} for name, pin in MEMBERS.items()],
            "duplicate_copy_byte_identical": True}


def parse_csv(raw, expected_fields):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != expected_fields or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("Unexpected or duplicate CSV columns")
    records, last_line = [], 1
    for ordinal, row in enumerate(reader, 1):
        if None in row or any(value is None for value in row.values()):
            raise ValueError("CSV row has a mismatched column count")
        records.append({"record_ordinal": ordinal, "start_line": last_line + 1, "end_line": reader.line_num, "fields": row})
        last_line = reader.line_num
    return records


def placement_key(fields, metadata=False):
    return (fields["Campaign"], fields["Ad group"], fields["Keyword"], fields["Match type" if metadata else "Criterion Type"])


def assemble(keyword_bytes, metadata_bytes, intake_date, source):
    """Pure transformation; production CLI supplies checksum-verified members."""
    date.fromisoformat(intake_date)
    keyword_rows = parse_csv(keyword_bytes, KEYWORD_FIELDS)
    metadata_rows = parse_csv(metadata_bytes, METADATA_FIELDS)
    metadata_index = {}
    for row in metadata_rows:
        key = placement_key(row["fields"], metadata=True)
        if key in metadata_index:
            raise ValueError("Duplicate metadata placement key")
        metadata_index[key] = row
    placements, groups, seen = [], {}, set()
    for row in keyword_rows:
        fields = row["fields"]
        key = placement_key(fields)
        if key in seen or key not in metadata_index:
            raise ValueError("Duplicate keyword placement or missing exact metadata join")
        seen.add(key)
        if any(fields[name] != "Paused" for name in ["Campaign status", "Ad group status", "Status"]):
            raise ValueError("Historical source status differs from the pinned paused-draft contract")
        if fields["Criterion Type"] not in {"Exact", "Phrase"} or not fields["Keyword"].strip():
            raise ValueError("Unexpected match type or blank historical phrase")
        metadata = metadata_index[key]
        if metadata["fields"]["Live-account evidence"] != "NOT VERIFIED":
            raise ValueError("Unexpected live-evidence claim; review source separately")
        placement_id = f"LEGACY-PLACEMENT-{row['record_ordinal']:04}"
        placements.append({"placement_id": placement_id,
                           "keyword_source_locator": {"member": KEYWORDS, **{k: row[k] for k in ["record_ordinal", "start_line", "end_line"]}},
                           "metadata_source_locator": {"member": METADATA, **{k: metadata[k] for k in ["record_ordinal", "start_line", "end_line"]}},
                           "original_keyword_fields": fields, "original_metadata_fields": metadata["fields"]})
        norm = normalize(fields["Keyword"])
        if norm not in groups:
            groups[norm] = {"candidate_id": f"LEGACY-POS-{len(groups) + 1:04}", "original_text": fields["Keyword"],
                            "original_text_variants": [], "normalized_text": norm, "placement_ids": [], "match_types_seen": [],
                            "source_id": "HISTORICAL-DRAFT-ZIP", "source_kind": "historical_draft_archive",
                            "review_state": "CANDIDATE", "approval_state": "PENDING", "mapping_status": "OWNER_REVIEW_REQUIRED",
                            **dict.fromkeys(NULL_FIELDS)}
        candidate = groups[norm]
        if fields["Keyword"] not in candidate["original_text_variants"]:
            candidate["original_text_variants"].append(fields["Keyword"])
        candidate["placement_ids"].append(placement_id)
        match_type = fields["Criterion Type"].upper()
        if match_type not in candidate["match_types_seen"]:
            candidate["match_types_seen"].append(match_type)
    if seen != set(metadata_index):
        raise ValueError("Unmatched metadata records must not be discarded")
    result = {"schema_version": SCHEMA, "intake_date": intake_date, "source": source,
              "scope": "UNAPPROVED_HISTORICAL_RESEARCH_INTAKE_NOT_LIVE_STATE",
              "new_360_mapping_assigned": False, "deployment_export_allowed": False,
              "counts": {"historical_placements": len(placements), "distinct_unreviewed_candidates": len(groups),
                         "reviewed_positive_rows": 0, "approved_rows": 0, "deployed_rows_from_this_intake": 0,
                         "reviewed_positive_target": 14000, "reviewed_positive_deficit": 14000,
                         "historical_match_types": dict(Counter(r["fields"]["Criterion Type"] for r in keyword_rows)),
                         "historical_campaign_names": dict(Counter(r["fields"]["Campaign"] for r in keyword_rows)),
                         "historical_ad_group_names": dict(Counter(r["fields"]["Ad group"] for r in keyword_rows))},
              "required_before_reviewed_promotion": ["Verify current service/entity relevance and source freshness",
                  "Review original language, spelling, meaning and protected intent",
                  "Resolve approved primary campaign/ad-group/page ownership under the new registry",
                  "Record independent reviewer, dated evidence and expiry; leave unmeasured volume/CPC null",
                  "Reconcile historical placements against current account without recreating or replaying imports"],
              "placements": placements, "candidates": list(groups.values())}
    validate_intake(result)
    return result


def validate_intake(document):
    if document.get("schema_version") != SCHEMA or document.get("scope") != "UNAPPROVED_HISTORICAL_RESEARCH_INTAKE_NOT_LIVE_STATE":
        raise ValueError("Unsupported historical staging contract")
    if document.get("new_360_mapping_assigned") is not False or document.get("deployment_export_allowed") is not False:
        raise ValueError("Staging cannot grant mapping or deployment authority")
    if document.get("source") != expected_source_envelope():
        raise ValueError("Pinned historical source envelope or unverified freshness state changed")
    placements = document["placements"]
    by_id = {row["placement_id"]: row for row in placements}
    if len(by_id) != len(placements):
        raise ValueError("Duplicate placement identity")
    metadata_ordinals, expected_groups = [], {}
    for ordinal, placement in enumerate(placements, 1):
        fields, metadata = placement["original_keyword_fields"], placement["original_metadata_fields"]
        if list(fields) != KEYWORD_FIELDS or list(metadata) != METADATA_FIELDS:
            raise ValueError("Original column structure changed")
        if placement["placement_id"] != f"LEGACY-PLACEMENT-{ordinal:04}" or placement_key(fields) != placement_key(metadata, True):
            raise ValueError("Original placement identity or exact metadata join changed")
        if any(fields[name] != "Paused" for name in ["Campaign status", "Ad group status", "Status"]) or metadata["Live-account evidence"] != "NOT VERIFIED":
            raise ValueError("Historical draft/evidence state changed")
        for locator_name, member in [("keyword_source_locator", KEYWORDS), ("metadata_source_locator", METADATA)]:
            locator = placement[locator_name]
            if locator["member"] != member or type(locator["record_ordinal"]) is not int or not 1 <= locator["record_ordinal"] <= len(placements) or type(locator["start_line"]) is not int or type(locator["end_line"]) is not int or not 2 <= locator["start_line"] <= locator["end_line"]:
                raise ValueError("Invalid source locator")
        if placement["keyword_source_locator"]["record_ordinal"] != ordinal:
            raise ValueError("Original keyword ordinal changed")
        metadata_ordinals.append(placement["metadata_source_locator"]["record_ordinal"])
        expected_groups.setdefault(normalize(fields["Keyword"]), []).append(placement["placement_id"])
    if set(metadata_ordinals) != set(range(1, len(placements) + 1)):
        raise ValueError("Metadata provenance rows were lost or reused")
    seen, normalized = [], set()
    expected_order = list(expected_groups)
    if len(document["candidates"]) != len(expected_order):
        raise ValueError("Candidate groups differ from original placement groups")
    for ordinal, candidate in enumerate(document["candidates"], 1):
        if candidate["candidate_id"] != f"LEGACY-POS-{ordinal:04}":
            raise ValueError("Candidate identities must preserve original first-occurrence order")
        if candidate.get("review_state") != "CANDIDATE" or candidate.get("approval_state") != "PENDING" or candidate.get("mapping_status") != "OWNER_REVIEW_REQUIRED":
            raise ValueError("Historical intake was silently promoted")
        if any(candidate.get(key) is not None for key in NULL_FIELDS):
            raise ValueError("Unverified research, metric or mapping value introduced")
        if candidate.get("source_id") != "HISTORICAL-DRAFT-ZIP" or candidate.get("source_kind") != "historical_draft_archive":
            raise ValueError("Candidate historical provenance class changed")
        norm = candidate["normalized_text"]
        if norm != expected_order[ordinal - 1] or candidate["placement_ids"] != expected_groups[norm]:
            raise ValueError("Original first-occurrence group or placement order changed")
        if normalize(candidate["original_text"]) != norm or norm in normalized:
            raise ValueError("Duplicate or inconsistent normalized candidate")
        normalized.add(norm)
        variants, matches = [], []
        for key in candidate["placement_ids"]:
            if key not in by_id:
                raise ValueError("Missing provenance placement")
            fields = by_id[key]["original_keyword_fields"]
            if normalize(fields["Keyword"]) != norm:
                raise ValueError("Candidate text differs from historical provenance")
            if fields["Keyword"] not in variants:
                variants.append(fields["Keyword"])
            if fields["Criterion Type"].upper() not in matches:
                matches.append(fields["Criterion Type"].upper())
            seen.append(key)
        if not variants or candidate["original_text"] != variants[0] or candidate["original_text_variants"] != variants or candidate["match_types_seen"] != matches:
            raise ValueError("Original text variants or match placements were lost")
    if Counter(seen) != Counter(by_id.keys()):
        raise ValueError("Every original placement must be retained exactly once")
    counts = document["counts"]
    expected = {"historical_placements": len(placements), "distinct_unreviewed_candidates": len(normalized),
                "reviewed_positive_rows": 0, "approved_rows": 0, "deployed_rows_from_this_intake": 0,
                "reviewed_positive_target": 14000, "reviewed_positive_deficit": 14000}
    if any(counts.get(key) != value for key, value in expected.items()):
        raise ValueError("Intake count or completion claim differs from evidence")
    for output_name, field in [("historical_match_types", "Criterion Type"), ("historical_campaign_names", "Campaign"), ("historical_ad_group_names", "Ad group")]:
        if counts.get(output_name) != dict(Counter(p["original_keyword_fields"][field] for p in placements)):
            raise ValueError("Historical dimension counts differ from source records")
    return {"status": "PASS_STAGING_ONLY", **expected, "deployment_export_allowed": False}


def read_pinned_archive(path):
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
        archive_hash = digest.hexdigest()
    if archive_hash != ARCHIVE_SHA256:
        raise ValueError("Archive checksum changed; do not ingest an unreviewed replacement")
    selected = {}
    with zipfile.ZipFile(path) as archive:
        counts = Counter(archive.namelist())
        for name, pin in MEMBERS.items():
            if counts[name] != 1:
                raise ValueError("Missing or duplicate selected archive member")
            info = archive.getinfo(name)
            if info.file_size != pin["bytes"]:
                raise ValueError("Member size differs from reviewed source")
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != pin["sha256"]:
                raise ValueError("Selected source checksum changed")
            selected[name] = raw
    if selected[KEYWORDS] != selected[DUPLICATE_COPY]:
        raise ValueError("Historical duplicate keyword files differ")
    provenance = expected_source_envelope()
    return selected[KEYWORDS], selected[METADATA], provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--intake-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    ensure_output_is_not_input(args.output, [args.archive, args.report])
    ensure_output_is_not_input(args.report, [args.archive, args.output])
    keyword_bytes, metadata_bytes, source = read_pinned_archive(args.archive)
    document = assemble(keyword_bytes, metadata_bytes, args.intake_date, source)
    if len(document["placements"]) != 82 or len(document["candidates"]) != 41:
        raise ValueError("Pinned historical count differs from reviewed 82 placements/41 phrases")
    report = validate_intake(document)
    encoded = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    report["intake_sha256"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    for path, data in [(args.output, encoded), (args.report, json.dumps(report, indent=2) + "\n")]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8", newline="\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
