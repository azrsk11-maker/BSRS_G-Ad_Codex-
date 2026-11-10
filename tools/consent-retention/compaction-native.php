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
    echo 'READY:'.$db->get_var('SELECT CONNECTION_ID()')."\n"; fflush(STDOUT);
    try { $control->applyLedgerCompaction($request['plan'],$request['approval'],$request['anchor']); echo "COMPACTED\n"; }
    catch(Throwable $error) { echo 'HELD:'.$error->getMessage()."\n"; }
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
nq('START TRANSACTION'); $locked=$adapter->read(true);
$process=proc_open([PHP_BINARY,__FILE__,'compact-worker'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
if(!is_resource($process))throw new RuntimeException('Synthetic compaction worker unavailable');
try {
    fwrite($pipes[0],json_encode(['clock'=>$clock,'plan'=>$waitingPlan,'approval'=>PreferenceRetirement::compactionApproval($waitingPlan),'anchor'=>$waitingAnchor],JSON_THROW_ON_ERROR)."\n"); fclose($pipes[0]);
    stream_set_timeout($pipes[1],5); $ready=trim((string)fgets($pipes[1]));
    if(!preg_match('/^READY:([0-9]+)$/D',$ready,$match))throw new RuntimeException('Synthetic worker did not become ready');
    $observed=false; $deadline=microtime(true)+5;
    do {
        $observed=(int)$db->get_var($db->prepare('SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX t ON w.requesting_trx_id=t.trx_id WHERE t.trx_mysql_thread_id=%d',(int)$match[1]))>0;
        if(!$observed)usleep(20000);
    } while(!$observed && microtime(true)<$deadline);
    nc('concurrent_compactor_waits_on_real_checkpoint_lock',$observed);
    $history=['subject_key'=>str_repeat('e',64),'receipt'=>str_repeat('f',32),'revision'=>1,'analytics'=>0,'ad_measurement'=>0,'personalization'=>0,'notice_version'=>'SYNTHETIC_CONCURRENT','changed_at'=>$clock-400*86400,'uncertain'=>0];
    $adapter->record(['history'=>[$history]],['eligible'=>['bsre_consent_history:'.$history['receipt']]],$clock,$locked);
    nq('COMMIT');
    $outcome=trim((string)fgets($pipes[1])); fclose($pipes[1]); $exit=proc_close($process); $process=null;
    nc('concurrent_append_invalidates_waiting_compaction',$exit===0 && $outcome==='HELD:CURRENT_LEDGER_ANCHOR_REQUIRED' && count($adapter->read(false)['rows'])===2);
} finally { if(is_resource($process)){ $db->query('ROLLBACK'); proc_terminate($process); proc_close($process); } }
echo wp_json_encode(['phase'=>'retirement_ledger_compaction','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'prefix'=>'retention_compaction_synthetic_','nonempty_recovery_authorized'=>false,'production_reopen_authorized'=>false])."\n";
