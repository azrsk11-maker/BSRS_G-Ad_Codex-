"""Pinned transcription of the existing conditional owner-intent narrative."""
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_triage import load_corpus,compile_workbench,SUPPLY_CAPTURE
PINS={'proposals.json':'84261d3eefb8936b7f7a9a0102e02386f994bb370e8aebbd620700b9f602f5b3',
      'workbench.json':'b7118852ef5592db4501f28ae14201dc7715bca5f1ca5bf8036d66e6b5fb9cc2'}
NARRATIVE_PIN='e7834b5f30f72afdafd3ce1e8caf0252c2b0eb7f5ce51e50e9a0ca3ad5ffaf38'


def verify():
    if hashlib.sha256((HERE/'INTENT_REVIEW.md').read_bytes()).hexdigest()!=NARRATIVE_PIN:
        raise ValueError('EXISTING_NARRATIVE_CHANGED')
    loaded={}
    for name,pin in PINS.items():
        raw=(HERE/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('SUPPLY_REVIEW_CHANGED')
        loaded[name]=parse_json_bytes(raw)
    fresh=compile_workbench(load_corpus(ROOT,capture=SUPPLY_CAPTURE),loaded['proposals.json'],proposed_on='2026-11-11')
    if fresh!=loaded['workbench.json'] or fresh['summary']['dispositions']!={
        'HOLD':19,'NEGATIVE_EXACT_REVIEW':0,'POSITIVE_REVIEW':12,'UNASSESSED':0}:
        raise ValueError('SUPPLY_REVIEW_NOT_REPRODUCIBLE')
    return {'passed':True,'scope':'CONDITIONAL_NARRATIVE_TRANSCRIPTION_NOT_ADMISSION',**fresh['summary'],
            'commercial_owner_phrases_held':2,'deployment_authorized':False}


if __name__=='__main__':
    try:print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'CONDITIONAL_NARRATIVE_TRANSCRIPTION_NOT_ADMISSION','deployment_authorized':False}))
        raise SystemExit(1)
