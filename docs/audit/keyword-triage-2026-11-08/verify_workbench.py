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
  "proposals.json": "fdc04f71def945a359c3d05cdcb2364f26b863a6eeeee9c81f3453501e756bd7",
  "workbench.json": "ea172a9112ce7c20d88040e2af5c8f0864264771a8a9103a5ec9dfdee5f3b575"
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
