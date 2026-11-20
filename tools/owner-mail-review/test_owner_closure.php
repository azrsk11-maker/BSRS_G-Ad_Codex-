<?php
declare(strict_types=1);
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
$GLOBALS['synthetic_closure_environment'] = 'local';
$GLOBALS['synthetic_closure_home'] = 'http://bsre.invalid';
function wp_get_environment_type(): string { return $GLOBALS['synthetic_closure_environment']; }
function home_url(): string { return $GLOBALS['synthetic_closure_home']; }
require __DIR__ . '/TestDoubles.php';
require __DIR__ . '/OwnerClosure.php';
use BSRE\ClosedRetention as C;
use BSRE\OwnerMailReview as O;

/** Explicit synthetic observations; no sender, private business record or live authority. */
final class SyntheticClosureSafety implements O\ClosureEditReadback
{
    public array $overrides = [];
    public bool $unknown = false;
    public bool $throw = false;
    public int $reads = 0;
    public int $leasedReads = 0;
    public $afterRead = null;
    public function __construct(private C\Journal $journal) {}
    public function readback(array $closure, int $now): ?array
    {
        $this->reads++;
        try { $this->journal->locked($closure['closure_id'], fn() => null); }
        catch (RuntimeException $error) { $this->leasedReads++; }
        if ($this->throw) throw new RuntimeException('PRIVATE_SAFETY_CANARY');
        if ($this->unknown) return null;
        $value = array_replace(['contract' => O\OwnerClosureController::SAFETY, 'closure_hash' => C\Workflow::digest($closure),
            'sender_fence' => 'NONE', 'retirement_intent' => 'NONE', 'authoritative' => true,
            'observed_at' => $now, 'expires_at' => $now + 300, 'evidence_reference' => 'SYNTHETIC_SENDER_AND_RETIREMENT_READBACK',
            'evidence_hash' => str_repeat('b', 64)], $this->overrides);
        if ($this->afterRead) ($this->afterRead)();
        return $value;
    }
}

/** Simulates acknowledgement failure around the actual lease-required MemoryJournal writer. */
final class ClosureFaultJournal implements C\Journal, C\ClosureWriter
{
    public int $writes = 0;
    public bool $failBefore = false;
    public bool $loseAcknowledgement = false;
    public $beforeWrite = null;
    public function __construct(public C\MemoryJournal $inner) {}
    public function locked(string $closureId, callable $operation) { return $this->inner->locked($closureId, $operation); }
    public function closure(string $closureId): ?array { return $this->inner->closure($closureId); }
    public function journal(string $planId): ?array { return $this->inner->journal($planId); }
    public function save(array &$record): void { $this->inner->save($record); }
    public function markHistoryIncomplete(): void { $this->inner->markHistoryIncomplete(); }
    public function historyIncomplete(): bool { return $this->inner->historyIncomplete(); }
    public function pinAdmissionFloor(string $policyHash): void { $this->inner->pinAdmissionFloor($policyHash); }
    public function admissionFloor(): ?string { return $this->inner->admissionFloor(); }
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void { $this->inner->forget($closureId, $planId, $keepClosure); }
    public function replaceClosure(array $before, array $after): void
    {
        $this->writes++;
        if ($this->beforeWrite) ($this->beforeWrite)();
        if ($this->failBefore) throw new RuntimeException('PRIVATE_WRITE_CANARY');
        $this->inner->replaceClosure($before, $after);
        if ($this->loseAcknowledgement) { $this->loseAcknowledgement = false; throw new RuntimeException('PRIVATE_COMMITTED_ACK_CANARY'); }
    }
}

function closureFixture(): array
{
    $f = C\fixture(); $journal = new ClosureFaultJournal($f['journal']);
    $store = new O\MemoryStore(); $session = new O\SyntheticSession(); $safety = new SyntheticClosureSafety($journal);
    $controller = new O\OwnerClosureController($journal, $store, $session, $safety);
    return array_merge($f, compact('journal', 'store', 'session', 'safety', 'controller'));
}
function closureForm(O\OwnerClosureController $controller, array $view, string $operation): array
{
    preg_match_all('/<form method="post">(.*?)<\/form>/s', $controller->render($view), $forms);
    foreach ($forms[1] as $body) {
        preg_match_all('/<input type="hidden" name="([^"]+)" value="([^"]*)">/', $body, $inputs, PREG_SET_ORDER);
        $values = [];
        foreach ($inputs as $input) $values[html_entity_decode($input[1], ENT_QUOTES, 'UTF-8')] = html_entity_decode($input[2], ENT_QUOTES, 'UTF-8');
        if (($values['operation'] ?? '') === $operation) return $values;
    }
    throw new RuntimeException('Synthetic closure form unavailable');
}
function closureInput(array $f, array $changes = []): array
{
    return array_replace(closureForm($f['controller'], ['status' => 'READY', 'job' => null], 'prepare') + [
        'closure_id' => $f['closure']['closure_id'], 'status' => 'CLOSED', 'closed_at_utc' => gmdate('Y-m-d\TH:i:s\Z', $f['now'] - 3600),
        'evidence_reference' => 'SYNTHETIC_OWNER_CLOSURE_EVIDENCE', 'evidence_hash' => str_repeat('a', 64)], $changes);
}
function closurePrepare(array $f, array $changes = []): array { return $f['controller']->handle('POST', closureInput($f, $changes), $f['now']); }
function closureApprove(array $f, array $review, ?int $now = null): array
{
    return $f['controller']->handle('POST', closureForm($f['controller'], $review, 'approve'), $now ?? $f['now']);
}
$checks = [];
function closureCheck(string $name, bool $passed): void
{
    global $checks;
    if (!$passed) throw new RuntimeException('Owner closure check failed: ' . $name);
    $checks[$name] = true;
}
function closureReject(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure|C\Failure $error) { return $error->getMessage() === $code; }
}
function closureHeld(array $view, string $code): bool
{
    return $view['status'] === 'HELD' && in_array($code, $view['hold_codes'], true);
}

$f = closureFixture(); $f['store']->jobs['synthetic-expired-cache'] = ['cleanup_after' => $f['now'] - 1];
$before = $f['journal']->closure($f['closure']['closure_id']);
closureCheck('get_is_read_only_including_expired_cache', $f['controller']->handle('GET', [], $f['now']) === ['status' => 'READY', 'job' => null]
    && isset($f['store']->jobs['synthetic-expired-cache']) && $f['journal']->closure($f['closure']['closure_id']) === $before);
$f['session']->allowed = false; $reads = $f['store']->reads;
closureCheck('unauthenticated_get_precedes_storage_and_cleanup', closureReject(fn() => $f['controller']->handle('GET', ['job' => str_repeat('0', 64)], $f['now']), 'OWNER_SESSION_REQUIRED')
    && $f['store']->reads === $reads && isset($f['store']->jobs['synthetic-expired-cache']));
$f['session']->allowed = true;
$unverified = new O\OwnerClosureController($f['journal'], $f['store'], $f['session']);
closureCheck('default_safety_is_unverified', closureReject(fn() => $unverified->handle('POST', closureInput($f), $f['now']), 'CLOSURE_EDIT_SAFETY_UNVERIFIED'));
closureCheck('missing_authoritative_baseline_never_creates_a_row', closureReject(fn() => $f['controller']->handle('POST', closureInput($f, ['closure_id' => C\syntheticUuid(99)]), $f['now']), 'CLOSURE_BASELINE_REQUIRED')
    && count($f['journal']->inner->closures) === 1);
foreach (['reviewer', 'revision', 'accepted_at_utc', 'request_id', 'outcome_ids', 'authoritative'] as $field) {
    closureCheck('caller_' . $field . '_is_rejected', closureReject(fn() => $f['controller']->handle('POST', closureInput($f) + [$field => 'forbidden'], $f['now']), 'INPUT_SCHEMA_INVALID'));
}
$review = closurePrepare($f); $plan = $review['job']['plan'];
closureCheck('preparation_never_changes_authoritative_closure', $f['journal']->writes === 0 && $f['journal']->closure($f['closure']['closure_id']) === $before
    && $review['job']['approved_at'] === null && $review['job']['manifest'] === null);
closureCheck('review_has_distinct_contract_and_exact_fifteen_minute_window', $plan['contract'] === O\OwnerClosureController::CONTRACT
    && $plan['expires_at'] === $plan['created_at'] + 900 && preg_match('/^[a-f0-9]{64}$/D', $review['job']['id']) === 1);
$after = $plan['after']; $immutable = $before;
foreach (['status', 'closed_at_utc', 'evidence_reference', 'evidence_hash', 'reviewer', 'recorded_at_utc', 'revision'] as $field) unset($immutable[$field]);
closureCheck('all_identity_and_association_fields_are_preserved', array_intersect_key($after, $immutable) === $immutable);
closureCheck('reviewer_revision_and_recording_time_are_server_owned', $after['reviewer'] === $f['session']->actor()
    && $after['revision'] === $before['revision'] + 1 && $after['recorded_at_utc'] === gmdate('Y-m-d\TH:i:s\Z', $f['now']));
closureCheck('recent_closure_is_editable_without_retirement_due_status', closureReject(fn() => C\Workflow::validateClosureRecord($after, $f['now'], true), 'RETENTION_NOT_DUE'));
closureCheck('safety_observation_is_bound_under_actual_closure_lease', $f['safety']->reads === $f['safety']->leasedReads && $f['safety']->reads > 0);
foreach ([['closed_at_utc' => '2024-01-01T00:00:00Z'], ['closed_at_utc' => gmdate('Y-m-d\TH:i:s\Z', $f['now'] + 1)]] as $changes) {
    closureCheck('invalid_closure_chronology_' . count($checks), closureReject(fn() => closurePrepare($f, $changes), 'CLOSURE_TIME_INVALID'));
}
closureCheck('open_status_requires_null_closure_timestamp', closureReject(fn() => closurePrepare($f, ['status' => 'OPEN']), 'CLOSURE_INVALID'));
$open = closurePrepare($f, ['status' => 'OPEN', 'closed_at_utc' => '']);
closureCheck('explicit_open_amendment_preserves_identities', $open['job']['plan']['after']['closed_at_utc'] === null
    && $open['job']['plan']['after']['request_id'] === $before['request_id']);
$htmlReview = closurePrepare($f, ['evidence_reference' => '<script>synthetic-only</script>']);
$html = $f['controller']->render($htmlReview);
closureCheck('private_renderer_escapes_evidence_and_contains_no_external_resources', str_contains($html, '&lt;script&gt;synthetic-only&lt;/script&gt;')
    && !str_contains($html, '<script>') && str_contains($html, 'aria-label="Exact private closure amendment"') && !str_contains($html, 'src='));
$input = closureForm($f['controller'], $review, 'approve'); $input['nonce'] = 'invalid';
closureCheck('csrf_rejection_cannot_record_approval', closureReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED')
    && $f['store']->jobs[$review['job']['id']]['approved_at'] === null);
$input = closureForm($f['controller'], $review, 'approve'); $input['nonce'] = closureInput($f)['nonce'];
closureCheck('prepare_nonce_cannot_approve_an_exact_job', closureReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$input = closureForm($f['controller'], $review, 'approve'); $input['plan_digest'] = str_repeat('f', 64);
closureCheck('approval_nonce_binds_exact_digest', closureReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$f['session']->identity = 'another-synthetic-owner';
closureCheck('another_owner_cannot_read_private_job', closureReject(fn() => $f['controller']->handle('GET', ['job' => $review['job']['id']], $f['now']), 'REVIEW_NOT_FOUND'));
closureCheck('another_owner_cannot_render_cached_private_job', closureReject(fn() => $f['controller']->render($review), 'REVIEW_NOT_FOUND'));
$f['session']->identity = 'synthetic-owner';
$input = closureForm($f['controller'], $review, 'approve'); $f['session']->token = 'synthetic-replacement-session';
closureCheck('replaced_session_rejects_old_nonce', closureReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));

foreach ([
    'non_authoritative' => ['authoritative' => false], 'sender_fence' => ['sender_fence' => 'PRESENT'],
    'unresolved_retirement' => ['retirement_intent' => 'ACTIVE'], 'wrong_closure' => ['closure_hash' => str_repeat('f', 64)],
    'stale' => ['expires_at' => $f['now']], 'excess_validity' => ['expires_at' => $f['now'] + 301],
] as $name => $overrides) {
    $g = closureFixture(); $g['safety']->overrides = $overrides; $rejected = false;
    try { closurePrepare($g); } catch (O\ReviewFailure $error) { $rejected = true; }
    closureCheck($name . '_cannot_prepare_an_amendment', $rejected && $g['store']->jobs === [] && $g['journal']->writes === 0);
}
$g = closureFixture(); $g['safety']->throw = true;
closureCheck('provider_exception_is_bounded_and_cannot_become_safety', closureReject(fn() => closurePrepare($g), 'CLOSURE_EDIT_SAFETY_UNCERTAIN'));
$g = closureFixture(); $g['safety']->afterRead = function () use ($g) { $g['session']->allowed = false; };
closureCheck('logout_during_preparation_cannot_save_a_review_job', closureReject(fn() => closurePrepare($g), 'OWNER_SESSION_REQUIRED') && $g['store']->jobs === []);
$g = closureFixture(); $r = closurePrepare($g); $g['safety']->afterRead = function () use ($g) { $g['session']->allowed = false; };
closureCheck('logout_during_approval_cannot_commit_write_intent', closureReject(fn() => closureApprove($g, $r), 'OWNER_SESSION_REQUIRED')
    && $g['store']->jobs[$r['job']['id']]['approved_at'] === null && $g['journal']->writes === 0);

$g = closureFixture(); $r = closurePrepare($g); $g['journal']->inner->closures[$g['closure']['closure_id']]['revision']++;
closureCheck('changed_baseline_revision_holds_without_cas', closureHeld(closureApprove($g, $r), 'CLOSURE_BASELINE_CHANGED') && $g['journal']->writes === 0);
$g = closureFixture(); $r = closurePrepare($g); $g['journal']->inner->closures[$g['closure']['closure_id']]['evidence_hash'] = str_repeat('f', 64);
closureCheck('changed_same_revision_body_is_also_stale', closureHeld(closureApprove($g, $r), 'CLOSURE_BASELINE_CHANGED') && $g['journal']->writes === 0);
$g = closureFixture(); $g['journal']->inner->closures[$g['closure']['closure_id']]['email_status'] = 'RETIRED_NO_COPY';
closureCheck('retired_closure_cannot_be_amended_even_to_closed', closureReject(fn() => closurePrepare($g), 'RETIRED_CLOSURE_REQUIRES_RECONCILIATION'));
$g = closureFixture(); $r = closurePrepare($g); $g['safety']->overrides['sender_fence'] = 'PRESENT';
closureCheck('new_sender_fence_after_review_holds_approval', closureHeld(closureApprove($g, $r), 'CLOSURE_EDIT_BLOCKED')
    && $g['store']->jobs[$r['job']['id']]['approved_at'] === null && $g['journal']->writes === 0);
$g = closureFixture(); $r = closurePrepare($g); $g['journal']->inner->journals['synthetic-existing-job'] = ['plan' => ['closure_id' => $g['closure']['closure_id']]];
closureCheck('existing_authoritative_workflow_job_blocks_writer', closureHeld(closureApprove($g, $r), 'CLOSURE_JOB_RECONCILIATION_REQUIRED')
    && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);
$g = closureFixture(); $r = closurePrepare($g); $g['journal']->inner->journals['synthetic-unknown-binding'] = ['plan' => []];
closureCheck('unknown_workflow_job_binding_cannot_establish_a_clear_inventory', closureHeld(closureApprove($g, $r), 'CLOSURE_JOB_RECONCILIATION_REQUIRED')
    && $g['journal']->closure($g['closure']['closure_id']) === $g['closure']);

$g = closureFixture(); $r = closurePrepare($g); $intentSeen = false; $storeLeaseSeen = false;
$g['journal']->beforeWrite = function () use ($g, $r, &$intentSeen, &$storeLeaseSeen) {
    $stored = $g['store']->load($r['job']['id']);
    $intentSeen = $stored['approved_at'] === $g['now'] && $stored['manifest']['after_hash'] === $r['job']['plan']['after_hash'];
    try { $g['store']->locked($r['job']['id'], fn() => null); }
    catch (O\ReviewFailure $error) { $storeLeaseSeen = $error->getMessage() === 'REVIEW_BUSY'; }
};
$applied = closureApprove($g, $r);
closureCheck('durable_exact_owner_intent_precedes_cas_under_store_then_closure_leases', $intentSeen && $storeLeaseSeen
    && $applied['status'] === 'CLOSURE_AMENDMENT_APPLIED' && $g['safety']->reads === $g['safety']->leasedReads);
closureCheck('successful_cas_changes_only_the_reviewed_target_once', $g['journal']->closure($g['closure']['closure_id']) === $r['job']['plan']['after'] && $g['journal']->writes === 1);
$revision = $g['journal']->closure($g['closure']['closure_id'])['revision'];
$replay = $g['controller']->handle('POST', closureForm($g['controller'], $applied, 'resume'), $g['now']);
closureCheck('exact_replay_confirms_without_a_second_revision_bump', $replay['status'] === 'CLOSURE_AMENDMENT_APPLIED'
    && $g['journal']->writes === 1 && $g['journal']->closure($g['closure']['closure_id'])['revision'] === $revision);
$authority = new O\ReviewAuthority($g['store'], $g['session']); $authority->select($r['job']['id']);
closureCheck('amendment_approval_cannot_authorize_purge', !$authority->canApply($g['session']->actor(), $r['job']['plan']['digest'], $g['now'], 'PURGE'));
closureCheck('amendment_never_calls_mail_purge_or_sender_and_preserves_original_outputs', $g['journal']->inner->journals === []
    && array_sum(array_map(fn($adapter) => $adapter->deletes, $g['adapters'])) === 0 && $g['journal']->inner->incomplete === false);

$g = closureFixture(); $r = closurePrepare($g); $g['journal']->loseAcknowledgement = true;
$uncertain = closureApprove($g, $r);
closureCheck('lost_cas_ack_keeps_durable_intent_without_raw_error', closureHeld($uncertain, 'CLOSURE_STORAGE_UNCERTAIN')
    && $g['journal']->closure($g['closure']['closure_id']) === $r['job']['plan']['after']
    && $g['store']->jobs[$r['job']['id']]['manifest'] !== null && !str_contains(json_encode($uncertain), 'PRIVATE_COMMITTED_ACK_CANARY'));
$later = $g['now'] + 901;
$confirmed = $g['controller']->handle('POST', closureForm($g['controller'], $uncertain, 'resume'), $later);
closureCheck('expired_first_approval_window_allows_only_exact_already_applied_confirmation', $confirmed['status'] === 'CLOSURE_AMENDMENT_APPLIED' && $g['journal']->writes === 1);
$g['safety']->unknown = true;
$held = $g['controller']->handle('POST', closureForm($g['controller'], $confirmed, 'resume'), $later);
closureCheck('unknown_safety_does_not_confirm_even_an_existing_exact_target', closureHeld($held, 'CLOSURE_EDIT_SAFETY_UNVERIFIED') && $g['journal']->writes === 1);

$g = closureFixture(); $r = closurePrepare($g); $g['journal']->failBefore = true;
$uncertain = closureApprove($g, $r); $g['journal']->failBefore = false;
$late = $g['controller']->handle('POST', closureForm($g['controller'], $uncertain, 'resume'), $g['now'] + 901);
closureCheck('expired_write_intent_cannot_newly_apply_a_stale_target', closureHeld($late, 'PLAN_EXPIRED')
    && $g['journal']->closure($g['closure']['closure_id']) === $g['closure'] && $g['journal']->writes === 1);
$g = closureFixture(); $r = closurePrepare($g);
closureCheck('expired_unapproved_review_cannot_record_new_approval', closureReject(fn() => closureApprove($g, $r, $g['now'] + 900), 'REVIEW_NOT_FOUND')
    && $g['store']->jobs[$r['job']['id']]['approved_at'] === null && $g['journal']->writes === 0);

// Same-process synthetic environment controls preserve the pure runner's disabled subprocess/network APIs.
$GLOBALS['synthetic_closure_environment'] = 'production';
closureCheck('controller_rejects_production_environment', closureReject(fn() => $g['controller']->handle('GET', [], $g['now']), 'ISOLATED_LAB_ONLY'));
$GLOBALS['synthetic_closure_environment'] = 'local'; $GLOBALS['synthetic_closure_home'] = 'https://example.invalid';
closureCheck('controller_rejects_foreign_host', closureReject(fn() => $g['controller']->handle('GET', [], $g['now']), 'ISOLATED_LAB_ONLY'));
$GLOBALS['synthetic_closure_home'] = 'http://bsre.invalid';

echo json_encode(['phase' => 'synthetic_owner_closure_amendment', 'checks' => count($checks), 'passed' => array_keys($checks),
    'source_records' => 'Synthetic existing closure only', 'safety' => 'Synthetic trusted callback; no real sender/custody authority',
    'production_authorized' => false], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n";
