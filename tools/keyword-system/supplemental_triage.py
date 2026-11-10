"""Dated public-capture adapter over the byte-pinned historical triage compiler.

No global mutation, master admission or platform writer. The legacy date field
is a transport projection only; actual dates are validated before projection
and retained in the returned workbench. All phrase/assessment bytes survive.
"""
from copy import deepcopy
from datetime import date,datetime,timedelta,timezone
import hashlib
import importlib.util
from pathlib import Path

import triage_workbench as legacy
from keyword_audit import negative_matches, normalize, parse_json_bytes, tokens

CAPTURE = Path('docs/audit/keyword-employment-education-2026-11-10')
EMPLOYMENT_CAPTURE = Path('docs/audit/keyword-employment-broad-2026-11-10')
EXCLUSION_CAPTURE = Path('docs/audit/keyword-exclusions-2026-11-10')
SUPPLY_CAPTURE = Path('docs/audit/keyword-discovery-supply-2026-11-08')
READINESS_CAPTURE = Path('docs/audit/keyword-property-readiness-2026-11-11')
NORTHERN_CAPTURE = Path('docs/audit/keyword-northern-emirates-2026-11-11')
ABU_SHARJAH_CAPTURE = Path('docs/audit/keyword-abu-dhabi-sharjah-2026-11-11')
DEVELOPER_EMPLOYMENT_CAPTURE = Path('docs/audit/keyword-developer-employment-2026-11-11')
CAPTURES = frozenset((CAPTURE, EMPLOYMENT_CAPTURE, EXCLUSION_CAPTURE, SUPPLY_CAPTURE, READINESS_CAPTURE, NORTHERN_CAPTURE, ABU_SHARJAH_CAPTURE, DEVELOPER_EMPLOYMENT_CAPTURE))
DAY = '2026-11-10'
SCOPE, NEGATIVE_SCOPE, need = legacy.SCOPE, legacy.NEGATIVE_SCOPE, legacy.need


def dubai_date(instant=None):
    """The review/capture business day is Dubai UTC+04, independent of host TZ."""
    instant=datetime.now(timezone.utc) if instant is None else instant
    need(isinstance(instant,datetime) and instant.tzinfo is not None and
         instant.utcoffset() is not None,'Timezone-aware review instant required')
    return instant.astimezone(timezone(timedelta(hours=4))).date()


def load_corpus(root, *, capture=CAPTURE):
    """Only the fixed reviewed captures are loadable; no arbitrary verifier path."""
    need(isinstance(capture, Path) and capture in CAPTURES, 'Unreviewed capture path')
    folder = Path(root).resolve() / capture
    spec = importlib.util.spec_from_file_location('supplemental_triage_capture', folder / 'verify_capture.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    verified = verifier.verify()
    need(verified.get('passed') is True, 'Capture verification did not pass')
    index_blob = (folder / 'capture.json').read_bytes()
    need(hashlib.sha256(index_blob).hexdigest() == verifier.PINS['capture.json'], 'Capture changed after verification')
    sources, entries = {}, {}
    for item in parse_json_bytes(index_blob)['source_files']:
        batch = item['batch_id']
        need(batch not in sources, 'Duplicate batch')
        blob = (folder / item['file']).read_bytes()
        need(hashlib.sha256(blob).hexdigest() == item['sha256'], 'Capture changed after verification')
        sources[batch] = {'file': (capture / item['file']).as_posix(), 'sha256': item['sha256']}
        for record in parse_json_bytes(blob)['source_projection']['records']:
            original = record['values']['Keyword']
            entry = entries.setdefault(normalize(original), {'original_forms': [], 'source_refs': []})
            if original not in entry['original_forms']:
                entry['original_forms'].append(original)
            entry['source_refs'].append({'batch': batch, 'source_line': record['source_line']})
    need(len(entries) == verified['distinct_phrases'] and
         sum(len(e['source_refs']) for e in entries.values()) == verified['export_rows'], 'Corpus coverage mismatch')
    return {'sources': sources, 'entries': entries}


def compile_workbench(corpus, proposals, *, proposed_on=DAY):
    """Validate actual dating, then reuse the unchanged legacy semantic compiler."""
    legacy._validate_corpus(corpus)
    need(isinstance(proposed_on, str), 'Invalid proposal date')
    day = date.fromisoformat(proposed_on)
    need(day.isoformat() == proposed_on and DAY <= proposed_on and day <= dubai_date(), 'Invalid proposal date')
    need(isinstance(proposals, dict) and proposals.get('proposed_on') == proposed_on, 'Invalid proposal document')
    # The pinned legacy schema accepts only its original date. Project that one
    # field on a detached copy; never change globals, input evidence or rows.
    transport = deepcopy(proposals)
    transport['proposed_on'] = legacy.DAY
    result = legacy.compile_workbench(corpus, transport)
    result['proposed_on'] = proposed_on
    return result


def compile_protection_review(corpus, proposals, additional_queries, generic_terms, *, proposed_on=DAY):
    workbench = compile_workbench(corpus, proposals, proposed_on=proposed_on)
    for values, limit in ((additional_queries, 30000), (generic_terms, 32)):
        need(isinstance(values, list) and len(values) <= limit and
             all(isinstance(q, str) and bool(tokens(q)) for q in values) and
             len(set(map(normalize, values))) == len(values), 'Invalid protection review input')
    protected = sorted(set(map(normalize, additional_queries)) |
                       set(workbench['diagnostics']['protected_phrases']))
    exact_index = {}
    for query in protected:
        exact_index.setdefault(tuple(tokens(query)), []).append(query)
    exact = [{'negative': row['negative'], 'hypothetical_match_type': 'EXACT',
              'protected_queries_tested': len(protected),
              'lexical_conflicts': list(exact_index.get(tuple(tokens(row['negative'])), ())),
              'scope_approved': False} for row in workbench['diagnostics']['exact_negative_tests']]
    generic = [{'attempted_generic': term, 'hypothetical_match_type': 'BROAD',
                'protected_queries_tested': len(protected),
                'lexical_conflicts': [q for q in protected if negative_matches(term, 'BROAD', q)],
                'legitimate_exclusion': False, 'scope_approved': False} for term in generic_terms]
    return {'workbench': workbench, 'screen': {
        'version': 1, 'scope': 'PROVISIONAL_UNSCOPED_LEXICAL_SCREEN',
        'basis': 'CONSERVATIVE_LEXICAL_ONLY_NOT_PLATFORM_MATCHING',
        'additional_queries': len(additional_queries), 'protected_queries': len(protected),
        'exact_negative_tests': exact, 'unsafe_generic_tests': generic,
        'exact_conflict_count': sum(len(row['lexical_conflicts']) for row in exact),
        'positive_library_coverage_verified': False, 'scope_verified': False,
        'deployment_authorized': False, 'master_additions': 0}}
