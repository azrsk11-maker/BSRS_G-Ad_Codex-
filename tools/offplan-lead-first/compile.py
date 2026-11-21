"""Offline review compiler. Never connects to WordPress, Google Ads or a mailbox."""
import argparse
import csv
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import unicodedata

OWN = Path(__file__).resolve().parent
INPUTS = ('launch.json', 'copy.json', 'keywords.json', 'policy_sources.json')
MARKETS = {'AE': ('en-AE', 1000), 'DE': ('de-DE', 1001), 'FR': ('fr-FR', 1002), 'TW': ('zh-Hant-TW', 1018)}
ORIGIN = 'https://blackswanrealestate.ae'
FUNNEL = '/enquire/off-plan/'
PAGE_KEYS = {'country_code', 'locale', 'title', 'intro', 'sections', 'cta_label', 'form_step_notice', 'rsa'}


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def finite(value):
    if isinstance(value, float):
        need(math.isfinite(value), 'Nonfinite JSON number')
    elif isinstance(value, dict):
        for item in value.values(): finite(item)
    elif isinstance(value, list):
        for item in value: finite(item)


def load_inputs(folder=OWN):
    data, pins = {}, {}
    for name in INPUTS:
        path = Path(folder) / name
        need(not path.is_symlink(), 'Input symlink')
        raw = path.read_bytes()
        need(len(raw) <= 2 * 1024 * 1024, 'Input byte bound')
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: need(False, 'Nonfinite JSON constant'))
        finite(value)
        data[name], pins[name] = value, pin(raw)
    return data, pins


def units(text):
    """Google double-width accounting; final platform validation remains required."""
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in text)


def single_line(text):
    need(isinstance(text, str) and text and text == text.strip(), 'Empty or padded text')
    need(not any(unicodedata.category(c) in ('Cc', 'Cf') for c in text), 'Control character')
    need(text[0] not in '=+-@', 'Spreadsheet formula prefix')
    return text


def validate(data):
    launch, copy, keywords = (data[n] for n in INPUTS[:3])
    need(launch['account_id'] == '573-038-4686' and launch['site_origin'] == ORIGIN, 'Wrong account/site')
    need(launch['intent'] == 'OFF_PLAN_BUYERS_ONLY' and launch['crm_sync'] is False, 'Wrong business scope')
    need(type(launch['aggregate_average_daily_budget_aed']) is int and launch['aggregate_average_daily_budget_aed'] == 2500, 'Wrong aggregate budget')
    need(launch['daily_enquiry_target'] == 345 and launch['target_is_not_guaranteed'] is True, 'Unapproved target/guarantee')
    need(launch['english_funnel_path'] == FUNNEL, 'Unreviewed enquiry route')
    need(launch['russia_geography_status'] == 'DO_NOT_ACTIVATE_GOOGLE_REGIONAL_RESTRICTION', 'Russia activation')
    need(launch['resale_ad_group_keep_paused'] == '204397706314', 'Resale exclusion lost')
    need(set(launch['non_offplan_campaigns_keep_paused']) == {'24367388382', '24378494092', '24378494098'} and launch['all_other_legacy_campaigns_keep_paused'] is True, 'Non-offplan exclusion lost')
    action = launch['accepted_conversion_policy']
    need(action['action_id'] == '7873290954' and action['optimization'] == 'SECONDARY' and action['count'] == 'ONE' and action['fallback_value_aed'] == 0 and action['duplicate_ga4_import'] is False, 'Accepted-action policy changed')
    markets = launch['markets']
    need(len(markets) == 4 and {m['country_code'] for m in markets} == set(MARKETS), 'Wrong country set')
    need(sum(m['daily_average_budget_aed'] for m in markets) == 2500, 'Budget sum')
    need(len({m['campaign_name'] for m in markets}) == 4, 'Duplicate campaign proposal name')
    slugs = [m['proposed_slug'] for m in markets if m['country_code'] != 'AE']
    need(len(slugs) == len(set(slugs)), 'Duplicate proposed page slug')
    for market in markets:
        country = market['country_code']
        need((market['locale'], market['language_criterion_id']) == MARKETS[country], 'Wrong language criterion')
        need(type(market['daily_average_budget_aed']) is int and market['daily_average_budget_aed'] > 0, 'Invalid country budget')
        need(market['max_cpc_aed'] == 20 and market['positive_bid_adjustments'] == 0 and market['bidding_label'] == 'Maximize clicks', 'Bid policy changed')
        need(market['networks'] == ['GOOGLE_SEARCH'] and all(market[k] is False for k in ['search_partners', 'display_expansion', 'ai_max']), 'Network expansion')
        need(market['location_option'] == 'PRESENCE_OR_REGULARLY_IN', 'Geographic presence expansion')
        need(market['schedule_timezone'] == 'Asia/Dubai' and market['schedule'] == '10:00-19:00 daily', 'Unreviewed contact-hours expansion')
        need(market['initial_status'] == 'PAUSED' and market['live_status_verified'] is False, 'Premature activation claim')
        need(market['geographic_criterion_id'] is None and market['actual_cms_page_id'] is None, 'Invented live geography/CMS binding')
        if country == 'AE':
            need((market['campaign_id'], market['offplan_ad_group_id'], market['ad_id']) == ('24372566774', '204397706154', '828621612892'), 'Wrong retained UAE identities')
            need(market['last_observed_final_url'] == ORIGIN + FUNNEL, 'Wrong retained UAE URL')
        else:
            need(all(market[k] is None for k in ['campaign_id', 'offplan_ad_group_id', 'ad_id', 'last_observed_final_url']), 'Invented new live ID/URL')
            need(re.fullmatch('[a-z0-9]+(?:-[a-z0-9]+)*', market['proposed_slug']) is not None, 'Unsafe proposed slug')
    pages = copy['pages']
    need(len(pages) == 3 and {p['country_code'] for p in pages} == {'DE', 'FR', 'TW'}, 'Wrong localized pages')
    for page in pages:
        need(set(page) == PAGE_KEYS, 'Unexpected customer page fields')
        need(page['locale'] == MARKETS[page['country_code']][0], 'Page language mismatch')
        need(bool(page['form_step_notice']), 'English-form disclosure missing')
        need(len(page['rsa']['headlines']) == 15 and len(page['rsa']['descriptions']) == 4, 'RSA asset counts')
        for key, limit in [('headlines', 30), ('descriptions', 90)]:
            unique = {unicodedata.normalize('NFC', ' '.join(text.split())).casefold() for text in page['rsa'][key]}
            need(len(unique) == len(page['rsa'][key]), 'Duplicate RSA assets')
            for text in page['rsa'][key]:
                single_line(text)
                need(units(text) <= limit, 'RSA weighted length')
    need(keywords['count_as_14000_canonical_admissions'] is False, 'Research admission inflation')
    seen = set()
    for row in keywords['positive_candidates']:
        single_line(row['draft_id'])
        single_line(row['text'])
        country = row['country_code']
        need(country in ('DE', 'FR', 'TW'), 'Keyword country')
        key = country, unicodedata.normalize('NFC', row['text']).casefold()
        need(key not in seen, 'Duplicate localized keyword')
        seen.add(key)
        need(row['match_types'] == ['EXACT', 'PHRASE'], 'Unreviewed match expansion')
        need(row['canonical_keyword_id'] is None and row['google_resource_id'] is None and row['admitted'] is False and row['observed_search_demand'] is None, 'Invented keyword admission/metrics/ID')
    need(len(seen) == 46, 'Unexpected reviewed keyword cohort')
    return launch, pages, keywords


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def csv_bytes(header, rows):
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(header)
    writer.writerows(rows)
    return output.getvalue().encode('utf-8')


def render_page(page):
    esc = html.escape
    out = ['<!-- wp:html -->', '<section class="bsre-offplan-localized" lang="' + esc(page['locale'], quote=True) + '">']
    for paragraph in page['intro']: out.append('<p>' + esc(paragraph) + '</p>')
    for section in page['sections']:
        need(set(section) == {'heading', 'paragraphs', 'bullets'}, 'Unexpected page section fields')
        out.append('<h2>' + esc(section['heading']) + '</h2>')
        for paragraph in section['paragraphs']: out.append('<p>' + esc(paragraph) + '</p>')
        if section['bullets']:
            out.append('<ul>')
            out.extend('<li>' + esc(item) + '</li>' for item in section['bullets'])
            out.append('</ul>')
    out.append('<p class="bsre-form-language-notice">' + esc(page['form_step_notice']) + '</p>')
    out.append('<p><a class="wp-element-button" href="' + FUNNEL + '">' + esc(page['cta_label']) + '</a></p>')
    out.extend(['</section>', '<!-- /wp:html -->', ''])
    return '\n'.join(out).encode('utf-8')


def compile_bundle(data, pins):
    launch, pages, keywords = validate(data)
    outputs, native, ads, keyword_rows = {}, [], [], []
    markets = {m['country_code']: m for m in launch['markets']}
    for page in pages:
        market = markets[page['country_code']]
        name = market['proposed_slug'] + '.html'
        content = render_page(page)
        outputs[name] = content
        native.append({'country_code': page['country_code'], 'locale': page['locale'], 'title': page['title'],
            'proposed_slug': market['proposed_slug'], 'proposed_path': '/' + market['proposed_slug'] + '/',
            'post_type': 'page', 'requested_status': 'draft', 'content_file': name, 'content_pin': pin(content),
            'actual_cms_id': None, 'actual_live_url': None, 'created': False, 'published': False,
            'document_language_hreflang_canonical_noindex_readback': 'PENDING_NATIVE_CMS',
            'form_language': 'EXISTING_ENGLISH_FORM_WITH_LOCALIZED_STEP_NOTICE', 'localized_form_installed': False,
            'form_delivery_and_consent_acceptance': 'PENDING_LIVE_VERIFICATION',
            'planning_360_identity': None, 'planning_note': 'Supplemental country proposal; no canonical registry identity assigned or overwritten.'})
        for kind in ('headlines', 'descriptions'):
            ads.extend([page['country_code'], page['locale'], kind, text, units(text), 'DRAFT_NOT_UPLOADED'] for text in page['rsa'][kind])
    for row in keywords['positive_candidates']:
        for match in row['match_types']:
            keyword_rows.append([row['draft_id'], row['country_code'], MARKETS[row['country_code']][0], row['text'], match, 'AUTHORED_DRAFT_NOT_ADMITTED_OR_UPLOADED'])
    outputs['native-pages.json'] = json_bytes({'schema':'bsre-native-wordpress-country-drafts-v1', 'site_origin':ORIGIN, 'pages':native,
        'publishing_or_import_api':None, 'note':'Use the existing native WordPress editor; this compiler never loads a synthetic writer or WordPress.'})
    outputs['keyword-review.csv'] = csv_bytes(['Draft ID','Country','Locale','Keyword','Proposed match type','State'], keyword_rows)
    outputs['rsa-review.csv'] = csv_bytes(['Country','Locale','Asset type','Text','Weighted units','State'], ads)
    outputs['activation-review.json'] = json_bytes({'schema':'bsre-offplan-activation-review-v1','account_id':launch['account_id'],
        'intent':launch['intent'],'aggregate_average_daily_budget_aed':2500,'daily_enquiry_target':345,
        'target_media_cost_per_enquiry_arithmetic_aed':round(2500/345,2),'performance_forecast':None,
        'ready_for_live_mutation':False,'campaigns':launch['markets'],
        'mandatory_before_enable':['Fresh account/campaign/geo/language/budget readback','Pause resale ad group 204397706314 and keep all non-offplan/legacy campaigns paused',
            'Publish only reviewed native pages after checking route collisions and actual CMS language/SEO bindings',
            'Verify actual enquiry delivery and applicable consent/privacy; optional measurement remains denied until permitted',
            'Verify factual/country eligibility and platform approval; Taiwan applicability is unresolved',
            'Bind actual new campaign/page IDs; re-read serving budget sum before enable'],
        'accepted_action_policy':launch['accepted_conversion_policy'],'negative_proposals_applied':False,
        'qualified_imports_or_CRM_required_for_this_lead_first_launch':False,'live_account_or_site_changes_performed':False})
    outputs['MANIFEST.json'] = json_bytes({'schema':'bsre-offplan-review-bundle-v1','scope':'OFFLINE_DRAFTS_NOT_LIVE_ACCEPTANCE',
        'inputs':pins,'outputs':{name:pin(raw) for name,raw in sorted(outputs.items())},
        'counts':{'localized_pages':3,'distinct_authored_keyword_strings':46,'proposed_match_placements':len(keyword_rows),
                  'localized_RSA_assets':len(ads),'new_live_campaigns':0,'published_pages':0},
        'production_ads_mail_or_sheet_writes':0,'full_14000_library_admissions_added':0})
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--write', action='store_true')
    group.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    data, pins = load_inputs()
    outputs = compile_bundle(data, pins)
    target = OWN / 'generated'
    need(not target.is_symlink(), 'Output directory symlink')
    if args.write: target.mkdir(exist_ok=True)
    need(target.is_dir(), 'Generated output missing')
    need({p.name for p in target.iterdir()} <= set(outputs), 'Unexpected output member')
    for name, raw in outputs.items():
        path = target / name
        need(not path.is_symlink(), 'Output member symlink')
        if args.write: path.write_bytes(raw)
        else: need(path.is_file() and path.read_bytes() == raw, 'Generated output drift: ' + name)
    print(json.dumps({'status':'WROTE_OFFLINE_DRAFTS' if args.write else 'VERIFIED_OFFLINE_DRAFTS',
        'files':len(outputs),'localized_pages':3,'keyword_strings':46,'match_placements':92,'RSA_assets':57,
        'live_or_production_mutations':0}))


if __name__ == '__main__': main()
