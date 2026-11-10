"""Fixed, raw-pinned observed-source reconciliation. No arbitrary file inputs."""
import hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import verify_capture,_exact
from discovery_review_coverage import reconcile

REGISTRY=[
 ('keyword-discovery-2026-11-08','4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268',
  'keyword-triage-2026-11-08','1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477'),
 ('keyword-discovery-supply-2026-11-08','279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7',
  'keyword-discovery-supply-2026-11-08','b7118852ef5592db4501f28ae14201dc7715bca5f1ca5bf8036d66e6b5fb9cc2'),
 ('keyword-employment-education-2026-11-10','8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f',
  'keyword-employment-education-2026-11-10','b22f03d89237aa4467b2e7d9cc8a74c36882cdee104cabb85d55f8150e6f139a'),
 ('keyword-employment-broad-2026-11-10','bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864',
  'keyword-employment-broad-2026-11-10','c93745c44b95b530b8c4dbcd1ac6f7e4b7b04cdd8eabfacaaf9a6578b1fa2002'),
 ('keyword-exclusions-2026-11-10','1c47ca4c73590f0d5755b7520a08a6d2cd804295d2af58314bab4ad268804fc4',
  'keyword-exclusions-2026-11-10','585ea863a978e63537b440b5eb6feaedaf236d07f05878d19c7f7ce267ef4a58')]
CASES='docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
CASES_PIN='ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43'
REPORT_PIN='61251134d6b248366ec2872819146cda98955a9929c5e7e4ce13d752127dceb9'
ORIGINAL_VERIFIER_PIN='d57fbe7f95d74270f0880a63d59e1776afd3e3c68a8cfd154ca399cd9ff63cee'


def pinned(path,pin):
    with path.open('rb') as stream:raw=stream.read(64*1024*1024+1)
    if len(raw)>64*1024*1024 or hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('PINNED_INPUT_CHANGED')
    return parse_json_bytes(raw)


def build():
    captures,reviews,manifest_pins=[],[],{}
    for folder,manifest_pin,review_folder,review_pin in REGISTRY:
        relative='docs/audit/'+folder
        path=ROOT/relative
        index=pinned(path/'capture.json',manifest_pin)
        if folder=='keyword-discovery-2026-11-08':
            # The immutable original manifest uses its original four counter
            # names, not the later five-field duplicate/overlap schema.
            code=path/'verify_capture.py'
            if hashlib.sha256(code.read_bytes()).hexdigest()!=ORIGINAL_VERIFIER_PIN:
                raise ValueError('ORIGINAL_CAPTURE_VERIFIER_CHANGED')
            spec=importlib.util.spec_from_file_location('original_fixed_capture_verifier',code)
            verifier=importlib.util.module_from_spec(spec);spec.loader.exec_module(verifier)
            if verifier.verify().get('passed') is not True:raise ValueError('ORIGINAL_CAPTURE_FAILED')
        else:
            verify_capture(path,{'capture.json':manifest_pin,**{r['file']:r['sha256'] for r in index['source_files']}})
        manifest_pins[relative+'/capture.json']=manifest_pin
        for item in index['source_files']:
            captures.append({'file':relative+'/'+item['file'],'sha256':item['sha256'],
                'captured_on':index['capture_date_dubai'],'batch':pinned(path/item['file'],item['sha256'])})
        review_file='docs/audit/'+review_folder+'/workbench.json'
        reviews.append({'file':review_file,'sha256':review_pin,'workbench':pinned(ROOT/review_file,review_pin)})
    cases=pinned(ROOT/CASES,CASES_PIN)
    if (cases['scope']!='AUTHORED_PROTECTED_INTENT_TESTS_NOT_OBSERVED_QUERIES' or
        cases['counts_toward_research_or_masters'] is not False or
        cases['asserts_inventory_or_service_availability'] is not False or len(cases['cases'])!=20):
        raise ValueError('AUTHORED_CASE_AUTHORITY')
    master=cases['master_source']
    if master!={'file':'docs/google-ads/BlackSwan_Real_Estate_Algorithmic_Master_Plan_v3.md',
                'sha256':'8b0f7eafc4572c6ba7421b891285e9a324e96d53ca2507b58ef6d0e540efd7a4'} or hashlib.sha256((ROOT/master['file']).read_bytes()).hexdigest()!=master['sha256']:
        raise ValueError('AUTHORED_CASE_MASTER_CHANGED')
    result=reconcile(captures,reviews,[r['query'] for r in cases['cases']])
    result['source_bindings']={'capture_manifests_sha256':manifest_pins,
        'capture_files_sha256':{r['file']:r['sha256'] for r in captures},
        'review_workbenches_sha256':{r['file']:r['sha256'] for r in reviews},
        'authored_protection_cases':{'file':CASES,'sha256':CASES_PIN},'master_source':master,
        'original_capture_verifier_sha256':ORIGINAL_VERIFIER_PIN}
    return result


def verify():
    saved=pinned(HERE/'report.json',REPORT_PIN);fresh=build()
    if not _exact(saved,fresh) or not fresh['all_phrases_have_preliminary_assessments']:
        raise ValueError('SOURCE_REVIEW_COVERAGE_INCOMPLETE_OR_CHANGED')
    return {'passed':True,**{k:v for k,v in fresh.items() if k not in {'source_bindings','cross_review_overlap_phrases'}},
        'cross_review_overlap_phrase_count':len(fresh['cross_review_overlap_phrases'])}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_SOURCE_REVIEW_RECONCILIATION_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
