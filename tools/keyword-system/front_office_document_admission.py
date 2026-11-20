"""Append-only, full-literal front-office document research; never exclusion or release approval."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import hashlib
from pathlib import Path
import runpy

import append_only_admission as stage
import source_membership_diagnostic as comparator
import bank_channel_login_admission as prior
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first
from followup_admission import VALIDITY

FOLDER = 'docs/audit/keyword-negative-front-office-document-admission-2026-11-13'
SEMANTIC = 'docs/audit/keyword-front-office-documents-review-2026-11-13'
CAPTURE = 'docs/audit/keyword-application-documents-2026-11-13'
SOURCE_PINS = {'docs/audit/keyword-application-documents-2026-11-13/application-documents.json': '308e98c6a5836459cf572e7ff8d4e063b06cdd1881170f245f17b0f6b8bbb587', 'docs/audit/keyword-application-documents-2026-11-13/capture.json': '2a5c148cd42f6a94077553ee9cef4e97fb59d03dfd358c947d030c9b965f34b3', 'docs/audit/keyword-front-office-documents-review-2026-11-13/review.json': '828e2c5c87e8156d8885533d39e31b8f31bf3524594018ca1480939ae60e8fa8'}
TEXT_PINS = {'docs/audit/keyword-front-office-documents-review-2026-11-13/verify_review.py': '5da8a1f58002b76333243c7b4612e829e21cc2409ea10949767e19c41e80e62b', 'docs/audit/keyword-front-office-documents-review-2026-11-13/README.md': '7113c9edc900f2011c74f1fb9c67fd83b0a263af687551ba653378431e8784ad', 'docs/audit/keyword-application-documents-2026-11-13/verify_capture.py': '599ad56a91f4c5f5e005ddb925903b78f33461f9c28337b3628ea2c151feaae8', 'tools/keyword-system/bank_channel_login_admission.py': '713f71f452eacbba3a07d515b932cfd914eea97d3953aaa610d0cc9071c31fbd', 'tools/keyword-system/source_membership_diagnostic.py': 'bd8bafb4c49d23185b8cff91112e1c79679ae39bd9def9974e6d911ed891e41c'}
BASE_SHA256 = 'a93d5aa368975f79d3fd5bd92223ccfe93d8b48d725ac8c301013aba8d3868cb'
REVIEW_PIN = '0cd8aed9365e27553f93c659af56f2e0fc6d2a2fa62f6071305fac541f133b94'
OUTPUT_PINS = {'index.json': '574161772cea121cce9ae2ee15047325ad95f3ec7f81aacb1a5becbd4152d592', 'cohort-report.json': '379be8d30b4413e93e6adc1ab58953ac49e4e892011ef8b73f37856d27a02ffd', 'library-report.json': '64a50974df94afc6add45778e25af06370777fb2c4670c24acc7fe6c5479794f', 'research-pool-allocation.json': '4a1623a22055b69e37a03894180e90faee10da660b5e8e77d32bdcc27123ffc2'}
STAGE_KEY = 'front_office_document_append_only_state'
SOURCE_ID = 'KP-FRONT-OFFICE-DOCUMENTS-20261113'
INTENT = 'EXPLICIT_APPLICATION_DOCUMENT_RESEARCH'
LIMITS = prior.LIMITS
# Observed role-form pairs hold only with an identical ordered remainder.
# Broader occupational families are never collapsed into equivalent intent.
ROLE_FORMS = (('ADMIN_ASSISTANT_POTENTIAL_ABBREVIATION', (('administrative', 'assistant'), ('admin', 'assistant'))), ('CUSTOMER_SERVICE_REP_POTENTIAL_ABBREVIATION', (('customer', 'service', 'representative'), ('customer', 'service', 'rep'))))


def implementation_binding(root):
    for path,pin in TEXT_PINS.items():
        raw=(Path(root)/path).read_bytes()
        first.need(len(raw)<=1024*1024 and hashlib.sha256(raw).hexdigest()==pin,
                   'FRONT_OFFICE_DOCUMENT_REVIEW_OR_DEPENDENCY_CHANGED')
    return {'prior_bank_implementation':prior.implementation_binding(root),
            'semantic_and_comparison_implementation_sha256':dict(TEXT_PINS)}


def load_sources(root):
    documents={path:first.pinned(root,path,pin) for path,pin in SOURCE_PINS.items()}
    implementation=implementation_binding(root)
    verifier=runpy.run_path(str(Path(root)/SEMANTIC/'verify_review.py'))
    semantic=documents[SEMANTIC+'/review.json']
    verifier['validate'](semantic,{Path(p).name:documents[p] for p in SOURCE_PINS if p.startswith(CAPTURE+'/')})
    rows=[{**r,'source_ordinal':n} for n,r in enumerate(
        documents[CAPTURE+'/application-documents.json']['source_projection']['records'],1)]
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
    first.need(len(source_groups)==4356 and len(groups)==1100 and len(proposed)==1060 and
        len(initial_holds)==40,'FRONT_OFFICE_DOCUMENT_SEMANTIC_OR_COMPATIBILITY_CHANGED')
    return {'rows':rows,'groups':groups,'source_groups':source_groups,'decisions':decisions,
        'profiles':profiles,'proposed':sorted(proposed),'initial_holds':initial_holds,
        'semantic':semantic,'implementation':implementation,
        'context':first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN),
        'registry':first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])}


def role_form_holds(source_groups):
    """Only observed form pairs with identical ordered nonrole remainders hold.

    A possible abbreviation relationship is not a verified identity, Google
    equivalence or licence to collapse broader occupational families.
    """
    spans={};form_map={};review=[];held={}
    for key,rows in source_groups.items():
        tokens=tuple(ka.tokens(rows[0]['values']['Keyword']))
        for family,forms in ROLE_FORMS:
            for form in forms:
                for start in range(len(tokens)-len(form)+1):
                    if tokens[start:start+len(form)]==form:
                        remainder=tokens[:start]+tokens[start+len(form):]
                        identity=(family,remainder)
                        spans.setdefault(identity,set()).add(key)
                        form_map.setdefault(identity,set()).add(form)
    for (family,remainder),keys in sorted(spans.items()):
        if len(form_map[(family,remainder)])<2:continue
        entry={'family':family,'ordered_nonrole_remainder':list(remainder),
            'observed_role_forms':[list(f) for f in sorted(form_map[(family,remainder)])],
            'source_ordinals':sorted(source_groups[key][0]['source_ordinal'] for key in keys),
            'identity_or_google_equivalence_verified':False}
        review.append(entry)
        for key in keys:held.setdefault(key,[]).append(entry)
    return held,review


def membership(base,material):
    raw=comparator.compare(base,material['rows'],material['semantic']['decisions'])
    forms,form_review=role_form_holds(material['source_groups'])
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
        if key in forms:reasons.append({'kind':'POTENTIAL_ROLE_ABBREVIATION_FORM',
                                      'observed_relationships':forms[key]})
        if reasons:conflicts[key]=reasons
    proposed=set(material['proposed']);selected=sorted(proposed-set(conflicts))
    held=sorted(set(material['groups'])-set(selected))
    first.need(not raw['semantic_holds_matching_existing_negatives'] and
        all(not any(identity.startswith('records:') for reason in conflicts.get(key,[])
        for identity in reason.get('existing_identities',[])) for key in held),
        'FRONT_OFFICE_DOCUMENT_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    first.need(len(joins)==4356 and raw['external_key_comparisons']==raw['within_source_key_comparisons']==17424
        and set(material['groups'])<=set(joins),'FRONT_OFFICE_DOCUMENT_INCOMPLETE_COMPARISONS')
    protected={ka.normalize(row['text']) for row in base['protected_queries']}
    return {'selected_normalized_phrases':selected,'all_held_normalized_phrases':held,
        'additional_variant_holds':{key:conflicts[key] for key in sorted(proposed&set(conflicts))},
        'all_source_group_conflicts':conflicts,'source_group_join_results':joins,
        'existing_held_protection_keys':sorted(set(held)&protected),
        'source_groups_compared':4356,'cohort_groups_compared':1100,
        'external_key_comparisons':17424,'within_source_key_comparisons':17424,
        'cohort_external_key_comparisons':4400,'cohort_within_source_key_comparisons':4400,
        'source_role_form_review':form_review,
        'complete_base_counts':{field:len(base[field]) for field in
            ('records','archived_records','protected_queries','sources','campaigns','campaign_context')},
        'lexical_methods':list(comparator.METHODS),'google_equivalence_verified':False,
        'counts_distinct_concepts':False,'noncohort_state':'UNASSESSED_NOT_ADMITTED',
        'noncohort_source_groups':3256}


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources','campaigns','campaign_context'))
        == (12156,18,17715,30,360,1) and
        sum(len(r['provenance_occurrences']) for r in base['records']) == 12369 and
        base['campaigns'] == material['registry'], 'FRONT_OFFICE_DOCUMENT_PRIOR_BASE_CHANGED')
    return membership(base,material)


def review_subject(review, material):
    return stage.digest({'review':{k:v for k,v in review.items() if k!='subject_sha256'},
        'context':material['context'],'registry':material['registry'],'source_pins':SOURCE_PINS,
        'text_pins':TEXT_PINS,'implementation':material['implementation']})


def make_review(base,root=first.ROOT,when=None):
    when=first.dubai_date() if when is None else when
    material=load_sources(root);diagnostic=verify_base(base,material)
    review={'version':1,'scope':'AI_REVIEWED_FRONT_OFFICE_DOCUMENT_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN',
        'reviewed_on':when.isoformat(),'valid_until':(when+timedelta(days=30)).isoformat(),
        'validity_basis':VALIDITY,'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_phrases':diagnostic['selected_normalized_phrases'],
        'held_groups':{key:'Preserve complete original: semantic/text hold, complete-history/source-peer conflict or an observed narrow role-form relationship; no canonical repair.'
                       for key in diagnostic['all_held_normalized_phrases']},
        'fresh_variant_review':diagnostic,'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Lead AI read all1,100 complete front-office application-document literals. Preserve40 semantic holds. Full4,356-source joins and only identical-remainder observed role-abbreviation pairs precede full-exact research admission. No generic role, service, CV or resume token is proposed.',
        'source_identity_limits':'Planner ideas and historical estimates are not served queries, actual CPC, current demand, verified provider identities or Google matching certification. Distinct phrases are not distinct concepts. Lead AI review is not independent human approval. All3,256 noncohort rows remain intent-unreviewed; every one participates as a source peer.',
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
        review['version']==1 and review['scope']=='AI_REVIEWED_FRONT_OFFICE_DOCUMENT_NOT_EXCLUSION_APPROVAL' and
        review['reviewer']==first.REVIEWER and review['reviewer_kind']=='CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'FRONT_OFFICE_DOCUMENT_REVIEW_AUTHORITY')
    selected=review['selected_normalized_phrases']; held=review['held_groups']
    first.need(type(selected) is list and selected==sorted(set(selected)) and 0<=len(selected)<=983 and
        set(selected)<=set(material['proposed']) and type(held) is dict and
        set(held)==set(material['groups'])-set(selected) and all(type(v) is str and v.strip() for v in held.values()) and
        selected==review['fresh_variant_review']['selected_normalized_phrases'] and
        sorted(held)==review['fresh_variant_review']['all_held_normalized_phrases'] and
        review['source_pins']==SOURCE_PINS and review['text_pins']==TEXT_PINS and
        review['implementation']==material['implementation'] and review['base_sha256']==BASE_SHA256,
        'FRONT_OFFICE_DOCUMENT_REVIEW_BINDINGS_CHANGED')
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
        'FRONT_OFFICE_DOCUMENT_SCOPE_CHANGED')
    start,end=date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat()==review['reviewed_on'] and end.isoformat()==review['valid_until'] and
        start<=when<=end and end-start==timedelta(days=30) and review['validity_basis']==VALIDITY and
        review['reviewed_on']==material['semantic']['reviewed_on'] and
        context['observed_date_dubai']<=review['reviewed_on'], 'FRONT_OFFICE_DOCUMENT_REVIEW_DATES')
    first.need(all(type(review[k]) is str and review[k].strip() for k in
        ('semantic_rationale','source_identity_limits')) and
        review['subject_sha256']==review_subject(review,material), 'FRONT_OFFICE_DOCUMENT_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material=load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN)==64,'FRONT_OFFICE_DOCUMENT_REVIEW_UNREGISTERED')
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
            'file':CAPTURE+'/application-documents.json','sha256':SOURCE_PINS[CAPTURE+'/application-documents.json'],
            'raw_source_sha256':'840561b4e04958a8c911bf0bf89fb941377c81d284284260d30b26fc940a3fa5',
            'capture_file':CAPTURE+'/capture.json','capture_sha256':SOURCE_PINS[CAPTURE+'/capture.json'],
            'review_file':FOLDER+'/review.json','review_sha256':REVIEW_PIN,
            'semantic_review_file':SEMANTIC+'/review.json','semantic_review_sha256':SOURCE_PINS[SEMANTIC+'/review.json'],
            'semantic_selected_ordinal':material['decisions'][key]['selected_ordinal']}]
        adapted={'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW',
            'original_forms':[row['values']['Keyword']],'assessment':{'intent':INTENT,
            'negative_scope_proposal':{'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record=first.make_record(adapted,review,occurrences,source_id=SOURCE_ID,
            source_reference=CAPTURE+'/application-documents.json#source_ordinal='+str(row['source_ordinal']),
            review_folder=FOLDER,allowed_intents={INTENT})
        record['evidence_ref']=FOLDER+'/review.json#'+key;records.append(record)
    source={'source_id':SOURCE_ID,'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-13','valid_until':review['valid_until'],
        'capture_kind':'authentic_keyword_planner_front_office_document_subset',
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
               'FRONT_OFFICE_DOCUMENT_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections=build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result=stage.checked_audit(inputs,when);state=inputs[STAGE_KEY]
    new=inputs['records'][state['retained_records']:]
    protections=inputs['protected_queries'][state['retained_protections']:]
    diagnostic=material['review']['fresh_variant_review']
    first.need(len(new)==len(material['review']['selected_normalized_phrases']) and
        sum(len(r['provenance_occurrences']) for r in new)==len(new),'FRONT_OFFICE_DOCUMENT_OCCURRENCES_CHANGED')
    index={'version':1,'scope':'APPEND_ONLY_FRONT_OFFICE_DOCUMENT_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[r['query_id'] for r in protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort={'scope':'AI_REVIEWED_FRONT_OFFICE_DOCUMENT_RESEARCH_NOT_SEARCH_DEMAND',
        'full_source_groups':4356,'cohort_groups':1100,'semantic_proposed_groups':1060,'semantic_hold_groups':40,
        'selected_groups':len(new),'held_groups':len(material['review']['held_groups']),
        'outside_semantic_cohort':3256,
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
    summary={'scope':'CURRENT_RESEARCH_AFTER_FRONT_OFFICE_DOCUMENT_APPEND_ONLY_REVIEW',
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
    first.need(previous['total_target']==14000 and previous['total_admitted']==12156 and
        previous['remaining']['EMPLOYMENT']==983,'FRONT_OFFICE_DOCUMENT_ALLOCATION_BASE_CHANGED')
    admitted=dict(previous['admitted']);admitted['EMPLOYMENT']+=len(new)
    remaining={k:previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v>=0 for v in remaining.values()) and
        sum(admitted.values())==len(inputs['records']),'FRONT_OFFICE_DOCUMENT_ALLOCATION_COUNTS')
    allocation={'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'new_rows':{'EMPLOYMENT':len(new)},'admitted':admitted,'remaining':remaining,
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
    first.need(first.canonical(inputs)==first.canonical(expected),'FRONT_OFFICE_DOCUMENT_DERIVED_BODIES_CHANGED')
    documents,summary=_outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return summary
