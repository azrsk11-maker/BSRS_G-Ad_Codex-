"""Pinned public projection and overlap; optional private raw equality only."""
import argparse, hashlib, json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import verify_capture, overlap_report
PINS = {'software-services-products.json': '23c440857a175a0674332b037d8acfedd550c2d060300cbad5b14a48acd5edaa', 'capture.json': '1c47ca4c73590f0d5755b7520a08a6d2cd804295d2af58314bab4ad268804fc4'}
PRIOR_PINS = {'keyword-discovery-2026-11-08/capture.json': '4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268', 'keyword-discovery-supply-2026-11-08/capture.json': '279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7', 'keyword-employment-education-2026-11-10/capture.json': '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f', 'keyword-employment-broad-2026-11-10/capture.json': 'bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864'}
OVERLAP_PIN = '87a60fd42be12f8ad0564aec81c9377b143662c56dcaf79fa766df52fcf1907d'


def verify(sources=None):
    result = verify_capture(HERE, PINS, sources)
    previous = []
    for relative, digest in PRIOR_PINS.items():
        path = ROOT / 'docs/audit' / relative
        blob = path.read_bytes()
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError('PRIOR_CAPTURE_CHANGED')
        for item in parse_json_bytes(blob)['source_files']:
            member = (path.parent / item['file']).read_bytes()
            if hashlib.sha256(member).hexdigest() != item['sha256']:
                raise ValueError('PRIOR_SOURCE_CHANGED')
            previous.append(parse_json_bytes(member))
    current = [parse_json_bytes((HERE / 'software-services-products.json').read_bytes())]
    full = overlap_report(previous, current)
    expected = {key: value for key, value in full.items() if key != 'phrases'}
    expected.update({'prior_manifest_sha256': PRIOR_PINS,
                     'supplemental_phrases': [p for p in full['phrases'] if p['supplemental_refs']]})
    blob = (HERE / 'overlap.json').read_bytes()
    if hashlib.sha256(blob).hexdigest() != OVERLAP_PIN or parse_json_bytes(blob) != expected:
        raise ValueError('OVERLAP_NOT_REPRODUCIBLE')
    return dict(result, overlap_counts=full['counts'], classification_inherited=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', metavar='PRIVATE_PATH')
    args = parser.parse_args()
    try:
        print(json.dumps(verify({'software-services-products': args.source} if args.source else None)))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'PUBLIC_CAPTURE_FAILED', 'deployment_authorized': False}))
        raise SystemExit(1)
