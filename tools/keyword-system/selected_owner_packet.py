"""Print/verify selected held owner workorders without changing pinned helpers."""
import argparse
import copy
import json
from pathlib import Path

import positive_service_packet as base


def build_packet(root=base.ROOT, candidate_ids=None):
    root = Path(root)
    template = base.build_packet(root)
    history = base.load_history((root / base.HISTORY).read_bytes())
    candidates = {r['candidate_id']: r for r in history['candidates']}
    placements = {r['placement_id']: r for r in history['placements']}
    if (not isinstance(candidate_ids, list) or not candidate_ids
            or any(not isinstance(i, str) for i in candidate_ids)
            or len(set(candidate_ids)) != len(candidate_ids)):
        raise ValueError('Select unique nonempty historical candidate IDs')
    if any(i not in candidates for i in candidate_ids):
        raise ValueError('Unknown historical candidate ID')
    rows = []
    for identity, candidate in candidates.items():
        if identity not in candidate_ids:
            continue
        occurrences = [placements[i] for i in candidate['placement_ids']]
        if any(p['original_keyword_fields']['Campaign'] != 'BSRE_SEARCH_OWNERS_EN' for p in occurrences):
            raise ValueError('Owner-service workorders require historical owner placements')
        row = copy.deepcopy(template['rows'][0])
        row.update(candidate_id=identity, original_text=candidate['original_text'],
                   source_candidate_sha256=base.canonical_sha256(candidate),
                   historical_occurrences=[{
                       'placement_id': p['placement_id'], 'placement_sha256': base.canonical_sha256(p),
                       'keyword_source_locator': p['keyword_source_locator'],
                       'metadata_source_locator': p['metadata_source_locator'],
                       'historical_match_type': p['original_keyword_fields']['Criterion Type']}
                       for p in occurrences])
        rows.append(row)
    template.update(scope='SELECTED_HISTORICAL_OWNER_CANDIDATES_NOT_MASTER_OR_LAUNCH_COHORT', rows=rows)
    template['counts'].update(selected_canonical_seeds=len(rows),
                              historical_occurrences=sum(len(r['historical_occurrences']) for r in rows))
    return template


def verify_packet(content, root=base.ROOT, candidate_ids=None):
    expected = build_packet(root, candidate_ids)
    actual = base.keyword_audit.parse_json_bytes(content)
    # Canonical JSON distinguishes false/0 and integer/float unlike Python ==.
    if base.canonical_sha256(actual) != base.canonical_sha256(expected):
        raise ValueError('Workorder differs from fresh source-bound explicit selection')
    return {'status': 'PASS_INTAKE_CONSISTENCY_ONLY', **expected['counts'],
            'master_admission_allowed': False, 'business_evidence_accepted': False,
            'deployment_export_allowed': False, 'packet_canonical_sha256': base.canonical_sha256(actual)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-id', action='append', required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--verify', type=Path)
    modes.add_argument('--emit-workorder', action='store_true')
    args = parser.parse_args()
    value = (build_packet(candidate_ids=args.candidate_id) if args.emit_workorder
             else verify_packet(args.verify.read_bytes(), candidate_ids=args.candidate_id))
    print(json.dumps(value, sort_keys=True))


if __name__ == '__main__':
    main()
