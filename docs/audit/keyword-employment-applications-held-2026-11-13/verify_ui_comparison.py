"""Check complete UI/export comparison; the original capture remains held."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PIN='96ee2bca743bf1ff56d9b5940b3bb7b1b6ac0babd8a5d97760ab0b4e94ae8af2'


def verify():
    body=(HERE/'ui-comparison.json').read_bytes()
    assert len(body)<64*1024 and hashlib.sha256(body).hexdigest()==PIN,'UI_COMPARISON_PIN'
    receipt=json.loads(body.decode('utf-8'))
    assert receipt['scope']=='COMPLETE_DISPLAYED_LABEL_COMPARISON_NOT_SOURCE_PROMOTION'
    for name,pin in receipt['source_pins'].items():
        assert name in {'projection.json','capture.json','verify_capture.py'}
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==pin
    spec=importlib.util.spec_from_file_location('original_held_capture',HERE/'verify_capture.py')
    original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
    assert original.verify()['capture_accepted_for_research'] is False
    data=json.loads((HERE/'projection.json').read_text(encoding='utf-8'))['source_projection']['records']
    labels=receipt['complete_observed_ui_labels']
    assert receipt['independent_ui_count']==len(labels)==len(set(labels))==176
    assert receipt['raw_export_count']==len(data)==177
    original_words=[r['values']['Keyword'] for r in data]
    assert not set(labels)-set(original_words) and receipt['ui_only']==[]
    extra=[{'source_ordinal':i,'source_line':r['source_line'],'original_literal':r['values']['Keyword']}
           for i,r in enumerate(data,1) if r['values']['Keyword'] not in set(labels)]
    assert extra==receipt['export_only']==[{'source_ordinal':99,'source_line':102,
        'original_literal':'real estate accountant jobs in dubai'}]
    assert [w for w in original_words if w in set(labels)]==labels
    for key in ['cause_established','capture_accepted_for_research','semantic_review_complete',
                'deployment_authorized','original_source_rows_removed_or_repaired']:
        assert receipt[key] is False
    assert type(receipt['master_rows_added']) is int and receipt['master_rows_added']==0
    assert receipt['temporary_500_row_display_restored_to_10'] is True
    return {'passed':True,'scope':'HELD_EVIDENCE_LOCALIZATION_ONLY','ui_labels':176,'raw_rows':177,
            'export_only_source_ordinal':99,'cause_established':False,
            'source_promoted':False,'library_rows_added':0,'deployment_authorized':False}


if __name__=='__main__':
    try:
        print(json.dumps(verify(),sort_keys=True))
    except Exception as error:
        print(json.dumps({'passed':False,'code':'UI_COMPARISON_UNVERIFIED','error_type':type(error).__name__}))
        raise SystemExit(1)
