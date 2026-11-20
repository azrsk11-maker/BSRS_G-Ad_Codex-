<?php
declare(strict_types=1);
/** Actual reviewed repository + MariaDB provider, in one disposable namespace only. */
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
require '/opt/wordpress/wp-load.php';
require_once __DIR__ . '/fixtures.php';
require_once __DIR__ . '/WpCaptureResource.php';
use BSRE\ClosedRetention as C;
use BSRE\Enquiries as E;

function captureConnection(): C\LeaseBoundWpdb
{
    global $wpdb;
    $db = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->set_prefix($wpdb->prefix);
    $db->prefix = C\WpCaptureResource::PREFIX;
    $db->suppress_errors(true);
    return $db;
}
$db = captureConnection();
$journal = new C\LabSqlJournal($db);
$provider = new C\WpCaptureResource($db, $journal);
$store = new E\WpConsentRepository($db);
$table = C\WpCaptureResource::PREFIX . 'bsre_consent_captures';

// Workers use the same actual source and independent SQL connections, never array providers.
if (($argv[1] ?? '') === '--custody-probe') {
    $blocked = false;
    try { $journal->locked($argv[2], fn() => $provider->read($argv[3])); }
    catch (C\Failure $error) { $blocked = $error->getMessage() === 'CLOSURE_LEASE_BUSY'; }
    echo json_encode(['blocked'=>$blocked], JSON_THROW_ON_ERROR) . "\n";
    exit($blocked ? 0 : 1);
}
if (($argv[1] ?? '') === '--link-probe') {
    $db->query('SET SESSION innodb_lock_wait_timeout=1');
    $blocked = false;
    try { $store->link($argv[2], $argv[3], $argv[4], $argv[5]); }
    catch (RuntimeException $error) { $blocked = true; }
    echo json_encode(['blocked'=>$blocked], JSON_THROW_ON_ERROR) . "\n";
    exit($blocked ? 0 : 1);
}
if (($argv[1] ?? '') === '--connection-loss-probe') {
    $held = false;
    try {
        $journal->locked($argv[2], function () use ($db, $provider, $argv) {
            $binding = $provider->read($argv[3]);
            if ($binding === null) throw new RuntimeException('Synthetic capture connection probe missing');
            $thread = $db->custodyConnectionId();
            if ($thread === null || !ctype_digit($thread)) throw new RuntimeException('Synthetic capture lease missing');
            $killer = captureConnection();
            if ($killer->query('KILL CONNECTION ' . $thread) === false) throw new RuntimeException('Synthetic capture kill unavailable');
            $provider->removeExact($binding);
        });
    } catch (C\Failure $error) {
        $held = in_array($error->getMessage(), ['RETIREMENT_CONNECTION_LEASE_LOST', 'RETIREMENT_CUSTODY_RELEASE_UNCONFIRMED'], true);
    }
    $fresh = captureConnection();
    $present = (string) $fresh->get_var($fresh->prepare("SELECT COUNT(*) FROM {$table} WHERE request_id=%s", $argv[3])) === '1';
    $noReconnect = $db->custodyIsActive() && $db->db_connect(false) === false && $db->check_connection(false) === false;
    echo json_encode(['held'=>$held,'present'=>$present,'reconnect_denied'=>$noReconnect], JSON_THROW_ON_ERROR) . "\n";
    exit($held && $present && $noReconnect ? 0 : 1);
}

$checks = [];
function captureCheck(string $name, bool $ok): void
{
    global $checks;
    if (!$ok) throw new RuntimeException('Synthetic capture native assertion failed: ' . $name);
    $checks[$name] = true;
}
function captureDenied(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (Throwable $error) { return $error->getMessage() === $code; }
}
function captureSql(string $sql): void
{
    global $db;
    if ($db->prefix !== C\WpCaptureResource::PREFIX || home_url() !== 'http://bsre.invalid'
        || $db->query($sql) === false) throw new RuntimeException('Synthetic capture fixture SQL failed');
}
function captureWorker(array $arguments): array
{
    $pipes = [];
    $process = proc_open([PHP_BINARY, '-d', 'sendmail_path=/bin/false', __FILE__, ...$arguments],
        [0=>['pipe','r'], 1=>['pipe','w'], 2=>['pipe','w']], $pipes);
    if (!is_resource($process)) throw new RuntimeException('Synthetic capture worker unavailable');
    fclose($pipes[0]); stream_set_timeout($pipes[1], 8);
    $line = fgets($pipes[1], 4097);
    $metadata = stream_get_meta_data($pipes[1]);
    if ($metadata['timed_out']) { proc_terminate($process, 9); throw new RuntimeException('Synthetic capture worker timeout'); }
    fclose($pipes[1]); fclose($pipes[2]);
    $status = proc_close($process);
    if ($status !== 0 || !is_string($line)) throw new RuntimeException('Synthetic capture worker failed');
    return json_decode($line, true, 8, JSON_THROW_ON_ERROR);
}
function captureSeed(E\WpConsentRepository $store, array $closure, bool $known = true): array
{
    $at = strtotime('2025-01-01T12:00:00Z');
    $choice = $known ? $store->choose(str_repeat('a',64), ['analytics'=>false,'ad_measurement'=>false], 'SYNTHETIC_NOTICE', $at) : null;
    $rawHash = hash('sha256', json_encode(['synthetic'=>true,'request_id'=>$closure['request_id']], JSON_THROW_ON_ERROR));
    $store->stage(['request_id'=>$closure['request_id'],'fingerprint'=>$rawHash,
        'subject_key'=>$choice['subject_key'] ?? '', 'original_revision'=>$choice['revision'] ?? 0,
        'decision_version'=>$choice['receipt'] ?? str_repeat('b',32), 'notice_version'=>'SYNTHETIC_NOTICE',
        'analytics'=>0,'ad_measurement'=>0,'preference_expires_at'=>$known ? $at+15552000 : 0,
        'eligible'=>0,'known'=>$known ? 1 : 0,'created_at'=>$at,'uncertain'=>$known ? 0 : 1,
        'click_capture_state'=>'NOT_PERMITTED','gclid_first'=>'','gclid_last'=>'',
        'gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0]);
    return $store->link($closure['request_id'], $rawHash, $closure['lead_id'], $closure['event_id']);
}

captureCheck('original_repository_loaded', class_exists(E\WpConsentRepository::class, false));
$journal->install();
$original = $wpdb;
try { $wpdb = $db; $installed = E\install_consent_storage(); }
finally { $wpdb = $original; }
captureCheck('original_reviewed_schema_installed', $installed);
$f = C\fixture($journal);
$f['now']=time();$f['admission']->refresh($f['now']);
$row = captureSeed($store, $f['closure']);
$request = $f['closure']['request_id']; $closureId = $f['closure']['closure_id'];
$locked = fn(callable $operation) => $journal->locked($closureId, $operation);
captureCheck('read_without_journal_custody_denied', captureDenied(fn() => $provider->read($request), 'CLOSURE_LEASE_REQUIRED'));
$binding = $locked(fn() => $provider->read($request));
captureCheck('real_stage_link_inventory_exactly_one', $locked(fn() => $provider->inventory($request)) === [$binding]);
$locked(function () use ($db,$provider,$request) {
    $beforeLog=$db->queries ?? [];$observedQueries=0;$priorSaveQueries=$db->save_queries ?? false;
    $observer=function($sql)use(&$observedQueries){$observedQueries++;return $sql;};
    add_filter('query',$observer);$db->save_queries=true;
    try {
        $held=captureDenied(fn()=>$provider->read($request),'CAPTURE_QUERY_LOGGING_UNVERIFIED');
        $noSqlOrLog=$observedQueries===0&&($db->queries ?? [])===$beforeLog;
    } finally {$db->save_queries=$priorSaveQueries;remove_filter('query',$observer);}
    captureCheck('dynamic_query_recording_holds_before_any_sql_or_log',$held&&$noSqlOrLog);
});
captureCheck('raw_wp_fingerprint_preserved', $binding['fingerprint'] === $row['fingerprint']
    && $binding['fingerprint'] !== $f['adapters']['intake']->rows['synthetic-intake']['fingerprint']);
captureCheck('private_values_absent_from_binding', !str_contains(json_encode($binding, JSON_THROW_ON_ERROR), str_repeat('a',64))
    && !array_key_exists('subject_key',$binding) && !array_key_exists('gclid_first',$binding));
captureCheck('refused_and_expired_consent_not_upgraded_or_excluded', $binding !== null && (int)$row['analytics']===0
    && (int)$row['ad_measurement']===0 && (int)$row['preference_expires_at']<time());
$db2 = captureConnection(); $journal2 = new C\LabSqlJournal($db2); $provider2 = new C\WpCaptureResource($db2, $journal2);
$locked(function () use ($provider2, $request, $journal, $db2) {
    captureCheck('other_connection_cannot_borrow_lease', captureDenied(fn() => $provider2->read($request), 'CLOSURE_LEASE_REQUIRED'));
    captureCheck('different_connection_rejected_by_journal', captureDenied(fn() => $journal->assertProviderCustody($db2,$request), 'CAPTURE_CONNECTION_CONFLICT'));
});
captureCheck('cross_process_namespace_custody_enforced', $locked(fn() => captureWorker(['--custody-probe',$closureId,$request])) === ['blocked'=>true]);
captureCheck('lost_connection_cannot_delete_or_reconnect', captureWorker(['--connection-loss-probe',$closureId,$request])
    === ['held'=>true,'present'=>true,'reconnect_denied'=>true]);

captureSql($db->prepare("UPDATE {$table} SET notice_version=%s WHERE request_id=%s", 'SYNTHETIC_CHANGED', $request));
captureCheck('complete_row_change_invalidates_exact_binding', $locked(fn() => captureDenied(fn() => $provider->removeExact($binding), 'CAPTURE_BINDING_CHANGED')));
captureSql($db->prepare("UPDATE {$table} SET notice_version=%s WHERE request_id=%s", 'SYNTHETIC_NOTICE', $request));
captureCheck('same_complete_row_restores_stable_binding', $locked(fn() => $provider->read($request)) === $binding);
$altered=$binding;$altered['evidence_hash']=str_repeat('f',64);
captureCheck('caller_replaced_row_digest_denied', $locked(fn()=>captureDenied(fn()=>$provider->removeExact($altered),'CAPTURE_BINDING_CHANGED')));
foreach (['delivery_pending'=>1,'state'=>'STAGED'] as $field=>$value) {
    captureSql($db->prepare("UPDATE {$table} SET {$field}=%s WHERE request_id=%s", (string)$value, $request));
    captureCheck('in_flight_' . $field . '_holds', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_DELIVERY_UNVERIFIED')));
    captureSql($db->prepare("UPDATE {$table} SET {$field}=%s WHERE request_id=%s", $field==='state'?'ACCEPTED':'0', $request));
}
captureSql($db->prepare("UPDATE {$table} SET event_id=%s WHERE request_id=%s", 'evt_invalid', $request));
captureCheck('unlinked_receipt_denied', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_IDENTITY_INVALID')));
captureSql($db->prepare("UPDATE {$table} SET event_id=%s WHERE request_id=%s", $f['closure']['event_id'], $request));
$other = $f['closure']; $other['request_id']=C\syntheticUuid(81); $other['event_id']='evt_'.C\syntheticUuid(82);
captureSeed($store, $other, false);
captureCheck('shared_lead_receipt_denied', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_SHARED_RECEIPT')));
captureSql($db->prepare("DELETE FROM {$table} WHERE request_id=%s", $other['request_id']));
$unknown = $other; $unknown['lead_id']='BSRE-'.C\syntheticUuid(83);
captureSeed($store,$unknown,false);
$unknownBinding=$journal->locked($unknown['request_id'],fn() => $provider->read($unknown['request_id']));
captureCheck('unknown_uncertain_permission_does_not_invent_delivery_failure', $unknownBinding !== null);
captureCheck('different_request_cannot_borrow_current_closure_scope', $locked(fn()=>captureDenied(fn()=>$provider->read($unknown['request_id']),'CAPTURE_CLOSURE_SCOPE_CONFLICT')));
captureCheck('missing_canonical_closure_cannot_authorize_delete', $journal->locked($unknown['request_id'],fn()=>captureDenied(fn()=>$provider->removeExact($unknownBinding),'CAPTURE_CLOSURE_SCOPE_CONFLICT')));
captureSql($db->prepare("DELETE FROM {$table} WHERE request_id=%s", $unknown['request_id']));

$open=$f['closure'];$open['revision']++;$open['status']='OPEN';$open['closed_at_utc']=null;$open['recorded_at_utc']=gmdate('Y-m-d\\TH:i:s\\Z',$f['now']);
$journal->putClosure($open);
captureCheck('open_canonical_closure_cannot_authorize_delete', $locked(fn()=>captureDenied(fn()=>$provider->removeExact($binding),'ENQUIRY_OPEN')));
$recent=$open;$recent['revision']++;$recent['status']='CLOSED';$recent['closed_at_utc']=gmdate('Y-m-d\\TH:i:s\\Z',$f['now']-3600);
$journal->putClosure($recent);
captureCheck('recent_canonical_closure_cannot_authorize_delete', $locked(fn()=>captureDenied(fn()=>$provider->removeExact($binding),'RETENTION_NOT_DUE')));
$restored=$f['closure'];$restored['revision']=$recent['revision']+1;$restored['recorded_at_utc']=$open['recorded_at_utc'];
$journal->putClosure($restored);$f['closure']=$restored;
$mismatched=$restored;$mismatched['closure_id']=C\syntheticUuid(84);
captureSql($db->prepare('UPDATE '.C\WpCaptureResource::PREFIX.'closures SET body=%s WHERE id=%s',json_encode($mismatched,JSON_THROW_ON_ERROR),$closureId));
captureCheck('leased_sql_id_must_match_canonical_body', $locked(fn()=>captureDenied(fn()=>$provider->read($request),'CAPTURE_CLOSURE_SCOPE_CONFLICT')));
captureSql($db->prepare('UPDATE '.C\WpCaptureResource::PREFIX.'closures SET body=%s WHERE id=%s',json_encode($restored,JSON_THROW_ON_ERROR),$closureId));

$visibilityFault=function($sql){return str_contains($sql,'FROM information_schema.USER_PRIVILEGES')?'SELECT 0':$sql;};
add_filter('query',$visibilityFault);
captureCheck('hidden_metadata_cannot_prove_no_side_effects', $locked(fn()=>captureDenied(fn()=>$provider->read($request),'CAPTURE_METADATA_VISIBILITY_UNVERIFIED')));
remove_filter('query',$visibilityFault);
$sharedCountBeforeDrift=(string)$db->get_var('SELECT COUNT(*) FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_history');
captureSql('CREATE TRIGGER '.C\WpCaptureResource::PREFIX.'delete_probe AFTER DELETE ON '.$table
    .' FOR EACH ROW DELETE FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_history WHERE subject_key=OLD.subject_key');
captureCheck('delete_trigger_cannot_touch_shared_history', $locked(fn()=>captureDenied(fn()=>$provider->removeExact($binding),'CAPTURE_SCHEMA_UNVERIFIED')));
captureSql('DROP TRIGGER '.C\WpCaptureResource::PREFIX.'delete_probe');
$child=C\WpCaptureResource::PREFIX.'fk_probe';
captureSql("CREATE TABLE {$child} (request_id char(36) NOT NULL, PRIMARY KEY(request_id), CONSTRAINT closed_capture_synthetic_child_fk"
    ." FOREIGN KEY(request_id) REFERENCES {$table}(request_id) ON DELETE CASCADE) ENGINE=InnoDB ".$db->get_charset_collate());
captureSql($db->prepare("INSERT INTO {$child} (request_id) VALUES (%s)",$request));
captureCheck('incoming_foreign_key_cascade_denied', $locked(fn()=>captureDenied(fn()=>$provider->removeExact($binding),'CAPTURE_SCHEMA_UNVERIFIED')));
captureCheck('foreign_child_preserved_after_rejected_delete',(string)$db->get_var("SELECT COUNT(*) FROM {$child}")==='1');
captureSql("DROP TABLE {$child}");
captureSql("ALTER TABLE {$table} ADD CONSTRAINT closed_capture_synthetic_subject_fk FOREIGN KEY(subject_key) REFERENCES "
    .C\WpCaptureResource::PREFIX.'bsre_consent_state(subject_key)');
captureCheck('outgoing_unreviewed_foreign_key_denied', $locked(fn()=>captureDenied(fn()=>$provider->read($request),'CAPTURE_SCHEMA_UNVERIFIED')));
captureSql("ALTER TABLE {$table} DROP FOREIGN KEY closed_capture_synthetic_subject_fk");
captureCheck('side_effect_drift_holds_preserve_capture_and_shared_history',
    (string)$db->get_var($db->prepare("SELECT COUNT(*) FROM {$table} WHERE request_id=%s",$request))==='1'
    &&(string)$db->get_var('SELECT COUNT(*) FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_history')===$sharedCountBeforeDrift);

captureSql("ALTER TABLE {$table} ADD COLUMN synthetic_extra int NOT NULL DEFAULT 0");
captureCheck('extra_schema_column_denied', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_SCHEMA_UNVERIFIED')));
captureSql("ALTER TABLE {$table} DROP COLUMN synthetic_extra");
captureSql("ALTER TABLE {$table} DROP PRIMARY KEY");
captureCheck('missing_primary_key_denied', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_SCHEMA_UNVERIFIED')));
captureSql("ALTER TABLE {$table} ADD PRIMARY KEY (request_id)");
captureSql("ALTER TABLE {$table} ENGINE=MyISAM");
captureCheck('nontransactional_capture_table_denied', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_SCHEMA_UNVERIFIED')));
captureSql("ALTER TABLE {$table} ENGINE=InnoDB");
$fault = function ($sql) use ($table) { return str_starts_with($sql,"SELECT * FROM {$table} ") ? 'SELECT synthetic_missing_capture_column' : $sql; };
add_filter('query',$fault);
captureCheck('provider_error_is_not_absence', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_STORAGE_UNVERIFIED')));
remove_filter('query',$fault);
$locked(function () use ($db,$provider,$request) {
    $db->query('START TRANSACTION');
    captureCheck('existing_transaction_cannot_be_committed_by_provider', captureDenied(fn() => $provider->read($request), 'CAPTURE_TRANSACTION_ALREADY_ACTIVE'));
    captureCheck('caller_transaction_remains_active', (string)$db->get_var('SELECT @@session.in_transaction')==='1');
    $db->query('ROLLBACK');
});
captureSql('SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED');
captureCheck('weaker_gap_lock_isolation_denied', $locked(fn() => captureDenied(fn() => $provider->read($request), 'CAPTURE_TRANSACTION_ISOLATION_UNVERIFIED')));
captureSql('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ');

$beforeShared = [];
foreach (['state','history'] as $part) $beforeShared[$part]=$db->get_results('SELECT * FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_'.$part.' ORDER BY '.($part==='state'?'subject_key':'receipt'),ARRAY_A);
$f['adapters']['capture']=$provider;
$f['workflow']=new C\Workflow($journal,$f['adapters'],$f['authority'],$f['admission']);
$plan=C\approved($f);
$lockedDeleteProbe = false; $dropAck = true; $captureDeleted = false;
$interruption = function ($sql) use ($table,$request,$binding,$f,&$lockedDeleteProbe,&$dropAck,&$captureDeleted,$db) {
    if (str_starts_with($sql,"DELETE FROM {$table} ")) {
        $lockedDeleteProbe = captureWorker(['--link-probe',$request,$binding['fingerprint'],$f['closure']['lead_id'],$f['closure']['event_id']]) === ['blocked'=>true];
        $captureDeleted = true;
    }
    if ($sql === 'COMMIT' && $captureDeleted && $dropAck) {
        $dropAck=false;
        if ($db->query('COMMIT') === false) throw new RuntimeException('Synthetic committed deletion unavailable');
        return 'SELECT synthetic_missing_capture_commit_ack';
    }
    return $sql;
};
add_filter('query',$interruption);
$first=C\executeWithOwnerMail($f,$plan,$f['now']);
remove_filter('query',$interruption);
captureCheck('actual_source_link_blocked_during_locked_delete', $lockedDeleteProbe);
captureCheck('lost_commit_ack_holds_workflow', $first['status']==='HELD');
$saved=$journal->journal($plan['digest']);
$captureStep=array_search('capture',array_column($plan['resources'],'store'),true);
captureCheck('workflow_intent_survives_lost_commit_ack', is_int($captureStep)&&$saved['steps'][$captureStep]==='INTENT_RECORDED');
captureCheck('fresh_actual_sql_confirms_committed_absence', $journal2->locked($closureId,fn()=>$provider2->read($request))===null);
captureCheck('absent_inventory_is_authoritative_empty', $journal2->locked($closureId,fn()=>$provider2->inventory($request))===[]);
captureCheck('adapter_never_repeats_missing_delete', $locked(fn()=>captureDenied(fn()=>$provider->removeExact($binding),'CAPTURE_RESOURCE_MISSING')));
$f['admission']->refresh($f['now']+60);
$resumed=new C\Workflow($journal2,array_replace($f['adapters'],['capture'=>$provider2]),$f['authority'],$f['admission']);
$result=$resumed->execute($plan,'synthetic-owner',$f['now']+60);
captureCheck('fresh_workflow_resumes_from_provider_absence', $result['status']==='COMPLETE'&&$result['confirmed_absent']===5);
foreach (['state','history'] as $part) {
    $after=$db2->get_results('SELECT * FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_'.$part.' ORDER BY '.($part==='state'?'subject_key':'receipt'),ARRAY_A);
    captureCheck('shared_consent_'.$part.'_preserved',$after===$beforeShared[$part]);
}
// This original producer has no retirement/admission fence: demonstrate the limitation.
captureSeed($store,$f['closure']);
captureCheck('original_stage_link_can_recreate_after_commit', $journal2->locked($closureId,fn()=>$provider2->read($request))!==null);
captureCheck('workflow_holds_when_actual_capture_reappears', $resumed->execute($plan,'synthetic-owner',$f['now']+60)['status']==='HELD');
echo json_encode(['phase'=>'wp_capture_resource_native','checks'=>$checks,'provider'=>'Actual reviewed WpConsentRepository and MariaDB capture SQL',
    'other_resources'=>'Synthetic memory adapters','synthetic_data_only'=>true,'producer_restore_fence_acceptance'=>'HELD',
    'durable_absence_claimed'=>false,'production_authorized'=>false],JSON_THROW_ON_ERROR)."\n";
