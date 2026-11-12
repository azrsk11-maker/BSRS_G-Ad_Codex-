"""Official source coverage, preservation and failed-promotion contracts."""
from copy import deepcopy
from datetime import date,timedelta
import unittest
from unittest.mock import patch
import append_only_admission as stage
import bank_support_admission as prior
import ofqual_animal_care_admission as e
import current_negative_library as current


class AnimalCareAdmissionTests(unittest.TestCase):
    FRESH_BASE=None
    FRESH_INPUTS=None

    @classmethod
    def setUpClass(cls):
        cls.when=date(2026,11,12)
        cls.base=cls.FRESH_BASE if cls.FRESH_BASE is not None else current.reconstruct_bank_support_snapshot(at=cls.when)
        cls.material=e.load_reviewed(e.first.ROOT,cls.when)
        cls.inputs=cls.FRESH_INPUTS if cls.FRESH_INPUTS is not None else e.extend(cls.base,e.first.ROOT,cls.when)

    def test_every_historical_body_order_and_extra_marker_is_preserved(self):
        self.assertEqual(stage.digest(self.base),e.BASE_SHA256)
        self.assertEqual(stage.recover_base(self.inputs,stage_key=e.STAGE_KEY),self.base)
        for field in ['records','sources','protected_queries']:
            self.assertEqual(self.inputs[field][:len(self.base[field])],self.base[field])
        for field in set(self.base)-{'records','sources','protected_queries'}:
            self.assertEqual(self.inputs[field],self.base[field])

    def test_all_444_occurrences_and_prior_unavailable_held_peers_are_compared(self):
        d=self.material['review']['fresh_variant_review'];joins=d['source_group_join_results']
        self.assertEqual((len(joins),sum(len(x['source_ordinals']) for x in joins.values())),(423,444))
        self.assertEqual((d['external_key_comparisons'],d['within_source_key_comparisons']),(1692,1692))
        self.assertEqual((d['cohort_external_key_comparisons'],d['cohort_within_source_key_comparisons']),(852,852))
        source=self.material['projection']
        all_ordinals={n for j in joins.values() for n in j['source_ordinals']}
        self.assertTrue(set(source['previously_reviewed_available_ordinals'])<=all_ordinals)
        unavailable={r['source_record_ordinal'] for r in source['records'] if r['values']['Qualification Status']!='Available to learners'}
        self.assertEqual(len(unavailable),178);self.assertTrue(unavailable<=all_ordinals)

    def test_original_text_flags_wording_holds_and_duplicate_forms_remain(self):
        m=self.material;held=m['review']['held_groups'];self.assertTrue(set(m['initial_holds'])<=set(held))
        self.assertEqual((len(m['groups']),sum(map(len,m['groups'].values()))),(213,214))
        duplicates=[v for v in m['groups'].values() if len(v)>1]
        self.assertEqual(len(duplicates),1)
        original=[r['values']['Qualification Title'] for r in duplicates[0]]
        self.assertNotEqual(original[0],original[1]);self.assertEqual(e.ka.normalize(original[0]),e.ka.normalize(original[1]))
        self.assertIn(e.ka.normalize(original[0]),held)
        self.assertTrue(set(m['wording_holds'])<=set(held))

    def test_source_wording_is_not_repaired_or_promoted(self):
        evidence=self.material['wording_evidence']['source_occurrences']
        a,b=evidence
        self.assertIn('STO166',a['original_literal']);self.assertEqual(a['apprenticeship_standard_reference_number'],'ST0166')
        self.assertIn('Qualifcations',b['original_literal']);self.assertEqual(b['owner_organisation_name'],'AIM Qualifications')
        new=self.inputs['records'][len(self.base['records']):]
        ordinals={o['source_record_ordinal'] for r in new for o in r['provenance_occurrences']}
        self.assertFalse(ordinals&{12445,41428})

    def test_new_occurrences_bind_all_original_cells_and_have_unknown_metrics(self):
        for record in self.inputs['records'][len(self.base['records']):]:
            key=record['normalized_text'];rows=self.material['groups'][key]
            self.assertEqual(record['original_text'],rows[0]['values']['Qualification Title'])
            self.assertEqual(len(record['provenance_occurrences']),len(rows))
            for row,occurrence in zip(rows,record['provenance_occurrences']):
                self.assertEqual(occurrence['qualification_number'],row['values']['Qualification Number'])
                self.assertEqual(occurrence['complete_public_values_sha256'],stage.digest(row['values']))
                self.assertEqual(occurrence['original_literal'],row['values']['Qualification Title'])
            self.assertIsNone(record['volume']);self.assertIsNone(record['cpc'])
            self.assertEqual(record['approval_state'],'PENDING');self.assertEqual(record['deployed_resource_ids'],[])

    def test_parent_metadata_does_not_collapse_entry_numbers_levels_types_or_subjects(self):
        self.assertNotEqual(e.keys('Provider Entry 1 Award in Animal Care'),e.keys('Provider Entry 2 Award in Animal Care'))
        self.assertNotEqual(e.keys('Provider Level 3 Award in Dog Grooming'),e.keys('Provider Level 3 Certificate in Dog Grooming'))
        self.assertNotEqual(e.keys('Provider Level 3 Canine Massage'),e.keys('Provider Level 3 Canine Hydrotherapy'))
        diagnostics=self.material['review']['fresh_variant_review']['qualification_parent_diagnostics']
        self.assertTrue(all(x['parent_membership_causes_hold'] is False for x in diagnostics))

    def test_new_hold_cannot_hide_conflicting_existing_negative(self):
        key=next(iter(self.material['initial_holds']))
        base={k:[] for k in ['records','archived_records','protected_queries','sources']}
        base['records']=[{'original_text':key,'keyword_id':'EXISTING'}]
        with self.assertRaisesRegex(ValueError,'ANIMAL_CARE_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE'):
            e.membership(base,self.material)

    def test_resealed_false_hold_cannot_replace_fresh_comparisons(self):
        m=deepcopy(self.material);r=m['review'];key=r['selected_normalized_phrases'][0]
        r['selected_normalized_phrases'].remove(key);r['held_groups'][key]='fabricated hold'
        r['fresh_variant_review']['selected_normalized_phrases']=list(r['selected_normalized_phrases'])
        r['fresh_variant_review']['all_held_normalized_phrases']=sorted(r['held_groups'])
        r['subject_sha256']=e.review_subject(r,m);e.validate_review(r,m,self.when)
        with patch.object(e,'load_reviewed',return_value=m):
            with self.assertRaisesRegex(ValueError,'ANIMAL_CARE_FRESH_VARIANT_REVIEW_CHANGED'):
                e.extend(self.base,e.first.ROOT,self.when)

    def test_resealed_authority_scope_and_expiry_changes_fail(self):
        for key,value in [('deployment_authorized',True),('campaign_key','OTHER'),('reviewer_kind','HUMAN'),
                          ('valid_until',(self.when+timedelta(days=31)).isoformat())]:
            r=deepcopy(self.material['review']);r[key]=value;r['subject_sha256']=e.review_subject(r,self.material)
            with self.subTest(key=key),self.assertRaises(ValueError):e.validate_review(r,self.material,self.when)

    def test_base_archives_and_unregistered_reviews_cannot_be_substituted(self):
        changed=deepcopy(self.base);changed['archived_records'][0]['original_text']+=' changed'
        with self.assertRaisesRegex(ValueError,'ANIMAL_CARE_PRIOR_BASE_CHANGED'):e.verify_base(changed,self.material)
        with patch.object(e,'REVIEW_PIN',None):
            with self.assertRaisesRegex(ValueError,'ANIMAL_CARE_REVIEW_UNREGISTERED'):e.load_reviewed(e.first.ROOT,self.when)

    def test_modified_derived_records_are_rejected(self):
        changed=deepcopy(self.inputs);changed['records'][-1]['evidence_ref']='fabricated'
        with self.assertRaisesRegex(ValueError,'ANIMAL_CARE_DERIVED_BODIES_CHANGED'):
            e.check_saved(changed,e.first.ROOT,self.when)

    def test_saved_audit_and_allocation_remain_non_deployable(self):
        summary=e.check_saved(self.inputs,e.first.ROOT,self.when)
        self.assertEqual(summary['reviewed_eligible_rows'],len(self.inputs['records']))
        self.assertEqual(summary['approved_exclusion_rows'],0);self.assertFalse(summary['deployment_export_allowed'])
        a=e.first.pinned(e.first.ROOT,e.FOLDER+'/research-pool-allocation.json',e.OUTPUT_PINS['research-pool-allocation.json'])
        p=e.first.pinned(e.first.ROOT,prior.FOLDER+'/research-pool-allocation.json',prior.OUTPUT_PINS['research-pool-allocation.json'])
        self.assertEqual(a['targets'],p['targets']);self.assertIsNone(a['target_transfer'])

    def test_new_default_and_support_snapshot_have_separate_fresh_chains(self):
        with patch.object(current,'_fresh_ofqual_animal_care_state',return_value=('animal','animal-report')) as a:
            self.assertEqual(current.reconstruct_ofqual_animal_care_snapshot(at=self.when),'animal');self.assertEqual(current.verify_ofqual_animal_care_snapshot(at=self.when),'animal-report')
            self.assertEqual(a.call_count,2)
        with patch.object(current,'_fresh_bank_support_state',return_value=('old','old-report')) as old:
            self.assertEqual(current.reconstruct_bank_support_snapshot(at=self.when),'old')
            self.assertEqual(current.verify_bank_support_snapshot(at=self.when),'old-report');self.assertEqual(old.call_count,2)


if __name__=='__main__':unittest.main()
