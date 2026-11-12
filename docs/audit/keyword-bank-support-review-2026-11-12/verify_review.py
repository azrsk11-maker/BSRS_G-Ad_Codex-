"""Read-only source/coverage/authority checks; not semantic or admission approval."""
from collections import Counter
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
import keyword_audit as ka

FOLDER = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/audit/keyword-bank-access-navigation-2026-11-12'
PINS = {
    'bank-access-navigation.json': '822129ae18676ee62700c0726dcc11179c1bb7293636f031d7f3908e6fc879ea',
    'capture.json': 'a3d6fe2f1c2caa5c905651d4f8955a338118a6380d5a7e6251b17c82767f3c99',
    'credential-review-a.json': '89df3708b481a29d8c0d94ba068e99046e7f388ce2780cbc8e49af7d66dbbe6a',
    'credential-review-b.json': '4f8489d14c2b0233ce8db8c920a886eabc57baead6161d99864547bfab45fecb',
}
REVIEW_SHA256 = 'cc3a3d36d564bb577cc1b8b2015e3600e5d8daaecd2fa3b30a80246f7ffca89d'
INCLUDE = r'\b(customer (care|service|support)|helpline|contact (number|no)|phone (number|banking)|support)\b'
EXCLUDE = r'\b(passwords?|reset)\b'
PROPOSE = 'PROPOSE_FULL_EXACT_RESEARCH'
PROPOSAL_REASON = 'NAMED_OR_EXPLICIT_BANK_HELP_LOOKUP'
HOLD_REASONS = {'FINANCIAL_SCOPE_UNRESOLVED', 'POTENTIAL_DOMAIN_OR_ROUTE_FORM',
                'WORDING_OR_ENTITY_AMBIGUITY', 'NON_NAVIGATION_OR_ROLE_AMBIGUITY',
                'PHYSICAL_BRANCH_CONTEXT_UNRESOLVED'}
LIMITS = {'research_proposal_only': True, 'lexical_selection_is_not_intent_proof': True,
          'provider_identity_verified': False, 'metrics_used_for_intent': False,
          'current_library_membership_checked': False, 'compatibility_checked': False,
          'within_source_aliases_checked': False, 'protected_intent_checked': False,
          'independent_exclusion_approval': False, 'library_rows_added': 0,
          'live_bindings_added': 0, 'deployed': 0, 'source_metrics_modified': False}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def read_json(path, pin):
    raw = path.read_bytes()
    need(len(raw) <= 4 * 1024 * 1024 and hashlib.sha256(raw).hexdigest() == pin,
         'PINNED_DOCUMENT_CHANGED')
    return ka.parse_json_bytes(raw)


def validate(review, sources):
    need(review['schema'] == 'bsre-bank-support-semantic-review-v1' and
         review['reviewed_on'] == '2026-11-12', 'REVIEW_IDENTITY_CHANGED')
    need(review['source_pins'] == PINS and
         review['source_directory'] == 'docs/audit/keyword-bank-access-navigation-2026-11-12' and
         review['raw_source_sha256'] == '2893a10b0bc281451e62049540b1227a0b82a7f4de69ac365bd4ed489d298c2e',
         'SOURCE_IDENTITY_CHANGED')
    need(review['reviewer'] == {'name': 'Codex AI lead', 'kind': 'AI_SEMANTIC_REVIEW',
         'all_complete_literals_read': True, 'independent_second_review': False,
         'human_approval': False}, 'REVIEW_AUTHORITY_CHANGED')
    need(set(review['limits']) == set(LIMITS) and all(
         type(review['limits'][k]) is type(v) and review['limits'][k] == v
         for k, v in LIMITS.items()), 'RESEARCH_AUTHORITY_CHANGED')
    rows = sources['bank-access-navigation.json']['source_projection']['records']
    need(len(rows) == 3481, 'SOURCE_POPULATION_CHANGED')
    credential = {n for n, row in enumerate(rows, 1)
                  if re.search(EXCLUDE, row['values']['Keyword'], re.I)}
    earlier = sources['credential-review-a.json']['decisions'] + sources['credential-review-b.json']['decisions']
    need(len(earlier) == 803 and {r['source_ordinal'] for r in earlier} == credential,
         'PREVIOUS_REVIEW_COVERAGE_CHANGED')
    selected = [(n, row) for n, row in enumerate(rows, 1) if n not in credential and
                re.search(INCLUDE, row['values']['Keyword'], re.I)]
    need(len(selected) == 690 and len(credential) == 803, 'COMPLETE_SELECTION_CHANGED')
    need(review['selection'] == {'include_pattern': INCLUDE, 'exclude_pattern': EXCLUDE,
         'flags': 'IGNORECASE', 'source_records': 3481, 'previous_credential_records': 803,
         'selected_records': 690, 'remaining_outside_both_cohorts': 1988,
         'source_order_preserved': True, 'quota_cutoff': False}, 'SELECTION_CONTRACT_CHANGED')
    decisions = review['decisions']
    need(len(decisions) == 690, 'INCOMPLETE_REVIEW')
    for index, (decision, (ordinal, row)) in enumerate(zip(decisions, selected), 1):
        literal = row['values']['Keyword']
        expected = {'selected_ordinal': index, 'source_ordinal': ordinal,
                    'source_line': row['source_line'], 'original_literal': literal,
                    'normalized_literal': ka.normalize(literal),
                    'literal_utf8_sha256': hashlib.sha256(literal.encode('utf-8')).hexdigest(),
                    'complete_public_values_sha256': digest(row['values'])}
        need(set(decision) == set(expected) | {'decision', 'reason_codes'}, 'ROW_FIELDS_CHANGED')
        need(all(type(decision[k]) is type(v) and decision[k] == v for k, v in expected.items()),
             'LITERAL_OCCURRENCE_OR_COMPLETE_CELLS_CHANGED')
        codes = decision['reason_codes']
        need(isinstance(codes, list) and len(codes) > 0 and len(set(codes)) == len(codes),
             'INVALID_REASON_CODES')
        if decision['decision'] == PROPOSE:
            need(codes == [PROPOSAL_REASON], 'PROPOSAL_HAS_HOLD_REASON')
        else:
            need(decision['decision'] == 'HOLD' and set(codes) <= HOLD_REASONS, 'UNKNOWN_DISPOSITION')
    counts = dict(Counter(d['decision'] for d in decisions))
    reasons = dict(Counter(c for d in decisions for c in d['reason_codes']))
    need(counts == review['decision_counts'] == {PROPOSE: 487, 'HOLD': 203}, 'DECISION_COUNTS_CHANGED')
    need(reasons == review['reason_counts'] and
         set(review['reason_definitions']) == HOLD_REASONS | {PROPOSAL_REASON} and
         all(isinstance(v, str) and v for v in review['reason_definitions'].values()), 'REASON_COUNTS_CHANGED')
    return {'passed': True, 'source_records': len(rows), 'previous_credential_records': len(credential),
            'complete_literals_reviewed': len(selected), 'disjoint_previous_cohort': True,
            'remaining_outside_both_cohorts': 1988, 'decision_counts': counts,
            'library_rows_added': 0, 'approved': 0, 'deployed': 0}


def self_check(review, sources):
    # Mutate in-memory structures after the raw-byte check. Thus these exercise
    # actual invariants rather than merely relying on a changed document hash.
    cases = {
        'dropped_occurrence': lambda r: r['decisions'].pop(),
        'duplicate_occurrence': lambda r: r['decisions'].__setitem__(1, deepcopy(r['decisions'][0])),
        'reversed_order': lambda r: r['decisions'].reverse(),
        'altered_literal': lambda r: r['decisions'][0].__setitem__('original_literal', 'bank mortgage support'),
        'altered_complete_cells': lambda r: r['decisions'][0].__setitem__('complete_public_values_sha256', '0' * 64),
        'credential_overlap': lambda r: r['decisions'][0].__setitem__('source_ordinal', 3),
        'boolean_ordinal': lambda r: r['decisions'][0].__setitem__('selected_ordinal', True),
        'granted_approval': lambda r: r['limits'].__setitem__('independent_exclusion_approval', True),
        'rows_promoted': lambda r: r['limits'].__setitem__('library_rows_added', 487),
        'boolean_zero': lambda r: r['limits'].__setitem__('deployed', False),
        'source_pin_changed': lambda r: r['source_pins'].__setitem__('bank-access-navigation.json', '0' * 64),
        'selection_broadened': lambda r: r['selection'].__setitem__('exclude_pattern', ''),
        'summary_changed': lambda r: r['decision_counts'].__setitem__('HOLD', 0),
        'hold_unilaterally_promoted': lambda r: r['decisions'][6].__setitem__('decision', PROPOSE),
        'human_review_invented': lambda r: r['reviewer'].__setitem__('human_approval', True),
    }
    for name, mutate in cases.items():
        changed = deepcopy(review)
        mutate(changed)
        try:
            validate(changed, sources)
        except (ValueError, KeyError, TypeError):
            continue
        raise AssertionError('Tamper case accepted: ' + name)
    return list(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    start = perf_counter()
    sources = {name: read_json(SOURCE / name, pin) for name, pin in PINS.items()}
    review = read_json(FOLDER / 'review.json', REVIEW_SHA256)
    result = validate(review, sources)
    if args.self_check:
        result['tamper_cases_rejected'] = self_check(review, sources)
    result['elapsed_seconds'] = round(perf_counter() - start, 6)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
