"""Reproduce this reviewed capture's unapproved exact proposals and full provisional protection."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,OCCUPATIONAL_EDUCATION_CAPTURE
PINS={'proposals.json': '5bc5aceb9847e58f3500ad5dc76c4a48fb7728b6100e6805578a6081fbd45a1e', 'workbench.json': '4487755de36391aa59f5bdb06d8bb72edb3c48a8f46ca2a89a6d733248daa1b0', 'protection-screen.json': '130d759500068d55142069ca3ac04128203576640913135d5be73086d7741d15'}
CAPTURE_PIN='1e30f171310155e76229d35922e951aed2965def632af757f3c8d30386eb6217'
CASES='docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
CASES_PIN='ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43'
GENERIC=['course', 'courses', 'degree', 'exam', 'training', 'free', 'license', 'property', 'management', 'investment', 'landlord', 'rera']


def verify():
    loaded={}
    for name,pin in PINS.items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('OCCUPATIONAL_EDUCATION_REVIEW_CHANGED')
        loaded[name]=parse_json_bytes(raw)
    bindings=loaded['protection-screen.json']['source_bindings']
    if bindings['capture_manifest_sha256']!=CAPTURE_PIN or bindings['authored_protection_cases_sha256']!=CASES_PIN:
        raise ValueError('PROTECTION_BINDINGS_CHANGED')
    protected=set()
    for relative,pin in bindings['prior_workbench_sha256'].items():
        # These are exact paths in a raw-pinned screen, not caller arguments.
        raw=(ROOT/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('PRIOR_REVIEW_CHANGED')
        protected.update(r['normalized_text'] for r in parse_json_bytes(raw)['queue'] if r['disposition']!='NEGATIVE_EXACT_REVIEW')
    raw=(ROOT/CASES).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=CASES_PIN:raise ValueError('AUTHORED_CASES_CHANGED')
    cases=parse_json_bytes(raw)
    if cases['counts_toward_research_or_masters'] is not False or len(cases['cases'])!=20:
        raise ValueError('AUTHORED_CASE_AUTHORITY')
    protected.update(r['query'] for r in cases['cases'])
    if len(protected)!=11160 or hashlib.sha256((HERE/'capture.json').read_bytes()).hexdigest()!=CAPTURE_PIN:
        raise ValueError('PRIOR_PROTECTION_OR_CAPTURE_CHANGED')
    fresh=compile_protection_review(load_corpus(ROOT,capture=OCCUPATIONAL_EDUCATION_CAPTURE),
        loaded['proposals.json'],sorted(protected),GENERIC,proposed_on='2026-11-11')
    fresh['screen']['source_bindings']=bindings
    if (not _exact(fresh['workbench'],loaded['workbench.json']) or not _exact(fresh['screen'],loaded['protection-screen.json']) or
        fresh['workbench']['summary']['dispositions']!={'HOLD':413,'NEGATIVE_EXACT_REVIEW':959,'POSITIVE_REVIEW':0,'UNASSESSED':0} or
        fresh['screen']['protected_queries']!=11573 or fresh['screen']['exact_conflict_count']!=3):
        raise ValueError('OCCUPATIONAL_EDUCATION_REVIEW_NOT_REPRODUCIBLE')
    return {'passed':True,'scope':'PRELIMINARY_EDUCATION_RESEARCH_NOT_ADMISSION_OR_SCOPE',
        **fresh['workbench']['summary'],'protected_queries':11573,'exact_lexical_conflicts':3,
        'authored_tests_outside_research_counts':20,'positive_library_coverage_verified':False,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_OCCUPATIONAL_EDUCATION_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
