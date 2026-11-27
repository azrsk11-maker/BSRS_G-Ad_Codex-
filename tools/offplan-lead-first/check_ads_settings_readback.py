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
CAPTURE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S UTC"
SCHEDULES = {"10:00-19:00 daily": "All days, 10:00 AM - 7:00 PM"}
DISABLED = ("auto_created_assets", "broad_match", "text_customization", "final_url_expansion", "ai_max")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_fields(pairs):
    fields = dict(pairs)
    require(len(fields) == len(pairs), "Duplicate capture field")
    return fields


def pinned_capture(path, expected):
    with path.open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES and sha256(data).hexdigest() == expected.lower(), "Capture size or SHA-256 mismatch")
    return json.loads(data, object_pairs_hook=unique_fields)


def roster(capture, account_id, *, enabled_campaign_id=None, enabled_campaign_ids=None):
    require(enabled_campaign_id is None or enabled_campaign_ids is None, "Conflicting enabled campaign inputs")
    enabled_ids = set(enabled_campaign_ids) if enabled_campaign_ids is not None else set()
    if enabled_campaign_id is not None:
        enabled_ids.add(enabled_campaign_id)
    require(capture["account_id"] == account_id and isinstance(capture["no_ads_running"], bool),
            "Account identity or serving mismatch")
    if not enabled_ids:
        require(capture["no_ads_running"] is True, "Account identity or serving mismatch")
    require(capture["capture"] == FORMAT, "Expected a complete unfiltered settings view")
    datetime.strptime(capture["captured_at_utc"], CAPTURE_TIME_FORMAT)
    rows = capture["campaigns"]
    require(isinstance(rows, list) and len(rows) == 24, "Incomplete campaign roster")
    by_id = {row["campaign_id"]: row for row in rows}
    require(len(by_id) == 24 and all(re.fullmatch(r"\d{10,12}", key) for key in by_id), "Invalid or duplicate campaign IDs")
    counts = Counter(row["campaign_state"] for row in rows)
    expected = {"Paused": 21, "Removed": 3}
    if enabled_ids:
        expected.update(Paused=21 - len(enabled_ids), Enabled=len(enabled_ids))
        require(all(key in by_id and by_id[key]["campaign_state"] == "Enabled" for key in enabled_ids),
                "Intended campaign is not enabled")
    require(counts == expected and counts == capture["observed_campaign_states"], "Paused or removed state drift")
    return by_id


def read_plan():
    return (json.loads((HERE / "launch.json").read_bytes()),
            json.loads((HERE / "native-paused/APPLIED.json").read_bytes()))


def check_applied_pools(ids, plan, applied):
    markets = {row["country_code"]: row for row in plan["markets"]}
    approved = {row["country"]: row for row in applied["campaigns"]}
    require(applied["account_id"] == plan["account_id"] and len(plan["markets"]) == len(markets) == 5
            and len(applied["campaigns"]) == len(approved) == len({row["id"] for row in approved.values()}) == 5
            and approved.keys() == markets.keys(), "Incomplete or incorrect off-plan pool identities")
    aggregate = 0
    for country, pool in approved.items():
        goal = markets[country]
        row = ids[pool["id"]]
        allocation = pool["average_daily_budget_AED"]
        require(type(allocation) is int and allocation == goal["daily_average_budget_aed"]
                and row["daily_amount_display"] == f"AED{allocation:,.2f}/day", f"{country} allocation differs")
        require(row["campaign_name"] == pool["name"] == goal["campaign_name"] and pool["status"] == "Paused"
                and goal["campaign_id"] in (None, pool["id"]), f"{country} identity or state differs")
        aggregate += allocation
    require(aggregate == plan["aggregate_average_daily_budget_aed"] ==
            applied["aggregate_offplan_average_daily_budget_AED"] == 2500, "Incomplete or incorrect off-plan allocation")
    return approved, aggregate


def check_visible_search_settings(row, goal):
    require((row["campaign_type"], row["bidding_strategy"], row["networks"], row["location_display"],
             row["positive_bid_adjustment_display"]) == ("Search", "Maximize clicks", "Google search", goal["country_name"], "None")
            and all(row[key] == "Off" for key in DISABLED), f"{goal['country_code']} visible Search settings differ")


def verify(capture, reference=None):
    plan, applied = read_plan()
    account = plan["account_id"]
    ids = roster(capture, account)
    if reference is not None:
        saved = roster(reference, account)
        require({key: r["campaign_state"] for key, r in ids.items()} ==
                {key: r["campaign_state"] for key, r in saved.items()}, "Campaign identity or status differs from the frozen roster")
    approved_pools, aggregate = check_applied_pools(ids, plan, applied)
    observed = {}
    markets = {row["country_code"]: row for row in plan["markets"]}
    for country, approved in approved_pools.items():
        goal = markets[country]
        row = ids[approved["id"]]
        require(row["campaign_state"] == "Paused", f"{country} identity or state differs")
        check_visible_search_settings(row, goal)
        observed[country] = {
            "campaign_id": approved["id"],
            "children_missing_in_status": "Campaign has no ad groups" in row["serving_status_display"],
            "language_display": row["language_display"],
            "schedule_display": row["schedule_display"],
            "schedule_matches_plan": row["schedule_display"] == SCHEDULES[goal["schedule"]],
        }
    return {"status": "MATCHED_PAUSED_SETTINGS_CAPTURE", "launch_readiness": "HOLD", "launch_authorized": False,
            "account_id": account, "average_daily_budget_aed": aggregate, "campaigns": len(ids),
            "compared_to_frozen_roster": reference is not None, "markets": observed,
            "search_language_policy": plan["search_language_policy"],
            "requires_separate_readback": ["approved_rsa_keywords_and_destination_by_locale", "budget_resources", "location_option", "bid_cap",
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
