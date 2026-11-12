"""Small pinned-source and synthetic integrity tests; no baseline reconstruction."""
from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch

import append_only_admission as stage
import entertainment_admission as e
import current_negative_library as current
import negative_library as history


class EntertainmentAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.when = date(2026, 11, 11)
        cls.material = e.load_sources(e.first.ROOT)
        cls.review = e.make_review(e.first.ROOT, cls.when)
        cls.material['review'] = cls.review

    def fixture(self):
        return {'records': [], 'archived_records': [], 'sources': [], 'protected_queries': [],
            'campaigns': self.material['registry'], 'campaign_context': [{
                'campaign_key': e.first.CAMPAIGN, 'services': ['residential_rental'],
                'evidence_ref': e.first.FOLDER+'/service-context.json',
                'reviewed_on': '2026-11-11', 'valid_until': '2026-12-11',
                'scope_kind': 'PLANNING_PURPOSE_ONLY', 'live_resource_mapping_claimed': False}],
            'synthetic_historical_extra': {'preserve': ['complete original marker']},
            'deployment_authorized': False, 'production_writes_available': False}

    def extended(self):
        base = self.fixture()
        cohort, protections = e.build_cohort(base, self.material)
        return base, stage.extend(base, cohort, protections,
            expected_base_sha256=stage.digest(base), stage_key=e.STAGE_KEY)

    def test_immutable_reviews_merge_only_nine_extra_holds(self):
        m = self.material
        self.assertEqual((len(m['rows']), len(m['selected']), len(m['held'])), (518,303,215))
        initial = e.first.pinned(e.first.ROOT, e.CAPTURE+'/review.json',
                                 e.SOURCE_PINS[e.CAPTURE+'/review.json'])
        original_holds = {r['ordinal'] for r in initial['assessments'] if r['disposition'] == 'HOLD'}
        self.assertEqual(len(original_holds), 200)
        self.assertTrue(original_holds <= set(m['held']))
        peer_selected = {r['ordinal'] for r in m['independent']['assessments'] if r['decision'] == 'PROPOSE_EXACT'}
        self.assertEqual(set(m['selected'])-peer_selected, e.RESOLVED)
        self.assertTrue(all(i in m['held'] for i,r in m['rows'].items() if '.' in r['keyword']))

    def test_review_authority_scope_partition_and_dates_fail_closed_after_reseal(self):
        changes = [lambda r:r.update(human_review_verified=0),
            lambda r:r.update(exclusion_approval_granted=True),
            lambda r:r.update(campaign_key='BSRE-C0001'),
            lambda r:r['selected_ordinals'].append(6),
            lambda r:r['held_ordinals'].pop(),
            lambda r:r['implementation'].clear(),
            lambda r:r['variant_review'].update(google_equivalence_verified=True),
            lambda r:r.update(valid_until='2026-12-12')]
        for change in changes:
            review = deepcopy(self.review); change(review)
            review['subject_sha256'] = e.review_subject(review, self.material)
            with self.assertRaises(ValueError):
                e.validate_review(review, self.material, self.when)
        with self.assertRaises(ValueError):
            e.validate_review(self.review, self.material, date(2027,1,1))

    def test_source_capture_cannot_claim_metrics_csv_or_observed_queries(self):
        original = e.first.pinned
        for field,value in [('metrics_status','CAPTURED'),('is_csv_export',True),('observed_served_queries',True)]:
            def changed(root, file, pin):
                document = original(root, file, pin)
                if file == e.CAPTURE+'/capture.json':
                    document = deepcopy(document); document[field] = value
                return document
            with patch.object(e.first,'pinned',side_effect=changed):
                with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_CAPTURE_IDENTITY_CHANGED'):
                    e.load_sources(e.first.ROOT)

    def test_delta_cannot_reopen_original_hold(self):
        original = e.first.pinned
        initial = original(e.first.ROOT,e.CAPTURE+'/review.json',e.SOURCE_PINS[e.CAPTURE+'/review.json'])
        delta = deepcopy(self.material['delta'])
        delta['resolutions'][0]['ordinal'] = 6
        with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_DELTA_COVERAGE_CHANGED'):
            e.merged_selection(initial,self.material['independent'],delta,self.material['lexical'])

    def test_missing_variant_member_rejected(self):
        original = e.first.pinned(e.first.ROOT,e.CAPTURE+'/review.json',e.SOURCE_PINS[e.CAPTURE+'/review.json'])
        peer = deepcopy(self.material['independent'])
        peer['equal_token_bag_group_reviews'][0]['ordinals'].pop()
        with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_VARIANT_PARTITION_CHANGED'):
            e.merged_selection(original,peer,self.material['delta'],self.material['lexical'])

    def test_actual_source_orders_remain_distinct_but_case_only_duplicates_fail(self):
        e._verify_membership(self.fixture(),self.material)
        changed = deepcopy(self.material)
        changed['rows'][2]['keyword'] = changed['rows'][1]['keyword'].upper()
        with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_ORDERED_VARIANT_COLLISION'):
            e._verify_membership(self.fixture(),changed)

    def test_current_protected_and_nonidentical_token_peers_are_recomputed(self):
        for field,row in [('records',{'original_text':'house flipper game'}),
                          ('archived_records',{'original_text':'flipper game house'}),
                          ('protected_queries',{'text':'house flipper'})]:
            base = self.fixture(); base[field].append(row)
            with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_FRESH_MEMBERSHIP_CHANGED'):
                e._verify_membership(base,self.material)

    def test_synthetic_extension_preserves_every_extra_and_source_literal(self):
        base = self.fixture(); before = deepcopy(base)
        cohort, protections = e.build_cohort(base,self.material)
        inputs = stage.extend(base,cohort,protections,expected_base_sha256=stage.digest(base),stage_key=e.STAGE_KEY)
        self.assertEqual(stage.recover_base(inputs,stage_key=e.STAGE_KEY),before)
        self.assertEqual(base,before)
        self.assertEqual((len(inputs['records']),len(inputs['protected_queries'])),(303,215))
        for row in inputs['records']:
            occurrence = row['provenance_occurrences'][0]
            self.assertEqual(row['original_text'],self.material['rows'][occurrence['source_ordinal']]['keyword'])
            self.assertEqual(row['source_type'],'official_reference')
            self.assertTrue(all(row[k] is None for k in ('volume','cpc','observed_query','observation_date')))
            self.assertEqual((row['match_type'],row['risk_level'],row['approval_state']),('EXACT','HIGH','PENDING'))
        changed = deepcopy(inputs); changed['synthetic_historical_extra']['preserve'].append('changed')
        with self.assertRaises(ValueError):stage.recover_base(changed,stage_key=e.STAGE_KEY)

    def test_arbitrary_base_and_unregistered_review_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_PRIOR_BASE_CHANGED'):
            e.verify_base(self.fixture(),self.material)
        with patch.object(e,'REVIEW_PIN',None):
            with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_REVIEW_UNREGISTERED'):
                e.load_reviewed(e.first.ROOT,self.when)

    def test_resealed_domain_tail_changes_rejected_before_saved_output_check(self):
        base, inputs = self.extended()
        changes = [lambda x:x['records'][0]['provenance_occurrences'][0].update(source_ordinal=6),
            lambda x:x['records'][0].update(volume=0),
            lambda x:x['records'][0].update(observed_query='claimed served query'),
            lambda x:x['records'][0].update(approval_state='APPROVED'),
            lambda x:x['protected_queries'].pop(),
            lambda x:x['sources'][0].update(kind='first_party_observed')]
        for change in changes:
            changed = deepcopy(inputs); change(changed)
            with patch.object(e,'load_reviewed',return_value=self.material), \
                 patch.object(e,'verify_base'),patch.object(e,'BASE_SHA256',stage.digest(base)), \
                 patch.object(e,'_outputs') as outputs:
                with self.assertRaisesRegex(ValueError,'ENTERTAINMENT_DERIVED_BODIES_CHANGED'):
                    e.check_saved(changed,e.first.ROOT,self.when)
                outputs.assert_not_called()

    def test_all_twenty_two_public_entrypoints_start_from_fresh_history(self):
        calls = (current.reconstruct_vendor_snapshot,current.verify_vendor_snapshot,
            current.reconstruct_followup_snapshot,current.verify_followup_snapshot,
            current.reconstruct_valuation_snapshot,current.verify_valuation_snapshot,
            current.reconstruct_ofqual_snapshot,current.verify_ofqual_snapshot,
            current.reconstruct_entertainment_snapshot,current.verify_entertainment_snapshot,
            current.reconstruct_apprenticeship_snapshot,current.verify_apprenticeship_snapshot,
            current.reconstruct_ofqual_occupational_snapshot,current.verify_ofqual_occupational_snapshot,
            current.reconstruct_ofqual_veterinary_snapshot,current.verify_ofqual_veterinary_snapshot,
            current.reconstruct_bank_credential_snapshot,current.verify_bank_credential_snapshot,
            current.reconstruct_bank_support_snapshot,current.verify_bank_support_snapshot,
            current.reconstruct_ofqual_animal_care_snapshot,current.verify_ofqual_animal_care_snapshot,
            current.reconstruct_bank_channel_login_snapshot,current.verify_bank_channel_login_snapshot,
            current.reconstruct,current.verify)
        with patch.object(history,'reconstruct_current',side_effect=ValueError('fresh source unavailable')) as fresh:
            for call in calls:
                with self.assertRaisesRegex(ValueError,'fresh source unavailable'):call(at=self.when)
            self.assertEqual(fresh.call_count,26)


if __name__ == '__main__':
    unittest.main()
