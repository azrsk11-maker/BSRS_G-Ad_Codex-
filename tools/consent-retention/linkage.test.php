<?php
declare(strict_types=1);
require __DIR__.'/LinkageReconciliation.php';
use BSRE\RetentionReview\LinkageReconciliation as L;
use BSRE\RetentionReview\RetentionInventory as I;
function fixture(string $id='11111111-1111-4111-8111-111111111111'): array {
    $capture=array_fill_keys(I::COLUMNS['captures'],'');
    foreach(['original_revision','analytics','ad_measurement','personalization','preference_expires_at','eligible','known','created_at','uncertain','delivery_pending','gclid_first_captured_ms','gclid_last_captured_ms'] as $k)$capture[$k]=0;
    $capture=array_replace($capture,['request_id'=>$id,'fingerprint'=>hash('sha256','SYNTHETIC RAW BODY'),'subject_key'=>str_repeat('a',64),'original_revision'=>1,'decision_version'=>str_repeat('b',32),'notice_version'=>'SYNTHETIC','known'=>1,'created_at'=>1700000000,'state'=>'ACCEPTED','lead_id'=>'BSRE-22222222-2222-4222-8222-222222222222','event_id'=>'evt_33333333-3333-4333-8333-333333333333']);
    $row=array_fill(0,26,''); $row[0]=$id; $row[1]=$capture['lead_id']; $row[2]=$capture['event_id'];
    $row[5]=json_encode(['request_id'=>$id,'role'=>'tenant'],JSON_THROW_ON_ERROR); $row[4]=hash('sha256',$row[5]); $row[6]='SENT'; $row[14]='tenant';
    return ['source'=>'SYNTHETIC_PIPE_SESSION','receiver_headers'=>L::HEADERS,'captures'=>[$capture],'receiver_rows'=>[$row]];
}
function check(bool $ok):void {if(!$ok)throw new RuntimeException('Linkage assertion failed');}
function issue(array $s,string $code):void{$r=L::assess($s);check(($r['issues'][$code]??0)>0 && $r['global_linkage_hold']);}
function invalid(array $s):void{try{L::assess($s);}catch(InvalidArgumentException $e){check(!str_contains($e->getMessage(),'SYNTHETIC RAW'));return;}throw new RuntimeException('Invalid input accepted');}
$cases=[];
$cases['distinct fingerprint domains and scoped redaction']=function(){ $s=fixture();$r=L::assess($s);check($s['captures'][0]['fingerprint']!==$s['receiver_rows'][0][4] && $r['matched_request_receipts']===1 && $r['issues']===[]);$text=json_encode($r);foreach([$s['captures'][0]['request_id'],$s['captures'][0]['subject_key'],$s['receiver_rows'][0][1]] as $private)check(!str_contains($text,$private));check(!$r['historical_coverage_verified']&&!$r['mail_delivery_verified']&&!$r['deletion_authorized']&&!$r['import_authorized']);};
$cases['missing capture']=function(){$s=fixture();$s['captures']=[];issue($s,'CAPTURE_MISSING');};
$cases['missing receiver']=function(){$s=fixture();$s['receiver_rows']=[];issue($s,'RECEIVER_ROW_MISSING');};
$cases['lost acknowledgement remains held']=function(){$s=fixture();$s['captures'][0]['state']='STAGED';$s['captures'][0]['lead_id']='';$s['captures'][0]['event_id']='';$s['captures'][0]['delivery_pending']=1;issue($s,'RECEIPT_NOT_LINKED');};
$cases['receipt conflict']=function(){$s=fixture();$s['captures'][0]['event_id']='evt_44444444-4444-4444-8444-444444444444';issue($s,'RECEIPT_ID_CONFLICT');};
$cases['duplicate capture canonical identity']=function(){$s=fixture('abcdef01-1111-4111-8111-111111111111');$s['captures'][]=$s['captures'][0];$s['captures'][1]['request_id']=strtoupper($s['captures'][1]['request_id']);issue($s,'DUPLICATE_CAPTURE_REQUEST');check(L::assess($s)['matched_request_receipts']===0);};
$cases['duplicate receiver canonical identity']=function(){$s=fixture('abcdef01-1111-4111-8111-111111111111');$s['receiver_rows'][]=$s['receiver_rows'][0];$s['receiver_rows'][1][0]=strtoupper($s['receiver_rows'][1][0]);issue($s,'DUPLICATE_RECEIVER_REQUEST');};
$cases['reused lead or event excludes both identities']=function(){foreach([1,2] as $column){$s=fixture();$t=fixture('44444444-4444-4444-8444-444444444444');$t['receiver_rows'][0][1]='BSRE-55555555-5555-4555-8555-555555555555';$t['receiver_rows'][0][2]='evt_66666666-6666-4666-8666-666666666666';$t['captures'][0]['lead_id']=$t['receiver_rows'][0][1];$t['captures'][0]['event_id']=$t['receiver_rows'][0][2];$t['receiver_rows'][0][$column]=$s['receiver_rows'][0][$column];$s['captures'][]=$t['captures'][0];$s['receiver_rows'][]=$t['receiver_rows'][0];issue($s,$column===1?'DUPLICATE_LEAD_ID':'DUPLICATE_EVENT_ID');check(L::assess($s)['matched_request_receipts']===0);}};
$cases['payload checksum']=function(){$s=fixture();$s['receiver_rows'][0][5].=' ';issue($s,'RECEIVER_PAYLOAD_DIGEST_MISMATCH');check(L::assess($s)['matched_request_receipts']===0);};
$cases['payload identity']=function(){$s=fixture();$s['receiver_rows'][0][14]='seller';issue($s,'RECEIVER_PAYLOAD_IDENTITY_MISMATCH');};
$cases['unknown subject and permission holds']=function(){$s=fixture();$s['captures'][0]['subject_key']='';$s['captures'][0]['known']=0;issue($s,'CAPTURE_SUBJECT_UNKNOWN');check(L::assess($s)['original_measurement_holds']===1);};
$cases['unsupported or unresolved original evidence stays held']=function(){ $base=fixture();$base['captures'][0]=array_replace($base['captures'][0],['known'=>1,'ad_measurement'=>1,'eligible'=>1,'preference_expires_at'=>time()+3600]);check(L::assess($base)['original_measurement_holds']===0);foreach(['personalization'=>1,'notice_version'=>'','original_revision'=>0,'created_at'=>0] as $field=>$value){$s=$base;$s['captures'][0][$field]=$value;check(L::assess($s)['original_measurement_holds']===1);} $s=$base;$s['captures'][0]['created_at']=time()+3600;check(L::assess($s)['original_measurement_holds']===1); };
$cases['outbox is not mail verification']=function(){foreach(['QUEUED','RETRY_WAIT','SENDING','AMBIGUOUS','NEEDS_REVIEW'] as $status){$s=fixture();$s['receiver_rows'][0][6]=$status;$r=L::assess($s);check($r['outbox_holds']===1 && !$r['mail_delivery_verified']);}};
$cases['unsupported schema and supplied authority rejected']=function(){$s=fixture();$s['complete']=true;invalid($s);$s=fixture();array_pop($s['receiver_headers']);invalid($s);$s=fixture();$s['source']='PRODUCTION_COMPLETE';invalid($s);};
$cases['bounds and malformed row types']=function(){$s=fixture();$s['receiver_rows']=array_fill(0,1000,$s['receiver_rows'][0]);invalid($s);$s=fixture();$s['receiver_rows'][0][11]=str_repeat('x',8*1024*1024+1);invalid($s);$s=fixture();$s['receiver_rows'][0][5]=[];invalid($s);$s=fixture();$s['captures'][0]['known']='yes';invalid($s);};
$start=microtime(true);foreach($cases as $name=>$run){$run();}
echo json_encode(['phase'=>'linkage_reconciliation_unit','status'=>'PASS','cases'=>count($cases),'elapsed_ms'=>round((microtime(true)-$start)*1000,3),'synthetic_only'=>true,'production_acceptance'=>false],JSON_THROW_ON_ERROR)."\n";
