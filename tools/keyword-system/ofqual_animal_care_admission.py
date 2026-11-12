"""Append-only official animal-study title research; no exclusion/release approval."""
from collections import Counter, defaultdict
from datetime import date, timedelta
import csv, hashlib, io, json
from pathlib import Path
import runpy
import append_only_admission as stage
import bank_support_admission as prior
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first
from followup_admission import VALIDITY
FOLDER = 'docs/audit/keyword-negative-ofqual-animal-care-admission-2026-11-12'
CAPTURE = 'docs/audit/keyword-ofqual-animal-care-2026-11-12'
BASE_SHA256 = 'bbb5968ad7a28f8a7e8d036a979c0d08455dee97860fd1aa6b0dca159f713171'
REVIEW_PIN = '870a60fbcfa14da5b4612fefc59b4ff797287d19a83d65bf7748fbce8a031292'
OUTPUT_PINS = {'index.json': 'aab0fb37cf7aa15d34bb3d90f74ef15122cc4251bbef4fd2cdf00a4724b85a29', 'cohort-report.json': '4641cf0f5c08bc7d7277892b383431139f999ca391bd44f7a8caf9e78e2b03e1', 'library-report.json': '9e49f3a1341392411926b17a307c055a80f2a29dc362e4c38a88e0090fb93b45', 'research-pool-allocation.json': 'd90761c35213bc5dddf9ff327f729e02a306072b0081de2ad60893b9f56d84db'}
STAGE_KEY = 'ofqual_animal_care_append_only_state'
SOURCE_ID = 'OFQUAL-ANIMAL-CARE-QUALIFICATIONS-20261111'
INTENT = 'EXPLICIT_OCCUPATIONAL_STUDY_OR_ASSESSMENT_RESEARCH'
LIMITS = prior.LIMITS
RAW_SHA256 = 'ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5'
METHODS = ('normalized_exact','ordered_tokens','equal_token_bag','closed_alphanumeric')
SOURCE_PINS = {'docs/audit/keyword-ofqual-animal-care-2026-11-12/qualifications.json': 'e265c3aa15e185b3457321df54365386330a0e75548cc251a8d114ac1043a903', 'docs/audit/keyword-ofqual-animal-care-2026-11-12/semantic-review.json': 'ae971dfa91438e9ae00927b6b3bfe1493096ca7e3cb56ca9528dea307d83126e', 'docs/audit/keyword-ofqual-animal-care-2026-11-12/capture.json': '6ae964664aa6dec7f6f79f8c06c89bf3c05bb2fc0e1b05446e515be4e1bf4387', 'docs/audit/keyword-negative-ofqual-animal-care-admission-2026-11-12/wording-evidence.json': '4f035649956d62fe51f385e23c0efe509b602f108b7b67ef225a2c84c6c0c35e'}
TEXT_PINS = {'docs/audit/keyword-ofqual-animal-care-2026-11-12/extract.py': 'c4866ea958a8d4714d09c3b42cb1afebc0b9ac092198c97a0baf3efc4785689d', 'docs/audit/keyword-ofqual-animal-care-2026-11-12/README.md': 'b7eadf9b582f515b523b29bdd72929162594ad31eb800254588b09a93d541642', 'tools/keyword-system/bank_support_admission.py': '7751b56078497921dae4e812c1299e30a699b7acd661f200ef034216d703565f'}

def implementation_binding(root):
    for path, pin in TEXT_PINS.items():
        raw = (Path(root)/path).read_bytes()
        first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == pin,
                   'ANIMAL_CARE_REVIEW_OR_DEPENDENCY_CHANGED')
    return {'prior_bank_implementation': prior.implementation_binding(root),
            'animal_review_and_dependency_sha256': dict(TEXT_PINS)}

def review_subject(review, material):
    return stage.digest({'review':{k:v for k,v in review.items() if k!='subject_sha256'},
        'context':material['context'],'registry':material['registry'],'source_pins':SOURCE_PINS,
        'text_pins':TEXT_PINS,'implementation':material['implementation']})

def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_normalized_phrases','held_groups','fresh_variant_review',
        'source_pins','text_pins','implementation','base_sha256','semantic_rationale','source_identity_limits',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review)==required and type(review['version']) is int and
        review['version']==1 and review['scope']=='AI_REVIEWED_ANIMAL_CARE_NOT_EXCLUSION_APPROVAL' and
        review['reviewer']==first.REVIEWER and review['reviewer_kind']=='CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'ANIMAL_CARE_REVIEW_AUTHORITY')
    selected=review['selected_normalized_phrases']; held=review['held_groups']
    first.need(type(selected) is list and selected==sorted(set(selected)) and 0<=len(selected)<=111 and
        set(selected)<=set(material['proposed']) and type(held) is dict and
        set(held)==set(material['groups'])-set(selected) and all(type(v) is str and v.strip() for v in held.values()) and
        selected==review['fresh_variant_review']['selected_normalized_phrases'] and
        sorted(held)==review['fresh_variant_review']['all_held_normalized_phrases'] and
        review['source_pins']==SOURCE_PINS and review['text_pins']==TEXT_PINS and
        review['implementation']==material['implementation'] and review['base_sha256']==BASE_SHA256,
        'ANIMAL_CARE_REVIEW_BINDINGS_CHANGED')
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
        'ANIMAL_CARE_SCOPE_CHANGED')
    start,end=date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat()==review['reviewed_on'] and end.isoformat()==review['valid_until'] and
        start<=when<=end and end-start==timedelta(days=30) and review['validity_basis']==VALIDITY and
        review['reviewed_on']==material['semantic']['reviewed_on'] and
        context['observed_date_dubai']<=review['reviewed_on'], 'ANIMAL_CARE_REVIEW_DATES')
    first.need(all(type(review[k]) is str and review[k].strip() for k in
        ('semantic_rationale','source_identity_limits')) and
        review['subject_sha256']==review_subject(review,material), 'ANIMAL_CARE_REVIEW_SUBJECT_CHANGED')

def load_reviewed(root, when):
    material=load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN)==64,'ANIMAL_CARE_REVIEW_UNREGISTERED')
    review=first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_review(review,material,when)
    return dict(material,review=review)

def extend(base, root, when):
    material=load_reviewed(root,when)
    first.need(verify_base(base,material)==material['review']['fresh_variant_review'],
               'ANIMAL_CARE_FRESH_VARIANT_REVIEW_CHANGED')
    cohort,protections=build_cohort(base,material)
    return stage.extend(base,cohort,protections,expected_base_sha256=BASE_SHA256,stage_key=STAGE_KEY)

def build_outputs(base, root=first.ROOT, when=None):
    when=first.dubai_date() if when is None else when
    inputs=extend(base,root,when)
    documents,_=_outputs(inputs,load_reviewed(root,when),root,when)
    return inputs,documents

def check_saved(inputs, root, when):
    base=stage.recover_base(inputs,stage_key=STAGE_KEY)
    expected=extend(base,root,when)
    first.need(first.canonical(inputs)==first.canonical(expected),'ANIMAL_CARE_DERIVED_BODIES_CHANGED')
    documents,summary=_outputs(inputs,load_reviewed(root,when),root,when)
    stage.check_documents(root,FOLDER,OUTPUT_PINS,documents)
    return summary


def load_sources(root):
    docs={p:first.pinned(root,p,pin) for p,pin in SOURCE_PINS.items()}
    implementation=implementation_binding(root)
    parser=runpy.run_path(str(Path(root)/CAPTURE/'extract.py'))
    projection=docs[CAPTURE+'/qualifications.json'];semantic=docs[CAPTURE+'/semantic-review.json']
    parser['validate_projection'](projection);parser['validate_review'](semantic,projection)
    parser['validate_capture'](docs[CAPTURE+'/capture.json'])
    rows=projection['records'];by_ordinal={r['source_record_ordinal']:r for r in rows}
    selected=set(projection['selected_source_ordinals']);groups=defaultdict(list);source_groups=defaultdict(list)
    for row in rows:
        key=ka.normalize(row['values']['Qualification Title']);source_groups[key].append(row)
        if row['source_record_ordinal'] in selected:groups[key].append(row)
    wording=docs[FOLDER+'/wording-evidence.json']
    first.need(wording['schema']=='bsre-ofqual-animal-care-wording-v1' and
        wording['raw_source_sha256']==RAW_SHA256 and wording['raw_source_bytes']==23984795 and
        wording['independent_human_approval'] is False and wording['new_keyword_or_canonical_form_created'] is False and
        [r['source_record_ordinal'] for r in wording['source_occurrences']]==[12445,41428],
        'ANIMAL_CARE_WORDING_SOURCE_CHANGED')
    wording_holds={}
    for evidence in wording['source_occurrences']:
        row=by_ordinal[evidence['source_record_ordinal']];values=row['values']
        first.need(evidence['qualification_number']==values['Qualification Number'] and
            evidence['original_literal']==values['Qualification Title'] and
            evidence['owner_organisation_name']==values['Owner Organisation Name'] and
            evidence['decision']=='HOLD_UNRESOLVED_SOURCE_WORDING_NO_REPAIR' and
            len(evidence['complete_36_source_cells_sha256'])==64,'ANIMAL_CARE_WORDING_LITERAL_CHANGED')
        wording_holds[ka.normalize(values['Qualification Title'])]=evidence
    profiles={};initial={};proposed=[];decisions={}
    for decision in semantic['decisions']:
        decisions[decision['source_record_ordinal']]=decision
    for key,occurrences in groups.items():
        profile_list=[compatibility.profile_text(r['values']['Qualification Title'])['original'] for r in occurrences]
        profiles[key]=profile_list;reasons=[]
        if any(p['classification']!='NO_KNOWN_INCOMPATIBILITY_DETECTED' for p in profile_list):
            reasons.append('ORIGINAL_LITERAL_TEXT_COMPATIBILITY_HOLD')
        if key in wording_holds:reasons.append('SOURCE_WORDING_CONTRADICTION_OR_PROVIDER_SPELLING_HOLD')
        if reasons:initial[key]=reasons
        else:proposed.append(key)
    first.need(len(rows)==444 and len(source_groups)==423 and len(groups)==213 and
        sum(map(len,groups.values()))==214 and len(proposed)==101 and len(initial)==112,
        'ANIMAL_CARE_COMPLETE_SOURCE_OR_INITIAL_HOLDS_CHANGED')
    return {'groups':dict(groups),'source_groups':dict(source_groups),'projection':projection,
        'semantic':semantic,'decisions':decisions,'profiles':profiles,'initial_holds':initial,
        'wording_holds':wording_holds,'wording_evidence':wording,'proposed':sorted(proposed),
        'implementation':implementation,
        'context':first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN),
        'registry':first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])}


def verify_wording_source(path, root=first.ROOT):
    material=load_sources(root);p=Path(path)
    first.need(p.stat().st_size==23984795,'ANIMAL_CARE_PRIVATE_SOURCE_SIZE')
    raw=p.read_bytes()
    first.need(hashlib.sha256(raw).hexdigest()==RAW_SHA256,'ANIMAL_CARE_PRIVATE_SOURCE_HASH')
    expected={r['source_record_ordinal']:r for r in material['wording_evidence']['source_occurrences']}
    found=set();reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
    for ordinal,row in enumerate(reader,1):
        if ordinal not in expected:continue
        e=expected[ordinal]
        first.need(stage.digest(row)==e['complete_36_source_cells_sha256'] and
            row['Qualification Number']==e['qualification_number'] and
            row['Qualification Title']==e['original_literal'] and
            row['Owner Organisation Name']==e['owner_organisation_name'] and
            row['Apprenticeship Standard Reference Number']==e['apprenticeship_standard_reference_number'] and
            row['Apprenticeship Standard Title']==e['apprenticeship_standard_title'],
            'ANIMAL_CARE_PRIVATE_WORDING_EVIDENCE_CHANGED')
        found.add(ordinal)
    first.need(ordinal==53175 and found==set(expected),'ANIMAL_CARE_PRIVATE_WORDING_COVERAGE')
    return {'passed':True,'raw_sha256':RAW_SHA256,'complete_source_records':53175,
        'wording_occurrences_verified':len(found),'source_titles_repaired':False}


def keys(text):
    normalized=ka.normalize(text);tokens=tuple(ka.tokens(text))
    return normalized,tokens,tuple(sorted(tokens)),''.join(c for c in normalized if c.isalnum())


def membership(base, material):
    maps={m:defaultdict(set) for m in METHODS};own={m:defaultdict(set) for m in METHODS}
    protected=set()
    for field,textfield,idfield in [('records','original_text','keyword_id'),
        ('archived_records','original_text','keyword_id'),('protected_queries','text','query_id')]:
        for row in base[field]:
            for method,value in zip(METHODS,keys(row[textfield])):
                maps[method][value].add(field+':'+row[idfield])
            if field=='protected_queries':protected.add(ka.normalize(row[textfield]))
    for key,rows in material['source_groups'].items():
        for method,value in zip(METHODS,keys(rows[0]['values']['Qualification Title'])):own[method][value].add(key)
    joins={};conflicts={};external=internal=0;parents=defaultdict(list)
    for key,rows in material['source_groups'].items():
        results=[];reasons=[]
        for method,value in zip(METHODS,keys(rows[0]['values']['Qualification Title'])):
            existing=sorted(maps[method].get(value,set()));other=sorted(own[method].get(value,set())-{key})
            ordinals=sorted(r['source_record_ordinal'] for peer in other for r in material['source_groups'][peer])
            results.append({'method':method,'existing_identities':existing,'source_peer_ordinals':ordinals})
            external+=1;internal+=1
            if existing:reasons.append({'kind':method,'existing_identities':existing})
            if other:reasons.append({'kind':'within_source_'+method,'other_normalized_titles':other,
                'source_peer_ordinals':ordinals})
        joins[key]={'source_ordinals':[r['source_record_ordinal'] for r in rows],
            'selected_cohort_ordinals':[r['source_record_ordinal'] for r in material['groups'].get(key,[])],
            'statuses':sorted({r['values']['Qualification Status'] for r in rows}),'joins':results}
        if reasons:conflicts[key]=reasons
        for row in rows:
            v=row['values'];parents[(v['Owner Organisation Name'],v['Qualification Level'],v['Qualification Type'])].append(row['source_record_ordinal'])
    selected=sorted(set(material['proposed'])-set(conflicts));held=sorted(set(material['groups'])-set(selected))
    first.need(all(not any(identity.startswith('records:') for reason in conflicts.get(k,[])
        for identity in reason.get('existing_identities',[])) for k in held),
        'ANIMAL_CARE_NEW_HOLD_CONFLICTS_WITH_EXISTING_NEGATIVE')
    first.need(len(joins)==423 and external==internal==4*len(joins) and
        sum(len(r['source_ordinals']) for r in joins.values())==444,'ANIMAL_CARE_INCOMPLETE_SOURCE_COMPARISONS')
    return {'selected_normalized_phrases':selected,'all_held_normalized_phrases':held,
        'additional_variant_holds':{k:conflicts[k] for k in sorted(set(material['proposed'])&set(conflicts))},
        'all_source_group_conflicts':conflicts,
        'preheld_source_group_conflicts':{k:conflicts[k] for k in sorted(set(material['initial_holds'])&set(conflicts))},
        'existing_held_protection_keys':sorted(set(held)&protected),'source_group_join_results':joins,
        'source_groups_compared':len(joins),'source_occurrences_compared':444,'cohort_groups_compared':213,
        'cohort_occurrences_compared':214,'external_key_comparisons':external,'within_source_key_comparisons':internal,
        'cohort_external_key_comparisons':852,'cohort_within_source_key_comparisons':852,
        'qualification_parent_diagnostics':[{'owner':a,'level':b,'qualification_type':c,
            'source_ordinals':sorted(v),'parent_membership_causes_hold':False}
            for (a,b,c),v in sorted(parents.items())],
        'wording_hold_ordinals':[12445,41428],
        'distinct_phrases_not_concepts':True,'levels_types_specialisms_and_entry_numbers_preserved':True,
        'google_equivalence_verified':False,'lexical_methods':list(METHODS),
        'complete_base_counts':{k:len(base[k]) for k in ['records','archived_records','protected_queries','sources','campaigns','campaign_context']}}


def verify_base(base, material):
    first.need(stage.digest(base)==BASE_SHA256 and
        tuple(len(base[k]) for k in ['records','archived_records','protected_queries','sources','campaigns','campaign_context'])
        ==(11885,18,17522,28,360,1) and sum(len(r['provenance_occurrences']) for r in base['records'])==12098 and
        base['campaigns']==material['registry'],'ANIMAL_CARE_PRIOR_BASE_CHANGED')
    return membership(base,material)


def make_review(base, root=first.ROOT, when=None):
    when=first.dubai_date() if when is None else when
    material=load_sources(root);diagnostic=verify_base(base,material)
    review={'version':1,'scope':'AI_REVIEWED_ANIMAL_CARE_NOT_EXCLUSION_APPROVAL',
        'reviewer':first.REVIEWER,'reviewer_kind':'CODEX_AI_NOT_HUMAN','reviewed_on':when.isoformat(),
        'valid_until':(when+timedelta(days=30)).isoformat(),'validity_basis':VALIDITY,
        'campaign_key':first.CAMPAIGN,'landing_page_id':first.PAGE,
        'selected_normalized_phrases':diagnostic['selected_normalized_phrases'],
        'held_groups':{k:'Preserve source text/wording flags or fresh complete membership/variant conflict; no repair, canonical choice, demand or permanent ineligibility inferred.' for k in diagnostic['all_held_normalized_phrases']},
        'fresh_variant_review':diagnostic,'source_pins':dict(SOURCE_PINS),'text_pins':dict(TEXT_PINS),
        'implementation':material['implementation'],'base_sha256':BASE_SHA256,
        'semantic_rationale':'Lead read all213complete normalized titles/214original occurrences. Preserve111text-flagged occurrences and two source-wording discrepancies. All423groups/444source peers participate, including prior/unavailable/held records. Levels, types, awarding organisations, standards, specialisms and entry sublevels are not stripped or collapsed into concepts.',
        'source_identity_limits':'Frozen11November Ofqual labels are not current demand, a course offered by Black Swan, verified Google equivalence, property inventory or UAE regulatory approval. Source wording holds do not create corrected phrases. Lead review is not independent AI/human approval.',
        **{k:False for k in LIMITS}}
    review['subject_sha256']=review_subject(review,material);validate_review(review,material,when)
    return review


def build_cohort(base, material):
    review=material['review'];records=[]
    for key in review['selected_normalized_phrases']:
        rows=material['groups'][key];originals={r['values']['Qualification Title'] for r in rows}
        first.need(len(originals)==1,'ANIMAL_CARE_UNRESOLVED_ORIGINAL_FORMS')
        occurrences=[]
        for row in rows:
            text=row['values']['Qualification Title'];ordinal=row['source_record_ordinal']
            occurrences.append({'batch':SOURCE_ID,'source_record_ordinal':ordinal,
                'source_line_start':row['source_line_start'],'source_line_end':row['source_line_end'],
                'qualification_number':row['values']['Qualification Number'],'original_text':text,
                'original_literal':text,'literal_utf8_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'complete_public_values_sha256':stage.digest(row['values']),
                'file':CAPTURE+'/qualifications.json','sha256':SOURCE_PINS[CAPTURE+'/qualifications.json'],
                'raw_source_sha256':RAW_SHA256,'capture_file':CAPTURE+'/capture.json',
                'capture_sha256':SOURCE_PINS[CAPTURE+'/capture.json'],'review_file':FOLDER+'/review.json',
                'review_sha256':REVIEW_PIN,'semantic_review_file':CAPTURE+'/semantic-review.json',
                'semantic_review_sha256':SOURCE_PINS[CAPTURE+'/semantic-review.json']})
        adapted={'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW','original_forms':list(originals),
            'assessment':{'intent':INTENT,'negative_scope_proposal':
                {'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record=first.make_record(adapted,review,occurrences,source_id=SOURCE_ID,
            source_reference=CAPTURE+'/qualifications.json#source_record_ordinal='+str(rows[0]['source_record_ordinal']),
            review_folder=FOLDER,allowed_intents={INTENT});record['evidence_ref']=FOLDER+'/review.json#'+key
        records.append(record)
    source={'source_id':SOURCE_ID,'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-11','valid_until':review['valid_until'],
        'capture_kind':'frozen_ofqual_animal_study_qualification_titles','metrics_copied_into_records':False,
        'current_course_offering_or_demand_claimed':False,'independent_human_review_claimed':False}
    existing=set(review['fresh_variant_review']['existing_held_protection_keys'])
    protections=[{'query_id':'BSRE-Q-'+hashlib.sha256(k.encode('utf-8')).hexdigest()[:24],'text':k,
        'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
        'evidence_ref':FOLDER+'/review.json#'+k,'reviewed_on':review['reviewed_on'],
        'valid_until':review['valid_until'],'source_kind':'official_reference',
        'protection_basis':'UNRESOLVED_FULL_SOURCE_LITERAL_NOT_DEMAND_OR_PERMANENT_INELIGIBILITY'}
        for k in sorted(review['held_groups']) if k not in existing]
    return {'records':records,'sources':[source],'protected_queries':[],
        'campaigns':base['campaigns'],'campaign_context':base['campaign_context']},protections


def _outputs(inputs, material, root, when):
    result=stage.checked_audit(inputs,when);state=inputs[STAGE_KEY];new=inputs['records'][state['retained_records']:]
    protections=inputs['protected_queries'][state['retained_protections']:];d=material['review']['fresh_variant_review']
    occurrences=sum(len(r['provenance_occurrences']) for r in new)
    first.need(len(new)==len(material['review']['selected_normalized_phrases']) and occurrences==sum(
        len(material['groups'][k]) for k in material['review']['selected_normalized_phrases']),
        'ANIMAL_CARE_SOURCE_OCCURRENCES_CHANGED')
    index={'version':1,'scope':'APPEND_ONLY_ANIMAL_CARE_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'text_pins':dict(TEXT_PINS),'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[r['query_id'] for r in protections],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort={'scope':'AI_REVIEWED_OFFICIAL_ANIMAL_QUALIFICATION_TITLES_NOT_DEMAND',
        'source_occurrences':444,'source_groups':423,'cohort_occurrences':214,'cohort_groups':213,
        'text_clear_occurrences':103,'text_flagged_occurrences':111,'wording_hold_occurrences':2,
        'compatible_proposed_groups':101,'selected_groups':len(new),'new_source_occurrences':occurrences,
        'held_groups':len(material['review']['held_groups']),'additional_variant_holds':len(d['additional_variant_holds']),
        'external_key_comparisons':d['external_key_comparisons'],'within_source_key_comparisons':d['within_source_key_comparisons'],
        'cohort_external_key_comparisons':852,'cohort_within_source_key_comparisons':852,
        'new_protections':len(protections),'existing_held_protection_occurrences':len(d['existing_held_protection_keys']),
        'previous_available_occurrences_excluded':52,'unavailable_source_occurrences':178,
        'parent_membership_alone_causes_hold':False,'independent_ai_or_human_approval_claimed':False,
        **{k:False for k in LIMITS}}
    summary={'scope':'CURRENT_RESEARCH_AFTER_ANIMAL_CARE_APPEND_ONLY_REVIEW',
        **{k:result[k] for k in ['as_of','input_rows','distinct_nonblank_phrases','reviewed_eligible_rows',
            'excluded_rows','approved_exclusion_rows','target','deficit','exact_target_pass','structural_pass',
            'deployment_export_allowed','production_writes_available','positive_library_coverage_verified','protected_queries_indexed']},
        'computed_conflicts':len(result['protected_conflicts']),'prior_rows':state['retained_records'],'new_rows':len(new),
        'archived_original_rows':len(inputs['archived_records']),
        'source_occurrences_retained_in_current_records':sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'new_exact_provenance_occurrences':occurrences,'new_proposal_holds':len(material['review']['held_groups']),
        'historical_records_rewritten':False,'human_review_verified':False,'live_campaign_mapping_verified':False,'release_authorized':False}
    pin=prior.OUTPUT_PINS['research-pool-allocation.json'];previous=first.pinned(root,prior.FOLDER+'/research-pool-allocation.json',pin)
    first.need(previous['total_target']==14000 and previous['total_admitted']==11885 and
        previous['remaining']['ACADEMIC']==111,'ANIMAL_CARE_ALLOCATION_BASE_CHANGED')
    admitted=dict(previous['admitted']);admitted['ACADEMIC']+=len(new)
    remaining={k:previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v>=0 for v in remaining.values()) and sum(admitted.values())==len(inputs['records']),
        'ANIMAL_CARE_ALLOCATION_COUNTS')
    allocation={'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL','requirements_ref':first.MASTER,
        'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json','previous_allocation_sha256':pin,
        'targets':previous['targets'],'before':previous['targets'],'target_transfer':None,'new_rows':{'ACADEMIC':len(new)},
        'admitted':admitted,'remaining':remaining,'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),'owner_approval_claimed':False,'media_budget_changed':False,
        'exclusion_approval_granted':False}
    return {'index.json':index,'cohort-report.json':cohort,'library-report.json':dict(summary,as_of=material['review']['reviewed_on']),
        'research-pool-allocation.json':allocation},summary
