"""Verify pinned public Discovery capture; optional private raw equality, no writes."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PINS={
  "buyers.json": "2c742c953164e44038032c828808769e4b4db3f5b713e689a7edee79df1dbf36",
  "tenants.json": "72f757844e324a6bc0c01e89e3bdb21559b1ad13b503210ca5f83f6c71a13b33",
  "owners.json": "d89d9ee30ab0b02d2525d6833af1d92a545b48157ce65e2dc6e4bffac376f681",
  "commercial.json": "0e0976a1dd40288917cdbac847ed4c2c553ab3a28bc7c9cf36c2f635fb63478f",
  "capture.json": "4217d078fa72c1b5244548fb0adba51106a5f1e26cdc0c335079216b306a9268"
}
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from keyword_audit import normalize, parse_json_bytes
from planner_discovery import parse_discovery, BASE_COLUMNS, EXCLUDED_COLUMNS, _monthly_columns

def need(ok,code):
    if not ok: raise ValueError(code)

def verify(sources=None):
    sources=sources or {}
    need(set(sources)<=set(('buyers','tenants','owners','commercial')),'UNKNOWN_BATCH')
    loaded={}
    for filename,expected in PINS.items():
        blob=(HERE/filename).read_bytes()
        need(hashlib.sha256(blob).hexdigest()==expected,'CAPTURE_BYTES_CHANGED')
        loaded[filename]=parse_json_bytes(blob)
    index=loaded['capture.json']; keys=collections.Counter(); total=0; private_verified=[]
    need(index['master_contribution']=={'reviewed_positive':0,'reviewed_negative':0,'approved_positive':0,'approved_negative':0,'deployed':0},'MASTER_PROMOTION_FORBIDDEN')
    for item in index['source_files']:
        filename=item['file']; batch=loaded[filename]; data=batch['source_projection']; topic=batch['topic']
        need(item['sha256']==PINS[filename] and item['bytes']==(HERE/filename).stat().st_size,'INDEX_BINDING')
        need(batch['scope']=='AUTHENTIC_PLANNER_DISCOVERY_UNREVIEWED' and batch['ui_context']=={'account_id':'573-038-4686','location':'United Arab Emirates','language':'English','network_display':'Google','date_preset':'Last 12 months','exclude_adult_ideas':True,'website_filter':None,'ui_idea_count':item['records']},'RESEARCH_CONTEXT')
        need(batch['controls']=={'reviewed':False,'approved':False,'deployed':False,'master_rows_added':0,'live_campaign_changes':False,'raw_export_committed':False},'AUTHORITY_BOUNDARY')
        public=[c for c in data['column_labels'] if c not in EXCLUDED_COLUMNS]
        need(data['public_columns']==public and set(data['excluded_columns'])==EXCLUDED_COLUMNS,'PRIVACY_COLUMNS')
        need(set(data['column_labels'])==set(BASE_COLUMNS)|set(_monthly_columns(data['date_header'])),'SOURCE_SCHEMA')
        need(len(batch['input_seeds'])==10 and len(set(map(normalize,batch['input_seeds'])))==10,'SEED_IDENTITIES')
        local=collections.Counter()
        for n,record in enumerate(data['records'],4):
            need(record['source_line']==n and list(record['values'])==public,'SOURCE_LINE_OR_COLUMNS')
            need(all(v is None or isinstance(v,str) for v in record['values'].values()),'EXACT_CELL_TYPES')
            local[normalize(record['values']['Keyword'])]+=1
        need(len(data['records'])==data['record_count']==item['records'] and len(local)==data['distinct_normalized_count']==item['distinct_normalized'],'COUNTS')
        need(not data['duplicate_groups'] and all(v==1 for v in local.values()),'DUPLICATES_REQUIRING_REVIEW')
        missing=[{'seed':seed,'grouped_under':None} for seed in batch['input_seeds'] if normalize(seed) not in local]
        need(batch['seed_reconciliation']=={'exact_returned':10-len(missing),'without_separate_exact_row':missing},'SEED_RECONCILIATION')
        need(data['source_sha256']==item['source_sha256'] and data['source_bytes']==item['source_bytes'],'RAW_PROVENANCE')
        keys.update(local); total+=len(data['records'])
        if topic in sources:
            raw=parse_discovery(sources[topic]); raw['source_basename']=data['source_basename']
            need(raw==data,'PRIVATE_RAW_PROJECTION_MISMATCH')
            private_verified.append(topic)
    need(index['totals']=={'export_rows':total,'distinct_normalized_phrases':len(keys),'repeated_occurrences_across_batches':total-len(keys),'overlap_groups':sum(v>1 for v in keys.values())},'UNION_COUNTS')
    return {'passed':True,'scope':'PRIVATE_RAW_EQUIVALENCE' if len(private_verified)==4 else 'PUBLIC_CONSISTENCY_ONLY','raw_batches_verified':sorted(private_verified),'export_rows':total,'distinct_phrases':len(keys),'reviewed_positive':0,'reviewed_negative':0,'deployment_authorized':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',action='append',default=[],metavar='BATCH=PRIVATE_PATH');args=ap.parse_args()
    try:
        sources={}
        for value in args.source:
            name,path=value.split('=',1);need(name not in sources,'DUPLICATE_SOURCE_ARGUMENT');sources[name]=path
        print(json.dumps(verify(sources)))
    except Exception:
        print(json.dumps({'passed':False,'code':'CAPTURE_VERIFICATION_FAILED','deployment_authorized':False}));raise SystemExit(1)
