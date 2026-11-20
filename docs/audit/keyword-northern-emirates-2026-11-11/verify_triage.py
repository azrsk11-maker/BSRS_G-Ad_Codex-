"""Pinned preliminary 701-row research review, without geographic or serving authority."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import _exact
from supplemental_triage import load_corpus,compile_protection_review,NORTHERN_CAPTURE
PINS={'proposals.json':'e96bbe7cce033b93ad4600eec31b54813e9a637cf74363009dcb795e54fd8c24',
 'workbench.json':'eb0035f901825002009107ff05f81e2ca1c9671b54f99eafeeed0af1a12d6ed3',
 'protection-screen.json':'9f2c5bf428778f53630415d472d910302cf2e2a5cd25cfcac98c24409fa9b525'}
GENERIC=['cheap','free','monthly','owner','rent','land','farm','hotel']


def verify():
    loaded={}
    for name,pin in PINS.items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('NORTHERN_REVIEW_CHANGED')
        loaded[name]=parse_json_bytes(raw)
    fresh=compile_protection_review(load_corpus(ROOT,capture=NORTHERN_CAPTURE),
        loaded['proposals.json'],[],GENERIC,proposed_on='2026-11-11')
    if (not _exact(fresh['workbench'],loaded['workbench.json']) or
        not _exact(fresh['screen'],loaded['protection-screen.json']) or
        fresh['workbench']['summary']['dispositions']!={
            'HOLD':407,'NEGATIVE_EXACT_REVIEW':0,'POSITIVE_REVIEW':294,'UNASSESSED':0}):
        raise ValueError('NORTHERN_REVIEW_NOT_REPRODUCIBLE')
    return {'passed':True,'scope':'PRELIMINARY_PROPERTY_RESEARCH_NOT_SERVICE_SCOPE_OR_ADMISSION',
        **fresh['workbench']['summary'],'hypothetical_generic_tests':len(GENERIC),
        'protected_observed_literals':fresh['screen']['protected_queries'],
        'master_rows_added':0,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_NORTHERN_RESEARCH_ONLY','deployment_authorized':False}))
        raise SystemExit(1)
