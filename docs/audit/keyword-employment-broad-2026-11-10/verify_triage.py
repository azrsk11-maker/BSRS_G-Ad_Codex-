"""Pinned complete employment triage; unscoped lexical checks confer no authority."""
import hashlib, json
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from supplemental_triage import load_corpus, compile_protection_review, EMPLOYMENT_CAPTURE
PINS = {'proposals.json': '523226d018018157e44a3e7e7c3fe53c286ad5742fd044138d2eda4c36d41fa4',
 'workbench.json': 'c93745c44b95b530b8c4dbcd1ac6f7e4b7b04cdd8eabfacaaf9a6578b1fa2002',
 'protection-screen.json': 'd8e748bc857d1f697a0676fddc6169a8c8e4c1599cae8779ec7ed57d128657ba'}
PRIOR = {'keyword-triage-2026-11-08/workbench.json': '1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477',
 'keyword-employment-education-2026-11-10/workbench.json': 'b22f03d89237aa4467b2e7d9cc8a74c36882cdee104cabb85d55f8150e6f139a'}
CAPTURE_PIN = 'bdc847f3c9759eb166d2bb89122ac365ce414127200463ce0b423a9628eef864'
GENERICS = ['job', 'jobs', 'salary', 'career', 'broker', 'agent', 'company', 'dubai', 'indian', 'british', 'foreigners', 'work']


def verify():
    loaded, protected = {}, set()
    for name, digest in PINS.items():
        blob = (HERE / name).read_bytes()
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError('TRIAGE_BYTES_CHANGED')
        loaded[name] = parse_json_bytes(blob)
    for relative, digest in PRIOR.items():
        blob = (ROOT / 'docs/audit' / relative).read_bytes()
        if hashlib.sha256(blob).hexdigest() != digest:
            raise ValueError('PRIOR_REVIEW_CHANGED')
        protected.update(parse_json_bytes(blob)['diagnostics']['protected_phrases'])
    if hashlib.sha256((HERE / 'capture.json').read_bytes()).hexdigest() != CAPTURE_PIN:
        raise ValueError('CAPTURE_CHANGED')
    fresh = compile_protection_review(load_corpus(ROOT, capture=EMPLOYMENT_CAPTURE), loaded['proposals.json'],
                                      sorted(protected), GENERICS)
    fresh['screen']['source_bindings'] = {'prior_workbench_sha256': PRIOR,
                                         'capture_manifest_sha256': CAPTURE_PIN}
    if fresh['workbench'] != loaded['workbench.json'] or fresh['screen'] != loaded['protection-screen.json']:
        raise ValueError('TRIAGE_NOT_REPRODUCIBLE')
    summary = fresh['workbench']['summary']
    if (summary['unique_phrases'] != 136 or summary['source_occurrences'] != 136 or
        summary['dispositions']['UNASSESSED'] or
        len(fresh['workbench']['diagnostics']['protected_phrases']) != summary['dispositions']['HOLD'] or
        fresh['screen']['exact_conflict_count']):
        raise ValueError('INCOMPLETE_OR_CONFLICTED_DRAFT')
    return {'passed': True, 'scope': 'PRELIMINARY_TRIAGE_NOT_ADMISSION', **summary,
            'protected_queries': fresh['screen']['protected_queries'], 'exact_lexical_conflicts': 0,
            'positive_library_coverage_verified': False, 'deployment_authorized': False}


if __name__ == '__main__':
    try:
        print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed': False, 'scope': 'PRELIMINARY_TRIAGE_NOT_ADMISSION', 'deployment_authorized': False}))
        raise SystemExit(1)
