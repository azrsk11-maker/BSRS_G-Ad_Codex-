"""Meaningful append-only, provenance, fresh-input and unresolved-hold guards."""
from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch

import append_only_admission as stage
import current_negative_library as current
import ofqual_veterinary_admission as e


class OfqualVeterinaryAdmissionTests(unittest.TestCase):
    # An in-process generator may inject its already freshly reconstructed full
    # base. No serialized base or acceptance result is read by these tests.
    FRESH_BASE = None
    FRESH_INPUTS = None

    @classmethod
    def setUpClass(cls):
        cls.when = date(2026,11,12)
        cls.base = cls.FRESH_BASE if cls.FRESH_BASE is not None else current.reconstruct_ofqual_occupational_snapshot(
            e.first.ROOT,at=cls.when)
        cls.material = e.load_reviewed(e.first.ROOT,cls.when)
        cls.inputs = cls.FRESH_INPUTS if cls.FRESH_INPUTS is not None else e.extend(cls.base,e.first.ROOT,cls.when)

    def test_complete_history_order_archives_and_every_extra_body_are_preserved(self):
        self.assertEqual(tuple(len(self.base[key]) for key in
            ('records','archived_records','protected_queries','sources')), (11170,18,16693,25))
        self.assertEqual(stage.digest(self.base),e.BASE_SHA256)
        self.assertEqual(stage.recover_base(self.inputs,stage_key=e.STAGE_KEY),self.base)
        for field,count in (('records',11170),('protected_queries',16693),('sources',25)):
            self.assertEqual(self.inputs[field][:count],self.base[field])
        for key in set(self.base)-{'records','protected_queries','sources'}:
            self.assertEqual(self.inputs[key],self.base[key])

    def test_every_actual_provider_occurrence_retains_original_title_number_and_lines(self):
        rows = self.inputs['records'][11170:]
        self.assertEqual(len(rows),len(self.material['review']['selected_normalized_titles']))
        for row in rows:
            source_rows = self.material['groups'][row['normalized_text']]
            self.assertEqual(len(row['provenance_occurrences']),len(source_rows))
            for saved,source in zip(row['provenance_occurrences'],source_rows):
                self.assertEqual({key:saved[key] for key in e.occurrence(source)},e.occurrence(source))
                self.assertEqual(saved['original_text'],source['values']['Qualification Title'])
                self.assertEqual(saved['official_csv_sha256'],e.RAW_SHA256)
                self.assertEqual(saved['sha256'],e.SOURCE_PINS[e.CAPTURE+'/qualifications.json'])
            self.assertEqual(row['original_text'],source_rows[0]['values']['Qualification Title'])
            self.assertEqual((row['match_type'],row['risk_level'],row['approval_state']),('EXACT','HIGH','PENDING'))
            self.assertTrue(all(row[key] is None for key in ('volume','cpc','observed_query','observation_date')))
            self.assertEqual(row['eligible_campaigns'],['BSRE-C0301'])
            self.assertEqual(row['deployed_resource_ids'],[])

    def test_all_length_symbol_and_semantic_holds_remain_protected_without_shortening(self):
        selected = set(self.material['review']['selected_normalized_titles'])
        held = set(self.material['review']['held_groups'])
        self.assertEqual(selected|held,set(self.material['groups']))
        self.assertFalse(selected&held)
        for key,rows in self.material['groups'].items():
            profile = e.compatibility.profile_text(rows[0]['values']['Qualification Title'])['original']
            if profile['reason_codes'] or key not in self.material['proposed']:
                self.assertIn(key,held)
        all_protected = {row['text'] for row in self.inputs['protected_queries']}
        self.assertTrue(held <= all_protected)
        self.assertTrue(all(row['must_serve'] is True for row in self.inputs['protected_queries'][16693:]))
        self.assertNotIn(self.material['projection']['records'][2]['normalized_title'],selected)

    def test_new_exact_token_bag_and_closed_alias_conflicts_become_holds_not_forced_rows(self):
        key = self.material['review']['selected_normalized_titles'][0]
        text = self.material['groups'][key][0]['values']['Qualification Title']
        values = [text,' '.join(reversed(e.ka.tokens(text))),e._closed(text)]
        for value in values:
            base = dict(self.base)
            base['protected_queries'] = self.base['protected_queries']+[{'query_id':'SYNTHETIC-CONFLICT','text':value}]
            diagnostic = e.membership(base,self.material)
            self.assertNotIn(key,diagnostic['selected_normalized_titles'])
            self.assertIn(key,diagnostic['additional_variant_holds'])
            self.assertEqual(len(base['records']),11170)

    def test_within_source_peer_and_old_negative_new_hold_conflicts_fail_conservatively(self):
        key = self.material['review']['selected_normalized_titles'][0]
        text = self.material['groups'][key][0]['values']['Qualification Title']
        base = dict(self.base)
        base['records'] = self.base['records']+[{'keyword_id':'SYNTHETIC-CURRENT','original_text':text}]
        with self.assertRaisesRegex(ValueError,'VETERINARY_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE'):
            e.membership(base,self.material)
        material = dict(self.material); material['groups'] = dict(material['groups'])
        other = deepcopy(material['groups'][key])
        alternate = ' '.join(reversed(e.ka.tokens(text)))
        other[0]['values']['Qualification Title'] = alternate
        material['groups'][alternate] = other
        self.assertIn(key,e.membership(self.base,material)['additional_variant_holds'])

    def test_plausible_alias_families_hold_clear_titles_and_keep_text_held_peers(self):
        diagnostic = self.material['review']['fresh_variant_review']
        selected = set(diagnostic['selected_normalized_titles'])
        groups = self.material['groups']
        ordinal_keys = {row['source_record_ordinal']:key for key,rows in groups.items() for row in rows}
        for family in e.ALIAS_FAMILIES:
            keys = {ordinal_keys[ordinal] for ordinal in family['ordinals']}
            self.assertFalse(keys & selected)
            for key in keys:
                self.assertTrue(any(reason.get('family_key') == family['key'] for reason in
                    diagnostic['all_source_group_conflicts'][key]))
                self.assertIn(key,diagnostic['all_held_normalized_titles'])
        # The clear CQ SA and EQ routes remain held alongside the full old/new
        # source peers. No SA/EQ expansion or literal replacement is admitted.
        for ordinal in (44508,44510):
            self.assertIn(ordinal_keys[ordinal],self.material['proposed'])
            self.assertNotIn(ordinal_keys[ordinal],selected)
        self.assertNotIn(ordinal_keys[44490],self.material['proposed'])
        self.assertIn(ordinal_keys[44490],diagnostic['preheld_source_group_conflicts'])
        for ordinal in (44502,44504,44691,48092,48120,49199):
            self.assertIn(ordinal_keys[ordinal],selected)
        families = deepcopy(e.ALIAS_FAMILIES)
        families[0]['ordinals'][0] = 999999
        with patch.object(e,'ALIAS_FAMILIES',families):
            with self.assertRaisesRegex(ValueError,'VETERINARY_ALIAS_SOURCE_BINDING_CHANGED'):
                e.membership(self.base,self.material)

    def test_resealed_alias_unhold_is_rejected_against_the_fresh_complete_base(self):
        material = deepcopy(self.material)
        review = material['review']; diagnostic = review['fresh_variant_review']
        key = next(key for key in self.material['proposed'] if key in diagnostic['additional_variant_holds'])
        review['selected_normalized_titles'] = sorted(review['selected_normalized_titles']+[key])
        del review['held_groups'][key]
        diagnostic['selected_normalized_titles'] = list(review['selected_normalized_titles'])
        diagnostic['all_held_normalized_titles'].remove(key)
        del diagnostic['additional_variant_holds'][key]
        review['subject_sha256'] = e.review_subject(review,material)
        with patch.object(e,'load_reviewed',return_value=material):
            with self.assertRaisesRegex(ValueError,'VETERINARY_FRESH_VARIANT_REVIEW_CHANGED'):
                e.extend(self.base,e.first.ROOT,self.when)

    def test_preheld_titles_receive_all_four_external_and_internal_joins(self):
        key = sorted(set(self.material['groups'])-set(self.material['proposed']))[0]
        text = self.material['groups'][key][0]['values']['Qualification Title']
        reverse = ' '.join(reversed(e.ka.tokens(text)))
        self.assertNotEqual(tuple(e.ka.tokens(text)),tuple(e.ka.tokens(reverse)))
        cases = [('protected_queries','text','query_id',reverse,'equal_token_bag'),
            ('archived_records','original_text','keyword_id',e._closed(text),'closed_alphanumeric')]
        for field,textfield,idfield,alias,expected_kind in cases:
            base = dict(self.base)
            base[field] = self.base[field]+[{idfield:'SYNTHETIC-PREHELD-EXTERNAL-PEER',textfield:alias}]
            diagnostic = e.membership(base,self.material)
            self.assertIn(key,diagnostic['all_held_normalized_titles'])
            self.assertNotIn(key,diagnostic['selected_normalized_titles'])
            self.assertNotIn(key,diagnostic['additional_variant_holds'])
            reasons = diagnostic['preheld_source_group_conflicts'][key]
            self.assertTrue(any(reason['kind'] == expected_kind for reason in reasons))
            self.assertEqual(diagnostic['source_groups_compared'],51)
            self.assertEqual(diagnostic['external_key_comparisons'],204)
            self.assertEqual(diagnostic['within_source_key_comparisons'],204)
        # A pre-held token-bag alias of an old negative must hold the whole new
        # admission, even when ordered tokens differ; no old row is removed.
        base = dict(self.base)
        base['records'] = self.base['records']+[{'keyword_id':'SYNTHETIC-PREHELD-CURRENT-PEER','original_text':reverse}]
        with self.assertRaisesRegex(ValueError,'VETERINARY_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE'):
            e.membership(base,self.material)

    def test_resealed_scope_authority_dates_selection_and_baseline_changes_fail(self):
        changes = [lambda review:review.update(human_review_verified=0),
            lambda review:review.update(exclusion_approval_granted=True),
            lambda review:review.update(campaign_key='BSRE-C0001'),
            lambda review:review['selected_normalized_titles'].append(next(iter(review['held_groups']))),
            lambda review:review['held_groups'].pop(next(iter(review['held_groups']))),
            lambda review:review['implementation'].clear(),
            lambda review:review.update(base_sha256='0'*64),
            lambda review:review.update(valid_until='2026-12-13')]
        for change in changes:
            review = deepcopy(self.material['review']); change(review)
            review['subject_sha256'] = e.review_subject(review,self.material)
            with self.assertRaises(ValueError):e.validate_review(review,self.material,self.when)
        with self.assertRaisesRegex(ValueError,'VETERINARY_REVIEW_DATES'):
            e.validate_review(self.material['review'],self.material,date(2027,1,1))
        for field in ('records','archived_records','protected_queries','sources'):
            base = dict(self.base); base[field] = self.base[field][:-1]
            with self.assertRaisesRegex(ValueError,'VETERINARY_PRIOR_BASE_CHANGED'):e.verify_base(base,self.material)
        base = dict(self.base); base['invented_extra_marker'] = True
        with self.assertRaisesRegex(ValueError,'VETERINARY_PRIOR_BASE_CHANGED'):e.verify_base(base,self.material)

    def test_source_peer_hold_provenance_metrics_and_missing_registration_cannot_be_resealed(self):
        original = e.first.pinned
        changes = [(e.CAPTURE+'/qualifications.json',lambda doc:doc['controls'].update(volume=0)),
            (e.CAPTURE+'/semantic-decisions.json',lambda doc:doc['decisions'][0].update(source_line_start=1)),
            (e.CAPTURE+'/semantic-decisions.json',lambda doc:doc['controls'].update(admission_authorized=True)),
            (e.CAPTURE+'/semantic-decisions.json',lambda doc:doc['decisions'].pop())]
        for relative,change in changes:
            def altered(root,file,pin):
                value = original(root,file,pin)
                if file == relative:
                    value = deepcopy(value); change(value)
                return value
            with patch.object(e.first,'pinned',side_effect=altered):
                with self.assertRaises(ValueError):e.load_sources(e.first.ROOT)
        with patch.object(e,'REVIEW_PIN',None):
            with self.assertRaisesRegex(ValueError,'VETERINARY_REVIEW_UNREGISTERED'):
                e.load_reviewed(e.first.ROOT,self.when)

    def test_mutated_derived_tail_is_rejected_before_saved_audit(self):
        changes = [lambda row:row.update(volume=0),lambda row:row.update(approval_state='APPROVED'),
            lambda row:row['provenance_occurrences'][0].update(qualification_number='SYNTHETIC-CHANGED'),
            lambda row:row['provenance_occurrences'][0].update(source_record_ordinal=568),
            lambda row:row.update(eligible_campaigns=['BSRE-C0001'])]
        for change in changes:
            inputs = dict(self.inputs)
            inputs['records'] = self.inputs['records'][:11170]+deepcopy(self.inputs['records'][11170:])
            change(inputs['records'][11170])
            with patch.object(e,'_outputs') as outputs:
                with self.assertRaisesRegex(ValueError,'VETERINARY_DERIVED_BODIES_CHANGED'):
                    e.check_saved(inputs,e.first.ROOT,self.when)
                outputs.assert_not_called()

    def test_real_generic_auditor_rejects_malformed_new_protection(self):
        inputs = dict(self.inputs)
        inputs['protected_queries'] = self.inputs['protected_queries'][:16693]+deepcopy(self.inputs['protected_queries'][16693:])
        inputs['protected_queries'][16693]['must_serve'] = False
        with self.assertRaisesRegex(ValueError,'APPEND_ONLY_RESEARCH_NOT_ELIGIBLE'):
            stage.checked_audit(inputs,self.when)

    def test_saved_outputs_bind_all_counts_without_approvals_or_target_transfers(self):
        report = e.check_saved(self.inputs,e.first.ROOT,self.when)
        self.assertEqual(report['input_rows'],11170+len(self.material['review']['selected_normalized_titles']))
        self.assertEqual(report['input_rows'],report['reviewed_eligible_rows'])
        self.assertEqual((report['computed_conflicts'],report['excluded_rows'],report['approved_exclusion_rows']),(0,0,0))
        self.assertFalse(report['deployment_export_allowed'])
        self.assertFalse(report['positive_library_coverage_verified'])
        allocation = e.first.pinned(e.first.ROOT,e.FOLDER+'/research-pool-allocation.json',e.OUTPUT_PINS['research-pool-allocation.json'])
        self.assertIsNone(allocation['target_transfer'])
        self.assertEqual(allocation['targets']['ACADEMIC'],2000)
        self.assertEqual(allocation['remaining']['ACADEMIC'],117-report['new_rows'])

    def test_new_and_frozen_entrypoints_keep_their_own_fresh_chain(self):
        with patch.object(current,'_fresh_ofqual_occupational_state',side_effect=ValueError('fresh occupational unavailable')) as fresh:
            for call in (current.reconstruct_ofqual_occupational_snapshot,current.verify_ofqual_occupational_snapshot,
                current.reconstruct,current.verify):
                with self.assertRaisesRegex(ValueError,'fresh occupational unavailable'):call(at=self.when)
            self.assertEqual(fresh.call_count,4)
        with patch.object(e,'extend',side_effect=ValueError('fresh veterinary unavailable')) as extension, \
             patch.object(current,'_fresh_ofqual_occupational_state',return_value=(self.base,{})):
            for call in (current.reconstruct,current.verify):
                with self.assertRaisesRegex(ValueError,'fresh veterinary unavailable'):call(at=self.when)
            self.assertEqual(extension.call_count,2)


if __name__ == '__main__':
    unittest.main()
