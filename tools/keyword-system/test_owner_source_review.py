"""Owner-role ambiguity, source custody, complete comparisons and held authority."""
from copy import deepcopy
import hashlib
import importlib.util
import unittest
from unittest.mock import patch

import owner_source_review as owner


class OwnerSourceReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = owner.load_material()
        cls.report = owner.assemble(*cls.material)
        spec = importlib.util.spec_from_file_location('owner_tests_capture',
            owner.ROOT / owner.FOLDER / 'verify_capture.py')
        cls.verifier = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.verifier)
        cls.previous_pins = {p:hashlib.sha256((owner.ROOT/p).read_bytes()).hexdigest() for p in (
            owner.commercial.FOLDER+'/commercial-property.json',
            owner.buyer.FOLDER+'/buyer-property.json',owner.buyer.historical.HISTORY,owner.buyer.PRIOR)}

    @classmethod
    def tearDownClass(cls):
        for path, pin in cls.previous_pins.items():
            if hashlib.sha256((owner.ROOT/path).read_bytes()).hexdigest() != pin:
                raise AssertionError('Earlier source bytes changed')

    def row(self,n):
        return self.report['records'][n-1]

    def reject_report(self,mutate):
        report = deepcopy(self.report)
        mutate(report)
        with self.assertRaisesRegex(ValueError,'OWNER_REVIEW_DIFFERS_FROM_FRESH_INPUTS'):
            owner.validate_report(report)

    def test_capture_preserves_all_cells_and_rejects_twelve_tamper_probes(self):
        receipt = self.verifier.verify()
        self.assertTrue(receipt['passed'])
        self.assertEqual((receipt['export_rows'],receipt['public_columns'],receipt['excluded_account_specific_columns']),
                         (147,21,5))
        self.assertEqual(self.verifier.self_check()['in_memory_mutations_rejected'],12)

    def test_ten_actual_seeds_keep_their_nonconsecutive_source_positions(self):
        positions = [142,1,2,3,143,144,145,146,4,147]
        self.assertEqual([self.row(n)['original_literal'] for n in positions],self.material[0]['input_seeds'])
        self.assertEqual([r['source_ordinal'] for r in self.report['records'] if r['exact_input_seed_wording']],
                         [1,2,3,4,142,143,144,145,146,147])
        self.assertFalse(self.row(5)['exact_input_seed_wording'])

    def test_all_147_complete_literals_lines_and_3087_cells_are_bound(self):
        self.assertEqual([r['source_ordinal'] for r in self.report['records']],list(range(1,148)))
        self.assertEqual([r['source_line'] for r in self.report['records']],list(range(4,151)))
        source = self.material[0]['source_projection']['records']
        self.assertEqual(sum(len(r['values']) for r in source),3087)
        for original, reviewed in zip(source,self.report['records']):
            self.assertEqual(reviewed['original_literal'],original['values']['Keyword'])
            self.assertEqual(reviewed['complete_public_values_sha256'],owner.buyer.digest(original['values']))

    def test_explicit_manual_partition_reads_every_literal_once(self):
        manual = self.material[1]
        ordinals = [n for c in manual['categories'].values() for n in c['ordinals']]
        self.assertEqual(sorted(ordinals),list(range(1,148)))
        self.assertEqual(len(set(ordinals)),147)
        self.assertIs(manual['all_complete_literals_read'],True)
        self.assertEqual(manual['cohorts'],[[1,147]])

    def test_seller_and_landlord_hypotheses_do_not_inherit_buyer_rows(self):
        sellers = [r['source_ordinal'] for r in self.report['records'] if r['decision_code']=='SELLER_HYPOTHESIS']
        landlords = [r['source_ordinal'] for r in self.report['records'] if r['decision_code']=='LANDLORD_HYPOTHESIS']
        self.assertEqual(sellers,[1,2,142,143])
        self.assertEqual(landlords,[144,145,146,147])
        self.assertEqual(self.report['counts']['buyer_research_other_role'],53)
        self.assertEqual(self.report['counts']['other_review_holds'],86)

    def test_for_sell_and_to_sell_wording_remains_role_ambiguous(self):
        self.assertEqual(self.row(80)['original_literal'],'villa for sell in dubai')
        self.assertEqual(self.row(103)['original_literal'],'apartment to sell dubai')
        for n in (80,103):
            self.assertEqual(self.row(n)['decision_code'],'SELLER_BUYER_AMBIGUITY_HOLD')

    def test_budget_locality_readiness_and_tenure_are_not_discarded(self):
        for n in (13,16,32,38,42,51,62,102,105):
            self.assertEqual(self.row(n)['decision_code'],'BUYER_RESEARCH_OTHER_ROLE')
        for n in (82,86):
            self.assertEqual(self.row(n)['decision_code'],'TENURE_OR_DISTRESS_HOLD')
        self.assertIsNone(self.row(13)['asset_family'])
        self.assertIsNone(self.row(13)['actual_volume'])

    def test_valuation_is_not_a_confirmed_professional_service_or_price(self):
        vals = [r for r in self.report['records'] if r['decision_code']=='VALUATION_EVIDENCE_HOLD']
        self.assertEqual(len(vals),20)
        for n in (3,85,104,112,123,136):
            self.assertEqual(self.row(n)['decision_code'],'VALUATION_EVIDENCE_HOLD')
            self.assertIsNone(self.row(n)['native_page'])
            self.assertFalse(self.row(n)['admitted'])

    def test_management_short_stay_and_software_require_their_own_producers(self):
        counts = self.report['counts']['decision_codes']
        self.assertEqual((counts['MANAGEMENT_PRODUCER_HOLD'],counts['SHORT_STAY_PRODUCER_HOLD'],
                          counts['SOFTWARE_OR_TOOL_HOLD']),(17,11,5))
        self.assertEqual(self.row(84)['decision_code'],'MANAGEMENT_PRODUCER_HOLD')
        self.assertEqual(self.row(120)['decision_code'],'MANAGEMENT_PRODUCER_HOLD')
        self.assertEqual(self.row(31)['decision_code'],'SOFTWARE_OR_TOOL_HOLD')

    def test_provider_dispute_and_maintenance_holds_create_no_negatives(self):
        self.assertEqual(self.report['counts']['decision_codes']['PROVIDER_OR_PORTAL_CONTEXT_HOLD'],21)
        self.assertEqual(self.row(60)['decision_code'],'PROVIDER_OR_PORTAL_CONTEXT_HOLD')
        self.assertEqual(self.row(97)['decision_code'],'DISPUTE_SERVICE_HOLD')
        for n in (94,96):
            self.assertEqual(self.row(n)['decision_code'],'MAINTENANCE_PRODUCER_HOLD')
        self.assertEqual(self.report['counts']['negative_proposals_added'],0)

    def test_every_named_prior_form_and_within_source_peer_participates(self):
        external = owner.external_forms(self.material[3])
        self.assertEqual(len(external),3947)
        self.assertEqual(len([r for r in external if r['reference'].startswith('buyer-property:')]),3195)
        self.assertEqual(len([r for r in external if r['reference'].startswith('commercial-property:')]),705)
        matched = set()
        keys = [owner.buyer.attention_keys(r['original_literal']) for r in self.report['records']]
        external_keys = [(r['reference'],owner.buyer.attention_keys(r['original_literal'])) for r in external]
        for n,row in enumerate(self.report['records']):
            for index,join in enumerate(row['joins']):
                expected = sorted(reference for reference,k in external_keys if k[index] == keys[n][index])
                self.assertEqual(join['external_references'],expected)
                self.assertEqual(join['source_peer_ordinals'],[i+1 for i,k in enumerate(keys)
                    if i != n and k[index] == keys[n][index]])
                matched.update(expected)
        self.assertEqual({r['reference'] for r in self.report['comparison_matched_contexts']},matched)

    def test_every_authority_and_actual_mapping_remains_held(self):
        self.assertEqual(self.report['controls'],owner.CONTROLS)
        self.assertIsNone(self.report['counts']['confirmed_novel_canonicals'])
        for row in self.report['records']:
            for key in ('asset_family','primary_campaign','ad_group','native_page','actual_volume','actual_cpc'):
                self.assertIsNone(row[key])
            for key in ('admitted','independent_approval','canonical_merge_approved','genuine_query_observed'):
                self.assertIs(row[key],False)

    def test_saved_review_replays_complete_fresh_inputs(self):
        self.assertIs(owner.verify_saved()['passed'],True)

    def test_fabricated_novelty_authority_or_source_role_is_rejected(self):
        for mutate in (
            lambda r:r['counts'].__setitem__('confirmed_novel_canonicals',147),
            lambda r:r['controls'].__setitem__('admission_authorized',0),
            lambda r:r['records'][4].__setitem__('decision_code','SELLER_HYPOTHESIS'),
        ):
            with self.subTest(mutation=mutate):
                self.reject_report(mutate)

    def test_missing_duplicate_and_boolean_manual_ordinals_are_rejected(self):
        for replacement in ([],[1,1],[True]):
            manual=deepcopy(self.material[1])
            manual['categories']['SELLER_HYPOTHESIS']['ordinals']=replacement
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(ValueError,'OWNER_MANUAL_PARTITION'):
                    owner.assemble(self.material[0],manual,self.material[2],self.material[3])

    def test_changed_current_source_pin_is_not_hidden_by_prior_verification(self):
        read=owner.buyer.read_bound
        target=owner.ROOT/owner.FOLDER/'owner-services.json'
        def changed(path):
            blob=read(path)
            return blob+b' ' if path==target else blob
        with patch.object(owner.buyer,'read_bound',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'PUBLIC_PIN_CHANGED|OWNER_INPUT_PIN_CHANGED'):
                owner.verify_saved()


if __name__ == '__main__':
    unittest.main()
