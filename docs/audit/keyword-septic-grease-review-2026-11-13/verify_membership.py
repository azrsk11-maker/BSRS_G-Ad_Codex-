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

REPORT_SHA256 = 'e8fba67815fa0e221209b987e5418fbb8b9ac69f44a8f3cee91217a6cc2ec549'
REVIEW_VERIFIER_SHA256 = '7d913497d8333686d5113abc3d971fa5576b49ad32dbf13387fe87269d161f62'
COMPARISON_MODULE_SHA256 = 'bd8bafb4c49d23185b8cff91112e1c79679ae39bd9def9974e6d911ed891e41c'
BASE_SHA256 = 'b83194a546a36acdf7e60a38214003a6d785ff8f2af63a8120aed1106686b814'
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
    base = current.reconstruct_front_office_document_snapshot(at=date(2026,11,13))
    need(stage.digest(base) == BASE_SHA256, 'DIAGNOSTIC_COMPLETE_BASE_CHANGED')
    diagnostic = comparison.compare(base,
        sources['service-installation.json']['source_projection']['records'],review['decisions'])
    need(stage.digest(base) == BASE_SHA256, 'DIAGNOSTIC_MUTATED_BASE')
    return {'schema':'bsre-septic-grease-pre-admission-comparison-v1',
        'as_of':'2026-11-13','base_complete_inputs_sha256':BASE_SHA256,
        'source_pins':verifier['PINS'],'semantic_review_sha256':verifier['REVIEW_SHA256'],
        'comparison_module':MODULE,'comparison_module_sha256':COMPARISON_MODULE_SHA256,
        'diagnostic':diagnostic}, verifier['exact']


def validate(report, expected, exact):
    need(exact(report,expected), 'FRESH_COMPLETE_DIAGNOSTIC_CHANGED')
    diagnostic = report['diagnostic']
    need(diagnostic['source_records_compared'] == 6053 and
         diagnostic['reviewed_records_compared'] == 914 and
         diagnostic['external_key_comparisons'] == diagnostic['within_source_key_comparisons'] == 24212
         and diagnostic['cohort_external_key_comparisons'] ==
             diagnostic['cohort_within_source_key_comparisons'] == 3656,
         'DIAGNOSTIC_COVERAGE_CHANGED')
    return {'passed':True,'source_records_compared':6053,'cohort_records_compared':914,
        'external_key_comparisons':24212,'within_source_key_comparisons':24212,
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
