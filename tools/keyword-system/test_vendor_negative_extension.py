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


class VendorExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.when = date(2026,11,11)
        with patch.object(current,'reconstruct_registered',wraps=current.reconstruct_registered) as calls:
            cls.inputs = current.reconstruct_vendor_snapshot(at=cls.when)
            cls.base_constructions = calls.call_count
        cls.entry = registered.AFTER_REVIEW_CATALOG[0]
        cls.review = cls.inputs['post_review_cohorts'][0]

    def test_current_counts_and_original_rows_survive_a_single_fresh_base(self):
        data = self.inputs
        self.assertEqual(self.base_constructions,1)
        self.assertEqual((len(data['records']),len(data['archived_records']),len(data['protected_queries'])),
                         (10014,12,15309))
        original_raw = (first.ROOT/'tools/keyword-system/data/negative.json').read_bytes()
        self.assertEqual(hashlib.sha256(original_raw).hexdigest(),history.OUTPUT_PINS['data/negative.json'])
        lookup = {r['keyword_id']:r for r in data['records']+data['archived_records']}
        for row in json.loads(original_raw):
            self.assertEqual(first.canonical(row),first.canonical(lookup[row['keyword_id']]))
        index = first.pinned(first.ROOT,current.POST_INDEX,current.POST_INDEX_PIN)
        self.assertEqual(index['reviewed_base']['eligible_rows'],8025)
        self.assertEqual(index['reviewed_base']['records_sha256'],
            hashlib.sha256(first.canonical(data['records'][:8025])).hexdigest())
        self.assertEqual(index['additional_records_sha256'],
            hashlib.sha256(first.canonical(data['records'][8025:])).hexdigest())
        self.assertEqual(index['archived_records_sha256'],
            hashlib.sha256(first.canonical(data['archived_records'])).hexdigest())

    def test_complete_current_report_has_no_exclusion_or_release_authority(self):
        result = current.check_post_outputs(self.inputs,first.ROOT,self.when)
        self.assertEqual((result['reviewed_eligible_rows'],result['deficit'],result['new_rows'],
            result['archived_original_rows'],result['new_proposal_holds']), (10014,3986,1989,12,96))
        self.assertTrue(result['passed'] and result['index_verified'] and result['release_held'])
        for name in ('human_review_verified','live_campaign_mapping_verified','release_authorized',
                     'positive_library_coverage_verified','deployment_export_allowed','production_writes_available'):
            self.assertIs(result[name],False)
        self.assertEqual(result['approved_exclusion_rows'],0)

    def test_new_records_have_actual_provenance_and_only_the_reviewed_planning_scope(self):
        rows = self.inputs['records'][8025:]
        self.assertEqual(len(rows),1989)
        self.assertEqual(self.review['intent_counts'],{
            'EXPLICIT_OPERATIONAL_SOFTWARE_PRODUCT_RESEARCH':1569,'EXPLICIT_EMPLOYMENT_RESEARCH':339,
            'EXPLICIT_CRM_ERP_PRODUCT_RESEARCH':52,'EXPLICIT_OCCUPATIONAL_APPLICATION_ARTIFACT_RESEARCH':3,
            'EXPLICIT_TECHNICAL_SOURCE_RESEARCH':25,'EXPLICIT_OCCUPATIONAL_ENTRY_RESEARCH':1})
        for row in rows:
            self.assertTrue(row['provenance_occurrences'])
            self.assertEqual(row['eligible_campaigns'],[first.CAMPAIGN])
            self.assertEqual((row['match_type'],row['risk_level'],row['approval_state']),('EXACT','HIGH','PENDING'))
            self.assertIsNone(row['volume']); self.assertIsNone(row['cpc'])
            self.assertIsNone(row['observed_query']); self.assertIsNone(row['observation_date'])
            self.assertEqual(row['deployed_resource_ids'],[])

    def test_all_twelve_archived_and_ninety_six_new_holds_fail_reinsertion(self):
        relative = 'docs/audit/keyword-vendor-operations-commercial-2026-11-11/workbench.json'
        wb = first.pinned(first.ROOT,relative,'10cd054e471948b21db06203cec7293145396a2f9019796b0a8228eac0c39701')
        protected = {r['text'] for r in self.inputs['protected_queries']}
        self.assertTrue(set(self.review['held_phrases']) <= protected)
        self.assertFalse(set(self.review['held_phrases']) & {r['normalized_text'] for r in self.inputs['records']})
        attempts = list(self.inputs['archived_records'])
        for row in wb['queue']:
            if row['normalized_text'] not in self.review['held_phrases']: continue
            ref = row['source_refs'][0]; source = wb['sources'][ref['batch']]
            occurrence = {'batch':ref['batch'],'source_line':ref['source_line'],'file':source['file'],
                'sha256':source['sha256'],'review_file':relative,
                'review_sha256':'10cd054e471948b21db06203cec7293145396a2f9019796b0a8228eac0c39701'}
            attempts.append(first.make_record(row,self.review,[occurrence],source_id=ref['batch'],
                source_reference=source['file']+'#'+str(ref['source_line']),review_folder=self.entry['folder'],
                allowed_intents=set(self.review['semantic_rationale'])))
        result = audit('negative',attempts,self.inputs['sources'],self.inputs['campaigns'],
                       self.inputs['campaign_context'],self.inputs['protected_queries'],self.when)
        self.assertEqual((len(attempts),result['reviewed_eligible_rows'],len(result['protected_conflicts'])),(108,0,108))

    def test_resealed_index_or_changed_provenance_body_cannot_pass(self):
        original = first.pinned
        def changed(root,relative,pin):
            value = original(root,relative,pin)
            if relative == current.POST_INDEX:
                value = copy.deepcopy(value)
                value['additional_eligible_keyword_ids'][0] = value['archived_original_keyword_ids'][0]
            return value
        with patch.object(first,'pinned',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'POST_REVIEW_INDEX_CHANGED'):
                current.check_post_outputs(self.inputs,first.ROOT,self.when)
        altered = copy.deepcopy(self.inputs)
        altered['records'][8025]['provenance_occurrences'][0]['source_line'] += 1
        with self.assertRaisesRegex(ValueError,'POST_REVIEW_INDEX_CHANGED'):
            current.check_post_outputs(altered,first.ROOT,self.when)

    def test_prefix_reordering_and_unknown_or_authorizing_reviews_fail_closed(self):
        altered = copy.deepcopy(self.inputs)
        altered['records'][0],altered['records'][1] = altered['records'][1],altered['records'][0]
        with self.assertRaisesRegex(ValueError,'POST_REVIEW_BASE_REPLACED'): current.post_index(altered)
        with self.assertRaisesRegex(ValueError,'UNREGISTERED_COHORT'):
            registered.reconstruct(first.ROOT,dict(self.entry,key='unknown'),self.inputs)
        original = first.pinned
        def changed(root,relative,pin):
            value = original(root,relative,pin)
            if relative == self.entry['folder']+'/review.json':
                value = copy.deepcopy(value); value['production_authorized'] = True
            return value
        with patch.object(first,'pinned',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'REGISTERED_REVIEW_CANNOT_GRANT_AUTHORITY'):
                registered.reconstruct(first.ROOT,self.entry,self.inputs)

    def test_research_pool_rebalance_preserves_total_and_media_budget(self):
        previous = first.pinned(first.ROOT,current.FOLDER+'/research-pool-allocation.json',current.ALLOCATION_PIN)
        overlay = first.pinned(first.ROOT,current.LATEST_INDEX,current.LATEST_INDEX_PIN)
        allocation = current.post_allocation(self.inputs,previous,overlay)
        self.assertEqual((allocation['total_target'],allocation['total_admitted'],allocation['total_remaining']),
                         (14000,10014,3986))
        self.assertEqual(allocation['target_transfer'],{'from':'EMPLOYMENT','to':'SOFTWARE','rows':1362})
        self.assertEqual((allocation['targets']['EMPLOYMENT'],allocation['targets']['SOFTWARE']),(5061,2362))
        self.assertEqual(allocation['new_rows'],{'SOFTWARE':1646,'EMPLOYMENT':343})
        self.assertEqual(allocation['held_deduction'],{'SOFTWARE':9,'EMPLOYMENT':1})
        for name in ('owner_approval_claimed','media_budget_changed','exclusion_approval_granted'):
            self.assertIs(allocation[name],False)

    def test_each_public_entrypoint_requires_a_fresh_baseline(self):
        with patch.object(history,'reconstruct_current',side_effect=ValueError('fresh source unavailable')) as fresh:
            for call in (current.reconstruct_vendor_snapshot,current.verify_vendor_snapshot,
                         current.reconstruct_followup_snapshot,current.verify_followup_snapshot,
                         current.reconstruct_valuation_snapshot,current.verify_valuation_snapshot,
                         current.reconstruct_ofqual_snapshot,current.verify_ofqual_snapshot,
                         current.reconstruct,current.verify):
                with self.assertRaisesRegex(ValueError,'fresh source unavailable'): call(at=self.when)
            self.assertEqual(fresh.call_count,10)


if __name__ == '__main__': unittest.main()
