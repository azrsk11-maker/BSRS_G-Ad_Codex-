"""Append-only valuation employment research over a caller-fresh full snapshot.

All historical reconstruction and audits remain mandatory in the public caller.
Pinned diagnostic snapshots bind the expected corpus; they never replace a fresh
caller reconstruction. No platform writer, approval, export or acceptance cache.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
from pathlib import Path

import negative_admission as first
import negative_library as history
import followup_admission as prior
from keyword_audit import audit, normalize, tokens
from supplemental_discovery import verify_capture

FOLDER = 'docs/audit/keyword-negative-valuation-admission-2026-11-11'
CAPTURE = 'docs/audit/keyword-valuation-employment-2026-11-11'
SOURCE_PINS = {
    CAPTURE+'/capture.json': '9408a2be59c1858152c770d82e833e18a87a6e89b25e927284ad93ef27ecfb76',
    CAPTURE+'/valuation-employment.json': '7be9d5d16a1413cf738b49e8bb92adcdb75e4c02b86bd7e61c940640d7f9371b',
    CAPTURE+'/semantic-review.json': 'f76d38225613c010a84ce7f95ecd8e84b09153f56bfbff469d70329af03760e1',
    CAPTURE+'/membership-snapshot.json': '15ab02cbc6eca0ad5791f8b1b01a2823d41a975b3be32cfc0041b8b61ba090e4',
    CAPTURE+'/existing-overlap-reconciliation.json': '1e94820037d0cfe5445fa39f0374659d17b721fec87600fc2e8c9fa6a28636a0',
}
REVIEW_PIN = 'bff7782db75cc1076f83b9d9084b1fe2c9b88a6349f1c487cfe11b7b0c430f7b'
INDEX_PIN = '887f53e1e7cc98df1bdb4bef4159d4d2fb77694818046f2c4cb5d18bfcd3f57c'
COHORT_REPORT_PIN = 'a0f149409fb6de2178aeedf58a2317203a8ca9dd12b819207fbf3b8fce427b44'
LIBRARY_REPORT_PIN = 'bd0782809fc30ae0f39898045eaa177acc85242cb4af254d485f3cb4fa223456'
ALLOCATION_PIN = '227a68f0732b9c6b62a58a747669e0b53bb213f2eeb1e40ad94c1b558264ddcb'
PREVIOUS_INDEX = prior.FOLDER+'/index.json'
PREVIOUS_REPORT = prior.FOLDER+'/library-report.json'
PREVIOUS_ALLOCATION = prior.FOLDER+'/research-pool-allocation.json'
COHORT_KEY = 'valuation-employment-20261111'
INTENT = 'EXPLICIT_EMPLOYMENT_RESEARCH'
LIMITS = prior.LIMITS
FINAL_VARIANT_LINES = {517, 520}
FINAL_AMBIGUOUS_LINES = {385}


def digest(value):
    return hashlib.sha256(first.canonical(value)).hexdigest()


def reference(file, pin):
    return {'file':file, 'sha256':pin}


def final_review_subject(review, context, campaign):
    return digest({'review':{k:v for k,v in review.items() if k!='subject_sha256'},
        'service_context':context, 'planned_campaign':campaign,
        'source_pins':SOURCE_PINS, 'original_scope_pins':first.PINS,
        'previous_index':reference(PREVIOUS_INDEX,prior.INDEX_PIN),
        'previous_report':reference(PREVIOUS_REPORT,prior.LIBRARY_REPORT_PIN)})


def load_sources(root):
    """Re-read pinned capture, original interpretations and scope evidence."""
    docs = {name:first.pinned(root,name,pin) for name,pin in SOURCE_PINS.items()}
    pins = {Path(name).name:SOURCE_PINS[name] for name in
        (CAPTURE+'/capture.json',CAPTURE+'/valuation-employment.json')}
    verify_capture(Path(root)/CAPTURE,pins)
    batch = docs[CAPTURE+'/valuation-employment.json']
    preliminary = docs[CAPTURE+'/semantic-review.json']
    snapshot = docs[CAPTURE+'/membership-snapshot.json']
    reconciliation = docs[CAPTURE+'/existing-overlap-reconciliation.json']
    source = batch['source_projection']['records']
    rows = preliminary['rows']
    first.need(len(source)==len(rows)==865 and
        preliminary['raw_source_sha256']==batch['source_projection']['source_sha256'] and
        snapshot['source_batch']['sha256']==SOURCE_PINS[CAPTURE+'/valuation-employment.json'],
        'VALUATION_SOURCE_BINDING')
    for raw,row in zip(source,rows):
        first.need((raw['source_line'],raw['values']['Keyword'],normalize(raw['values']['Keyword'])) ==
            (row['source_line'],row['original_text'],row['normalized_text']), 'VALUATION_ROW_IDENTITY')
    byline = {r['source_line']:r for r in rows}
    first.need(len(byline)==865 and len({r['normalized_text'] for r in rows})==865,
        'VALUATION_SOURCE_DUPLICATE')
    groups = {row['normalized_text']:kind for kind,items in snapshot['groups'].items() for row in items}
    first.need(len(groups)==865 and all(r['membership_screen']==groups.get(r['normalized_text']) for r in rows),
        'VALUATION_SNAPSHOT_PARTITION')
    original_documents = {name:first.pinned(root,name,pin)
        for name,pin in reconciliation['source_pins_sha256'].items()}
    reconciled = reconciliation['rows']
    expected = {r['source_line'] for r in rows if
        r['membership_screen']=='existing_eligible' and r['disposition']=='HOLD'}
    first.need(len(reconciled)==len(expected)==16 and {r['source_line'] for r in reconciled}==expected and
        reconciliation['controls']['current_library_changed'] is False and
        reconciliation['controls']['approval_granted'] is False and
        reconciliation['controls']['production_authorized'] is False, 'VALUATION_RECONCILIATION_CHANGED')
    for row in reconciled:
        old = byline[row['source_line']]
        first.need(row['original_text']==old['original_text'] and row['preliminary_row_sha256']==digest(old) and
            row['resolution']=='RETAIN_EXISTING_RESEARCH_ONLY_NO_NEW_ADMISSION' and
            row['new_source_occurrence_accepted'] is False, 'VALUATION_RECONCILIATION_IDENTITY')
        oldbench = original_documents[row['prior_semantic_workbench']['path']]
        priorrow = next(r for r in oldbench['queue'] if r['queue_id']==row['prior_semantic_workbench']['queue_id'])
        first.need(digest(priorrow)==row['prior_semantic_workbench']['row_sha256'] and
            priorrow['normalized_text']==row['normalized_text'] and priorrow['disposition']=='NEGATIVE_EXACT_REVIEW',
            'VALUATION_ORIGINAL_SEMANTIC_REVIEW_CHANGED')
    context = first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN)
    registry = first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])
    first.pinned(root,first.MASTER,first.PINS[first.MASTER])
    index = first.pinned(root,PREVIOUS_INDEX,prior.INDEX_PIN)
    first.pinned(root,PREVIOUS_REPORT,prior.LIBRARY_REPORT_PIN)
    return {'batch':batch,'preliminary':preliminary,'snapshot':snapshot,'reconciliation':reconciliation,
        'rows':byline,'context':context,'registry':registry,'previous_index':index}


def validate_final_review(review, material, when):
    required = {'version','scope','cohort_key','reviewer','reviewer_kind','reviewed_on','valid_until',
        'validity_basis','campaign_key','landing_page_id','source_pins_sha256','selected_source_lines',
        'held_source_lines','existing_occurrence_only_source_lines','selected_intent','semantic_rationale',
        'variant_review','source_identity_limits','subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review)==required, 'VALUATION_REVIEW_SCHEMA')
    first.need(type(review['version']) is int and review['version']==1 and
        review['scope']=='AI_REVIEWED_PLANNING_RESEARCH_NOT_EXCLUSION_APPROVAL' and
        review['cohort_key']==COHORT_KEY and review['reviewer']==first.REVIEWER and
        review['reviewer_kind']=='CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'VALUATION_REVIEW_AUTHORITY')
    context = material['context']
    campaign = next(r for r in material['registry'] if r['campaign_key']==first.CAMPAIGN)
    first.need(review['campaign_key']==campaign['campaign_key']==first.CAMPAIGN and
        review['landing_page_id']==campaign['landing_page_id']==first.PAGE and
        campaign['family_code']=='RNT' and campaign['family_slot']==1 and campaign['actual_url'] is None and
        campaign['google_campaign_id'] is None and campaign['release_approved'] is False and
        context['source_url']=='https://blackswanrealestate.ae/enquire/rent/' and
        context['context_kind']=='PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        all(context[k] is False for k in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed','live_campaign_mapping_assigned')), 'VALUATION_SCOPE_CHANGED')
    first.need(isinstance(review['reviewed_on'],str) and isinstance(review['valid_until'],str) and
        type(when) is date, 'VALUATION_REVIEW_DATES')
    start,end = date.fromisoformat(review['reviewed_on']),date.fromisoformat(review['valid_until'])
    first.need(start.isoformat()==review['reviewed_on'] and end.isoformat()==review['valid_until'] and
        end-start==timedelta(days=30) and review['validity_basis']==prior.VALIDITY and
        context['observed_date_dubai']<=review['reviewed_on'] and start<=when<=end, 'VALUATION_REVIEW_DATES')
    first.need(first.canonical(review['source_pins_sha256'])==first.canonical(SOURCE_PINS),
        'VALUATION_REVIEW_SOURCES_CHANGED')
    selected,held,existing = (review['selected_source_lines'],review['held_source_lines'],
        review['existing_occurrence_only_source_lines'])
    for lines in (selected,existing):
        first.need(type(lines) is list and all(type(n) is int for n in lines) and
            lines==sorted(set(lines)), 'VALUATION_REVIEW_MEMBERSHIP')
    first.need(bool(selected) and type(held) is dict and all(type(k) is str and k.isascii() and
        k.isdecimal() and str(int(k))==k and isinstance(v,str) and v.strip() for k,v in held.items()),
        'VALUATION_REVIEW_MEMBERSHIP')
    heldlines = set(map(int,held))
    rows = material['rows']
    first.need(set(selected)|heldlines|set(existing)==set(rows) and
        len(selected)+len(held)+len(existing)==len(rows), 'VALUATION_REVIEW_PARTITION')
    expected_existing = {n for n,r in rows.items() if r['membership_screen']=='existing_eligible'}
    first.need(set(existing)==expected_existing and all(rows[n]['disposition']=='PROPOSE_NARROW_EMPLOYMENT_RESEARCH'
        and rows[n]['membership_screen']=='novel_unprotected' for n in selected) and
        all(n in heldlines for n,r in rows.items() if r['disposition']=='HOLD' and n not in expected_existing),
        'VALUATION_PRIOR_HOLD_NOT_PRESERVED')
    first.need(FINAL_VARIANT_LINES|FINAL_AMBIGUOUS_LINES <= heldlines,
        'VALUATION_FINAL_SEMANTIC_HOLD_NOT_PRESERVED')
    bags = defaultdict(list)
    for n,r in rows.items(): bags[tuple(sorted(tokens(r['normalized_text'])))].append(n)
    groups = [v for v in bags.values() if len(v)>1]
    byordinal = {r['source_ordinal']:r['source_line'] for r in rows.values()}
    additional = {byordinal[n] for group in material['preliminary']['additional_possible_variant_groups'] for n in group}
    first.need(not set(selected) & ({n for group in groups for n in group}|additional) and
        all(not rows[n]['baseline_equal_token_peers'] for n in selected), 'VALUATION_VARIANT_HOLD')
    expected_variants = {'token_bag_groups':len(groups),'phrases_in_groups':sum(map(len,groups)),
        'additional_possible_variant_groups':len(material['preliminary']['additional_possible_variant_groups'])+1,
        'method':'MANUAL_AI_WORDING_REVIEW_NOT_PLATFORM_CERTIFICATE',
        'google_equivalence_verified':False,'counts_distinct_concepts':False}
    first.need(first.canonical(review['variant_review'])==first.canonical(expected_variants),
        'VALUATION_VARIANT_REVIEW_CHANGED')
    first.need(review['selected_intent']==INTENT and all(isinstance(review[k],str) and review[k].strip()
        for k in ('semantic_rationale','source_identity_limits')), 'VALUATION_INTENT_REVIEW')
    first.need(review['subject_sha256']==final_review_subject(review,context,campaign),
        'VALUATION_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    review = first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_final_review(review,material,when)
    return dict(material,review=review)


def verify_base(base, material):
    """The caller freshly verifies history; bind all exact input body populations."""
    expected = material['snapshot']['baseline']
    first.need(len(base['records'])==expected['eligible']==10199 and
        len(base['archived_records'])==expected['archived']==18 and
        len(base['protected_queries'])==expected['protected']==15499 and
        digest(base['records'])==expected['records_sha256'] and
        digest(base['archived_records'])==expected['archived_sha256'] and
        digest(base['protected_queries'])==expected['protected_sha256'] and
        digest(base['sources'])==material['previous_index']['sources_sha256'] and
        digest(base['campaign_context'])==prior.VENDOR_CONTEXT_SHA256 and
        first.canonical(base['campaigns'])==first.canonical(material['registry']), 'VALUATION_PRIOR_BASE_CHANGED')
    eligible = {normalize(r['original_text']) for r in base['records']}
    archived = {normalize(r['original_text']) for r in base['archived_records']}
    protected = {normalize(r['text']) for r in base['protected_queries']}
    first.need(len(eligible)==10199 and len(archived)==18 and len(protected)==15499 and
        not eligible&protected, 'VALUATION_PRIOR_IDENTITIES_CHANGED')
    for row in material['rows'].values():
        key = row['normalized_text']
        membership = ('archived' if key in archived else 'protected' if key in protected else
            'existing_eligible' if key in eligible else 'novel_unprotected')
        first.need(row['membership_screen']==membership, 'VALUATION_FRESH_MEMBERSHIP_CHANGED')
    previous_bags = {tuple(sorted(tokens(key))) for key in eligible|archived|protected}
    first.need(all(tuple(sorted(tokens(material['rows'][n]['normalized_text']))) not in previous_bags
        for n in material['review']['selected_source_lines']), 'VALUATION_PRIOR_VARIANT_HOLD')


def apply_overlay(base, review, rows):
    """Add new protections without modifying any existing record or archive."""
    held = {rows[int(n)]['normalized_text'] for n in review['held_source_lines']}
    current = {normalize(r['original_text']) for r in base['records']+base['archived_records']}
    first.need(not held&current, 'VALUATION_HELD_EXISTING_NEEDS_RECONCILIATION')
    protected = {normalize(r['text']) for r in base['protected_queries']}
    additions = [{'query_id':'BSRE-Q-'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:24],
        'text':key,'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
        'evidence_ref':FOLDER+'/review.json#source-line-'+str(next(n for n,r in rows.items() if r['normalized_text']==key)),
        'reviewed_on':review['reviewed_on'],'valid_until':review['valid_until']}
        for key in sorted(held-protected)]
    all_queries = base['protected_queries']+additions
    first.need(len({r['query_id'] for r in all_queries})==len(all_queries), 'VALUATION_PROTECTION_ID_COLLISION')
    return deepcopy(dict(base,protected_queries=all_queries,valuation_added_protections=additions,
        deployment_authorized=False,production_writes_available=False))


def build_cohort(base, material):
    review,batch = material['review'],material['batch']
    records = []
    known = {normalize(r['original_text']) for r in base['records']+base['archived_records']}
    protected = {normalize(r['text']) for r in base['protected_queries']}
    for line in review['selected_source_lines']:
        source = material['rows'][line]; key = source['normalized_text']
        first.need(key not in known|protected, 'VALUATION_SELECTED_NOT_NOVEL')
        occurrence = {'batch':batch['batch_id'],'source_line':line,'file':CAPTURE+'/valuation-employment.json',
            'sha256':SOURCE_PINS[CAPTURE+'/valuation-employment.json'],'review_file':FOLDER+'/review.json',
            'review_sha256':REVIEW_PIN,'original_semantic_review_file':CAPTURE+'/semantic-review.json',
            'original_semantic_review_sha256':SOURCE_PINS[CAPTURE+'/semantic-review.json'],
            'source_sha256':batch['source_projection']['source_sha256']}
        row = {'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW','original_forms':[source['original_text']],
            'assessment':{'intent':INTENT,'negative_scope_proposal':{'type':'CAMPAIGN','campaign_keys':[],
                'approved':False,'match_type':'EXACT'}}}
        record = first.make_record(row,review,[occurrence],source_id=batch['batch_id'],
            source_reference=occurrence['file']+'#'+str(line),review_folder=FOLDER,allowed_intents={INTENT})
        record['evidence_ref'] = FOLDER+'/review.json#source-line-'+str(line)
        records.append(record)
    records.sort(key=lambda r:r['normalized_text'])
    sources = [{'source_id':batch['batch_id'],'kind':'official_reference','approved_for_research':True,
        'evidence_ref':CAPTURE+'/capture.json','observed_on':'2026-11-11','valid_until':review['valid_until'],
        'research_use_basis':'OWNER_AUTHORIZED_PLANNER_RESEARCH_AND_VERIFIED_PROVIDER_CAPTURE',
        'served_query_or_current_performance_claimed':False}]
    return {'records':records,'sources':sources,'campaigns':base['campaigns'],
        'campaign_context':base['campaign_context'],'protected_queries':[]}


def extend(base, root, when):
    material = load_reviewed(root,when)
    verify_base(base,material)
    overlaid = apply_overlay(base,material['review'],material['rows'])
    part = build_cohort(overlaid,material)
    combined = history.compose([overlaid,part])
    # Preserve caller metadata and all historical state; only these fields extend.
    result = deepcopy(dict(base,**combined,archived_records=base['archived_records'],
        valuation_review=material['review'],valuation_rows=material['rows'],
        valuation_new_records=deepcopy(part['records']),
        valuation_added_protections=deepcopy(overlaid['valuation_added_protections']),
        valuation_base_records_sha256=digest(base['records']),
        valuation_base_archived_sha256=digest(base['archived_records']),
        valuation_base_protection_sha256=digest(base['protected_queries']),
        valuation_base_sources_sha256=digest(base['sources']),
        valuation_base_context_sha256=digest(base['campaign_context']),
        valuation_retained_rows=len(base['records']),
        valuation_retained_source_rows=len(base['sources']),
        valuation_retained_protected_rows=len(base['protected_queries']),
        deployment_authorized=False,production_writes_available=False))
    first.need(first.canonical(result['records'][:len(base['records'])])==first.canonical(base['records']) and
        result['archived_records']==base['archived_records'] and
        result['protected_queries'][:len(base['protected_queries'])]==base['protected_queries'],
        'VALUATION_HISTORICAL_BODY_REPLACED')
    return result


def build_index(inputs):
    records,archived = inputs['records'],inputs['archived_records']
    n = inputs['valuation_retained_rows']; new = inputs['valuation_new_records']
    q,s = inputs['valuation_retained_protected_rows'],inputs['valuation_retained_source_rows']
    first.need(digest(records[:n])==inputs['valuation_base_records_sha256'] and
        first.canonical(records[n:])==first.canonical(new) and
        digest(archived)==inputs['valuation_base_archived_sha256'], 'VALUATION_PREFIX_CHANGED')
    first.need(digest(inputs['protected_queries'][:q])==inputs['valuation_base_protection_sha256'] and
        first.canonical(inputs['protected_queries'][q:])==first.canonical(inputs['valuation_added_protections']) and
        digest(inputs['sources'][:s])==inputs['valuation_base_sources_sha256'] and
        digest(inputs['campaign_context'])==inputs['valuation_base_context_sha256'],
        'VALUATION_EVIDENCE_PREFIX_CHANGED')
    first.need(len({r['keyword_id'] for r in records+archived})==len(records)+len(archived) and
        len({normalize(r['original_text']) for r in records+archived})==len(records)+len(archived),
        'VALUATION_IDENTITY_COLLISION')
    return {'version':1,'scope':'VALUATION_RESEARCH_INDEX_AND_PROTECTION_NOT_APPROVAL',
        'previous_index':reference(PREVIOUS_INDEX,prior.INDEX_PIN),
        'previous_report':reference(PREVIOUS_REPORT,prior.LIBRARY_REPORT_PIN),
        'review':reference(FOLDER+'/review.json',REVIEW_PIN),'source_pins':SOURCE_PINS,
        'counts':{'retained_prior':n,'new':len(new),'eligible':len(records),'archived_originals':len(archived),
            'new_protections':len(inputs['valuation_added_protections']),'protected_queries':len(inputs['protected_queries'])},
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[r['query_id'] for r in inputs['valuation_added_protections']],
        'prior_records_sha256':inputs['valuation_base_records_sha256'],
        'prior_archived_sha256':inputs['valuation_base_archived_sha256'],
        'prior_protection_sha256':inputs['valuation_base_protection_sha256'],
        'prior_sources_sha256':inputs['valuation_base_sources_sha256'],
        'prior_context_sha256':inputs['valuation_base_context_sha256'],
        'additional_records_sha256':digest(new),'records_sha256':digest(records),
        'archived_records_sha256':digest(archived),'protected_queries_sha256':digest(inputs['protected_queries']),
        'sources_sha256':digest(inputs['sources']),'research_only':True,'human_review_verified':False,
        'exclusion_approval_granted':False,'deployment_authorized':False,'historical_records_rewritten':False}


def cohort_report(inputs):
    review = inputs['valuation_review']; records = inputs['valuation_new_records']
    return {'scope':'AI_REVIEWED_VALUATION_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'review':reference(FOLDER+'/review.json',REVIEW_PIN),'source_pins':SOURCE_PINS,
        'canonical_source_rows':len(inputs['valuation_rows']),'reviewed_rows':len(records),
        'held_phrases':len(review['held_source_lines']),
        'existing_occurrence_only':len(review['existing_occurrence_only_source_lines']),
        'retained_new_record_occurrences':sum(len(r['provenance_occurrences']) for r in records),
        'intent_counts':dict(Counter(r['reason_code'] for r in records)),'record_bodies_sha256':digest(records),
        'human_review_verified':False,'exclusion_approval_granted':False,'live_binding_verified':False,
        'production_authorized':False}


def summary(inputs, result):
    return {'scope':'CURRENT_RESEARCH_AFTER_EXPLICIT_VALUATION_REVIEW_AND_PROTECTION',
        **{k:result[k] for k in ('as_of','input_rows','distinct_nonblank_phrases','reviewed_eligible_rows',
            'excluded_rows','approved_exclusion_rows','target','deficit','exact_target_pass','structural_pass',
            'deployment_export_allowed','production_writes_available','positive_library_coverage_verified',
            'protected_queries_indexed')},'computed_conflicts':len(result['protected_conflicts']),
        'prior_rows':inputs['valuation_retained_rows'],'new_rows':len(inputs['valuation_new_records']),
        'archived_original_rows':len(inputs['archived_records']),
        'new_proposal_holds':len(inputs['valuation_review']['held_source_lines']),
        'source_occurrences_retained_in_current_records':sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'human_review_verified':False,'live_campaign_mapping_verified':False,
        'historical_records_rewritten':False,'release_authorized':False}


def allocation(inputs, previous):
    first.need(previous['total_target']==14000 and previous['total_admitted']==inputs['valuation_retained_rows'] and
        sum(previous['admitted'].values())==inputs['valuation_retained_rows'] and
        sum(previous['targets'].values())==14000,'VALUATION_ALLOCATION_BASE_CHANGED')
    first.need(all(r['reason_code']==INTENT for r in inputs['valuation_new_records']),
        'VALUATION_ALLOCATION_UNKNOWN_ADDITION')
    admitted = dict(previous['admitted']); added = len(inputs['valuation_new_records'])
    admitted['EMPLOYMENT'] += added
    targets = dict(previous['targets']); remaining = {p:targets[p]-n for p,n in admitted.items()}
    first.need(all(type(n) is int and n>=0 for n in remaining.values()) and
        sum(admitted.values())==len(inputs['records']), 'VALUATION_ALLOCATION_COUNTS')
    return {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':PREVIOUS_ALLOCATION,
        'previous_allocation_sha256':prior.ALLOCATION_PIN,'before':previous['targets'],'targets':targets,
        'held_deduction':{},'new_rows':{'EMPLOYMENT':added},
        'basis':'Preserve all research-pool targets and original bodies; add only the source-bound final employment cohort. No media-budget or exclusion authority changes.',
        'target_transfer':None,'admitted':admitted,'remaining':remaining,'total_target':14000,
        'total_admitted':sum(admitted.values()),'total_remaining':sum(remaining.values()),
        'owner_approval_claimed':False,'media_budget_changed':False,'exclusion_approval_granted':False}


def check_saved(inputs, root, when):
    material = load_reviewed(root,when)
    first.need(first.canonical(inputs['valuation_review'])==first.canonical(material['review']) and
        first.canonical(inputs['valuation_rows'])==first.canonical(material['rows']),
        'VALUATION_DERIVED_REVIEW_CHANGED')
    n,q,s = (inputs['valuation_retained_rows'],inputs['valuation_retained_protected_rows'],
        inputs['valuation_retained_source_rows'])
    base = dict(inputs,records=inputs['records'][:n],protected_queries=inputs['protected_queries'][:q],
        sources=inputs['sources'][:s])
    verify_base(base,material)
    overlay = apply_overlay(base,material['review'],material['rows'])
    cohort = build_cohort(overlay,material)
    first.need(first.canonical(inputs['records'][n:])==first.canonical(cohort['records']) and
        first.canonical(inputs['valuation_new_records'])==first.canonical(cohort['records']) and
        first.canonical(inputs['protected_queries'])==first.canonical(overlay['protected_queries']) and
        first.canonical(inputs['sources'][s:])==first.canonical(cohort['sources']),
        'VALUATION_DERIVED_BODIES_CHANGED')
    result = audit('negative',inputs['records'],inputs['sources'],inputs['campaigns'],
        inputs['campaign_context'],inputs['protected_queries'],when)
    current = summary(inputs,result)
    first.need(current['structural_pass'] and current['reviewed_eligible_rows']==len(inputs['records']) and
        current['computed_conflicts']==current['excluded_rows']==current['approved_exclusion_rows']==0 and
        not current['deployment_export_allowed'] and not current['positive_library_coverage_verified'],
        'VALUATION_RESEARCH_NOT_ELIGIBLE')
    expected = [('index.json',INDEX_PIN,build_index(inputs)),
        ('cohort-report.json',COHORT_REPORT_PIN,cohort_report(inputs)),
        ('library-report.json',LIBRARY_REPORT_PIN,dict(current,as_of=inputs['valuation_review']['reviewed_on'])),
        ('research-pool-allocation.json',ALLOCATION_PIN,allocation(inputs,
            first.pinned(root,PREVIOUS_ALLOCATION,prior.ALLOCATION_PIN)))]
    for name,pin,document in expected:
        first.need(first.canonical(first.pinned(root,FOLDER+'/'+name,pin))==first.canonical(document),
            'VALUATION_SAVED_OUTPUT_CHANGED')
    return dict(current,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',release_held=True)
