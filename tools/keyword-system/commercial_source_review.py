"""Complete commercial-source wording review and bounded comparisons; no admission."""
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path

import buyer_source_reconciliation as buyer

ROOT = Path(__file__).resolve().parents[2]
FOLDER = 'docs/audit/keyword-commercial-property-planner-2026-11-13'
SOURCE_PIN = '083d3df74e8b75f2443f9acc096fe98a70faac08cf652d92ba1e1afeaa7863a0'
VERIFIER_PIN = '46d0892179f2b83870b91e9af558ad8d54c70c82c8b2d42e22b38e7efbea0802'
MANUAL_PIN = '5b800d11104148b0a83a9a21cb17eda98d50c96e018180b783c890fe8e348113'
REPORT_PIN = '728212e3b0eddf562fc8b5ee267e62f01921bf9714b01fad62c42ae0ea76a265'
DEPENDENCIES = {'tools/keyword-system/buyer_source_reconciliation.py':
                '21b8f4af1107a28c0851e8456c5f7a264a27bad466e9619e306736b612eafdd8'}


def need(value, code):
    if not value:
        raise ValueError(code)


def bound(relative, pin):
    blob = buyer.read_bound(ROOT / relative)
    need(hashlib.sha256(blob).hexdigest() == pin, 'INPUT_PIN_CHANGED')
    return blob


def load_material():
    for path, pin in DEPENDENCIES.items():
        bound(path, pin)
    path = ROOT / FOLDER / 'verify_capture.py'
    bound(FOLDER + '/verify_capture.py', VERIFIER_PIN)
    spec = importlib.util.spec_from_file_location('commercial_capture_fresh', path)
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    receipt = verifier.verify()
    batch = buyer.ka.parse_json_bytes(bound(FOLDER + '/commercial-property.json', SOURCE_PIN))
    verifier.validate_batch(batch)
    manual = buyer.ka.parse_json_bytes(bound(FOLDER + '/manual-classifications.json', MANUAL_PIN))
    need(manual['source_public_sha256'] == SOURCE_PIN and manual['source_occurrences'] == 705 and
         manual['all_complete_literals_read'] is True and manual['cohorts'] == [[1,240],[241,480],[481,705]] and
         manual['reviewer'] == 'Lead AI — preliminary wording only, not independent human approval' and
         buyer.sd._exact({k: manual[k] for k in ('admission_authorized','independent_approval','negative_proposals_created','deployment_authorized')},
                        {'admission_authorized':False,'independent_approval':False,'negative_proposals_created':0,'deployment_authorized':False}),
         'MANUAL_SCOPE_OR_AUTHORITY_CHANGED')
    old = buyer.load_inputs()
    return batch, manual, receipt, old


def assemble(batch, manual, receipt, old):
    previous = buyer._compute(*old)
    external = list(previous['external_literal_references']) + [
        {'reference':'buyer-property:ordinal:' + str(i), 'population':'prior_full_buyer_capture',
         'source_ordinal':i, 'original_literal':r['values']['Keyword'],
         'complete_public_values_sha256':buyer.digest(r['values'])}
        for i,r in enumerate(old[0]['source_projection']['records'],1)]
    indexes = {method:defaultdict(list) for method in buyer.METHODS}
    for row in external:
        for method, key in zip(buyer.METHODS, buyer.attention_keys(row['original_literal'])):
            indexes[method][key].append(row['reference'])
    source = batch['source_projection']['records']
    peer_indexes = {method:defaultdict(list) for method in buyer.METHODS}
    row_keys = [buyer.attention_keys(r['values']['Keyword']) for r in source]
    for i, keys in enumerate(row_keys,1):
        for method, key in zip(buyer.METHODS, keys): peer_indexes[method][key].append(i)
    labels = {}; categories = manual['categories']
    for code, ordinals in manual['explicit_exception_ordinals'].items():
        need(code in categories, 'UNKNOWN_MANUAL_CATEGORY')
        for n in ordinals:
            need(type(n) is int and 1 <= n <= len(source) and n not in labels, 'MANUAL_ORDINAL_COLLISION')
            labels[n] = code
    seeds = {buyer.ka.normalize(s) for s in batch['input_seeds']}
    rows = []; exact_rows = []; attention_rows = []
    for i,(row, keys) in enumerate(zip(source,row_keys),1):
        code = labels.get(i,manual['default_for_remaining_read_literals'])
        decision = categories[code]
        joins = [{'method':method,'external_references':sorted(indexes[method].get(key,())),
                  'source_peer_ordinals':[n for n in peer_indexes[method][key] if n != i]}
                 for method,key in zip(buyer.METHODS,keys)]
        if joins[0]['external_references']: exact_rows.append(i)
        if any(j['external_references'] or j['source_peer_ordinals'] for j in joins[1:]): attention_rows.append(i)
        rows.append({'source_ordinal':i,'source_line':row['source_line'],'original_literal':row['values']['Keyword'],
                     'complete_public_values_sha256':buyer.digest(row['values']),
                     'exact_input_seed_wording':buyer.ka.normalize(row['values']['Keyword']) in seeds,
                     'decision_code':code, 'decision':decision['decision'],'reason':decision['reason'],
                     'source_kind':'RESEARCH_HYPOTHESIS','genuine_query_observed':False,
                     'asset_family':None,'primary_campaign':None,'ad_group':None,'native_page':None,
                     'actual_volume':None,'actual_cpc':None,'admitted':False,'independent_approval':False,
                     'canonical_merge_approved':False,'joins':joins})
    counts = Counter(r['decision_code'] for r in rows)
    return {'schema_version':1,'scope':'COMPLETE_PRELIMINARY_COMMERCIAL_WORDING_REVIEW_NOT_ADMISSION',
            'source_public_sha256':SOURCE_PIN,'manual_sha256':MANUAL_PIN,
            'source_raw_sha256':receipt['source_sha256'],
            'reviewer':manual['reviewer'],'reviewed_on_dubai':manual['reviewed_on_dubai'],
            'counts':{'complete_literals_read':len(rows),'source_public_cells':21*len(rows),
                      'conditional_lease_hypotheses':counts['L'],'conditional_purchase_hypotheses':counts['P'],
                      'other_review_holds':len(rows)-counts['L']-counts['P'],
                      'decision_codes':dict(sorted(counts.items())),
                      'comparison_external_forms':len(external),'comparison_prior_full_buyer_rows':3195,
                      'historical_candidates':len(old[1]['candidates']),'historical_placements':len(old[1]['placements']),
                      'prior_buyer_rows':len(old[2]['rows']), 'exact_external_context_rows':len(exact_rows),
                      'lexical_attention_rows':len(attention_rows),'confirmed_novel_canonicals':None,
                      'positive_admissions_added':0,'negative_proposals_added':0,'approvals_added':0,'deployments_added':0},
            'comparison_methods':list(buyer.METHODS),'external_literal_references':external,
            'exact_external_context_ordinals':exact_rows,'lexical_attention_ordinals':attention_rows,
            'records':rows,'controls':{'all_source_occurrences_retained':True,'all_complete_literals_preliminarily_reviewed':True,
                                     'semantic_canonicalization_complete':False,'five_subject_bound_reviews_complete':False,
                                     'current_exclusion_scope_verified':False,'business_evidence_verified':False,
                                     'actual_campaign_or_page_mapping_verified':False,'independent_review_complete':False,
                                     'admission_authorized':False,'deployment_authorized':False},
            'limits':'These named source comparisons are not global membership, semantic or Google-equivalence checks. Retain every variant and historical metric. Actual service/inventory/rights, five subject-bound reviews, campaign/page and applicable exclusions must be verified before admission. Other property/operator/retail holds are retained, not discarded or turned into negatives.'}


def build_report():
    return assemble(*load_material())


def validate_report(report):
    need(buyer.sd._exact(report,build_report()), 'COMMERCIAL_REVIEW_DIFFERS_FROM_FRESH_INPUTS')


def verify_saved():
    report = buyer.ka.parse_json_bytes(bound(FOLDER+'/review.json',REPORT_PIN))
    validate_report(report)
    return {'passed':True,'counts':report['counts'],'deployment_authorized':False}


if __name__ == '__main__':
    try:
        print(json.dumps(verify_saved(),sort_keys=True))
    except Exception as error:
        print(json.dumps({'passed':False,'code':'COMMERCIAL_SOURCE_REVIEW_HELD','error_type':type(error).__name__,'deployment_authorized':False}))
        raise SystemExit(1)
