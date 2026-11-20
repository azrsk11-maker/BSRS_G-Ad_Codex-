#!/usr/bin/env python3
"""Validate the BSRE planning specification, not live campaigns or keyword quality.

Usage: python validate_planning_package.py [package_directory]
Requires Python 3.10+ and the standard library only.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from collections import Counter
from typing import Any


def load(root: Path, filename: str) -> Any:
    path = root / filename
    with path.open(encoding='utf-8') as handle:
        return json.load(handle)


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    def check(name: str, condition: bool, observed: Any) -> None:
        checks.append({'check': name, 'passed': bool(condition), 'observed': observed})
        if not condition:
            errors.append(name)

    config = load(root, 'company_config.json')
    pairs = load(root, 'planned_campaign_page_registry.json')
    signals = load(root, 'positive_intent_taxonomy.json')
    allocations = load(root, 'page_family_allocation.json')['families']
    negatives = load(root, 'negative_research_plan.json')
    master = (root / 'BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md').read_text(encoding='utf-8')

    check('360 planned pairs', len(pairs) == 360, len(pairs))
    for field in ['campaign_key', 'landing_page_id', 'proposed_path']:
        distinct = len({x[field] for x in pairs})
        check(f'Unique {field}', distinct == 360, distinct)
    check('No fabricated live IDs or actual URLs', all(x['google_campaign_id'] is None and x['actual_url'] is None for x in pairs), 'All unknown')
    check('Every pair held and unapproved', all(x['status'] == 'PLANNED_SOURCE_REQUIRED' and not x['budget_approved'] and not x['release_approved'] for x in pairs), 'Held')
    check('All proposed routes in /lp/', all(re.fullmatch(r'/lp/bsre-c\d{4}/', x['proposed_path']) for x in pairs), 'Route pattern only')
    family_counts = Counter(x['family_code'] for x in pairs)
    check('Family counts reconcile', all(family_counts[x['code']] == x['pages'] for x in allocations), dict(family_counts))
    check('360 allocated page slots', sum(x['pages'] for x in allocations) == 360, sum(x['pages'] for x in allocations))
    check('14,000 positive research target', sum(x['positive_research_target'] for x in allocations) == 14000, sum(x['positive_research_target'] for x in allocations))
    check('14,000 negative research target', sum(x['research_target'] for x in negatives['pools']) == 14000, sum(x['research_target'] for x in negatives['pools']))
    check('70 intent signals', len(signals) == 70 and len({x['signal_id'] for x in signals}) == 70, len(signals))
    check('Seven property destinations', len(config['scope']['property_destinations']) == 7, config['scope']['property_destinations'])
    check('No CRM/Zoho writes', config['integrations']['crm_sync'] is False and config['integrations']['zoho_writes'] is False, 'Disabled')
    check('Required lead email', config['integrations']['primary_lead_email'] == 'marketing@blackswanrealestate.ae', config['integrations']['primary_lead_email'])
    check('Required lead subject', config['integrations']['email_subject'] == 'G-Ad | [Campaign] | [Lead Name] | [Lead ID]', config['integrations']['email_subject'])
    check('Production approvals false', all(config['approvals'][k] is False for k in ['production_writes','website_publication','ad_activation','audience_upload']), 'Unapproved')
    check('Real Estate budget not invented', config['approvals']['monthly_budget_aed'] is None and config['approvals']['daily_average_budget_aed'] is None, 'Unknown')
    lp = config['landing_pages']
    check('Unlisted but accessible', lp['noindex'] and lp['crawler_access'] and not lp['password_required'] and not lp['require_gclid_to_open'], 'Noindex is not access control')
    check('URL expansion disabled', lp['final_url_expansion'] is False, False)
    check('10800 research cells only', config['targets']['concept_evaluation_cells'] == 360 * 30, 10800)
    check('Explicit keyword-library noncompletion', 'actual 28,000 researched keyword records' in (root/'README.md').read_text(encoding='utf-8'), 'Disclosed')
    check('Markdown fences balanced', master.count('```') % 2 == 0, master.count('```'))
    check('No empty writing-block placeholders', ':::writing' not in master, 'None')
    h2 = re.findall(r'^## (\d+)\.', master, flags=re.M)
    check('24 numbered master sections', h2 == [str(i) for i in range(1,25)], h2)

    website = config['website']
    tracking = load(root, 'website_tracking_contract.json')
    tests = load(root, 'website_tracking_acceptance_tests.json')
    check('Native main-site pages required', website['existing_main_website_required'] and website['same_cms_or_application_required'] and config['landing_pages']['native_main_site_pages_required'], True)
    check('No independent landing sites', not website['new_independent_landing_sites_allowed'] and not website['external_page_iframes_allowed'] and not config['landing_pages']['standalone_site_deployments_allowed'], 'Forbidden')
    check('360 native page bindings remain unknown', all(x['website_scope'] == 'EXISTING_MAIN_SITE_NATIVE_PAGE' and x['cms_content_or_native_route_id'] is None for x in pairs), len(pairs))
    check('Real tracking IDs not invented', all(v is None or v == {} for v in tracking['verified_ids'].values()), 'Unknown')
    check('No new GA4 property per campaign', tracking['installation']['new_tracking_property_per_campaign'] is False, False)
    check('Public-site attribution continuity required', tracking['attribution']['cover_public_site_forms'] and tracking['attribution']['rehydrate_context_each_page'] and not tracking['attribution']['internal_utm_retagging'], True)
    check('Enquiry not gated by consent or click ID', tracking['attribution']['consent_or_click_id_required_to_enquire'] is False, False)
    check('Privacy and deduplication rules present', not tracking['privacy']['pii_in_ga4_or_urls'] and tracking['deduplication']['server_acceptance_before_lead_event'] and tracking['deduplication']['one_ads_route_per_business_event'], True)
    check('23 canonical event mappings', len(tracking['events']) == 23 and len({x['operational_event'] for x in tracking['events']}) == 23, len(tracking['events']))
    check('32 live test designs not executed', len(tests['tests']) == 32 and all(x['status'] == 'NOT_EXECUTED' for x in tests['tests']), len(tests['tests']))
    check('No live tracking verified claim', tracking['live_verified'] is False and all(x['tracking_status'] == 'NOT_IMPLEMENTED_NOT_TESTED' for x in pairs), False)

    headlines = ['Compare UAE Property Options','Buy, Rent, Sell Or Lease','Know The Full Property Cost','Find Ready-To-Move Homes','Commercial Space That Fits','Compare Off-Plan Payments','Request A Property Shortlist']
    descriptions = ['Compare suitable UAE properties by budget, timing and intended use. Request a shortlist.','Understand price, fees and payment terms before arranging your next property viewing.']
    check('Illustrative headlines <= 30 characters', all(len(s) <= 30 for s in headlines), [len(s) for s in headlines])
    check('Illustrative descriptions <= 90 characters', all(len(s) <= 90 for s in descriptions), [len(s) for s in descriptions])
    return {'status': 'PASS' if not errors else 'FAIL', 'scope': 'PLANNING_PACKAGE_ONLY_NOT_LIVE_RELEASE', 'checks': checks, 'errors': errors, 'actual_completed_positive_keyword_master_rows': 0, 'actual_completed_negative_keyword_master_rows': 0, 'live_campaigns_created': 0, 'live_pages_created': 0}


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
    try:
        report = validate(root)
        (root/'planning_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f'Cannot validate planning package: {exc}', file=sys.stderr)
        return 2
    print(json.dumps({'status':report['status'], 'checks':len(report['checks']), 'errors':report['errors'], 'scope':report['scope']}, indent=2))
    return 0 if report['status'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
