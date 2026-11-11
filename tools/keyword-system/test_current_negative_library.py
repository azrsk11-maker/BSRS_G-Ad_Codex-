import copy
from datetime import date
import hashlib
import json
import unittest
from unittest.mock import patch

import current_negative_library as current
import negative_admission as first
import negative_library as history
import negative_reviewed_cohort as registered
from keyword_audit import audit


class CurrentLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.when = date(2026, 11, 11)
        cls.inputs = current.reconstruct(at=cls.when)

    def test_full_current_source_preserves_originals_and_reconciles_the_count(self):
        inputs = self.inputs
        raw = (first.ROOT/'tools/keyword-system/data/negative.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), history.OUTPUT_PINS['data/negative.json'])
        original = json.loads(raw)
        held = {r['keyword_id'] for r in inputs['archived_records']}
        prior = [r for r in original if r['keyword_id'] not in held]
        self.assertEqual(first.canonical(inputs['records'][:7186]), first.canonical(prior))
        self.assertEqual(first.canonical(inputs['archived_records']),
                         first.canonical([r for r in original if r['keyword_id'] in held]))
        self.assertEqual((len(inputs['records']), len(held), len(inputs['protected_queries'])), (8035, 2, 13905))
        self.assertFalse(held & {r['keyword_id'] for r in inputs['records']})
        result = current.check_outputs(inputs, first.ROOT, self.when)
        self.assertEqual((result['reviewed_eligible_rows'], result['new_rows'], result['deficit']), (8035, 849, 5965))
        self.assertFalse(result['deployment_export_allowed'])
        self.assertFalse(result['release_authorized'])
        self.assertEqual(result['approved_exclusion_rows'], 0)

    def test_new_holds_and_archived_recruitment_cannot_reenter_current_research(self):
        review = self.inputs['current_cohorts'][0]
        self.assertEqual((review['pool_rows'], review['existing_cohort_overlaps'], len(review['held_phrases'])), (1051, 178, 24))
        current_text = {r['normalized_text'] for r in self.inputs['records']}
        protected = {r['text'] for r in self.inputs['protected_queries']}
        self.assertTrue(set(review['held_phrases']) <= protected)
        self.assertFalse(set(review['held_phrases']) & current_text)
        result = audit('negative', self.inputs['archived_records'], self.inputs['sources'],
            self.inputs['campaigns'], self.inputs['campaign_context'], self.inputs['protected_queries'], self.when)
        self.assertEqual(result['reviewed_eligible_rows'], 0)
        self.assertEqual(len(result['protected_conflicts']), 2)
        for row in self.inputs['records'][7186:]:
            self.assertEqual(row['eligible_campaigns'], [first.CAMPAIGN])
            self.assertEqual((row['match_type'], row['risk_level'], row['approval_state']), ('EXACT', 'HIGH', 'PENDING'))
            self.assertIsNone(row['volume'])
            self.assertIsNone(row['cpc'])
            self.assertEqual(row['deployed_resource_ids'], [])

    def test_resealed_index_response_cannot_restore_an_archived_id(self):
        original = first.pinned
        def changed(root, relative, pin):
            value = original(root, relative, pin)
            if relative == current.INDEX:
                value = copy.deepcopy(value)
                value['eligible_keyword_ids'].append(value['held_historical_keyword_ids'].pop())
                value['counts'].update(eligible=8036, held_historical=1)
            return value
        with patch.object(first, 'pinned', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'CURRENT_LIBRARY_INDEX_CHANGED'):
                current.check_outputs(self.inputs, first.ROOT, self.when)

    def test_unknown_registration_and_changed_review_cannot_gain_authority(self):
        entry = dict(registered.CURRENT_CATALOG[0], key='unregistered')
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_COHORT'):
            registered.reconstruct(first.ROOT, entry, self.inputs)
        original = first.pinned
        def changed(root, relative, pin):
            value = original(root, relative, pin)
            if relative == current.FOLDER+'/review.json':
                value = copy.deepcopy(value)
                value['exclusion_approval_granted'] = True
            return value
        with patch.object(first, 'pinned', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'REGISTERED_REVIEW_CANNOT_GRANT_AUTHORITY'):
                registered.reconstruct(first.ROOT, registered.CURRENT_CATALOG[0], self.inputs)

    def test_duplicate_phrase_and_history_replacement_fail_before_index_acceptance(self):
        changed = copy.deepcopy(self.inputs)
        changed['records'].append(copy.deepcopy(changed['records'][0]))
        with self.assertRaisesRegex(ValueError, 'CURRENT_LIBRARY_IDENTITY_COLLISION'):
            current.build_index(changed)
        changed = copy.deepcopy(self.inputs)
        changed['records'][0], changed['records'][1] = changed['records'][1], changed['records'][0]
        with self.assertRaisesRegex(ValueError, 'CURRENT_LIBRARY_HISTORY_REPLACED'):
            current.build_index(changed)

    def test_allocation_preserves_targets_and_deducts_archive_without_budget_change(self):
        previous = first.pinned(first.ROOT, current.PREVIOUS_ALLOCATION, current.PREVIOUS_ALLOCATION_PIN)
        allocation = current.allocation(self.inputs, previous)
        self.assertEqual(allocation['targets'], previous['after'])
        self.assertEqual((allocation['total_target'], allocation['total_admitted'], allocation['total_remaining']), (14000, 8035, 5965))
        self.assertEqual(allocation['held_deduction'], {'EMPLOYMENT': 2})
        self.assertEqual(sum(allocation['new_rows'].values()), 849)
        self.assertFalse(allocation['owner_approval_claimed'])
        self.assertFalse(allocation['media_budget_changed'])
        self.assertFalse(allocation['exclusion_approval_granted'])

    def test_each_verification_starts_a_fresh_base_instead_of_reusing_acceptance(self):
        with patch.object(history, 'reconstruct_current', side_effect=ValueError('fresh source failure')) as fresh:
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'fresh source failure'):
                    current.verify(at=self.when)
            self.assertEqual(fresh.call_count, 2)


if __name__ == '__main__':
    unittest.main()
