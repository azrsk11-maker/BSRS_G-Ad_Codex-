"""Append-only official veterinary-title research, never exclusion approval.

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
import ofqual_occupational_admission as prior
from followup_admission import VALIDITY
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first

FOLDER = 'docs/audit/keyword-negative-ofqual-veterinary-admission-2026-11-12'
CAPTURE = 'docs/audit/keyword-ofqual-veterinary-2026-11-12'
SOURCE_PINS = {
    CAPTURE+'/qualifications.json': '00daad3657a0ea8d2407c50dd2478ac7099355c53d33fadbbd92598c2eac09fa',
    CAPTURE+'/capture.json': 'ecf76b2123ff80f7f4518c0a1c3f157cab3ab499768e6d2cea7d8be4ad258afd',
    CAPTURE+'/semantic-decisions.json': '7c280316bab94d4ad892b58f2f738d3295913cb0dbc90e608c404a238113b68b',
}
TEXT_PINS = {
    CAPTURE+'/extract.py': '88aad542fba54547531d030f791ce4edf0f3c088ca098444421f01812764b712',
    CAPTURE+'/semantic-review.md': '203bb34392027ae8bd454c7bdbc39098cae3ec2ccd2dfedcd1fafd985e8d0b78',
    CAPTURE+'/README.md': '1a5007ea9e59cceca1ff2aa11437476ecf52bc66625ecbc8faf8178fbf815f3b',
}
BASE_SHA256 = '4b3106190c37a47deaefdd391e9dfded0554c9a91b381c6d3a62424b54c80587'
REVIEW_PIN = '5fd9d98b9b2ad620cd0b0ddd9bdc6b4fa1ac7d54d3cf71d3e14b5b6ed62bdc87'
OUTPUT_PINS = {'index.json': '403e3058d0403cfa24ceb53cef180af05ddc615f90fdbbcffc6ea333e42a78e7', 'cohort-report.json': '6127a8be50ecbc4d908478233d6a97ff70c416cd987358699ee9131b125268b3', 'library-report.json': '63d0cd7c848d4e846bb92fce3dacca970161e336a8127e4eff05d0cac12ee3cc', 'research-pool-allocation.json': '38cf12a92abbc06f89f256666f41fe17c4df6172d4c515ba41786c1a9a0139ae'}
STAGE_KEY = 'ofqual_veterinary_append_only_state'
SOURCE_ID = 'OFQUAL-VETERINARY-QUALIFICATIONS-20261111'
INTENT = 'EXPLICIT_OCCUPATIONAL_STUDY_OR_ASSESSMENT_RESEARCH'
LIMITS = prior.LIMITS
RAW_SHA256 = 'ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5'

# Independent complete-literal AI review identified plausible route/provider
# relationships, not proven aliases. Hold the whole family without rewriting
# titles or inferring an abbreviation's expansion. Include already text-held
# peers so their unresolved relationship cannot be hidden by the first screen.
ALIAS_FAMILIES = (
    {'key':'LEVEL3_RECEPTION_CREDENTIAL_ROUTES','ordinals':[10746,45228,49191,49213,49214],
     'reason':'Same level and veterinary reception role; provider Certificate/Reception Skills and iPET Award/Certificate or BVRA routes remain unresolved.'},
    {'key':'LEVEL2_NURSING_ASSISTANT_DIPLOMA_ROUTES','ordinals':[10764,44484,44498,44499,44509],
     'reason':'Provider-prefixed generic and animal-specific Level 2 Veterinary Nursing Assistant diploma routes require distinctness review.'},
    {'key':'LEVEL3_EQUINE_NURSING_DIPLOMA_ROUTES','ordinals':[39023,44489,44510,48081],
     'reason':'CQ EQ/Equine Practice and provider work-based or VTEC diploma routes remain unresolved; no abbreviation is expanded.'},
    {'key':'LEVEL3_SMALL_ANIMAL_NURSING_DIPLOMA_ROUTES','ordinals':[39024,44490,44508,48080],
     'reason':'CQ SA/Small Animal Practice and provider Small Animal/Companion Animal routes require review; equivalence is not inferred.'},
    {'key':'LEVEL3_VETERINARY_NURSE_END_POINT_ROUTES','ordinals':[39123,44492,48098],
     'reason':'Same occupational assessment and level across providers, with ST0343 present only in some full titles; route distinctness is unresolved.'},
    {'key':'LEVEL2_VETERINARY_CARE_ASSISTANT_DIPLOMA_ROUTES','ordinals':[45219,53002],
     'reason':'Generic and Small Animals provider-prefixed Level 2 Veterinary Care Assistant diplomas require route distinctness review.'},
    {'key':'LEVEL5_MEDICAL_NURSING_VTEC_ROUTES','ordinals':[48087,48094],
     'reason':'VTEC and non-VTEC advanced Medical nursing diplomas remain unresolved; both original text holds stay in evidence.'},
)


def implementation_binding(root):
    for relative, pin in TEXT_PINS.items():
        raw = (Path(root)/relative).read_bytes()
        first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == pin,
                   'VETERINARY_REVIEW_OR_EXTRACTOR_BYTES_CHANGED')
    return {'audit_and_compatibility': prior.implementation_binding(root),
            'source_extractor_and_peer_narrative_sha256': dict(TEXT_PINS)}


def occurrence(row):
    values = row['values']
    return {'qualification_number': values['Qualification Number'],
        'source_record_ordinal': row['source_record_ordinal'],
        'source_line_start': row['source_line_start'], 'source_line_end': row['source_line_end'],
        'qualification_title': values['Qualification Title'],
        'qualification_status': values['Qualification Status']}


def load_sources(root):
    docs = {path:first.pinned(root,path,pin) for path,pin in SOURCE_PINS.items()}
    implementation = implementation_binding(root)
    # The frozen verifier checks its public projection and earlier source pins;
    # it does not claim fresh private-CSV authentication or library acceptance.
    verifier = runpy.run_path(str(Path(root)/CAPTURE/'extract.py'))
    first.need(verifier['verify']()['passed'] is True, 'VETERINARY_CAPTURE_NOT_VERIFIED')
    projection, capture, peer = (docs[CAPTURE+'/'+name] for name in
        ('qualifications.json','capture.json','semantic-decisions.json'))
    first.need(projection['source_sha256'] == capture['original_source']['sha256'] == RAW_SHA256 and
        projection['source_bytes'] == 23984795 and projection['source_record_count'] == 53175 and
        len(projection['records']) == 51 and
        all(projection['controls'][k] is False for k in ('semantic_review_complete',
            'current_library_membership_verified','protected_query_and_scope_clearance',
            'published_titles_are_observed_queries','deployment_authorized')) and
        all(projection['controls'][k] is None for k in ('volume','cpc','competition')),
        'VETERINARY_SOURCE_IDENTITY_OR_AUTHORITY_CHANGED')
    groups = defaultdict(list)
    for row in projection['records']:
        groups[ka.normalize(row['values']['Qualification Title'])].append(row)
    summary = peer['summary']; controls = peer['controls']; method = peer['method']
    first.need(len(groups) == 51 and
        peer['review_type'] == 'INDEPENDENT_COMPLETE_LITERAL_SEMANTIC_REVIEW_SOURCE_SUPPLY_ONLY' and
        method['all_51_complete_literals_individually_read'] is True and
        method['individual_reasons_authored_by_source_ordinal'] is True and
        method['compatibility_used_to_select_semantic_review'] is False and
        method['pattern_batch_approval'] is False and
        controls['semantic_review_complete_for_frozen_51_only'] is True and
        all(controls[k] is False for k in ('source_files_changed','current_library_membership_verified',
            'duplicate_and_variant_clearance','protected_query_and_scope_clearance','admission_authorized',
            'deployment_authorized','production_changed','live_campaign_changes')) and
        controls['metrics_status'] == 'NOT_OBSERVED_UNKNOWN' and
        summary == {'source_occurrences':51,'complete_literals_reviewed':51,
            'distinct_source_normalized_titles':51,'propose_full_exact_research':51,'semantic_hold':0,
            'local_length_word_precheck_pass':27,'local_length_word_precheck_hold':24,
            'text_compatibility_no_known_incompatibility':19,'text_compatibility_requires_review':11,
            'text_compatibility_documented_incompatibility':21,'text_compatibility_admission_holds':32,
            'current_library_admissions':0,'new_negative_admissions':0,'approved_exclusions':0,'deployments':0},
        'VETERINARY_PEER_IDENTITY_OR_AUTHORITY_CHANGED')
    frozen = {row['file']:row for row in peer['frozen_source_files']}
    first.need(set(frozen) == {'extract.py','qualifications.json','capture.json','README.md'} and
        all(frozen[name]['sha256'] == (SOURCE_PINS|TEXT_PINS)[CAPTURE+'/'+name] and
            frozen[name]['bytes'] == (Path(root)/CAPTURE/name).stat().st_size for name in frozen) and
        peer['underlying_raw_source']['sha256'] == RAW_SHA256 and
        peer['underlying_raw_source']['bytes'] == 23984795 and
        peer['underlying_raw_source']['fresh_raw_verification_performed_by_this_semantic_review'] is False,
        'VETERINARY_PEER_SOURCE_BINDINGS_CHANGED')
    decisions = {row['normalized_title']:row for row in peer['decisions']}
    first.need(len(decisions) == len(peer['decisions']) == 51 and set(decisions) == set(groups),
        'VETERINARY_PEER_COVERAGE_CHANGED')
    proposed = set()
    for key, rows in groups.items():
        first.need(len(rows) == 1,'VETERINARY_UNEXPECTED_NORMALIZED_DUPLICATE')
        row = rows[0]; decision = decisions[key]; text = row['values']['Qualification Title']
        profile = compatibility.profile_text(text)['original']
        classification = profile['classification']
        gate = {'NO_KNOWN_INCOMPATIBILITY_DETECTED':'NO_KNOWN_INCOMPATIBILITY_DETECTED_NOT_PLATFORM_ACCEPTANCE',
            'REQUIRES_REVIEW':'HOLD_TEXT_COMPATIBILITY_REVIEW',
            'DOCUMENTED_INCOMPATIBILITY_DETECTED':'HOLD_DOCUMENTED_TEXT_INCOMPATIBILITY'}[classification]
        expected_profile = {'classification':classification,'reason_codes':profile['reason_codes'],
            'invalid_symbols':profile['invalid_symbols'],'character_count':len(text),
            'whitespace_word_count':len(text.split()),
            'local_length_word_precheck_pass':row['local_length_word_precheck_pass'],'admission_gate':gate}
        first.need(decision['source_record_ordinal'] == row['source_record_ordinal'] and
            decision['qualification_number'] == row['values']['Qualification Number'] and
            decision['original_literal'] == text and decision['normalized_title'] == key and
            decision['source_line_start'] == row['source_line_start'] and
            decision['source_line_end'] == row['source_line_end'] and
            decision['original_literal_utf8_sha256'] == hashlib.sha256(text.encode('utf-8')).hexdigest() and
            decision['semantic_decision'] == 'PROPOSE_FULL_EXACT_RESEARCH' and
            type(decision['semantic_reason']) is str and bool(decision['semantic_reason'].strip()) and
            decision['proposed_matching_limit'] == 'COMPLETE_ORIGINAL_LITERAL_ONLY_FOR_LATER_EXACT_REVIEW' and
            decision['text_compatibility'] == expected_profile and
            decision['admission_state'] == 'HOLD_PENDING_INDEPENDENT_MEMBERSHIP_VARIANT_PROTECTION_AND_SCOPE_GATES',
            'VETERINARY_FULL_LITERAL_PEER_CHANGED')
        if classification == 'NO_KNOWN_INCOMPATIBILITY_DETECTED' and row['local_length_word_precheck_pass']:
            proposed.add(key)
    first.need(len(proposed) == 19,'VETERINARY_TEXT_PREHOLDS_CHANGED')
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
    ordinal_keys = {row['source_record_ordinal']:key for key,rows in material['groups'].items() for row in rows}
    alias_review = []
    for family in ALIAS_FAMILIES:
        first.need(all(ordinal in ordinal_keys for ordinal in family['ordinals']),
            'VETERINARY_ALIAS_SOURCE_BINDING_CHANGED')
        keys = sorted({ordinal_keys[ordinal] for ordinal in family['ordinals']})
        alias_review.append({**deepcopy(family),'normalized_titles':keys,
            'decision':'HOLD_PLAUSIBLE_ROUTE_OR_PROVIDER_RELATIONSHIP_NOT_PROVEN_EQUIVALENCE'})
        for key in keys:
            all_conflicts.setdefault(key,[]).append({'kind':'explicit_source_route_or_provider_hold',
                'family_key':family['key'],'other_normalized_titles':[value for value in keys if value != key],
                'source_record_ordinals':list(family['ordinals']),'reason':family['reason']})
    proposed = set(material['proposed'])
    conflicts = {key:all_conflicts[key] for key in material['proposed'] if key in all_conflicts}
    selected = [key for key in material['proposed'] if key not in all_conflicts]
    held = sorted(set(material['groups'])-set(selected))
    # New source holds cannot silently remove an already admitted old record.
    # This covers every lexical method, including pre-held bag/closed aliases.
    first.need(all(not any(identity.startswith('records:') for reason in all_conflicts.get(key,[])
        for identity in reason.get('existing_identities',[])) for key in held),
        'VETERINARY_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    first.need(compared_groups == len(material['groups']) and
        external_key_comparisons == within_source_key_comparisons == 4*compared_groups,
        'VETERINARY_INCOMPLETE_SOURCE_GROUP_COMPARISONS')
    return {'selected_normalized_titles':selected,'additional_variant_holds':conflicts,
        'all_held_normalized_titles':held,
        'existing_held_protection_keys':sorted(set(held)&protected_exact),
        'all_source_group_conflicts':all_conflicts,
        'preheld_source_group_conflicts':{key:value for key,value in all_conflicts.items() if key not in proposed},
        'source_groups_compared':compared_groups,
        'external_key_comparisons':external_key_comparisons,
        'within_source_key_comparisons':within_source_key_comparisons,
        'explicit_alias_family_review':alias_review,
        'alias_review_authority':'INDEPENDENT_AI_PLAUSIBLE_RELATIONSHIP_HOLD_ONLY_NOT_GOOGLE_EQUIVALENCE',
        'complete_base_counts':{field:len(base[field]) for field in
            ('records','archived_records','protected_queries','sources','campaigns','campaign_context')},
        'lexical_methods':list(maps),'all_51_source_groups_compared':compared_groups == 51,
        'google_equivalence_verified':False,'counts_distinct_concepts':False}


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources',
            'campaigns','campaign_context')) == (11170,18,16693,25,360,1) and
        sum(len(row['provenance_occurrences']) for row in base['records']) == 11383 and
        base['campaigns'] == material['registry'], 'VETERINARY_PRIOR_BASE_CHANGED')
    return membership(base,material)


def review_subject(review, material):
    return stage.digest({'review':{key:value for key,value in review.items() if key != 'subject_sha256'},
        'context':material['context'],'registry':material['registry'],
        'source_pins':SOURCE_PINS,'text_pins':TEXT_PINS,'implementation':material['implementation']})


def make_review(base, root=first.ROOT, when=None):
    when = first.dubai_date() if when is None else when
    material = load_sources(root); diagnostic = verify_base(base,material)
    selected = diagnostic['selected_normalized_titles']
    first.need(0 < len(selected) <= 117, 'VETERINARY_ACADEMIC_HEADROOM')
    held = {}
    for key in diagnostic['all_held_normalized_titles']:
        if key in diagnostic['additional_variant_holds']:
            reason = 'Fresh complete current/archive/protected, within-source lexical or explicitly reviewed provider/route relationship remains HOLD; retain full literal.'
        elif key not in material['proposed']:
            reason = 'Original complete-title text compatibility or length/word HOLD; no shortened, repaired or rewritten literal.'
        else:
            reason = 'Independent full-literal semantic or documented-symbol HOLD; preserve exact source and peer reasons.'
        held[key] = reason
    review = {'version':1,'scope':'AI_REVIEWED_VETERINARY_TITLES_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN',
        'reviewed_on':when.isoformat(),'valid_until':(when+timedelta(days=30)).isoformat(),
        'validity_basis':VALIDITY,'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_titles':selected,'held_groups':held,'fresh_variant_review':diagnostic,
        'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Independent complete-literal AI review supports explicit veterinary learning or assessment for later exact residential-rental-intake research; preserve every original symbol, provider, title and occurrence. Text compatibility and plausible provider/route relationships remain separate holds. Newly discovered conflicts hold rather than force a preliminary count.',
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
        review['version'] == 1 and review['scope'] == 'AI_REVIEWED_VETERINARY_TITLES_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[key] is False for key in LIMITS),'VETERINARY_REVIEW_AUTHORITY')
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
        'VETERINARY_SCOPE_CHANGED')
    selected = review['selected_normalized_titles']; held = review['held_groups']
    first.need(type(selected) is list and selected == sorted(set(selected)) and
        0 < len(selected) <= 117 and set(selected) <= set(material['proposed']) and
        type(held) is dict and set(held) == set(material['groups'])-set(selected) and
        all(type(value) is str and value.strip() for value in held.values()) and
        selected == review['fresh_variant_review']['selected_normalized_titles'] and
        sorted(held) == review['fresh_variant_review']['all_held_normalized_titles'] and
        review['source_pins'] == SOURCE_PINS and review['text_pins'] == TEXT_PINS and
        review['implementation'] == material['implementation'] and review['base_sha256'] == BASE_SHA256 and
        all(type(review[key]) is str and review[key].strip() for key in
            ('semantic_rationale','source_identity_limits')), 'VETERINARY_REVIEW_BINDINGS_CHANGED')
    start,end = date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        start <= when <= end and end-start == timedelta(days=30) and review['validity_basis'] == VALIDITY and
        material['projection']['original_capture_date_utc'] <= material['peer']['reviewed_at_utc'][:10] == review['reviewed_on'] and
        context['observed_date_dubai'] <= review['reviewed_on'], 'VETERINARY_REVIEW_DATES')
    first.need(review['subject_sha256'] == review_subject(review,material),'VETERINARY_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN) == 64,'VETERINARY_REVIEW_UNREGISTERED')
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
        'capture_kind':'official_published_veterinary_qualification_titles',
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
    first.need(diagnostic == material['review']['fresh_variant_review'],'VETERINARY_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections = build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result = stage.checked_audit(inputs,when)
    state = inputs[STAGE_KEY]; n = state['retained_records']; new = inputs['records'][n:]
    new_protections = inputs['protected_queries'][state['retained_protections']:]
    first.need(len(new) == len(material['review']['selected_normalized_titles']) and
        sum(len(row['provenance_occurrences']) for row in new) ==
        sum(len(material['groups'][key]) for key in material['review']['selected_normalized_titles']),
        'VETERINARY_SOURCE_OCCURRENCES_CHANGED')
    index = {'version':1,'scope':'APPEND_ONLY_VETERINARY_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[row['keyword_id'] for row in new],
        'additional_protected_query_ids':[row['query_id'] for row in new_protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort = {'scope':'AI_REVIEWED_VETERINARY_QUALIFICATION_TITLES_NOT_SEARCH_DEMAND',
        'source_groups':51,'source_occurrences':51,'precheck_candidate_groups':27,
        'peer_semantic_proposed_groups':51,'text_compatible_proposed_groups':len(material['proposed']),'selected_groups':len(new),
        'original_text_compatibility_holds':len(material['groups'])-len(material['proposed']),
        'all_source_groups_compared':material['review']['fresh_variant_review']['source_groups_compared'],
        'external_key_comparisons':material['review']['fresh_variant_review']['external_key_comparisons'],
        'within_source_key_comparisons':material['review']['fresh_variant_review']['within_source_key_comparisons'],
        'explicit_alias_families':len(material['review']['fresh_variant_review']['explicit_alias_family_review']),
        'retained_new_occurrences':sum(len(row['provenance_occurrences']) for row in new),
        'held_groups':len(material['review']['held_groups']),
        'held_occurrences':sum(len(material['groups'][key]) for key in material['review']['held_groups']),
        'additional_protected_queries':len(new_protections),
        'existing_held_protection_occurrences':len(material['review']['fresh_variant_review']['existing_held_protection_keys']),
        'additional_variant_hold_groups':len(material['review']['fresh_variant_review']['additional_variant_holds']),
        'record_bodies_sha256':stage.digest(new),'source_pins':dict(SOURCE_PINS),
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},
        'search_demand_verified':False,**{key:False for key in LIMITS}}
    summary = {'scope':'CURRENT_RESEARCH_AFTER_VETERINARY_APPEND_ONLY_REVIEW',
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
        previous['remaining']['ACADEMIC'] == 117 and sum(previous['admitted'].values()) == n and
        sum(previous['targets'].values()) == 14000,'VETERINARY_ALLOCATION_BASE_CHANGED')
    admitted = dict(previous['admitted']); admitted['ACADEMIC'] += len(new)
    remaining = {key:previous['targets'][key]-value for key,value in admitted.items()}
    first.need(all(type(value) is int and value >= 0 for value in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']),'VETERINARY_ALLOCATION_COUNTS')
    allocation = {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':previous_pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'held_deduction':{},'new_rows':{'ACADEMIC':len(new)},'admitted':admitted,
        'remaining':remaining,'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),
        'basis':'Preserve all prior bodies, archives, protection prefix and category targets; append only reviewed complete veterinary qualification literals after fresh full-body checks.',
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
    first.need(first.canonical(inputs) == first.canonical(expected),'VETERINARY_DERIVED_BODIES_CHANGED')
    documents,summary = _outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return dict(summary,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',release_held=True)
