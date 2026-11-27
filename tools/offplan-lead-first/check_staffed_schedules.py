"""Review the staffed Search schedule on the five existing paused parents."""

from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from check_ads_settings_readback import MAX_BYTES, pinned_capture, read_plan, require, verify
from check_uae_activation_scope import timestamp

DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SHIFT = ("10:00", "19:00")
ZONE = "Asia/Dubai"
DETAIL_FORMAT = "OFFPLAN_AD_SCHEDULE_DETAIL_V1"
SOURCES = {"time_zone": "Google Ads account settings", "weekly_rows": "Google Ads Ad schedule, all days"}


def detail_rows(detail, capture, reference, capture_sha256, evidence, markets, now):
    require(detail.get("format") == DETAIL_FORMAT
            and detail.get("account_id") == capture["account_id"]
            and detail.get("account_time_zone") == ZONE
            and detail.get("settings_sha256") == capture_sha256.lower()
            and detail.get("readback_sources") == SOURCES
            and detail.get("original_source_sha256") == evidence["original_source_sha256"],
            "Detail account, verified time zone or settings capture differs")
    start = timestamp(evidence["not_before_utc"])
    finish = timestamp(detail["captured_at_utc"])
    require(timestamp(reference["captured_at_utc"]) < start <= timestamp(capture["captured_at_utc"]) <= finish <= now,
            "Grid and detail must be inside the current verification window")
    observations = detail["campaigns"]
    require(isinstance(observations, list), "Detail campaign inventory must be a list")
    by_id = {row["campaign_id"]: row["schedule"] for row in observations}
    require(len(observations) == len(by_id) == 5
            and set(by_id) == {row["campaign_id"] for row in markets.values()},
            "Detail campaign identity is incomplete or differs")
    return by_id


def exact_week(rows):
    require(isinstance(rows, list), "Detail schedule must be a list")
    return len(rows) == 7 and {
        row["day"] for row in rows
        if (row["start"], row["end"]) == SHIFT
        and type(row["bid_adjustment_percent"]) is int and row["bid_adjustment_percent"] == 0
    } == set(DAYS)


def build(capture, reference, capture_sha256, reference_sha256, *, detail=None, evidence=None, now=None):
    settings = verify(capture, reference)
    plan, _ = read_plan()
    require(all(row["schedule_timezone"] == ZONE and row["schedule"] == "10:00-19:00 daily"
                for row in plan["markets"]), "Planned staffed window differs")
    markets = settings["markets"]
    require((detail is None) == (evidence is None), "Detail and independently pinned evidence must be paired")
    if now is None:
        now = datetime.now(timezone.utc)
    by_id = detail_rows(detail, capture, reference, capture_sha256, evidence, markets, now) if detail is not None else {}
    schedule = [{"day": day, "start": SHIFT[0], "end": SHIFT[1], "bid_adjustment_percent": 0} for day in DAYS]
    result = []
    for country, row in markets.items():
        campaign_id = row["campaign_id"]
        state = "WEEKLY_DETAIL_REQUIRED"
        if row["schedule_display"] == "All day":
            state = "ALL_DAY_IN_CAPTURE"
        if by_id:
            if exact_week(by_id[campaign_id]) and row["schedule_matches_plan"]:
                state = "EXACT_WEEK_MATCHED"
            else:
                state = "GRID_OR_WEEKLY_DETAIL_DIFFERS"
        result.append({
            "country": country, "campaign_id": campaign_id, "state": state,
            "observed_schedule": row["schedule_display"],
        })
    return {
        "status": "PAUSED_SCHEDULE_REVIEW", "launch_readiness": "HOLD", "launch_authorized": False,
        "account_id": settings["account_id"], "planned_schedule_time_zone": ZONE,
        "capture_sha256": capture_sha256.lower(), "captured_at_utc": capture["captured_at_utc"],
        "reference_sha256": reference_sha256.lower(),
        "weekly_detail_evidence": evidence | {"captured_at_utc": detail["captured_at_utc"]} if by_id else None,
        "paused_or_removed_campaign_count": settings["campaigns"],
        "average_daily_budget_aed": settings["average_daily_budget_aed"],
        "weekly_detail_supplied": detail is not None, "reviewed_week": schedule, "campaigns": result,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    parser.add_argument("sha256")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--detail", type=Path)
    parser.add_argument("--detail-sha256")
    parser.add_argument("--original-detail", type=Path)
    parser.add_argument("--original-detail-sha256")
    parser.add_argument("--not-before-utc")
    args = parser.parse_args()
    try:
        detail_inputs = (args.detail, args.detail_sha256, args.original_detail, args.original_detail_sha256,
                         args.not_before_utc)
        require(all(detail_inputs) or not any(detail_inputs), "Provide detail and original readbacks, pins and window together")
        detail = pinned_capture(args.detail, args.detail_sha256) if args.detail else None
        evidence = None
        if detail is not None:
            with args.original_detail.open("rb") as stream:
                original = stream.read(MAX_BYTES + 1)
            original_pin = args.original_detail_sha256.lower()
            require(0 < len(original) <= MAX_BYTES and sha256(original).hexdigest() == original_pin,
                    "Original schedule and time-zone readback size or SHA-256 mismatch")
            evidence = {"detail_sha256": args.detail_sha256.lower(), "original_source_sha256": original_pin,
                        "not_before_utc": args.not_before_utc}
        capture = pinned_capture(args.capture, args.sha256)
        reference = pinned_capture(args.reference, args.reference_sha256)
        report = build(capture, reference, args.sha256, args.reference_sha256, detail=detail, evidence=evidence)
    except (OSError, KeyError, TypeError, AttributeError, ValueError) as error:
        print(json.dumps({"status": "HOLD", "launch_authorized": False, "reason": str(error)}))
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
