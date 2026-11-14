"""Reproduce the unapproved triage queue from pinned observed source records."""
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'tools/keyword-system'))
from triage_workbench import load_corpus,compile_workbench
from keyword_audit import negative_matches, parse_json_bytes
PINS={
  "proposals.json": "e5e5375f451eb8c92b721105efe8cdadf72d4c9101ddae58e96a66adc9a307e5",
  "workbench.json": "1a687839b595c7b56cd7bbc150e31fb735eb1dfdaabe094b5e097b4323c7f477"
}
def verify_archived_negative_screen(proposals):
    intake_path = ROOT / 'tools/keyword-system/staging/historical-negative-intake.json'
    candidates = parse_json_bytes(intake_path.read_bytes())['candidates']
    match_types = {'Negative phrase': 'PHRASE', 'Negative exact': 'EXACT'}
    negatives = [(row['original_text'], match_types[mode])
                 for row in candidates for mode in row['historical_match_types_seen']]
    protected = {row['text'] for row in proposals if row['protect_against_generic']}
    if len(negatives) != 9 or len(set(negatives)) != 9 or len(protected) != 570:
        raise ValueError('Archived negative screen inputs changed')
    if not all(negative_matches(term, mode, term) for term, mode in negatives):
        raise ValueError('Archived negative screen control failed')
    if any(negative_matches(term, mode, query) for term, mode in negatives for query in protected):
        raise ValueError('Archived negative conflicts with a provisionally protected phrase')
    return {'comparisons': len(negatives) * len(protected), 'lexical_conflicts': 0}


def verify():
    values={}
    for filename,expected in PINS.items():
        content=(HERE/filename).read_bytes()
        if hashlib.sha256(content).hexdigest()!=expected: raise ValueError('Triage bytes changed')
        values[filename]=parse_json_bytes(content)
    fresh=compile_workbench(load_corpus(ROOT),values['proposals.json'])
    if fresh!=values['workbench.json']: raise ValueError('Workbench does not reproduce from observed sources')
    return {'passed':True,'scope':'PRELIMINARY_TRIAGE_NOT_ADMISSION','unique_phrases':fresh['summary']['unique_phrases'],'source_occurrences':fresh['summary']['source_occurrences'],'dispositions':fresh['summary']['dispositions'],'archived_negative_screen':verify_archived_negative_screen(values['proposals.json']['proposals']),'reviewed_positive':0,'reviewed_negative':0,'deployment_authorized':False}
if __name__=='__main__':
    try: print(json.dumps(verify()))
    except Exception:
        print(json.dumps({'passed':False,'scope':'PRELIMINARY_TRIAGE_NOT_ADMISSION','deployment_authorized':False}));raise SystemExit(1)
