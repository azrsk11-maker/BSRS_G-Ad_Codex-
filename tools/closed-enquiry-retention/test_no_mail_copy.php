<?php
declare(strict_types=1);
define('BSRE_CLOSED_RETENTION_LAB', true);
function wp_get_environment_type(): string { return 'local'; }
function home_url(): string { return 'http://bsre.invalid'; }
require __DIR__ . '/fixtures.php';
use BSRE\ClosedRetention as C;

require_once __DIR__ . '/ReceiverPipe.php';

final class CleanupFaultJournal implements C\Journal
{
    public bool $failForget = false;
    public function __construct(public C\MemoryJournal $inner) {}
    public function locked(string $closureId, callable $operation) { return $this->inner->locked($closureId, $operation); }
    public function closure(string $closureId): ?array { return $this->inner->closure($closureId); }
    public function journal(string $planId): ?array { return $this->inner->journal($planId); }
    public function save(array &$record): void { $this->inner->save($record); }
    public function markHistoryIncomplete(): void { $this->inner->markHistoryIncomplete(); }
    public function historyIncomplete(): bool { return $this->inner->historyIncomplete(); }
    public function pinAdmissionFloor(string $policyHash): void { $this->inner->pinAdmissionFloor($policyHash); }
    public function admissionFloor(): ?string { return $this->inner->admissionFloor(); }
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void
    {
        if ($this->failForget) throw new RuntimeException('Synthetic journal cleanup unavailable');
        $this->inner->forget($closureId, $planId, $keepClosure);
    }
}

function noCopyFixture(): array
{
    $f = C\fixture(); $pipe = new SyntheticReceiverPipe();
    $f['admission']->value['source_hashes']['receiver'] = $pipe->call('metadata')['source_hash'];
    $a = $f['admission']->value;
    $admissionHash = C\Workflow::digest(['wp' => $a['wp'], 'receiver' => $a['receiver'],
        'source_hashes' => $a['source_hashes'], 'restore_policy_hash' => $a['restore_policy_hash']]);
    $identity = $pipe->call('init', ['accepted_at' => strtotime($f['closure']['accepted_at_utc']),
        'now' => $f['now'], 'admission_hash' => $admissionHash, 'activated_at' => $a['receiver']['activated_at']]);
    $f['closure'] = array_replace($f['closure'], array_intersect_key($identity, array_flip(['request_id', 'lead_id', 'event_id'])));
    $f['closure']['email_status'] = 'RETIRED_NO_COPY'; $f['closure']['mail_message_ids'] = [];
    $f['journal']->closures[$f['closure']['closure_id']] = $f['closure'];
    $f['adapters']['email']->rows = [];
    foreach (['intake', 'capture', 'outcome'] as $store) foreach ($f['adapters'][$store]->rows as &$row) {
        foreach (['request_id', 'lead_id', 'event_id', 'fingerprint'] as $key) $row[$key] = $identity[$key];
        $row['request_ids'] = [$identity['request_id']];
    }
    unset($row);
    $scope = C\NoMailCopyProof::scope($f['closure'], $admissionHash, $identity['fingerprint']);
    $pipe->call('retire', compact('scope'));
    $f['adapters']['intake'] = new SyntheticReceiverIntakeResource($pipe, $f['journal'], $scope);
    $f['workflow'] = new C\Workflow($f['journal'], $f['adapters'], $f['authority'], $f['admission'], $pipe);
    return $f + compact('pipe', 'scope');
}

$checks = [];
function checkNoCopy(string $name, bool $value): void
{
    global $checks;
    if (!$value) throw new RuntimeException('No-copy check failed: ' . $name);
    $checks[$name] = true;
}
function noCopyHeld(array $result, string $code): bool
{
    return $result['status'] === 'HELD' && in_array($code, $result['hold_codes'], true);
}

$f = noCopyFixture();
$unverified = new C\Workflow($f['journal'], $f['adapters'], $f['authority'], $f['admission']);
checkNoCopy('default_adapter_never_allows_zero_email_resources', noCopyHeld($unverified->preview($f['closure']['closure_id'], $f['now']), 'NO_COPY_UNVERIFIED'));
$sent = C\fixture(); $sent['adapters']['email']->rows = [];
checkNoCopy('sent_status_still_requires_an_exact_email_copy', noCopyHeld($sent['workflow']->preview($sent['closure']['closure_id'], $sent['now']), 'LINKAGE_INCOMPLETE'));
unset($sent);
$preview = $f['workflow']->preview($f['closure']['closure_id'], $f['now']);
checkNoCopy('actual_receiver_proof_allows_aggregate_preview', $preview['status'] === 'READY_FOR_OWNER_REVIEW'
    && !str_contains(json_encode($preview), $f['scope']['request_id']));
$plan = C\approved($f);
checkNoCopy('exact_plan_binds_original_scope_and_fence', $plan['no_mail_copy']['scope'] === $f['scope']
    && count($plan['resources']) === 4);
$result = $f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
checkNoCopy('four_exact_nonmail_resources_complete_without_owner_mail_action', $result['status'] === 'COMPLETE'
    && $result['confirmed_absent'] === 4 && $f['authority']->receipts === [] && $f['adapters']['email']->deletes === 0);
checkNoCopy('intake_purge_removes_same_receiver_outbox_row', $f['pipe']->call('stats')['rows'] === 0
    && $f['pipe']->call('stats')['mail'] === 0);
checkNoCopy('history_and_nonidentifying_admission_floor_survive', $f['journal']->historyIncomplete()
    && $f['journal']->admissionFloor() === $plan['admission_hash']);
checkNoCopy('completed_retry_revalidates_provider_proof', $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE');
$f['pipe']->call('state', ['key' => 'mailbox', 'value' => 'UNKNOWN']);
checkNoCopy('completed_retry_cannot_ignore_new_mailbox_uncertainty', noCopyHeld($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'NO_COPY_MAILBOX_UNVERIFIED'));
unset($f);

$f = noCopyFixture();
foreach (['SENDING', 'AMBIGUOUS', 'QUEUED', 'UNKNOWN'] as $status) {
    $f['journal']->closures[$f['closure']['closure_id']]['email_status'] = $status;
    checkNoCopy('closure_' . strtolower($status) . '_cannot_mint_no_copy', noCopyHeld($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'OUTBOX_NOT_RECONCILED'));
}
unset($f);

$f = noCopyFixture();
foreach ([
    'incomplete_mailbox' => fn($p) => array_replace_recursive($p, ['mailbox' => ['complete' => false]]),
    'trash_unobserved' => fn($p) => array_replace_recursive($p, ['mailbox' => ['includes_trash' => false]]),
    'wrong_scope' => fn($p) => array_replace_recursive($p, ['scope' => ['closure_revision' => 2]]),
    'string_revision' => fn($p) => array_replace_recursive($p, ['scope' => ['closure_revision' => '1']]),
    'wrong_scope_hash' => fn($p) => array_replace($p, ['scope_hash' => str_repeat('0', 64)]),
    'stale_mailbox' => fn($p) => array_replace_recursive($p, ['mailbox' => ['expires_at' => $f['now']]]),
    'missing_provider_field' => function ($p) { unset($p['recovery']); return $p; },
    'unbound_store_floor' => fn($p) => array_replace($p, ['external_floor_hash' => str_repeat('0', 64)]),
] as $name => $alter) {
    $f['pipe']->alterProof = $alter;
    checkNoCopy($name . '_is_held', $f['workflow']->preview($f['closure']['closure_id'], $f['now'])['status'] === 'HELD');
}
$f['pipe']->alterProof = null;
$plan = C\approved($f);
$f['pipe']->alterProof = fn($p) => array_replace($p, ['fence_hash' => str_repeat('0', 64)]);
checkNoCopy('changed_fence_invalidates_exact_approved_plan', noCopyHeld($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'PLAN_STALE'));
checkNoCopy('changed_fence_prevents_any_delete', array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 0);
unset($f);

$f = noCopyFixture(); $plan = C\approved($f);
$f['adapters']['outcome']->afterDelete = fn() => $f['pipe']->call('state', ['key' => 'mailbox', 'value' => 'UNKNOWN']);
$first = $f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
checkNoCopy('loss_of_absence_during_partial_purge_holds_remaining_steps', noCopyHeld($first, 'NO_COPY_MAILBOX_UNVERIFIED')
    && $f['adapters']['outcome']->deletes === 1 && $f['adapters']['intake']->deletes === 0);
$f['adapters']['outcome']->afterDelete = null;
$f['pipe']->call('state', ['key' => 'mailbox', 'value' => 'ABSENT']); $f['admission']->refresh($f['now'] + 600);
checkNoCopy('fresh_same_scope_absence_resumes_without_duplicate_delete', $f['workflow']->execute($plan, 'synthetic-owner', $f['now'] + 600)['status'] === 'COMPLETE'
    && $f['adapters']['outcome']->deletes === 2 && $f['pipe']->call('stats')['rows'] === 0);
$cleanupAt = $f['now'] + 600 + 30 * 86400;
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL'; $f['admission']->refresh($cleanupAt);
checkNoCopy('thirty_day_boundary_alone_cannot_delete_fence_or_journal', noCopyHeld($f['workflow']->expire($plan, 'synthetic-owner', $cleanupAt), 'NO_COPY_RECOVERY_UNVERIFIED')
    && $f['pipe']->call('stats')['private_fences'] === 1 && $f['journal']->journal($plan['digest']) !== null);
$f['pipe']->call('state', ['key' => 'backupsExpiredThrough', 'value' => $cleanupAt]);
$f['pipe']->call('state', ['key' => 'storageFault', 'value' => true]);
checkNoCopy('unconfirmed_fence_cleanup_keeps_private_journal', $f['workflow']->expire($plan, 'synthetic-owner', $cleanupAt)['status'] === 'HELD'
    && $f['journal']->journal($plan['digest']) !== null && $f['pipe']->call('stats')['private_fences'] === 1);
$f['pipe']->call('state', ['key' => 'storageFault', 'value' => false]);
checkNoCopy('verified_backup_expiry_and_restore_floor_allow_bounded_private_cleanup', $f['workflow']->expire($plan, 'synthetic-owner', $cleanupAt)['status'] === 'PRIVATE_JOURNAL_EXPIRED'
    && $f['pipe']->call('stats')['private_fences'] === 0 && $f['journal']->closures === [] && $f['journal']->journals === []);
checkNoCopy('cleanup_retains_only_nonidentifying_safety_state', $f['pipe']->call('stats')['floor_present'] === true
    && $f['journal']->historyIncomplete() && $f['journal']->admissionFloor() === $plan['admission_hash']);
unset($f);

$f = noCopyFixture(); $plan = C\approved($f);
checkNoCopy('cleanup_fault_fixture_completes', $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE');
$journal = new CleanupFaultJournal($f['journal']);
$workflow = new C\Workflow($journal, $f['adapters'], $f['authority'], $f['admission'], $f['pipe']);
$cleanupAt = $f['now'] + 30 * 86400; $f['admission']->refresh($cleanupAt);
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL';
$f['pipe']->call('state', ['key' => 'backupsExpiredThrough', 'value' => $cleanupAt]);
$f['pipe']->loseForgetAcknowledgement = true;
checkNoCopy('lost_fence_delete_ack_retains_signed_intent_in_existing_private_journal',
    noCopyHeld($workflow->expire($plan, 'synthetic-owner', $cleanupAt), 'NO_COPY_CUSTODY_UNCONFIRMED')
    && is_array($journal->journal($plan['digest'])['no_copy_cleanup']) && $f['pipe']->call('stats')['private_fences'] === 0);
$bareAbsenceHeld = false;
try { $f['pipe']->readback($f['scope'], $cleanupAt, true); }
catch (C\Failure $error) { $bareAbsenceHeld = $error->getMessage() === 'NO_COPY_FENCE_MISSING'; }
checkNoCopy('deleted_fence_absence_without_signed_intent_is_not_cleanup_proof', $bareAbsenceHeld);
$journal->failForget = true; $journalFailed = false;
try { $workflow->expire($plan, 'synthetic-owner', $cleanupAt); }
catch (RuntimeException $error) { $journalFailed = true; }
checkNoCopy('journal_cleanup_failure_keeps_authenticated_retry_intent', $journalFailed
    && $journal->journal($plan['digest']) !== null && $f['pipe']->call('stats')['private_fences'] === 0);
$journal->failForget = false;
checkNoCopy('signed_intent_reconciles_deleted_fence_and_finishes_journal_cleanup',
    $workflow->expire($plan, 'synthetic-owner', $cleanupAt)['status'] === 'PRIVATE_JOURNAL_EXPIRED'
    && $journal->journal($plan['digest']) === null && $journal->closure($plan['closure_id']) === null
    && $journal->historyIncomplete());
unset($f, $workflow, $journal);

$f = noCopyFixture(); $plan = C\approved($f);
$f['adapters']['intake']->afterDelete = function () use ($f) {
    $f['pipe']->alterProof = fn($proof) => array_replace($proof, ['row_state' => 'RETIRED']);
};
checkNoCopy('actual_sender_row_absence_is_required_at_final_completion',
    noCopyHeld($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'NO_COPY_INTAKE_NOT_ABSENT'));
$f['adapters']['intake']->afterDelete = null; $f['pipe']->alterProof = null;
checkNoCopy('consistent_absence_resumes_without_repeating_completed_deletes',
    $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE'
    && $f['adapters']['intake']->deletes === 1);
$f['pipe']->alterProof = fn($proof) => array_replace($proof, ['row_state' => 'RETIRED']);
checkNoCopy('completed_retry_rechecks_actual_sender_row_absence',
    noCopyHeld($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'NO_COPY_INTAKE_NOT_ABSENT'));
$f['pipe']->alterProof = null;
checkNoCopy('completed_retry_can_recover_consistent_readback', $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE');
$f['pipe']->alterProof = fn($proof) => array_replace($proof, ['row_state' => 'RETIRED']);
$cleanupAt = $f['now'] + 30 * 86400; $f['admission']->refresh($cleanupAt);
$f['authority']->actions[] = 'EXPIRE_PRIVATE_JOURNAL';
$f['pipe']->call('state', ['key' => 'backupsExpiredThrough', 'value' => $cleanupAt]);
checkNoCopy('completed_cleanup_rejects_contradictory_sender_row_retention',
    noCopyHeld($f['workflow']->expire($plan, 'synthetic-owner', $cleanupAt), 'NO_COPY_INTAKE_NOT_ABSENT')
    && $f['pipe']->call('stats')['private_fences'] === 1 && $f['journal']->journal($plan['digest']) !== null);
unset($f);

$f = noCopyFixture(); $intake = $f['adapters']['intake']; $leaseHeld = false;
try { $intake->inventory($f['scope']['request_id']); } catch (C\Failure $error) { $leaseHeld = $error->getMessage() === 'CLOSURE_LEASE_REQUIRED'; }
checkNoCopy('intake_sdk_read_requires_actual_authoritative_closure_lease', $leaseHeld);
$binding = $f['journal']->locked($f['scope']['closure_id'], fn() => $intake->read($f['scope']['request_id']));
$intentHeld = false;
try { $f['journal']->locked($f['scope']['closure_id'], fn() => $intake->removeExact($binding)); }
catch (C\Failure $error) { $intentHeld = $error->getMessage() === 'INTAKE_PURGE_INTENT_UNVERIFIED'; }
checkNoCopy('intake_sdk_delete_cannot_precede_actual_saved_workflow_intent', $intentHeld && $f['pipe']->call('stats')['intake_deletes'] === 0);
$other = $f['closure']; $other['closure_id'] = C\syntheticUuid(99); $f['journal']->closures[$other['closure_id']] = $other;
checkNoCopy('intake_sdk_custody_rejects_another_closure_sharing_receipts', noCopyHeld($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'INTAKE_CLOSURE_IDENTITY_SHARED'));
unset($f, $intake);

$f = noCopyFixture(); $base = $f['journal']->closures;
foreach (['missing_fields' => [], 'wrong_registry_key' => $f['closure'],
    'uppercase_alias' => array_replace($f['closure'], ['closure_id' => C\syntheticUuid(99), 'event_id' => strtoupper($f['closure']['event_id'])]),
    'future_chronology' => array_replace($f['closure'], ['closure_id' => C\syntheticUuid(99), 'recorded_at_utc' => '2028-01-01T00:00:00Z'])] as $name => $other) {
    $f['journal']->closures = $base + [C\syntheticUuid(99) => $other];
    checkNoCopy('intake_sdk_' . $name . '_registry_is_unverified', noCopyHeld($f['workflow']->preview($f['closure']['closure_id'], $f['now']), 'INTAKE_CLOSURE_REGISTRY_UNVERIFIED'));
}
unset($f);

$f = noCopyFixture(); $plan = C\approved($f); $f['adapters']['intake']->loseDeleteAcknowledgement = true;
checkNoCopy('intake_sdk_lost_delete_ack_keeps_durable_intent_for_readback',
    noCopyHeld($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'INTAKE_DELETE_ACK_UNCERTAIN')
    && $f['pipe']->call('stats')['intake_deletes'] === 1 && $f['pipe']->call('stats')['rows'] === 0);
checkNoCopy('intake_sdk_lost_ack_resumes_from_actual_absence_without_second_delete',
    $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE'
    && $f['pipe']->call('stats')['intake_deletes'] === 1);
unset($f);

$f = noCopyFixture(); $plan = C\approved($f);
$f['adapters']['intake']->beforeDelete = function () use ($f) { $f['journal']->expiredUnresolved = 1; };
checkNoCopy('intake_sdk_rechecks_current_uncertainty_after_saved_intent',
    noCopyHeld($f['workflow']->execute($plan, 'synthetic-owner', $f['now']), 'RETIREMENT_CUSTODY_RECONCILIATION_REQUIRED')
    && $f['pipe']->call('stats')['intake_deletes'] === 0 && $f['pipe']->call('stats')['rows'] === 1);
$f['journal']->expiredUnresolved = 0; $f['adapters']['intake']->beforeDelete = null;
checkNoCopy('intake_sdk_verified_custody_reconciliation_resumes_exact_saved_intent',
    $f['workflow']->execute($plan, 'synthetic-owner', $f['now'])['status'] === 'COMPLETE'
    && $f['pipe']->call('stats')['intake_deletes'] === 1);
unset($f);

echo json_encode(['phase' => 'closed_retention_no_mail_copy', 'checks' => $checks,
    'receiver' => 'Exact source-derived receiver executed through local Node pipes',
    'providers' => 'Synthetic mailbox, runtime, Sheet, mail and lock doubles', 'production_authorized' => false], JSON_THROW_ON_ERROR) . "\n";
