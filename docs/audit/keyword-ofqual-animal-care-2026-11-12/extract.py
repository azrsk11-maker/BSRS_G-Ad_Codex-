"""Read-only official-source/coverage checks; no admission, export or file writer."""
from collections import Counter, defaultdict
from copy import deepcopy
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from time import perf_counter

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
import ofqual_discovery as od
import keyword_audit as ka
import keyword_text_compatibility as compatibility

SOURCE_SHA256='ec3d5f789e14dd07fcc8a46b61e46a5d4f103ac84b6a6fd3330fcc94211409d5'
SOURCE_BYTES=23984795
SOURCE_RECORDS=53175
SOURCE_URL='https://downloads.find-a-qualification.services.ofqual.gov.uk/extracts/Qualifications.csv'
PATTERN=r'\b(veterinary|animal care|dog grooming|canine|equine)\b'
TOPIC=re.compile(PATTERN,re.IGNORECASE)
AVAILABLE='Available to learners'
TOPIC_STATUSES=dict(zip(od.STATUSES,(266,19,159,0)))
SOURCE_STATUSES=dict(zip(od.STATUSES,(17212,1532,34208,223)))
PREVIOUS={
    'docs/audit/keyword-ofqual-discovery-2026-11-11/qualifications.json':
        ('2869cab8a06a76fa113ef430b28d09c53a324b72555cd0b3b36d3bdf82de4ccc',338),
    'docs/audit/keyword-ofqual-occupational-2026-11-12/qualifications.json':
        ('8cdd1a1e0475857b1fc7473734756da9bb20b2229890c61d639ee41ed6dac91c',524),
    'docs/audit/keyword-ofqual-veterinary-2026-11-12/qualifications.json':
        ('00daad3657a0ea8d2407c50dd2478ac7099355c53d33fadbbd92598c2eac09fa',51),
}
DEPENDENCY_PINS = {'tools/keyword-system/ofqual_discovery.py': '0c6e1ca3c8109237d98ea173c0b460d4e5b95d5f78f16a25c72836ed2041ebd2', 'tools/keyword-system/keyword_audit.py': 'ef6ce0535c8ce5cd83f50e169d26328cd763a236cfcbee4919f927c6fd8cd8d6', 'tools/keyword-system/keyword_text_compatibility.py': '723988151adfeae8f2a6efeb073a399451eefcbfe1d3f8c311e0e168fd56763f'}
PROJECTION_PIN = 'e265c3aa15e185b3457321df54365386330a0e75548cc251a8d114ac1043a903'
REVIEW_PIN = 'ae971dfa91438e9ae00927b6b3bfe1493096ca7e3cb56ca9528dea307d83126e'
CONTROLS={'raw_source_committed':False,'admission_to_negative_library':False,
    'exclusion_approval':False,'deployed':False,'live_campaign_changes':False,
    'property_inventory_or_rights_claimed':False,'observed_query_or_demand_claimed':False}


def need(condition,message):
    if not condition:raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()


def exact(left,right):
    if type(left) is not type(right):return False
    if isinstance(right,dict):return set(left)==set(right) and all(exact(left[k],v) for k,v in right.items())
    if isinstance(right,list):return len(left)==len(right) and all(exact(a,b) for a,b in zip(left,right))
    return left==right


def pinned(path,pin):
    raw=path.read_bytes()
    need(isinstance(pin,str) and len(raw)<=4*1024*1024 and hashlib.sha256(raw).hexdigest()==pin,
         'PINNED_DOCUMENT_CHANGED_OR_UNREGISTERED')
    return ka.parse_json_bytes(raw)


def previous_rows():
    ordinals={};refs=[]
    for relative,(pin,count) in PREVIOUS.items():
        old=pinned(ROOT/relative,pin)
        need(len(old['records'])==count and old['source_sha256']==SOURCE_SHA256,
             'PREVIOUS_SOURCE_IDENTITY_CHANGED')
        for row in old['records']:
            ordinal=row['source_record_ordinal']
            need(type(ordinal) is int and ordinal not in ordinals,'PREVIOUS_ORDINAL_OVERLAP')
            ordinals[ordinal]=relative
        refs.append({'file':relative,'sha256':pin,'records':count})
    need(len(ordinals)==913,'PREVIOUS_POPULATION_CHANGED')
    return ordinals,refs


def classify(topic_rows,old):
    selected=[];excluded=[]
    for row in topic_rows:
        if row['values']['Qualification Status']!=AVAILABLE:continue
        ordinal=row['source_record_ordinal']
        (excluded if ordinal in old else selected).append(ordinal)
    return selected,excluded


def projection(rows,old,refs,header_end):
    selected,excluded=classify(rows,old)
    return {'schema':'bsre-ofqual-animal-care-source-v1','source_sha256':SOURCE_SHA256,
        'source_bytes':SOURCE_BYTES,'source_record_count':SOURCE_RECORDS,'source_url':SOURCE_URL,
        'original_capture_date_utc':'2026-11-11','extraction_date_dubai':'2026-11-12',
        'source_encoding':'UTF-8 with BOM','source_headers':list(od.HEADERS),
        'public_fields':list(od.PUBLIC_FIELDS),'header_source_line_end':header_end,
        'source_status_counts':SOURCE_STATUSES,'topic_pattern':PATTERN,'topic_flags':'IGNORECASE',
        'topic_status_counts':TOPIC_STATUSES,'previous_projections':refs,'records':rows,
        'selected_source_ordinals':selected,'previously_reviewed_available_ordinals':excluded,
        'selected_records':len(selected),'previously_reviewed_available_records':len(excluded),
        'unavailable_topic_records':len(rows)-len(selected)-len(excluded),
        'controls':dict(CONTROLS)}


def extract(source):
    old,refs=previous_rows();path=Path(source)
    need(path.stat().st_size==SOURCE_BYTES,'SOURCE_BYTE_BOUND')
    raw=path.read_bytes()
    need(len(raw)==SOURCE_BYTES and hashlib.sha256(raw).hexdigest()==SOURCE_SHA256 and
         raw.startswith(b'\xef\xbb\xbf'),'EXACT_RAW_SOURCE_PIN_OR_BOM')
    text=raw.decode('utf-8-sig',errors='strict');od._csv_quoting(text)
    reader=csv.reader(io.StringIO(text,newline=''),strict=True)
    need(next(reader,None)==list(od.HEADERS),'SOURCE_HEADERS_CHANGED')
    header_end=reader.line_num;rows=[];qans=set();statuses=Counter();ordinal=0
    while True:
        start=reader.line_num+1;cells=next(reader,None)
        if cells is None:break
        ordinal+=1
        need(ordinal<=od.MAX_SOURCE_ROWS and len(cells)==len(od.HEADERS),'SOURCE_ROW_BOUND_OR_WIDTH')
        for cell in cells:od._cell(cell)
        original=dict(zip(od.HEADERS,cells));values={k:original[k] for k in od.PUBLIC_FIELDS}
        od._metadata(values);qan=values['Qualification Number']
        need(qan not in qans,'DUPLICATE_SOURCE_QUALIFICATION_NUMBER');qans.add(qan)
        statuses[values['Qualification Status']]+=1
        if TOPIC.search(values['Qualification Title']):
            rows.append({'source_record_ordinal':ordinal,'source_line_start':start,
                'source_line_end':reader.line_num,'values':values,'complete_public_values_sha256':digest(values)})
    need(ordinal==SOURCE_RECORDS and dict(statuses)==SOURCE_STATUSES,'INCOMPLETE_FULL_SOURCE')
    result=projection(rows,old,refs,header_end)
    validate_projection(result)
    return result


def validate_projection(value):
    old,refs=previous_rows();rows=value['records']
    need(type(rows) is list and len(rows)==444,'INCOMPLETE_TOPIC_POPULATION')
    ordinals=[];qans=set();statuses=Counter();prior_line=value['header_source_line_end']
    first_previous=next(iter(PREVIOUS))
    expected_header=pinned(ROOT/first_previous,PREVIOUS[first_previous][0])['header_source_line_end']
    need(type(prior_line) is int and prior_line==expected_header,'HEADER_LINE_INVALID')
    for row in rows:
        need(set(row)=={'source_record_ordinal','source_line_start','source_line_end','values',
                        'complete_public_values_sha256'},'ROW_FIELDS_CHANGED')
        ordinal=row['source_record_ordinal'];start=row['source_line_start'];end=row['source_line_end']
        need(type(ordinal) is int and 1<=ordinal<=SOURCE_RECORDS and type(start) is int and
             type(end) is int and prior_line<start<=end,'ROW_ORDER_OR_PHYSICAL_LINES_CHANGED')
        prior_line=end;ordinals.append(ordinal);values=row['values'];od._metadata(values)
        need(set(values)==set(od.PUBLIC_FIELDS) and all(type(v) is str for v in values.values()) and
             TOPIC.search(values['Qualification Title']) and row['complete_public_values_sha256']==digest(values),
             'PUBLIC_SOURCE_CELLS_CHANGED')
        need(values['Qualification Number'] not in qans,'DUPLICATE_TOPIC_QUALIFICATION_NUMBER')
        qans.add(values['Qualification Number']);statuses[values['Qualification Status']]+=1
    need(ordinals==sorted(set(ordinals)) and dict(statuses)=={k:v for k,v in TOPIC_STATUSES.items() if v},
         'TOPIC_ORDER_OR_STATUS_COUNTS_CHANGED')
    expected=projection(rows,old,refs,value['header_source_line_end'])
    need(exact(value,expected) and value['selected_records']==214 and
         value['previously_reviewed_available_records']==52 and value['unavailable_topic_records']==178,
         'SOURCE_SELECTION_OR_AUTHORITY_CHANGED')
    selected=set(value['selected_source_ordinals'])
    need(len({ka.normalize(r['values']['Qualification Title']) for r in rows if r['source_record_ordinal'] in selected})==213,
         'NORMALIZED_SELECTED_POPULATION_CHANGED')


def profile(text):
    original=compatibility.profile_text(text)['original']
    return {k:v for k,v in original.items() if k!='text'}


def validate_review(review,source):
    need(review['schema']=='bsre-ofqual-animal-care-literal-review-v1' and
        review['projection_sha256']==PROJECTION_PIN and review['reviewed_on']=='2026-11-12' and
        exact(review['reviewer'],{'name':'Codex AI lead','all_complete_literals_read':True,
              'independent_second_review':False,'human_approval':False}) and
        exact(review['controls'],CONTROLS),'REVIEW_SOURCE_OR_AUTHORITY_CHANGED')
    selected=set(source['selected_source_ordinals'])
    rows=[r for r in source['records'] if r['source_record_ordinal'] in selected]
    decisions=review['decisions'];need(len(decisions)==214,'INCOMPLETE_LITERAL_REVIEW')
    for index,(row,d) in enumerate(zip(rows,decisions),1):
        text=row['values']['Qualification Title']
        expected={'selected_ordinal':index,'source_record_ordinal':row['source_record_ordinal'],
            'source_line_start':row['source_line_start'],'source_line_end':row['source_line_end'],
            'qualification_number':row['values']['Qualification Number'],'original_literal':text,
            'normalized_title':ka.normalize(text),'literal_utf8_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
            'complete_public_values_sha256':row['complete_public_values_sha256'],
            'semantic_decision':'PROPOSE_FULL_EXACT_RESEARCH','reason_code':'EXPLICIT_NAMED_ANIMAL_STUDY_OR_ASSESSMENT',
            'matching_limit':'COMPLETE_ORIGINAL_LITERAL_ONLY_FOR_LATER_EXACT_REVIEW',
            'text_compatibility':profile(text)}
        need(exact(d,expected),'LITERAL_REVIEW_OR_COMPATIBILITY_CHANGED')
    counts=dict(Counter(d['text_compatibility']['classification'] for d in decisions))
    need(exact(review['summary'],{'source_occurrences':214,'distinct_normalized_titles':213,
        'semantic_proposals':214,'text_compatibility':counts,'negative_library_rows_added':0,
        'approved':0,'deployed':0}),'REVIEW_COUNTS_CHANGED')


def make_capture():
    return {'schema':'bsre-ofqual-animal-care-capture-v1','source_url':SOURCE_URL,
        'original_capture_date_utc':'2026-11-11','extracted_on_dubai':'2026-11-12',
        'raw_source_sha256':SOURCE_SHA256,'raw_source_bytes':SOURCE_BYTES,
        'existing_private_source_reused':True,'new_provider_downloads':0,'raw_source_committed':False,
        'source_records':53175,'complete_topic_records':444,'topic_status_counts':TOPIC_STATUSES,
        'new_available_source_occurrences':214,'new_distinct_normalized_titles':213,
        'previously_reviewed_available_occurrences':52,'unavailable_topic_occurrences':178,
        'files':{name:{'sha256':hashlib.sha256((HERE/name).read_bytes()).hexdigest(),
            'bytes':(HERE/name).stat().st_size} for name in ['qualifications.json','semantic-review.json','extract.py']},
        'dependencies':DEPENDENCY_PINS,'master_rows_added':0,'exclusion_approval':False,'deployment':False}


def validate_capture(capture):
    need(exact(capture,make_capture()),'CAPTURE_BINDINGS_OR_AUTHORITY_CHANGED')


def self_check(source,review,capture):
    source_cases={
        'drop_topic_occurrence':lambda x:x['records'].pop(),
        'reverse_source_order':lambda x:x['records'].reverse(),
        'public_cell_changed':lambda x:x['records'][0]['values'].__setitem__('Qualification Title','Animal care fabricated'),
        'source_id_replaced':lambda x:x['records'][0]['values'].__setitem__('Qualification Number','000/0000/0'),
        'old_ordinal_reintroduced':lambda x:x['selected_source_ordinals'].append(x['previously_reviewed_available_ordinals'][0]),
        'status_changed':lambda x:x['records'][0]['values'].__setitem__('Qualification Status',
            'No longer awarded' if x['records'][0]['values']['Qualification Status']==AVAILABLE else AVAILABLE),
        'boolean_count':lambda x:x.__setitem__('selected_records',True),
        'authority_granted':lambda x:x['controls'].__setitem__('exclusion_approval',True),
    }
    review_cases={
        'drop_review_occurrence':lambda x:x['decisions'].pop(),
        'alter_review_literal':lambda x:x['decisions'][0].__setitem__('original_literal','animal care'),
        'invent_human_approval':lambda x:x['reviewer'].__setitem__('human_approval',True),
        'erase_compatibility_hold':lambda x:x['decisions'][0]['text_compatibility'].__setitem__('classification','CLEARED'),
        'promote_master_count':lambda x:x['summary'].__setitem__('negative_library_rows_added',103),
        'projection_pin_changed':lambda x:x.__setitem__('projection_sha256','0'*64),
    }
    capture_cases={
        'capture_code_pin_changed':lambda x:x['files']['extract.py'].__setitem__('sha256','0'*64),
        'capture_authority_changed':lambda x:x.__setitem__('deployment',True),
    }
    checked=[]
    for cases,original,validator in [(source_cases,source,validate_projection),
                                   (review_cases,review,lambda x:validate_review(x,source)),
                                   (capture_cases,capture,validate_capture)]:
        for name,mutate in cases.items():
            changed=deepcopy(original);mutate(changed)
            try:validator(changed)
            except (ValueError,KeyError,TypeError):checked.append(name);continue
            raise AssertionError('Tamper accepted: '+name)
    return checked


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path)
    parser.add_argument('--self-check',action='store_true');args=parser.parse_args();tick=perf_counter()
    need(isinstance(DEPENDENCY_PINS,dict),'DEPENDENCIES_UNREGISTERED')
    for path,pin in DEPENDENCY_PINS.items():
        need(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==pin,'DEPENDENCY_BYTES_CHANGED')
    source=pinned(HERE/'qualifications.json',PROJECTION_PIN);validate_projection(source)
    review=pinned(HERE/'semantic-review.json',REVIEW_PIN);validate_review(review,source)
    capture_raw=(HERE/'capture.json').read_bytes();need(len(capture_raw)<=128*1024,'CAPTURE_BYTE_BOUND')
    capture=ka.parse_json_bytes(capture_raw);validate_capture(capture)
    result={'passed':True,'topic_occurrences':444,'new_available_occurrences':214,
        'distinct_new_titles':213,'prior_available_occurrences_excluded':52,'unavailable_occurrences':178,
        'new_research_rows':0,'approved':0,'deployed':0,'private_source_equivalence':False}
    if args.source:
        need(exact(extract(args.source),source),'PRIVATE_SOURCE_CELL_EQUIVALENCE_FAILED')
        result['private_source_equivalence']=True
    if args.self_check:result['tamper_cases_rejected']=self_check(source,review,capture)
    result['elapsed_seconds']=round(perf_counter()-tick,6)
    print(json.dumps(result,ensure_ascii=True,sort_keys=True))


if __name__=='__main__':main()
