"""Fresh-history admission, source-peer holds and scoped rollback regressions."""
from copy import deepcopy
from datetime import date, timedelta
import unittest
from unittest.mock import patch

import append_only_admission as stage
import current_negative_library as current
import front_office_document_admission as e


class FrontOfficeDocumentAdmissionTests(unittest.TestCase):
    FRESH_BASE = None
    FRESH_INPUTS = None

    @classmethod
    def setUpClass(cls):
        cls.when=date(2026,11,13)
        cls.base=cls.FRESH_BASE if cls.FRESH_BASE is not None else current.reconstruct_bank_channel_login_snapshot(at=cls.when)
        cls.material=e.load_reviewed(e.first.ROOT,cls.when)
        cls.inputs=cls.FRESH_INPUTS if cls.FRESH_INPUTS is not None else e.extend(cls.base,e.first.ROOT,cls.when)

    def test_complete_history_and_rollback_preserve_every_old_body_and_field(self):
        self.assertEqual(stage.recover_base(self.inputs,stage_key=e.STAGE_KEY),self.base)
        self.assertEqual(stage.digest(self.base),e.BASE_SHA256)
        for field in ('records','protected_queries','sources'):
            self.assertEqual(self.inputs[field][:len(self.base[field])],self.base[field])
        for field in set(self.base)-{'records','protected_queries','sources'}:
            self.assertEqual(self.inputs[field],self.base[field])

    def test_every_source_row_including_all_noncohort_and_held_peers_is_compared(self):
        d=self.material['review']['fresh_variant_review']
        self.assertEqual((d['source_groups_compared'],d['cohort_groups_compared']),(4356,1100))
        self.assertEqual((d['external_key_comparisons'],d['within_source_key_comparisons']),(17424,17424))
        self.assertEqual((d['cohort_external_key_comparisons'],d['cohort_within_source_key_comparisons']),(4400,4400))
        states=[r['semantic_state'] for r in d['source_group_join_results'].values()]
        self.assertEqual(states.count('REVIEWED_COHORT'),1100)
        self.assertEqual(states.count('UNASSESSED_NONCOHORT_NOT_ADMITTED'),3256)

    def test_all_semantic_holds_and_full_literals_survive(self):
        self.assertEqual(len(self.material['initial_holds']),40)
        review=self.material['review']
        self.assertTrue(set(self.material['initial_holds'])<=set(review['held_groups']))
        self.assertFalse(set(review['selected_normalized_phrases'])&set(review['held_groups']))
        self.assertEqual(len(review['selected_normalized_phrases'])+len(review['held_groups']),1100)

    def test_exact_original_source_and_complete_public_cells_bind_every_new_record(self):
        for record in self.inputs['records'][len(self.base['records']):]:
            key=record['normalized_text'];row=self.material['groups'][key][0]
            occurrence=record['provenance_occurrences'][0]
            self.assertEqual(occurrence['source_ordinal'],row['source_ordinal'])
            self.assertEqual(occurrence['source_line'],row['source_line'])
            self.assertEqual(occurrence['original_literal'],record['original_text'])
            self.assertEqual(occurrence['complete_public_values_sha256'],stage.digest(row['values']))
            self.assertIn('/application-documents.json#source_ordinal=',record['source_reference'])
            self.assertIsNone(record['volume']);self.assertIsNone(record['cpc'])
            self.assertIsNone(record['observed_query'])

    def test_only_identical_remainder_observed_role_forms_hold(self):
        texts=['admin assistant resume','administrative assistant resume',
               'administrative assistant cover letter','administrative manager resume']
        groups={text:[{'source_ordinal':n,'values':{'Keyword':text}}] for n,text in enumerate(texts,1)}
        holds,review=e.role_form_holds(groups)
        self.assertEqual(set(holds),set(texts[:2]));self.assertEqual(len(review),1)
        self.assertEqual(review[0]['source_ordinals'],[1,2])
        self.assertFalse(review[0]['identity_or_google_equivalence_verified'])

    def test_all_held_groups_are_protected_or_already_protected_without_overwriting(self):
        before={e.ka.normalize(row['text']) for row in self.base['protected_queries']}
        additions=self.inputs['protected_queries'][len(self.base['protected_queries']):]
        held=set(self.material['review']['held_groups'])
        self.assertEqual({e.ka.normalize(row['text']) for row in additions},held-before)
        self.assertTrue(all(row['must_serve'] is True for row in additions))

    def test_truncated_base_fails_before_comparison(self):
        changed=deepcopy(self.base);changed['records'].pop()
        with patch.object(e,'membership') as compared:
            with self.assertRaisesRegex(ValueError,'PRIOR_BASE_CHANGED'):
                e.verify_base(changed,self.material)
            compared.assert_not_called()

    def test_held_or_outside_cohort_cannot_be_added_to_selection(self):
        changed=deepcopy(self.material['review'])
        changed['selected_normalized_phrases'].append(next(iter(changed['held_groups'])))
        changed['selected_normalized_phrases'].sort()
        changed['subject_sha256']=e.review_subject(changed,self.material)
        with self.assertRaisesRegex(ValueError,'BINDINGS_CHANGED'):
            e.validate_review(changed,self.material,self.when)

    def test_approval_authority_cannot_be_invented_even_with_recomputed_subject(self):
        changed=deepcopy(self.material['review']);changed[next(iter(e.LIMITS))]=True
        changed['subject_sha256']=e.review_subject(changed,self.material)
        with self.assertRaisesRegex(ValueError,'REVIEW_AUTHORITY'):
            e.validate_review(changed,self.material,self.when)

    def test_future_and_expired_review_are_rejected(self):
        for when in (self.when-timedelta(days=1),self.when+timedelta(days=31)):
            with self.assertRaisesRegex(ValueError,'REVIEW_DATES'):
                e.validate_review(self.material['review'],self.material,when)

    def test_campaign_scope_does_not_become_a_live_campaign_mapping(self):
        review=self.material['review']
        self.assertEqual((review['campaign_key'],review['landing_page_id']),('BSRE-C0301','BSRE-LP0301'))
        records=self.inputs['records'][len(self.base['records']):]
        self.assertTrue(all(r['approval_state']=='PENDING' and r['deployed_resource_ids']==[] for r in records))
        self.assertTrue(all(r['scope_basis']=='PLANNED_RENTAL_PURPOSE_ONLY_NOT_LIVE_CAMPAIGN_BINDING' for r in records))

    def test_modified_new_body_cannot_pass_saved_verification(self):
        changed=deepcopy(self.inputs);changed['records'][-1]['original_text']='rent apartment dubai'
        with patch.object(e,'_outputs') as outputs:
            with self.assertRaisesRegex(ValueError,'DERIVED_BODIES_CHANGED'):
                e.check_saved(changed,e.first.ROOT,self.when)
            outputs.assert_not_called()

    def test_pool_targets_are_not_reallocated_or_used_as_a_cutoff(self):
        documents,_=e._outputs(self.inputs,self.material,e.first.ROOT,self.when)
        allocation=documents['research-pool-allocation.json']
        previous=e.first.pinned(e.first.ROOT,e.prior.FOLDER+'/research-pool-allocation.json',e.prior.OUTPUT_PINS['research-pool-allocation.json'])
        self.assertEqual(allocation['targets'],previous['targets'])
        self.assertIsNone(allocation['target_transfer'])
        self.assertEqual(allocation['new_rows'],{'EMPLOYMENT':len(self.inputs['records'])-12156})
        self.assertTrue(all(n>=0 for n in allocation['remaining'].values()))

    def test_front_office_and_bank_snapshots_keep_their_original_fresh_stages(self):
        with patch.object(current,'_fresh_front_office_document_state',return_value=('new','new-report')) as fresh:
            self.assertEqual(current.reconstruct_front_office_document_snapshot(at=self.when),'new')
            self.assertEqual(current.verify_front_office_document_snapshot(at=self.when),'new-report')
            self.assertEqual(fresh.call_count,2)
        with patch.object(current,'_fresh_bank_channel_login_state',return_value=('old','old-report')) as fresh:
            self.assertEqual(current.reconstruct_bank_channel_login_snapshot(at=self.when),'old')
            self.assertEqual(current.verify_bank_channel_login_snapshot(at=self.when),'old-report')
            self.assertEqual(fresh.call_count,2)


if __name__=='__main__':
    unittest.main()
