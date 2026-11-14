"""Candidate attention is not entity equivalence, novelty or admission."""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

import buyer_canonical_review as c


class BuyerCanonicalContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material, cls.previous = c.load_material()
        cls.graph = c.candidate_graph(cls.previous['review.json'], cls.material[3])
        cls.saved = {name: c.full.prior.ka.parse_json_bytes((c.ROOT / c.FOLDER / name).read_bytes())
                     for name in c.OUTPUT_PINS}
        cls.manual = c.full.prior.ka.parse_json_bytes((c.ROOT / c.FOLDER / 'manual-review.json').read_bytes())

    def group(self, n):
        return self.graph['components'][n - 1]

    def decision(self, n):
        return self.saved['review.json']['reviewed_components'][n - 1]

    def reject(self, mutate):
        changed = deepcopy(self.saved)
        mutate(changed)
        with self.assertRaisesRegex(ValueError, 'CANONICAL_REVIEW_DIFFERS'):
            c.validate_outputs(changed)

    def reject_manual(self, mutate, code):
        changed = deepcopy(self.manual)
        mutate(changed)
        blob = (json.dumps(changed, ensure_ascii=False) + '\n').encode('utf-8')
        with patch.object(c, 'build_candidates', return_value=self.graph), \
             patch.object(c.full.prior.buyer, 'read_bound', return_value=blob), \
             patch.object(c, 'MANUAL_SHA256', hashlib.sha256(blob).hexdigest()):
            with self.assertRaisesRegex(ValueError, code):
                c.build_outputs()

    def test_saved_public_review_replays_against_fresh_complete_inputs(self):
        result = c.verify_saved()
        self.assertIs(result['passed'], True)
        self.assertEqual(result['counts'], self.graph['counts'])
        self.assertEqual(result['counts']['conditional_buyer_occurrences_compared'], 1331)

    def test_every_original_and_held_peer_is_compared_before_selecting_buyers(self):
        self.assertEqual(self.graph['counts']['source_occurrences_compared'], 3195)
        self.assertEqual(self.graph['counts']['external_literal_forms_compared'], 47)
        self.assertEqual(self.graph['counts']['held_source_peers'], 2)
        originals = {r['source_ordinal']: r for r in self.previous['review.json']['records']}
        references = {r['reference']: r for r in self.material[3]['external_literal_references']}
        for group in self.graph['components']:
            for row in group['source_literals']:
                self.assertEqual(row, {key: originals[row['source_ordinal']][key] for key in row})
            self.assertEqual(group['external_literals'], [references[key] for key in group['external_references']])

    def test_components_and_unmatched_partition_buyers_without_double_counting(self):
        grouped = [n for g in self.graph['components'] for n in g['buyer_ordinals']]
        unmatched = self.graph['unmatched_buyer_ordinals']
        all_buyers = [r['source_ordinal'] for r in self.previous['review.json']['records'] if r['decision'] == c.full.DEFAULT]
        self.assertEqual(len(grouped), len(set(grouped)))
        self.assertEqual((len(self.graph['components']), len(grouped), len(unmatched)), (233, 553, 778))
        self.assertEqual(sorted(grouped + unmatched), all_buyers)

    def test_all_key_memberships_and_complete_transitive_context_are_retained(self):
        for group in self.graph['components']:
            members = {'s:' + str(n) for n in group['source_ordinals']} | {'e:' + key for key in group['external_references']}
            touched = set()
            for membership in group['key_memberships']:
                self.assertIn(membership['method'], c.METHODS)
                self.assertTrue(set(membership['members']) <= members)
                touched.update(membership['members'])
            self.assertEqual(touched, members)
        self.assertEqual(len(self.group(58)['source_ordinals']), 12)

    def test_review_decisions_cover_complete_bound_contexts_in_order(self):
        for manual, group in zip(self.manual['decisions'], self.graph['components']):
            for key in ('component_id', 'buyer_ordinals', 'source_ordinals', 'external_references'):
                self.assertEqual(manual[key], group[key])
            self.assertTrue(manual['review_note'].strip())
        self.assertEqual(len(self.manual['decisions']), 233)
        self.assertEqual(self.saved['review.json']['decision_counts'], {
            'EXACT_SOURCE_WORDING_REUSE_ONLY': 6, 'HOLD_ENTITY_OR_LOCATION_RELATION': 8,
            'HOLD_ROLE_OR_CONSTRAINT_MEANING': 2, 'HOLD_ROOM_OR_PROPERTY_DEFINITION': 21,
            'REVIEWED_SURFACE_INTENT_VARIANTS_PENDING_SUBJECT': 196})

    def test_bhk_bedroom_attention_requires_explicit_definition_holds(self):
        self.assertEqual(c.candidate_keys('2 bhk flat for sale in dubai')[-1],
                         c.candidate_keys('two bedroom apartment for sale dubai')[-1])
        self.assertNotEqual(c.candidate_keys('2 bhk flat for sale in dubai')[-2],
                            c.candidate_keys('two bedroom apartment for sale dubai')[-2])
        for n in (15, 22, 58, 221, 227):
            self.assertEqual(self.decision(n)['decision'], 'HOLD_ROOM_OR_PROPERTY_DEFINITION')

    def test_numbered_proper_names_are_not_converted_to_bedroom_counts(self):
        for phrase, preserved in [('five palm jumeirah apartments for sale', 'five'),
                                  ('district one dubai villas for sale', 'one'),
                                  ('one zaabeel apartment for sale', 'one'),
                                  ('one jbr apartment for sale', 'one')]:
            with self.subTest(phrase=phrase):
                self.assertIn(preserved, c.room_tokens(phrase))
        self.assertIn('five', c.candidate_keys('five palm jumeirah apartments for sale')[-1])

    def test_explicit_room_formats_are_attention_only_and_keep_cardinality(self):
        self.assertEqual(c.room_tokens('2bhk flat'), ['2', 'bhk', 'flat'])
        self.assertEqual(c.room_tokens('one bedroom apartment'), ['1', 'bedroom', 'apartment'])
        self.assertEqual(c.candidate_keys('2 br apartment for sale dubai')[-2],
                         c.candidate_keys('two bedroom apartment for sale dubai')[-2])
        self.assertNotEqual(c.candidate_keys('1 bhk apartment for sale dubai')[-1],
                            c.candidate_keys('2 bhk apartment for sale dubai')[-1])

    def test_role_constraint_location_number_and_asset_distinctions_survive(self):
        pairs = [('buy apartment dubai', 'rent apartment dubai'),
                 ('property for sale dubai', 'sell property dubai'),
                 ('villa with pool for sale', 'villa without pool for sale'),
                 ('damac hills 1 villa for sale', 'damac hills 2 villa for sale'),
                 ('villa for sale dubai', 'house for sale dubai'),
                 ('home for sale dubai', 'house for sale dubai'),
                 ('townhome for sale dubai', 'townhouse for sale dubai'),
                 ('condo for sale dubai', 'apartment for sale dubai'),
                 ('apartment for sale dubai', 'apartment for sale abu dhabi'),
                 ('buy to let dubai', 'let dubai')]
        for left, right in pairs:
            with self.subTest(left=left, right=right):
                self.assertTrue(all(a != b for a, b in zip(c.candidate_keys(left), c.candidate_keys(right))))

    def test_location_aliases_and_name_segmentation_are_not_verified(self):
        for n in (27, 33, 47, 106, 114, 121, 131, 199):
            self.assertEqual(self.decision(n)['decision'], 'HOLD_ENTITY_OR_LOCATION_RELATION')
            self.assertIs(self.decision(n)['subject_identity_verified'], False)
        self.assertNotEqual(c.candidate_keys('jvc apartments for sale')[-1],
                            c.candidate_keys('jumeirah village circle apartments for sale')[-1])

    def test_both_held_role_peers_remain_held_without_promotion(self):
        for n, ordinal in ((24, 1801), (136, 2171)):
            self.assertEqual(self.group(n)['held_source_peer_ordinals'], [ordinal])
            self.assertEqual(self.decision(n)['decision'], 'HOLD_ROLE_OR_CONSTRAINT_MEANING')
            self.assertNotIn(ordinal, self.group(n)['buyer_ordinals'])
        self.assertIs(self.graph['controls']['held_peers_promoted'], False)

    def test_exact_reuse_does_not_turn_mixed_variants_into_exact_matches(self):
        self.assertEqual(self.decision(3)['decision'], 'EXACT_SOURCE_WORDING_REUSE_ONLY')
        for n in (93, 108):
            self.assertEqual(self.decision(n)['decision'], 'REVIEWED_SURFACE_INTENT_VARIANTS_PENDING_SUBJECT')
        self.assertEqual(len(self.group(108)['external_references']), 2)

    def test_rental_income_purchase_remains_purchase_context_not_exclusion(self):
        self.assertEqual(self.group(167)['buyer_ordinals'], [856, 1948])
        self.assertEqual(self.decision(167)['decision'], 'REVIEWED_SURFACE_INTENT_VARIANTS_PENDING_SUBJECT')
        self.assertEqual(self.graph['controls']['negative_changes'], 0)

    def test_no_component_or_unmatched_row_grants_novelty_mapping_or_authority(self):
        controls = self.graph['controls']
        self.assertIsNone(controls['confirmed_novel_canonicals'])
        self.assertEqual(controls['positive_admissions_added'], 0)
        for key in ('semantic_equivalence_verified', 'google_matching_equivalence_verified',
                    'automatic_canonical_merge_allowed', 'actual_campaign_or_page_mapping_verified',
                    'deployment_authorized'):
            self.assertIs(controls[key], False)
        for row in self.saved['review.json']['reviewed_components']:
            for key in ('subject_identity_verified', 'canonical_merge_approved', 'independent_approval', 'positive_admission_granted'):
                self.assertIs(row[key], False)

    def test_dependency_mutation_is_detected_before_material_reuse(self):
        with patch.object(c, 'DEPENDENCIES', {next(iter(c.DEPENDENCIES)): '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'DEPENDENCY_PIN_CHANGED'):
                c.load_material()

    def test_complete_preliminary_pin_change_is_not_silently_accepted(self):
        with patch.dict(c.full.OUTPUT_PINS, {'review.json': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'COMPLETE_PRELIMINARY_OUTPUT_PIN_CHANGED'):
                c.load_material()

    def test_every_verifier_invocation_reads_inputs_fresh(self):
        with patch.object(c, 'load_material', side_effect=ValueError('FRESH_INPUT_UNAVAILABLE')):
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, 'FRESH_INPUT_UNAVAILABLE'):
                    c.build_outputs()

    def test_manual_held_peer_promotion_fails_even_with_a_new_manual_pin(self):
        self.reject_manual(lambda m: m['decisions'][23].__setitem__('decision', 'REVIEWED_SURFACE_INTENT_VARIANTS_PENDING_SUBJECT'),
                           'HELD_SOURCE_PEER_CONTEXT_MUST_REMAIN_HELD')

    def test_manual_false_exact_reuse_fails_even_with_a_new_manual_pin(self):
        self.reject_manual(lambda m: m['decisions'][0].__setitem__('decision', 'EXACT_SOURCE_WORDING_REUSE_ONLY'),
                           'EXACT_REUSE_REQUIRES_COMPLETE_LITERAL_MATCH')

    def test_manual_dropped_peer_and_added_authority_fields_fail(self):
        self.reject_manual(lambda m: m['decisions'][0]['source_ordinals'].pop(), 'MANUAL_COMPLETE_CONTEXT_BINDING_CHANGED')
        self.reject_manual(lambda m: m['decisions'][0].__setitem__('admitted', True), 'MANUAL_COMPLETE_CONTEXT_BINDING_CHANGED')

    def test_manual_independent_reviewer_or_incomplete_coverage_claims_fail(self):
        self.reject_manual(lambda m: m.__setitem__('reviewer', 'Independent human reviewer'), 'MANUAL_REVIEW_SCOPE_CHANGED')
        self.reject_manual(lambda m: m['decisions'].pop(), 'MANUAL_COMPONENT_COVERAGE_CHANGED')

    def test_missing_peer_or_external_reference_rejected(self):
        self.reject(lambda o: o['candidates.json']['components'][23]['held_source_peer_ordinals'].clear())
        self.reject(lambda o: o['candidates.json']['components'][107]['external_references'].pop())

    def test_automatic_merge_and_invented_novel_count_rejected(self):
        self.reject(lambda o: o['review.json']['controls'].__setitem__('automatic_canonical_merge_allowed', True))
        self.reject(lambda o: o['review.json']['controls'].__setitem__('confirmed_novel_canonicals', 1011))

    def test_unmatched_coverage_and_source_order_tampering_rejected(self):
        self.reject(lambda o: o['candidates.json']['unmatched_buyer_ordinals'].pop())
        self.reject(lambda o: o['review.json']['reviewed_components'].reverse())


if __name__ == '__main__':
    unittest.main()
