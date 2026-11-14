"""Canonical byte/error parity and fresh mutable-body traversal."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import threading
import unittest

import negative_admission as first


def legacy(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


class CanonicalEncodingTests(unittest.TestCase):
    def outcome(self, function, value):
        try:
            return ('bytes', function(value))
        except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
            return (type(exc).__name__, exc.args)

    def test_complete_bytes_match_original_for_native_json_and_shared_values(self):
        shared = ['synthetic', {'nested': True}]
        values = [None, True, False, 0, -1, 1.0, -0.0, 1e100,
                  'Unicode \u00e9 \u6c49 \U0001f642 and "quote"\n',
                  {'z': shared, 'a': shared, 'empty': {}, 'array': []},
                  {2: 'two', 1: 'one'}, (1, 'tuple', False)]
        for value in values:
            with self.subTest(kind=type(value).__name__):
                self.assertEqual(first.canonical(value), legacy(value))

    def test_original_error_types_and_arguments_remain_exact(self):
        cyclic = []; cyclic.append(cyclic)
        values = [math.nan, math.inf, -math.inf, {'x': math.nan},
                  {1: 'one', 'x': 'mixed key types'}, {object(): 'key'},
                  {'x': object()}, {'x': {1, 2}}, '\ud800', cyclic]
        for value in values:
            with self.subTest(kind=type(value).__name__):
                expected = self.outcome(legacy, value)
                self.assertNotEqual(expected[0], 'bytes')
                self.assertEqual(self.outcome(first.canonical, value), expected)

    def test_nested_mutation_is_encoded_fresh_on_every_call(self):
        value = {'id': 'SYNTHETIC', 'nested': {'items': [1]}}
        before = first.canonical(value)
        value['nested']['items'].append(2)
        self.assertNotEqual(first.canonical(value), before)
        self.assertEqual(first.canonical(value), legacy(value))
        value['nested']['items'][0] = math.nan
        self.assertEqual(self.outcome(first.canonical, value), self.outcome(legacy, value))

    def test_circular_failure_does_not_poison_later_traversal(self):
        value = {'items': []}; value['items'].append(value)
        with self.assertRaises(ValueError):
            first.canonical(value)
        value['items'].clear()
        self.assertEqual(first.canonical(value), legacy(value))

    def test_equal_python_scalars_keep_distinct_canonical_representations(self):
        values = [True, 1, 1.0, '1', False, 0, 0.0, -0.0, None]
        encoded = [first.canonical(x) for x in values]
        self.assertEqual(len(set(encoded)), len(values))
        self.assertEqual(encoded, [legacy(x) for x in values])

    def test_shared_encoder_has_no_cross_thread_traversal_state(self):
        barrier = threading.Barrier(4)
        before = dict(vars(first._CANONICAL_ENCODER))
        def encode_batch(worker):
            barrier.wait(timeout=5)
            for item in range(25):
                value = {'worker': worker, 'item': item, 'list': [worker, item]}
                if first.canonical(value) != legacy(value):
                    return False
            return True
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertTrue(all(pool.map(encode_batch, range(4))))
        self.assertEqual(vars(first._CANONICAL_ENCODER), before)


if __name__ == '__main__':
    unittest.main()
