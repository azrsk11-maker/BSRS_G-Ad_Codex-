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
REVIEW_SHA256 = '597a03ccdbc92ae5a58b429981b0dafbc7749676730e2db5d697926076ebdd60'
COHORT_PATTERN = '\\birrigat|\\bduct|fire|alarm'
PROPOSE = 'PROPOSE_FULL_EXACT_RESEARCH'
PROPOSAL_REASON = 'EXPLICIT_IRRIGATION_DUCT_OR_ALARM_SERVICE_RESEARCH'
# These dispositions were assigned after reading every complete selected literal.
# They are a frozen AI assessment, not a lexical classifier or human approval.
HOLD_ORDINALS = {'SERVICE_ONLY_PURPOSE_NOT_ESTABLISHED': (24, 39, 76, 126, 154, 176, 195, 202, 214, 231, 254, 266, 283, 309, 342, 347, 351, 365, 372, 415, 440, 450, 475, 482, 483, 489, 491, 519, 526, 528, 532, 534, 546, 561, 562, 566, 585, 597, 601, 605, 620, 656, 659, 673, 702, 742, 759, 763, 768, 774, 776, 778, 779, 781, 782, 791, 792, 802, 818, 841, 860, 861, 888, 894, 897, 929, 930, 947, 970, 979, 992, 998, 1007, 1021, 1026, 1041, 1046, 1047, 1048, 1052, 1054, 1072, 1078, 1088, 1102, 1106, 1111, 1112, 1117, 1128, 1136, 1152, 1155, 1165, 1187, 1198, 1220, 1249, 1250, 1258, 1271, 1274, 1277, 1286, 1294, 1295, 1306, 1307, 1309, 1314, 1325, 1337, 1353, 1384, 1408, 1411, 1417, 1425, 1427, 1428, 1431, 1443, 1465, 1480, 1485, 1511, 1521, 1528, 1529, 1542, 1545, 1556, 1557, 1569, 1573, 1588, 1596, 1600, 1604, 1618, 1623, 1625, 1631, 1637, 1643, 1656, 1659, 1681, 1689, 1693, 1695, 1696, 1722, 1746, 1757, 1758, 1764, 1773, 1776, 1785, 1803, 1807, 1811, 1819, 1823, 1841, 1842, 1845, 1848, 1850, 1854, 1856, 1860, 1872, 1873, 1881, 1882, 1889, 1893, 1896, 1910, 1917, 1919, 1924, 1930, 1933, 1938, 1961, 1963, 1975, 1976, 1991, 2026, 2034, 2037, 2044, 2046, 2052, 2056, 2080, 2095, 2102, 2105, 2115, 2131, 2172, 2181, 2187, 2214, 2251, 2254, 2266, 2283, 2289, 2293, 2304, 2317, 2330, 2341, 2346, 2366, 2367, 2368, 2374, 2379, 2382, 2384, 2394, 2398, 2402, 2409, 2419, 2427, 2438, 2443, 2492, 2494, 2496, 2502, 2505, 2506, 2523, 2547, 2558, 2567, 2580, 2592, 2612, 2616, 2622, 2631, 2632, 2640, 2671, 2674, 2688, 2690, 2693, 2715, 2726, 2735, 2749, 2755, 2759, 2771, 2782, 2799, 2814, 2815, 2824, 2864, 2873, 2876, 2882, 2917, 2918, 2928, 2957, 2989, 2993, 3001, 3003, 3006, 3012, 3028, 3029, 3043, 3046, 3047, 3066, 3067, 3068, 3069, 3079, 3085, 3095, 3112, 3117, 3118, 3134, 3138, 3143, 3181, 3214, 3217, 3229, 3232, 3286, 3289, 3290, 3297, 3299, 3300, 3316, 3342, 3352, 3390, 3413, 3414, 3479, 3486, 3488, 3496, 3518, 3522, 3524, 3532, 3533, 3538, 3561, 3570, 3573, 3576, 3598, 3611, 3612, 3614, 3620, 3634, 3646, 3648, 3651, 3654, 3657, 3662, 3675, 3676, 3677, 3685, 3694, 3706, 3714, 3726, 3744, 3754, 3772, 3807, 3808, 3818, 3821, 3830, 3840, 3868, 3876, 3884, 3886, 3889, 3926, 3927, 3939, 3940, 3978, 3984, 3988, 3999, 4017, 4026, 4028, 4066, 4106, 4111, 4113, 4116, 4120, 4137, 4142, 4143, 4173, 4176, 4191, 4212, 4219, 4230, 4236, 4237, 4253, 4254, 4256, 4257, 4258, 4260, 4261, 4262, 4269, 4304, 4426, 4438, 4439, 4440, 4558, 4559, 4573, 4643, 4644, 4646, 4673, 4681, 4741, 4757, 4759, 4770, 4771, 4772, 4773, 4774, 4775, 4778, 4787, 4797, 4805, 4808, 4824, 4827, 4829, 4830, 4831, 4834, 4835, 4836, 4837, 4839, 4840, 4841, 4842, 4843, 4844, 4846, 4847, 4848, 4851, 4852, 4864, 4871, 4872, 4873, 4874, 4878, 4879, 4883, 4907, 4908, 4911, 4915, 4919, 4920, 4921, 4922, 4923, 4924, 4934, 4962, 4965, 4987, 5014, 5086, 5088, 5107, 5122, 5157, 5158, 5178, 5187, 5188, 5191, 5227, 5229, 5232, 5253, 5271, 5277, 5291, 5292, 5293, 5336, 5337, 5338, 5344, 5345, 5350, 5360, 5361, 5368, 5369, 5400, 5401, 5402, 5418, 5453, 5457, 5467, 5468, 5511, 5523, 5525, 5529, 5530, 5536, 5537, 5539, 5546, 5568, 5574, 5577, 5585, 5588, 5602, 5674, 5716, 5717, 5718, 5719, 5720, 5721, 5722, 5843, 5980, 6005, 6022)}

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
    need(review['schema'] == 'bsre-trade-services-semantic-review-v1'
         and review['reviewed_on'] == '2026-11-13', 'REVIEW_IDENTITY_CHANGED')
    need(exact(review['source_pins'], PINS) and review['source_directory'] == SOURCE
         and review['raw_source_sha256'] == RAW_SHA256, 'SOURCE_BINDING_CHANGED')
    need(exact(review['reviewer'], REVIEWER) and exact(review['limits'], LIMITS),
         'RESEARCH_AUTHORITY_CHANGED')
    rows = sources['service-installation.json']['source_projection']['records']
    selected = selection(rows)
    need(len(rows) == 6053 and len(selected) == 1019, 'COMPLETE_SELECTION_CHANGED')
    need(exact(review['selection'], {'cohort_pattern': COHORT_PATTERN,
         'flags': 'IGNORECASE', 'source_records': 6053, 'selected_records': 1019,
         'remaining_outside_cohort': 5034, 'source_order_preserved': True,
         'quota_cutoff': False}), 'SELECTION_CONTRACT_CHANGED')
    holds = {n for ordinals in HOLD_ORDINALS.values() for n in ordinals}
    need(len(holds) == 538 and holds <= {n for n, _ in selected}, 'HOLD_COVERAGE_CHANGED')
    decisions = review['decisions']
    need(type(decisions) is list and len(decisions) == len(selected), 'INCOMPLETE_REVIEW')
    for index, (decision, (ordinal, row)) in enumerate(zip(decisions, selected), 1):
        need(exact(decision, expected_decision(index, ordinal, row)),
             'LITERAL_OCCURRENCE_COMPLETE_CELLS_OR_DISPOSITION_CHANGED')
    counts = dict(Counter(d['decision'] for d in decisions))
    reasons = dict(Counter(c for d in decisions for c in d['reason_codes']))
    need(exact(review['decision_counts'], counts) and counts == {PROPOSE: 481, 'HOLD': 538},
         'DECISION_COUNTS_CHANGED')
    need(exact(review['reason_counts'], reasons) and
         set(review['reason_definitions']) == set(HOLD_ORDINALS) | {PROPOSAL_REASON}
         and all(type(v) is str and v.strip() for v in review['reason_definitions'].values()),
         'REASON_DEFINITIONS_CHANGED')
    return {'passed': True, 'source_records': 6053, 'complete_literals_reviewed': 1019,
            'remaining_outside_cohort': 5034, 'decision_counts': counts,
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
        'rows_promoted': lambda r: r['limits'].update(library_rows_added=481),
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
