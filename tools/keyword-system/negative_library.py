"""Exact composition of registered reviewed cohorts; no promotion, export or live writes."""
from collections import Counter
import json

import negative_admission as first
import negative_employment_admission as employment
import negative_reviewed_cohort as registered
from keyword_audit import audit, normalize

OUTPUT_PINS = {'data/negative.json': 'f7340c8e7f62e1c1ba0b66dd4eca65c39266af7b8d2989ca8087dc5f3d49b835', 'data/sources.json': '3d2263b60bded42d345fe0e6e7e65b9a1c7be80bc76cddf61c72ce5072eed1ca', 'data/campaign_context.json': 'b32986087b40a11c32c0a9a7e08d8bf123e4b89115056525ff264df3a590df97', 'library-report.json': 'a5b8201a593ae99c9561f4f802e503cc79d87948a511d3dbcb17375024abab01'}  # Complete master and aggregate report bytes.
LIBRARY_REPORT = 'docs/audit/keyword-negative-study-goods-admission-2026-11-11/library-report.json'


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


def reconstruct(root=first.ROOT, at=None):
    initial = first.reconstruct(root)
    second = employment.reconstruct(root, prior=initial)
    if at is not None:
        first._verify_reconstructed(initial, root, at)
        employment._verify_reconstructed(second, root, at)
    parts = [initial, second]
    for entry in registered.CATALOG:
        reviewed = registered.reconstruct(root, entry, compose(parts))
        if at is not None:
            registered._verify_reconstructed(reviewed, entry, root, at)
        parts.append(reviewed)
    return compose(parts)


def summarize(inputs, result):
    return {'scope': 'COMPOSED_AI_REVIEWED_NEGATIVE_RESEARCH_NOT_EXCLUSION_APPROVAL',
        **{k: result[k] for k in ('as_of', 'input_rows', 'distinct_nonblank_phrases', 'reviewed_eligible_rows',
        'excluded_rows', 'approved_exclusion_rows', 'target', 'deficit', 'exact_target_pass', 'structural_pass',
        'deployment_export_allowed', 'production_writes_available', 'positive_library_coverage_verified',
        'protected_queries_indexed')},
        'cohorts': [{'review': first.FOLDER+'/review.json', 'research_rows': 1178},
                    {'review': employment.FOLDER+'/review.json', 'research_rows': 935}]+
                   [{'review': e['folder']+'/review.json', 'research_rows': e['expected_rows']}
                    for e in registered.CATALOG],
        'source_occurrences_retained': sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'computed_conflicts': len(result['protected_conflicts']),
        'approval_hold_counts': dict(Counter(reason for r in result['records'] for reason in r['deployment_holds'])),
        'source_capture_count': len(inputs['sources']), 'human_review_verified': False,
        'live_campaign_mapping_verified': False, 'authored_cases_outside_research_counts': 20}


def verify(root=first.ROOT, at=None):
    # Fresh provenance once per invocation; all cohort/report/expiry checks remain.
    when = first.dubai_date() if at is None else at
    inputs = reconstruct(root, at=when)
    first.need(set(OUTPUT_PINS) == {'data/negative.json', 'data/sources.json',
        'data/campaign_context.json', 'library-report.json'}, 'LIBRARY_OUTPUT_BINDINGS')
    for relative, expected in (('data/negative.json', inputs['records']),
        ('data/sources.json', inputs['sources']), ('data/campaign_context.json', inputs['campaign_context'])):
        actual = first.pinned(root, 'tools/keyword-system/'+relative, OUTPUT_PINS[relative])
        first.need(first.canonical(actual) == first.canonical(expected), 'LIBRARY_MASTER_DIFFERS_FROM_COHORTS')
    result = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
        inputs['campaign_context'], inputs['protected_queries'], when)
    summary = summarize(inputs, result)
    expected_rows = 1178+935+sum(e['expected_rows'] for e in registered.CATALOG)
    first.need(summary['structural_pass'] and summary['reviewed_eligible_rows'] == expected_rows and
        summary['approved_exclusion_rows'] == summary['computed_conflicts'] == 0 and
        summary['exact_target_pass'] is (expected_rows == summary['target']) and
        not summary['deployment_export_allowed'] and
        not summary['positive_library_coverage_verified'], 'COMPOSED_LIBRARY_NOT_ELIGIBLE')
    saved = first.pinned(root, LIBRARY_REPORT, OUTPUT_PINS['library-report.json'])
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
