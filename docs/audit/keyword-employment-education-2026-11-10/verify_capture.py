"""Pinned public consistency or optional private raw equality; never admission."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import verify_capture, overlap_report

PINS = {
    'employment.json': '34848eca2c291995570ba381850fac8ddbeac5f7878ff09777d879f228efa532',
    'education-specific.json': 'fcc4f35fe10a04d9ab11da4d7d6674e6779881c81b3b16690c4d9f8740f3f969',
    'education-broader.json': '231b7029722f786705a3eaa14c658f657b3b38179deca37e862d9afc259002de',
    'capture.json': '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f',
}
PRIOR_PINS = {
    'keyword-discovery-2026-11-08/capture.json': '4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268',
    'keyword-discovery-supply-2026-11-08/capture.json': '279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7',
}
OVERLAP_PIN = '514be2602a5f6dd2406c82dfa69353c4b44eae5c0a43a0f5240f87b21dc02d93'


def verify(sources=None):
    result = verify_capture(HERE, PINS, sources)
    original = []
    for relative, digest in PRIOR_PINS.items():
        manifest = ROOT / 'docs/audit' / relative
        blob = manifest.read_bytes()
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError('PRIOR_MANIFEST_CHANGED')
        for item in parse_json_bytes(blob)['source_files']:
            member = (manifest.parent / item['file']).read_bytes()
            if hashlib.sha256(member).hexdigest() != item['sha256']:
                raise ValueError('PRIOR_SOURCE_CHANGED')
            original.append(parse_json_bytes(member))
    index = parse_json_bytes((HERE / 'capture.json').read_bytes())
    batches = [parse_json_bytes((HERE / item['file']).read_bytes()) for item in index['source_files']]
    full = overlap_report(original, batches)
    expected = {key: value for key, value in full.items() if key != 'phrases'}
    expected.update({'prior_manifest_sha256': PRIOR_PINS,
                     'supplemental_phrases': [p for p in full['phrases'] if p['supplemental_refs']]})
    blob = (HERE / 'overlap.json').read_bytes()
    if hashlib.sha256(blob).hexdigest() != OVERLAP_PIN or parse_json_bytes(blob) != expected:
        raise ValueError('OVERLAP_NOT_REPRODUCIBLE')
    return dict(result, overlap_counts=full['counts'], classification_inherited=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', action='append', default=[], metavar='TOPIC=PRIVATE_PATH')
    args = parser.parse_args()
    try:
        sources = {}
        for value in args.source:
            topic, path = value.split('=', 1)
            if topic in sources:
                raise ValueError('DUPLICATE_SOURCE_ARGUMENT')
            sources[topic] = path
        print(json.dumps(verify(sources)))
    except Exception:
        print(json.dumps({'passed': False, 'code': 'EMPLOYMENT_EDUCATION_CAPTURE_FAILED',
                          'deployment_authorized': False}))
        raise SystemExit(1)
