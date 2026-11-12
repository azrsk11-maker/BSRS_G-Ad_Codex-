"""Focused source/alias guards over one freshly reconstructed complete base."""
from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch

import apprenticeship_admission as e
import append_only_admission as stage
import current_negative_library as current


class ApprenticeshipAdmissionTests(unittest.TestCase):
    # A same-process generator may share its freshly reconstructed base. Never
    # load a serialized base, saved output body or acceptance cache here.
    FRESH_BASE = None

    @classmethod
    def setUpClass(cls):
        cls.when = date(2026, 11, 12)
        cls.base = cls.FRESH_BASE if cls.FRESH_BASE is not None else current._fresh_entertainment_state(
            e.first.ROOT, cls.when)[0]
        cls.material = e.load_reviewed(e.first.ROOT, cls.when)
        cls.inputs = e.extend(cls.base, e.first.ROOT, cls.when)

    def test_actual_complete_base_and_every_historical_body_are_preserved(self):
        base, inputs = self.base, self.inputs
        self.assertEqual(tuple(len(base[k]) for k in
            ('records','archived_records','protected_queries','sources')), (10955,18,16383,23))
        self.assertEqual(stage.digest(base), e.BASE_SHA256)
        self.assertEqual(stage.recover_base(inputs, stage_key=e.STAGE_KEY), base)
        self.assertEqual(inputs['records'][:10955], base['records'])
        self.assertEqual(inputs['sources'][:23], base['sources'])
        self.assertEqual(inputs['protected_queries'], base['protected_queries'])
        self.assertEqual(inputs['archived_records'], base['archived_records'])
        for key in set(base)-{'records','sources','protected_queries'}:
            self.assertEqual(inputs[key], base[key])

    def test_eight_original_literals_have_exact_high_pending_and_unknown_metrics(self):
        rows = self.inputs['records'][10955:]
        self.assertEqual(len(rows),8)
        self.assertEqual(sum(len(r['provenance_occurrences']) for r in rows),8)
        self.assertEqual(sorted(r['provenance_occurrences'][0]['source_ordinal'] for r in rows), e.SELECTED)
        for row in rows:
            occurrence = row['provenance_occurrences'][0]
            original = self.material['rows'][occurrence['source_ordinal']]
            self.assertEqual(row['original_text'], original['original_text'])
            self.assertEqual(occurrence['original_text'], row['original_text'])
            self.assertEqual(row['keyword_id'], original['candidate_identity'])
            self.assertEqual((row['match_type'],row['risk_level'],row['approval_state']),('EXACT','HIGH','PENDING'))
            self.assertTrue(all(row[k] is None for k in ('volume','cpc','observed_query','observation_date')))
            self.assertEqual(row['eligible_campaigns'],['BSRE-C0301'])
            self.assertEqual(row['deployed_resource_ids'],[])

    def test_same_route_alias_is_separate_evidence_never_ninth_count_or_protection(self):
        rows = self.inputs['records'][10955:]
        alias = self.material['rows'][1]
        representative = next(r for r in rows if r['keyword_id'] == self.material['rows'][7]['candidate_identity'])
        self.assertNotIn(alias['candidate_identity'], {r['keyword_id'] for r in rows})
        self.assertEqual(representative['supporting_semantic_alias_evidence'], e.alias_evidence(self.material))
        self.assertEqual(representative['provenance_occurrences'][0]['source_ordinal'],7)
        self.assertNotEqual(alias['normalized_text'],representative['normalized_text'])
        self.assertEqual(len(self.inputs['protected_queries']),16383)
        self.assertEqual(sum('supporting_semantic_alias_evidence' in r for r in rows),1)

    def test_current_records_archives_protections_token_peers_and_closed_strings_fail(self):
        text = self.material['rows'][2]['original_text']
        cases = [('records',{'original_text':text}),
            ('archived_records',{'original_text':' '.join(reversed(e.ka.tokens(text)))}),
            ('protected_queries',{'text':text}),
            ('protected_queries',{'text':''.join(e.ka.tokens(text))})]
        for field,row in cases:
            # Reuse every real body, adding only the adversarial conflict.
            base = dict(self.base); base[field] = self.base[field]+[row]
            with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_FRESH_MEMBERSHIP_CHANGED'):
                e._verify_membership(base,self.material)

    def test_review_authority_scope_alias_partition_implementation_and_dates_reseal_fail(self):
        changes = [lambda r:r.update(human_review_verified=0),
            lambda r:r.update(exclusion_approval_granted=True),
            lambda r:r.update(campaign_key='BSRE-C0001'),
            lambda r:r['selected_ordinals'].insert(0,1),
            lambda r:r['held_ordinals'].append(1),
            lambda r:r['supporting_alias'].update(adds_exact_occurrence=True),
            lambda r:r['supporting_alias'].update(representative_ordinal=6),
            lambda r:r['variant_review'].update(supporting_alias_is_separate_negative=True),
            lambda r:r['implementation'].clear(),
            lambda r:r.update(base_sha256='0'*64),
            lambda r:r.update(reviewed_on='2026-11-13',valid_until='2026-12-13')]
        for change in changes:
            review = deepcopy(self.material['review']); change(review)
            review['subject_sha256'] = e.review_subject(review,self.material)
            with self.assertRaises(ValueError): e.validate_review(review,self.material,self.when)
        with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_REVIEW_DATES'):
            e.validate_review(self.material['review'],self.material,date(2027,1,1))

    def test_hash_tamper_and_unregistered_review_fail_closed(self):
        with patch.dict(e.SOURCE_PINS,{e.CAPTURE+'/source.json':'0'*64}):
            with self.assertRaises(ValueError): e.load_sources(e.first.ROOT)
        with patch.object(e,'REVIEW_PIN',None):
            with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_REVIEW_UNREGISTERED'):
                e.load_reviewed(e.first.ROOT,self.when)
        material = deepcopy(self.material)
        review = deepcopy(material['review']); review['subject_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_REVIEW_SUBJECT_CHANGED'):
            e.validate_review(review,material,self.when)

    def test_source_semantic_alias_and_metrics_mutations_are_not_accepted(self):
        original = e.first.pinned
        for relative,change in [(e.CAPTURE+'/projection.json',lambda d:d['rows'][1].update(volume=0)),
            (e.SECOND+'/independent-review.json',lambda d:d['rows'][0]['variant_review'].update(separately_proposed_candidate=True)),
            (e.CAPTURE+'/source.json',lambda d:d['source_pages'][0]['verbatim_title_excerpts'].clear())]:
            def changed(root,file,pin):
                document = original(root,file,pin)
                if file == relative:
                    document=deepcopy(document); change(document)
                return document
            with patch.object(e.first,'pinned',side_effect=changed):
                with self.assertRaises(ValueError):e.load_sources(e.first.ROOT)

    def test_actual_base_resealed_changes_and_historical_markers_fail(self):
        for field in ['records','archived_records','sources','protected_queries']:
            base = dict(self.base); base[field] = self.base[field][:-1]
            with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_PRIOR_BASE_CHANGED'):
                e.verify_base(base,self.material)
        inputs = dict(self.inputs); inputs['invented_historical_marker'] = True
        state = dict(inputs[e.STAGE_KEY]); inputs[e.STAGE_KEY] = state
        # Resealing a modified reconstructed base cannot change the fixed base.
        base = dict(self.base); base['invented_historical_marker'] = True
        state['base_sha256'] = stage.digest(base)
        with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_PRIOR_BASE_CHANGED'):
            e.check_saved(inputs,e.first.ROOT,self.when)

    def test_mutated_derived_tail_is_rejected_before_output_audit_even_after_reseal(self):
        for change in [lambda r:r.update(volume=0),lambda r:r.update(approval_state='APPROVED'),
            lambda r:r['provenance_occurrences'][0].update(source_ordinal=1),
            lambda r:r['provenance_occurrences'].append(deepcopy(r['provenance_occurrences'][0])),
            lambda r:r.update(eligible_campaigns=['BSRE-C0001'])]:
            inputs = dict(self.inputs)
            inputs['records'] = self.inputs['records'][:10955]+deepcopy(self.inputs['records'][10955:])
            change(inputs['records'][10955])
            with patch.object(e,'_outputs') as outputs:
                with self.assertRaisesRegex(ValueError,'APPRENTICESHIP_DERIVED_BODIES_CHANGED'):
                    e.check_saved(inputs,e.first.ROOT,self.when)
                outputs.assert_not_called()

    def test_saved_outputs_bind_actual_full_audit_counts_and_no_exports(self):
        report = e.check_saved(self.inputs,e.first.ROOT,self.when)
        self.assertEqual((report['input_rows'],report['reviewed_eligible_rows'],report['new_rows']), (10963,10963,8))
        self.assertEqual((report['computed_conflicts'],report['excluded_rows'],report['approved_exclusion_rows']), (0,0,0))
        self.assertEqual(report['source_occurrences_retained_in_current_records'],11169)
        self.assertFalse(report['deployment_export_allowed'])
        self.assertFalse(report['production_writes_available'])
        self.assertFalse(report['positive_library_coverage_verified'])
        self.assertTrue(report['release_held'])


if __name__ == '__main__':
    unittest.main()
