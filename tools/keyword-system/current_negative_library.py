"""Current reviewed research from verified history and explicit extensions.

Historical source files stay intact. The ID index owns current membership;
record bodies are freshly reconstructed from their single provenance sources.
No platform, export, approval or production writer is provided.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy

import negative_admission as first
import negative_library as history
import negative_reviewed_cohort as registered
from keyword_audit import audit, normalize
from negative_partition import reference

FOLDER = 'docs/audit/keyword-negative-role-admission-2026-11-11'
INDEX = 'tools/keyword-system/data/negative-research-index.json'
INDEX_PIN = 'ff04733c369954f66d562dc14a263bf40b58c7b14877332767f309472cb5e525'
REPORT_PIN = '61352575aa6f8c2ea08d9fbe5cc6eec8ecfc02fc06ddd486a09ddf9773c05c6f'
ALLOCATION_PIN = '1e2b7b4262162f1a72d83b2afe11e88afaf3414d65748d540315c5dd090535a1'
PREVIOUS_ALLOCATION = 'docs/audit/keyword-negative-gap-admission-2026-11-11/research-pool-allocation.json'
PREVIOUS_ALLOCATION_PIN = '94d313beb04085fc2c734f11080da1562509a0332234bfc7264291a1b5f32173'

LATEST_FOLDER = 'docs/audit/keyword-vendor-review-coverage-2026-11-11'
LATEST_VERIFIER_PIN = '1a2687c268ac3f45948c3462bd782e7a3a86a0a70cef92f9c172da8ae846bf12'
LATEST_INDEX = 'tools/keyword-system/data/negative-latest-review-index.json'
LATEST_INDEX_PIN = '4fe30cd2c768f5779982dc4d7cc41be3b8aa7055e67dda8008672624d9a58293'

INTENT_POOLS = {
    'EXPLICIT_OCCUPATIONAL_STUDY_OR_ASSESSMENT_RESEARCH': 'ACADEMIC',
    'EXPLICIT_APPLICATION_DOCUMENT_RESEARCH': 'EMPLOYMENT',
    'EXPLICIT_EMPLOYMENT_APPLICATION_RESEARCH': 'EMPLOYMENT',
    'EXPLICIT_EMPLOYMENT_RESEARCH': 'EMPLOYMENT',
    'EXPLICIT_GRAPHIC_OR_MOCKUP_ARTIFACT_RESEARCH': 'MEDIA',
    'EXPLICIT_MARKETING_TEMPLATE_ARTIFACT_RESEARCH': 'MEDIA',
    'EXPLICIT_SOFTWARE_DESIGN_ARTIFACT_RESEARCH': 'SOFTWARE',
}


def extend(base, root, when):
    """Internal: extend only this invocation's freshly verified base."""
    parts = [base]
    for entry in registered.CURRENT_CATALOG:
        cohort = registered.reconstruct(root, entry, history.compose(parts))
        registered._verify_reconstructed(cohort, entry, root, when)
        parts.append(cohort)
    merged = history.compose(parts)
    return dict(merged, archived_records=deepcopy(base['archived_records']),
        base_index=deepcopy(base['research_index']),
        current_cohorts=deepcopy([part['review'] for part in parts[1:]]),
        base_eligible_rows=len(base['records']),
        deployment_authorized=False, production_writes_available=False)


def build_index(inputs):
    records, archived = inputs['records'], inputs['archived_records']
    ids = [r['keyword_id'] for r in records]
    held = [r['keyword_id'] for r in archived]
    phrases = [normalize(r['original_text']) for r in records + archived]
    first.need(all(phrases) and len(phrases) == len(set(phrases)) and
        len(ids + held) == len(set(ids + held)), 'CURRENT_LIBRARY_IDENTITY_COLLISION')
    first.need(held == inputs['base_index']['held_keyword_ids'] and
        ids[:inputs['base_eligible_rows']] == inputs['base_index']['eligible_keyword_ids'],
        'CURRENT_LIBRARY_HISTORY_REPLACED')
    return {'version': 1, 'scope': 'CURRENT_REVIEWED_RESEARCH_INDEX_NOT_ADS_EXCLUSION_APPROVAL',
        'base_index': reference({'file': 'tools/keyword-system/'+history.CURRENT_INDEX,
                                 'sha256': history.CURRENT_INDEX_PIN}),
        'cohorts': [{'review': reference({'file': e['folder']+'/review.json', 'sha256': e['review_sha256']}),
                     'report': reference({'file': e['folder']+'/cohort-report.json', 'sha256': e['report_sha256']})}
                    for e in registered.CURRENT_CATALOG],
        'counts': {'eligible': len(ids), 'held_historical': len(held),
                   'new': len(ids)-inputs['base_eligible_rows']},
        'eligible_keyword_ids': ids, 'held_historical_keyword_ids': held,
        'research_only': True, 'exclusion_approval_granted': False,
        'deployment_authorized': False, 'production_writes_available': False,
        'historical_records_rewritten': False}


def summarize(inputs, result):
    return {'scope': 'CURRENT_COMPOSED_REVIEWED_NEGATIVE_RESEARCH_NOT_EXCLUSION_APPROVAL',
        **{k: result[k] for k in ('as_of', 'input_rows', 'distinct_nonblank_phrases',
            'reviewed_eligible_rows', 'excluded_rows', 'approved_exclusion_rows', 'target',
            'deficit', 'exact_target_pass', 'structural_pass', 'deployment_export_allowed',
            'production_writes_available', 'positive_library_coverage_verified', 'protected_queries_indexed')},
        'base_eligible_rows': inputs['base_eligible_rows'],
        'historical_rows_preserved': inputs['base_index']['counts']['historical'],
        'held_historical_rows': len(inputs['archived_records']),
        'new_rows': len(inputs['records'])-inputs['base_eligible_rows'],
        'cohorts': [{'key': e['key'], 'rows': e['expected_rows']} for e in registered.CURRENT_CATALOG],
        'computed_conflicts': len(result['protected_conflicts']),
        'source_occurrences_retained_in_current_records': sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'approval_hold_counts': dict(Counter(reason for r in result['records'] for reason in r['deployment_holds'])),
        'human_review_verified': False, 'live_campaign_mapping_verified': False,
        'historical_records_rewritten': False, 'release_authorized': False}


def allocation(inputs, previous):
    first.need(previous['total_target'] == 14000 and previous['total_admitted'] == 7188 and
        sum(previous['after'].values()) == 14000 and sum(previous['admitted'].values()) == 7188 and
        previous['owner_approval_claimed'] is False and previous['media_budget_changed'] is False and
        previous['exclusion_approval_granted'] is False, 'CURRENT_ALLOCATION_BASE')
    # The latest screen holds exactly these original employment records; this
    # is a deduction, never a reinterpretation or rewrite of their old evidence.
    held = {r['normalized_text'] for r in inputs['archived_records']}
    first.need(held == {'estate agent recruitment', 'property agent recruitment'},
               'CURRENT_ALLOCATION_ARCHIVE_CHANGED')
    added = Counter()
    for row in inputs['records'][inputs['base_eligible_rows']:]:
        first.need(row['reason_code'] in INTENT_POOLS, 'CURRENT_ALLOCATION_UNKNOWN_INTENT')
        added[INTENT_POOLS[row['reason_code']]] += 1
    admitted = dict(previous['admitted'])
    admitted['EMPLOYMENT'] -= len(held)
    for key, value in added.items():
        admitted[key] += value
    remaining = {key: previous['after'][key]-value for key, value in admitted.items()}
    first.need(all(v >= 0 for v in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']) and
        sum(remaining.values()) + len(inputs['records']) == 14000, 'CURRENT_ALLOCATION_COUNTS')
    return {'version': 1, 'scope': 'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref': first.MASTER, 'previous_allocation_ref': PREVIOUS_ALLOCATION,
        'previous_allocation_sha256': PREVIOUS_ALLOCATION_PIN,
        'basis': 'Keep existing targets; deduct two latest-held historical employment records; add only the newly reviewed cohort.',
        'owner_approval_claimed': False, 'media_budget_changed': False,
        'exclusion_approval_granted': False, 'targets': previous['after'],
        'held_deduction': {'EMPLOYMENT': len(held)}, 'new_rows': dict(added),
        'admitted': admitted, 'remaining': remaining, 'total_target': 14000,
        'total_admitted': sum(admitted.values()), 'total_remaining': sum(remaining.values())}


def check_outputs(inputs, root, when):
    result = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
                   inputs['campaign_context'], inputs['protected_queries'], when)
    summary = summarize(inputs, result)
    expected = inputs['base_eligible_rows'] + sum(e['expected_rows'] for e in registered.CURRENT_CATALOG)
    first.need(summary['structural_pass'] and summary['reviewed_eligible_rows'] == expected and
        summary['input_rows'] == expected and summary['computed_conflicts'] == summary['excluded_rows'] ==
        summary['approved_exclusion_rows'] == 0 and not summary['deployment_export_allowed'] and
        not summary['positive_library_coverage_verified'], 'CURRENT_LIBRARY_NOT_ELIGIBLE')
    saved_index = first.pinned(root, INDEX, INDEX_PIN)
    first.need(first.canonical(saved_index) == first.canonical(build_index(inputs)), 'CURRENT_LIBRARY_INDEX_CHANGED')
    previous = first.pinned(root, PREVIOUS_ALLOCATION, PREVIOUS_ALLOCATION_PIN)
    saved_allocation = first.pinned(root, FOLDER+'/research-pool-allocation.json', ALLOCATION_PIN)
    first.need(first.canonical(saved_allocation) == first.canonical(allocation(inputs, previous)),
               'CURRENT_LIBRARY_ALLOCATION_CHANGED')
    saved_report = first.pinned(root, FOLDER+'/library-report.json', REPORT_PIN)
    first.need(first.canonical(saved_report) == first.canonical(dict(summary, as_of='2026-11-11')),
               'CURRENT_LIBRARY_REPORT_CHANGED')
    return dict(summary, passed=True, index_verified=True,
        current_index_file=INDEX, release_held=True)


def reconstruct_registered(root=first.ROOT, at=None):
    """Verify the immutable registered baseline, before later protective holds.

    This is historical input to the latest guard, not current admission output.
    """
    when = first.dubai_date() if at is None else at
    inputs = extend(history.reconstruct_current(root, at=when), root, when)
    check_outputs(inputs, root, when)
    return inputs


def build_latest_index(inputs, impact):
    """Sparse held-ID overlay; preserve every registered body and its source."""
    ids = [row['keyword_id'] for row in inputs['records']]
    known, held, pairs = set(ids), set(), set()
    first.need(len(ids) == len(known), 'LATEST_BASE_DUPLICATE_ID')
    for key in ('registered_input_rows', 'latest_review_eligible_rows', 'latest_excluded_rows',
                'latest_deficit', 'approved_exclusion_rows', 'master_additions'):
        first.need(type(impact.get(key)) is int and impact[key] >= 0, 'LATEST_REVIEW_COUNT')
    first.need(impact['approved_exclusion_rows'] == impact['master_additions'] == 0 and
        impact.get('historical_rows_rewritten') is False and impact.get('deployment_authorized') is False,
        'LATEST_REVIEW_AUTHORITY')
    first.need(isinstance(impact.get('protected_conflicts'), list), 'LATEST_REVIEW_CONFLICTS')
    for conflict in impact['protected_conflicts']:
        first.need(isinstance(conflict, dict) and set(conflict) ==
            {'negative_id', 'protected_query_id', 'affected_campaign_keys', 'result'}, 'LATEST_REVIEW_CONFLICT_FIELDS')
        identity, query, campaigns = conflict['negative_id'], conflict['protected_query_id'], conflict['affected_campaign_keys']
        first.need(identity in known and isinstance(query, str) and query and campaigns == [first.CAMPAIGN] and
            conflict['result'] == 'CONFLICT_HOLD', 'LATEST_REVIEW_UNKNOWN_OR_BAD_CONFLICT')
        pair = (identity, query)
        first.need(pair not in pairs, 'LATEST_REVIEW_DUPLICATE_CONFLICT')
        pairs.add(pair); held.add(identity)
    first.need(impact['registered_input_rows'] == len(ids) and impact['latest_excluded_rows'] == len(held) and
        impact['latest_review_eligible_rows'] == len(ids)-len(held) and
        impact['latest_deficit'] == max(14000-len(ids)+len(held), 0) and
        impact.get('admission_held') is bool(held), 'LATEST_REVIEW_MEMBERSHIP_COUNTS')
    return {'version': 1, 'scope': 'LATEST_REVIEW_HOLD_OVERLAY_NOT_AD_SERVING_STATUS',
        'registered_index': reference({'file': INDEX, 'sha256': INDEX_PIN}),
        'latest_coverage': reference({'file': LATEST_FOLDER+'/report.json', 'sha256': impact['latest_coverage_sha256']}),
        'counts': {'registered': len(ids), 'eligible': len(ids)-len(held),
            'additional_held': len(held), 'total_archived': len(inputs['archived_records'])+len(held)},
        'additional_held_keyword_ids': [identity for identity in ids if identity in held],
        'prior_archived_keyword_ids': [r['keyword_id'] for r in inputs['archived_records']],
        'research_only': True, 'independent_review_verified': False,
        'deployment_authorized': False, 'historical_records_rewritten': False}


def latest_screen(inputs, root, when):
    """Fresh all-current screen; never recurse into the public current API."""
    path = Path(root)/LATEST_FOLDER/'verify_coverage.py'
    with path.open('rb') as stream:
        raw = stream.read(1024*1024+1)
    first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == LATEST_VERIFIER_PIN,
               'LATEST_REVIEW_VERIFIER_CHANGED')
    module = runpy.run_path(str(path))
    report = module['pinned'](path.parent/'report.json', module['REPORT_PIN'])
    expected = module['pinned'](path.parent/'admitted-master-impact.json', module['IMPACT_PIN'])
    bundle = module['build_impact'](report, data=inputs, at=when, with_protected=True)
    first.need(first.canonical(bundle['impact']) == first.canonical(expected), 'LATEST_CURRENT_IMPACT_CHANGED')
    first.need(len(bundle['protected_queries']) == expected['protected_queries'], 'LATEST_CURRENT_PROTECTION_COUNT')
    index = build_latest_index(inputs, bundle['impact'])
    saved = first.pinned(root, LATEST_INDEX, LATEST_INDEX_PIN)
    first.need(first.canonical(saved) == first.canonical(index), 'LATEST_CURRENT_INDEX_CHANGED')
    return dict(bundle, review_index=index)


def apply_latest(inputs, screen):
    held = set(screen['review_index']['additional_held_keyword_ids'])
    return deepcopy(dict(inputs,
        records=[r for r in inputs['records'] if r['keyword_id'] not in held],
        archived_records=inputs['archived_records']+[r for r in inputs['records'] if r['keyword_id'] in held],
        protected_queries=screen['protected_queries'], current_review_index=screen['review_index'],
        current_protection_evidence=LATEST_FOLDER+'/admitted-master-impact.json',
        deployment_authorized=False, production_writes_available=False))


def reconstruct(root=first.ROOT, at=None):
    when = first.dubai_date() if at is None else at
    inputs = reconstruct_registered(root, at=when)
    return apply_latest(inputs, latest_screen(inputs, root, when))


def verify(root=first.ROOT, at=None):
    when = first.dubai_date() if at is None else at
    inputs = reconstruct_registered(root, at=when)
    screen = latest_screen(inputs, root, when)
    impact = screen['impact']
    registered = first.pinned(root, FOLDER+'/library-report.json', REPORT_PIN)
    return dict(registered, passed=True, scope='CURRENT_NEGATIVE_RESEARCH_AFTER_LATEST_COMPLETE_REVIEW',
        as_of=when.isoformat(), registered_research_rows=len(inputs['records']),
        reviewed_eligible_rows=impact['latest_review_eligible_rows'], excluded_rows=impact['latest_excluded_rows'],
        deficit=impact['latest_deficit'], computed_conflicts=len(impact['protected_conflicts']),
        protected_queries_indexed=impact['protected_queries'],
        held_historical_rows=screen['review_index']['counts']['total_archived'],
        latest_protection_evidence=LATEST_FOLDER+'/admitted-master-impact.json',
        current_index_file=LATEST_INDEX, index_verified=True, admission_held=impact['admission_held'], release_held=True)


if __name__ == '__main__':
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'CURRENT_RESEARCH_LIBRARY_HELD',
                          'deployment_export_allowed': False, 'production_writes_available': False}))
        raise SystemExit(1)
