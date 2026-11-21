import copy
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('offplan_review_compiler',OWN/'compile.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


class OffplanReviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data,cls.pins=c.load_inputs()

    def test_actual_cohort_compiles_deterministically_with_exact_pins(self):
        first=c.compile_bundle(self.data,self.pins)
        self.assertEqual(first,c.compile_bundle(self.data,self.pins))
        manifest=json.loads(first['MANIFEST.json'])
        self.assertEqual(len(first),8)
        self.assertNotIn('MANIFEST.json',manifest['outputs'])
        self.assertEqual(manifest['counts']['proposed_match_placements'],92)
        for name,pin in manifest['outputs'].items():self.assertEqual(c.pin(first[name]),pin)

    def test_actual_native_pages_are_drafts_without_live_ids_or_external_sites(self):
        output=c.compile_bundle(self.data,self.pins)
        pages=json.loads(output['native-pages.json'])
        self.assertEqual(pages['site_origin'],c.ORIGIN)
        for page in pages['pages']:
            self.assertEqual((page['requested_status'],page['created'],page['published']),('draft',False,False))
            self.assertIsNone(page['actual_cms_id']);self.assertIsNone(page['actual_live_url'])
            body=output[page['content_file']].decode()
            self.assertIn('href="/enquire/off-plan/"',body)
            self.assertIn('lang="'+page['locale']+'"',body)
            self.assertNotIn('<script',body);self.assertNotIn('<form',body)
            self.assertFalse(page['localized_form_installed'])

    def test_actual_csv_has_92_placements_without_canonical_or_performance_claims(self):
        output=c.compile_bundle(self.data,self.pins)
        rows=list(csv.DictReader(io.StringIO(output['keyword-review.csv'].decode())))
        self.assertEqual(len(rows),92)
        self.assertEqual({r['Proposed match type'] for r in rows},{'EXACT','PHRASE'})
        self.assertEqual({r['State'] for r in rows},{'AUTHORED_DRAFT_NOT_ADMITTED_OR_UPLOADED'})
        self.assertEqual(len(list(csv.DictReader(io.StringIO(output['rsa-review.csv'].decode())))),57)

    def test_chinese_double_width_boundary_and_latin_accents(self):
        self.assertEqual(c.units('杜'*15),30)
        self.assertEqual(c.units('杜'*16),32)
        self.assertEqual(c.units('àéö'),3)
        data=copy.deepcopy(self.data)
        data['copy.json']['pages'][0]['rsa']['headlines'][0]='杜'*16
        with self.assertRaisesRegex(ValueError,'weighted length'):c.validate(data)

    def test_over_budget_or_unapproved_aggregate_rejects(self):
        for change in ['sum','aggregate','boolean']:
            data=copy.deepcopy(self.data)
            if change=='sum':data['launch.json']['markets'][0]['daily_average_budget_aed']+=1
            elif change=='aggregate':data['launch.json']['aggregate_average_daily_budget_aed']=2501
            else:data['launch.json']['markets'][0]['daily_average_budget_aed']=True
            with self.subTest(change=change),self.assertRaises(ValueError):c.validate(data)

    def test_russia_or_wrong_country_language_is_not_silently_activated(self):
        data=copy.deepcopy(self.data);data['launch.json']['markets'][1]['country_code']='RU'
        with self.assertRaisesRegex(ValueError,'country set'):c.validate(data)
        data=copy.deepcopy(self.data);data['launch.json']['markets'][3]['language_criterion_id']=1017
        with self.assertRaisesRegex(ValueError,'language criterion'):c.validate(data)

    def test_retained_real_estate_ids_and_resale_pause_are_required(self):
        for field in ['campaign_id','offplan_ad_group_id','ad_id']:
            data=copy.deepcopy(self.data);data['launch.json']['markets'][0][field]='999'
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'retained UAE identities'):c.validate(data)
        data=copy.deepcopy(self.data);data['launch.json']['resale_ad_group_keep_paused']=None
        with self.assertRaisesRegex(ValueError,'Resale exclusion'):c.validate(data)

    def test_new_live_ids_or_ready_status_cannot_be_fabricated(self):
        for field,value in [('campaign_id','123'),('actual_cms_page_id',123),('geographic_criterion_id',123),('initial_status','ENABLED')]:
            data=copy.deepcopy(self.data);data['launch.json']['markets'][1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):c.validate(data)

    def test_legacy_network_and_secondary_action_policies_are_preserved(self):
        for field in ['search_partners','display_expansion','ai_max']:
            data=copy.deepcopy(self.data);data['launch.json']['markets'][1][field]=True
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Network expansion'):c.validate(data)
        data=copy.deepcopy(self.data);data['launch.json']['accepted_conversion_policy']['optimization']='PRIMARY'
        with self.assertRaisesRegex(ValueError,'Accepted-action policy'):c.validate(data)

    def test_geographic_interest_and_uncovered_contact_hours_reject(self):
        for field,value in [('location_option','PRESENCE_OR_INTEREST'),('schedule','00:00-24:00 daily'),('schedule_timezone','Europe/Berlin')]:
            data=copy.deepcopy(self.data);data['launch.json']['markets'][1][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):c.validate(data)

    def test_duplicate_headline_and_description_assets_reject(self):
        for field in ['headlines','descriptions']:
            data=copy.deepcopy(self.data)
            data['copy.json']['pages'][0]['rsa'][field][1]=data['copy.json']['pages'][0]['rsa'][field][0].swapcase()
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Duplicate RSA'):c.validate(data)

    def test_duplicate_or_falsely_admitted_localized_keywords_reject(self):
        data=copy.deepcopy(self.data);data['keywords.json']['positive_candidates'][1]['text']=data['keywords.json']['positive_candidates'][0]['text'].upper()
        with self.assertRaisesRegex(ValueError,'Duplicate localized'):c.validate(data)
        data=copy.deepcopy(self.data);data['keywords.json']['positive_candidates'][0]['admitted']=True
        with self.assertRaisesRegex(ValueError,'Invented keyword'):c.validate(data)

    def test_formula_control_char_and_unreviewed_match_expansion_reject(self):
        for text in ['=HYPERLINK("bad")','offplan\nDubai','offplan\u202eDubai']:
            data=copy.deepcopy(self.data);data['keywords.json']['positive_candidates'][0]['text']=text
            with self.subTest(text=text),self.assertRaises(ValueError):c.validate(data)
        data=copy.deepcopy(self.data);data['keywords.json']['positive_candidates'][0]['match_types']=['BROAD']
        with self.assertRaisesRegex(ValueError,'match expansion'):c.validate(data)

    def test_customer_text_is_escaped_and_review_metadata_is_not_rendered(self):
        page=copy.deepcopy(self.data['copy.json']['pages'][0]);page['intro']=['<script>alert("x")</script>']
        body=c.render_page(page).decode()
        self.assertNotIn('<script>',body);self.assertIn('&lt;script&gt;',body)
        data=copy.deepcopy(self.data);data['copy.json']['pages'][0]['private_review_notes']='secret'
        with self.assertRaisesRegex(ValueError,'Unexpected customer page'):c.validate(data)

    def test_enquiry_route_and_slug_cannot_escape_the_existing_site(self):
        data=copy.deepcopy(self.data);data['launch.json']['english_funnel_path']='https://example.invalid/form'
        with self.assertRaisesRegex(ValueError,'enquiry route'):c.validate(data)
        data=copy.deepcopy(self.data);data['launch.json']['markets'][1]['proposed_slug']='../enquire'
        with self.assertRaisesRegex(ValueError,'Unsafe proposed slug'):c.validate(data)

    def test_duplicate_native_slug_or_campaign_name_cannot_overwrite_a_market(self):
        for field in ['proposed_slug','campaign_name']:
            data=copy.deepcopy(self.data)
            data['launch.json']['markets'][2][field]=data['launch.json']['markets'][1][field]
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'Duplicate'):c.validate(data)

    def test_loader_rejects_duplicate_keys_and_overflow_before_use(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            for name in c.INPUTS:(p/name).write_bytes((OWN/name).read_bytes())
            for bad in [b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e400}']:
                (p/'launch.json').write_bytes(bad)
                with self.subTest(bad=bad),self.assertRaises(ValueError):c.load_inputs(p)


if __name__=='__main__':unittest.main()
