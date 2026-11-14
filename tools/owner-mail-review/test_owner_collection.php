<?php
declare(strict_types=1);
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
$GLOBALS['synthetic_collection_environment'] = 'local';
$GLOBALS['synthetic_collection_home'] = 'http://bsre.invalid';
function wp_get_environment_type(): string { return $GLOBALS['synthetic_collection_environment']; }
function home_url(): string { return $GLOBALS['synthetic_collection_home']; }
require __DIR__ . '/TestDoubles.php';
require __DIR__ . '/OwnerCollection.php';
use BSRE\ClosedRetention as C;
use BSRE\OwnerMailReview as O;

/** Synthetic complete source only; no private records, mailbox credentials or real authority. */
final class SyntheticCollectionSource implements C\ClosureCollectionSource
{
    public array $overrides = [];
    public bool $unknown = false;
    public bool $throw = false;
    public int $reads = 0;
    public int $leasedReads = 0;
    public $afterRead = null;
    public function __construct(public array $facts, private C\Journal $journal) {}
    public function observe(string $requestId, int $now): ?array
    {
        $this->reads++;
        try { $this->journal->locked($requestId, fn() => null); }
        catch (RuntimeException $error) { $this->leasedReads++; }
        if ($this->throw) throw new RuntimeException('PRIVATE_SOURCE_CANARY');
        if ($this->unknown) return null;
        $frame = array_replace(['contract' => C\CollectionSnapshot::CONTRACT, 'facts' => $this->facts,
            'source_hash' => str_repeat('7', 64), 'source_generation' => str_repeat('8', 64),
            'observed_at' => $now, 'valid_until' => $now + 300, 'authoritative' => true, 'complete' => true,
            'sender_fence' => 'ABSENT', 'retirement_intent' => 'NONE', 'mailbox' => 'marketing@blackswanrealestate.ae',
            'mailbox_coverage' => 'COMPLETE', 'includes_trash' => true, 'attempt_count' => 1,
            'send_started_at_utc' => '2025-01-01T12:00:01Z', 'sent_at_utc' => '2025-01-01T12:00:02Z'], $this->overrides);
        if ($this->afterRead) ($this->afterRead)($this->reads);
        return $frame;
    }
}

/** Actual MemoryJournal collection checks remain in the call path around injected acknowledgement faults. */
final class CollectionFaultJournal implements C\Journal, C\ClosureCollectorWriter
{
    public int $writes = 0;
    public bool $failBefore = false;
    public bool $loseAcknowledgement = false;
    public $beforeWrite = null;
    public function __construct(public C\MemoryJournal $inner) {}
    public function locked(string $id, callable $operation) { return $this->inner->locked($id, $operation); }
    public function closure(string $id): ?array { return $this->inner->closure($id); }
    public function journal(string $id): ?array { return $this->inner->journal($id); }
    public function save(array &$record): void { $this->inner->save($record); }
    public function markHistoryIncomplete(): void { $this->inner->markHistoryIncomplete(); }
    public function historyIncomplete(): bool { return $this->inner->historyIncomplete(); }
    public function pinAdmissionFloor(string $hash): void { $this->inner->pinAdmissionFloor($hash); }
    public function admissionFloor(): ?string { return $this->inner->admissionFloor(); }
    public function forget(string $id, string $plan, bool $keep = false): void { $this->inner->forget($id, $plan, $keep); }
    public function assertCollectionTarget(array $target, bool $allowExact = false): void { $this->inner->assertCollectionTarget($target, $allowExact); }
    public function insertClosure(array $target): void
    {
        $this->writes++;
        if ($this->beforeWrite) ($this->beforeWrite)();
        if ($this->failBefore) throw new RuntimeException('PRIVATE_INSERT_CANARY');
        $this->inner->insertClosure($target);
        if ($this->loseAcknowledgement) { $this->loseAcknowledgement = false; throw new RuntimeException('PRIVATE_INSERT_ACK_CANARY'); }
    }
}

function collectionFixture(): array
{
    $f = C\fixture(); $f['journal']->closures = [];
    $journal = new CollectionFaultJournal($f['journal']);
    $store = new O\MemoryStore(); $session = new O\SyntheticSession();
    $authority = new O\ReviewAuthority($store, $session);
    $workflow = new C\Workflow($journal, $f['adapters'], $authority, $f['admission']);
    $facts = $f['closure'];
    foreach (['schema_version', 'closure_id', 'revision', 'reviewer', 'recorded_at_utc'] as $key) unset($facts[$key]);
    $source = new SyntheticCollectionSource($facts, $journal);
    $controller = new O\OwnerCollectionController($workflow, $journal, $store, $session, $source);
    return array_merge($f, compact('journal', 'store', 'session', 'authority', 'workflow', 'source', 'controller'));
}
function collectionForm(O\OwnerCollectionController $controller, array $view, string $operation): array
{
    preg_match_all('/<form method="post">(.*?)<\/form>/s', $controller->render($view), $forms);
    foreach ($forms[1] as $body) {
        preg_match_all('/<input type="hidden" name="([^"]+)" value="([^"]*)">/', $body, $inputs, PREG_SET_ORDER);
        $values = [];
        foreach ($inputs as $input) $values[html_entity_decode($input[1], ENT_QUOTES, 'UTF-8')] = html_entity_decode($input[2], ENT_QUOTES, 'UTF-8');
        if (($values['operation'] ?? '') === $operation) return $values;
    }
    throw new RuntimeException('Synthetic collection form unavailable');
}
function collectionInput(array $f): array
{
    return collectionForm($f['controller'], ['status' => 'READY', 'job' => null], 'prepare') + ['request_id' => $f['closure']['request_id']];
}
function collectionPrepare(array $f): array { return $f['controller']->handle('POST', collectionInput($f), $f['now']); }
function collectionApply(array $f, array $view, string $operation = 'approve', ?int $now = null): array
{
    return $f['controller']->handle('POST', collectionForm($f['controller'], $view, $operation), $now ?? $f['now']);
}
$checks = [];
function collectionCheck(string $name, bool $passed): void
{
    global $checks;
    if (!$passed) throw new RuntimeException('Owner collection check failed: ' . $name);
    $checks[$name] = true;
}
function collectionReject(callable $operation, ?string $code = null): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure|C\Failure $error) { return $code === null || $error->getMessage() === $code; }
}
function collectionHeld(array $view, ?string $code = null): bool
{
    return $view['status'] === 'HELD' && ($code === null || in_array($code, $view['hold_codes'], true));
}

$f = collectionFixture(); $f['store']->jobs['synthetic-expired-cache'] = ['cleanup_after' => $f['now'] - 1];
collectionCheck('get_never_collects_or_prunes', $f['controller']->handle('GET', [], $f['now']) === ['status' => 'READY', 'job' => null]
    && $f['source']->reads === 0 && isset($f['store']->jobs['synthetic-expired-cache']));
$f['session']->allowed = false; $reads = $f['store']->reads;
collectionCheck('authentication_precedes_private_reads', collectionReject(fn() => $f['controller']->handle('GET', ['job' => str_repeat('0', 64)], $f['now']), 'OWNER_SESSION_REQUIRED') && $f['store']->reads === $reads);
$f['session']->allowed = true;
$default = new O\OwnerCollectionController($f['workflow'], $f['journal'], $f['store'], $f['session']);
collectionCheck('default_source_remains_unverified', collectionReject(fn() => $default->handle('POST', collectionInput($f), $f['now']), 'CLOSURE_COLLECTION_SOURCE_UNVERIFIED'));
$other = collectionFixture();
collectionCheck('different_authoritative_journal_is_rejected', collectionReject(fn() => new O\OwnerCollectionController($f['workflow'], $other['journal'], $f['store'], $f['session']), 'COLLECTION_JOURNAL_CONFLICT'));
foreach (['status', 'closed_at_utc', 'reviewer', 'revision', 'accepted_at_utc', 'lead_id', 'outcome_ids', 'evidence_hash', 'authoritative'] as $key) {
    collectionCheck('caller_' . $key . '_cannot_supply_source_facts', collectionReject(fn() => $f['controller']->handle('POST', collectionInput($f) + [$key => 'forbidden'], $f['now']), 'INPUT_SCHEMA_INVALID'));
}
$f = collectionFixture(); $review = collectionPrepare($f); $plan = $review['job']['plan'];
collectionCheck('prepare_leaves_canonical_ledger_unchanged', $f['journal']->inner->closures === [] && $f['journal']->writes === 0 && $review['job']['manifest'] === null);
collectionCheck('review_binds_exact_purpose_source_context_and_fixed_window', $plan['contract'] === O\OwnerCollectionController::CONTRACT
    && $plan['expires_at'] === $f['now'] + 900 && strlen($plan['source_fingerprint']) === 64 && count($plan['context']) === 2);
collectionCheck('server_derives_stable_identity_revision_reviewer_recording', $plan['after']['closure_id'] === $f['closure']['request_id']
    && $plan['after']['revision'] === 1 && $plan['after']['reviewer'] === $f['session']->actor()
    && $plan['after']['recorded_at_utc'] === gmdate('Y-m-d\TH:i:s\Z', $f['now']));
collectionCheck('all_source_observations_hold_closure_lease', $f['source']->reads > 0 && $f['source']->reads === $f['source']->leasedReads);
$input = collectionForm($f['controller'], $review, 'approve'); $input['nonce'] = 'invalid';
collectionCheck('invalid_nonce_cannot_commit_intent', collectionReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED') && $f['store']->jobs[$review['job']['id']]['approved_at'] === null);
$input = collectionForm($f['controller'], $review, 'approve'); $input['nonce'] = collectionInput($f)['nonce'];
collectionCheck('prepare_nonce_cannot_approve_collection', collectionReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$input = collectionForm($f['controller'], $review, 'approve'); $input['plan_digest'] = str_repeat('f', 64);
collectionCheck('approval_nonce_binds_exact_digest', collectionReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$f['session']->identity = 'other-synthetic-owner';
collectionCheck('other_owner_cannot_read_or_render_private_plan', collectionReject(fn() => $f['controller']->handle('GET', ['job' => $review['job']['id']], $f['now']), 'REVIEW_NOT_FOUND') && collectionReject(fn() => $f['controller']->render($review), 'REVIEW_NOT_FOUND'));
$f['session']->identity = 'synthetic-owner'; $input = collectionForm($f['controller'], $review, 'approve'); $f['session']->token = 'replacement';
collectionCheck('session_replacement_invalidates_nonce', collectionReject(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));

foreach (['not_authoritative' => ['authoritative' => false], 'incomplete' => ['complete' => false],
    'fenced' => ['sender_fence' => 'PRESENT'], 'retirement_pending' => ['retirement_intent' => 'ACTIVE'],
    'wrong_mailbox' => ['mailbox' => 'other@example.invalid'], 'missing_trash' => ['includes_trash' => false],
    'incomplete_mailbox' => ['mailbox_coverage' => 'UNKNOWN'], 'negative_attempts' => ['attempt_count' => -1],
    'zero_sent_attempts' => ['attempt_count' => 0], 'missing_sent_time' => ['sent_at_utc' => null]] as $name => $overrides) {
    $g = collectionFixture(); $g['source']->overrides = $overrides;
    collectionCheck($name . '_cannot_create_review', collectionReject(fn() => collectionPrepare($g)) && $g['store']->jobs === [] && $g['journal']->writes === 0);
}
foreach (['stale' => [-1, 0], 'future' => [1, 301], 'excessive_window' => [0, 901]] as $name => [$observed, $until]) {
    $g = collectionFixture(); $g['source']->overrides = ['observed_at' => $g['now'] + $observed, 'valid_until' => $g['now'] + $until];
    collectionCheck($name . '_source_window_holds', collectionReject(fn() => collectionPrepare($g)) && $g['journal']->writes === 0);
}
$g = collectionFixture(); $g['source']->throw = true;
collectionCheck('provider_error_is_sanitized_and_held', collectionReject(fn() => collectionPrepare($g), 'CLOSURE_COLLECTION_SOURCE_UNCERTAIN'));
$g = collectionFixture(); $g['source']->facts['email_status'] = 'RETIRED_NO_COPY';
collectionCheck('collection_cannot_originate_retired_no_copy', collectionReject(fn() => collectionPrepare($g)));
$g = collectionFixture(); $g['source']->facts['request_id'] = C\syntheticUuid(99);
collectionCheck('source_cannot_rebind_requested_identity', collectionReject(fn() => collectionPrepare($g)));
$g = collectionFixture(); $g['source']->facts['closed_at_utc'] = gmdate('Y-m-d\TH:i:s\Z', $g['now'] - 60); $r = collectionPrepare($g);
collectionCheck('recent_genuine_source_closure_can_be_recorded_without_purge_due', collectionReject(fn() => C\Workflow::validateClosureRecord($r['job']['plan']['after'], $g['now'], true), 'RETENTION_NOT_DUE'));
$g = collectionFixture(); $g['source']->facts['email_status'] = 'QUEUED'; $g['source']->facts['mail_message_ids'] = [];
$g['source']->overrides = ['attempt_count' => 0, 'send_started_at_utc' => null, 'sent_at_utc' => null]; $g['adapters']['email']->rows = [];
$r = collectionPrepare($g); $applied = collectionApply($g, $r);
collectionCheck('zero_attempt_pending_source_is_collected_without_retirement', $applied['status'] === 'CLOSURE_COLLECTION_APPLIED'
    && $g['journal']->closure($g['closure']['request_id'])['email_status'] === 'QUEUED' && $g['journal']->inner->journals === []);
$g = collectionFixture(); $g['source']->facts['email_status'] = 'QUEUED'; $g['source']->facts['mail_message_ids'] = [];
collectionCheck('attempted_pending_source_is_not_clearance', collectionReject(fn() => collectionPrepare($g)));
$g = collectionFixture(); $g['source']->facts['status'] = 'OPEN'; $g['source']->facts['closed_at_utc'] = null; $r = collectionPrepare($g);
collectionCheck('explicit_open_source_is_preserved_without_inventing_closure', $r['job']['plan']['after']['status'] === 'OPEN' && $r['job']['plan']['after']['closed_at_utc'] === null);

$g = collectionFixture(); $r = collectionPrepare($g); $g['source']->facts['evidence_hash'] = str_repeat('f', 64);
collectionCheck('changed_source_facts_hold_without_intent', collectionHeld(collectionApply($g, $r), 'COLLECTION_SOURCE_CHANGED') && $g['store']->jobs[$r['job']['id']]['approved_at'] === null && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['source']->overrides['source_generation'] = str_repeat('f', 64);
collectionCheck('changed_source_generation_holds', collectionHeld(collectionApply($g, $r), 'COLLECTION_SOURCE_CHANGED'));
$g = collectionFixture(); $r = collectionPrepare($g); $g['adapters']['capture']->rows['synthetic-capture']['fingerprint'] = str_repeat('f', 64);
collectionCheck('changed_exact_inventory_holds', collectionHeld(collectionApply($g, $r), 'COLLECTION_CONTEXT_CHANGED') && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['admission']->value['source_hashes']['wp'] = str_repeat('9', 64);
collectionCheck('changed_admission_configuration_holds', collectionHeld(collectionApply($g, $r), 'COLLECTION_CONTEXT_CHANGED') && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $applied = collectionApply($g, $r, 'approve', $g['now'] + 60);
collectionCheck('fresh_wrapper_same_facts_preserves_exact_plan_and_deadline', $applied['status'] === 'CLOSURE_COLLECTION_APPLIED' && $applied['job']['plan'] === $r['job']['plan'] && $g['journal']->writes === 1);
$g = collectionFixture(); $r = collectionPrepare($g); $originalFactOrder = array_keys($g['source']->facts);
$g['source']->facts = array_reverse($g['source']->facts, true); $applied = collectionApply($g, $r);
collectionCheck('source_object_key_order_does_not_change_exact_target_or_fingerprint', array_keys($g['source']->facts) !== $originalFactOrder
    && $applied['status'] === 'CLOSURE_COLLECTION_APPLIED' && $applied['job']['plan'] === $r['job']['plan']
    && $g['journal']->closure($r['job']['plan']['closure_id']) === $r['job']['plan']['after'] && $g['journal']->writes === 1);

$g = collectionFixture(); $g['source']->afterRead = function () use ($g) { $g['session']->allowed = false; };
collectionCheck('logout_during_prepare_cannot_save_private_plan', collectionReject(fn() => collectionPrepare($g), 'OWNER_SESSION_REQUIRED') && $g['store']->jobs === []);
$g = collectionFixture(); $r = collectionPrepare($g); $g['source']->afterRead = function () use ($g) { $g['session']->allowed = false; };
collectionCheck('logout_during_approval_prevents_intent_and_insert', collectionReject(fn() => collectionApply($g, $r), 'OWNER_SESSION_REQUIRED') && $g['store']->jobs[$r['job']['id']]['manifest'] === null && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['store']->afterSave = function (array $job) use ($g) {
    if ($job['manifest'] !== null) $g['source']->facts['evidence_hash'] = str_repeat('f', 64);
};
collectionCheck('source_is_rechecked_after_committed_intent', collectionHeld(collectionApply($g, $r), 'COLLECTION_SOURCE_CHANGED') && $g['store']->jobs[$r['job']['id']]['manifest'] !== null && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['store']->afterSave = function (array $job) use ($g) {
    if ($job['manifest'] !== null) $g['session']->allowed = false;
};
collectionCheck('logout_after_committed_intent_still_prevents_insert', collectionReject(fn() => collectionApply($g, $r), 'OWNER_SESSION_REQUIRED') && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['store']->afterSave = function (array $job) use ($g) {
    if ($job['manifest'] !== null) {
        $g['store']->afterSave = null;
        $g['store']->jobs[$job['id']]['status'] = 'SYNTHETIC_READBACK_CONFLICT';
    }
};
collectionCheck('conflicting_intent_readback_prevents_insert', collectionHeld(collectionApply($g, $r), 'COLLECTION_INTENT_UNCONFIRMED') && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['store']->afterSave = function (array $job) use ($g) {
    if ($job['manifest'] !== null) { $g['store']->afterSave = null; throw new RuntimeException('PRIVATE_STORE_ACK_CANARY'); }
};
$held = collectionApply($g, $r);
collectionCheck('lost_private_store_ack_cannot_start_insert', collectionHeld($held, 'CLOSURE_COLLECTION_STORAGE_UNCERTAIN') && $g['journal']->writes === 0 && !str_contains(json_encode($held), 'PRIVATE_STORE_ACK_CANARY'));
collectionCheck('durably_recovered_store_intent_can_resume_in_original_window', collectionApply($g, $held, 'resume')['status'] === 'CLOSURE_COLLECTION_APPLIED' && $g['journal']->writes === 1);

foreach (['request_id', 'lead_id', 'event_id'] as $field) {
    $g = collectionFixture(); $duplicate = $g['closure']; $duplicate['closure_id'] = C\syntheticUuid(98);
    $duplicate['outcome_ids'] = [C\syntheticUuid(94)]; $duplicate['mail_message_ids'] = ['synthetic-other-message'];
    foreach (['request_id' => C\syntheticUuid(91), 'lead_id' => 'BSRE-' . C\syntheticUuid(92), 'event_id' => 'evt_' . C\syntheticUuid(93)] as $key => $value) if ($field !== $key) $duplicate[$key] = $value;
    $g['journal']->inner->closures[$duplicate['closure_id']] = $duplicate;
    collectionCheck('legacy_duplicate_' . $field . '_holds', collectionReject(fn() => collectionPrepare($g)) && $g['journal']->writes === 0);
}
foreach (['outcome_ids', 'mail_message_ids'] as $field) {
    $g = collectionFixture(); $duplicate = $g['closure'];
    $duplicate['closure_id'] = C\syntheticUuid(98); $duplicate['request_id'] = C\syntheticUuid(91);
    $duplicate['lead_id'] = 'BSRE-' . C\syntheticUuid(92); $duplicate['event_id'] = 'evt_' . C\syntheticUuid(93);
    if ($field !== 'outcome_ids') $duplicate['outcome_ids'] = [C\syntheticUuid(94)];
    if ($field !== 'mail_message_ids') $duplicate['mail_message_ids'] = ['synthetic-other-message'];
    $g['journal']->inner->closures[$duplicate['closure_id']] = $duplicate;
    collectionCheck('legacy_shared_' . $field . '_holds_independently_of_enquiry_identity', collectionReject(fn() => collectionPrepare($g), 'COLLECTION_IDENTITY_ALREADY_BOUND') && $g['journal']->writes === 0);
}
$g = collectionFixture(); $g['journal']->inner->closures[C\syntheticUuid(98)] = ['unknown' => true];
collectionCheck('malformed_canonical_record_cannot_be_skipped', collectionReject(fn() => collectionPrepare($g)));
foreach (['current' => ['plan' => ['closure_id' => C\syntheticUuid(2)]], 'unknown' => ['plan' => []]] as $name => $job) {
    $g = collectionFixture(); $g['journal']->inner->journals['synthetic-conflict'] = $job;
    collectionCheck($name . '_journal_job_blocks_collection', collectionReject(fn() => collectionPrepare($g)));
}
$g = collectionFixture(); $g['journal']->inner->expiredUnresolved = 1;
collectionCheck('unresolved_global_custody_blocks_new_collection', collectionReject(fn() => collectionPrepare($g)));
$g = collectionFixture(); $r = collectionPrepare($g); $g['journal']->beforeWrite = function () use ($g) {
    $g['journal']->inner->journals['synthetic-late-job'] = ['plan' => []];
};
collectionCheck('writer_rechecks_unknown_jobs_immediately_before_insert', collectionHeld(collectionApply($g, $r)) && $g['journal']->inner->closures === []);

$g = collectionFixture(); $r = collectionPrepare($g); $intentSeen = false; $storeLeaseSeen = false;
$g['journal']->beforeWrite = function () use ($g, $r, &$intentSeen, &$storeLeaseSeen) {
    $stored = $g['store']->load($r['job']['id']);
    $intentSeen = $stored['manifest'] === ['contract' => O\OwnerCollectionController::CONTRACT,
        'plan_digest' => $r['job']['plan']['digest'], 'after_hash' => $r['job']['plan']['after_hash'],
        'source_fingerprint' => $r['job']['plan']['source_fingerprint'], 'intent_at' => $g['now']];
    try { $g['store']->locked($r['job']['id'], fn() => null); }
    catch (O\ReviewFailure $error) { $storeLeaseSeen = $error->getMessage() === 'REVIEW_BUSY'; }
};
$applied = collectionApply($g, $r);
collectionCheck('durable_exact_intent_and_store_lease_precede_insertion', $intentSeen && $storeLeaseSeen && $applied['status'] === 'CLOSURE_COLLECTION_APPLIED');
collectionCheck('only_exact_reviewed_canonical_target_is_inserted', $g['journal']->inner->closures === [$r['job']['plan']['closure_id'] => $r['job']['plan']['after']] && $g['journal']->writes === 1);
collectionCheck('approval_rereads_source_before_and_after_intent_under_lease', $g['source']->reads >= 3 && $g['source']->reads === $g['source']->leasedReads);
$g['authority']->select($r['job']['id']);
collectionCheck('collection_approval_never_authorizes_purge', !$g['authority']->canApply($g['session']->actor(), $r['job']['plan']['digest'], $g['now'], 'PURGE'));
collectionCheck('collection_has_no_provider_deletion_or_retirement_effect', $g['journal']->inner->journals === [] && !$g['journal']->inner->incomplete
    && array_sum(array_map(fn($adapter) => $adapter->deletes, $g['adapters'])) === 0);
$again = collectionApply($g, $applied, 'resume');
collectionCheck('exact_acknowledgement_does_not_insert_twice', $again['status'] === 'CLOSURE_COLLECTION_APPLIED' && $g['journal']->writes === 1);
$g['journal']->inner->expiredUnresolved = 1;
collectionCheck('exact_acknowledgement_still_checks_global_custody', collectionHeld(collectionApply($g, $again, 'resume')) && $g['journal']->writes === 1);
$g = collectionFixture(); $r = collectionPrepare($g); $applied = collectionApply($g, $r);
$g['journal']->inner->journals['synthetic-unknown-job'] = ['plan' => []];
collectionCheck('exact_acknowledgement_still_checks_unknown_jobs', collectionHeld(collectionApply($g, $applied, 'resume')) && $g['journal']->writes === 1);
$g = collectionFixture(); $r = collectionPrepare($g); $applied = collectionApply($g, $r); $duplicate = $r['job']['plan']['after'];
$duplicate['closure_id'] = C\syntheticUuid(99); $g['journal']->inner->closures[$duplicate['closure_id']] = $duplicate;
collectionCheck('exact_acknowledgement_still_checks_other_duplicate_closures', collectionHeld(collectionApply($g, $applied, 'resume')) && $g['journal']->writes === 1);

$g = collectionFixture(); $r = collectionPrepare($g); $g['journal']->loseAcknowledgement = true;
$uncertain = collectionApply($g, $r);
collectionCheck('lost_insert_ack_preserves_intent_and_sanitizes_failure', collectionHeld($uncertain, 'CLOSURE_COLLECTION_STORAGE_UNCERTAIN')
    && $g['store']->jobs[$r['job']['id']]['manifest'] !== null && !str_contains(json_encode($uncertain), 'PRIVATE_INSERT_ACK_CANARY'));
$g['source']->unknown = true; $confirmed = collectionApply($g, $uncertain, 'resume', $g['now'] + 901);
collectionCheck('expired_create_window_can_confirm_only_committed_exact_target', $confirmed['status'] === 'CLOSURE_COLLECTION_APPLIED' && $g['journal']->writes === 1);
$g = collectionFixture(); $r = collectionPrepare($g); $g['journal']->failBefore = true; $failed = collectionApply($g, $r); $g['journal']->failBefore = false;
collectionCheck('failed_insert_after_original_deadline_cannot_create', collectionHeld(collectionApply($g, $failed, 'resume', $g['now'] + 900), 'PLAN_EXPIRED') && $g['journal']->inner->closures === [] && $g['journal']->writes === 1);
$g = collectionFixture(); $r = collectionPrepare($g);
collectionCheck('unapproved_review_expires_at_fifteen_minutes', collectionReject(fn() => collectionApply($g, $r, 'approve', $g['now'] + 900), 'REVIEW_NOT_FOUND') && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $g['journal']->inner->closures[$r['job']['plan']['closure_id']] = $r['job']['plan']['after'];
collectionCheck('exact_existing_target_without_owner_intent_cannot_be_adopted', collectionHeld(collectionApply($g, $r), 'COLLECTION_TARGET_ALREADY_EXISTS') && $g['journal']->writes === 0);
$g = collectionFixture(); $r = collectionPrepare($g); $applied = collectionApply($g, $r); $target = $r['job']['plan']['after'];
$g['store']->pruneExpired($g['now'] + 30 * 86400);
collectionCheck('thirty_day_cache_cleanup_preserves_canonical_evidence', $g['store']->jobs === [] && $g['journal']->closure($target['closure_id']) === $target);
$g['admission']->refresh($g['now'] + 30 * 86400);
collectionCheck('pruned_ui_cannot_recreate_existing_canonical_closure', collectionReject(fn() => $g['controller']->handle('POST', collectionInput($g), $g['now'] + 30 * 86400)) && $g['journal']->writes === 1);

$g = collectionFixture(); $g['source']->facts['evidence_reference'] = '<script>synthetic-only</script>'; $r = collectionPrepare($g); $html = $g['controller']->render($r);
collectionCheck('private_renderer_escapes_source_evidence_and_has_no_external_resources', str_contains($html, '&lt;script&gt;synthetic-only&lt;/script&gt;') && !str_contains($html, '<script>') && !str_contains($html, 'src=') && str_contains($html, 'aria-label="Exact private closure collection"'));
$GLOBALS['synthetic_collection_environment'] = 'production';
collectionCheck('production_environment_is_rejected', collectionReject(fn() => $g['controller']->handle('GET', [], $g['now']), 'ISOLATED_LAB_ONLY'));
$GLOBALS['synthetic_collection_environment'] = 'local'; $GLOBALS['synthetic_collection_home'] = 'https://example.invalid';
collectionCheck('foreign_host_is_rejected', collectionReject(fn() => $g['controller']->handle('GET', [], $g['now']), 'ISOLATED_LAB_ONLY'));
$GLOBALS['synthetic_collection_home'] = 'http://bsre.invalid';

echo json_encode(['phase' => 'synthetic_owner_closure_collection', 'checks' => count($checks), 'passed' => array_keys($checks),
    'source_records' => 'Synthetic source facts and provider resources only', 'source_authority' => 'Synthetic trusted callback; no real source/mailbox/custody acceptance',
    'production_authorized' => false], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES) . "\n";
