<?php
declare(strict_types=1);
/** Injected into the fixed receiver native driver only, before bridge cleanup. Never standalone/live. */
if(PHP_SAPI!=='cli'||!isset($isolation,$wpdb,$journal,$custody,$policy,$producer,$authority,$port,$after,$owner)
    ||in_array(false,$isolation,true)||DB_NAME!=='bsre_synthetic'||$wpdb->prefix!=='g5_receiver_synthetic_'
    ||realpath(__DIR__)!=='/opt/lab/g5-receiver-runtime/tests')throw new RuntimeException('ACTUAL_PURGE_FIXED_NATIVE_CONTEXT_REQUIRED');
$purgeCode='/opt/lab/g5-receiver-runtime/candidate/plugin/includes/candidate/closed-enquiry-retention/';
require_once $purgeCode.'ActualPurgeWorkflow.php';require_once $purgeCode.'ActualPurgeCaptureResource.php';
final class NativePurgeAbi implements \BSRE\ActualRetention\PurgeServiceTransport,\BSRE\ActualRetention\Intake26Transport,
    \BSRE\ActualRetention\Outcome40Transport,\BSRE\ActualRetention\MarketingMailReadTransport {
    public int $calls=0;public bool $forge=false;public bool $incomplete=false;public int $resourceCalls=0;
    public ?array $approved=null;public int $delaySeconds=0;
    public function __construct(private \BSRE\ActualRetention\RuntimePolicy $p,private \BSRE\ActualRetention\ActualRecoveryCustody $anchor,
        private \BSRE\ClosedRetention\LeaseBoundWpdb $db,private array $intake){}
    public function exchange(string $op,array $q):string {
        $this->calls++;$actor=$this->p->actor();$now=time();$body=$q['body'];
        if($q['actor']!==$actor||$q['policy']!==$this->p->scope())throw new RuntimeException('SYNTHETIC_PURGE_SCOPE_CONFLICT');
        if($op==='approval'){$r=$this->approved;if($r===null)throw new RuntimeException('SYNTHETIC_PURGE_NOT_APPROVED');}
        elseif($op==='boundary'){
            // Independent fixture reads the real SQL ciphertext/current anchor rather than accepting caller flags.
            $row=$this->db->get_row('SELECT revision,body_hash,body FROM g5_receiver_synthetic_bsre_g5_journal WHERE id=1',ARRAY_A);
            $a=$this->anchor->current();$current=is_array($row)&&$a===['revision'=>(int)$row['revision'],'hash'=>$row['body_hash']]
                &&hash('sha256',$row['body'])===$row['body_hash'];
            if($current){$state=$this->anchor->open($row['body'],(int)$row['revision']);$record=$body['record'];
                if($record!==null)$current=($state['jobs'][$record['plan']['digest']]??null)===$record;}
            $r=['request_hash'=>\BSRE\ClosedRetention\Workflow::digest($body),'owner_approval'=>true,'current_journal'=>$current,
                'current_sources'=>true,'mail_and_trash'=>!$this->incomplete,'recovery_custody'=>true,'history_floor'=>true];
        }elseif($op==='resource'){
            $this->resourceCalls++;$store=$body['store'];$operation=$body['operation'];
            if($operation==='remove_exact')throw new RuntimeException('SYNTHETIC_PURGE_NO_DELETE_FIXTURE');
            $rows=$store==='intake'?[$this->intake]:[];
            $result=$operation==='inventory'?['bindings'=>$rows]:['state'=>'ABSENT','binding'=>null];
            $r=['request_hash'=>\BSRE\ClosedRetention\Workflow::digest($body),'store'=>$store,
                'schema'=>['intake'=>'Intake26','outcome'=>'Outcome40','email'=>'MarketingExactMessageV1'][$store],
                'schema_hash'=>['intake'=>'0dcac495bed4beda7a027c5d21d0d8b1caaa8a307e6eb815e3566c46f41369ca','outcome'=>'bf477cc0cc4a161775abd702777898c6046d5dfcf0f2ae0e86fe078a3a63d9df','email'=>null][$store],
                'complete_surface'=>true,'trash_included'=>$store==='email'?true:null,'shared_identity_absent'=>true,'metadata_bound'=>true,
                'wire_v1_preserved'=>true,'outbox_reconciled'=>true,'result'=>$result];
        }else throw new RuntimeException('SYNTHETIC_PURGE_UNKNOWN_OPERATION');
        if($this->delaySeconds>0)sleep($this->delaySeconds);
        $s=['contract'=>'bsre-actual-purge-evidence-v1','actor'=>$actor,'policy'=>$this->p->scope(),'source_hash'=>$q['source_hash'],
            'operation'=>$op,'challenge'=>$q['challenge'],'request_hash'=>\BSRE\ClosedRetention\Workflow::digest($q),
            'issued_at'=>time(),'expires_at'=>time()+30,'result'=>$r];
        $sig=sodium_crypto_sign_detached(\BSRE\ClosedRetention\Workflow::digest($s),receiver_test_secret());
        if($this->forge)$sig=str_repeat('x',64);
        return \BSRE\ActualRetention\ReceiverV1\Guard::canonical(['key_id'=>'synthetic-rfc8032','statement'=>$s,'signature'=>base64_encode($sig)]);
    }
}
$nativeIntake=['key'=>$after['request_id'],'request_id'=>$after['request_id'],'request_ids'=>[$after['request_id']],
    'lead_id'=>$after['lead_id'],'event_id'=>$after['event_id'],'fingerprint'=>$scope['fingerprint'],
    'evidence_reference'=>'SYNTHETIC_NATIVE_INTAKE26_BINDING','evidence_hash'=>str_repeat('c',64)];
$nativeAbi=new NativePurgeAbi($policy,$custody,$wpdb,$nativeIntake);
$nativeSigned=new \BSRE\ActualRetention\SignedPurgeService($policy,$nativeAbi,'synthetic-rfc8032',
    hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'),str_repeat('e',64));
$nativeBoundary=new \BSRE\ActualRetention\PurgeBoundary($policy,$wpdb,$producer,$nativeSigned);
receiver_check('purge_default_off_holds_without_service',receiver_denied(fn()=>$nativeBoundary->begin($after['closure_id']))&&$nativeAbi->calls===0);
define('BSRE_ACTUAL_PURGE_ENABLED',true);
$nativeBoundary->begin($after['closure_id']);
try{
    $nativeJournal=new \BSRE\ActualRetention\ActualPurgeJournal($wpdb,$policy,$custody,$authority,$evidence,$proof,$producer,$nativeBoundary);
    receiver_check('purge_real_journal_reads_same_anchored_closure',$nativeJournal->locked($after['closure_id'],fn()=>$nativeJournal->closure($after['closure_id']))===$after);
    $nativeCapture=new \BSRE\ActualRetention\ActualPurgeCaptureResource($wpdb,$nativeJournal,$policy,$producer,$nativeBoundary);
    receiver_check('purge_real_capture_confirms_missing_fixture',$nativeJournal->locked($after['closure_id'],fn()=>$nativeCapture->read($after['request_id']))===null);
    $nativeMail=\BSRE\ActualRetention\PurgeResources::mail($policy,$nativeAbi,'synthetic-rfc8032',hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'),str_repeat('e',64),$nativeBoundary);
    $count=$nativeAbi->calls;receiver_check('purge_mail_delete_has_no_provider_path',receiver_denied(fn()=>$nativeMail->removeExact([]),'ACTUAL_PURGE_MAIL_MANUAL_ONLY')&&$nativeAbi->calls===$count);
    $nativeAbi->forge=true;receiver_check('purge_independent_forgery_is_rejected',receiver_denied(fn()=>$nativeBoundary->check(),'ACTUAL_PURGE_SIGNATURE_UNVERIFIED'));$nativeAbi->forge=false;
    $nativeAbi->incomplete=true;receiver_check('purge_missing_mail_trash_custody_holds',receiver_denied(fn()=>$nativeBoundary->check(),'ACTUAL_PURGE_CUSTODY_HELD'));$nativeAbi->incomplete=false;
}finally{$nativeBoundary->end();}
$nativeIntakeAdapter=\BSRE\ActualRetention\PurgeResources::intake($policy,$nativeAbi,'synthetic-rfc8032',hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'),str_repeat('e',64),$nativeBoundary);
$nativeOutcomeAdapter=\BSRE\ActualRetention\PurgeResources::outcome($policy,$nativeAbi,'synthetic-rfc8032',hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'),str_repeat('e',64),$nativeBoundary);
$nativeAdmission=new class implements \BSRE\ClosedRetention\Admission {public function readback(int $now):?array{return null;}};
$nativeWorkflow=new \BSRE\ActualRetention\ActualPurgeWorkflow($policy,$nativeJournal,$nativeBoundary,$authority,$nativeAdmission,$port,$nativeCapture,$nativeIntakeAdapter,$nativeOutcomeAdapter,$nativeMail);
receiver_check('purge_consumed_composition_holds_missing_admission',receiver_denied(fn()=>$nativeWorkflow->prepare($after['closure_id']),'ADMISSION_UNVERIFIED'));
$nativePlan=['closure_id'=>$after['closure_id'],'digest'=>str_repeat('f',64)];
$nativeAbi->approved=['actor'=>$policy->actor(),'action'=>'PURGE','plan_digest'=>$nativePlan['digest'],'approved_at'=>time(),'approval_expires_at'=>time()+1];
$nativeAbi->delaySeconds=2;
receiver_check('purge_immutable_grant_expires_during_io',receiver_denied(fn()=>$nativeBoundary->begin($after['closure_id'],$nativePlan,'PURGE'),'ACTUAL_PURGE_EXACT_APPROVAL_REQUIRED'));
$nativeAbi->delaySeconds=0;
receiver_check('purge_original_global_connection_preserved',$GLOBALS['wpdb']===$wpdb&&!$wpdb->custodyIsActive());
// Positive multi-store purge/expiry and provider fault/race modes remain explicit REQUIRED gates.
