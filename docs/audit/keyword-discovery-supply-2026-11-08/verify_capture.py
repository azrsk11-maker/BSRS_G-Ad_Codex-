"""Verify separate supply capture and overlap; no inherited review or writes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import verify_capture,overlap_report
PINS={
  "sellers.json": "ad59fa643c50af4b2e03782428979a841e64ed17557f8e376280fe57f151781e",
  "landlords.json": "a1c5ab276d12b76541508ad00587a9d2c3f0ddd01b75c7be63c842bfe3690c11",
  "capture.json": "279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7"
}
OVERLAP_PIN='1379da9e835e647f6df40d9c52c384a6d62ee6eb7fcc1a5e000b94ba8f21b776'
ORIGINAL_TRIAGE_PINS={
  "proposals.json": "e5e5375f451eb8c92b721105efe8cdadf72d4c9101ddae58e96a66adc9a307e5",
  "workbench.json": "1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477"
}

def need(ok,code):
    if not ok:raise ValueError(code)

def verify(sources=None):
    result=verify_capture(HERE,PINS,sources)
    original=ROOT/'docs/audit/keyword-discovery-2026-11-08'
    spec=importlib.util.spec_from_file_location('original_discovery_check',original/'verify_capture.py')
    check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check);check.verify()
    for name,pin in ORIGINAL_TRIAGE_PINS.items():
        need(hashlib.sha256((ROOT/'docs/audit/keyword-triage-2026-11-08'/name).read_bytes()).hexdigest()==pin,'ORIGINAL_TRIAGE_CHANGED')
    old_index=parse_json_bytes((original/'capture.json').read_bytes())
    new_index=parse_json_bytes((HERE/'capture.json').read_bytes())
    old_batches=[parse_json_bytes((original/item['file']).read_bytes()) for item in old_index['source_files']]
    new_batches=[parse_json_bytes((HERE/item['file']).read_bytes()) for item in new_index['source_files']]
    full=overlap_report(old_batches,new_batches)
    expected={**{k:v for k,v in full.items() if k!='phrases'},'original_capture_manifest_sha256':hashlib.sha256((original/'capture.json').read_bytes()).hexdigest(),'supplemental_phrases':[p for p in full['phrases'] if p['supplemental_refs']]}
    blob=(HERE/'overlap.json').read_bytes()
    need(hashlib.sha256(blob).hexdigest()==OVERLAP_PIN,'OVERLAP_BYTES_CHANGED')
    need(parse_json_bytes(blob)==expected,'OVERLAP_NOT_REPRODUCIBLE')
    return {**result,'overlap_counts':full['counts'],'original_classifications_unchanged':True,'classification_inherited':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',action='append',default=[],metavar='TOPIC=PRIVATE_PATH');args=ap.parse_args()
    try:
        sources={}
        for value in args.source:
            topic,path=value.split('=',1);need(topic not in sources,'DUPLICATE_SOURCE_ARGUMENT');sources[topic]=path
        print(json.dumps(verify(sources)))
    except Exception:
        print(json.dumps({'passed':False,'code':'SUPPLY_CAPTURE_VERIFICATION_FAILED','deployment_authorized':False}));raise SystemExit(1)
