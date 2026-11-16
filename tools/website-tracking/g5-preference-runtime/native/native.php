<?php
declare(strict_types=1);
/** Prepared native acceptance: actual canonical SQL/crypto, fixed synthetic service fixtures only. */
$modes=['disabled','missing_provider','nonce','signature','coverage','reference_coverage','closed_due','closed_early','retire','known_after','unknown_after','new_choice','restore_later','cas_ack','rollback','trigger','foreign_key','snapshot_expiry','compact','floor_restore','upgrade_scope','large_unrelated','partition_conflict','orphan_history','expired_approval','revoked_cleanup','expired_backup_reference','external_deadlines'];
$mode=$argv[1]??'';if(count($argv)!==2||!in_array($mode,$modes,true))throw new RuntimeException('G37_FIXED_MODE_REQUIRED');
$isolation=['cli'=>PHP_SAPI==='cli','non_root'=>function_exists('posix_geteuid')&&posix_geteuid()!==0,
 'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
 'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
 'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
 'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
 'readonly_application'=>!is_writable('/opt/wordpress')&&!is_writable('/opt/lab/g36')&&!is_writable('/opt/lab/g37-pref'),
 'database_already_started'=>is_dir('/tmp/database')&&file_exists('/tmp/bsre.sock'),'no_docker_socket'=>!file_exists('/var/run/docker.sock')];
foreach($isolation as $ok)if(!$ok)throw new RuntimeException('G37_ISOLATION_REQUIRED');
$checks=[];$stage='bootstrap';$failure=null;$completed=false;ob_start();
register_shutdown_function(static function()use(&$completed,&$failure,&$checks,&$stage,$mode):void{
 if($completed)return;while(ob_get_level())@ob_end_clean();$code=null;
 if($failure instanceof Throwable&&preg_match('/\b([A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+)\b/',$failure->getMessage(),$m)===1)$code=substr($m[1],0,96);
 $out=['phase'=>'g37_preference_diagnostic','status'=>'FAIL','mode'=>$mode,'stage'=>$stage,'checks'=>$checks,'error_code'=>$code,
  'throwable'=>$failure instanceof Throwable?get_class($failure):null,'file'=>$failure instanceof Throwable?basename($failure->getFile()):null,
  'line'=>$failure instanceof Throwable?$failure->getLine():null,'synthetic_only'=>true,'native_provider_accepted'=>false];
 $raw=json_encode($out,JSON_UNESCAPED_SLASHES);if(is_string($raw)&&strlen($raw)<=16384)fwrite(STDERR,$raw."\n");exit(1);
});
function g37check(string $name,bool $ok):void{global $checks,$stage;$stage='check:'.$name;if(isset($checks[$name]))throw new RuntimeException('G37_DUPLICATE_CHECK');$checks[$name]=$ok;if(!$ok)throw new RuntimeException('G37_ASSERTION_FAILED');}
function g37denied(callable $call,string $message):bool{try{$call();return false;}catch(Throwable $e){return $e->getMessage()===$message;}}
use BSRE\Enquiries as E;use BSRE\SharedRepository as G;use BSRE\RetentionAdmission as A;
use BSRE\ActualRetention as R;use BSRE\ActualRetention\PreferenceV1 as V;use BSRE\PreferenceNative as N;
/** Synthetic time translation only: creates an aged ledger fixture, not actual historical proof. */
function g37ageLedger(V\Policy $policy,N\Services $services,N\Keys $keys): void {
 global $wpdb;N\fixed();$row=$wpdb->get_row("SELECT * FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'",ARRAY_A);
 $crypto=new V\Custody($policy,new V\Proofs($policy,$services,$services),$keys);$state=$crypto->open($row['body'],(int)$row['operation_revision']);
 $hash=$state['ledger']['floor']['hash'];
 foreach($state['ledger']['rows'] as &$entry){
  $entry['previous_hash']=$hash;$entry['retired_at']=time()-2592001;$entry['expires_at']=$entry['retired_at']+2592000;
  unset($entry['chain_hash']);$hash=V\Algebra::rowHash($entry);$entry['chain_hash']=$hash;
 }unset($entry);
 $state['ledger']['anchor']['hash']=$hash;$state['ledger']=V\Algebra::validate($state['ledger']);
 $before=json_decode($row['before_anchor'],true,48,JSON_THROW_ON_ERROR);$body=$crypto->seal($state,(int)$row['operation_revision']);
 $after=V\Custody::next($before,$state['ledger'],hash('sha256',$body));
 $ok=$wpdb->query($wpdb->prepare("UPDATE {$wpdb->prefix}bsre_pref_runtime SET body_hash=%s,body=%s,after_anchor=%s WHERE id='aa'",hash('sha256',$body),$body,json_encode($after,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)));
 if($ok!==1)throw new RuntimeException('G37_TIME_TRANSLATION_FIXTURE_FAILED');$services->setAnchor($policy->scope(),$after);
}
try{
 define('WP_ENVIRONMENT_TYPE','local');define('WP_CONTENT_DIR','/opt/lab/g36/wp-content');define('WP_PLUGIN_DIR',WP_CONTENT_DIR.'/plugins');
 foreach(['BSRE_CANONICAL_LEASE_ENABLED','BSRE_G3_ROUTE_CONTEXT_ENABLED','BSRE_G2_SHARED_REPOSITORY_ENABLED','BSRE_PURPOSE_ATTRIBUTION_ENABLED','BSRE_RETENTION_ADMISSION_ENABLED','BSRE_ROUTING_ENABLED'] as $flag)define($flag,true);
 define('BSRE_RETENTION_ADMISSION_GENERATION',str_repeat('a',64));define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',time()-2000);
 define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));
 define('BSRE_G5_PREFERENCE_RUNTIME_ENABLED',$mode!=='disabled');
 define('BSRE_G5_PREFERENCE_SOURCE_SHA256',hash_file('sha256','/opt/lab/g37-pref/runtime/preference-source.json'));
 $_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='GET';$_SERVER['REQUEST_URI']='/enquire/';
 require '/opt/wordpress/wp-load.php';require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
 add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
 add_filter('plugins_url',fn($url)=>'https://blackswanrealestate.ae'.parse_url($url,PHP_URL_PATH));
 add_filter('rest_url',fn($url,$route)=>'https://blackswanrealestate.ae/wp-json/'.ltrim($route,'/'),10,2);
 $network=0;$mail=0;
 add_filter('pre_http_request',function()use(&$network){$network++;throw new RuntimeException('G37_NETWORK_FORBIDDEN');},PHP_INT_MAX);
 add_filter('pre_wp_mail',function()use(&$mail){$mail++;throw new RuntimeException('G37_MAIL_FORBIDDEN');},PHP_INT_MAX);
 $owner=get_user_by('login','synthetic_owner');if(!$owner)throw new RuntimeException('G37_SYNTHETIC_OWNER_REQUIRED');wp_set_current_user($owner->ID);
 $GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
 require_once '/opt/lab/g36/contact-abi.php';\BSRE\G36Native\reconcile();
 $privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g37-synthetic-privacy-'.$mode,'post_title'=>'SYNTHETIC G37 NOTICE'],true);
 if(is_wp_error($privacy))throw new RuntimeException('G37_NOTICE_FIXTURE_FAILED');define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);
 $wpdb->prefix='g37_pref_'.str_replace('_','',$mode).'_synthetic_';E\install();if(!G\migrate())throw new RuntimeException('G37_G2_SCHEMA_REQUIRED');
 require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/candidate/consent-retention/RetentionInventory.php';
 require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/candidate/purpose-retention/purpose-retention.php';
 require '/opt/lab/g37-pref/runtime/ActualPreferenceRetention.php';require '/opt/lab/g37-pref/FixturePorts.php';
 $base=new R\RuntimePolicy(DB_NAME,$wpdb->prefix,'https://blackswanrealestate.ae',$owner->ID);$source=BSRE_G5_PREFERENCE_SOURCE_SHA256;$policy=new V\Policy($base,$source,'aa');
 $keys=new N\Keys();$services=new N\Services($keys);
 $nonce=fn($action,$digest)=>wp_create_nonce('bsre-pref-v1|'.$policy->scope().'|'.$action.'|'.$digest);
 $bind=fn()=>R\ActualPreferenceRetention::bind($wpdb,$base,$source,'aa',$services,$services,$keys);
 $subject='aa'.substr(hash('sha256','SYNTHETIC_G37_'.$mode),0,62);
 $rawRows=static function()use($wpdb):array{$out=[];foreach(['state'=>'subject_key','history'=>'receipt','captures'=>'request_id'] as $kind=>$pk)$out[$kind]=$wpdb->get_results("SELECT * FROM {$wpdb->prefix}bsre_consent_{$kind} ORDER BY {$pk} LIMIT 2001",ARRAY_A);return$out;};
 $before=$rawRows();$queryBefore=$wpdb->num_queries;
 if($mode==='disabled'){
  g37check('default_off_before_component_sql',g37denied($bind,'PREFERENCE_RUNTIME_DISABLED')&&$wpdb->num_queries===$queryBefore);
  g37check('default_off_no_service_calls',$services->calls===0);
 }else{
  $runtime=$mode==='missing_provider'?R\ActualPreferenceRetention::bind($wpdb,$base,$source,'aa'):$bind();
  $initialHash=V\Guard::digest(['initialize'=>$policy->scope()]);$initialNonce=$nonce('INITIALIZE',$initialHash);
  if($mode==='missing_provider')g37check('missing_real_provider_holds',g37denied(fn()=>$runtime->initialize($initialNonce),'PREFERENCE_PROVIDER_UNCONFIGURED'));
  elseif($mode==='nonce')g37check('exact_owner_action_nonce_required',g37denied(fn()=>$runtime->initialize('not-a-nonce'),'PREFERENCE_OWNER_ACTION_NONCE_REQUIRED')&&$services->calls===0);
  elseif($mode==='signature'){$services->badSignature=true;g37check('unsigned_or_wrong_key_proof_holds',g37denied(fn()=>$runtime->initialize($initialNonce),'PREFERENCE_AUTHENTICATED_PROOF_REQUIRED'));}
  else{
   $runtime->initialize($initialNonce);g37check('real_canonical_initializer_anchored',$services->anchor['operation_revision']===1);
   $choice=G\repository()->choose($subject,['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time()-400*86400);
   $subjects=[$subject];$before=$rawRows();
   $preview=fn()=>$runtime->preview($subjects,$nonce('RETIRE',$runtime->previewDigest('RETIRE')));
   $apply=fn($plan)=>$runtime->apply($plan,$nonce('RETIRE',V\Guard::digest($plan)));
   if($mode==='coverage'){$services->denyCoverage=true;g37check('missing_complete_source_coverage_holds',g37denied($preview,'PREFERENCE_COVERAGE_HELD'));}
   elseif($mode==='reference_coverage'){$services->denyCatalog=true;g37check('missing_no_omission_reference_catalog_holds',g37denied($preview,'PREFERENCE_REFERENCE_COVERAGE_HELD'));}
   elseif($mode==='closed_early'){$services->closedBasis=true;$services->earlyClosure=true;g37check('submitted_closure_anniversary_required',g37denied($preview,'PREFERENCE_ENQUIRY_RETENTION_NOT_DUE'));}
   elseif($mode==='partition_conflict')g37check('foreign_subject_partition_holds',g37denied(fn()=>$runtime->preview(['ab'.substr($subject,2)],$nonce('RETIRE',$runtime->previewDigest('RETIRE'))),'PREFERENCE_SUBJECT_PARTITION_CONFLICT'));
   elseif($mode==='orphan_history'){
    $orphan='aa'.substr(hash('sha256','SYNTHETIC_ORPHAN_G37'),0,62);
    $wpdb->query($wpdb->prepare("INSERT INTO {$wpdb->prefix}bsre_consent_history VALUES(%s,%s,1,0,0,0,%s,%d,0)",substr(hash('sha256',$orphan),0,32),$orphan,E\CONSENT_NOTICE_VERSION,time()-400*86400));
    $cursor='';$all=[];do{$page=$runtime->discover($cursor,$nonce('RETIRE',V\Guard::digest(['scope'=>$policy->scope(),'discover'=>$cursor])));$all=array_merge($all,$page['subjects']);$cursor=$page['next'];}while($cursor!==null);
    sort($all);g37check('cursor_discovery_includes_orphan_history',in_array($orphan,$all,true));
    $p=$runtime->preview([$orphan],$nonce('RETIRE',$runtime->previewDigest('RETIRE')));
    g37check('original_missing_state_hold_preserved',$p['details']['eligible']===[]);
   }else{
    if($mode==='large_unrelated'){
     $states=[];$histories=[];$captures=[];$old=time()-400*86400;
     $captureFields=array_merge(\BSRE\RetentionReview\RetentionInventory::COLUMNS['captures'],['purpose_version','purpose_hash','purpose_record_hash','purpose_json']);
     for($i=0;$i<1100;$i++){
      $s='ab'.substr(hash('sha256','SYNTHETIC_UNRELATED_'.$i),0,62);$receipt=substr(hash('sha256',$s),0,32);
      $states[]=$wpdb->prepare('(%s,1,%s,0,0,0,%s,%d,%d,0)',$s,$receipt,E\CONSENT_NOTICE_VERSION,$old,$old+E\CONSENT_PREFERENCE_SECONDS);
      $histories[]=$wpdb->prepare('(%s,%s,1,0,0,0,%s,%d,0)',$receipt,$s,E\CONSENT_NOTICE_VERSION,$old);
      $h=hash('sha256','SYNTHETIC_UNRELATED_REQUEST_'.$i);$id=substr($h,0,8).'-'.substr($h,8,4).'-4'.substr($h,13,3).'-8'.substr($h,17,3).'-'.substr($h,20,12);
      $row=array_fill_keys($captureFields,'');foreach(['original_revision','analytics','ad_measurement','personalization','preference_expires_at','eligible','known','uncertain','delivery_pending','gclid_first_captured_ms','gclid_last_captured_ms','purpose_version'] as $f)$row[$f]=0;
      $row['request_id']=$id;$row['fingerprint']=$h;$row['subject_key']=$s;$row['original_revision']=1;$row['decision_version']=$receipt;$row['notice_version']=E\CONSENT_NOTICE_VERSION;
      $row['created_at']=$old;$row['state']='STAGED';$row['click_capture_state']='NOT_PERMITTED';$row['purpose_json']=null;
      $placeholders=implode(',',array_fill(0,count($captureFields),'%s'));$captures[]=$wpdb->prepare('('.$placeholders.')',...array_map(fn($f)=>$row[$f]??'',$captureFields));
     }
     if($wpdb->query("INSERT INTO {$wpdb->prefix}bsre_consent_state VALUES ".implode(',',$states))!==1100||
        $wpdb->query("INSERT INTO {$wpdb->prefix}bsre_consent_history VALUES ".implode(',',$histories))!==1100||
        $wpdb->query("INSERT INTO {$wpdb->prefix}bsre_consent_captures (".implode(',',$captureFields).") VALUES ".implode(',',$captures))!==1100)throw new RuntimeException('G37_UNRELATED_FIXTURE_FAILED');
     g37check('global_rows_exceed_legacy_work_bound',(int)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_history")>1000);
     $before=$rawRows();
    }
    if($mode==='closed_due')$services->closedBasis=true;
    $backup=null;
    if(in_array($mode,['restore_later','snapshot_expiry'],true)){
     $bp=$runtime->previewBackup($subjects,$nonce('BACKUP',$runtime->previewDigest('BACKUP')));
     $backup=$runtime->backup($bp,$nonce('BACKUP',V\Guard::digest($bp)))['snapshot']['snapshot_id'];
    }
    $plan=$preview();g37check('actual_domain_exact_two_preference_targets',$plan['contract']==='bsre-preference-runtime-v1'&&count($plan['details']['eligible'])===2&&$plan['subjects']===$subjects);
    if($mode==='expired_approval'){
     $short=$plan;$short['created_at']=time()-895;$short['expires_at']=$short['created_at']+900;
     $originalExpiry=$short['expires_at'];$anchorBefore=$services->anchor;$casBefore=$services->casCalls;
     $services->approvalDelaySeconds=2;
     g37check('expired_original_plan_not_renewed_by_fresh_approval',g37denied(fn()=>$apply($short),'PREFERENCE_ORIGINAL_PLAN_EXPIRED'));
     g37check('expired_plan_no_consent_ledger_or_cas_write',$rawRows()===$before&&$services->anchor===$anchorBefore&&$services->casCalls===$casBefore&&
       (string)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_pref_audit WHERE action='RETIRE'")==='0'&&$short['expires_at']===$originalExpiry);
    }elseif($mode==='expired_backup_reference'){
     $bp=$runtime->previewBackup($subjects,$nonce('BACKUP',$runtime->previewDigest('BACKUP')));
     $bp['created_at']=time()-898;$bp['expires_at']=$bp['created_at']+900;
     $services->referenceDelayUntil=$bp['expires_at'];$mutableBefore=$services->mutableCalls;$anchorBefore=$services->anchor;
     g37check('read_only_reference_delay_cannot_renew_backup',g37denied(fn()=>$runtime->backup($bp,$nonce('BACKUP',V\Guard::digest($bp))),'PREFERENCE_ORIGINAL_PLAN_EXPIRED'));
     g37check('expired_backup_no_external_snapshot_key_or_sql_write',$services->snapshots===[]&&$services->snapshotKeys===[]&&$services->mutableCalls===$mutableBefore&&$services->anchor===$anchorBefore&&$rawRows()===$before);
    }elseif($mode==='external_deadlines'){
     $proofs=new V\Proofs($policy,$services,$services);$custody=new V\Custody($policy,$proofs,$keys);
     $bp=$runtime->previewBackup($subjects,$nonce('BACKUP',$runtime->previewDigest('BACKUP')));
     $snapshot=['kind'=>V\SnapshotFormat::KIND,'batch'=>['partition'=>'aa','subjects'=>$subjects,'references'=>['version'=>1,'hash'=>str_repeat('0',64)]],
       'state'=>$before['state'],'history'=>$before['history'],'captures'=>$before['captures']];
     foreach(['STORE'=>'BACKUP','PREPARE_COMPACTION'=>'COMPACT','COMPARE_AND_SWAP'=>'RETIRE','FINISH_COMPACTION'=>'COMPACT','EXPIRE'=>'EXPIRE_BACKUP'] as $op=>$action){
      $digest=V\Guard::digest(['synthetic_deadline_boundary'=>$op]);$authorization=$proofs->approval($action,$digest,time()+2);
      $services->delayMutation=$op;$prior=[count($services->snapshots),count($services->snapshotKeys),count($keys->values),$services->anchor,$services->mutableCalls];
      $transition=['old_key'=>$keys->active,'new_key'=>'synthetic-never-applied','plan_hash'=>$digest,'after_floor'=>V\Algebra::empty()['floor']];
      $call=match($op){
       'STORE'=>fn()=>$custody->backup($snapshot,$services->anchor,$authorization),
       'PREPARE_COMPACTION'=>fn()=>$custody->prepareCompaction($keys->active,$services->anchor,$transition['after_floor'],$digest,$authorization),
       'COMPARE_AND_SWAP'=>fn()=>$custody->advance($services->anchor,$services->anchor+[],str_repeat('a',64),$authorization),
       'FINISH_COMPACTION'=>fn()=>$custody->finishCompaction($transition,$services->anchor,str_repeat('b',64),$authorization),
       'EXPIRE'=>fn()=>$custody->expire(str_repeat('c',64),$authorization)};
      // CAS also requires a valid next anchor; use the actual current ledger body.
      if($op==='COMPARE_AND_SWAP'){
       $row=$wpdb->get_row("SELECT body FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'",ARRAY_A);
       $state=$custody->open($row['body'],$services->anchor['operation_revision']);
       $next=V\Custody::next($services->anchor,$state['ledger'],str_repeat('d',64));
       $call=fn()=>$custody->advance($services->anchor,$next,str_repeat('a',64),$authorization);
      }
      g37check('independent_expired_'.strtolower($op).'_denied',g37denied($call,'G37_EXPIRED_INDEPENDENT_MUTATION_DENIED'));
      g37check('independent_expired_'.strtolower($op).'_no_effect',$prior===[count($services->snapshots),count($services->snapshotKeys),count($keys->values),$services->anchor,$services->mutableCalls]&&$rawRows()===$before);
     }
    }elseif($mode==='revoked_cleanup'){
     $services->onCoverage=static function(){wp_set_current_user(0);};
     g37check('owner_revocation_holds_before_delete',g37denied(fn()=>$apply($plan),'G5_OWNER_DOMAIN_REQUIRED'));
     $lock='bsre-g5-'.substr($base->scope(),0,48);
     g37check('revocation_rollback_releases_healthy_original_lease',$rawRows()===$before&&!$wpdb->custodyIsActive()&&$wpdb->get_var($wpdb->prepare('SELECT IS_USED_LOCK(%s)',$lock))===null);
     wp_set_current_user($owner->ID);
    }elseif($mode==='trigger'){
     $wpdb->query("CREATE TRIGGER {$wpdb->prefix}g37_guard BEFORE DELETE ON {$wpdb->prefix}bsre_consent_state FOR EACH ROW SET @g37_unreviewed=1");
     g37check('target_trigger_denied_before_delete',g37denied(fn()=>$apply($plan),'PREFERENCE_CONSENT_SIDE_EFFECT_HELD'));
     $wpdb->query("DROP TRIGGER {$wpdb->prefix}g37_guard");
    }elseif($mode==='foreign_key'){
     $collation=$wpdb->get_charset_collate();
     $wpdb->query("CREATE TABLE {$wpdb->prefix}g37_child (subject_key char(64) NOT NULL,FOREIGN KEY(subject_key) REFERENCES {$wpdb->prefix}bsre_consent_state(subject_key) ON DELETE CASCADE) ENGINE=InnoDB {$collation}");
     $wpdb->query($wpdb->prepare("INSERT INTO {$wpdb->prefix}g37_child VALUES(%s)",$subject));
     g37check('incoming_cascade_denied_before_delete',g37denied(fn()=>$apply($plan),'PREFERENCE_CONSENT_SIDE_EFFECT_HELD'));
     g37check('unrelated_child_preserved',(string)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}g37_child")==='1');
     $wpdb->query("DROP TABLE {$wpdb->prefix}g37_child");
    }elseif($mode==='rollback'){
     $services->rollbackKey=true;
     g37check('post_delete_failure_rolls_back',g37denied(fn()=>$apply($plan),'G37_INJECTED_KEY_FAILURE'));
     g37check('consent_ledger_audit_rollback_exact',$rawRows()===$before&&$services->anchor['operation_revision']===1);
    }else{
     if($mode==='cas_ack')$services->loseCasAck=true;
     if($mode==='cas_ack'){
      g37check('lost_cas_ack_remains_pending',g37denied(fn()=>$apply($plan),'PREFERENCE_DURABLE_INTENT_RECONCILIATION_REQUIRED'));
      $row=$wpdb->get_row("SELECT status,operation_id FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'",ARRAY_A);
      g37check('durable_pending_intent_exists',$row['status']==='PENDING_ANCHOR');
      $d=V\Guard::digest(['reconcile'=>$row['operation_id'],'scope'=>$policy->scope()]);
      $runtime->reconcile($row['operation_id'],$nonce('RECONCILE',$d));
      g37check('same_intent_reconciled_without_second_delete',(string)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_pref_audit WHERE action='RETIRE'")==='1');
     }else $apply($plan);
     $after=$rawRows();
     g37check('actual_state_history_deleted_atomically',(string)$wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_state WHERE subject_key=%s",$subject))==='0'&&
       (string)$wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_history WHERE subject_key=%s",$subject))==='0');
     if($mode==='large_unrelated')g37check('unrelated_partitions_preserved_after_batch',(string)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_history")==='1100');
     g37check('capture_table_unchanged',$after['captures']===$before['captures']);
     $row=$wpdb->get_row("SELECT status FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'",ARRAY_A);
     g37check('independent_sequence_and_ready_readback',$services->anchor['sequence']===1&&$row['status']==='READY');
     if(in_array($mode,['known_after','unknown_after'],true)){
      $id=wp_generate_uuid4();$capture=['request_id'=>$id,'fingerprint'=>hash('sha256','SYNTHETIC_G37_CAPTURE'),'subject_key'=>$subject,
       'original_revision'=>(int)$choice['revision'],'decision_version'=>$choice['receipt'],'notice_version'=>E\CONSENT_NOTICE_VERSION,
       'analytics'=>0,'ad_measurement'=>0,'preference_expires_at'=>$mode==='known_after'?(int)$choice['expires_at']:0,
       'eligible'=>$mode==='known_after'?1:0,'known'=>$mode==='known_after'?1:0,'created_at'=>time(),'uncertain'=>0,'click_capture_state'=>'NOT_PERMITTED',
       'gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0];
      A\Runtime::$session=str_repeat('s',64);A\Runtime::$proof=A\sign_new_request($id,A\Runtime::$session,BSRE_LEAD_HMAC_SECRET,A\configuration(),time());
      if($mode==='known_after')g37check('old_known_receipt_still_denied',g37denied(fn()=>G\repository()->stage($capture),'Consent evidence retired.'));
      else{$staged=G\repository()->stage($capture);g37check('healthy_unknown_intake_survives',(int)$staged['known']===0&&(int)$staged['eligible']===0&&(int)$staged['analytics']===0);}
     }
     if(in_array($mode,['new_choice','restore_later'],true)){
      $new=G\repository()->choose($subject,['analytics'=>true,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time());
      g37check('new_receipt_can_reuse_revision',$new['receipt']!==$choice['receipt']&&(int)$new['revision']===1);
      if($mode==='restore_later'){
       $rp=$runtime->previewRestore($backup,$nonce('RESTORE',$runtime->previewDigest('RESTORE')));
       $runtime->restore($rp,$nonce('RESTORE',V\Guard::digest($rp)));
       g37check('restore_preserves_later_new_receipt',G\repository()->current($subject)['receipt']===$new['receipt']);
      }
     }
     if($mode==='snapshot_expiry'){$services->expiredSnapshot=true;g37check('expired_snapshot_and_key_held',g37denied(fn()=>$runtime->previewRestore($backup,$nonce('RESTORE',$runtime->previewDigest('RESTORE'))),'PREFERENCE_SNAPSHOT_EXPIRED_OR_CHANGED'));}
     if($mode==='upgrade_scope'){
      $nextPolicy=new V\Policy($base,hash('sha256','SYNTHETIC_NEXT_REVIEWED_CODE'),'aa');
      g37check('code_upgrade_does_not_reset_scope',$nextPolicy->scope()===$policy->scope());
      $old=V\Custody::zero();$crypto=new V\Custody($policy,new V\Proofs($policy,$services,$services),$keys);
      $body=$crypto->seal(['synthetic_crypto_probe'=>true],1);
      $upgraded=new V\Custody($nextPolicy,new V\Proofs($nextPolicy,$services,$services),$keys);
      g37check('old_body_aad_survives_code_version',$upgraded->open($body,1)===['synthetic_crypto_probe'=>true]);
     }
     if(in_array($mode,['compact','floor_restore'],true)){
      g37ageLedger($policy,$services,$keys);g37check('synthetic_time_translation_not_actual_history',true);
      $cp=$runtime->previewCompaction($nonce('COMPACT',$runtime->previewDigest('COMPACT')));
      $runtime->compact($cp,$nonce('COMPACT',V\Guard::digest($cp)));
      g37check('expired_prefix_compacts_with_independent_floor',$services->anchor['floor_generation']===1&&$services->anchor['floor_sequence']===1);
      g37check('old_ledger_key_deleted_after_commit',!isset($keys->values['native-ledger-0']));
      g37check('compacted_history_cannot_claim_complete',g37denied(fn()=>$runtime->assertQualificationHistoryComplete(),'PREFERENCE_COMPACTED_HISTORY_INCOMPLETE'));
      if($mode==='floor_restore'){
       G\repository()->choose($subject,['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time());
       $bp=$runtime->previewBackup($subjects,$nonce('BACKUP',$runtime->previewDigest('BACKUP')));
       $id=$runtime->backup($bp,$nonce('BACKUP',V\Guard::digest($bp)))['snapshot']['snapshot_id'];
       g37check('positive_floor_holds_even_fresh_nonempty_restore',g37denied(fn()=>$runtime->previewRestore($id,$nonce('RESTORE',$runtime->previewDigest('RESTORE'))),'COMPACTED_HISTORY_REQUIRES_RECONCILIATION'));
      }
     }
    }
   }
   if(in_array($mode,['coverage','reference_coverage','closed_early','partition_conflict','trigger','foreign_key'],true))g37check('held_operation_preserves_all_consent_rows',$rawRows()===$before);
  }
 }
 g37check('no_mail_or_network_provider_calls',$network===0&&$mail===0);
 g37check('same_real_canonical_connection',get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb'&&!$wpdb->custodyIsActive());
 while(ob_get_level())ob_end_clean();
 echo json_encode(['phase'=>'g37_preference_runtime','mode'=>$mode,'checks'=>$checks,'runtime_isolation'=>$isolation,'synthetic_only'=>true,
  'actual_provider_accepted'=>false,'production_authorized'=>false,'source_profile'=>'G36_CANONICAL_SITE_PLUS_PRIVATE_PREFERENCE_RUNTIME',
  'historical_fixture_accepted'=>false,'code_migration_accepted'=>false,'full_operational_retention_accepted'=>false,
  'limits'=>'Fixed native SQL/crypto fixtures only. Real provider enrollment, scale, all concurrency schedules and operational/release acceptance remain separate.'],JSON_THROW_ON_ERROR)."\n";
 $completed=true;
}catch(Throwable $error){$failure=$error;exit(1);}
