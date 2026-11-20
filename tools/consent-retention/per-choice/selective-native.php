<?php
declare(strict_types=1);
/** Actual WordPress/MariaDB acceptance, restricted to its own disposable synthetic namespace. */
define('WP_ENVIRONMENT_TYPE','local');define('BSRE_RETENTION_LAB',true);
define('BSRE_PER_CHOICE_LAB_ENABLED',true);define('BSRE_PER_CHOICE_APPLY_ENABLED',true);
require '/opt/wordpress/wp-load.php';require '/opt/lab/consent-retention/candidate-store.php';
require __DIR__.'/SelectiveChoiceRetirement.php';
use BSRE\RetentionCandidate\WpConsentRepository;
use BSRE\RetentionReview\PerChoice\PerChoicePlanner as P;
use BSRE\RetentionReview\PerChoice\ApplicationV1\SelectiveChoiceRetirement as C;
wp_set_current_user(get_user_by('login','synthetic_owner')->ID);
$clock=2000000000;$checks=[];
function selectiveDb(string $class='wpdb'){$db=new $class(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);$db->set_prefix($GLOBALS['wpdb']->prefix);$db->prefix=C::PREFIX;$db->suppress_errors(true);return $db;}
$db=selectiveDb();
function sx(string $name,bool $condition):void{global$checks;if(!$condition)throw new RuntimeException('Synthetic selective SQL assertion failed: '.$name);$checks[$name]=true;}
function sh(callable $fn,string $code):bool{try{$fn();return false;}catch(Throwable $error){return $error->getMessage()===$code;}}
function sq(string $sql):void{global$db;if($db->query($sql)===false)throw new RuntimeException('Synthetic selective fixture SQL failed');}
function controller($connection=null):C{return new C($connection??$GLOBALS['db'],fn()=>$GLOBALS['clock']);}
function captureRow(array $original,string $request):array{
    return ['request_id'=>$request,'fingerprint'=>str_repeat('f',64),'subject_key'=>$original['subject_key'],'original_revision'=>$original['revision'],'decision_version'=>$original['receipt'],
        'notice_version'=>$original['notice_version'],'analytics'=>$original['analytics'],'ad_measurement'=>$original['ad_measurement'],'personalization'=>0,'preference_expires_at'=>(int)$original['changed_at']+15552000,
        'eligible'=>1,'known'=>1,'created_at'=>(int)$original['changed_at']+60,'state'=>'ACCEPTED','uncertain'=>0,'delivery_pending'=>1,'click_capture_state'=>'ABSENT',
        'gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0,'lead_id'=>'BSRE-SYNTHETIC-LEAD','event_id'=>'evt_synthetic_event'];
}
function fixture(bool $seed=true):C{
    global$db,$wpdb,$clock;
    if($db->prefix!==C::PREFIX||home_url()!=='http://bsre.invalid')throw new RuntimeException('Synthetic fixture boundary failed');
    foreach(['bsre_choice_audit','bsre_choice_control','bsre_consent_captures','bsre_consent_history','bsre_consent_state']as$table)sq('DROP TABLE IF EXISTS '.C::PREFIX.$table);
    $control=controller();$control->installLabTables();
    $original=$wpdb;try{$wpdb=$db;$installed=BSRE\RetentionCandidate\install_consent_storage();}finally{$wpdb=$original;}
    if(!$installed)throw new RuntimeException('Synthetic consent schema unavailable');
    if($seed){
        $store=new WpConsentRepository($db);$off=['analytics'=>false,'ad_measurement'=>false];$on=['analytics'=>true,'ad_measurement'=>true];
        foreach([['a',500,$off,'A1'],['a',400,$off,'A2'],['a',10,$off,'A3'],['b',500,$on,'B1'],['b',450,$off,'B2'],['b',5,$on,'B3'],['c',400,$off,'C1']]as[$subject,$days,$flags,$notice])$store->choose(str_repeat($subject,64),$flags,'SYNTHETIC_'.$notice,$clock-$days*86400);
        $originalChoice=$db->get_row("SELECT * FROM ".C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('b',64)."' AND revision=1",ARRAY_A);
        if($db->insert(C::PREFIX.'bsre_consent_captures',captureRow($originalChoice,'11111111-1111-4111-8111-111111111111'))===false)throw new RuntimeException('Synthetic capture seed failed');
    }return $control;
}
function preparePlan(C $control):array{
    global$clock;$source=$control->reviewSource();
    $coverage=['kind'=>P::COVERAGE,'snapshot_sha256'=>P::digest($source['snapshot']),'status'=>'COMPLETE_SYNTHETIC','observed_at'=>$clock,'valid_until'=>$clock+3600,'history_pruned'=>false];
    return [$control->preview($coverage,$source['anchor']),$source];
}
class SelectiveFaultDb extends wpdb {
    public string $fault='';public int $deleteNumber=0;
    public function query($query){
        $delete=str_starts_with($query,'DELETE FROM '.C::PREFIX.'bsre_consent_');
        if($this->fault==='second-delete'&&$delete&&++$this->deleteNumber===2){$this->fault='';$this->last_error='SYNTHETIC_DELETE_FAILURE';return false;}
        if($this->fault==='delete-count'&&$delete){$this->fault='';return 0;}
        if($this->fault==='audit'&&str_starts_with($query,'INSERT INTO '.C::PREFIX.'bsre_choice_audit')){$this->fault='';return false;}
        if($this->fault==='checkpoint'&&str_starts_with($query,'UPDATE '.C::PREFIX.'bsre_choice_control')){$this->fault='';return false;}
        if($query==='COMMIT'&&in_array($this->fault,['commit-before','commit-after'],true)){
            $mode=$this->fault;$this->fault='';if($mode==='commit-after')parent::query($query);$this->last_error='SYNTHETIC_COMMIT_ACK_UNKNOWN';return false;
        }
        return parent::query($query);
    }
}
class SelectivePauseDb extends wpdb {
    public $beforeDelete=null;
    public function query($query){
        if($this->beforeDelete!==null&&str_starts_with($query,'DELETE FROM '.C::PREFIX.'bsre_consent_')){
            $callback=$this->beforeDelete;$this->beforeDelete=null;$callback();
        }return parent::query($query);
    }
}

if(in_array($argv[1]??'',['apply-worker','stage-worker'],true)){
    $input=json_decode(trim((string)fgets(STDIN,20000)),true,64,JSON_THROW_ON_ERROR);
    echo 'READY:'.$db->get_var('SELECT CONNECTION_ID()')."\n";fflush(STDOUT);
    if($argv[1]==='stage-worker'){
        try{(new WpConsentRepository($db))->stage($input['capture']);echo "STAGED\n";}
        catch(Throwable $error){echo $error->getMessage()==='Consent evidence retired.'?"RETIRED\n":"SYNTHETIC_UNCLASSIFIED_HOLD\n";}
        fflush(STDOUT);exit;
    }
    try{controller()->apply($input['plan'],$input['ack'],$input['anchor']);echo "APPLIED\n";}
    catch(Throwable $error){echo 'HELD:'.(in_array($error->getMessage(),['SELECTIVE_PLAN_STALE_OR_ALTERED','SELECTIVE_CURRENT_ANCHOR_REQUIRED'],true)?$error->getMessage():'SYNTHETIC_UNCLASSIFIED_HOLD')."\n";}
    fflush(STDOUT);exit;
}

$control=fixture();[$plan,$before]=preparePlan($control);
sx('first_plan_selects_only_due_history_and_closed_choice_state',$plan['deleted_state']===1&&$plan['deleted_history']===3&&count($plan['selected'])===4);
$result=$control->apply($plan,C::labAcknowledgement($plan),$before['anchor']);$after=$control->reviewSource();
sx('actual_selective_rows_deleted_exactly',$result['deleted_rows']===4&&count($after['snapshot']['state'])===2&&count($after['snapshot']['history'])===4);
sx('retained_current_authority_and_captures_byte_identical',P::digest($after['snapshot']['captures'])===P::digest($before['snapshot']['captures'])&&array_values(array_filter($after['snapshot']['state'],fn($r)=>$r['subject_key']===str_repeat('a',64)||$r['subject_key']===str_repeat('b',64)))===array_values(array_filter($before['snapshot']['state'],fn($r)=>$r['subject_key']!==str_repeat('c',64))));
sx('submitted_original_and_withdrawal_history_remain',count(array_filter($after['snapshot']['history'],fn($r)=>$r['subject_key']===str_repeat('b',64)))===3);
sx('pruning_latches_history_gap_and_never_grants_reopen',$result['history_incomplete']===true&&$result['production_acceptance']===false&&$result['reopen_authorized']===false);
$readback=$control->reconcileLast($plan,$result['anchor']);
sx('read_only_exact_reconciliation_does_not_clear_gap',$readback['last_operation_reconciled']===true&&$readback['history_incomplete']===true&&$readback['future_application_authorized']===false&&$readback['reopen_authorized']===false);
$audit=$db->get_row('SELECT * FROM '.C::PREFIX.'bsre_choice_audit',ARRAY_A);
sx('audit_contains_no_retired_subject_receipt_or_permission_payload',array_keys($audit)===['plan_hash','generation','before_hash','after_hash','before_anchor_hash','after_anchor_hash','deleted_state','deleted_history','applied_at','actor']);
$control->installLabTables();sx('reinstall_cannot_clear_proven_history_gap',$control->anchor()===$result['anchor']);
$coverage=['kind'=>P::COVERAGE,'snapshot_sha256'=>P::digest($after['snapshot']),'status'=>'COMPLETE_SYNTHETIC','observed_at'=>$clock,'valid_until'=>$clock+3600,'history_pruned'=>false];
sx('caller_false_pruned_flag_cannot_resume_application',sh(fn()=>$control->preview($coverage,$result['anchor']),'SELECTIVE_HISTORY_RECONCILIATION_REQUIRED'));
sx('lost_ack_plan_not_reapplied',sh(fn()=>$control->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_CURRENT_ANCHOR_REQUIRED')&&P::digest($control->reviewSource()['snapshot'])===$plan['expected_after_hash']);
sq('UPDATE '.C::PREFIX.'bsre_choice_control SET history_gap=0 WHERE id=1');
sx('control_gap_tampering_held',sh(fn()=>$control->anchor(),'SELECTIVE_AUDIT_CONTROL_MISMATCH'));sq('UPDATE '.C::PREFIX.'bsre_choice_control SET history_gap=1 WHERE id=1');
sq('UPDATE '.C::PREFIX.'bsre_choice_audit SET actor=actor+1');sx('audit_payload_tampering_held',sh(fn()=>$control->anchor(),'SELECTIVE_AUDIT_CONTROL_MISMATCH'));sq('UPDATE '.C::PREFIX.'bsre_choice_audit SET actor=actor-1');
sq('DELETE FROM '.C::PREFIX.'bsre_choice_audit');sx('missing_audit_not_reset_by_install',sh(fn()=>$control->installLabTables(),'SELECTIVE_AUDIT_CONTROL_MISMATCH')&&(string)$db->get_var('SELECT generation FROM '.C::PREFIX.'bsre_choice_control WHERE id=1')==='1');
sq('DROP TABLE '.C::PREFIX.'bsre_choice_control');sx('missing_control_not_reinitialized',sh(fn()=>$control->installLabTables(),'SELECTIVE_PARTIAL_INSTALLATION'));
sq('DROP TABLE '.C::PREFIX.'bsre_choice_audit');sx('existing_pruned_consent_namespace_not_reinitialized',sh(fn()=>$control->installLabTables(),'SELECTIVE_PARTIAL_INSTALLATION'));

$control=fixture();[$plan,$before]=preparePlan($control);$tampered=$plan;$tampered['selected']=[];
sx('recomputed_ack_cannot_authorize_altered_plan',sh(fn()=>$control->apply($tampered,C::labAcknowledgement($tampered),$before['anchor']),'SELECTIVE_PLAN_STALE_OR_ALTERED')&&P::digest($control->reviewSource()['snapshot'])===$plan['source_hash']);
sq('UPDATE '.C::PREFIX."bsre_consent_history SET notice_version='SYNTHETIC_NEW_NOTICE' WHERE subject_key='".str_repeat('a',64)."' AND revision=1");
sx('stale_source_rejected_before_deletion',sh(fn()=>$control->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_PLAN_STALE_OR_ALTERED'));

foreach(['second-delete'=>'SELECTIVE_STORAGE_UNAVAILABLE','delete-count'=>'SELECTIVE_DELETE_COUNT_CONFLICT','audit'=>'SELECTIVE_STORAGE_UNAVAILABLE','checkpoint'=>'SELECTIVE_STORAGE_UNAVAILABLE']as$fault=>$code){
    $control=fixture();[$plan,$before]=preparePlan($control);$faultDb=selectiveDb(SelectiveFaultDb::class);$faultDb->fault=$fault;
    sx($fault.'_failure_rolls_back_all_rows_audit_and_control',sh(fn()=>controller($faultDb)->apply($plan,C::labAcknowledgement($plan),$before['anchor']),$code)&&P::digest($control->reviewSource()['snapshot'])===$plan['source_hash']&&$control->anchor()===$before['anchor']&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_choice_audit')===0);$faultDb->close();
}
foreach(['commit-before','commit-after']as$mode){
    $control=fixture();[$plan,$before]=preparePlan($control);$faultDb=selectiveDb(SelectiveFaultDb::class);$uncertain=controller($faultDb);$faultDb->fault=$mode;
    sx($mode.'_returns_ambiguous_hold',sh(fn()=>$uncertain->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_COMMIT_AMBIGUOUS_READBACK_REQUIRED'));
    sx($mode.'_cannot_blind_retry_same_instance',sh(fn()=>$uncertain->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_FRESH_READBACK_REQUIRED'));
    $faultDb->close();$fresh=controller();$freshSource=$fresh->reviewSource();
    if($mode==='commit-before')sx('fresh_connection_proves_uncommitted_transaction_rolled_back',P::digest($freshSource['snapshot'])===$plan['source_hash']&&$freshSource['anchor']===$before['anchor']);
    else sx('fresh_connection_reconciles_committed_lost_ack_without_redeletion',P::digest($freshSource['snapshot'])===$plan['expected_after_hash']&&$fresh->reconcileLast($plan,$freshSource['anchor'])['last_operation_reconciled']===true);
}

$control=fixture();[$plan,$before]=preparePlan($control);$marker='SYNTHETIC_CALLER_UNCOMMITTED';
sq('START TRANSACTION');sq($db->prepare('UPDATE '.C::PREFIX.'bsre_consent_history SET notice_version=%s WHERE subject_key=%s AND revision=1',$marker,str_repeat('a',64)));
$other=selectiveDb();
sx('caller_transaction_preserved_even_for_ddl_install',sh(fn()=>$control->installLabTables(),'SELECTIVE_CALLER_TRANSACTION_FORBIDDEN')&&sh(fn()=>$control->anchor(),'SELECTIVE_CALLER_TRANSACTION_FORBIDDEN')&&(string)$db->get_var('SELECT @@session.in_transaction')==='1'&&$db->get_var('SELECT notice_version FROM '.C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('a',64)."' AND revision=1")===$marker&&$other->get_var('SELECT notice_version FROM '.C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('a',64)."' AND revision=1")!==$marker);
sq('ROLLBACK');$other->close();
sq('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED');sx('non_repeatable_read_session_refused_without_change',sh(fn()=>$control->anchor(),'SELECTIVE_REPEATABLE_READ_REQUIRED')&&$db->get_var('SELECT @@session.tx_isolation')==='READ-COMMITTED');sq('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');
sq('ALTER TABLE '.C::PREFIX.'bsre_choice_audit ENGINE=MyISAM');sx('nontransactional_audit_refused_before_any_delete',sh(fn()=>$control->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_TRANSACTIONAL_TABLE_REQUIRED')&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_consent_history')===7);sq('ALTER TABLE '.C::PREFIX.'bsre_choice_audit ENGINE=InnoDB');

$control=fixture();$row=$db->get_row('SELECT * FROM '.C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('b',64)."' AND revision=1",ARRAY_A);$unlinked=captureRow($row,'22222222-2222-4222-8222-222222222222');$unlinked['subject_key']='';$db->insert(C::PREFIX.'bsre_consent_captures',$unlinked);
sx('unknown_linkage_blocks_entire_mutation_plan',sh(fn()=>preparePlan($control),'SELECTIVE_SOURCE_COVERAGE_UNRESOLVED')&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_choice_audit')===0);
$control=fixture();sq('DELETE FROM '.C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('a',64)."' AND revision=1");sx('unexplained_history_gap_blocks_entire_mutation_plan',sh(fn()=>preparePlan($control),'SELECTIVE_SOURCE_COVERAGE_UNRESOLVED'));
$control=fixture(false);$store=new WpConsentRepository($db);$choice=(new DateTimeImmutable('2024-02-29T14:00:00+04:00'))->getTimestamp();$boundary=(new DateTimeImmutable('2025-02-28T14:00:00+04:00'))->getTimestamp();$store->choose(str_repeat('d',64),['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_LEAP',$choice);
$clock=$boundary-1;[$early,$earlySource]=preparePlan($control);$noop=$control->apply($early,C::labAcknowledgement($early),$earlySource['anchor']);
sx('exact_calendar_deadline_noop_does_not_advance_or_audit',$noop['deleted_rows']===0&&$noop['anchor']===$earlySource['anchor']&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_choice_audit')===0);
$clock=$boundary;[$due,$dueSource]=preparePlan($control);sx('exact_dubai_leap_anniversary_applies_due_state_and_history',$control->apply($due,C::labAcknowledgement($due),$dueSource['anchor'])['deleted_rows']===2);$clock=2000000000;

// A competing capture transaction holds the actual state row. Observe, never sleep-infer, the wait.
$control=fixture();[$plan,$before]=preparePlan($control);$parent=(int)$db->get_var('SELECT CONNECTION_ID()');$observer=selectiveDb();
sq('START TRANSACTION');$db->get_row('SELECT * FROM '.C::PREFIX."bsre_consent_state WHERE subject_key='".str_repeat('a',64)."' FOR UPDATE",ARRAY_A);
$process=proc_open([PHP_BINARY,'-d','sendmail_path=/bin/false',__FILE__,'apply-worker'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
if(!is_resource($process)){sq('ROLLBACK');throw new RuntimeException('Synthetic selective worker unavailable');}
try{
    fwrite($pipes[0],json_encode(['plan'=>$plan,'ack'=>C::labAcknowledgement($plan),'anchor'=>$before['anchor']],JSON_THROW_ON_ERROR)."\n");fclose($pipes[0]);stream_set_timeout($pipes[1],5);
    $ready=trim((string)fgets($pipes[1]));if(!preg_match('/^READY:([0-9]+)$/D',$ready,$match))throw new RuntimeException('Synthetic selective worker readiness failed');
    $worker=(int)$match[1];$observed=false;$deadline=microtime(true)+5;
    do{
        $observer->last_error='';$waiting=$observer->get_var($observer->prepare('SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX wt ON w.requesting_trx_id=wt.trx_id JOIN information_schema.INNODB_TRX bt ON w.blocking_trx_id=bt.trx_id WHERE wt.trx_mysql_thread_id=%d AND bt.trx_mysql_thread_id=%d',$worker,$parent));
        if($observer->last_error!=='')throw new RuntimeException('Synthetic lock observer unavailable');
        $observed=(int)$waiting>0;if(!$observed)usleep(200000); // Shared cache requires >100ms idle.
    }while(!$observed&&microtime(true)<$deadline);
    sx('actual_competing_capture_lock_observed',$worker!==$parent&&$observed);
    $original=$db->get_row('SELECT * FROM '.C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('a',64)."' AND revision=1",ARRAY_A);
    if($db->insert(C::PREFIX.'bsre_consent_captures',captureRow($original,'33333333-3333-4333-8333-333333333333'))===false)throw new RuntimeException('Synthetic competing capture insert failed');
    sq('COMMIT');stream_set_timeout($pipes[1],5);$outcome=trim((string)fgets($pipes[1]));if($outcome==='')throw new RuntimeException('Synthetic selective worker outcome timeout');fclose($pipes[1]);$exit=proc_close($process);$process=null;
    sx('new_capture_invalidates_waiting_plan_without_deletion',$exit===0&&$outcome==='HELD:SELECTIVE_PLAN_STALE_OR_ALTERED'&&$control->anchor()===$before['anchor']&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_consent_captures')===2&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_consent_history')===7);
}finally{
    if(is_resource($process)){try{proc_terminate($process,9);foreach($pipes as$pipe)if(is_resource($pipe))fclose($pipe);proc_close($process);}finally{$db->query('ROLLBACK');}}
    $observer->close();
}

// In the opposite ordering, the real writer owns its full snapshot before a stale stage starts.
$control=fixture();[$plan,$before]=preparePlan($control);$pauseDb=selectiveDb(SelectivePauseDb::class);$writer=controller($pauseDb);
$oldChoice=$db->get_row('SELECT * FROM '.C::PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('a',64)."' AND revision=1",ARRAY_A);
$staleCapture=captureRow($oldChoice,'44444444-4444-4444-8444-444444444444');$staleCapture['state']='STAGED';$staleCapture['lead_id']='';$staleCapture['event_id']='';
$writerConnection=(int)$pauseDb->get_var('SELECT CONNECTION_ID()');$observer=selectiveDb();$process=null;$pipes=[];
$pauseDb->beforeDelete=function()use(&$process,&$pipes,$staleCapture,$writerConnection,$observer){
    $process=proc_open([PHP_BINARY,'-d','sendmail_path=/bin/false',__FILE__,'stage-worker'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
    if(!is_resource($process))throw new RuntimeException('Synthetic producer worker unavailable');
    try{
        fwrite($pipes[0],json_encode(['capture'=>$staleCapture],JSON_THROW_ON_ERROR)."\n");fclose($pipes[0]);stream_set_timeout($pipes[1],5);
        $ready=trim((string)fgets($pipes[1]));if(!preg_match('/^READY:([0-9]+)$/D',$ready,$match))throw new RuntimeException('Synthetic producer worker readiness failed');
        $worker=(int)$match[1];$observed=false;$deadline=microtime(true)+5;
        do{
            $observer->last_error='';$count=$observer->get_var($observer->prepare('SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX wt ON w.requesting_trx_id=wt.trx_id JOIN information_schema.INNODB_TRX bt ON w.blocking_trx_id=bt.trx_id WHERE wt.trx_mysql_thread_id=%d AND bt.trx_mysql_thread_id=%d',$worker,$writerConnection));
            if($observer->last_error!=='')throw new RuntimeException('Synthetic producer lock observer unavailable');
            $observed=(int)$count>0;if(!$observed)usleep(200000);
        }while(!$observed&&microtime(true)<$deadline);
        sx('actual_source_producer_waits_while_writer_owns_snapshot',$worker!==$writerConnection&&$observed);
    }catch(Throwable $error){
        // Stop this owned disposable producer before the controller rolls back/unlocks on failure.
        proc_terminate($process,9);foreach($pipes as$pipe)if(is_resource($pipe))fclose($pipe);proc_close($process);$process=null;throw $error;
    }
};
try{
    $applied=$writer->apply($plan,C::labAcknowledgement($plan),$before['anchor']);
    stream_set_timeout($pipes[1],5);$outcome=trim((string)fgets($pipes[1]));if($outcome==='')throw new RuntimeException('Synthetic producer outcome timeout');
    fclose($pipes[1]);$exit=proc_close($process);$process=null;
    sx('stale_source_cannot_resurrect_retired_choice_or_capture',$exit===0&&$outcome==='RETIRED'&&$applied['deleted_rows']===4&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PREFIX.'bsre_consent_captures')===1&&P::digest($control->reviewSource()['snapshot'])===$plan['expected_after_hash']);
}finally{
    if(is_resource($process)){proc_terminate($process,9);foreach($pipes as$pipe)if(is_resource($pipe))fclose($pipe);proc_close($process);}
    $pauseDb->close();$observer->close();
}
echo wp_json_encode(['phase'=>'selective_choice_application','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'history_gap_clearing_available'=>false,'production_acceptance'=>false,'reopen_authorized'=>false])."\n";
