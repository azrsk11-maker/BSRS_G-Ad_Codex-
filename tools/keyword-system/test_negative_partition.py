"""Synthetic ID partition integrity, authority and input isolation checks."""
import copy
import unittest
from datetime import date
from unittest.mock import patch

from negative_partition import build_index
import negative_library as library


def fixture():
    rows = [{'keyword_id': 'SYNTHETIC-N-'+str(n), 'original_text': 'synthetic phrase '+str(n)} for n in range(3)]
    conflict = {'negative_id':'SYNTHETIC-N-1','protected_query_id':'SYNTHETIC-Q-1',
                'affected_campaign_keys':['SYNTHETIC-C-1'],'result':'CONFLICT_HOLD'}
    impact = {'historical_input_rows':3,'latest_review_eligible_rows':2,'latest_excluded_rows':1,
              'latest_deficit':13998,'approved_exclusion_rows':0,'master_additions':0,
              'protected_conflicts':[conflict],'admission_held':True,
              'historical_rows_rewritten':False,'deployment_authorized':False,
              'historical_master_sha256':'a'*64,'latest_coverage_sha256':'b'*64}
    refs = {'historical_master':{'file':'data/SYNTHETIC-master.json','sha256':'a'*64},
            'latest_report':{'file':'docs/audit/SYNTHETIC-report.json','sha256':'b'*64},
            'latest_impact':{'file':'docs/audit/SYNTHETIC-impact.json','sha256':'c'*64}}
    return rows, impact, refs


class NegativePartitionTests(unittest.TestCase):
    def test_current_materializer_detaches_mutable_data_from_verified_history(self):
        rows, impact, refs = fixture()
        index = build_index(rows, impact, **refs)
        inputs = {'records':rows,'sources':[{'source_id':'SYNTHETIC-S'}],
                  'campaigns':[],'campaign_context':[],'protected_queries':[{'text':'old'}]}
        screen = {'protected_queries':[{'text':'current protected'}], 'impact':impact}
        before = copy.deepcopy((inputs, screen, index))
        with patch.object(library, 'current_state', return_value=(inputs, {}, screen, index)):
            result = library.reconstruct_current(at=date(2026, 11, 11))
        self.assertEqual([r['keyword_id'] for r in result['records']], ['SYNTHETIC-N-0','SYNTHETIC-N-2'])
        self.assertEqual([r['keyword_id'] for r in result['archived_records']], ['SYNTHETIC-N-1'])
        self.assertEqual(result['protected_queries'], screen['protected_queries'])
        result['records'][0]['original_text'] = 'changed'
        result['archived_records'][0]['original_text'] = 'changed held'
        result['sources'][0]['source_id'] = 'changed source'
        result['protected_queries'][0]['text'] = 'changed protection'
        result['research_index']['eligible_keyword_ids'].clear()
        self.assertEqual((inputs, screen, index), before)

    def test_every_id_is_partitioned_once_in_original_order_without_record_copies(self):
        rows, impact, refs = fixture()
        before = copy.deepcopy((rows, impact, refs))
        result = build_index(rows, impact, **refs)
        self.assertEqual(result['eligible_keyword_ids'], ['SYNTHETIC-N-0','SYNTHETIC-N-2'])
        self.assertEqual(result['held_keyword_ids'], ['SYNTHETIC-N-1'])
        self.assertEqual(result['counts'], {'historical':3,'eligible':2,'held':1})
        self.assertNotIn('records', result)
        self.assertEqual((rows, impact, refs), before)
        rows[0]['keyword_id'] = 'changed'
        refs['historical_master']['file'] = 'changed'
        impact['protected_conflicts'].clear()
        self.assertEqual(result['eligible_keyword_ids'][0], 'SYNTHETIC-N-0')
        self.assertEqual(result['historical_master']['file'], 'data/SYNTHETIC-master.json')
        self.assertFalse(result['controls']['deployment_authorized'])

    def test_multiple_valid_conflicts_hold_one_record_not_multiple_rows(self):
        rows, impact, refs = fixture()
        other = copy.deepcopy(impact['protected_conflicts'][0])
        other['protected_query_id'] = 'SYNTHETIC-Q-2'
        impact['protected_conflicts'].append(other)
        self.assertEqual(build_index(rows, impact, **refs)['counts']['held'], 1)
        impact['protected_conflicts'].append(copy.deepcopy(other))
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_CONFLICT'):
            build_index(rows, impact, **refs)

    def test_unknown_conflicts_duplicate_ids_and_normalized_phrases_fail_closed(self):
        for change in ('unknown','duplicate-id','duplicate-text','missing-conflict'):
            rows, impact, refs = fixture()
            if change == 'unknown':impact['protected_conflicts'][0]['negative_id'] = 'not-present'
            elif change == 'duplicate-id':rows[2]['keyword_id'] = rows[0]['keyword_id']
            elif change == 'duplicate-text':rows[2]['original_text'] = '[SYNTHETIC PHRASE 0]'
            else:impact['protected_conflicts'].clear()
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_index(rows, impact, **refs)

    def test_unexplained_counts_boolean_counts_authority_and_bad_scopes_fail_closed(self):
        for change in ('count','bool','approved','deployed','rewritten','scope','state'):
            rows, impact, refs = fixture()
            if change == 'count':impact['latest_review_eligible_rows'] = 3
            elif change == 'bool':impact['latest_excluded_rows'] = True
            elif change == 'approved':impact['approved_exclusion_rows'] = 1
            elif change == 'deployed':impact['deployment_authorized'] = True
            elif change == 'rewritten':impact['historical_rows_rewritten'] = True
            elif change == 'scope':impact['protected_conflicts'][0]['affected_campaign_keys'] = []
            else:impact['admission_held'] = False
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_index(rows, impact, **refs)

    def test_hash_mismatches_private_paths_and_traversal_do_not_become_provenance(self):
        for change in ('master','report','traversal','absolute','drive','nul'):
            rows, impact, refs = fixture()
            if change == 'master':refs['historical_master']['sha256'] = 'd'*64
            elif change == 'report':refs['latest_report']['sha256'] = 'd'*64
            else:refs['latest_impact']['file'] = {'traversal':'../outside.json','absolute':'/outside.json',
                'drive':'C:/private.json','nul':'data/bad\x00.json'}[change]
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_index(rows, impact, **refs)


if __name__ == '__main__':
    unittest.main()
