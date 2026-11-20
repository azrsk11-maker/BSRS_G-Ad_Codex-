"""Source-bound append-only apprenticeship research; no live or approval writer.

Callers must reconstruct the complete pre-stage history freshly. A saved index
fingerprint is only an expected body binding, never evidence of freshness.
"""
from copy import deepcopy
from datetime import date, timedelta
import hashlib

import append_only_admission as stage
import entertainment_admission as prior
from followup_admission import VALIDITY
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first

FOLDER = 'docs/audit/keyword-negative-apprenticeship-admission-2026-11-12'
CAPTURE = 'docs/audit/keyword-apprenticeship-feasibility-2026-11-12'
SECOND = 'docs/audit/keyword-apprenticeship-review-2026-11-12'
SOURCE_PINS = {
    CAPTURE+'/source.json': 'b20eac063ead4bb4882d8535a396a320e2336673941a509a10fa570cf54bc1fb',
    CAPTURE+'/projection.json': '1f5d3a3d6baf3c0b2d1e82c18cf2552b6572687a9741311a3449916f6ea7122f',
    SECOND+'/independent-review.json': '6ad55fadbbcd94f5e371159ecf5c605f161a391746628b184d4c3ce3184d421b',
}
BASE_SHA256 = '6732c169d372828ac96078bfa4b17dc9c9dd571e6b01b5b717d096b2c534a5ea'
REVIEW_PIN = 'bb0fc935b24f263b24e7803b39ef5e5df83c6b042cf77f82e7293d0ad2bfc86b'
OUTPUT_PINS = {'cohort-report.json': '9da535240733bb47e27f72f7ab5d52aa75edd6ccbec55e32e38cdad9381bd842', 'index.json': '9975ed7062101070b410258913392e15669006abbe596baa36da057c0212372a', 'library-report.json': '31823e15b154608a1e41480226c11b82789e00cbfc4fc6553455959b17398051', 'research-pool-allocation.json': '7081460c15662dd875602992c5d2fc2ec991bf63a9e1e5ed283a7e81e289bb37'}
STAGE_KEY = 'apprenticeship_append_only_state'
SOURCE_ID = 'PRIMARY-APPRENTICESHIP-TITLES-20261112'
INTENT = 'EXPLICIT_OCCUPATIONAL_APPRENTICESHIP_RESEARCH'
SELECTED = list(range(2, 10))
LIMITS = prior.LIMITS
VARIANTS = {'selected_ordinals': SELECTED, 'supporting_alias_ordinal': 1,
    'representative_ordinal': 7, 'supporting_alias_is_exact_occurrence': False,
    'supporting_alias_is_separate_negative': False, 'supporting_alias_is_protected_query': False,
    'google_equivalence_verified': False, 'counts_distinct_concepts': False,
    'external_closed_alias_semantics_verified': False,
    'lexical_checks': ['normalized_exact', 'ordered_tokens', 'equal_token_bag', 'closed_alphanumeric_string']}


def implementation_binding(root):
    return prior.implementation_binding(root)


def load_sources(root):
    docs = {p: first.pinned(root, p, pin) for p, pin in SOURCE_PINS.items()}
    source, projection, peer = (docs[CAPTURE+'/source.json'], docs[CAPTURE+'/projection.json'],
                                docs[SECOND+'/independent-review.json'])
    rows = {r['ordinal']: r for r in projection['rows']}
    reviewed = {r['ordinal']: r for r in peer['rows']}
    first.need(list(rows) == list(reviewed) == list(range(1, 10)) and
        projection['source_sha256'] == SOURCE_PINS[CAPTURE+'/source.json'] and
        projection['captured_literals'] == source['counts']['title_literals_captured'] == 9 and
        source['counts']['primary_pages_rechecked'] == len(source['source_pages']) == 6 and
        source['observed_search_queries'] is False and source['keyword_planner_source'] is False and
        source['metrics_status'] == 'NOT_OBSERVED_UNKNOWN' and
        peer['independent_human_review'] is False, 'APPRENTICESHIP_SOURCE_IDENTITY_CHANGED')
    first.need(all(source['counts'][k] == projection[k] == 0 for k in
        ('reviewed_for_admission', 'admitted', 'approved', 'deployed')) and
        all(peer['counts'][k] == 0 for k in ('full_admission_audits_completed','admitted','approved','deployed')),
        'APPRENTICESHIP_SOURCE_AUTHORITY_CHANGED')
    for page in source['source_pages']:
        literals = [rows[i]['original_text'] for i in page['ordinals']]
        excerpt = ''.join(t+'\n' for t in literals).encode('utf-8')
        first.need(literals == page['verbatim_title_excerpts'] and
            len(excerpt) == page['retained_title_excerpt_utf8_lf_bytes'] and
            hashlib.sha256(excerpt).hexdigest() == page['retained_title_excerpt_sha256'],
            'APPRENTICESHIP_EXCERPT_CHANGED')
        for ordinal in page['ordinals']:
            row, assessment = rows[ordinal], reviewed[ordinal]
            text, key = row['original_text'], ka.normalize(row['original_text'])
            identity = 'BSRE-N-'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]
            first.need(row['source_url'] == page['url'] == assessment['source_url'] and
                row['source_page_id'] == page['source_page_id'] == assessment['source_page_id'] and
                assessment['original_text'] == text and row['normalized_text'] ==
                assessment['normalized_text'] == key and row['candidate_identity'] ==
                assessment['candidate_identity_from_feasibility'] == identity and
                assessment['literal_sha256']['value'] == hashlib.sha256(text.encode('utf-8')).hexdigest() and
                assessment['complete_literal_read'] is True and
                assessment['source_title_confirmed_verbatim_on_primary_page'] is True and
                assessment['source_intent']['category'] == 'EXPLICIT_OCCUPATIONAL_APPRENTICESHIP' and
                assessment['source_intent']['observed_search_query'] is False and
                all(row[k] is None for k in ('observed_query','volume','cpc','competition')) and
                row['admission_state'] == assessment['admission_state'] == 'NOT_ADMITTED' and
                all(assessment[k] is False for k in ('full_admission_audit_completed',
                    'human_review_completed','exclusion_approval_granted','deployment_authorized')),
                'APPRENTICESHIP_LITERAL_CHANGED')
            first.need(not compatibility.profile_text(text)['original']['reason_codes'] and
                assessment['text_compatibility']['within_both_local_limits'] is True and
                assessment['text_compatibility']['character_count'] == len(text) and
                assessment['text_compatibility']['word_count'] == len(text.split()),
                'APPRENTICESHIP_TEXT_COMPATIBILITY_HOLD')
            selected = ordinal in SELECTED
            first.need(assessment['variant_review']['separately_proposed_candidate'] is selected and
                assessment['variant_review']['representative_ordinal'] == (7 if ordinal == 1 else ordinal) and
                assessment['variant_review']['wording_manufactured'] is False and
                assessment['proposed_decision'] == ('PROVISIONAL_COMPLETE_LITERAL_FOR_ROOT_EVALUATION'
                    if selected else 'SOURCE_OCCURRENCE_VARIANT_ONLY_NOT_SEPARATE_PROPOSAL'),
                'APPRENTICESHIP_SOURCE_PARTITION_CHANGED')
    route = peer['town_planner_route_resolution']
    first.need(route['ordinals'] == [1,7] and route['representative_ordinal'] == 7 and
        route['supporting_source_occurrence_ordinal'] == 1 and
        route['resolution'] == 'ONE_ROUTE_GROUP_ONE_PROVISIONAL_CANDIDATE' and
        route['evidence'][1]['standard_reference'] == 'ST0536' and
        route['evidence'][1]['standard_level'] == 7 and route['evidence'][1]['lars_code'] == 424 and
        rows[1]['normalized_text'] != rows[7]['normalized_text'], 'APPRENTICESHIP_ALIAS_CHANGED')
    first.need({b['file']: b['sha256'] for b in peer['input_bindings']} ==
        {p: pin for p,pin in SOURCE_PINS.items() if p.startswith(CAPTURE+'/')},
        'APPRENTICESHIP_INDEPENDENT_INPUT_CHANGED')
    return {'rows': rows, 'source': source, 'independent': peer, 'selected': list(SELECTED),
        'context': first.pinned(root, first.FOLDER+'/service-context.json', first.CONTEXT_PIN),
        'registry': first.pinned(root, first.REGISTRY, first.PINS[first.REGISTRY]),
        'implementation': implementation_binding(root)}


def review_subject(review, material):
    return stage.digest({'review': {k:v for k,v in review.items() if k != 'subject_sha256'},
        'context': material['context'], 'registry': material['registry'], 'source_pins': SOURCE_PINS,
        'implementation': material['implementation'], 'base_sha256': BASE_SHA256})


def make_review(base, root=first.ROOT, when=None):
    """Return a review over caller-fresh complete history; never write or approve."""
    when = first.dubai_date() if when is None else when
    material = load_sources(root)
    verify_base(base, material)
    review = {'version': 1, 'scope': 'AI_REVIEWED_APPRENTICESHIP_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'reviewer': first.REVIEWER, 'reviewer_kind': 'CODEX_AI_NOT_HUMAN',
        'reviewed_on': when.isoformat(), 'valid_until': (when+timedelta(days=30)).isoformat(),
        'validity_basis': VALIDITY, 'campaign_key': first.CAMPAIGN, 'landing_page_id': first.PAGE,
        'selected_ordinals': list(SELECTED), 'held_ordinals': [], 'source_pins': dict(SOURCE_PINS),
        'implementation': material['implementation'], 'base_sha256': BASE_SHA256,
        'source_identity_limits': 'Published full apprenticeship titles, not observed queries, demand, vacancies, metrics or UAE credential recognition. Excerpt hashes do not archive remote pages.',
        'semantic_rationale': 'The independent complete-literal review supports occupational training intent for planned residential rental intake research only. Preserve property-service and guidance intent. Ordinal 1 supports the ST0536/LARS424 route represented by ordinal 7; it adds no negative, exact occurrence or protection.',
        'variant_review': deepcopy(VARIANTS), 'supporting_alias': alias_evidence(material),
        **{key: False for key in LIMITS}}
    review['subject_sha256'] = review_subject(review, material)
    validate_review(review, material, when)
    return review


def alias_evidence(material):
    row = material['rows'][1]
    return {'source_ordinal': 1, 'representative_ordinal': 7,
        'representative_candidate_identity': material['rows'][7]['candidate_identity'],
        'alias_candidate_identity_not_admitted': row['candidate_identity'],
        'original_text': row['original_text'], 'source_url': row['source_url'],
        'source_file': CAPTURE+'/projection.json', 'source_sha256': SOURCE_PINS[CAPTURE+'/projection.json'],
        'independent_review_file': SECOND+'/independent-review.json',
        'independent_review_sha256': SOURCE_PINS[SECOND+'/independent-review.json'],
        'relationship': 'SEMANTIC_SAME_ROUTE_SUPPORT_NOT_EXACT_LITERAL_OCCURRENCE',
        'adds_record': False, 'adds_exact_occurrence': False, 'adds_protection': False}


def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_ordinals','held_ordinals','source_pins','implementation',
        'base_sha256','source_identity_limits','semantic_rationale','variant_review','supporting_alias',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review) == required and type(review['version']) is int and
        review['version'] == 1 and review['scope'] == 'AI_REVIEWED_APPRENTICESHIP_RESEARCH_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'APPRENTICESHIP_REVIEW_AUTHORITY')
    campaign = next(r for r in material['registry'] if r['campaign_key'] == first.CAMPAIGN)
    context = material['context']
    first.need(review['campaign_key'] == campaign['campaign_key'] == 'BSRE-C0301' and
        review['landing_page_id'] == campaign['landing_page_id'] == 'BSRE-LP0301' and
        campaign['family_code'] == 'RNT' and campaign['family_slot'] == 1 and
        campaign['actual_url'] is None and campaign['google_campaign_id'] is None and
        campaign['release_approved'] is False and
        context['context_kind'] == 'PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        context['source_url'] == 'https://blackswanrealestate.ae/enquire/rent/' and
        all(context[k] is False for k in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed','live_campaign_mapping_assigned')),
        'APPRENTICESHIP_SCOPE_CHANGED')
    first.need(review['selected_ordinals'] == SELECTED and
        all(type(i) is int for i in review['selected_ordinals']) and review['held_ordinals'] == [] and
        review['variant_review'] == VARIANTS and review['supporting_alias'] == alias_evidence(material) and
        review['source_pins'] == SOURCE_PINS and review['implementation'] == material['implementation'] and
        review['base_sha256'] == BASE_SHA256 and
        all(type(review[k]) is str and review[k].strip() for k in ('semantic_rationale','source_identity_limits')),
        'APPRENTICESHIP_REVIEW_BINDINGS_CHANGED')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        start <= when <= end and end-start == timedelta(days=30) and
        material['source']['capture_date_dubai'] <= material['independent']['review_date_dubai'] == review['reviewed_on'] and
        context['observed_date_dubai'] <= review['reviewed_on'] and review['validity_basis'] == VALIDITY,
        'APPRENTICESHIP_REVIEW_DATES')
    first.need(review['subject_sha256'] == review_subject(review, material),
        'APPRENTICESHIP_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN) == 64, 'APPRENTICESHIP_REVIEW_UNREGISTERED')
    review = first.pinned(root, FOLDER+'/review.json', REVIEW_PIN)
    validate_review(review, material, when)
    return dict(material, review=review)


def _closed_string(text):
    return ''.join(c for c in ka.normalize(text) if c.isalnum())


def _verify_membership(base, material):
    """Fresh complete-body lexical reconciliation, including the uncounted alias."""
    texts = [r['original_text'] for r in base['records']+base['archived_records']]
    texts += [r['text'] for r in base['protected_queries']]
    current = {ka.normalize(t) for t in texts}
    ordered = {tuple(ka.tokens(t)) for t in texts}
    bags = {tuple(sorted(ka.tokens(t))) for t in texts}
    closed = {_closed_string(t) for t in texts}
    seen_keys, seen_ordered, seen_bags, seen_closed = set(), set(), set(), set()
    for row in material['rows'].values():
        text = row['original_text']; key = ka.normalize(text); words = tuple(ka.tokens(text))
        bag, compact = tuple(sorted(words)), _closed_string(text)
        first.need(key not in current and words not in ordered and bag not in bags and compact not in closed,
            'APPRENTICESHIP_FRESH_MEMBERSHIP_CHANGED')
        first.need(key not in seen_keys and words not in seen_ordered and bag not in seen_bags and
            compact not in seen_closed, 'APPRENTICESHIP_WITHIN_CAPTURE_VARIANT_CHANGED')
        seen_keys.add(key); seen_ordered.add(words); seen_bags.add(bag); seen_closed.add(compact)
        first.need(not compatibility.profile_text(text)['original']['reason_codes'],
            'APPRENTICESHIP_TEXT_COMPATIBILITY_HOLD')


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources',
                                     'campaigns','campaign_context')) == (10955,18,16383,23,360,1) and
        sum(len(r['provenance_occurrences']) for r in base['records']) == 11161 and
        base['campaigns'] == material['registry'], 'APPRENTICESHIP_PRIOR_BASE_CHANGED')
    _verify_membership(base, material)


def build_cohort(base, material):
    review, records = material['review'], []
    for ordinal in SELECTED:
        row = material['rows'][ordinal]; text = row['original_text']; key = ka.normalize(text)
        occurrence = {'batch': SOURCE_ID, 'source_ordinal': ordinal,
            'file': CAPTURE+'/projection.json', 'sha256': SOURCE_PINS[CAPTURE+'/projection.json'],
            'source_file': CAPTURE+'/source.json', 'source_sha256': SOURCE_PINS[CAPTURE+'/source.json'],
            'source_page_id': row['source_page_id'], 'source_url': row['source_url'],
            'source_section': row['source_section'], 'original_text': text,
            'capture_kind': 'primary_published_apprenticeship_title',
            'review_file': FOLDER+'/review.json', 'review_sha256': REVIEW_PIN,
            'independent_review_file': SECOND+'/independent-review.json',
            'independent_review_sha256': SOURCE_PINS[SECOND+'/independent-review.json']}
        adapted = {'normalized_text': key, 'disposition': 'NEGATIVE_EXACT_REVIEW', 'original_forms': [text],
            'assessment': {'intent': INTENT, 'negative_scope_proposal':
                {'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record = first.make_record(adapted, review, [occurrence], source_id=SOURCE_ID,
            source_reference=CAPTURE+'/projection.json#ordinal='+str(ordinal), review_folder=FOLDER,
            allowed_intents={INTENT})
        record['evidence_ref'] = FOLDER+'/review.json#ordinal='+str(ordinal)
        if ordinal == 7:
            record['supporting_semantic_alias_evidence'] = alias_evidence(material)
        records.append(record)
    records.sort(key=lambda row: row['normalized_text'])
    source = {'source_id': SOURCE_ID, 'kind':'official_reference', 'approved_for_research': True,
        'evidence_ref': CAPTURE+'/source.json', 'observed_on': material['source']['capture_date_dubai'],
        'valid_until': review['valid_until'], 'capture_kind':'primary_published_apprenticeship_titles',
        'research_use_basis':'OWNER_AUTHORIZED_RESEARCH_AND_PINNED_PRIMARY_TITLES_WITH_INDEPENDENT_AI_REVIEW',
        'metrics_captured': False, 'served_query_or_current_performance_claimed': False}
    # A corroborating alternate title is neither a ninth negative nor evidence
    # that property services must serve it. No must_serve protection is invented.
    return {'records': records, 'sources': [source], 'protected_queries': [],
        'campaigns': base['campaigns'], 'campaign_context': base['campaign_context']}, []


def extend(base, root, when):
    material = load_reviewed(root, when)
    verify_base(base, material)
    cohort, protections = build_cohort(base, material)
    return stage.extend(base, cohort, protections, expected_base_sha256=BASE_SHA256, stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result = stage.checked_audit(inputs, when)
    state = inputs[STAGE_KEY]; n = state['retained_records']; new = inputs['records'][n:]
    first.need(len(new) == sum(len(r['provenance_occurrences']) for r in new) == 8 and
        len(inputs['protected_queries']) == state['retained_protections'] and
        material['rows'][1]['candidate_identity'] not in {r['keyword_id'] for r in new},
        'APPRENTICESHIP_ALIAS_COUNT_CHANGED')
    index = {'version':1,'scope':'APPEND_ONLY_APPRENTICESHIP_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[], 'supporting_semantic_aliases':[alias_evidence(material)],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort = {'scope':'AI_REVIEWED_PRIMARY_APPRENTICESHIP_TITLES_NOT_SEARCH_DEMAND',
        'captured_literal_occurrences':9,'selected_new_rows':8,'retained_new_exact_occurrences':8,
        'supporting_semantic_aliases_not_exact_occurrences':1,'held_source_literals':0,
        'additional_protected_queries':0,'record_bodies_sha256':stage.digest(new),
        'source_pins':dict(SOURCE_PINS),'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},
        'google_equivalence_verified':False,'counts_distinct_concepts':False,'metrics_captured':False,
        'search_demand_verified':False,**{k:False for k in LIMITS}}
    summary = {'scope':'CURRENT_RESEARCH_AFTER_APPRENTICESHIP_APPEND_ONLY_REVIEW',
        **{k:result[k] for k in ('as_of','input_rows','distinct_nonblank_phrases','reviewed_eligible_rows',
            'excluded_rows','approved_exclusion_rows','target','deficit','exact_target_pass','structural_pass',
            'deployment_export_allowed','production_writes_available','positive_library_coverage_verified',
            'protected_queries_indexed')},'computed_conflicts':len(result['protected_conflicts']),
        'prior_rows':n,'new_rows':len(new),'archived_original_rows':len(inputs['archived_records']),
        'source_occurrences_retained_in_current_records':sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'captured_new_literals':9,'new_exact_provenance_occurrences':8,'supporting_aliases_separate_from_exact_occurrences':1,
        'new_proposal_holds':0,'historical_records_rewritten':False,'human_review_verified':False,
        'live_campaign_mapping_verified':False,'release_authorized':False,
        'text_compatibility_is_local_screen_not_platform_acceptance':True}
    previous_pin = prior.OUTPUT_PINS['research-pool-allocation.json']
    previous = first.pinned(root, prior.FOLDER+'/research-pool-allocation.json', previous_pin)
    first.need(previous['total_target'] == 14000 and previous['total_admitted'] == n and
        sum(previous['admitted'].values()) == n and sum(previous['targets'].values()) == 14000,
        'APPRENTICESHIP_ALLOCATION_BASE_CHANGED')
    admitted = dict(previous['admitted']); admitted['ACADEMIC'] += len(new)
    remaining = {k:previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v >= 0 for v in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']), 'APPRENTICESHIP_ALLOCATION_COUNTS')
    allocation = {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':previous_pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'held_deduction':{},'new_rows':{'ACADEMIC':len(new)},'admitted':admitted,
        'remaining':remaining,'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),
        'basis':'Preserve all prior bodies and pool targets; append eight source-bound full apprenticeship literals; retain the ninth only as uncounted same-route semantic evidence.',
        'owner_approval_claimed':False,'media_budget_changed':False,'exclusion_approval_granted':False}
    return {'index.json':index,'cohort-report.json':cohort,
        'library-report.json':dict(summary,as_of=material['review']['reviewed_on']),
        'research-pool-allocation.json':allocation}, summary


def build_outputs(base, root=first.ROOT, when=None):
    """Generate in memory from caller-fresh base; no reconstruction or writes."""
    when = first.dubai_date() if when is None else when
    inputs = extend(base, root, when)
    documents, _ = _outputs(inputs, load_reviewed(root, when), root, when)
    return inputs, documents


def check_saved(inputs, root, when):
    base = stage.recover_base(inputs, stage_key=STAGE_KEY)
    expected = extend(base, root, when)
    first.need(first.canonical(inputs) == first.canonical(expected), 'APPRENTICESHIP_DERIVED_BODIES_CHANGED')
    documents, summary = _outputs(inputs, load_reviewed(root, when), root, when)
    stage.check_documents(root, FOLDER, OUTPUT_PINS, documents)
    return dict(summary,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',release_held=True)
