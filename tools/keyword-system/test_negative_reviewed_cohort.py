"""Actual reviewed cohorts and isolated adversarial cases; no Google requests."""
import copy
from datetime import date
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import negative_admission as first
import negative_employment_admission as employment
import negative_reviewed_cohort as registered
import negative_library as library


class RegisteredCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = first.reconstruct()
        cls.prior = library.compose([cls.first, employment.reconstruct(prior=cls.first)])
        cls.entry = registered.CATALOG[0]
        cls.inputs = registered.reconstruct(first.ROOT, cls.entry, cls.prior)
        cls.context = first.pinned(first.ROOT, first.FOLDER+'/service-context.json', first.CONTEXT_PIN)
        cls.campaign = next(r for r in cls.prior['campaigns'] if r['campaign_key'] == first.CAMPAIGN)
        cls.bindings = first.pinned(first.ROOT, first.REPORT, first.PINS[first.REPORT])['source_bindings']['review_workbenches_sha256']

    def reseal(self, review, context=None, campaign=None):
        review['subject_sha256'] = registered.subject(review, context or self.context,
                                                      campaign or self.campaign, self.bindings)
        return review

    def test_actual_academic_admission_preserves_holds_and_protection(self):
        result = registered._verify_reconstructed(self.inputs, self.entry, at=date(2026, 11, 11))
        self.assertEqual((result['reviewed_eligible_rows'], result['held_phrases'], result['prior_protected_holds']), (903, 56, 3))
        self.assertEqual(result['source_occurrences_retained'], 903)
        self.assertEqual(result['protected_queries_indexed'], 12139)
        self.assertEqual(result['approved_exclusion_rows'], 0)
        selected = {r['normalized_text'] for r in self.inputs['records']}
        held = set(self.inputs['review']['held_phrases'])
        self.assertFalse(selected & held)
        self.assertTrue(held <= {r['text'] for r in self.inputs['protected_queries']})
        self.assertIn('certified residential appraiser exam', selected)
        self.assertIn('property bachelor', held)
        self.assertIn('real estate agent bachelor degree', held)
        self.assertIn('realestate exam', held)

    def test_unknown_cohort_is_not_discovered_or_promoted(self):
        unknown = dict(self.entry, key='TEST-ONLY-UNREGISTERED')
        with self.assertRaisesRegex(ValueError, 'UNREGISTERED_COHORT'):
            registered.reconstruct(first.ROOT, unknown, self.prior)

    def test_original_coverage_cannot_be_omitted(self):
        review = dict(self.inputs['review'], coverage_reports=[])
        with self.assertRaisesRegex(ValueError, 'COVERAGE_REPORTS'):
            registered.load_bindings(first.ROOT, review)

    def test_explicit_additional_coverage_cannot_replace_prior_workbench_versions(self):
        review = copy.deepcopy(self.inputs['review'])
        extra = 'docs/audit/TEST-ONLY-COVERAGE.json'
        review['coverage_reports'].append({'file': extra, 'sha256': '0'*64})
        source = next(iter(self.bindings))
        fake = {'source_bindings': {'review_workbenches_sha256': {source: '0'*64}},
                'cross_review_overlap_phrases': []}
        original = first.pinned
        def extra_report(root, relative, digest):
            return fake if relative == extra else original(root, relative, digest)
        with patch.object(first, 'pinned', side_effect=extra_report):
            with self.assertRaisesRegex(ValueError, 'SOURCE_REVIEW_DISAGREEMENT'):
                registered.load_bindings(first.ROOT, review)

    def test_new_held_source_is_checked_without_rewriting_old_cohorts(self):
        review = copy.deepcopy(self.inputs['review'])
        report = 'docs/audit/TEST-ONLY-NEW-COVERAGE.json'
        wb = 'docs/audit/TEST-ONLY-NEW-WORKBENCH.json'
        review['coverage_reports'].append({'file': report, 'sha256': '0'*64})
        bindings = dict(self.bindings, **{wb: '0'*64})
        query = self.inputs['records'][0]['normalized_text']
        synthetic_coverage = {'source_bindings': {'review_workbenches_sha256': {wb: '0'*64}},
                              'cross_review_overlap_phrases': []}
        synthetic_wb = {'queue': [{'normalized_text': query, 'disposition': 'HOLD'}]}
        review['subject_sha256'] = registered.subject(review, self.context, self.campaign, bindings)
        original = first.pinned
        def new_evidence(root, relative, digest):
            if relative == report:
                return synthetic_coverage
            if relative == wb:
                return synthetic_wb
            if relative == self.entry['folder']+'/review.json':
                return review
            return original(root, relative, digest)
        with patch.object(first, 'pinned', side_effect=new_evidence):
            with self.assertRaisesRegex(ValueError, 'PRIOR_HOLD|PROTECTED_CONFLICT'):
                registered.reconstruct(first.ROOT, self.entry, self.prior)

    def test_review_cannot_claim_human_or_production_authority(self):
        for key in registered.LIMITS:
            for value in (True, 0):
                review = copy.deepcopy(self.inputs['review']);review[key] = value
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'CANNOT_GRANT_AUTHORITY'):
                    registered.validate_review(self.reseal(review), self.entry, self.context, self.campaign, self.bindings)
        review = copy.deepcopy(self.inputs['review']);review['reviewer'] = 'Amit'
        with self.assertRaisesRegex(ValueError, 'REVIEW_AUTHORITY'):
            registered.validate_review(self.reseal(review), self.entry, self.context, self.campaign, self.bindings)

    def test_unrecognized_source_or_changed_subject_fails(self):
        review = copy.deepcopy(self.inputs['review'])
        review['source_selection'] = {'docs/private.json': ['TEST-ONLY']}
        with self.assertRaisesRegex(ValueError, 'SOURCE_SELECTION'):
            registered.validate_review(self.reseal(review), self.entry, self.context, self.campaign, self.bindings)
        review = copy.deepcopy(self.inputs['review'])
        review['source_identity_limits'] += ' TEST-ONLY CHANGE'
        with self.assertRaisesRegex(ValueError, 'SUBJECT_CHANGED'):
            registered.validate_review(review, self.entry, self.context, self.campaign, self.bindings)

    def test_service_context_or_live_scope_cannot_gain_authority(self):
        for key in ('inventory_or_availability_verified', 'submission_or_consent_action_performed', 'live_campaign_mapping_assigned'):
            context = dict(self.context, **{key: True})
            review = self.reseal(copy.deepcopy(self.inputs['review']), context=context)
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'SERVICE_CONTEXT_AUTHORITY'):
                registered.validate_review(review, self.entry, context, self.campaign, self.bindings)
        campaign = dict(self.campaign, google_campaign_id='TEST-ONLY-NOT-A-PLATFORM-ID')
        review = self.reseal(copy.deepcopy(self.inputs['review']), campaign=campaign)
        with self.assertRaisesRegex(ValueError, 'PLANNING_SCOPE_CHANGED'):
            registered.validate_review(review, self.entry, self.context, campaign, self.bindings)

    def test_prior_protected_cases_cannot_be_admitted_by_resealed_counts(self):
        review = copy.deepcopy(self.inputs['review'])
        for text in self.inputs['prior_protected_holds']:
            review['held_phrases'].pop(text)
        review['selected_rows'] = 906
        review['intent_counts']['FORMAL_ACADEMIC_RESEARCH'] += 3
        self.reseal(review)
        entry = dict(self.entry, expected_rows=906)
        original = first.pinned
        def fake_review(root, relative, digest):
            if relative == entry['folder']+'/review.json':
                return review
            return original(root, relative, digest)
        with patch.object(registered, 'CATALOG', (entry,)), patch.object(first, 'pinned', side_effect=fake_review):
            with self.assertRaisesRegex(ValueError, 'UNRESOLVED_CONFLICT'):
                registered.reconstruct(first.ROOT, entry, self.prior)

    def test_current_invocation_still_checks_new_source_after_previous_success(self):
        library.verify(at=date(2026, 11, 11))
        original = first.pinned
        target = next(iter(self.inputs['review']['source_selection']))
        def changed_source(root, relative, digest):
            if relative == target:
                raise ValueError('TEST_ONLY_NEW_SOURCE_CHANGED')
            return original(root, relative, digest)
        with patch.object(first, 'pinned', side_effect=changed_source):
            with self.assertRaisesRegex(ValueError, 'NEW_SOURCE_CHANGED'):
                library.verify(at=date(2026, 11, 11))

    def test_expired_future_or_fake_platform_equivalence_holds(self):
        for at in (date(2026, 11, 10), date(2026, 12, 12)):
            with self.subTest(at=at), self.assertRaisesRegex(ValueError, 'RESEARCH_NOT_ELIGIBLE'):
                registered._verify_reconstructed(self.inputs, self.entry, at=at)
        review = copy.deepcopy(self.inputs['review'])
        review['variant_review']['google_equivalence_verified'] = True
        with self.assertRaisesRegex(ValueError, 'VARIANT_AUTHORITY'):
            registered.validate_review(self.reseal(review), self.entry, self.context, self.campaign, self.bindings)

    def test_immutable_cohort_report_mutation_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/self.entry['folder']/'cohort-report.json'
            path.parent.mkdir(parents=True);path.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'PINNED_INPUT_CHANGED'):
                registered._verify_reconstructed(self.inputs, self.entry, Path(tmp), date(2026, 11, 11))

    def test_actual_nonproperty_review_preserves_held_navigation_and_variants(self):
        prior = library.compose([self.prior, self.inputs])
        entry = registered.CATALOG[1]
        inputs = registered.reconstruct(first.ROOT, entry, prior)
        result = registered._verify_reconstructed(inputs, entry, at=date(2026, 11, 11))
        self.assertEqual((result['reviewed_eligible_rows'], result['held_phrases'],
                          result['source_occurrences_retained']), (412, 24, 412))
        self.assertEqual(inputs['review']['intent_counts'], {'SOFTWARE': 350, 'SERVICE': 42, 'MEDIA': 20})
        selected = {r['normalized_text'] for r in inputs['records']}
        held = set(inputs['review']['held_phrases'])
        self.assertFalse(selected & held)
        self.assertTrue(held <= {r['text'] for r in inputs['protected_queries']})
        for phrase in ('bitrix24 real estate', 'mycrm propertyfinder', 'sales force real estate crm',
                       'realestate plugin', 'plumber dubai emergency plumbing in dubai'):
            self.assertIn(phrase, held)
        for phrase in ('real estate crm software', 'water heater repair dubai', 'property stock photos'):
            self.assertIn(phrase, selected)
        self.assertEqual(result['protected_queries_indexed'], 12163)
        self.assertEqual(result['approved_exclusion_rows'], 0)
        self.assertFalse(result['deployment_export_allowed'])

    def test_actual_vehicle_review_preserves_ambiguity_and_both_source_occurrences(self):
        prior = library.compose([self.prior, self.inputs])
        nonproperty = registered.reconstruct(first.ROOT, registered.CATALOG[1], prior)
        prior = library.compose([prior, nonproperty])
        entry = registered.CATALOG[2]
        inputs = registered.reconstruct(first.ROOT, entry, prior)
        result = registered._verify_reconstructed(inputs, entry, at=date(2026, 11, 11))
        self.assertEqual((result['reviewed_eligible_rows'],result['held_phrases'],
                          result['source_occurrences_retained']), (1509,53,1510))
        selected = {r['normalized_text']:r for r in inputs['records']}
        held = set(inputs['review']['held_phrases'])
        self.assertFalse(set(selected) & held)
        self.assertTrue(held <= {r['text'] for r in inputs['protected_queries']})
        for phrase in ('prado for rent in dubai','rent urus dubai','pick up rental dubai',
                       'carrentals dubai','drivus car rental dubai dubai'):
            self.assertIn(phrase,held)
        self.assertTrue('car rental dubai' in selected, 'Captured car-rental literal missing')
        self.assertTrue('rent bmw 7 series dubai' in selected, 'Captured make/model literal missing')
        self.assertEqual({o['batch'] for o in selected['annual car lease dubai']['provenance_occurrences']},
            {'KP-DISC-20261108-TENANTS','KP-20261110-SOFTWARE-SERVICES-PRODUCTS'})
        self.assertEqual(result['protected_queries_indexed'],12216)
        self.assertEqual(result['approved_exclusion_rows'],0)
        self.assertFalse(result['deployment_export_allowed'])


class SeparatedCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initial=first.reconstruct()
        cls.prior=library.compose([initial,employment.reconstruct(prior=initial)])
        for entry in registered.CATALOG[:-1]:
            part=registered.reconstruct(first.ROOT,entry,cls.prior)
            cls.prior=library.compose([cls.prior,part])
        cls.entry=registered.CATALOG[-1]
        cls.inputs=registered.reconstruct(first.ROOT,cls.entry,cls.prior)
        cls.capture='docs/audit/keyword-discovery-2026-11-08/capture.json'
        cls.context=first.pinned(first.ROOT,first.FOLDER+'/service-context.json',first.CONTEXT_PIN)
        cls.campaign=next(c for c in cls.prior['campaigns'] if c['campaign_key']==first.CAMPAIGN)
        cls.bindings,_=registered.load_bindings(first.ROOT,cls.inputs['review'])

    def test_actual_separate_review_uses_real_export_capture_and_preserves_holds(self):
        result=registered._verify_reconstructed(self.inputs,self.entry,at=date(2026,11,11))
        self.assertEqual((result['reviewed_eligible_rows'],result['held_phrases'],
                          result['prior_protected_holds'],result['source_occurrences_retained']), (259,31,1,261))
        pins=self.inputs['review']['capture_pins']
        self.assertIn(self.capture,pins)
        self.assertNotIn('docs/audit/keyword-triage-2026-11-08/capture.json',pins)
        selected={r['normalized_text'] for r in self.inputs['records']}
        held=set(self.inputs['review']['held_phrases'])
        self.assertTrue('buy gold dubai' in selected,'Actual goods literal missing')
        self.assertTrue('real estate broker course' in selected,'Actual occupational literal missing')
        self.assertFalse(selected & held)
        self.assertTrue(held <= {r['text'] for r in self.inputs['protected_queries']})
        for phrase in ('estate agency and property management course','oqood training course registration dubai',
                       'dubai shopping festival sale','real estate course in person'):
            self.assertIn(phrase,held)
        self.assertEqual(result['protected_queries_indexed'],12246)
        self.assertFalse(result['deployment_export_allowed'])

    def test_capture_wrong_account_is_rejected_after_pin_read(self):
        original=first.pinned
        def wrong(root,relative,digest):
            value=original(root,relative,digest)
            if relative==self.capture:value['account_id']='TEST_ONLY_WRONG_ACCOUNT'
            return value
        with patch.object(first,'pinned',side_effect=wrong):
            with self.assertRaisesRegex(ValueError,'REGISTERED_SOURCE_ACCOUNT'):
                registered.reconstruct(first.ROOT,self.entry,self.prior)

    def test_capture_source_manifest_digest_mismatch_is_rejected(self):
        original=first.pinned
        def wrong(root,relative,digest):
            value=original(root,relative,digest)
            if relative==self.capture:
                next(r for r in value['source_files'] if r['batch_id']=='KP-DISC-20261108-COMMERCIAL')['sha256']='0'*64
            return value
        with patch.object(first,'pinned',side_effect=wrong):
            with self.assertRaisesRegex(ValueError,'REGISTERED_CAPTURE_SOURCE_MISMATCH'):
                registered.reconstruct(first.ROOT,self.entry,self.prior)

    def test_resealed_review_cannot_substitute_a_review_folder_capture(self):
        review=copy.deepcopy(self.inputs['review'])
        review['capture_pins'].pop(self.capture)
        review['capture_pins']['docs/audit/keyword-triage-2026-11-08/capture.json']='0'*64
        review['subject_sha256']=registered.subject(review,self.context,self.campaign,self.bindings)
        original=first.pinned
        def changed(root,relative,digest):
            return review if relative==self.entry['folder']+'/review.json' else original(root,relative,digest)
        with patch.object(first,'pinned',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'REGISTERED_CAPTURE_COVERAGE'):
                registered.reconstruct(first.ROOT,self.entry,self.prior)

    def test_category_context_document_bytes_are_bound_in_the_review(self):
        for relative in (self.entry['folder']+'/PRIMARY_CONTEXT.md',
                         'docs/audit/keyword-employment-education-2026-11-10/ENTITY_REVIEW.md'):
            self.assertIn(hashlib.sha256((first.ROOT/relative).read_bytes()).hexdigest(),
                          self.inputs['review']['source_identity_limits'])

    def test_resealed_counts_cannot_promote_prior_property_learning_conflict(self):
        review=copy.deepcopy(self.inputs['review'])
        review['held_phrases'].pop('estate agency and property management course')
        review['selected_rows']+=1;review['intent_counts']['PROFESSIONAL_LEARNING_OR_ENTRY']+=1
        review['subject_sha256']=registered.subject(review,self.context,self.campaign,self.bindings)
        entry=dict(self.entry,expected_rows=260)
        original=first.pinned
        def changed(root,relative,digest):
            return review if relative==entry['folder']+'/review.json' else original(root,relative,digest)
        with patch.object(registered,'CATALOG',(entry,)),patch.object(first,'pinned',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'REGISTERED_UNRESOLVED_CONFLICT'):
                registered.reconstruct(first.ROOT,entry,self.prior)


if __name__ == '__main__':
    unittest.main()
