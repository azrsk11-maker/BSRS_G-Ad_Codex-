import json
import math
import unittest
from unittest.mock import patch
import fresh_history_codec as codec


class LosslessFixtureTests(unittest.TestCase):
    def document(self):
        return json.loads(codec.dumps({'int_rows': {2: 'two', 10: 'ten'}, 'string_rows': {'2': 'two', '10': 'ten'}}))

    def deny(self, document):
        with self.assertRaises(codec.CodecError):
            codec.loads(json.dumps(document).encode())

    def test_integer_and_numeric_string_keys_remain_distinct(self):
        original = {'int_rows': {2: 'two', 10: 'ten'}, 'string_rows': {'2': 'two', '10': 'ten'}}
        restored = codec.loads(codec.dumps(original))
        self.assertEqual(original, restored)
        self.assertEqual([type(key) for key in restored['int_rows']], [int, int])
        self.assertEqual([type(key) for key in restored['string_rows']], [str, str])

    def test_list_tuple_and_shared_alias_identity_survive(self):
        shared = [{'x': 1}]
        original = {'a': shared, 'b': (shared, shared[0]), 'c': shared}
        restored = codec.loads(codec.dumps(original))
        self.assertEqual(original, restored)
        self.assertIs(type(restored['b']), tuple)
        self.assertIs(restored['a'], restored['c'])
        self.assertIs(restored['a'], restored['b'][0])
        self.assertIs(restored['a'][0], restored['b'][1])

    def test_primitive_types_unicode_and_negative_zero_survive(self):
        original = [None, True, False, 0, 2**80, 'العربية', -0.0, 1.25]
        restored = codec.loads(codec.dumps(original))
        self.assertEqual(original, restored)
        self.assertEqual([type(v) for v in original], [type(v) for v in restored])
        self.assertEqual(math.copysign(1, restored[-2]), -1)

    def test_case_copy_is_detached_without_losing_internal_alias(self):
        from copy import deepcopy
        shared = [1]
        fixture = codec.loads(codec.dumps({'a': shared, 'b': shared}))
        first, second = deepcopy(fixture), deepcopy(fixture)
        first['a'].append(2)
        self.assertEqual(first['b'], [1, 2])
        self.assertEqual(second['a'], [1])
        self.assertEqual(fixture['a'], [1])

    def test_wrong_version_and_extra_top_level_keys_deny(self):
        for edit in (lambda d: d.update(schema='unknown'), lambda d: d.update(extra=True)):
            document = self.document(); edit(document); self.deny(document)

    def test_negative_bool_and_out_of_bounds_references_deny(self):
        for ref in (-1, True, 1000000, '0'):
            document = self.document(); document['root'] = {'ref': ref}; self.deny(document)

    def test_duplicate_json_keys_deny(self):
        with self.assertRaisesRegex(codec.CodecError, 'DUPLICATE_JSON_KEY'):
            codec.loads(b'{"schema":"x","schema":"x","root":null,"nodes":[]}')

    def test_duplicate_decoded_data_keys_deny(self):
        document = {'schema': codec.SCHEMA, 'root': {'ref': 0},
                    'nodes': [['dict', [[1, 'a'], [True, 'b']]]]}
        self.deny(document)

    def test_unreachable_nodes_deny(self):
        document = self.document(); document['nodes'].append(['list', []]); self.deny(document)

    def test_encoded_and_decoded_cycles_deny(self):
        cyclic = []; cyclic.append(cyclic)
        with self.assertRaisesRegex(codec.CodecError, 'CYCLE'): codec.dumps(cyclic)
        self.deny({'schema': codec.SCHEMA, 'root': {'ref': 0}, 'nodes': [['list', [{'ref': 0}]]]})

    def test_arbitrary_types_and_malformed_node_shapes_deny(self):
        with self.assertRaises(codec.CodecError): codec.dumps(object())
        for node in (['code', []], ['dict', [['one']]], ['list', {}]):
            self.deny({'schema': codec.SCHEMA, 'root': {'ref': 0}, 'nodes': [node]})

    def test_nonfinite_and_noncanonical_float_values_deny(self):
        for value in (float('nan'), float('inf')):
            with self.assertRaises(codec.CodecError): codec.dumps(value)
        for text in ('nan', 'inf', '1.0', '0x1.0000000000000p+000'):
            self.deny({'schema': codec.SCHEMA, 'root': {'float': text}, 'nodes': []})

    def test_byte_and_node_bounds_deny(self):
        with patch.object(codec, 'MAX_BYTES', 10), self.assertRaises(codec.CodecError): codec.dumps({'x': 1})
        with patch.object(codec, 'MAX_NODES', 0), self.assertRaises(codec.CodecError): codec.dumps([])
        with patch.object(codec, 'MAX_BYTES', 1), self.assertRaises(codec.CodecError): codec.loads(b'{}')

    def test_depth_limit_deny(self):
        original = [[[[1]]]]
        with patch.object(codec, 'MAX_DEPTH', 2), self.assertRaises(codec.CodecError): codec.dumps(original)
        raw = codec.dumps(original)
        with patch.object(codec, 'MAX_DEPTH', 2), self.assertRaises(codec.CodecError): codec.loads(raw)


if __name__ == '__main__':
    unittest.main()
