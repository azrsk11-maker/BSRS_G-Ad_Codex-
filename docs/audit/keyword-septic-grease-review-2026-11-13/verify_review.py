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
REVIEW_SHA256 = '5d8c1d8af6ccff0a0c0f40faff8f899e2f6bd56e372959c4083220662581f028'
COHORT_PATTERN = 'grease|septic'
PROPOSE = 'PROPOSE_FULL_EXACT_RESEARCH'
PROPOSAL_REASON = 'EXPLICIT_SEPTIC_OR_GREASE_MAINTENANCE_SERVICE_RESEARCH'
# These dispositions were assigned after reading every complete selected literal.
# They are a frozen AI assessment, not a lexical classifier or human approval.
HOLD_ORDINALS = {'SERVICE_ONLY_PURPOSE_NOT_ESTABLISHED': (35, 160, 245, 293, 321, 361, 396, 428, 492, 540, 599, 621, 623, 644, 794, 795, 845, 852, 869, 870, 914, 928, 933, 990, 1058, 1092, 1099, 1147, 1150, 1151, 1189, 1229, 1331, 1360, 1366, 1375, 1407, 1433, 1445, 1446, 1467, 1470, 1478, 1487, 1519, 1558, 1583, 1592, 1602, 1606, 1613, 1641, 1645, 1661, 1668, 1692, 1707, 1709, 1718, 1748, 1749, 1784, 1817, 1818, 1821, 1828, 1862, 1865, 1879, 1894, 1895, 1898, 1928, 1929, 1936, 1940, 1950, 1951, 1955, 1979, 1986, 1993, 1996, 1997, 2030, 2035, 2043, 2049, 2050, 2091, 2107, 2108, 2109, 2122, 2124, 2125, 2126, 2140, 2146, 2150, 2180, 2188, 2201, 2224, 2230, 2232, 2240, 2243, 2250, 2260, 2296, 2299, 2305, 2328, 2342, 2354, 2358, 2383, 2387, 2396, 2463, 2490, 2491, 2493, 2516, 2518, 2519, 2521, 2541, 2550, 2554, 2563, 2571, 2575, 2576, 2579, 2581, 2594, 2603, 2605, 2615, 2624, 2628, 2636, 2650, 2652, 2653, 2663, 2668, 2675, 2676, 2680, 2683, 2695, 2703, 2713, 2719, 2744, 2770, 2775, 2776, 2790, 2793, 2808, 2818, 2845, 2859, 2867, 2871, 2885, 2889, 2893, 2910, 2915, 2920, 2933, 2945, 2953, 2966, 2977, 2984, 3009, 3013, 3014, 3019, 3027, 3032, 3050, 3051, 3052, 3056, 3065, 3080, 3083, 3088, 3091, 3097, 3101, 3116, 3121, 3125, 3129, 3132, 3140, 3147, 3156, 3158, 3161, 3175, 3177, 3183, 3190, 3200, 3201, 3209, 3210, 3223, 3238, 3239, 3241, 3242, 3245, 3247, 3250, 3255, 3260, 3266, 3271, 3295, 3311, 3313, 3324, 3336, 3345, 3348, 3350, 3357, 3359, 3389, 3391, 3399, 3412, 3423, 3424, 3429, 3435, 3442, 3443, 3448, 3454, 3472, 3474, 3475, 3484, 3494, 3501, 3509, 3517, 3523, 3535, 3563, 3575, 3593, 3596, 3597, 3606, 3615, 3618, 3625, 3628, 3629, 3635, 3636, 3640, 3643, 3645, 3659, 3687, 3688, 3698, 3707, 3710, 3712, 3721, 3723, 3728, 3739, 3755, 3757, 3760, 3764, 3766, 3777, 3779, 3813, 3815, 3822, 3824, 3827, 3841, 3850, 3859, 3873, 3874, 3880, 3887, 3893, 3896, 3937, 3948, 3949, 3950, 3967, 3985, 3989, 4008, 4013, 4016, 4044, 4052, 4060, 4070, 4071, 4078, 4079, 4080, 4085, 4099, 4103, 4115, 4139, 4154, 4156, 4160, 4163, 4169, 4177, 4185, 4190, 4192, 4195, 4199, 4208, 4220, 4228, 4241, 4242, 4243, 4244, 4245, 4322, 4325, 4330, 4331, 4333, 4338, 4423, 4464, 4603, 4641, 4645, 4657, 4672, 4674, 4749, 4750, 4784, 4785, 4795, 4799, 4804, 4806, 4815, 4938, 4939, 4940, 4948, 4949, 4969, 4976, 4982, 5085, 5106, 5233, 5235, 5236, 5237, 5240, 5256, 5257, 5258, 5288, 5289, 5301, 5304, 5308, 5321, 5352, 5355, 5365, 5366, 5367, 5390, 5396, 5414, 5472, 5474, 5475, 5476, 5477, 5486, 5487, 5515, 5593, 5597, 5607, 5609, 5623, 5624, 5625, 5626, 5627, 5628, 5630, 5631, 5632, 5633, 5634, 5635, 5636, 5637, 5638, 5639, 5640, 5641, 5642, 5643, 5644, 5647, 5650, 5651, 5652, 5653, 5654, 5655, 5656, 5657, 5658, 5659, 5660, 5661, 5662, 5663, 5665, 5667, 5668, 5670, 5699, 5700, 5702, 5825, 5834, 5836, 5837, 5838, 5839, 5841, 5978, 6029, 6050)}

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
    return [(n, row) for n, row in enumerate(rows, 1)
            if re.search(COHORT_PATTERN, row['values']['Keyword'], re.I)]


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
    need(review['schema'] == 'bsre-septic-grease-semantic-review-v1'
         and review['reviewed_on'] == '2026-11-13', 'REVIEW_IDENTITY_CHANGED')
    need(exact(review['source_pins'], PINS) and review['source_directory'] == SOURCE
         and review['raw_source_sha256'] == RAW_SHA256, 'SOURCE_BINDING_CHANGED')
    need(exact(review['reviewer'], REVIEWER) and exact(review['limits'], LIMITS),
         'RESEARCH_AUTHORITY_CHANGED')
    rows = sources['service-installation.json']['source_projection']['records']
    selected = selection(rows)
    need(len(rows) == 6053 and len(selected) == 914, 'COMPLETE_SELECTION_CHANGED')
    need(exact(review['selection'], {'cohort_pattern': COHORT_PATTERN,
         'flags': 'IGNORECASE', 'source_records': 6053, 'selected_records': 914,
         'remaining_outside_cohort': 5139, 'source_order_preserved': True,
         'quota_cutoff': False}), 'SELECTION_CONTRACT_CHANGED')
    holds = {n for ordinals in HOLD_ORDINALS.values() for n in ordinals}
    need(len(holds) == 470 and holds <= {n for n, _ in selected}, 'HOLD_COVERAGE_CHANGED')
    decisions = review['decisions']
    need(type(decisions) is list and len(decisions) == len(selected), 'INCOMPLETE_REVIEW')
    for index, (decision, (ordinal, row)) in enumerate(zip(decisions, selected), 1):
        need(exact(decision, expected_decision(index, ordinal, row)),
             'LITERAL_OCCURRENCE_COMPLETE_CELLS_OR_DISPOSITION_CHANGED')
    counts = dict(Counter(d['decision'] for d in decisions))
    reasons = dict(Counter(c for d in decisions for c in d['reason_codes']))
    need(exact(review['decision_counts'], counts) and counts == {PROPOSE: 444, 'HOLD': 470},
         'DECISION_COUNTS_CHANGED')
    need(exact(review['reason_counts'], reasons) and
         set(review['reason_definitions']) == set(HOLD_ORDINALS) | {PROPOSAL_REASON}
         and all(type(v) is str and v.strip() for v in review['reason_definitions'].values()),
         'REASON_DEFINITIONS_CHANGED')
    return {'passed': True, 'source_records': 6053, 'complete_literals_reviewed': 914,
            'remaining_outside_cohort': 5139, 'decision_counts': counts,
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
        'rows_promoted': lambda r: r['limits'].update(library_rows_added=444),
        'changed_pin': lambda r: r['source_pins'].update({'service-installation.json':'0'*64}),
        'broadened_selection': lambda r: r['selection'].update(cohort_pattern=''),
        'changed_summary': lambda r: r['decision_counts'].update(HOLD=0),
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
