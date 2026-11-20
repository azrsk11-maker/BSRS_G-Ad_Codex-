"""Verify complete, source-bound literal review; never approve or deploy exclusions."""
from collections import Counter
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys
from time import perf_counter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
import keyword_audit as ka

SOURCE = 'docs/audit/keyword-service-installation-2026-11-13'
PINS = {'service-installation.json': '91b8edcdcc6b8ab216c89ba2b1c9674ced8bcaf2be93d9f3ffe47795c1c75392', 'capture.json': '3e6f99d8cce615ab77549c2e33b1edce93605f78e7fb4b034fb9e9440e6f12ea'}
RAW_SHA256 = '4dda5a60cfbb680edff4d2b6c17319f55afb41055968052bb18e6b3d883f5078'
REVIEW_SHA256 = '704457d2646095a1c46aee54faac8becb4d99bc353fa27129ba174b54e82ca90'
PRIOR_REVIEW_PINS = {'docs/audit/keyword-septic-grease-review-2026-11-13/review.json': '5d8c1d8af6ccff0a0c0f40faff8f899e2f6bd56e372959c4083220662581f028', 'docs/audit/keyword-trade-services-review-2026-11-13/review.json': '597a03ccdbc92ae5a58b429981b0dafbc7749676730e2db5d697926076ebdd60'}
COHORT_PATTERN = '(?:(?:\\b(?:wasps?|hornets?)\\b)|(?:\\b(?:fleas?|ticks?)\\b)|(?:\\bfumigat)|(?:\\b(?:rodents?|mice|rats?)\\b)|(?:\\b(?:algae|algaecide|backwash)\\b)|(?:\\btermite\\b.*\\binspect|\\binspect.*\\btermite\\b)|(?:\\b(?:exterminator|extermination)\\b.*\\b(?:cost|price|quote)\\b|\\b(?:cost|price|quote)\\b.*\\b(?:exterminator|extermination)\\b))|(?:\\b(?:commercial|industrial|emergency|same day|24 hour)\\b)'
PROPOSE = 'PROPOSE_FULL_EXACT_RESEARCH'
PROPOSAL_REASON = 'EXPLICIT_PEST_COMMERCIAL_OR_URGENT_SERVICE_RESEARCH'
# These dispositions were assigned after reading every complete selected literal.
# They are a frozen AI assessment, not a lexical classifier or human approval.
HOLD_ORDINALS = {'INSPECTION_OR_PROPERTY_CONDITION': (431, 461, 678, 680, 765, 847, 1036, 1527, 1857, 2194, 2511, 2952, 3126, 5911, 5931, 5946), 'PRODUCT_OR_DIY_PURPOSE': (456, 1176, 2138, 2501, 2556, 2777, 2963, 3176, 3219, 3222, 3551, 3770, 3898, 4014, 4193, 4263, 4346, 4347, 4379, 4409, 4578, 4597, 5244, 5249, 5250), 'UNVERIFIED_VENDOR_OR_LANGUAGE': (1874, 2074, 2408, 4068, 4276, 5364, 5913), 'SERVICE_ONLY_PURPOSE_NOT_ESTABLISHED': (184, 227, 505, 635, 985, 1145, 1290, 1347, 1377, 1476, 1589, 1952, 1977, 2274, 2277, 2495, 2500, 2503, 2645, 2737, 2789, 2816, 2870, 3131, 3603, 3769, 3857, 3954, 4630, 4631, 4632, 4635, 4801), 'MEDICAL_OR_AMBIGUOUS_SYMPTOM': (3115,)}

LIMITS = {'research_proposal_only': True, 'lexical_selection_is_not_intent_proof': True,
          'provider_identity_verified': False, 'metrics_used_for_intent': False,
          'current_library_membership_checked': False, 'compatibility_checked': False,
          'within_source_aliases_checked': False, 'protected_intent_checked': False,
          'independent_exclusion_approval': False, 'library_rows_added': 0,
          'live_bindings_added': 0, 'deployed': 0, 'source_metrics_modified': False}
REVIEWER = {'name': 'Codex AI lead', 'kind': 'AI_SEMANTIC_REVIEW',
            'all_complete_literals_read': True, 'independent_second_review': False,
            'human_approval': False}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def exact(a, b):
    return type(a) is type(b) and (set(a) == set(b) and all(exact(a[k], b[k]) for k in a)
        if type(a) is dict else len(a) == len(b) and all(exact(x, y) for x, y in zip(a, b))
        if type(a) is list else a == b)


def selection(rows):
    prior_ordinals=set()
    for path,pin in PRIOR_REVIEW_PINS.items():
        prior_review=read_json(ROOT/path,pin)
        prior_ordinals.update(d['source_ordinal'] for d in prior_review['decisions'])
    need(len(prior_ordinals)==1933,'PRIOR_ASSESSMENT_SCOPE_CHANGED')
    return [(n,row) for n,row in enumerate(rows,1)
            if n not in prior_ordinals and re.search(COHORT_PATTERN,row['values']['Keyword'],re.I)]


def expected_decision(index, ordinal, row):
    literal = row['values']['Keyword']
    reasons = [code for code, ordinals in HOLD_ORDINALS.items() if ordinal in ordinals]
    return {'selected_ordinal': index, 'source_ordinal': ordinal,
            'source_line': row['source_line'], 'original_literal': literal,
            'normalized_literal': ka.normalize(literal),
            'literal_utf8_sha256': hashlib.sha256(literal.encode('utf-8')).hexdigest(),
            'complete_public_values_sha256': digest(row['values']),
            'decision': 'HOLD' if reasons else PROPOSE,
            'reason_codes': reasons or [PROPOSAL_REASON]}


def validate(review, sources):
    need(review['schema'] == 'bsre-pest-commercial-services-semantic-review-v1'
         and review['reviewed_on'] == '2026-11-13', 'REVIEW_IDENTITY_CHANGED')
    need(exact(review['source_pins'], PINS) and review['source_directory'] == SOURCE
         and review['raw_source_sha256'] == RAW_SHA256, 'SOURCE_BINDING_CHANGED')
    need(exact(review['reviewer'], REVIEWER) and exact(review['limits'], LIMITS),
         'RESEARCH_AUTHORITY_CHANGED')
    rows = sources['service-installation.json']['source_projection']['records']
    selected = selection(rows)
    need(len(rows) == 6053 and len(selected) == 169, 'COMPLETE_SELECTION_CHANGED')
    need(exact(review['selection'], {'cohort_pattern': COHORT_PATTERN,
         'prior_review_pins': PRIOR_REVIEW_PINS,
         'flags': 'IGNORECASE', 'source_records': 6053, 'selected_records': 169,
         'remaining_outside_cohort': 5884, 'source_order_preserved': True,
         'quota_cutoff': False}), 'SELECTION_CONTRACT_CHANGED')
    holds = {n for ordinals in HOLD_ORDINALS.values() for n in ordinals}
    need(len(holds) == 82 and holds <= {n for n, _ in selected}, 'HOLD_COVERAGE_CHANGED')
    decisions = review['decisions']
    need(type(decisions) is list and len(decisions) == len(selected), 'INCOMPLETE_REVIEW')
    for index, (decision, (ordinal, row)) in enumerate(zip(decisions, selected), 1):
        need(exact(decision, expected_decision(index, ordinal, row)),
             'LITERAL_OCCURRENCE_COMPLETE_CELLS_OR_DISPOSITION_CHANGED')
    counts = dict(Counter(d['decision'] for d in decisions))
    reasons = dict(Counter(c for d in decisions for c in d['reason_codes']))
    need(exact(review['decision_counts'], counts) and counts == {PROPOSE: 87, 'HOLD': 82},
         'DECISION_COUNTS_CHANGED')
    need(exact(review['reason_counts'], reasons) and
         set(review['reason_definitions']) == set(HOLD_ORDINALS) | {PROPOSAL_REASON}
         and all(type(v) is str and v.strip() for v in review['reason_definitions'].values()),
         'REASON_DEFINITIONS_CHANGED')
    return {'passed': True, 'source_records': 6053, 'complete_literals_reviewed': 169,
            'remaining_outside_cohort': 5884, 'decision_counts': counts,
            'library_rows_added': 0, 'approved': 0, 'deployed': 0}


def read_json(path, pin):
    with path.open('rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    need(0 < len(raw) <= 8 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == pin,
         'PINNED_DOCUMENT_CHANGED')
    return ka.parse_json_bytes(raw)


def self_check(review, sources):
    cases = {
        'missing_row': lambda r: r['decisions'].pop(),
        'duplicate_row': lambda r: r['decisions'].__setitem__(1, deepcopy(r['decisions'][0])),
        'reversed_order': lambda r: r['decisions'].reverse(),
        'changed_literal': lambda r: r['decisions'][0].__setitem__('original_literal', 'rent apartment'),
        'changed_cells': lambda r: r['decisions'][0].__setitem__('complete_public_values_sha256', '0'*64),
        'changed_line': lambda r: r['decisions'][0].__setitem__('source_line', 100),
        'boolean_ordinal': lambda r: r['decisions'][0].__setitem__('source_ordinal', True),
        'promoted_hold': lambda r: next(d for d in r['decisions'] if d['decision']=='HOLD').update(decision=PROPOSE),
        'invented_hold': lambda r: r['decisions'][0].update(decision='HOLD', reason_codes=['LANGUAGE_MEANING_NOT_VERIFIED']),
        'granted_approval': lambda r: r['limits'].update(independent_exclusion_approval=True),
        'boolean_zero': lambda r: r['limits'].update(deployed=False),
        'rows_promoted': lambda r: r['limits'].update(library_rows_added=87),
        'changed_pin': lambda r: r['source_pins'].update({'service-installation.json':'0'*64}),
        'broadened_selection': lambda r: r['selection'].update(cohort_pattern=''),
        'changed_summary': lambda r: r['decision_counts'].update(HOLD=0),
        'changed_prior_review_binding': lambda r: r['selection'].update(prior_review_pins={}),
        'human_review_invented': lambda r: r['reviewer'].update(human_approval=True),
    }
    for name, mutate in cases.items():
        changed = deepcopy(review)
        mutate(changed)
        try:
            validate(changed, sources)
        except (ValueError, KeyError, TypeError):
            continue
        raise AssertionError('Tamper accepted: '+name)
    return list(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    start = perf_counter()
    # Invoke the source's actual pinned field/custody verifier as well as our pins.
    capture = runpy.run_path(str(ROOT / SOURCE / 'verify_capture.py'))
    documents = {name: read_json(ROOT / SOURCE / name, pin) for name, pin in PINS.items()}
    capture['validate_batch'](documents['service-installation.json'])
    capture['sd'].verify_capture(ROOT / SOURCE, PINS)
    review = read_json(HERE / 'review.json', REVIEW_SHA256)
    result = validate(review, documents)
    if args.self_check:
        result['tamper_cases_rejected'] = self_check(review, documents)
    result['elapsed_seconds'] = round(perf_counter()-start, 6)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
