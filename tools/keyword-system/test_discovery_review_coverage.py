"""Synthetic occurrence reconciliation; no API, credentials or master writes."""
import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from datetime import date,timedelta

from planner_discovery import parse_discovery
from supplemental_discovery import CONTEXT,CONTROLS
from test_planner_discovery import fixture,fixture_row
from test_triage_workbench import document,proposal
import triage_workbench as legacy
from discovery_review_coverage import reconcile
from supplemental_triage import dubai_date


class DiscoveryReviewCoverageTests(unittest.TestCase):
    def capture(self,name,words):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'TEST_ONLY.csv';path.write_bytes(fixture([fixture_row(w) for w in words]))
            data=parse_discovery(path)
        batch={'version':1,'scope':'AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED','batch_id':'TEST_ONLY_'+name,
          'topic':name,'input_seeds':[words[0]],'ui_context':dict(CONTEXT,ui_idea_count=len(words)),
          'source_projection':data,'seed_reconciliation':{'exact_returned':1,'without_separate_exact_row':[]},
          'controls':dict(CONTROLS)}
        raw=json.dumps(batch).encode()
        return {'file':'TEST_ONLY/'+name+'.json','sha256':hashlib.sha256(raw).hexdigest(),
                'captured_on':'2026-11-08','batch':batch}

    def review(self,capture,states=None):
        batch=capture['batch'];entries={}
        for row in batch['source_projection']['records']:
            text=row['values']['Keyword']
            entries.setdefault(text,{'original_forms':[text],'source_refs':[]})['source_refs'].append(
                {'batch':batch['batch_id'],'source_line':row['source_line']})
        corpus={'sources':{batch['batch_id']:{'file':capture['file'],'sha256':capture['sha256']}},'entries':entries}
        doc=document(*[proposal(text,(states or {}).get(text,'HOLD')) for text in entries])
        wb=legacy.compile_workbench(corpus,doc)
        return {'file':'TEST_ONLY/review-'+batch['topic']+'.json','sha256':hashlib.sha256(json.dumps(wb).encode()).hexdigest(),
                'workbench':wb}

    def test_shared_phrases_keep_all_occurrences_and_independent_assessments(self):
        a=self.capture('a',['shared property','other property']);b=self.capture('b',['shared property'])
        rs=[self.review(a),self.review(b)];before=copy.deepcopy(([a,b],rs))
        r=reconcile([a,b],rs)
        self.assertEqual((r['source_occurrences'],r['distinct_source_phrases'],r['review_assessment_instances']),(3,2,3))
        self.assertEqual(r['canonical_disposition_counts']['HOLD'],2)
        self.assertTrue(r['all_phrases_have_preliminary_assessments'])
        self.assertEqual(len(r['cross_review_overlap_phrases']),1)
        self.assertFalse(r['cross_review_overlap_phrases'][0]['classification_or_approval_inherited'])
        self.assertEqual(([a,b],rs),before)
        self.assertFalse(r['admission_authorized']);self.assertFalse(r['deployment_authorized'])

    def test_missing_batch_review_is_incomplete_not_silently_dropped(self):
        a=self.capture('a',['one']);b=self.capture('b',['two'])
        r=reconcile([a,b],[self.review(a)])
        self.assertFalse(r['all_phrases_have_preliminary_assessments'])
        self.assertEqual(r['unreviewed_batches'],['TEST_ONLY_b'])
        self.assertEqual(r['canonical_disposition_counts']['NO_STRUCTURED_REVIEW'],1)

    def test_partial_or_invented_source_references_are_refused(self):
        a=self.capture('a',['one','two'])
        for change in ('omit','unknown','wrong-line','wrong-text','wrong-binding'):
            r=self.review(a);w=r['workbench']
            if change=='omit':w['queue'].pop()
            elif change=='unknown':w['queue'][0]['source_refs'][0]['batch']='TEST_ONLY_UNKNOWN'
            elif change=='wrong-line':w['queue'][0]['source_refs'][0]['source_line']+=999
            elif change=='wrong-text':w['queue'][0]['original_forms']=['invented query']
            else:w['sources']['TEST_ONLY_a']['sha256']='f'*64
            with self.subTest(change=change),self.assertRaises(ValueError):reconcile([a],[r])

    def test_changed_disposition_without_recompilation_is_refused(self):
        a=self.capture('a',['one']);r=self.review(a);r['workbench']['queue'][0]['disposition']='POSITIVE_REVIEW'
        with self.assertRaisesRegex(ValueError,'REVIEW_NOT_REPRODUCIBLE'):reconcile([a],[r])

    def test_reordered_physical_occurrences_cannot_rewrite_source_order(self):
        a=self.capture('a',['one','one']);r=self.review(a)
        r['workbench']['queue'][0]['source_refs'].reverse()
        with self.assertRaisesRegex(ValueError,'REVIEW_SOURCE_OCCURRENCE_MISMATCH'):reconcile([a],[r])

    def test_duplicate_batch_or_review_ownership_is_refused(self):
        a=self.capture('a',['one']);r=self.review(a)
        with self.assertRaises(ValueError):reconcile([a,a],[r])
        s=copy.deepcopy(r);s['file']='TEST_ONLY/second-review.json'
        with self.assertRaises(ValueError):reconcile([a],[r,s])

    def test_counts_and_authority_types_cannot_be_overridden(self):
        a=self.capture('a',['one'])
        for field in ('control','count','boolean-count'):
            r=self.review(a)
            if field=='control':r['workbench']['controls']['approved']=True
            else:r['workbench']['summary']['unique_phrases']=2 if field=='count' else True
            with self.subTest(field=field),self.assertRaises(ValueError):reconcile([a],[r])

    def test_review_dates_bound_capture_and_current_day(self):
        a=self.capture('a',['one'])
        for value in ('2026-11-07',(dubai_date()+timedelta(days=1)).isoformat(),True,'2026-2-3'):
            r=self.review(a);r['workbench']['proposed_on']=value
            with self.subTest(value=value),self.assertRaises((ValueError,TypeError)):reconcile([a],[r])

    def test_cross_source_disagreement_is_retained_and_held(self):
        a=self.capture('a',['shared']);b=self.capture('b',['shared'])
        r=reconcile([a,b],[self.review(a,{'shared':'POSITIVE_REVIEW'}),self.review(b)])
        self.assertEqual(r['canonical_disposition_counts']['DISAGREEMENT_HOLD'],1)
        self.assertFalse(r['cross_review_overlap_phrases'][0]['dispositions_agree'])
        self.assertFalse(r['independent_review_verified'])

    def test_all_holds_receive_conservative_exact_alias_protection(self):
        a=self.capture('a',['cheap-flat','cheap flat'])
        r=reconcile([a],[self.review(a,{'cheap-flat':'NEGATIVE_EXACT_REVIEW'})])
        self.assertEqual(r['provisional_exact_screen']['conflicts'],[{'negative':'cheap-flat','protected_queries':['cheap flat']}])
        self.assertFalse(r['provisional_exact_screen']['actual_scope_verified'])

    def test_authored_tests_never_increase_source_counts(self):
        a=self.capture('a',['one']);r=reconcile([a],[self.review(a)],['authored property query'])
        self.assertEqual(r['distinct_source_phrases'],1)
        self.assertEqual(r['source_occurrences'],1)
        self.assertEqual(r['provisional_exact_screen']['authored_test_cases_excluded_from_source_counts'],1)
        for bad in (['x','X'],[''],[True]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):reconcile([a],[self.review(a)],bad)

    def test_unassessed_rows_are_not_counted_as_complete(self):
        a=self.capture('a',['one']);r=self.review(a)
        r['workbench']=legacy.compile_workbench({'sources':r['workbench']['sources'],
          'entries':{'one':{'original_forms':['one'],'source_refs':[{'batch':'TEST_ONLY_a','source_line':4}]}}},document())
        self.assertFalse(reconcile([a],[r])['all_phrases_have_preliminary_assessments'])

    def test_descriptor_paths_and_hashes_are_bounded(self):
        a=self.capture('a',['one'])
        for field,value in [('file','../outside.json'),('file','/absolute.json'),('file','TEST_ONLY//a.json'),('sha256','not-a-hash')]:
            b=copy.deepcopy(a);b[field]=value
            with self.subTest(value=value),self.assertRaises(ValueError):reconcile([b],[self.review(a)])


if __name__=='__main__':unittest.main()
