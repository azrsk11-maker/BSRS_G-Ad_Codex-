"""Synthetic adapter/protection behavior and pinned public-capture coverage."""
import copy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import unittest
from unittest.mock import patch
import supplemental_triage as st
import triage_workbench as legacy
from test_triage_workbench import corpus, document, proposal


def dated(*rows):
    result = document(*rows)
    result['proposed_on'] = st.DAY
    return result


class SupplementalTriageTests(unittest.TestCase):
    def test_role_exam_asset_capture_preserves_four_batches_without_quarantine(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2], capture=st.ROLE_EXAM_ASSET_CAPTURE)
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (4, 1717))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 1717)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 1717)
        self.assertIn('questions to ask brokerage', data['entries'])
        self.assertIn('real estate quiz for clients', data['entries'])
        self.assertNotIn('tiles fixing company in dubai', data['entries'])
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_actual_capture_preserves_every_occurrence(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2])
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (3, 263))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 266)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 263)
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_no_arbitrary_capture_path_can_select_code(self):
        for capture in (Path('../outside'), Path('docs/audit/unknown'), str(st.CAPTURE), []):
            with self.subTest(capture=repr(capture)), \
                 patch.object(st.importlib.util, 'spec_from_file_location') as load, self.assertRaises(ValueError):
                st.load_corpus(Path('.'), capture=capture)
            load.assert_not_called()

    def test_gap_capture_preserves_three_batches_without_topic_intent_inheritance(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2], capture=st.GAP_RESEARCH_CAPTURE)
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (3, 3084))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 3084)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 3084)
        self.assertTrue(all(row['assessment'] is None for row in built['queue']))
        for phrase in ('property vacancies', 'hiring a property manager',
                       'pest control company for sale in dubai', 'real estate game assets'):
            self.assertIn(phrase, data['entries'])
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_employment_capture_is_explicit_and_preserves_all_136_rows(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2], capture=st.EMPLOYMENT_CAPTURE)
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (1, 136))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 136)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 136)
        self.assertTrue(all(s['file'].startswith(st.EMPLOYMENT_CAPTURE.as_posix() + '/')
                            for s in data['sources'].values()))
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_actual_date_and_inputs_survive_projection_without_global_mutation(self):
        data, doc = corpus(), dated(proposal('hotel apartment', 'HOLD', ['hotel']))
        before = copy.deepcopy((data, doc))
        original_day = legacy.DAY
        built = st.compile_workbench(data, doc)
        self.assertEqual((built['proposed_on'], doc['proposed_on']), (st.DAY, st.DAY))
        self.assertEqual((data, doc), before)
        self.assertEqual(legacy.DAY, original_day)
        baseline = legacy.compile_workbench(data, document(proposal('hotel apartment', 'HOLD', ['hotel'])))
        baseline['proposed_on'] = st.DAY
        self.assertEqual(built, baseline)
        for day in ('2026-02-30', '2026-1-1', True, '2026-11-08', (st.dubai_date() + timedelta(days=1)).isoformat()):
            with self.subTest(day=day), self.assertRaises((ValueError, TypeError)):
                st.compile_workbench(data, doc, proposed_on=day)
        with self.assertRaises(ValueError):
            st.compile_workbench(data, document())

    def test_four_pool_capture_retains_all_rows_and_never_inherits_intent(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2], capture=st.EXCLUSION_CAPTURE)
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (1, 2343))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 2343)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 2343)
        self.assertTrue(all(s['file'].startswith(st.EXCLUSION_CAPTURE.as_posix() + '/')
                            for s in data['sources'].values()))
        self.assertTrue(all(r['assessment'] is None for r in built['queue']))
        self.assertIn('long term lease dubai', data['entries'])
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_supply_capture_retains_all_31_rows_without_narrative_or_role_inheritance(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2], capture=st.SUPPLY_CAPTURE)
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (2, 31))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 31)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 31)
        self.assertTrue(all(r['assessment'] is None for r in built['queue']))
        self.assertIn('dubai letting agents', data['entries'])
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_dubai_review_day_crosses_midnight_at_20_utc(self):
        self.assertEqual(st.dubai_date(datetime(2026,11,10,19,59,59,tzinfo=timezone.utc)),date(2026,11,10))
        self.assertEqual(st.dubai_date(datetime(2026,11,10,20,0,tzinfo=timezone.utc)),date(2026,11,11))
        self.assertEqual(st.dubai_date(datetime(2026,11,11,tzinfo=timezone(timedelta(hours=4)))),date(2026,11,11))
        with self.assertRaises(ValueError):st.dubai_date(datetime(2026,11,11))

    def test_valid_dubai_day_is_preserved_while_the_next_business_day_is_refused(self):
        doc=dated();doc['proposed_on']='2026-11-11'
        with patch.object(st,'dubai_date',return_value=date(2026,11,11)):
            self.assertEqual(st.compile_workbench(corpus(),doc,proposed_on='2026-11-11')['proposed_on'],'2026-11-11')
        with patch.object(st,'dubai_date',return_value=date(2026,11,10)),self.assertRaises(ValueError):
            st.compile_workbench(corpus(),doc,proposed_on='2026-11-11')

    def test_token_alias_collision_and_internal_protection_are_retained(self):
        data = corpus()
        doc = dated(proposal('cheap-flat', 'NEGATIVE_EXACT_REVIEW'), proposal('hotel apartment', 'HOLD', ['hotel']))
        before = copy.deepcopy((data, doc))
        result = st.compile_protection_review(data, doc, ['cheap flat', 'office near school'], ['cheap', 'school', 'hotel'])
        screen = result['screen']
        self.assertEqual(screen['exact_conflict_count'], 1)
        self.assertEqual(screen['exact_negative_tests'][0]['lexical_conflicts'], ['cheap flat'])
        self.assertEqual(screen['unsafe_generic_tests'][1]['lexical_conflicts'], ['office near school'])
        self.assertEqual(screen['unsafe_generic_tests'][2]['lexical_conflicts'], ['hotel apartment'])
        self.assertFalse(screen['scope_verified'])
        self.assertFalse(screen['positive_library_coverage_verified'])
        self.assertFalse(screen['deployment_authorized'])
        self.assertEqual((data, doc), before)

    def test_bad_review_inputs_and_invented_authority_are_refused(self):
        for queries, terms in (([''], []), (['same', 'SAME'], []), ([], ['x'] * 33), ([], 'school')):
            with self.subTest(queries=queries, terms=terms), self.assertRaises(ValueError):
                st.compile_protection_review(corpus(), dated(), queries, terms)
        forged = dated(proposal('cheap flat', 'NEGATIVE_EXACT_REVIEW'))
        forged['proposals'][0]['negative_scope_proposal']['approved'] = True
        with self.assertRaises(ValueError):
            st.compile_protection_review(corpus(), forged, [], [])


if __name__ == '__main__':
    unittest.main()
