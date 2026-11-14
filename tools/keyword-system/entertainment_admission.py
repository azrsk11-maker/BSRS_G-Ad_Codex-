"""Append-only genuine Planner clipboard research; no serving or approval writer."""
from datetime import date, timedelta
import hashlib
from pathlib import Path
import runpy

import append_only_admission as stage
from followup_admission import VALIDITY
import keyword_audit as ka
import keyword_text_compatibility as compatibility
import negative_admission as first
import ofqual_admission as prior

FOLDER = 'docs/audit/keyword-negative-entertainment-admission-2026-11-11'
CAPTURE = 'docs/audit/keyword-entertainment-clipboard-2026-11-11'
SECOND = 'docs/audit/keyword-entertainment-admission-review-2026-11-11'
SOURCE_PINS = {
    CAPTURE+'/keywords.json': 'a3d8882f5edc61e40c482772723596caaf050a0d7a792e5fe4991be64b14e74f',
    CAPTURE+'/capture.json': '929321ac43e8a7acf9511c5d974b124d6a1448099860873929099991556aeabc',
    CAPTURE+'/review.json': 'dad9ca570b860ce3a0061eff2269d0a8d9c5cf026c20d83ff5eabff284bc5179',
    CAPTURE+'/lexical.json': 'e12dc3149d9ba8d8543d8ce4505899aa0f19f4a7ef5a99382afd6fd7097de597',
    SECOND+'/review.json': 'c96f199aae33de35356c26930d331e1225e37065bb7ae5a78e31d509ae1ef5ce',
    SECOND+'/resolution-evidence.json': '8a67879ba41b8aadca3c70656d18ba9a3f51f85080a065d358d4590763b21346',
    SECOND+'/reconciliation.json': 'dc7a56254791a137b546333203e4c83a4dc5a5e7872fa09657aae0685c578995',
}
CAPTURE_CODE_PINS = {
    CAPTURE+'/capture_tools.py': '135956c53c683d72c7357747d1c7f92bc44e313b5d1922b69f672caa44ab0140',
    CAPTURE+'/verify_capture.py': '2f4ba4f9e2d132ee972e2d776efa4aa59690e2632c1b8350f0d15d76150b6b55',
}
BASE_SHA256 = '9c4404b7997646efb9f5d9a4f8f794186425f5b7377614475d1af2536534437a'
REVIEW_PIN = 'eee92a456680a3e9a6e8681ce301ad6de117d44054c7848b91f378d79db4d9db'
OUTPUT_PINS = {'cohort-report.json': 'c62f2792a56a7f5bf683dcdad66f97171c964e4db7f53f7968a11860bc70588c',
 'index.json': 'bc8df0e0cc44190c7b4f7c22aa1aa59f36c46ca69ce6a62d645beb7a1341a2f8',
 'library-report.json': '997377419e285494901dd22e0e4b6a62ab59119b5a94c655188164dd7914a623',
 'research-pool-allocation.json': '02e9a31bb2726494a34102114d90870259931601019884e67eb7998d2001cb74'}
STAGE_KEY = 'entertainment_append_only_state'
SOURCE_ID = 'KP-20261111-ENTERTAINMENT-CLIPBOARD'
INTENT = 'EXPLICIT_GAMEPLAY_OR_DIGITAL_GAME_RESEARCH'
LIMITS = ('human_review_verified', 'exclusion_approval_granted', 'live_binding_verified',
          'production_authorized', 'google_platform_validation_performed')
RESOLVED = {59, 108, 302, 335, 385, 386, 388, 392, 395}
RAW_SHA256 = '3c2c8b015097200e3648f2f9d04c467ec6d447d4ea187d5cabd4be030bedb3ac'
CANONICAL_SHA256 = 'ceb01d1cc6c052279eabce3cdb8d3fa36122c2e7827d53939b8f2a40357d3244'


def implementation_binding(root):
    for relative, pin in CAPTURE_CODE_PINS.items():
        raw = (Path(root)/relative).read_bytes()
        first.need(len(raw) <= 1024*1024 and hashlib.sha256(raw).hexdigest() == pin,
                   'ENTERTAINMENT_CAPTURE_CODE_CHANGED')
    return {'audit_and_compatibility': prior.implementation_binding(root),
            'capture_code_sha256': dict(CAPTURE_CODE_PINS)}


def _ordinal_map(rows, field):
    first.need(type(rows) is list and len(rows) == 518 and
        [r.get('ordinal') for r in rows] == list(range(1, 519)) and
        all(type(r.get('ordinal')) is int and r.get(field) in {'PROPOSE_EXACT', 'HOLD'} for r in rows),
        'ENTERTAINMENT_REVIEW_COVERAGE_CHANGED')
    return {r['ordinal']: r for r in rows}


def merged_selection(original, independent, delta, lexical):
    """Derive all decisions from immutable reviews, not a dated membership report."""
    initial = _ordinal_map(original['assessments'], 'disposition')
    peer = _ordinal_map(independent['assessments'], 'decision')
    old_holds = {i for i, r in initial.items() if r['disposition'] == 'HOLD'}
    first.need(len(old_holds) == 200 and all(peer[i]['decision'] == 'HOLD' for i in old_holds) and
        all(peer[i]['original_disposition'] == initial[i]['disposition'] and
            peer[i]['original_reason_code'] == initial[i]['reason_code'] for i in initial),
        'ENTERTAINMENT_ORIGINAL_HOLD_CHANGED')
    proposed = {i for i, r in peer.items() if r['decision'] == 'PROPOSE_EXACT'}
    extra_holds = set(initial)-old_holds-proposed
    first.need(len(proposed) == 294 and len(extra_holds) == 24 and
        delta['base_review_file'] == 'review.json' and
        delta['base_review_sha256'] == SOURCE_PINS[SECOND+'/review.json'],
        'ENTERTAINMENT_INDEPENDENT_PARTITION_CHANGED')
    for key, input_key in (('equal_token_bag_group_reviews', 'equal_token_bag_groups'),
                           ('closed_string_alias_reviews', 'closed_string_alias_groups')):
        reviews, groups = independent[key], lexical[input_key]
        first.need(len(reviews) == len(groups), 'ENTERTAINMENT_VARIANT_COVERAGE_CHANGED')
        for assessed, group in zip(reviews, groups):
            members = group['ordinals']
            first.need(assessed['group'] == group['group'] and assessed['ordinals'] == members and
                assessed['conditional_proposals'] == [i for i in members if i in proposed] and
                assessed['held'] == [i for i in members if i not in proposed] and
                type(assessed['rationale']) is str and assessed['rationale'].strip(),
                'ENTERTAINMENT_VARIANT_PARTITION_CHANGED')
    resolutions = delta['resolutions']
    first.need(type(resolutions) is list and len(resolutions) == 24 and
        all(type(r.get('ordinal')) is int for r in resolutions) and
        {r['ordinal'] for r in resolutions} == extra_holds and
        all(r.get('decision') in {'PROPOSE_EXACT', 'HOLD'} and
            type(r.get('rationale')) is str and r['rationale'].strip() for r in resolutions),
        'ENTERTAINMENT_DELTA_COVERAGE_CHANGED')
    cleared = {r['ordinal'] for r in resolutions if r['decision'] == 'PROPOSE_EXACT'}
    first.need(cleared == RESOLVED and not cleared & old_holds,
               'ENTERTAINMENT_DELTA_AUTHORITY_CHANGED')
    selected = sorted(proposed | cleared)
    held = sorted(set(initial)-set(selected))
    first.need(len(selected) == 303 and len(held) == 215 and old_holds <= set(held),
               'ENTERTAINMENT_FINAL_PARTITION_CHANGED')
    return selected, held


def load_sources(root):
    implementation = implementation_binding(root)
    docs = {p: first.pinned(root, p, pin) for p, pin in SOURCE_PINS.items()}
    # Use explicit static paths; the independent review's legacy source_directory
    # is historical working context and is never a lookup authority.
    verifier = runpy.run_path(str(Path(root)/CAPTURE/'verify_capture.py'))
    first.need(verifier['verify']()['passed'] is True, 'ENTERTAINMENT_CAPTURE_NOT_VERIFIED')
    projection, capture = docs[CAPTURE+'/keywords.json'], docs[CAPTURE+'/capture.json']
    original, lexical = docs[CAPTURE+'/review.json'], docs[CAPTURE+'/lexical.json']
    independent, delta = docs[SECOND+'/review.json'], docs[SECOND+'/resolution-evidence.json']
    rows = {r['ordinal']: r for r in projection['records']}
    first.need(len(rows) == 518 and list(rows) == list(range(1, 519)) and
        projection['source_raw_sha256'] == capture['source_raw_sha256'] ==
        independent['source_raw_sha256'] == delta['source_raw_sha256'] == RAW_SHA256 and
        projection['canonical_lf_sha256'] == independent['canonical_lf_sha256'] == CANONICAL_SHA256 and
        capture['source_id'] == SOURCE_ID and capture['source_kind'] == 'provider_ui_clipboard_keywords_only' and
        capture['metrics_status'] == 'NOT_CAPTURED_UNKNOWN' and capture['is_csv_export'] is False and
        capture['observed_served_queries'] is False, 'ENTERTAINMENT_CAPTURE_IDENTITY_CHANGED')
    first.need(independent['source_file_sha256'] ==
        {name: SOURCE_PINS[CAPTURE+'/'+name] for name in ('capture.json','keywords.json','review.json','lexical.json')} and
        independent['projection_sha256'] == delta['projection_sha256'] == SOURCE_PINS[CAPTURE+'/keywords.json'] and
        independent['requirements']['path'] == first.MASTER and
        independent['requirements']['sha256'] == first.PINS[first.MASTER],
        'ENTERTAINMENT_REVIEW_SOURCE_CHANGED')
    first.pinned(root, first.MASTER, first.PINS[first.MASTER])
    selected, held = merged_selection(original, independent, delta, lexical)
    periods = [i for i, r in rows.items() if '.' in r['keyword']]
    first.need(len(periods) == 17 and set(periods) <= set(held) and
        independent['period_observations']['ordinals'] == periods,
        'ENTERTAINMENT_PERIOD_HOLD_CHANGED')
    first.need(all(capture[k] == 0 for k in ('master_contribution','approved_contribution','deployed_contribution')) and
        all(independent['authority'][k] is False and delta['authority'][k] is False for k in
            ('admission_authorized','human_approval_verified','production_changed')),
        'ENTERTAINMENT_SOURCE_AUTHORITY_CHANGED')
    first.need(capture['capture_date_dubai'] <= independent['review_date_dubai'] <= delta['review_date_dubai'],
               'ENTERTAINMENT_SOURCE_CHRONOLOGY_CHANGED')
    return {'rows': rows, 'selected': selected, 'held': held, 'capture': capture,
        'independent': independent, 'delta': delta, 'lexical': lexical,
        'context': first.pinned(root, first.FOLDER+'/service-context.json', first.CONTEXT_PIN),
        'registry': first.pinned(root, first.REGISTRY, first.PINS[first.REGISTRY]),
        'implementation': implementation}


def review_subject(review, material):
    return stage.digest({'review': {k:v for k,v in review.items() if k != 'subject_sha256'},
        'context': material['context'], 'registry': material['registry'],
        'source_pins': SOURCE_PINS, 'implementation': material['implementation'],
        'base_sha256': BASE_SHA256})


def make_review(root=first.ROOT, when=None):
    """Return complete review for root to inspect, write and explicitly pin."""
    when = first.dubai_date() if when is None else when
    material = load_sources(root)
    review = {'version': 1, 'scope': 'AI_REVIEWED_PLANNER_CLIPBOARD_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'reviewer': first.REVIEWER, 'reviewer_kind': 'CODEX_AI_NOT_HUMAN',
        'reviewed_on': when.isoformat(), 'valid_until': (when+timedelta(days=30)).isoformat(),
        'validity_basis': VALIDITY, 'campaign_key': first.CAMPAIGN, 'landing_page_id': 'BSRE-LP0301',
        'selected_ordinals': material['selected'], 'held_ordinals': material['held'],
        'source_pins': dict(SOURCE_PINS), 'implementation': material['implementation'],
        'base_sha256': BASE_SHA256,
        'source_identity_limits': 'Actual Keyword Planner UI clipboard keywords only; no CSV, captured metrics, served queries, demand or platform availability claim.',
        'semantic_rationale': 'Independent full-literal and variant review plus an explicit nine-ordinal source-bound delta; preserve all original 200 and 15 additional holds. Only incompatible game/digital-game intent is proposed for narrow rental planning research.',
        'variant_review': {'ordered_token_patterns_unique': True, 'equal_token_groups_reviewed': 87,
            'closed_alias_groups_reviewed': 7, 'google_equivalence_verified': False,
            'counts_distinct_concepts': False, 'all_original_semantic_holds_retained': True},
        **{key: False for key in LIMITS}}
    review['subject_sha256'] = review_subject(review, material)
    validate_review(review, material, when)
    return review


def validate_review(review, material, when):
    required = {'version','scope','reviewer','reviewer_kind','reviewed_on','valid_until','validity_basis',
        'campaign_key','landing_page_id','selected_ordinals','held_ordinals','source_pins',
        'implementation','base_sha256','source_identity_limits','semantic_rationale','variant_review',
        'subject_sha256'} | set(LIMITS)
    first.need(type(review) is dict and set(review) == required and type(review['version']) is int and
        review['version'] == 1 and review['scope'] == 'AI_REVIEWED_PLANNER_CLIPBOARD_RESEARCH_NOT_EXCLUSION_APPROVAL' and
        review['reviewer'] == first.REVIEWER and review['reviewer_kind'] == 'CODEX_AI_NOT_HUMAN' and
        all(review[key] is False for key in LIMITS), 'ENTERTAINMENT_REVIEW_AUTHORITY')
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
        'ENTERTAINMENT_SCOPE_CHANGED')
    first.need(review['selected_ordinals'] == material['selected'] and review['held_ordinals'] == material['held'] and
        all(type(i) is int for i in review['selected_ordinals']+review['held_ordinals']) and
        review['source_pins'] == SOURCE_PINS and review['implementation'] == material['implementation'] and
        review['base_sha256'] == BASE_SHA256 and review['variant_review'] == {
            'ordered_token_patterns_unique': True, 'equal_token_groups_reviewed': 87,
            'closed_alias_groups_reviewed': 7, 'google_equivalence_verified': False,
            'counts_distinct_concepts': False, 'all_original_semantic_holds_retained': True} and
        all(type(review[k]) is str and review[k].strip() for k in ('semantic_rationale','source_identity_limits')),
        'ENTERTAINMENT_REVIEW_BINDINGS_CHANGED')
    start, end = date.fromisoformat(review['reviewed_on']), date.fromisoformat(review['valid_until'])
    first.need(start.isoformat() == review['reviewed_on'] and end.isoformat() == review['valid_until'] and
        start <= when <= end and end-start == timedelta(days=30) and
        material['delta']['review_date_dubai'] <= review['reviewed_on'] and
        context['observed_date_dubai'] <= review['reviewed_on'] and review['validity_basis'] == VALIDITY,
        'ENTERTAINMENT_REVIEW_DATES')
    first.need(review['subject_sha256'] == review_subject(review, material), 'ENTERTAINMENT_REVIEW_SUBJECT_CHANGED')


def load_reviewed(root, when):
    material = load_sources(root)
    first.need(type(REVIEW_PIN) is str and len(REVIEW_PIN) == 64, 'ENTERTAINMENT_REVIEW_UNREGISTERED')
    review = first.pinned(root, FOLDER+'/review.json', REVIEW_PIN)
    validate_review(review, material, when)
    return dict(material, review=review)


def verify_base(base, material):
    first.need(stage.digest(base) == BASE_SHA256 and
        tuple(len(base[k]) for k in ('records','archived_records','protected_queries','sources',
                                     'campaigns','campaign_context')) == (10652,18,16168,22,360,1) and
        sum(len(r['provenance_occurrences']) for r in base['records']) == 10858 and
        base['campaigns'] == material['registry'], 'ENTERTAINMENT_PRIOR_BASE_CHANGED')
    _verify_membership(base, material)


def _verify_membership(base, material):
    """Fresh comparisons over supplied rows; never read the dated diagnostic."""
    prior_texts = {ka.normalize(r['original_text']) for r in base['records']+base['archived_records']}
    prior_texts.update(ka.normalize(r['text']) for r in base['protected_queries'])
    prior_bags = {tuple(sorted(ka.tokens(text))) for text in prior_texts}
    ordered = []
    for ordinal, row in material['rows'].items():
        text = row['keyword']; key = ka.normalize(text); words = tuple(ka.tokens(text))
        first.need(key not in prior_texts and tuple(sorted(words)) not in prior_bags,
                   'ENTERTAINMENT_FRESH_MEMBERSHIP_CHANGED')
        ordered.append(words)
        if ordinal in material['selected']:
            first.need(not compatibility.profile_text(text)['original']['reason_codes'] and '.' not in text,
                       'ENTERTAINMENT_TEXT_COMPATIBILITY_HOLD')
    first.need(len({ka.normalize(r['keyword']) for r in material['rows'].values()}) == 518 and
        len(set(ordered)) == len(ordered) == 518, 'ENTERTAINMENT_ORDERED_VARIANT_COLLISION')


def build_cohort(base, material):
    review = material['review']; records = []
    for ordinal in material['selected']:
        text = material['rows'][ordinal]['keyword']; key = ka.normalize(text)
        occurrence = {'batch': SOURCE_ID, 'source_ordinal': ordinal,
            'file': CAPTURE+'/keywords.json', 'sha256': SOURCE_PINS[CAPTURE+'/keywords.json'],
            'source_sha256': RAW_SHA256, 'canonical_lf_sha256': CANONICAL_SHA256,
            'capture_kind': 'provider_ui_clipboard_keywords_only',
            'review_file': FOLDER+'/review.json', 'review_sha256': REVIEW_PIN,
            'independent_review_file': SECOND+'/review.json',
            'independent_review_sha256': SOURCE_PINS[SECOND+'/review.json'],
            'resolution_evidence_file': SECOND+'/resolution-evidence.json',
            'resolution_evidence_sha256': SOURCE_PINS[SECOND+'/resolution-evidence.json']}
        adapted = {'normalized_text': key, 'disposition': 'NEGATIVE_EXACT_REVIEW', 'original_forms': [text],
            'assessment': {'intent': INTENT, 'negative_scope_proposal':
                {'type':'CAMPAIGN','campaign_keys':[],'approved':False,'match_type':'EXACT'}}}
        record = first.make_record(adapted, review, [occurrence], source_id=SOURCE_ID,
            source_reference=CAPTURE+'/keywords.json#ordinal='+str(ordinal), review_folder=FOLDER,
            allowed_intents={INTENT})
        record['evidence_ref'] = FOLDER+'/review.json#ordinal='+str(ordinal)
        records.append(record)
    records.sort(key=lambda row: row['normalized_text'])
    source = {'source_id': SOURCE_ID, 'kind': 'official_reference', 'approved_for_research': True,
        'evidence_ref': CAPTURE+'/capture.json', 'observed_on': material['capture']['capture_date_dubai'],
        'valid_until': review['valid_until'], 'capture_kind': 'provider_ui_clipboard_keywords_only',
        'research_use_basis': 'OWNER_AUTHORIZED_AUTHENTIC_PLANNER_UI_CLIPBOARD_AND_PINNED_AI_REVIEW',
        'metrics_captured': False, 'served_query_or_current_performance_claimed': False}
    protections = []
    for ordinal in material['held']:
        key = ka.normalize(material['rows'][ordinal]['keyword'])
        protections.append({'query_id':'BSRE-Q-'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:24],
            'text':key,'campaign_keys':[first.CAMPAIGN],'services':['residential_rental'],'must_serve':True,
            'evidence_ref':FOLDER+'/review.json#ordinal='+str(ordinal),
            'reviewed_on':review['reviewed_on'],'valid_until':review['valid_until']})
    return {'records':records,'sources':[source],'protected_queries':[],
        'campaigns':base['campaigns'],'campaign_context':base['campaign_context']}, protections


def extend(base, root, when):
    material = load_reviewed(root, when)
    verify_base(base, material)
    cohort, protections = build_cohort(base, material)
    return stage.extend(base, cohort, protections, expected_base_sha256=BASE_SHA256, stage_key=STAGE_KEY)


def _outputs(inputs, material, root, when):
    result = stage.checked_audit(inputs, when)
    state = inputs[STAGE_KEY]; n = state['retained_records']; new = inputs['records'][n:]
    index = {'version':1,'scope':'APPEND_ONLY_PLANNER_CLIPBOARD_RESEARCH_NOT_EXCLUSION_APPROVAL',
        'previous_index':{'file':prior.FOLDER+'/index.json','sha256':prior.OUTPUT_PINS['index.json']},
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},'source_pins':dict(SOURCE_PINS),
        'implementation':material['implementation'],'base_state':state,
        'records_sha256':stage.digest(inputs['records']),'archived_sha256':stage.digest(inputs['archived_records']),
        'protected_sha256':stage.digest(inputs['protected_queries']),'sources_sha256':stage.digest(inputs['sources']),
        'additional_records_sha256':stage.digest(new),'complete_inputs_sha256':stage.digest(inputs),
        'additional_eligible_keyword_ids':[r['keyword_id'] for r in new],
        'additional_protected_query_ids':[r['query_id'] for r in inputs['protected_queries'][state['retained_protections']:]],
        'historical_records_rewritten':False,'exclusion_approval_granted':False,'deployment_authorized':False}
    cohort = {'scope':'AI_REVIEWED_PLANNER_UI_CLIPBOARD_KEYWORDS_NOT_SERVED_QUERIES_OR_METRICS',
        'source_occurrences':518,'selected_new_rows':len(new),'held_source_occurrences':len(material['held']),
        'retained_new_occurrences':sum(len(r['provenance_occurrences']) for r in new),
        'record_bodies_sha256':stage.digest(new),'source_pins':dict(SOURCE_PINS),
        'review':{'file':FOLDER+'/review.json','sha256':REVIEW_PIN},
        'google_equivalence_verified':False,'counts_distinct_concepts':False,
        'metrics_captured':False,'search_demand_verified':False,**{k:False for k in LIMITS}}
    summary = {'scope':'CURRENT_RESEARCH_AFTER_ENTERTAINMENT_CLIPBOARD_APPEND_ONLY_REVIEW',
        **{k:result[k] for k in ('as_of','input_rows','distinct_nonblank_phrases','reviewed_eligible_rows',
            'excluded_rows','approved_exclusion_rows','target','deficit','exact_target_pass','structural_pass',
            'deployment_export_allowed','production_writes_available','positive_library_coverage_verified',
            'protected_queries_indexed')},'computed_conflicts':len(result['protected_conflicts']),
        'prior_rows':n,'new_rows':len(new),'archived_original_rows':len(inputs['archived_records']),
        'source_occurrences_retained_in_current_records':sum(len(r['provenance_occurrences']) for r in inputs['records']),
        'new_proposal_holds':len(material['held']),'historical_records_rewritten':False,
        'human_review_verified':False,'live_campaign_mapping_verified':False,'release_authorized':False,
        'text_compatibility_is_local_screen_not_platform_acceptance':True}
    previous_pin = prior.OUTPUT_PINS['research-pool-allocation.json']
    previous = first.pinned(root, prior.FOLDER+'/research-pool-allocation.json', previous_pin)
    first.need(previous['total_target'] == 14000 and previous['total_admitted'] == n and
        sum(previous['admitted'].values()) == n and sum(previous['targets'].values()) == 14000,
        'ENTERTAINMENT_ALLOCATION_BASE_CHANGED')
    admitted = dict(previous['admitted']); admitted['MEDIA'] += len(new)
    remaining = {k:previous['targets'][k]-v for k,v in admitted.items()}
    first.need(all(type(v) is int and v >= 0 for v in remaining.values()) and
        sum(admitted.values()) == len(inputs['records']), 'ENTERTAINMENT_ALLOCATION_COUNTS')
    allocation = {'version':1,'scope':'RESEARCH_PLAN_ONLY_NOT_BUDGET_OR_EXCLUSION_APPROVAL',
        'requirements_ref':first.MASTER,'previous_allocation_ref':prior.FOLDER+'/research-pool-allocation.json',
        'previous_allocation_sha256':previous_pin,'targets':previous['targets'],'before':previous['targets'],
        'target_transfer':None,'held_deduction':{},'new_rows':{'MEDIA':len(new)},'admitted':admitted,
        'remaining':remaining,'total_target':14000,'total_admitted':sum(admitted.values()),
        'total_remaining':sum(remaining.values()),
        'basis':'Preserve all prior bodies and pool targets; append only genuine source-bound complete game/digital-game literals.',
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
    first.need(first.canonical(inputs) == first.canonical(expected), 'ENTERTAINMENT_DERIVED_BODIES_CHANGED')
    documents, summary = _outputs(inputs, load_reviewed(root, when), root, when)
    stage.check_documents(root, FOLDER, OUTPUT_PINS, documents)
    return dict(summary,passed=True,index_verified=True,current_index_file=FOLDER+'/index.json',release_held=True)
