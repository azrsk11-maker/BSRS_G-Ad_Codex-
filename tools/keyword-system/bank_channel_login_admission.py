"""Append-only, full-literal banking-channel login research; never exclusion or release approval."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
from pathlib import Path
import runpy

import append_only_admission as stage
import bank_credential_admission as comparator
import ofqual_animal_care_admission as prior
import bank_support_admission as support
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first
from followup_admission import VALIDITY

FOLDER = 'docs/audit/keyword-negative-bank-channel-login-admission-2026-11-13'
SEMANTIC = 'docs/audit/keyword-bank-channel-login-review-2026-11-13'
CAPTURE = comparator.CAPTURE
SOURCE_PINS = dict(comparator.SOURCE_PINS) | {
'docs/audit/keyword-bank-channel-login-review-2026-11-13/review.json': '0c5dd4ffe8cbe4a39f11e17f6e309cb492a106bde1ac3ef378d299e4b790d147',
'docs/audit/keyword-bank-support-review-2026-11-12/review.json': 'cc3a3d36d564bb577cc1b8b2015e3600e5d8daaecd2fa3b30a80246f7ffca89d'}
TEXT_PINS = {'docs/audit/keyword-bank-channel-login-review-2026-11-13/verify_review.py': '5a9c8e11f929dd5c3a158044795ec7ca76101a9e6f08b5a8cb2b721288edff3a', 'docs/audit/keyword-bank-channel-login-review-2026-11-13/README.md': 'f12d74f826b3eba4442f39a25a41b87616474b1a433c6d68cab581ad1eec9b38', 'tools/keyword-system/ofqual_animal_care_admission.py': '41e08b991106a6ca3a7b89b9223f8187549c835ba347cb38ce368d36568e6208', 'tools/keyword-system/bank_support_admission.py': '7751b56078497921dae4e812c1299e30a699b7acd661f200ef034216d703565f'}
BASE_SHA256 = 'ea897a269a001239ab9d2ef1a75f9640909c1a55f66c6c8e5e40ec98623c3765'
REVIEW_PIN = 'cf6bd76fb5438976ce1984086ff49014819b2a9d68e22a325d24e98c5e6337bb'
OUTPUT_PINS = {'index.json': '364fa785057f2bf825d627d71ef944b977eab1c243aa530f5e3319587c2c7f88', 'cohort-report.json': 'bf70563984b61b9c34483b762ada6bfc233a5cb471ac3d1934567bbca8a4c814', 'library-report.json': '9285460d607d99491fb340999a9c146b7f13e800ec2465de47500574c2702220', 'research-pool-allocation.json': '7b0225d3d59d22e62cbcb9c281171f4832650ddbe5273d785e6781fdfce04746'}
STAGE_KEY = 'bank_channel_login_append_only_state'
SOURCE_ID = 'KP-BANK-CHANNEL-LOGIN-20261113'
INTENT = 'EXPLICIT_BANKING_CHANNEL_LOGIN_NAVIGATION_RESEARCH'
LIMITS = prior.LIMITS
# Potential relationships observed in source wording, not verified identities.
# Only an identical ordered nonprovider remainder can produce a variant hold.
# Products (including Liv), channels and actions stay outside these spans.
PROVIDER_SPANS = support.PROVIDER_SPANS + (('HDFC_POTENTIAL_PROVIDER_FORM', (('hdfc', 'bank'), ('hdfc',))), ('ICICI_POTENTIAL_PROVIDER_FORM', (('icici', 'bank'), ('icici',))), ('IDBI_POTENTIAL_PROVIDER_FORM', (('idbi', 'bank'), ('idbi',))), ('INDUSIND_POTENTIAL_PROVIDER_FORM', (('indusind', 'bank'), ('indusind',))), ('KOTAK_POTENTIAL_PROVIDER_FORM', (('kotak', 'mahindra', 'bank'), ('kotak', 'mahindra'), ('kotak', 'bank'), ('kotak',))), ('STANDARD_CHARTERED_POTENTIAL_PROVIDER_FORM', (('standard', 'chartered', 'bank'), ('standard', 'chartered'))), ('YES_POTENTIAL_PROVIDER_FORM', (('yes', 'bank'), ('yes',))), ('SBI_UNRESOLVED_PROVIDER_FORM', (('state', 'bank', 'of', 'india'), ('sbi',))), ('BOI_UNRESOLVED_PROVIDER_FORM', (('bank', 'of', 'india'), ('boi',))), ('BOB_UNRESOLVED_PROVIDER_FORM', (('bank', 'of', 'baroda'), ('bob',))), ('UNION_INDIA_UNRESOLVED_PROVIDER_FORM', (('union', 'bank', 'of', 'india'), ('union', 'bank'), ('unionbank',), ('union',))))


def implementation_binding(root):
    for path, pin in TEXT_PINS.items():
        raw = (Path(root)/path).read_bytes()
        first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == pin,
                   'BANK_CHANNEL_LOGIN_REVIEW_OR_DEPENDENCY_CHANGED')
    return {'prior_bank_implementation': prior.implementation_binding(root),
            'support_review_and_dependency_sha256': dict(TEXT_PINS)}


def load_sources(root):
    documents = {path:first.pinned(root,path,pin) for path,pin in SOURCE_PINS.items()}
    implementation = implementation_binding(root)
    verifier = runpy.run_path(str(Path(root)/SEMANTIC/'verify_review.py'))
    semantic = documents[SEMANTIC+'/review.json']
    verifier['validate'](semantic, dict({Path(p).name:documents[p] for p in comparator.SOURCE_PINS}, **{'support-review.json':documents['docs/audit/keyword-bank-support-review-2026-11-12/review.json']}))
    rows = [{**r,'source_ordinal':n} for n,r in enumerate(
        documents[CAPTURE+'/bank-access-navigation.json']['source_projection']['records'],1)]
    source_groups = {ka.normalize(r['values']['Keyword']):[r] for r in rows}
    decisions = {}; profiles = {}; groups = {}; proposed = []; initial_holds = {}
    for decision in semantic['decisions']:
        row = rows[decision['source_ordinal']-1]
        key = ka.normalize(row['values']['Keyword'])
        profile = compatibility.profile_text(row['values']['Keyword'])['original']
        groups[key] = [row]; decisions[key] = decision; profiles[key] = profile
        reasons = []
        if decision['decision'] == 'HOLD': reasons.extend(decision['reason_codes'])
        if profile['classification'] != 'NO_KNOWN_INCOMPATIBILITY_DETECTED':
            reasons.append('ORIGINAL_LITERAL_TEXT_COMPATIBILITY_HOLD')
        if reasons: initial_holds[key] = reasons
        else: proposed.append(key)
    first.need(len(source_groups) == 3481 and len(groups) == 251 and len(proposed) == 226 and
               len(initial_holds) == 25, 'BANK_CHANNEL_LOGIN_SEMANTIC_OR_COMPATIBILITY_CHANGED')
    earlier = documents[CAPTURE+'/credential-review-a.json']['decisions'] + documents[CAPTURE+'/credential-review-b.json']['decisions'] + documents['docs/audit/keyword-bank-support-review-2026-11-12/review.json']['decisions']
    previous_keys = {ka.normalize(rows[r['source_ordinal']-1]['values']['Keyword']) for r in earlier}
    return {'groups':groups,'source_groups':source_groups,'decisions':decisions,'profiles':profiles,
        'proposed':sorted(proposed),'initial_holds':initial_holds,'strict_batch_holds':{},
        'previous_reviewed_keys':previous_keys,
        'semantic':semantic,'implementation':implementation,
        'context':first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN),
        'registry':first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])}


def provider_holds(source_groups):
    conflicts = {}; diagnostics = []
    for family, spans in PROVIDER_SPANS:
        signatures = defaultdict(list); parents = []
        for key, rows in source_groups.items():
            tokens = tuple(ka.tokens(rows[0]['values']['Keyword']))
            matches = [(len(span), offset, span) for span in spans
                       for offset in range(len(tokens)-len(span)+1)
                       if tokens[offset:offset+len(span)] == span]
            if not matches: continue
            length, offset, span = max(matches,key=lambda v:(v[0],-v[1]))
            signature = tokens[:offset]+('@'+family,)+tokens[offset+length:]
            signatures[signature].append({'source_ordinal':rows[0]['source_ordinal'],
                'normalized_phrase':key,'original_provider_span_tokens':list(span),
                'span_token_offset':offset})
            parents.append(rows[0]['source_ordinal'])
        collisions = []
        for signature, members in signatures.items():
            if len({tuple(m['original_provider_span_tokens']) for m in members}) < 2: continue
            collisions.append({'remaining_ordered_token_signature':list(signature),'members':members})
            for member in members:
                conflicts.setdefault(member['normalized_phrase'],[]).append({
                    'kind':'channel_login_provider_span_identical_ordered_remainder_hold','family_key':family,
                    'source_peer_ordinals':[p['source_ordinal'] for p in members if p != member],
                    'verified_identity_or_google_equivalence':False})
        diagnostics.append({'family_key':family,'potential_provider_spans':[list(s) for s in spans],
            'narrow_ordered_remainder_collisions':collisions,
            'broad_shared_provider_source_ordinals_diagnostic_only':parents,
            'broad_parent_membership_causes_hold':False})
    return conflicts, diagnostics


def membership(base, material):
    # The prior pure comparison covers all source groups, even held and outside
    # this cohort. It does not load its old base, saved diagnostic or admission.
    diagnostic = comparator.membership(base,material)
    extra, families = provider_holds(material['source_groups'])
    conflicts = diagnostic['all_source_group_conflicts']
    for key, reasons in extra.items(): conflicts.setdefault(key,[]).extend(reasons)
    selected = sorted(set(material['proposed'])-set(conflicts))
    held = sorted(set(material['groups'])-set(selected))
    first.need(all(not any(identity.startswith('records:') for reason in conflicts.get(key,[])
        for identity in reason.get('existing_identities',[])) for key in held),
        'BANK_CHANNEL_LOGIN_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    diagnostic.update(selected_normalized_phrases=selected, all_held_normalized_phrases=held,
        additional_variant_holds={k:conflicts[k] for k in sorted(set(material['proposed'])&set(conflicts))},
        preheld_source_group_conflicts={k:conflicts[k] for k in sorted(set(material['initial_holds'])&set(conflicts))},
        channel_login_provider_span_review=families,
        existing_held_protection_keys=sorted(set(held)&{ka.normalize(r['text']) for r in base['protected_queries']}))
    diagnostic['noncohort_state']='OUTSIDE_CURRENT_CHANNEL_LOGIN_COHORT_NOT_ADMITTED_BY_THIS_STAGE'
    for key, join in diagnostic['source_group_join_results'].items():
        join['semantic_state']=('REVIEWED_CURRENT_CHANNEL_LOGIN_COHORT' if key in material['groups'] else
            'PREVIOUSLY_REVIEWED_BANK_COHORTS' if key in material['previous_reviewed_keys'] else
            'UNASSESSED_OUTSIDE_ALL_THREE_SEMANTIC_COHORTS')
    return diagnostic


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources','campaigns','campaign_context'))
        == (11986,18,17634,29,360,1) and
        sum(len(r['provenance_occurrences']) for r in base['records']) == 12199 and
        base['campaigns'] == material['registry'], 'BANK_CHANNEL_LOGIN_PRIOR_BASE_CHANGED')
    return membership(base,material)


def review_subject(review, material):
    return stage.digest({'review':{k:v for k,v in review.items() if k!='subject_sha256'},
        'context':material['context'],'registry':material['registry'],'source_pins':SOURCE_PINS,
        'text_pins':TEXT_PINS,'implementation':material['implementation']})


def make_review(base, root=first.ROOT, when=None):
    when = first.dubai_date() if when is None else when
    material = load_sources(root); diagnostic = verify_base(base,material)
    review = {'version':1,'scope':'AI_REVIEWED_BANK_CHANNEL_LOGIN_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN',
        'reviewed_on':when.isoformat(),'valid_until':(when+timedelta(days=30)).isoformat(),
        'validity_basis':VALIDITY,'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_phrases':diagnostic['selected_normalized_phrases'],
        'held_groups':{key:('Original semantic/text HOLD or fresh complete membership/provider/route conflict; '
                          'preserve full literal and exact source-bound diagnostics without canonical repair.')
                       for key in diagnostic['all_held_normalized_phrases']},
        'fresh_variant_review':diagnostic,'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Lead AI read all251 complete banking-channel login literals. Retain25 semantic holds. Append only source-bound full phrases after fresh complete-history, source-peer and narrow provider-span checks. Distinct phrases are not redefined as distinct concepts; no generic bank or financial exclusion is proposed.',
        'source_identity_limits':'Planner ideas/historical estimate strings are not served queries, actual CPC, current demand, verified provider identities or Google matching certification. Lead AI review is not independent human approval. All1,737 outside all three semantic cohorts remain unassessed for intent.',
        **{key:False for key in LIMITS}}
    review['subject_sha256'] = review_subject(review,material)
    validate_review(review,material,when)
    return review


def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_normalized_phrases','held_groups','fresh_variant_review',
        'source_pins','text_pins','implementation','base_sha256','semantic_rationale','source_identity_limits',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review)==required and type(review['version']) is int and
        review['version']==1 and review['scope']=='AI_REVIEWED_BANK_CHANNEL_LOGIN_NOT_EXCLUSION_APPROVAL' and
        review['reviewer']==first.REVIEWER and review['reviewer_kind']=='CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'BANK_CHANNEL_LOGIN_REVIEW_AUTHORITY')
    selected=review['selected_normalized_phrases']; held=review['held_groups']
    first.need(type(selected) is list and selected==sorted(set(selected)) and 0<=len(selected)<=291 and
        set(selected)<=set(material['proposed']) and type(held) is dict and
        set(held)==set(material['groups'])-set(selected) and all(type(v) is str and v.strip() for v in held.values()) and
        selected==review['fresh_variant_review']['selected_normalized_phrases'] and
        sorted(held)==review['fresh_variant_review']['all_held_normalized_phrases'] and
        review['source_pins']==SOURCE_PINS and review['text_pins']==TEXT_PINS and
        review['implementation']==material['implementation'] and review['base_sha256']==BASE_SHA256,
        'BANK_CHANNEL_LOGIN_REVIEW_BINDINGS_CHANGED')
    campaign=next(r for r in material['registry'] if r['campaign_key']==first.CAMPAIGN)
    context=material['context']
    first.need(review['campaign_key']==campaign['campaign_key']=='BSRE-C0301' and
        review['landing_page_id']==campaign['landing_page_id']=='BSRE-LP0301' and
        campaign['family_code']=='RNT' and campaign['family_slot']==1 and campaign['actual_url'] is None and
        campaign['google_campaign_id'] is None and campaign['release_approved'] is False and
        context['context_kind']=='PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        context['source_url']=='https://blackswanrealestate.ae/enquire/rent/' and
        all(context[k] is False for k in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed','live_campaign_mapping_assigned')),
        'BANK_CHANNEL_LOGIN_SCOPE_CHANGED')
    start,end=date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat()==review['reviewed_on'] and end.isoformat()==review['valid_until'] and
        start<=when<=end and end-start==timedelta(days=30) and review['validity_basis']==VALIDITY and
        review['reviewed_on']==material['semantic']['reviewed_on'] and
        context['observed_date_dubai']<=review['reviewed_on'], 'BANK_CHANNEL_LOGIN_REVIEW_DATES')
    first.need(all(type(review[k]) is str and review[k].strip() for k in
        ('semantic_rationale','source_identity_limits')) and
        review['subject_sha256']==review_subject(review,material), 'BANK_CHANNEL_LOGIN_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material=load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN)==64,'BANK_CHANNEL_LOGIN_REVIEW_UNREGISTERED')
    review=first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_review(review,material,when)
    return dict(material,review=review)


def build_cohort(base, material):
    review=material['review']; records=[]
    for key in review['selected_normalized_phrases']:
        row=material['groups'][key][0]
        occurrences=[{'batch':SOURCE_ID,**comparator.occurrence(row),'original_text':row['values']['Keyword'],
            'file':CAPTURE+'/bank-access-navigation.json','sha256':SOURCE_PINS[CAPTURE+'/bank-access-navigation.json'],
            'raw_source_sha256':comparator.RAW_SHA256,'capture_file':CAPTURE+'/capture.json',
            'capture_sha256':SOURCE_PINS[CAPTURE+'/capture.json'],
            'review_file':FOLDER+'/review.json','review_sha256':REVIEW_PIN,
            'semantic_review_file':SEMANTIC+'/review.json','semantic_review_sha256':SOURCE_PINS[SEMANTIC+'/review.json'],
            'semantic_selected_ordinal':material['decisions'][key]['selected_ordinal']}]
        adapted={'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW',
            'original_forms':[row['values']['Keyword']],'assessment':{'intent':INTENT,
            'negative_scope_proposal':{'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record=first.make_record(adapted,review,occurrences,source_id=SOURCE_ID,
            source_reference=CAPTURE+'/bank-access-navigation.json#source_ordinal='+str(row['source_ordinal']),
            review_folder=FOLDER,allowed_intents={INTENT})
        record['evidence_ref']=FOLDER+'/review.json#'+key;records.append(record)
    source={'source_id':SOURCE_ID,'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-12','valid_until':review['valid_until'],
        'capture_kind':'authentic_keyword_planner_banking_channel_login_subset',
        'research_use_basis':'OWNER_AUTHORIZED_RESEARCH_PINNED_PLANNER_SOURCE_LEAD_AI_LITERAL_REVIEW',
        'metrics_in_source_are_historical_provider_estimates':True,'metrics_copied_into_records':False,
        'served_query_or_current_performance_claimed':False,'independent_human_review_claimed':False}
    existing=set(review['fresh_variant_review']['existing_held_protection_keys'])
    protections=[{'query_id':'BSRE-Q-'+hashlib.sha256(key.encode('utf8')).hexdigest()[:24],
        'text':key,'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
        'evidence_ref':FOLDER+'/review.json#'+key,'reviewed_on':review['reviewed_on'],
        'valid_until':review['valid_until'],'source_kind':'official_reference',
        'protection_basis':'UNRESOLVED_FULL_LITERAL_NOT_VALUED_DEMAND_OR_PERMANENT_INELIGIBILITY'}
        for key in sorted(review['held_groups']) if key not in existing]
    return {'records':records,'sources':[source],'protected_queries':[],
            'campaigns':base['campaigns'],'campaign_context':base['campaign_context']},protections


def extend(base, root, when):
    material=load_reviewed(root,when)
    first.need(verify_base(base,material)==material['review']['fresh_variant_review'],
               'BANK_CHANNEL_LOGIN_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections=build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result=stage.checked_audit(inputs,when);state=inputs[STAGE_KEY]
    new=inputs['records'][state['retained_records']:]
    protections=inputs['protected_queries'][state['retained_protections']:]
    diagnostic=material['review']['fresh_variant_review']
    first.need(len(new)==len(material['review']['selected_normalized_phrases']) and
        sum(len(r['provenance_occurrences']) for r in new)==len(new),'BANK_CHANNEL_LOGIN_OCCURRENCES_CHANGED')
    index={'version':1,'scope':'APPEND_ONLY_BANK_CHANNEL_LOGIN_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[r['query_id'] for r in protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort={'scope':'AI_REVIEWED_BANKING_CHANNEL_LOGIN_RESEARCH_NOT_SEARCH_DEMAND',
        'full_source_groups':3481,'cohort_groups':251,'semantic_proposed_groups':226,'semantic_hold_groups':25,
        'selected_groups':len(new),'held_groups':len(material['review']['held_groups']),
        'previous_reviewed_bank_cohorts':1493,'outside_all_three_semantic_cohorts':1737,
        'all_source_groups_compared':diagnostic['source_groups_compared'],
        'external_key_comparisons':diagnostic['external_key_comparisons'],
        'within_source_key_comparisons':diagnostic['within_source_key_comparisons'],
        'cohort_external_key_comparisons':diagnostic['cohort_external_key_comparisons'],
        'cohort_within_source_key_comparisons':diagnostic['cohort_within_source_key_comparisons'],
        'additional_variant_holds':len(diagnostic['additional_variant_holds']),
        'additional_protected_queries':len(protections),
        'existing_held_protection_occurrences':len(diagnostic['existing_held_protection_keys']),
        'text_compatibility_classifications':dict(Counter(p['classification'] for p in material['profiles'].values())),
        'independent_review_claimed':False,'source_pins':dict(SOURCE_PINS),
        'record_bodies_sha256':stage.digest(new),**{k:False for k in LIMITS}}
    summary={'scope':'CURRENT_RESEARCH_AFTER_BANK_CHANNEL_LOGIN_APPEND_ONLY_REVIEW',
        **{k:result[k] for k in ('as_of','input_rows','distinct_nonblank_phrases','reviewed_eligible_rows',
            'excluded_rows','approved_exclusion_rows','target','deficit','exact_target_pass','structural_pass',
            'deployment_export_allowed','production_writes_available','positive_library_coverage_verified',
            'protected_queries_indexed')},'computed_conflicts':len(result['protected_conflicts']),
        'prior_rows':state['retained_records'],'new_rows':len(new),'archived_original_rows':len(inputs['archived_records']),
        'source_occurrences_retained_in_current_records':sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'new_exact_provenance_occurrences':len(new),'new_proposal_holds':len(material['review']['held_groups']),
        'historical_records_rewritten':False,'human_review_verified':False,
        'live_campaign_mapping_verified':False,'release_authorized':False}
    pin=prior.OUTPUT_PINS['research-pool-allocation.json']
    previous=first.pinned(root,prior.FOLDER+'/research-pool-allocation.json',pin)
    first.need(previous['total_target']==14000 and previous['total_admitted']==11986 and
        previous['remaining']['NAVIGATION']==291,'BANK_CHANNEL_LOGIN_ALLOCATION_BASE_CHANGED')
    admitted=dict(previous['admitted']);admitted['NAVIGATION']+=len(new)
    remaining={k:previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v>=0 for v in remaining.values()) and
        sum(admitted.values())==len(inputs['records']),'BANK_CHANNEL_LOGIN_ALLOCATION_COUNTS')
    allocation={'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'new_rows':{'NAVIGATION':len(new)},'admitted':admitted,'remaining':remaining,
        'total_target':14000,'total_admitted':sum(admitted.values()),'total_remaining':sum(remaining.values()),
        'owner_approval_claimed':False,'media_budget_changed':False,'exclusion_approval_granted':False}
    return {'index.json':index,'cohort-report.json':cohort,
        'library-report.json':dict(summary,as_of=material['review']['reviewed_on']),
        'research-pool-allocation.json':allocation},summary


def build_outputs(base, root=first.ROOT, when=None):
    when=first.dubai_date() if when is None else when
    inputs=extend(base,root,when)
    documents,_=_outputs(inputs,load_reviewed(root,when),root,when)
    return inputs,documents


def check_saved(inputs, root, when):
    base=stage.recover_base(inputs,stage_key=STAGE_KEY)
    expected=extend(base,root,when)
    first.need(first.canonical(inputs)==first.canonical(expected),'BANK_CHANNEL_LOGIN_DERIVED_BODIES_CHANGED')
    documents,summary=_outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return summary
