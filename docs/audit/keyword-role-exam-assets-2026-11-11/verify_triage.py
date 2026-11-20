"""Reproduce fixed preliminary annotations/protections; no admission or platform writer."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,ROLE_EXAM_ASSET_CAPTURE
PINS={'proposals.json': '1416cf5e3092bca442b0be86e0f7de53ada4af1efcc3d80d99ba090abe9dbe00', 'workbench.json': '5c760a1135b7ef0694efe04e4305025a1c2fa44904402a20e0172707bcd333e5', 'protection-screen.json': 'c9f9d631a54cb812f46156c29a1168afcb244a3ba76b6b83664a3298606a140e'}
CAPTURE_PIN='ec254a5df735685452ce344da2201c6d44ef87b5775479cbac2e2b10c68d0092'
PRIMARY_CONTEXT_PIN='9f6e203e551d2ca8b0a127e86732b4aedb7d8fc4ea7f6c560424cec7c45afc3c'
CASES='docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
GENERIC=['job', 'career', 'exam', 'license', 'questions', 'study', 'template', 'brochure', 'flyer', 'application', 'letter', 'property', 'rent', 'free', 'investment', 'logo']

def pinned(path,pin):
    with path.open('rb') as stream:raw=stream.read(32*1024*1024+1)
    if len(raw)>32*1024*1024 or hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('ROLE_EXAM_ASSET_REVIEW_INPUT_CHANGED')
    return parse_json_bytes(raw)

def verify():
    loaded={name:pinned(HERE/name,pin) for name,pin in PINS.items()}
    if hashlib.sha256((HERE/'PRIMARY_CONTEXT.md').read_bytes()).hexdigest()!=PRIMARY_CONTEXT_PIN:
        raise ValueError('CATEGORY_CONTEXT_CHANGED')
    bindings=loaded['protection-screen.json']['source_bindings']
    coverage=pinned(ROOT/'docs/audit/keyword-gap-review-coverage-2026-11-11/report.json',bindings['prior_coverage_report_sha256'])
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
    if len(protected)!=13092:raise ValueError('PRIOR_WORKBENCH_PROTECTION_CHANGED')
    for relative,pin in bindings['prior_cohort_review_sha256'].items():
        protected.update(pinned(ROOT/relative,pin)['held_phrases'])
    if len(protected)!=13261 or hashlib.sha256((HERE/'capture.json').read_bytes()).hexdigest()!=CAPTURE_PIN:
        raise ValueError('PRIOR_COHORT_PROTECTION_OR_CAPTURE_CHANGED')
    fresh=compile_protection_review(load_corpus(ROOT,capture=ROLE_EXAM_ASSET_CAPTURE),loaded['proposals.json'],
        sorted(protected),GENERIC,proposed_on='2026-11-11')
    fresh['screen']['source_bindings']=bindings
    if (not _exact(fresh['workbench'],loaded['workbench.json']) or not _exact(fresh['screen'],loaded['protection-screen.json']) or
        fresh['workbench']['summary']['dispositions']!={'HOLD': 666, 'NEGATIVE_EXACT_REVIEW': 1051, 'POSITIVE_REVIEW': 0, 'UNASSESSED': 0} or
        fresh['screen']['protected_queries']!=13881 or fresh['screen']['exact_conflict_count']):
        raise ValueError('ROLE_EXAM_ASSET_REVIEW_NOT_REPRODUCIBLE')
    rows={r['normalized_text']:r for r in fresh['workbench']['queue']}
    for text in ('questions to ask brokerage','real estate quiz for clients','real estate brochure templates',
                 'property agent recruitment','estate agent recruitment','caa atpl exams'):
        if rows[text]['disposition']!='HOLD':raise ValueError('PROTECTED_LITERAL_PROMOTED')
    return {'passed':True,'scope':'PRELIMINARY_ROLE_EXAM_ASSET_RESEARCH_NOT_ADMISSION_OR_SCOPE',
        **fresh['workbench']['summary'],'protected_queries':13881,'exact_lexical_conflicts':0,
        'authored_tests_outside_research_counts':20,'positive_library_coverage_verified':False,'deployment_authorized':False}

if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_ROLE_EXAM_ASSET_RESEARCH_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
