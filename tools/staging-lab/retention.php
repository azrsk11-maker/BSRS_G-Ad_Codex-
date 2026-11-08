<?php
/** Disposable DB only. No production table, routing, mail or backup access. */
define('WP_ENVIRONMENT_TYPE', 'local');
define('BSRE_RETENTION_LAB', true);
require '/opt/wordpress/wp-load.php';
require '/opt/lab/consent-retention/candidate-store.php';
require '/opt/lab/consent-retention/PreferenceRetirement.php';
use BSRE\RetentionCandidate\WpConsentRepository;
use BSRE\RetentionReview\PreferenceRetirement;
use BSRE\RetentionReview\RetentionInventory;
$db = clone $wpdb; $db->prefix = 'retention_synthetic_';
$store = new WpConsentRepository($db);
if (($argv[1] ?? '') === 'stage-worker') {
    $capture = json_decode(trim(fgets(STDIN)), true, 32, JSON_THROW_ON_ERROR);
    echo 'READY:' . $db->get_var('SELECT CONNECTION_ID()') . "\n"; fflush(STDOUT);
    try { $store->stage($capture); echo "STAGED\n"; }
    catch (Throwable $e) { echo "RETIRED\n"; }
    exit;
}
$checks = [];
function retention_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Retention check failed: ' . $name);
    $checks[$name] = true;
}
function denied(callable $fn, string $message): bool {
    try { $fn(); return false; } catch (Throwable $e) { return $e->getMessage() === $message; }
}
$original = $wpdb; $wpdb = $db;
retention_check('candidate_schema', BSRE\RetentionCandidate\install_consent_storage());
$wpdb = $original;
$now = (new DateTimeImmutable('2026-11-08T12:00:00+04:00'))->getTimestamp();
$clock = $now;
$retirement = new PreferenceRetirement($db, fn() => $GLOBALS['clock']);
$retirement->installLabAudit();
$subject = str_repeat('a',64);
$old = (new DateTimeImmutable('2025-10-01T12:00:00+04:00'))->getTimestamp();
$state = $store->choose($subject, ['analytics'=>false,'ad_measurement'=>false], 'SYNTHETIC_NOTICE', $old);
retention_check('anonymous_preview_denied', denied(fn() => $retirement->preview(), 'OWNER_REQUIRED'));
wp_set_current_user(get_user_by('login','synthetic_owner')->ID);
$plan = $retirement->preview();
retention_check('old_refusal_eligible', count($plan['eligible']) === 2);
retention_check('preview_does_not_delete', $store->current($subject) !== null);
retention_check('apply_disabled_by_default', denied(fn() => $retirement->apply($plan, PreferenceRetirement::approval($plan)), 'APPLY_DISABLED'));
define('BSRE_RETENTION_APPLY_ENABLED', true);
wp_set_current_user(0);
retention_check('anonymous_apply_denied', denied(fn() => $retirement->apply($plan, PreferenceRetirement::approval($plan)), 'OWNER_REQUIRED'));
wp_set_current_user(get_user_by('login','synthetic_owner')->ID);
retention_check('wrong_approval_denied', denied(fn() => $retirement->apply($plan,'invalid'), 'EXACT_PLAN_APPROVAL_REQUIRED'));
$clock += 900;
retention_check('expired_plan_denied', denied(fn() => $retirement->apply($plan, PreferenceRetirement::approval($plan)), 'PLAN_EXPIRED_OR_INVALID'));
$clock = $now;
$altered = $plan; $altered['eligible'] = [];
retention_check('self_rehashed_altered_plan_denied', denied(fn() => $retirement->apply($altered, PreferenceRetirement::approval($altered)), 'PLAN_STALE_OR_ALTERED'));
$store->choose($subject, ['analytics'=>true,'ad_measurement'=>true], 'SYNTHETIC_NOTICE', $old+1);
retention_check('changed_snapshot_denied', denied(fn() => $retirement->apply($plan, PreferenceRetirement::approval($plan)), 'PLAN_STALE_OR_ALTERED'));
$plan = $retirement->preview();
$failure = function($sql) use ($db) { return str_starts_with($sql, "DELETE FROM {$db->prefix}bsre_consent_state ") ? 'SYNTHETIC INVALID SQL' : $sql; };
$db->suppress_errors(true); add_filter('query',$failure);
retention_check('delete_fault_reported', denied(fn() => $retirement->apply($plan, PreferenceRetirement::approval($plan)), 'RETENTION_STORAGE_UNAVAILABLE'));
remove_filter('query',$failure); $db->suppress_errors(false);
retention_check('atomic_rollback_restores_history', $store->current($subject) !== null && (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_consent_history") === 2);
retention_check('rollback_has_no_success_audit', (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_retention_audit") === 0);
$result = $retirement->apply($plan,PreferenceRetirement::approval($plan));
retention_check('exact_three_rows_deleted', $result['deleted_rows'] === 3 && $store->current($subject) === null);
retention_check('one_private_count_only_audit', (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_retention_audit") === 1);
retention_check('replay_denied', denied(fn() => $retirement->apply($plan, PreferenceRetirement::approval($plan)), 'PLAN_STALE_OR_ALTERED'));
// Candidate stage rejects a known choice whose original evidence was retired.
function synthetic_capture(array $state, string $subject): array {
    return ['request_id'=>wp_generate_uuid4(),'fingerprint'=>str_repeat('b',64),'subject_key'=>$subject,'original_revision'=>(int)$state['revision'],'decision_version'=>$state['receipt'],'notice_version'=>'SYNTHETIC_NOTICE','analytics'=>0,'ad_measurement'=>0,'preference_expires_at'=>$state['expires_at'],'eligible'=>0,'known'=>1,'created_at'=>time(),'uncertain'=>0,'click_capture_state'=>'NOT_PERMITTED','gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0];
}
$capture = synthetic_capture($state,$subject);
retention_check('stale_stage_cannot_recreate_grant', denied(fn() => $store->stage($capture), 'Consent evidence retired.'));
// A capture of any age/state protects all its subject history.
$state = $store->choose($subject, ['analytics'=>false,'ad_measurement'=>false], 'SYNTHETIC_NOTICE', $old);
$capture = synthetic_capture($state,$subject); $beforeCapture = $retirement->preview(); $store->stage($capture);
retention_check('capture_winning_race_invalidates_plan', denied(fn() => $retirement->apply($beforeCapture,PreferenceRetirement::approval($beforeCapture)), 'PLAN_STALE_OR_ALTERED'));
retention_check('staged_subject_fully_held', $retirement->preview()['eligible'] === []);
$store->link($capture['request_id'],$capture['fingerprint'],'BSRE-11111111-1111-4111-8111-111111111111','evt_22222222-2222-4222-8222-222222222222');
retention_check('accepted_subject_fully_held', $retirement->preview()['eligible'] === []);
$other = str_repeat('c',64); $otherState = $store->choose($other,['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_NOTICE',$old);
retention_check('unrelated_old_subject_eligible', count($retirement->preview()['eligible']) === 2);
$unknown = synthetic_capture($state,''); $unknown['known']=0; $store->stage($unknown);
retention_check('unknown_capture_holds_all', $retirement->preview()['eligible'] === []);
// Remove only our known disposable unknown fixture, to test concurrent staging.
$db->query($db->prepare("DELETE FROM {$db->prefix}bsre_consent_captures WHERE request_id=%s",$unknown['request_id']));
$recent = str_repeat('d',64); $store->choose($recent,['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_NOTICE',$now-181*86400);
retention_check('180_day_expiry_is_not_retention', count($retirement->preview()['eligible']) === 2);
$leap = (new DateTimeImmutable('2024-02-29T14:30:00+04:00'))->getTimestamp();
retention_check('leap_anniversary_clamped', RetentionInventory::anniversary($leap) === (new DateTimeImmutable('2025-02-28T14:30:00+04:00'))->getTimestamp());
// Separate DB connection must block on the shared subject lock until commit.
$worker = null; $workerPipes = []; $blocked = false;
$beforeDelete = function($sql) use ($db,$other,$otherState,&$worker,&$workerPipes,&$blocked) {
    if ($worker !== null || !str_starts_with($sql, "DELETE FROM {$db->prefix}bsre_consent_history ")) return $sql;
    $worker = proc_open([PHP_BINARY,'-d','sendmail_path=/bin/false',__FILE__,'stage-worker'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$workerPipes);
    if (!is_resource($worker)) throw new RuntimeException('Worker failed to start');
    stream_set_timeout($workerPipes[1],5);
    fwrite($workerPipes[0],wp_json_encode(synthetic_capture($otherState,$other))."\n"); fflush($workerPipes[0]);
    $ready = trim(fgets($workerPipes[1]));
    if (!preg_match('/^READY:([0-9]+)$/D',$ready,$match)) throw new RuntimeException('Worker not ready');
    for($i=0;$i<100;$i++) {
        $waiting = $db->get_var($db->prepare('SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX t ON t.trx_id=w.requesting_trx_id WHERE t.trx_mysql_thread_id=%d',(int)$match[1]));
        if ((int)$waiting > 0) { $blocked = true; break; }
        usleep(20000);
    }
    return $sql;
};
$plan = $retirement->preview(); add_filter('query',$beforeDelete);
$result = $retirement->apply($plan,PreferenceRetirement::approval($plan)); remove_filter('query',$beforeDelete);
retention_check('concurrent_stage_waits_for_retirement_lock', $blocked);
retention_check('concurrent_stale_stage_rejected_after_commit', trim(fgets($workerPipes[1])) === 'RETIRED');
fclose($workerPipes[0]); fclose($workerPipes[1]);
retention_check('concurrent_worker_clean_exit', proc_close($worker) === 0);
retention_check('capture_evidence_untouched', (int)$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_consent_captures") === 1 && $store->current($subject) !== null);
retention_check('recent_preference_untouched', $store->current($recent) !== null);
$badDb = clone $db; $badDb->prefix='synthetic_';
retention_check('other_database_scope_denied', denied(fn() => new PreferenceRetirement($badDb), 'ISOLATED_LAB_ONLY'));
echo wp_json_encode(['phase'=>'preference_retirement_candidate','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'production_apply_supported'=>false,'submitted_deletion_implemented'=>false,'backup_restore_accepted'=>false,'production_acceptance'=>false]) . "\n";
