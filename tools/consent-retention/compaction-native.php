<?php
declare(strict_types=1);
/** Actual disposable MariaDB behavior; never production data or the earlier fixture prefix. */
define('WP_ENVIRONMENT_TYPE','local');
define('BSRE_RETENTION_LAB',true);
define('BSRE_RETENTION_APPLY_ENABLED',true);
define('BSRE_RETENTION_COMPACTION_ENABLED',true);
require '/opt/wordpress/wp-load.php';
require '/opt/lab/consent-retention/candidate-store.php';
require __DIR__.'/PreferenceRetirement.php';
use BSRE\RetentionCandidate\WpConsentRepository;
use BSRE\RetentionReview\PreferenceRetirement;
use BSRE\RetentionReview\RetirementLedger;
use BSRE\RetentionReview\RetentionInventory;

// A new connection avoids sharing mysqli result handles with global WordPress wpdb.
$db=new wpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);
$db->set_prefix($wpdb->prefix); $db->prefix='retention_compaction_synthetic_';
wp_set_current_user(get_user_by('login','synthetic_owner')->ID);
$clock=2000000000;
$control=new PreferenceRetirement($db,fn()=>$GLOBALS['clock']);
$adapter=new RetirementLedger($db);
if (($argv[1]??'')==='compact-worker') {
    $request=json_decode(trim(fgets(STDIN)),true,32,JSON_THROW_ON_ERROR);
    $clock=$request['clock'];
    $db->suppress_errors(true);
    $checkpointSql="SELECT * FROM {$db->prefix}bsre_retirement_checkpoint WHERE id=1 FOR UPDATE";
    add_filter('query',static function($sql) use($checkpointSql) {
        if ($sql===$checkpointSql) { echo "CHECKPOINT_LOCK_ATTEMPT\n"; fflush(STDOUT); }
        return $sql;
    });
    echo 'READY:'.$db->get_var('SELECT CONNECTION_ID()')."\n"; fflush(STDOUT);
    try { $control->applyLedgerCompaction($request['plan'],$request['approval'],$request['anchor']); echo "COMPACTED\n"; }
    catch(Throwable $error) {
        $code=preg_match('/^[A-Z][A-Z0-9_]{0,79}$/D',$error->getMessage()) ? $error->getMessage() : 'UNCLASSIFIED_WORKER_FAILURE';
        echo 'HELD:'.$code."\n";
    }
    fflush(STDOUT);
    exit;
}
$checks=[];
function nc(string $name,bool $condition): void { global $checks; if(!$condition)throw new RuntimeException('Native compaction check failed: '.$name); $checks[$name]=true; }
function nd(callable $call,string $code): bool { try{$call();return false;}catch(Throwable $e){return $e->getMessage()===$code;} }
function nq(string $sql): void { global $db; if($db->query($sql)===false)throw new RuntimeException('Synthetic compaction fixture SQL failed'); }
function restoreOwnFixture(array $snapshot): void {
    global $db;
    nq('START TRANSACTION');
    try {
        foreach(['captures','history','state'] as $part) {
            nq("DELETE FROM {$db->prefix}bsre_consent_{$part}");
            foreach($snapshot[$part] as $row) if($db->insert($db->prefix.'bsre_consent_'.$part,$row)===false)throw new RuntimeException('Synthetic fixture insert failed');
        }
        nq('COMMIT');
    } catch(Throwable $error) { $db->query('ROLLBACK'); throw $error; }
}
function metadata(array $snapshot,array $anchor,int $now): array {
    return ['version'=>1,'source'=>'SYNTHETIC_BSRE_LAB','createdAtMs'=>$now*1000,'expiresAtMs'=>($now+2592000)*1000,
        'snapshotSha256'=>hash('sha256',json_encode($snapshot,JSON_THROW_ON_ERROR)),'deletionLedgerWatermark'=>$anchor['sequence']];
}
$original=$wpdb; $wpdb=$db;
nc('separate_synthetic_consent_schema',BSRE\RetentionCandidate\install_consent_storage());
$wpdb=$original;
$control->installLabAudit(); $store=new WpConsentRepository($db);
nc('no_compaction_preserves_legacy_anchor',array_keys($control->ledgerAnchor())===['sequence','hash']);
$base=$clock; $saved=null;
foreach(['a','b','c'] as $index=>$digit) {
    $clock=$base+$index*86400;
    $store->choose(str_repeat($digit,64),['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_COMPACTION_NOTICE',$base-400*86400);
    if ($saved===null) $saved=$control->backupSnapshot();
    $retire=$control->preview(); $control->apply($retire,PreferenceRetirement::approval($retire));
}
$clock=$base+2592000-1; $before=$adapter->read(false); $anchor=$before['anchor'];
$nothing=$control->previewLedgerCompaction($anchor);
$noop=$control->applyLedgerCompaction($nothing,PreferenceRetirement::compactionApproval($nothing),$anchor);
nc('no_due_compaction_creates_no_history_gap',$noop['deleted_ledger_rows']===0 && !$noop['history_gap_after_compaction'] && $control->ledgerAnchor()===$anchor);
nc('no_due_compaction_has_no_purge_audit',(int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_ledger_compaction_audit")===0);
$clock=$base+2592000; $plan=$control->previewLedgerCompaction($anchor);
nc('exact_thirty_day_boundary_prefix',$plan['delete_sequences']===[1]);
nc('wrong_exact_approval_held',nd(fn()=>$adapter->compact($plan,'bad',$anchor,$clock),'EXACT_COMPACTION_APPROVAL_REQUIRED'));
$clock+=900;
nc('expired_plan_held',nd(fn()=>$control->applyLedgerCompaction($plan,PreferenceRetirement::compactionApproval($plan),$anchor),'PLAN_EXPIRED_OR_INVALID'));
$clock-=900;
nq('START TRANSACTION');
nc('nested_transaction_refused_without_rollback',nd(fn()=>$adapter->compact($plan,PreferenceRetirement::compactionApproval($plan),$anchor,$clock),'EXISTING_TRANSACTION_FORBIDDEN') && (string)$db->get_var('SELECT @@session.in_transaction')==='1');
nq('ROLLBACK');
foreach(['floor','audit'] as $fault) {
    $filter=static function($sql) use($fault,$db) {
        $match=$fault==='floor' ? str_starts_with($sql,"UPDATE {$db->prefix}bsre_retirement_floor ") : str_starts_with($sql,"INSERT INTO {$db->prefix}bsre_ledger_compaction_audit ");
        return $match ? 'SYNTHETIC INVALID SQL' : $sql;
    };
    $db->suppress_errors(true); add_filter('query',$filter);
    $failed=nd(fn()=>$adapter->compact($plan,PreferenceRetirement::compactionApproval($plan),$anchor,$clock),'LEDGER_STORAGE_UNAVAILABLE');
    remove_filter('query',$filter); $db->suppress_errors(false);
    nc('direct_'.$fault.'_failure_reported',$failed);
    nc('direct_'.$fault.'_failure_rolls_back_everything',$adapter->read(false)===$before && (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_ledger_compaction_audit")===0);
}
$changed=$plan; $changed['after_floor']['generation']=2;
nc('altered_plan_held',nd(fn()=>$adapter->compact($changed,PreferenceRetirement::compactionApproval($changed),$anchor,$clock),'COMPACTION_PLAN_STALE_OR_ALTERED'));
$result=$adapter->compact($plan,PreferenceRetirement::compactionApproval($plan),$anchor,$clock);
$current=$control->ledgerAnchor(); $after=$adapter->read(false);
nc('direct_helper_is_atomic_controller',$result['deleted_rows']===1 && count($after['rows'])===2 && $current['version']===2 && $current['floor']['sequence']===1);
nc('suffix_chain_and_checkpoint_preserved',$current['sequence']===$anchor['sequence'] && $current['hash']===$anchor['hash'] && $after['rows'][0]['previous_hash']===$current['floor']['hash']);
nc('new_anchor_binds_floor',hash_equals($current['anchor_sha256'],RetirementLedger::rowHash(array_diff_key($current,['anchor_sha256'=>true]))));
nc('audit_contains_only_count_actor_and_digests',(int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_ledger_compaction_audit")===1 && array_keys($db->get_row("SELECT * FROM {$db->prefix}bsre_ledger_compaction_audit LIMIT 1",ARRAY_A))===['plan_hash','applied_at','actor','deleted_rows','floor_sequence','floor_generation','anchor_sha256']);
nc('lost_ack_repeat_is_held_not_reapplied',nd(fn()=>$adapter->compact($plan,PreferenceRetirement::compactionApproval($plan),$anchor,$clock),'CURRENT_LEDGER_ANCHOR_REQUIRED') && count($adapter->read(false)['rows'])===2 && (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_ledger_compaction_audit")===1);
restoreOwnFixture($saved);
$package=metadata($saved,$current,$clock);
nc('expired_identity_cannot_resurrect_via_fresh_metadata',nd(fn()=>$control->previewRestore($package,$current),'COMPACTED_HISTORY_REQUIRES_RECONCILIATION'));
$subset=['sequence'=>$current['sequence'],'hash'=>$current['hash']];
nc('stripped_floor_anchor_held',nd(fn()=>$control->previewRestore($package,$subset),'CURRENT_LEDGER_ANCHOR_REQUIRED'));
$forged=$package; $forged['complete_recovery_verified']=true;
nc('caller_boolean_cannot_waive_gap',nd(fn()=>$control->previewRestore($forged,$current),'BACKUP_METADATA_INVALID_OR_EXPIRED'));
$floorRow=$db->get_row("SELECT * FROM {$db->prefix}bsre_retirement_floor WHERE id=1",ARRAY_A);
nq("DELETE FROM {$db->prefix}bsre_retirement_floor WHERE id=1");
nc('missing_floor_cannot_hide_pruning',nd(fn()=>$control->ledgerAnchor(),'LEDGER_MISSING_OR_UNBOUNDED'));
if($db->insert($db->prefix.'bsre_retirement_floor',$floorRow)===false)throw new RuntimeException('Synthetic floor recovery failed');
$empty=['kind'=>RetentionInventory::KIND,'state'=>[],'history'=>[],'captures'=>[]];
restoreOwnFixture($empty);
$emptyPlan=$control->previewRestore(metadata($empty,$current,$clock),$current);
$emptyResult=$control->applyRestore($emptyPlan,PreferenceRetirement::restoreApproval($emptyPlan),$current);
nc('empty_recovery_never_reopens_or_erases_gap',$emptyResult['reopen_authorized']===false && $control->ledgerAnchor()['floor']['generation']===1);

// A fresh, separately labelled fixture proves capacity is retained-row count, not lifetime sequence.
foreach(['bsre_retirement_ledger','bsre_retirement_checkpoint','bsre_retirement_floor','bsre_ledger_compaction_audit'] as $table) nq("DELETE FROM {$db->prefix}{$table}");
$adapter->install(); $previous=str_repeat('0',64);
nq('START TRANSACTION');
for($sequence=1;$sequence<=1000;++$sequence) {
    $row=['sequence_no'=>$sequence,'previous_hash'=>$previous,'subject_key'=>hash('sha256','SYNTHETIC:'.$sequence),'receipt'=>str_pad(dechex($sequence),32,'0',STR_PAD_LEFT),'revision'=>1,'row_hash'=>hash('sha256','SYNTHETIC_HISTORY:'.$sequence),'retired_at'=>$clock-2592000,'expires_at'=>$clock,'plan_hash'=>hash('sha256','SYNTHETIC_PLAN')];
    $row['chain_hash']=RetirementLedger::rowHash($row); $previous=$row['chain_hash'];
    if($db->insert($db->prefix.'bsre_retirement_ledger',$row)===false)throw new RuntimeException('Synthetic capacity insert failed');
}
nq($db->prepare("UPDATE {$db->prefix}bsre_retirement_checkpoint SET sequence_no=1000,chain_hash=%s WHERE id=1",$previous)); nq('COMMIT');
$full=$control->ledgerAnchor(); $fullPlan=$control->previewLedgerCompaction($full);
$compacted=$control->applyLedgerCompaction($fullPlan,PreferenceRetirement::compactionApproval($fullPlan),$full);
nc('full_expired_ledger_compacts_to_bound_floor',$compacted['deleted_ledger_rows']===1000 && count($adapter->read(false)['rows'])===0 && $compacted['ledger_anchor']['floor']['sequence']===1000);
$store->choose(str_repeat('d',64),['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_APPEND_NOTICE',$clock-400*86400);
$retire=$control->preview(); $control->apply($retire,PreferenceRetirement::approval($retire));
$appended=$control->ledgerAnchor();
nc('append_after_sequence1000_uses_reclaimed_capacity',$appended['sequence']===1001 && count($adapter->read(false)['rows'])===1);
nc('history_gap_survives_empty_suffix_and_append',$appended['version']===2 && $appended['floor']['generation']===1 && $appended['floor']['sequence']===1000);
nq("UPDATE {$db->prefix}bsre_retirement_checkpoint SET sequence_no=18446744073709551615 WHERE id=1");
nc('real_unsigned_database_overflow_held',nd(fn()=>$control->ledgerAnchor(),'LEDGER_INTEGER_OUT_OF_RANGE'));
nq("UPDATE {$db->prefix}bsre_retirement_checkpoint SET sequence_no=1001 WHERE id=1");

// A second process must actually wait for the checkpoint lock, then reject its stale authority.
$clock+=2592000; $waitingAnchor=$control->ledgerAnchor(); $waitingPlan=$control->previewLedgerCompaction($waitingAnchor);
$parentConnection=(int)$db->get_var('SELECT CONNECTION_ID()');
// Metadata is observed on its own connection, never inside the blocking transaction.
$observer=new wpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST); $observer->suppress_errors(true);
$observerConnection=(int)$observer->get_var('SELECT CONNECTION_ID()');
nq('START TRANSACTION'); $locked=$adapter->read(true);
$parentTransaction=(string)$db->get_var('SELECT @@session.in_transaction');
$process=proc_open([PHP_BINARY,'-d','sendmail_path=/bin/false',__FILE__,'compact-worker'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
if(!is_resource($process)){ $db->query('ROLLBACK'); $observer->close(); throw new RuntimeException('Synthetic compaction worker unavailable'); }
$workerConnection=null; $workerOutcome=null; $workerExit=null; $attempted=false; $lastWaitCount=null; $observerError='NONE';
$diagnostic=static function(string $stage) use(&$process,&$workerConnection,&$workerOutcome,&$workerExit,&$attempted,&$lastWaitCount,&$observerError,$parentConnection,$observerConnection,$parentTransaction,$db,$observer) {
    $status=is_resource($process) ? proc_get_status($process) : ['running'=>false,'exitcode'=>$workerExit];
    $knownExit=is_int($status['exitcode']) && $status['exitcode']>=0;
    $active=(string)$db->get_var('SELECT @@session.in_transaction');
    $metadata=['collection_error'=>false];
    try {
        $countValue=static function($value) { return is_scalar($value) && preg_match('/^[0-9]{1,7}$/D',(string)$value) && (int)$value<=1000000 ? (int)$value : null; };
        $errorClass=static function($error): string {
            if ($error==='') return 'NONE';
            $text=strtolower((string)$error);
            return str_contains($text,'denied')?'ACCESS_DENIED':(str_contains($text,'unknown column')?'METADATA_SCHEMA_MISMATCH':(str_contains($text,'exist')?'METADATA_TABLE_UNAVAILABLE':'QUERY_ERROR'));
        };
        $parentNow=(int)$db->get_var('SELECT CONNECTION_ID()');
        $observerNow=(int)$observer->get_var('SELECT CONNECTION_ID()');
        $metadata['connection_identity']=['parent_current'=>$parentNow,'parent_matches_ready'=>$parentNow===$parentConnection,
            'observer_current'=>$observerNow,'observer_matches_ready'=>$observerNow===$observerConnection,
            'parent_schema_matches_expected'=>$db->get_var('SELECT DATABASE()')===DB_NAME,
            'observer_schema_matches_expected'=>$observer->get_var('SELECT DATABASE()')===DB_NAME,
            'parent_prefix_matches_expected'=>$db->prefix==='retention_compaction_synthetic_'];
        $observer->last_error='';
        // Only this synthetic schema's active statements, plus the exact known parent/worker IDs.
        // Raw INFO, database, user and host fields are never copied into the receipt.
        $processRows=$observer->get_results($observer->prepare('SELECT ID,COMMAND,STATE,DB,INFO FROM information_schema.PROCESSLIST WHERE ID IN (%d,%d) OR (DB=%s AND COMMAND=%s AND ID<>%d) ORDER BY ID LIMIT 8',$parentConnection,(int)$workerConnection,DB_NAME,'Query',$observerNow),ARRAY_A);
        $metadata['processlist_error']=$errorClass($observer->last_error);
        $metadata['processlist']=[]; $threads=[$parentConnection,(int)$workerConnection,$parentNow];
        $tables=['retention_compaction_synthetic_bsre_retirement_checkpoint'=>'CHECKPOINT',
            'retention_compaction_synthetic_bsre_retirement_floor'=>'FLOOR',
            'retention_compaction_synthetic_bsre_retirement_ledger'=>'LEDGER'];
        foreach(is_array($processRows)?$processRows:[] as $row) {
            $id=(int)$row['ID']; $threads[]=$id; $statement=trim((string)($row['INFO']??''));
            $statementClass=$statement===''?'IDLE':'OTHER'; $tableClass=null;
            foreach($tables as $table=>$tableLabel) {
                if (preg_match('/^SHOW\s+FULL\s+COLUMNS\s+FROM\s+`?'.preg_quote($table,'/').'`?(?:\s|$)/iD',$statement)) { $statementClass='SHOW_FULL_COLUMNS'; $tableClass=$tableLabel; }
                elseif (preg_match('/^SHOW\s+TABLE\s+STATUS\s+WHERE\s+Name\s*=\s*[\'\"]'.preg_quote($table,'/').'[\'\"]/iD',$statement)) { $statementClass='SHOW_TABLE_STATUS'; $tableClass=$tableLabel; }
                elseif ($statement==='SELECT * FROM '.$table.' WHERE id=1 FOR UPDATE') { $statementClass=$tableLabel.'_FOR_UPDATE'; $tableClass=$tableLabel; }
                elseif ($tableLabel==='LEDGER' && $statement==='SELECT * FROM '.$table.' ORDER BY sequence_no LIMIT 1001 FOR UPDATE') { $statementClass='LEDGER_FOR_UPDATE'; $tableClass=$tableLabel; }
            }
            $state=strtolower(trim((string)($row['STATE']??'')));
            $states=[''=>'EMPTY','waiting for table metadata lock'=>'METADATA_LOCK','waiting for table level lock'=>'TABLE_LEVEL_LOCK',
                'waiting for table flush'=>'TABLE_FLUSH','waiting for global read lock'=>'GLOBAL_READ_LOCK','statistics'=>'STATISTICS',
                'sending data'=>'SENDING_DATA','executing'=>'EXECUTING','updating'=>'UPDATING','opening tables'=>'OPENING_TABLES',
                'closing tables'=>'CLOSING_TABLES','starting'=>'STARTING','waiting for handler commit'=>'HANDLER_COMMIT'];
            $metadata['processlist'][]=['connection'=>$id,'role'=>$id===$parentNow?'PARENT':($id===$workerConnection?'WORKER_READY_ID':'OTHER_ACTIVE_IN_SYNTHETIC_SCHEMA'),
                'schema_matches_expected'=>($row['DB']??null)===DB_NAME,
                'command'=>in_array($row['COMMAND'],['Query','Sleep','Killed'],true)?strtoupper($row['COMMAND']):'OTHER',
                'state'=>$states[$state]??'OTHER','statement_class'=>$statementClass,'table_class'=>$tableClass];
        }
        $metadata['processlist_limit_reached']=is_array($processRows) && count($processRows)===8;
        $threads=array_values(array_unique(array_filter($threads,static fn($id)=>$id>0)));
        $observer->last_error='';
        $trxRows=$observer->get_results('SELECT trx_mysql_thread_id,trx_state,trx_rows_locked,trx_tables_locked,trx_requested_lock_id FROM information_schema.INNODB_TRX WHERE trx_mysql_thread_id IN ('.implode(',',$threads).') ORDER BY trx_mysql_thread_id LIMIT 10',ARRAY_A);
        $metadata['transaction_error']=$errorClass($observer->last_error); $metadata['transactions']=[];
        foreach(is_array($trxRows)?$trxRows:[] as $row) $metadata['transactions'][]=['connection'=>(int)$row['trx_mysql_thread_id'],
            'state'=>in_array($row['trx_state'],['RUNNING','LOCK WAIT','ROLLING BACK','COMMITTING'],true)?$row['trx_state']:'OTHER',
            'rows_locked'=>$countValue($row['trx_rows_locked']),'tables_locked'=>$countValue($row['trx_tables_locked']),
            'requested_lock_present'=>$row['trx_requested_lock_id']!==null && $row['trx_requested_lock_id']!==''];
        $observer->last_error='';
        $waits=$observer->get_row($observer->prepare('SELECT (SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS) AS all_waits,(SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX t ON w.requesting_trx_id=t.trx_id WHERE t.trx_mysql_thread_id=%d) AS requester_waits,(SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX t ON w.blocking_trx_id=t.trx_id WHERE t.trx_mysql_thread_id=%d) AS blocker_waits',(int)$workerConnection,$parentNow),ARRAY_A);
        $metadata['wait_metadata_error']=$errorClass($observer->last_error);
        $metadata['wait_counts']=['all_unjoined'=>$countValue($waits['all_waits']??null),'worker_requester_only'=>$countValue($waits['requester_waits']??null),'parent_blocker_only'=>$countValue($waits['blocker_waits']??null)];
    } catch(Throwable $error) { $metadata['collection_error']=true; }
    fwrite(STDERR,wp_json_encode(['phase'=>'retirement_ledger_compaction_contention_diagnostic','status'=>'FAIL','stage'=>$stage,
        'parent_connection'=>$parentConnection,'observer_connection'=>$observerConnection,'worker_connection'=>$workerConnection,
        'parent_transaction_before_worker'=>$parentTransaction,'parent_transaction_at_failure'=>in_array($active,['0','1'],true)?$active:'UNKNOWN',
        'worker_reached_checkpoint_query'=>$attempted,'worker_running'=>(bool)$status['running'],
        'worker_exit_code'=>$status['running']||!$knownExit?null:$status['exitcode'],'worker_exit_code_known'=>!$status['running']&&$knownExit,'worker_outcome'=>$workerOutcome,
        'observer_query'=>'INNODB_LOCK_WAITS_REQUESTER_AND_BLOCKER','observer_error'=>$observerError,'last_wait_count'=>$lastWaitCount,'metadata'=>$metadata])."\n");
};
try {
    fwrite($pipes[0],json_encode(['clock'=>$clock,'plan'=>$waitingPlan,'approval'=>PreferenceRetirement::compactionApproval($waitingPlan),'anchor'=>$waitingAnchor],JSON_THROW_ON_ERROR)."\n"); fclose($pipes[0]);
    stream_set_timeout($pipes[1],5); $ready=trim((string)fgets($pipes[1]));
    if(!preg_match('/^READY:([0-9]+)$/D',$ready,$match)){ $workerOutcome='READY_NOT_RECEIVED'; $diagnostic('WORKER_READY_PROTOCOL'); throw new RuntimeException('Synthetic worker did not become ready'); }
    $workerConnection=(int)$match[1];
    if ($parentTransaction!=='1' || min($parentConnection,$observerConnection,$workerConnection)<=0 || count(array_unique([$parentConnection,$observerConnection,$workerConnection]))!==3) {
        $diagnostic('INVALID_CONNECTION_OR_TRANSACTION_SETUP');
        throw new RuntimeException('Synthetic compaction contention setup invalid');
    }
    stream_set_blocking($pipes[1],false); $workerBuffer='';
    $observed=false; $deadline=microtime(true)+5;
    do {
        $workerBuffer.=(string)stream_get_contents($pipes[1]);
        if (strlen($workerBuffer)>1024) { $workerOutcome='PROTOCOL_OUTPUT_TOO_LARGE'; break; }
        while(($newline=strpos($workerBuffer,"\n"))!==false) {
            $line=trim(substr($workerBuffer,0,$newline)); $workerBuffer=substr($workerBuffer,$newline+1);
            if ($line==='CHECKPOINT_LOCK_ATTEMPT') $attempted=true;
            elseif ($line==='COMPACTED' || preg_match('/^HELD:[A-Z][A-Z0-9_]{0,79}$/D',$line)) $workerOutcome=$line;
            else $workerOutcome='UNCLASSIFIED_WORKER_OUTPUT';
        }
        if ($workerOutcome!==null) break;
        $observer->last_error='';
        $count=$observer->get_var($observer->prepare('SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX wt ON w.requesting_trx_id=wt.trx_id JOIN information_schema.INNODB_TRX bt ON w.blocking_trx_id=bt.trx_id WHERE wt.trx_mysql_thread_id=%d AND bt.trx_mysql_thread_id=%d',$workerConnection,$parentConnection));
        if ($observer->last_error!=='') {
            $error=strtolower($observer->last_error);
            $observerError=str_contains($error,'denied')?'ACCESS_DENIED':(str_contains($error,'unknown column')?'METADATA_SCHEMA_MISMATCH':(str_contains($error,'exist')?'METADATA_TABLE_UNAVAILABLE':'QUERY_ERROR'));
            break;
        }
        if (!is_scalar($count) || !preg_match('/^[0-9]+$/D',(string)$count)) { $observerError='INVALID_COUNT_RESULT'; break; }
        $lastWaitCount=(int)$count; $observed=$attempted && $lastWaitCount>0;
        // MariaDB's shared InnoDB metadata cache refreshes only after >100ms idle.
        // Every read resets its idle timer: 20ms polling can pin the pre-worker snapshot.
        // Keep the same five-second deadline and actual waiter/blocker proof.
        if(!$observed)usleep(200000);
    } while(!$observed && microtime(true)<$deadline);
    if (!$observed) $diagnostic('CHECKPOINT_LOCK_NOT_OBSERVED');
    nc('concurrent_compactor_waits_on_real_checkpoint_lock',$observed);
    $history=['subject_key'=>str_repeat('e',64),'receipt'=>str_repeat('f',32),'revision'=>1,'analytics'=>0,'ad_measurement'=>0,'personalization'=>0,'notice_version'=>'SYNTHETIC_CONCURRENT','changed_at'=>$clock-400*86400,'uncertain'=>0];
    $adapter->record(['history'=>[$history]],['eligible'=>['bsre_consent_history:'.$history['receipt']]],$clock,$locked);
    nq('COMMIT');
    stream_set_blocking($pipes[1],true); stream_set_timeout($pipes[1],5);
    // Only proc_close's known zero can pass; a consumed/unknown (-1) exit never becomes success.
    $outcome=trim((string)fgets($pipes[1])); fclose($pipes[1]); $exit=proc_close($process); $process=null; $workerExit=$exit;
    if ($exit!==0 || $outcome!=='HELD:CURRENT_LEDGER_ANCHOR_REQUIRED') {
        $workerOutcome=preg_match('/^(?:COMPACTED|HELD:[A-Z][A-Z0-9_]{0,79})$/D',$outcome)?$outcome:'UNCLASSIFIED_WORKER_OUTPUT';
        $diagnostic('POST_RELEASE_WORKER_OUTCOME');
    }
    nc('concurrent_append_invalidates_waiting_compaction',$exit===0 && $outcome==='HELD:CURRENT_LEDGER_ANCHOR_REQUIRED' && count($adapter->read(false)['rows'])===2);
} finally {
    try {
        if(is_resource($process)) {
            try {
                // This disposable Linux worker is owned by this harness. Reap it before unlocking.
                proc_terminate($process,9);
                foreach($pipes as $pipe)if(is_resource($pipe))fclose($pipe);
                proc_close($process); $process=null;
            } finally { $db->query('ROLLBACK'); }
        }
    } finally { $observer->close(); }
}
// Runs only after the base lock/stale-authority acceptance above; never masks that gate.
require_once '/opt/lab/purpose-retention/PreferenceRetirement.php';
$purposeDb=new wpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);
$purposeDb->set_prefix($wpdb->prefix); $purposeDb->prefix='purpose_compact_synthetic_';
$purposeTables=['bsre_retention_audit','bsre_restore_audit','bsre_retirement_checkpoint','bsre_retirement_floor','bsre_retirement_ledger','bsre_ledger_compaction_audit'];
nc('derived_compaction_names_fit_database_limit',count(array_filter($purposeTables,static fn($table)=>strlen('purpose_compact_synthetic_'.$table)>64))===0);
$purposeControl=new BSRE\PurposeRetention\PreferenceRetirement($purposeDb,fn()=>$GLOBALS['clock']);
$purposeControl->installLabAudit();
foreach($purposeTables as $table) {
    $status=$purposeDb->get_row($purposeDb->prepare('SHOW TABLE STATUS WHERE Name=%s',$purposeDb->prefix.$table),ARRAY_A);
    if(!$status || strtolower($status['Engine'])!=='innodb')throw new RuntimeException('Synthetic derived compaction table missing');
}
nc('derived_compaction_tables_materialize',true);
$purposeAnchor=$purposeControl->ledgerAnchor();
$purposePlan=$purposeControl->previewLedgerCompaction($purposeAnchor);
$purposeResult=$purposeControl->applyLedgerCompaction($purposePlan,BSRE\PurposeRetention\PreferenceRetirement::compactionApproval($purposePlan),$purposeAnchor);
nc('derived_empty_compaction_preserves_legacy_anchor',array_keys($purposeAnchor)===['sequence','hash'] && $purposePlan['delete_sequences']===[] && $purposeResult['deleted_ledger_rows']===0 && $purposeResult['history_gap_after_compaction']===false && $purposeControl->ledgerAnchor()===$purposeAnchor);
$purposeDb->close();
echo wp_json_encode(['phase'=>'retirement_ledger_compaction','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'prefix'=>'retention_compaction_synthetic_','nonempty_recovery_authorized'=>false,'production_reopen_authorized'=>false])."\n";
