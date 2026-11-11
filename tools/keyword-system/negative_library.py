"""Exact composition of registered reviewed cohorts; no promotion, export or live writes."""
from collections import Counter
import json

import negative_admission as first
import negative_employment_admission as employment
from keyword_audit import audit, normalize

OUTPUT_PINS = {'data/negative.json': 'ba70665227a02cfb92bafd94dd60db9d3565550cbdaac91c146ce9763087873e', 'data/sources.json': '8cfc8ae23be8c7110f5063df2ca277eb267a4677240ecdda8b0b5291ab620268', 'data/campaign_context.json': 'b32986087b40a11c32c0a9a7e08d8bf123e4b89115056525ff264df3a590df97', 'library-report.json': '34c8edd2bfb17b7839202697e0a4ac2dab46444c8e9cf6a686139e3c1b7e7a58'}  # Actual complete-master and aggregate-report bytes, finalized before admission.


def merge_unique(groups, key, *, allow_identical):
    merged = {}
    for group in groups:
        for row in group:
            identity = row[key]
            if identity in merged:
                first.need(allow_identical and first.canonical(merged[identity]) == first.canonical(row),
                           'COHORT_DUPLICATE_OR_DISAGREEMENT')
            else:
                merged[identity] = row
    return list(merged.values())


def compose(cohorts):
    first.need(type(cohorts) is list and len(cohorts) >= 1, 'COHORTS_REQUIRED')
    registry = cohorts[0]['campaigns']
    first.need(all(first.canonical(c['campaigns']) == first.canonical(registry) for c in cohorts),
               'COHORT_REGISTRY_DISAGREEMENT')
    records = merge_unique([c['records'] for c in cohorts], 'keyword_id', allow_identical=False)
    keys = [normalize(r['original_text']) for r in records]
    first.need(len(set(keys)) == len(keys) and all(keys), 'COHORT_PHRASE_DUPLICATE')
    return {'records': records,
        'sources': merge_unique([c['sources'] for c in cohorts], 'source_id', allow_identical=True),
        'campaign_context': merge_unique([c['campaign_context'] for c in cohorts], 'campaign_key', allow_identical=True),
        'protected_queries': merge_unique([c['protected_queries'] for c in cohorts], 'query_id', allow_identical=True),
        'campaigns': registry}


def reconstruct(root=first.ROOT):
    initial = first.reconstruct(root)
    return compose([initial, employment.reconstruct(root, prior=initial)])


def summarize(inputs, result):
    return {'scope': 'COMPOSED_AI_REVIEWED_NEGATIVE_RESEARCH_NOT_EXCLUSION_APPROVAL',
        **{k: result[k] for k in ('as_of', 'input_rows', 'distinct_nonblank_phrases', 'reviewed_eligible_rows',
        'excluded_rows', 'approved_exclusion_rows', 'target', 'deficit', 'exact_target_pass', 'structural_pass',
        'deployment_export_allowed', 'production_writes_available', 'positive_library_coverage_verified',
        'protected_queries_indexed')},
        'cohorts': [{'review': first.FOLDER+'/review.json', 'research_rows': 1178},
                    {'review': employment.FOLDER+'/review.json', 'research_rows': 935}],
        'source_occurrences_retained': sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'computed_conflicts': len(result['protected_conflicts']),
        'approval_hold_counts': dict(Counter(reason for r in result['records'] for reason in r['deployment_holds'])),
        'source_capture_count': len(inputs['sources']), 'human_review_verified': False,
        'live_campaign_mapping_verified': False, 'authored_cases_outside_research_counts': 20}


def verify(root=first.ROOT, at=None):
    # Cohort report/expiry/provenance checks cannot be bypassed by a merged count.
    first.verify(root, at)
    employment.verify(root, at)
    inputs = reconstruct(root)
    first.need(set(OUTPUT_PINS) == {'data/negative.json', 'data/sources.json',
        'data/campaign_context.json', 'library-report.json'}, 'LIBRARY_OUTPUT_BINDINGS')
    for relative, expected in (('data/negative.json', inputs['records']),
        ('data/sources.json', inputs['sources']), ('data/campaign_context.json', inputs['campaign_context'])):
        actual = first.pinned(root, 'tools/keyword-system/'+relative, OUTPUT_PINS[relative])
        first.need(first.canonical(actual) == first.canonical(expected), 'LIBRARY_MASTER_DIFFERS_FROM_COHORTS')
    result = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
        inputs['campaign_context'], inputs['protected_queries'], first.dubai_date() if at is None else at)
    summary = summarize(inputs, result)
    first.need(summary['structural_pass'] and summary['reviewed_eligible_rows'] == 2113 and
        summary['approved_exclusion_rows'] == summary['computed_conflicts'] == 0 and
        not summary['exact_target_pass'] and not summary['deployment_export_allowed'] and
        not summary['positive_library_coverage_verified'], 'COMPOSED_LIBRARY_NOT_ELIGIBLE')
    saved = first.pinned(root, employment.FOLDER+'/library-report.json', OUTPUT_PINS['library-report.json'])
    historical = dict(summary, as_of='2026-11-11')
    first.need(first.canonical(saved) == first.canonical(historical), 'LIBRARY_REPORT_CHANGED')
    return dict(summary, passed=True)


if __name__ == '__main__':
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'COMPOSED_RESEARCH_HELD',
                          'deployment_export_allowed': False, 'production_writes_available': False}))
        raise SystemExit(1)
