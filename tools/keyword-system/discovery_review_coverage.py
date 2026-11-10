"""Occurrence-level preliminary review reconciliation, never keyword admission.

The fixed caller must verify raw file/manifest hashes. This pure function checks
their associations and recompiles every review using the unchanged historical
compiler on a detached date projection. It does not authenticate reviewers or
establish Google matching, serving scope, business facts or master eligibility.
"""
from collections import Counter,defaultdict
from datetime import date
import re
from pathlib import PurePosixPath

import triage_workbench as legacy
from keyword_audit import normalize,tokens
from supplemental_discovery import _batch,_exact
from supplemental_triage import dubai_date

STATES=legacy.DISPOSITIONS|{'UNASSESSED'}
CANONICAL_STATES=STATES|{'DISAGREEMENT_HOLD','NO_STRUCTURED_REVIEW'}


def need(ok,code):
    if not ok:raise ValueError(code)


def day(value):
    need(isinstance(value,str),'INVALID_DATE')
    result=date.fromisoformat(value)
    need(result.isoformat()==value and result<=dubai_date(),'INVALID_DATE')
    return result


def metadata(item,keys):
    need(isinstance(item,dict) and set(item)==keys,'DESCRIPTOR_FIELDS')
    name=item['file']
    need(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_./-]+\.json',name) and
         not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts and
         PurePosixPath(name).as_posix()==name,
         'DESCRIPTOR_PATH')
    need(isinstance(item['sha256'],str) and re.fullmatch(r'[0-9a-f]{64}',item['sha256']),
         'DESCRIPTOR_HASH')


def reconcile(captures,reviews,authored_queries=None):
    need(isinstance(captures,list) and 1<=len(captures)<=64 and
         isinstance(reviews,list) and len(reviews)<=32,'INPUT_BOUNDS')
    authored_queries=[] if authored_queries is None else authored_queries
    need(isinstance(authored_queries,list) and len(authored_queries)<=1000 and
         all(isinstance(q,str) and bool(tokens(q)) for q in authored_queries) and
         len(set(map(normalize,authored_queries)))==len(authored_queries),'AUTHORED_CASES')
    batches,observed,forms,source_files={}, {},{},set()
    for item in captures:
        metadata(item,{'file','sha256','captured_on','batch'})
        _batch(item['batch']);day(item['captured_on'])
        batch=item['batch']['batch_id']
        need(batch not in batches and item['file'] not in source_files,'DUPLICATE_SOURCE')
        batches[batch]=item;source_files.add(item['file'])
        for row in item['batch']['source_projection']['records']:
            ref=(batch,row['source_line']);key=normalize(row['values']['Keyword'])
            need(ref not in observed,'DUPLICATE_SOURCE_OCCURRENCE')
            observed[ref]=key;forms[ref]=row['values']['Keyword']
    need(0<len(observed)<=500000 and len(set(observed.values()))<=100000,'CORPUS_BOUNDS')
    assigned,assessments,review_files={},defaultdict(list),set()
    instance_counts=Counter()
    for item in reviews:
        metadata(item,{'file','sha256','workbench'})
        need(item['file'] not in review_files,'DUPLICATE_REVIEW')
        review_files.add(item['file']);wb=item['workbench']
        need(isinstance(wb,dict) and isinstance(wb.get('sources'),dict) and bool(wb['sources'])
             and isinstance(wb.get('queue'),list),'REVIEW_STRUCTURE')
        reviewed_on=day(wb.get('proposed_on'));owned=set(wb['sources'])
        for batch,binding in wb['sources'].items():
            need(batch in batches and batch not in assigned,'UNKNOWN_OR_REPEATED_REVIEW_SOURCE')
            source=batches[batch]
            need(binding=={'file':source['file'],'sha256':source['sha256']},'SOURCE_BINDING_MISMATCH')
            need(reviewed_on>=day(source['captured_on']),'REVIEW_PREDATES_CAPTURE')
        expected=defaultdict(list)
        for ref,key in observed.items():
            if ref[0] in owned:expected[key].append(ref)
        entries={}
        for row in wb['queue']:
            need(isinstance(row,dict),'REVIEW_ROW')
            key=row.get('normalized_text')
            need(isinstance(key,str) and key in expected and key not in entries,'REVIEW_IDENTITY')
            refs=row.get('source_refs');original=row.get('original_forms')
            need(isinstance(refs,list) and all(isinstance(r,dict) and set(r)=={'batch','source_line'}
                 and isinstance(r['batch'],str) and type(r['source_line']) is int for r in refs),'REVIEW_REFS')
            identities=[(r['batch'],r['source_line']) for r in refs]
            need(len(identities)==len(set(identities)) and identities==expected[key],
                 'REVIEW_SOURCE_OCCURRENCE_MISMATCH')
            expected_forms=list(dict.fromkeys(forms[ref] for ref in expected[key]))
            need(isinstance(original,list) and all(isinstance(f,str) for f in original) and len(original)==len(set(original)) and
                 original==expected_forms,'REVIEW_SOURCE_TEXT_MISMATCH')
            entries[key]={'original_forms':original,'source_refs':refs}
        need(set(entries)==set(expected),'MISSING_REVIEW_PHRASE')
        corpus={'sources':wb['sources'],'entries':entries}
        proposals={'version':1,'scope':legacy.SCOPE,'proposed_on':legacy.DAY,
                   'proposals':[r['assessment'] for r in wb['queue'] if r.get('assessment') is not None]}
        fresh=legacy.compile_workbench(corpus,proposals)
        fresh['proposed_on']=wb['proposed_on']
        need(_exact(fresh,wb),'REVIEW_NOT_REPRODUCIBLE')
        for batch in owned:assigned[batch]=item['file']
        for row in fresh['queue']:
            disposition=row['disposition'];instance_counts[disposition]+=1
            assessments[row['normalized_text']].append({'review_file':item['file'],
                'disposition':disposition,'possible_services':row['assessment']['possible_services']
                if row['assessment'] is not None else []})
    occurrences=Counter(observed.values());canonical_counts=Counter();overlaps=[]
    for key in sorted(occurrences):
        rows=assessments[key];states={r['disposition'] for r in rows}
        state='NO_STRUCTURED_REVIEW' if not rows else next(iter(states)) if len(states)==1 else 'DISAGREEMENT_HOLD'
        canonical_counts[state]+=1
        if len(rows)>1:overlaps.append({'normalized_text':key,'source_occurrences':occurrences[key],
            'review_assessments':rows,'dispositions_agree':len(states)==1,
            'classification_or_approval_inherited':False})
    protected={k for k,rows in assessments.items() if any(r['disposition']!='NEGATIVE_EXACT_REVIEW' for r in rows)}
    protected.update(k for k in occurrences if not assessments[k])
    protected.update(map(normalize,authored_queries))
    exact_index=defaultdict(list)
    for query in sorted(protected):exact_index[tuple(tokens(query))].append(query)
    negatives=sorted(k for k,rows in assessments.items() if any(r['disposition']=='NEGATIVE_EXACT_REVIEW' for r in rows))
    conflicts=[{'negative':k,'protected_queries':exact_index[tuple(tokens(k))]} for k in negatives
               if tuple(tokens(k)) in exact_index]
    return {'version':1,'scope':'PRELIMINARY_SOURCE_REVIEW_RECONCILIATION_ONLY',
        'capture_batches':len(batches),'review_documents':len(reviews),
        'source_occurrences':len(observed),'distinct_source_phrases':len(occurrences),
        'repeated_source_occurrences':len(observed)-len(occurrences),
        'review_assessment_instances':sum(instance_counts.values()),
        'review_instances_by_disposition':{s:instance_counts[s] for s in sorted(STATES)},
        'canonical_disposition_counts':{s:canonical_counts[s] for s in sorted(CANONICAL_STATES)},
        'unreviewed_batches':sorted(set(batches)-set(assigned)),
        'all_phrases_have_preliminary_assessments':not(set(batches)-set(assigned)) and not instance_counts['UNASSESSED'],
        'cross_review_overlap_phrases':overlaps,
        'provisional_exact_screen':{'draft_negative_literals':len(negatives),'protected_literals':len(protected),
            'authored_test_cases_excluded_from_source_counts':len(authored_queries),'conflicts':conflicts,
            'google_matching_verified':False,'actual_scope_verified':False,'full_approved_positive_library_coverage':False},
        'master_rows_added':0,'independent_review_verified':False,
        'admission_authorized':False,'deployment_authorized':False}
