"""Reproduce the complete preliminary review and unscoped protection screen."""
import hashlib
import json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_triage import load_corpus, compile_protection_review

PINS = {
    'proposals.json': '058acc675edac89a0ea379aa4c10f30088f2db5786705d54ec8e17536636168f',
    'workbench.json': 'b22f03d89237aa4467b2e7d9cc8a74c36882cdee104cabb85d55f8150e6f139a',
    'protection-screen.json': 'c1d11d04292032ae1664a70ddce38b32d0bc137ea81ffc01adb2a9187556eb30',
}
PRIOR_WORKBENCH = '1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477'
CAPTURE_MANIFEST = '8129d8f27594257e58d35e112dd1f12ba6566e238f8b544ab66e82af08a00e3f'
ENTITY_REVIEW = '72703422ad2a894dd7f803db7fe60858b185df1c6f4e90d3e2871f5d4af7606d'


def verify():
    loaded = {}
    for filename, digest in PINS.items():
        blob = (HERE / filename).read_bytes()
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError('TRIAGE_BYTES_CHANGED')
        loaded[filename] = parse_json_bytes(blob)
    old = (ROOT / 'docs/audit/keyword-triage-2026-11-08/workbench.json').read_bytes()
    if hashlib.sha256(old).hexdigest() != PRIOR_WORKBENCH:
        raise ValueError('PRIOR_WORKBENCH_CHANGED')
    if hashlib.sha256((HERE / 'capture.json').read_bytes()).hexdigest() != CAPTURE_MANIFEST:
        raise ValueError('CAPTURE_CHANGED')
    if hashlib.sha256((HERE / 'ENTITY_REVIEW.md').read_bytes()).hexdigest() != ENTITY_REVIEW:
        raise ValueError('ENTITY_REVIEW_CHANGED')
    fresh = compile_protection_review(load_corpus(ROOT),
                loaded['proposals.json'], parse_json_bytes(old)['diagnostics']['protected_phrases'],
                ['broker', 'agent', 'course', 'free', 'mortgage', 'job', 'school', 'training'],
                proposed_on='2026-11-10')
    fresh['screen']['source_bindings'] = {'prior_workbench_sha256': PRIOR_WORKBENCH,
                                         'capture_manifest_sha256': CAPTURE_MANIFEST,
                                         'entity_review_sha256': ENTITY_REVIEW}
    if fresh['workbench'] != loaded['workbench.json'] or fresh['screen'] != loaded['protection-screen.json']:
        raise ValueError('TRIAGE_NOT_REPRODUCIBLE')
    summary = fresh['workbench']['summary']
    protected = fresh['workbench']['diagnostics']['protected_phrases']
    if (summary['unique_phrases'] != 263 or summary['source_occurrences'] != 266 or
            summary['dispositions']['UNASSESSED'] or len(protected) != summary['dispositions']['HOLD'] or
            fresh['screen']['exact_conflict_count']):
        raise ValueError('INCOMPLETE_OR_CONFLICTED_DRAFT_REVIEW')
    return {'passed': True, 'scope': 'PRELIMINARY_TRIAGE_NOT_ADMISSION', **summary,
            'protected_queries': fresh['screen']['protected_queries'],
            'exact_lexical_conflicts': fresh['screen']['exact_conflict_count'],
            'positive_library_coverage_verified': False, 'deployment_authorized': False}


if __name__ == '__main__':
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'PRELIMINARY_TRIAGE_NOT_ADMISSION',
                          'deployment_authorized': False}))
        raise SystemExit(1)
