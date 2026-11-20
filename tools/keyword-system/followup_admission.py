"""Append-only follow-up research over a caller-fresh vendor snapshot.

The old vendor reconstruction remains mandatory and unchanged. Heuristic preview
holds are not historical semantic workbench holds; this layer binds a separate
manual review without weakening any historical admission rule. No live writer.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date, timedelta
import hashlib
from pathlib import Path

import negative_admission as first
import negative_library as history
import followup_reconciliation as capture
from keyword_audit import audit, normalize, tokens

FOLDER = 'docs/audit/keyword-negative-followup-admission-2026-11-11'
PRELIMINARY = 'docs/audit/keyword-employment-followup-reconciled-2026-11-11/review.json'
PRELIMINARY_PIN = '706a600d1db0d72a663d2810e5307312c7aebe001cb3c1a47cb9227d71fd45d5'
REVIEW_PIN = 'efe1ed60f37f16f6bee3992135f61bb17ed37a390fa3aa00273e0cbda4144025'
INDEX_PIN = '2486aa3e638953518c4581360befba1896f8e6e5f8ef26120e6861f3ef479df9'
COHORT_REPORT_PIN = '65ad221407767f92c04bdd1b1274cee5a8009400ca7c248a9b140f1cc0bb6fdb'
LIBRARY_REPORT_PIN = '484be86c6215b3df5adf35918c2c13db760f7856ecf107e49c60eef5a2e17bbc'
ALLOCATION_PIN = '2f35c75fc7213902e098faeb47cbe198b834331b57f77c8c2764690da5307bac'
VENDOR_INDEX = 'tools/keyword-system/data/negative-extension-index.json'
VENDOR_INDEX_PIN = 'dad9573128190e6a8fa9d039af6d9cc8a0ef2720d7796dc875cfc2b0ca625229'
VENDOR_REPORT = capture.BASELINE_REPORT
VENDOR_ALLOCATION = 'docs/audit/keyword-negative-vendor-admission-2026-11-11/research-pool-allocation.json'
VENDOR_ALLOCATION_PIN = 'b39bc2500950b2a77367d137d05dc9666f1c4df8c80469f8a0f26ce4b7a42291'
VENDOR_RECORDS_SHA256 = 'f57593f690d33d3d1d97c8679f35dd95712144f811f0117a617e6d9719f095f8'
VENDOR_ARCHIVED_SHA256 = '54acfaf519c792c8dc31d4739fc8503f0be1939a3ff2c901e149cffacc22b160'
VENDOR_PROTECTION_SHA256 = '370633eed3091f9109b59295da8372c719a9c6f11f0c7130ca2e36ddd1e542c3'
VENDOR_SOURCE_SHA256 = '3a19b71d5c53c81e313297bb753d205e72e2781dbf99e0416411dbd7b98173ca'
VENDOR_CONTEXT_SHA256 = '90b774f0074b93b7c2eee7a6b9cb712860d12539b7708e69163edb5135211f56'
COHORT_KEY = 'followup-employment-20261111'
INTENTS = {'EXPLICIT_EMPLOYMENT_RESEARCH', 'EXPLICIT_OCCUPATIONAL_ENTRY_RESEARCH'}
LIMITS = ('human_review_verified', 'exclusion_approval_granted',
          'live_binding_verified', 'production_authorized')
VALIDITY = 'LOCAL_30_DAY_REVIEW_DEADLINE_NOT_GOOGLE_EXPIRY_OR_FRESHNESS_GUARANTEE'


def digest(value):
    return hashlib.sha256(first.canonical(value)).hexdigest()


def reference(file, pin):
    return {'file': file, 'sha256': pin}


def final_review_subject(review, context, campaign):
    return digest({'review': {k: v for k, v in review.items() if k != 'subject_sha256'},
        'service_context': context, 'planned_campaign': campaign,
        'preliminary_review': reference(PRELIMINARY, PRELIMINARY_PIN),
        'capture_pins': capture.SOURCES, 'original_scope_pins': first.PINS,
        'vendor_index': reference(VENDOR_INDEX, VENDOR_INDEX_PIN),
        'vendor_report': VENDOR_REPORT})


def validate_final_review(review, preliminary, reconciled, context, campaign, when):
    required = {'version', 'scope', 'cohort_key', 'reviewer', 'reviewer_kind', 'reviewed_on',
        'valid_until', 'validity_basis', 'campaign_key', 'landing_page_id', 'preliminary_review',
        'selected_canonical_ids', 'held_phrases', 'existing_occurrence_only_ids',
        'intent_by_canonical_id', 'semantic_rationale', 'heuristic_preview_reassessment',
        'variant_review', 'source_identity_limits', 'subject_sha256'} | set(LIMITS)
    first.need(isinstance(review, dict) and set(review) == required, 'FOLLOWUP_REVIEW_SCHEMA')
    first.need(type(review['version']) is int and review['version'] == 1 and
        review['scope'] == 'AI_REVIEWED_PLANNING_RESEARCH_NOT_EXCLUSION_APPROVAL' and
        review['cohort_key'] == COHORT_KEY and review['reviewer'] == first.REVIEWER and
        review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[k] is False for k in LIMITS), 'FOLLOWUP_REVIEW_AUTHORITY')
    first.need(review['preliminary_review'] == reference(PRELIMINARY, PRELIMINARY_PIN),
               'FOLLOWUP_PRELIMINARY_CHANGED')
    first.need(review['campaign_key'] == campaign['campaign_key'] == first.CAMPAIGN and
        review['landing_page_id'] == campaign['landing_page_id'] == first.PAGE and
        campaign['family_code'] == 'RNT' and campaign['family_slot'] == 1 and
        campaign['actual_url'] is None and campaign['google_campaign_id'] is None and
        campaign['release_approved'] is False and context['source_url'] ==
        'https://blackswanrealestate.ae/enquire/rent/' and context['context_kind'] ==
        'PUBLIC_RENTAL_INTAKE_PURPOSE_NOT_INVENTORY_OR_DELIVERY' and
        all(context[k] is False for k in ('inventory_or_availability_verified',
            'submission_or_consent_action_performed', 'live_campaign_mapping_assigned')),
        'FOLLOWUP_PLANNING_SCOPE_CHANGED')
    first.need(isinstance(review['reviewed_on'],str) and isinstance(review['valid_until'],str) and
        type(when) is date, 'FOLLOWUP_REVIEW_DATES')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        end-start == timedelta(days=30) and review['validity_basis'] == VALIDITY and
        context['observed_date_dubai'] <= review['reviewed_on'] and start <= when <= end,
        'FOLLOWUP_REVIEW_DATES')
    selected, held, existing = (review['selected_canonical_ids'], review['held_phrases'],
                               review['existing_occurrence_only_ids'])
    first.need(type(selected) is list and bool(selected) and type(existing) is list and
        type(held) is dict and all(isinstance(k, str) for k in selected+existing) and
        selected == sorted(set(selected)) and existing == sorted(set(existing)) and
        all(isinstance(k, str) and isinstance(v, str) and v.strip() for k,v in held.items()),
        'FOLLOWUP_REVIEW_MEMBERSHIP')
    source = {r['canonical_id']: r for r in reconciled['records']}
    prior = {r['canonical_id']: r for r in preliminary['records']}
    first.need(set(selected) | set(held) | set(existing) == set(source) == set(prior) and
        len(selected)+len(held)+len(existing) == len(source), 'FOLLOWUP_REVIEW_PARTITION')
    first.need(all(prior[k]['disposition'] == 'NEGATIVE_EXACT_REVIEW' for k in selected) and
        all(prior[k]['disposition'] == 'EXISTING_NEGATIVE_NO_NEW_ROW' for k in existing) and
        all(k in held for k,r in prior.items() if r['disposition'] == 'HOLD'),
        'FOLLOWUP_PRIOR_HOLD_NOT_PRESERVED')
    first.need(all(source[k]['preview_state'] != 'DISAGREEMENT_HOLD' for k in selected) and
        all(k in held for k,r in source.items() if r['preview_state'] == 'DISAGREEMENT_HOLD'),
        'FOLLOWUP_DISAGREEMENT_BYPASS')
    intents = review['intent_by_canonical_id']
    first.need(type(intents) is dict and set(intents) == set(selected) and
        all(isinstance(v,str) and v in INTENTS for v in intents.values()), 'FOLLOWUP_INTENT_REVIEW')
    for key in ('semantic_rationale', 'heuristic_preview_reassessment', 'source_identity_limits'):
        first.need(isinstance(review[key],str) and review[key].strip(), 'FOLLOWUP_REVIEW_EXPLANATION')
    bags = defaultdict(list)
    for row in source.values(): bags[tuple(sorted(tokens(row['normalized_keyword'])))].append(row['canonical_id'])
    groups = [v for v in bags.values() if len(v)>1]
    first.need(not set(selected) & {k for group in groups for k in group},
               'FOLLOWUP_INTERNAL_VARIANT_HOLD')
    variants = review['variant_review']
    first.need(type(variants) is dict and set(variants) == {'token_bag_groups','phrases_in_groups',
        'method','google_equivalence_verified','counts_distinct_concepts'} and
        type(variants['token_bag_groups']) is int and variants['token_bag_groups'] == len(groups) and
        type(variants['phrases_in_groups']) is int and variants['phrases_in_groups'] == sum(map(len,groups)) and
        variants['method'] == 'MANUAL_AI_WORDING_REVIEW_NOT_PLATFORM_CERTIFICATE' and
        variants['google_equivalence_verified'] is False and variants['counts_distinct_concepts'] is False,
        'FOLLOWUP_VARIANT_REVIEW')
    first.need(review['subject_sha256'] == final_review_subject(review,context,campaign),
               'FOLLOWUP_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    """Re-read immutable public sources and the separately registered AI review."""
    documents = capture.load_sources(root)
    reconciled = capture.reconcile_sources(documents)
    preliminary = first.pinned(root, PRELIMINARY, PRELIMINARY_PIN)
    first.pinned(root, VENDOR_REPORT['file'], VENDOR_REPORT['sha256'])
    raw_report = (Path(root)/VENDOR_REPORT['file']).read_bytes()
    capture.validate_preliminary_review(preliminary,reconciled,raw_report)
    context = first.pinned(root,first.FOLDER+'/service-context.json',first.CONTEXT_PIN)
    registry = first.pinned(root,first.REGISTRY,first.PINS[first.REGISTRY])
    campaign = next(r for r in registry if r['campaign_key'] == first.CAMPAIGN)
    review = first.pinned(root,FOLDER+'/review.json',REVIEW_PIN)
    validate_final_review(review,preliminary,reconciled,context,campaign,when)
    first.pinned(root,first.MASTER,first.PINS[first.MASTER])
    first.pinned(root,VENDOR_INDEX,VENDOR_INDEX_PIN)
    return {'review':review,'preliminary':preliminary,'reconciled':reconciled,
            'context':context,'registry':registry}


def verify_base(base, material):
    """Require the exact vendor snapshot already verified by this invocation."""
    first.need(len(base['records']) == 10014 and len(base['archived_records']) == 12 and
        len(base['protected_queries']) == 15309 and
        digest(base['records']) == VENDOR_RECORDS_SHA256 and
        digest(base['archived_records']) == VENDOR_ARCHIVED_SHA256 and
        digest(base['protected_queries']) == VENDOR_PROTECTION_SHA256 and
        digest(base['sources']) == VENDOR_SOURCE_SHA256 and
        digest(base['campaign_context']) == VENDOR_CONTEXT_SHA256,
        'FOLLOWUP_VENDOR_BASE_CHANGED')
    first.need(first.canonical(base['campaigns']) == first.canonical(material['registry']),
               'FOLLOWUP_VENDOR_REGISTRY_CHANGED')
    current = {normalize(r['original_text']) for r in base['records']}
    protected = {normalize(r['text']) for r in base['protected_queries']}
    first.need(len(current)==10014 and len(protected)==15309 and not current & protected,
               'FOLLOWUP_VENDOR_PROTECTION_CHANGED')
    for row in material['preliminary']['records']:
        key = row['normalized_keyword']
        observed = ('EXISTING_NEGATIVE' if key in current else
            'EXISTING_PROTECTED' if key in protected else 'NOVEL_UNPROTECTED')
        first.need(row['baseline_membership']==observed, 'FOLLOWUP_CURRENT_MEMBERSHIP_CHANGED')
    # The final manual review held all observed reordering ambiguity. Verify the
    # current complete base has not introduced an equal-token-bag variant.
    previous_bags = {tuple(sorted(tokens(r['original_text'])))
        for r in base['records']+base['archived_records']}
    previous_bags.update(tuple(sorted(tokens(r['text']))) for r in base['protected_queries'])
    source = {r['canonical_id']:r for r in material['reconciled']['records']}
    first.need(all(tuple(sorted(tokens(source[k]['normalized_keyword']))) not in previous_bags
        for k in material['review']['selected_canonical_ids']), 'FOLLOWUP_PRIOR_VARIANT_HOLD')


def apply_overlay(base, review, reconciled):
    """Pure protective split: preserve all old bodies and append new protection."""
    rows = {r['canonical_id']:r for r in reconciled['records']}
    held = {rows[k]['normalized_keyword'] for k in review['held_phrases']}
    records, archived = [], []
    for row in base['records']:
        (archived if normalize(row['original_text']) in held else records).append(row)
    old_protected = {normalize(r['text']):r for r in base['protected_queries']}
    first.need(len(old_protected)==len(base['protected_queries']), 'FOLLOWUP_DUPLICATE_PROTECTION')
    additions = []
    for key in sorted(held-set(old_protected)):
        identity = 'BSRE-Q-'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]
        additions.append({'query_id':identity,'text':key,'campaign_keys':[first.CAMPAIGN],
            'services':['residential_rental'],'must_serve':True,
            'evidence_ref':FOLDER+'/review.json#'+capture.canonical_id(key),
            'reviewed_on':review['reviewed_on'],'valid_until':review['valid_until']})
    combined = base['protected_queries']+additions
    first.need(len({r['query_id'] for r in combined})==len(combined), 'FOLLOWUP_PROTECTION_ID_COLLISION')
    return deepcopy(dict(base, records=records,
        archived_records=base['archived_records']+archived, protected_queries=combined,
        followup_newly_archived=archived, followup_added_protections=additions,
        deployment_authorized=False, production_writes_available=False))


def build_cohort(base, material):
    """Only final manual selections can become research records; previews cannot."""
    review, reconciled = material['review'], material['reconciled']
    rows = {r['canonical_id']:r for r in reconciled['records']}
    existing = {normalize(r['original_text']) for r in base['records']+base['archived_records']}
    protected = {normalize(r['text']) for r in base['protected_queries']}
    records = []
    for identity in review['selected_canonical_ids']:
        source = rows[identity]
        key = source['normalized_keyword']
        first.need(key not in existing and key not in protected and
            len(source['keyword_variants'])==1,'FOLLOWUP_SELECTED_NOT_NOVEL')
        occurrences = []
        for ref in source['provenance_occurrences']:
            spec = capture.SOURCES[ref['source_key']]
            occurrences.append({'batch':ref['batch_id'],'source_line':ref['source_line'],
                'file':spec['folder']+'/'+spec['batch_file'],'sha256':ref['batch_sha256'],
                'review_file':FOLDER+'/review.json','review_sha256':REVIEW_PIN,
                'original_preview_file':spec['folder']+'/semantic-review-preview.json',
                'original_preview_sha256':spec['pins']['semantic-review-preview.json'],
                'source_sha256':ref['source_sha256']})
        first.need(len(occurrences)==2 and len({r['batch'] for r in occurrences})==2,
                   'FOLLOWUP_SOURCE_OCCURRENCES_LOST')
        adapted = {'normalized_text':key,'disposition':'NEGATIVE_EXACT_REVIEW',
            'original_forms':source['keyword_variants'],
            'assessment':{'intent':review['intent_by_canonical_id'][identity],
                'negative_scope_proposal':{'type':'CAMPAIGN','campaign_keys':[],
                    'approved':False,'match_type':'EXACT'}}}
        record = first.make_record(adapted,review,occurrences,
            source_id=source['provenance_occurrences'][0]['batch_id'],
            source_reference=occurrences[0]['file']+'#'+str(occurrences[0]['source_line']),
            review_folder=FOLDER,allowed_intents=INTENTS)
        record['evidence_ref'] = FOLDER+'/review.json#'+identity
        records.append(record)
    # Keep the exact source order while retaining every source occurrence.
    records.sort(key=lambda r:r['normalized_text'])
    source_catalog = [{'source_id':r['batch_id'],'kind':'official_reference',
        'approved_for_research':True,'evidence_ref':r['folder']+'/capture.json',
        'observed_on':'2026-11-11','valid_until':review['valid_until'],
        'research_use_basis':'OWNER_AUTHORIZED_PLANNER_RESEARCH_AND_VERIFIED_PROVIDER_CAPTURE',
        'served_query_or_current_performance_claimed':False}
        for r in reconciled['sources']]
    return {'records':records,'sources':source_catalog,'campaigns':base['campaigns'],
        'campaign_context':deepcopy(base['campaign_context']),'protected_queries':[]}


def extend(base, root, when):
    """Use a caller-fresh vendor snapshot once; never reuse an acceptance cache."""
    material = load_reviewed(root,when)
    verify_base(base,material)
    overlaid = apply_overlay(base,material['review'],material['reconciled'])
    part = build_cohort(overlaid,material)
    combined = history.compose([overlaid,part])
    result = deepcopy(dict(combined, archived_records=overlaid['archived_records'],
        followup_review=material['review'], followup_reconciled=material['reconciled'],
        followup_newly_archived=overlaid['followup_newly_archived'],
        followup_added_protections=overlaid['followup_added_protections'],
        followup_base_records_sha256=digest(base['records']),
        followup_base_archived_sha256=digest(base['archived_records']),
        followup_retained_records_sha256=digest(overlaid['records']),
        followup_base_protection_sha256=digest(base['protected_queries']),
        followup_base_source_sha256=digest(base['sources']),
        followup_new_records=part['records'], followup_base_sources=base['sources'],
        followup_retained_rows=len(overlaid['records']),
        deployment_authorized=False,production_writes_available=False))
    first.need(first.canonical(result['records'][:result['followup_retained_rows']]) ==
        first.canonical(overlaid['records']) and result['archived_records'][:12]==base['archived_records'],
        'FOLLOWUP_HISTORICAL_BODY_REPLACED')
    return result


def build_index(inputs):
    records, archived = inputs['records'], inputs['archived_records']
    new = inputs['followup_new_records']
    n = inputs['followup_retained_rows']
    first.need(digest(records[:n])==inputs['followup_retained_records_sha256'] and
        first.canonical(records[n:])==first.canonical(new), 'FOLLOWUP_PREFIX_CHANGED')
    first.need(len({r['keyword_id'] for r in records+archived})==len(records)+len(archived) and
        len({normalize(r['original_text']) for r in records+archived})==len(records)+len(archived),
        'FOLLOWUP_IDENTITY_COLLISION')
    return {'version':1,'scope':'FOLLOWUP_RESEARCH_INDEX_AND_HOLD_OVERLAY_NOT_APPROVAL',
        'vendor_index':reference(VENDOR_INDEX,VENDOR_INDEX_PIN),'vendor_report':VENDOR_REPORT,
        'review':reference(FOLDER+'/review.json',REVIEW_PIN),
        'preliminary_review':reference(PRELIMINARY,PRELIMINARY_PIN),
        'counts':{'vendor_eligible':10014,'retained_vendor':n,'new':len(new),'eligible':len(records),
            'newly_archived':len(inputs['followup_newly_archived']),'archived_originals':len(archived),
            'new_protections':len(inputs['followup_added_protections']),
            'protected_queries':len(inputs['protected_queries'])},
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_held_keyword_ids':[r['keyword_id'] for r in inputs['followup_newly_archived']],
        'additional_protected_query_ids':[r['query_id'] for r in inputs['followup_added_protections']],
        'vendor_records_sha256':inputs['followup_base_records_sha256'],
        'vendor_archived_sha256':inputs['followup_base_archived_sha256'],
        'vendor_protection_sha256':inputs['followup_base_protection_sha256'],
        'vendor_sources_sha256':inputs['followup_base_source_sha256'],
        'vendor_context_sha256':VENDOR_CONTEXT_SHA256,
        'retained_vendor_records_sha256':digest(records[:n]),
        'additional_records_sha256':digest(new),'archived_records_sha256':digest(archived),
        'protected_queries_sha256':digest(inputs['protected_queries']),
        'sources_sha256':digest(inputs['sources']),
        'research_only':True,'human_review_verified':False,'exclusion_approval_granted':False,
        'deployment_authorized':False,'historical_records_rewritten':False}


def cohort_report(inputs):
    review = inputs['followup_review']
    records = inputs['followup_new_records']
    return {'scope':'AI_REVIEWED_FOLLOWUP_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'review':reference(FOLDER+'/review.json',REVIEW_PIN),
        'preliminary_review':reference(PRELIMINARY,PRELIMINARY_PIN),
        'source_capture_pins':capture.SOURCES,
        'canonical_source_rows':len(inputs['followup_reconciled']['records']),
        'source_occurrences':inputs['followup_reconciled']['counts']['source_occurrences'],
        'reviewed_rows':len(records),'held_phrases':len(review['held_phrases']),
        'existing_occurrence_only':len(review['existing_occurrence_only_ids']),
        'preview_disagreements_held':inputs['followup_reconciled']['counts']['disagreement_hold'],
        'retained_new_record_occurrences':sum(len(r['provenance_occurrences']) for r in records),
        'intent_counts':dict(Counter(r['reason_code'] for r in records)),
        'record_bodies_sha256':digest(records),
        'human_review_verified':False,'exclusion_approval_granted':False,
        'live_binding_verified':False,'production_authorized':False}


def summary(inputs, result):
    return {'scope':'CURRENT_RESEARCH_AFTER_EXPLICIT_FOLLOWUP_REVIEW_AND_HOLD_OVERLAY',
        **{k:result[k] for k in ('as_of','input_rows','distinct_nonblank_phrases',
            'reviewed_eligible_rows','excluded_rows','approved_exclusion_rows','target','deficit',
            'exact_target_pass','structural_pass','deployment_export_allowed',
            'production_writes_available','positive_library_coverage_verified','protected_queries_indexed')},
        'computed_conflicts':len(result['protected_conflicts']),
        'vendor_rows_before_overlay':10014,'retained_vendor_rows':inputs['followup_retained_rows'],
        'new_rows':len(inputs['followup_new_records']),
        'newly_archived_original_rows':len(inputs['followup_newly_archived']),
        'archived_original_rows':len(inputs['archived_records']),
        'new_proposal_holds':len(inputs['followup_review']['held_phrases']),
        'source_occurrences_retained_in_current_records':sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'human_review_verified':False,'live_campaign_mapping_verified':False,
        'historical_records_rewritten':False,'release_authorized':False}


def allocation(inputs, previous):
    first.need(previous['total_target']==14000 and previous['total_admitted']==10014 and
        sum(previous['admitted'].values())==10014 and sum(previous['targets'].values())==14000,
        'FOLLOWUP_ALLOCATION_BASE_CHANGED')
    # All six old conflicts and the new full-literal cohort are employment
    # research. A previously unknown reason requires explicit pool review.
    first.need(all(r['reason_code'] in INTENTS for r in inputs['followup_newly_archived']),
        'FOLLOWUP_ALLOCATION_UNKNOWN_ARCHIVE')
    first.need(all(r['reason_code'] in INTENTS for r in inputs['followup_new_records']),
        'FOLLOWUP_ALLOCATION_UNKNOWN_ADDITION')
    admitted = dict(previous['admitted'])
    removed, added = len(inputs['followup_newly_archived']),len(inputs['followup_new_records'])
    admitted['EMPLOYMENT'] += added-removed
    targets = dict(previous['targets'])
    remaining = {pool:targets[pool]-count for pool,count in admitted.items()}
    first.need(all(type(n) is int and n>=0 for n in remaining.values()) and
        sum(admitted.values())==len(inputs['records']), 'FOLLOWUP_ALLOCATION_COUNTS')
    return {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':VENDOR_ALLOCATION,
        'previous_allocation_sha256':VENDOR_ALLOCATION_PIN,'before':previous['targets'],
        'targets':targets,'held_deduction':{'EMPLOYMENT':removed},'new_rows':{'EMPLOYMENT':added},
        'basis':'Preserve all research-pool targets; deduct the newly held employment records and add only the explicitly reviewed source-bound employment cohort. No media-budget or exclusion authority changes.',
        'target_transfer':None,'admitted':admitted,'remaining':remaining,
        'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),'owner_approval_claimed':False,
        'media_budget_changed':False,'exclusion_approval_granted':False}


def check_saved(inputs, root, when):
    result = audit('negative',inputs['records'],inputs['sources'],inputs['campaigns'],
        inputs['campaign_context'],inputs['protected_queries'],when)
    current = summary(inputs,result)
    first.need(current['structural_pass'] and current['reviewed_eligible_rows']==len(inputs['records']) and
        current['computed_conflicts']==current['excluded_rows']==current['approved_exclusion_rows']==0 and
        not current['deployment_export_allowed'] and not current['positive_library_coverage_verified'],
        'FOLLOWUP_RESEARCH_NOT_ELIGIBLE')
    comparisons = [('index.json',INDEX_PIN,build_index(inputs)),
        ('cohort-report.json',COHORT_REPORT_PIN,cohort_report(inputs)),
        ('library-report.json',LIBRARY_REPORT_PIN,dict(current,as_of=inputs['followup_review']['reviewed_on'])),
        ('research-pool-allocation.json',ALLOCATION_PIN,allocation(inputs,
            first.pinned(root,VENDOR_ALLOCATION,VENDOR_ALLOCATION_PIN)))]
    for name,pin,expected in comparisons:
        saved = first.pinned(root,FOLDER+'/'+name,pin)
        first.need(first.canonical(saved)==first.canonical(expected), 'FOLLOWUP_SAVED_OUTPUT_CHANGED')
    return dict(current,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',
                release_held=True)

