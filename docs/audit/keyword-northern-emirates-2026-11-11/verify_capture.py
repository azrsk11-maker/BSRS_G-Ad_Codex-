"""Pinned public projection and overlap; optional private raw equality only."""
import argparse, hashlib, json, re
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_discovery import verify_capture, overlap_report, _exact
PINS = {'northern-emirates.json': 'c290895884a00f5da71b985afd53eb465ed0c21e7cf38d43dec950beca8cb53e', 'capture.json': '55fb083ab6f73b57ed7ae18815b64eed22f6c8e2c4caec173bef6405b7b04a83'}
PRIOR_PINS = {'keyword-discovery-2026-11-08/capture.json': '4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268', 'keyword-discovery-supply-2026-11-08/capture.json': '279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7', 'keyword-employment-education-2026-11-10/capture.json': '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f', 'keyword-employment-broad-2026-11-10/capture.json': 'bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864', 'keyword-exclusions-2026-11-10/capture.json': '1c47ca4c73590f0d5755b7520a08a6d2cd804295d2af58314bab4ad268804fc4', 'keyword-property-readiness-2026-11-11/capture.json': '81a1c496372d528668f42dc1056d67d29911a3951bee23ac0dc2ae878522539f'}
OVERLAP_PIN = '61c1241b22136f251c2500e78018c6035848baf2b07ae5ba58a88030cf7d1ddb'
GEOGRAPHY_PIN = '283520b1ceda9788a8a565dbd290f2ab8b43aed48c2e27141de8864bc8d369eb'
ALIASES = {'Dubai': ['dubai'], 'Abu Dhabi': ['abu dhabi', 'abudhabi'], 'Sharjah': ['sharjah'], 'Ajman': ['ajman'], 'Ras Al Khaimah': ['ras al khaimah', 'ras al khaima', 'ras alkhaimah', 'rasalkhaimah'], 'Fujairah': ['fujairah'], 'Umm Al Quwain': ['umm al quwain', 'ummul quwain']}


def geography(phrases):
 old=[p['normalized_text'] for p in phrases if p['original_refs']];all_=[p['normalized_text'] for p in phrases]
 return {'scope':'LITERAL_PLACE_MENTIONS_ONLY_NOT_INTENT_OR_SERVICE_COVERAGE','aliases':ALIASES,
  'before_source_distinct':len(old),'after_source_distinct':len(all_),
  'counts':[{'place':place,'before':sum(any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',p) for a in names) for p in old),
   'after':sum(any(re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)',p) for a in names) for p in all_)} for place,names in ALIASES.items()],
  'counts_nonexclusive':True,'ambiguous_acronyms_rak_uaq_assigned':False,'unmatched_means_place_absent':False,
  'searcher_location_inferred':False,'demand_or_inventory_verified':False,'service_scope_approved':False,'admission_authorized':False}


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
    current = [parse_json_bytes((HERE / 'northern-emirates.json').read_bytes())]
    full = overlap_report(previous, current)
    expected = {key: value for key, value in full.items() if key != 'phrases'}
    expected.update({'prior_manifest_sha256': PRIOR_PINS,
                     'supplemental_phrases': [p for p in full['phrases'] if p['supplemental_refs']]})
    blob = (HERE / 'overlap.json').read_bytes()
    if hashlib.sha256(blob).hexdigest() != OVERLAP_PIN or parse_json_bytes(blob) != expected:
        raise ValueError('OVERLAP_NOT_REPRODUCIBLE')
    geo_blob=(HERE/'geography.json').read_bytes()
    if hashlib.sha256(geo_blob).hexdigest()!=GEOGRAPHY_PIN or not _exact(parse_json_bytes(geo_blob),geography(full['phrases'])):
        raise ValueError('LITERAL_GEOGRAPHY_NOT_REPRODUCIBLE')
    return dict(result, overlap_counts=full['counts'], classification_inherited=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', metavar='PRIVATE_PATH')
    args = parser.parse_args()
    try:
        print(json.dumps(verify({'northern-emirates': args.source} if args.source else None)))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'PUBLIC_CAPTURE_FAILED', 'deployment_authorized': False}))
        raise SystemExit(1)
