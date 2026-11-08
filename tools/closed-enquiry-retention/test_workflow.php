<?php
declare(strict_types=1);
define('BSRE_CLOSED_RETENTION_LAB', true);
function wp_get_environment_type(): string { return 'local'; }
function home_url(): string { return 'http://bsre.invalid'; }
require __DIR__ . '/fixtures.php';
use BSRE\ClosedRetention as C;

$checks = [];
function check(string $name, bool $condition): void
{
    global $checks;
    if (!$condition) throw new RuntimeException('Closed retention check failed: ' . $name);
    $checks[$name] = true;
}
function held(array $result, string $code): bool { return $result['status'] === 'HELD' && in_array($code, $result['hold_codes'], true); }

$f = C\fixture();
$preview = $f['workflow']->preview($f['closure']['closure_id'], $f['now']);
check('preview_is_aggregate_only', $preview['status'] === 'READY_FOR_OWNER_REVIEW'
    && !str_contains(json_encode($preview), $f['closure']['request_id']));
check('preview_never_deletes', array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 0);
$plan = C\approved($f);
$result = C\executeWithOwnerMail($f, $plan, $f['now']);
check('all_five_exact_resources_deleted', $result['status'] === 'COMPLETE' && $result['confirmed_absent'] === 5);
check('history_incomplete_persists', $f['journal']->historyIncomplete());
check('completed_retry_is_idempotent', C\executeWithOwnerMail($f, $plan, $f['now'])['status'] === 'COMPLETE'
    && array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 4 && $f['adapters']['email']->deletes === 0);
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL';
check('private_cleanup_not_early', held($f['workflow']->expire($plan, 'synthetic-owner', $f['now'] + 86400), 'RECOVERY_WINDOW_ACTIVE'));
$f['admission']->refresh($f['now'] + 30 * 86400);
check('private_cleanup_after_thirty_days', $f['workflow']->expire($plan, 'synthetic-owner', $f['now'] + 30 * 86400)['status'] === 'PRIVATE_JOURNAL_EXPIRED'
    && $f['journal']->closures === [] && $f['journal']->journals === [] && $f['journal']->historyIncomplete());

$f = C\fixture();
$workflow = new C\Workflow($f['journal'], $f['adapters'], $f['authority']);
check('unverified_admission_held', held($workflow->preview($f['closure']['closure_id'], $f['now']), 'ADMISSION_UNVERIFIED'));
$f['admission']->value['receiver']['generation'] = str_repeat('f', 64);
check('generation_mismatch_held', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'ADMISSION_GENERATION_CONFLICT'));
$f = C\fixture(); $f['admission']->value['wp']['routes_installed'] = false;
check('route_enforcement_required', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'ADMISSION_UNVERIFIED'));
$f = C\fixture(); $f['admission']->value['expires_at'] = $f['now'];
check('expired_readback_held', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'ADMISSION_STALE'));
$f = C\fixture();
check('calendar_boundary_not_early', held($f['workflow']->preview($f['closure']['closure_id'], $f['now'] - 1), 'RETENTION_NOT_DUE'));
check('leap_day_clamps_in_dubai', gmdate('Y-m-d\TH:i:s\Z', \BSRE\RetentionReview\RetentionInventory::anniversary(strtotime('2024-02-29T08:00:00Z'))) === '2025-02-28T08:00:00Z');
$f = C\fixture(); $f['journal']->closures[$f['closure']['closure_id']]['email_status'] = 'AMBIGUOUS';
check('ambiguous_outbox_held', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'OUTBOX_NOT_RECONCILED'));
$f = C\fixture(); $f['journal']->closures[$f['closure']['closure_id']]['closed_at_utc'] = '2025-02-30T12:00:00Z';
check('invalid_calendar_time_rejected', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'TIME_INVALID'));
$f = C\fixture(); $f['adapters']['email']->rows['synthetic-message-1']['mailbox'] = 'outside@example.invalid';
check('wrong_mailbox_held', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'MAIL_BINDING_INVALID'));
$f = C\fixture(); $f['adapters']['capture']->rows['synthetic-capture']['request_ids'][] = C\syntheticUuid(99);
check('shared_resource_held', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'SHARED_RESOURCE_REQUIRES_REVIEW'));
$f = C\fixture(); $f['adapters']['outcome']->rows = [];
check('missing_associated_outcome_held', held($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'LINKAGE_INCOMPLETE'));

$f = C\fixture(); $plan = C\approved($f);
$f['journal']->closures[$f['closure']['closure_id']]['revision']++;
check('changed_revision_invalidates_plan', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'PLAN_STALE'));
$f = C\fixture(); $plan = C\approved($f);
$f['journal']->closures[$f['closure']['closure_id']]['status'] = 'OPEN';
$f['journal']->closures[$f['closure']['closure_id']]['closed_at_utc'] = null;
check('reopened_record_held', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'ENQUIRY_OPEN'));
$f = C\fixture(); $plan = C\approved($f); $plan['resources'] = [];
check('tampered_plan_rejected', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'PLAN_INVALID'));

$f = C\fixture(); $plan = C\approved($f); $f['journal']->markerFails = true;
check('missing_history_marker_prevents_delete', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'HISTORY_MARKER_UNVERIFIED')
    && array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 0);
$f = C\fixture(); $plan = C\approved($f);
$f['adapters']['outcome']->afterDelete = function () { throw new RuntimeException('PRIVATE_CANARY_ID'); };
$result = C\executeWithOwnerMail($f, $plan, $f['now']);
check('lost_ack_retains_durable_intent', held($result, 'PROVIDER_OR_STORAGE_UNCERTAIN')
    && !str_contains(json_encode($result), 'PRIVATE_CANARY_ID')
    && $f['journal']->journal($plan['digest'])['steps'][1] === 'INTENT_RECORDED');
$f['adapters']['outcome']->afterDelete = null;
$f['admission']->refresh($f['now'] + 600);
check('fresh_same_config_resume_after_readback_expiry', C\executeWithOwnerMail($f, $plan, $f['now'] + 600)['status'] === 'COMPLETE'
    && $f['adapters']['email']->deletes === 0 && $f['adapters']['outcome']->deletes === 2);

$f = C\fixture(); $plan = C\approved($f);
$f['adapters']['outcome']->afterDelete = function () { throw new RuntimeException('after delete'); };
C\executeWithOwnerMail($f, $plan, $f['now']);
$f['adapters']['outcome']->afterDelete = null;
$f['journal']->closures[$f['closure']['closure_id']]['revision']++;
check('partial_reopen_prevents_further_delete', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'CLOSURE_CHANGED_OR_REOPENED')
    && $f['adapters']['outcome']->deletes === 1);
check('expired_partial_job_requires_reconciliation', held(C\executeWithOwnerMail($f, $plan, $f['now'] + 30 * 86400), 'RECOVERY_WINDOW_EXPIRED'));
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL';
$expiry = $f['workflow']->expire($plan, 'synthetic-owner', $f['now'] + 30 * 86400);
check('expired_partial_job_scrubbed_with_explicit_reconciliation', $expiry['status'] === 'PRIVATE_JOURNAL_EXPIRED'
    && $expiry['hold_codes'] === ['MANUAL_RECONCILIATION_REQUIRED'] && $f['journal']->journals === []
    && $f['journal']->closures !== [] && $f['journal']->expiredUnresolved === 1 && $f['journal']->historyIncomplete());

$f = C\fixture(); $plan = C\approved($f); $mail = $f['adapters']['email']->rows['synthetic-message-1'];
C\executeWithOwnerMail($f, $plan, $f['now']);
$f['adapters']['email']->rows['synthetic-message-1'] = $mail;
check('recreated_resource_blocks_complete', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'RESOURCE_SCOPE_CHANGED'));

$f = C\fixture(); $plan = C\approved($f); $mail = $f['adapters']['email']->rows['synthetic-message-1'];
C\executeWithOwnerMail($f, $plan, $f['now']);
$f['adapters']['email']->rows['synthetic-message-1'] = $mail;
$f['admission']->refresh($f['now'] + 30 * 86400);
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL';
check('cleanup_keeps_bindings_when_resource_reappears', held($f['workflow']->expire($plan, 'synthetic-owner', $f['now'] + 30 * 86400), 'RESOURCE_SCOPE_CHANGED')
    && $f['journal']->journal($plan['digest']) !== null);

$f = C\fixture(); $plan = C\approved($f); $f['authority']->approved = null;
check('exact_owner_approval_required', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'EXACT_APPROVAL_REQUIRED')
    && $f['adapters']['email']->deletes === 0);

$f = C\fixture(); $plan = C\approved($f);
$f['adapters']['outcome']->beforeDelete = function () { throw new RuntimeException('before provider action'); };
check('predelete_failure_keeps_intent', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'PROVIDER_OR_STORAGE_UNCERTAIN')
    && $f['adapters']['outcome']->deletes === 0);
$f['adapters']['outcome']->beforeDelete = null;
check('retry_present_target_deletes_once', C\executeWithOwnerMail($f, $plan, $f['now'])['status'] === 'COMPLETE'
    && $f['adapters']['email']->deletes === 0 && $f['adapters']['outcome']->deletes === 2);

$f = C\fixture(); $plan = C\approved($f);
$f['authority']->afterManualMail = function () use (&$f) {
    $extra = reset($f['adapters']['outcome']->rows); $extra['key'] = C\syntheticUuid(99);
    $f['adapters']['outcome']->rows[$extra['key']] = $extra;
};
check('late_linked_resource_stops_partial_purge', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'RESOURCE_SCOPE_CHANGED')
    && $f['adapters']['outcome']->deletes === 0);

$f = C\fixture(); $plan = C\approved($f);
C\executeWithOwnerMail($f, $plan, $f['now']);
$f['journal']->journals[$plan['digest']]['steps'][0] = 'UNSUPPORTED';
check('corrupt_journal_cannot_claim_complete', held(C\executeWithOwnerMail($f, $plan, $f['now']), 'JOURNAL_INVALID'));

$f = C\fixture(); $plan = C\approved($f);
check('private_owner_manifest_requires_durable_intent', $f['workflow']->ownerMailAction($plan, 'synthetic-owner', $f['now']) === null);
$waiting = $f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
check('no_automatic_email_or_other_provider_delete', $waiting['status'] === 'AWAITING_OWNER_MAIL_ACTION'
    && array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 0);
$originalMail = $f['adapters']['email']->rows['synthetic-message-1'];
$manifest = C\ownerAction($f, $plan, $f['now']);
check('owner_manifest_is_exact_marketing_copy', $manifest['plan_digest'] === $plan['digest']
    && $manifest['binding']['mailbox'] === 'marketing@blackswanrealestate.ae'
    && $manifest['binding']['message_id'] === 'synthetic-message-1');
$f['adapters']['email']->rows['synthetic-message-1'] = $originalMail;
check('owner_receipt_without_independent_absence_still_waits', $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'AWAITING_OWNER_MAIL_ACTION'
    && $f['adapters']['outcome']->deletes === 0);
unset($f['adapters']['email']->rows['synthetic-message-1']);
$receipt = $f['authority']->receipts[$plan['digest']]['synthetic-message-1'];
unset($f['authority']->receipts[$plan['digest']]['synthetic-message-1']);
check('absence_without_bound_owner_receipt_held', held($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'OWNER_MAIL_RECEIPT_REQUIRED'));
$badReceipt = $receipt; $badReceipt['plan_digest'] = str_repeat('0', 64);
$f['authority']->receipts[$plan['digest']]['synthetic-message-1'] = $badReceipt;
check('receipt_for_different_plan_held', held($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'OWNER_MAIL_RECEIPT_CONFLICT'));
$f['authority']->receipts[$plan['digest']]['synthetic-message-1'] = $receipt;
check('bound_owner_receipt_and_absence_allow_other_stores', $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE'
    && $f['adapters']['email']->deletes === 0 && $f['adapters']['outcome']->deletes === 2);
check('durable_nonidentifying_admission_floor_pinned', $f['journal']->admissionFloor() === $plan['admission_hash']);

$f = C\fixture(); $plan = C\approved($f);
$f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
$f['journal']->floor = null;
check('missing_floor_after_intent_holds_resume', held($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'ADMISSION_FLOOR_UNVERIFIED')
    && $f['workflow']->ownerMailAction($plan, 'synthetic-owner', $f['now']) === null);

$f = C\fixture(); $plan = C\approved($f);
$f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
$f['adapters']['email'] = new class($f['adapters']['email']) implements C\ResourceAdapter {
    private C\MemoryResource $source;
    public function __construct(C\MemoryResource $source) { $this->source = $source; }
    public function inventory(string $requestId): array { return $this->source->inventory($requestId); }
    public function read(string $key): ?array
    {
        $row = $this->source->read($key);
        if ($row !== null) $row['fingerprint'] = str_repeat('7', 64);
        return $row;
    }
    public function removeExact(array $binding): void { throw new RuntimeException('Synthetic mail delete forbidden'); }
};
$f['workflow'] = new C\Workflow($f['journal'], $f['adapters'], $f['authority'], $f['admission']);
$directConflict = false;
try { $f['workflow']->ownerMailAction($plan, 'synthetic-owner', $f['now']); }
catch (C\Failure $error) { $directConflict = $error->getMessage() === 'RESOURCE_BINDING_CHANGED'; }
check('mail_manifest_rechecks_exact_direct_binding', $directConflict);

$f = C\fixture(); $plan = C\approved($f);
$f['adapters']['intake']->afterDelete = function () use (&$f) {
    // Simulate an external writer that did not honor the required closure lease.
    $row = &$f['journal']->closures[$f['closure']['closure_id']];
    $row['revision']++;
    $row['status'] = 'OPEN';
    $row['closed_at_utc'] = null;
};
$lastReopen = C\executeWithOwnerMail($f, $plan, $f['now']);
check('last_step_reopen_blocks_completion', held($lastReopen, 'CLOSURE_CHANGED_OR_REOPENED')
    && $lastReopen['confirmed_absent'] === 5 && $f['journal']->historyIncomplete());

echo json_encode(['phase' => 'closed_retention_pure', 'checks' => $checks, 'production_authorized' => false], JSON_THROW_ON_ERROR) . "\n";
