<?php
declare(strict_types=1);
/** Prepared fixed synthetic extension only. The builder supplies the receiver bootstrap. */
use BSRE\ActualRetention as A;
use BSRE\ClosedRetention as C;
use BSRE\SharedRepository as G;
use BSRE\ActualRetention\PreferenceV1 as HV;
use BSRE\ActualRetention\HistoryLocalV1 as HL;

require_once '/opt/lab/g39-history-local/preference/ActualPreferenceRetention.php';
require_once '/opt/lab/g39-history-local/history/LocalHistoryObserver.php';

function g39_fixed():void {
 global $wpdb;
 if(PHP_SAPI!=='cli'||WP_ENVIRONMENT_TYPE!=='local'||DB_NAME!=='bsre_synthetic'||
    DB_HOST!=='localhost:/tmp/bsre.sock'||DB_USER!=='root'||DB_PASSWORD!==''||
    get_class($wpdb)!=='BSRE\\ClosedRetention\\LeaseBoundWpdb'||$wpdb->prefix!=='g39_history_synthetic_'||
    !defined('BSRE_G5_PREFERENCE_RUNTIME_ENABLED')||BSRE_G5_PREFERENCE_RUNTIME_ENABLED!==true||
    !defined('BSRE_G5_PREFERENCE_SOURCE_SHA256')||
    is_writable('/opt/wordpress')||is_writable('/opt/lab/g36')||is_writable('/opt/lab/g39-history-local')||
    realpath(__DIR__)!=='/opt/lab/g39-history-local/tests')throw new RuntimeException('G39_FIXED_SYNTHETIC_FIXTURE_REQUIRED');
}

/** Published RFC8032 material is synthetic fixture data, never an enrolled provider. */
final class G39HistoryKeys implements HV\SnapshotKeys {
 public function activeId():string {g39_fixed();return 'g39-published-synthetic-ledger';}
 public function key(string $id):string {g39_fixed();if($id!==$this->activeId())throw new RuntimeException('G39_SYNTHETIC_KEY_ABSENT');return str_repeat('L',32);}
}

/** Minimal signed CURRENT/INITIALIZE/CAS service. No coverage, retirement or export API. */
final class G39HistoryServices implements HV\SignedTransport,HV\IndependentKeys {
 public array $anchors=[];public array $readScopes=[];public int $mutableCalls=0;
 public bool $badSignature=false;public bool $observing=false;public array $connectionIds=[];public bool $reconnectGuardsVerified=false;
 private array $policies=[];
 public function __construct(private A\RuntimePolicy $base,private string $source,private C\LeaseBoundWpdb $db){
  g39_fixed();for($i=0;$i<256;$i++){$p=new HV\Policy($base,$source,sprintf('%02x',$i));$this->policies[$p->scope()]=$p;}
 }
 public function publicKey(string $service,string $keyId):string {
  g39_fixed();if(!in_array($service,['preference-anchor','owner-approval'],true)||$keyId!=='g39-rfc8032')throw new RuntimeException('G39_SYNTHETIC_SIGNER_ABSENT');
  return hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a');
 }
 private function approval(array $request):string {
  $p=$request['payload'];$a=$p['authorization']??null;
  if(!is_array($a))throw new RuntimeException('G39_SYNTHETIC_INITIALIZE_APPROVAL_REQUIRED');
  HV\Guard::keys($a,['action','plan_hash','authorized_until','approval']);$e=$a['approval'];
  if(!is_array($e))throw new RuntimeException('G39_SYNTHETIC_INITIALIZE_APPROVAL_REQUIRED');
  HV\Guard::keys($e,['key_id','statement','signature']);$s=$e['statement'];$sig=base64_decode($e['signature'],true);
  $digest=HV\Guard::digest(['initialize'=>$request['scope']]);
  if(!is_array($s)||$e['key_id']!=='g39-rfc8032'||!is_string($sig)||strlen($sig)!==64||
     !sodium_crypto_sign_verify_detached($sig,C\Workflow::digest($s),$this->publicKey('owner-approval','g39-rfc8032'))||
     $s['contract']!==$request['contract']||$s['service']!=='owner-approval'||$s['operation']!=='APPROVE'||
     $s['scope']!==$request['scope']||$s['source']!==$request['source']||$s['actor']!==$request['actor']||
     $a['action']!=='INITIALIZE'||$a['plan_hash']!==$digest||
     !is_int($a['authorized_until'])||$a['authorized_until']<=time()||
     $s['claims']!==['approved'=>true,'action'=>'INITIALIZE','plan_hash'=>$digest,'expires_at'=>$a['authorized_until']]||
     $s['expires_at']<=time()||$p['authorized_until']!==$a['authorized_until'])throw new RuntimeException('G39_SYNTHETIC_INITIALIZE_APPROVAL_REQUIRED');
  return C\Workflow::digest($a);
 }
 public function exchange(string $operation,array $request):string {
  g39_fixed();HV\Guard::keys($request,['contract','service','operation','scope','source','actor','challenge','payload']);
  $binding=$this->policies[$request['scope']]??null;
  if(!$binding instanceof HV\Policy||$request['contract']!==HV\Policy::CONTRACT||$request['operation']!==$operation||
     $request['source']!==$binding->source()||$request['actor']!==$binding->actor())throw new RuntimeException('G39_SYNTHETIC_REQUEST_SCOPE_CONFLICT');
  $p=$request['payload'];$service=$request['service'];$claims=null;$authorizationHash=null;
  if($service==='preference-anchor'&&$operation==='CURRENT'){
   if($p!==[])throw new RuntimeException('G39_SYNTHETIC_CURRENT_PAYLOAD_INVALID');
   if($this->observing){
    $id=$this->db->custodyConnectionId();
    if(!$this->db->custodyIsActive()||$id===null||
       (string)$this->db->get_var('SELECT CONNECTION_ID()')!==$id||
       (string)$this->db->get_var('SELECT @@session.in_transaction')!=='1'||
       (string)$this->db->get_var('SELECT @@session.tx_isolation')!=='REPEATABLE-READ'||
       (string)$this->db->get_var('SELECT @@session.tx_read_only')!=='1')throw new RuntimeException('G39_SYNTHETIC_PARENT_READONLY_TRANSACTION_REQUIRED');
    if(!$this->reconnectGuardsVerified){
     if($this->db->check_connection(false)!==false||$this->db->db_connect(false)!==false||
        (string)$this->db->get_var('SELECT CONNECTION_ID()')!==$id)throw new RuntimeException('G39_SYNTHETIC_RECONNECT_NOT_REFUSED');
     $this->reconnectGuardsVerified=true;
    }
    $this->connectionIds[$id]=true;$this->readScopes[$request['scope']]=($this->readScopes[$request['scope']]??0)+1;
   }
   $claims=['anchor'=>$this->anchors[$request['scope']]??HV\Custody::zero()];
  }elseif($service==='owner-approval'&&$operation==='APPROVE'){
   HV\Guard::keys($p,['action','plan_hash','expires_at']);
   if($this->observing||$binding->partition!=='aa'||$p['action']!=='INITIALIZE'||
      $p['plan_hash']!==HV\Guard::digest(['initialize'=>$request['scope']])||!is_int($p['expires_at'])||
      $p['expires_at']<=time()||$p['expires_at']>time()+30)throw new RuntimeException('G39_SYNTHETIC_ONLY_INITIALIZER_ALLOWED');
   $claims=['approved'=>true,'action'=>$p['action'],'plan_hash'=>$p['plan_hash'],'expires_at'=>$p['expires_at']];
  }elseif($service==='preference-anchor'&&$operation==='COMPARE_AND_SWAP'){
   if($this->observing||$binding->partition!=='aa')throw new RuntimeException('G39_SYNTHETIC_OBSERVE_MUTATION_DENIED');
   HV\Guard::keys($p,['before','after','operation','authorized_until','authorization']);
   $authorizationHash=$this->approval($request);HV\Custody::anchor($p['before']);HV\Custody::anchor($p['after']);
   $actual=$this->anchors[$request['scope']]??HV\Custody::zero();
   if($p['before']!==HV\Custody::zero()||$actual!==$p['before']||$p['after']['operation_revision']!==1||
      $p['after']['sequence']!==0||$p['after']['floor_generation']!==0)throw new RuntimeException('G39_SYNTHETIC_INITIALIZE_CAS_CONFLICT');
   $this->anchors[$request['scope']]=$p['after'];$this->mutableCalls++;
   $claims=['before'=>$p['before'],'after'=>$p['after'],'operation'=>$p['operation'],'durable'=>true,'authorized_until'=>$p['authorized_until']];
  }
  if(!is_array($claims))throw new RuntimeException('G39_SYNTHETIC_OPERATION_UNSUPPORTED');
  if($authorizationHash!==null)$claims['authorization_hash']=$authorizationHash;
  $issued=time();$s=['contract'=>$request['contract'],'service'=>$service,'operation'=>$operation,'scope'=>$request['scope'],
   'source'=>$request['source'],'actor'=>$request['actor'],'challenge'=>$request['challenge'],'request_hash'=>C\Workflow::digest($request),
   'issued_at'=>$issued,'expires_at'=>$issued+30,'claims'=>$claims];
  $sig=$this->badSignature?str_repeat('x',64):sodium_crypto_sign_detached(C\Workflow::digest($s),receiver_test_secret());
  return json_encode(['key_id'=>'g39-rfc8032','statement'=>$s,'signature'=>base64_encode($sig)],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
 }
}

/** Fixed local synthetic readback. It asserts no genuine operational enrollment. */
final class G39HistoryAdmission implements C\Admission {
 public string $mode='current';public int $calls=0;
 public function __construct(private array $descriptor,private A\CanonicalCaptureProducer $producer,private C\LeaseBoundWpdb $db){}
 public function readback(int $now):?array {
  g39_fixed();$this->producer->assertCurrent($this->db);$this->calls++;$at=time();
  if($this->mode==='stale')$at-=301;elseif($this->mode==='future')$at+=10;
  return ['wp'=>$this->descriptor+['routes_installed'=>true,'store_installed'=>true],'receiver'=>$this->descriptor,
   'source_hashes'=>['wp'=>hash('sha256','SYNTHETIC_G39_WP_ADMISSION'),'receiver'=>hash('sha256','SYNTHETIC_G39_RECEIVER_ADMISSION')],
   'restore_policy_hash'=>hash('sha256','SYNTHETIC_G39_LOCAL_RESTORE_POLICY'),
   'evidence_reference'=>'SYNTHETIC_G39_LOCAL_ADMISSION_ONLY','evidence_hash'=>hash('sha256','SYNTHETIC_G39_LOCAL_ADMISSION_BYTES'),
   'observed_at'=>$at,'expires_at'=>$at+300];
 }
}

/** Private comparison hash, never emitted as rows or identifiers. */
function g39_storage_hash():string {
 global $wpdb;$tables=['bsre_g5_journal'=>'id','bsre_pref_runtime'=>'id','bsre_pref_audit'=>'operation_id',
  'bsre_consent_state'=>'subject_key','bsre_consent_history'=>'receipt','bsre_consent_captures'=>'request_id'];$hashes=[];
 foreach($tables as $suffix=>$order){$wpdb->last_error='';$rows=$wpdb->get_results("SELECT * FROM {$wpdb->prefix}{$suffix} ORDER BY {$order} LIMIT 1002",ARRAY_A);
  if($wpdb->last_error!==''||!is_array($rows)||count($rows)>1001)throw new RuntimeException('G39_SYNTHETIC_COMPARISON_UNAVAILABLE');
  $hashes[$suffix]=hash('sha256',json_encode($rows,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES));}
 return C\Workflow::digest($hashes);
}

/** Server READ ONLY plus before/after comparisons; canonical hook inventory stays exact. */
function g39_observation_attempt(callable $call,G39HistoryServices $services):mixed {
 global $wpdb;$before=g39_storage_hash();$anchors=$services->anchors;$mutations=$services->mutableCalls;
 $readonly=(string)$wpdb->get_var('SELECT @@session.tx_read_only');
 if($wpdb->custodyIsActive()||(string)$wpdb->get_var('SELECT @@session.in_transaction')!=='0')throw new RuntimeException('G39_SYNTHETIC_FRESH_ATTEMPT_REQUIRED');
 $services->readScopes=[];$services->connectionIds=[];$services->observing=true;
 try{return$call();}finally{
  $services->observing=false;
  if($before!==g39_storage_hash()||$anchors!==$services->anchors||$mutations!==$services->mutableCalls)throw new RuntimeException('G39_SYNTHETIC_OBSERVE_CHANGED_STORAGE');
  if($wpdb->custodyIsActive()||(string)$wpdb->get_var('SELECT @@session.in_transaction')!=='0'||
     (string)$wpdb->get_var('SELECT @@session.tx_read_only')!==$readonly)throw new RuntimeException('G39_SYNTHETIC_OBSERVE_CLEANUP_FAILED');
 }
}

g39_fixed();
$journal=new A\ActualReceiverJournal($wpdb,$policy,$custody,$authority,$evidence,$proof,$producer);
receiver_check('g39_journal_unapproved_initializer_denied',receiver_denied(fn()=>$journal->initialize(),'G5_EXACT_APPROVAL_REQUIRED'));
$review->allow('INITIALIZE_JOURNAL',C\Workflow::digest(['scope'=>$policy->scope(),'operation'=>'INITIALIZE_JOURNAL','schema'=>1]));$journal->initialize();
$historyKeys=new G39HistoryKeys();$historySource=BSRE_G5_PREFERENCE_SOURCE_SHA256;
$historyServices=new G39HistoryServices($policy,$historySource,$wpdb);$historyPolicy=new HV\Policy($policy,$historySource,'aa');
$historyRuntime=A\ActualPreferenceRetention::bind($wpdb,$policy,$historySource,'aa',$historyServices,$historyServices,$historyKeys);
$initializeDigest=HV\Guard::digest(['initialize'=>$historyPolicy->scope()]);
$historyRuntime->initialize(wp_create_nonce('bsre-pref-v1|'.$historyPolicy->scope().'|INITIALIZE|'.$initializeDigest));
receiver_check('g39_real_preference_initializer_seeds_one_partition',
 (string)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_pref_runtime")==='1'&&
 (string)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa' AND status='READY'")==='1'&&
 $historyServices->mutableCalls===1&&!$wpdb->custodyIsActive());
$historyAdmission=new G39HistoryAdmission($descriptor,$producer,$wpdb);
$historyLedgerPath=__DIR__.'/synthetic-ledger.json';$historyLedgerBytes=file_get_contents($historyLedgerPath);
if(!is_string($historyLedgerBytes))throw new RuntimeException('G39_SYNTHETIC_LEDGER_MISSING');$historyLedgerSha=hash('sha256',$historyLedgerBytes);
$historyLease='00000000-0000-4000-8000-000000000039';
$makeHistoryObserver=static fn(?A\RuntimePolicy $base=null,?string $source=null,?string $ledgerSha=null)=>new HL\LocalHistoryObserver(
 $wpdb,$base??$policy,$producer,$journal,$source??$historySource,$historyServices,$historyServices,$historyKeys,$historyAdmission,$historyLedgerPath,$ledgerSha??$historyLedgerSha);
$historyObserver=$makeHistoryObserver();
$observeHistory=static fn()=>g39_observation_attempt(fn()=>$historyObserver->observe($historyLease),$historyServices);
$historyCheckpoint=$observeHistory();
$partitionNames=array_map(static fn(int $i):string=>sprintf('%02x',$i),range(0,255));
receiver_check('g39_all_256_partitions_observed_in_order',count($historyCheckpoint['partitions'])===256&&array_column($historyCheckpoint['partitions'],'partition')===$partitionNames&&count($historyServices->readScopes)===256);
receiver_check('g39_physical_control_inventory_exact',$historyCheckpoint['control_inventory']===['aa']);
receiver_check('g39_exact_one_anchored_and_255_absent_partitions',
 count(array_filter($historyCheckpoint['partitions'],static fn(array $p):bool=>$p['observation']==='ANCHORED_LEDGER'&&$p['partition']==='aa'))===1&&
 count(array_filter($historyCheckpoint['partitions'],static fn(array $p):bool=>$p['observation']==='ZERO_ANCHOR_AND_PHYSICAL_ABSENCE'&&$p['anchor']===HV\Custody::zero()&&$p['body_sha256']===null))===255);
receiver_check('g39_one_canonical_connection_for_every_signed_current',count($historyServices->connectionIds)===1&&isset($historyServices->connectionIds[(string)$historyCheckpoint['connection_id']]));
receiver_check('g39_reconnect_entrypoints_refused_under_parent_custody',$historyServices->reconnectGuardsVerified);
receiver_check('g39_exact_readonly_ledger_bytes_bound',$historyCheckpoint['inputs']['ledger_sha256']===$historyLedgerSha&&$historyCheckpoint['inputs']['ledger_bytes']===strlen($historyLedgerBytes)&&!is_writable($historyLedgerPath));
receiver_check('g39_current_admission_and_local_scope_only',$historyAdmission->calls>=2&&$historyCheckpoint['schema']==='bsre-g39-local-history-observation-v1'&&$historyCheckpoint['authority']==='LOCAL_OBSERVATION_ONLY'&&$historyCheckpoint['local_vetoes']===[]&&
 $historyCheckpoint['unresolved_authority']===HL\LocalHistoryObserver::UNRESOLVED&&count($historyCheckpoint['unresolved_authority'])===3&&
 !array_key_exists('history_marker_verified',$historyCheckpoint)&&!array_key_exists('whole_history_complete',$historyCheckpoint)&&!array_key_exists('eligible_exports',$historyCheckpoint));
receiver_check('g39_no_observation_storage_or_anchor_writes',$historyServices->mutableCalls===1);
receiver_check('g39_no_custody_or_transaction_after_success',!$wpdb->custodyIsActive()&&(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0');

// Clock predicate only: this altered copy is not claimed to retain its original signature validity.
$agedRetainedProof=$historyCheckpoint['partitions'][0]['proofs'][0];$retainedProofClock=time();
$agedRetainedProof['statement']['issued_at']=$retainedProofClock-31;$agedRetainedProof['statement']['expires_at']=$retainedProofClock+29;
receiver_check('g39_retained_proof_31s_old_unexpired_clock_denied',receiver_denied(fn()=>HL\LocalHistoryObserver::retainedProofDeadline($agedRetainedProof,$retainedProofClock),'G39_OBSERVATION_PROOF_STALE'));

$historyProofs=new HV\Proofs($historyPolicy,$historyServices,$historyServices);$historyCrypto=new HV\Custody($historyPolicy,$historyProofs,$historyKeys);
$historyBorrowStore=new HV\AtomicStore($wpdb,$historyPolicy,$producer,$historyCrypto,$historyProofs);
receiver_check('g39_borrow_without_parent_denied',receiver_denied(fn()=>$historyBorrowStore->observeBorrowedHistory(),'G39_BORROWED_CUSTODY_REQUIRED'));

// Physical control inventory must reject malformed IDs before reading any partition anchor.
$beforeInvalidControl=g39_storage_hash();$invalidControlDenied=false;$invalidControlReadScopes=null;
if($wpdb->query("INSERT INTO {$wpdb->prefix}bsre_pref_runtime (id,operation_revision,body_hash,body,status,operation_id,before_anchor,after_anchor) SELECT 'gg',operation_revision,body_hash,body,status,operation_id,before_anchor,after_anchor FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'")!==1)throw new RuntimeException('G39_SYNTHETIC_INVALID_CONTROL_SEED_FAILED');
try{
 $invalidControlDenied=receiver_denied($observeHistory,'G39_PREFERENCE_CONTROL_DOMAIN_INVALID');$invalidControlReadScopes=$historyServices->readScopes;
}finally{
 if($wpdb->query("DELETE FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='gg'")!==1||g39_storage_hash()!==$beforeInvalidControl)throw new RuntimeException('G39_SYNTHETIC_INVALID_CONTROL_RESTORE_FAILED');
}
receiver_check('g39_out_of_domain_physical_control_row_denied',$invalidControlDenied&&$invalidControlReadScopes===[]);

$absentPolicy=new HV\Policy($policy,$historySource,'ab');$historyServices->anchors[$absentPolicy->scope()]=$historyServices->anchors[$historyPolicy->scope()];
receiver_check('g39_nonzero_signed_anchor_and_absent_row_denied',receiver_denied($observeHistory,'G39_PREFERENCE_ABSENT_ANCHOR_CONFLICT'));
unset($historyServices->anchors[$absentPolicy->scope()]);
$historyServices->badSignature=true;receiver_check('g39_forged_signed_anchor_denied',receiver_denied($observeHistory,'PREFERENCE_AUTHENTICATED_PROOF_REQUIRED'));$historyServices->badSignature=false;
receiver_check('g39_changed_expected_ledger_bytes_denied',receiver_denied(fn()=>g39_observation_attempt(fn()=>$makeHistoryObserver(null,null,str_repeat('f',64))->observe($historyLease),$historyServices),'G39_LEDGER_BYTES_CHANGED'));
$historyAdmission->mode='stale';receiver_check('g39_stale_admission_denied',receiver_denied($observeHistory,'ADMISSION_STALE'));
$historyAdmission->mode='future';receiver_check('g39_future_admission_denied',receiver_denied($observeHistory,'ADMISSION_STALE'));$historyAdmission->mode='current';
receiver_check('g39_changed_source_binding_denied',receiver_denied(fn()=>g39_observation_attempt(fn()=>$makeHistoryObserver(null,str_repeat('f',64))->observe($historyLease),$historyServices)));
$foreignHistoryPolicy=new A\RuntimePolicy(DB_NAME,'g39_foreign_synthetic_','https://blackswanrealestate.ae',(int)$owner->ID);
receiver_check('g39_foreign_base_scope_denied',receiver_denied(fn()=>g39_observation_attempt(fn()=>$makeHistoryObserver($foreignHistoryPolicy)->observe($historyLease),$historyServices)));
wp_set_current_user(0);receiver_check('g39_revoked_owner_denied',receiver_denied($observeHistory));wp_set_current_user($owner->ID);
$wpdb->save_queries=true;receiver_check('g39_query_logging_denied',receiver_denied($observeHistory));$wpdb->save_queries=false;

/** Authenticated synthetic compacted floor injection, not a claim of actual historical retirement. */
$savedHistoryRow=$wpdb->get_row("SELECT * FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'",ARRAY_A);
$savedHistoryAnchor=$historyServices->anchors[$historyPolicy->scope()];
$floorState=$historyCrypto->open($savedHistoryRow['body'],(int)$savedHistoryRow['operation_revision']);
$syntheticFloor=['sequence'=>1,'hash'=>hash('sha256','SYNTHETIC_G39_COMPACTED_FLOOR'),'generation'=>1,'compacted_at'=>time()-1];
$floorState['ledger']=HV\Algebra::validate(['anchor'=>['sequence'=>1,'hash'=>$syntheticFloor['hash']],'floor'=>$syntheticFloor,'rows'=>[]]);
$floorBody=$historyCrypto->seal($floorState,(int)$savedHistoryRow['operation_revision']);
$floorBefore=json_decode($savedHistoryRow['before_anchor'],true,48,JSON_THROW_ON_ERROR);
$floorAfter=HV\Custody::next($floorBefore,$floorState['ledger'],hash('sha256',$floorBody));
if($wpdb->query($wpdb->prepare("UPDATE {$wpdb->prefix}bsre_pref_runtime SET body_hash=%s,body=%s,after_anchor=%s WHERE id='aa'",hash('sha256',$floorBody),$floorBody,json_encode($floorAfter,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)))!==1)throw new RuntimeException('G39_SYNTHETIC_FLOOR_SEED_FAILED');
$historyServices->anchors[$historyPolicy->scope()]=$floorAfter;$floorCheckpoint=$observeHistory();
receiver_check('g39_compacted_floor_retains_local_veto',in_array('PREFERENCE_COMPACTED_HISTORY:aa',$floorCheckpoint['local_vetoes'],true)&&$floorCheckpoint['authority']==='LOCAL_OBSERVATION_ONLY'&&!array_key_exists('history_marker_verified',$floorCheckpoint));
if($wpdb->query($wpdb->prepare("UPDATE {$wpdb->prefix}bsre_pref_runtime SET body_hash=%s,body=%s,after_anchor=%s WHERE id='aa'",$savedHistoryRow['body_hash'],$savedHistoryRow['body'],$savedHistoryRow['after_anchor']))!==1)throw new RuntimeException('G39_SYNTHETIC_FLOOR_RESTORE_FAILED');
$historyServices->anchors[$historyPolicy->scope()]=$savedHistoryAnchor;

// Irreversible submitted-history marker is last; observation must expose its veto.
$journal->locked($historyLease,fn()=>$journal->markHistoryIncomplete());$incompleteCheckpoint=$observeHistory();
receiver_check('g39_submitted_incomplete_retains_local_veto',in_array('SUBMITTED_JOURNAL_INCOMPLETE',$incompleteCheckpoint['local_vetoes'],true)&&$incompleteCheckpoint['journal']['incomplete']===true&&$incompleteCheckpoint['authority']==='LOCAL_OBSERVATION_ONLY');
$producer->assertCurrent($wpdb);
receiver_check('g39_original_connection_and_clean_lease_preserved',!$wpdb->custodyIsActive()&&(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0'&&$GLOBALS['wpdb']===$wpdb&&G\repository()->database()===$wpdb);
receiver_check('g39_network_and_mail_never_called',$networkCalls===0&&$mailCalls===0);
