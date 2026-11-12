"""Synthetic boundaries for pure preprocessing; no admission result is cached."""
import copy
from datetime import date, timedelta
import unittest
from unittest.mock import patch

import keyword_audit as ka
from test_keyword_audit import audit, negative, CAMPAIGNS, PROTECTED, SOURCES


class AuditPreprocessingTests(unittest.TestCase):
    def setUp(self):
        ka._cached_iso_day.cache_clear()
        ka._cached_lexical_form.cache_clear()

    def tearDown(self):
        ka._cached_iso_day.cache_clear()
        ka._cached_lexical_form.cache_clear()

    def test_complete_reports_equal_with_uncached_date_and_lexical_parsing(self):
        for text, match in [('broker exam course', 'EXACT'),
                            ('apartment rental near school', 'EXACT'),
                            ('rental school', 'BROAD'), ('rental near', 'PHRASE'),
                            ('[ＦＵＬＬ　ＷＩＤＴＨ]', 'EXACT'), ('!!!', 'EXACT'),
                            ('', 'EXACT')]:
            row = negative()
            row.update(original_text=text, normalized_text=ka.normalize(text), match_type=match)
            with self.subTest(text=text, match=match):
                actual = audit('negative', [row])
                with patch.object(ka, '_cached_iso_day', side_effect=ka._parse_iso_day), \
                     patch.object(ka, '_lexical_form', side_effect=lambda text:
                                  (tuple(ka.tokens(text)), frozenset(ka.tokens(text)))):
                    expected = audit('negative', [row])
                self.assertEqual(actual, expected)

    def test_query_and_row_tokenize_once_when_no_lexical_comparison_is_needed(self):
        row = negative()
        with patch.object(ka, 'tokens', wraps=ka.tokens) as tokenize:
            result = audit('negative', [row])
        self.assertEqual(result['lexical_comparisons_executed'], 0)
        self.assertEqual([call.args[0] for call in tokenize.call_args_list],
                         [PROTECTED[0]['text'], row['normalized_text']])

    def test_blank_query_keeps_late_token_validation_and_error_order(self):
        protected = copy.deepcopy(PROTECTED)
        protected[0]['text'] = ' '
        result = audit('negative', [negative()], protected_queries=protected)
        self.assertEqual(result['global_errors'],
                         ['protected queries: text and must_serve=true required QA-Q1'])
        protected[0]['text'] = None
        with patch.object(ka, 'fresh', wraps=ka.fresh) as freshness:
            with self.assertRaisesRegex(ValueError, 'Keyword text must be a string'):
                audit('negative', [negative()], protected_queries=protected)
        self.assertTrue(any(call.args[3] == 'protected query QA-Q1'
                            for call in freshness.call_args_list))

    def test_each_warm_audit_rechecks_freshness_and_does_not_mutate_inputs(self):
        rows = [negative()]
        sources = copy.deepcopy(SOURCES)
        before = copy.deepcopy((rows, sources))
        with patch.object(ka, 'fresh', wraps=ka.fresh) as freshness:
            first = audit('negative', rows, sources=sources)
            calls = freshness.call_count
            second = audit('negative', rows, sources=sources)
        self.assertEqual(first, second)
        self.assertEqual(freshness.call_count, 2*calls)
        self.assertEqual((rows, sources), before)
        first['records'][0]['errors'].append('TEST_ONLY:mutated returned report')
        self.assertNotEqual(first, audit('negative', rows, sources=sources))
        sources[0]['observed_on'] = '2026-11-06'
        changed = audit('negative', rows, sources=sources)
        self.assertEqual(changed['reviewed_eligible_rows'], 0)
        self.assertNotEqual(second, changed)
        expired = audit('negative', rows, at=date(2026, 12, 2))
        self.assertEqual(expired['reviewed_eligible_rows'], 0)
        self.assertNotEqual(second, expired)

    def test_cached_dates_preserve_parse_values_and_errors(self):
        cases = ['2024-02-29', '0001-01-01', '9999-12-31', '2026-02-29',
                 '2026-11-31', '20261101', '2026-1-01', '', 'x'*1000,
                 None, [], {}, 123, date(2026, 11, 1)]
        for value in cases:
            with self.subTest(value=value):
                try:
                    expected = ka._parse_iso_day(value)
                except (TypeError, ValueError) as error:
                    with self.assertRaises(type(error)) as actual:
                        ka.iso_day(value)
                    self.assertEqual(str(actual.exception), str(error))
                else:
                    self.assertEqual(ka.iso_day(value), expected)
                    self.assertIs(type(ka.iso_day(value)), date)

    def test_invalid_dates_are_not_cached(self):
        for _ in range(2):
            with self.assertRaises(ValueError):
                ka.iso_day('2026-02-30')
        info = ka._cached_iso_day.cache_info()
        self.assertEqual((info.hits, info.misses, info.currsize), (0, 2, 0))

    def test_subclasses_and_unhashable_inputs_bypass_date_cache(self):
        class UnhashableText(str):
            __hash__ = None
        self.assertEqual(ka.iso_day(UnhashableText('2026-11-01')), date(2026, 11, 1))
        self.assertEqual(ka.iso_day(type('Text', (str,), {})('2026-11-01')),
                         date(2026, 11, 1))
        for value in [[], {}, 'x'*11]:
            with self.assertRaises(ValueError):
                ka.iso_day(value)
        self.assertEqual(ka._cached_iso_day.cache_info().currsize, 0)
        self.assertEqual(ka._cached_iso_day.cache_info().misses, 0)

    def test_date_cache_remains_bounded_and_eviction_preserves_values(self):
        start = date(2025, 1, 1)
        for offset in range(300):
            value = start + timedelta(days=offset)
            self.assertEqual(ka.iso_day(value.isoformat()), value)
        self.assertEqual(ka._cached_iso_day.cache_info().maxsize, 256)
        self.assertEqual(ka._cached_iso_day.cache_info().currsize, 256)
        self.assertEqual(ka.iso_day(start.isoformat()), start)

    def test_scope_duplicates_unknown_overlap_and_invalid_lists_keep_errors(self):
        duplicate = 'scope lists contain duplicates'
        unknown = 'unknown or overlapping eligible/ineligible campaign scope'
        cases = [(['QA-C1', 'QA-C1'], ['QA-C2'], [duplicate]),
                 (['QA-C1'], ['QA-C2', 'QA-C2'], [duplicate]),
                 (['QA-C1'], ['QA-C1'], [unknown]),
                 (['UNKNOWN'], [], [unknown]),
                 (['UNKNOWN', 'UNKNOWN'], ['UNKNOWN'], [duplicate, unknown]),
                 (None, [], ['eligible_campaigns must be nonempty string list']),
                 (['QA-C1'], {}, ['ineligible_campaigns must be string list']),
                 ([[]], [123], ['eligible_campaigns must be nonempty string list',
                                'ineligible_campaigns must be string list'])]
        scope_errors = {duplicate, unknown, 'eligible_campaigns must be nonempty string list',
                        'ineligible_campaigns must be string list'}
        for eligible, ineligible, expected in cases:
            row = negative()
            row.update(eligible_campaigns=eligible, ineligible_campaigns=ineligible)
            with self.subTest(eligible=eligible, ineligible=ineligible):
                result = audit('negative', [row])
                self.assertEqual([error for error in result['records'][0]['errors']
                                  if error in scope_errors], expected)

    def test_account_and_shared_list_sets_are_fresh_for_changed_scope(self):
        row = negative()
        row.update(scope_type='ACCOUNT', scope_target={'account_id': '573-038-4686'},
                   eligible_campaigns=[campaign['campaign_key'] for campaign in CAMPAIGNS],
                   ineligible_campaigns=[])
        error = 'account scope must explicitly cover every registered campaign without exceptions'
        self.assertNotIn(error, audit('negative', [row])['records'][0]['errors'])
        row['eligible_campaigns'].pop()
        self.assertIn(error, audit('negative', [row])['records'][0]['errors'])
        row = negative()
        row.update(scope_type='SHARED_LIST', scope_target={'list_key': 'QA-LIST'})
        hold = 'shared-list ownership/complete association binding unverified'
        self.assertNotIn(hold, audit('negative', [row])['records'][0]['deployment_holds'])
        row['eligible_campaigns'].append('QA-C2')
        row['ineligible_campaigns'] = []
        self.assertIn(hold, audit('negative', [row])['records'][0]['deployment_holds'])

    def test_known_campaign_set_is_constructed_once_per_audit(self):
        original_index = ka.unique_index
        campaign_indices, constructed = [], []
        def index(rows, field, errors, label):
            result = original_index(rows, field, errors, label)
            if label == 'campaigns':
                campaign_indices.append(result)
            return result
        def counted_set(values=()):
            if any(values is registry for registry in campaign_indices):
                constructed.append(values)
            return set(values)
        counted_set.intersection = set.intersection
        with patch.object(ka, 'unique_index', side_effect=index), \
             patch.object(ka, 'set', counted_set, create=True):
            first = audit('negative', [negative()])
            second = audit('negative', [negative()])
        self.assertEqual(first, second)
        self.assertEqual(len(constructed), 2)
        self.assertIs(constructed[0], campaign_indices[0])
        self.assertIs(constructed[1], campaign_indices[1])


if __name__ == '__main__':
    unittest.main()
