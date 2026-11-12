"""Small mutable-input guards for JSON cohort merging; no source reconstruction."""
import unittest
from unittest.mock import patch

import negative_library as library
import negative_admission as first


class MergeUniqueTests(unittest.TestCase):
    def merge(self, groups, allowed=True):
        return library.merge_unique(groups, 'id', allow_identical=allowed)

    def test_alias_serializes_once_distinct_equal_twice_and_keeps_original_order(self):
        row = {'id': 'a', 'value': [1, True]}
        next_row = {'id': 'b'}
        real = first.canonical
        for duplicate, expected_calls in ((row, 1), (dict(row), 2)):
            with self.subTest(alias=duplicate is row), patch.object(first, 'canonical', wraps=real) as encode:
                result = self.merge([[row, next_row], [duplicate]])
            self.assertEqual(encode.call_count, expected_calls)
            self.assertEqual(result, [row, next_row])
            self.assertIs(result[0], row)

    def test_denied_duplicate_never_serializes_even_invalid_body(self):
        row = {'id': 'a', 'value': object()}
        with patch.object(first, 'canonical', side_effect=AssertionError('must not encode')) as encode:
            with self.assertRaisesRegex(ValueError, '^COHORT_DUPLICATE_OR_DISAGREEMENT$'):
                self.merge([[row, row]], False)
        encode.assert_not_called()

    def test_distinct_changed_body_and_boolean_number_are_not_identical(self):
        for left, right in ((1, 2), (True, 1), (1, 1.0)):
            with self.subTest(left=left, right=right):
                with self.assertRaisesRegex(ValueError, '^COHORT_DUPLICATE_OR_DISAGREEMENT$'):
                    self.merge([[{'id': 'a', 'v': left}, {'id': 'a', 'v': right}]])

    def test_same_object_invalid_json_values_still_fail(self):
        cycle = {'id': 'a'}
        cycle['value'] = cycle
        cases = ((cycle, ValueError, 'Circular reference detected'),
                 ({'id': 'a', 'value': float('nan')}, ValueError, 'Out of range float'),
                 ({'id': 'a', 'value': object()}, TypeError, 'not JSON serializable'))
        for row, kind, message in cases:
            with self.subTest(kind=kind.__name__, message=message):
                with self.assertRaisesRegex(kind, message):
                    self.merge([[row, row]])

    def test_generator_mutation_rereads_each_duplicate_and_rejects_new_invalid_value(self):
        row = {'id': 'a', 'value': 0}
        def changing():
            yield row
            row['value'] = 1
            yield row
            row['value'] = float('nan')
            yield row
        real = first.canonical
        with patch.object(first, 'canonical', wraps=real) as encode:
            with self.assertRaisesRegex(ValueError, 'Out of range float'):
                self.merge([changing()])
        self.assertEqual(encode.call_count, 2)

    def test_prior_success_never_reuses_body_across_calls(self):
        row = {'id': 'a', 'value': [1]}
        self.assertIs(self.merge([[row, row]])[0], row)
        row['value'].append(float('nan'))
        with self.assertRaisesRegex(ValueError, 'Out of range float'):
            self.merge([[row, row]])

    def test_dictionary_subclass_keeps_two_traversals_and_disagreement(self):
        class ChangingDictionary(dict):
            def items(self):
                self['value'] += 1
                return super().items()
        row = ChangingDictionary(id='a', value=0)
        real = first.canonical
        with patch.object(first, 'canonical', wraps=real) as encode:
            with self.assertRaisesRegex(ValueError, '^COHORT_DUPLICATE_OR_DISAGREEMENT$'):
                self.merge([[row, row]])
        self.assertEqual(encode.call_count, 2)

    def test_empty_and_missing_identity_keep_existing_outcomes(self):
        self.assertEqual(self.merge([]), [])
        with self.assertRaises(KeyError):
            self.merge([[{}]])


if __name__ == '__main__':
    unittest.main()
