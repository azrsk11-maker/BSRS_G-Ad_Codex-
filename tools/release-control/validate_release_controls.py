"""Fail-closed static guard for the approved four-campaign release plan."""
from __future__ import annotations
import json, sys
from pathlib import Path

EXPECTED = {
    "BSRE_V2_SEARCH_BUYERS_UAE_EN": 1200,
    "BSRE_V2_SEARCH_OWNERS_UAE_EN": 400,
    "BSRE_V2_SEARCH_TENANTS_UAE_EN": 300,
    "BSRE_V2_SEARCH_BRAND_UAE_EN": 100,
}

def validate(path: Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("INVALID_RELEASE_CONTROLS") from exc
    if data.get("schema_version") != 1 or data.get("account_id") != "573-038-4686":
        raise ValueError("ACCOUNT_OR_SCHEMA")
    if data.get("currency") != "AED" or data.get("aggregate_average_daily_budget") != 2000:
        raise ValueError("AGGREGATE_BUDGET")
    if data.get("release_authorized") is not False or data.get("ads_activation_authorized") is not False:
        raise ValueError("AUTHORITY_PRESENT")
    targeting = data.get("targeting")
    expected_targeting = {
        "locations": ["United Arab Emirates"], "location_presence": "PEOPLE_IN_OR_REGULARLY_IN",
        "language": "English", "network": "Google Search", "search_partners": False,
        "display_expansion": False, "ai_max": False, "ai_max_search_term_matching": False,
        "ai_max_text_customization": False, "ai_max_final_url_expansion": False,
    }
    if targeting != expected_targeting:
        raise ValueError("TARGETING_EXPANSION")
    if data.get("bidding") != {"strategy": "MAXIMIZE_CLICKS", "service_campaign_cpc_limit_aed": 20, "brand_campaign_cpc_limit_aed": 5, "positive_bid_adjustments_percent": 0}:
        raise ValueError("BIDDING_CONTROLS")
    campaigns = data.get("campaigns")
    if not isinstance(campaigns, list) or len(campaigns) != len(EXPECTED):
        raise ValueError("CAMPAIGN_COUNT")
    observed = {}
    for row in campaigns:
        if not isinstance(row, dict) or set(row) != {"name", "average_daily_budget", "status", "google_campaign_id"}:
            raise ValueError("CAMPAIGN_SHAPE")
        name = row["name"]
        if name in observed or name not in EXPECTED or row["average_daily_budget"] != EXPECTED[name]:
            raise ValueError("CAMPAIGN_ALLOCATION")
        if row["status"] != "PAUSED_CONSTRUCTION" or row["google_campaign_id"] is not None:
            raise ValueError("CAMPAIGN_NOT_HELD")
        observed[name] = row["average_daily_budget"]
    if observed != EXPECTED or sum(observed.values()) != 2000:
        raise ValueError("BUDGET_SUM")
    return {"passed": True, "campaigns": len(observed), "aggregate_average_daily_budget": 2000, "activation_authorized": False}

if __name__ == "__main__":
    print(json.dumps(validate(Path(sys.argv[1])), sort_keys=True))
