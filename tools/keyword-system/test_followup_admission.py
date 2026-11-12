"""Source-bound guards and pure synthetic split cases; no acceptance cache.

The required current-library composition check supplies the complete vendor
reconstruction and generic audit. These cases do not repeat that expensive work.
"""
from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch

import followup_admission as f


class FollowupAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.material = f.load_reviewed(f.first.ROOT,date(2026,11,11))

    def validate(self, review):
        m = self.material
        f.validate_final_review(review,m['preliminary'],m['reconciled'],m['context'],
                                next(r for r in m['registry'] if r['campaign_key']==f.first.CAMPAIGN),
                                date(2026,11,11))

    def fixture(self):
        """Small clearly synthetic base for body/partition algorithm tests."""
        m = self.material
        byid = {r['canonical_id']:r for r in m['reconciled']['records']}
        conflicts = [byid[r['canonical_id']]['normalized_keyword']
            for r in m['preliminary']['records'] if r['baseline_membership']=='EXISTING_NEGATIVE'
            and r['canonical_id'] in m['review']['held_phrases']]
        self.assertEqual(len(conflicts),6)
        records = [{'keyword_id':'SYNTHETIC-OLD-'+str(i),'original_text':text,
            'reason_code':'EXPLICIT_EMPLOYMENT_RESEARCH',
            'provenance_occurrences':[{'synthetic_occurrence':i}],
            'synthetic_nested_metadata':{'unchanged':['source','body']}}
            for i,text in enumerate(conflicts)]
        records.append({'keyword_id':'SYNTHETIC-KEEP','original_text':'synthetic retained phrase',
            'reason_code':'EXPLICIT_EMPLOYMENT_RESEARCH','provenance_occurrences':[]})
        protected = [{'query_id':'SYNTHETIC-Q-'+str(i),'text':r['normalized_keyword']}
            for i,r in enumerate(m['preliminary']['records']) if r['baseline_membership']=='EXISTING_PROTECTED']
        for query in protected:
            query.update(campaign_keys=[f.first.CAMPAIGN],services=['residential_rental'],
                must_serve=True,evidence_ref='SYNTHETIC_PROTECTED_MATCHING_CASE',
                reviewed_on='2026-11-11',valid_until='2026-12-11')
        return {'records':records,'archived_records':[{'keyword_id':'SYNTHETIC-PRIOR-ARCHIVE',
            'original_text':'synthetic previously archived phrase'}],
            'protected_queries':protected,'sources':[],
            'campaigns':m['registry'],'campaign_context':[]}

    def test_pinned_manual_review_has_explicit_authority_and_complete_partition(self):
        self.validate(self.material['review'])
        review = self.material['review']
        self.assertEqual(len(review['selected_canonical_ids']),191)
        self.assertEqual(len(review['held_phrases']),235)
        self.assertEqual(len(review['existing_occurrence_only_ids']),18)
        self.assertTrue(all(review[k] is False for k in f.LIMITS))

    def test_final_manual_review_cannot_promote_an_original_hold_or_disagreement(self):
        review = deepcopy(self.material['review'])
        key = next(k for k in review['held_phrases'])
        del review['held_phrases'][key]
        review['selected_canonical_ids'] = sorted(review['selected_canonical_ids']+[key])
        review['intent_by_canonical_id'][key] = 'EXPLICIT_EMPLOYMENT_RESEARCH'
        with self.assertRaisesRegex(ValueError,'FOLLOWUP_PRIOR_HOLD_NOT_PRESERVED'):
            self.validate(review)

    def test_final_review_rejects_authority_scope_and_missing_partition(self):
        for change in ('authority','scope','missing','duplicate'):
            with self.subTest(change=change):
                review = deepcopy(self.material['review'])
                if change=='authority': review['production_authorized']=True
                elif change=='scope': review['campaign_key']='BSRE-C0001'
                elif change=='missing': review['selected_canonical_ids'].pop()
                else: review['selected_canonical_ids'].append(review['selected_canonical_ids'][0])
                with self.assertRaises(ValueError): self.validate(review)

    def test_review_subject_cannot_be_replaced_by_newer_heuristic_result(self):
        review = deepcopy(self.material['review'])
        review['heuristic_preview_reassessment'] += ' changed'
        with self.assertRaisesRegex(ValueError,'FOLLOWUP_REVIEW_SUBJECT_CHANGED'):
            self.validate(review)

    def test_expired_review_is_not_current_research_acceptance(self):
        m = self.material
        with self.assertRaisesRegex(ValueError,'FOLLOWUP_REVIEW_DATES'):
            f.validate_final_review(m['review'],m['preliminary'],m['reconciled'],m['context'],
                next(r for r in m['registry'] if r['campaign_key']==f.first.CAMPAIGN),date(2027,1,1))

    def test_protective_split_preserves_old_bodies_order_and_prior_archive(self):
        base = self.fixture()
        before = deepcopy(base)
        result = f.apply_overlay(base,self.material['review'],self.material['reconciled'])
        self.assertEqual(base,before)
        self.assertEqual(result['records'],before['records'][-1:])
        self.assertEqual(result['archived_records'],before['archived_records']+before['records'][:-1])
        self.assertEqual(result['followup_newly_archived'],before['records'][:-1])
        self.assertEqual(len(result['followup_added_protections']),190)
        self.assertEqual(result['protected_queries'][:45],before['protected_queries'])
        result['archived_records'][1]['synthetic_nested_metadata']['unchanged'].append('changed copy')
        self.assertEqual(base,before)

    def test_new_cohort_retains_both_real_source_occurrences_and_false_release_authority(self):
        base = self.fixture()
        overlaid = f.apply_overlay(base,self.material['review'],self.material['reconciled'])
        cohort = f.build_cohort(overlaid,self.material)
        self.assertEqual(len(cohort['records']),191)
        self.assertEqual(len(cohort['sources']),2)
        source_ids = {s['source_id'] for s in cohort['sources']}
        self.assertEqual({r['reason_code'] for r in cohort['records']},f.INTENTS)
        for row in cohort['records']:
            refs = row['provenance_occurrences']
            self.assertEqual(len(refs),2)
            self.assertEqual({r['batch'] for r in refs},source_ids)
            self.assertTrue(all(r['review_sha256']==f.REVIEW_PIN for r in refs))
            self.assertEqual(row['scope_target'],{'campaign_key':f.first.CAMPAIGN})
            self.assertEqual(row['match_type'],'EXACT')
            self.assertEqual(row['risk_level'],'HIGH')
            self.assertEqual(row['approval_state'],'PENDING')
            self.assertEqual(row['evidence_ref'],f.FOLDER+'/review.json#'+f.capture.canonical_id(row['normalized_text']))
            self.assertEqual(row['deployed_resource_ids'],[])
            self.assertIsNone(row['volume'])
            self.assertIsNone(row['cpc'])

    def test_previously_protected_or_known_literal_cannot_be_added_as_novel(self):
        for group in ('records','archived_records','protected_queries'):
            with self.subTest(group=group):
                base = self.fixture()
                key = self.material['review']['selected_canonical_ids'][0]
                row = next(r for r in self.material['reconciled']['records'] if r['canonical_id']==key)
                if group=='protected_queries': base[group].append({'query_id':'SYNTHETIC-COLLISION','text':row['normalized_keyword']})
                else: base[group].append({'keyword_id':'SYNTHETIC-COLLISION','original_text':row['normalized_keyword']})
                with self.assertRaisesRegex(ValueError,'FOLLOWUP_SELECTED_NOT_NOVEL'):
                    f.build_cohort(base,self.material)

    def test_arbitrary_supplied_base_cannot_skip_complete_vendor_snapshot(self):
        with self.assertRaisesRegex(ValueError,'FOLLOWUP_VENDOR_BASE_CHANGED'):
            f.verify_base(self.fixture(),self.material)

    def test_all_held_phrase_reinsertion_hypotheses_hit_actual_generated_protection(self):
        base = self.fixture()
        overlaid = f.apply_overlay(base,self.material['review'],self.material['reconciled'])
        cohort = f.build_cohort(overlaid,self.material)
        byid = {r['canonical_id']:r for r in self.material['reconciled']['records']}
        hypotheses = []
        for i,key in enumerate(self.material['review']['held_phrases']):
            row = deepcopy(cohort['records'][0])
            # Explicit unsafe synthetic hypotheses: never research rows/exports.
            row.update(keyword_id='SYNTHETIC-HELD-'+str(i),negative_id='SYNTHETIC-HELD-'+str(i),
                original_text=byid[key]['keyword_variants'][0],normalized_text=byid[key]['normalized_keyword'],
                evidence_ref='SYNTHETIC_UNSAFE_REINSERTION_NOT_RESEARCH')
            hypotheses.append(row)
        contexts = [{'campaign_key':f.first.CAMPAIGN,'services':['residential_rental'],
            'evidence_ref':'SYNTHETIC_MATCHING_CONTEXT','reviewed_on':'2026-11-11',
            'valid_until':'2026-12-11'}]
        result = f.audit('negative',hypotheses,cohort['sources'],cohort['campaigns'],
            contexts,overlaid['protected_queries'],date(2026,11,11))
        self.assertEqual(result['global_errors'],[])
        self.assertEqual(result['excluded_rows'],235)
        self.assertEqual(result['reviewed_eligible_rows'],0)
        self.assertEqual(len(result['protected_conflicts']),235)
        self.assertFalse(result['deployment_export_allowed'])

    def test_complete_base_catalog_body_guards_do_not_accept_count_only_substitutions(self):
        # A clearly synthetic full-size shape isolates fingerprint enforcement.
        # It is never passed to admission or written as a verified source.
        m = self.material
        prior = m['preliminary']['records']
        base = self.fixture()
        known = [r['normalized_keyword'] for r in prior if r['baseline_membership']=='EXISTING_NEGATIVE']
        base['records'] = [{'keyword_id':'SYNTHETIC-BASE-'+str(i),'original_text':text}
            for i,text in enumerate(known)]
        base['records'] += [{'keyword_id':'SYNTHETIC-BASE-'+str(i),
            'original_text':'synthetic baseline phrase '+str(i)} for i in range(24,10014)]
        base['archived_records'] = [{'keyword_id':'SYNTHETIC-ARCHIVE-'+str(i),
            'original_text':'synthetic archived phrase '+str(i)} for i in range(12)]
        base['protected_queries'] += [{'query_id':'SYNTHETIC-PROTECTION-'+str(i),
            'text':'synthetic protected phrase '+str(i)} for i in range(45,15309)]
        base['sources'] = [{'source_id':'SYNTHETIC-BASE-SOURCE','synthetic':True}]
        base['campaign_context'] = [{'campaign_key':f.first.CAMPAIGN,'synthetic':True}]
        pins = {'VENDOR_RECORDS_SHA256':f.digest(base['records']),
            'VENDOR_ARCHIVED_SHA256':f.digest(base['archived_records']),
            'VENDOR_PROTECTION_SHA256':f.digest(base['protected_queries']),
            'VENDOR_SOURCE_SHA256':f.digest(base['sources']),
            'VENDOR_CONTEXT_SHA256':f.digest(base['campaign_context'])}
        with patch.multiple(f,**pins):
            f.verify_base(base,m)
            for key in ('records','archived_records','protected_queries','sources','campaign_context'):
                with self.subTest(catalog=key):
                    changed = deepcopy(base)
                    changed[key][0]['synthetic_changed_body']=True
                    with self.assertRaisesRegex(ValueError,'FOLLOWUP_VENDOR_BASE_CHANGED'):
                        f.verify_base(changed,m)

    def test_index_fingerprints_preserve_bodies_and_provenance_beyond_ids(self):
        # Comparator-only synthetic fixture: actual full check_saved remains in
        # the required fresh current-library integration, not this small test.
        base = self.fixture()
        overlaid = f.apply_overlay(base,self.material['review'],self.material['reconciled'])
        part = f.build_cohort(overlaid,self.material)
        inputs = f.history.compose([overlaid,part])
        inputs.update(archived_records=overlaid['archived_records'],
            followup_newly_archived=overlaid['followup_newly_archived'],
            followup_added_protections=overlaid['followup_added_protections'],
            followup_retained_rows=len(overlaid['records']),followup_new_records=part['records'],
            followup_retained_records_sha256=f.digest(overlaid['records']),
            followup_base_records_sha256=f.digest(base['records']),
            followup_base_archived_sha256=f.digest(base['archived_records']),
            followup_base_protection_sha256=f.digest(base['protected_queries']),
            followup_base_source_sha256=f.digest(base['sources']))
        expected = f.build_index(inputs)
        changed = deepcopy(inputs)
        changed['records'][0]['provenance_occurrences'].append({'synthetic':'changed old provenance'})
        with self.assertRaisesRegex(ValueError,'FOLLOWUP_PREFIX_CHANGED'):
            f.build_index(changed)
        for key,field in (('archived_records','archived_records_sha256'),
                          ('protected_queries','protected_queries_sha256'),
                          ('sources','sources_sha256'),
                          ('followup_new_records','additional_records_sha256')):
            with self.subTest(catalog=key):
                changed = deepcopy(inputs)
                if key=='followup_new_records':
                    changed[key][0]['provenance_occurrences'][0]['synthetic_changed_body']=True
                else: changed[key][0]['synthetic_changed_body']=True
                self.assertNotEqual(f.build_index(changed)[field],expected[field])


if __name__=='__main__': unittest.main()
