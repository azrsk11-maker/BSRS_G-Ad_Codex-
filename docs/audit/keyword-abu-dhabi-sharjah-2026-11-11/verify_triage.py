"""Pinned preliminary two-emirate review; never business or serving authority."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,ABU_SHARJAH_CAPTURE
PINS={'proposals.json':'91e67eccf83dda044425ebc4ddce60d0a52a9823a088ad1dc9f1e610095ac689',
 'workbench.json':'ba1fa77c48953f73f0bce0bf4a1124b8991afa636ea775945a611d288e4ce2b4',
 'protection-screen.json':'e61ff996dd4bf240ff41d9d34b5f65af3251dc03d8e794d7bc9aeb9999b36ef1'}
GENERIC=['cheap','free','monthly','owner','rent','commercial','pool','serviced','hotel','expat']


def verify():
    loaded={}
    for name,pin in PINS.items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('ABU_SHARJAH_REVIEW_CHANGED')
        loaded[name]=parse_json_bytes(raw)
    fresh=compile_protection_review(load_corpus(ROOT,capture=ABU_SHARJAH_CAPTURE),
        loaded['proposals.json'],[],GENERIC,proposed_on='2026-11-11')
    if (not _exact(fresh['workbench'],loaded['workbench.json']) or
        not _exact(fresh['screen'],loaded['protection-screen.json']) or
        fresh['workbench']['summary']['dispositions']!={
            'HOLD':1366,'NEGATIVE_EXACT_REVIEW':0,'POSITIVE_REVIEW':896,'UNASSESSED':0}):
        raise ValueError('ABU_SHARJAH_REVIEW_NOT_REPRODUCIBLE')
    return {'passed':True,'scope':'PRELIMINARY_PROPERTY_RESEARCH_NOT_SCOPE_OR_ADMISSION',
        **fresh['workbench']['summary'],'hypothetical_generic_tests':len(GENERIC),
        'protected_observed_literals':fresh['screen']['protected_queries'],
        'master_rows_added':0,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_ABU_SHARJAH_RESEARCH_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
