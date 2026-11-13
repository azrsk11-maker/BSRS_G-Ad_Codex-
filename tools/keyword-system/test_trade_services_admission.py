"""Fresh-history admission, source-peer holds and scoped rollback regressions."""
from copy import deepcopy
from datetime import date, timedelta
import unittest
from unittest.mock import patch

import append_only_admission as stage
import current_negative_library as current
import trade_services_admission as e


class TradeServicesAdmissionTests(unittest.TestCase):
    FRESH_BASE = None
    FRESH_INPUTS = None

    @classmethod
    def setUpClass(cls):
        cls.when=date(2026,11,13)
        cls.base=cls.FRESH_BASE if cls.FRESH_BASE is not None else current.reconstruct_septic_grease_snapshot(at=cls.when)
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
        self.assertEqual((d['source_groups_compared'],d['cohort_groups_compared']),(6053,1019))
        self.assertEqual((d['external_key_comparisons'],d['within_source_key_comparisons']),(24212,24212))
        self.assertEqual((d['cohort_external_key_comparisons'],d['cohort_within_source_key_comparisons']),(4076,4076))
        states=[r['semantic_state'] for r in d['source_group_join_results'].values()]
        self.assertEqual(states.count('REVIEWED_COHORT'),1019)
        self.assertEqual(states.count('UNASSESSED_NONCOHORT_NOT_ADMITTED'),5034)

    def test_all_semantic_holds_and_full_literals_survive(self):
        self.assertEqual(len(self.material['initial_holds']),538)
        review=self.material['review']
        self.assertTrue(set(self.material['initial_holds'])<=set(review['held_groups']))
        self.assertFalse(set(review['selected_normalized_phrases'])&set(review['held_groups']))
        self.assertEqual(len(review['selected_normalized_phrases'])+len(review['held_groups']),1019)

    def test_exact_original_source_and_complete_public_cells_bind_every_new_record(self):
        for record in self.inputs['records'][len(self.base['records']):]:
            key=record['normalized_text'];row=self.material['groups'][key][0]
            occurrence=record['provenance_occurrences'][0]
            self.assertEqual(occurrence['source_ordinal'],row['source_ordinal'])
            self.assertEqual(occurrence['source_line'],row['source_line'])
            self.assertEqual(occurrence['original_literal'],record['original_text'])
            self.assertEqual(occurrence['complete_public_values_sha256'],stage.digest(row['values']))
            self.assertIn('/service-installation.json#source_ordinal=',record['source_reference'])
            self.assertIsNone(record['volume']);self.assertIsNone(record['cpc'])
            self.assertIsNone(record['observed_query'])

    def test_held_or_noncohort_source_peer_blocks_otherwise_proposed_literal(self):
        # Original observed closed-form pair; this is an isolated diagnostic fixture.
        rows=[{'source_line':4,'values':{'Keyword':'septic pumping'}},
              {'source_line':5,'values':{'Keyword':'septicpumping'}}]
        decisions=[{'source_ordinal':1,'source_line':4,'original_literal':'septic pumping',
                    'decision':'PROPOSE_FULL_EXACT_RESEARCH'}]
        base={'records':[],'archived_records':[],'protected_queries':[]}
        result=e.comparator.compare(base,rows,decisions)
        self.assertEqual(result['unmatched_compatible_proposal_ordinals'],[])
        first=result['source_row_comparisons'][0]
        closed=next(j for j in first['joins'] if j['method']=='closed_alphanumeric')
        self.assertEqual(closed['outside_cohort_peer_ordinals'],[2])
        self.assertEqual(result['noncohort_records_compared'],1)
        self.assertFalse(result['google_equivalence_verified'])

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

    def test_evidence_bound_rebalance_preserves_target_and_every_qualified_original(self):
        documents,_=e._outputs(self.inputs,self.material,e.first.ROOT,self.when)
        allocation=documents['research-pool-allocation.json']
        previous=self.previous_allocation()
        count=len(self.inputs['records'])-len(self.base['records'])
        planned=e.rebalance_research(previous,count)
        self.assertEqual(allocation['targets'],planned['targets'])
        self.assertEqual(allocation['admitted'],planned['admitted'])
        self.assertEqual(allocation['remaining'],planned['remaining'])
        self.assertEqual(allocation['new_rows'],{'SERVICE':count})
        self.assertEqual(allocation['total_target'],14000)
        self.assertEqual(count,len(self.material['review']['selected_normalized_phrases']))
        transfer=allocation['target_transfer']
        self.assertEqual(transfer['evidence_sha256'],e.REVIEW_PIN)
        self.assertEqual(transfer['source_pins'],e.SOURCE_PINS)
        self.assertEqual(transfer['complete_current_base_sha256'],e.BASE_SHA256)
        self.assertTrue(transfer['implementation_decision_not_owner_approval'])
        self.assertFalse(allocation['owner_approval_claimed'])
        self.assertFalse(allocation['media_budget_changed'])
        self.assertTrue(all(n>=0 for n in allocation['remaining'].values()))

    def previous_allocation(self):
        return e.first.pinned(e.first.ROOT,e.prior.FOLDER+'/research-pool-allocation.json',
            e.prior.OUTPUT_PINS['research-pool-allocation.json'])

    def test_rebalance_uses_capacity_without_transfer_until_exhausted(self):
        previous=self.previous_allocation();before=deepcopy(previous)
        for number in (0,1,116):
            actual=e.rebalance_research(previous,number)
            self.assertEqual(actual['targets'],previous['targets'])
            self.assertIsNone(actual['target_transfer'])
            self.assertEqual(sum(actual['remaining'].values()),557-number)
        self.assertEqual(previous,before)

    def test_largest_remainder_has_independently_calculated_integer_result(self):
        # Isolated arithmetic probe, not an actual research-admission claim.
        actual=e.rebalance_research(self.previous_allocation(),200)
        self.assertEqual(actual['target_transfer']['from'],
            {'ACADEMIC':2,'EMPLOYMENT':22,'MEDIA':37,'NAVIGATION':23})
        self.assertEqual(actual['target_transfer']['to'],{'SERVICE':84})
        self.assertEqual(actual['remaining']['SERVICE'],0)
        self.assertEqual(sum(actual['remaining'].values()),357)
        self.assertEqual(sum(actual['targets'].values()),14000)

    def test_rebalance_is_order_independent_and_preserves_fully_admitted_pools(self):
        original=self.previous_allocation();reordered=deepcopy(original)
        for field in ('targets','admitted','remaining'):
            reordered[field]=dict(reversed(list(reordered[field].items())))
        self.assertEqual(e.rebalance_research(original,200),e.rebalance_research(reordered,200))
        result=e.rebalance_research(original,557)
        self.assertTrue(all(n==0 for n in result['remaining'].values()))
        for field in ('SOFTWARE','UNRELATED_PRODUCT'):
            self.assertEqual(result['targets'][field],original['targets'][field])

    def test_rebalance_rejects_boolean_overflow_and_inconsistent_previous_evidence(self):
        previous=self.previous_allocation()
        for count in (True,False,-1,558,1.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                e.rebalance_research(previous,count)
        for mutate in (lambda x:x['remaining'].update(ACADEMIC=11),
                       lambda x:x['targets'].update(ACADEMIC=True),
                       lambda x:x.update(total_admitted=1)):
            changed=deepcopy(previous);mutate(changed)
            with self.assertRaises(ValueError):e.rebalance_research(changed,200)

    def test_default_entrypoints_use_new_stage_and_septic_snapshot_stays_frozen(self):
        with patch.object(current,'_fresh_trade_services_state',return_value=('new','new-report')) as fresh:
            self.assertEqual(current.reconstruct_trade_services_snapshot(at=self.when),'new')
            self.assertEqual(current.verify_trade_services_snapshot(at=self.when),'new-report')
            self.assertEqual(fresh.call_count,2)
        with patch.object(current,'_fresh_septic_grease_state',return_value=('old','old-report')) as fresh:
            self.assertEqual(current.reconstruct_septic_grease_snapshot(at=self.when),'old')
            self.assertEqual(current.verify_septic_grease_snapshot(at=self.when),'old-report')
            self.assertEqual(fresh.call_count,2)


if __name__=='__main__':
    unittest.main()
