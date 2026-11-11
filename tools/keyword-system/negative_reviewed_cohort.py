"""Explicitly registered AI reviews with common provenance checks; never auto-promote."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import PurePosixPath

import negative_admission as first
from keyword_audit import audit, tokens

CATALOG = ({'key': 'academic-20261111',
    'folder': 'docs/audit/keyword-negative-academic-admission-2026-11-11',
    'review_sha256': '68dae20ec5ef1a3226b52c0f8bff3110b6a4f43890a195d6b1a7ca0b6627c3ea',
    'report_sha256': '7813dd28b0fa8c3ec4996d1cbd1a62d59d5aea298b5c5e1876896b3203d535fb',
    'expected_rows': 903},
    {'key': 'nonproperty-20261111',
     'folder': 'docs/audit/keyword-negative-nonproperty-admission-2026-11-11', 'review_sha256': '9ccc090b096ad6c27c0c163f4cf7dcffa1d19eb1fd6033edd2eb0d8a03144488', 'report_sha256': '74468db413b5dd2badcde2e736495c3c49b4c4aa49e6ba81255477a1a26cd3c7', 'expected_rows': 412},
    {'key': 'vehicle-20261111', 'folder': 'docs/audit/keyword-negative-vehicle-admission-2026-11-11', 'review_sha256': 'cece889ed2775eecb0480157b6ab6e96aff93384e09f9fa19b1eb9db24a0cd0b', 'report_sha256': '3abc58e9dc0f8692dfdd333f389e2b574364089821672d99aacfceccc675a901', 'expected_rows': 1509},
    {'key': 'study-goods-20261111', 'folder': 'docs/audit/keyword-negative-study-goods-admission-2026-11-11', 'review_sha256': 'ce32ec9287f9d88b71fea69fdba1f55cbbebd2bb4f9d22a5c9120b127ae2f268', 'report_sha256': '7860e1f32e5415abb57b8e7ccc6ded762d3bf1655f7d8063daf305c03e850968', 'expected_rows': 259},
    {'key': 'gap-20261111', 'folder': 'docs/audit/keyword-negative-gap-admission-2026-11-11', 'review_sha256': 'a3bb5d2980e195102b60a662216a8d38e9979b8178e307aa37601e3e3711a5b7', 'report_sha256': '0ee7db1b933058306a8c5465fdd3176d80d3279cb4f2e8846798937e09234eb0', 'expected_rows': 1992},)
LIMITS = ('human_review_verified', 'exclusion_approval_granted',
          'live_binding_verified', 'production_authorized')

# Current extensions compose after the verified eligible/held historical split.
# They never join CATALOG or alter reconstruction of the original master.
CURRENT_CATALOG = ({'key': 'role-artifacts-20261111',
    'folder': 'docs/audit/keyword-negative-role-admission-2026-11-11',
    'review_sha256': 'e4572216faf4f02ce9071c733c0552b370794a22d111f818a502c5fb7ff88136', 'report_sha256': '46925157361d2fdfdce041b3c4cd00bc91408a2dcb82bb7e94c1d59ce167d9ab',
    'expected_rows': 849},)


def load_bindings(root, review):
    reports = review['coverage_reports']
    baseline = {'file': first.REPORT, 'sha256': first.PINS[first.REPORT]}
    first.need(type(reports) is list and bool(reports) and baseline in reports and
        all(type(r) is dict and set(r) == {'file', 'sha256'} for r in reports) and
        len({r['file'] for r in reports}) == len(reports), 'REGISTERED_COVERAGE_REPORTS')
    bindings, conflicts = {}, set()
    for reference in reports:
        report = first.pinned(root, reference['file'], reference['sha256'])
        current = report['source_bindings']['review_workbenches_sha256']
        first.need(type(current) is dict, 'REGISTERED_COVERAGE_BINDINGS')
        for relative, digest in current.items():
            first.need(relative not in bindings or bindings[relative] == digest,
                       'REGISTERED_SOURCE_REVIEW_DISAGREEMENT')
            bindings[relative] = digest
        conflicts.update(r['normalized_text'] for r in report['cross_review_overlap_phrases']
                         if r['dispositions_agree'] is not True)
    return bindings, conflicts


def subject(review, context, campaign, bindings):
    return hashlib.sha256(first.canonical({'review': {k: v for k, v in review.items() if k != 'subject_sha256'},
        'service_context': context, 'planned_campaign': campaign,
        'source_pins': first.PINS, 'workbench_bindings': bindings})).hexdigest()


def validate_review(review, entry, context, campaign, bindings):
    first.need(set(entry) == {'key', 'folder', 'review_sha256', 'report_sha256', 'expected_rows'} and
        type(entry['expected_rows']) is int and entry['expected_rows'] > 0, 'REGISTERED_COHORT_SCHEMA')
    required = {'version', 'scope', 'cohort_key', 'reviewer', 'reviewer_kind', 'reviewed_on', 'valid_until',
        'validity_basis', 'campaign_key', 'landing_page_id', 'source_selection', 'capture_pins', 'coverage_reports',
        'pool_rows', 'selected_rows', 'existing_cohort_overlaps', 'held_phrases', 'intent_counts',
        'semantic_rationale', 'variant_review', 'source_identity_limits', 'subject_sha256'} | set(LIMITS)
    first.need(set(review) == required, 'REGISTERED_REVIEW_SCHEMA')
    first.need(type(review['version']) is int and review['version'] == 1 and
        review['cohort_key'] == entry['key'] and review['scope'] ==
        'AI_REVIEWED_PLANNING_RESEARCH_NOT_EXCLUSION_APPROVAL' and review['reviewer'] == first.REVIEWER and
        review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN', 'REGISTERED_REVIEW_AUTHORITY')
    first.need(all(review[k] is False for k in LIMITS), 'REGISTERED_REVIEW_CANNOT_GRANT_AUTHORITY')
    first.need(review['campaign_key'] == campaign['campaign_key'] == first.CAMPAIGN and
        review['landing_page_id'] == campaign['landing_page_id'] == first.PAGE and
        campaign['family_code'] == 'RNT' and campaign['actual_url'] is None and
        campaign['family_slot'] == 1 and campaign['google_campaign_id'] is None and campaign['release_approved'] is False,
        'REGISTERED_PLANNING_SCOPE_CHANGED')
    first.need(context['context_kind'] == 'PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        context['source_url'] == 'https://blackswanrealestate.ae/enquire/rent/' and
        all(context[k] is False for k in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed', 'live_campaign_mapping_assigned')),
        'REGISTERED_SERVICE_CONTEXT_AUTHORITY')
    selections = review['source_selection']
    first.need(type(selections) is dict and bool(selections) and all(p in bindings and
        type(v) is list and bool(v) and len(v) == len(set(v)) and
        all(isinstance(i, str) and i.strip() for i in v) for p, v in selections.items()),
        'REGISTERED_SOURCE_SELECTION')
    intents = {i for values in selections.values() for i in values}
    first.need(set(review['semantic_rationale']) == intents and set(review['intent_counts']) <= intents and
        all(isinstance(v, str) and v.strip() for v in review['semantic_rationale'].values()) and
        isinstance(review['source_identity_limits'], str) and bool(review['source_identity_limits'].strip()),
        'REGISTERED_SEMANTIC_REVIEW_MISSING')
    first.need(type(review['held_phrases']) is dict and
        all(isinstance(k, str) and first.normalize(k) == k and k and isinstance(v, str) and v.strip()
            for k, v in review['held_phrases'].items()) and
        all(type(review[k]) is int and review[k] >= 0 for k in
            ('pool_rows', 'selected_rows', 'existing_cohort_overlaps')) and
        review['selected_rows'] == entry['expected_rows'], 'REGISTERED_SELECTION_COUNTS')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        end-start == timedelta(days=30) and review['validity_basis'] ==
        'LOCAL_30_DAY_REVIEW_DEADLINE_NOT_GOOGLE_EXPIRY_OR_FRESHNESS_GUARANTEE' and
        context['observed_date_dubai'] <= review['reviewed_on'], 'REGISTERED_REVIEW_DATES')
    variants = review['variant_review']
    first.need(set(variants) == {'token_bag_groups', 'phrases_in_groups', 'method',
        'google_equivalence_verified', 'counts_distinct_concepts'} and
        all(type(variants[k]) is int and variants[k] >= 0 for k in ('token_bag_groups', 'phrases_in_groups')) and
        variants['method'] == 'MANUAL_AI_WORDING_REVIEW_NOT_PLATFORM_CERTIFICATE' and
        variants['google_equivalence_verified'] is False and variants['counts_distinct_concepts'] is False,
        'REGISTERED_VARIANT_AUTHORITY')
    first.need(review['subject_sha256'] == subject(review, context, campaign, bindings),
               'REGISTERED_REVIEW_SUBJECT_CHANGED')


def reconstruct(root, entry, prior):
    first.need(any(entry == e for e in CATALOG + CURRENT_CATALOG), 'UNREGISTERED_COHORT')
    review = first.pinned(root, entry['folder']+'/review.json', entry['review_sha256'])
    context = first.pinned(root, first.FOLDER+'/service-context.json', first.CONTEXT_PIN)
    bindings, conflicts = load_bindings(root, review)
    campaign = next(r for r in prior['campaigns'] if r['campaign_key'] == first.CAMPAIGN)
    validate_review(review, entry, context, campaign, bindings)
    pool, primary = {}, {}
    for relative, intents in review['source_selection'].items():
        wb = first.pinned(root, relative, bindings[relative])
        for row in wb['queue']:
            if row['disposition'] != 'NEGATIVE_EXACT_REVIEW' or row['assessment']['intent'] not in intents:
                continue
            key = row['normalized_text']
            first.need(key not in pool, 'REGISTERED_POOL_DUPLICATE')
            pool[key] = row
            ref = row['source_refs'][0]
            source = wb['sources'][ref['batch']]
            primary[key] = (ref['batch'], source['file'], ref['source_line'], source['sha256'])
    # Review workbenches can live separately from their actual export captures.
    capture_paths = {str(PurePosixPath(ref[1]).parent/'capture.json') for ref in primary.values()}
    first.need(type(review['capture_pins']) is dict and set(review['capture_pins']) == capture_paths,
               'REGISTERED_CAPTURE_COVERAGE')
    captures = {p: first.pinned(root, p, digest) for p, digest in review['capture_pins'].items()}
    first.need(all(c['account_id'] == '573-038-4686' for c in captures.values()),
               'REGISTERED_SOURCE_ACCOUNT')
    existing = {r['normalized_text'] for r in prior['records']}
    held = set(review['held_phrases'])
    overlaps = set(pool) & existing
    first.need(len(pool) == review['pool_rows'] and held <= set(pool) and not held & existing and
        len(overlaps) == review['existing_cohort_overlaps'], 'REGISTERED_POOL_OR_HOLDS_CHANGED')
    selected = {k: r for k, r in pool.items() if k not in held and k not in existing}
    first.need(len(selected) == review['selected_rows'] and
        dict(Counter(r['assessment']['intent'] for r in selected.values())) == review['intent_counts'],
        'REGISTERED_SELECTION_CHANGED')
    protected = {r['text'] for r in prior['protected_queries']}
    first.need(not set(selected) & (protected | conflicts), 'REGISTERED_UNRESOLVED_CONFLICT')
    all_protected = set(protected)
    occurrences, cache = defaultdict(list), {}
    for relative, digest in bindings.items():
        wb = first.pinned(root, relative, digest)
        for row in wb['queue']:
            key = row['normalized_text']
            if row['disposition'] != 'NEGATIVE_EXACT_REVIEW':
                all_protected.add(key)
            if key not in selected:
                continue
            first.need(row['disposition'] == 'NEGATIVE_EXACT_REVIEW', 'REGISTERED_PRIOR_HOLD')
            for ref in row['source_refs']:
                source = wb['sources'][ref['batch']]
                if source['file'] not in cache:
                    data = first.pinned(root, source['file'], source['sha256'])
                    cache[source['file']] = {r['source_line']: r['values']['Keyword']
                                            for r in data['source_projection']['records']}
                first.need(first.normalize(cache[source['file']].get(ref['source_line'], '')) == key,
                           'REGISTERED_OCCURRENCE_IDENTITY')
                occurrences[key].append({'batch': ref['batch'], 'source_line': ref['source_line'],
                    'file': source['file'], 'sha256': source['sha256'], 'review_file': relative,
                    'review_sha256': digest})
    first.need(not set(selected) & all_protected, 'REGISTERED_NEW_PROTECTED_CONFLICT')
    records = [first.make_record(row, review, occurrences[key], source_id=primary[key][0],
        source_reference=primary[key][1]+'#'+str(primary[key][2]), review_folder=entry['folder'],
        allowed_intents=set(review['semantic_rationale'])) for key, row in sorted(selected.items())]
    sources = []
    for batch in sorted({r['source_id'] for r in records}):
        key = next(k for k in selected if primary[k][0] == batch)
        capture_path = str(PurePosixPath(primary[key][1]).parent/'capture.json')
        capture = captures[capture_path]
        first.need(capture['account_id'] == '573-038-4686', 'REGISTERED_SOURCE_ACCOUNT')
        first.need(any(r['batch_id'] == batch and r['sha256'] == primary[key][3] and
            r['file'] == PurePosixPath(primary[key][1]).name for r in capture['source_files']),
            'REGISTERED_CAPTURE_SOURCE_MISMATCH')
        sources.append({'source_id': batch, 'kind': 'official_reference', 'approved_for_research': True,
            'evidence_ref': capture_path, 'observed_on': capture['capture_date_dubai'],
            'valid_until': review['valid_until'],
            'research_use_basis': 'OWNER_AUTHORIZED_PLANNER_RESEARCH_AND_VERIFIED_PROVIDER_CAPTURE',
            'served_query_or_current_performance_claimed': False})
    extra_protection = [{'query_id': 'BSRE-Q-'+hashlib.sha256(k.encode()).hexdigest()[:24],
        'text': k, 'campaign_keys': [first.CAMPAIGN], 'services': ['residential_rental'], 'must_serve': True,
        'evidence_ref': entry['folder']+'/review.json#'+('held_phrases' if k in held else 'coverage_reports'),
        'reviewed_on': review['reviewed_on'], 'valid_until': review['valid_until']}
        for k in sorted((held | all_protected)-protected)]
    bags = defaultdict(list)
    for key in selected:
        bags[tuple(sorted(tokens(key)))].append(key)
    groups = [v for v in bags.values() if len(v) > 1]
    first.need(len(groups) == review['variant_review']['token_bag_groups'] and
        sum(map(len, groups)) == review['variant_review']['phrases_in_groups'], 'REGISTERED_VARIANT_COUNTS')
    return {'review': review, 'records': records, 'sources': sources, 'campaigns': prior['campaigns'],
        'campaign_context': prior['campaign_context'],
        'protected_queries': prior['protected_queries']+extra_protection,
        'prior_overlap_phrases': sorted(overlaps), 'prior_protected_holds': sorted(held & protected)}


def summarize(inputs, result):
    return {'scope': 'REGISTERED_AI_REVIEWED_COHORT_NOT_EXCLUSION_APPROVAL',
        **{k: result[k] for k in ('as_of', 'input_rows', 'distinct_nonblank_phrases', 'reviewed_eligible_rows',
        'excluded_rows', 'approved_exclusion_rows', 'structural_pass', 'deployment_export_allowed',
        'production_writes_available', 'positive_library_coverage_verified', 'protected_queries_indexed')},
        'source_occurrences_retained': sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'held_phrases': len(inputs['review']['held_phrases']),
        'prior_protected_holds': len(inputs['prior_protected_holds']),
        'computed_conflicts': len(result['protected_conflicts']),
        'human_review_verified': False, 'live_campaign_mapping_verified': False,
        'subject_sha256': inputs['review']['subject_sha256']}


def _verify_reconstructed(inputs, entry, root=first.ROOT, at=None):
    result = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
        inputs['campaign_context'], inputs['protected_queries'], first.dubai_date() if at is None else at)
    summary = summarize(inputs, result)
    first.need(summary['structural_pass'] and summary['reviewed_eligible_rows'] == entry['expected_rows'] and
        summary['approved_exclusion_rows'] == summary['computed_conflicts'] == 0 and
        not summary['deployment_export_allowed'] and not summary['positive_library_coverage_verified'],
        'REGISTERED_RESEARCH_NOT_ELIGIBLE')
    saved = first.pinned(root, entry['folder']+'/cohort-report.json', entry['report_sha256'])
    first.need(first.canonical(saved) == first.canonical(dict(summary, as_of=inputs['review']['reviewed_on'])),
               'REGISTERED_COHORT_REPORT_CHANGED')
    return dict(summary, passed=True)
