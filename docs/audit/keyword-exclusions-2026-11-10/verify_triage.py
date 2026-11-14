"""Reproduce complete unapproved review and explicitly authored protection tests."""
from datetime import date
import hashlib,json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import normalize,parse_json_bytes
from supplemental_triage import load_corpus,compile_protection_review,EXCLUSION_CAPTURE
PINS={
 'proposals.json':'20e6c1b0c54b3f021aa12211b1118f30682944f88b1b7bf74643c2af865ded88',
 'workbench.json':'585ea863a978e63537b440b5eb6feaedaf236d07f05878d19c7f7ce267ef4a58',
 'protection-screen.json':'6a8f623bb77907176b5ead60f892289e72a84856194173f0de3455730dcc6e1b',
 'protected-cases.json':'ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43'}
PRIOR={
 'keyword-triage-2026-11-08/workbench.json':'1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477',
 'keyword-employment-education-2026-11-10/workbench.json':'b22f03d89237aa4467b2e7d9cc8a74c36882cdee104cabb85d55f8150e6f139a',
 'keyword-employment-broad-2026-11-10/workbench.json':'c93745c44b95b530b8c4dbcd1ac6f7e4b7b04cdd8eabfacaaf9a6578b1fa2002'}
CAPTURE_PIN='1c47ca4c73590f0d5755b7520a08a6d2cd804295d2af58314bab4ad268804fc4'
MASTER='docs/google-ads/BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md'
MASTER_PIN='8b0f7eafc4572c6ba7421b891285e9a324e96d53ca2507b58ef6d0e540efd7a4'
GENERICS=['rent','rental','lease','cheap','free','commercial','office','car','software','crm','stock','photo','repair','brand','dubai']


def need(ok,code):
    if not ok:raise ValueError(code)


def verify():
    loaded,protected={},set()
    for name,pin in PINS.items():
        blob=(HERE/name).read_bytes()
        need(hashlib.sha256(blob).hexdigest()==pin,'REVIEW_BYTES_CHANGED')
        loaded[name]=parse_json_bytes(blob)
    for relative,pin in PRIOR.items():
        blob=(ROOT/'docs/audit'/relative).read_bytes()
        need(hashlib.sha256(blob).hexdigest()==pin,'PRIOR_REVIEW_CHANGED')
        protected.update(parse_json_bytes(blob)['diagnostics']['protected_phrases'])
    master=(ROOT/MASTER).read_bytes()
    need(hashlib.sha256(master).hexdigest()==MASTER_PIN,'MASTER_SOURCE_CHANGED')
    cases=loaded['protected-cases.json']
    need(set(cases)=={'version','scope','authored_on','master_source','counts_toward_research_or_masters',
                     'asserts_inventory_or_service_availability','cases'},'PROTECTION_FIELDS')
    need(type(cases['version']) is int and cases['version']==1 and
         cases['scope']=='AUTHORED_PROTECTED_INTENT_TESTS_NOT_OBSERVED_QUERIES' and
         cases['counts_toward_research_or_masters'] is False and
         cases['asserts_inventory_or_service_availability'] is False,'PROTECTION_AUTHORITY')
    need(cases['master_source']=={'file':MASTER,'sha256':MASTER_PIN},'PROTECTION_SOURCE')
    day=date.fromisoformat(cases['authored_on'])
    need(day.isoformat()==cases['authored_on'] and day<=date.today(),'PROTECTION_DATE')
    rows=cases['cases'];need(isinstance(rows,list) and len(rows)==20,'PROTECTION_COUNT')
    queries=[]
    for i,row in enumerate(rows,1):
        need(set(row)=={'id','basis','query'} and row['id']==f'PROTECT-{i:02d}' and
             isinstance(row['query'],str) and bool(row['query'].strip()),'PROTECTION_CASE')
        basis='MASTER_EXAMPLE' if i<=8 else 'AUTHORED_COUNTEREXAMPLE'
        need(row['basis']==basis,'PROTECTION_BASIS')
        if basis=='MASTER_EXAMPLE':need(row['query'] in master.decode('utf-8'),'MASTER_EXAMPLE_MISSING')
        queries.append(row['query'])
    need(len(set(map(normalize,queries)))==20,'PROTECTION_DUPLICATE')
    protected.update(queries)
    need(hashlib.sha256((HERE/'capture.json').read_bytes()).hexdigest()==CAPTURE_PIN,'CAPTURE_CHANGED')
    fresh=compile_protection_review(load_corpus(ROOT,capture=EXCLUSION_CAPTURE),loaded['proposals.json'],
                                    sorted(protected),GENERICS)
    fresh['screen']['source_bindings']={'prior_workbench_sha256':PRIOR,'capture_manifest_sha256':CAPTURE_PIN,
        'authored_protected_cases_sha256':PINS['protected-cases.json'],'master_source_sha256':MASTER_PIN}
    need(fresh['workbench']==loaded['workbench.json'] and fresh['screen']==loaded['protection-screen.json'],
         'REVIEW_NOT_REPRODUCIBLE')
    summary=fresh['workbench']['summary']
    need(summary['unique_phrases']==summary['source_occurrences']==2343 and summary['dispositions']=={
        'HOLD':345,'NEGATIVE_EXACT_REVIEW':1998,'POSITIVE_REVIEW':0,'UNASSESSED':0},'REVIEW_COVERAGE')
    need(len(fresh['workbench']['diagnostics']['protected_phrases'])==345 and
         fresh['screen']['protected_queries']==4016 and fresh['screen']['exact_conflict_count']==0,
         'PROVISIONAL_PROTECTION_FAILED')
    return {'passed':True,'scope':'PRELIMINARY_TRIAGE_NOT_ADMISSION',**summary,
        'protected_queries':4016,'authored_test_cases':20,'exact_lexical_conflicts':0,
        'positive_library_coverage_verified':False,'scope_verified':False,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_TRIAGE_NOT_ADMISSION','deployment_authorized':False}))
        raise SystemExit(1)
