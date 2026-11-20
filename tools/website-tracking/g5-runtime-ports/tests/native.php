<?php
declare(strict_types=1);
/** Prepared only. Synthetic fixture services are NEVER candidate runtime providers. */
$isolation=[
 'cli'=>PHP_SAPI==='cli' && count($argv)===1,
 'non_root'=>function_exists('posix_geteuid') && posix_geteuid()!==0,
 'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
 'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
 'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
 'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
 'readonly_application'=>!is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g5'),
 'database_already_started'=>is_dir('/tmp/database') && file_exists('/tmp/bsre.sock'),
 'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach($isolation as $name=>$ok) if(!$ok) throw new RuntimeException('G5 isolation failed: '.$name);
define('WP_ENVIRONMENT_TYPE','local'); define('BSRE_G5_DURABLE_LAB',true);
require '/opt/wordpress/wp-load.php';
if(DB_NAME!=='bsre_synthetic' || DB_HOST!=='localhost:/tmp/bsre.sock' || DB_USER!=='root' || DB_PASSWORD!=='') throw new RuntimeException('G5_FIXED_DATABASE_REQUIRED');
require __DIR__.'/../ready/plugin/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php';
use BSRE\ActualRetention as A;
use BSRE\ClosedRetention as C;

add_filter('home_url',fn($url,$path)=>'http://bsre.invalid'.($path===''?'':'/'.ltrim($path,'/')),10,2);
$owner=get_user_by('login','synthetic_owner');
if(!$owner) throw new RuntimeException('G5_SYNTHETIC_OWNER_REQUIRED'); wp_set_current_user($owner->ID);
$db=new C\LeaseBoundWpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);
$db->set_prefix('g5_durable_synthetic_'); $db->suppress_errors(true);
$policy=new A\RuntimePolicy('bsre_synthetic','g5_durable_synthetic_','http://bsre.invalid',(int)$owner->ID,true);
$checks=[];
function check(string $name,bool $ok):void { global $checks; $checks[$name]=$ok; file_put_contents('/tmp/g5-native-progress.json',json_encode($checks,JSON_THROW_ON_ERROR)); if(!$ok)throw new RuntimeException('G5 native assertion failed: '.$name); }
function denied(callable $fn,string $code):bool { try{$fn();return false;}catch(Throwable $e){return $e->getMessage()===$code;} }

/** Deliberately synthetic local custody fixture, independent of journal SQL. */
final class SyntheticWitness implements A\AnchorTransport
{
 public array $anchor=['revision'=>0,'hash'=>'0000000000000000000000000000000000000000000000000000000000000000'];
 public bool $wrongChallenge=false; public bool $rejectAdvance=false;
 public function __construct(private string $secret){}
 private function receipt(string $scope,string $challenge,?array $before):array {
  $s=['anchor'=>$this->anchor,'challenge'=>$this->wrongChallenge?str_repeat('0',64):$challenge,'contract'=>'bsre-current-anchor-v1','expires_at'=>time()+30,'issued_at'=>time(),'previous'=>$before,'scope'=>$scope];
  return ['statement'=>$s,'signature'=>base64_encode(sodium_crypto_sign_detached(C\Workflow::digest($s),$this->secret))];
 }
 public function current(string $scope,string $challenge):array{return $this->receipt($scope,$challenge,null);}
 public function advance(string $scope,array $before,array $after,string $challenge):array{
  if($this->rejectAdvance || $before!==$this->anchor || $after['revision']!==$before['revision']+1)throw new RuntimeException('SYNTHETIC_CAS_REJECTED');
  $this->anchor=$after;return $this->receipt($scope,$challenge,$before);
 }
}
final class SyntheticKeys implements A\EncryptionKeys {
 public function activeId():string{return 'synthetic-only';} public function key(string $id):string{if($id!=='synthetic-only')throw new RuntimeException('SYNTHETIC_KEY_MISSING');return str_repeat('k',32);}
}
final class SyntheticEvidence implements A\OperationalEvidence {
 public bool $grant=true; public bool $custody=false; public bool $collection=true;
 public function approved(string $actor,string $action,string $digest,int $now):bool{return $this->grant;}
 public function mailReceipt(string $actor,string $digest,string $id):?array{return null;}
 public function captureCustody(array $closure,array $record,string $request,int $now):bool{return $this->custody;}
 public function collectionCustody(array $target,int $now):bool{return $this->collection;}
 public function retirementCustody(array $record,array $proof,int $now):bool{return false;}
}
final class SyntheticProducer implements A\CaptureProducer {
 public function __construct(private C\LeaseBoundWpdb $db){}
 public function assertCurrent(C\LeaseBoundWpdb $db):void {if($db!==$this->db)throw new RuntimeException('SYNTHETIC_CONNECTION_CHANGED');}
 public function assertPurposeRecord(array $row):void {if($row['purpose_version']!==0)throw new RuntimeException('SYNTHETIC_PURPOSE_V0_ONLY');}
}
$pair=sodium_crypto_sign_keypair(); $witness=new SyntheticWitness(sodium_crypto_sign_secretkey($pair));
$custody=new A\ActualRecoveryCustody($policy->scope(),$witness,new SyntheticKeys(),sodium_crypto_sign_publickey($pair));
$evidence=new SyntheticEvidence(); $authority=new A\OwnerAuthority($policy,$evidence);
$journal=new A\ActualJournal($db,$policy,$custody,$authority,$evidence);
check('unconfigured_authority_held',!(new A\OwnerAuthority($policy))->canApply($policy->actor(),str_repeat('a',64),time(),'PURGE'));
$witness->wrongChallenge=true;check('signed_replay_challenge_rejected',denied(fn()=>$custody->current(),'G5_ANCHOR_AUTHENTICATION_REQUIRED'));$witness->wrongChallenge=false;
$sealed=$custody->seal(['synthetic'=>true],1);check('aead_roundtrip',$custody->open($sealed,1)===['synthetic'=>true]);
check('aead_revision_substitution_rejected',denied(fn()=>$custody->open($sealed,2),'G5_JOURNAL_AUTHENTICATION_FAILED'));
// Fresh image only; never delete/reuse previous tables to make acceptance pass.
check('fresh_fixture_required',(string)$db->get_var("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='g5_durable_synthetic_bsre_g5_journal'")==='0');
$journal->initialize();
$id='00000000-0000-4000-8000-000000000001'; $lead='BSRE-00000000-0000-4000-8000-000000000002';$event='evt_00000000-0000-4000-8000-000000000003';
$closure=['schema_version'=>1,'closure_id'=>$id,'revision'=>1,'status'=>'CLOSED','request_id'=>$id,'lead_id'=>$lead,'event_id'=>$event,
 'accepted_at_utc'=>'2024-01-01T12:00:00Z','closed_at_utc'=>'2024-01-01T13:00:00Z','recorded_at_utc'=>'2024-01-02T12:00:00Z',
 'reviewer'=>$policy->actor(),'evidence_reference'=>'synthetic-closure','evidence_hash'=>str_repeat('a',64),'outcome_ids'=>[],'mail_message_ids'=>['synthetic-message'],'email_status'=>'SENT'];
$evidence->collection=false;
check('owner_approval_cannot_replace_source_custody',denied(fn()=>$journal->locked($id,fn()=>$journal->insertClosure($closure)),'G5_EXACT_COLLECTION_APPROVAL_REQUIRED'));$evidence->collection=true;
$journal->locked($id,function()use($journal,$closure){$journal->insertClosure($closure);});
check('retirement_requires_independent_sender_proof',denied(fn()=>$journal->locked($id,fn()=>$journal->commitRetirement(['plan'=>['closure_id'=>$id,'digest'=>str_repeat('a',64)]],[],time())),'G5_RETIREMENT_CUSTODY_HELD'));
$journal2=new A\ActualJournal($db,$policy,$custody,$authority,$evidence);
$journal2->locked($id,function()use($journal2,$closure){check('new_adapter_reads_durable_closure',$journal2->closure($closure['closure_id'])===$closure);$journal2->markHistoryIncomplete();$journal2->pinAdmissionFloor(str_repeat('b',64));check('durable_history_floor',$journal2->historyIncomplete()&&$journal2->admissionFloor()===str_repeat('b',64));});
$before=$db->get_row('SELECT * FROM g5_durable_synthetic_bsre_g5_journal',ARRAY_A);
$journal2->locked($id,function()use($journal2,$closure){$after=$closure;$after['revision']=2;$after['recorded_at_utc']='2024-01-03T12:00:00Z';$journal2->replaceClosure($closure,$after);});
$newer=$db->get_row('SELECT * FROM g5_durable_synthetic_bsre_g5_journal',ARRAY_A);
$db->query($db->prepare('UPDATE g5_durable_synthetic_bsre_g5_journal SET revision=%d,body_hash=%s,body=%s WHERE id=1',$before['revision'],$before['body_hash'],$before['body']));
check('valid_encrypted_old_snapshot_rejected',denied(fn()=>$journal2->locked($id,fn()=>$journal2->closure($id)),'G5_CURRENT_ANCHOR_MISMATCH'));
$db->query($db->prepare('UPDATE g5_durable_synthetic_bsre_g5_journal SET revision=%d,body_hash=%s,body=%s WHERE id=1',$newer['revision'],$newer['body_hash'],$newer['body']));
$evidence->grant=false;
check('authority_revocation_rechecked',denied(fn()=>$journal2->locked($id,fn()=>$journal2->replaceClosure($closure,$closure)),'G5_EXACT_CLOSURE_APPROVAL_REQUIRED'));$evidence->grant=true;
$actor=$policy->actor();wp_set_current_user(0);check('anonymous_owner_denied',!$authority->canReview($actor));wp_set_current_user($owner->ID);
$db->prefix='wrong_';check('namespace_change_rejected',denied(fn()=>$journal2->locked($id,fn()=>null),'G5_CONNECTION_BINDING_INVALID'));$db->prefix=$policy->prefix;
check('calendar_leap_clamp',BSRE\RetentionReview\RetentionInventory::anniversary(strtotime('2024-02-29T08:00:00Z'))===strtotime('2025-02-28T08:00:00Z'));
check('before_calendar_deadline_held',denied(fn()=>C\Workflow::validateClosureRecord($closure,strtotime('2025-01-01T12:59:59Z'),true),'RETENTION_NOT_DUE'));
C\Workflow::validateClosureRecord($closure,strtotime('2025-01-01T13:00:00Z'),true);check('at_calendar_deadline_due',true);
// Real SQL capture table, synthetic producer boundary; full G2 producer acceptance is separate.
$reflection=new ReflectionClass(A\ActualCaptureResource::class);$schema=$reflection->getConstant('SCHEMA')+$reflection->getConstant('PURPOSE_SCHEMA');
$defs=[];$row=[];
foreach($schema as $field=>$type){$defs[]=$field.' '.$type.($field==='purpose_json'?' NULL':' NOT NULL');$row[$field]=str_ends_with($type,' unsigned')?0:'';}
$defs[]='PRIMARY KEY(request_id)';$defs[]='KEY subject_revision(subject_key,original_revision)';$defs[]='KEY lead_id(lead_id)';
check('capture_table_created',$db->query('CREATE TABLE g5_durable_synthetic_bsre_consent_captures ('.implode(',',$defs).') ENGINE=InnoDB')!==false);
$row=array_replace($row,['request_id'=>$id,'fingerprint'=>str_repeat('c',64),'decision_version'=>str_repeat('d',32),'notice_version'=>'synthetic-v1','created_at'=>strtotime('2024-01-01T12:00:00Z'),'state'=>'ACCEPTED','click_capture_state'=>'NOT_PERMITTED','lead_id'=>$lead,'event_id'=>$event,'purpose_json'=>null]);
check('capture_fixture_inserted',$db->insert('g5_durable_synthetic_bsre_consent_captures',$row)!==false);
$capture=new A\ActualCaptureResource($db,$journal2,$policy,new SyntheticProducer($db));
$binding=$journal2->locked($id,fn()=>$capture->read($id));check('actual_sql_capture_read',$binding!==null&&$binding['lead_id']===$lead&&$binding['event_id']===$event);
check('capture_without_durable_intent_held',denied(fn()=>$journal2->locked($id,fn()=>$capture->removeExact($binding)),'G5_CAPTURE_CUSTODY_HELD'));
$journal2->locked($id,function()use($journal2,$id,$binding){
 $c=$journal2->closure($id);$p=['schema_version'=>1,'closure_id'=>$id,'closure_hash'=>C\Workflow::digest($c),'admission_hash'=>str_repeat('b',64),'created_at'=>time(),'expires_at'=>time()+900,'resources'=>[['store'=>'capture','binding'=>$binding]]];$p['digest']=C\Workflow::digest($p);
 $r=['plan'=>$p,'revision'=>0,'state'=>'APPLYING','started_at'=>time(),'completed_at'=>null,'steps'=>['INTENT_RECORDED'],'intent_at'=>[time()],'code'=>''];$journal2->save($r);
 check('durable_capture_intent_readback',$journal2->journal($p['digest'])===$r);
});
check('missing_receiver_proof_still_held',denied(fn()=>$journal2->locked($id,fn()=>$capture->removeExact($binding)),'G5_CAPTURE_CUSTODY_HELD'));
$evidence->custody=true;
$db->update('g5_durable_synthetic_bsre_consent_captures',['fingerprint'=>str_repeat('f',64)],['request_id'=>$id]);
$newBinding=$journal2->locked($id,fn()=>$capture->read($id));
check('changed_row_readback_has_new_binding',$newBinding!==$binding&&$newBinding['fingerprint']===str_repeat('f',64));
check('approved_old_binding_cannot_delete_new_row',denied(fn()=>$journal2->locked($id,fn()=>$capture->removeExact($newBinding)),'G5_CAPTURE_APPROVAL_BINDING_CHANGED'));
check('approval_mismatch_preserves_new_row',$journal2->locked($id,fn()=>$capture->read($id))===$newBinding);
$db->update('g5_durable_synthetic_bsre_consent_captures',['fingerprint'=>str_repeat('c',64)],['request_id'=>$id]);
$changed=$binding;$changed['evidence_hash']=str_repeat('f',64);
check('changed_exact_binding_rollback',denied(fn()=>$journal2->locked($id,fn()=>$capture->removeExact($changed)),'CAPTURE_BINDING_CHANGED'));
check('rollback_preserves_exact_row',$journal2->locked($id,fn()=>$capture->read($id))===$binding);
$journal2->locked($id,fn()=>$capture->removeExact($binding));
check('actual_sql_exact_capture_delete_readback',$journal2->locked($id,fn()=>$capture->read($id))===null);
// Lost independent custody acknowledgement after durable SQL must hold, never retry mutation.
$witness->rejectAdvance=true;
check('admission_floor_cannot_be_replaced',denied(fn()=>$journal2->locked($id,fn()=>$journal2->pinAdmissionFloor(str_repeat('e',64))),'G5_ADMISSION_FLOOR_CONFLICT'));
$journal3=new A\ActualJournal($db,$policy,$custody,$authority,$evidence);
$probe=$closure;$probe['closure_id']=$probe['request_id']='00000000-0000-4000-8000-000000000004';$probe['lead_id']='BSRE-00000000-0000-4000-8000-000000000005';$probe['event_id']='evt_00000000-0000-4000-8000-000000000006';$probe['mail_message_ids']=['synthetic-message-2'];
check('independent_service_failure_holds_after_commit',denied(fn()=>$journal3->locked($probe['closure_id'],fn()=>$journal3->insertClosure($probe)), 'G5_COMMIT_OR_CUSTODY_UNCERTAIN'));
$fresh=new A\ActualJournal($db,$policy,$custody,$authority,$evidence);
check('new_instance_cannot_bypass_anchor_gap',denied(fn()=>$fresh->locked($id,fn()=>$fresh->closure($id)),'G5_CURRENT_ANCHOR_MISMATCH'));
echo json_encode(['phase'=>'g5_durable_ports','status'=>'SYNTHETIC_NATIVE_ONLY','checks'=>$checks,'runtime_isolation'=>$isolation,'actual_provider_accepted'=>false,'production_authorized'=>false],JSON_THROW_ON_ERROR)."\n";
