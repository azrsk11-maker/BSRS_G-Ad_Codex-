"""Verify preserved evidence of a held source; PASS does not accept the batch."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'tools/keyword-system'))
from keyword_audit import parse_json_bytes
from planner_discovery import parse_discovery
import supplemental_discovery as sd

PINS = {
    'projection.json': '8ffbbfbbc8a8b29696f4cdd2fa6b049e982d34d69f4a8da237c0380865e7025b',
    'capture.json': '323b9d929b9b6087fd0c41cd4ce725c4f3263f1050ceeb08425f9f71cdb68b85',
}
DEPENDENCIES = {
    'tools/keyword-system/planner_discovery.py': '952423aac9ed3d1a4cb23185dd8da2a5451d19f7166fc73ce1c2b86391aadf9b',
    'tools/keyword-system/supplemental_discovery.py': '727230214dd3537089a093e0ad0a819e62986db8ca310e6856714403269106bf',
    'tools/keyword-system/keyword_audit.py': 'ef6ce0535c8ce5cd83f50e169d26328cd763a236cfcbee4919f927c6fd8cd8d6',
}
RAW_SHA = '5ec969b194766310f22066bf42a9d53c7ea4c29638343bcd8195bebf0ddf92f4'


def need(condition, code):
    if not condition:
        raise ValueError(code)


def read_bound(path):
    with Path(path).open('rb') as stream:
        body = stream.read(1024 * 1024 + 1)
    need(0 < len(body) <= 1024 * 1024, 'BYTE_BOUND')
    return body


def validate(projection, capture):
    need(projection['scope'] == 'RAW_PUBLIC_PROJECTION_QUARANTINED_UI_COUNT_MISMATCH', 'QUARANTINE_SCOPE')
    data = projection['source_projection']
    need(capture['status'] == 'HELD_UI_EXPORT_COUNT_MISMATCH', 'HOLD_REQUIRED')
    need(sd._exact(capture['observed_context'], dict(sd.CONTEXT, ui_idea_count=176)), 'ORIGINAL_UI_CONTEXT')
    need(type(data['record_count']) is int and data['record_count'] == 177
         and data['distinct_normalized_count'] == 177 and data['duplicate_groups'] == [], 'ORIGINAL_EXPORT_COUNT')
    need(capture['raw_export_rows'] == 177 and capture['difference_export_minus_ui'] == 1, 'DISCREPANCY_REQUIRED')
    need(data['source_sha256'] == capture['source_sha256'] == RAW_SHA
         and data['source_bytes'] == capture['source_bytes'] == 26924, 'RAW_IDENTITY')
    need(data['date_header'] == 'November 1, 2025 - October 31, 2026', 'ORIGINAL_PERIOD')
    need([r['source_line'] for r in data['records']] == list(range(4, 181)), 'ALL_PHYSICAL_LINES')
    need(sd._exact(capture['master_contribution'], sd.MASTER)
         and sd._exact(capture['controls'], sd.CONTROLS), 'ZERO_AUTHORITY')
    for key in ('cause_established', 'source_rows_removed_or_repaired', 'semantic_review_complete',
                'current_library_membership_verified', 'capture_accepted_for_research', 'deployment_authorized'):
        need(capture[key] is False, 'HELD_WITHOUT_PROMOTION')
    need(capture['seed_status'] == 'AGENT_RESEARCH_HYPOTHESES_NOT_OBSERVED_QUERIES_OR_EXCLUSIONS', 'SEED_AUTHORITY')
    positions = {sd.normalize(r['values']['Keyword']): (i, r['source_line']) for i, r in enumerate(data['records'], 1)}
    expected = [{'seed': s, 'source_ordinal': positions[sd.normalize(s)][0],
                 'source_line': positions[sd.normalize(s)][1]} for s in capture['seeds']]
    need(sd._exact(capture['seed_relationships'], expected), 'ORIGINAL_SEED_RELATIONSHIPS')
    batch = {'version': 1, 'scope': 'AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED',
             'topic': 'employment-applications', 'batch_id': 'BSRE-KP-EMP-20261113-01',
             'input_seeds': capture['seeds'], 'ui_context': capture['observed_context'],
             'source_projection': data, 'controls': capture['controls'],
             'seed_reconciliation': {'exact_returned': 10, 'without_separate_exact_row': []}}
    try:
        sd._batch(batch)
    except ValueError as error:
        need(str(error) == 'RESEARCH_CONTEXT', 'UNEXPECTED_REJECTION')
    else:
        raise ValueError('MISMATCH_MUST_NOT_PASS_GENERIC_CAPTURE')
    # Validate the complete public schema independently of the observed count.
    # This is a structural diagnostic, never a replacement UI observation.
    diagnostic = copy.deepcopy(batch)
    diagnostic['ui_context']['ui_idea_count'] = 177
    sd._batch(diagnostic)


def verify(source=None, self_check=False):
    for name, pin in DEPENDENCIES.items():
        need(hashlib.sha256(read_bound(ROOT / name)).hexdigest() == pin, 'DEPENDENCY_CHANGED')
    public = {}
    for name, pin in PINS.items():
        body = read_bound(HERE / name)
        need(hashlib.sha256(body).hexdigest() == pin, 'PUBLIC_BYTES_CHANGED')
        public[name] = parse_json_bytes(body)
    projection, capture = public['projection.json'], public['capture.json']
    validate(projection, capture)
    if source is not None:
        raw = parse_discovery(source)
        raw['source_basename'] = projection['source_projection']['source_basename']
        need(sd._exact(raw, projection['source_projection']), 'PRIVATE_RAW_CELL_MISMATCH')
    rejected = 0
    if self_check:
        for key, value in [('status', 'ACCEPTED'), ('capture_accepted_for_research', True),
                           ('deployment_authorized', True), ('cause_established', True),
                           ('source_rows_removed_or_repaired', True), ('semantic_review_complete', True)]:
            altered = copy.deepcopy(capture)
            altered[key] = value
            try:
                validate(projection, altered)
            except ValueError:
                rejected += 1
            else:
                raise ValueError('HOLD_TAMPER_NOT_REJECTED')
        for label, mutate in [
            ('UI_COUNT', lambda p, c: c['observed_context'].__setitem__('ui_idea_count', 177)),
            ('ROW_DROP', lambda p, c: p['source_projection']['records'].pop()),
            ('ACCOUNT_CELL', lambda p, c: p['source_projection']['records'][0]['values'].__setitem__('In account?', 'Yes')),
            ('APPROVAL', lambda p, c: c['controls'].__setitem__('approved', True)),
        ]:
            altered_p, altered_c = copy.deepcopy(projection), copy.deepcopy(capture)
            mutate(altered_p, altered_c)
            try:
                validate(altered_p, altered_c)
            except ValueError:
                rejected += 1
            else:
                raise ValueError('SOURCE_TAMPER_NOT_REJECTED_' + label)
    return {'passed': True, 'scope': 'HELD_EVIDENCE_PRESERVATION_ONLY',
            'raw_export_rows': 177, 'independently_observed_ui_rows': 176,
            'private_raw_equivalence_verified': source is not None,
            'tamper_diagnostics_rejected': rejected, 'capture_accepted_for_research': False,
            'cause_established': False, 'master_rows_added': 0, 'deployment_authorized': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, metavar='PRIVATE_PATH')
    parser.add_argument('--self-check', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    try:
        result = verify(args.source, args.self_check)
        result['measured_elapsed_seconds'] = round(time.perf_counter() - started, 6)
        print(json.dumps(result, sort_keys=True))
    except Exception as error:
        print(json.dumps({'passed': False, 'code': 'HELD_EMPLOYMENT_EVIDENCE_FAILED',
                          'error_type': type(error).__name__, 'deployment_authorized': False}))
        raise SystemExit(1)
