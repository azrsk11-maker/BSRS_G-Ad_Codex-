"""Source guards and small synthetic append-only tests; no full reconstruction."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import append_only_admission as stage
import ofqual_admission as o


class OfqualAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.when = date(2026, 11, 11)
        cls.material = o.load_reviewed(o.first.ROOT, cls.when)

    def fixture(self):
        return {'records': [], 'archived_records': [], 'sources': [], 'protected_queries': [],
                'campaigns': self.material['registry'], 'campaign_context': [{
                    'campaign_key': o.first.CAMPAIGN, 'services': ['residential_rental'],
                    'evidence_ref': o.first.FOLDER+'/service-context.json', 'reviewed_on': '2026-11-11',
                    'valid_until': '2026-12-11', 'scope_kind': 'PLANNING_PURPOSE_ONLY',
                    'live_resource_mapping_claimed': False}],
                'synthetic_historical_extra': {'preserve': ['complete original marker']},
                'deployment_authorized': False, 'production_writes_available': False}

    def extended(self):
        base = self.fixture()
        cohort, protections = o.build_cohort(base, self.material)
        return base, stage.extend(base, cohort, protections,
                                  expected_base_sha256=stage.digest(base), stage_key=o.STAGE_KEY)

    def test_pinned_sources_partition_occurrences_and_scope(self):
        material = self.material
        self.assertEqual((len(material['groups']), len(material['selected']),
                          len(material['review']['held_groups'])), (311, 42, 269))
        self.assertEqual(sum(len(material['groups'][k]['source_occurrences'])
                             for k in material['selected']), 50)
        self.assertTrue(all(material['review'][k] is False for k in o.LIMITS))
        self.assertEqual(material['implementation']['historical_normalizer_sha256'],
                         '0cbbc8965ed891208066887eeaca0b011092efa6668af161bab3a2feb76454d9')

    def test_review_authority_partition_binding_and_dates_fail_closed(self):
        changes = [lambda r:r.update(human_review_verified=0),
                   lambda r:r.update(production_authorized=True),
                   lambda r:r.update(campaign_key='BSRE-C0001'),
                   lambda r:r['selected_group_ids'].append('OFQUAL-TITLE-298'),
                   lambda r:r['held_groups'].pop('OFQUAL-TITLE-069'),
                   lambda r:r['implementation']['current_code_sha256'].clear(),
                   lambda r:r['variant_review'].update(google_equivalence_verified=True),
                   lambda r:r.update(valid_until='2026-12-12')]
        for change in changes:
            review = deepcopy(self.material['review']); change(review)
            review['subject_sha256'] = o.review_subject(review, self.material)
            with self.assertRaises(ValueError):
                o.validate_review(review, self.material, self.when)
        with self.assertRaises(ValueError):
            o.validate_review(self.material['review'], self.material, date(2027, 1, 1))

    def test_held_semantic_and_compatibility_literals_remain_unmodified(self):
        for identity in ('OFQUAL-TITLE-069', 'OFQUAL-TITLE-070', 'OFQUAL-TITLE-122',
                         'OFQUAL-TITLE-170', 'OFQUAL-TITLE-298', 'OFQUAL-TITLE-299',
                         'OFQUAL-TITLE-033'):
            self.assertIn(identity, self.material['review']['held_groups'])
        base, inputs = self.extended()
        self.assertEqual(len(inputs['protected_queries']), 269)
        self.assertEqual(len(inputs['records']), 42)
        protected = {r['text'] for r in inputs['protected_queries']}
        self.assertTrue(all(self.material['groups'][k]['normalized_title_key'] in protected
                            for k in self.material['review']['held_groups']))

    def test_actual_source_occurrence_fields_preserved(self):
        _, inputs = self.extended()
        for record in inputs['records']:
            self.assertEqual((record['match_type'], record['risk_level'], record['approval_state']),
                             ('EXACT', 'HIGH', 'PENDING'))
            self.assertIsNone(record['observed_query'])
            for occurrence in record['provenance_occurrences']:
                source = self.material['rows'][occurrence['source_record_ordinal']]
                self.assertEqual(occurrence['values'], source['values'])
                self.assertEqual(len(occurrence['values']), 10)
                self.assertEqual(occurrence['qualification_number'], source['values']['Qualification Number'])
                self.assertEqual(occurrence['source_line_end'], source['source_line_end'])
                self.assertEqual(occurrence['published_status'], source['values']['Qualification Status'])

    def test_complete_prefix_and_historical_markers_are_immutable(self):
        base, inputs = self.extended(); before = deepcopy(base)
        self.assertEqual(stage.recover_base(inputs, stage_key=o.STAGE_KEY), base)
        self.assertEqual(base, before)
        for mutate in (lambda x:x['synthetic_historical_extra']['preserve'].append('changed'),
                       lambda x:x[o.STAGE_KEY].update(retained_records=True),
                       lambda x:x.update(campaign_context=[])):
            changed = deepcopy(inputs); mutate(changed)
            with self.assertRaises(ValueError):
                stage.recover_base(changed, stage_key=o.STAGE_KEY)

    def test_arbitrary_base_cannot_pass_actual_binding(self):
        with self.assertRaisesRegex(ValueError, 'OFQUAL_PRIOR_BASE_CHANGED'):
            o.verify_base(self.fixture(), self.material)

    def test_domain_tail_mutations_fail_before_saved_output_audit(self):
        base, inputs = self.extended()
        changes = [lambda x:x['records'][0]['provenance_occurrences'][0]['values'].update(
                       {'Qualification Number': 'FORGED'}),
                   lambda x:x['records'][0].update(approval_state='APPROVED'),
                   lambda x:x['protected_queries'].pop(),
                   lambda x:x['sources'][0].update(kind='observed_query')]
        for change in changes:
            changed = deepcopy(inputs); change(changed)
            with patch.object(o, 'load_reviewed', return_value=self.material), \
                 patch.object(o, 'verify_base'), patch.object(o, 'BASE_SHA256', stage.digest(base)):
                with self.assertRaisesRegex(ValueError, 'OFQUAL_DERIVED_BODIES_CHANGED'):
                    o.check_saved(changed, o.first.ROOT, self.when)

    def test_source_and_current_code_tamper_fail_closed(self):
        original = o.first.pinned
        def changed(root, file, pin):
            document = original(root, file, pin)
            if file == o.CAPTURE+'/semantic-review.json':
                document = deepcopy(document)
                document['groups'][0]['source_occurrences'][0]['source_line_end'] += 1
            return document
        with patch.object(o.first, 'pinned', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'OFQUAL_OCCURRENCE_CHANGED'):
                o.load_sources(o.first.ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            for relative in o.CODE_PINS:
                target = Path(temporary)/relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'altered source\n')
            with self.assertRaisesRegex(ValueError, 'OFQUAL_CURRENT_IMPLEMENTATION_CHANGED'):
                o.implementation_binding(temporary)

    def test_output_pins_and_resealed_documents_do_not_grant_authority(self):
        with self.assertRaisesRegex(ValueError, 'APPEND_ONLY_OUTPUT_PINS_UNREGISTERED'):
            stage.check_documents(o.first.ROOT, o.FOLDER, {}, {'index.json': {}})
        with patch.object(stage.first, 'pinned', return_value={'forged': True}):
            with self.assertRaisesRegex(ValueError, 'APPEND_ONLY_SAVED_OUTPUT_CHANGED'):
                stage.check_documents(o.first.ROOT, o.FOLDER, {'index.json': 'a'*64},
                                      {'index.json': {'forged': False}})

    def test_returned_implementation_binding_cannot_mutate_constants(self):
        pins = dict(o.CODE_PINS)
        binding = o.implementation_binding(o.first.ROOT)
        binding['current_code_sha256'].clear()
        self.assertEqual(o.CODE_PINS, pins)
        self.assertEqual(o.implementation_binding(o.first.ROOT)['current_code_sha256'], pins)

    def test_generic_append_rejects_archived_identity_and_protection_collisions(self):
        base = self.fixture(); cohort, protections = o.build_cohort(base, self.material)
        base['archived_records'] = [deepcopy(cohort['records'][0])]
        with self.assertRaisesRegex(ValueError, 'APPEND_ONLY_ARCHIVE_COLLISION'):
            stage.extend(base, cohort, protections, expected_base_sha256=stage.digest(base), stage_key=o.STAGE_KEY)
        base = self.fixture(); base['protected_queries'] = [deepcopy(protections[0])]
        with self.assertRaisesRegex(ValueError, 'APPEND_ONLY_PROTECTION_COLLISION'):
            stage.extend(base, cohort, protections, expected_base_sha256=stage.digest(base), stage_key=o.STAGE_KEY)

    def test_small_actual_domain_cohort_uses_real_generic_auditor(self):
        _, inputs = self.extended()
        result = stage.checked_audit(inputs, self.when)
        self.assertEqual(result['reviewed_eligible_rows'], 42)
        self.assertEqual(len(result['protected_conflicts']), 0)
        changed = deepcopy(inputs)
        changed['records'][0]['original_text'] = changed['protected_queries'][0]['text']
        with self.assertRaises(ValueError):
            stage.checked_audit(changed, self.when)


if __name__ == '__main__':
    unittest.main()
