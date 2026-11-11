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

PINS = {'management-software.json': 'ec726b055bde9fbd33e7d55015c84700aefbac0ef2634462634f84a7c4154063', 'property-operations-employment.json': '466a47fac06312ade996e9c9596f512775da3b726f87876aaf7bbe778a4210cc', 'commercial-industrial-property.json': '90d655d2ca4a600d7cfccee255efcb791f8c2a5ca37ab7129d8810c5253a30e5', 'capture.json': 'cd18511e136d67cde9f7cd704731423670a43a9e700cc29df110c4c1cd7d8bff'}
PRIOR_PINS = {'keyword-discovery-2026-11-08/capture.json': '4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268', 'keyword-discovery-supply-2026-11-08/capture.json': '279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7', 'keyword-employment-education-2026-11-10/capture.json': '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f', 'keyword-employment-broad-2026-11-10/capture.json': 'bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864', 'keyword-exclusions-2026-11-10/capture.json': '1c47ca4c73590f0d5755b7520a08a6d2cd804295d2af58314bab4ad268804fc4', 'keyword-property-readiness-2026-11-11/capture.json': '81a1c496372d528668f42dc1056d67d29911a3951bee23ac0dc2ae878522539f', 'keyword-northern-emirates-2026-11-11/capture.json': '55fb083ab6f73b57ed7ae18815b64eed22f6c8e2c4caec173bef6405b7b04a83', 'keyword-abu-dhabi-sharjah-2026-11-11/capture.json': '719d1bcdce7620740266046ed24705b6c05fdf521cdb67e9be3b6a014023f62d', 'keyword-developer-employment-2026-11-11/capture.json': 'a89397314f9565d5f2e0027c8d19a7b6b55b9f738f1c5272f275d2716ecdc06f', 'keyword-occupational-education-2026-11-11/capture.json': '1e30f171310155e76229d35922e951aed2965def632af757f3c8d30386eb6217', 'keyword-employment-lifecycle-2026-11-11/capture.json': '94dfa8a6fe28a0ed76b865a5a230c4404a5bc8c25ecfa0cd9fae6f6311fa78c1', 'keyword-gap-research-2026-11-11/capture.json': '5ccdbf45f7d9b4408792a9f241e5d9f8b90f1e612620a3770c6c3e03881dc3f9', 'keyword-role-exam-assets-2026-11-11/capture.json': 'ec254a5df735685452ce344da2201c6d44ef87b5775479cbac2e2b10c68d0092'}
OVERLAP_PIN = 'bbab6bcdb5d418275ad9aacba6e82a2c306670e16b3c027d05fcee2a09830361'


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
        print(json.dumps({'passed': False, 'code': 'GAP_RESEARCH_CAPTURE_FAILED',
                          'deployment_authorized': False}))
        raise SystemExit(1)
