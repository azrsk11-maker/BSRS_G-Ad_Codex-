"""Full-history support cohort and failed-promotion behavior; no live exports."""
from copy import deepcopy
from datetime import date, timedelta
import unittest
from unittest.mock import patch

import append_only_admission as stage
import bank_credential_admission as prior
import bank_support_admission as e
import current_negative_library as current


class BankSupportAdmissionTests(unittest.TestCase):
    FRESH_BASE = None
    FRESH_INPUTS = None

    @classmethod
    def setUpClass(cls):
        cls.when = date(2026,11,12)
        cls.base = cls.FRESH_BASE if cls.FRESH_BASE is not None else current.reconstruct_bank_credential_snapshot(at=cls.when)
        cls.material = e.load_reviewed(e.first.ROOT,cls.when)
        cls.inputs = cls.FRESH_INPUTS if cls.FRESH_INPUTS is not None else e.extend(cls.base,e.first.ROOT,cls.when)

    def test_history_order_and_bodies_including_credential_stage_are_unchanged(self):
        self.assertEqual(stage.recover_base(self.inputs,stage_key=e.STAGE_KEY),self.base)
        self.assertEqual(stage.digest(self.base),e.BASE_SHA256)
        for field in ('records','protected_queries','sources'):
            self.assertEqual(self.inputs[field][:len(self.base[field])],self.base[field])
        for field in set(self.base)-{'records','protected_queries','sources'}:
            self.assertEqual(self.inputs[field],self.base[field])

    def test_all_source_groups_and_all_690_selected_literals_are_joined(self):
        d=self.material['review']['fresh_variant_review']
        self.assertEqual((d['source_groups_compared'],d['cohort_groups_compared']),(3481,690))
        self.assertEqual((d['external_key_comparisons'],d['within_source_key_comparisons']),(13924,13924))
        self.assertEqual((d['cohort_external_key_comparisons'],d['cohort_within_source_key_comparisons']),(2760,2760))
        self.assertEqual(len(d['source_group_join_results']),3481)
        states=[r['semantic_state'] for r in d['source_group_join_results'].values()]
        self.assertEqual(states.count('REVIEWED_CURRENT_SUPPORT_COHORT'),690)
        self.assertEqual(states.count('PREVIOUSLY_REVIEWED_CREDENTIAL_COHORT'),803)
        self.assertEqual(states.count('UNASSESSED_OUTSIDE_BOTH_SEMANTIC_COHORTS'),1988)

    def test_every_original_semantic_hold_remains_held(self):
        held=self.material['review']['held_groups']
        self.assertEqual(len(self.material['initial_holds']),203)
        self.assertTrue(set(self.material['initial_holds'])<=set(held))
        selected=set(self.material['review']['selected_normalized_phrases'])
        self.assertFalse(selected&set(self.material['previous_credential_keys']))
        self.assertFalse(selected&set(self.material['initial_holds']))

    def test_exact_occurrence_cells_and_lead_semantics_are_bound_without_metrics(self):
        for record in self.inputs['records'][len(self.base['records']):]:
            key=record['normalized_text'];row=self.material['groups'][key][0]
            occurrence=record['provenance_occurrences'][0]
            self.assertEqual(occurrence['source_ordinal'],row['source_ordinal'])
            self.assertEqual(occurrence['original_literal'],row['values']['Keyword'])
            self.assertEqual(occurrence['complete_public_values_sha256'],stage.digest(row['values']))
            self.assertEqual(occurrence['semantic_selected_ordinal'],self.material['decisions'][key]['selected_ordinal'])
            self.assertNotIn('independent_review_file',occurrence)
            self.assertNotIn('Avg. monthly searches',record)
        source=self.inputs['sources'][-1]
        self.assertFalse(source['independent_human_review_claimed'])
        self.assertFalse(source['metrics_copied_into_records'])

    def test_outside_cohort_provider_peer_can_hold_but_shared_parent_alone_cannot(self):
        texts=['axis bank support','axis support','axis bank support email','axis bank card support']
        groups={text:[{'source_ordinal':n,'values':{'Keyword':text}}] for n,text in enumerate(texts,1)}
        conflicts,diagnostics=e.provider_holds(groups)
        self.assertIn(texts[0],conflicts);self.assertIn(texts[1],conflicts)
        self.assertNotIn(texts[2],conflicts);self.assertNotIn(texts[3],conflicts)
        self.assertTrue(all(d['broad_parent_membership_causes_hold'] is False for d in diagnostics))

    def test_products_channels_actions_and_unlisted_entities_are_not_rewritten(self):
        texts=['nbd liv customer care','emirates nbd customer care','citi online support',
               'citibank chat support','a different bank support']
        groups={t:[{'source_ordinal':n,'values':{'Keyword':t}}] for n,t in enumerate(texts,1)}
        conflicts,_=e.provider_holds(groups)
        self.assertEqual(conflicts,{})
        self.assertEqual(list(groups),texts)

    def test_existing_negative_alias_in_a_new_hold_blocks_the_extension(self):
        m=deepcopy(self.material);key=next(iter(m['initial_holds']))
        base={k:[] for k in ('records','archived_records','protected_queries','sources')}
        base['records']=[{'original_text':key,'keyword_id':'EXISTING'}]
        with self.assertRaisesRegex(ValueError,'NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE'):
            e.membership(base,m)

    def test_resealed_unhold_cannot_replace_fresh_actual_comparisons(self):
        m=deepcopy(self.material);review=m['review'];d=review['fresh_variant_review']
        key=next(iter(d['additional_variant_holds']))
        review['selected_normalized_phrases']=sorted(review['selected_normalized_phrases']+[key])
        del review['held_groups'][key]
        d['selected_normalized_phrases']=list(review['selected_normalized_phrases'])
        d['all_held_normalized_phrases']=sorted(review['held_groups'])
        review['subject_sha256']=e.review_subject(review,m)
        e.validate_review(review,m,self.when)
        with patch.object(e,'load_reviewed',return_value=m):
            with self.assertRaisesRegex(ValueError,'BANK_SUPPORT_FRESH_VARIANT_REVIEW_CHANGED'):
                e.extend(self.base,e.first.ROOT,self.when)

    def test_resealed_authority_scope_and_dates_fail(self):
        for field,value in [('deployment_authorized',True),('campaign_key','OTHER'),
                            ('reviewer_kind','HUMAN'),('valid_until',(self.when+timedelta(days=31)).isoformat())]:
            review=deepcopy(self.material['review']);review[field]=value
            review['subject_sha256']=e.review_subject(review,self.material)
            with self.subTest(field=field),self.assertRaises(ValueError):
                e.validate_review(review,self.material,self.when)

    def test_complete_base_tamper_and_unregistered_review_fail(self):
        base=deepcopy(self.base);base['archived_records'][0]['original_text']+=' changed'
        with self.assertRaisesRegex(ValueError,'BANK_SUPPORT_PRIOR_BASE_CHANGED'):
            e.verify_base(base,self.material)
        with patch.object(e,'REVIEW_PIN',None):
            with self.assertRaisesRegex(ValueError,'BANK_SUPPORT_REVIEW_UNREGISTERED'):
                e.load_reviewed(e.first.ROOT,self.when)

    def test_saved_outputs_do_not_grant_approval_or_transfer_targets(self):
        summary=e.check_saved(self.inputs,e.first.ROOT,self.when)
        self.assertEqual(summary['input_rows'],len(self.inputs['records']))
        self.assertEqual(summary['approved_exclusion_rows'],0)
        self.assertFalse(summary['deployment_export_allowed'])
        p=e.first.pinned(e.first.ROOT,e.FOLDER+'/research-pool-allocation.json',e.OUTPUT_PINS['research-pool-allocation.json'])
        before=e.first.pinned(e.first.ROOT,prior.FOLDER+'/research-pool-allocation.json',prior.OUTPUT_PINS['research-pool-allocation.json'])
        self.assertEqual(p['targets'],before['targets'])
        self.assertIsNone(p['target_transfer'])

    def test_derived_body_change_cannot_be_resealed(self):
        changed=deepcopy(self.inputs);changed['records'][-1]['evidence_ref']='fabricated'
        with self.assertRaisesRegex(ValueError,'BANK_SUPPORT_DERIVED_BODIES_CHANGED'):
            e.check_saved(changed,e.first.ROOT,self.when)

    def test_latest_and_credential_snapshot_use_separate_fresh_chains(self):
        with patch.object(current,'_fresh_bank_support_state',return_value=('support','support-report')) as fresh:
            self.assertEqual(current.reconstruct(at=self.when),'support')
            self.assertEqual(current.verify(at=self.when),'support-report')
            self.assertEqual(fresh.call_count,2)
        with patch.object(current,'_fresh_bank_credential_state',return_value=('old','old-report')) as old:
            self.assertEqual(current.reconstruct_bank_credential_snapshot(at=self.when),'old')
            self.assertEqual(current.verify_bank_credential_snapshot(at=self.when),'old-report')
            self.assertEqual(old.call_count,2)


if __name__=='__main__':
    unittest.main()
