"""Complete read-only lexical comparison, including held and noncohort source peers.

Unmatched wording is not semantic, platform-equivalence or admission approval.
The caller owns custody, source pins, current-history verification and scope.
"""
from collections import defaultdict

import keyword_audit as ka
import keyword_text_compatibility as compatibility

METHODS = ('normalized_literal', 'ordered_tokens', 'token_bag', 'closed_alphanumeric')
BASE_FIELDS = (('records', 'original_text', 'keyword_id'),
               ('archived_records', 'original_text', 'keyword_id'),
               ('protected_queries', 'text', 'query_id'))


def need(condition, code):
    if not condition:
        raise ValueError(code)


def keys(text):
    need(type(text) is str and bool(ka.normalize(text)), 'INVALID_COMPLETE_LITERAL')
    tokens = tuple(ka.tokens(text))
    return (ka.normalize(text), tokens, tuple(sorted(tokens)),
            ''.join(char for char in ka.normalize(text) if char.isalnum()))


def compare(base, rows, decisions):
    """Join four keys for every original row; never mutate or filter the source."""
    need(type(rows) is list and bool(rows) and type(decisions) is list,
         'INVALID_SOURCE_OR_DECISIONS')
    external = {method: defaultdict(set) for method in METHODS}
    for field, text_field, id_field in BASE_FIELDS:
        need(type(base.get(field)) is list, 'MISSING_COMPLETE_BASE_POPULATION')
        seen = set()
        for row in base[field]:
            identity = row[id_field]
            need(type(identity) is str and identity and identity not in seen,
                 'DUPLICATE_OR_INVALID_BASE_IDENTITY')
            seen.add(identity)
            for method, value in zip(METHODS, keys(row[text_field])):
                external[method][value].add(field+':'+identity)
    source_keys = []; peers = {method: defaultdict(set) for method in METHODS}
    for ordinal, row in enumerate(rows, 1):
        need(type(row.get('source_line')) is int and row['source_line'] > 0,
             'INVALID_SOURCE_OCCURRENCE')
        values = keys(row['values']['Keyword'])
        source_keys.append(values)
        for method, value in zip(METHODS, values):
            peers[method][value].add(ordinal)
    reviewed = {}
    for decision in decisions:
        ordinal = decision['source_ordinal']
        need(type(ordinal) is int and 1 <= ordinal <= len(rows) and ordinal not in reviewed,
             'INVALID_OR_DUPLICATE_REVIEWED_OCCURRENCE')
        need(decision['decision'] in ('HOLD', 'PROPOSE_FULL_EXACT_RESEARCH') and
             decision['original_literal'] == rows[ordinal-1]['values']['Keyword'] and
             type(decision['source_line']) is int and
             decision['source_line'] == rows[ordinal-1]['source_line'],
             'REVIEW_SOURCE_BINDING_CHANGED')
        reviewed[ordinal] = decision
    comparisons = []; unmatched = []; held = []; hold_negative_conflicts = []
    for ordinal, (row, values) in enumerate(zip(rows, source_keys), 1):
        joins = []; conflict = False
        for method, value in zip(METHODS, values):
            existing = sorted(external[method].get(value, ()))
            others = sorted(peers[method][value] - {ordinal})
            conflict = conflict or bool(existing) or bool(others)
            joins.append({'method': method, 'existing_identities': existing,
                          'source_peer_ordinals': others,
                          'outside_cohort_peer_ordinals': [n for n in others if n not in reviewed]})
        result = {'source_ordinal': ordinal, 'source_line': row['source_line'],
                  'semantic_state': 'REVIEWED_COHORT' if ordinal in reviewed else
                                    'UNASSESSED_NONCOHORT_NOT_ADMITTED',
                  'joins': joins}
        if ordinal in reviewed:
            decision = reviewed[ordinal]
            profile = compatibility.profile_text(row['values']['Keyword'])['original']
            result['original_text_compatibility'] = profile
            result['semantic_decision'] = decision['decision']
            if (decision['decision'] == 'PROPOSE_FULL_EXACT_RESEARCH' and not conflict and
                    profile['classification'] == 'NO_KNOWN_INCOMPATIBILITY_DETECTED'):
                unmatched.append(ordinal)
            else:
                held.append(ordinal)
            if decision['decision'] == 'HOLD' and any(
                    identity.startswith('records:') for join in joins
                    for identity in join['existing_identities']):
                hold_negative_conflicts.append(ordinal)
        comparisons.append(result)
    return {'scope': 'READ_ONLY_PRE_ADMISSION_DIAGNOSTIC',
            'source_records_compared': len(rows), 'reviewed_records_compared': len(reviewed),
            'noncohort_records_compared': len(rows)-len(reviewed),
            'external_key_comparisons': 4*len(rows), 'within_source_key_comparisons': 4*len(rows),
            'cohort_external_key_comparisons': 4*len(reviewed),
            'cohort_within_source_key_comparisons': 4*len(reviewed),
            'complete_base_counts': {field: len(base[field]) for field, _, _ in BASE_FIELDS},
            'lexical_methods': list(METHODS), 'source_row_comparisons': comparisons,
            'unmatched_compatible_proposal_ordinals': unmatched,
            'held_or_conflicting_cohort_ordinals': held,
            'semantic_holds_matching_existing_negatives': hold_negative_conflicts,
            'google_equivalence_verified': False, 'provider_identity_verified': False,
            'counts_distinct_concepts': False, 'admission_approved': False,
            'library_rows_added': 0, 'exclusion_approval_granted': False,
            'deployment_authorized': False}
