"""Append-only official occupational-title research, never exclusion approval.

Every public invocation starts with caller-fresh complete history. Pinned saved
metadata binds bodies; it is not a serialized baseline or acceptance cache.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
from pathlib import Path
import runpy

import append_only_admission as stage
import apprenticeship_admission as prior
from followup_admission import VALIDITY
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first

FOLDER = 'docs/audit/keyword-negative-ofqual-occupational-admission-2026-11-12'
CAPTURE = 'docs/audit/keyword-ofqual-occupational-2026-11-12'
SOURCE_PINS = {
    CAPTURE+'/qualifications.json': '8cdd1a1e0475857b1fc7473734756da9bb20b2229890c61d639ee41ed6dac91c',
    CAPTURE+'/capture.json': '85c9a3ed815c72a8bfc3966fdaa016aec64063e43c4dd352e59e5504fa61530e',
    CAPTURE+'/semantic-decisions.json': '5f7aeb754ae4d8feccd2024847fef9b625d1bf6be94bc903900b59239627c7ee',
}
TEXT_PINS = {
    CAPTURE+'/extract.py': 'c37a98859e1865d543e82c43886608b63f265b0ac3d44725fd52bdc30ab199ed',
    CAPTURE+'/semantic-review.md': '9a6e977f2dfe914ce05906e86e1cb408f16d5f0743e9a43b46a9d66f5309234c',
}
BASE_SHA256 = '4db6a3a93ac0b7f4015cb2e329898b5446aa947586e2880b98b02537941373ac'
REVIEW_PIN = '71309898f85a5dac4f820126aaa312f7e0afc8572450e55c1f9a395d53737dea'
OUTPUT_PINS = {'index.json': 'cd85c0306a8494c342ada20254b83392e816f859156d95939cf539aea5b3bc6c', 'cohort-report.json': '2b896735516cc18f66b596f294ac758001ce27f58d58cbaca524ddaca89fd874', 'library-report.json': '55ebf0a4c11961bebc4e3a25681bfdbe264ae528f462fb9b42cfd18da17b4df0', 'research-pool-allocation.json': '9a05d86b547cff58350e68c130aff002a7b7f068bda0cd7cb842ef75e76c5ae3'}
STAGE_KEY = 'ofqual_occupational_append_only_state'
SOURCE_ID = 'OFQUAL-OCCUPATIONAL-QUALIFICATIONS-20261111'
INTENT = 'EXPLICIT_OCCUPATIONAL_STUDY_OR_ASSESSMENT_RESEARCH'
LIMITS = prior.LIMITS
RAW_SHA256 = 'ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5'


def implementation_binding(root):
    for relative, pin in TEXT_PINS.items():
        raw = (Path(root)/relative).read_bytes()
        first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == pin,
                   'OCCUPATIONAL_REVIEW_OR_EXTRACTOR_BYTES_CHANGED')
    return {'audit_and_compatibility': prior.implementation_binding(root),
            'source_extractor_and_peer_narrative_sha256': dict(TEXT_PINS)}


def occurrence(row):
    values = row['values']
    return {'qualification_number': values['Qualification Number'],
        'source_record_ordinal': row['source_record_ordinal'],
        'source_line_start': row['source_line_start'], 'source_line_end': row['source_line_end'],
        'qualification_title': values['Qualification Title'],
        'qualification_status': values['Qualification Status']}


def _profile_without_text(text, canonical):
    return {key: {k:v for k,v in value.items() if k != 'text'}
            for key,value in compatibility.profile_text(text, canonical_text=canonical).items()}


def load_sources(root):
    docs = {path:first.pinned(root,path,pin) for path,pin in SOURCE_PINS.items()}
    implementation = implementation_binding(root)
    # Execute only the already byte-pinned local read-only verifier. It checks
    # source/extractor/dependency pins and original 338-ordinal exclusion anew.
    verifier = runpy.run_path(str(Path(root)/CAPTURE/'extract.py'))
    first.need(verifier['verify']()['passed'] is True, 'OCCUPATIONAL_CAPTURE_NOT_VERIFIED')
    projection, capture, peer = (docs[CAPTURE+'/'+name] for name in
        ('qualifications.json','capture.json','semantic-decisions.json'))
    first.need(projection['source_sha256'] == capture['original_source']['sha256'] == RAW_SHA256 and
        projection['source_bytes'] == 23984795 and projection['source_record_count'] == 53175 and
        len(projection['records']) == 524 and
        all(projection['controls'][k] is False for k in ('semantic_review_complete',
            'current_library_membership_verified','protected_query_and_scope_clearance',
            'published_titles_are_observed_queries','deployment_authorized')) and
        all(projection['controls'][k] is None for k in ('volume','cpc','competition')),
        'OCCUPATIONAL_SOURCE_IDENTITY_OR_AUTHORITY_CHANGED')
    groups = defaultdict(list)
    for row in projection['records']:
        groups[ka.normalize(row['values']['Qualification Title'])].append(row)
    eligible = {key:rows for key,rows in groups.items() if rows[0]['local_length_word_precheck_pass']}
    first.need(len(groups) == 517 and len(eligible) == 296 and
        sum(len(rows) for rows in eligible.values()) == 303 and
        peer['schema'] == 'bsre-ofqual-occupational-preliminary-semantic-review-v1' and
        peer['authority'] == 'PRELIMINARY_PROPOSE_OR_HOLD_ONLY' and
        peer['projection']['sha256'] == SOURCE_PINS[CAPTURE+'/qualifications.json'] and
        peer['projection']['capture_sha256'] == SOURCE_PINS[CAPTURE+'/capture.json'] and
        peer['projection']['official_csv_sha256'] == RAW_SHA256 and
        all(value is False for value in peer['controls'].values()) and
        peer['summary']['preliminary_propose_groups'] == 207 and
        peer['summary']['preliminary_hold_groups'] == 89 and
        peer['summary']['current_library_novelty_or_admissibility_count'] is None,
        'OCCUPATIONAL_PEER_IDENTITY_OR_AUTHORITY_CHANGED')
    decisions = {row['normalized_title']:row for row in peer['decisions']}
    first.need(len(decisions) == len(peer['decisions']) == 296 and set(decisions) == set(eligible),
        'OCCUPATIONAL_PEER_COVERAGE_CHANGED')
    proposed = set()
    for key, rows in eligible.items():
        decision = decisions[key]
        literals = list(dict.fromkeys(row['values']['Qualification Title'] for row in rows))
        profiles = [_profile_without_text(text,key) for text in literals]
        reasons = set(code for profile in profiles for value in profile.values()
                      for code in value['reason_codes'])
        first.need(decision['normalized_title_sha256'] == hashlib.sha256(key.encode('utf-8')).hexdigest() and
            decision['complete_literals_read_individually'] is True and
            decision['occurrences'] == [occurrence(row) for row in rows] and
            decision['local_text_profiles'] == profiles and
            decision['manual_semantic_decision'] in {'PROPOSE','HOLD'} and
            decision['semantic_reason_code'] in peer['semantic_reason_catalog'] and
            decision['matching_limit'] == 'COMPLETE_UNSHORTENED_LITERAL_ONLY_FOR_LATER_EXACT_REVIEW',
            'OCCUPATIONAL_FULL_LITERAL_PEER_CHANGED')
        expected = 'PROPOSE' if decision['manual_semantic_decision'] == 'PROPOSE' and not reasons else 'HOLD'
        first.need(decision['preliminary_decision'] == expected and
            all(code in decision['hold_reason_codes'] for code in reasons),
            'OCCUPATIONAL_COMPATIBILITY_OR_SEMANTIC_HOLD_CHANGED')
        if expected == 'PROPOSE':
            proposed.add(key)
    expected_holds = [{'qualification_number':row['values']['Qualification Number'],
        'source_record_ordinal':row['source_record_ordinal'], 'source_line_start':row['source_line_start'],
        'source_line_end':row['source_line_end'], 'local_precheck_holds':row['local_precheck_holds']}
        for row in projection['records'] if not row['local_length_word_precheck_pass']]
    first.need(len(proposed) == 207 and peer['unreviewed_precheck_holds']['references'] == expected_holds,
        'OCCUPATIONAL_PRECHECK_HOLDS_CHANGED')
    return {'groups':dict(groups),'peer':peer,'decisions':decisions,'proposed':sorted(proposed),
        'projection':projection,'capture':capture,'implementation':implementation,
        'context':first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN),
        'registry':first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])}


def _closed(text):
    return ''.join(char for char in ka.normalize(text) if char.isalnum())


def membership(base, material):
    """Reconcile all complete current/archive/protected bodies in this call."""
    maps = {kind:defaultdict(set) for kind in ('normalized_exact','ordered_tokens','equal_token_bag','closed_alphanumeric')}
    protected_exact = set()
    for field,textfield,idfield in (('records','original_text','keyword_id'),
        ('archived_records','original_text','keyword_id'),('protected_queries','text','query_id')):
        for row in base[field]:
            text = row[textfield]; key = ka.normalize(text); tokens = tuple(ka.tokens(text))
            values = (key,tokens,tuple(sorted(tokens)),_closed(text))
            for kind,value in zip(maps,values):
                maps[kind][value].add(field+':'+row[idfield])
            if field == 'protected_queries': protected_exact.add(key)
    own = {kind:defaultdict(set) for kind in maps}
    for key,rows in material['groups'].items():
        text = rows[0]['values']['Qualification Title']; tokens = tuple(ka.tokens(text))
        for kind,value in zip(own,(key,tokens,tuple(sorted(tokens)),_closed(text))):
            own[kind][value].add(key)
    # Complete every join for every source group, including groups already held
    # by source length, symbols or semantics. Pre-held does not mean unexamined.
    all_conflicts = {}
    compared_groups = 0
    external_key_comparisons = 0
    within_source_key_comparisons = 0
    for key in sorted(material['groups']):
        text = material['groups'][key][0]['values']['Qualification Title']; tokens = tuple(ka.tokens(text))
        reasons = []
        for kind,value in zip(maps,(key,tokens,tuple(sorted(tokens)),_closed(text))):
            external_key_comparisons += 1
            if maps[kind].get(value):
                reasons.append({'kind':kind,'existing_identities':sorted(maps[kind][value])})
            within_source_key_comparisons += 1
            others = own[kind].get(value,set())-{key}
            if others:
                reasons.append({'kind':'within_capture_'+kind,'other_normalized_titles':sorted(others)})
        compared_groups += 1
        if reasons: all_conflicts[key] = reasons
    proposed = set(material['proposed'])
    conflicts = {key:all_conflicts[key] for key in material['proposed'] if key in all_conflicts}
    selected = [key for key in material['proposed'] if key not in all_conflicts]
    held = sorted(set(material['groups'])-set(selected))
    # New source holds cannot silently remove an already admitted old record.
    # This covers every lexical method, including pre-held bag/closed aliases.
    first.need(all(not any(identity.startswith('records:') for reason in all_conflicts.get(key,[])
        for identity in reason.get('existing_identities',[])) for key in held),
        'OCCUPATIONAL_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    first.need(compared_groups == len(material['groups']) and
        external_key_comparisons == within_source_key_comparisons == 4*compared_groups,
        'OCCUPATIONAL_INCOMPLETE_SOURCE_GROUP_COMPARISONS')
    return {'selected_normalized_titles':selected,'additional_variant_holds':conflicts,
        'all_held_normalized_titles':held,
        'existing_held_protection_keys':sorted(set(held)&protected_exact),
        'all_source_group_conflicts':all_conflicts,
        'preheld_source_group_conflicts':{key:value for key,value in all_conflicts.items() if key not in proposed},
        'source_groups_compared':compared_groups,
        'external_key_comparisons':external_key_comparisons,
        'within_source_key_comparisons':within_source_key_comparisons,
        'complete_base_counts':{field:len(base[field]) for field in
            ('records','archived_records','protected_queries','sources','campaigns','campaign_context')},
        'lexical_methods':list(maps),'all_517_source_groups_compared':compared_groups == 517,
        'google_equivalence_verified':False,'counts_distinct_concepts':False}


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources',
            'campaigns','campaign_context')) == (10963,18,16383,24,360,1) and
        sum(len(row['provenance_occurrences']) for row in base['records']) == 11169 and
        base['campaigns'] == material['registry'], 'OCCUPATIONAL_PRIOR_BASE_CHANGED')
    return membership(base,material)


def review_subject(review, material):
    return stage.digest({'review':{key:value for key,value in review.items() if key != 'subject_sha256'},
        'context':material['context'],'registry':material['registry'],
        'source_pins':SOURCE_PINS,'text_pins':TEXT_PINS,'implementation':material['implementation']})


def make_review(base, root=first.ROOT, when=None):
    when = first.dubai_date() if when is None else when
    material = load_sources(root); diagnostic = verify_base(base,material)
    selected = diagnostic['selected_normalized_titles']
    first.need(0 < len(selected) <= 324, 'OCCUPATIONAL_ACADEMIC_HEADROOM')
    held = {}
    for key in diagnostic['all_held_normalized_titles']:
        if key in diagnostic['additional_variant_holds']:
            reason = 'Fresh complete current/archive/protected or within-source lexical peer remains HOLD; retain full literal.'
        elif key not in material['decisions']:
            reason = 'Original complete-title length/word precheck HOLD; no shortened or rewritten literal.'
        else:
            reason = 'Independent full-literal semantic or documented-symbol HOLD; preserve exact source and peer reasons.'
        held[key] = reason
    review = {'version':1,'scope':'AI_REVIEWED_OCCUPATIONAL_TITLES_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN',
        'reviewed_on':when.isoformat(),'valid_until':(when+timedelta(days=30)).isoformat(),
        'validity_basis':VALIDITY,'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_titles':selected,'held_groups':held,'fresh_variant_review':diagnostic,
        'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Independent complete-literal AI review supports explicit occupational learning or assessment for later exact residential-rental-intake research; preserve every original symbol, provider, title and occurrence. Newly discovered conflicts hold rather than force the preliminary count.',
        'source_identity_limits':'Official qualification titles are not observed queries, demand, current course delivery, UAE recognition, local inventory or platform matching certification. Published source status is retained without interpretation.',
        **{key:False for key in LIMITS}}
    review['subject_sha256'] = review_subject(review,material)
    validate_review(review,material,when)
    return review


def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_normalized_titles','held_groups','fresh_variant_review',
        'source_pins','text_pins','implementation','base_sha256','semantic_rationale','source_identity_limits',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review) == required and type(review['version']) is int and
        review['version'] == 1 and review['scope'] == 'AI_REVIEWED_OCCUPATIONAL_TITLES_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[key] is False for key in LIMITS),'OCCUPATIONAL_REVIEW_AUTHORITY')
    campaign = next(row for row in material['registry'] if row['campaign_key'] == first.CAMPAIGN)
    context = material['context']
    first.need(review['campaign_key'] == campaign['campaign_key'] == 'BSRE-C0301' and
        review['landing_page_id'] == campaign['landing_page_id'] == 'BSRE-LP0301' and
        campaign['family_code'] == 'RNT' and campaign['family_slot'] == 1 and
        campaign['actual_url'] is None and campaign['google_campaign_id'] is None and
        campaign['release_approved'] is False and
        context['context_kind'] == 'PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        context['source_url'] == 'https://blackswanrealestate.ae/enquire/rent/' and
        all(context[key] is False for key in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed','live_campaign_mapping_assigned')),
        'OCCUPATIONAL_SCOPE_CHANGED')
    selected = review['selected_normalized_titles']; held = review['held_groups']
    first.need(type(selected) is list and selected == sorted(set(selected)) and
        0 < len(selected) <= 324 and set(selected) <= set(material['proposed']) and
        type(held) is dict and set(held) == set(material['groups'])-set(selected) and
        all(type(value) is str and value.strip() for value in held.values()) and
        selected == review['fresh_variant_review']['selected_normalized_titles'] and
        sorted(held) == review['fresh_variant_review']['all_held_normalized_titles'] and
        review['source_pins'] == SOURCE_PINS and review['text_pins'] == TEXT_PINS and
        review['implementation'] == material['implementation'] and review['base_sha256'] == BASE_SHA256 and
        all(type(review[key]) is str and review[key].strip() for key in
            ('semantic_rationale','source_identity_limits')), 'OCCUPATIONAL_REVIEW_BINDINGS_CHANGED')
    start,end = date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        start <= when <= end and end-start == timedelta(days=30) and review['validity_basis'] == VALIDITY and
        material['projection']['original_capture_date_utc'] <= material['peer']['review_date_dubai'] == review['reviewed_on'] and
        context['observed_date_dubai'] <= review['reviewed_on'], 'OCCUPATIONAL_REVIEW_DATES')
    first.need(review['subject_sha256'] == review_subject(review,material),'OCCUPATIONAL_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN) == 64,'OCCUPATIONAL_REVIEW_UNREGISTERED')
    review = first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_review(review,material,when)
    return dict(material,review=review)


def build_cohort(base, material):
    review = material['review']; records = []
    for key in review['selected_normalized_titles']:
        rows = material['groups'][key]; occurrences = []
        for row in rows:
            occurrences.append({'batch':SOURCE_ID, **occurrence(row),
                'original_text':row['values']['Qualification Title'],
                'file':CAPTURE+'/qualifications.json','sha256':SOURCE_PINS[CAPTURE+'/qualifications.json'],
                'official_csv_sha256':RAW_SHA256,'capture_file':CAPTURE+'/capture.json',
                'capture_sha256':SOURCE_PINS[CAPTURE+'/capture.json'],
                'review_file':FOLDER+'/review.json','review_sha256':REVIEW_PIN,
                'independent_review_file':CAPTURE+'/semantic-decisions.json',
                'independent_review_sha256':SOURCE_PINS[CAPTURE+'/semantic-decisions.json']})
        adapted = {'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW',
            'original_forms':list(dict.fromkeys(row['values']['Qualification Title'] for row in rows)),
            'assessment':{'intent':INTENT,'negative_scope_proposal':
                {'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record = first.make_record(adapted,review,occurrences,source_id=SOURCE_ID,
            source_reference=CAPTURE+'/qualifications.json#source_record_ordinal='+str(rows[0]['source_record_ordinal']),
            review_folder=FOLDER,allowed_intents={INTENT})
        record['evidence_ref'] = FOLDER+'/review.json#'+key
        records.append(record)
    source = {'source_id':SOURCE_ID,'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-11','valid_until':review['valid_until'],
        'capture_kind':'official_published_occupational_qualification_titles',
        'research_use_basis':'OWNER_AUTHORIZED_RESEARCH_AND_PINNED_OFFICIAL_TITLES_WITH_INDEPENDENT_AI_REVIEW',
        'metrics_captured':False,'served_query_or_current_performance_claimed':False}
    existing = set(review['fresh_variant_review']['existing_held_protection_keys'])
    protections = [{'query_id':'BSRE-Q-'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:24],
        'text':key,'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
        'evidence_ref':FOLDER+'/review.json#'+key,'reviewed_on':review['reviewed_on'],
        'valid_until':review['valid_until'],'source_kind':'official_reference',
        'protection_basis':'UNRESOLVED_FULL_SOURCE_LITERAL_NOT_OBSERVED_QUERY_OR_SERVICE_ELIGIBILITY'}
        for key in sorted(review['held_groups']) if key not in existing]
    return {'records':records,'sources':[source],'protected_queries':[],
        'campaigns':base['campaigns'],'campaign_context':base['campaign_context']},protections


def extend(base, root, when):
    material = load_reviewed(root,when)
    diagnostic = verify_base(base,material)
    first.need(diagnostic == material['review']['fresh_variant_review'],'OCCUPATIONAL_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections = build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result = stage.checked_audit(inputs,when)
    state = inputs[STAGE_KEY]; n = state['retained_records']; new = inputs['records'][n:]
    new_protections = inputs['protected_queries'][state['retained_protections']:]
    first.need(len(new) == len(material['review']['selected_normalized_titles']) and
        sum(len(row['provenance_occurrences']) for row in new) ==
        sum(len(material['groups'][key]) for key in material['review']['selected_normalized_titles']),
        'OCCUPATIONAL_SOURCE_OCCURRENCES_CHANGED')
    index = {'version':1,'scope':'APPEND_ONLY_OCCUPATIONAL_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[row['keyword_id'] for row in new],
        'additional_protected_query_ids':[row['query_id'] for row in new_protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort = {'scope':'AI_REVIEWED_OCCUPATIONAL_QUALIFICATION_TITLES_NOT_SEARCH_DEMAND',
        'source_groups':517,'source_occurrences':524,'precheck_candidate_groups':296,
        'peer_proposed_groups':207,'selected_groups':len(new),
        'retained_new_occurrences':sum(len(row['provenance_occurrences']) for row in new),
        'held_groups':len(material['review']['held_groups']),
        'held_occurrences':sum(len(material['groups'][key]) for key in material['review']['held_groups']),
        'additional_protected_queries':len(new_protections),
        'existing_held_protection_occurrences':len(material['review']['fresh_variant_review']['existing_held_protection_keys']),
        'additional_variant_hold_groups':len(material['review']['fresh_variant_review']['additional_variant_holds']),
        'record_bodies_sha256':stage.digest(new),'source_pins':dict(SOURCE_PINS),
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},
        'search_demand_verified':False,**{key:False for key in LIMITS}}
    summary = {'scope':'CURRENT_RESEARCH_AFTER_OCCUPATIONAL_APPEND_ONLY_REVIEW',
        **{key:result[key] for key in ('as_of','input_rows','distinct_nonblank_phrases','reviewed_eligible_rows',
            'excluded_rows','approved_exclusion_rows','target','deficit','exact_target_pass','structural_pass',
            'deployment_export_allowed','production_writes_available','positive_library_coverage_verified',
            'protected_queries_indexed')},'computed_conflicts':len(result['protected_conflicts']),
        'prior_rows':n,'new_rows':len(new),'archived_original_rows':len(inputs['archived_records']),
        'source_occurrences_retained_in_current_records':sum(len(row['provenance_occurrences']) for row in inputs['records']),
        'new_exact_provenance_occurrences':sum(len(row['provenance_occurrences']) for row in new),
        'new_proposal_holds':len(material['review']['held_groups']),
        'historical_records_rewritten':False,'human_review_verified':False,
        'live_campaign_mapping_verified':False,'release_authorized':False,
        'text_compatibility_is_local_screen_not_platform_acceptance':True}
    previous_pin = prior.OUTPUT_PINS['research-pool-allocation.json']
    previous = first.pinned(root,prior.FOLDER+'/research-pool-allocation.json',previous_pin)
    first.need(previous['total_target'] == 14000 and previous['total_admitted'] == n and
        previous['remaining']['ACADEMIC'] == 324 and sum(previous['admitted'].values()) == n and
        sum(previous['targets'].values()) == 14000,'OCCUPATIONAL_ALLOCATION_BASE_CHANGED')
    admitted = dict(previous['admitted']); admitted['ACADEMIC'] += len(new)
    remaining = {key:previous['targets'][key]-value for key,value in admitted.items()}
    first.need(all(type(value) is int and value >= 0 for value in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']),'OCCUPATIONAL_ALLOCATION_COUNTS')
    allocation = {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':previous_pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'held_deduction':{},'new_rows':{'ACADEMIC':len(new)},'admitted':admitted,
        'remaining':remaining,'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),
        'basis':'Preserve all prior bodies, archives, protection prefix and category targets; append only reviewed complete occupational qualification literals after fresh full-body checks.',
        'owner_approval_claimed':False,'media_budget_changed':False,'exclusion_approval_granted':False}
    return {'index.json':index,'cohort-report.json':cohort,
        'library-report.json':dict(summary,as_of=material['review']['reviewed_on']),
        'research-pool-allocation.json':allocation},summary


def build_outputs(base, root=first.ROOT, when=None):
    """Generate in memory over this invocation's freshly verified complete base."""
    when = first.dubai_date() if when is None else when
    inputs = extend(base,root,when)
    documents,_ = _outputs(inputs,load_reviewed(root,when),root,when)
    return inputs,documents


def check_saved(inputs, root, when):
    base = stage.recover_base(inputs,stage_key=STAGE_KEY)
    expected = extend(base,root,when)
    first.need(first.canonical(inputs) == first.canonical(expected),'OCCUPATIONAL_DERIVED_BODIES_CHANGED')
    documents,summary = _outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return dict(summary,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',release_held=True)
