"""Check saved account and all-status UAE ad-group scope for one release stage."""

from argparse import ArgumentParser
from datetime import datetime, timezone
import json
from pathlib import Path

from check_ads_settings_readback import CAPTURE_TIME_FORMAT, HERE, pinned_capture, require, roster


CHILD_SCHEMA = "bsre.offplan.uae-all-ad-group-readback.v1"
AD_GROUP_STATUSES = ["Enabled", "Paused", "Removed"]
STAGE_STATES = {
    "staged": ("Paused", "Enabled"),
    "enabled": ("Enabled", "Enabled"),
    "rollback": ("Paused", "Paused"),
}


def timestamp(value):
    return datetime.strptime(value, CAPTURE_TIME_FORMAT).replace(tzinfo=timezone.utc)


def check_children(capture, account_id, parent_id, offplan_id, resale_id, offplan_state):
    require(isinstance(capture, dict) and capture.get("schema") == CHILD_SCHEMA,
            "All-status UAE child readback required")
    require(capture["account_id"] == account_id and capture["campaign_or_ad_group_changes"] is False,
            "Wrong child readback account or write recorded")
    require(capture["view"] == {"campaign_id": parent_id, "ad_group_statuses": AD_GROUP_STATUSES, "other_filters": []},
            "Expected an all-status ad-group view scoped only to the exact UAE parent")
    rows = capture["ad_groups"]
    require(isinstance(rows, list), "Missing ad-group rows")
    by_id = {row["ad_group_id"]: row for row in rows}
    require(type(capture["view_total"]) is int and capture["view_total"] == len(rows) == len(by_id),
            "Incomplete or duplicate ad-group rows")
    require(set(by_id) == {offplan_id, resale_id} and all(row["campaign_id"] == parent_id for row in rows),
            "Unexpected or missing UAE child identity")
    require(by_id[resale_id]["explicit_status"] == "Paused", "Resale child must be explicitly paused")
    require(by_id[offplan_id]["explicit_status"] == offplan_state,
            "Off-plan child state differs from the selected stage")


def verify(stage, current, children, reference, not_before, *, now=None):
    parent_state, offplan_state = STAGE_STATES[stage]
    launch = json.loads((HERE / "launch.json").read_bytes())
    account_id = launch["account_id"]
    uae = next(market for market in launch["markets"] if market["country_code"] == "AE")
    parent_id, offplan_id = uae["campaign_id"], uae["offplan_ad_group_id"]
    resale_id = launch["resale_ad_group_keep_paused"]

    baseline = roster(reference, account_id)
    require(parent_id in baseline and baseline[parent_id]["campaign_state"] == "Paused",
            "Exact UAE parent is missing from the paused reference")
    enabled_id = parent_id if parent_state == "Enabled" else None
    observed = roster(current, account_id, enabled_campaign_id=enabled_id)
    expected = {key: row["campaign_state"] for key, row in baseline.items()}
    expected[parent_id] = parent_state
    require({key: row["campaign_state"] for key, row in observed.items()} == expected,
            "Campaign identity or status differs from the frozen roster for this stage")
    check_children(children, account_id, parent_id, offplan_id, resale_id, offplan_state)

    start = timestamp(not_before)
    now = now if now is not None else datetime.now(timezone.utc)
    require(timestamp(reference["captured_at_utc"]) < start <= now,
            "Readback window must follow the frozen reference and begin by the verification time")
    require(all(start <= timestamp(capture["captured_at_utc"]) <= now for capture in (current, children)),
            "Both readbacks must be captured within the current verification window")
    return {
        "status": "MATCHED_UAE_ACTIVATION_SCOPE", "scope_match": True, "launch_authorized": False,
        "stage": stage, "account_id": account_id, "campaign_id": parent_id, "campaign_state": parent_state,
        "offplan_ad_group_id": offplan_id, "offplan_ad_group_state": offplan_state,
        "resale_ad_group_id": resale_id, "resale_ad_group_state": "Paused", "campaigns_compared": len(observed),
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGE_STATES)
    parser.add_argument("campaigns", type=Path)
    parser.add_argument("campaigns_sha256")
    parser.add_argument("children", type=Path)
    parser.add_argument("children_sha256")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--not-before", required=True, metavar="YYYY-MM-DD HH:MM:SS UTC",
                        help="UTC start of the current stage's readback window")
    args = parser.parse_args()
    try:
        result = verify(args.stage, pinned_capture(args.campaigns, args.campaigns_sha256),
                        pinned_capture(args.children, args.children_sha256),
                        pinned_capture(args.reference, args.reference_sha256), args.not_before)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"status": "HOLD", "scope_match": False, "launch_authorized": False, "reason": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
