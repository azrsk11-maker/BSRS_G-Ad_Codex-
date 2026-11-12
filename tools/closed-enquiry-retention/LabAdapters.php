<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;
require_once __DIR__ . '/Workflow.php';
require_once __DIR__ . '/RetirementJournal.php';
require_once __DIR__ . '/LeaseBoundWpdb.php';

/** All provider mutations below affect only explicitly supplied synthetic arrays. */
final class MemoryResource implements ResourceAdapter
{
    public array $rows;
    public int $deletes = 0;
    public $afterDelete = null;
    public $beforeDelete = null;
    public function __construct(array $rows) { $this->rows = $rows; }
    public function inventory(string $requestId): array
    {
        return array_values(array_filter($this->rows, fn($row) => $row['request_id'] === $requestId));
    }
    public function read(string $key): ?array { return $this->rows[$key] ?? null; }
    public function removeExact(array $binding): void
    {
        if ($this->beforeDelete) ($this->beforeDelete)($this, $binding);
        $actual = $this->rows[$binding['key']] ?? null;
        if ($actual === null || Workflow::digest($actual) !== Workflow::digest($binding)) throw new \RuntimeException('Synthetic compare failed');
        unset($this->rows[$binding['key']]);
        $this->deletes++;
        if ($this->afterDelete) ($this->afterDelete)($this, $binding);
    }
}

final class LabAuthority implements Authority
{
    public ?string $approved = null;
    public array $actions = ['PURGE'];
    public array $receipts = [];
    public $afterManualMail = null;
    public function canReview(string $actor): bool { return $actor === 'synthetic-owner'; }
    public function canApply(string $actor, string $planDigest, int $now, string $action): bool
    {
        return $this->canReview($actor) && in_array($action, $this->actions, true)
            && $this->approved !== null && hash_equals($this->approved, $planDigest);
    }
    public function mailReceipt(string $actor, string $planDigest, string $messageId): ?array
    {
        return $this->canReview($actor) ? ($this->receipts[$planDigest][$messageId] ?? null) : null;
    }
}

final class MemoryJournal implements Journal, ClosureWriter, RetirementWriter
{
    use RetirementJournal;
    public array $closures = [];
    public array $journals = [];
    public bool $incomplete = false;
    public bool $markerFails = false;
    public int $expiredUnresolved = 0;
    public ?string $floor = null;
    public $beforeSave = null;
    private array $locks = [];
    public function locked(string $closureId, callable $operation)
    {
        if ($this->locks !== []) throw new Failure('CLOSURE_LEASE_BUSY');
        $this->locks[$closureId] = true;
        try { return $operation(); } finally { unset($this->locks[$closureId]); }
    }
    public function closure(string $closureId): ?array { return $this->closures[$closureId] ?? null; }
    public function replaceClosure(array $before, array $after): void
    {
        $id = $before['closure_id'];
        $this->assertClosureLease($id);
        $this->assertRetirementOpen();
        $this->assertNoClosureJobs($id);
        $this->writeClosure($before, $after);
    }
    private function assertClosureLease(string $id): void
    {
        if (!isset($this->locks[$id])) throw new Failure('CLOSURE_LEASE_REQUIRED');
    }
    private function unresolvedRetirementCount(): int
    {
        if ($this->expiredUnresolved < 0) throw new Failure('RETIREMENT_CUSTODY_RECONCILIATION_REQUIRED');
        return $this->expiredUnresolved;
    }
    private function assertNoClosureJobs(string $id, ?string $except = null): void
    {
        foreach ($this->journals as $key => $job) {
            if ($key === $except) continue;
            $bound = is_array($job) && is_array($job['plan'] ?? null) ? ($job['plan']['closure_id'] ?? null) : null;
            if (!is_string($bound) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $bound)
                || $bound === $id) throw new Failure('CLOSURE_JOB_RECONCILIATION_REQUIRED');
        }
    }
    private function writeClosure(array $before, array $after): void
    {
        $id = $before['closure_id'];
        if ($this->closure($id) !== $before || ($after['closure_id'] ?? null) !== $id
            || ($after['revision'] ?? null) !== $before['revision'] + 1) throw new Failure('CLOSURE_REVISION_CONFLICT');
        $this->closures[$id] = $after;
        if ($this->closure($id) !== $after) throw new Failure('CLOSURE_WRITE_UNCONFIRMED');
    }
    public function journal(string $planId): ?array { return $this->journals[$planId] ?? null; }
    public function save(array &$record): void
    {
        if ($this->beforeSave) ($this->beforeSave)($this, $record);
        $old = $this->journals[$record['plan']['digest']] ?? null;
        if ($record['revision'] !== ($old['revision'] ?? 0)) throw new \RuntimeException('JOURNAL_REVISION_CONFLICT');
        $record['revision']++;
        $this->journals[$record['plan']['digest']] = $record;
    }
    public function markHistoryIncomplete(): void { $this->assertCurrentLease(); if (!$this->markerFails) $this->incomplete = true; }
    public function historyIncomplete(): bool { return $this->incomplete; }
    public function pinAdmissionFloor(string $policyHash): void { $this->assertCurrentLease(); $this->floor ??= $policyHash; }
    public function admissionFloor(): ?string { return $this->floor; }
    private function assertCurrentLease(): void
    {
        if (count($this->locks) !== 1) throw new Failure('CLOSURE_LEASE_REQUIRED');
        $this->assertClosureLease((string) array_key_first($this->locks));
    }
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void
    {
        $this->assertClosureLease($closureId);
        unset($this->journals[$planId]);
        if ($keepClosure) $this->expiredUnresolved++;
        else unset($this->closures[$closureId]);
    }
}

/** Explicit synthetic readback, with no production enforcement claim. */
final class LabAdmission implements Admission
{
    public array $value;
    public function __construct(int $now)
    {
        $gate = ['contract' => 'bsre-retention-admission-v1', 'mode' => 'ENFORCED',
            'generation' => str_repeat('a', 64), 'activated_at' => $now - 1000,
            'max_age_seconds' => 900, 'audience' => str_repeat('b', 64)];
        $this->value = ['wp' => $gate + ['routes_installed' => true, 'store_installed' => true], 'receiver' => $gate,
            'source_hashes' => ['wp' => str_repeat('c', 64), 'receiver' => str_repeat('d', 64)],
            'restore_policy_hash' => str_repeat('f', 64),
            'evidence_reference' => 'synthetic-runtime-only', 'evidence_hash' => str_repeat('e', 64),
            'observed_at' => $now, 'expires_at' => $now + 300];
    }
    public function readback(int $now): ?array { return $this->value; }
    public function refresh(int $now): void { $this->value['observed_at'] = $now; $this->value['expires_at'] = $now + 300; }
}

/** MariaDB journal with committed intents and a connection-owned closure lease. */
final class LabSqlJournal implements Journal, ClosureWriter, RetirementWriter
{
    use RetirementJournal;
    private $db;
    private string $prefix;
    private array $leases = [];
    private static array $custodyLeases = [];
    public function __construct($db)
    {
        if (!defined('BSRE_CLOSED_RETENTION_LAB') || BSRE_CLOSED_RETENTION_LAB !== true
            || wp_get_environment_type() !== 'local' || home_url() !== 'http://bsre.invalid'
            || !($db instanceof LeaseBoundWpdb)
            || !in_array($db->prefix, ['closed_retention_synthetic_', 'owner_retirement_synthetic_'], true)) throw new \RuntimeException('ISOLATED_LAB_ONLY');
        $this->db = $db;
        $this->db->suppress_errors(true);
        $this->prefix = $db->prefix;
    }
    public function install(): void
    {
        foreach (['closures' => 'id char(36) PRIMARY KEY, body mediumtext NOT NULL',
            'jobs' => 'id char(64) PRIMARY KEY, revision bigint unsigned NOT NULL, body mediumtext NOT NULL',
            'meta' => 'id tinyint PRIMARY KEY, incomplete tinyint NOT NULL, expired_unresolved bigint unsigned NOT NULL, admission_floor char(64) NULL'] as $name => $columns) {
            $this->query("CREATE TABLE IF NOT EXISTS {$this->prefix}{$name} ($columns) ENGINE=InnoDB");
        }
        $this->query("INSERT IGNORE INTO {$this->prefix}meta VALUES (1,0,0,NULL)");
    }
    public function locked(string $closureId, callable $operation)
    {
        $name = 'bsre-closed-' . substr(hash('sha256', $closureId), 0, 40);
        $custody = 'bsre-custody-' . substr(hash('sha256', $this->prefix), 0, 40);
        // Static process guard also prevents GET_LOCK reentrancy through another adapter on the same connection.
        if ($this->leases !== [] || isset(self::$custodyLeases[$custody]) || $this->db->custodyIsActive()) throw new Failure('CLOSURE_LEASE_BUSY');
        if ((string) $this->db->get_var($this->db->prepare('SELECT GET_LOCK(%s,0)', $custody)) !== '1') throw new Failure('CLOSURE_LEASE_BUSY');
        self::$custodyLeases[$custody] = true; $closureHeld = false;
        try {
            $this->db->beginCustody();
            if ((string) $this->db->get_var($this->db->prepare('SELECT IS_USED_LOCK(%s)', $custody)) !== $this->db->custodyConnectionId()) throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
            if ((string) $this->db->get_var($this->db->prepare('SELECT GET_LOCK(%s,0)', $name)) !== '1') throw new Failure('CLOSURE_LEASE_BUSY');
            $closureHeld = true; $this->leases[$closureId] = true;
            return $operation();
        } finally {
            $closureReleased = !$closureHeld || (string) $this->db->get_var($this->db->prepare('SELECT RELEASE_LOCK(%s)', $name)) === '1';
            $custodyReleased = (string) $this->db->get_var($this->db->prepare('SELECT RELEASE_LOCK(%s)', $custody)) === '1';
            if (!$closureReleased || !$custodyReleased) throw new Failure('RETIREMENT_CUSTODY_RELEASE_UNCONFIRMED');
            $this->db->endCustody();
            unset($this->leases[$closureId], self::$custodyLeases[$custody]);
        }
    }
    public function putClosure(array $closure): void
    {
        $this->locked($closure['closure_id'], function () use ($closure) {
            $this->assertRetirementOpen();
            $old = $this->closure($closure['closure_id']);
            if ($old !== null && $closure['revision'] !== $old['revision'] + 1) throw new \RuntimeException('CLOSURE_REVISION_CONFLICT');
            $this->query($this->db->prepare("INSERT INTO {$this->prefix}closures VALUES (%s,%s) ON DUPLICATE KEY UPDATE body=VALUES(body)",
                $closure['closure_id'], json_encode($closure, JSON_THROW_ON_ERROR)));
        });
    }
    public function closure(string $closureId): ?array { return $this->read('closures', $closureId); }
    public function replaceClosure(array $before, array $after): void
    {
        $id = $before['closure_id'];
        $this->assertClosureLease($id);
        $this->assertRetirementOpen();
        $this->assertNoClosureJobs($id);
        $this->writeClosure($before, $after);
    }
    private function assertClosureLease(string $id): void
    {
        if (!isset($this->leases[$id])) throw new Failure('CLOSURE_LEASE_REQUIRED');
        $custody = 'bsre-custody-' . substr(hash('sha256', $this->prefix), 0, 40);
        $closure = 'bsre-closed-' . substr(hash('sha256', $id), 0, 40);
        $state = $this->db->get_row($this->db->prepare('SELECT CONNECTION_ID() AS connection_id, IS_USED_LOCK(%s) AS custody_owner, IS_USED_LOCK(%s) AS closure_owner', $custody, $closure), ARRAY_A);
        $expected = $this->db->custodyConnectionId();
        if ($expected === null || !is_array($state) || (string) $state['connection_id'] !== $expected
            || (string) $state['custody_owner'] !== $expected || (string) $state['closure_owner'] !== $expected) throw new Failure('RETIREMENT_CONNECTION_LEASE_LOST');
    }
    private function unresolvedRetirementCount(): int
    {
        $this->db->last_error = '';
        $value = $this->db->get_var("SELECT expired_unresolved FROM {$this->prefix}meta WHERE id=1");
        if ($this->db->last_error !== '' || !is_scalar($value) || !preg_match('/^[0-9]{1,18}$/D', (string) $value)) throw new Failure('RETIREMENT_CUSTODY_RECONCILIATION_REQUIRED');
        return (int) $value;
    }
    private function assertNoClosureJobs(string $id, ?string $except = null): void
    {
        $this->db->last_error = '';
        $binding = "JSON_EXTRACT(body,'$.plan.closure_id')";
        $jobs = $this->db->get_var($this->db->prepare("SELECT COUNT(*) FROM {$this->prefix}jobs WHERE id<>%s AND (JSON_UNQUOTE($binding)=%s"
            . " OR JSON_TYPE($binding) IS NULL OR JSON_TYPE($binding)<>'STRING'"
            . " OR BINARY JSON_UNQUOTE($binding) NOT REGEXP '^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$')", $except ?? '', $id));
        if ($this->db->last_error !== '' || (string) $jobs !== '0') throw new Failure('CLOSURE_JOB_RECONCILIATION_REQUIRED');
    }
    private function writeClosure(array $before, array $after): void
    {
        $id = $before['closure_id'];
        if ($this->closure($id) !== $before || ($after['closure_id'] ?? null) !== $id
            || ($after['revision'] ?? null) !== $before['revision'] + 1) throw new Failure('CLOSURE_REVISION_CONFLICT');
        $result = $this->db->query($this->db->prepare("UPDATE {$this->prefix}closures SET body=%s WHERE id=%s AND BINARY body=BINARY %s",
            json_encode($after, JSON_THROW_ON_ERROR), $id, json_encode($before, JSON_THROW_ON_ERROR)));
        if ($result !== 1 || $this->closure($id) !== $after) throw new Failure('CLOSURE_WRITE_UNCONFIRMED');
    }
    public function journal(string $planId): ?array { return $this->read('jobs', $planId); }
    public function save(array &$record): void
    {
        $this->assertClosureLease($record['plan']['closure_id']);
        $next = $record;
        $next['revision']++;
        $json = json_encode($next, JSON_THROW_ON_ERROR);
        if ($record['revision'] === 0) {
            $query = $this->db->prepare("INSERT IGNORE INTO {$this->prefix}jobs VALUES (%s,%d,%s)", $record['plan']['digest'], 1, $json);
        } else {
            $query = $this->db->prepare("UPDATE {$this->prefix}jobs SET revision=%d,body=%s WHERE id=%s AND revision=%d",
                $next['revision'], $json, $record['plan']['digest'], $record['revision']);
        }
        if ($this->db->query($query) !== 1 || $this->journal($record['plan']['digest']) !== $next) throw new \RuntimeException('JOURNAL_REVISION_OR_STORAGE_CONFLICT');
        $record = $next;
    }
    public function markHistoryIncomplete(): void { $this->assertCurrentLease(); $this->query("UPDATE {$this->prefix}meta SET incomplete=1 WHERE id=1"); }
    public function historyIncomplete(): bool { return (string) $this->db->get_var("SELECT incomplete FROM {$this->prefix}meta WHERE id=1") === '1'; }
    public function pinAdmissionFloor(string $policyHash): void
    {
        $this->assertCurrentLease();
        $this->query($this->db->prepare("UPDATE {$this->prefix}meta SET admission_floor=%s WHERE id=1 AND admission_floor IS NULL", $policyHash));
    }
    public function admissionFloor(): ?string
    {
        return $this->db->get_var("SELECT admission_floor FROM {$this->prefix}meta WHERE id=1");
    }
    private function assertCurrentLease(): void
    {
        if (count($this->leases) !== 1) throw new Failure('CLOSURE_LEASE_REQUIRED');
        $this->assertClosureLease((string) array_key_first($this->leases));
    }
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void
    {
        $this->assertClosureLease($closureId);
        $this->query('START TRANSACTION');
        try {
            $this->query($this->db->prepare("DELETE FROM {$this->prefix}jobs WHERE id=%s", $planId));
            if ($keepClosure) $this->query("UPDATE {$this->prefix}meta SET expired_unresolved=expired_unresolved+1 WHERE id=1");
            else $this->query($this->db->prepare("DELETE FROM {$this->prefix}closures WHERE id=%s", $closureId));
            $this->query('COMMIT');
        } catch (\Throwable $error) { $this->db->query('ROLLBACK'); throw $error; }
    }
    private function read(string $table, string $id): ?array
    {
        $this->db->last_error = '';
        $raw = $this->db->get_var($this->db->prepare("SELECT body FROM {$this->prefix}{$table} WHERE id=%s", $id));
        if ($this->db->last_error !== '') throw new \RuntimeException('JOURNAL_STORAGE_FAILED');
        if ($raw === null) return null;
        if (!is_string($raw) || strlen($raw) > 262144) throw new \RuntimeException('JOURNAL_INVALID');
        return json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
    }
    private function query(string $sql): void
    {
        if ($this->db->query($sql) === false) throw new \RuntimeException('JOURNAL_STORAGE_FAILED');
    }
}
