"""Candidate selection preserves source identities and never grants release."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import compile_entry_cohort as c


class EntryCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs,cls.pins=c.load_inputs()
        cls.proposal=c.compile_proposal(cls.inputs,cls.pins)

    def reject(self,mutate,code=None):
        value=deepcopy(self.inputs);mutate(value)
        if code:
            with self.assertRaisesRegex(ValueError,code):c.compile_proposal(value,self.pins)
        else:
            with self.assertRaises(ValueError):c.compile_proposal(value,self.pins)

    def test_saved_proposal_replays_current_inputs(self):
        result=c.verify_saved()
        self.assertTrue(result['passed'])
        self.assertEqual(result['candidate_campaigns'],4)
        self.assertFalse(result['apply_supported'])

    def test_all_360_slots_and_15_families_remain_unchanged(self):
        original=deepcopy(self.inputs)
        result=c.compile_proposal(self.inputs,self.pins)
        self.assertEqual(self.inputs,original)
        self.assertEqual(result['source_page_count'],360)
        self.assertEqual(len(result['source_family_counts']),15)
        self.assertEqual(sum(result['source_family_counts'].values()),360)
        self.assertFalse(result['source_registry_modified'])
        self.assertFalse(result['source_routes_modified'])

    def test_four_known_ids_and_exact_average_budget_pools(self):
        rows=self.proposal['campaigns']
        self.assertEqual([r['historically_observed_google_campaign_id']for r in rows],list(c.EXPECTED_IDS.values()))
        self.assertEqual([r['average_daily_budget_aed_proposed']for r in rows],[1200,400,300,100])
        self.assertEqual(self.proposal['aggregate_average_daily_budget_aed_proposed'],2000)
        self.assertIs(self.proposal['vat_included'],False)
        self.assertIs(self.proposal['normal_overdelivery_accepted'],True)

    def test_each_campaign_has_one_distinct_candidate_with_secondary_services(self):
        rows=self.proposal['campaigns']
        self.assertEqual([r['candidate_planning_campaign_key']for r in rows],['BSRE-C0121','BSRE-C0336','BSRE-C0301','BSRE-C0281'])
        self.assertEqual(len({r['candidate_landing_page_id']for r in rows}),4)
        self.assertEqual(rows[0]['secondary_service_families_preserved'],['RDY'])
        self.assertEqual(rows[1]['secondary_service_families_preserved'],['LND'])
        self.assertEqual(rows[0]['existing_service_paths_preserved'],['/enquire/off-plan/','/enquire/resale/'])
        self.assertEqual(rows[1]['existing_service_paths_preserved'],['/enquire/sell/','/enquire/let/'])

    def test_new_entries_do_not_fabricate_existing_urls_or_cms_ids(self):
        for row in self.proposal['campaigns'][:2]:
            self.assertEqual(row['candidate_kind'],'NEW_NATIVE_ENTRY_REVIEW')
            self.assertIsNone(row['publicly_observed_candidate_url'])
            self.assertIsNone(row['publicly_observed_candidate_cms_id'])
            self.assertIsNone(row['public_identity_observed_at'])
            self.assertTrue(row['candidate_entry_path'].startswith('/lp/bsre-c'))

    def test_rental_and_hub_reuse_identities_are_dated_candidates(self):
        tenant,brand=self.proposal['campaigns'][2:]
        self.assertEqual((tenant['candidate_entry_path'],tenant['publicly_observed_candidate_cms_id']),('/enquire/rent/',26753))
        self.assertEqual((brand['candidate_entry_path'],brand['publicly_observed_candidate_cms_id']),('/enquire/',26750))
        for row in (tenant,brand):
            self.assertTrue(row['source_path_differs_from_reuse_candidate'])
            self.assertTrue(row['source_registry_proposed_path'].startswith('/lp/'))
            self.assertTrue(row['public_identity_observed_at'].startswith('2026-11-13'))
            self.assertFalse(row['actual_cms_ownership_binding_approved'])

    def test_tenant_direct_form_and_brand_child_choices_avoid_self_links(self):
        tenant,brand=self.proposal['campaigns'][2:]
        self.assertTrue(tenant['tenant_form_is_direct_entry'])
        self.assertEqual(len(brand['existing_service_paths_preserved']),5)
        self.assertNotIn('/enquire/',brand['existing_service_paths_preserved'])
        self.assertTrue(all(r['create_self_link_cta']is False for r in self.proposal['campaigns']))

    def test_no_actual_slot_binding_configuration_or_release_inferred(self):
        for row in self.proposal['campaigns']:
            for key in ('latest_campaign_configuration_verified','actual_planning_slot_binding_approved',
                        'actual_cms_ownership_binding_approved','campaign_url_change_approved'):
                self.assertIs(row[key],False)
            self.assertIn('SEPARATE_ACTION_SPECIFIC_RELEASE_AUTHORIZATION',row['remaining_blockers'])
        for key in ('apply_supported','old_campaign_reactivation_supported','website_publication_authorized',
                    'tracking_changes_authorized','ads_changes_authorized','ads_activation_authorized','spending_authorized'):
            self.assertIs(self.proposal[key],False)

    def test_brand_cmp_competition_is_an_explicit_remaining_review(self):
        row=self.proposal['campaigns'][3]
        self.assertEqual(row['primary_family_candidate'],'CMP')
        self.assertIn('CMP_BRAND_ROLE_AND_COMPETING_BRIEF_REVIEW',row['remaining_blockers'])

    def test_legacy_or_manufactured_google_campaign_ids_rejected_for_all_roles(self):
        for role in c.EXPECTED_IDS:
            name='BSRE_V2_SEARCH_'+role+'_UAE_EN'
            def mutate(d):
                for row in d['historical_ads']['ads_in_export_order']:
                    if row['Campaign']==name:row['Campaign ID']='123'
            self.reject(mutate,'HISTORICAL_CAMPAIGN_ID_NOT_ALLOWLISTED')

    def test_three_campaign_or_1900_exception_rejected(self):
        self.reject(lambda d:d['release_controls']['campaigns'].pop(),'EXACT_FOUR_CAMPAIGNS_REQUIRED')
        self.reject(lambda d:d['release_controls'].__setitem__('aggregate_average_daily_budget',1900),'RELEASE_CONTEXT_CHANGED')

    def test_primary_or_secondary_family_changes_rejected(self):
        self.reject(lambda d:d['family_decisions']['decisions'][0].__setitem__('primary_family_code','RDY'),'OWNER_PRIMARY_OR_SECONDARY_DECISION_CHANGED')
        self.reject(lambda d:d['family_decisions']['decisions'][1]['secondary_family_codes_preserved'].clear(),'OWNER_PRIMARY_OR_SECONDARY_DECISION_CHANGED')

    def test_premature_cms_or_slot_binding_in_primary_record_rejected(self):
        self.reject(lambda d:d['family_decisions']['decisions'][0].__setitem__('cms_page_id',100),'PRIMARY_FAMILY_RECORD_IS_NOT_A_DEPLOYMENT_BINDING')
        self.reject(lambda d:d['family_decisions']['decisions'][0].__setitem__('planning_slot_campaign_key','BSRE-C0121'),'PRIMARY_FAMILY_RECORD_IS_NOT_A_DEPLOYMENT_BINDING')

    def test_changed_or_duplicate_source_slot_rejected(self):
        self.reject(lambda d:d['registry'].pop())
        self.reject(lambda d:d['registry'][120].__setitem__('family_code','CMP'))
        self.reject(lambda d:d['native_manifest']['pages'][120].__setitem__('proposed_path','/unreviewed/'),'NATIVE_MANIFEST_DRIFT')

    def test_wrong_public_type_status_parent_id_and_authority_rejected(self):
        self.reject(lambda d:d['public_identities']['pages'][3].__setitem__('type','post'),'PUBLIC_NATIVE_PAGE_NOT_PUBLISHED')
        self.reject(lambda d:d['public_identities']['pages'][3].__setitem__('status','draft'),'PUBLIC_NATIVE_PAGE_NOT_PUBLISHED')
        self.reject(lambda d:d['public_identities']['pages'][3].__setitem__('parent',0),'PUBLIC_SERVICE_PARENT_CHANGED')
        self.reject(lambda d:d['public_identities']['pages'][3].__setitem__('id',26750),'PUBLIC_PAGE_IDENTITY_COLLISION')
        self.reject(lambda d:d['public_identities']['controls'].__setitem__('release_authorized',True),'PUBLIC_READBACK_IS_NOT_RELEASE_AUTHORITY')
        self.reject(lambda d:d['public_identities']['controls'].__setitem__('production_writes',False),'PUBLIC_READBACK_IS_NOT_RELEASE_AUTHORITY')

    def test_numeric_false_cannot_supply_authority_or_redirect_fields(self):
        self.reject(lambda d:d['release_controls'].__setitem__('release_authorized',0),'RELEASE_CONTEXT_CHANGED')
        self.reject(lambda d:d['public_identities'].__setitem__('redirect_followed',0),'PUBLIC_READBACK_IS_NOT_RELEASE_AUTHORITY')

    def test_source_pin_set_covers_every_declared_input_and_existing_fragments(self):
        expected=set(c.INPUTS.values())|{'tools/native-wordpress/entry-drafts/buyers.html','tools/native-wordpress/entry-drafts/owners.html'}
        self.assertEqual(set(self.proposal['input_sha256']),expected)
        for path,pin in self.proposal['input_sha256'].items():
            self.assertEqual(hashlib.sha256((c.ROOT/path).read_bytes()).hexdigest(),pin)

    def test_fresh_input_failure_blocks_every_verification_invocation(self):
        with patch.object(c,'load_inputs',side_effect=ValueError('FRESH_INPUT_UNAVAILABLE')):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'FRESH_INPUT_UNAVAILABLE'):c.verify_saved()

    def test_amit_and_private_folder_resolution_is_not_an_open_nomination(self):
        decision=self.inputs['family_decisions']
        self.assertTrue(any('Amit nominated' in item for item in decision['readiness_update']['resolved_since_family_decision']))
        self.assertTrue(any('Owner-only Marketing evidence folder' in item for item in decision['readiness_update']['resolved_since_family_decision']))
        self.assertFalse(any('Receive qualified factual-reviewer' in item for item in decision['remaining']))
        self.assertTrue(any('genuine dated' in item for item in decision['remaining']))


if __name__=='__main__':unittest.main()
