"""Synthetic regression boundaries for reused immutable lexical preprocessing."""
import unittest
import keyword_audit as ka


class LexicalPreprocessingTests(unittest.TestCase):
    def setUp(self):
        ka._cached_lexical_form.cache_clear()

    def tearDown(self):
        ka._cached_lexical_form.cache_clear()

    def test_unicode_wrappers_punctuation_and_close_variants_keep_existing_results(self):
        cases=[
            ('[OFFICE RENT]','EXACT','office-rent',True),
            ('"villa pool"','PHRASE','large villa, pool and garden',True),
            ('rent office','PHRASE','office for rent',False),
            ('office rent','BROAD','rent an office',True),
            ('office','EXACT','offices',False),
            ('Straße','EXACT','STRASSE',True),
            ('ｖｉｌｌａ','EXACT','villa',True),
            ('شقة للإيجار','PHRASE','ابحث شقة للإيجار دبي',True),
            ('fäm properties','EXACT','fam properties',False),
            ('a_b','EXACT','a b',False),
            ('villa villa','EXACT','villa',False),
            ('villa villa','PHRASE','large villa',False),
            ('villa villa','BROAD','villa',True),
            ('!!!','EXACT','villa',False),
        ]
        for repeat in range(2):
            for negative,kind,query,expected in cases:
                with self.subTest(repeat=repeat,negative=negative,kind=kind,query=query):
                    self.assertIs(ka.negative_matches(negative,kind,query),expected)

    def test_mutable_public_tokens_do_not_change_later_matches(self):
        self.assertTrue(ka.negative_matches('villa pool','EXACT','villa pool'))
        public=ka.tokens('villa pool');public[:]=['office']
        self.assertTrue(ka.negative_matches('villa pool','EXACT','villa pool'))
        self.assertFalse(ka.negative_matches('villa pool','EXACT','office'))
        self.assertEqual(ka.tokens('villa pool'),['villa','pool'])

    def test_invalid_unhashable_inputs_keep_keyword_validation_errors(self):
        for value in (None,[],{},123):
            for left,right in ((value,'villa'),('villa',value)):
                with self.subTest(left=left,right=right):
                    with self.assertRaisesRegex(ValueError,'Keyword text must be a string'):
                        ka.negative_matches(left,'EXACT',right)

    def test_unhashable_string_subclass_still_works_without_cache(self):
        class UnhashableText(str):
            __hash__=None
        self.assertTrue(ka.negative_matches(UnhashableText('Villa'),'EXACT','villa'))
        self.assertTrue(ka.negative_matches('villa','PHRASE',UnhashableText('large villa')))

    def test_oversized_inputs_keep_semantics_without_entering_bounded_cache(self):
        text='villa '*200
        self.assertGreater(len(text),512)
        for kind in ('EXACT','PHRASE','BROAD'):
            self.assertTrue(ka.negative_matches(text,kind,text))
        self.assertEqual(ka._cached_lexical_form.cache_info().currsize,0)

    def test_eviction_and_empty_invalid_match_cases_keep_results(self):
        for i in range(4100):
            self.assertTrue(ka.negative_matches('synthetic '+str(i),'EXACT','synthetic '+str(i)))
        self.assertLessEqual(ka._cached_lexical_form.cache_info().currsize,4096)
        self.assertTrue(ka.negative_matches('synthetic 0','EXACT','synthetic 0'))
        self.assertFalse(ka.negative_matches('!!!','UNSUPPORTED','villa'))
        with self.assertRaisesRegex(ValueError,'Unsupported negative match type'):
            ka.negative_matches('villa','UNSUPPORTED','villa')


if __name__=='__main__':
    unittest.main()
