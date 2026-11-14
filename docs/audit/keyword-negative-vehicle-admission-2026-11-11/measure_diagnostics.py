"""Measure forced failure formatting; print metrics only, never record contents."""
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time
import unittest

root = Path(__file__).resolve().parents[3]
folder = 'docs/audit/keyword-negative-vehicle-admission-2026-11-11/'
rows = json.loads((root/'tools/keyword-system/data/negative.json').read_text(encoding='utf-8'))
selected = {r['normalized_text']:r for r in rows if r['evidence_ref'].startswith(folder)}
assert len(selected) == 1509 and 'rent a car dubai' not in selected
case = unittest.TestCase()


def trial(bounded):
    started = time.perf_counter()
    try:
        if bounded:
            case.assertTrue('rent a car dubai' in selected, 'Captured car-rental literal missing')
        else:
            case.assertIn('rent a car dubai', selected)
    except AssertionError as error:
        raw = str(error).encode('utf-8')
        return {'failed_as_expected':True, 'message_bytes':len(raw),
                'message_sha256':hashlib.sha256(raw).hexdigest(),
                'elapsed_seconds':time.perf_counter()-started}
    raise RuntimeError('Forced absence failed to raise')


if __name__ == '__main__':
    before = [trial(False) for _ in range(3)]
    after = [trial(True) for _ in range(3)]
    assert len({r['message_sha256'] for r in before}) == len({r['message_sha256'] for r in after}) == 1
    print(json.dumps({'scope':'FORCED_TEST_FAILURE_FORMATTING_ONLY_NOT_PROVIDER_TOKEN_OR_BILLING',
        'python':platform.python_version(), 'platform':platform.system(), 'records':len(selected),
        'selected_records_sha256':hashlib.sha256(json.dumps(selected,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        'before_method':'assertIn(missing_literal, full_record_mapping)',
        'after_method':'assertTrue(missing_literal in mapping, bounded_message)',
        'before':before, 'after':after,
        'before_median_seconds':statistics.median(r['elapsed_seconds'] for r in before),
        'after_median_seconds':statistics.median(r['elapsed_seconds'] for r in after),
        'all_failures_still_detected':True, 'network_or_production_actions':False},indent=2))
