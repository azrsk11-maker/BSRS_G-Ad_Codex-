"""Synthetic adapter/protection behavior and pinned public-capture coverage."""
import copy
from datetime import date, timedelta
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
    def test_actual_capture_preserves_every_occurrence(self):
        data = st.load_corpus(Path(__file__).resolve().parents[2])
        built = st.compile_workbench(data, dated())
        self.assertEqual((len(data['sources']), len(data['entries'])), (3, 263))
        self.assertEqual(sum(len(e['source_refs']) for e in data['entries'].values()), 266)
        self.assertEqual(built['summary']['dispositions']['UNASSESSED'], 263)
        self.assertFalse(built['controls']['deployment_authorized'])

    def test_no_arbitrary_capture_path_can_select_code(self):
        with patch.object(st.importlib.util, 'spec_from_file_location') as load, self.assertRaises(TypeError):
            st.load_corpus(Path('.'), capture=Path('../outside'))
        load.assert_not_called()

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
        for day in ('2026-02-30', '2026-1-1', True, '2026-11-08', (date.today() + timedelta(days=1)).isoformat()):
            with self.subTest(day=day), self.assertRaises((ValueError, TypeError)):
                st.compile_workbench(data, doc, proposed_on=day)
        with self.assertRaises(ValueError):
            st.compile_workbench(data, document())

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
