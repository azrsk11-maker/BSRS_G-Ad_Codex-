"""Reproduce a pinned baseline's protective literals, never its acceptance.

Callers must pin all workbenches, reviewed membership and authored cases. This
pure projection is only a preliminary triage input. Full current-library source,
chronology, scope, report and aggregate verification remains mandatory elsewhere.
"""
import hashlib
import re

from keyword_audit import normalize


def derive(workbenches, eligible_ids, authored_queries):
    def need(ok, code):
        if not ok:
            raise ValueError(code)
    need(isinstance(workbenches, list) and bool(workbenches) and len(workbenches) <= 100,
         'TRIAGE_BASE_WORKBENCHES')
    need(isinstance(eligible_ids, list) and 0 < len(eligible_ids) <= 100000 and
         all(isinstance(v, str) and re.fullmatch(r'BSRE-N-[0-9a-f]{24}', v) for v in eligible_ids) and
         len(set(eligible_ids)) == len(eligible_ids), 'TRIAGE_BASE_MEMBERSHIP')
    need(isinstance(authored_queries, list) and all(isinstance(v, str) and normalize(v) for v in authored_queries) and
         len({normalize(v) for v in authored_queries}) == len(authored_queries), 'TRIAGE_BASE_AUTHORED')
    eligible, seen, protected = set(eligible_ids), set(), {normalize(v) for v in authored_queries}
    for workbench in workbenches:
        need(isinstance(workbench, dict) and isinstance(workbench.get('queue'), list) and
             bool(workbench['queue']), 'TRIAGE_BASE_QUEUE')
        local = set()
        for row in workbench['queue']:
            need(isinstance(row, dict), 'TRIAGE_BASE_ROW')
            text, disposition = row.get('normalized_text'), row.get('disposition')
            need(isinstance(text, str) and text and normalize(text) == text and text not in local and
                 disposition in {'HOLD', 'POSITIVE_REVIEW', 'NEGATIVE_EXACT_REVIEW'}, 'TRIAGE_BASE_ROW')
            local.add(text)
            identity = 'BSRE-N-'+hashlib.sha256(text.encode('utf8')).hexdigest()[:24]
            seen.add(identity)
            if disposition != 'NEGATIVE_EXACT_REVIEW' or identity not in eligible:
                protected.add(text)
    need(eligible <= seen, 'TRIAGE_BASE_UNKNOWN_MEMBERSHIP')
    return sorted(protected)
