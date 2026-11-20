"""Closed JSON graph for fresh public test data. No pickle, code or verdicts."""
import json
import math

SCHEMA = 'bsre-fresh-history-graph-v1'
MAX_BYTES = 128 * 1024 * 1024
MAX_NODES = 1000000
MAX_DEPTH = 256


class CodecError(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise CodecError(code)


def dumps(value):
    nodes, memo, active = [], {}, set()

    def visit(item, depth=0):
        need(depth <= MAX_DEPTH, 'FIXTURE_DEPTH_EXCEEDED')
        kind = type(item)
        if kind in (type(None), bool, int, str):
            return item
        if kind is float:
            need(math.isfinite(item), 'FIXTURE_NONFINITE')
            return {'float': item.hex()}
        need(kind in (dict, list, tuple), 'FIXTURE_TYPE_UNSUPPORTED')
        identity = id(item)
        need(identity not in active, 'FIXTURE_CYCLE')
        if identity in memo:
            return {'ref': memo[identity]}
        need(len(nodes) < MAX_NODES, 'FIXTURE_NODES_EXCEEDED')
        index = len(nodes)
        memo[identity] = index
        nodes.append(None)
        active.add(identity)
        if kind is dict:
            body = []
            for key, nested in item.items():
                need(type(key) in (type(None), bool, int, float, str), 'FIXTURE_KEY_TYPE_UNSUPPORTED')
                body.append([visit(key, depth + 1), visit(nested, depth + 1)])
            nodes[index] = ['dict', body]
        else:
            nodes[index] = ['tuple' if kind is tuple else 'list', [visit(v, depth + 1) for v in item]]
        active.remove(identity)
        return {'ref': index}

    document = {'schema': SCHEMA, 'root': visit(value), 'nodes': nodes}
    raw = json.dumps(document, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf-8')
    need(len(raw) <= MAX_BYTES, 'FIXTURE_BYTES_EXCEEDED')
    return raw


def loads(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'FIXTURE_BYTES_INVALID')

    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'FIXTURE_DUPLICATE_JSON_KEY')
            result[key] = value
        return result

    def no_constant(_):
        raise CodecError('FIXTURE_NONFINITE')

    try:
        document = json.loads(raw, object_pairs_hook=object_pairs, parse_constant=no_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise CodecError('FIXTURE_JSON_INVALID') from error
    need(type(document) is dict and set(document) == {'schema', 'root', 'nodes'}
         and document['schema'] == SCHEMA, 'FIXTURE_SCHEMA_INVALID')
    nodes = document['nodes']
    need(type(nodes) is list and len(nodes) <= MAX_NODES, 'FIXTURE_NODES_INVALID')
    memo, active, reached = {}, set(), set()

    def visit(item, depth=0):
        need(depth <= MAX_DEPTH, 'FIXTURE_DEPTH_EXCEEDED')
        if type(item) in (type(None), bool, int, str):
            return item
        need(type(item) is dict, 'FIXTURE_VALUE_INVALID')
        if set(item) == {'float'}:
            text = item['float']
            need(type(text) is str and len(text) <= 32, 'FIXTURE_FLOAT_INVALID')
            try:
                number = float.fromhex(text)
            except ValueError as error:
                raise CodecError('FIXTURE_FLOAT_INVALID') from error
            need(math.isfinite(number) and number.hex() == text, 'FIXTURE_FLOAT_INVALID')
            return number
        need(set(item) == {'ref'} and type(item['ref']) is int
             and 0 <= item['ref'] < len(nodes), 'FIXTURE_REFERENCE_INVALID')
        index = item['ref']
        need(index not in active, 'FIXTURE_CYCLE')
        reached.add(index)
        if index in memo:
            return memo[index]
        entry = nodes[index]
        need(type(entry) is list and len(entry) == 2 and entry[0] in ('dict', 'list', 'tuple')
             and type(entry[1]) is list, 'FIXTURE_NODE_INVALID')
        tag, body = entry
        active.add(index)
        if tag == 'dict':
            result = {}
            for pair in body:
                need(type(pair) is list and len(pair) == 2, 'FIXTURE_PAIR_INVALID')
                key, value = visit(pair[0], depth + 1), visit(pair[1], depth + 1)
                need(type(key) in (type(None), bool, int, float, str), 'FIXTURE_KEY_TYPE_UNSUPPORTED')
                need(key not in result, 'FIXTURE_DUPLICATE_DATA_KEY')
                result[key] = value
        else:
            result = [visit(value, depth + 1) for value in body]
            if tag == 'tuple':
                result = tuple(result)
        active.remove(index)
        memo[index] = result
        return result

    result = visit(document['root'])
    need(len(reached) == len(nodes), 'FIXTURE_UNREACHABLE_NODE')
    return result
