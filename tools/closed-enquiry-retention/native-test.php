<?php
declare(strict_types=1);
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
require '/opt/wordpress/wp-load.php';
require __DIR__ . '/fixtures.php';
use BSRE\ClosedRetention as C;

$db = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
$db->prefix = 'closed_retention_synthetic_';
$journal = new C\LabSqlJournal($db);
$journal->install();
$checks = [];
function nativeCheck(string $name, bool $condition): void
{
    global $checks;
    if (!$condition) throw new RuntimeException('Closed retention native check failed: ' . $name);
    $checks[$name] = true;
}

$f = C\fixture($journal);
$plan = C\approved($f);
$db2 = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
$db2->prefix = 'closed_retention_synthetic_';
$restarted = new C\LabSqlJournal($db2);
$seenBeforeAction = false;
$f['adapters']['outcome']->beforeDelete = function () use ($restarted, $plan, &$seenBeforeAction) {
    $observed = $restarted->journal($plan['digest']);
    $seenBeforeAction = $observed['steps'][1] === 'INTENT_RECORDED' && $restarted->historyIncomplete()
        && $restarted->admissionFloor() === $plan['admission_hash'];
};
$f['adapters']['outcome']->afterDelete = function () { throw new RuntimeException('synthetic lost acknowledgment'); };
$first = C\executeWithOwnerMail($f, $plan, $f['now']);
nativeCheck('provider_loss_is_held', $first['status'] === 'HELD');
$stored = $journal->journal($plan['digest']);
nativeCheck('intent_committed_before_provider_action', $seenBeforeAction && $stored['steps'][1] === 'INTENT_RECORDED' && $stored['revision'] >= 3);
nativeCheck('history_marker_committed_before_outcome_delete', $seenBeforeAction && $f['adapters']['outcome']->deletes === 1);
nativeCheck('admission_floor_durable_and_nonidentifying', $journal->admissionFloor() === $plan['admission_hash']);

nativeCheck('fresh_connection_reads_same_journal', $restarted->journal($plan['digest']) === $stored);
$f['adapters']['outcome']->afterDelete = null;
$f['adapters']['outcome']->beforeDelete = null;
$f['admission']->refresh($f['now'] + 600);
$resumed = new C\Workflow($restarted, $f['adapters'], $f['authority'], $f['admission']);
$result = $resumed->execute($plan, 'synthetic-owner', $f['now'] + 600);
nativeCheck('fresh_workflow_resumes_to_completion', $result['status'] === 'COMPLETE' && $result['confirmed_absent'] === 5);
nativeCheck('no_mail_provider_delete_and_no_duplicate_outcome_delete', $f['adapters']['email']->deletes === 0 && $f['adapters']['outcome']->deletes === 2);

$journal->locked($f['closure']['closure_id'], function () use ($journal, $restarted, $f, $plan) {
    $revision = $f['closure']; $revision['revision']++;
    $busy = false;
    try { $restarted->putClosure($revision); } catch (RuntimeException $error) { $busy = $error->getMessage() === 'CLOSURE_LEASE_BUSY'; }
    nativeCheck('concurrent_closure_writer_blocked', $busy && $journal->closure($revision['closure_id'])['revision'] === 1);
    $current = $journal->journal($plan['digest']);
    $stale = $current;
    $journal->save($current);
    $conflict = false;
    try { $journal->save($stale); } catch (RuntimeException $error) { $conflict = true; }
    nativeCheck('stale_journal_cas_cannot_overwrite', $conflict && $journal->journal($plan['digest']) === $current);
});

$cleanupAt = $f['now'] + 600 + 30 * 86400;
$f['admission']->refresh($cleanupAt);
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL';
nativeCheck('private_identifiers_removed_after_recovery_window', $resumed->expire($plan, 'synthetic-owner', $cleanupAt)['status'] === 'PRIVATE_JOURNAL_EXPIRED'
    && $restarted->journal($plan['digest']) === null && $restarted->closure($f['closure']['closure_id']) === null);
nativeCheck('nonidentifying_history_gap_marker_survives_cleanup', $restarted->historyIncomplete());
nativeCheck('nonidentifying_admission_floor_survives_cleanup', $restarted->admissionFloor() === $plan['admission_hash']);

// Protected amendments use the existing connection-owned lease and exact CAS.
$amendment = C\fixture($journal);
$before = $amendment['closure'];
$after = $before;
$after['revision']++;
$after['status'] = 'CLOSED';
$after['recorded_at_utc'] = gmdate('Y-m-d\TH:i:s\Z', $amendment['now']);
$denied = false;
try { $journal->replaceClosure($before, $after); }
catch (RuntimeException $error) { $denied = $error->getMessage() === 'CLOSURE_LEASE_REQUIRED'; }
nativeCheck('amendment_requires_existing_closure_lease', $denied && $journal->closure($before['closure_id']) === $before);
$journal->locked($before['closure_id'], function () use ($journal, $restarted, $before, $after) {
    $denied = false;
    try { $restarted->replaceClosure($before, $after); }
    catch (RuntimeException $error) { $denied = $error->getMessage() === 'CLOSURE_LEASE_REQUIRED'; }
    nativeCheck('another_connection_cannot_borrow_closure_lease', $denied);
    $journal->replaceClosure($before, $after);
    nativeCheck('exact_amendment_is_visible_to_fresh_connection', $restarted->closure($before['closure_id']) === $after);
    $denied = false;
    try { $journal->replaceClosure($before, $after); }
    catch (RuntimeException $error) { $denied = $error->getMessage() === 'CLOSURE_REVISION_CONFLICT'; }
    nativeCheck('stale_amendment_cannot_bump_revision_twice', $denied && $journal->closure($before['closure_id']) === $after);
});
$amendment['closure'] = $after;
$amendmentPlan = C\approved($amendment);
$amendment['workflow']->execute($amendmentPlan, 'synthetic-owner', $amendment['now']);
$next = $after; $next['revision']++;
$journal->locked($after['closure_id'], function () use ($journal, $after, $next) {
    $denied = false;
    try { $journal->replaceClosure($after, $next); }
    catch (RuntimeException $error) { $denied = $error->getMessage() === 'CLOSURE_JOB_RECONCILIATION_REQUIRED'; }
    nativeCheck('existing_purge_journal_blocks_amendment', $denied && $journal->closure($after['closure_id']) === $after);
});

$unknownBefore = $after; $unknownBefore['closure_id'] = C\syntheticUuid(102); $unknownBefore['revision'] = 1;
$journal->putClosure($unknownBefore);
$unknownAfter = $unknownBefore; $unknownAfter['revision']++;
$unknownId = str_repeat('f', 64);
if ($db->query($db->prepare("INSERT INTO closed_retention_synthetic_jobs VALUES (%s,1,%s)",
    $unknownId, json_encode(['revision' => 1, 'plan' => []], JSON_THROW_ON_ERROR))) !== 1) throw new RuntimeException('Synthetic unknown job fixture failed');
$journal->locked($unknownBefore['closure_id'], function () use ($journal, $unknownBefore, $unknownAfter) {
    $denied = false;
    try { $journal->replaceClosure($unknownBefore, $unknownAfter); }
    catch (RuntimeException $error) { $denied = $error->getMessage() === 'CLOSURE_JOB_RECONCILIATION_REQUIRED'; }
    nativeCheck('unknown_job_binding_is_not_assumed_unrelated', $denied && $journal->closure($unknownBefore['closure_id']) === $unknownBefore);
});
if ($db->query($db->prepare("DELETE FROM closed_retention_synthetic_jobs WHERE id=%s", $unknownId)) !== 1) throw new RuntimeException('Synthetic unknown job cleanup failed');

echo json_encode(['phase' => 'closed_retention_native', 'checks' => $checks,
    'journal' => 'Actual MariaDB', 'provider_resources' => 'Synthetic memory adapters',
    'production_authorized' => false], JSON_THROW_ON_ERROR) . "\n";
