<?php
declare(strict_types=1);
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
$GLOBALS['synthetic_retirement_environment'] = 'local';
$GLOBALS['synthetic_retirement_home'] = 'http://bsre.invalid';
function wp_get_environment_type(): string { return $GLOBALS['synthetic_retirement_environment']; }
function home_url(): string { return $GLOBALS['synthetic_retirement_home']; }
require __DIR__ . '/TestDoubles.php';
require __DIR__ . '/OwnerRetirement.php';
use BSRE\ClosedRetention as C;
use BSRE\OwnerMailReview as O;

/** Only synthetic database doubles. Exercises real core intent staging, guards, CAS and scrub. */
final class RetirementFaultJournal implements C\Journal, C\RetirementWriter
{
    public int $commits = 0;
    public int $scrubs = 0;
    public bool $loseStageAck = false;
    public bool $loseCommitAck = false;
    public bool $loseScrubAck = false;
    public ?string $loseSaveAckPhase = null;
    public $beforeCommit = null;
    public function __construct(public C\MemoryJournal $inner) {}
    public function locked(string $closureId, callable $operation) { return $this->inner->locked($closureId, $operation); }
    public function closure(string $closureId): ?array { return $this->inner->closure($closureId); }
    public function journal(string $planId): ?array { return $this->inner->journal($planId); }
    public function save(array &$record): void
    {
        $this->inner->save($record);
        if ($this->loseSaveAckPhase === $record['phase']) {
            $this->loseSaveAckPhase = null; throw new RuntimeException('PRIVATE_SAVED_PHASE_CANARY');
        }
    }
    public function markHistoryIncomplete(): void { $this->inner->markHistoryIncomplete(); }
    public function historyIncomplete(): bool { return $this->inner->historyIncomplete(); }
    public function pinAdmissionFloor(string $policyHash): void { $this->inner->pinAdmissionFloor($policyHash); }
    public function admissionFloor(): ?string { return $this->inner->admissionFloor(); }
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void { $this->inner->forget($closureId, $planId, $keepClosure); }
    public function assertRetirementOpen(): void { $this->inner->assertRetirementOpen(); }
    public function stageRetirement(array &$record, int $now): void
    {
        $this->inner->stageRetirement($record, $now);
        if ($this->loseStageAck) { $this->loseStageAck = false; throw new RuntimeException('PRIVATE_STAGE_ACK_CANARY'); }
    }
    public function assertRetirementSource(array $record, int $now): void { $this->inner->assertRetirementSource($record, $now); }
    public function commitRetirement(array $record, array $proof, int $now): void
    {
        $this->commits++;
        if ($this->beforeCommit) ($this->beforeCommit)();
        $this->inner->commitRetirement($record, $proof, $now);
        if ($this->loseCommitAck) { $this->loseCommitAck = false; throw new RuntimeException('PRIVATE_CAS_ACK_CANARY'); }
    }
    public function scrubRetirement(array $record, int $now): bool
    {
        $this->scrubs++; $value = $this->inner->scrubRetirement($record, $now);
        if ($this->loseScrubAck) { $this->loseScrubAck = false; throw new RuntimeException('PRIVATE_SCRUB_ACK_CANARY'); }
        return $value;
    }
}

/** Capability-only fake: no process, network, mail, real records, provider deletion or secret. */
final class SyntheticOwnerRetirer implements C\NoMailRetirement
{
    public ?string $digest = null;
    public int $inspects = 0;
    public int $retires = 0;
    public int $leasedCalls = 0;
    public int $cleanupCalls = 0;
    public bool $unknown = false;
    public bool $throwInspect = false;
    public bool $throwBeforeFence = false;
    public bool $loseFenceAck = false;
    public bool $fenced = false;
    public bool $forceUnretired = false;
    public ?int $created = null;
    public array $frameOverrides = [];
    public array $proofOverrides = [];
    public $afterInspect = null;
    public array $observedPhases = [];
    public function __construct(private RetirementFaultJournal $journal, private int $activatedAt) {}
    private function witnessed(array $scope, int $now): array
    {
        if ($this->digest === null) throw new RuntimeException('Synthetic intent digest required');
        $record = $this->journal->journal($this->digest);
        if ($record === null) throw new RuntimeException('Source called without authoritative intent');
        C\RetirementIntent::validateRecord($record, $now);
        if ($record['revision'] < 1 || $record['plan']['scope'] !== $scope) throw new RuntimeException('Synthetic intent scope mismatch');
        $this->observedPhases[] = $record['phase'];
        try { $this->journal->locked($scope['closure_id'], fn() => null); }
        catch (RuntimeException $error) { $this->leasedCalls++; }
        return $record;
    }
    private function store(array $scope): array
    {
        return ['contract' => C\NoMailCopyProof::CONTRACT, 'namespace' => 'SYNTHETIC_BSRE_NO_COPY',
            'epoch' => str_repeat('e', 64), 'revision' => 2, 'pruned_through' => 0, 'generation' => str_repeat('a', 64),
            'activated_at' => $this->activatedAt, 'audience' => str_repeat('b', 64), 'admission_hash' => $scope['admission_hash'],
            'source_hash' => str_repeat('d', 64), 'restore_policy_hash' => str_repeat('f', 64)];
    }
    private function mailbox(array $scope, int $now): array
    {
        return ['scope_hash' => C\Workflow::digest($scope), 'mailbox' => 'marketing@blackswanrealestate.ae', 'result' => 'ABSENT',
            'complete' => true, 'includes_trash' => true, 'observed_at' => $now, 'expires_at' => $now + 300,
            'evidence_reference' => 'SYNTHETIC_COMPLETE_MAILBOX_ONLY', 'evidence_hash' => str_repeat('a', 64)];
    }
    private function proof(array $scope, int $now): array
    {
        $store = $this->store($scope);
        return array_replace(['schema_version' => 1, 'scope' => $scope, 'scope_hash' => C\Workflow::digest($scope),
            'owner_intent_digest' => $this->digest,
            'fence_hash' => str_repeat('9', 64), 'epoch' => $store['epoch'], 'fence_revision' => 2,
            'source_hash' => $store['source_hash'], 'restore_policy_hash' => $store['restore_policy_hash'],
            'fence_created_at' => $this->created, 'fence_expires_at' => $this->created + C\NoMailCopyProof::RECOVERY,
            'row_state' => 'RETIRED', 'mailbox' => $this->mailbox($scope, $now), 'observed_at' => $now, 'expires_at' => $now + 300,
            'recovery' => ['contract' => 'bsre-retention-admission-v1', 'window_seconds' => C\NoMailCopyProof::RECOVERY,
                'restore_fenced' => true, 'backups_expired_through' => 0], 'current_store' => $store,
            'external_floor_hash' => C\Workflow::digest($store), 'cleanup_receipt' => null], $this->proofOverrides);
    }
    public function inspect(array $scope, int $now): ?array
    {
        $this->inspects++; $this->witnessed($scope, $now);
        if ($this->throwInspect) throw new RuntimeException('PRIVATE_INSPECTION_CANARY');
        if ($this->unknown) return null;
        if ($this->fenced && !$this->forceUnretired) {
            $value = ['contract' => C\NoMailRetirementProof::CONTRACT, 'scope_hash' => C\Workflow::digest($scope),
                'state' => 'RETIRED', 'proof' => $this->proof($scope, $now)];
        } else {
            $store = $this->store($scope);
            $value = array_replace(['contract' => C\NoMailRetirementProof::CONTRACT, 'scope_hash' => C\Workflow::digest($scope),
                'state' => 'UNRETIRED', 'current_store' => $store, 'source_hash' => $store['source_hash'],
                'restore_policy_hash' => $store['restore_policy_hash'], 'external_floor_hash' => C\Workflow::digest($store),
                'mailbox' => $this->mailbox($scope, $now), 'row_status' => 'QUEUED', 'attempt_count' => 0,
                'send_started_at' => '', 'sent_at' => '', 'observed_at' => $now, 'expires_at' => $now + 300], $this->frameOverrides);
        }
        if ($this->afterInspect) ($this->afterInspect)();
        return $value;
    }
    public function retire(array $scope, array $record, int $now): ?array
    {
        $this->retires++; $stored = $this->witnessed($scope, $now);
        if ($stored !== $record || $now >= $record['plan']['expires_at']) throw new RuntimeException('Synthetic authority invalid');
        if ($this->throwBeforeFence) throw new RuntimeException('PRIVATE_BEFORE_FENCE_CANARY');
        $this->fenced = true; $this->created ??= $now;
        if ($this->loseFenceAck) { $this->loseFenceAck = false; throw new RuntimeException('PRIVATE_FENCE_ACK_CANARY'); }
        return $this->proof($scope, $now);
    }
    public function readback(array $scope, int $now, bool $cleanup = false, ?array $ticket = null): ?array
    {
        return $this->fenced ? $this->proof($scope, $now) : null;
    }
    public function prepareCleanup(array $scope, int $now): ?array { $this->cleanupCalls++; throw new RuntimeException('Unexpected cleanup capability'); }
    public function forget(array $scope, int $now, array $ticket): bool { $this->cleanupCalls++; throw new RuntimeException('Unexpected cleanup capability'); }
}

function retirementFixture(): array
{
    $f = C\fixture(); $f['closure']['email_status'] = 'QUEUED'; $f['closure']['mail_message_ids'] = [];
    $f['journal']->closures[$f['closure']['closure_id']] = $f['closure']; $f['adapters']['email']->rows = [];
    $journal = new RetirementFaultJournal($f['journal']); $store = new O\MemoryStore(); $session = new O\SyntheticSession();
    $authority = new O\ReviewAuthority($store, $session);
    $workflow = new C\Workflow($journal, $f['adapters'], $authority, $f['admission']);
    $retirer = new SyntheticOwnerRetirer($journal, $f['now'] - 1000);
    $controller = new O\OwnerRetirementController($workflow, $journal, $store, $session, $retirer);
    return array_merge($f, compact('journal', 'store', 'session', 'authority', 'workflow', 'retirer', 'controller'));
}
function retirementForm(O\OwnerRetirementController $controller, array $view, string $operation): array
{
    preg_match_all('/<form method="post">(.*?)<\/form>/s', $controller->render($view), $forms);
    foreach ($forms[1] as $body) {
        preg_match_all('/<input type="hidden" name="([^"]+)" value="([^"]*)">/', $body, $inputs, PREG_SET_ORDER);
        $values = [];
        foreach ($inputs as $input) $values[html_entity_decode($input[1], ENT_QUOTES, 'UTF-8')] = html_entity_decode($input[2], ENT_QUOTES, 'UTF-8');
        if (($values['operation'] ?? '') === $operation) return $values;
    }
    throw new RuntimeException('Synthetic retirement form unavailable');
}
function retirementPrepare(array $f): array
{
    $input = retirementForm($f['controller'], $f['controller']->handle('GET', [], $f['now']), 'prepare');
    $view = $f['controller']->handle('POST', $input + ['closure_id' => $f['closure']['closure_id']], $f['now']);
    $f['retirer']->digest = $view['job']['plan']['digest'];
    return $view;
}
function retirementApprove(array $f, array $view, ?int $now = null): array
{
    return $f['controller']->handle('POST', retirementForm($f['controller'], $view, 'approve'), $now ?? $f['now']);
}
function retirementReview(array $f, string $digest, int $now): array
{
    $input = retirementForm($f['controller'], $f['controller']->handle('GET', [], $now), 'review_intent');
    return $f['controller']->handle('POST', $input + ['intent_digest' => $digest], $now);
}
function retirementRecover(array $f, array $view, int $now): array
{
    return $f['controller']->handle('POST', retirementForm($f['controller'], $view, 'recover'), $now);
}
$checks = [];
function retirementCheck(string $name, bool $passed): void
{
    global $checks;
    if (!$passed) throw new RuntimeException('Owner retirement check failed: ' . $name);
    $checks[$name] = true;
}
function retirementReject(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure|C\Failure $error) { return $error->getMessage() === $code; }
}
function retirementHeld(array $view, string $code): bool { return $view['status'] === 'HELD' && in_array($code, $view['hold_codes'], true); }

$f = retirementFixture(); $initial = $f['controller']->handle('GET', [], $f['now']);
retirementCheck('get_is_read_only_and_never_inspects_source', $initial['status'] === 'READY' && $f['store']->jobs === []
    && $f['journal']->inner->journals === [] && $f['retirer']->inspects === 0);
retirementCheck('mismatched_workflow_and_authoritative_journal_are_rejected', retirementReject(fn() => new O\OwnerRetirementController($f['workflow'], new RetirementFaultJournal(new C\MemoryJournal()), $f['store'], $f['session']), 'RETIREMENT_JOURNAL_MISMATCH'));
$f['session']->allowed = false; $reads = $f['store']->reads;
retirementCheck('authentication_precedes_private_storage', retirementReject(fn() => $f['controller']->handle('GET', ['job' => str_repeat('0', 64)], $f['now']), 'OWNER_SESSION_REQUIRED') && $reads === $f['store']->reads);
$f['session']->allowed = true;
$prepareInput = retirementForm($f['controller'], $initial, 'prepare') + ['closure_id' => $f['closure']['closure_id']];
retirementCheck('caller_cannot_upload_a_target_or_authority', retirementReject(fn() => $f['controller']->handle('POST', $prepareInput + ['after' => $f['closure']], $f['now']), 'INPUT_SCHEMA_INVALID'));
$review = retirementPrepare($f); $plan = $review['job']['plan'];
retirementCheck('prepare_has_no_authoritative_intent_or_source_call', $f['journal']->inner->journals === []
    && $f['retirer']->inspects === 0 && $f['retirer']->retires === 0 && $review['job']['approved_at'] === null);
$expected = $f['closure']; $expected['revision']++; $expected['email_status'] = 'RETIRED_NO_COPY';
retirementCheck('target_preserves_all_business_evidence_dates_and_identifiers', $plan['after'] === $expected
    && $plan['after']['reviewer'] === $plan['before']['reviewer'] && $plan['after']['recorded_at_utc'] === $plan['before']['recorded_at_utc']);
retirementCheck('scope_binds_target_revision_hash_and_actual_intake_fingerprint', $plan['scope'] === C\NoMailCopyProof::scope($expected, $plan['admission_hash'], $f['adapters']['intake']->rows['synthetic-intake']['fingerprint']));
retirementCheck('review_window_is_fixed_fifteen_minutes', $plan['expires_at'] === $plan['created_at'] + 900 && $plan['closure_id'] === $plan['before']['closure_id']);
$input = retirementForm($f['controller'], $review, 'approve'); $input['nonce'] = 'invalid';
retirementCheck('invalid_nonce_cannot_stage_authoritative_intent', retirementReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED') && $f['journal']->inner->journals === []);
$input = retirementForm($f['controller'], $review, 'approve'); $input['plan_digest'] = str_repeat('f', 64);
retirementCheck('approval_nonce_is_exact_digest_bound', retirementReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$f['session']->identity = 'another-synthetic-owner';
retirementCheck('another_owner_cannot_read_review_or_render_cached_plan', retirementReject(fn() => $f['controller']->handle('GET', ['job' => $review['job']['id']], $f['now']), 'REVIEW_NOT_FOUND')
    && retirementReject(fn() => $f['controller']->render($review), 'RETIREMENT_OWNER_REQUIRED'));
$f['session']->identity = 'synthetic-owner';
$input = retirementForm($f['controller'], $review, 'approve'); $f['session']->token = 'synthetic-new-session';
retirementCheck('replaced_session_invalidates_old_nonce', retirementReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));

$g = retirementFixture(); $r = retirementPrepare($g);
$default = new O\OwnerRetirementController($g['workflow'], $g['journal'], $g['store'], $g['session']);
$held = $default->handle('POST', retirementForm($default, $r, 'approve'), $g['now']);
retirementCheck('default_unverified_source_holds_after_durable_owner_intent', retirementHeld($held, 'RETIREMENT_INSPECTION_UNVERIFIED')
    && $g['journal']->journal($r['job']['plan']['digest'])['phase'] === 'INTENT_RECORDED'
    && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);
$g = retirementFixture(); $g['journal']->inner->closures[$g['closure']['closure_id']]['closed_at_utc'] = gmdate('Y-m-d\TH:i:s\Z', $g['now'] - 3600);
$g['journal']->inner->closures[$g['closure']['closure_id']]['recorded_at_utc'] = gmdate('Y-m-d\TH:i:s\Z', $g['now']);
retirementCheck('recent_closure_is_not_retirement_due', retirementReject(fn() => retirementPrepare($g), 'RETENTION_NOT_DUE'));
$g = retirementFixture(); $g['journal']->inner->closures[$g['closure']['closure_id']]['email_status'] = 'SENT';
retirementCheck('sent_closure_cannot_be_coerced_to_never_sent', retirementReject(fn() => retirementPrepare($g), 'RETIREMENT_TARGET_INVALID'));
$g = retirementFixture(); $g['adapters']['intake']->rows['synthetic-intake']['request_ids'][] = C\syntheticUuid(99);
retirementCheck('shared_intake_binding_holds_before_any_source_call', retirementReject(fn() => retirementPrepare($g), 'SHARED_RESOURCE_REQUIRES_REVIEW') && $g['retirer']->inspects === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['journal']->inner->closures[$g['closure']['closure_id']]['evidence_hash'] = str_repeat('f', 64);
$changed = retirementApprove($g, $r);
retirementCheck('changed_closure_cannot_stage_or_call_source', $changed['intent'] === null && $g['journal']->inner->journals === [] && $g['retirer']->inspects === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['adapters']['intake']->rows['synthetic-intake']['fingerprint'] = str_repeat('8', 64);
retirementCheck('changed_inventory_cannot_stage_or_call_source', retirementApprove($g, $r)['intent'] === null && $g['retirer']->inspects === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['admission']->value['expires_at'] = $g['now'];
retirementCheck('stale_admission_cannot_stage_or_call_source', retirementApprove($g, $r)['intent'] === null && $g['retirer']->inspects === 0);

$g = retirementFixture(); $r = retirementPrepare($g); $atCas = false;
$g['journal']->beforeCommit = function () use ($g, $r, &$atCas) {
    $saved = $g['journal']->journal($r['job']['plan']['digest']);
    $atCas = $saved['phase'] === 'FENCE_CONFIRMED' && is_string($saved['proof_hash']);
};
$done = retirementApprove($g, $r); $digest = $r['job']['plan']['digest'];
retirementCheck('authoritative_intent_precedes_every_source_call_under_closure_lease', $g['retirer']->observedPhases === ['INTENT_RECORDED', 'INTENT_RECORDED']
    && $g['retirer']->leasedCalls === $g['retirer']->inspects + $g['retirer']->retires);
retirementCheck('verified_fence_is_durable_before_closure_cas', $atCas && $done['intent']['phase'] === 'RETIREMENT_RECORDED'
    && $g['journal']->closure($g['closure']['closure_id']) === $r['job']['plan']['after']);
retirementCheck('retirement_does_not_mutate_outputs_history_or_purge', array_sum(array_map(fn($adapter) => $adapter->deletes, $g['adapters'])) === 0
    && $g['journal']->historyIncomplete() === false && $g['retirer']->cleanupCalls === 0);
$g['authority']->select($r['job']['id']);
retirementCheck('retirement_owner_approval_is_not_purge_authority', !$g['authority']->canApply($g['session']->actor(), $digest, $g['now'], 'PURGE'));
$replay = retirementRecover($g, $done, $g['now']);
retirementCheck('recorded_replay_only_inspects_existing_fence_without_new_revision', $replay['status'] === 'RETIREMENT_RECORDED'
    && $g['retirer']->retires === 1 && $g['journal']->closure($g['closure']['closure_id'])['revision'] === 2);
$g['store']->jobs = []; $privateReview = retirementReview($g, $digest, $g['now']);
retirementCheck('authoritative_recovery_survives_ui_cache_pruning', $privateReview['intent']['plan']['digest'] === $digest
    && retirementRecover($g, $privateReview, $g['now'])['status'] === 'RETIREMENT_RECORDED' && $g['store']->jobs === []);
$input = retirementForm($g['controller'], $privateReview, 'recover'); $input['intent_digest'] = str_repeat('f', 64);
retirementCheck('recovery_nonce_rejects_changed_authoritative_digest', retirementReject(fn() => $g['controller']->handle('POST', $input, $g['now']), 'CSRF_REJECTED'));
$g['session']->identity = 'another-synthetic-owner';
retirementCheck('authoritative_recovery_enforces_original_owner', retirementReject(fn() => retirementReview($g, $digest, $g['now']), 'RETIREMENT_OWNER_REQUIRED'));
$g['session']->identity = 'synthetic-owner';

foreach (['stage' => 'loseStageAck', 'fence' => 'loseFenceAck', 'cas' => 'loseCommitAck'] as $point => $property) {
    $g = retirementFixture(); $r = retirementPrepare($g);
    if ($point === 'fence') $g['retirer']->$property = true; else $g['journal']->$property = true;
    $uncertain = retirementApprove($g, $r); $digest = $r['job']['plan']['digest'];
    retirementCheck($point . '_ack_loss_keeps_authoritative_intent_and_bounds_error', $g['journal']->journal($digest) !== null
        && $uncertain['status'] === 'HELD' && !str_contains(json_encode($uncertain), 'PRIVATE_'));
    if ($point === 'stage') retirementCheck('ambiguous_stage_does_not_call_source_before_reread', $g['retirer']->inspects === 0 && $g['retirer']->retires === 0);
    $g['store']->jobs = []; $when = $g['now'] + ($point === 'stage' ? 1 : 901); $g['admission']->refresh($when);
    $recovered = retirementRecover($g, retirementReview($g, $digest, $when), $when);
    retirementCheck($point . '_ack_loss_recovers_exact_intent_without_new_fence_or_revision', $recovered['status'] === 'RETIREMENT_RECORDED'
        && $g['retirer']->retires === 1 && $g['journal']->closure($g['closure']['closure_id'])['revision'] === 2);
}
$g = retirementFixture(); $r = retirementPrepare($g); $g['journal']->loseSaveAckPhase = 'FENCE_CONFIRMED';
$held = retirementApprove($g, $r);
retirementCheck('ambiguous_proof_save_preserves_pinned_hash_before_any_cas', $held['status'] === 'HELD'
    && $g['journal']->journal($r['job']['plan']['digest'])['phase'] === 'FENCE_CONFIRMED' && $g['journal']->commits === 0);
retirementCheck('proof_save_recovery_never_retires_twice', retirementRecover($g, $held, $g['now'])['status'] === 'RETIREMENT_RECORDED' && $g['retirer']->retires === 1);

foreach ([
    'absent' => ['row_state' => 'ABSENT'], 'predated' => ['fence_created_at' => 1, 'fence_expires_at' => 1 + C\NoMailCopyProof::RECOVERY],
    'changed_scope' => ['scope_hash' => str_repeat('0', 64)],
    'wrong_owner_intent' => ['owner_intent_digest' => str_repeat('f', 64)],
] as $case => $overrides) {
    $g = retirementFixture(); $r = retirementPrepare($g); $g['retirer']->proofOverrides = $overrides;
    $blocked = retirementApprove($g, $r);
    retirementCheck($case . '_source_proof_cannot_commit_retirement_target', $blocked['status'] === 'HELD'
        && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);
}
$g = retirementFixture(); $r = retirementPrepare($g); $g['retirer']->frameOverrides['attempt_count'] = 1;
retirementCheck('attempted_row_cannot_be_positive_unretired_clearance', retirementHeld(retirementApprove($g, $r), 'RETIREMENT_OUTBOX_UNVERIFIED') && $g['retirer']->retires === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['retirer']->unknown = true;
retirementCheck('unknown_inspection_never_becomes_unretired', retirementHeld(retirementApprove($g, $r), 'RETIREMENT_INSPECTION_UNVERIFIED') && $g['retirer']->retires === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['retirer']->throwInspect = true;
retirementCheck('inspection_exception_is_bounded_without_source_write', retirementHeld(retirementApprove($g, $r), 'RETIREMENT_SOURCE_UNCERTAIN') && $g['retirer']->retires === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['retirer']->throwBeforeFence = true;
$held = retirementApprove($g, $r); $g['retirer']->throwBeforeFence = false;
$when = $g['now'] + 901; $g['admission']->refresh($when);
$late = retirementRecover($g, retirementReview($g, $r['job']['plan']['digest'], $when), $when);
retirementCheck('unretired_old_intent_cannot_create_a_new_fence_after_review_expiry', retirementHeld($late, 'PLAN_EXPIRED')
    && $g['retirer']->retires === 1 && $g['retirer']->fenced === false && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);
$g = retirementFixture(); $r = retirementPrepare($g); $done = retirementApprove($g, $r); $g['retirer']->forceUnretired = true;
retirementCheck('previously_confirmed_fence_cannot_be_recreated_from_unretired_state', retirementHeld(retirementRecover($g, $done, $g['now']), 'RETIREMENT_FENCE_STATE_CONFLICT') && $g['retirer']->retires === 1);
$g = retirementFixture(); $r = retirementPrepare($g);
retirementCheck('expired_unapproved_review_cannot_stage_any_intent', retirementReject(fn() => retirementApprove($g, $r, $g['now'] + 900), 'REVIEW_NOT_FOUND')
    && $g['journal']->inner->journals === [] && $g['retirer']->inspects === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $g['journal']->inner->journals['synthetic-unknown'] = ['plan' => []];
$blocked = retirementApprove($g, $r);
retirementCheck('unknown_journal_job_blocks_before_any_sender_call', $g['retirer']->inspects === 0 && $g['retirer']->retires === 0
    && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);
$g = retirementFixture(); $first = retirementPrepare($g);
$input = retirementForm($g['controller'], $g['controller']->handle('GET', [], $g['now'] + 1), 'prepare') + ['closure_id' => $g['closure']['closure_id']];
$second = $g['controller']->handle('POST', $input, $g['now'] + 1);
$g['retirer']->unknown = true; retirementApprove($g, $first); $sourceBefore = $g['retirer']->inspects;
$g['retirer']->digest = $second['job']['plan']['digest']; $conflict = retirementApprove($g, $second, $g['now'] + 1);
retirementCheck('competing_valid_intent_cannot_be_staged_or_strand_the_first_fence', $g['journal']->journal($second['job']['plan']['digest']) === null
    && $g['retirer']->inspects === $sourceBefore && $g['retirer']->retires === 0
    && $g['journal']->journal($first['job']['plan']['digest'])['phase'] === 'INTENT_RECORDED');
$g = retirementFixture(); $r = retirementPrepare($g);
$g['retirer']->afterInspect = function () use ($g) { $g['journal']->inner->journals['synthetic-late-unknown'] = ['plan' => []]; };
$blocked = retirementApprove($g, $r);
retirementCheck('new_conflicting_job_after_inspection_blocks_source_write', $blocked['status'] === 'HELD' && $g['retirer']->retires === 0
    && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);
$g = retirementFixture(); $r = retirementPrepare($g);
$g['retirer']->afterInspect = function () use ($g) { $g['session']->allowed = false; };
retirementCheck('logout_during_inspection_blocks_source_write_and_cas', retirementReject(fn() => retirementApprove($g, $r), 'OWNER_SESSION_REQUIRED')
    && $g['retirer']->retires === 0 && $g['journal']->commits === 0);
$g = retirementFixture(); $r = retirementPrepare($g);
$g['retirer']->afterInspect = function () use ($g) { $g['journal']->inner->expiredUnresolved = 1; };
$blocked = retirementApprove($g, $r);
retirementCheck('new_global_unresolved_marker_after_inspection_blocks_source_write', $blocked['status'] === 'HELD' && $g['retirer']->retires === 0);
$g = retirementFixture(); $r = retirementPrepare($g); $done = retirementApprove($g, $r);
$g['retirer']->proofOverrides['fence_hash'] = str_repeat('0', 64);
retirementCheck('pinned_fence_hash_cannot_be_replaced_during_recovery', retirementHeld(retirementRecover($g, $done, $g['now']), 'RETIREMENT_FENCE_CHANGED')
    && $g['retirer']->retires === 1 && $g['journal']->closure($g['closure']['closure_id']) === $r['job']['plan']['after']);

$g = retirementFixture(); $r = retirementPrepare($g); $done = retirementApprove($g, $r); $digest = $r['job']['plan']['digest'];
$before = $g['journal']->closure($g['closure']['closure_id']); $sourceCalls = $g['retirer']->inspects + $g['retirer']->retires;
$early = $g['controller']->handle('POST', retirementForm($g['controller'], $done, 'expire'), $g['now']);
retirementCheck('early_expiry_holds_without_source_or_scrub', retirementHeld($early, 'RECOVERY_WINDOW_ACTIVE') && $g['journal']->scrubs === 0);
$when = $done['intent']['recovery_until'];
$expiredRecovery = retirementRecover($g, retirementReview($g, $digest, $when), $when);
retirementCheck('thirty_day_recovery_boundary_never_calls_source', retirementHeld($expiredRecovery, 'RECOVERY_WINDOW_EXPIRED')
    && $sourceCalls === $g['retirer']->inspects + $g['retirer']->retires);
$g['journal']->loseScrubAck = true;
$expired = $g['controller']->handle('POST', retirementForm($g['controller'], $done, 'expire'), $when);
retirementCheck('expiry_scrubs_only_intent_and_resolves_lost_commit_ack', $expired['intent'] === null && $expired['manual_reconciliation_required'] === true
    && $expired['source_fence_modified'] === false && $expired['provider_completion_verified'] === false
    && $g['journal']->journal($digest) === null && $g['journal']->closure($g['closure']['closure_id']) === $before
    && $g['retirer']->fenced === true && $g['retirer']->cleanupCalls === 0);
$counter = $g['journal']->inner->expiredUnresolved;
$again = $g['controller']->handle('POST', retirementForm($g['controller'], $done, 'expire'), $when);
retirementCheck('repeated_expiry_does_not_repeat_scrub_or_unresolved_counter', $again['status'] === 'NO_PRIVATE_RETIREMENT_INTENT'
    && $g['journal']->inner->expiredUnresolved === $counter && $g['journal']->scrubs === 1 && $counter === 1);
$blockedNew = false;
try { retirementPrepare($g); } catch (C\Failure $error) { $blockedNew = true; }
retirementCheck('nonidentifying_unresolved_marker_blocks_new_retirement', $blockedNew && $sourceCalls === $g['retirer']->inspects + $g['retirer']->retires);

$g = retirementFixture(); $r = retirementPrepare($g); $done = retirementApprove($g, $r);
unset($g['journal']->inner->closures[$g['closure']['closure_id']]); // Models a separately accepted later purge, not a controller action.
$when = $done['intent']['recovery_until'];
$scrubbed = $g['controller']->handle('POST', retirementForm($g['controller'], $done, 'expire'), $when);
retirementCheck('duplicate_intent_expiry_preserves_existing_authoritative_closure_absence', $scrubbed['status'] === 'PRIVATE_RETIREMENT_INTENT_EXPIRED'
    && $g['journal']->closure($g['closure']['closure_id']) === null && $g['retirer']->retires === 1 && $g['retirer']->cleanupCalls === 0);

$GLOBALS['synthetic_retirement_environment'] = 'production';
retirementCheck('production_environment_cannot_use_controller', retirementReject(fn() => $g['controller']->handle('GET', [], $g['now']), 'ISOLATED_LAB_ONLY'));
$GLOBALS['synthetic_retirement_environment'] = 'local'; $GLOBALS['synthetic_retirement_home'] = 'https://example.invalid';
retirementCheck('foreign_host_cannot_use_controller', retirementReject(fn() => $g['controller']->handle('GET', [], $g['now']), 'ISOLATED_LAB_ONLY'));
$GLOBALS['synthetic_retirement_home'] = 'http://bsre.invalid';

echo json_encode(['phase' => 'synthetic_owner_no_mail_retirement', 'checks' => count($checks), 'passed' => array_keys($checks),
    'receiver' => 'Synthetic positive inspection and fence proof only; no live provider',
    'custody' => 'Actual core MemoryJournal contracts through injected acknowledgement faults', 'production_authorized' => false],
    JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n";
