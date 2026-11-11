"""Read-only public-cohort checks and temporary adversarial mutations; no platform calls."""
import copy
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import negative_admission as na
from keyword_audit import audit


class NegativeAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = na.reconstruct()
        cls.campaign = next(r for r in cls.inputs['campaigns'] if r['campaign_key'] == na.CAMPAIGN)
        cls.context = na.pinned(na.ROOT, na.FOLDER+'/service-context.json', na.CONTEXT_PIN)

    def reviewed(self, **changes):
        review = copy.deepcopy(self.inputs['review'])
        review.update(changes)
        review['subject_sha256'] = na.subject(review, self.context, self.campaign)
        return review

    def test_actual_cohort_counts_are_not_approval_or_target_completion(self):
        result = na.verify(at=date(2026, 11, 11))
        self.assertEqual((result['reviewed_eligible_rows'], result['deficit']), (1178, 12822))
        self.assertEqual(result['approved_exclusion_rows'], 0)
        self.assertEqual(result['protected_queries_indexed'], 12081)
        for key in ('exact_target_pass', 'deployment_export_allowed', 'production_writes_available',
                    'positive_library_coverage_verified', 'human_review_verified', 'live_campaign_mapping_verified'):
            self.assertIs(result[key], False)

    def test_original_source_occurrences_and_local_ids_remain_distinct(self):
        rows = self.inputs['records']
        self.assertEqual(len({r['keyword_id'] for r in rows}), 1178)
        self.assertEqual(sum(len(r['provenance_occurrences']) for r in rows), 1182)
        self.assertEqual(sum(len(r['provenance_occurrences']) == 2 for r in rows), 4)
        self.assertTrue(all(r['volume'] is None and r['cpc'] is None and r['observed_query'] is None for r in rows))
        self.assertTrue(all(r['risk_level'] == 'HIGH' and r['approval_state'] == 'PENDING' and
                            r['deployed_resource_ids'] == [] and r['deployed_at'] is None for r in rows))

    def test_review_cannot_claim_human_approval_or_live_authority(self):
        for key in ('human_review_verified', 'exclusion_approval_granted', 'live_binding_verified', 'production_authorized'):
            for value in (True, 0):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    na.validate_review(self.reviewed(**{key: value}), self.context, self.campaign)

    def test_actual_urls_ids_or_another_planning_slot_cannot_be_assigned(self):
        for key, value in [('actual_url', 'https://example.invalid/TEST-ONLY'),
                           ('google_campaign_id', 'TEST-ONLY-NOT-A-PLATFORM-ID'), ('campaign_key', 'BSRE-C0302')]:
            changed = dict(self.campaign, **{key: value})
            review = copy.deepcopy(self.inputs['review'])
            review['subject_sha256'] = na.subject(review, self.context, changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                na.validate_review(review, self.context, changed)

    def test_context_inventory_delivery_or_other_destination_claim_refused(self):
        for key, value in [('inventory_or_availability_verified', True),
                           ('submission_or_consent_action_performed', True),
                           ('live_campaign_mapping_assigned', True), ('source_url', 'https://example.invalid/TEST-ONLY')]:
            context = dict(self.context, **{key: value})
            review = copy.deepcopy(self.inputs['review'])
            review['subject_sha256'] = na.subject(review, context, self.campaign)
            with self.subTest(key=key), self.assertRaises(ValueError):
                na.validate_review(review, context, self.campaign)

    def test_source_or_scope_review_change_invalidates_subject(self):
        review = copy.deepcopy(self.inputs['review'])
        review['semantic_rationale']['EXPLICIT_INTERNSHIP_RESEARCH'] += ' TEST-ONLY CHANGE'
        with self.assertRaisesRegex(ValueError, 'REVIEW_SUBJECT_CHANGED'):
            na.validate_review(review, self.context, self.campaign)

    def test_deadline_is_bounded_and_expiry_holds_research(self):
        with self.assertRaisesRegex(ValueError, 'REVIEW_DATES'):
            na.validate_review(self.reviewed(valid_until='2027-12-11'), self.context, self.campaign)
        with self.assertRaisesRegex(ValueError, 'RESEARCH_NOT_ELIGIBLE'):
            na.verify(at=date(2026, 12, 12))
        with self.assertRaisesRegex(ValueError, 'RESEARCH_NOT_ELIGIBLE'):
            na.verify(at=date(2026, 11, 10))

    def test_keyword_holds_or_proposal_approval_cannot_be_promoted(self):
        wb = na.pinned(na.ROOT, na.COHORT+'/workbench.json', na.PINS[na.COHORT+'/workbench.json'])
        row = copy.deepcopy(next(r for r in wb['queue'] if r['disposition'] == 'NEGATIVE_EXACT_REVIEW'))
        row['disposition'] = 'HOLD'
        with self.assertRaisesRegex(ValueError, 'UNREVIEWED_OR_HELD_PHRASE'):
            na.make_record(row, self.inputs['review'], [])
        row['disposition'] = 'NEGATIVE_EXACT_REVIEW'
        row['assessment']['negative_scope_proposal']['approved'] = True
        with self.assertRaisesRegex(ValueError, 'PROPOSAL_AUTHORITY_CHANGED'):
            na.make_record(row, self.inputs['review'], [])

    def test_actual_protected_literal_and_missing_service_evidence_hold(self):
        row = copy.deepcopy(self.inputs['records'][0])
        protected = self.inputs['protected_queries'][0]
        row['original_text'] = row['normalized_text'] = protected['text']
        result = audit('negative', [row], self.inputs['sources'], self.inputs['campaigns'],
                       self.inputs['campaign_context'], [protected], date(2026, 11, 11))
        self.assertEqual(result['reviewed_eligible_rows'], 0)
        self.assertEqual(len(result['protected_conflicts']), 1)
        row = self.inputs['records'][0]
        result = audit('negative', [row], self.inputs['sources'], self.inputs['campaigns'],
                       [], [protected], date(2026, 11, 11))
        self.assertEqual(result['reviewed_eligible_rows'], 0)

    def test_variant_diagnostic_cannot_claim_google_or_concept_equivalence(self):
        for key in ('google_equivalence_verified', 'counts_distinct_concepts'):
            review = copy.deepcopy(self.inputs['review'])
            review['variant_review'][key] = True
            review['subject_sha256'] = na.subject(review, self.context, self.campaign)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'VARIANT_REVIEW_AUTHORITY'):
                na.validate_review(review, self.context, self.campaign)

    def test_pinned_reader_rejects_path_escape_and_digest_mutation(self):
        for relative in ('../private.json', '/tmp/private.json', 'C:/private.json',
                         'docs/../../private.json', 'docs\\private.json', '.git/config'):
            with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'PUBLIC_PATH_INVALID'):
                na.pinned(na.ROOT, relative, '0'*64)
        with self.assertRaisesRegex(ValueError, 'PINNED_INPUT_CHANGED'):
            na.pinned(na.ROOT, na.COHORT+'/workbench.json', '0'*64)

    def test_pinned_reader_refuses_file_and_parent_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); directory = root/'docs'; directory.mkdir()
            original = directory/'original.json'; original.write_text('{}', encoding='utf-8')
            alias = directory/'alias.json'; parent = directory/'linked'
            try:
                alias.symlink_to(original)
                parent.symlink_to(directory, target_is_directory=True)
            except OSError:
                if os.name != 'nt':
                    raise
                self.skipTest('Windows does not grant symlink creation to this test process')
            pin = hashlib.sha256(original.read_bytes()).hexdigest()
            for relative in ('docs/alias.json', 'docs/linked/original.json'):
                with self.subTest(relative=relative), self.assertRaisesRegex(ValueError, 'PUBLIC_PATH_LINKED'):
                    na.pinned(root, relative, pin)

    def test_persisted_record_tampering_fails_before_counting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for relative in ('data/negative.json', 'data/sources.json', 'data/campaign_context.json'):
                target = root/'tools/keyword-system'/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((na.ROOT/'tools/keyword-system'/relative).read_bytes())
            path = root/'tools/keyword-system/data/negative.json'
            rows = json.loads(path.read_text(encoding='utf-8'))
            rows[0]['approval_state'] = 'APPROVED'
            path.write_text(json.dumps(rows), encoding='utf-8')
            with patch.object(na, 'reconstruct', return_value=copy.deepcopy(self.inputs)):
                with self.assertRaisesRegex(ValueError, 'PINNED_INPUT_CHANGED'):
                    na.verify(root, at=date(2026, 11, 11))


if __name__ == '__main__':
    unittest.main()
