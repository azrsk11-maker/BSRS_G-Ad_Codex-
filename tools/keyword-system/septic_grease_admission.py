"""Append-only, full-literal septic/grease service research; never exclusion or release approval."""
from collections import Counter
from datetime import date, timedelta
import hashlib
from pathlib import Path
import runpy

import append_only_admission as stage
import source_membership_diagnostic as comparator
import front_office_document_admission as prior
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first
from followup_admission import VALIDITY

FOLDER = 'docs/audit/keyword-negative-septic-grease-admission-2026-11-13'
SEMANTIC = 'docs/audit/keyword-septic-grease-review-2026-11-13'
CAPTURE = 'docs/audit/keyword-service-installation-2026-11-13'
SOURCE_PINS = {'docs/audit/keyword-service-installation-2026-11-13/service-installation.json': '91b8edcdcc6b8ab216c89ba2b1c9674ced8bcaf2be93d9f3ffe47795c1c75392', 'docs/audit/keyword-service-installation-2026-11-13/capture.json': '3e6f99d8cce615ab77549c2e33b1edce93605f78e7fb4b034fb9e9440e6f12ea', 'docs/audit/keyword-septic-grease-review-2026-11-13/review.json': '5d8c1d8af6ccff0a0c0f40faff8f899e2f6bd56e372959c4083220662581f028'}
TEXT_PINS = {'docs/audit/keyword-septic-grease-review-2026-11-13/verify_review.py': '7d913497d8333686d5113abc3d971fa5576b49ad32dbf13387fe87269d161f62', 'docs/audit/keyword-septic-grease-review-2026-11-13/README.md': 'c7bf90519fa8af738deb8e8324a5e74b959e97133d1f4492e0c0ed2b5c4474f1', 'docs/audit/keyword-service-installation-2026-11-13/verify_capture.py': '7814cc6fafc96b736233a5c5834c3c7fddfc3a8abbd2b634263f9be804af2ebe', 'tools/keyword-system/front_office_document_admission.py': '9331de366ef52d2246ac30c413386bd45fe4a02697c0f3933864f99d1c3d035f', 'tools/keyword-system/source_membership_diagnostic.py': 'bd8bafb4c49d23185b8cff91112e1c79679ae39bd9def9974e6d911ed891e41c'}
BASE_SHA256 = 'b83194a546a36acdf7e60a38214003a6d785ff8f2af63a8120aed1106686b814'
REVIEW_PIN = 'b02043e514eaabb35ddd6231ca9ef1d6bf442dff0db7ed15c58a73ed940a701b'
OUTPUT_PINS = {'index.json': 'd456d0520b2f10d7e38cc9f78b88397564936cd8719f00d6e724ab5fa59bc74c', 'cohort-report.json': '76a29f67b0b9ddb397f954ad67e4e321c84fb880a262d031ac6d262ea5c1f02c', 'library-report.json': '425c81343157a8227998daa5bf1cdb8140563b26cda151cbf37d61d50fb4a81a', 'research-pool-allocation.json': '93e64ac6e61ed8320c8eb715d80c6dfc08f40f01ea7c2f65cab7fbc6c9e8edc1'}
STAGE_KEY = 'septic_grease_append_only_state'
SOURCE_ID = 'KP-SEPTIC-GREASE-20261113'
INTENT = 'EXPLICIT_SEPTIC_GREASE_SERVICE_RESEARCH'
LIMITS = prior.LIMITS


def implementation_binding(root):
    for path,pin in TEXT_PINS.items():
        raw=(Path(root)/path).read_bytes()
        first.need(len(raw)<=1024*1024 and hashlib.sha256(raw).hexdigest()==pin,
                   'SEPTIC_GREASE_REVIEW_OR_DEPENDENCY_CHANGED')
    return {'prior_front_office_implementation':prior.implementation_binding(root),
            'semantic_and_comparison_implementation_sha256':dict(TEXT_PINS)}


def load_sources(root):
    documents={path:first.pinned(root,path,pin) for path,pin in SOURCE_PINS.items()}
    implementation=implementation_binding(root)
    verifier=runpy.run_path(str(Path(root)/SEMANTIC/'verify_review.py'))
    semantic=documents[SEMANTIC+'/review.json']
    verifier['validate'](semantic,{Path(p).name:documents[p] for p in SOURCE_PINS if p.startswith(CAPTURE+'/')})
    rows=[{**r,'source_ordinal':n} for n,r in enumerate(
        documents[CAPTURE+'/service-installation.json']['source_projection']['records'],1)]
    source_groups={ka.normalize(r['values']['Keyword']):[r] for r in rows}
    decisions={};profiles={};groups={};proposed=[];initial_holds={}
    for decision in semantic['decisions']:
        row=rows[decision['source_ordinal']-1];key=ka.normalize(row['values']['Keyword'])
        profile=compatibility.profile_text(row['values']['Keyword'])['original']
        groups[key]=[row];decisions[key]=decision;profiles[key]=profile;reasons=[]
        if decision['decision']=='HOLD':reasons.extend(decision['reason_codes'])
        if profile['classification']!='NO_KNOWN_INCOMPATIBILITY_DETECTED':
            reasons.append('ORIGINAL_LITERAL_TEXT_COMPATIBILITY_HOLD')
        if reasons:initial_holds[key]=reasons
        else:proposed.append(key)
    first.need(len(source_groups)==6053 and len(groups)==914 and len(proposed)==444 and
        len(initial_holds)==470,'SEPTIC_GREASE_SEMANTIC_OR_COMPATIBILITY_CHANGED')
    return {'rows':rows,'groups':groups,'source_groups':source_groups,'decisions':decisions,
        'profiles':profiles,'proposed':sorted(proposed),'initial_holds':initial_holds,
        'semantic':semantic,'implementation':implementation,
        'context':first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN),
        'registry':first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])}





def membership(base,material):
    raw=comparator.compare(base,material['rows'],material['semantic']['decisions'])
    ordinal_keys={rows[0]['source_ordinal']:key for key,rows in material['source_groups'].items()}
    joins={};conflicts={}
    for row in raw['source_row_comparisons']:
        key=ordinal_keys[row['source_ordinal']];joins[key]=row;reasons=[]
        for join in row['joins']:
            if join['existing_identities']:reasons.append({'kind':join['method'],
                'existing_identities':join['existing_identities']})
            if join['source_peer_ordinals']:reasons.append({'kind':'within_capture_'+join['method'],
                'source_peer_ordinals':join['source_peer_ordinals'],
                'outside_cohort_peer_ordinals':join['outside_cohort_peer_ordinals']})
        if reasons:conflicts[key]=reasons
    proposed=set(material['proposed']);selected=sorted(proposed-set(conflicts))
    held=sorted(set(material['groups'])-set(selected))
    first.need(not raw['semantic_holds_matching_existing_negatives'] and
        all(not any(identity.startswith('records:') for reason in conflicts.get(key,[])
        for identity in reason.get('existing_identities',[])) for key in held),
        'SEPTIC_GREASE_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    first.need(len(joins)==6053 and raw['external_key_comparisons']==raw['within_source_key_comparisons']==24212
        and set(material['groups'])<=set(joins),'SEPTIC_GREASE_INCOMPLETE_COMPARISONS')
    protected={ka.normalize(row['text']) for row in base['protected_queries']}
    return {'selected_normalized_phrases':selected,'all_held_normalized_phrases':held,
        'additional_variant_holds':{key:conflicts[key] for key in sorted(proposed&set(conflicts))},
        'all_source_group_conflicts':conflicts,'source_group_join_results':joins,
        'existing_held_protection_keys':sorted(set(held)&protected),
        'source_groups_compared':6053,'cohort_groups_compared':914,
        'external_key_comparisons':24212,'within_source_key_comparisons':24212,
        'cohort_external_key_comparisons':3656,'cohort_within_source_key_comparisons':3656,
        'complete_base_counts':{field:len(base[field]) for field in
            ('records','archived_records','protected_queries','sources','campaigns','campaign_context')},
        'lexical_methods':list(comparator.METHODS),'google_equivalence_verified':False,
        'counts_distinct_concepts':False,'noncohort_state':'UNASSESSED_NOT_ADMITTED',
        'noncohort_source_groups':5139}


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources','campaigns','campaign_context'))
        == (13025,18,17943,31,360,1) and
        sum(len(r['provenance_occurrences']) for r in base['records']) == 13238 and
        base['campaigns'] == material['registry'], 'SEPTIC_GREASE_PRIOR_BASE_CHANGED')
    return membership(base,material)


def review_subject(review, material):
    return stage.digest({'review':{k:v for k,v in review.items() if k!='subject_sha256'},
        'context':material['context'],'registry':material['registry'],'source_pins':SOURCE_PINS,
        'text_pins':TEXT_PINS,'implementation':material['implementation']})


def make_review(base,root=first.ROOT,when=None):
    when=first.dubai_date() if when is None else when
    material=load_sources(root);diagnostic=verify_base(base,material)
    review={'version':1,'scope':'AI_REVIEWED_SEPTIC_GREASE_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN',
        'reviewed_on':when.isoformat(),'valid_until':(when+timedelta(days=30)).isoformat(),
        'validity_basis':VALIDITY,'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_phrases':diagnostic['selected_normalized_phrases'],
        'held_groups':{key:'Preserve complete original: semantic/text hold or complete-history/source-peer conflict; no canonical repair.'
                       for key in diagnostic['all_held_normalized_phrases']},
        'fresh_variant_review':diagnostic,'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Lead AI read all914 complete grease/septic literals. Preserve470 semantic holds. Complete6,053-source and current-history joins precede full-exact service-research admission. No generic septic, grease, pump, service or property token is proposed.',
        'source_identity_limits':'Planner ideas and historical estimates are not served queries, actual CPC, current demand, verified provider identities or Google matching certification. Distinct phrases are not distinct concepts. Lead AI review is not independent human approval. All5,139 noncohort rows remain intent-unreviewed; every one participates as a source peer.',
        **{key:False for key in LIMITS}}
    review['subject_sha256']=review_subject(review,material)
    validate_review(review,material,when)
    return review


def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_normalized_phrases','held_groups','fresh_variant_review',
        'source_pins','text_pins','implementation','base_sha256','semantic_rationale','source_identity_limits',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review)==required and type(review['version']) is int and
        review['version']==1 and review['scope']=='AI_REVIEWED_SEPTIC_GREASE_NOT_EXCLUSION_APPROVAL' and
        review['reviewer']==first.REVIEWER and review['reviewer_kind']=='CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'SEPTIC_GREASE_REVIEW_AUTHORITY')
    selected=review['selected_normalized_phrases']; held=review['held_groups']
    first.need(type(selected) is list and selected==sorted(set(selected)) and 0<=len(selected)<=534 and
        set(selected)<=set(material['proposed']) and type(held) is dict and
        set(held)==set(material['groups'])-set(selected) and all(type(v) is str and v.strip() for v in held.values()) and
        selected==review['fresh_variant_review']['selected_normalized_phrases'] and
        sorted(held)==review['fresh_variant_review']['all_held_normalized_phrases'] and
        review['source_pins']==SOURCE_PINS and review['text_pins']==TEXT_PINS and
        review['implementation']==material['implementation'] and review['base_sha256']==BASE_SHA256,
        'SEPTIC_GREASE_REVIEW_BINDINGS_CHANGED')
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
        'SEPTIC_GREASE_SCOPE_CHANGED')
    start,end=date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat()==review['reviewed_on'] and end.isoformat()==review['valid_until'] and
        start<=when<=end and end-start==timedelta(days=30) and review['validity_basis']==VALIDITY and
        review['reviewed_on']==material['semantic']['reviewed_on'] and
        context['observed_date_dubai']<=review['reviewed_on'], 'SEPTIC_GREASE_REVIEW_DATES')
    first.need(all(type(review[k]) is str and review[k].strip() for k in
        ('semantic_rationale','source_identity_limits')) and
        review['subject_sha256']==review_subject(review,material), 'SEPTIC_GREASE_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material=load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN)==64,'SEPTIC_GREASE_REVIEW_UNREGISTERED')
    review=first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_review(review,material,when)
    return dict(material,review=review)


def build_cohort(base, material):
    review=material['review']; records=[]
    for key in review['selected_normalized_phrases']:
        row=material['groups'][key][0]
        occurrences=[{'batch':SOURCE_ID,'source_ordinal':row['source_ordinal'],
            'source_line':row['source_line'],'original_literal':row['values']['Keyword'],
            'original_text':row['values']['Keyword'],'complete_public_values_sha256':stage.digest(row['values']),
            'file':CAPTURE+'/service-installation.json','sha256':SOURCE_PINS[CAPTURE+'/service-installation.json'],
            'raw_source_sha256':'4dda5a60cfbb680edff4d2b6c17319f55afb41055968052bb18e6b3d883f5078',
            'capture_file':CAPTURE+'/capture.json','capture_sha256':SOURCE_PINS[CAPTURE+'/capture.json'],
            'review_file':FOLDER+'/review.json','review_sha256':REVIEW_PIN,
            'semantic_review_file':SEMANTIC+'/review.json','semantic_review_sha256':SOURCE_PINS[SEMANTIC+'/review.json'],
            'semantic_selected_ordinal':material['decisions'][key]['selected_ordinal']}]
        adapted={'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW',
            'original_forms':[row['values']['Keyword']],'assessment':{'intent':INTENT,
            'negative_scope_proposal':{'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record=first.make_record(adapted,review,occurrences,source_id=SOURCE_ID,
            source_reference=CAPTURE+'/service-installation.json#source_ordinal='+str(row['source_ordinal']),
            review_folder=FOLDER,allowed_intents={INTENT})
        record['evidence_ref']=FOLDER+'/review.json#'+key;records.append(record)
    source={'source_id':SOURCE_ID,'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-13','valid_until':review['valid_until'],
        'capture_kind':'authentic_keyword_planner_septic_grease_service_subset',
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
               'SEPTIC_GREASE_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections=build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result=stage.checked_audit(inputs,when);state=inputs[STAGE_KEY]
    new=inputs['records'][state['retained_records']:]
    protections=inputs['protected_queries'][state['retained_protections']:]
    diagnostic=material['review']['fresh_variant_review']
    first.need(len(new)==len(material['review']['selected_normalized_phrases']) and
        sum(len(r['provenance_occurrences']) for r in new)==len(new),'SEPTIC_GREASE_OCCURRENCES_CHANGED')
    index={'version':1,'scope':'APPEND_ONLY_SEPTIC_GREASE_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[r['query_id'] for r in protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort={'scope':'AI_REVIEWED_SEPTIC_GREASE_RESEARCH_NOT_SEARCH_DEMAND',
        'full_source_groups':6053,'cohort_groups':914,'semantic_proposed_groups':444,'semantic_hold_groups':470,
        'selected_groups':len(new),'held_groups':len(material['review']['held_groups']),
        'outside_semantic_cohort':5139,
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
    summary={'scope':'CURRENT_RESEARCH_AFTER_SEPTIC_GREASE_APPEND_ONLY_REVIEW',
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
    first.need(previous['total_target']==14000 and previous['total_admitted']==13025 and
        previous['remaining']['SERVICE']==534,'SEPTIC_GREASE_ALLOCATION_BASE_CHANGED')
    admitted=dict(previous['admitted']);admitted['SERVICE']+=len(new)
    remaining={k:previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v>=0 for v in remaining.values()) and
        sum(admitted.values())==len(inputs['records']),'SEPTIC_GREASE_ALLOCATION_COUNTS')
    allocation={'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'new_rows':{'SERVICE':len(new)},'admitted':admitted,'remaining':remaining,
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
    first.need(first.canonical(inputs)==first.canonical(expected),'SEPTIC_GREASE_DERIVED_BODIES_CHANGED')
    documents,summary=_outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return summary
