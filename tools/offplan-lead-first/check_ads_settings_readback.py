"""Check a pinned account settings capture against the paused off-plan plan."""

from argparse import ArgumentParser
from collections import Counter
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parent
MAX_BYTES = 96 * 1024
FORMAT = "Chrome UI, Campaigns > Settings, Campaign status All, 1–24 of 24"
SCHEDULES = {"10:00-19:00 daily": "All days, 10:00 AM - 7:00 PM"}
DISABLED = ("auto_created_assets", "broad_match", "text_customization", "final_url_expansion", "ai_max")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pinned_capture(path, expected):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES and sha256(data).hexdigest() == expected.lower(), "Capture size or SHA-256 mismatch")
    return json.loads(data)


def roster(capture, account_id):
    require(capture["account_id"] == account_id and capture["no_ads_running"] is True, "Account identity or serving mismatch")
    require(capture["capture"] == FORMAT, "Expected a complete unfiltered settings view")
    datetime.strptime(capture["captured_at_utc"], "%Y-%m-%d %H:%M:%S UTC")
    rows = capture["campaigns"]
    require(isinstance(rows, list) and len(rows) == 24, "Incomplete campaign roster")
    by_id = {row["campaign_id"]: row for row in rows}
    require(len(by_id) == 24 and all(re.fullmatch(r"\d{10,12}", key) for key in by_id), "Invalid or duplicate campaign IDs")
    counts = Counter(row["campaign_state"] for row in rows)
    require(counts == {"Paused": 21, "Removed": 3} and counts == capture["observed_campaign_states"], "Paused or removed state drift")
    return by_id


def verify(capture, reference=None):
    plan = json.loads((HERE / "launch.json").read_bytes())
    applied = json.loads((HERE / "native-paused/APPLIED.json").read_bytes())
    account = plan["account_id"]
    ids = roster(capture, account)
    if reference is not None:
        saved = roster(reference, account)
        require({key: r["campaign_state"] for key, r in ids.items()} ==
                {key: r["campaign_state"] for key, r in saved.items()}, "Campaign identity or status differs from the frozen roster")
    observed = {}
    aggregate = 0
    markets = {row["country_code"]: row for row in plan["markets"]}
    for approved in applied["campaigns"]:
        country = approved["country"]
        goal = markets[country]
        row = ids[approved["id"]]
        allocation = approved["average_daily_budget_AED"]
        require(allocation == goal["daily_average_budget_aed"] and row["daily_amount_display"] == f"AED{allocation:,.2f}/day",
                f"{country} allocation differs")
        require(row["campaign_name"] == approved["name"] and row["campaign_state"] == "Paused",
                f"{country} identity or state differs")
        require((row["campaign_type"], row["bidding_strategy"], row["networks"], row["location_display"],
                 row["positive_bid_adjustment_display"]) == ("Search", "Maximize clicks", "Google search", goal["country_name"], "None")
                and all(row[key] == "Off" for key in DISABLED), f"{country} visible Search settings differ")
        aggregate += allocation
        observed[country] = {
            "campaign_id": approved["id"],
            "children_missing_in_status": "Campaign has no ad groups" in row["serving_status_display"],
            "language_display": row["language_display"],
            "schedule_display": row["schedule_display"],
            "schedule_matches_plan": row["schedule_display"] == SCHEDULES[goal["schedule"]],
        }
    require(set(observed) == set(markets) and aggregate == plan["aggregate_average_daily_budget_aed"] == 2500,
            "Incomplete or incorrect off-plan allocation")
    return {"status": "MATCHED_PAUSED_SETTINGS_CAPTURE", "launch_readiness": "HOLD", "launch_authorized": False,
            "account_id": account, "average_daily_budget_aed": aggregate, "campaigns": len(ids),
            "compared_to_frozen_roster": reference is not None, "markets": observed,
            "requires_separate_readback": ["language_criteria", "budget_resources", "location_option", "bid_cap",
                                          "effective_assets_negatives_and_automation", "serving_children_and_destinations"]}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("readback", type=Path)
    parser.add_argument("sha256")
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--reference-sha256")
    args = parser.parse_args()
    try:
        require(bool(args.reference) == bool(args.reference_sha256), "Reference capture and pin must be provided together")
        reference = pinned_capture(args.reference, args.reference_sha256) if args.reference else None
        result = verify(pinned_capture(args.readback, args.sha256), reference)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"status": "HOLD", "launch_authorized": False, "reason": str(error)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
