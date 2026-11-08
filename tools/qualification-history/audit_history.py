"""Bounded, aggregate-only audit of explicit local Outcome40/intake extracts."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat

from qualification_core import DUBAI, inspect_reporting, strict_json_bytes, when

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 10_000
LEDGER_FIELDS = {"fixture_only", "history_complete", "history_evidence_reference", "intake", "records"}
KNOWN_EXCLUSIONS = {"TEST_RECORD", "NOT_QUALIFIED_STAGE", "DUPLICATE_RECORD"}


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
        report, selected = inspect_reporting(
            ledger, now, from_day, to_day, source_review, ledger_sha256
        )
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        if isinstance(error, AuditInputError):
            raise
        raise AuditInputError("INPUT_OR_VALIDATION_ERROR") from error

    outcome_holds = Counter(code for issue in report["outcome_issues"] for code in issue["codes"])
    ties = [row for row in selected if row["first_qualification_tied"]]
    if ties:
        outcome_holds["FIRST_QUALIFICATION_TIE_REVIEW_REQUIRED"] += len(ties)
    qualified = [row for row in selected if not row["first_qualification_tied"]]
    by_day = Counter(when(row["occurred_at_utc"]).astimezone(DUBAI).date().isoformat() for row in qualified)
    by_role = Counter(row["role"] for row in qualified)
    by_source = dict(report["provided_history_first_qualified_by_source"])
    # The existing source classifier assigns tied earliest outcomes to UNKNOWN.
    by_source["UNKNOWN_SOURCE"] -= len(ties)
    unresolved = bool(report["held_person_mappings"] or (set(outcome_holds) - KNOWN_EXCLUSIONS))
    available = report["history_complete_attested"] and not ledger["fixture_only"] and not unresolved
    return {
        "schema": "bsre-qualification-history-audit-v1",
        "scope": "LOCAL_AGGREGATE_REVIEW_ONLY",
        "status": "AUDITED_WITH_HOLDS" if not available or outcome_holds or report["source_review_hold_counts"] else "AUDITED",
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
        "outcome_hold_counts": dict(sorted(outcome_holds.items())),
        "source_review_hold_counts": report["source_review_hold_counts"],
        "source_review_bound_to_ledger_bytes": report["source_review_bound_to_ledger_bytes"],
        "source_evidence_truth_independently_verified": False,
        "contains_record_identifiers_or_click_data": False,
        "upload_supported": False,
    }


def main(argv=None) -> int:
    parser = AuditArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--from-day")
    parser.add_argument("--to-day")
    parser.add_argument("--source-review", type=Path)
    try:
        args = parser.parse_args(argv)
        raw = read_bounded(args.ledger)
        source = strict_json_bytes(read_bounded(args.source_review)) if args.source_review else None
        result = audit_history(strict_json_bytes(raw), when(args.now), args.from_day, args.to_day,
                               source, hashlib.sha256(raw).hexdigest())
    except (AuditInputError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as error:
        code = str(error) if isinstance(error, AuditInputError) else "INPUT_OR_VALIDATION_ERROR"
        print(json.dumps({"status": "INPUT_REJECTED", "code": code, "upload_supported": False}))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
