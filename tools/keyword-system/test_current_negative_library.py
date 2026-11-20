import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
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
        # Preserve acceptance of the original registered snapshot separately
        # from later complete-review holds, which have their own current tests.
        cls.inputs = current.reconstruct_registered(at=cls.when)
        cls.latest = current.latest_screen(cls.inputs, first.ROOT, cls.when)

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

    def test_latest_all_current_screen_preserves_every_body_and_all_twelve_holds(self):
        before = first.canonical(self.inputs)
        filtered = current.apply_latest(self.inputs, self.latest)
        self.assertEqual((len(filtered['records']), len(filtered['archived_records']),
                          len(filtered['protected_queries'])), (8025, 12, 15213))
        original = {r['keyword_id']: r for r in self.inputs['records']+self.inputs['archived_records']}
        after = {r['keyword_id']: r for r in filtered['records']+filtered['archived_records']}
        self.assertEqual(first.canonical(original), first.canonical(after))
        held = set(self.latest['review_index']['additional_held_keyword_ids'])
        self.assertEqual(len(held), 10)
        self.assertFalse(held & {r['keyword_id'] for r in filtered['records']})
        result = audit('negative', filtered['archived_records'], filtered['sources'],
            filtered['campaigns'], filtered['campaign_context'], filtered['protected_queries'], self.when)
        self.assertEqual((result['reviewed_eligible_rows'], len(result['protected_conflicts'])), (0, 12))
        self.assertEqual(first.canonical(self.inputs), before)
        filtered['records'][0]['original_text'] = 'detached test value'
        self.assertEqual(first.canonical(self.inputs), before)

    def test_reviewed_baseline_cannot_report_the_registered_count_as_eligible(self):
        with patch.object(current, 'reconstruct_registered', return_value=self.inputs), \
             patch.object(current, 'latest_screen', return_value=self.latest):
            filtered = current.reconstruct_reviewed_baseline(at=self.when)
            result = current.verify_reviewed_baseline(at=self.when)
        self.assertEqual(len(filtered['records']), 8025)
        self.assertEqual((result['registered_research_rows'], result['reviewed_eligible_rows'],
                          result['excluded_rows'], result['deficit'], result['held_historical_rows']),
                         (8035, 8025, 10, 5975, 12))
        self.assertTrue(result['admission_held'] and result['release_held'])
        self.assertFalse(result['deployment_export_allowed'] or result['release_authorized'])
        self.assertEqual(result['current_index_file'], current.LATEST_INDEX)

    def test_latest_overlay_rejects_unknown_duplicate_wrong_scope_or_mismatched_conflicts(self):
        for change in ('unknown', 'duplicate', 'scope', 'count', 'bool', 'authority'):
            impact = copy.deepcopy(self.latest['impact'])
            if change == 'unknown': impact['protected_conflicts'][0]['negative_id'] = 'unknown'
            elif change == 'duplicate': impact['protected_conflicts'].append(copy.deepcopy(impact['protected_conflicts'][0]))
            elif change == 'scope': impact['protected_conflicts'][0]['affected_campaign_keys'] = ['other']
            elif change == 'count': impact['latest_review_eligible_rows'] += 1
            elif change == 'bool': impact['master_additions'] = False
            else: impact['deployment_authorized'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                current.build_latest_index(self.inputs, impact)

    def test_resealed_latest_index_cannot_restore_a_newly_held_id(self):
        original = first.pinned
        def changed(root, relative, pin):
            value = original(root, relative, pin)
            if relative == current.LATEST_INDEX:
                value = copy.deepcopy(value)
                value['additional_held_keyword_ids'].pop()
                value['counts'].update(eligible=8026, additional_held=9, total_archived=11)
            return value
        with patch.object(first, 'pinned', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'LATEST_CURRENT_INDEX_CHANGED'):
                current.latest_screen(self.inputs, first.ROOT, self.when)

    def test_old_success_and_partial_historical_body_cannot_replace_the_latest_screen(self):
        module = runpy.run_path(str(first.ROOT/current.LATEST_FOLDER/'verify_coverage.py'))
        partial = copy.deepcopy(self.inputs)
        partial['records'] = partial['records'][:7188]
        report = module['pinned'](first.ROOT/current.LATEST_FOLDER/'report.json', module['REPORT_PIN'])
        with self.assertRaisesRegex(ValueError, 'REGISTERED_CURRENT_BASE_CHANGED'):
            module['build_impact'](report, data=partial, at=self.when)
        stale = copy.deepcopy(self.latest)
        stale['impact'].update(latest_review_eligible_rows=8035, latest_excluded_rows=0,
                               latest_deficit=5965, protected_conflicts=[], admission_held=False)
        module['build_impact'] = lambda *args, **kwargs: stale
        with patch.object(current.runpy, 'run_path', return_value=module):
            with self.assertRaisesRegex(ValueError, 'LATEST_CURRENT_IMPACT_CHANGED'):
                current.latest_screen(self.inputs, first.ROOT, self.when)

    def test_changed_latest_verifier_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/current.LATEST_FOLDER/'verify_coverage.py'
            path.parent.mkdir(parents=True)
            path.write_bytes(b'raise RuntimeError("must never execute")\n')
            with self.assertRaisesRegex(ValueError, 'LATEST_REVIEW_VERIFIER_CHANGED'):
                current.latest_screen(self.inputs, Path(folder), self.when)


if __name__ == '__main__':
    unittest.main()
