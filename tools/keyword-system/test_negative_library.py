"""Actual-source composition and isolated adversarial tests; no platform requests."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import negative_admission as first
import negative_employment_admission as employment
import negative_library as library
import negative_reviewed_cohort as registered
from keyword_audit import audit


class NegativeLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.initial = first.reconstruct()
        cls.second = employment.reconstruct(prior=cls.initial)
        cls.inputs = library.reconstruct()
        cls.context = first.pinned(first.ROOT, first.FOLDER+'/service-context.json', first.CONTEXT_PIN)
        cls.campaign = next(r for r in cls.initial['campaigns'] if r['campaign_key'] == first.CAMPAIGN)
        cls.bindings = first.pinned(first.ROOT, first.REPORT, first.PINS[first.REPORT])['source_bindings']['review_workbenches_sha256']

    def review(self, **changes):
        review = copy.deepcopy(self.second['review'])
        review.update(changes)
        review['subject_sha256'] = employment.subject(review, self.context, self.campaign, self.bindings)
        return review

    def test_actual_library_is_partial_research_never_approval_or_release(self):
        result = library.verify(at=date(2026, 11, 11))
        self.assertEqual((result['input_rows'], result['reviewed_eligible_rows'], result['deficit']), (3428, 3428, 10572))
        self.assertEqual(result['source_occurrences_retained'], 3432)
        self.assertEqual(result['protected_queries_indexed'], 12163)
        self.assertEqual(result['source_capture_count'], 6)
        self.assertEqual(result['approved_exclusion_rows'], 0)
        for key in ('exact_target_pass', 'deployment_export_allowed', 'production_writes_available',
                    'positive_library_coverage_verified', 'human_review_verified', 'live_campaign_mapping_verified'):
            self.assertIs(result[key], False)

    def test_initial_1178_records_reproduce_original_published_bytes(self):
        raw = (json.dumps(self.inputs['records'][:1178], ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '57405055be2db88f3b982436348a7e01517af573f5d6cf77667554e81217401a')
        self.assertEqual(first.verify(at=date(2026, 11, 11))['reviewed_eligible_rows'], 1178)

    def test_original_two_cohorts_reproduce_their_complete_published_master(self):
        raw = (json.dumps(self.inputs['records'][:2113], ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'ba70665227a02cfb92bafd94dd60db9d3565550cbdaac91c146ce9763087873e')

    def test_previous_3016_records_preserve_published_academic_master_bytes(self):
        raw = (json.dumps(self.inputs['records'][:3016], ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        self.assertEqual(hashlib.sha256(raw).hexdigest(), '603d3f46d08b144a3f0922eea00abcb32c223b45ad749ba73f7edcd706fbc324')

    def test_one_fresh_reconstruction_per_registered_cohort_per_invocation(self):
        with patch.object(first, 'reconstruct', wraps=first.reconstruct) as a, \
             patch.object(employment, 'reconstruct', wraps=employment.reconstruct) as b, \
             patch.object(registered, 'reconstruct', wraps=registered.reconstruct) as c:
            result = library.verify(at=date(2026, 11, 11))
        self.assertEqual(a.call_count, 1)
        self.assertEqual(b.call_count, 1)
        self.assertEqual(c.call_count, len(registered.CATALOG))
        self.assertEqual(result['reviewed_eligible_rows'], 3428)

    def test_previous_success_does_not_cache_source_inputs_across_invocations(self):
        library.verify(at=date(2026, 11, 11))
        original = first.pinned
        def changed_source(root, relative, digest):
            if relative == first.COHORT+'/employment-lifecycle.json':
                raise ValueError('TEST_ONLY_SOURCE_CHANGED_AFTER_SUCCESS')
            return original(root, relative, digest)
        with patch.object(first, 'pinned', side_effect=changed_source):
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED_AFTER_SUCCESS'):
                library.verify(at=date(2026, 11, 11))

    def test_overlap_and_spelling_holds_cannot_pad_counts(self):
        self.assertEqual(len(self.second['existing_overlap_phrases']), 4)
        self.assertEqual(len(self.second['records']), 935)
        current = {r['normalized_text'] for r in self.second['records']}
        self.assertFalse(current & set(self.second['existing_overlap_phrases']))
        self.assertFalse(current & set(employment.HELD))
        protected = {r['text'] for r in self.inputs['protected_queries']}
        self.assertTrue(set(employment.HELD) <= protected)
        self.assertEqual(len({r['keyword_id'] for r in self.inputs['records']}), 3428)

    def test_source_spelling_diacritics_and_unknown_metrics_preserved(self):
        texts = {r['original_text'] for r in self.second['records']}
        self.assertIn('engel and v\u00f6lkers careers', texts)
        self.assertIn('f\u00e4m properties careers', texts)
        for row in self.second['records']:
            self.assertIsNone(row['volume'])
            self.assertIsNone(row['cpc'])
            self.assertIsNone(row['observed_query'])
            self.assertEqual(row['approval_state'], 'PENDING')
            self.assertEqual(row['risk_level'], 'HIGH')
            self.assertEqual(row['deployed_resource_ids'], [])
            self.assertEqual(row['eligible_campaigns'], [first.CAMPAIGN])

    def test_no_cohort_can_claim_human_approval_or_live_authority(self):
        for key in ('human_review_verified', 'exclusion_approval_granted', 'live_binding_verified', 'production_authorized'):
            for value in (True, 0):
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'CANNOT_GRANT_AUTHORITY'):
                    employment.validate_review(self.review(**{key: value}), self.context, self.campaign, self.bindings)

    def test_selection_and_existing_overlaps_are_bound(self):
        for key, value in [('selected_rows', 940), ('pool_rows', 935), ('existing_cohort_overlaps', 0),
                           ('held_phrases', {}), ('source_selections', {})]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'SELECTION_CHANGED'):
                employment.validate_review(self.review(**{key: value}), self.context, self.campaign, self.bindings)

    def test_subject_cannot_be_reused_for_changed_semantics(self):
        review = copy.deepcopy(self.second['review'])
        review['semantic_rationale']['EXPLICIT_EMPLOYMENT_RESEARCH'] += ' TEST-ONLY CHANGE'
        with self.assertRaisesRegex(ValueError, 'SUBJECT_CHANGED'):
            employment.validate_review(review, self.context, self.campaign, self.bindings)

    def test_review_expiry_and_future_review_hold_the_whole_library(self):
        for at in (date(2026, 12, 12), date(2026, 11, 10)):
            with self.subTest(at=at), self.assertRaises(ValueError):
                library.verify(at=at)
            with self.subTest(second_at=at), self.assertRaisesRegex(ValueError, 'EMPLOYMENT_RESEARCH_NOT_ELIGIBLE'):
                employment.verify(at=at)

    def test_variant_review_cannot_claim_platform_equivalence(self):
        for key in ('google_equivalence_verified', 'counts_distinct_concepts'):
            value = dict(self.second['review']['variant_review'], **{key: True})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'VARIANT_AUTHORITY'):
                employment.validate_review(self.review(variant_review=value), self.context, self.campaign, self.bindings)

    def test_duplicate_rows_cannot_silently_merge_or_count_twice(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_OR_DISAGREEMENT'):
            library.compose([self.initial, self.initial])
        changed = copy.deepcopy(self.second)
        changed['records'][0]['keyword_id'] = self.initial['records'][0]['keyword_id']
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_OR_DISAGREEMENT'):
            library.compose([self.initial, changed])

    def test_same_phrase_under_different_ids_or_case_still_fails(self):
        changed = copy.deepcopy(self.second)
        changed['records'][0]['original_text'] = self.initial['records'][0]['original_text'].upper()
        with self.assertRaisesRegex(ValueError, 'PHRASE_DUPLICATE'):
            library.compose([self.initial, changed])

    def test_empty_or_disagreeing_campaign_register_fails(self):
        with self.assertRaisesRegex(ValueError, 'COHORTS_REQUIRED'):
            library.compose([])
        changed = copy.deepcopy(self.second)
        changed['campaigns'][0]['actual_url'] = 'https://example.invalid/TEST-ONLY'
        with self.assertRaisesRegex(ValueError, 'REGISTRY_DISAGREEMENT'):
            library.compose([self.initial, changed])

    def test_source_context_or_protection_disagreement_never_newest_wins(self):
        for key, field in [('sources', 'evidence_ref'), ('campaign_context', 'evidence_ref'),
                           ('protected_queries', 'evidence_ref')]:
            changed = copy.deepcopy(self.second)
            changed[key].append(dict(self.initial[key][0], **{field: 'TEST-ONLY-DIFFERENT-EVIDENCE'}))
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'DUPLICATE_OR_DISAGREEMENT'):
                library.compose([self.initial, changed])

    def test_protection_is_rechecked_after_composition(self):
        row = copy.deepcopy(self.second['records'][0])
        row['original_text'] = row['normalized_text'] = self.initial['protected_queries'][0]['text']
        result = audit('negative', [row], self.inputs['sources'], self.inputs['campaigns'],
            self.inputs['campaign_context'], self.inputs['protected_queries'], date(2026, 11, 11))
        self.assertEqual(result['reviewed_eligible_rows'], 0)
        self.assertEqual(len(result['protected_conflicts']), 1)

    def test_full_master_tampering_fails_even_when_cohort_reconstruction_is_intact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ('data/negative.json', 'data/sources.json', 'data/campaign_context.json'):
                path = root/'tools/keyword-system'/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((first.ROOT/'tools/keyword-system'/relative).read_bytes())
            path = root/'tools/keyword-system/data/negative.json'
            rows = json.loads(path.read_text(encoding='utf-8'))
            rows[-1]['approval_state'] = 'APPROVED'
            path.write_text(json.dumps(rows), encoding='utf-8')
            with patch.object(library, 'reconstruct', return_value=self.inputs):
                with self.assertRaisesRegex(ValueError, 'PINNED_INPUT_CHANGED'):
                    library.verify(root, at=date(2026, 11, 11))
                pins = dict(library.OUTPUT_PINS, **{'data/negative.json': hashlib.sha256(path.read_bytes()).hexdigest()})
                with patch.object(library, 'OUTPUT_PINS', pins):
                    with self.assertRaisesRegex(ValueError, 'MASTER_DIFFERS_FROM_COHORTS'):
                        library.verify(root, at=date(2026, 11, 11))

    def test_unregistered_extra_or_missing_cohort_records_cannot_be_accepted(self):
        initial_only = library.compose([self.initial])
        self.assertEqual(len(initial_only['records']), 1178)
        with patch.object(library, 'reconstruct', return_value=initial_only):
            with self.assertRaisesRegex(ValueError, 'MASTER_DIFFERS_FROM_COHORTS'):
                library.verify(at=date(2026, 11, 11))


if __name__ == '__main__':
    unittest.main()
