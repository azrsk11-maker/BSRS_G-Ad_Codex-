"""Offline staffed response measurement. Emits aggregates only."""
import argparse
from datetime import date, timedelta, timezone
import json
from pathlib import Path

from release_packet import instant, load_json

DUBAI = timezone(timedelta(hours=4))
SHIFT_START = 10 * 3600
SHIFT_SECONDS = 9 * 3600
TARGET_SECONDS = 30 * 60


def staffed_clock(value):
    local = value.astimezone(DUBAI)
    elapsed = local.hour * 3600 + local.minute * 60 + local.second - SHIFT_START
    return local.toordinal() * SHIFT_SECONDS + min(SHIFT_SECONDS, max(0, elapsed))


def summarize(data):
    if not isinstance(data, dict) or set(data) != {"as_of_utc", "cases"}:
        raise ValueError("Invalid evidence envelope")
    as_of = instant(data["as_of_utc"])
    cases = data["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 10000:
        raise ValueError("Invalid case count")
    keys = set()
    delays = []
    missing = late = 0
    for case in cases:
        if not isinstance(case, dict) or set(case) != {"case_key", "accepted_at_utc", "first_attempt_at_utc"}:
            raise ValueError("Invalid case")
        key = case["case_key"]
        if not isinstance(key, str) or not key or len(key) > 128 or key in keys:
            raise ValueError("Missing or duplicate case key")
        keys.add(key)
        accepted = instant(case["accepted_at_utc"])
        attempt = case["first_attempt_at_utc"]
        attempted = instant(attempt) if attempt is not None else None
        end = attempted if attempted is not None else as_of
        if not accepted <= end <= as_of:
            raise ValueError("Invalid event order")
        seconds = staffed_clock(end) - staffed_clock(accepted)
        late += seconds > TARGET_SECONDS
        if attempted is None:
            missing += 1
        else:
            delays.append(seconds)
    return {
        "peak_first_contact_sample_count": len(delays),
        "peak_first_contact_max_seconds": max(delays, default=None),
        "missing_first_attempt_count": missing,
        "late_first_attempt_count": late,
        "within_target_for_supplied_sample": missing == 0 and late == 0,
    }


def summarize_capacity(data):
    if not isinstance(data, dict) or set(data) != {"days"}:
        raise ValueError("Invalid capacity evidence envelope")
    days = data["days"]
    if not isinstance(days, list) or not 1 <= len(days) <= 31:
        raise ValueError("Invalid staffed day count")
    fields = {"opening_backlog", "arrivals", "completed", "closing_backlog"}
    dates = set()
    for row in days:
        if not isinstance(row, dict) or set(row) != fields | {"dubai_date"}:
            raise ValueError("Invalid staffed day")
        day = date.fromisoformat(row["dubai_date"])
        if day.isoformat() != row["dubai_date"] or day in dates:
            raise ValueError("Invalid or duplicate Dubai date")
        dates.add(day)
        if any(type(row[key]) is not int or not 0 <= row[key] <= 10000 for key in fields):
            raise ValueError("Invalid capacity count")
        if row["opening_backlog"] + row["arrivals"] != row["completed"] + row["closing_backlog"]:
            raise ValueError("Unreconciled daily backlog")
    ordered = sorted(days, key=lambda row: row["dubai_date"])
    gaps = 0
    for earlier, later in zip(ordered, ordered[1:]):
        elapsed = date.fromisoformat(later["dubai_date"]) - date.fromisoformat(earlier["dubai_date"])
        if elapsed.days != 1:
            gaps += 1
        elif earlier["closing_backlog"] != later["opening_backlog"]:
            raise ValueError("Unreconciled overnight backlog")
    return {
        "staffed_days_supplied": len(days),
        "sample_date_gaps": gaps,
        "total_arrivals": sum(row["arrivals"] for row in days),
        "total_completed": sum(row["completed"] for row in days),
        "min_daily_completions_observed": min(row["completed"] for row in days),
        "days_with_backlog_growth": sum(row["closing_backlog"] > row["opening_backlog"] for row in days),
        "max_closing_backlog": max(row["closing_backlog"] for row in days),
        "sample_representativeness_verified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--capacity", action="store_true", help="Reconcile aggregate daily workload and backlog")
    args = parser.parse_args()
    try:
        calculator = summarize_capacity if args.capacity else summarize
        result = calculator(load_json(args.evidence))
    except (OSError, ValueError, TypeError, OverflowError):
        code = "INVALID_PRIVATE_CAPACITY_EVIDENCE" if args.capacity else "INVALID_PRIVATE_TIMING_EVIDENCE"
        print(json.dumps({"error": code}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
