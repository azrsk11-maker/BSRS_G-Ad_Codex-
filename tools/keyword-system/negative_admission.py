"""Read-only, fixed-cohort research admission. No approval, live binding or exporter.

Protected inputs are derived in memory from pinned reviews instead of duplicating
their phrase inventories. All reviewer/source authenticity remains inspectable
evidence, not something a checksum or this validator can authenticate.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path, PurePosixPath

from keyword_audit import audit, normalize, parse_json_bytes, tokens
from supplemental_triage import dubai_date

ROOT = Path(__file__).resolve().parents[2]
FOLDER = 'docs/audit/keyword-negative-admission-2026-11-11'
COHORT = 'docs/audit/keyword-employment-lifecycle-2026-11-11'
REPORT = 'docs/audit/keyword-review-coverage-2026-11-11/report.json'
REGISTRY = 'docs/google-ads/planned_campaign_page_registry.json'
CASES = 'docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
MASTER = 'docs/google-ads/BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md'
CAMPAIGN = 'BSRE-C0301'
PAGE = 'BSRE-LP0301'
REVIEWER = 'Codex AI semantic review; independent human review pending'
INTENTS = {'EXPLICIT_INTERNSHIP_RESEARCH', 'EXPLICIT_EMPLOYMENT_APPLICATION_RESEARCH',
           'EXPLICIT_SALARY_OR_WAGE_RESEARCH', 'EXPLICIT_APPLICATION_DOCUMENT_RESEARCH'}
PINS = {
    MASTER: '8b0f7eafc4572c6ba7421b891285e9a324e96d53ca2507b58ef6d0e540efd7a4',
    REGISTRY: '4cb1101bd54e687674938a368a73e6eacd3cee5a4743d2046f2d8bc6abef7b65',
    REPORT: 'a17b8e8cb1ca777379d6cf099ddcf04cccffe4fb91126c960c7c1529ec4b1d99',
    CASES: 'ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43',
    COHORT+'/capture.json': '94dfa8a6fe28a0ed76b865a5a230c4404a5bc8c25ecfa0cd9fae6f6311fa78c1',
    COHORT+'/employment-lifecycle.json': 'ff63d459628f60eb7bf3b64b7ee881d57e7f8abacb734c15d7f7e597b5a12b7e',
    COHORT+'/workbench.json': 'd55c2ba4f03fe8f91cc49477f938cd0eae0ac638b1667709de422ab540404449',
    COHORT+'/proposals.json': '3df02838ac668271034bfb6e84907884c27193234733cb2b4c622670ed73cd59',
}
REVIEW_PIN = '64be0f3cf6b4345f73a83af9f91eb56445b9bfa31b81b1990b009c39739e8e40'
CONTEXT_PIN = '48915be7de329a10475ffcb8bc24dd8eb89f19f1b94d80f2f4bf1ccfe2341f17'
OUTPUT_PINS = {'data/negative.json': '57405055be2db88f3b982436348a7e01517af573f5d6cf77667554e81217401a', 'data/sources.json': 'b7c79d8fc2faa549540c0aaaab940a6008dd0a57e474b8215c0c879c78515c15', 'data/campaign_context.json': 'b32986087b40a11c32c0a9a7e08d8bf123e4b89115056525ff264df3a590df97', 'admission-report.json': 'da48963260945b2e97a6ed3870ed044b24819c10360604073dfa8b87ae220c99'}  # Filled from the actual reviewed source artifacts, never fixtures.


def need(condition, code):
    if not condition:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def pinned(root, relative, digest):
    part = PurePosixPath(relative)
    need(bool(part.parts) and part.parts[0] in {'docs', 'tools'} and not part.is_absolute() and
         '..' not in part.parts and '.git' not in part.parts and '\\' not in relative and
         ':' not in relative and '\x00' not in relative,
         'PUBLIC_PATH_INVALID')
    root = Path(root).resolve()
    path = root/relative
    cursor = path
    while cursor != root:
        need(not cursor.is_symlink() and not (hasattr(cursor, 'is_junction') and cursor.is_junction()),
             'PUBLIC_PATH_LINKED')
        cursor = cursor.parent
    need(path.is_file(), 'PUBLIC_INPUT_MISSING')
    with path.open('rb') as stream:
        raw = stream.read(32*1024*1024+1)
    need(len(raw) <= 32*1024*1024 and hashlib.sha256(raw).hexdigest() == digest,
         'PINNED_INPUT_CHANGED')
    return parse_json_bytes(raw) if relative.endswith('.json') else raw


def subject(review, context, campaign):
    payload = {k: v for k, v in review.items() if k != 'subject_sha256'}
    return hashlib.sha256(canonical({'review': payload, 'service_context': context,
                                    'planned_campaign': campaign, 'source_pins': PINS})).hexdigest()


def validate_review(review, context, campaign):
    need(set(review) == {'version', 'scope', 'reviewer', 'reviewer_kind', 'reviewed_on', 'valid_until',
         'validity_basis', 'campaign_key', 'landing_page_id', 'selected_intents', 'selected_rows',
         'source_kind', 'human_review_verified', 'exclusion_approval_granted', 'live_binding_verified',
         'production_authorized', 'semantic_rationale', 'variant_review', 'subject_sha256'}, 'REVIEW_SCHEMA')
    need(review['version'] == 1 and type(review['version']) is int and
         review['scope'] == 'AI_REVIEWED_PLANNING_RESEARCH_NOT_EXCLUSION_APPROVAL' and
         review['reviewer'] == REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN', 'REVIEW_AUTHORITY')
    need(all(review[key] is False for key in ('human_review_verified', 'exclusion_approval_granted',
         'live_binding_verified', 'production_authorized')), 'REVIEW_CANNOT_GRANT_AUTHORITY')
    need(review['campaign_key'] == CAMPAIGN and review['landing_page_id'] == PAGE and
         campaign['campaign_key'] == CAMPAIGN and campaign['landing_page_id'] == PAGE and
         campaign['family_code'] == 'RNT' and campaign['family_slot'] == 1 and
         campaign['actual_url'] is None and campaign['google_campaign_id'] is None and
         campaign['release_approved'] is False, 'PLANNING_SCOPE_CHANGED')
    need(set(review['selected_intents']) == INTENTS and len(review['selected_intents']) == 4 and
         type(review['selected_rows']) is int and review['selected_rows'] == 1178 and
         review['source_kind'] == 'official_reference', 'COHORT_REVIEW_CHANGED')
    need(set(review['semantic_rationale']) == INTENTS and all(isinstance(value, str) and value.strip()
         for value in review['semantic_rationale'].values()), 'SEMANTIC_REVIEW_MISSING')
    variants = review['variant_review']
    need(set(variants) == {'token_bag_groups', 'phrases_in_groups', 'method', 'google_equivalence_verified',
         'counts_distinct_concepts'} and type(variants['token_bag_groups']) is int and
         variants['token_bag_groups'] == 65 and type(variants['phrases_in_groups']) is int and
         variants['phrases_in_groups'] == 137 and variants['method'] == 'MANUAL_AI_WORDING_REVIEW_NOT_PLATFORM_CERTIFICATE' and
         variants['google_equivalence_verified'] is False and variants['counts_distinct_concepts'] is False,
         'VARIANT_REVIEW_AUTHORITY')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
         end-start == timedelta(days=30) and review['validity_basis'] ==
         'LOCAL_30_DAY_REVIEW_DEADLINE_NOT_GOOGLE_EXPIRY_OR_FRESHNESS_GUARANTEE', 'REVIEW_DATES')
    need(set(context) == {'version', 'context_kind', 'observed_date_dubai', 'source_url', 'heading_seen',
         'tenant_form_seen', 'annual_budget_field_seen', 'inventory_or_availability_verified',
         'submission_or_consent_action_performed', 'live_campaign_mapping_assigned', 'observed_purpose',
         'limits', 'private_evidence_sha256'} and type(context['version']) is int and context['version'] == 1,
         'SERVICE_CONTEXT_SCHEMA')
    need(context['source_url'] == 'https://blackswanrealestate.ae/enquire/rent/' and
         context['observed_date_dubai'] == review['reviewed_on'] and
         context['context_kind'] == 'PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
         all(context[key] is True for key in ('heading_seen', 'tenant_form_seen', 'annual_budget_field_seen')) and
         all(context[key] is False for key in ('inventory_or_availability_verified',
             'submission_or_consent_action_performed', 'live_campaign_mapping_assigned')), 'SERVICE_CONTEXT')
    need(review['subject_sha256'] == subject(review, context, campaign), 'REVIEW_SUBJECT_CHANGED')


def make_record(row, review, occurrences):
    key = row['normalized_text']
    need(row['disposition'] == 'NEGATIVE_EXACT_REVIEW' and row['assessment']['intent'] in INTENTS and
         len(row['original_forms']) == 1 and normalize(row['original_forms'][0]) == key,
         'UNREVIEWED_OR_HELD_PHRASE')
    need(canonical(row['assessment']['negative_scope_proposal']) == canonical(
         {'type': 'CAMPAIGN', 'campaign_keys': [], 'approved': False, 'match_type': 'EXACT'}),
         'PRELIMINARY_PROPOSAL_AUTHORITY_CHANGED')
    identity = 'BSRE-N-'+hashlib.sha256(key.encode()).hexdigest()[:24]
    return {'keyword_id': identity, 'negative_id': identity, 'original_text': row['original_forms'][0],
        'normalized_text': key, 'language': 'en', 'match_type': 'EXACT',
        'source_id': 'KP-20261111-EMPLOYMENT-LIFECYCLE', 'source_type': 'official_reference',
        'source_reference': COHORT+'/employment-lifecycle.json#'+str(row['source_refs'][0]['source_line']),
        'evidence_ref': FOLDER+'/review.json#'+identity, 'review_state': 'REVIEWED',
        'reviewer': review['reviewer'], 'reviewed_on': review['reviewed_on'], 'valid_until': review['valid_until'],
        'volume': None, 'cpc': None, 'observed_query': None, 'observation_date': None,
        'reason_code': row['assessment']['intent'], 'service_applicability': ['residential_rental'],
        'eligible_campaigns': [CAMPAIGN], 'ineligible_campaigns': [], 'scope_type': 'CAMPAIGN',
        'scope_target': {'campaign_key': CAMPAIGN}, 'risk_level': 'HIGH', 'protected_query_conflicts': [],
        'estimated_lost_coverage': None, 'approval_state': 'PENDING', 'approval_reference': None,
        'approval_reviewer': None, 'approved_on': None, 'deployed_resource_ids': [], 'deployed_at': None,
        'rollback_reference': None, 'scope_basis': 'PLANNED_RENTAL_PURPOSE_ONLY_NOT_LIVE_CAMPAIGN_BINDING',
        'provenance_occurrences': occurrences}


def reconstruct(root=ROOT):
    review = pinned(root, FOLDER+'/review.json', REVIEW_PIN)
    context = pinned(root, FOLDER+'/service-context.json', CONTEXT_PIN)
    registry = pinned(root, REGISTRY, PINS[REGISTRY])
    campaign = next(row for row in registry if row['campaign_key'] == CAMPAIGN)
    validate_review(review, context, campaign)
    pinned(root, MASTER, PINS[MASTER])
    pinned(root, COHORT+'/capture.json', PINS[COHORT+'/capture.json'])
    pinned(root, COHORT+'/proposals.json', PINS[COHORT+'/proposals.json'])
    cohort = pinned(root, COHORT+'/employment-lifecycle.json', PINS[COHORT+'/employment-lifecycle.json'])
    workbench = pinned(root, COHORT+'/workbench.json', PINS[COHORT+'/workbench.json'])
    coverage = pinned(root, REPORT, PINS[REPORT])
    cases = pinned(root, CASES, PINS[CASES])
    selected = {row['normalized_text']: row for row in workbench['queue']
                if row['disposition'] == 'NEGATIVE_EXACT_REVIEW'}
    need(len(selected) == review['selected_rows'] and workbench['summary']['source_occurrences'] == 1686,
         'COHORT_CARDINALITY')
    conflicted = {row['normalized_text'] for row in coverage['cross_review_overlap_phrases']
                  if row['dispositions_agree'] is not True}
    need(not set(selected) & conflicted, 'UNRESOLVED_CROSS_REVIEW_CONFLICT')
    protected, occurrences, source_cache = set(), defaultdict(list), {}
    for relative, digest in coverage['source_bindings']['review_workbenches_sha256'].items():
        old = pinned(root, relative, digest)
        for row in old['queue']:
            key = row['normalized_text']
            if row['disposition'] != 'NEGATIVE_EXACT_REVIEW':
                protected.add(key)
            if key not in selected:
                continue
            need(row['disposition'] == 'NEGATIVE_EXACT_REVIEW', 'PRIOR_HOLD_NOT_RESOLVED')
            for ref in row['source_refs']:
                source = old['sources'][ref['batch']]
                if source['file'] not in source_cache:
                    data = pinned(root, source['file'], source['sha256'])
                    source_cache[source['file']] = {r['source_line']: r['values']['Keyword']
                                                   for r in data['source_projection']['records']}
                actual = source_cache[source['file']].get(ref['source_line'])
                need(actual is not None and normalize(actual) == key, 'OCCURRENCE_IDENTITY')
                occurrences[key].append({'batch': ref['batch'], 'source_line': ref['source_line'],
                    'file': source['file'], 'sha256': source['sha256'], 'review_file': relative,
                    'review_sha256': digest})
    need(cases['counts_toward_research_or_masters'] is False and len(cases['cases']) == 20, 'AUTHORED_CASE_AUTHORITY')
    protected.update(normalize(row['query']) for row in cases['cases'])
    need(len(protected) == 12081 and not set(selected) & protected, 'PROTECTED_COHORT_CONFLICT')
    records = [make_record(row, review, occurrences[key]) for key, row in sorted(selected.items())]
    need(sum(len(row['provenance_occurrences']) for row in records) == 1182, 'SOURCE_OCCURRENCES_LOST')
    sources = [{'source_id': cohort['batch_id'], 'kind': 'official_reference', 'approved_for_research': True,
        'evidence_ref': COHORT+'/capture.json', 'observed_on': '2026-11-11', 'valid_until': review['valid_until'],
        'research_use_basis': 'OWNER_AUTHORIZED_PLANNER_RESEARCH_AND_VERIFIED_PROVIDER_CAPTURE',
        'served_query_or_current_performance_claimed': False}]
    contexts = [{'campaign_key': CAMPAIGN, 'services': ['residential_rental'],
        'evidence_ref': FOLDER+'/service-context.json', 'reviewed_on': review['reviewed_on'],
        'valid_until': review['valid_until'], 'scope_kind': 'PLANNING_PURPOSE_ONLY',
        'live_resource_mapping_claimed': False}]
    protection = [{'query_id': 'BSRE-Q-'+hashlib.sha256(text.encode()).hexdigest()[:24], 'text': text,
        'campaign_keys': [CAMPAIGN], 'services': ['residential_rental'], 'must_serve': True,
        'evidence_ref': REPORT+'#provisional_exact_screen', 'reviewed_on': review['reviewed_on'],
        'valid_until': review['valid_until']} for text in sorted(protected)]
    need(len({r['query_id'] for r in protection}) == len(protection), 'PROTECTION_ID_COLLISION')
    return {'review': review, 'records': records, 'sources': sources, 'campaigns': registry,
            'campaign_context': contexts, 'protected_queries': protection}


def summarize(inputs, report):
    bags = defaultdict(list)
    for row in inputs['records']:
        bags[tuple(sorted(tokens(row['normalized_text'])))].append(row['keyword_id'])
    groups = [ids for ids in bags.values() if len(ids) > 1]
    return {'scope': 'AI_REVIEWED_PLANNING_NEGATIVE_RESEARCH_NOT_APPROVAL',
        **{key: report[key] for key in ('as_of', 'input_rows', 'distinct_nonblank_phrases',
          'reviewed_eligible_rows', 'excluded_rows', 'approved_exclusion_rows', 'target', 'deficit',
          'exact_target_pass', 'structural_pass', 'deployment_export_allowed', 'production_writes_available',
          'positive_library_coverage_verified', 'protected_corpus_status', 'protected_queries_indexed')},
        'computed_conflicts': len(report['protected_conflicts']),
        'approval_hold_counts': dict(Counter(reason for row in report['records'] for reason in row['deployment_holds'])),
        'subject_sha256': inputs['review']['subject_sha256'], 'proposed_campaign_key': CAMPAIGN,
        'live_campaign_mapping_verified': False, 'human_review_verified': False,
        'authored_cases_outside_research_counts': 20, 'source_occurrences_retained': 1182,
        'token_bag_groups': len(groups), 'phrases_in_token_bag_groups': sum(map(len, groups)),
        'token_bag_is_semantic_or_google_equivalence_oracle': False}


def verify(root=ROOT, at=None):
    inputs = reconstruct(root)
    for relative, expected in (('data/negative.json', inputs['records']),
            ('data/sources.json', inputs['sources']), ('data/campaign_context.json', inputs['campaign_context'])):
        actual = pinned(root, 'tools/keyword-system/'+relative, OUTPUT_PINS[relative])
        need(canonical(actual) == canonical(expected), 'RESEARCH_RECORDS_DIFFER_FROM_REVIEW')
    when = dubai_date() if at is None else at
    report = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
                   inputs['campaign_context'], inputs['protected_queries'], when)
    summary = summarize(inputs, report)
    need(summary['structural_pass'] and summary['reviewed_eligible_rows'] == 1178 and
         summary['approved_exclusion_rows'] == 0 and not summary['exact_target_pass'] and
         not summary['computed_conflicts'] and not summary['deployment_export_allowed'] and
         not summary['positive_library_coverage_verified'], 'RESEARCH_NOT_ELIGIBLE_OR_AUTHORITY_CHANGED')
    saved = pinned(root, FOLDER+'/admission-report.json', OUTPUT_PINS['admission-report.json'])
    historical = dict(summary, as_of=inputs['review']['reviewed_on'])
    need(canonical(saved) == canonical(historical), 'ADMISSION_REPORT_CHANGED')
    return dict(summary, passed=True)


if __name__ == '__main__':
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'RESEARCH_ADMISSION_HELD',
                          'deployment_export_allowed': False, 'production_writes_available': False}))
        raise SystemExit(1)
