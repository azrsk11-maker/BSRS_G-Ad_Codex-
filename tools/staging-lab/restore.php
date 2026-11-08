<?php
/** Actual SQL restore rehearsal on synthetic consent tables, never provider data. */
define('WP_ENVIRONMENT_TYPE','local'); define('BSRE_RETENTION_LAB',true); define('BSRE_RETENTION_APPLY_ENABLED',true);
require '/opt/wordpress/wp-load.php';
require '/opt/lab/consent-retention/candidate-store.php';
require '/opt/lab/consent-retention/PreferenceRetirement.php';
use BSRE\RetentionCandidate\WpConsentRepository;
use BSRE\RetentionReview\PreferenceRetirement;
use BSRE\RetentionReview\RetirementLedger;
$db=new wpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST); $db->set_prefix($wpdb->prefix); $db->prefix='retention_synthetic_';
$store=new WpConsentRepository($db);
wp_set_current_user(get_user_by('login','synthetic_owner')->ID);
$clock=(new DateTimeImmutable('2026-11-08T12:00:00+04:00'))->getTimestamp();
$retirement=new PreferenceRetirement($db,fn()=>$GLOBALS['clock']); $retirement->installLabAudit();
$checks=[];
function restore_check(string $name,bool $ok): void { global $checks; if(!$ok)throw new RuntimeException('Restore check failed: '.$name); $checks[$name]=true; }
function restore_denied(callable $fn,string $message): bool {try{$fn();return false;}catch(Throwable $e){return $e->getMessage()===$message;}}
function package_snapshot(array $snapshot,int $watermark,int $now): array {
    $process=proc_open(['node','/opt/lab/backup-bridge.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
    if(!is_resource($process))throw new RuntimeException('Synthetic backup process unavailable');
    fwrite($pipes[0],json_encode(['raw'=>json_encode($snapshot,JSON_THROW_ON_ERROR),'watermark'=>$watermark,'nowMs'=>$now*1000],JSON_THROW_ON_ERROR)); fclose($pipes[0]);
    stream_set_timeout($pipes[1],5); $output=stream_get_contents($pipes[1]); fclose($pipes[1]);
    if(proc_close($process)!==0)throw new RuntimeException('Synthetic encryption bridge failed');
    return json_decode($output,true,32,JSON_THROW_ON_ERROR);
}
function restore_fixture(array $snapshot): void {
    global $db;
    $db->query('START TRANSACTION');
    try {
        foreach(['captures','history','state'] as $part) {
            $table=$db->prefix.'bsre_consent_'.$part;
            if($db->query("DELETE FROM {$table}")===false)throw new RuntimeException('Synthetic restore failed');
            foreach($snapshot[$part] as $row)if($db->insert($table,$row)===false)throw new RuntimeException('Synthetic restore failed');
        }
        $db->query('COMMIT');
    }catch(Throwable $e){$db->query('ROLLBACK');throw $e;}
}
$subject=str_repeat('e',64); $old=$clock-400*86400;
$state=$store->choose($subject,['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_NOTICE',$old);
$before=$retirement->backupSnapshot(); $oldAnchor=$retirement->ledgerAnchor();
$package=package_snapshot($before,$oldAnchor['sequence'],$clock-100);
restore_check('authenticated_package_roundtrip', $package['restoreAuthorized']===false && json_decode($package['raw'],true)===$before);
$plan=$retirement->preview();
$ledgerAdapter=new RetirementLedger($db);
restore_check('ledger_capacity_refuses_append_before_write', restore_denied(fn()=>$ledgerAdapter->record($before,$plan,$clock,['anchor'=>['sequence'=>1000,'hash'=>str_repeat('0',64)],'rows'=>array_fill(0,1000,[])]),'LEDGER_CAPACITY_EXCEEDED'));
$ledgerFault=fn($sql)=>str_starts_with($sql,'INSERT') && str_contains($sql,'bsre_retirement_ledger')?'SYNTHETIC INVALID SQL':$sql;
$db->suppress_errors(true); add_filter('query',$ledgerFault);
restore_check('ledger_write_fault_reported', restore_denied(fn()=>$retirement->apply($plan,PreferenceRetirement::approval($plan)),'LEDGER_STORAGE_UNAVAILABLE'));
remove_filter('query',$ledgerFault); $db->suppress_errors(false);
restore_check('ledger_and_deletion_roll_back_together', $retirement->backupSnapshot()===$before && $retirement->ledgerAnchor()===$oldAnchor);
$result=$retirement->apply($plan,PreferenceRetirement::approval($plan)); $anchor=$result['ledger_anchor'];
restore_check('deletion_records_advance_ledger', $anchor['sequence']>$oldAnchor['sequence'] && $store->current($subject)===null);
$liveCaptures=$retirement->backupSnapshot()['captures'];
restore_fixture(json_decode($package['raw'],true));
restore_check('restore_cannot_roll_back_current_ledger', $retirement->ledgerAnchor()===$anchor);
restore_check('old_package_anchor_not_current_authority', restore_denied(fn()=>$retirement->previewRestore($package['metadata'],$oldAnchor),'CURRENT_LEDGER_ANCHOR_REQUIRED'));
// A restored capture referencing retired evidence must be held, never erased.
$conflict=$before['captures'][0]; $conflict['request_id']=wp_generate_uuid4(); $conflict['subject_key']=$subject;
$conflict['original_revision']=$state['revision']; $conflict['decision_version']=$state['receipt'];
$conflict['state']='STAGED'; $conflict['lead_id']=''; $conflict['event_id']='';
$db->insert($db->prefix.'bsre_consent_captures',$conflict);
$conflictPackage=package_snapshot($retirement->backupSnapshot(),$oldAnchor['sequence'],$clock-100);
restore_check('restored_capture_blocks_automatic_redeletion', restore_denied(fn()=>$retirement->previewRestore($conflictPackage['metadata'],$anchor),'RESTORED_CAPTURE_REQUIRES_RECONCILIATION'));
$db->delete($db->prefix.'bsre_consent_captures',['request_id'=>$conflict['request_id']]);
$restorePlan=$retirement->previewRestore($package['metadata'],$anchor);
restore_check('old_deleted_rows_selected_for_redeletion', count($restorePlan['eligible'])===2);
restore_check('restore_requires_exact_approval', restore_denied(fn()=>$retirement->applyRestore($restorePlan,'invalid',$anchor),'EXACT_RESTORE_APPROVAL_REQUIRED'));
$clock+=900;
restore_check('restore_plan_expires', restore_denied(fn()=>$retirement->applyRestore($restorePlan,PreferenceRetirement::restoreApproval($restorePlan),$anchor),'PLAN_EXPIRED_OR_INVALID'));
$clock-=900;
$fault=fn($sql)=>str_starts_with($sql,"DELETE FROM {$db->prefix}bsre_consent_state ")?'SYNTHETIC INVALID SQL':$sql;
$db->suppress_errors(true); add_filter('query',$fault);
restore_check('restore_delete_fault_reported', restore_denied(fn()=>$retirement->applyRestore($restorePlan,PreferenceRetirement::restoreApproval($restorePlan),$anchor),'RETENTION_STORAGE_UNAVAILABLE'));
remove_filter('query',$fault); $db->suppress_errors(false);
restore_check('restore_rollback_preserves_snapshot', $retirement->backupSnapshot()===$before);
restore_check('restore_rollback_has_no_success_audit', (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_restore_audit")===0);
$reapplied=$retirement->applyRestore($restorePlan,PreferenceRetirement::restoreApproval($restorePlan),$anchor);
restore_check('retention_reapplied_before_any_reopen', $reapplied['reapplied_rows']===2 && $reapplied['reopen_authorized']===false && $store->current($subject)===null);
restore_check('accepted_capture_evidence_preserved', $retirement->backupSnapshot()['captures']===$liveCaptures);
restore_check('restore_success_private_audit', (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_restore_audit")===1);
// A new receipt must survive a later snapshot, even when the subject key repeats.
$newState=$store->choose($subject,['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_NOTICE',$clock);
$newSnapshot=$retirement->backupSnapshot(); $newPackage=package_snapshot($newSnapshot,$anchor['sequence'],$clock);
$cleanPlan=$retirement->previewRestore($newPackage['metadata'],$anchor);
restore_check('new_choice_not_erased_by_old_tombstone', $cleanPlan['eligible']===[] && $store->current($subject)['receipt']===$newState['receipt']);
$badMetadata=$newPackage['metadata']; $badMetadata['deletionLedgerWatermark']=$anchor['sequence']+1;
restore_check('future_watermark_rejected', restore_denied(fn()=>$retirement->previewRestore($badMetadata,$anchor),'CURRENT_LEDGER_ANCHOR_REQUIRED'));
$clock+=2592000;
restore_check('expired_backup_never_reopens', restore_denied(fn()=>$retirement->previewRestore($newPackage['metadata'],$anchor),'BACKUP_METADATA_INVALID_OR_EXPIRED'));
$clock-=2592000;
// Current ledger corruption and truncation must be detected, never treated as empty.
$last=$db->get_row("SELECT * FROM {$db->prefix}bsre_retirement_ledger ORDER BY sequence_no DESC LIMIT 1",ARRAY_A);
$db->update($db->prefix.'bsre_retirement_ledger',['row_hash'=>str_repeat('0',64)],['sequence_no'=>$last['sequence_no']]);
restore_check('tampered_ledger_blocks_recovery', restore_denied(fn()=>$retirement->ledgerAnchor(),'LEDGER_CHAIN_INVALID'));
$db->update($db->prefix.'bsre_retirement_ledger',['row_hash'=>$last['row_hash']],['sequence_no'=>$last['sequence_no']]);
$db->delete($db->prefix.'bsre_retirement_ledger',['sequence_no'=>$last['sequence_no']]);
restore_check('truncated_ledger_blocks_recovery', restore_denied(fn()=>$retirement->ledgerAnchor(),'LEDGER_CHECKPOINT_MISMATCH'));
$db->insert($db->prefix.'bsre_retirement_ledger',$last);
restore_check('verified_ledger_restored_after_fault_fixture', $retirement->ledgerAnchor()===$anchor);
echo wp_json_encode(['phase'=>'retention_restore_rehearsal','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'ledger_is_outside_restored_three_tables'=>true,'provider_restore_accepted'=>false,'production_reopen_authorized'=>false]) . "\n";
