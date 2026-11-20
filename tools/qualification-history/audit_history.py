"""Bounded, aggregate-only audit of explicit local Outcome40/intake extracts."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from qualification_core import DUBAI, inspect_reporting, strict_json_bytes, when
from qualification_sources import GROUPS, _row_codes, source_report

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
LEDGER_FIELDS = {"fixture_only", "history_complete", "history_evidence_reference", "intake", "records"}
KNOWN_EXCLUSIONS = {"TEST_RECORD", "NOT_QUALIFIED_STAGE", "DUPLICATE_RECORD"}
HERE = Path(__file__).resolve().parent
COMPONENTS = ("audit_history.py", "qualification_core.py", "qualification_sources.py",
              "schema/outcome-register-schema.json")
COMMERCIAL_SCHEMA = "bsre-commercial-qualification-aggregate-v1"
BUSINESS_REVIEW_FIELDS = {"schema", "fixture_only", "ledger_sha256", "source_review_sha256",
    "all_available_history_reviewed", "retention_history_incomplete", "retention_marker_verified",
    "observed_at_utc", "valid_until_utc", "reviewer_reference", "evidence_reference"}


class AuditInputError(ValueError):
    """The input cannot support a complete, bounded audit."""


class AuditArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise AuditInputError("ARGUMENTS_INVALID")


def read_bounded(path: Path) -> bytes:
    try:
        initial = path.lstat()
        if not stat.S_ISREG(initial.st_mode):
            raise AuditInputError("INPUT_TYPE_NOT_REGULAR")
        if initial.st_size > MAX_FILE_BYTES:
            raise AuditInputError("INPUT_SIZE_LIMIT")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        flags |= getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise AuditInputError("INPUT_TYPE_NOT_REGULAR")
            if (initial.st_dev, initial.st_ino) != (before.st_dev, before.st_ino):
                raise AuditInputError("INPUT_CHANGED_DURING_READ")
            if before.st_size > MAX_FILE_BYTES:
                raise AuditInputError("INPUT_SIZE_LIMIT")
            with os.fdopen(descriptor, "rb", closefd=False) as source:
                raw = source.read(MAX_FILE_BYTES + 1)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if len(raw) > MAX_FILE_BYTES:
            raise AuditInputError("INPUT_SIZE_LIMIT")
        if not stat.S_ISREG(after.st_mode) or (
            before.st_size, before.st_mtime_ns, before.st_dev, before.st_ino
        ) != (
            after.st_size, after.st_mtime_ns, after.st_dev, after.st_ino
        ) or len(raw) != before.st_size:
            raise AuditInputError("INPUT_CHANGED_DURING_READ")
        return raw
    except OSError as error:
        raise AuditInputError("INPUT_UNAVAILABLE") from error


def validate_envelope(ledger: object, source_review: object | None) -> None:
    if not isinstance(ledger, dict) or set(ledger) - LEDGER_FIELDS:
        raise AuditInputError("LEDGER_ENVELOPE_INVALID")
    if type(ledger.get("fixture_only")) is not bool or type(ledger.get("history_complete")) is not bool:
        raise AuditInputError("HISTORY_CLASSIFICATION_REQUIRED")
    evidence = ledger.get("history_evidence_reference")
    if evidence is not None and (not isinstance(evidence, str) or len(evidence) > 4096):
        raise AuditInputError("HISTORY_REFERENCE_INVALID")
    if isinstance(evidence, str) and evidence and not evidence.strip():
        raise AuditInputError("HISTORY_REFERENCE_INVALID")
    for key in ("intake", "records"):
        rows = ledger.get(key)
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise AuditInputError("ROW_LIMIT_OR_SHAPE")
    if source_review is not None:
        if not isinstance(source_review, dict) or not isinstance(source_review.get("records"), list):
            raise AuditInputError("SOURCE_REVIEW_INVALID")
        if len(source_review["records"]) > MAX_ROWS:
            raise AuditInputError("ROW_LIMIT_OR_SHAPE")


def audit_history(ledger: dict, now, from_day=None, to_day=None,
                  source_review=None, ledger_sha256=None) -> dict:
    """Apply the existing business validator, exposing no record identifiers."""
    try:
        validate_envelope(ledger, source_review)
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise AuditInputError("TIMEZONE_REQUIRED")
        for value in (from_day, to_day):
            if value is not None and date.fromisoformat(value).isoformat() != value:
                raise AuditInputError("DAY_FILTER_INVALID")
        if from_day and to_day and from_day > to_day:
            raise AuditInputError("DAY_FILTER_REVERSED")
        # Keep *all* first qualifications until every history hold is known.
        # A tie outside the reporting window still withholds completeness.
        report, full_selection = inspect_reporting(ledger, now, source_review=source_review,
                                                   ledger_sha256=ledger_sha256)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        if isinstance(error, AuditInputError):
            raise
        raise AuditInputError("INPUT_OR_VALIDATION_ERROR") from error

    outcome_holds = Counter(code for issue in report["outcome_issues"] for code in issue["codes"])
    all_ties = [row for row in full_selection if row["first_qualification_tied"]]
    if all_ties:
        outcome_holds["FIRST_QUALIFICATION_TIE_REVIEW_REQUIRED"] += len(all_ties)
    selected = [row for row in full_selection if
                (from_day is None or when(row["occurred_at_utc"]).astimezone(DUBAI).date().isoformat() >= from_day) and
                (to_day is None or when(row["occurred_at_utc"]).astimezone(DUBAI).date().isoformat() <= to_day)]
    ties = [row for row in selected if row["first_qualification_tied"]]
    qualified = [row for row in selected if not row["first_qualification_tied"]]
    by_day = Counter(when(row["occurred_at_utc"]).astimezone(DUBAI).date().isoformat() for row in qualified)
    by_role = Counter(row["role"] for row in qualified)
    source_result = source_report([(when(row["occurred_at_utc"]).astimezone(DUBAI).date().isoformat(), row)
                                   for row in qualified], source_review, now, ledger["fixture_only"],
                                  ledger_sha256, report["history_complete_attested"])
    by_source = source_result["provided_history_first_qualified_by_source"]
    by_day_source = source_result["provided_history_first_qualified_by_day_and_source"]
    # Reuse the original classifier's row rules. Native campaign IDs are only
    # aggregate source evidence, never an invented BSRE-Cxxxx mapping.
    source_rows, conflicts = {}, set()
    for row in source_review["records"] if source_review is not None else []:
        oid = row["outcome_id"]
        if oid in source_rows and source_rows[oid] != row:
            conflicts.add(oid)
        else:
            source_rows[oid] = row
    native_campaign_days = {}
    for row in qualified:
        review = source_rows.get(row["outcome_id"])
        if (review is not None and row["outcome_id"] not in conflicts and
                not _row_codes(review, row, now) and review["source_group"] == "ADS_ATTRIBUTED"):
            day = when(row["occurred_at_utc"]).astimezone(DUBAI).date().isoformat()
            counts = native_campaign_days.setdefault(day, Counter())
            counts[review["campaign_id"]] += 1
    unresolved = bool(report["held_person_mappings"] or (set(outcome_holds) - KNOWN_EXCLUSIONS))
    available = report["history_complete_attested"] and not ledger["fixture_only"] and not unresolved
    return {
        "schema": "bsre-qualification-history-audit-v1",
        "scope": "LOCAL_AGGREGATE_REVIEW_ONLY",
        "status": "AUDITED_WITH_HOLDS" if not available or outcome_holds or source_result["source_review_hold_counts"] else "AUDITED",
        "fixture_only": ledger["fixture_only"],
        "evaluated_at_utc": now.astimezone(timezone.utc).isoformat(),
        "history": {
            "complete_attested": report["history_complete_attested"],
            "truth_independently_verified": False,
            "staff_attested_first_qualification_total": len(qualified) if available else None,
        },
        "counts": {
            "intake_rows_supplied": len(ledger["intake"]),
            "outcome_rows_supplied": len(ledger["records"]),
            "outcomes_with_hold_codes": len(report["outcome_issues"]),
            "held_person_mappings": report["held_person_mappings"],
            "tied_first_qualification_people": len(ties),
            "unambiguous_first_qualifications_in_supplied_window": len(qualified),
        },
        "provided_history_by_dubai_day": dict(sorted(by_day.items())),
        "provided_history_by_role": dict(sorted(by_role.items())),
        "provided_history_by_source": by_source,
        "provided_history_by_day_and_source": by_day_source,
        "provided_history_ads_by_day_and_native_campaign": {
            day: dict(sorted(counts.items())) for day, counts in sorted(native_campaign_days.items())},
        "selection_window": {"from_day": from_day, "to_day": to_day, "end_inclusive": True,
                             "timezone": "Asia/Dubai"},
        "whole_history_business_holds_resolved": not unresolved,
        "outcome_hold_counts": dict(sorted(outcome_holds.items())),
        "source_review_hold_counts": source_result["source_review_hold_counts"],
        "source_review_bound_to_ledger_bytes": report["source_review_bound_to_ledger_bytes"],
        "source_evidence_truth_independently_verified": False,
        "contains_record_identifiers_or_click_data": False,
        "upload_supported": False,
    }


def audited_bytes(raw, now, from_day=None, to_day=None, source_raw=None, business_review_raw=None):
    """Execute the actual audit over exact bytes; return aggregate provenance only.

    Business review is a bounded source/retention/freshness attestation. It never
    authenticates its author or changes advertising permission/export state.
    """
    for value in (raw, source_raw, business_review_raw):
        if value is not None and (not isinstance(value, bytes) or len(value) > MAX_FILE_BYTES):
            raise AuditInputError("INPUT_SIZE_OR_TYPE_INVALID")
    ledger_hash = hashlib.sha256(raw).hexdigest()
    source_hash = hashlib.sha256(source_raw).hexdigest() if source_raw is not None else None
    ledger = strict_json_bytes(raw)
    source = strict_json_bytes(source_raw) if source_raw is not None else None
    result = audit_history(ledger, now, from_day, to_day, source, ledger_hash)
    holds = []
    review_summary = None
    if business_review_raw is None:
        holds.append("BUSINESS_HISTORY_REVIEW_REQUIRED")
    else:
        review = strict_json_bytes(business_review_raw)
        if not isinstance(review, dict) or set(review) != BUSINESS_REVIEW_FIELDS:
            raise AuditInputError("BUSINESS_REVIEW_FIELDS_INVALID")
        if (review["schema"] != "bsre-business-history-review-v1" or
                type(review["fixture_only"]) is not bool or review["fixture_only"] != ledger["fixture_only"]):
            raise AuditInputError("BUSINESS_REVIEW_CLASSIFICATION_INVALID")
        if review["ledger_sha256"] != ledger_hash or review["source_review_sha256"] != source_hash:
            raise AuditInputError("BUSINESS_REVIEW_INPUT_HASH_MISMATCH")
        for key in ("reviewer_reference", "evidence_reference"):
            if not isinstance(review[key], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9:_-]{0,149}", review[key]):
                raise AuditInputError("BUSINESS_REVIEW_REFERENCE_INVALID")
        if (type(review["all_available_history_reviewed"]) is not bool or
                type(review["retention_marker_verified"]) is not bool or
                (review["retention_history_incomplete"] is not None and
                 type(review["retention_history_incomplete"]) is not bool)):
            raise AuditInputError("BUSINESS_REVIEW_BOOLEAN_INVALID")
        observed, expiry = when(review["observed_at_utc"]), when(review["valid_until_utc"])
        if observed > now or expiry <= now or observed >= expiry:
            holds.append("BUSINESS_HISTORY_REVIEW_STALE_OR_FUTURE")
        if any(when(row["recorded_at_utc"]) > observed for row in ledger["records"]):
            holds.append("BUSINESS_REVIEW_PRECEDES_RECORDED_HISTORY")
        if review["all_available_history_reviewed"] is not True:
            holds.append("ALL_AVAILABLE_HISTORY_REVIEW_REQUIRED")
        if review["retention_marker_verified"] is not True or review["retention_history_incomplete"] is not False:
            holds.append("AUTHORITATIVE_RETENTION_HISTORY_NOT_COMPLETE")
        review_summary = {"observed_at_utc": observed.astimezone(timezone.utc).isoformat(),
                          "valid_until_utc": expiry.astimezone(timezone.utc).isoformat(),
                          "input_bytes_bound": True, "author_independently_verified": False}
    if not result["history"]["complete_attested"]:
        holds.append("COMPLETE_HISTORY_NOT_ATTESTED")
    if not result["whole_history_business_holds_resolved"]:
        holds.append("WHOLE_HISTORY_BUSINESS_HOLDS_UNRESOLVED")
    if from_day is None or to_day is None:
        holds.append("EXPLICIT_COMMERCIAL_WINDOW_REQUIRED")
    # Fixture reports remain visibly illustrative. The raw audit's staff total
    # stays null for fixtures; this candidate's supplied-history counts can be
    # exercised offline without claiming genuine outcomes.
    projection = {"schema": COMMERCIAL_SCHEMA, "scope": "PRIVATE_BUSINESS_AGGREGATE_REVIEW_ONLY",
        "UPLOAD_PROHIBITED": True, "fixture_only": ledger["fixture_only"],
        "evaluated_at_utc": result["evaluated_at_utc"], "selection_window": result["selection_window"],
        "holds": sorted(set(holds)), "source_truth_independently_verified": False,
        "review": review_summary, "provenance": {"ledger_sha256": ledger_hash,
            "source_review_sha256": source_hash,
            "business_review_sha256": hashlib.sha256(business_review_raw).hexdigest() if business_review_raw is not None else None,
            "validator_components_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                                              for name in COMPONENTS}},
        "source_counts": {"intake_rows_supplied": len(ledger["intake"]), "outcome_rows_supplied": len(ledger["records"]),
                          "selected_first_qualified_people": result["counts"]["unambiguous_first_qualifications_in_supplied_window"]},
        "by_day_and_source": result["provided_history_by_day_and_source"],
        "ads_by_day_and_native_campaign": result["provided_history_ads_by_day_and_native_campaign"],
        "source_hold_counts": result["source_review_hold_counts"],
        "contains_record_identifiers_or_click_data": False}
    result["commercial_qualification_aggregate"] = projection
    return result


def main(argv=None) -> int:
    parser = AuditArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--from-day")
    parser.add_argument("--to-day")
    parser.add_argument("--source-review", type=Path)
    parser.add_argument("--business-review", type=Path)
    try:
        args = parser.parse_args(argv)
        raw = read_bounded(args.ledger)
        source_raw = read_bounded(args.source_review) if args.source_review else None
        business_raw = read_bounded(args.business_review) if args.business_review else None
        result = audited_bytes(raw, when(args.now), args.from_day, args.to_day, source_raw, business_raw)
    except (AuditInputError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        code = str(error) if isinstance(error, AuditInputError) else "INPUT_OR_VALIDATION_ERROR"
        print(json.dumps({"status": "INPUT_REJECTED", "code": code, "upload_supported": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
