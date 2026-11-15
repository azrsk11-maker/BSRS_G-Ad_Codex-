<?php
declare(strict_types=1);
/** Disposable repository/retirement concurrency proof; never a public route. */
if (PHP_SAPI !== 'cli') throw new RuntimeException('G1_CONCURRENCY_CLI_ONLY');
$worker = ($argv[1] ?? '') === 'worker';
if ((!$worker && count($argv) !== 1) || ($worker && (count($argv) !== 3 || !in_array($argv[2], ['stage','retire'], true)))) {
    throw new RuntimeException('G1_CONCURRENCY_FIXED_MODE_ONLY');
}
define('WP_ENVIRONMENT_TYPE', 'local');
define('BSRE_RETENTION_LAB', true);
define('BSRE_RETENTION_APPLY_ENABLED', true);
require '/opt/wordpress/wp-load.php';
require '/opt/lab/g1-retention/store.php';
require '/opt/lab/purpose/purpose-attribution.php';
require '/opt/lab/retention-admission/retention-admission.php';
require '/opt/lab/purpose-retention/PreferenceRetirement.php';

use BSRE\PurposeAttribution as P;
use BSRE\PurposeRetention\PreferenceRetirement as Retirement;

const G1C_PREFIX = 'purpose_retention_synthetic_';
const G1C_CLOCK = 1794733200; // Fixed synthetic retirement clock, not a live date claim.
const G1C_TABLES = ['bsre_consent_state','bsre_consent_history','bsre_consent_captures',
    'bsre_retention_audit','bsre_restore_audit','bsre_retirement_checkpoint',
    'bsre_retirement_ledger','bsre_retirement_floor','bsre_ledger_compaction_audit'];

if (wp_get_environment_type() !== 'local' || home_url() !== 'http://bsre.invalid'
    || DB_NAME !== 'bsre_synthetic' || DB_HOST !== 'localhost:/tmp/bsre.sock'
    || DB_USER !== 'root' || DB_PASSWORD !== '') throw new RuntimeException('G1_CONCURRENCY_ISOLATED_LAB_ONLY');
$owner = get_user_by('login', 'synthetic_owner');
if (!$owner) throw new RuntimeException('G1_CONCURRENCY_OWNER_MISSING');
wp_set_current_user($owner->ID);
// No HTTP or mail is part of this repository-only lane, even on failure.
add_filter('pre_http_request', function () { throw new RuntimeException('G1_CONCURRENCY_HTTP_FORBIDDEN'); }, PHP_INT_MAX);
add_filter('pre_wp_mail', function () { throw new RuntimeException('G1_CONCURRENCY_MAIL_FORBIDDEN'); }, PHP_INT_MAX);

/** Observes real statements; neither results nor SQL text are substituted. */
final class G1ConcurrencyDb extends wpdb {
    public $beforeCommit = null;
    public $beforeStateQuery = null;
    public array $events = [];
    public int $stateLocks = 0;
    public bool $timeout = false;
    public function query($query) {
        if ($query === 'COMMIT' && $this->beforeCommit !== null) {
            $callback = $this->beforeCommit; $this->beforeCommit = null;
            $callback();
        }
        $stateLock = is_string($query) && str_contains($query, G1C_PREFIX.'bsre_consent_state') && str_contains($query, 'FOR UPDATE');
        if ($stateLock && $this->beforeStateQuery !== null) {
            $callback = $this->beforeStateQuery; $this->beforeStateQuery = null;
            $callback();
        }
        $result = parent::query($query);
        if ($result === false && mysqli_errno($this->dbh) === 1205) $this->timeout = true;
        if ($stateLock && $result !== false) $this->stateLocks++;
        if (in_array($query, ['START TRANSACTION','COMMIT','ROLLBACK'], true)) $this->events[] = [$query, $result !== false];
        return $result;
    }
}
function g1c_db(): G1ConcurrencyDb {
    $db = new G1ConcurrencyDb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->set_prefix(G1C_PREFIX); $db->suppress_errors(true);
    if ($db->query('SET SESSION innodb_lock_wait_timeout=8') === false) throw new RuntimeException('G1_CONCURRENCY_TIMEOUT_SETUP');
    return $db;
}
function g1c_send($pipe, array $value): void {
    $line = json_encode($value, JSON_THROW_ON_ERROR)."\n";
    if (strlen($line) > 65536 || fwrite($pipe, $line) !== strlen($line) || !fflush($pipe)) throw new RuntimeException('G1_CONCURRENCY_PIPE_WRITE');
}
function g1c_read($pipe): array {
    stream_set_timeout($pipe, 10);
    $line = fgets($pipe, 65538);
    if ($line === false || strlen($line) > 65536 || !str_ends_with($line, "\n")) throw new RuntimeException('G1_CONCURRENCY_PIPE_READ');
    $value = json_decode($line, true, 24, JSON_THROW_ON_ERROR);
    if (!is_array($value)) throw new RuntimeException('G1_CONCURRENCY_PIPE_SHAPE');
    return $value;
}
function g1c_check(string $name, bool $ok): void {
    // Emit diagnostic evidence BEFORE an assertion can terminate this trial.
    echo json_encode(['phase'=>'g1_concurrency_check','check'=>$name,'pass'=>$ok], JSON_THROW_ON_ERROR)."\n";
    if (!$ok) throw new RuntimeException('G1_CONCURRENCY_CHECK:'.$name);
}
function g1c_has_event(G1ConcurrencyDb $db, string $event): bool { return in_array([$event,true], $db->events, true); }
function g1c_count(G1ConcurrencyDb $db, string $table): int {
    if (!in_array($table, G1C_TABLES, true)) throw new RuntimeException('G1_CONCURRENCY_TABLE_SCOPE');
    $db->last_error = ''; $n = $db->get_var('SELECT COUNT(*) FROM '.G1C_PREFIX.$table);
    if ($db->last_error !== '' || $n === null) throw new RuntimeException('G1_CONCURRENCY_COUNT_FAILED');
    return (int)$n;
}

if ($worker) {
    $init = g1c_read(STDIN);
    if (array_keys($init) !== ['capture','plan'] || !is_array($init['capture']) || !is_array($init['plan'])) throw new RuntimeException('G1_CONCURRENCY_INIT');
    $db = g1c_db(); $id = (int)$db->get_var('SELECT CONNECTION_ID()');
    g1c_send(STDOUT, ['op'=>'ready','connection'=>$id]);
    $db->beforeStateQuery = function () { g1c_send(STDOUT, ['op'=>'attempting_state_lock']); };
    $result = null; $error = null;
    try {
        if ($argv[2] === 'stage') $result = (new P\WpConsentRepository($db))->stage($init['capture']);
        else {
            $retirement = new Retirement($db, fn() => G1C_CLOCK);
            $result = $retirement->apply($init['plan'], Retirement::approval($init['plan']));
        }
    } catch (Throwable $e) {
        // Report only finite observed identities over the owned private pipe.
        // An unrelated error cannot satisfy a retirement expectation.
        $message = $e->getMessage();
        $error = in_array($message, ['Consent evidence retired.','PLAN_STALE_OR_ALTERED'], true)
            ? $message : 'G1_CONCURRENCY_UNEXPECTED_EXCEPTION';
    }
    g1c_send(STDOUT, ['op'=>'result','error'=>$error,'committed'=>g1c_has_event($db,'COMMIT'),
        'rollback'=>g1c_has_event($db,'ROLLBACK'),'state_lock'=>$db->stateLocks > 0,'timeout'=>$db->timeout,
        'capture_staged'=>is_array($result) && ($result['state'] ?? '') === 'STAGED',
        'deleted_rows'=>is_array($result) ? ($result['deleted_rows'] ?? null) : null]);
    $db->close(); exit(0);
}

/** Own exactly one child and terminate it on every exceptional exit. */
final class G1ConcurrencyChild {
    private $process = null;
    private array $pipes = [];
    public int $connection;
    public function __construct(string $operation, array $capture, array $plan) {
        if (!in_array($operation, ['stage','retire'], true)) throw new RuntimeException('G1_CONCURRENCY_FIXED_CHILD');
        $this->process = proc_open(['php','-d','sendmail_path=/bin/false',__FILE__,'worker',$operation],
            [0=>['pipe','r'],1=>['pipe','w'],2=>STDERR], $this->pipes);
        if (!is_resource($this->process)) throw new RuntimeException('G1_CONCURRENCY_CHILD_START');
        try {
            g1c_send($this->pipes[0], ['capture'=>$capture,'plan'=>$plan]);
            $ready = g1c_read($this->pipes[1]);
            if (($ready['op'] ?? '') !== 'ready' || !is_int($ready['connection'] ?? null) || $ready['connection'] < 1) throw new RuntimeException('G1_CONCURRENCY_CHILD_READY');
            $this->connection = $ready['connection'];
            if (g1c_read($this->pipes[1]) !== ['op'=>'attempting_state_lock']) throw new RuntimeException('G1_CONCURRENCY_CHILD_BARRIER');
        } catch (Throwable $e) { $this->stop(); throw $e; }
    }
    public function finish(): array {
        try {
            $result = g1c_read($this->pipes[1]);
            if (($result['op'] ?? '') !== 'result') throw new RuntimeException('G1_CONCURRENCY_CHILD_RESULT');
            // Child has emitted its final small frame; bound the actual exit too.
            $deadline = hrtime(true) + 2000000000;
            do {
                $status = proc_get_status($this->process);
                if (!$status['running']) break;
                usleep(10000);
            } while (hrtime(true) < $deadline);
            if ($status['running'] || $status['exitcode'] !== 0) throw new RuntimeException('G1_CONCURRENCY_CHILD_EXIT');
            foreach ($this->pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
            proc_close($this->process); $this->process = null; $this->pipes = [];
            return $result;
        } finally { $this->stop(); }
    }
    public function stop(): void {
        if (is_resource($this->process)) {
            $status = proc_get_status($this->process);
            if ($status['running']) proc_terminate($this->process, 9);
            foreach ($this->pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
            proc_close($this->process);
        }
        $this->process = null; $this->pipes = [];
    }
    public function __destruct() { $this->stop(); }
}

/** Poll actual lock metadata, not elapsed sleep, while the parent holds its txn. */
function g1c_wait(G1ConcurrencyDb $db, int $child): array {
    $parent = (int)$db->get_var('SELECT CONNECTION_ID()');
    if ($parent < 1 || $child === $parent) throw new RuntimeException('G1_CONCURRENCY_DISTINCT_CONNECTIONS');
    $start = hrtime(true); $polls = 0;
    do {
        $db->last_error = '';
        $rows = $db->get_results($db->prepare("SELECT r.trx_query AS waiting_query FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX r ON r.trx_id=w.requesting_trx_id JOIN information_schema.INNODB_TRX b ON b.trx_id=w.blocking_trx_id WHERE r.trx_mysql_thread_id=%d AND b.trx_mysql_thread_id=%d", $child, $parent), ARRAY_A);
        if ($db->last_error !== '' || !is_array($rows)) throw new RuntimeException('G1_CONCURRENCY_LOCK_METADATA_UNAVAILABLE');
        $polls++;
        foreach ($rows as $row) if (is_string($row['waiting_query']) && str_contains($row['waiting_query'], G1C_PREFIX.'bsre_consent_state') && str_contains($row['waiting_query'], 'FOR UPDATE')) {
            return ['real_wait'=>true,'distinct_connections'=>true,'polls'=>$polls,'wait_observation_ms'=>(hrtime(true)-$start)/1000000];
        }
        usleep(20000); // Backoff only; metadata row is the required evidence.
    } while (hrtime(true)-$start < 4000000000);
    throw new RuntimeException('G1_CONCURRENCY_EXPECTED_REAL_WAIT_MISSING');
}

/** Fixed disposable fixture reset, never counted as policy retirement/apply. */
function g1c_fixture(G1ConcurrencyDb $db): array {
    global $wpdb;
    foreach (G1C_TABLES as $table) if ($db->query('DROP TABLE IF EXISTS '.G1C_PREFIX.$table) === false) throw new RuntimeException('G1_CONCURRENCY_FIXTURE_RESET');
    $original = $wpdb; $wpdb = $db;
    try { if (!P\install_consent_storage()) throw new RuntimeException('G1_CONCURRENCY_SCHEMA'); }
    finally { $wpdb = $original; }
    $retirement = new Retirement($db, fn() => G1C_CLOCK); $retirement->installLabAudit();
    $store = new P\WpConsentRepository($db);
    // Deliberately delayed known snapshot from an old synthetic choice. The
    // live consent_current freshness rules are not bypassed or called here.
    $choice = $store->choose(str_repeat('a',64), ['analytics'=>true,'ad_measurement'=>false], \BSRE\Enquiries\CONSENT_NOTICE_VERSION, 1704067200);
    $capture = ['request_id'=>'11111111-1111-4111-8111-111111111111','fingerprint'=>hash('sha256','SYNTHETIC_G1_CONCURRENCY'),
        'subject_key'=>$choice['subject_key'],'original_revision'=>(int)$choice['revision'],'decision_version'=>$choice['receipt'],
        'notice_version'=>\BSRE\Enquiries\CONSENT_NOTICE_VERSION,'analytics'=>1,'ad_measurement'=>0,'preference_expires_at'=>(int)$choice['expires_at'],
        'eligible'=>1,'known'=>1,'created_at'=>1704067201,'uncertain'=>0,'click_capture_state'=>'NOT_PERMITTED',
        'gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0];
    $plan = $retirement->preview();
    g1c_check('fixture_exact_two_policy_rows', count($plan['eligible']) === 2);
    $db->events = []; $db->stateLocks = 0;
    return [$store,$retirement,$capture,$plan];
}

$started = hrtime(true); $db = g1c_db();
try {
    foreach (['retire_commit','stage_commit','retire_rollback','stage_rollback'] as $case) {
        if (hrtime(true)-$started > 60000000000) throw new RuntimeException('G1_CONCURRENCY_TOTAL_BUDGET');
        [$store,$retirement,$capture,$plan] = g1c_fixture($db);
        $child = null; $wait = null; $error = null; $parentResult = null;
        $retireFirst = str_starts_with($case, 'retire_');
        $rollback = str_ends_with($case, '_rollback');
        $db->beforeCommit = function () use ($db,$case,$retireFirst,$rollback,$capture,$plan,&$child,&$wait) {
            $child = new G1ConcurrencyChild($retireFirst ? 'stage' : 'retire', $capture, $plan);
            $wait = g1c_wait($db, $child->connection);
            // Persist real wait/timing evidence before any failure injection.
            echo json_encode(['phase'=>'g1_concurrency_wait','case'=>$case]+$wait, JSON_THROW_ON_ERROR)."\n";
            if ($rollback) throw new RuntimeException('G1_CONCURRENCY_TEST_ROLLBACK');
        };
        try {
            try {
                $parentResult = $retireFirst ? $retirement->apply($plan, Retirement::approval($plan)) : $store->stage($capture);
            } catch (Throwable $e) { $error = $e->getMessage(); }
            g1c_check($case.'_real_lock_wait', is_array($wait) && $wait['real_wait'] && $wait['distinct_connections']);
            g1c_check($case.'_parent_outcome', $rollback ? $error === 'G1_CONCURRENCY_TEST_ROLLBACK' && g1c_has_event($db,'ROLLBACK') && !g1c_has_event($db,'COMMIT') : $error === null && g1c_has_event($db,'COMMIT') && !g1c_has_event($db,'ROLLBACK'));
            $result = $child->finish();
            $expectedError = $retireFirst ? ($rollback ? null : 'Consent evidence retired.') : ($rollback ? null : 'PLAN_STALE_OR_ALTERED');
            g1c_check($case.'_child_exact_outcome', $result['error'] === $expectedError && $result['timeout'] === false
                && $result['committed'] === ($expectedError === null) && $result['rollback'] === ($expectedError !== null));
            $deleted = ($retireFirst && !$rollback) || (!$retireFirst && $rollback);
            g1c_check($case.'_policy_rows', g1c_count($db,'bsre_consent_state') === ($deleted ? 0 : 1) && g1c_count($db,'bsre_consent_history') === ($deleted ? 0 : 1));
            g1c_check($case.'_capture_count', g1c_count($db,'bsre_consent_captures') === ($deleted ? 0 : 1));
            g1c_check($case.'_audit_ledger_atomic', g1c_count($db,'bsre_retention_audit') === ($deleted ? 1 : 0) && g1c_count($db,'bsre_retirement_ledger') === ($deleted ? 1 : 0));
            $anchor = $retirement->ledgerAnchor();
            g1c_check($case.'_verified_ledger_anchor', (int)$anchor['sequence'] === ($deleted ? 1 : 0) && ($deleted ? $anchor['hash'] !== str_repeat('0',64) : $anchor['hash'] === str_repeat('0',64)));
            if ($deleted) {
                g1c_check($case.'_actual_apply_deleted_two', ($retireFirst ? $parentResult['deleted_rows'] : $result['deleted_rows']) === 2);
                $audit = $db->get_row('SELECT * FROM '.G1C_PREFIX.'bsre_retention_audit', ARRAY_A);
                g1c_check($case.'_exact_plan_audit', is_array($audit) && $audit['plan_hash'] === hash('sha256',json_encode($plan,JSON_THROW_ON_ERROR)) && (int)$audit['deleted_rows'] === 2 && (int)$audit['actor'] === $owner->ID && (int)$audit['applied_at'] === G1C_CLOCK);
            } else {
                $row = $db->get_row($db->prepare('SELECT * FROM '.G1C_PREFIX.'bsre_consent_captures WHERE request_id=%s', $capture['request_id']), ARRAY_A);
                g1c_check($case.'_staged_original_preserved', is_array($row) && $row['state'] === 'STAGED' && $row['decision_version'] === $capture['decision_version'] && $row['fingerprint'] === $capture['fingerprint'] && (int)$row['known'] === 1 && (int)$row['purpose_version'] === 0);
                $next = $retirement->preview();
                g1c_check($case.'_new_plan_holds_inflight', $next['eligible'] === []);
            }
            echo json_encode(['phase'=>'g1_concurrency_case','case'=>$case,'pass'=>true,'policy_deleted'=>$deleted,'repository_only'=>true], JSON_THROW_ON_ERROR)."\n";
        } finally {
            $db->beforeCommit = null;
            if ($child instanceof G1ConcurrencyChild) $child->stop();
            $db->query('ROLLBACK');
        }
    }
    echo json_encode(['phase'=>'g1_retention_concurrency','cases'=>4,'pass'=>true,'elapsed_ms'=>(hrtime(true)-$started)/1000000,
        'limits'=>'Synthetic direct repository snapshots and actual guarded policy apply; not REST/current-choice, provider or production acceptance.'], JSON_THROW_ON_ERROR)."\n";
} finally { $db->close(); }
