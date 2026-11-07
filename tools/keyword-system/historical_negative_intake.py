"""Recover pinned historical negative proposals into unapproved staging only.

No network, live account access, current scope assignment or negative exporter.
Historical reasons/risk/scope are preserved claims, never current approvals.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import zipfile

from historical_intake import ARCHIVE_SHA256, parse_csv
from keyword_audit import ensure_output_is_not_input, iso_day, normalize

SCHEMA = "bsre-historical-negative-intake-v1"
PRIMARY = "black-swan-implementation/campaigns/negative-keywords-candidates.csv"
DUPLICATE_COPY = "black-swan-implementation/full-scope/campaigns/negative-keywords.csv"
MEMBER_SHA256 = "3a388e1b46a5e083d07b9f97624618bd889ea2f71753deb21d3866f7f64e3257"
MEMBER_BYTES = 5532
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
FIELDS = ["Campaign", "Ad group", "Keyword", "Criterion Type", "Scope", "Risk", "Decision", "Reason"]
RECORDS_SHA256 = "668308b7f8a0151d5f3e129f2b334e5adb4e029dbb18528cbe38c005047c64e0"
UNKNOWN_FIELDS = ["language", "reviewer", "reviewed_on", "valid_until", "source_observed_on", "volume", "cpc",
                  "current_scope_type", "current_scope_target", "current_eligible_campaigns", "current_ineligible_campaigns",
                  "current_service_applicability", "current_risk_level", "current_protected_query_conflicts",
                  "current_deployment_status", "approval_reference", "approval_reviewer", "approved_on"]


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


def expected_source_envelope():
    return {"archive_basename": "black-swan-no-crm-implementation.zip", "archive_sha256": ARCHIVE_SHA256,
            "source_classification": "OWNER_SUPPLIED_HISTORICAL_DRAFT_NOT_CURRENT_ACCOUNT_EVIDENCE",
            "freshness_verified": False,
            "selected_members": [{"member": name, "sha256": MEMBER_SHA256, "bytes": MEMBER_BYTES}
                                 for name in [PRIMARY, DUPLICATE_COPY]],
            "duplicate_copy_byte_identical": True, "canonical_original_records_sha256": RECORDS_SHA256}


def read_pinned_archive(path):
    # One bounded snapshot binds archive validation and member parsing to the same bytes.
    with path.open("rb") as handle:
        raw_archive = handle.read(MAX_ARCHIVE_BYTES + 1)
    if len(raw_archive) > MAX_ARCHIVE_BYTES or hashlib.sha256(raw_archive).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Archive size/checksum changed; do not ingest an unreviewed replacement")
    selected = {}
    with zipfile.ZipFile(io.BytesIO(raw_archive)) as archive:
        names = Counter(archive.namelist())
        for name in [PRIMARY, DUPLICATE_COPY]:
            if names[name] != 1:
                raise ValueError("Missing or duplicate selected negative member")
            info = archive.getinfo(name)
            if info.file_size != MEMBER_BYTES:
                raise ValueError("Selected negative member size changed")
            raw = archive.read(name)
            if hashlib.sha256(raw).hexdigest() != MEMBER_SHA256:
                raise ValueError("Selected negative member checksum changed")
            selected[name] = raw
    if selected[PRIMARY] != selected[DUPLICATE_COPY]:
        raise ValueError("Historical negative copies differ")
    return selected[PRIMARY]


def verify_records(records):
    # Bind every original field, record order and multiline locator independently
    # of the candidate aggregation. Self-consistent edits cannot rewrite history.
    if canonical_hash(records) != RECORDS_SHA256 or len(records) != 27:
        raise ValueError("Original negative records, order or locators differ from pinned evidence")


def build_document(records, intake_date):
    iso_day(intake_date)
    verify_records(records)
    placements, groups = [], {}
    for row in records:
        fields = row["fields"]
        placement_id = f"LEGACY-NEG-PLACEMENT-{row['record_ordinal']:04}"
        placements.append({"placement_id": placement_id,
                           "source_locator": {"member": PRIMARY, **{k: row[k] for k in ["record_ordinal", "start_line", "end_line"]}},
                           "original_negative_fields": fields})
        norm = normalize(fields["Keyword"])
        if norm not in groups:
            groups[norm] = {"candidate_id": f"LEGACY-NEG-{len(groups) + 1:04}", "original_text": fields["Keyword"],
                            "original_text_variants": [], "normalized_text": norm, "placement_ids": [],
                            "historical_match_types_seen": [], "historical_risk_claims_seen": [],
                            "source_id": "HISTORICAL-DRAFT-ZIP", "source_kind": "historical_draft_archive",
                            "review_state": "CANDIDATE", "approval_state": "PENDING",
                            "mapping_status": "CURRENT_SCOPE_UNKNOWN_OWNER_REVIEW_REQUIRED",
                            "protected_intent_test_status": "NOT_PERFORMED", "deployed_resource_ids_from_this_intake": [],
                            **dict.fromkeys(UNKNOWN_FIELDS)}
        candidate = groups[norm]
        candidate["placement_ids"].append(placement_id)
        for key, value in [("original_text_variants", fields["Keyword"]),
                           ("historical_match_types_seen", fields["Criterion Type"]),
                           ("historical_risk_claims_seen", fields["Risk"])]:
            if value not in candidate[key]:
                candidate[key].append(value)
    if len(groups) != 9:
        raise ValueError("Historical distinct negative candidate count differs from pinned evidence")
    return {"schema_version": SCHEMA, "intake_date": intake_date, "source": expected_source_envelope(),
            "scope": "UNAPPROVED_HISTORICAL_NEGATIVE_INTAKE_NOT_LIVE_STATE",
            "current_scope_assigned": False, "deployment_export_allowed": False, "production_writes_available": False,
            "counts": {"historical_placements": len(placements), "distinct_unreviewed_candidates": len(groups),
                       "reviewed_negative_rows": 0, "approved_exclusion_rows": 0, "deployed_rows_from_this_intake": 0,
                       "reviewed_negative_target": 14000, "reviewed_negative_deficit": 14000,
                       "historical_match_types": dict(Counter(row["fields"]["Criterion Type"] for row in records)),
                       "historical_campaign_names": dict(Counter(row["fields"]["Campaign"] for row in records))},
            "required_before_reviewed_promotion": [
                "Verify actual search terms, current business relevance and dated source evidence; historical LOW risk is not a current risk review",
                "Individually review every candidate and its historical reason, preserving protected buyer/tenant/seller/landlord intent",
                "Resolve current Real Estate account/campaign/ad-group/shared-list scope and inherited exclusions without replaying old campaign names",
                "Test exact supplied positive library and reviewed protected corpus, assess lost coverage and obtain independent exclusion approval",
                "Leave unmeasured volume/CPC and unresolved scope null; obtain separate live settings authorization before any future application"],
            "placements": placements, "candidates": list(groups.values())}


def assemble(member_bytes, intake_date):
    if len(member_bytes) != MEMBER_BYTES or hashlib.sha256(member_bytes).hexdigest() != MEMBER_SHA256:
        raise ValueError("Selected negative source bytes differ from the reviewed pin")
    return build_document(parse_csv(member_bytes, FIELDS), intake_date)


def validate_intake(document):
    if not isinstance(document, dict):
        raise ValueError("Historical negative staging must be an object")
    try:
        placements = document["placements"]
        records = [{"record_ordinal": row["source_locator"]["record_ordinal"],
                    "start_line": row["source_locator"]["start_line"], "end_line": row["source_locator"]["end_line"],
                    "fields": row["original_negative_fields"]} for row in placements]
        expected = build_document(records, document["intake_date"])
    except (KeyError, TypeError) as error:
        raise ValueError("Invalid historical negative staging structure") from error
    if canonical_hash(document) != canonical_hash(expected):
        raise ValueError("Staging provenance, grouping, counts, unknown scope or unapproved state changed")
    return {"status": "PASS_STAGING_ONLY", **{key: expected["counts"][key] for key in [
        "historical_placements", "distinct_unreviewed_candidates", "reviewed_negative_rows", "approved_exclusion_rows",
        "deployed_rows_from_this_intake", "reviewed_negative_target", "reviewed_negative_deficit"]},
        "current_scope_assigned": False, "deployment_export_allowed": False, "production_writes_available": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--intake-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    ensure_output_is_not_input(args.output, [args.archive, args.report])
    ensure_output_is_not_input(args.report, [args.archive, args.output])
    document = assemble(read_pinned_archive(args.archive), args.intake_date)
    report = validate_intake(document)
    encoded = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    report["intake_sha256"] = hashlib.sha256(encoded).hexdigest()
    for path, content in [(args.output, encoded), (args.report, (json.dumps(report, indent=2) + "\n").encode("utf-8"))]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    print(json.dumps(report))


if __name__ == "__main__":
    main()
