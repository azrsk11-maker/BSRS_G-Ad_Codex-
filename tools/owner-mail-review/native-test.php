<?php
declare(strict_types=1);
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
require '/opt/wordpress/wp-load.php';
$hooksBefore = array_map(fn($hook) => $hook->callbacks, $GLOBALS['wp_filter']);
require __DIR__ . '/WordPress.php';
require __DIR__ . '/TestDoubles.php';
require_once __DIR__ . '/Cleanup.php';
$noHooksInstalled = $hooksBefore === array_map(fn($hook) => $hook->callbacks, $GLOBALS['wp_filter']);
use BSRE\OwnerMailReview as O;
$checks = [];
function nativeCheck(string $name, bool $condition): void
{
    global $checks;
    if (!$condition) throw new RuntimeException('Owner mail native check failed: ' . $name);
    $checks[$name] = true;
}
function denied(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure $error) { return $error->getMessage() === $code; }
}
function syntheticUser(string $name): int
{
    $existing = get_user_by('login', $name);
    if ($existing) return (int) $existing->ID;
    $id = wp_insert_user(['user_login' => $name, 'user_email' => $name . '@example.invalid',
        'user_pass' => 'Synthetic-local-lab-only-487!', 'role' => 'administrator']);
    if (is_wp_error($id)) throw new RuntimeException('Synthetic user fixture failed');
    return (int) $id;
}
$ownerId = syntheticUser('owner-mail-synthetic-owner');
$otherId = syntheticUser('owner-mail-synthetic-other');
wp_set_current_user($ownerId);
$session = new O\WordPressSession($ownerId);
nativeCheck('loading_candidate_installs_no_hooks', $noHooksInstalled);
nativeCheck('real_wordpress_nominated_owner', $session->actor() === 'wp-user:' . $ownerId);
$nonce = $session->nonce('synthetic-action');
nativeCheck('real_wordpress_nonce_verifies_exact_action', $session->verify($nonce, 'synthetic-action') && !$session->verify($nonce, 'different-action'));
wp_set_current_user($otherId);
nativeCheck('other_administrator_is_not_owner', denied(fn() => $session->actor(), 'OWNER_SESSION_REQUIRED'));
wp_set_current_user(0);
nativeCheck('anonymous_cannot_issue_private_nonce', denied(fn() => $session->nonce('synthetic-action'), 'OWNER_SESSION_REQUIRED'));
wp_set_current_user($ownerId);
$owner = wp_get_current_user(); $owner->add_cap('manage_options', false);
nativeCheck('owner_without_capability_is_denied', denied(fn() => $session->actor(), 'OWNER_SESSION_REQUIRED'));
$owner->add_cap('manage_options');

$db = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $db->prefix = 'owner_mail_review_synthetic_';
$store = new O\WordPressStore($db); $store->install();
$db2 = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $db2->prefix = 'owner_mail_review_synthetic_';
$restarted = new O\WordPressStore($db2);
$badDb = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $badDb->prefix = 'wp_';
nativeCheck('ordinary_wordpress_prefix_is_rejected', denied(fn() => new O\WordPressStore($badDb), 'SYNTHETIC_STORE_REQUIRED'));
$f = O\fixture($store, $session); $view = O\prepare($f); $id = $view['job']['id'];
nativeCheck('private_job_survives_new_db_connection', $restarted->load($id) === $view['job']);
$store->locked($id, function () use ($id, $store, $restarted) {
    nativeCheck('connection_owned_job_lease_blocks_other_writer', denied(fn() => $restarted->locked($id, fn() => null), 'REVIEW_BUSY'));
    $job = $store->load($id); $stale = $job; $store->save($job);
    nativeCheck('stale_revision_cannot_overwrite_review', denied(function () use ($store, &$stale) { $store->save($stale); }, 'REVIEW_REVISION_OR_STORAGE_CONFLICT'));
    nativeCheck('readback_after_cas_retains_latest_revision', $restarted->load($id) === $job);
});
$view = O\approve($f, $view);
nativeCheck('native_owner_approval_records_exact_intent', $view['status'] === 'AWAITING_OWNER_MAIL_ACTION' && $restarted->load($id)['approved_at'] === $f['now']);
$input = O\handoff($f, $view);
nativeCheck('native_owner_assertion_cannot_replace_readback', denied(fn() => $f['controller']->handle('POST', $input, $f['now']), 'MAIL_ABSENCE_UNVERIFIED'));
unset($f['adapters']['email']->rows['synthetic-message-1']);
$complete = $f['controller']->handle('POST', $input, $f['now']);
nativeCheck('native_receipt_is_durable_on_fresh_connection', isset($restarted->load($id)['verified_receipts']['synthetic-message-1']));
nativeCheck('native_synthetic_flow_completes_without_mail_delete', $complete['status'] === 'COMPLETE' && $f['adapters']['email']->deletes === 0);
nativeCheck('private_html_uses_exact_ids_and_accessible_forms', str_contains($f['controller']->render($view), 'aria-labelledby=')
    && str_contains($f['controller']->render($view), 'rfc822_message_id'));

$later = $f['now'] + 30 * 86400;
$store->pruneExpired($later);
nativeCheck('sql_expiry_scrubs_only_private_review_cache', $restarted->load($id) === null && $f['journal']->journal($view['job']['plan']['digest']) !== null);
$cleanup = new O\CleanupController($f['workflow'], $f['authority'], $f['journal'], $session);
$digest = $view['job']['plan']['digest'];
$f['admission']->refresh($later);
$result = $cleanup->handle('POST', ['operation' => 'expire', 'plan_digest' => $digest,
    'nonce' => $session->nonce('bsre-owner-mail-cleanup/expire/' . $digest)], $later);
nativeCheck('separate_exact_cleanup_works_after_sql_cache_expiry', $result['status'] === 'PRIVATE_JOURNAL_EXPIRED' && $f['journal']->journals === []);
nativeCheck('cleanup_preserves_history_incomplete_marker', $f['journal']->historyIncomplete());
// Real WordPress identity/nonces and private MariaDB custody; source safety remains synthetic.
final class NativeSyntheticClosureSafety implements O\ClosureEditReadback
{
    public function readback(array $closure, int $now): ?array
    {
        return ['contract' => O\OwnerClosureController::SAFETY,
            'closure_hash' => \BSRE\ClosedRetention\Workflow::digest($closure),
            'sender_fence' => 'NONE', 'retirement_intent' => 'NONE', 'authoritative' => true,
            'observed_at' => $now, 'expires_at' => $now + 60,
            'evidence_reference' => 'synthetic-native-edit-safety', 'evidence_hash' => str_repeat('7', 64)];
    }
}
$db3 = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $db3->prefix = 'closed_retention_synthetic_';
$closureJournal = new \BSRE\ClosedRetention\LabSqlJournal($db3); $closureJournal->install();
$cf = \BSRE\ClosedRetention\fixture();
$baseline = $cf['closure']; $baseline['closure_id'] = \BSRE\ClosedRetention\syntheticUuid(101);
$closureJournal->putClosure($baseline);
$closureNow = time();
$producer = new O\OwnerClosureController($closureJournal, $store, $session, new NativeSyntheticClosureSafety());
$purpose = fn($operation, $job = '', $digest = '') => 'bsre-owner-closure/'
    . \BSRE\ClosedRetention\Workflow::digest([$operation, $job, $digest]);
$prepare = ['operation' => 'prepare', 'nonce' => $session->nonce($purpose('prepare')),
    'closure_id' => $baseline['closure_id'], 'status' => 'CLOSED',
    'closed_at_utc' => gmdate('Y-m-d\TH:i:s\Z', $closureNow - 3600),
    'evidence_reference' => 'synthetic-native-actual-closure', 'evidence_hash' => str_repeat('6', 64)];
wp_set_current_user($otherId);
nativeCheck('closure_screen_rejects_another_real_administrator', denied(fn() => $producer->handle('GET', [], $closureNow), 'OWNER_SESSION_REQUIRED'));
wp_set_current_user($ownerId);
$wrongPurpose = $prepare; $wrongPurpose['nonce'] = $session->nonce('bsre-owner-mail/prepare');
nativeCheck('closure_action_rejects_other_screen_nonce', denied(fn() => $producer->handle('POST', $wrongPurpose, $closureNow), 'CSRF_REJECTED'));
$privateReview = $producer->handle('POST', $prepare, $closureNow);
$closureId = $privateReview['job']['id']; $closureDigest = $privateReview['job']['plan']['digest'];
nativeCheck('closure_prepare_changes_no_authoritative_record', $closureJournal->closure($baseline['closure_id']) === $baseline);
nativeCheck('closure_private_plan_survives_fresh_sql_connection', $restarted->load($closureId) === $privateReview['job']);
nativeCheck('closure_screen_has_private_exact_form', str_contains($producer->render($privateReview), 'Exact private closure amendment')
    && str_contains($producer->render($privateReview), $closureDigest));
$approveClosure = ['operation' => 'approve', 'job' => $closureId, 'plan_digest' => $closureDigest,
    'nonce' => $session->nonce($purpose('approve', $closureId, $closureDigest))];
$updated = $producer->handle('POST', $approveClosure, $closureNow);
$recorded = $closureJournal->closure($baseline['closure_id']);
nativeCheck('real_owner_nonce_and_sql_cas_record_recent_closure', $updated['status'] === 'CLOSURE_AMENDMENT_APPLIED'
    && $recorded === $privateReview['job']['plan']['after'] && $recorded['revision'] === 2);
nativeCheck('closure_server_derives_identity_and_recording_time', $recorded['reviewer'] === 'wp-user:' . $ownerId
    && $recorded['recorded_at_utc'] === gmdate('Y-m-d\TH:i:s\Z', $closureNow)
    && $recorded['request_id'] === $baseline['request_id'] && $recorded['outcome_ids'] === $baseline['outcome_ids']);
$purgeAuthority = new O\ReviewAuthority($store, $session); $purgeAuthority->select($closureId);
nativeCheck('closure_approval_never_grants_purge', !$purgeAuthority->canApply($session->actor(), $closureDigest, $closureNow, 'PURGE'));
$resumeClosure = ['operation' => 'resume', 'job' => $closureId, 'plan_digest' => $closureDigest,
    'nonce' => $session->nonce($purpose('resume', $closureId, $closureDigest))];
$confirmed = $producer->handle('POST', $resumeClosure, $closureNow);
nativeCheck('native_closure_replay_does_not_increment_revision', $confirmed['status'] === 'CLOSURE_AMENDMENT_APPLIED'
    && $closureJournal->closure($baseline['closure_id']) === $recorded);
$due = false;
try { \BSRE\ClosedRetention\Workflow::validateClosureRecord($recorded, $closureNow, true); }
catch (\BSRE\ClosedRetention\Failure $error) { $due = $error->getMessage() === 'RETENTION_NOT_DUE'; }
nativeCheck('recent_recording_grants_no_early_retirement', $due);
$unverifiedProducer = new O\OwnerClosureController($closureJournal, $store, $session);
nativeCheck('native_default_safety_readback_remains_held', denied(fn() => $unverifiedProducer->handle('POST', $prepare, $closureNow), 'CLOSURE_EDIT_SAFETY_UNVERIFIED'));

echo json_encode(['scope' => 'SYNTHETIC_OWNER_MAIL_NATIVE', 'checks' => count($checks), 'passed' => array_keys($checks),
    'production_authorized' => false, 'mailbox_provider' => 'synthetic_memory_only'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
