"""Pinned preliminary purchase-readiness review; no finance or master authority."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,READINESS_CAPTURE
PINS={'proposals.json':'9bfe7abc7e5e6d9e69bb9b959aee316f0d5d40d8fa83eb11a5d0c2c4f38c8e0f',
      'workbench.json':'835894b843b9c80e27468cf0ddfa1ab5104a227dca6841f7e18126523294ea4d',
      'protection-screen.json':'e52141c776d3ebd32a19eaf51cb9a051d741aa79de5b9b5bbf4e44d64d688711'}
GENERIC=['mortgage','registration','fees','price','low price','down payment','indian rupees','inr']


def verify():
    loaded={}
    for name,pin in PINS.items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('READINESS_REVIEW_CHANGED')
        loaded[name]=parse_json_bytes(raw)
    review=compile_protection_review(load_corpus(ROOT,capture=READINESS_CAPTURE),
        loaded['proposals.json'],[],GENERIC,proposed_on='2026-11-11')
    if (not _exact(review['workbench'],loaded['workbench.json']) or
        not _exact(review['screen'],loaded['protection-screen.json']) or
        review['workbench']['summary']['dispositions']!={
            'HOLD':5,'NEGATIVE_EXACT_REVIEW':0,'POSITIVE_REVIEW':25,'UNASSESSED':0}):
        raise ValueError('READINESS_REVIEW_NOT_REPRODUCIBLE')
    return {'passed':True,'scope':'PRELIMINARY_PURCHASE_READINESS_NOT_FINANCE_OR_ADMISSION',
        **review['workbench']['summary'],'hypothetical_generic_tests':len(GENERIC),
        'protected_observed_literals':review['screen']['protected_queries'],
        'master_rows_added':0,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_READINESS_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
