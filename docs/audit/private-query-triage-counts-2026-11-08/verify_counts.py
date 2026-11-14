"""Public count integrity; optional PRIVATE source/proposal reproduction.

Neither mode grants disclosure, business admission, exclusion or deployment.
No source cell, query, path or error detail is printed by the CLI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
import private_query_triage as adapter

AUDIT_PIN = '38a2174df39038bac0c653ccfbbb6683f7d6af0976db421247565d769de45ff8'
BENCHMARK_PIN = '1d235f6350ffc989083433986e08801e861a362c5dcd3d22418cdc69a017ed16'


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(source=None, proposals=None):
    need((source is None) == (proposals is None), 'PRIVATE_INPUT_PAIR_REQUIRED')
    raw = (HERE/'audit.json').read_bytes()
    need(sha(raw) == AUDIT_PIN, 'COUNT_AUDIT_BYTES_CHANGED')
    audit = parse_json_bytes(raw)
    need(set(audit) == {'version', 'scope', 'account_id', 'observed_date_dubai',
         'report_window', 'private_proposals_sha256', 'private_workbench_sha256',
         'count_summary', 'review', 'private_records_committed', 'classification_inherited'}, 'AUDIT_FIELDS')
    need(audit['version'] == 1 and audit['scope'] ==
         'COUNT_ONLY_PRIVATE_INTENT_TRIAGE_NOT_DISCLOSURE_OR_ADMISSION'
         and audit['account_id'] == '573-038-4686' and audit['observed_date_dubai'] == '2026-11-08'
         and audit['report_window'] == {'start': '2026-10-01', 'end': '2026-10-31'}, 'AUDIT_CONTEXT')
    need(audit['private_records_committed'] is False and audit['classification_inherited'] is False
         and audit['review'] == {'preliminary_agent_intent_review': True, 'separate_peer_coverage': True,
             'human_business_admission': False, 'public_disclosure_review_complete': False}, 'REVIEW_SCOPE')
    count = audit['count_summary']
    need(set(count) == adapter.COUNT_FIELDS | adapter.BOOLEAN_FIELDS | {'source_sha256'}, 'COUNT_FIELDS')
    need(all(type(count[k]) is int and count[k] >= 0 for k in adapter.COUNT_FIELDS)
         and all(type(count[k]) is bool for k in adapter.BOOLEAN_FIELDS), 'COUNT_TYPES')
    for pin in [audit['private_proposals_sha256'], audit['private_workbench_sha256'], count['source_sha256']]:
        need(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin) is not None, 'HASH_TYPE')
    need(count['positive_review_identities'] + count['hold_identities'] +
         count['negative_exact_review_identities'] + count['unassessed_identities'] ==
         count['unique_query_identities'], 'DISPOSITION_ACCOUNTING')
    need(count['manual_intent_proposals'] + count['automatic_privacy_hold_identities'] ==
         count['unique_query_identities'] and count['unassessed_identities'] == 0
         and count['complete_input_required'] is True and count['complete_intent_triage'] is True, 'COVERAGE')
    need(count['manual_disclosure_review_required_occurrences'] == count['query_occurrences']
         and count['privacy_flagged_source_records'] <= count['automatic_privacy_hold_occurrences'] <= count['query_occurrences'], 'DISCLOSURE_PENDING')
    need(all(count[k] == 0 for k in ['reviewed_positive', 'reviewed_negative', 'approved_positive',
         'approved_negative', 'admitted_positive', 'admitted_negative', 'master_additions', 'deployed'])
         and all(count[k] is False for k in [*adapter.AUTHORITY, 'lexical_scope_verified', 'resource_ids_verified']), 'ZERO_AUTHORITY')
    history = parse_json_bytes((HERE.parent/'search-terms-2026-11-08/audit.json').read_bytes())
    need(count['source_sha256'] == history['source']['sha256'] and count['source_bytes'] == history['source']['bytes']
         and count['query_occurrences'] == history['summary']['query_placement_rows']
         and count['unique_query_identities'] == history['summary']['distinct_normalized_search_terms'], 'HISTORICAL_SOURCE_LINK')

    raw = (HERE/'benchmark.json').read_bytes()
    need(sha(raw) == BENCHMARK_PIN, 'BENCHMARK_BYTES_CHANGED')
    benchmark = parse_json_bytes(raw)
    need(benchmark['scope'] == 'ONE_LOCAL_RUN_NOT_CONTROLLED_MULTI_RUN_BENCHMARK'
         and benchmark['timing_is_statistical_claim'] is False and benchmark['output_bytes_unchanged'] is True
         and benchmark['classifications_authority_unchanged'] is True, 'BENCHMARK_LIMITS')
    need(sha((ROOT/'tools/keyword-system/triage_workbench.py').read_bytes()) == benchmark['optimized_code_sha256']
         and sha((HERE.parent/'keyword-triage-2026-11-08/workbench.json').read_bytes()) == benchmark['golden_workbench_sha256'], 'OPTIMIZATION_SOURCE_AND_GOLDEN')
    need(round(benchmark['baseline_compile_seconds']/benchmark['optimized_compile_seconds'], 3)
         == benchmark['observed_single_run_speedup'], 'TIMING_ARITHMETIC')
    if source is not None:
        raw = Path(proposals).read_bytes()
        need(sha(raw) == audit['private_proposals_sha256'], 'PRIVATE_PROPOSALS_IDENTITY')
        result = adapter.compile_private_history(source, parse_json_bytes(raw))
        encoded = (json.dumps(result['private_workbench'], ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        need(result['count_summary'] == count and sha(encoded) == audit['private_workbench_sha256'], 'PRIVATE_REPRODUCTION')
    return {'passed': True, 'scope': 'PRIVATE_SOURCE_AND_INTENT_REPRODUCTION' if source is not None else
            'PUBLIC_COUNT_INTEGRITY_ONLY', 'unique_identities': count['unique_query_identities'],
            'source_occurrences': count['query_occurrences'], 'unassessed': count['unassessed_identities'],
            'public_disclosure_authorized': False, 'business_admission_complete': False,
            'negative_authorized': False, 'deployment_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source')
    parser.add_argument('--proposals')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.source, args.proposals)))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'COUNT_AUDIT_FAILED',
                          'public_disclosure_authorized': False, 'deployment_authorized': False}))
        raise SystemExit(1)
