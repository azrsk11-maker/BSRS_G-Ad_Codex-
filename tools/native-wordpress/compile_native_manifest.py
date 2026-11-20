"""Compile proposed campaign/page identities into a non-deployable native WP manifest."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

SCHEMA = "bsre-native-page-plan-v1"
PAGE_COUNT = 360


def compile_manifest(registry, allocation):
    if not isinstance(registry, list) or len(registry) != PAGE_COUNT:
        raise ValueError("Exactly 360 planned campaign/page pairs are required")
    if allocation.get("page_target") != PAGE_COUNT:
        raise ValueError("Allocation target must remain 360")
    families = allocation.get("families", [])
    family_counts = {item["code"]: item["pages"] for item in families}
    if len(family_counts) != len(families) or sum(family_counts.values()) != PAGE_COUNT:
        raise ValueError("Family allocation is duplicated or inconsistent")
    campaigns, page_ids, paths = set(), set(), set()
    actual_counts = Counter()
    pages = []
    for item in registry:
        campaign, page_id, path = (item.get(k) for k in
                                   ("campaign_key", "landing_page_id", "proposed_path"))
        if not isinstance(campaign, str) or not re.fullmatch(r"BSRE-C\d{4}", campaign):
            raise ValueError("Invalid immutable campaign key")
        if not isinstance(page_id, str) or not re.fullmatch(r"BSRE-LP\d{4}", page_id):
            raise ValueError("Invalid immutable landing-page ID")
        if path != "/lp/" + campaign.lower() + "/":
            raise ValueError("Proposed path differs from the supplied opaque route contract; resolve explicitly")
        if campaign in campaigns or page_id in page_ids or path in paths:
            raise ValueError("Campaign, page and path mappings must be one-to-one")
        if item.get("family_code") not in family_counts:
            raise ValueError("Unknown page family")
        if item.get("website_scope") != "EXISTING_MAIN_SITE_NATIVE_PAGE":
            raise ValueError("Standalone sites are outside the native-page contract")
        if item.get("visibility") != "UNLISTED_NOINDEX_PUBLIC_URL":
            raise ValueError("Unexpected page visibility")
        if any(item.get(k) is not None for k in
               ("actual_url", "google_campaign_id", "cms_content_or_native_route_id", "page_version")):
            raise ValueError("Existing deployments need explicit reconciliation; this compiler handles planned slots only")
        if item.get("budget_approved") is not False or item.get("release_approved") is not False:
            raise ValueError("Planning compilation cannot confer or consume release/budget approval")
        if item.get("status") != "PLANNED_SOURCE_REQUIRED":
            raise ValueError("A changed slot state needs a reviewed compiler transition")
        campaigns.add(campaign)
        page_ids.add(page_id)
        paths.add(path)
        actual_counts[item["family_code"]] += 1
        pages.append({"campaign_key": campaign, "landing_page_id": page_id,
                      "family_code": item["family_code"], "proposed_path": path,
                      "path_status": "PROPOSED_NOT_VERIFIED", "actual_url": None,
                      "cms_page_id": None, "google_campaign_id": None,
                      "page_version": None, "content_state": "BLOCKED_SOURCE_REQUIRED"})
    if dict(actual_counts) != family_counts:
        raise ValueError("Per-family page counts do not reconcile")
    digest = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False).encode()).hexdigest()
    return {"schema": SCHEMA, "source_registry_canonical_sha256": digest,
            "site_origin_expected": "https://blackswanrealestate.ae",
            "origin_status": "REQUIRES_CURRENT_CMS_VERIFICATION",
            "mode": "PLAN_ONLY", "page_count": len(pages),
            "family_counts": dict(sorted(actual_counts.items())),
            "native_policy": {"post_type": "page", "post_status": "draft",
                              "generated_content": False, "sitewide_changes": False,
                              "publication_allowed": False, "apply_supported": False,
                              "main_site_preserved": True},
            "required_before_apply": [
                "Resolve source and historical plan inconsistencies through owner decisions",
                "Verify current CMS, canonical origin, parent route, page limits and deployment permissions",
                "Approve a scoped staging draft-write implementation separately",
                "Validate one native template with existing consent and lead routing",
                "Supply dated factual evidence, rights and consultant review for each content page",
                "Verify page-specific indexing, discovery exclusions and crawler access",
                "Validate actual campaign/page/CTA attribution and record release authorization"],
            "pages": pages}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--allocation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        inputs = [args.registry.resolve(), args.allocation.resolve()]
        output = args.output.resolve()
        if output in inputs or (output.exists() and any(output.samefile(path) for path in inputs)):
            raise ValueError("Output must not overwrite either authoritative input")
        manifest = compile_manifest(json.loads(args.registry.read_text(encoding="utf-8")),
                                    json.loads(args.allocation.read_text(encoding="utf-8")))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PLAN_ONLY", "pages": manifest["page_count"],
                          "families": len(manifest["family_counts"]), "apply_supported": False}))
        return 0
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"status": "INVALID", "error_type": type(error).__name__,
                          "detail": str(error) if isinstance(error, ValueError) else "Check the explicit input files and schema"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
