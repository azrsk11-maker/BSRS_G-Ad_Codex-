"""Append-only official bank credential-recovery-title research, never exclusion approval.

Every public invocation starts with caller-fresh complete history. Pinned saved
metadata binds bodies; it is not a serialized baseline or acceptance cache.
"""
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
from pathlib import Path
import runpy
import re
from collections import Counter

import append_only_admission as stage
import ofqual_veterinary_admission as prior
from followup_admission import VALIDITY
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first

FOLDER = 'docs/audit/keyword-negative-bank-credential-admission-2026-11-12'
CAPTURE = 'docs/audit/keyword-bank-access-navigation-2026-11-12'
SOURCE_PINS = {
    CAPTURE+'/bank-access-navigation.json':'822129ae18676ee62700c0726dcc11179c1bb7293636f031d7f3908e6fc879ea',
    CAPTURE+'/capture.json':'a3d6fe2f1c2caa5c905651d4f8955a338118a6380d5a7e6251b17c82767f3c99',
    CAPTURE+'/credential-review-a.json':'89df3708b481a29d8c0d94ba068e99046e7f388ce2780cbc8e49af7d66dbbe6a',
    CAPTURE+'/credential-review-b.json':'4f8489d14c2b0233ce8db8c920a886eabc57baead6161d99864547bfab45fecb',
}
TEXT_PINS = {
    CAPTURE+'/verify_capture.py':'890ae388335ecef0088ccc8f21ef57bf5b49253e0e27c3f122e3f5228952cc7e',
    CAPTURE+'/README.md':'4b1d61ac2f1afe5e613a59ad050e03e97a2ddca5b99e702f87c26cf44be73677',
    CAPTURE+'/credential-review-a.md':'57086f255179de855c3abcc97d2f5799a3e4f1bf9da28a9534d620d5304ad520',
    CAPTURE+'/credential-review-b.md':'8242e0b5e2d34272c3ddc1b6c260b09468aff9e0598910aba5b80717a3e2fed7',
}
BASE_SHA256 = '0be4c040baa13d97f105f0f5cd514fd5717a29647b24d2b542b959b5ab4d295c'
REVIEW_PIN = 'f607d84650e6ddbd59027870c27df615590ec6c3f2b117da0e957f1b3bcb9210'
OUTPUT_PINS = {'index.json': '67434034ca5aa49ea7edcc7fb8652bf17bc559af7393c6a4279c322342475737', 'cohort-report.json': '6228a82433804a240364a7eaa6fca99dac3139b139be6d175b01155a25e7d350', 'library-report.json': '80e63619807bc6c4831daba9d3aff5f8afa375f2745a22b7d202258520f7a27b', 'research-pool-allocation.json': '5320bb346a4864a98fe508d98afbe43540202826fcadcbdb1e27eafdfa30b154'}
STAGE_KEY = 'bank_credential_append_only_state'
SOURCE_ID = 'KP-BANK-CREDENTIAL-RECOVERY-20261112'
INTENT = 'EXPLICIT_ACCOUNT_CREDENTIAL_RECOVERY_NAVIGATION_RESEARCH'
LIMITS = prior.LIMITS
RAW_SHA256 = '2893a10b0bc281451e62049540b1227a0b82a7f4de69ac365bd4ed489d298c2e'
PATTERN = r"\b(passwords?|reset)\b"
TOPIC = re.compile(PATTERN,re.IGNORECASE)
METHODS = ('normalized_exact','ordered_tokens','equal_token_bag','closed_alphanumeric')
# Lead implementation-reviewed, source-observed potential identity/spelling relationships.
# These spans are diagnostic markers only, never rewritten candidate wording or
# proven entity identities. No channel/product/action/method token is removed.
PROVIDER_SPAN_FAMILIES = (
    ('ICICI_POTENTIAL_PROVIDER_FORM',(('icici','bank'),('icici',))),
    ('SBI_STATE_BANK_OF_INDIA_POTENTIAL_IDENTITY',(('state','bank','of','india'),('sbi',))),
    ('FNB_FIRST_NATIONAL_BANK_UNRESOLVED_IDENTITY',(('first','national','bank'),('fnb',))),
    ('RBC_ROYAL_BANK_UNRESOLVED_IDENTITY',(('royal','bank'),('rbc',))),
    ('BOB_BANK_OF_BARODA_UNRESOLVED_IDENTITY',(('bank','of','baroda'),('bob',))),
    ('SCB_STANDARD_CHARTERED_UNRESOLVED_IDENTITY',(('standard','chartered','bank'),('scb',))),
    ('HDFC_POTENTIAL_PROVIDER_FORM',(('hdfc','bank'),('hdfc',))),
)


def implementation_binding(root):
    for relative, pin in TEXT_PINS.items():
        raw = (Path(root)/relative).read_bytes()
        first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == pin,
                   'BANK_CREDENTIAL_REVIEW_OR_EXTRACTOR_BYTES_CHANGED')
    return {'audit_and_compatibility': prior.implementation_binding(root),
            'source_extractor_and_peer_narrative_sha256': dict(TEXT_PINS)}


def occurrence(row):
    text = row['values']['Keyword']
    return {'source_ordinal':row['source_ordinal'],'source_line':row['source_line'],
        'original_literal':text,'literal_utf8_sha256':hashlib.sha256(text.encode('utf8')).hexdigest(),
        'complete_public_values_sha256':stage.digest(row['values'])}


def load_sources(root):
    docs = {path:first.pinned(root,path,pin) for path,pin in SOURCE_PINS.items()}
    implementation = implementation_binding(root)
    verifier = runpy.run_path(str(Path(root)/CAPTURE/'verify_capture.py'))
    first.need(verifier['verify']()['passed'] is True,'BANK_CREDENTIAL_CAPTURE_NOT_VERIFIED')
    batch,capture,a,b = (docs[CAPTURE+'/'+name] for name in
        ('bank-access-navigation.json','capture.json','credential-review-a.json','credential-review-b.json'))
    verifier['validate_batch'](batch)
    projection = batch['source_projection']
    first.need(projection['source_sha256'] == RAW_SHA256 and projection['source_bytes'] == 464600 and
        projection['record_count'] == projection['distinct_normalized_count'] == 3481 and
        len(projection['records']) == 3481 and len(projection['public_columns']) == 21 and
        capture['source_files'][0]['sha256'] == SOURCE_PINS[CAPTURE+'/bank-access-navigation.json'] and
        all(batch['controls'][key] is False for key in ('reviewed','approved','deployed',
            'live_campaign_changes','raw_export_committed')) and
        type(batch['controls']['master_rows_added']) is int and batch['controls']['master_rows_added'] == 0,
        'BANK_CREDENTIAL_SOURCE_IDENTITY_OR_AUTHORITY_CHANGED')
    rows = [{**row,'source_ordinal':ordinal} for ordinal,row in enumerate(projection['records'],1)]
    source_groups = {ka.normalize(row['values']['Keyword']):[row] for row in rows}
    cohort = [row for row in rows if TOPIC.search(row['values']['Keyword'])]
    first.need(len(source_groups) == 3481 and len(cohort) == 803,'BANK_CREDENTIAL_COMPLETE_COHORT_CHANGED')
    first.need(a['source_sha256'] == b['source_sha256'] == SOURCE_PINS[CAPTURE+'/bank-access-navigation.json'] and
        a['raw_source_sha256'] == RAW_SHA256 and a['selection_pattern'] == b['selection_pattern'] == PATTERN and
        a['selection_case_insensitive'] is True and b['selection_flags'] == 'IGNORECASE' and
        a['total_source_occurrences'] == b['source_rows'] == 3481 and a['total_selected'] == b['total_selected'] == 803 and
        a['partition'] == {'offset':0,'count':401,'first_source_ordinal':3,'last_source_ordinal':2274,
            'next_partition_first_source_ordinal':2278,'source_order_preserved':True} and
        b['partition'] == {'offset':401,'count':402,'selected_ordinal_first':402,'selected_ordinal_last':803,
            'source_ordinal_first':2278,'source_ordinal_last':3479,'source_line_first':2281,'source_line_last':3482} and
        a['semantic_summary'] == {'PROPOSE_FULL_EXACT_RESEARCH':352,'HOLD':49} and
        b['decision_counts'] == {'PROPOSE_FULL_EXACT_RESEARCH':274,'HOLD':128} and
        a['method']['all_401_complete_phrases_individually_read'] is True and
        a['method']['no_seed_or_metric_intent_inference'] is True and a['method']['no_quota_cutoff'] is True and
        b['boundaries']['research_proposal_only'] is True and
        all(value is False for key,value in b['boundaries'].items() if key != 'research_proposal_only'),
        'BANK_CREDENTIAL_PEER_IDENTITY_PARTITION_OR_AUTHORITY_CHANGED')
    for item in a['source_pins']:
        first.need(item['sha256'] == (SOURCE_PINS|TEXT_PINS)[CAPTURE+'/'+item['file']] and
            item['bytes'] == (Path(root)/CAPTURE/item['file']).stat().st_size,'BANK_CREDENTIAL_PEER_SOURCE_BINDING_CHANGED')
    first.need(len(a['decisions']) == 401 and len(b['decisions']) == 402,'BANK_CREDENTIAL_PEER_PARTITION_COVERAGE_CHANGED')
    decisions = {};proposed=[];semantic_proposed=[];initial_holds={};strict_batch_holds={};profiles={}
    for index,(row,decision) in enumerate(zip(cohort,a['decisions']+b['decisions']),1):
        key=ka.normalize(row['values']['Keyword']);text=row['values']['Keyword'];is_a=index<=401
        first.need(type(decision['source_ordinal']) is int and decision['source_ordinal'] == row['source_ordinal'] and
            type(decision['source_line']) is int and decision['source_line'] == row['source_line'] and
            decision['original_literal'] == text and decision['normalized_phrase'] == key and
            decision['literal_sha256'] == hashlib.sha256(text.encode('utf8')).hexdigest() and
            decision['decision'] in {'PROPOSE_FULL_EXACT_RESEARCH','HOLD'} and
            type(decision['reason']) is str and bool(decision['reason'].strip()) and
            decision['selection_index' if is_a else 'selected_ordinal'] == index,
            'BANK_CREDENTIAL_FULL_LITERAL_OR_PARTITION_CHANGED')
        if is_a:
            flags=decision['intent_flags'];eq=decision['equivalence_flags']
            first.need(type(flags) is list and type(eq) is list and
                'FULL_SOURCE_AND_CURRENT_LIBRARY_EQUIVALENCE_UNCHECKED' in eq and
                'NO_CANONICAL_WORD_ORDER_SELECTED' in eq,'BANK_CREDENTIAL_PEER_EQUIVALENCE_CHANGED')
            recovery=bool(set(flags)&{'EXPLICIT_CREDENTIAL_RESET','FORGOTTEN_CREDENTIAL_RECOVERY',
                'CREDENTIAL_REGENERATION','EXPIRED_CREDENTIAL_ACCESS_RECOVERY'})
        else:
            flags=decision['intent_flags'];eq=decision['equivalence_flags']
            first.need(eq == {'full_original_literal_only':True,'word_order_check':'UNRESOLVED',
                'provider_equivalence_check':'UNRESOLVED','closed_alias_check':'UNRESOLVED',
                'compatibility_check':'UNRESOLVED','protected_scope_check':'UNRESOLVED',
                'current_library_and_archive_membership_check':'NOT_PERFORMED','canonical_equivalence_selection':'NOT_SELECTED'} and
                flags['complete_literal_reviewed'] is True and
                all(type(value) is bool for name,value in flags.items() if name!='official_provider_reference_ids'),
                'BANK_CREDENTIAL_PEER_EQUIVALENCE_CHANGED')
            recovery=flags['explicit_recovery_wording']
        profile=compatibility.profile_text(text)['original'];profiles[key]=profile
        reasons=[]
        if decision['decision']=='HOLD':reasons.append('INDEPENDENT_COMPLETE_LITERAL_SEMANTIC_HOLD')
        else:
            semantic_proposed.append(key)
            if not recovery:
                reasons.append('CURRENT_RECOVERY_BATCH_SETUP_OR_ACCESS_RELATIONSHIP_UNRESOLVED')
                strict_batch_holds[key]={'source_ordinal':row['source_ordinal'],
                    'semantic_decision':decision['decision'],'explicit_recovery_flag':False,
                    'original_reason':decision['reason'],
                    'limit':'Current recovery-batch HOLD only; setup/account-access remains within the full NAVIGATION goal for separate reconciliation. No property value, permanent ineligibility or semantic reversal inferred.'}
        if profile['classification'] != 'NO_KNOWN_INCOMPATIBILITY_DETECTED':
            reasons.append('ORIGINAL_LITERAL_TEXT_COMPATIBILITY_HOLD')
        if reasons:initial_holds[key]=reasons
        else:proposed.append(key)
        decisions[key]=decision
    first.need(len(decisions) == 803 and len(semantic_proposed) == 626 and len(strict_batch_holds) == 26 and
        Counter(row['decision'] for row in decisions.values()) == {'PROPOSE_FULL_EXACT_RESEARCH':626,'HOLD':177},
        'BANK_CREDENTIAL_SEMANTIC_OR_BATCH_HOLDS_CHANGED')
    return {'groups':{ka.normalize(row['values']['Keyword']):[row] for row in cohort},
        'source_groups':source_groups,'decisions':decisions,'proposed':sorted(proposed),
        'semantic_proposed':sorted(semantic_proposed),'initial_holds':initial_holds,
        'strict_batch_holds':strict_batch_holds,'profiles':profiles,'batch':batch,'projection':projection,
        'capture':capture,'peer_a':a,'peer_b':b,'implementation':implementation,
        'context':first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN),
        'registry':first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])}


def _closed(text):
    return ''.join(char for char in ka.normalize(text) if char.isalnum())


def _keys(text):
    tokens=tuple(ka.tokens(text))
    return (ka.normalize(text),tokens,tuple(sorted(tokens)),_closed(text))


def family_holds(source_groups):
    """Hold only exact remaining ordered-token collisions after a listed span.

    Shared-provider parent membership is retained as a diagnostic. It never
    supplies a hold, canonical choice, semantic disposition or concept count.
    """
    conflicts={};reviews=[]
    for family,spans in PROVIDER_SPAN_FAMILIES:
        signatures=defaultdict(list);parent=[]
        for key,rows in source_groups.items():
            tokens=tuple(ka.tokens(rows[0]['values']['Keyword']));matches=[]
            for span in spans:
                for offset in range(len(tokens)-len(span)+1):
                    if tokens[offset:offset+len(span)]==span:
                        matches.append((len(span),offset,span))
            if not matches:continue
            length,offset,span=max(matches,key=lambda value:(value[0],-value[1]))
            signature=tokens[:offset]+('@'+family,)+tokens[offset+length:]
            member={'source_ordinal':rows[0]['source_ordinal'],'normalized_phrase':key,
                'original_provider_span_tokens':list(span),'span_token_offset':offset}
            signatures[signature].append(member);parent.append(rows[0]['source_ordinal'])
        collisions=[]
        for signature,members in signatures.items():
            if len({tuple(member['original_provider_span_tokens']) for member in members})<2:continue
            collision={'remaining_ordered_token_signature':list(signature),'members':members}
            collisions.append(collision)
            for member in members:
                key=member['normalized_phrase']
                conflicts.setdefault(key,[]).append({'kind':'narrow_provider_span_ordered_remainder_hold',
                    'family_key':family,'source_peer_ordinals':[other['source_ordinal'] for other in members
                        if other['source_ordinal']!=member['source_ordinal']],
                    'limit':'Potential provider spelling/identity relation only; all nonprovider tokens identical. No proven identity, canonical phrase or Google-equivalence claim.'})
        reviews.append({'family_key':family,'listed_potential_provider_spans':[list(span) for span in spans],
            'narrow_ordered_remainder_collision_groups':collisions,
            'broad_shared_provider_source_ordinals_diagnostic_only':parent,
            'broad_parent_membership_causes_hold':False,
            'limit':'Master counts distinct supported full phrases. Different credential/product/channel/method or generic/specific wording is not held solely for this shared provider.'})
    return conflicts,reviews


def membership(base, material):
    """Actually join every complete source group, including all pre-held rows."""
    maps={kind:defaultdict(set) for kind in METHODS};own={kind:defaultdict(set) for kind in METHODS}
    protected_exact=set()
    for field,textfield,idfield in (('records','original_text','keyword_id'),
        ('archived_records','original_text','keyword_id'),('protected_queries','text','query_id')):
        for row in base[field]:
            for kind,value in zip(METHODS,_keys(row[textfield])):maps[kind][value].add(field+':'+row[idfield])
            if field=='protected_queries':protected_exact.add(ka.normalize(row[textfield]))
    for key,rows in material['source_groups'].items():
        for kind,value in zip(METHODS,_keys(rows[0]['values']['Keyword'])):own[kind][value].add(key)
    joins={};all_conflicts={};external=internal=0
    for key,rows in material['source_groups'].items():
        results=[];reasons=[]
        for kind,value in zip(METHODS,_keys(rows[0]['values']['Keyword'])):
            existing=sorted(maps[kind].get(value,set()));others=sorted(own[kind].get(value,set())-{key})
            external+=1;internal+=1
            results.append({'method':kind,'existing_identities':existing,
                'source_peer_ordinals':[material['source_groups'][other][0]['source_ordinal'] for other in others]})
            if existing:reasons.append({'kind':kind,'existing_identities':existing})
            if others:reasons.append({'kind':'within_capture_'+kind,'other_normalized_phrases':others,
                'outside_cohort_peer_ordinals':[material['source_groups'][other][0]['source_ordinal'] for other in others if other not in material['groups']]})
        joins[key]={'source_ordinal':rows[0]['source_ordinal'],'joins':results,
            'semantic_state':'REVIEWED_COHORT' if key in material['groups'] else 'UNASSESSED_NONCOHORT_NOT_ADMITTED'}
        if reasons:all_conflicts[key]=reasons
    families,family_review=family_holds(material['source_groups'])
    for key,reasons in families.items():all_conflicts.setdefault(key,[]).extend(reasons)
    proposed=set(material['proposed']);selected=sorted(proposed-set(all_conflicts))
    held=sorted(set(material['groups'])-set(selected))
    first.need(all(not any(identity.startswith('records:') for reason in all_conflicts.get(key,[])
        for identity in reason.get('existing_identities',[])) for key in held),
        'BANK_CREDENTIAL_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    first.need(len(joins)==len(material['source_groups']) and external==internal==4*len(joins) and
        set(material['groups'])<=set(joins),'BANK_CREDENTIAL_INCOMPLETE_SOURCE_GROUP_COMPARISONS')
    return {'selected_normalized_phrases':selected,'all_held_normalized_phrases':held,
        'additional_variant_holds':{key:all_conflicts[key] for key in sorted(proposed&set(all_conflicts))},
        'all_source_group_conflicts':all_conflicts,
        'preheld_source_group_conflicts':{key:all_conflicts[key] for key in sorted((set(material['groups'])-proposed)&set(all_conflicts))},
        'existing_held_protection_keys':sorted(set(held)&protected_exact),
        'source_group_join_results':joins,'source_groups_compared':len(joins),
        'cohort_groups_compared':sum(key in joins for key in material['groups']),
        'external_key_comparisons':external,'within_source_key_comparisons':internal,
        'cohort_external_key_comparisons':4*sum(key in joins for key in material['groups']),
        'cohort_within_source_key_comparisons':4*sum(key in joins for key in material['groups']),
        'source_family_review':family_review,'strict_recovery_batch_holds':material['strict_batch_holds'],
        'noncohort_state':'UNASSESSED_NOT_ADMITTED_NOT_REVIEWED_AS_A_GROUP',
        'noncohort_source_groups':len(material['source_groups'])-len(material['groups']),
        'complete_base_counts':{field:len(base[field]) for field in
            ('records','archived_records','protected_queries','sources','campaigns','campaign_context')},
        'lexical_methods':list(METHODS),'google_equivalence_verified':False,'counts_distinct_concepts':False}


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources',
            'campaigns','campaign_context')) == (11176,18,16738,26,360,1) and
        sum(len(row['provenance_occurrences']) for row in base['records']) == 11389 and
        base['campaigns'] == material['registry'], 'BANK_CREDENTIAL_PRIOR_BASE_CHANGED')
    return membership(base,material)


def review_subject(review, material):
    return stage.digest({'review':{key:value for key,value in review.items() if key != 'subject_sha256'},
        'context':material['context'],'registry':material['registry'],
        'source_pins':SOURCE_PINS,'text_pins':TEXT_PINS,'implementation':material['implementation']})


def make_review(base, root=first.ROOT, when=None):
    when = first.dubai_date() if when is None else when
    material = load_sources(root); diagnostic = verify_base(base,material)
    selected = diagnostic['selected_normalized_phrases']
    first.need(0 <= len(selected) <= 1000, 'BANK_CREDENTIAL_NAVIGATION_HEADROOM')
    held = {}
    for key in diagnostic['all_held_normalized_phrases']:
        if key in diagnostic['additional_variant_holds']:
            reason = 'Fresh complete current/archive/protected, within-source lexical or explicitly reviewed provider/route relationship remains HOLD; retain full literal.'
        elif key not in material['proposed']:
            reason = 'Original semantic, recovery-batch setup/access or text compatibility HOLD; preserve exact independent reasons and full literal. No permanent ineligibility or property value is inferred.'
        else:
            reason = 'Independent full-literal semantic or documented-symbol HOLD; preserve exact source and peer reasons.'
        held[key] = reason
    review = {'version':1,'scope':'AI_REVIEWED_BANK_CREDENTIAL_TITLES_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN',
        'reviewed_on':when.isoformat(),'valid_until':(when+timedelta(days=30)).isoformat(),
        'validity_basis':VALIDITY,'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_phrases':selected,'held_groups':held,'fresh_variant_review':diagnostic,
        'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Two independent complete-literal AI partitions supply intent proposals only. This recovery batch retains semantic, setup/access, compatibility, provider/route, full-source-peer and complete-base holds without choosing canonical wording or forcing a proposal count. Preserve every original literal, source row and unknown metric boundary.',
        'source_identity_limits':'Complete Planner credential-recovery literals are not observed served queries, actual CPC, current demand or platform matching certification. Historical provider estimate strings remain only in the frozen full source; no metric is promoted. Noncohort source rows remain unassessed and unadmitted.',
        **{key:False for key in LIMITS}}
    review['subject_sha256'] = review_subject(review,material)
    validate_review(review,material,when)
    return review


def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_normalized_phrases','held_groups','fresh_variant_review',
        'source_pins','text_pins','implementation','base_sha256','semantic_rationale','source_identity_limits',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review) == required and type(review['version']) is int and
        review['version'] == 1 and review['scope'] == 'AI_REVIEWED_BANK_CREDENTIAL_TITLES_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[key] is False for key in LIMITS),'BANK_CREDENTIAL_REVIEW_AUTHORITY')
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
        'BANK_CREDENTIAL_SCOPE_CHANGED')
    selected = review['selected_normalized_phrases']; held = review['held_groups']
    first.need(type(selected) is list and selected == sorted(set(selected)) and
        0 <= len(selected) <= 1000 and set(selected) <= set(material['proposed']) and
        type(held) is dict and set(held) == set(material['groups'])-set(selected) and
        all(type(value) is str and value.strip() for value in held.values()) and
        selected == review['fresh_variant_review']['selected_normalized_phrases'] and
        sorted(held) == review['fresh_variant_review']['all_held_normalized_phrases'] and
        review['source_pins'] == SOURCE_PINS and review['text_pins'] == TEXT_PINS and
        review['implementation'] == material['implementation'] and review['base_sha256'] == BASE_SHA256 and
        all(type(review[key]) is str and review[key].strip() for key in
            ('semantic_rationale','source_identity_limits')), 'BANK_CREDENTIAL_REVIEW_BINDINGS_CHANGED')
    start,end = date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        start <= when <= end and end-start == timedelta(days=30) and review['validity_basis'] == VALIDITY and
        material['capture']['capture_date_dubai'] == material['peer_a']['reviewed_at_utc'][:10] == material['peer_b']['review_date'] == review['reviewed_on'] and
        context['observed_date_dubai'] <= review['reviewed_on'], 'BANK_CREDENTIAL_REVIEW_DATES')
    first.need(review['subject_sha256'] == review_subject(review,material),'BANK_CREDENTIAL_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN) == 64,'BANK_CREDENTIAL_REVIEW_UNREGISTERED')
    review = first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_review(review,material,when)
    return dict(material,review=review)


def build_cohort(base, material):
    review=material['review'];records=[]
    for key in review['selected_normalized_phrases']:
        row=material['groups'][key][0];decision=material['decisions'][key]
        peer='credential-review-a.json' if decision.get('selection_index',804)<=401 else 'credential-review-b.json'
        occurrences=[{'batch':SOURCE_ID,**occurrence(row),'original_text':row['values']['Keyword'],
            'file':CAPTURE+'/bank-access-navigation.json','sha256':SOURCE_PINS[CAPTURE+'/bank-access-navigation.json'],
            'raw_source_sha256':RAW_SHA256,'capture_file':CAPTURE+'/capture.json',
            'capture_sha256':SOURCE_PINS[CAPTURE+'/capture.json'],
            'review_file':FOLDER+'/review.json','review_sha256':REVIEW_PIN,
            'independent_review_file':CAPTURE+'/'+peer,'independent_review_sha256':SOURCE_PINS[CAPTURE+'/'+peer]}]
        adapted={'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW','original_forms':[row['values']['Keyword']],
            'assessment':{'intent':INTENT,'negative_scope_proposal':
                {'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record=first.make_record(adapted,review,occurrences,source_id=SOURCE_ID,
            source_reference=CAPTURE+'/bank-access-navigation.json#source_ordinal='+str(row['source_ordinal']),
            review_folder=FOLDER,allowed_intents={INTENT})
        record['evidence_ref']=FOLDER+'/review.json#'+key;records.append(record)
    source={'source_id':SOURCE_ID,'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-12','valid_until':review['valid_until'],
        'capture_kind':'authentic_keyword_planner_credential_recovery_subset',
        'research_use_basis':'OWNER_AUTHORIZED_RESEARCH_AND_PINNED_PLANNER_SOURCE_WITH_TWO_AI_LITERAL_REVIEWS',
        'metrics_in_source_are_historical_provider_estimates':True,'metrics_copied_into_records':False,
        'served_query_or_current_performance_claimed':False}
    existing=set(review['fresh_variant_review']['existing_held_protection_keys'])
    protections=[{'query_id':'BSRE-Q-'+hashlib.sha256(key.encode('utf8')).hexdigest()[:24],
        'text':key,'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
        'evidence_ref':FOLDER+'/review.json#'+key,'reviewed_on':review['reviewed_on'],
        'valid_until':review['valid_until'],'source_kind':'official_reference',
        'protection_basis':'UNRESOLVED_CURRENT_BATCH_FULL_LITERAL_NOT_VALUED_DEMAND_OR_PERMANENT_INELIGIBILITY'}
        for key in sorted(review['held_groups']) if key not in existing]
    return {'records':records,'sources':[source],'protected_queries':[],
        'campaigns':base['campaigns'],'campaign_context':base['campaign_context']},protections


def extend(base, root, when):
    material = load_reviewed(root,when)
    diagnostic = verify_base(base,material)
    first.need(diagnostic == material['review']['fresh_variant_review'],'BANK_CREDENTIAL_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections = build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result = stage.checked_audit(inputs,when)
    state = inputs[STAGE_KEY]; n = state['retained_records']; new = inputs['records'][n:]
    new_protections = inputs['protected_queries'][state['retained_protections']:]
    first.need(len(new) == len(material['review']['selected_normalized_phrases']) and
        sum(len(row['provenance_occurrences']) for row in new) ==
        sum(len(material['groups'][key]) for key in material['review']['selected_normalized_phrases']),
        'BANK_CREDENTIAL_SOURCE_OCCURRENCES_CHANGED')
    index = {'version':1,'scope':'APPEND_ONLY_BANK_CREDENTIAL_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[row['keyword_id'] for row in new],
        'additional_protected_query_ids':[row['query_id'] for row in new_protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    diagnostic=material['review']['fresh_variant_review']
    cohort = {'scope':'AI_REVIEWED_BANK_CREDENTIAL_RECOVERY_RESEARCH_NOT_SEARCH_DEMAND',
        'full_source_groups':3481,'full_source_occurrences':3481,'cohort_groups':803,
        'semantic_proposed_groups':626,'semantic_hold_groups':177,
        'strict_recovery_batch_holds':len(material['strict_batch_holds']),
        'compatible_recovery_proposed_groups':len(material['proposed']),'selected_groups':len(new),
        'all_source_groups_compared':diagnostic['source_groups_compared'],
        'cohort_groups_compared':diagnostic['cohort_groups_compared'],
        'external_key_comparisons':diagnostic['external_key_comparisons'],
        'within_source_key_comparisons':diagnostic['within_source_key_comparisons'],
        'cohort_external_key_comparisons':diagnostic['cohort_external_key_comparisons'],
        'cohort_within_source_key_comparisons':diagnostic['cohort_within_source_key_comparisons'],
        'noncohort_groups':2678,'noncohort_state':'UNASSESSED_NOT_ADMITTED',
        'retained_new_occurrences':sum(len(row['provenance_occurrences']) for row in new),
        'held_groups':len(material['review']['held_groups']),
        'additional_protected_queries':len(new_protections),
        'existing_held_protection_occurrences':len(diagnostic['existing_held_protection_keys']),
        'additional_variant_hold_groups':len(diagnostic['additional_variant_holds']),
        'text_compatibility_classifications':dict(sorted(Counter(profile['classification'] for profile in material['profiles'].values()).items())),
        'record_bodies_sha256':stage.digest(new),'source_pins':dict(SOURCE_PINS),
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},
        'search_demand_verified':False,**{key:False for key in LIMITS}}
    summary = {'scope':'CURRENT_RESEARCH_AFTER_BANK_CREDENTIAL_APPEND_ONLY_REVIEW',
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
        previous['remaining']['NAVIGATION'] == 1000 and sum(previous['admitted'].values()) == n and
        sum(previous['targets'].values()) == 14000,'BANK_CREDENTIAL_ALLOCATION_BASE_CHANGED')
    admitted = dict(previous['admitted']); admitted['NAVIGATION'] += len(new)
    remaining = {key:previous['targets'][key]-value for key,value in admitted.items()}
    first.need(all(type(value) is int and value >= 0 for value in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']),'BANK_CREDENTIAL_ALLOCATION_COUNTS')
    allocation = {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':previous_pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'held_deduction':{},'new_rows':{'NAVIGATION':len(new)},'admitted':admitted,
        'remaining':remaining,'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),
        'basis':'Preserve all prior bodies, archives, protection prefix and category targets; append only compatible complete credential-recovery literals after fresh full-body and all-source-peer checks; preserve current-batch holds without declaring valued demand or permanent ineligibility.',
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
    first.need(first.canonical(inputs) == first.canonical(expected),'BANK_CREDENTIAL_DERIVED_BODIES_CHANGED')
    documents,summary = _outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return dict(summary,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',release_held=True)
