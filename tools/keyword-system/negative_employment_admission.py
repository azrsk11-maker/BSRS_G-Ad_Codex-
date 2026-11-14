"""Second actual employment review; read-only research, never exclusion approval."""
from collections import defaultdict
from datetime import date, timedelta
import hashlib
import json
from pathlib import PurePosixPath

import negative_admission as first
from keyword_audit import audit

FOLDER = 'docs/audit/keyword-negative-employment-admission-2026-11-11'
SELECTIONS = {
    'docs/audit/keyword-employment-broad-2026-11-10/workbench.json': 'EXPLICIT_EMPLOYMENT_RESEARCH',
    'docs/audit/keyword-developer-employment-2026-11-11/workbench.json': 'EXPLICIT_EMPLOYMENT_RESEARCH',
    'docs/audit/keyword-employment-education-2026-11-10/workbench.json': 'EXPLICIT_EMPLOYMENT_APPLICATION',
}
HELD = {
    'deyar real estate careers': 'Possible spelling variant of a separately captured phrase; unresolved, not a new research count.',
    'realestate job': 'Unspaced spelling variant; retain source, do not add a research row.',
    'realestate photography jobs': 'Unspaced spelling variant; retain source, do not add a research row.',
    'sothebys realty careers': 'Unresolved punctuation/spelling variant of a separately captured phrase; not a new count.',
    'sothebys realty jobs': 'Unresolved punctuation/spelling variant of a separately captured phrase; not a new count.',
}
REVIEW_PIN = 'b8453933eabf5fbaf75fd9b8624a8c5d41dc2ceca11cd6ec32192b0c558abcd6'
REPORT_PIN = '6940c88960de1b7193fb9aa7df1c536041d73f0505e5212bb4552c424dca4709'
CAPTURE_PINS = {'docs/audit/keyword-employment-broad-2026-11-10/capture.json': 'bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864', 'docs/audit/keyword-developer-employment-2026-11-11/capture.json': 'a89397314f9565d5f2e0027c8d19a7b6b55b9f738f1c5272f275d2716ecdc06f', 'docs/audit/keyword-employment-education-2026-11-10/capture.json': '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f'}  # Actual pre-existing capture receipts, finalized before admission.


def subject(review, context, campaign, bindings):
    return hashlib.sha256(first.canonical({'review': {k: v for k, v in review.items() if k != 'subject_sha256'},
        'service_context': context, 'planned_campaign': campaign, 'source_pins': first.PINS,
        'workbench_bindings': bindings, 'capture_pins': CAPTURE_PINS})).hexdigest()


def validate_review(review, context, campaign, bindings):
    first.need(set(review) == {'version', 'scope', 'reviewer', 'reviewer_kind', 'reviewed_on', 'valid_until',
        'validity_basis', 'campaign_key', 'landing_page_id', 'source_selections', 'pool_rows', 'selected_rows',
        'existing_cohort_overlaps', 'held_phrases', 'human_review_verified', 'exclusion_approval_granted',
        'live_binding_verified', 'production_authorized', 'semantic_rationale', 'variant_review',
        'source_identity_limits', 'subject_sha256'}, 'EMPLOYMENT_REVIEW_SCHEMA')
    first.need(type(review['version']) is int and review['version'] == 1 and
        review['scope'] == 'AI_REVIEWED_PLANNING_RESEARCH_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN',
        'EMPLOYMENT_REVIEW_AUTHORITY')
    first.need(all(review[k] is False for k in ('human_review_verified', 'exclusion_approval_granted',
        'live_binding_verified', 'production_authorized')), 'EMPLOYMENT_CANNOT_GRANT_AUTHORITY')
    first.need(review['campaign_key'] == campaign['campaign_key'] == first.CAMPAIGN and
        review['landing_page_id'] == campaign['landing_page_id'] == first.PAGE and
        campaign['actual_url'] is None and campaign['google_campaign_id'] is None and
        campaign['release_approved'] is False, 'EMPLOYMENT_PLANNING_SCOPE_CHANGED')
    first.need(review['source_selections'] == SELECTIONS and review['held_phrases'] == HELD and
        all(type(review[k]) is int and review[k] == v for k, v in
        (('pool_rows', 944), ('selected_rows', 935), ('existing_cohort_overlaps', 4))),
        'EMPLOYMENT_SELECTION_CHANGED')
    first.need(set(review['semantic_rationale']) == set(SELECTIONS.values()) and
        all(isinstance(v, str) and v.strip() for v in review['semantic_rationale'].values()) and
        isinstance(review['source_identity_limits'], str) and review['source_identity_limits'].strip(),
        'EMPLOYMENT_SEMANTIC_REVIEW_MISSING')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        end-start == timedelta(days=30) and review['validity_basis'] ==
        'LOCAL_30_DAY_REVIEW_DEADLINE_NOT_GOOGLE_EXPIRY_OR_FRESHNESS_GUARANTEE' and
        context['observed_date_dubai'] == review['reviewed_on'], 'EMPLOYMENT_REVIEW_DATES')
    variants = review['variant_review']
    first.need(set(variants) == {'token_bag_groups', 'phrases_in_groups', 'method',
        'google_equivalence_verified', 'counts_distinct_concepts'} and
        type(variants['token_bag_groups']) is int and variants['token_bag_groups'] == 25 and
        type(variants['phrases_in_groups']) is int and variants['phrases_in_groups'] == 50 and
        variants['method'] == 'MANUAL_AI_WORDING_REVIEW_NOT_PLATFORM_CERTIFICATE' and
        variants['google_equivalence_verified'] is False and variants['counts_distinct_concepts'] is False,
        'EMPLOYMENT_VARIANT_AUTHORITY')
    first.need(review['subject_sha256'] == subject(review, context, campaign, bindings),
        'EMPLOYMENT_REVIEW_SUBJECT_CHANGED')


def reconstruct(root=first.ROOT, prior=None):
    prior = first.reconstruct(root) if prior is None else prior
    review = first.pinned(root, FOLDER+'/review.json', REVIEW_PIN)
    context = first.pinned(root, first.FOLDER+'/service-context.json', first.CONTEXT_PIN)
    campaign = next(r for r in prior['campaigns'] if r['campaign_key'] == first.CAMPAIGN)
    coverage = first.pinned(root, first.REPORT, first.PINS[first.REPORT])
    bindings = coverage['source_bindings']['review_workbenches_sha256']
    validate_review(review, context, campaign, bindings)
    expected_captures = {str(PurePosixPath(p).parent/'capture.json') for p in SELECTIONS}
    first.need(set(CAPTURE_PINS) == expected_captures, 'EMPLOYMENT_CAPTURE_COVERAGE')
    captures = {p: first.pinned(root, p, digest) for p, digest in CAPTURE_PINS.items()}
    selected, primary, originals = {}, {}, {}
    for relative, intent in SELECTIONS.items():
        wb = first.pinned(root, relative, bindings[relative])
        for row in wb['queue']:
            if row['disposition'] != 'NEGATIVE_EXACT_REVIEW' or row['assessment']['intent'] != intent:
                continue
            key = row['normalized_text']
            first.need(key not in selected, 'EMPLOYMENT_SELECTION_DUPLICATE')
            selected[key] = row
            ref = row['source_refs'][0]
            primary[key] = (ref['batch'], wb['sources'][ref['batch']]['file'], ref['source_line'])
            originals[key] = relative
    existing = {r['normalized_text'] for r in prior['records']}
    overlaps = set(selected) & existing
    first.need(len(selected) == 944 and len(overlaps) == 4 and set(HELD) <= set(selected) and
        not set(HELD) & overlaps, 'EMPLOYMENT_POOL_CHANGED')
    selected = {k: r for k, r in selected.items() if k not in overlaps and k not in HELD}
    first.need(len(selected) == 935, 'EMPLOYMENT_COHORT_CARDINALITY')
    conflicts = {r['normalized_text'] for r in coverage['cross_review_overlap_phrases']
                 if r['dispositions_agree'] is not True}
    protected = {r['text'] for r in prior['protected_queries']}
    first.need(not set(selected) & (conflicts | protected), 'EMPLOYMENT_UNRESOLVED_CONFLICT')
    occurrences, cache = defaultdict(list), {}
    for relative, digest in bindings.items():
        wb = first.pinned(root, relative, digest)
        for row in wb['queue']:
            key = row['normalized_text']
            if key not in selected:
                continue
            first.need(row['disposition'] == 'NEGATIVE_EXACT_REVIEW', 'EMPLOYMENT_PRIOR_HOLD')
            for ref in row['source_refs']:
                source = wb['sources'][ref['batch']]
                if source['file'] not in cache:
                    data = first.pinned(root, source['file'], source['sha256'])
                    cache[source['file']] = {r['source_line']: r['values']['Keyword']
                                            for r in data['source_projection']['records']}
                first.need(first.normalize(cache[source['file']].get(ref['source_line'], '')) == key,
                           'EMPLOYMENT_OCCURRENCE_IDENTITY')
                occurrences[key].append({'batch': ref['batch'], 'source_line': ref['source_line'],
                    'file': source['file'], 'sha256': source['sha256'], 'review_file': relative,
                    'review_sha256': digest})
    records = [first.make_record(row, review, occurrences[key], source_id=primary[key][0],
        source_reference=primary[key][1]+'#'+str(primary[key][2]), review_folder=FOLDER,
        allowed_intents=set(SELECTIONS.values())) for key, row in sorted(selected.items())]
    source_ids = {r['source_id'] for r in records}
    sources = []
    for batch in sorted(source_ids):
        key = next(k for k in selected if primary[k][0] == batch)
        capture_path = str(PurePosixPath(originals[key]).parent/'capture.json')
        capture = captures[capture_path]
        first.need(capture['account_id'] == '573-038-4686', 'EMPLOYMENT_SOURCE_ACCOUNT')
        sources.append({'source_id': batch, 'kind': 'official_reference', 'approved_for_research': True,
            'evidence_ref': capture_path, 'observed_on': capture['capture_date_dubai'],
            'valid_until': review['valid_until'],
            'research_use_basis': 'OWNER_AUTHORIZED_PLANNER_RESEARCH_AND_VERIFIED_PROVIDER_CAPTURE',
            'served_query_or_current_performance_claimed': False})
    held_protection = [{'query_id': 'BSRE-Q-'+hashlib.sha256(text.encode()).hexdigest()[:24],
        'text': text, 'campaign_keys': [first.CAMPAIGN], 'services': ['residential_rental'],
        'must_serve': True, 'evidence_ref': FOLDER+'/review.json#held_phrases',
        'reviewed_on': review['reviewed_on'], 'valid_until': review['valid_until']} for text in sorted(HELD)]
    return {'review': review, 'records': records, 'sources': sources, 'campaigns': prior['campaigns'],
        'campaign_context': prior['campaign_context'],
        'protected_queries': prior['protected_queries']+held_protection,
        'existing_overlap_phrases': sorted(overlaps)}


def summarize(inputs, result):
    return {'scope': 'SECOND_AI_EMPLOYMENT_RESEARCH_COHORT_NOT_APPROVAL',
        **{k: result[k] for k in ('as_of', 'input_rows', 'distinct_nonblank_phrases', 'reviewed_eligible_rows',
        'excluded_rows', 'approved_exclusion_rows', 'deficit', 'structural_pass', 'deployment_export_allowed',
        'production_writes_available', 'positive_library_coverage_verified', 'protected_queries_indexed')},
        'source_occurrences_retained': sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'previous_cohort_overlaps_not_counted_again': len(inputs['existing_overlap_phrases']),
        'spelling_or_punctuation_holds_not_counted': len(HELD),
        'computed_conflicts': len(result['protected_conflicts']),
        'human_review_verified': False, 'live_campaign_mapping_verified': False,
        'subject_sha256': inputs['review']['subject_sha256']}


def _verify_reconstructed(inputs, root=first.ROOT, at=None):
    """Internal: retain every audit/report check while reusing verified inputs in-call."""
    result = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
        inputs['campaign_context'], inputs['protected_queries'], first.dubai_date() if at is None else at)
    summary = summarize(inputs, result)
    first.need(summary['structural_pass'] and summary['reviewed_eligible_rows'] == 935 and
        summary['approved_exclusion_rows'] == summary['computed_conflicts'] == 0 and
        not summary['deployment_export_allowed'] and not summary['positive_library_coverage_verified'],
        'EMPLOYMENT_RESEARCH_NOT_ELIGIBLE')
    saved = first.pinned(root, FOLDER+'/cohort-report.json', REPORT_PIN)
    first.need(first.canonical(saved) == first.canonical(dict(summary, as_of=inputs['review']['reviewed_on'])),
               'EMPLOYMENT_REPORT_CHANGED')
    return dict(summary, passed=True)


def verify(root=first.ROOT, at=None):
    return _verify_reconstructed(reconstruct(root), root, at)


if __name__ == '__main__':
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'EMPLOYMENT_RESEARCH_HELD',
                          'deployment_export_allowed': False, 'production_writes_available': False}))
        raise SystemExit(1)
