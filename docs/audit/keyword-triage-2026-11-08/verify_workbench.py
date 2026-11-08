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
  "proposals.json": "31ef2bc99e54038d2f22d3610b1cf682fce9f1c06441b5874d06ae39bb2a176a",
  "workbench.json": "8324fba806361e8f26ad933049ba5a6a19b53a56fe268c284691bee2f2168405"
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
