"""Read-only diagnostics must preserve custody, unresolved intent and every peer."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import source_membership_diagnostic as diagnostic


def source(*texts):
    return [{'source_line': n+3, 'values': {'Keyword': text}}
            for n, text in enumerate(texts, 1)]


def decision(rows, ordinal=1, hold=False):
    return {'source_ordinal': ordinal, 'source_line': rows[ordinal-1]['source_line'],
            'original_literal': rows[ordinal-1]['values']['Keyword'],
            'decision': 'HOLD' if hold else 'PROPOSE_FULL_EXACT_RESEARCH'}


def base():
    return {'records': [], 'archived_records': [], 'protected_queries': []}


class SourceMembershipDiagnosticTests(unittest.TestCase):
    def test_unreviewed_peer_can_hold_a_reviewed_proposal(self):
        rows = source('customer service resume', 'resume customer service')
        result = diagnostic.compare(base(), rows, [decision(rows)])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [])
        joined = result['source_row_comparisons'][0]['joins']
        self.assertEqual(joined[2]['outside_cohort_peer_ordinals'], [2])
        self.assertEqual(result['external_key_comparisons'], 8)
        self.assertEqual(result['within_source_key_comparisons'], 8)

    def test_duplicate_source_occurrences_are_not_dropped_or_self_joined(self):
        rows = source('receptionist cv', 'receptionist cv')
        result = diagnostic.compare(base(), rows, [decision(rows)])
        self.assertEqual(result['source_records_compared'], 2)
        self.assertEqual(len(result['source_row_comparisons']), 2)
        for n, row in enumerate(result['source_row_comparisons'], 1):
            self.assertTrue(all(j['source_peer_ordinals'] == [3-n] for j in row['joins']))

    def test_records_archives_and_protected_queries_all_participate(self):
        original = base()
        original['records'] = [{'keyword_id': 'K1', 'original_text': 'receptionist cv'}]
        original['archived_records'] = [{'keyword_id': 'K2', 'original_text': 'resume receptionist'}]
        original['protected_queries'] = [{'query_id': 'Q1', 'text': 'rent apartment'}]
        rows = source('receptionist cv', 'receptionist resume', 'rent apartment')
        result = diagnostic.compare(original, rows, [decision(rows, n) for n in range(1, 4)])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [])
        identities = {identity for row in result['source_row_comparisons']
                      for join in row['joins'] for identity in join['existing_identities']}
        self.assertEqual(identities, {'records:K1', 'archived_records:K2', 'protected_queries:Q1'})

    def test_closed_word_form_is_compared_even_when_tokens_differ(self):
        rows = source('customer service resume', 'customerservice resume')
        result = diagnostic.compare(base(), rows, [decision(rows)])
        self.assertEqual(result['source_row_comparisons'][0]['joins'][3]['source_peer_ordinals'], [2])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [])

    def test_preheld_row_is_compared_and_cannot_become_a_proposal(self):
        rows = source('resume vendor customer service')
        original = base()
        original['records'] = [{'keyword_id': 'K1', 'original_text': rows[0]['values']['Keyword']}]
        result = diagnostic.compare(original, rows, [decision(rows, hold=True)])
        self.assertEqual(result['semantic_holds_matching_existing_negatives'], [1])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [])
        self.assertEqual(result['cohort_external_key_comparisons'], 4)

    def test_noncohort_text_cannot_be_promoted_by_being_unmatched(self):
        result = diagnostic.compare(base(), source('rent apartment'), [])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [])
        self.assertEqual(result['noncohort_records_compared'], 1)
        self.assertEqual(result['source_row_comparisons'][0]['semantic_state'],
                         'UNASSESSED_NONCOHORT_NOT_ADMITTED')

    def test_compatibility_hold_overrides_absence_of_membership_conflicts(self):
        rows = source('receptionist cv')
        with patch.object(diagnostic.compatibility, 'profile_text', return_value={
                'original': {'classification': 'UNRESOLVED_TEXT'}}):
            result = diagnostic.compare(base(), rows, [decision(rows)])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [])
        self.assertEqual(result['held_or_conflicting_cohort_ordinals'], [1])

    def test_input_populations_remain_unchanged(self):
        original = base(); rows = source('receptionist cv'); reviewed = [decision(rows)]
        before = deepcopy((original, rows, reviewed))
        result = diagnostic.compare(original, rows, reviewed)
        result['source_row_comparisons'][0]['joins'].clear()
        self.assertEqual((original, rows, reviewed), before)

    def test_missing_population_and_reused_identity_are_rejected(self):
        rows = source('receptionist cv')
        for original in ({'records': [], 'archived_records': []},
                dict(base(), records=[{'keyword_id': 'K1', 'original_text': 'one'},
                                      {'keyword_id': 'K1', 'original_text': 'two'}])):
            with self.assertRaises(ValueError):
                diagnostic.compare(original, rows, [decision(rows)])

    def test_boolean_and_duplicate_review_ordinals_are_rejected(self):
        rows = source('receptionist cv')
        for reviewed in ([dict(decision(rows), source_ordinal=True)],
                         [decision(rows), decision(rows)]):
            with self.assertRaisesRegex(ValueError, 'INVALID_OR_DUPLICATE'):
                diagnostic.compare(base(), rows, reviewed)

    def test_altered_occurrence_and_literal_are_rejected(self):
        rows = source('receptionist cv')
        for changed in ({'source_line': 90}, {'source_line': True},
                        {'original_literal': 'rent apartment'}):
            with self.assertRaisesRegex(ValueError, 'REVIEW_SOURCE_BINDING'):
                diagnostic.compare(base(), rows, [dict(decision(rows), **changed)])

    def test_unmatched_result_grants_no_admission_or_platform_claim(self):
        rows = source('receptionist cv')
        result = diagnostic.compare(base(), rows, [decision(rows)])
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'], [1])
        self.assertEqual(result['library_rows_added'], 0)
        for field in ('google_equivalence_verified', 'provider_identity_verified',
                      'counts_distinct_concepts', 'admission_approved',
                      'exclusion_approval_granted', 'deployment_authorized'):
            self.assertIs(result[field], False)


if __name__ == '__main__':
    unittest.main()
