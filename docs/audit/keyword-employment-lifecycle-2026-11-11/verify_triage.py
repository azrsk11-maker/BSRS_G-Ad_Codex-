"""Reproduce this reviewed capture's unapproved exact proposals and full provisional protection."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,EMPLOYMENT_LIFECYCLE_CAPTURE
PINS={'proposals.json': '3df02838ac668271034bfb6e84907884c27193234733cb2b4c622670ed73cd59', 'workbench.json': 'd55c2ba4f03fe8f91cc49477f938cd0eae0ac638b1667709de422ab540404449', 'protection-screen.json': 'd4317c7bb94502076d60449a14d74e60a0d48dad28145f5921b612e070b6f783'}
CAPTURE_PIN='94dfa8a6fe28a0ed76b865a5a230c4404a5bc8c25ecfa0cd9fae6f6311fa78c1'
CASES='docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
CASES_PIN='ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43'
GENERIC=['salary','income','interview','resume','cv','job','agent','property','rent','lease','free','india']


def verify():
    loaded={}
    for name,pin in PINS.items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('EMPLOYMENT_LIFECYCLE_REVIEW_CHANGED')
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
    if len(protected)!=11573 or hashlib.sha256((HERE/'capture.json').read_bytes()).hexdigest()!=CAPTURE_PIN:
        raise ValueError('PRIOR_PROTECTION_OR_CAPTURE_CHANGED')
    fresh=compile_protection_review(load_corpus(ROOT,capture=EMPLOYMENT_LIFECYCLE_CAPTURE),
        loaded['proposals.json'],sorted(protected),GENERIC,proposed_on='2026-11-11')
    fresh['screen']['source_bindings']=bindings
    if (not _exact(fresh['workbench'],loaded['workbench.json']) or not _exact(fresh['screen'],loaded['protection-screen.json']) or
        fresh['workbench']['summary']['dispositions']!={'HOLD':508,'NEGATIVE_EXACT_REVIEW':1178,'POSITIVE_REVIEW':0,'UNASSESSED':0} or
        fresh['screen']['protected_queries']!=12081 or fresh['screen']['exact_conflict_count']):
        raise ValueError('EMPLOYMENT_LIFECYCLE_REVIEW_NOT_REPRODUCIBLE')
    return {'passed':True,'scope':'PRELIMINARY_EMPLOYMENT_RESEARCH_NOT_ADMISSION_OR_SCOPE',
        **fresh['workbench']['summary'],'protected_queries':12081,'exact_lexical_conflicts':0,
        'authored_tests_outside_research_counts':20,'positive_library_coverage_verified':False,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_EMPLOYMENT_LIFECYCLE_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
