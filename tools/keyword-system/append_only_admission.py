"""Common append-only mechanics over caller-fresh verified research inputs.

Fingerprints bind complete bodies, ordering and all historical extra markers.
They do not substitute for the caller's fresh historical reconstruction.
"""
from copy import deepcopy
import hashlib

import negative_admission as first
import negative_library as history
from keyword_audit import audit, normalize


def digest(value):
    return hashlib.sha256(first.canonical(value)).hexdigest()


def extend(base, cohort, protections, *, expected_base_sha256, stage_key):
    first.need(stage_key not in base and digest(base) == expected_base_sha256,
               "APPEND_ONLY_BASE_CHANGED")
    first.need(cohort['campaigns'] == base['campaigns'] and
               cohort['campaign_context'] == base['campaign_context'] and
               not cohort['protected_queries'], "APPEND_ONLY_SCOPE_CHANGED")
    merged = history.compose([base, cohort])
    merged['protected_queries'] = deepcopy(base['protected_queries'] + protections)
    first.need(len({r['query_id'] for r in merged['protected_queries']}) ==
               len(merged['protected_queries']), "APPEND_ONLY_PROTECTION_COLLISION")
    all_records = merged['records'] + base['archived_records']
    first.need(len({r['keyword_id'] for r in all_records}) == len(all_records) and
               len({normalize(r['original_text']) for r in all_records}) == len(all_records),
               "APPEND_ONLY_ARCHIVE_COLLISION")
    # compose already supplies the replacement core fields. Copy only retained
    # history/extra fields, in one operation so their shared references survive.
    # The discarded core copy conveyed no ownership: update replaced it with
    # compose's original row/registry references in the previous implementation.
    result = deepcopy({key: value for key, value in base.items() if key not in merged})
    result.update(merged)
    result[stage_key] = {'base_sha256': expected_base_sha256,
        'retained_records': len(base['records']), 'retained_sources': len(base['sources']),
        'retained_protections': len(base['protected_queries'])}
    first.need(result['records'][:len(base['records'])] == base['records'] and
               result['sources'][:len(base['sources'])] == base['sources'] and
               result['protected_queries'][:len(base['protected_queries'])] == base['protected_queries'] and
               result['archived_records'] == base['archived_records'] and
               recover_base(result, stage_key=stage_key) == base,
               "APPEND_ONLY_HISTORICAL_BODY_REPLACED")
    return result


def recover_base(inputs, *, stage_key):
    first.need(type(inputs.get(stage_key)) is dict, "APPEND_ONLY_STATE_MISSING")
    state = inputs[stage_key]
    first.need(set(state) == {'base_sha256', 'retained_records', 'retained_sources',
                              'retained_protections'}, "APPEND_ONLY_STATE_CHANGED")
    for key, field in (('retained_records', 'records'), ('retained_sources', 'sources'),
                       ('retained_protections', 'protected_queries')):
        first.need(type(state[key]) is int and 0 <= state[key] <= len(inputs[field]),
                   "APPEND_ONLY_PREFIX_LENGTH_CHANGED")
    base = dict(inputs)
    del base[stage_key]
    for key, field in (('retained_records', 'records'), ('retained_sources', 'sources'),
                       ('retained_protections', 'protected_queries')):
        base[field] = inputs[field][:state[key]]
    first.need(digest(base) == state['base_sha256'], "APPEND_ONLY_PREFIX_CHANGED")
    return base


def checked_audit(inputs, when):
    """Always execute the real complete-input audit; grant no export authority."""
    result = audit('negative', inputs['records'], inputs['sources'], inputs['campaigns'],
                   inputs['campaign_context'], inputs['protected_queries'], when)
    first.need(result['structural_pass'] and
               result['reviewed_eligible_rows'] == result['input_rows'] == len(inputs['records']) and
               len(result['protected_conflicts']) == result['excluded_rows'] ==
               result['approved_exclusion_rows'] == 0 and
               not result['deployment_export_allowed'] and
               not result['production_writes_available'] and
               not result['positive_library_coverage_verified'], "APPEND_ONLY_RESEARCH_NOT_ELIGIBLE")
    return result


def check_documents(root, folder, pins, documents):
    first.need(type(pins) is dict and set(pins) == set(documents) and
               all(type(pin) is str and len(pin) == 64 for pin in pins.values()),
               "APPEND_ONLY_OUTPUT_PINS_UNREGISTERED")
    for name, document in documents.items():
        first.need(first.canonical(first.pinned(root, folder+'/'+name, pins[name])) ==
                   first.canonical(document), "APPEND_ONLY_SAVED_OUTPUT_CHANGED")
