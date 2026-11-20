"""Fixed, raw-pinned observed-source reconciliation. No arbitrary file inputs."""
import hashlib,importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import verify_capture,_exact
from discovery_review_coverage import reconcile

REGISTRY=[('keyword-discovery-2026-11-08', '4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268', 'keyword-triage-2026-11-08', '1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477'), ('keyword-discovery-supply-2026-11-08', '279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7', 'keyword-discovery-supply-2026-11-08', 'b7118852ef5592db4501f28ae14201dc7715bca5f1ca5bf8036d66e6b5fb9cc2'), ('keyword-employment-education-2026-11-10', '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f', 'keyword-employment-education-2026-11-10', 'b22f03d89237aa4467b2e7d9cc8a74c36882cdee104cabb85d55f8150e6f139a'), ('keyword-employment-broad-2026-11-10', 'bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864', 'keyword-employment-broad-2026-11-10', 'c93745c44b95b530b8c4dbcd1ac6f7e4b7b04cdd8eabfacaaf9a6578b1fa2002'), ('keyword-exclusions-2026-11-10', '1c47ca4c73590f0d5755b7520a08a6d2cd804295d2af58314bab4ad268804fc4', 'keyword-exclusions-2026-11-10', '585ea863a978e63537b440b5eb6feaedaf236d07f05878d19c7f7ce267ef4a58'), ('keyword-property-readiness-2026-11-11', '81a1c496372d528668f42dc1056d67d29911a3951bee23ac0dc2ae878522539f', 'keyword-property-readiness-2026-11-11', '835894b843b9c80e27468cf0ddfa1ab5104a227dca6841f7e18126523294ea4d'), ('keyword-northern-emirates-2026-11-11', '55fb083ab6f73b57ed7ae18815b64eed22f6c8e2c4caec173bef6405b7b04a83', 'keyword-northern-emirates-2026-11-11', 'eb0035f901825002009107ff05f81e2ca1c9671b54f99eafeeed0af1a12d6ed3'), ('keyword-abu-dhabi-sharjah-2026-11-11', '719d1bcdce7620740266046ed24705b6c05fdf521cdb67e9be3b6a014023f62d', 'keyword-abu-dhabi-sharjah-2026-11-11', 'ba1fa77c48953f73f0bce0bf4a1124b8991afa636ea775945a611d288e4ce2b4'), ('keyword-developer-employment-2026-11-11', 'a89397314f9565d5f2e0027c8d19a7b6b55b9f738f1c5272f275d2716ecdc06f', 'keyword-developer-employment-2026-11-11', 'a7cb70063367d08f4518e42aaf7f230ae8c872f111a1eaa0069e76dc088b3a99'), ('keyword-occupational-education-2026-11-11', '1e30f171310155e76229d35922e951aed2965def632af757f3c8d30386eb6217', 'keyword-occupational-education-2026-11-11', '4487755de36391aa59f5bdb06d8bb72edb3c48a8f46ca2a89a6d733248daa1b0'), ('keyword-employment-lifecycle-2026-11-11', '94dfa8a6fe28a0ed76b865a5a230c4404a5bc8c25ecfa0cd9fae6f6311fa78c1', 'keyword-employment-lifecycle-2026-11-11', 'd55c2ba4f03fe8f91cc49477f938cd0eae0ac638b1667709de422ab540404449'), ('keyword-gap-research-2026-11-11', '5ccdbf45f7d9b4408792a9f241e5d9f8b90f1e612620a3770c6c3e03881dc3f9', 'keyword-gap-research-2026-11-11', '73da881c9b8ccea784178fd204a6e1dbb22dcdf309671c6d6f32cb51d1fbfd42'), ('keyword-role-exam-assets-2026-11-11', 'ec254a5df735685452ce344da2201c6d44ef87b5775479cbac2e2b10c68d0092', 'keyword-role-exam-assets-2026-11-11', '5c760a1135b7ef0694efe04e4305025a1c2fa44904402a20e0172707bcd333e5'), ('keyword-vendor-operations-commercial-2026-11-11', 'cd18511e136d67cde9f7cd704731423670a43a9e700cc29df110c4c1cd7d8bff', 'keyword-vendor-operations-commercial-2026-11-11', '10cd054e471948b21db06203cec7293145396a2f9019796b0a8228eac0c39701')]
CASES='docs/audit/keyword-exclusions-2026-11-10/protected-cases.json'
CASES_PIN='ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43'
REPORT_PIN='42d02347ba05fccc0f636bec212b36acd80491f2becb2575c9aecbef33672210'
IMPACT_PIN='493b4360dd2037e098521971027535fda355cc055eb6650e99ef41308fa4245d'
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



def build_impact(report,data=None,at=None,*,with_protected=False):
    from datetime import date
    from collections import Counter
    import current_negative_library as current
    import negative_admission as first
    from keyword_audit import audit
    when=date(2026,11,11) if at is None else at
    data=current.reconstruct_registered(ROOT,at=when) if data is None else data
    expected=pinned(ROOT/'docs/audit/keyword-vendor-operations-commercial-2026-11-11/protection-screen.json','ddebf84bb59925ae4dc5f32fa086ee7a287e8ae8cdd5374db28f3b3e8ee1dc8b')['source_bindings']
    if hashlib.sha256(first.canonical(data['records'])).hexdigest()!=expected['base_current_record_sha256']:
        raise ValueError('REGISTERED_CURRENT_BASE_CHANGED')
    index=pinned(ROOT/current.INDEX,current.INDEX_PIN)
    if [r['keyword_id'] for r in data['records']]!=index['eligible_keyword_ids'] or len(data['records'])!=8035:
        raise ValueError('ALL_CURRENT_RECORDS_REQUIRED')
    for group in ('capture_manifests_sha256','capture_files_sha256'):
        for relative,pin in report['source_bindings'][group].items():
            raw=(ROOT/relative).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('LATEST_CAPTURE_CHANGED')
    protected={r['text']:r for r in data['protected_queries']}
    for relative,pin in report['source_bindings']['review_workbenches_sha256'].items():
        for row in pinned(ROOT/relative,pin)['queue']:
            if row['disposition']=='NEGATIVE_EXACT_REVIEW':continue
            text=row['normalized_text']
            if text not in protected:
                protected[text]={'query_id':'BSRE-Q-'+hashlib.sha256(text.encode()).hexdigest()[:24],'text':text,
                    'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
                    'evidence_ref':relative+'#'+row['queue_id'],'reviewed_on':'2026-11-11','valid_until':'2026-12-11'}
    result=audit('negative',data['records'],data['sources'],data['campaigns'],data['campaign_context'],list(protected.values()),when)
    impact={'scope':'LATEST_REVIEW_SCREEN_OF_ALL_REGISTERED_CURRENT_RESEARCH_NOT_NEW_ADMISSION',
        'registered_input_rows':result['input_rows'],'latest_review_eligible_rows':result['reviewed_eligible_rows'],
        'latest_deficit':result['deficit'],'latest_excluded_rows':result['excluded_rows'],
        'protected_queries':len(protected),'protected_conflicts':result['protected_conflicts'],
        'latest_approval_hold_counts':dict(Counter(reason for row in result['records'] for reason in row['deployment_holds'])),
        'approved_exclusion_rows':result['approved_exclusion_rows'],'base_current_records_sha256':expected['base_current_record_sha256'],
        'registered_index':{'file':current.INDEX,'sha256':current.INDEX_PIN},'latest_coverage_sha256':REPORT_PIN,
        'historical_rows_rewritten':False,'master_additions':0,'admission_held':bool(result['protected_conflicts']),
        'independent_review_verified':False,'positive_library_coverage_verified':False,'deployment_authorized':False}
    return {'impact':impact,'protected_queries':list(protected.values())} if with_protected else impact

def verify():
    saved=pinned(HERE/'report.json',REPORT_PIN);fresh=build()
    if not _exact(saved,fresh) or not fresh['all_phrases_have_preliminary_assessments']:raise ValueError('COVERAGE_INCOMPLETE_OR_CHANGED')
    prior=pinned(ROOT/'docs/audit/keyword-role-review-coverage-2026-11-11/report.json','7b7ac5aa4d8dd65dafe80fd6a1409a0edddb7eecd12c88a44b442646ac2e6c4c')
    previous={r['normalized_text'] for r in prior['cross_review_overlap_phrases'] if r['dispositions_agree'] is not True}
    current={r['normalized_text'] for r in fresh['cross_review_overlap_phrases'] if r['dispositions_agree'] is not True}
    if not previous<=current:raise ValueError('PRIOR_DISAGREEMENT_LOST')
    impact=pinned(HERE/'admitted-master-impact.json',IMPACT_PIN)
    if not _exact(impact,build_impact(fresh)):raise ValueError('CURRENT_RESEARCH_SCREEN_CHANGED')
    return {'passed':True,'latest_master_impact':impact,**{k:v for k,v in fresh.items() if k not in {'source_bindings','cross_review_overlap_phrases'}},'cross_review_overlap_phrase_count':len(fresh['cross_review_overlap_phrases'])}

if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'ALL_CURRENT_RESEARCH_SCREEN_HELD','deployment_authorized':False}));raise SystemExit(1)
