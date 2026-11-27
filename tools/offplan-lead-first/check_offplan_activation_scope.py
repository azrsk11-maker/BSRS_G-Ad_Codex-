"""Compare pinned Ads captures with a reviewed off-plan activation scope."""

from argparse import ArgumentParser
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from check_ads_settings_readback import (CAPTURE_TIME_FORMAT, check_applied_pools, check_visible_search_settings,
                                         pinned_capture, read_plan, require, roster)
from check_uae_activation_scope import AD_GROUP_STATUSES, STAGE_STATES as UAE_STAGES, check_children, timestamp


SCOPE_SCHEMA = "bsre.offplan.activation-scope.v1"
CHILD_SCHEMA = "bsre.offplan.all-ad-group-readback.v1"
STAGES = {"staged": UAE_STAGES["staged"], "serving": UAE_STAGES["enabled"], "rollback": UAE_STAGES["rollback"]}
MATCHED = "MATCHED_OFFPLAN_ACTIVATION_SCOPE"


def valid_group_id(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value) is not None


def selected_groups(scope, account_id, pools, uae_group, resale_group):
    require(isinstance(scope, dict) and set(scope) == {"schema", "account_id", "markets"}
            and scope["schema"] == SCOPE_SCHEMA and scope["account_id"] == account_id,
            "Wrong activation scope schema or account")
    markets = scope["markets"]
    require(isinstance(markets, dict) and bool(markets) and markets.keys() <= pools.keys(),
            "Select a nonempty subset of the five applied markets")
    seen = {uae_group, resale_group}
    selected = {}
    for country, row in markets.items():
        require(isinstance(row, dict) and set(row) == {"campaign_id", "offplan_ad_group_ids"}
                and row["campaign_id"] == pools[country]["id"], f"{country} approved parent identity differs")
        ids = row["offplan_ad_group_ids"]
        require(isinstance(ids, list) and bool(ids) and all(valid_group_id(group) for group in ids)
                and len(ids) == len(set(ids)), f"{country} invalid or duplicate off-plan group IDs")
        selected[country] = set(ids)
        if country == "AE":
            require(ids == [uae_group], "UAE scope must name the retained off-plan group only")
        else:
            require(not seen.intersection(ids), f"{country} off-plan group ID belongs to another scope")
            seen.update(ids)
    return selected


def check_market_children(capture, account_id, parent_id, allowed, child_state):
    require(isinstance(capture, dict) and capture.get("schema") == CHILD_SCHEMA,
            "All-status market child readback required")
    require(capture["account_id"] == account_id and capture["campaign_or_ad_group_changes"] is False,
            "Wrong child readback account or write recorded")
    require(capture["view"] == {"campaign_id": parent_id, "ad_group_statuses": AD_GROUP_STATUSES, "other_filters": []},
            "Expected an all-status ad-group view scoped only to the exact market parent")
    rows = capture["ad_groups"]
    require(isinstance(rows, list), "Missing ad-group rows")
    by_id = {row["ad_group_id"]: row["explicit_status"] for row in rows}
    require(type(capture["view_total"]) is int and capture["view_total"] == len(rows) == len(by_id),
            "Incomplete or duplicate ad-group rows")
    require(all(row["campaign_id"] == parent_id and valid_group_id(row["ad_group_id"]) for row in rows)
            and all(status in AD_GROUP_STATUSES for status in by_id.values()), "Invalid ad-group identity or status")
    require(allowed <= by_id.keys() and all(by_id[group] == child_state for group in allowed),
            "An approved off-plan group is missing or differs from the selected stage")
    expected_enabled = allowed if child_state == "Enabled" else set()
    require({group for group, state in by_id.items() if state == "Enabled"} == expected_enabled,
            "Unexpected enabled group outside the reviewed off-plan scope")
    return by_id.keys()


def check_prior(stage, prior, account, scope_sha256, reference_sha256, start):
    if stage == "staged":
        require(prior is None, "A staged check starts a new verification sequence")
        return
    allowed = ("staged",) if stage == "serving" else ("staged", "serving")
    require(isinstance(prior, dict) and prior.get("status") == MATCHED and prior.get("scope_match") is True
            and prior.get("launch_authorized") is False and prior.get("stage") in allowed
            and prior.get("account_id") == account, "A matched prior stage receipt is required")
    require(prior.get("scope_sha256") == scope_sha256 and prior.get("reference_sha256") == reference_sha256,
            "Reviewed scope or frozen reference differs from the prior stage")
    require(timestamp(prior["latest_readback_utc"]) < start, "Current stage must follow the prior stage readbacks")


def verify(stage, current, children, reference, scope, not_before, *, scope_sha256, reference_sha256, prior=None, now=None):
    parent_state, child_state = STAGES[stage]
    require(all(isinstance(pin, str) and re.fullmatch(r"[0-9a-fA-F]{64}", pin) for pin in (scope_sha256, reference_sha256)),
            "Valid reviewed scope and frozen reference pins are required")
    scope_sha256, reference_sha256 = scope_sha256.lower(), reference_sha256.lower()
    plan, applied = read_plan()
    account = plan["account_id"]
    markets = {market["country_code"]: market for market in plan["markets"]}
    uae = markets["AE"]
    uae_group, resale_group = uae["offplan_ad_group_id"], plan["resale_ad_group_keep_paused"]

    baseline = roster(reference, account)
    pools, configured_budget = check_applied_pools(baseline, plan, applied)
    require(all(baseline[row["id"]]["campaign_state"] == "Paused" for row in pools.values()),
            "All five applied parents must be paused in the frozen reference")
    selected = selected_groups(scope, account, pools, uae_group, resale_group)
    parents = {country: pools[country]["id"] for country in selected}
    enabled = set(parents.values()) if parent_state == "Enabled" else set()
    observed = roster(current, account, enabled_campaign_ids=enabled)
    check_applied_pools(observed, plan, applied)
    for country, parent in parents.items():
        check_visible_search_settings(observed[parent], markets[country])
    expected = {key: row["campaign_state"] for key, row in baseline.items()}
    expected.update(dict.fromkeys(enabled, "Enabled"))
    require({key: row["campaign_state"] for key, row in observed.items()} == expected,
            "Campaign identity or status differs from the frozen roster for this stage")

    require(isinstance(children, dict) and children.keys() == selected.keys() | {"AE"},
            "Complete child readbacks required for selected markets and the shared UAE parent")
    uae_child_state = child_state if "AE" in selected else "Paused"
    check_children(children["AE"], account, uae["campaign_id"], uae_group, resale_group, uae_child_state)
    seen = {uae_group, resale_group}
    for country, groups in selected.items():
        if country == "AE":
            continue
        observed_groups = check_market_children(children[country], account, parents[country], groups, child_state)
        require(not seen.intersection(observed_groups), "An ad-group identity appears under multiple parents")
        seen.update(observed_groups)

    start = timestamp(not_before)
    now = now if now is not None else datetime.now(timezone.utc)
    require(timestamp(reference["captured_at_utc"]) < start <= now,
            "Readback window must follow the frozen reference and begin by the verification time")
    observed_times = [timestamp(capture["captured_at_utc"]) for capture in (current, *children.values())]
    require(all(start <= observed_time <= now for observed_time in observed_times),
            "All current readbacks must be captured within the verification window")
    check_prior(stage, prior, account, scope_sha256, reference_sha256, start)

    return {
        "status": MATCHED, "scope_match": True, "launch_authorized": False,
        "stage": stage, "account_id": account, "campaigns_compared": len(observed),
        "scope_sha256": scope_sha256, "reference_sha256": reference_sha256,
        "latest_readback_utc": max(observed_times).strftime(CAPTURE_TIME_FORMAT),
        "selected_markets": sorted(selected), "child_readback_markets": sorted(children),
        "configured_daily_budget_aed": configured_budget,
        "enabled_daily_budget_aed": sum(row["average_daily_budget_AED"] for row in pools.values() if row["id"] in enabled),
        "uae_resale_ad_group_state": "Paused", "actual_serving_verified": False,
    }


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("campaigns", type=Path)
    parser.add_argument("campaigns_sha256")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--scope", type=Path, required=True, help="Reviewed account and selected parent/group IDs")
    parser.add_argument("--scope-sha256", required=True)
    parser.add_argument("--prior", type=Path, help="Matched preceding stage receipt for serving or rollback")
    parser.add_argument("--prior-sha256")
    parser.add_argument("--children", nargs=3, action="append", required=True, metavar=("MARKET", "FILE", "SHA256"))
    parser.add_argument("--not-before", required=True, metavar="YYYY-MM-DD HH:MM:SS UTC")
    args = parser.parse_args()
    try:
        require(bool(args.prior) == bool(args.prior_sha256), "Prior stage receipt and pin must be provided together")
        prior = pinned_capture(args.prior, args.prior_sha256) if args.prior else None
        markets = [market for market, _, _ in args.children]
        require(len(markets) == len(set(markets)), "Duplicate child market capture")
        result = verify(args.stage, pinned_capture(args.campaigns, args.campaigns_sha256),
                        {market: pinned_capture(Path(path), pin) for market, path, pin in args.children},
                        pinned_capture(args.reference, args.reference_sha256), pinned_capture(args.scope, args.scope_sha256),
                        args.not_before, scope_sha256=args.scope_sha256, reference_sha256=args.reference_sha256, prior=prior)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"status": "HOLD", "scope_match": False, "launch_authorized": False, "reason": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
