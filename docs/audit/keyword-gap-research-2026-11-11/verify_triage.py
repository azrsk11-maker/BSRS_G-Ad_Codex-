"""Reproduce fixed preliminary annotations/protections; no admission or platform writer."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,GAP_RESEARCH_CAPTURE
PINS={'proposals.json': 'fe951e3d89b34461f20a007076f57be319ef2de49b23ca243018695fa178f4c9', 'workbench.json': '73da881c9b8ccea784178fd204a6e1dbb22dcdf309671c6d6f32cb51d1fbfd42', 'protection-screen.json': '68ffd00b5e218f80e2db751c5c2fa6ff16fe0334b7489f210bee60147bbccb8c'}
CAPTURE_PIN='5ccdbf45f7d9b4408792a9f241e5d9f8b90f1e612620a3770c6c3e03881dc3f9'
PRIMARY_CONTEXT_PIN='9dca253a49753534e0fdab4ce5e7297bd4022f0c15206f9893bb87ef36385ef3'
CASES='docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
GENERIC=['job','manager','property','rent','free','theme','wordpress','clipart','repair','maintenance','control','sale']

def pinned(path,pin):
    with path.open('rb') as stream:raw=stream.read(32*1024*1024+1)
    if len(raw)>32*1024*1024 or hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('GAP_REVIEW_INPUT_CHANGED')
    return parse_json_bytes(raw)

def verify():
    loaded={name:pinned(HERE/name,pin) for name,pin in PINS.items()}
    if hashlib.sha256((HERE/'PRIMARY_CONTEXT.md').read_bytes()).hexdigest()!=PRIMARY_CONTEXT_PIN:
        raise ValueError('CATEGORY_CONTEXT_CHANGED')
    bindings=loaded['protection-screen.json']['source_bindings']
    coverage=pinned(ROOT/'docs/audit/keyword-review-coverage-2026-11-11/report.json',bindings['prior_coverage_report_sha256'])
    if (bindings['capture_manifest_sha256']!=CAPTURE_PIN or
        bindings['prior_workbench_sha256']!=coverage['source_bindings']['review_workbenches_sha256']):
        raise ValueError('PRIOR_REVIEW_BINDINGS_CHANGED')
    protected=set()
    for relative,pin in bindings['prior_workbench_sha256'].items():
        protected.update(r['normalized_text'] for r in pinned(ROOT/relative,pin)['queue'] if r['disposition']!='NEGATIVE_EXACT_REVIEW')
    cases=pinned(ROOT/CASES,bindings['authored_protection_cases_sha256'])
    if cases['counts_toward_research_or_masters'] is not False or len(cases['cases'])!=20:
        raise ValueError('AUTHORED_CASE_AUTHORITY')
    protected.update(r['query'] for r in cases['cases'])
    if len(protected)!=12081:raise ValueError('PRIOR_WORKBENCH_PROTECTION_CHANGED')
    for relative,pin in bindings['prior_cohort_review_sha256'].items():
        protected.update(pinned(ROOT/relative,pin)['held_phrases'])
    if len(protected)!=12246 or hashlib.sha256((HERE/'capture.json').read_bytes()).hexdigest()!=CAPTURE_PIN:
        raise ValueError('PRIOR_COHORT_PROTECTION_OR_CAPTURE_CHANGED')
    fresh=compile_protection_review(load_corpus(ROOT,capture=GAP_RESEARCH_CAPTURE),loaded['proposals.json'],
        sorted(protected),GENERIC,proposed_on='2026-11-11')
    fresh['screen']['source_bindings']=bindings
    if (not _exact(fresh['workbench'],loaded['workbench.json']) or not _exact(fresh['screen'],loaded['protection-screen.json']) or
        fresh['workbench']['summary']['dispositions']!={'HOLD':1022,'NEGATIVE_EXACT_REVIEW':2062,'POSITIVE_REVIEW':0,'UNASSESSED':0} or
        fresh['screen']['protected_queries']!=13256 or fresh['screen']['exact_conflict_count']):
        raise ValueError('GAP_REVIEW_NOT_REPRODUCIBLE')
    rows={r['normalized_text']:r for r in fresh['workbench']['queue']}
    for text in ('property vacancies','job of a property manager','hiring a property manager',
                 'pest control company for sale in dubai','woocommerce for real estate',
                 'themeforest wp residence','real estate website themeforest'):
        if rows[text]['disposition']!='HOLD':raise ValueError('PROTECTED_LITERAL_PROMOTED')
    return {'passed':True,'scope':'PRELIMINARY_GAP_RESEARCH_NOT_ADMISSION_OR_SCOPE',
        **fresh['workbench']['summary'],'protected_queries':13256,'exact_lexical_conflicts':0,
        'authored_tests_outside_research_counts':20,'positive_library_coverage_verified':False,'deployment_authorized':False}

if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_GAP_RESEARCH_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
