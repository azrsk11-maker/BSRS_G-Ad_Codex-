"""Fail-closed validation for the 360-slot native campaign/page planning registry."""
from __future__ import annotations
import json, re, sys
from pathlib import Path

EXPECTED = 360

def validate(path: Path) -> dict:
    try:
        rows = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("INVALID_REGISTRY") from exc
    if not isinstance(rows, list) or len(rows) != EXPECTED:
        raise ValueError("EXACT_360_REQUIRED")
    seen_campaign, seen_page = set(), set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError("ROW_OBJECT")
        campaign = f"BSRE-C{index:04d}"
        page = f"BSRE-LP{index:04d}"
        if row.get("campaign_key") != campaign or row.get("landing_page_id") != page:
            raise ValueError("SEQUENTIAL_IDS")
        if campaign in seen_campaign or page in seen_page:
            raise ValueError("DUPLICATE_IDS")
        seen_campaign.add(campaign); seen_page.add(page)
        if row.get("website_scope") != "EXISTING_MAIN_SITE_NATIVE_PAGE":
            raise ValueError("NATIVE_SCOPE")
        if row.get("status") != "PLANNED_SOURCE_REQUIRED":
            raise ValueError("PLANNING_STATUS")
        if row.get("actual_url") is not None or row.get("google_campaign_id") is not None:
            raise ValueError("LIVE_BINDING_PRESENT")
        if row.get("budget_approved") is not False or row.get("release_approved") is not False:
            raise ValueError("RELEASE_AUTHORITY")
    return {"passed": True, "planned_slots": EXPECTED, "actual_urls": 0, "campaign_ids": 0, "release_approved": 0}

if __name__ == "__main__":
    print(json.dumps(validate(Path(sys.argv[1])), sort_keys=True))
