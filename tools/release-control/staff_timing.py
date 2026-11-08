"""Offline staffed response measurement. Emits aggregates only."""
import argparse
from datetime import timedelta, timezone
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        result = summarize(load_json(args.evidence))
    except (OSError, ValueError, TypeError, OverflowError):
        print(json.dumps({"error": "INVALID_PRIVATE_TIMING_EVIDENCE"}))
        return 2
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
