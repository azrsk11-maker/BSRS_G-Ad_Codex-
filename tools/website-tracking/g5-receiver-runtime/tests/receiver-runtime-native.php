<?php
declare(strict_types=1);
/** Prepared fixed synthetic lab only. This is not an installed operational provider. */
$isolation=[
 'cli'=>PHP_SAPI==='cli'&&count($argv)===1,
 'non_root'=>function_exists('posix_geteuid')&&posix_geteuid()!==0,
 'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
 'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
 'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
 'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
 'readonly_application'=>!is_writable('/opt/wordpress')&&!is_writable('/opt/reviewed')&&!is_writable('/opt/lab/g36')&&!is_writable('/opt/lab/g5-receiver-runtime'),
 'database_already_started'=>is_dir('/tmp/database')&&file_exists('/tmp/bsre.sock'),
 'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach($isolation as $pass)if(!$pass)throw new RuntimeException('G5_RECEIVER_FIXED_ISOLATION_REQUIRED');
define('WP_ENVIRONMENT_TYPE','local');define('WP_CONTENT_DIR','/opt/lab/g36/wp-content');define('WP_PLUGIN_DIR',WP_CONTENT_DIR.'/plugins');
define('BSRE_CANONICAL_LEASE_ENABLED',true);define('BSRE_G3_ROUTE_CONTEXT_ENABLED',true);define('BSRE_G2_SHARED_REPOSITORY_ENABLED',true);
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);define('BSRE_RETENTION_ADMISSION_ENABLED',true);
define('BSRE_RETENTION_ADMISSION_GENERATION',str_repeat('a',64));define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',strtotime('2022-01-01T00:00:00Z'));
define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET','synthetic-secret-never-production-0000');define('BSRE_ROUTING_ENABLED',true);
define('BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED',true);
$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='GET';$_SERVER['REQUEST_URI']='/';
require '/opt/wordpress/wp-load.php';require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
use BSRE\ActualRetention as A;use BSRE\ClosedRetention as C;use BSRE\ActualRetention\ReceiverV1 as R;
use BSRE\Enquiries as E;use BSRE\SharedRepository as G;
if(DB_NAME!=='bsre_synthetic'||DB_HOST!=='localhost:/tmp/bsre.sock'||DB_USER!=='root'||DB_PASSWORD!==''||$wpdb->get_var('SELECT DATABASE()')!=='bsre_synthetic')throw new RuntimeException('G5_RECEIVER_FIXED_DATABASE_REQUIRED');
if(realpath(__DIR__)!=='/opt/lab/g5-receiver-runtime/tests')throw new RuntimeException('G5_RECEIVER_FIXED_DRIVER_REQUIRED');
require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/candidate/recovery/ActualRecoveryCustody.php';
require_once '/opt/lab/g5-receiver-runtime/candidate/plugin/includes/candidate/receiver/ActualReceiverWorkflow.php';
add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
$networkCalls=0;$mailCalls=0;
add_filter('pre_http_request',function()use(&$networkCalls){$networkCalls++;throw new RuntimeException('G5_RECEIVER_NETWORK_FORBIDDEN');},PHP_INT_MAX);
add_filter('pre_wp_mail',function()use(&$mailCalls){$mailCalls++;throw new RuntimeException('G5_RECEIVER_MAIL_FORBIDDEN');},PHP_INT_MAX);
$owner=get_user_by('login','synthetic_owner');if(!$owner instanceof WP_User)throw new RuntimeException('G5_RECEIVER_FIXED_OWNER_REQUIRED');wp_set_current_user($owner->ID);
$privacy=get_page_by_path('g36-synthetic-privacy-hub',OBJECT,'page');
if(!$privacy instanceof WP_Post||$privacy->post_status!=='publish'||$privacy->post_title!=='SYNTHETIC G36 NOTICE')throw new RuntimeException('G5_RECEIVER_PREDECESSOR_NOTICE_REQUIRED');
define('BSRE_PRIVACY_NOTICE_PAGE_ID',(int)$privacy->ID);
$wpdb->prefix='g5_receiver_synthetic_';E\install();if(!G\migrate())throw new RuntimeException('G5_RECEIVER_MIGRATION_REQUIRED');
$producer=new A\CanonicalCaptureProducer($wpdb);$producer->assertCurrent($wpdb);
$checks=[];$progress='/tmp/g5-receiver-runtime-progress.json';
if(file_exists($progress)||is_link($progress))throw new RuntimeException('G5_RECEIVER_FRESH_PROGRESS_REQUIRED');
function receiver_check(string $name,bool $pass):void{global $checks,$progress;if(array_key_exists($name,$checks))throw new RuntimeException('G5_RECEIVER_DUPLICATE_CHECK');$checks[$name]=$pass;$raw=json_encode($checks,JSON_THROW_ON_ERROR);if(file_put_contents($progress,$raw,LOCK_EX)!==strlen($raw))throw new RuntimeException('G5_RECEIVER_PROGRESS_UNAVAILABLE');if(!$pass)throw new RuntimeException('G5_RECEIVER_NATIVE_ASSERTION_FAILED:'.$name);}
function receiver_denied(callable $work,?string $code=null):bool{try{$work();return false;}catch(Throwable $e){return $code===null||$e->getMessage()===$code;}}
$bridge=proc_open(['node','/opt/lab/g5-receiver-runtime/tests/native-bridge.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes,null,['BSRE_RECEIVER_TEST_SOURCE_ROOT'=>'/opt/lab/g36-source/']);
if(!is_resource($bridge))throw new RuntimeException('G5_RECEIVER_BRIDGE_UNAVAILABLE');stream_set_timeout($pipes[1],10);
function receiver_bridge(array $message):array{global $pipes;$raw=json_encode($message,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)."\n";if(fwrite($pipes[0],$raw)!==strlen($raw)||!fflush($pipes[0]))throw new RuntimeException('G5_RECEIVER_BRIDGE_WRITE_FAILED');$line=fgets($pipes[1],2100000);if(!is_string($line)||!str_ends_with($line,"\n"))throw new RuntimeException('G5_RECEIVER_BRIDGE_READ_FAILED');$v=json_decode($line,true,48,JSON_THROW_ON_ERROR);if(!is_array($v)||($v['ok']??null)!==true||!is_array($v['value']??null))throw new RuntimeException('G5_RECEIVER_BRIDGE_HELD');return $v['value'];}
/** Published RFC8032 vectors imported as fixture bytes, never generated or enrolled. */
function receiver_test_secret():string{return hex2bin('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a');}
final class ReceiverNativeKeys implements R\IndependentKeys{public bool $present=true;public function publicKey(string $service,string $id):string{if(!$this->present||$service!==R\ReceiverPolicy::SERVICE||$id!=='synthetic-rfc8032')throw new RuntimeException('SYNTHETIC_SIGNER_ABSENT');return hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a');}}
final class ReceiverNativeControl implements R\ControlTransport{public int $calls=0;public bool $forge=false;public int $delaySeconds=0;public function exchange(string $raw):string{$this->calls++;if($this->delaySeconds>0)sleep($this->delaySeconds);$r=receiver_bridge(['op'=>'control','raw'=>$raw,'now'=>time()]);if($this->forge){$v=$r['reply'];$v['signature']=base64_encode(str_repeat('x',64));return R\Guard::canonical($v);}return $r['raw'];}}
final class ReceiverNativeAnchor implements A\AnchorTransport{
 public array $anchor=['revision'=>0,'hash'=>'0000000000000000000000000000000000000000000000000000000000000000'];
 private function signed(string $scope,string $nonce,?array $before):array{$s=['anchor'=>$this->anchor,'challenge'=>$nonce,'contract'=>'bsre-current-anchor-v1','expires_at'=>time()+30,'issued_at'=>time(),'previous'=>$before,'scope'=>$scope];return ['statement'=>$s,'signature'=>base64_encode(sodium_crypto_sign_detached(C\Workflow::digest($s),receiver_test_secret()))];}
 public function current(string $scope,string $challenge):array{return $this->signed($scope,$challenge,null);}
 public function advance(string $scope,array $before,array $after,string $challenge):array{if($before!==$this->anchor||$after['revision']!==$before['revision']+1)throw new RuntimeException('SYNTHETIC_ANCHOR_CAS_CONFLICT');$this->anchor=$after;return $this->signed($scope,$challenge,$before);}
}
final class ReceiverNativeEncryption implements A\EncryptionKeys{public function activeId():string{return 'synthetic-published-vector';}public function key(string $id):string{if($id!==$this->activeId())throw new RuntimeException('SYNTHETIC_KEY_MISSING');return str_repeat('k',32);}}
/** Fixed synthetic service: verifies actual anchored ciphertext before authorizing the receiver. */
final class ReceiverNativeReview implements R\ReviewTransport{
 public array $approved=[];public int $registered=0;public bool $rejectIntent=false;public int $delayIntentSeconds=0;
 public function __construct(private R\ReceiverPolicy $policy,private A\ActualRecoveryCustody $custody){}
 public function allow(string $action,string $digest):void{$this->approved[$action.':'.$digest]=true;}
 public function exchange(string $operation,array $request):string{
  R\Guard::keys($request,['actor','scope','source','challenge']);if($request['actor']!==$this->policy->actor()||R\Guard::canonical($request['source'])!==R\Guard::canonical($this->policy->sources()))throw new RuntimeException('SYNTHETIC_REVIEW_SCOPE_CONFLICT');
  $scope=$request['scope'];$intent=null;$result=false;
  if($operation==='approval'){$result=($this->approved[$scope['action'].':'.$scope['digest']]??false)===true;if($scope['action']==='RETIRE_NO_COPY')$intent=$scope['digest'];}
  elseif($operation==='collection_custody'){$target=$scope['target'];$result=($this->approved['COLLECT:'.C\Workflow::digest($target)]??false)===true&&$target['mail_message_ids']===[]&&$target['email_status']==='QUEUED';}
  elseif($operation==='register_owner_intent'){
   if($this->delayIntentSeconds>0)sleep($this->delayIntentSeconds);
   $record=$scope['record'];$intent=$record['plan']['digest'];C\RetirementIntent::validateRecord($record,time());
   if($this->rejectIntent||!($this->approved['RETIRE_NO_COPY:'.$intent]??false)||$scope['policy']!==$this->policy->owner->scope()||$scope['anchor']!==$this->custody->current()||$scope['encrypted_hash']!==hash('sha256',$scope['encrypted_body'])||$scope['anchor']['hash']!==$scope['encrypted_hash'])throw new RuntimeException('SYNTHETIC_DURABLE_INTENT_HELD');
   $state=$this->custody->open($scope['encrypted_body'],$scope['anchor']['revision']);
   if(($state['jobs'][$intent]??null)!==$record||($state['admission_floor']??null)!==$record['plan']['admission_hash'])throw new RuntimeException('SYNTHETIC_INTENT_NOT_IN_CURRENT_JOURNAL');
   receiver_bridge(['op'=>'authorize_intent','record'=>$record,'now'=>time()]);$this->registered++;
   $result=['registered'=>true,'intent_digest'=>$intent,'record_hash'=>C\Workflow::digest($record),'anchor'=>$scope['anchor']];
  }else throw new RuntimeException('SYNTHETIC_REVIEW_OPERATION_HELD');
  $s=['contract'=>R\ReceiverPolicy::EVIDENCE,'service'=>R\ReceiverPolicy::SERVICE,'operation'=>$operation,'scope'=>C\Workflow::digest($scope),'source'=>$this->policy->sources(),'actor'=>$request['actor'],'challenge'=>$request['challenge'],'request_hash'=>C\Workflow::digest(['operation'=>$operation,'body'=>R\Guard::canonical($request)]),'issued_at'=>time(),'expires_at'=>time()+60,'claims'=>['result'=>$result,'intent_digest'=>$intent,'current_history'=>true,'receiver_only'=>true]];
  return R\Guard::canonical(['key_id'=>'synthetic-rfc8032','statement'=>$s,'signature'=>base64_encode(sodium_crypto_sign_detached(C\Workflow::digest($s),receiver_test_secret()))]);
 }
}
try{
 $now=time();$descriptor=\BSRE\RetentionAdmission\configuration();
 $init=receiver_bridge(['op'=>'init','now'=>$now,'actor'=>'wp-user:'.$owner->ID,'descriptor'=>$descriptor,'admission_hash'=>str_repeat('d',64)]);
 receiver_check('first_global_is_canonical_original',get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb'&&defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED')&&G\repository()->database()===$wpdb);
 receiver_check('fresh_owned_journal_required',(string)$wpdb->get_var("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='g5_receiver_synthetic_bsre_g5_journal'")==='0');
 receiver_check('selected_receiver_base_exact',$init['selected_bytes']===50830&&$init['selected_sha256']==='00b62f1edc8996ab4f566a80155715a85f741bc5d68e7a0a54c94fc4ef2cbdc5');
 receiver_check('admitted_exact_intake26_zero_attempt',$init['identity']['columns']===26&&$init['identity']['email_status']==='QUEUED'&&$init['identity']['email_attempts']===0);
 $policy=new A\RuntimePolicy(DB_NAME,$wpdb->prefix,'https://blackswanrealestate.ae',(int)$owner->ID);
 $rp=new R\ReceiverPolicy($policy,$init['source_hash'],$init['namespace'],str_repeat('d',64),$descriptor['generation'],'synthetic-rfc8032');
 $keys=new ReceiverNativeKeys();$proof=new R\ReceiverRuntimeProof($rp,$keys);$transport=new ReceiverNativeControl();$port=new A\ActualRetirementPort($rp,$transport,$proof);
 $before=['schema_version'=>1,'closure_id'=>$init['identity']['request_id'],'revision'=>1,'status'=>'CLOSED','request_id'=>$init['identity']['request_id'],'lead_id'=>$init['identity']['lead_id'],'event_id'=>$init['identity']['event_id'],'accepted_at_utc'=>'2023-01-01T00:00:00Z','closed_at_utc'=>'2023-01-02T00:00:00Z','recorded_at_utc'=>'2023-01-03T00:00:00Z','reviewer'=>$policy->actor(),'evidence_reference'=>'SYNTHETIC_RECEIVER_CLOSURE','evidence_hash'=>str_repeat('a',64),'outcome_ids'=>[],'mail_message_ids'=>[],'email_status'=>'QUEUED'];
 $after=C\RetirementIntent::target($before);$scope=C\NoMailCopyProof::scope($after,$rp->admission,$init['identity']['fingerprint']);
 receiver_bridge(['op'=>'bind_scope','scope'=>$scope,'accepted_at_utc'=>'2023-01-01T00:00:00.000Z']);
 $keys->present=false;receiver_check('missing_independent_signer_holds_before_transport',receiver_denied(fn()=>$port->inspect($scope,time()))&&$transport->calls===0);$keys->present=true;
 $inspection=$port->inspect($scope,time());receiver_check('actual_signed_inspection_positive',$proof->inspection($inspection,$scope,time())['state']==='UNRETIRED');
 $transport->forge=true;receiver_check('lead_hmac_cannot_replace_independent_signature',receiver_denied(fn()=>$port->inspect($scope,time()),'G5_RECEIVER_SIGNED_PROOF_UNVERIFIED'));$transport->forge=false;
 $witness=new ReceiverNativeAnchor();$custody=new A\ActualRecoveryCustody($policy->scope(),$witness,new ReceiverNativeEncryption(),$keys->publicKey(R\ReceiverPolicy::SERVICE,'synthetic-rfc8032'));
 $review=new ReceiverNativeReview($rp,$custody);$evidence=new R\ReceiverOperationalEvidence($rp,$proof,$review);$authority=new A\OwnerAuthority($policy,$evidence);
 $journal=new A\ActualReceiverJournal($wpdb,$policy,$custody,$authority,$evidence,$proof,$producer);
 receiver_check('new_journal_rejects_unapproved_initialization',receiver_denied(fn()=>$journal->initialize(),'G5_EXACT_APPROVAL_REQUIRED'));
 $review->allow('INITIALIZE_JOURNAL',C\Workflow::digest(['scope'=>$policy->scope(),'operation'=>'INITIALIZE_JOURNAL','schema'=>1]));$journal->initialize();
 $review->allow('COLLECT',C\Workflow::digest($before));$journal->locked($before['closure_id'],fn()=>$journal->insertClosure($before));
 receiver_check('actual_journal_collects_exact_synthetic_closure',$journal->locked($before['closure_id'],fn()=>$journal->closure($before['closure_id']))===$before);
 $created=time();$plan=['schema_version'=>1,'contract'=>C\RetirementIntent::CONTRACT,'closure_id'=>$before['closure_id'],'actor'=>$policy->actor(),'before'=>$before,'after'=>$after,'before_hash'=>C\Workflow::digest($before),'after_hash'=>C\Workflow::digest($after),'scope'=>$scope,'admission_hash'=>$rp->admission,'inventory_hash'=>C\Workflow::digest($inspection),'created_at'=>$created,'expires_at'=>$created+900];$plan['digest']=C\Workflow::digest($plan);
 $record=['schema_version'=>1,'contract'=>C\RetirementIntent::CONTRACT,'revision'=>0,'plan'=>$plan,'approved_at'=>$plan['created_at'],'recovery_until'=>$plan['created_at']+2592000,'phase'=>'INTENT_RECORDED','proof_hash'=>null,'hold_codes'=>[]];
 $workflow=new A\ActualReceiverWorkflow($journal,$port,$wpdb,$producer);$calls=$transport->calls;
 receiver_check('unapproved_retirement_never_calls_source',receiver_denied(fn()=>$workflow->retire($record,time()))&&$transport->calls===$calls);
 $review->allow('RETIRE_NO_COPY',$plan['digest']);$review->rejectIntent=true;
 receiver_check('durable_intent_registration_failure_never_calls_source',receiver_denied(fn()=>$workflow->retire($record,time()))&&$transport->calls===$calls);
 $record=$journal->locked($before['closure_id'],fn()=>$journal->journal($plan['digest']));$review->rejectIntent=false;
 // Real elapsed local seconds, not a frozen-Date fixture: no deadline is extended.
 $transport->delaySeconds=2;$review->delayIntentSeconds=2;$began=time();
 $done=$workflow->recover($record,time());$elapsed=time()-$began;$transport->delaySeconds=0;$review->delayIntentSeconds=0;
 receiver_check('healthy_multi_rpc_workflow_over_five_seconds_uses_fresh_clocks',$elapsed>=6&&$done['approved_at']===$record['approved_at']&&$done['plan']['expires_at']===$record['plan']['expires_at']&&$done['recovery_until']===$record['recovery_until']);
 receiver_check('consumed_actual_workflow_commits_retirement',$done['phase']==='RETIREMENT_RECORDED'&&$journal->locked($before['closure_id'],fn()=>$journal->closure($before['closure_id']))===$after);
 receiver_check('independent_service_verified_anchored_durable_intent',$review->registered===1);
 $sql=$wpdb->get_row('SELECT revision,body_hash,body FROM g5_receiver_synthetic_bsre_g5_journal WHERE id=1',ARRAY_A);$state=$custody->open($sql['body'],(int)$sql['revision']);
 receiver_check('old_six_key_document_schema_preserved',array_keys($state)===['schema_version','closures','jobs','incomplete','expired_unresolved','admission_floor']);
 receiver_check('current_anchor_binds_exact_encrypted_journal',$custody->current()===['revision'=>(int)$sql['revision'],'hash'=>hash('sha256',$sql['body'])]&&$sql['body_hash']===hash('sha256',$sql['body']));
 $readback=$port->readback($scope,time());receiver_check('actual_readback_same_stable_fence',$proof->readback($readback,$scope,time(),false,null)===$done['proof_hash']);
 $stats=receiver_bridge(['op'=>'stats']);$again=$workflow->recover($done,time());$stats2=receiver_bridge(['op'=>'stats']);
 receiver_check('recovery_keeps_exact_closure_revision',$again===$done&&$journal->locked($before['closure_id'],fn()=>$journal->closure($before['closure_id']))['revision']===2);
 receiver_check('recovery_does_not_advance_sender_epoch',$stats2['epoch_revision']===$stats['epoch_revision']);
 receiver_check('retired_intake26_row_exact_and_unsent',$stats2['rows']===1&&$stats2['columns']===26&&$stats2['status']==='RETIRED_NO_COPY'&&$stats2['attempts']===0&&$stats2['sent_at']===''&&$stats2['send_started_at']==='');
 receiver_check('retirement_never_sends_or_deletes_intake',$stats2['mail']===0&&$stats2['intake_deletes']===0);
 receiver_check('early_cleanup_remains_held',receiver_denied(fn()=>$port->prepareCleanup($scope,time())));
 $calls=$transport->calls;wp_set_current_user(0);receiver_check('owner_revocation_holds_before_source',receiver_denied(fn()=>$workflow->recover($done,time()))&&$transport->calls===$calls);wp_set_current_user($owner->ID);
 $prefix=$wpdb->prefix;$wpdb->prefix='g5_receiver_foreign_synthetic_';receiver_check('changed_prefix_held_by_canonical_producer',receiver_denied(fn()=>$workflow->recover($done,time())));$wpdb->prefix=$prefix;
 $wpdb->save_queries=true;receiver_check('query_logging_held_by_canonical_producer',receiver_denied(fn()=>$workflow->recover($done,time())));$wpdb->save_queries=false;
 $producer->assertCurrent($wpdb);receiver_check('lease_clean_and_original_global_preserved',!$wpdb->custodyIsActive()&&$GLOBALS['wpdb']===$wpdb&&G\repository()->database()===$wpdb);
 receiver_check('stable_journal_namespace_excludes_actor_and_code',$policy->scope()===(new A\RuntimePolicy(DB_NAME,$prefix,'https://blackswanrealestate.ae',(int)$owner->ID+1))->scope());
 receiver_check('no_network_or_wordpress_mail',$networkCalls===0&&$mailCalls===0);
 echo wp_json_encode(['phase'=>'g5_receiver_runtime','checks'=>$checks,'runtime_isolation'=>$isolation,'synthetic_services'=>true,'provider_accepted'=>false,'production_authorized'=>false])."\n";
}finally{fclose($pipes[0]);fclose($pipes[1]);if(proc_close($bridge)!==0)throw new RuntimeException('G5_RECEIVER_BRIDGE_EXIT_FAILED');}
