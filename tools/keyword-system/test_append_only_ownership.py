"""Synthetic historical ownership, aliases and fresh mutation boundaries."""
from copy import deepcopy
import unittest

import append_only_admission as stage


class AppendOnlyOwnershipTests(unittest.TestCase):
    def fixture(self):
        record={'keyword_id':'SYNTHETIC-OLD','original_text':'synthetic old phrase','nested':{'v':[1,2]}}
        archive={'keyword_id':'SYNTHETIC-ARCHIVE','original_text':'synthetic archive phrase'}
        marker={'nested':[{'v':3}]}
        base={'records':[record],'archived_records':[archive],
              'protected_queries':[{'query_id':'SYNTHETIC-Q','text':'synthetic protected phrase'}],
              'sources':[{'source_id':'SYNTHETIC-S'}],
              'campaigns':[{'campaign_key':'SYNTHETIC-C'}],
              'campaign_context':[{'campaign_key':'SYNTHETIC-C'}],
              'historical_marker':marker,'same_marker':marker,'archive_alias':archive,
              'original_record_alias':record,'prior_stage_state':{'retained_records':0}}
        cohort={'records':[{'keyword_id':'SYNTHETIC-NEW','original_text':'synthetic new phrase'}],
                'sources':[{'source_id':'SYNTHETIC-NEW-S'}],'protected_queries':[],
                'campaigns':base['campaigns'],'campaign_context':base['campaign_context']}
        protection={'query_id':'SYNTHETIC-NEW-Q','text':'synthetic held phrase'}
        return base,cohort,[protection]

    def extend(self,base,cohort,protections):
        return stage.extend(base,cohort,protections,expected_base_sha256=stage.digest(base),stage_key='synthetic_stage')

    def test_full_history_and_extra_fields_recover_without_input_mutation(self):
        base,cohort,protections=self.fixture();before=deepcopy((base,cohort,protections))
        result=self.extend(base,cohort,protections)
        self.assertEqual(stage.recover_base(result,stage_key='synthetic_stage'),base)
        self.assertEqual((base,cohort,protections),before)
        self.assertEqual(result['records'],base['records']+cohort['records'])
        self.assertEqual(result['protected_queries'],base['protected_queries']+protections)

    def test_retained_markers_preserve_mutual_aliases_and_are_owned_copies(self):
        base,cohort,protections=self.fixture();result=self.extend(base,cohort,protections)
        self.assertIs(result['historical_marker'],result['same_marker'])
        self.assertIsNot(result['historical_marker'],base['historical_marker'])
        result['historical_marker']['nested'][0]['v']=9
        self.assertEqual(base['historical_marker']['nested'][0]['v'],3)

    def test_archive_alias_survives_and_archive_is_independent(self):
        base,cohort,protections=self.fixture();result=self.extend(base,cohort,protections)
        self.assertIs(result['archive_alias'],result['archived_records'][0])
        self.assertIsNot(result['archived_records'][0],base['archived_records'][0])
        result['archive_alias']['original_text']='synthetic changed archive'
        self.assertEqual(base['archived_records'][0]['original_text'],'synthetic archive phrase')
        with self.assertRaisesRegex(ValueError,'APPEND_ONLY_PREFIX_CHANGED'):
            stage.recover_base(result,stage_key='synthetic_stage')

    def test_composed_row_and_registry_reference_behavior_is_preserved(self):
        base,cohort,protections=self.fixture();result=self.extend(base,cohort,protections)
        self.assertIs(result['records'][0],base['records'][0])
        self.assertIs(result['records'][1],cohort['records'][0])
        self.assertIs(result['campaigns'],base['campaigns'])
        self.assertIsNot(result['original_record_alias'],result['records'][0])
        self.assertEqual(result['original_record_alias'],base['records'][0])

    def test_protection_copy_is_independent_of_both_inputs(self):
        base,cohort,protections=self.fixture();result=self.extend(base,cohort,protections)
        self.assertIsNot(result['protected_queries'][0],base['protected_queries'][0])
        self.assertIsNot(result['protected_queries'][-1],protections[0])
        result['protected_queries'][-1]['text']='synthetic changed protection'
        self.assertEqual(protections[0]['text'],'synthetic held phrase')

    def test_fresh_digest_and_collision_checks_still_fail(self):
        base,cohort,protections=self.fixture();expected=stage.digest(base)
        base['historical_marker']['nested'].append('synthetic mutation')
        with self.assertRaisesRegex(ValueError,'APPEND_ONLY_BASE_CHANGED'):
            stage.extend(base,cohort,protections,expected_base_sha256=expected,stage_key='synthetic_stage')
        base,cohort,protections=self.fixture();protections[0]['query_id']=base['protected_queries'][0]['query_id']
        with self.assertRaisesRegex(ValueError,'APPEND_ONLY_PROTECTION_COLLISION'):
            self.extend(base,cohort,protections)


if __name__=='__main__':
    unittest.main()
