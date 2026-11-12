"""Reproduce every frozen diagnostic from fresh complete source history; no admission."""
from copy import deepcopy
from datetime import date
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
from time import perf_counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT/'tools/keyword-system'))
import append_only_admission as stage
import current_negative_library as current
import source_membership_diagnostic as comparison

REPORT_SHA256 = 'e8e9a30a4657476d41d74fdd034779283341e2ef77c0a2b39c1e774711cd5ef3'
REVIEW_VERIFIER_SHA256 = '5da8a1f58002b76333243c7b4612e829e21cc2409ea10949767e19c41e80e62b'
COMPARISON_MODULE_SHA256 = 'bd8bafb4c49d23185b8cff91112e1c79679ae39bd9def9974e6d911ed891e41c'
BASE_SHA256 = 'a93d5aa368975f79d3fd5bd92223ccfe93d8b48d725ac8c301013aba8d3868cb'
MODULE = 'tools/keyword-system/source_membership_diagnostic.py'


def need(condition, code):
    if not condition:
        raise ValueError(code)


def read_bound(path, limit):
    with path.open('rb') as stream:
        raw = stream.read(limit+1)
    need(0 < len(raw) <= limit, 'DIAGNOSTIC_BYTE_BOUND')
    return raw


def pinned_text(path, pin):
    raw = read_bound(path, 1024*1024)
    need(hashlib.sha256(raw).hexdigest() == pin, 'DIAGNOSTIC_IMPLEMENTATION_CHANGED')


def expected_report():
    pinned_text(HERE/'verify_review.py', REVIEW_VERIFIER_SHA256)
    pinned_text(ROOT/MODULE, COMPARISON_MODULE_SHA256)
    verifier = runpy.run_path(str(HERE/'verify_review.py'))
    sources = {name:verifier['read_json'](ROOT/verifier['SOURCE']/name,pin)
               for name,pin in verifier['PINS'].items()}
    review = verifier['read_json'](HERE/'review.json',verifier['REVIEW_SHA256'])
    verifier['validate'](review,sources)
    base = current.reconstruct_bank_channel_login_snapshot(at=date(2026,11,13))
    need(stage.digest(base) == BASE_SHA256, 'DIAGNOSTIC_COMPLETE_BASE_CHANGED')
    diagnostic = comparison.compare(base,
        sources['application-documents.json']['source_projection']['records'],review['decisions'])
    need(stage.digest(base) == BASE_SHA256, 'DIAGNOSTIC_MUTATED_BASE')
    return {'schema':'bsre-front-office-document-pre-admission-comparison-v1',
        'as_of':'2026-11-13','base_complete_inputs_sha256':BASE_SHA256,
        'source_pins':verifier['PINS'],'semantic_review_sha256':verifier['REVIEW_SHA256'],
        'comparison_module':MODULE,'comparison_module_sha256':COMPARISON_MODULE_SHA256,
        'diagnostic':diagnostic}, verifier['exact']


def validate(report, expected, exact):
    need(exact(report,expected), 'FRESH_COMPLETE_DIAGNOSTIC_CHANGED')
    diagnostic = report['diagnostic']
    need(diagnostic['source_records_compared'] == 4356 and
         diagnostic['reviewed_records_compared'] == 1100 and
         diagnostic['external_key_comparisons'] == diagnostic['within_source_key_comparisons'] == 17424
         and diagnostic['cohort_external_key_comparisons'] ==
             diagnostic['cohort_within_source_key_comparisons'] == 4400,
         'DIAGNOSTIC_COVERAGE_CHANGED')
    return {'passed':True,'source_records_compared':4356,'cohort_records_compared':1100,
        'external_key_comparisons':17424,'within_source_key_comparisons':17424,
        'unmatched_compatible_proposals':len(diagnostic['unmatched_compatible_proposal_ordinals']),
        'semantic_holds_matching_existing_negatives':len(diagnostic['semantic_holds_matching_existing_negatives']),
        'base_complete_inputs_sha256':BASE_SHA256,'library_rows_added':0,'approved':0,'deployed':0}


def self_check(report, expected, exact):
    cases = {
        'missing_source_peer':lambda r:r['diagnostic']['source_row_comparisons'].pop(),
        'reversed_source':lambda r:r['diagnostic']['source_row_comparisons'].reverse(),
        'missing_method':lambda r:r['diagnostic']['source_row_comparisons'][0]['joins'].pop(),
        'changed_population':lambda r:r['diagnostic']['complete_base_counts'].update(records=1),
        'changed_base_binding':lambda r:r.update(base_complete_inputs_sha256='0'*64),
        'changed_source_pin':lambda r:r['source_pins'].update({'capture.json':'0'*64}),
        'changed_review':lambda r:r.update(semantic_review_sha256='0'*64),
        'changed_implementation':lambda r:r.update(comparison_module_sha256='0'*64),
        'invented_existing_identity':lambda r:r['diagnostic']['source_row_comparisons'][0]['joins'][0]['existing_identities'].append('records:invented'),
        'invented_peer':lambda r:r['diagnostic']['source_row_comparisons'][0]['joins'][0]['source_peer_ordinals'].append(99999),
        'false_google_equivalence':lambda r:r['diagnostic'].update(google_equivalence_verified=True),
        'false_admission':lambda r:r['diagnostic'].update(admission_approved=True),
        'boolean_zero':lambda r:r['diagnostic'].update(library_rows_added=False),
        'changed_cohort_count':lambda r:r['diagnostic'].update(cohort_external_key_comparisons=0),
    }
    for name,mutate in cases.items():
        changed = deepcopy(report); mutate(changed)
        try:
            validate(changed,expected,exact)
        except (ValueError,KeyError,TypeError):
            continue
        raise AssertionError('Diagnostic tamper accepted: '+name)
    return list(cases)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check',action='store_true')
    args=parser.parse_args(); start=perf_counter()
    raw=read_bound(HERE/'membership-diagnostic.json',8*1024*1024)
    need(hashlib.sha256(raw).hexdigest()==REPORT_SHA256,'DIAGNOSTIC_RAW_PIN_CHANGED')
    report=comparison.ka.parse_json_bytes(raw)
    expected,exact=expected_report()
    result=validate(report,expected,exact)
    if args.self_check:
        result['tamper_cases_rejected']=self_check(report,expected,exact)
    result['elapsed_seconds']=round(perf_counter()-start,6)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':
    main()
