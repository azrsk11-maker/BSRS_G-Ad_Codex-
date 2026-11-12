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

SOURCE = 'docs/audit/keyword-application-documents-2026-11-13'
PINS = {'application-documents.json': '308e98c6a5836459cf572e7ff8d4e063b06cdd1881170f245f17b0f6b8bbb587',
        'capture.json': '2a5c148cd42f6a94077553ee9cef4e97fb59d03dfd358c947d030c9b965f34b3'}
RAW_SHA256 = '840561b4e04958a8c911bf0bf89fb941377c81d284284260d30b26fc940a3fa5'
REVIEW_SHA256 = '828e2c5c87e8156d8885533d39e31b8f31bf3524594018ca1480939ae60e8fa8'
FAMILY = r'\b(?:administrative assistants?|admin assistants?|receptionists?|customer service)\b'
DOCUMENT = r'\b(?:resumes?|r[ée]sum[ée]s?|cvs?|curriculum vitae|cover letters?|coverletters?|application letters?)\b'
PROPOSE = 'PROPOSE_FULL_EXACT_RESEARCH'
PROPOSAL_REASON = 'EXPLICIT_EMPLOYMENT_APPLICATION_DOCUMENT'
# These dispositions were assigned after reading every complete selected literal.
# They are a frozen AI assessment, not a lexical classifier or human approval.
HOLD_ORDINALS = {
    'RESUME_VENDOR_SUPPORT_OR_ROLE_UNRESOLVED':
        (11,14,16,17,18,19,20,21,29,53,55,58,62,95,104,113,121,382,454,568,
         1957,1960,2851,3081,3715,4296),
    'PROVIDER_SERVICE_CONTINUATION_OR_ROLE_UNRESOLVED':
        (1070,1116,1620,1622,2000,3010,4248,4295,4317),
    'LANGUAGE_MEANING_NOT_VERIFIED': (1645,1647),
    'REPEATED_DOCUMENT_WORDING_UNRESOLVED': (1962,),
    'ACADEMIC_EXERCISE_CLASSIFICATION_UNRESOLVED': (2126,2128),
}
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
            if re.search(FAMILY, row['values']['Keyword'], re.I)
            and re.search(DOCUMENT, row['values']['Keyword'], re.I)]


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
    need(review['schema'] == 'bsre-front-office-document-semantic-review-v1'
         and review['reviewed_on'] == '2026-11-13', 'REVIEW_IDENTITY_CHANGED')
    need(exact(review['source_pins'], PINS) and review['source_directory'] == SOURCE
         and review['raw_source_sha256'] == RAW_SHA256, 'SOURCE_BINDING_CHANGED')
    need(exact(review['reviewer'], REVIEWER) and exact(review['limits'], LIMITS),
         'RESEARCH_AUTHORITY_CHANGED')
    rows = sources['application-documents.json']['source_projection']['records']
    selected = selection(rows)
    need(len(rows) == 4356 and len(selected) == 1100, 'COMPLETE_SELECTION_CHANGED')
    need(exact(review['selection'], {'family_pattern': FAMILY, 'document_pattern': DOCUMENT,
         'flags': 'IGNORECASE', 'source_records': 4356, 'selected_records': 1100,
         'remaining_outside_cohort': 3256, 'source_order_preserved': True,
         'quota_cutoff': False}), 'SELECTION_CONTRACT_CHANGED')
    holds = {n for ordinals in HOLD_ORDINALS.values() for n in ordinals}
    need(len(holds) == 40 and holds <= {n for n, _ in selected}, 'HOLD_COVERAGE_CHANGED')
    decisions = review['decisions']
    need(type(decisions) is list and len(decisions) == len(selected), 'INCOMPLETE_REVIEW')
    for index, (decision, (ordinal, row)) in enumerate(zip(decisions, selected), 1):
        need(exact(decision, expected_decision(index, ordinal, row)),
             'LITERAL_OCCURRENCE_COMPLETE_CELLS_OR_DISPOSITION_CHANGED')
    counts = dict(Counter(d['decision'] for d in decisions))
    reasons = dict(Counter(c for d in decisions for c in d['reason_codes']))
    need(exact(review['decision_counts'], counts) and counts == {PROPOSE: 1060, 'HOLD': 40},
         'DECISION_COUNTS_CHANGED')
    need(exact(review['reason_counts'], reasons) and
         set(review['reason_definitions']) == set(HOLD_ORDINALS) | {PROPOSAL_REASON}
         and all(type(v) is str and v.strip() for v in review['reason_definitions'].values()),
         'REASON_DEFINITIONS_CHANGED')
    return {'passed': True, 'source_records': 4356, 'complete_literals_reviewed': 1100,
            'remaining_outside_cohort': 3256, 'decision_counts': counts,
            'library_rows_added': 0, 'approved': 0, 'deployed': 0}


def read_json(path, pin):
    with path.open('rb') as stream:
        raw = stream.read(4 * 1024 * 1024 + 1)
    need(0 < len(raw) <= 4 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == pin,
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
        'rows_promoted': lambda r: r['limits'].update(library_rows_added=1060),
        'changed_pin': lambda r: r['source_pins'].update({'application-documents.json':'0'*64}),
        'broadened_selection': lambda r: r['selection'].update(document_pattern=''),
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
    capture['validate_batch'](documents['application-documents.json'])
    capture['sd'].verify_capture(ROOT / SOURCE, PINS)
    review = read_json(HERE / 'review.json', REVIEW_SHA256)
    result = validate(review, documents)
    if args.self_check:
        result['tamper_cases_rejected'] = self_check(review, documents)
    result['elapsed_seconds'] = round(perf_counter()-start, 6)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
