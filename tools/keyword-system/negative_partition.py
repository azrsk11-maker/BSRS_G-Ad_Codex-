"""Pure current/held research indexes; no source, platform or approval writer.

The caller must authenticate records and the latest impact first. Structural
validation here does not establish provenance, scope or independent approval.
"""
import re

from keyword_audit import normalize

CONTROLS = {'research_only': True, 'scope_approved': False,
            'deployment_authorized': False, 'live_campaign_changes': False,
            'master_records_rewritten': False, 'master_additions': 0}


def need(condition, code):
    if not condition:
        raise ValueError(code)


def reference(value):
    need(isinstance(value, dict) and set(value) == {'file', 'sha256'}, 'PARTITION_REFERENCE')
    name, digest = value['file'], value['sha256']
    need(isinstance(name, str) and 0 < len(name) <= 250 and
         not name.startswith(('/', '\\')) and ':' not in name and
         not any(part in {'', '.', '..'} for part in name.split('/')) and
         '\\' not in name and not any(ord(c) < 32 or ord(c) == 127 for c in name) and
         isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest) is not None,
         'PARTITION_REFERENCE')
    return dict(value)


def build_index(records, impact, *, historical_master, latest_report, latest_impact):
    """Partition every historical ID exactly once, retaining original order.

    Any unexplained eligibility loss, unknown conflict or count mismatch holds
    the operation. The result contains references/IDs, never copied record bodies.
    """
    need(isinstance(records, list) and 0 < len(records) <= 100000, 'PARTITION_RECORDS')
    ids, texts = [], set()
    for row in records:
        need(isinstance(row, dict) and isinstance(row.get('keyword_id'), str) and
             bool(row['keyword_id'].strip()) and isinstance(row.get('original_text'), str),
             'PARTITION_RECORD_IDENTITY')
        key = normalize(row['original_text'])
        need(bool(key) and key not in texts, 'PARTITION_DUPLICATE_PHRASE')
        texts.add(key); ids.append(row['keyword_id'])
    need(len(set(ids)) == len(ids), 'PARTITION_DUPLICATE_ID')
    need(isinstance(impact, dict), 'PARTITION_IMPACT')
    for key in ('historical_input_rows', 'latest_review_eligible_rows', 'latest_excluded_rows',
                'latest_deficit', 'approved_exclusion_rows', 'master_additions'):
        need(type(impact.get(key)) is int and impact[key] >= 0, 'PARTITION_COUNT')
    need(impact['approved_exclusion_rows'] == impact['master_additions'] == 0 and
         impact.get('deployment_authorized') is False and
         impact.get('historical_rows_rewritten') is False, 'PARTITION_AUTHORITY')
    conflicts = impact.get('protected_conflicts')
    need(isinstance(conflicts, list), 'PARTITION_CONFLICTS')
    known, held, seen = set(ids), set(), set()
    for conflict in conflicts:
        need(isinstance(conflict, dict) and set(conflict) ==
             {'negative_id', 'protected_query_id', 'affected_campaign_keys', 'result'}, 'PARTITION_CONFLICT_FIELDS')
        identity, query, campaigns = (conflict['negative_id'], conflict['protected_query_id'],
                                      conflict['affected_campaign_keys'])
        need(isinstance(identity, str) and identity in known, 'PARTITION_UNKNOWN_CONFLICT_ID')
        need(isinstance(query, str) and bool(query.strip()) and isinstance(campaigns, list) and
             bool(campaigns) and all(isinstance(c, str) and bool(c.strip()) for c in campaigns) and
             len(set(campaigns)) == len(campaigns) and conflict['result'] == 'CONFLICT_HOLD',
             'PARTITION_CONFLICT_SCOPE')
        pair = (identity, query, tuple(sorted(campaigns)))
        need(pair not in seen, 'PARTITION_DUPLICATE_CONFLICT')
        seen.add(pair); held.add(identity)
    eligible_ids = [identity for identity in ids if identity not in held]
    held_ids = [identity for identity in ids if identity in held]
    need(impact['historical_input_rows'] == len(ids) and
         impact['latest_review_eligible_rows'] == len(eligible_ids) and
         impact['latest_excluded_rows'] == len(held_ids) and
         impact['latest_deficit'] == max(0, 14000 - len(eligible_ids)) and
         type(impact.get('admission_held')) is bool and impact['admission_held'] == bool(held_ids),
         'PARTITION_UNEXPLAINED_ELIGIBILITY_OR_HOLDS')
    master = reference(historical_master)
    need(master['sha256'] == impact.get('historical_master_sha256'), 'PARTITION_MASTER_BINDING')
    report, evidence = reference(latest_report), reference(latest_impact)
    need(report['sha256'] == impact.get('latest_coverage_sha256'), 'PARTITION_REPORT_BINDING')
    return {'version': 1, 'scope': 'ELIGIBLE_AND_HELD_RESEARCH_INDEX_NOT_AD_SERVING_STATUS',
            'historical_master': master, 'latest_report': report, 'latest_impact': evidence,
            'counts': {'historical': len(ids), 'eligible': len(eligible_ids), 'held': len(held_ids)},
            'eligible_keyword_ids': eligible_ids, 'held_keyword_ids': held_ids,
            'controls': dict(CONTROLS)}
