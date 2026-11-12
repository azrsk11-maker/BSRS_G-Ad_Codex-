"""Source-bound Ofqual research over one freshly verified valuation snapshot.

Published titles are official references, not queries, demand or current offers.
No platform writer, acceptance cache or exclusion approval is supplied.
"""
import ast
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
from pathlib import Path

import append_only_admission as stage
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first
import ofqual_discovery
import valuation_admission as prior


FOLDER = 'docs/audit/keyword-negative-ofqual-admission-2026-11-11'
CAPTURE = 'docs/audit/keyword-ofqual-discovery-2026-11-11'
SECOND = 'docs/audit/keyword-ofqual-admission-review-2026-11-11'
SOURCE_PINS = {
    CAPTURE+'/capture.json': '40563540ed29d76e03e2bea8be1a46aca960d888c138fcc2f9ac2f54dec2e9f7',
    CAPTURE+'/qualifications.json': '2869cab8a06a76fa113ef430b28d09c53a324b72555cd0b3b36d3bdf82de4ccc',
    CAPTURE+'/semantic-review.json': 'd187bb0f469a97924bcb98bc8d64949bbba6f305d23a45c0ce9edc09abf50d24',
    SECOND+'/independent-review.json': '115dad89e56f9ebf2cc0d37a67468bc6d59b585a5abb36ab79264bb9a9fd31d7',
    SECOND+'/resolution-evidence.json': 'a53e829885284c1dd99df7025f50dc57a2c2cf2a659517f34dba5b5d84c33c67',
}
CODE_PINS = {
    'tools/keyword-system/keyword_audit.py': 'ef6ce0535c8ce5cd83f50e169d26328cd763a236cfcbee4919f927c6fd8cd8d6',
    'tools/keyword-system/keyword_text_compatibility.py': '723988151adfeae8f2a6efeb073a399451eefcbfe1d3f8c311e0e168fd56763f',
}
BASE_SHA256 = '954f8143a49d050d2f86f15a9dda52fb460eae0de75a25b1ebef1eb9e5d7c5d0'
REVIEW_PIN = 'ab1bfc9dfc73927c487e0d6abef78ec50472cb801773d6d94912ffc59f2c94b0'
OUTPUT_PINS = {
    'index.json': '9049c82eadd0a1a06af7c25b4daa833827a1efb6beee54f02dabb2c4f4666edd',
    'cohort-report.json': 'd98018263e3fea19bdfc254dac7d07bb024bd20222ab305b93cc9f931f439553',
    'library-report.json': '6ea26269b1e8a59e8dd593cad6e2a14b14bada8d1e4466c3355bafc24b11880c',
    'research-pool-allocation.json': '1cf6d2e6e3aae0ea6f9a598b48eafd80c2e828e66eb2e3a111958599971d50a5',
}
STAGE_KEY = 'ofqual_append_only_state'
SOURCE_ID = 'OFQUAL-QUALIFICATIONS-20261111'
INTENT = 'EXPLICIT_OCCUPATIONAL_STUDY_OR_ASSESSMENT_RESEARCH'
LIMITS = ('human_review_verified', 'exclusion_approval_granted', 'live_binding_verified',
          'production_authorized', 'google_platform_validation_performed')


def implementation_binding(root):
    for relative, pin in CODE_PINS.items():
        first.need(hashlib.sha256((Path(root)/relative).read_bytes()).hexdigest() == pin,
                   'OFQUAL_CURRENT_IMPLEMENTATION_CHANGED')
    tree = ast.parse((Path(root)/'tools/keyword-system/keyword_audit.py').read_text(encoding='utf-8'))
    functions = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode('utf-8')).hexdigest()
                 for node in tree.body if isinstance(node, ast.FunctionDef) and
                 node.name in {'normalize', 'tokens', 'negative_matches'}}
    first.need(len(functions) == 3, 'OFQUAL_MATCH_IMPLEMENTATION_MISSING')
    return {'current_code_sha256': dict(CODE_PINS), 'function_ast_sha256': functions,
            'historical_normalizer_sha256': '0cbbc8965ed891208066887eeaca0b011092efa6668af161bab3a2feb76454d9',
            'historical_file_hash_is_dated_evidence_not_current_code_pin': True}


def load_sources(root):
    docs = {p: first.pinned(root, p, pin) for p, pin in SOURCE_PINS.items()}
    ofqual_discovery.verify_capture(Path(root)/CAPTURE,
        {name: SOURCE_PINS[CAPTURE+'/'+name] for name in ('capture.json', 'qualifications.json')})
    projection = docs[CAPTURE+'/qualifications.json']
    original = docs[CAPTURE+'/semantic-review.json']
    second = docs[SECOND+'/independent-review.json']
    rows = {r['source_record_ordinal']: r for r in projection['records']}
    groups = {g['group_id']: g for g in original['groups']}
    first.need(len(groups) == 311 and len(rows) == 338 and projection['source_record_count'] == 53175,
               'OFQUAL_SOURCE_POPULATION_CHANGED')
    regrouped = defaultdict(list)
    for row in projection['records']:
        regrouped[ka.normalize(row['values']['Qualification Title'])].append(row)
    first.need(len(regrouped) == 311 and set(regrouped) ==
               {g['normalized_title_key'] for g in groups.values()}, 'OFQUAL_GROUP_MAP_CHANGED')
    for group in groups.values():
        source = regrouped[group['normalized_title_key']]
        first.need(group['literal_titles'] == list(dict.fromkeys(r['values']['Qualification Title'] for r in source)) and
                   len(group['source_occurrences']) == len(source), 'OFQUAL_LITERAL_GROUP_CHANGED')
        for occurrence, row in zip(group['source_occurrences'], source):
            expected = {'qualification_number': row['values']['Qualification Number'],
                'source_record_ordinal': row['source_record_ordinal'],
                'source_line_start': row['source_line_start'], 'source_line_end': row['source_line_end'],
                'literal_title_index': group['literal_titles'].index(row['values']['Qualification Title']),
                'published_status': row['values']['Qualification Status']}
            first.need(occurrence == expected, 'OFQUAL_OCCURRENCE_CHANGED')
    peers = {g['group_id']: g for g in second['groups']}
    first.need(len(peers) == 62 and set(peers) == {k for k,g in groups.items()
               if g['disposition'] != 'HOLD'}, 'OFQUAL_SECOND_REVIEW_COVERAGE_CHANGED')
    proposed = {k for k,g in peers.items()
                if g['reviewed_disposition'] == 'PROPOSE_LATER_EXACT_HIGH_PENDING_RESEARCH'}
    first.need(len(proposed) == 58 and set(peers)-proposed ==
               {'OFQUAL-TITLE-069', 'OFQUAL-TITLE-070', 'OFQUAL-TITLE-122', 'OFQUAL-TITLE-170'},
               'OFQUAL_SEMANTIC_HOLDS_CHANGED')
    for identity, group in peers.items():
        first.need(group['source_occurrences'] == groups[identity]['source_occurrences'] and
                   group['literal_titles'] == groups[identity]['literal_titles'], 'OFQUAL_REVIEW_SOURCE_CHANGED')
    selected = sorted(k for k in proposed if not compatibility.profile_text(
        groups[k]['proposed_literal_title'])['original']['reason_codes'])
    first.need(len(selected) == 42 and sum(len(groups[k]['source_occurrences']) for k in selected) == 50,
               'OFQUAL_COMPATIBLE_SELECTION_CHANGED')
    context = first.pinned(root, first.FOLDER+'/service-context.json', first.CONTEXT_PIN)
    registry = first.pinned(root, first.REGISTRY, first.PINS[first.REGISTRY])
    return {'groups': groups, 'rows': rows, 'selected': selected, 'context': context,
            'registry': registry, 'implementation': implementation_binding(root), 'projection': projection}


def review_subject(review, material):
    return stage.digest({'review': {k:v for k,v in review.items() if k != 'subject_sha256'},
        'context': material['context'], 'registry': material['registry'], 'source_pins': SOURCE_PINS,
        'implementation': material['implementation'], 'base_sha256': BASE_SHA256})


def validate_review(review, material, when):
    required = {'version', 'scope', 'reviewer', 'reviewer_kind', 'reviewed_on', 'valid_until',
        'validity_basis', 'campaign_key', 'landing_page_id', 'selected_group_ids', 'held_groups',
        'source_pins', 'implementation', 'base_sha256', 'source_identity_limits',
        'semantic_rationale', 'variant_review', 'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review) == required, 'OFQUAL_REVIEW_SCHEMA')
    first.need(type(review['version']) is int and review['version'] == 1 and
        review['scope'] == 'AI_REVIEWED_OFFICIAL_REFERENCE_RESEARCH_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[key] is False for key in LIMITS), 'OFQUAL_REVIEW_AUTHORITY')
    campaign = next(r for r in material['registry'] if r['campaign_key'] == first.CAMPAIGN)
    first.need(review['campaign_key'] == campaign['campaign_key'] == 'BSRE-C0301' and
        review['landing_page_id'] == campaign['landing_page_id'] == 'BSRE-LP0301' and
        campaign['family_code'] == 'RNT' and campaign['family_slot'] == 1 and
        campaign['actual_url'] is None and campaign['google_campaign_id'] is None and
        campaign['release_approved'] is False, 'OFQUAL_SCOPE_CHANGED')
    context = material['context']
    first.need(context['context_kind'] == 'PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        context['source_url'] == 'https://blackswanrealestate.ae/enquire/rent/' and
        all(context[k] is False for k in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed', 'live_campaign_mapping_assigned')),
        'OFQUAL_CONTEXT_AUTHORITY')
    first.need(review['selected_group_ids'] == material['selected'] and
        type(review['held_groups']) is dict and set(review['held_groups']) ==
        set(material['groups'])-set(material['selected']) and
        all(type(reason) is str and reason.strip() for reason in review['held_groups'].values()),
        'OFQUAL_REVIEW_PARTITION_CHANGED')
    first.need(review['source_pins'] == SOURCE_PINS and review['implementation'] == material['implementation'] and
        review['base_sha256'] == BASE_SHA256 and
        review['variant_review'] == {'equal_token_current_peers': 0, 'google_equivalence_verified': False,
            'counts_distinct_concepts': False, 'all_original_semantic_holds_retained': True} and
        all(type(review[k]) is str and review[k].strip() for k in
            ('semantic_rationale', 'source_identity_limits')), 'OFQUAL_REVIEW_BINDINGS_CHANGED')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        start <= when <= end and end-start == timedelta(days=30) and
        context['observed_date_dubai'] <= review['reviewed_on'] and review['validity_basis'] == prior.prior.VALIDITY,
        'OFQUAL_REVIEW_DATES')
    first.need(review['subject_sha256'] == review_subject(review, material), 'OFQUAL_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN) == 64, 'OFQUAL_REVIEW_UNREGISTERED')
    review = first.pinned(root, FOLDER+'/review.json', REVIEW_PIN)
    validate_review(review, material, when)
    return dict(material, review=review)


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records', 'archived_records', 'protected_queries', 'sources',
                                    'campaigns', 'campaign_context')) == (10610, 18, 15899, 21, 360, 1) and
        base['campaigns'] == material['registry'], 'OFQUAL_PRIOR_BASE_CHANGED')
    current = {ka.normalize(r['original_text']) for r in base['records']+base['archived_records']}
    protected = {ka.normalize(r['text']) for r in base['protected_queries']}
    bags = {tuple(sorted(ka.tokens(key))) for key in current | protected}
    for group in material['groups'].values():
        first.need(group['normalized_title_key'] not in current | protected, 'OFQUAL_FRESH_MEMBERSHIP_CHANGED')
    selected_bags = []
    held_bags = {tuple(sorted(ka.tokens(group['normalized_title_key'])))
                 for identity, group in material['groups'].items() if identity not in material['selected']}
    for identity in material['selected']:
        bag = tuple(sorted(ka.tokens(material['groups'][identity]['normalized_title_key'])))
        first.need(bag not in bags and bag not in held_bags, 'OFQUAL_PRIOR_VARIANT_HOLD')
        selected_bags.append(bag)
    first.need(len(selected_bags) == len(set(selected_bags)), 'OFQUAL_SELECTED_VARIANT_HOLD')
    # Existing research remains a historical count; independently expose known
    # incompatibility rather than silently grandfathering it into the new stage.
    for row in base['records']+base['archived_records']:
        profile = compatibility.profile_text(row['original_text'], canonical_text=row['normalized_text'])
        first.need(not profile['original']['reason_codes'] and not profile['provided_canonical']['reason_codes'],
            'OFQUAL_PRIOR_TEXT_COMPATIBILITY_REVIEW_REQUIRED')


def build_cohort(base, material):
    review = material['review']; records = []
    for identity in material['selected']:
        group = material['groups'][identity]; text = group['proposed_literal_title']
        first.need(text in group['literal_titles'] and ka.normalize(text) == group['normalized_title_key'] and
            all(not compatibility.profile_text(literal)['original']['reason_codes']
                for literal in group['literal_titles']), 'OFQUAL_SELECTED_LITERAL_CHANGED')
        occurrences = []
        for ref in group['source_occurrences']:
            row = material['rows'][ref['source_record_ordinal']]
            occurrences.append({'batch': SOURCE_ID, 'source_line': ref['source_line_start'],
                'file': CAPTURE+'/qualifications.json', 'sha256': SOURCE_PINS[CAPTURE+'/qualifications.json'],
                'source_sha256': material['projection']['source_sha256'], 'group_id': identity,
                **deepcopy(ref), 'values': deepcopy(row['values']), 'review_file': FOLDER+'/review.json',
                'review_sha256': REVIEW_PIN, 'original_semantic_review_file': CAPTURE+'/semantic-review.json',
                'original_semantic_review_sha256': SOURCE_PINS[CAPTURE+'/semantic-review.json'],
                'independent_review_file': SECOND+'/independent-review.json',
                'independent_review_sha256': SOURCE_PINS[SECOND+'/independent-review.json']})
        adapted = {'normalized_text': group['normalized_title_key'], 'disposition': 'NEGATIVE_EXACT_REVIEW',
            'original_forms': [text], 'assessment': {'intent': INTENT, 'negative_scope_proposal':
                {'type': 'CAMPAIGN', 'campaign_keys': [], 'approved': False, 'match_type': 'EXACT'}}}
        record = first.make_record(adapted, review, occurrences, source_id=SOURCE_ID,
            source_reference=CAPTURE+'/qualifications.json#'+identity, review_folder=FOLDER,
            allowed_intents={INTENT})
        record['evidence_ref'] = FOLDER+'/review.json#'+identity
        records.append(record)
    records.sort(key=lambda row: row['normalized_text'])
    source = {'source_id': SOURCE_ID, 'kind': 'official_reference', 'approved_for_research': True,
        'evidence_ref': CAPTURE+'/capture.json', 'observed_on': '2026-11-11', 'valid_until': review['valid_until'],
        'research_use_basis': 'OWNER_AUTHORIZED_RESEARCH_AND_PINNED_OFFICIAL_QUALIFICATION_REGISTER',
        'served_query_or_current_performance_claimed': False}
    protections = [{'query_id': 'BSRE-Q-'+hashlib.sha256(group['normalized_title_key'].encode('utf-8')).hexdigest()[:24],
        'text': group['normalized_title_key'], 'campaign_keys': [first.CAMPAIGN],
        'services': ['residential_rental'], 'must_serve': True, 'evidence_ref': FOLDER+'/review.json#'+identity,
        'reviewed_on': review['reviewed_on'], 'valid_until': review['valid_until']}
        for identity, group in sorted(material['groups'].items()) if identity in review['held_groups']]
    return {'records': records, 'sources': [source], 'protected_queries': [],
            'campaigns': base['campaigns'], 'campaign_context': base['campaign_context']}, protections


def extend(base, root, when):
    material = load_reviewed(root, when)
    verify_base(base, material)
    cohort, protections = build_cohort(base, material)
    return stage.extend(base, cohort, protections, expected_base_sha256=BASE_SHA256, stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result = stage.checked_audit(inputs, when)
    state = inputs[STAGE_KEY]; n = state['retained_records']
    new = inputs['records'][n:]
    index = {'version': 1, 'scope': 'APPEND_ONLY_OFQUAL_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index': {'file': prior.FOLDER+'/index.json', 'sha256': prior.INDEX_PIN},
        'review': {'file': FOLDER+'/review.json', 'sha256': REVIEW_PIN}, 'source_pins': dict(SOURCE_PINS),
        'implementation': material['implementation'], 'base_state': state,
        'records_sha256': stage.digest(inputs['records']), 'archived_sha256': stage.digest(inputs['archived_records']),
        'protected_sha256': stage.digest(inputs['protected_queries']), 'sources_sha256': stage.digest(inputs['sources']),
        'additional_records_sha256': stage.digest(new), 'complete_inputs_sha256': stage.digest(inputs),
        'additional_eligible_keyword_ids': [r['keyword_id'] for r in new],
        'additional_protected_query_ids': [r['query_id'] for r in inputs['protected_queries'][state['retained_protections']:]],
        'historical_records_rewritten': False, 'exclusion_approval_granted': False, 'deployment_authorized': False}
    cohort = {'scope': 'AI_REVIEWED_OFFICIAL_QUALIFICATION_TITLES_NOT_SEARCH_DEMAND',
        'source_groups': 311, 'source_occurrences': 338, 'selected_groups': len(new),
        'retained_new_occurrences': sum(len(r['provenance_occurrences']) for r in new),
        'held_groups': len(material['review']['held_groups']),
        'held_occurrences': sum(len(material['groups'][k]['source_occurrences']) for k in material['review']['held_groups']),
        'record_bodies_sha256': stage.digest(new), 'source_pins': dict(SOURCE_PINS),
        'review': {'file': FOLDER+'/review.json', 'sha256': REVIEW_PIN},
        **{k: False for k in LIMITS}, 'search_demand_verified': False}
    summary = {'scope': 'CURRENT_RESEARCH_AFTER_OFQUAL_APPEND_ONLY_REVIEW',
        **{k:result[k] for k in ('as_of', 'input_rows', 'distinct_nonblank_phrases', 'reviewed_eligible_rows',
            'excluded_rows', 'approved_exclusion_rows', 'target', 'deficit', 'exact_target_pass', 'structural_pass',
            'deployment_export_allowed', 'production_writes_available', 'positive_library_coverage_verified',
            'protected_queries_indexed')}, 'computed_conflicts': len(result['protected_conflicts']),
        'prior_rows': n, 'new_rows': len(new), 'archived_original_rows': len(inputs['archived_records']),
        'source_occurrences_retained_in_current_records': sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'new_proposal_holds': len(material['review']['held_groups']), 'historical_records_rewritten': False,
        'human_review_verified': False, 'live_campaign_mapping_verified': False, 'release_authorized': False,
        'text_compatibility_is_local_screen_not_platform_acceptance': True}
    previous = first.pinned(root, prior.FOLDER+'/research-pool-allocation.json', prior.ALLOCATION_PIN)
    first.need(previous['total_target'] == 14000 and previous['total_admitted'] == n and
        sum(previous['admitted'].values()) == n and sum(previous['targets'].values()) == 14000,
        'OFQUAL_ALLOCATION_BASE_CHANGED')
    admitted = dict(previous['admitted']); admitted['ACADEMIC'] += len(new)
    remaining = {k: previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v >= 0 for v in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']), 'OFQUAL_ALLOCATION_COUNTS')
    allocation = {'version': 1, 'scope': 'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref': first.MASTER, 'previous_allocation_ref': prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256': prior.ALLOCATION_PIN, 'targets': previous['targets'],
        'before': previous['targets'], 'target_transfer': None, 'held_deduction': {},
        'new_rows': {'ACADEMIC': len(new)}, 'admitted': admitted, 'remaining': remaining,
        'total_target': 14000, 'total_admitted': sum(admitted.values()), 'total_remaining': sum(remaining.values()),
        'basis': 'Preserve all prior bodies and pool targets; append only source-bound reviewed complete qualification literals.',
        'owner_approval_claimed': False, 'media_budget_changed': False, 'exclusion_approval_granted': False}
    return {'index.json': index, 'cohort-report.json': cohort,
            'library-report.json': dict(summary, as_of=material['review']['reviewed_on']),
            'research-pool-allocation.json': allocation}, summary


def build_outputs(base, root=first.ROOT, when=None):
    """Explicit generation using caller-fresh base; returns (inputs, four docs)."""
    when = first.dubai_date() if when is None else when
    inputs = extend(base, root, when)
    documents, _ = _outputs(inputs, load_reviewed(root, when), root, when)
    return inputs, documents


def check_saved(inputs, root, when):
    # Re-read source/review/code and reconstruct every tail; hashes alone are
    # insufficient because resealed derived records are not review authority.
    base = stage.recover_base(inputs, stage_key=STAGE_KEY)
    expected = extend(base, root, when)
    first.need(first.canonical(inputs) == first.canonical(expected), 'OFQUAL_DERIVED_BODIES_CHANGED')
    documents, summary = _outputs(inputs, load_reviewed(root, when), root, when)
    stage.check_documents(root, FOLDER, OUTPUT_PINS, documents)
    return dict(summary, passed=True, index_verified=True, current_index_file=FOLDER+'/index.json', release_held=True)
