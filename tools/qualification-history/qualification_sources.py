"""Private, no-network source grouping after whole-history person deduplication.

Source rows are staff attestations bound to the exact ledger bytes. A GCLID,
optional permission, form field or UTM alone never establishes Ads attribution.
The tool checks the attestation's structure, not the truth of an external report.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import re
import uuid

SCHEMA = "bsre-qualified-source-review-v1"
GROUPS = ("ADS_ATTRIBUTED", "OTHER_SOURCE", "UNKNOWN_SOURCE")
CAMPAIGNS = {"24372566774", "24367388382", "24378494092", "24378494098"}
# Historical attribution is reportable; none of these IDs may ever be enabled.
# Exact IDs are retained in ../legacy-campaign-baseline.json (13 paused/3 removed).
LEGACY_CAMPAIGNS = {"24150698534", "24155034442", "24155057422", "24155553763",
                    "24155555722", "24230718615", "24236347619", "24241801813",
                    "24271138041", "24271196121", "24271198545", "24271199472",
                    "24276622514", "24282277141", "24315232758", "24323098746"}
ENVELOPE_FIELDS = {"schema", "fixture_only", "ledger_sha256", "records"}
ROW_FIELDS = {"outcome_id", "lead_id", "source_group", "evidence_kind",
              "evidence_reference", "evidence_sha256", "reviewer_reference",
              "reviewed_at_utc", "review_verified", "customer_id", "campaign_id"}


def _error(code):
    raise ValueError(code)


def _utc(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        _error("INVALID_SOURCE_REVIEW_TIME")
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.tzinfo is None or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        _error("INVALID_SOURCE_REVIEW_TIME")
    return parsed


def _opaque(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9:_-]{1,150}", value) is not None


def _row_codes(row, record, now):
    codes = []
    if set(row) != ROW_FIELDS:
        _error("SOURCE_REVIEW_FIELDS_INVALID_CONTACT_DATA_FORBIDDEN")
    try:
        uuid.UUID(row["outcome_id"])
    except (ValueError, TypeError, AttributeError):
        codes.append("INVALID_SOURCE_OUTCOME_ID")
    if not _opaque(row["lead_id"]) or row["lead_id"] != record["lead_id"]:
        codes.append("SOURCE_LEAD_JOIN_MISMATCH")
    for key in ("evidence_reference", "reviewer_reference"):
        if not _opaque(row[key]):
            codes.append("SOURCE_EVIDENCE_REFERENCE_INVALID")
    if not isinstance(row["evidence_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["evidence_sha256"]):
        codes.append("SOURCE_EVIDENCE_HASH_INVALID")
    if row["review_verified"] is not True:
        codes.append("SOURCE_REVIEW_NOT_VERIFIED")
    try:
        reviewed = _utc(row["reviewed_at_utc"])
        occurred = _utc(record["occurred_at_utc"])
        if reviewed > now or reviewed < occurred:
            codes.append("SOURCE_REVIEW_TIME_ORDER_INVALID")
    except (ValueError, TypeError, OverflowError):
        codes.append("INVALID_SOURCE_REVIEW_TIME")
    if row["source_group"] == "ADS_ATTRIBUTED":
        if row["evidence_kind"] != "GOOGLE_ADS_NATIVE_RECONCILIATION":
            codes.append("ADS_NATIVE_RECONCILIATION_NOT_ATTESTED")
        if row["customer_id"] != "573-038-4686" or row["campaign_id"] not in (CAMPAIGNS | LEGACY_CAMPAIGNS):
            codes.append("ADS_ACCOUNT_OR_CAMPAIGN_NOT_ALLOWLISTED")
    elif row["source_group"] == "OTHER_SOURCE":
        if row["evidence_kind"] != "OTHER_SOURCE_BUSINESS_REVIEW":
            codes.append("OTHER_SOURCE_REVIEW_NOT_ATTESTED")
        if row["customer_id"] is not None or row["campaign_id"] is not None:
            codes.append("OTHER_SOURCE_HAS_ADS_BINDING")
    else:
        codes.append("SOURCE_GROUP_NOT_SUPPORTED")
    return sorted(set(codes))


def source_report(selected, review, now, fixture_only, ledger_sha256, history_complete, ambiguous_first_outcome_ids=frozenset()):
    """Return aggregate counts only; never return private joins or evidence values."""
    if now.tzinfo is None:
        _error("SOURCE_REPORT_TIME_WITHOUT_ZONE")
    now = now.astimezone(timezone.utc)
    rows = {}
    conflicts = set()
    if review is not None:
        if not isinstance(review, dict) or set(review) != ENVELOPE_FIELDS:
            _error("SOURCE_REVIEW_ENVELOPE_INVALID")
        if review["schema"] != SCHEMA or type(review["fixture_only"]) is not bool or review["fixture_only"] != fixture_only:
            _error("SOURCE_REVIEW_SCHEMA_OR_FIXTURE_MISMATCH")
        if not isinstance(ledger_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", ledger_sha256):
            _error("SOURCE_LEDGER_HASH_REQUIRED")
        if review["ledger_sha256"] != ledger_sha256:
            _error("SOURCE_REVIEW_LEDGER_HASH_MISMATCH")
        if not isinstance(review["records"], list):
            _error("SOURCE_REVIEW_RECORDS_INVALID")
        for row in review["records"]:
            if not isinstance(row, dict) or set(row) != ROW_FIELDS:
                _error("SOURCE_REVIEW_FIELDS_INVALID_CONTACT_DATA_FORBIDDEN")
            oid = row["outcome_id"]
            if not isinstance(oid, str):
                _error("SOURCE_REVIEW_OUTCOME_ID_INVALID")
            if oid in rows and rows[oid] != row:
                conflicts.add(oid)
            else:
                rows[oid] = row
    counts = Counter({group: 0 for group in GROUPS})
    days = {}
    holds = Counter()
    cohorts = {"APPROVED_NEW_CAMPAIGNS": 0, "LEGACY_DORMANT_CAMPAIGNS": 0}
    for day, record in selected:
        oid = record["outcome_id"]
        row = rows.get(oid)
        if oid in ambiguous_first_outcome_ids:
            codes = ["FIRST_QUALIFICATION_TIE_REVIEW_REQUIRED"]
        elif oid in conflicts:
            codes = ["SOURCE_REVIEW_CONFLICT"]
        elif row is None:
            codes = ["SOURCE_REVIEW_MISSING"]
        else:
            codes = _row_codes(row, record, now)
        group = "UNKNOWN_SOURCE" if codes else row["source_group"]
        counts[group] += 1
        if group == "ADS_ATTRIBUTED":
            cohorts["APPROVED_NEW_CAMPAIGNS" if row["campaign_id"] in CAMPAIGNS else "LEGACY_DORMANT_CAMPAIGNS"] += 1
        day_counts = days.setdefault(day, {key: 0 for key in GROUPS})
        day_counts[group] += 1
        holds.update(codes)
    return {
        "provided_history_first_qualified_by_source": dict(counts),
        "provided_history_first_qualified_by_day_and_source": dict(sorted(days.items())),
        "qualified_target_count_by_source": dict(counts) if history_complete else None,
        "provided_history_ads_qualified_by_campaign_cohort": cohorts,
        "qualified_target_ads_count_by_campaign_cohort": dict(cohorts) if history_complete else None,
        "source_review_hold_counts": dict(sorted(holds.items())),
        "source_review_bound_to_ledger_bytes": review is not None,
        "source_evidence_truth_independently_verified": False,
        "source_classification_scope": "Staff-reviewed supplied evidence, after whole-history first-person deduplication; native Google attribution is not independently verified by this local tool",
        "source_classification_changes_optional_permission_or_upload_eligibility": False,
    }
