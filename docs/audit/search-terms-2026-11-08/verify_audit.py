"""Public count-audit integrity; private reproduction only when source supplied."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import parse_json_bytes,normalize
from search_terms_intake import parse_search_terms,FOOTERS
AUDIT_PIN='a470294a9ce19315d3bd148843cc5bc6e104a0a91a3eb6b6eecbda42e6bc12ed'
EXPECTED={'version': 1, 'scope': 'COUNT_ONLY_PRIVATE_HISTORICAL_QUERY_AVAILABILITY_NOT_PERFORMANCE_OR_ADMISSION', 'account_id': '573-038-4686', 'observed_date_dubai': '2026-11-08', 'report_window': {'start': '2026-10-01', 'end': '2026-10-31'}, 'ui_scope': {'campaigns': 'ALL', 'campaign_status': 'ALL', 'ad_group_status': 'ALL', 'table_filters': 'NONE'}, 'source': {'sha256': '2b3a1cc6811e1a285cf7bd09a460aca8bb0ce0175446d016ce7d6494b9ffe305', 'bytes': 675640, 'private_native_evidence_sha256': '62e9eddbe36f3b2707e3ea1302de448a33543cc32a50836eea3df7a848229984', 'private_raw_committed': False}, 'resource_ids_available': False, 'source_visibility': {'disclosed_terms_only': True, 'all_searches_or_history_proven': False, 'other_search_terms_footer_present': True, 'undisclosed_term_count': 'UNKNOWN'}, 'idea_manifest_pins': {'docs/audit/keyword-discovery-2026-11-08/capture.json': '4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268', 'docs/audit/keyword-discovery-supply-2026-11-08/capture.json': '279b71e166ecbb3806af143549a99f559ac7846ffa9396497f266b871a2012a7'}, 'controls': {'public_disclosure_authorized': False, 'deployment_authorized': False, 'negative_authorized': False, 'qualification_authorized': False, 'all_records_require_manual_disclosure_review': True, 'unflagged_records_are_not_verified_safe': True, 'performance_financial_conversion_cells_retained': False}, 'master_contribution': {'reviewed_positive': 0, 'reviewed_negative': 0, 'approved_positive': 0, 'approved_negative': 0, 'deployed': 0}, 'classification_inherited': False, 'private_records_committed': False}
COUNT_FIELDS=['blank_ad_group_rows', 'distinct_campaign_ad_group_label_pairs_including_blank', 'distinct_campaign_labels', 'distinct_nonblank_ad_group_labels', 'distinct_nonblank_campaign_ad_group_label_pairs', 'distinct_normalized_search_terms', 'distinct_raw_search_terms', 'duplicate_query_placement_rows', 'footer_rows', 'manual_disclosure_review_required_records', 'privacy_flagged_records', 'query_placement_rows', 'repeated_normalized_query_occurrences', 'repeated_query_campaign_ad_group_context_rows', 'repeated_raw_query_occurrences', 'source_rows']
OVERLAP_FIELDS=['combined_lexical_union', 'idea_only', 'intersection', 'planner_idea_unique_normalized', 'reported_only', 'reported_unique_normalized']

def need(ok,code):
    if not ok:raise ValueError(code)

def verify(source=None):
    blob=(HERE/'audit.json').read_bytes();need(hashlib.sha256(blob).hexdigest()==AUDIT_PIN,'PUBLIC_COUNT_BYTES_CHANGED')
    audit=parse_json_bytes(blob)
    need(set(audit)==set(EXPECTED)|{'summary','lexical_overlap_counts'},'AUDIT_FIELDS')
    need({k:v for k,v in audit.items() if k in EXPECTED}==EXPECTED,'AUDIT_CONTEXT_OR_AUTHORITY')
    summary=audit['summary'];need(isinstance(summary,dict) and set(summary)==set(COUNT_FIELDS)|{'footer_counts'},'COUNT_FIELDS')
    need(all(type(summary[k]) is int and summary[k]>=0 for k in COUNT_FIELDS),'COUNT_TYPES')
    footer=summary['footer_counts'];need(isinstance(footer,dict) and set(footer)==set(FOOTERS) and all(type(v) is int and v>=0 for v in footer.values()),'FOOTER_COUNTS')
    n=summary['query_placement_rows'];need(summary['source_rows']==n+summary['footer_rows'] and sum(footer.values())==summary['footer_rows'],'ROW_ACCOUNTING')
    need(summary['manual_disclosure_review_required_records']==n and summary['privacy_flagged_records']<=n,'DISCLOSURE_REVIEW_REQUIRED')
    need(summary['distinct_normalized_search_terms']<=summary['distinct_raw_search_terms']<=n,'QUERY_IDENTITY_COUNTS')
    need(summary['repeated_raw_query_occurrences']==n-summary['distinct_raw_search_terms'] and summary['repeated_normalized_query_occurrences']==n-summary['distinct_normalized_search_terms'],'REPEAT_COUNTS')
    need(summary['distinct_nonblank_campaign_ad_group_label_pairs']<=summary['distinct_campaign_ad_group_label_pairs_including_blank']<=n,'LABEL_CONTEXT_COUNTS')
    overlap=audit['lexical_overlap_counts'];need(isinstance(overlap,dict) and set(overlap)==set(OVERLAP_FIELDS) and all(type(v) is int and v>=0 for v in overlap.values()),'OVERLAP_COUNTS')
    need(overlap['reported_unique_normalized']==summary['distinct_normalized_search_terms'],'OVERLAP_SOURCE_COUNT')
    need(overlap['reported_only']+overlap['intersection']==overlap['reported_unique_normalized'] and overlap['idea_only']+overlap['intersection']==overlap['planner_idea_unique_normalized'] and overlap['reported_unique_normalized']+overlap['planner_idea_unique_normalized']-overlap['intersection']==overlap['combined_lexical_union'],'OVERLAP_ARITHMETIC')
    for relative,pin in audit['idea_manifest_pins'].items():need(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==pin,'IDEA_MANIFEST_CHANGED')
    if source is not None:
        private=parse_search_terms(source)
        need(private['source_sha256']==audit['source']['sha256'] and private['source_bytes']==audit['source']['bytes'],'PRIVATE_SOURCE_IDENTITY')
        need(private['summary']==summary and private['controls']==audit['controls'],'PRIVATE_COUNT_REPRODUCTION')
        terms={r['normalized_search_term'] for r in private['records']};ideas=set()
        for relative in audit['idea_manifest_pins']:
            manifest=ROOT/relative;index=parse_json_bytes(manifest.read_bytes())
            for item in index['source_files']:
                raw=(manifest.parent/item['file']).read_bytes();need(hashlib.sha256(raw).hexdigest()==item['sha256'],'IDEA_PROJECTION_CHANGED')
                batch=parse_json_bytes(raw);ideas.update(normalize(r['values']['Keyword']) for r in batch['source_projection']['records'])
        expected_overlap={'reported_unique_normalized':len(terms),'planner_idea_unique_normalized':len(ideas),'intersection':len(terms&ideas),'reported_only':len(terms-ideas),'idea_only':len(ideas-terms),'combined_lexical_union':len(terms|ideas)}
        need(overlap==expected_overlap,'PRIVATE_OVERLAP_REPRODUCTION')
    return {'passed':True,'scope':'PRIVATE_SOURCE_COUNT_REPRODUCTION' if source is not None else 'PUBLIC_COUNT_INTEGRITY_ONLY','reported_rows':n,'distinct_reported_terms':summary['distinct_normalized_search_terms'],'private_records_published':False,'disclosure_authorized':False,'negative_authorized':False,'qualification_authorized':False,'deployment_authorized':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source');args=parser.parse_args()
    try:print(json.dumps(verify(args.source)))
    except Exception:
        print(json.dumps({'passed':False,'scope':'COUNT_AUDIT_FAILED','disclosure_authorized':False,'deployment_authorized':False}));raise SystemExit(1)
