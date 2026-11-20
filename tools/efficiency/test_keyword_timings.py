from copy import deepcopy
import json
import unittest

import keyword_timings as timing


def fixture():
    def row(name,seconds,count):
        return {'module':name,'elapsed_seconds':seconds,'exit':0,'complete':True,
            'coverage_verified':True,'passed':True,'expected':count,'started':count,
            'finished':count,'skipped':0,'output_tail':'synthetic-private-text',
            'source_path':'synthetic/private/path','events':['synthetic-case-id']}
    return {'summary':{'discovered_modules':2,'completed_modules':2,'discovered':3,
        'started':3,'finished':3,'skipped':0,'passed':True,'coverage_verified':True,'timed_out':False},
        'modules':[row('test_fast',0.2,1),row('test_slow',2.75,2)],
        'private_extra':'synthetic-contact@example.invalid'}


class KeywordTimingTests(unittest.TestCase):
    def assert_withheld(self,value):
        self.assertEqual(timing.project(value),timing.withheld())

    def test_complete_projection_is_small_whitelisted_and_slowest_first(self):
        original=fixture();before=deepcopy(original);value=timing.project(original)
        self.assertEqual(value['status'],'OBSERVED')
        self.assertEqual(value['module_count'],2);self.assertEqual(value['tests'],3)
        self.assertEqual(value['modules'],[
            {'module':'test_slow','elapsed_seconds':2.75,'tests':2,'skipped':0},
            {'module':'test_fast','elapsed_seconds':0.2,'tests':1,'skipped':0}])
        self.assertFalse(value['release_authorized']);self.assertEqual(original,before)
        text=json.dumps(value)
        for secret in ('synthetic-private-text','synthetic/private/path','synthetic-case-id','example.invalid'):
            self.assertNotIn(secret,text)

    def test_missing_failed_incomplete_or_timed_out_report_is_withheld(self):
        for change in (lambda r:r.pop('modules'),lambda r:r['modules'][0].update(exit=1),
            lambda r:r['modules'][0].update(complete=False),
            lambda r:r['modules'][0].update(coverage_verified=False),
            lambda r:r['summary'].update(timed_out=True),lambda r:r['summary'].update(passed=False)):
            value=fixture();change(value);self.assert_withheld(value)

    def test_elapsed_is_finite_nonnegative_and_inside_existing_bound(self):
        for number in (True,-1,300.000001,float('nan'),float('inf'),'2',None):
            with self.subTest(number=number):
                value=fixture();value['modules'][0]['elapsed_seconds']=number;self.assert_withheld(value)

    def test_boolean_or_noninteger_counters_cannot_replace_evidence(self):
        for field in ('expected','started','finished','skipped','exit'):
            value=fixture();value['modules'][0][field]=False;self.assert_withheld(value)
        value=fixture();value['summary']['finished']=True;self.assert_withheld(value)

    def test_module_names_cannot_publish_paths_or_private_text(self):
        for name in ('../test_secret','test_private@example.invalid','test bad','test_x\nsecret',None):
            value=fixture();value['modules'][0]['module']=name;self.assert_withheld(value)

    def test_duplicate_missing_and_mismatched_module_populations_are_withheld(self):
        for change in (lambda r:r['modules'][1].update(module='test_fast'),
            lambda r:r['modules'].pop(),lambda r:r['summary'].update(completed_modules=1),
            lambda r:r['modules'][0].update(expected=2),lambda r:r['summary'].update(finished=4),
            lambda r:r['summary'].update(skipped=1)):
            value=fixture();change(value);self.assert_withheld(value)

    def test_ties_are_deterministic_without_rounding_or_mutation(self):
        value=fixture();value['modules'][0]['elapsed_seconds']=2.75
        self.assertEqual([r['module'] for r in timing.project(value)['modules']],['test_fast','test_slow'])
        value['modules'].reverse()
        self.assertEqual([r['module'] for r in timing.project(value)['modules']],['test_fast','test_slow'])

    def test_skips_are_reported_without_becoming_tests_or_release_approval(self):
        value=fixture();value['modules'][0]['skipped']=1;value['summary']['skipped']=1
        result=timing.project(value);self.assertEqual((result['tests'],result['skipped']),(3,1))
        self.assertFalse(result['release_authorized'])


if __name__=='__main__':unittest.main()
