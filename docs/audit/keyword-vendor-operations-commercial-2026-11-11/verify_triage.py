"""Pinned complete preliminary review; no admission or live authority."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_triage import load_corpus,compile_protection_review,VENDOR_OPERATIONS_CAPTURE
from triage_protection import derive
PINS={'proposals.json': 'c45fb57383057e4de38f34da573aab32ee15d2254c87112121bccc6edaac0640', 'workbench.json': '10cd054e471948b21db06203cec7293145396a2f9019796b0a8228eac0c39701', 'protection-screen.json': 'ddebf84bb59925ae4dc5f32fa086ee7a287e8ae8cdd5374db28f3b3e8ee1dc8b'}
BINDINGS={'prior_workbench_sha256': {'docs/audit/keyword-triage-2026-11-08/workbench.json': '1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477', 'docs/audit/keyword-discovery-supply-2026-11-08/workbench.json': 'b7118852ef5592db4501f28ae14201dc7715bca5f1ca5bf8036d66e6b5fb9cc2', 'docs/audit/keyword-employment-education-2026-11-10/workbench.json': 'b22f03d89237aa4467b2e7d9cc8a74c36882cdee104cabb85d55f8150e6f139a', 'docs/audit/keyword-employment-broad-2026-11-10/workbench.json': 'c93745c44b95b530b8c4dbcd1ac6f7e4b7b04cdd8eabfacaaf9a6578b1fa2002', 'docs/audit/keyword-exclusions-2026-11-10/workbench.json': '585ea863a978e63537b440b5eb6feaedaf236d07f05878d19c7f7ce267ef4a58', 'docs/audit/keyword-property-readiness-2026-11-11/workbench.json': '835894b843b9c80e27468cf0ddfa1ab5104a227dca6841f7e18126523294ea4d', 'docs/audit/keyword-northern-emirates-2026-11-11/workbench.json': 'eb0035f901825002009107ff05f81e2ca1c9671b54f99eafeeed0af1a12d6ed3', 'docs/audit/keyword-abu-dhabi-sharjah-2026-11-11/workbench.json': 'ba1fa77c48953f73f0bce0bf4a1124b8991afa636ea775945a611d288e4ce2b4', 'docs/audit/keyword-developer-employment-2026-11-11/workbench.json': 'a7cb70063367d08f4518e42aaf7f230ae8c872f111a1eaa0069e76dc088b3a99', 'docs/audit/keyword-occupational-education-2026-11-11/workbench.json': '4487755de36391aa59f5bdb06d8bb72edb3c48a8f46ca2a89a6d733248daa1b0', 'docs/audit/keyword-employment-lifecycle-2026-11-11/workbench.json': 'd55c2ba4f03fe8f91cc49477f938cd0eae0ac638b1667709de422ab540404449', 'docs/audit/keyword-gap-research-2026-11-11/workbench.json': '73da881c9b8ccea784178fd204a6e1dbb22dcdf309671c6d6f32cb51d1fbfd42', 'docs/audit/keyword-role-exam-assets-2026-11-11/workbench.json': '5c760a1135b7ef0694efe04e4305025a1c2fa44904402a20e0172707bcd333e5'}, 'reviewed_membership': {'file': 'tools/keyword-system/data/negative-research-index.json', 'sha256': 'ff04733c369954f66d562dc14a263bf40b58c7b14877332767f309472cb5e525'}, 'prior_coverage_report': {'file': 'docs/audit/keyword-role-review-coverage-2026-11-11/report.json', 'sha256': '7b7ac5aa4d8dd65dafe80fd6a1409a0edddb7eecd12c88a44b442646ac2e6c4c'}, 'authored_protection_cases': {'file': 'docs/audit/keyword-exclusions-2026-11-10/protected-cases.json', 'sha256': 'ebc12f690c48a846b21d0f43cda3fe0e860e597f8f63215fe13abffebd85bf43'}, 'baseline_protected_text_sha256': '9dd6c9e60baac7acdc2b21de288fbe7fb931ae5fd60af561d02f6d4086cbdf53', 'capture_manifest_sha256': 'cd18511e136d67cde9f7cd704731423670a43a9e700cc29df110c4c1cd7d8bff', 'base_current_record_sha256': 'c969b6e633462f9f1c7567449e6912b598b8fdb7b848b9e6059258c6441e0601'}
PRIMARY_CONTEXT_PIN='0106405101f6f7ad4b028f512ccf3f75e7fd58bc1cd7988d43063e39795b535d'
PROJECTION_CODE_PIN='fde6f16ba5fc6eab9ccf783289ca69b8f090298a54d4db3dd9cb4410f509ddc8'
GENERIC=['software', 'crm', 'jobs', 'salary', 'property', 'rent', 'rental', 'application', 'portal', 'payment', 'inspection', 'investment', 'office', 'warehouse', 'commercial', 'housing', 'hire', 'free']

def pinned(relative,pin):
    raw=(ROOT/relative).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('REVIEW_INPUT_CHANGED')
    return parse_json_bytes(raw)

def protection_inputs():
    prior=pinned(BINDINGS['prior_coverage_report']['file'],BINDINGS['prior_coverage_report']['sha256'])
    if prior['source_bindings']['review_workbenches_sha256']!=BINDINGS['prior_workbench_sha256']:
        raise ValueError('PRIOR_REVIEW_REGISTRY_CHANGED')
    if hashlib.sha256((ROOT/'tools/keyword-system/triage_protection.py').read_bytes()).hexdigest()!=PROJECTION_CODE_PIN:
        raise ValueError('PROTECTION_PROJECTION_CODE_CHANGED')
    workbenches=[pinned(p,h) for p,h in BINDINGS['prior_workbench_sha256'].items()]
    member=pinned(BINDINGS['reviewed_membership']['file'],BINDINGS['reviewed_membership']['sha256'])
    cases=pinned(BINDINGS['authored_protection_cases']['file'],BINDINGS['authored_protection_cases']['sha256'])
    protected=derive(workbenches,member['eligible_keyword_ids'],[c['query'] for c in cases['cases']])
    raw=json.dumps(protected,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf8')
    if hashlib.sha256(raw).hexdigest()!=BINDINGS['baseline_protected_text_sha256'] or len(protected)!=13905:
        raise ValueError('BASELINE_PROTECTION_PROJECTION_CHANGED')
    return protected

def verify():
    if hashlib.sha256((HERE/'capture.json').read_bytes()).hexdigest()!=BINDINGS['capture_manifest_sha256'] or hashlib.sha256((HERE/'PRIMARY_CONTEXT.md').read_bytes()).hexdigest()!=PRIMARY_CONTEXT_PIN:
        raise ValueError('CAPTURE_OR_CONTEXT_CHANGED')
    saved={name:pinned((HERE.relative_to(ROOT)/name).as_posix(),pin) for name,pin in PINS.items()}
    built=compile_protection_review(load_corpus(ROOT,capture=VENDOR_OPERATIONS_CAPTURE),saved['proposals.json'],protection_inputs(),GENERIC,proposed_on='2026-11-11')
    built['screen']['source_bindings']=BINDINGS
    if built['workbench']!=saved['workbench.json'] or built['screen']!=saved['protection-screen.json']:
        raise ValueError('REVIEW_NOT_REPRODUCIBLE')
    summary=built['workbench']['summary']
    if summary['dispositions']!={'HOLD':1340,'NEGATIVE_EXACT_REVIEW':2314,'POSITIVE_REVIEW':118,'UNASSESSED':0} or built['screen']['protected_queries']!=15213 or built['screen']['exact_conflict_count']!=0:
        raise ValueError('COMPLETE_REVIEW_OR_PROTECTION_CHANGED')
    rows={r['normalized_text']:r for r in built['workbench']['queue']}
    for text in ('appfolio maintenance request','buildium resident portal','rental application software','hiring a management company for rental property','real estate data analyst job description','crm residential management','property management software software','cold storage for rent in dubai'):
        if rows[text]['disposition']!='HOLD':raise ValueError('VALUABLE_OR_UNCERTAIN_INTENT_LOST')
    for text in ('property management software','real estate accountant jobs'):
        if rows[text]['disposition']!='NEGATIVE_EXACT_REVIEW':raise ValueError('EXPLICIT_PRODUCT_OR_JOB_ASSESSMENT_CHANGED')
    for text,service in [('commercial villa for rent in dubai','commercial_leasing'),('apartments for rent in dubai industrial city','residential_rental')]:
        if rows[text]['disposition']!='POSITIVE_REVIEW' or rows[text]['assessment']['possible_services']!=[service]:raise ValueError('PROPERTY_INTENT_OR_PLACE_ROLE_CHANGED')
    return {'passed':True,'scope':'COMPLETE_PRELIMINARY_AI_REVIEW_NOT_ADMISSION',**summary,'protected_queries':15213,'exact_conflicts':0,'deployment_authorized':False}

if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_REVIEW_HELD','deployment_authorized':False}))
        raise SystemExit(1)
