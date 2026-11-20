"""Source-bound owner-intent wording review; no admission or platform writer."""
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json

import commercial_source_review as commercial

buyer = commercial.buyer
ROOT = commercial.ROOT
FOLDER = 'docs/audit/keyword-owner-services-planner-2026-11-13'
SOURCE_PIN = '0c4ed2af3a80d3521267fc9ba683925499d4fcef9c20dea4b279110994317f75'
VERIFIER_PIN = '0ea8946de36a4c3a1ea0971868fa2e0dbe99f3760527baaac91743171c70a927'
MANUAL_PIN = '5c4e3105ec920634ce5a5436e9d39b7a3cecff2961d83d3423eb7703a1078ee6'
DEPENDENCIES = {'tools/keyword-system/commercial_source_review.py':
                '9e0586b6068f837e237516db30db7e8b4ba888d943a706f093d31b81523dbbc4'}
OWNER_CODES = ('SELLER_HYPOTHESIS', 'LANDLORD_HYPOTHESIS')
CONTROLS = {'all_source_occurrences_retained':True,
            'all_complete_literals_preliminarily_reviewed':True,
            'semantic_canonicalization_complete':False,
            'five_subject_bound_reviews_complete':False,
            'current_exclusion_scope_verified':False,
            'business_evidence_verified':False,
            'actual_campaign_or_page_mapping_verified':False,
            'independent_review_complete':False,
            'admission_authorized':False,'deployment_authorized':False}


def need(value, code):
    if not value:
        raise ValueError(code)


def bound(relative, pin):
    blob = buyer.read_bound(ROOT / relative)
    need(hashlib.sha256(blob).hexdigest() == pin, 'OWNER_INPUT_PIN_CHANGED')
    return blob


def load_material():
    """Fresh complete input reads; no process-global body/hash/verdict cache."""
    for path, pin in DEPENDENCIES.items():
        bound(path, pin)
    bound(FOLDER + '/verify_capture.py', VERIFIER_PIN)
    spec = importlib.util.spec_from_file_location('owner_capture_fresh', ROOT / FOLDER / 'verify_capture.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    receipt = verifier.verify()
    batch = buyer.ka.parse_json_bytes(bound(FOLDER + '/owner-services.json', SOURCE_PIN))
    verifier.validate_batch(batch)
    manual = buyer.ka.parse_json_bytes(bound(FOLDER + '/manual-classifications.json', MANUAL_PIN))
    need(manual['source_public_sha256'] == SOURCE_PIN and
         type(manual['source_occurrences']) is int and manual['source_occurrences'] == 147 and
         manual['all_complete_literals_read'] is True and manual['cohorts'] == [[1,147]] and
         manual['reviewer'] == 'Lead AI — preliminary wording only, not independent human approval' and
         buyer.sd._exact({k:manual[k] for k in ('admission_authorized','independent_approval',
                                              'negative_proposals_created','deployment_authorized')},
                        {'admission_authorized':False,'independent_approval':False,
                         'negative_proposals_created':0,'deployment_authorized':False}),
         'OWNER_MANUAL_SCOPE_OR_AUTHORITY')
    prior = commercial.load_material()
    return batch, manual, receipt, prior


def external_forms(prior):
    """All named prior forms participate; only matched context is reserialized."""
    old = prior[3]
    forms = []
    for topic, batch in (('buyer-property',old[0]),('commercial-property',prior[0])):
        for n, row in enumerate(batch['source_projection']['records'],1):
            forms.append({'reference':topic + ':ordinal:' + str(n),
                          'original_literal':row['values']['Keyword'],
                          'complete_public_values_sha256':buyer.digest(row['values'])})
    for candidate in old[1]['candidates']:
        for n, literal in enumerate(candidate['original_text_variants'],1):
            forms.append({'reference':candidate['candidate_id'] + ':variant:' + str(n),
                          'original_literal':literal,'placement_ids':candidate['placement_ids']})
    for row in old[2]['rows']:
        forms.append({'reference':'prior-buyer:ordinal:' + str(row['source_ordinal']),
                      'original_literal':row['cells'][1],
                      'complete_cells_sha256':buyer.digest(row['cells'])})
    need(len(forms) == len({r['reference'] for r in forms}) == 3947, 'OWNER_COMPARISON_POPULATION')
    return forms


def assemble(batch, manual, receipt, prior):
    source = batch['source_projection']['records']
    need(len(source) == 147, 'OWNER_SOURCE_POPULATION')
    categories, labels = manual['categories'], {}
    for code, category in categories.items():
        need(isinstance(code,str) and isinstance(category['reason'],str) and bool(category['reason']),
             'OWNER_MANUAL_CATEGORY')
        for n in category['ordinals']:
            need(type(n) is int and 1 <= n <= 147 and n not in labels, 'OWNER_MANUAL_PARTITION')
            labels[n] = code
    need(set(labels) == set(range(1,148)), 'OWNER_MANUAL_PARTITION')
    external = external_forms(prior)
    indexes = {method:defaultdict(list) for method in buyer.METHODS}
    for row in external:
        for method, key in zip(buyer.METHODS,buyer.attention_keys(row['original_literal'])):
            indexes[method][key].append(row['reference'])
    peer_indexes = {method:defaultdict(list) for method in buyer.METHODS}
    row_keys = [buyer.attention_keys(r['values']['Keyword']) for r in source]
    for n, keys in enumerate(row_keys,1):
        for method, key in zip(buyer.METHODS,keys):
            peer_indexes[method][key].append(n)
    seeds = set(batch['input_seeds'])
    rows, exact_rows, attention_rows, matched = [], [], [], set()
    for n, (row, keys) in enumerate(zip(source,row_keys),1):
        joins = [{'method':method,'external_references':sorted(indexes[method].get(key,())),
                  'source_peer_ordinals':[p for p in peer_indexes[method][key] if p != n]}
                 for method, key in zip(buyer.METHODS,keys)]
        for join in joins:
            matched.update(join['external_references'])
        if joins[0]['external_references']:
            exact_rows.append(n)
        if any(j['external_references'] or j['source_peer_ordinals'] for j in joins[1:]):
            attention_rows.append(n)
        code = labels[n]
        rows.append({'source_ordinal':n,'source_line':row['source_line'],
                     'original_literal':row['values']['Keyword'],
                     'complete_public_values_sha256':buyer.digest(row['values']),
                     'exact_input_seed_wording':row['values']['Keyword'] in seeds,
                     'decision_code':code,'reason':categories[code]['reason'],
                     'source_kind':'RESEARCH_HYPOTHESIS','genuine_query_observed':False,
                     'asset_family':None,'primary_campaign':None,'ad_group':None,'native_page':None,
                     'actual_volume':None,'actual_cpc':None,'admitted':False,'independent_approval':False,
                     'canonical_merge_approved':False,'joins':joins})
    counts = Counter(r['decision_code'] for r in rows)
    old = prior[3]
    inputs = [
        {'path':buyer.FOLDER+'/buyer-property.json','occurrences':3195,
         'source_raw_sha256':old[3]['source_sha256']},
        {'path':commercial.FOLDER+'/commercial-property.json','occurrences':705,
         'public_sha256':commercial.SOURCE_PIN,'source_raw_sha256':prior[2]['source_sha256']},
        {'path':buyer.historical.HISTORY,'candidate_records':len(old[1]['candidates']),
         'placements':len(old[1]['placements']),
         'public_sha256':hashlib.sha256(buyer.read_bound(ROOT / buyer.historical.HISTORY)).hexdigest()},
        {'path':buyer.PRIOR,'occurrences':6,'public_sha256':buyer.PRIOR_SHA256}]
    return {'schema_version':1,'scope':'COMPLETE_PRELIMINARY_OWNER_WORDING_REVIEW_NOT_ADMISSION',
            'source_public_sha256':SOURCE_PIN,'manual_sha256':MANUAL_PIN,
            'source_raw_sha256':receipt['source_sha256'],
            'reviewer':manual['reviewer'],'reviewed_on_dubai':manual['reviewed_on_dubai'],
            'comparison_input_populations':inputs,'comparison_methods':list(buyer.METHODS),
            'comparison_matched_contexts':[r for r in external if r['reference'] in matched],
            'counts':{'complete_literals_read':147,'source_public_cells':3087,
                      'conditional_seller_hypotheses':counts[OWNER_CODES[0]],
                      'conditional_landlord_hypotheses':counts[OWNER_CODES[1]],
                      'buyer_research_other_role':counts['BUYER_RESEARCH_OTHER_ROLE'],
                      'other_review_holds':147-sum(counts[c] for c in OWNER_CODES)-counts['BUYER_RESEARCH_OTHER_ROLE'],
                      'decision_codes':dict(sorted(counts.items())),
                      'comparison_external_forms':len(external),
                      'matched_contexts_serialized':len(matched),
                      'exact_external_context_rows':len(exact_rows),
                      'lexical_attention_rows':len(attention_rows),
                      'confirmed_novel_canonicals':None,'positive_admissions_added':0,
                      'negative_proposals_added':0,'approvals_added':0,'deployments_added':0},
            'exact_external_context_ordinals':exact_rows,'lexical_attention_ordinals':attention_rows,
            'records':rows,'controls':dict(CONTROLS),
            'limits':'All 3,947 named external forms and all 147 within-source peers participate. Only matched external contexts are reserialized; source manifests preserve the complete comparison populations. These are lexical attention checks, not global membership, semantic/Google equivalence, demand, actual service or authority. Preserve every original and its historical estimates. Both complete reviewed 14,000 libraries, genuine evidence, five subject-bound reviews, actual mappings and fresh applicable exclusions remain required. All holds are retained; none becomes an automatic negative.'}


def build_report():
    return assemble(*load_material())


def validate_report(report):
    need(buyer.sd._exact(report,build_report()), 'OWNER_REVIEW_DIFFERS_FROM_FRESH_INPUTS')


def verify_saved():
    report = buyer.ka.parse_json_bytes(buyer.read_bound(ROOT / FOLDER / 'review.json'))
    validate_report(report)
    return {'passed':True,'counts':report['counts'],'deployment_authorized':False}


if __name__ == '__main__':
    try:
        print(json.dumps(verify_saved(),sort_keys=True))
    except Exception as error:
        print(json.dumps({'passed':False,'code':'OWNER_SOURCE_REVIEW_HELD',
                          'error_type':type(error).__name__,'deployment_authorized':False}))
        raise SystemExit(1)
