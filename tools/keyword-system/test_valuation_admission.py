"""Pinned review guards and explicitly synthetic extension partition tests.

The required full current-library check performs fresh historical composition
and the generic actual-input audit. These focused cases do not repeat it.
"""
from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch

import valuation_admission as v


class ValuationAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = v.load_reviewed(v.first.ROOT,date(2026,11,11))

    def reseal(self,review):
        campaign = next(r for r in self.material['registry'] if r['campaign_key']==v.first.CAMPAIGN)
        review['subject_sha256'] = v.final_review_subject(review,self.material['context'],campaign)
        return review

    def validate(self,review):
        return v.validate_final_review(review,self.material,date(2026,11,11))

    def fixture(self):
        """Small synthetic body population; never passes verify_base."""
        m = self.material
        old = [{'keyword_id':'SYNTHETIC-OLD-'+str(n),'original_text':m['rows'][n]['original_text'],
            'reason_code':'EXPLICIT_EMPLOYMENT_RESEARCH','provenance_occurrences':[{'synthetic':n}],
            'synthetic_metadata':{'unchanged':['original body']}}
            for n in m['review']['existing_occurrence_only_source_lines']]
        protected = [{'query_id':'SYNTHETIC-Q-'+str(n),'text':r['normalized_text'],
            'campaign_keys':[v.first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
            'evidence_ref':'SYNTHETIC_PROTECTION','reviewed_on':'2026-11-11','valid_until':'2026-12-11'}
            for n,r in m['rows'].items() if r['membership_screen']=='protected']
        return {'records':old,'archived_records':[{'keyword_id':'SYNTHETIC-ARCHIVE',
            'original_text':'synthetic previously archived phrase'}], 'protected_queries':protected,
            'sources':[{'source_id':'SYNTHETIC-OLD-SOURCE','synthetic_metadata':['source body']}],
            'campaigns':m['registry'],'campaign_context':[{'campaign_key':v.first.CAMPAIGN,
                'synthetic_metadata':['context body']}],
            'followup_historical_metadata':{'unchanged':['original metadata']}}

    def extended_fixture(self):
        with patch.object(v,'load_reviewed',return_value=self.material), patch.object(v,'verify_base'):
            return v.extend(self.fixture(),v.first.ROOT,date(2026,11,11))

    def test_pinned_review_partition_and_all_authority_holds(self):
        review = self.material['review']; self.validate(review)
        self.assertEqual((len(review['selected_source_lines']),len(review['held_source_lines']),
            len(review['existing_occurrence_only_source_lines'])),(411,408,46))
        self.assertTrue(all(review[k] is False for k in v.LIMITS))
        self.assertEqual(len(self.material['rows']),865)

    def test_existing_reconciliation_preserves_original_hold_evidence(self):
        m = self.material; review = m['review']
        oldheld = {n for n,r in m['rows'].items() if r['disposition']=='HOLD' and
            r['membership_screen']=='existing_eligible'}
        self.assertEqual(len(oldheld),16)
        self.assertLessEqual(oldheld,set(review['existing_occurrence_only_source_lines']))
        self.assertFalse(oldheld&set(review['selected_source_lines']))
        self.assertTrue(all(r['new_source_occurrence_accepted'] is False for r in m['reconciliation']['rows']))

    def test_prior_and_final_semantic_holds_cannot_be_promoted_even_if_resealed(self):
        original = self.material['review']
        for line in (385,517,520,next(n for n,r in self.material['rows'].items() if
                r['membership_screen']=='protected')):
            review = deepcopy(original)
            del review['held_source_lines'][str(line)]
            review['selected_source_lines'] = sorted(review['selected_source_lines']+[line])
            with self.assertRaises(ValueError): self.validate(self.reseal(review))

    def test_authority_scope_types_partition_and_variant_metadata_fail_closed(self):
        changes = [lambda r:r.update(production_authorized=True),
            lambda r:r.update(human_review_verified=0),lambda r:r.update(campaign_key='BSRE-C0001'),
            lambda r:r['selected_source_lines'].append(r['selected_source_lines'][0]),
            lambda r:r['selected_source_lines'].__setitem__(0,True),
            lambda r:r['existing_occurrence_only_source_lines'].pop(),
            lambda r:r['source_pins_sha256'].clear(),
            lambda r:r['variant_review'].update(google_equivalence_verified=True)]
        for change in changes:
            with self.subTest(change=change):
                review = deepcopy(self.material['review']); change(review)
                with self.assertRaises(ValueError): self.validate(self.reseal(review))

    def test_review_subject_and_expiry_are_checked(self):
        review = deepcopy(self.material['review']); review['semantic_rationale'] += ' altered'
        with self.assertRaisesRegex(ValueError,'VALUATION_REVIEW_SUBJECT_CHANGED'): self.validate(review)
        with self.assertRaisesRegex(ValueError,'VALUATION_REVIEW_DATES'):
            v.validate_final_review(self.material['review'],self.material,date(2027,1,1))

    def test_arbitrary_caller_population_cannot_skip_fresh_exact_base(self):
        with self.assertRaisesRegex(ValueError,'VALUATION_PRIOR_BASE_CHANGED'):
            v.verify_base(self.fixture(),self.material)

    def test_overlay_is_pure_and_preserves_all_old_bodies_and_archive(self):
        base = self.fixture(); before = deepcopy(base)
        result = v.apply_overlay(base,self.material['review'],self.material['rows'])
        self.assertEqual(base,before)
        self.assertEqual(result['records'],before['records'])
        self.assertEqual(result['archived_records'],before['archived_records'])
        self.assertEqual(result['protected_queries'][:8],before['protected_queries'])
        self.assertEqual(len(result['valuation_added_protections']),400)
        result['records'][0]['synthetic_metadata']['unchanged'].append('changed copy')
        self.assertEqual(base,before)

    def test_existing_hold_requires_reconciliation_instead_of_silent_archive(self):
        review = deepcopy(self.material['review']); line = review['existing_occurrence_only_source_lines'][0]
        review['held_source_lines'][str(line)] = 'SYNTHETIC_UNRESOLVED_EXISTING_CONFLICT'
        with self.assertRaisesRegex(ValueError,'VALUATION_HELD_EXISTING_NEEDS_RECONCILIATION'):
            v.apply_overlay(self.fixture(),review,self.material['rows'])

    def test_real_new_occurrences_scope_and_record_authority_are_preserved(self):
        base = self.fixture(); base = v.apply_overlay(base,self.material['review'],self.material['rows'])
        part = v.build_cohort(base,self.material)
        self.assertEqual(len(part['records']),411); self.assertEqual(len(part['sources']),1)
        for record in part['records']:
            self.assertEqual(len(record['provenance_occurrences']),1)
            occurrence = record['provenance_occurrences'][0]
            self.assertIn(occurrence['source_line'],self.material['review']['selected_source_lines'])
            self.assertEqual(occurrence['review_sha256'],v.REVIEW_PIN)
            self.assertEqual(occurrence['source_sha256'],self.material['batch']['source_projection']['source_sha256'])
            self.assertEqual(record['original_text'],self.material['rows'][occurrence['source_line']]['original_text'])
            self.assertEqual(record['scope_target'],{'campaign_key':v.first.CAMPAIGN})
            self.assertEqual((record['match_type'],record['risk_level'],record['approval_state']),('EXACT','HIGH','PENDING'))
            self.assertIsNone(record['volume']); self.assertIsNone(record['cpc'])
            self.assertEqual(record['deployed_resource_ids'],[])

    def test_selected_known_or_protected_literal_cannot_be_added(self):
        first = self.material['rows'][self.material['review']['selected_source_lines'][0]]
        for field in ('records','archived_records','protected_queries'):
            base = self.fixture()
            base[field].append({'query_id':'SYNTHETIC-COLLISION','text':first['normalized_text']}
                if field=='protected_queries' else
                {'keyword_id':'SYNTHETIC-COLLISION','original_text':first['original_text']})
            with self.assertRaisesRegex(ValueError,'VALUATION_SELECTED_NOT_NOVEL'):
                v.build_cohort(base,self.material)

    def test_extension_keeps_historical_metadata_and_index_detects_body_tampering(self):
        result = self.extended_fixture()
        self.assertEqual(result['followup_historical_metadata'],self.fixture()['followup_historical_metadata'])
        self.assertEqual(result['records'][:46],self.fixture()['records'])
        index = v.build_index(result)
        self.assertEqual((index['counts']['retained_prior'],index['counts']['new']),(46,411))
        for group in ('records','archived_records'):
            broken = deepcopy(result); broken[group][0]['original_text'] += ' altered'
            with self.assertRaisesRegex(ValueError,'VALUATION_PREFIX_CHANGED'): v.build_index(broken)

    def test_all_new_holds_have_protection_and_allocation_keeps_targets(self):
        result = self.extended_fixture()
        protected = {r['text'] for r in result['protected_queries']}
        self.assertTrue(all(self.material['rows'][int(line)]['normalized_text'] in protected
            for line in self.material['review']['held_source_lines']))
        actual = v.first.pinned(v.first.ROOT,v.PREVIOUS_ALLOCATION,v.prior.ALLOCATION_PIN)
        previous = dict(actual,admitted={p:46 if p=='EMPLOYMENT' else 0 for p in actual['targets']},total_admitted=46)
        allocation = v.allocation(result,previous)
        self.assertEqual(allocation['targets'],actual['targets'])
        self.assertEqual(allocation['total_admitted'],457)
        self.assertFalse(allocation['exclusion_approval_granted'])
        self.assertFalse(allocation['media_budget_changed'])

    def test_protection_source_context_prefixes_and_new_protection_tail_are_checked(self):
        result = self.extended_fixture()
        changes = [lambda r:r['protected_queries'][0].update(text='SYNTHETIC_CHANGED_PROTECTION'),
            lambda r:r['sources'][0]['synthetic_metadata'].append('changed source'),
            lambda r:r['campaign_context'][0]['synthetic_metadata'].append('changed context'),
            lambda r:r['protected_queries'][-1].update(text='SYNTHETIC_CHANGED_NEW_PROTECTION')]
        for change in changes:
            broken = deepcopy(result); change(broken)
            with self.assertRaisesRegex(ValueError,'VALUATION_EVIDENCE_PREFIX_CHANGED'):
                v.build_index(broken)


if __name__=='__main__':
    unittest.main()
