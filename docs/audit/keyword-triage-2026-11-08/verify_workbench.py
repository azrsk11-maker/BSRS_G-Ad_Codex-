"""Reproduce the unapproved triage queue from pinned observed source records."""
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from triage_workbench import load_corpus,compile_workbench
from keyword_audit import parse_json_bytes
PINS={
  "proposals.json": "e5e5375f451eb8c92b721105efe8cdadf72d4c9101ddae58e96a66adc9a307e5",
  "workbench.json": "1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477"
}
def verify():
    values={}
    for filename,expected in PINS.items():
        content=(HERE/filename).read_bytes()
        if hashlib.sha256(content).hexdigest()!=expected: raise ValueError('Triage bytes changed')
        values[filename]=parse_json_bytes(content)
    fresh=compile_workbench(load_corpus(ROOT),values['proposals.json'])
    if fresh!=values['workbench.json']: raise ValueError('Workbench does not reproduce from observed sources')
    return {'passed':True,'scope':'PRELIMINARY_TRIAGE_NOT_ADMISSION','unique_phrases':fresh['summary']['unique_phrases'],'source_occurrences':fresh['summary']['source_occurrences'],'dispositions':fresh['summary']['dispositions'],'reviewed_positive':0,'reviewed_negative':0,'deployment_authorized':False}
if __name__=='__main__':
    try: print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_TRIAGE_NOT_ADMISSION','deployment_authorized':False}));raise SystemExit(1)
