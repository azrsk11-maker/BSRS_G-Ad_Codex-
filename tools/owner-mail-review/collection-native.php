<?php
declare(strict_types=1);

define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
require '/opt/wordpress/wp-load.php';
$hooksBefore = array_map(fn($hook) => $hook->callbacks, $GLOBALS['wp_filter']);
require __DIR__ . '/WordPress.php';
require_once __DIR__ . '/../closed-enquiry-retention/fixtures.php';
use BSRE\ClosedRetention as C;
use BSRE\OwnerMailReview as O;

function collectionDb(): C\LeaseBoundWpdb
{
    $db = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->prefix = 'owner_collection_synthetic_';
    return $db;
}
function collectionJournal(): C\LabSqlJournal { return new C\LabSqlJournal(collectionDb()); }

if (($argv[1] ?? null) === '--competing-insert') {
    $target = json_decode(stream_get_contents(STDIN, 65536), true, 24, JSON_THROW_ON_ERROR);
    $journal = collectionJournal(); $blocked = false; $code = 'UNKNOWN';
    try { $journal->locked($target['closure_id'], fn() => $journal->insertClosure($target)); }
    catch (C\Failure $error) { $code = $error->getMessage(); $blocked = true; }
    echo json_encode(['blocked' => $blocked, 'code' => $code], JSON_THROW_ON_ERROR) . "\n";
    exit($blocked ? 0 : 1);
}

final class SyntheticCollectionSource implements C\ClosureCollectionSource
{
    public int $calls = 0;
    public $before = null;
    public function __construct(public array $frame) {}
    public function observe(string $requestId, int $now): ?array
    {
        $this->calls++;
        if ($this->before) ($this->before)($this->calls);
        return array_replace($this->frame, ['observed_at' => $now, 'valid_until' => $now + 300]);
    }
}

/** Only simulates a lost acknowledgement after actual private MariaDB persistence. */
final class CollectionAckStore implements O\Store
{
    public bool $loseAppliedAck = false;
    public function __construct(public O\WordPressStore $inner) {}
    public function locked(string $id, callable $operation) { return $this->inner->locked($id, $operation); }
    public function load(string $id): ?array { return $this->inner->load($id); }
    public function save(array &$job): void
    {
        $this->inner->save($job);
        if ($this->loseAppliedAck && $job['status'] === 'CLOSURE_COLLECTION_APPLIED') {
            $this->loseAppliedAck = false; throw new RuntimeException('Synthetic acknowledgement loss');
        }
    }
    public function pruneExpired(int $now): void { $this->inner->pruneExpired($now); }
}

$checks = [];
function collectionCheck(string $name, bool $value): void
{
    global $checks;
    if (!$value) throw new RuntimeException('Synthetic owner collection native check failed: ' . $name);
    $checks[$name] = true;
}
function collectionDenied(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure|C\Failure $error) { return $error->getMessage() === $code; }
}
function collectionPurpose(string $op, string $id = '', string $digest = ''): string
{
    return 'bsre-owner-collection/' . C\Workflow::digest([$op, $id, $digest]);
}
function collectionUser(string $name): int
{
    $user = get_user_by('login', $name);
    if ($user) return (int) $user->ID;
    $id = wp_insert_user(['user_login' => $name, 'user_email' => $name . '@example.invalid',
        'user_pass' => 'Synthetic-local-collection-only-487!', 'role' => 'administrator']);
    if (is_wp_error($id)) throw new RuntimeException('Synthetic owner creation unavailable');
    return (int) $id;
}
function collectionCompeting(array $target): array
{
    $process = proc_open([PHP_BINARY, '-d', 'sendmail_path=/bin/false', __FILE__, '--competing-insert'],
        [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($process)) throw new RuntimeException('Synthetic competing process unavailable');
    fwrite($pipes[0], json_encode($target, JSON_THROW_ON_ERROR)); fclose($pipes[0]);
    stream_set_timeout($pipes[1], 10); stream_set_timeout($pipes[2], 10);
    $output = stream_get_contents($pipes[1], 2048); $errors = stream_get_contents($pipes[2], 2048);
    fclose($pipes[1]); fclose($pipes[2]);
    $exit = proc_close($process);
    if ($exit !== 0 || $errors !== '') throw new RuntimeException('Synthetic competing process failed');
    return json_decode($output, true, 8, JSON_THROW_ON_ERROR);
}
function collectionFixture(C\LabSqlJournal $journal, O\Store $store, O\Session $session, int $number, int $now): array
{
    $f = C\fixture(); $f['admission']->refresh($now);
    $facts = array_intersect_key($f['closure'], array_flip(['status', 'request_id', 'lead_id', 'event_id',
        'accepted_at_utc', 'closed_at_utc', 'evidence_reference', 'evidence_hash', 'outcome_ids', 'mail_message_ids', 'email_status']));
    $facts = array_replace($facts, ['request_id' => C\syntheticUuid($number), 'lead_id' => 'BSRE-' . C\syntheticUuid($number + 1),
        'event_id' => 'evt_' . C\syntheticUuid($number + 2), 'accepted_at_utc' => gmdate('Y-m-d\TH:i:s\Z', $now - 86400),
        'closed_at_utc' => gmdate('Y-m-d\TH:i:s\Z', $now - 3600), 'outcome_ids' => [], 'mail_message_ids' => [], 'email_status' => 'QUEUED']);
    $f['adapters']['email']->rows = []; $f['adapters']['outcome']->rows = [];
    foreach (['intake', 'capture'] as $kind) foreach ($f['adapters'][$kind]->rows as &$row) {
        foreach (['request_id', 'lead_id', 'event_id'] as $key) $row[$key] = $facts[$key];
        $row['request_ids'] = [$facts['request_id']];
    }
    unset($row);
    $source = new SyntheticCollectionSource(['contract' => C\CollectionSnapshot::CONTRACT, 'facts' => $facts,
        'source_hash' => str_repeat('a', 64), 'source_generation' => str_repeat('b', 64),
        'observed_at' => $now, 'valid_until' => $now + 300, 'authoritative' => true, 'complete' => true,
        'sender_fence' => 'ABSENT', 'retirement_intent' => 'NONE', 'mailbox' => 'marketing@blackswanrealestate.ae',
        'mailbox_coverage' => 'COMPLETE', 'includes_trash' => true, 'attempt_count' => 0,
        'send_started_at_utc' => null, 'sent_at_utc' => null]);
    $authority = new O\ReviewAuthority($store, $session);
    $workflow = new C\Workflow($journal, $f['adapters'], $authority, $f['admission']);
    $controller = new O\OwnerCollectionController($workflow, $journal, $store, $session, $source);
    return array_replace($f, compact('journal', 'source', 'authority', 'workflow', 'controller', 'facts', 'now'));
}
function collectionPrepare(array $f, O\Session $session): array
{
    return $f['controller']->handle('POST', ['operation' => 'prepare', 'request_id' => $f['facts']['request_id'],
        'nonce' => $session->nonce(collectionPurpose('prepare'))], $f['now']);
}
function collectionApply(array $f, array $view, O\Session $session, string $op = 'approve', ?int $now = null): array
{
    $job = $view['job'];
    return $f['controller']->handle('POST', ['operation' => $op, 'job' => $job['id'], 'plan_digest' => $job['plan']['digest'],
        'nonce' => $session->nonce(collectionPurpose($op, $job['id'], $job['plan']['digest']))], $now ?? $f['now']);
}

collectionCheck('loading_adds_no_hook_or_route', $hooksBefore === array_map(fn($hook) => $hook->callbacks, $GLOBALS['wp_filter']));
$owner = collectionUser('owner-collection-synthetic-owner'); $other = collectionUser('owner-collection-synthetic-other');
wp_set_current_user($owner); $session = new O\WordPressSession($owner); $now = time();
$db = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST); $db->prefix = 'owner_mail_review_synthetic_';
$inner = new O\WordPressStore($db); $inner->install(); $store = new CollectionAckStore($inner);
$journal = collectionJournal(); $journal->install(); $f = collectionFixture($journal, $store, $session, 501, $now);
wp_set_current_user($other);
collectionCheck('actual_other_administrator_denied', collectionDenied(fn() => $f['controller']->handle('GET', [], $now), 'OWNER_SESSION_REQUIRED'));
wp_set_current_user($owner);
collectionCheck('bad_actual_nonce_before_source', collectionDenied(fn() => $f['controller']->handle('POST',
    ['operation' => 'prepare', 'request_id' => $f['facts']['request_id'], 'nonce' => 'wrong'], $now), 'CSRF_REJECTED') && $f['source']->calls === 0);
$prepared = collectionPrepare($f, $session); $plan = $prepared['job']['plan'];
collectionCheck('real_private_review_persists_before_canonical_row', $inner->load($prepared['job']['id']) === $prepared['job']
    && $journal->closure($plan['closure_id']) === null);
collectionCheck('server_derives_exact_initial_identity_revision_reviewer_time', $plan['after']['closure_id'] === $f['facts']['request_id']
    && $plan['after']['revision'] === 1 && $plan['after']['reviewer'] === $session->actor()
    && $plan['after']['recorded_at_utc'] === gmdate('Y-m-d\TH:i:s\Z', $now));
$witnessed = false; $competing = $plan['after']; $competing['request_id'] = $competing['closure_id'] = C\syntheticUuid(999);
$competing['event_id'] = 'evt_' . C\syntheticUuid(998);
$f['source']->before = function () use (&$witnessed, $inner, $prepared, $competing) {
    $job = $inner->load($prepared['job']['id']);
    if ($job['approved_at'] === null) return;
    collectionCheck('fresh_source_read_has_durable_exact_intent', $job['manifest']['plan_digest'] === $job['plan']['digest']
        && $job['manifest']['contract'] === O\OwnerCollectionController::CONTRACT);
    if (!$witnessed) {
        collectionCheck('other_process_cannot_insert_during_source_custody', collectionCompeting($competing)
            === ['blocked' => true, 'code' => 'CLOSURE_LEASE_BUSY']);
        $witnessed = true;
    }
};
$store->loseAppliedAck = true;
$lost = collectionApply($f, $prepared, $session);
collectionCheck('ack_loss_keeps_exact_canonical_row', $lost['status'] === 'HELD'
    && collectionJournal()->closure($plan['closure_id']) === $plan['after'] && $witnessed);
$sourceCalls = $f['source']->calls;
$restarted = new O\OwnerCollectionController($f['workflow'], $journal, $store, $session, $f['source']);
$f['controller'] = $restarted; $resumed = collectionApply($f, $lost, $session, 'resume', $now + 901);
collectionCheck('late_exact_acknowledgement_never_reinserts_or_reads_source', $resumed['status'] === 'CLOSURE_COLLECTION_APPLIED'
    && $f['source']->calls === $sourceCalls && collectionJournal()->closure($plan['closure_id']) === $plan['after']);
collectionCheck('actual_other_process_duplicate_identity_rejected', collectionCompeting($competing)
    === ['blocked' => true, 'code' => 'COLLECTION_IDENTITY_ALREADY_BOUND']);
$f['authority']->select($prepared['job']['id']);
collectionCheck('collection_contract_cannot_grant_purge', !$f['authority']->canApply($session->actor(), $plan['digest'], $now, 'PURGE'));
collectionCheck('direct_existing_target_never_upserts', collectionDenied(fn() => $journal->locked($plan['closure_id'],
    fn() => $journal->insertClosure($plan['after'])), 'COLLECTION_IDENTITY_ALREADY_BOUND'));
$store->pruneExpired($now + 30 * 86400 + 1);
collectionCheck('private_ui_prune_preserves_authoritative_closure', $inner->load($prepared['job']['id']) === null
    && collectionJournal()->closure($plan['closure_id']) === $plan['after']);
collectionCheck('pruned_job_does_not_recreate_or_confirm', collectionDenied(fn() => collectionApply($f, $lost, $session, 'resume',
    $now + 30 * 86400 + 1), 'REVIEW_NOT_FOUND'));
$fresh = collectionFixture($journal, $store, $session, 601, $now);
$stalePlan = collectionPrepare($fresh, $session);
collectionCheck('expired_unapplied_review_cannot_create', collectionDenied(fn() => collectionApply($fresh, $stalePlan, $session, 'approve', $now + 900), 'REVIEW_NOT_FOUND')
    && $journal->closure($fresh['facts']['request_id']) === null);
collectionCheck('recent_record_still_cannot_retire_early', collectionDenied(fn() => C\Workflow::validateClosureRecord($plan['after'], $now, true),
    'RETENTION_NOT_DUE'));
wp_set_current_user(0);
collectionCheck('logged_out_actual_owner_cannot_read', collectionDenied(fn() => $f['controller']->handle('GET', [], $now), 'OWNER_SESSION_REQUIRED'));
echo json_encode(['scope' => 'ISOLATED_WORDPRESS_MARIADB_INITIAL_CLOSURE_COLLECTION', 'fixture_only' => true,
    'source_and_mailbox_services' => 'SYNTHETIC_DOUBLES_ONLY', 'checks' => count($checks), 'passed' => true,
    'results' => $checks, 'provider_mutations' => 0, 'purge_or_retirement_authority' => false], JSON_THROW_ON_ERROR) . "\n";
