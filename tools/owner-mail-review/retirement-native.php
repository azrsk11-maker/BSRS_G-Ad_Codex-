<?php
declare(strict_types=1);
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
require '/opt/wordpress/wp-load.php';
$hooksBefore = array_map(fn($hook) => $hook->callbacks, $GLOBALS['wp_filter']);
require __DIR__ . '/WordPress.php';
require_once __DIR__ . '/../closed-enquiry-retention/fixtures.php';
require_once __DIR__ . '/../closed-enquiry-retention/ReceiverPipe.php';
use BSRE\ClosedRetention as C;
use BSRE\OwnerMailReview as O;

function retirementConnection(): C\LeaseBoundWpdb
{
    $db = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->prefix = 'owner_retirement_synthetic_';
    return $db;
}
function retirementJournal(): C\LabSqlJournal { return new C\LabSqlJournal(retirementConnection()); }

if (($argv[1] ?? null) === '--connection-loss-probe') {
    $connection = retirementConnection(); $probe = new C\LabSqlJournal($connection);
    $before = $probe->closure($argv[2] ?? '');
    if ($before === null) throw new RuntimeException('Synthetic connection-loss baseline missing');
    $after = $before; $after['revision']++;
    $held = false;
    try {
        $probe->locked($before['closure_id'], function () use ($probe, $connection, $before, $after) {
            $thread = $connection->custodyConnectionId();
            if ($thread === null || !ctype_digit($thread)) throw new RuntimeException('Synthetic leased connection missing');
            // Disconnect only this disposable lab connection, through another connection of the same test user.
            $killer = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $killer->suppress_errors(true);
            if ($killer->query('KILL CONNECTION ' . $thread) === false) throw new RuntimeException('Synthetic connection kill unavailable');
            $probe->replaceClosure($before, $after);
        });
    } catch (C\Failure $error) {
        $held = in_array($error->getMessage(), ['RETIREMENT_CONNECTION_LEASE_LOST', 'RETIREMENT_CUSTODY_RELEASE_UNCONFIRMED'], true);
    }
    $unchanged = retirementJournal()->closure($before['closure_id']) === $before;
    $reconnectDenied = $connection->custodyIsActive() && $connection->db_connect(false) === false && $connection->check_connection(false) === false;
    echo json_encode(['held' => $held, 'unchanged' => $unchanged, 'reconnect_denied' => $reconnectDenied], JSON_THROW_ON_ERROR) . "\n";
    exit($held && $unchanged && $reconnectDenied ? 0 : 1);
}

// A separate PHP process cannot be stopped by the parent process's static lock guard.
if (($argv[1] ?? null) === '--custody-probe') {
    $probe = retirementJournal();
    $record = $probe->journal($argv[2] ?? '');
    if ($record === null) throw new RuntimeException('Synthetic probe intent missing');
    $blocked = false;
    try { $probe->locked($record['plan']['closure_id'], fn() => $probe->scrubRetirement($record, $record['recovery_until'])); }
    catch (C\Failure $error) { $blocked = $error->getMessage() === 'CLOSURE_LEASE_BUSY'; }
    echo json_encode(['blocked' => $blocked], JSON_THROW_ON_ERROR) . "\n";
    exit($blocked ? 0 : 1);
}

$checks = [];
function retirementCheck(string $name, bool $ok): void
{
    global $checks;
    if (!$ok) throw new RuntimeException('Synthetic owner retirement native check failed: ' . $name);
    $checks[$name] = true;
}
function retirementDenied(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure|C\Failure $error) { return $error->getMessage() === $code; }
}
function retirementUser(string $name): int
{
    $user = get_user_by('login', $name);
    if ($user) return (int) $user->ID;
    $id = wp_insert_user(['user_login' => $name, 'user_email' => $name . '@example.invalid',
        'user_pass' => 'Synthetic-local-lab-only-487!', 'role' => 'administrator']);
    if (is_wp_error($id)) throw new RuntimeException('Synthetic owner creation failed');
    return (int) $id;
}
function retirementPurpose(string $operation, string $job = '', string $digest = ''): string
{
    return 'bsre-owner-retirement/' . C\Workflow::digest([$operation, $job, $digest]);
}
function retirementFixture(C\LabSqlJournal $journal, O\Store $store, O\Session $session, int $number, int $now): array
{
    $f = C\fixture(); $f['now'] = $now; $f['admission']->refresh($now);
    $pipe = new SyntheticReceiverPipe();
    $f['admission']->value['source_hashes']['receiver'] = $pipe->call('metadata')['source_hash'];
    $a = $f['admission']->value;
    $hash = C\Workflow::digest(['wp' => $a['wp'], 'receiver' => $a['receiver'],
        'source_hashes' => $a['source_hashes'], 'restore_policy_hash' => $a['restore_policy_hash']]);
    $identity = $pipe->call('init', ['accepted_at' => strtotime($f['closure']['accepted_at_utc']),
        'now' => $now, 'admission_hash' => $hash, 'activated_at' => $a['receiver']['activated_at']]);
    $before = array_replace($f['closure'], array_intersect_key($identity, array_flip(['request_id', 'lead_id', 'event_id'])),
        ['closure_id' => C\syntheticUuid($number), 'email_status' => 'QUEUED', 'mail_message_ids' => []]);
    $journal->putClosure($before); // Explicit synthetic initial-collector substitution.
    $f['adapters']['email']->rows = [];
    foreach (['intake', 'capture', 'outcome'] as $kind) foreach ($f['adapters'][$kind]->rows as &$binding) {
        foreach (['request_id', 'lead_id', 'event_id', 'fingerprint'] as $key) $binding[$key] = $identity[$key];
        $binding['request_ids'] = [$identity['request_id']];
    }
    unset($binding);
    $authority = new O\ReviewAuthority($store, $session);
    $workflow = new C\Workflow($journal, $f['adapters'], $authority, $f['admission'], $pipe);
    $controller = new O\OwnerRetirementController($workflow, $journal, $store, $session, $pipe);
    return array_replace($f, compact('before', 'pipe', 'authority', 'workflow', 'controller', 'identity', 'journal'), ['closure' => $before]);
}
function retirementPrepare(array $f, O\Session $session): array
{
    return $f['controller']->handle('POST', ['operation' => 'prepare', 'closure_id' => $f['before']['closure_id'],
        'nonce' => $session->nonce(retirementPurpose('prepare'))], $f['now']);
}
function retirementApprove(array $f, array $view, O\Session $session): array
{
    $job = $view['job'];
    return $f['controller']->handle('POST', ['operation' => 'approve', 'job' => $job['id'], 'plan_digest' => $job['plan']['digest'],
        'nonce' => $session->nonce(retirementPurpose('approve', $job['id'], $job['plan']['digest']))], $f['now']);
}

retirementCheck('candidate_loading_installs_no_hook_or_route', $hooksBefore === array_map(fn($hook) => $hook->callbacks, $GLOBALS['wp_filter']));
$owner = retirementUser('owner-mail-synthetic-owner'); $other = retirementUser('owner-retirement-synthetic-other');
wp_set_current_user($owner); $session = new O\WordPressSession($owner);
$db = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $db->prefix = 'owner_mail_review_synthetic_';
$store = new O\WordPressStore($db); $store->install();
$journal = retirementJournal(); $journal->install(); $restarted = retirementJournal(); $now = time();
$f = retirementFixture($journal, $store, $session, 201, $now);
wp_set_current_user($other);
retirementCheck('different_actual_administrator_cannot_review', retirementDenied(fn() => $f['controller']->handle('GET', [], $now), 'OWNER_SESSION_REQUIRED'));
wp_set_current_user($owner);
$sourceCalls = ['inspect' => 0, 'retire' => 0]; $digest = null;
$f['pipe']->beforeOwnerSource = function (string $action, array $scope) use (&$sourceCalls, &$digest, $restarted, $journal, $f, $now) {
    $sourceCalls[$action]++;
    $record = $restarted->journal($digest);
    retirementCheck('actual_source_' . $action . '_has_durable_typed_intent', $record !== null
        && $record['contract'] === C\RetirementIntent::CONTRACT && $record['plan']['scope'] === $scope);
    retirementCheck('actual_source_' . $action . '_cannot_escape_global_closure_lease', retirementDenied(
        fn() => $restarted->locked(C\syntheticUuid(999), fn() => null), 'CLOSURE_LEASE_BUSY'));
    C\RetirementIntent::validateRecord($record, $now);
};
$view = retirementPrepare($f, $session); $digest = $view['job']['plan']['digest'];
retirementCheck('prepare_does_not_call_source_or_change_closure', array_sum($sourceCalls) === 0 && $journal->closure($f['before']['closure_id']) === $f['before']);
retirementCheck('native_plan_uses_actual_normalized_receiver_fingerprint', $view['job']['plan']['scope']['fingerprint'] === $f['identity']['fingerprint']);
$approved = retirementApprove($f, $view, $session);
$stored = $restarted->journal($digest); $after = $journal->closure($f['before']['closure_id']);
retirementCheck('wordpress_sql_and_actual_source_retire_exact_target', $approved['status'] === 'RETIREMENT_RECORDED'
    && $stored['phase'] === 'RETIREMENT_RECORDED' && $after === $view['job']['plan']['after']);
retirementCheck('business_evidence_and_dates_survive_technical_retirement', $after === C\RetirementIntent::target($f['before'])
    && $after['reviewer'] === $f['before']['reviewer'] && $after['recorded_at_utc'] === $f['before']['recorded_at_utc']);
$proof = $f['pipe']->readback($stored['plan']['scope'], $now);
retirementCheck('actual_source_fence_binds_exact_owner_intent', $proof['row_state'] === 'RETIRED' && $proof['owner_intent_digest'] === $digest
    && C\RetirementIntent::verifiedFence($stored, $proof, $now) === $stored['proof_hash']);
$stats = $f['pipe']->call('stats');
retirementCheck('sender_retirement_does_not_delete_or_send', $stats['rows'] === 1 && $stats['mail'] === 0 && $stats['private_fences'] === 1);
$f['authority']->select($view['job']['id']);
retirementCheck('retirement_owner_approval_never_grants_purge', !$f['authority']->canApply($session->actor(), $digest, $now, 'PURGE'));
retirementCheck('private_retirement_screen_renders_exact_review', str_contains($f['controller']->render($approved), $digest));

// A successful source fence with a lost response must recover from inspection, without another write.
$g = retirementFixture($journal, $store, $session, 202, $now);
$gView = retirementPrepare($g, $session); $gDigest = $gView['job']['plan']['digest'];
$gCalls = ['inspect' => 0, 'retire' => 0];
$g['pipe']->beforeOwnerSource = function (string $action) use (&$gCalls, $gDigest, $restarted) {
    $gCalls[$action]++;
    if ($restarted->journal($gDigest) === null) throw new RuntimeException('Source preceded durable intent');
};
$g['pipe']->loseRetirementAcknowledgement = true;
$uncertain = retirementApprove($g, $gView, $session);
retirementCheck('actual_source_lost_ack_preserves_intent_and_original_closure', $uncertain['status'] === 'HELD'
    && $restarted->journal($gDigest)['phase'] === 'INTENT_RECORDED'
    && $journal->closure($g['before']['closure_id']) === $g['before'] && $gCalls['retire'] === 1);
// Remove only the duplicate UI cache in the disposable lab to prove the authoritative recovery path.
if ($db->query($db->prepare('DELETE FROM owner_mail_review_synthetic_jobs WHERE id=%s', $gView['job']['id'])) !== 1) throw new RuntimeException('Synthetic UI cache fixture failed');
$recovered = $g['controller']->handle('POST', ['operation' => 'recover', 'intent_digest' => $gDigest,
    'nonce' => $session->nonce(retirementPurpose('recover', '', $gDigest))], $now + 1);
retirementCheck('native_recovery_survives_pruned_ui_and_source_lost_ack', $recovered['status'] === 'RETIREMENT_RECORDED'
    && $journal->closure($g['before']['closure_id']) === $gView['job']['plan']['after'] && $gCalls['retire'] === 1);
retirementCheck('native_recovery_does_not_duplicate_sender_fence', $g['pipe']->call('stats')['private_fences'] === 1 && $g['pipe']->call('stats')['mail'] === 0);

// The global custody lease serializes different closures, including independent PHP processes.
$probeBefore = C\fixture()['closure']; $probeBefore['closure_id'] = C\syntheticUuid(203);
$journal->putClosure($probeBefore); $probeAfter = $probeBefore; $probeAfter['revision']++;
$lossProcess = proc_open([PHP_BINARY, '-d', 'sendmail_path=/bin/false', __FILE__, '--connection-loss-probe', $probeBefore['closure_id']],
    [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $lossPipes, __DIR__);
if (!is_resource($lossProcess)) throw new RuntimeException('Synthetic connection-loss probe unavailable');
fclose($lossPipes[0]); stream_set_timeout($lossPipes[1], 10); stream_set_timeout($lossPipes[2], 10);
$lossOutput = stream_get_contents($lossPipes[1], 2048); $lossErrors = stream_get_contents($lossPipes[2], 2048);
fclose($lossPipes[1]); fclose($lossPipes[2]);
$lossExit = proc_close($lossProcess); $lossEvidence = json_decode($lossOutput, true, 8, JSON_THROW_ON_ERROR);
retirementCheck('real_connection_loss_cannot_reconnect_and_execute_cas', $lossExit === 0 && $lossErrors === ''
    && $lossEvidence === ['held' => true, 'unchanged' => true, 'reconnect_denied' => true]);
$record = $restarted->journal($gDigest);
$journal->locked($probeBefore['closure_id'], function () use ($journal, $record, $gDigest, $probeBefore, $probeAfter) {
    $process = proc_open([PHP_BINARY, '-d', 'sendmail_path=/bin/false', __FILE__, '--custody-probe', $gDigest],
        [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, __DIR__);
    if (!is_resource($process)) throw new RuntimeException('Synthetic custody probe unavailable');
    fclose($pipes[0]); stream_set_timeout($pipes[1], 10); stream_set_timeout($pipes[2], 10);
    $output = stream_get_contents($pipes[1], 2048); $errors = stream_get_contents($pipes[2], 2048);
    fclose($pipes[1]); fclose($pipes[2]);
    retirementCheck('real_other_process_cannot_scrub_different_closure_mid_cas', proc_close($process) === 0
        && $errors === '' && json_decode($output, true, 8, JSON_THROW_ON_ERROR)['blocked'] === true);
    $journal->replaceClosure($probeBefore, $probeAfter);
    retirementCheck('guarded_cas_finishes_before_other_closure_scrub', $journal->closure($probeBefore['closure_id']) === $probeAfter);
});
$expireAt = $record['recovery_until'];
$beforeSourceCalls = $gCalls;
$expired = $g['controller']->handle('POST', ['operation' => 'expire', 'intent_digest' => $gDigest,
    'nonce' => $session->nonce(retirementPurpose('expire', '', $gDigest))], $expireAt);
retirementCheck('expiry_scrubs_intent_only_and_requires_reconciliation', $expired['status'] === 'PRIVATE_RETIREMENT_INTENT_EXPIRED'
    && $expired['manual_reconciliation_required'] === true && $restarted->journal($gDigest) === null
    && $journal->closure($g['before']['closure_id']) === $gView['job']['plan']['after'] && $gCalls === $beforeSourceCalls);
$again = $g['controller']->handle('POST', ['operation' => 'expire', 'intent_digest' => $gDigest,
    'nonce' => $session->nonce(retirementPurpose('expire', '', $gDigest))], $expireAt);
retirementCheck('lost_expiry_ack_cannot_repeat_scrub_or_claim_completion', $again['status'] === 'NO_PRIVATE_RETIREMENT_INTENT'
    && $again['manual_reconciliation_required'] === true);
retirementCheck('expiry_does_not_remove_or_cleanup_sender_fence', $g['pipe']->call('stats', ['now' => $expireAt])['private_fences'] === 1);
$next = $probeAfter; $next['revision']++;
$held = $journal->locked($probeAfter['closure_id'], fn() => retirementDenied(
    fn() => $journal->replaceClosure($probeAfter, $next), 'RETIREMENT_CUSTODY_RECONCILIATION_REQUIRED'));
retirementCheck('unresolved_scrub_blocks_later_amendment_cas', $held && $journal->closure($probeAfter['closure_id']) === $probeAfter);
retirementCheck('unresolved_scrub_blocks_new_retirement_before_source', retirementDenied(
    fn() => $g['controller']->handle('POST', ['operation' => 'prepare', 'closure_id' => $probeAfter['closure_id'],
        'nonce' => $session->nonce(retirementPurpose('prepare'))], $expireAt), 'RETIREMENT_CUSTODY_RECONCILIATION_REQUIRED'));
$store->pruneExpired($expireAt);
retirementCheck('expired_ui_cache_does_not_erase_authoritative_intent', $store->load($view['job']['id']) === null && $restarted->journal($digest) !== null);
$otherExpired = $f['controller']->handle('POST', ['operation' => 'expire', 'intent_digest' => $digest,
    'nonce' => $session->nonce(retirementPurpose('expire', '', $digest))], $expireAt);
retirementCheck('global_hold_does_not_prevent_private_identity_scrubbing', $otherExpired['status'] === 'PRIVATE_RETIREMENT_INTENT_EXPIRED'
    && $journal->closure($f['before']['closure_id']) === $after && $restarted->journal($digest) === null);

echo json_encode(['scope' => 'SYNTHETIC_OWNER_RETIREMENT_NATIVE', 'checks' => count($checks), 'passed' => array_keys($checks),
    'journal' => 'Actual MariaDB with cross-process custody lease', 'session' => 'Actual WordPress user and nonce',
    'receiver' => 'Actual source-derived receiver through local pipe', 'google_and_authority_services' => 'Synthetic doubles',
    'production_authorized' => false, 'purge_authorized' => false], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n";
