"""Authentic commercial wording, all-source comparisons and admission holds."""
from copy import deepcopy
import hashlib
import importlib.util
import unittest
from unittest.mock import patch

import commercial_source_review as c


class CommercialSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = c.load_material()
        cls.report = c.assemble(*cls.material)
        path = c.ROOT / c.FOLDER / 'verify_capture.py'
        spec = importlib.util.spec_from_file_location('commercial_tests_capture',path)
        cls.verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.verifier)
        cls.prior_pins = {p:hashlib.sha256((c.ROOT/p).read_bytes()).hexdigest() for p in
                          (c.buyer.FOLDER+'/buyer-property.json',c.buyer.PRIOR,c.buyer.historical.HISTORY)}

    @classmethod
    def tearDownClass(cls):
        for path,pin in cls.prior_pins.items():
            if hashlib.sha256((c.ROOT/path).read_bytes()).hexdigest()!=pin:
                raise AssertionError('Prior source bytes changed')

    def row(self,n): return self.report['records'][n-1]

    def reject(self,mutate):
        report=deepcopy(self.report);mutate(report)
        with self.assertRaisesRegex(ValueError,'COMMERCIAL_REVIEW_DIFFERS'):
            c.validate_report(report)

    def test_saved_review_replays_fresh_with_no_admission_authority(self):
        result=c.verify_saved()
        self.assertIs(result['passed'],True)
        self.assertIs(result['deployment_authorized'],False)

    def test_public_capture_rejects_all_twelve_tamper_probes(self):
        result=self.verifier.self_check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['in_memory_mutations_rejected'],12)

    def test_all_705_ordinals_originals_lines_and_14805_cells_bound(self):
        source=self.material[0]['source_projection']['records']
        self.assertEqual([r['source_ordinal']for r in self.report['records']],list(range(1,706)))
        self.assertEqual([r['source_line']for r in self.report['records']],list(range(4,709)))
        self.assertEqual(sum(len(r['values'])for r in source),14805)
        for original,review in zip(source,self.report['records']):
            self.assertEqual(review['original_literal'],original['values']['Keyword'])
            self.assertEqual(review['complete_public_values_sha256'],c.buyer.digest(original['values']))

    def test_tenth_seed_is_retained_at_705_without_reordering_the_source(self):
        seeds=self.material[0]['input_seeds']
        self.assertEqual([r['source_ordinal']for r in self.report['records']if r['exact_input_seed_wording']],list(range(1,10))+[705])
        self.assertEqual(self.row(705)['original_literal'],seeds[-1])
        self.assertFalse(self.row(10)['exact_input_seed_wording'])
        self.assertEqual(self.material[0]['seed_reconciliation'],{'exact_returned':10,'without_separate_exact_row':[]})

    def test_three_manual_cohorts_cover_all_complete_source_literals(self):
        manual=self.material[1]
        self.assertEqual(manual['cohorts'],[[1,240],[241,480],[481,705]])
        self.assertIs(manual['all_complete_literals_read'],True)
        self.assertEqual(self.report['counts']['complete_literals_read'],705)

    def test_lease_purchase_and_other_holds_remain_distinct(self):
        counts=self.report['counts']
        self.assertEqual((counts['conditional_lease_hypotheses'],counts['conditional_purchase_hypotheses'],counts['other_review_holds']),(272,48,385))
        self.assertEqual(sum(counts['decision_codes'].values()),705)

    def test_preleased_property_sale_remains_purchase_not_tenant_exclusion(self):
        self.assertEqual(self.row(393)['decision_code'],'P')
        self.assertEqual(self.report['counts']['negative_proposals_added'],0)

    def test_location_words_do_not_replace_the_commercial_lease_meaning(self):
        for n in (112,113,183,205,222,250,280,295,594,658):
            self.assertEqual(self.row(n)['decision_code'],'L')
            self.assertIsNone(self.row(n)['asset_family'])

    def test_clearance_and_event_sales_do_not_become_warehouse_property(self):
        for n in (28,160,394,411,584,696):
            self.assertEqual(self.row(n)['decision_code'],'U')
        for n in (3,396,403,483,699):
            self.assertEqual(self.row(n)['decision_code'],'P')
        for n in (83,385,430,702,703):
            self.assertEqual(self.row(n)['decision_code'],'A')

    def test_direct_owner_constraint_is_not_silently_removed(self):
        self.assertEqual(self.row(187)['decision_code'],'D')
        self.assertIsNone(self.row(187)['primary_campaign'])

    def test_furnished_office_is_not_automatically_a_serviced_provider(self):
        for n in (21,29,33,34,53,108,122):
            self.assertEqual(self.row(n)['decision_code'],'L')
        for n in (13,20,32,49,50,98,144,174,195,227):
            self.assertEqual(self.row(n)['decision_code'],'V')

    def test_operating_outlet_and_goodwill_context_stays_held(self):
        for n in (87,90,197,272,319,342,358,559,623,681):
            self.assertEqual(self.row(n)['decision_code'],'B')
            self.assertIs(self.row(n)['admitted'],False)

    def test_studio_flat_office_use_does_not_invent_permission(self):
        self.assertEqual(self.row(671)['decision_code'],'M')
        self.assertIsNone(self.row(671)['asset_family'])
        self.assertIs(self.report['controls']['business_evidence_verified'],False)

    def test_named_entities_and_old_years_do_not_supply_inventory_facts(self):
        for n in (456,563,566,569,580,589,695):
            self.assertEqual(self.row(n)['decision_code'],'A')
        for n in (105,700,701):
            self.assertEqual(self.row(n)['decision_code'],'T')

    def test_all_3242_named_external_forms_and_historical_placements_retained(self):
        counts=self.report['counts']
        self.assertEqual((counts['comparison_external_forms'],counts['comparison_prior_full_buyer_rows'],counts['historical_candidates'],counts['historical_placements'],counts['prior_buyer_rows']),(3242,3195,41,82,6))
        self.assertEqual(len(self.report['external_literal_references']),3242)
        self.assertEqual((counts['exact_external_context_rows'],counts['lexical_attention_rows']),(28,122))
        known={r['reference']for r in self.report['external_literal_references']}
        for row in self.report['records']:
            for join in row['joins']:
                self.assertTrue(set(join['external_references'])<=known)
                self.assertNotIn(row['source_ordinal'],join['source_peer_ordinals'])
                self.assertTrue(all(1<=n<=705 for n in join['source_peer_ordinals']))

    def test_no_actual_metrics_mapping_genuine_query_or_canonical_merge_inferred(self):
        for row in self.report['records']:
            self.assertEqual(row['source_kind'],'RESEARCH_HYPOTHESIS')
            for key in ('actual_volume','actual_cpc','asset_family','primary_campaign','ad_group','native_page'):
                self.assertIsNone(row[key])
            for key in ('genuine_query_observed','admitted','independent_approval','canonical_merge_approved'):
                self.assertIs(row[key],False)

    def test_exclusion_and_subject_bound_review_acceptance_still_required(self):
        for key in ('semantic_canonicalization_complete','five_subject_bound_reviews_complete','current_exclusion_scope_verified',
                    'actual_campaign_or_page_mapping_verified','independent_review_complete','admission_authorized','deployment_authorized'):
            self.assertIs(self.report['controls'][key],False)
        self.assertIsNone(self.report['counts']['confirmed_novel_canonicals'])

    def test_fabricated_novelty_or_changed_source_line_rejected(self):
        self.reject(lambda r:r['counts'].__setitem__('confirmed_novel_canonicals',705))
        self.reject(lambda r:r['records'][704].__setitem__('source_line',4))

    def test_numeric_false_cannot_replace_authority_boolean(self):
        self.reject(lambda r:r['controls'].__setitem__('deployment_authorized',0))

    def test_dropped_peer_or_reclassified_hold_rejected(self):
        self.reject(lambda r:r['external_literal_references'].pop())
        self.reject(lambda r:r['records'][670].__setitem__('decision_code','L'))

    def test_changed_source_dependency_or_manual_pin_fails_before_reuse(self):
        with patch.dict(c.DEPENDENCIES,{'tools/keyword-system/buyer_source_reconciliation.py':'0'*64}):
            with self.assertRaisesRegex(ValueError,'INPUT_PIN_CHANGED'): c.load_material()
        with patch.object(c,'MANUAL_PIN','0'*64):
            with self.assertRaisesRegex(ValueError,'INPUT_PIN_CHANGED'): c.load_material()

    def test_every_new_invocation_requires_fresh_input_availability(self):
        with patch.object(c,'load_material',side_effect=ValueError('FRESH_INPUT_UNAVAILABLE')):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError,'FRESH_INPUT_UNAVAILABLE'): c.build_report()


if __name__=='__main__': unittest.main()
