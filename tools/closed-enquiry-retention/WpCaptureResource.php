<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;
require_once __DIR__ . '/LabAdapters.php';

/** Concrete reviewed WordPress capture SQL provider; deployment remains forbidden. */
final class WpCaptureResource implements ResourceAdapter
{
    public const PREFIX = 'closed_capture_synthetic_';
    private const SOURCE = '7ccb7fdf0d88a3d2b1d54832f61c71bfcc025554bebf3927d7f5ce0c72f12262';
    private const CONTRACT = 'bsre-wp-capture-resource-v1';
    private const SCHEMA = [
        'request_id'=>'char(36)', 'fingerprint'=>'char(64)', 'subject_key'=>'char(64)',
        'original_revision'=>'bigint unsigned', 'decision_version'=>'char(32)', 'notice_version'=>'varchar(64)',
        'analytics'=>'tinyint unsigned', 'ad_measurement'=>'tinyint unsigned', 'personalization'=>'tinyint unsigned',
        'preference_expires_at'=>'bigint unsigned', 'eligible'=>'tinyint unsigned', 'known'=>'tinyint unsigned',
        'created_at'=>'bigint unsigned', 'state'=>'varchar(16)', 'uncertain'=>'tinyint unsigned',
        'delivery_pending'=>'tinyint unsigned', 'click_capture_state'=>'varchar(16)',
        'gclid_first'=>'varchar(256)', 'gclid_last'=>'varchar(256)',
        'gclid_first_captured_ms'=>'bigint unsigned', 'gclid_last_captured_ms'=>'bigint unsigned',
        'lead_id'=>'varchar(64)', 'event_id'=>'varchar(64)',
    ];
    private string $table;
    private ?string $activeRequest = null;
    private bool $mutating = false;

    public function __construct(private LeaseBoundWpdb $db, private LabSqlJournal $journal)
    {
        $this->guard();
        $this->db->suppress_errors(true);
        $this->table = self::PREFIX . 'bsre_consent_captures';
    }

    private function guard(): void
    {
        if (!defined('BSRE_CLOSED_RETENTION_LAB') || BSRE_CLOSED_RETENTION_LAB !== true
            || !function_exists('wp_get_environment_type') || wp_get_environment_type() !== 'local'
            || !function_exists('home_url') || home_url() !== 'http://bsre.invalid'
            || $this->db->prefix !== self::PREFIX) throw new Failure('CAPTURE_ISOLATED_LAB_ONLY');
        if ((defined('SAVEQUERIES') && SAVEQUERIES) || ($this->db->save_queries ?? false)) throw new Failure('CAPTURE_QUERY_LOGGING_UNVERIFIED');
        if (!class_exists('BSRE\\Enquiries\\WpConsentRepository', false)) throw new Failure('CAPTURE_SOURCE_UNVERIFIED');
        $path = (new \ReflectionClass('BSRE\\Enquiries\\WpConsentRepository'))->getFileName();
        if (!is_string($path) || !is_file($path) || !hash_equals(self::SOURCE, (string) @hash_file('sha256', $path))) {
            throw new Failure('CAPTURE_SOURCE_UNVERIFIED');
        }
    }

    private function custody(): void
    {
        $this->guard();
        if ($this->activeRequest === null) throw new Failure('CAPTURE_OPERATION_SCOPE_REQUIRED');
        $this->journal->assertProviderCustody($this->db, $this->activeRequest, $this->mutating);
    }

    private function query(string $sql): int
    {
        $this->custody();
        $this->db->last_error = '';
        $result = $this->db->query($sql);
        if ($result === false || $this->db->last_error !== '') throw new Failure('CAPTURE_STORAGE_UNVERIFIED');
        return (int) $result;
    }

    private function rows(string $sql): array
    {
        $this->custody();
        $this->db->last_error = '';
        $rows = $this->db->get_results($sql, ARRAY_A);
        if ($this->db->last_error !== '' || !is_array($rows)) throw new Failure('CAPTURE_STORAGE_UNVERIFIED');
        return $rows;
    }

    private function scalar(string $sql): string
    {
        $this->custody();
        $this->db->last_error = '';
        $value = $this->db->get_var($sql);
        if ($this->db->last_error !== '' || (!is_string($value) && !is_int($value))) throw new Failure('CAPTURE_STORAGE_UNVERIFIED');
        return (string) $value;
    }

    private function schema(): void
    {
        // Restricted metadata views can hide triggers or foreign children. Require direct
        // global visibility; role/schema-only grants are not inferred or expanded here.
        $visible = $this->scalar("SELECT COUNT(DISTINCT PRIVILEGE_TYPE) FROM information_schema.USER_PRIVILEGES"
            . " WHERE GRANTEE=CONCAT(QUOTE(SUBSTRING_INDEX(CURRENT_USER(),'@',1)),'@',QUOTE(SUBSTRING_INDEX(CURRENT_USER(),'@',-1)))"
            . " AND PRIVILEGE_TYPE IN ('SELECT','TRIGGER')");
        if ($visible !== '2') throw new Failure('CAPTURE_METADATA_VISIBILITY_UNVERIFIED');
        $status = $this->rows($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s', $this->table));
        if (count($status) !== 1 || strtolower((string) ($status[0]['Engine'] ?? '')) !== 'innodb') {
            throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
        }
        $columns = $this->rows("SHOW FULL COLUMNS FROM {$this->table}");
        if (count($columns) !== count(self::SCHEMA)) throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
        foreach (array_keys(self::SCHEMA) as $index => $field) {
            $column = $columns[$index];
            $type = strtolower((string) ($column['Type'] ?? ''));
            $type = preg_replace('/^(bigint|tinyint)\([0-9]+\)/', '$1', $type);
            if (($column['Field'] ?? null) !== $field || $type !== self::SCHEMA[$field]
                || ($column['Null'] ?? null) !== 'NO' || ($column['Extra'] ?? null) !== '') {
                throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
            }
        }
        $indices = [];
        foreach ($this->rows("SHOW INDEX FROM {$this->table}") as $index) {
            $name = $index['Key_name'] ?? '';
            $sequence = (string) ($index['Seq_in_index'] ?? '');
            if (!in_array($name, ['PRIMARY', 'subject_revision', 'lead_id'], true)
                || !preg_match('/^[12]$/D', $sequence) || isset($indices[$name][$sequence])
                || (string) ($index['Non_unique'] ?? '') !== ($name === 'PRIMARY' ? '0' : '1')
                || ($index['Sub_part'] ?? null) !== null || strtoupper((string) ($index['Index_type'] ?? '')) !== 'BTREE') {
                throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
            }
            $indices[$name][(int) $sequence] = $index['Column_name'];
        }
        foreach ($indices as &$columns) ksort($columns);
        unset($columns);
        ksort($indices);
        $expected = ['PRIMARY'=>[1=>'request_id'], 'lead_id'=>[1=>'lead_id'], 'subject_revision'=>[1=>'subject_key',2=>'original_revision']];
        if ($indices !== $expected) throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
        if ($this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.TRIGGERS'
                . ' WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE=%s', $this->table)) !== '0'
            || $this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE'
                . ' WHERE REFERENCED_TABLE_NAME IS NOT NULL AND ((TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s)'
                . ' OR (REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME=%s))', $this->table, $this->table)) !== '0') {
            throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
        }
    }

    /** No nested transaction and no transparent reconnect can weaken the row locks. */
    private function transaction(string $key, callable $operation, bool $mutation = false)
    {
        $this->guard();
        self::uuid($key);
        if ($this->activeRequest !== null) throw new Failure('CAPTURE_OPERATION_BUSY');
        $this->activeRequest = $key;
        $this->mutating = $mutation;
        try {
            $this->custody();
            if ($this->scalar('SELECT @@session.in_transaction') !== '0') throw new Failure('CAPTURE_TRANSACTION_ALREADY_ACTIVE');
            if (!in_array(strtoupper($this->scalar('SELECT @@session.tx_isolation')), ['REPEATABLE-READ', 'SERIALIZABLE'], true)) {
                throw new Failure('CAPTURE_TRANSACTION_ISOLATION_UNVERIFIED');
            }
            $committing = false;
            try {
                $this->query('START TRANSACTION');
                // Take a transaction-duration metadata lock before inspecting the engine/schema.
                // An ALTER must not replace the reviewed InnoDB table between that check and DELETE.
                $this->rows($this->db->prepare("SELECT request_id FROM {$this->table} WHERE request_id=%s LIMIT 2 FOR UPDATE", $key));
                $this->schema();
                $result = $operation();
                $committing = true;
                $this->query('COMMIT');
                if ($this->scalar('SELECT @@session.in_transaction') !== '0') throw new Failure('CAPTURE_COMMIT_UNCERTAIN');
                $this->custody();
                return $result;
            } catch (\Throwable $error) {
                // Rollback is attempted once; an uncertain commit is never retried here.
                // Do not let a failed semantic recheck prevent rollback on the original live connection.
                $rolledBack = false;
                try {
                    $this->db->last_error = '';
                    if ($this->db->query('ROLLBACK') !== false && $this->db->last_error === '') {
                        $this->db->last_error = '';
                        $state = $this->db->get_var('SELECT @@session.in_transaction');
                        $rolledBack = $this->db->last_error === '' && (string) $state === '0';
                    }
                } catch (\Throwable $ignored) {}
                if ($committing) throw new Failure('CAPTURE_COMMIT_UNCERTAIN');
                if (!$rolledBack) throw new Failure('CAPTURE_ROLLBACK_UNCERTAIN');
                if ($error instanceof Failure) throw $error;
                throw new Failure('CAPTURE_STORAGE_UNVERIFIED');
            }
        } finally {
            $this->activeRequest = null;
            $this->mutating = false;
        }
    }

    private static function uuid(string $value): void
    {
        if (!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $value)) {
            throw new Failure('CAPTURE_IDENTITY_INVALID');
        }
    }

    /** Canonical SQL types preserve every reviewed column without returning its private values. */
    private static function normalize(array $row): array
    {
        if (array_keys($row) !== array_keys(self::SCHEMA)) throw new Failure('CAPTURE_ROW_INVALID');
        foreach (self::SCHEMA as $field => $type) {
            $value = $row[$field];
            if (str_ends_with($type, ' unsigned')) {
                if (is_string($value) && preg_match('/^(0|[1-9][0-9]*)$/D', $value)
                    && (strlen($value) < strlen((string) PHP_INT_MAX)
                        || (strlen($value) === strlen((string) PHP_INT_MAX) && strcmp($value, (string) PHP_INT_MAX) <= 0))) $value = (int) $value;
                if (!is_int($value) || $value < 0 || ($type === 'tinyint unsigned' && $value > 1)) throw new Failure('CAPTURE_ROW_INVALID');
            } else {
                preg_match('/\(([0-9]+)\)/', $type, $width);
                if (!is_string($value) || strlen($value) > (int) $width[1] || preg_match('/[\x00-\x1f\x7f]/', $value)) throw new Failure('CAPTURE_ROW_INVALID');
            }
            $row[$field] = $value;
        }
        self::uuid($row['request_id']);
        foreach (['fingerprint'=>64, 'decision_version'=>32] as $field => $length) {
            if (!preg_match('/^[a-f0-9]{' . $length . '}$/D', $row[$field])) throw new Failure('CAPTURE_ROW_INVALID');
        }
        if ($row['subject_key'] !== '' && !preg_match('/^[a-f0-9]{64}$/D', $row['subject_key'])) throw new Failure('CAPTURE_ROW_INVALID');
        foreach (['lead_id'=>'BSRE-', 'event_id'=>'evt_'] as $field => $prefix) {
            if (!str_starts_with($row[$field], $prefix)) throw new Failure('CAPTURE_LINK_UNVERIFIED');
            self::uuid(substr($row[$field], strlen($prefix)));
        }
        if ($row['state'] !== 'ACCEPTED' || $row['delivery_pending'] !== 0) throw new Failure('CAPTURE_DELIVERY_UNVERIFIED');
        if ($row['personalization'] !== 0 || $row['notice_version'] === '' || $row['created_at'] < 1 || $row['created_at'] > time()
            || !in_array($row['click_capture_state'], ['UNAVAILABLE', 'NOT_PERMITTED', 'MISSING', 'INVALID', 'CAPTURED'], true)) {
            throw new Failure('CAPTURE_ROW_INVALID');
        }
        if (($row['known'] === 1 && ($row['subject_key'] === '' || $row['original_revision'] < 1
                || $row['preference_expires_at'] < 1))
            || ($row['known'] === 0 && ($row['analytics'] !== 0 || $row['ad_measurement'] !== 0
                || $row['eligible'] !== 0 || $row['preference_expires_at'] !== 0))) throw new Failure('CAPTURE_ROW_INVALID');
        if (in_array($row['click_capture_state'], ['MISSING', 'INVALID', 'CAPTURED'], true)
            && ($row['known'] !== 1 || $row['eligible'] !== 1 || $row['ad_measurement'] !== 1)) throw new Failure('CAPTURE_ROW_INVALID');
        foreach (['first', 'last'] as $touch) {
            $click = $row['gclid_' . $touch]; $stamp = $row['gclid_' . $touch . '_captured_ms'];
            if (($click === '') !== ($stamp === 0)
                || ($click !== '' && (!preg_match('/^[A-Za-z0-9._~-]{1,256}$/D', $click)
                    || $stamp < 946684800000 || $stamp > $row['created_at'] * 1000 + 300000))) throw new Failure('CAPTURE_ROW_INVALID');
            if ($click !== '' && $row['click_capture_state'] !== 'CAPTURED') throw new Failure('CAPTURE_ROW_INVALID');
        }
        if ($row['click_capture_state'] === 'CAPTURED' && $row['gclid_first'] === '' && $row['gclid_last'] === '') throw new Failure('CAPTURE_ROW_INVALID');
        // Consent refusal, expiry, QA ineligibility and uncertainty are retained facts, never approval or delivery failure.
        return $row;
    }

    private function current(string $request): ?array
    {
        self::uuid($request);
        $rows = $this->rows($this->db->prepare("SELECT * FROM {$this->table} WHERE request_id=%s LIMIT 2 FOR UPDATE", $request));
        if ($rows === []) return null;
        if (count($rows) !== 1) throw new Failure('CAPTURE_DUPLICATE_IDENTITY');
        $row = self::normalize($rows[0]);
        if ($row['request_id'] !== $request) throw new Failure('CAPTURE_IDENTITY_INVALID');
        // Lock all matching ownership/alias candidates. This is complete SQL, never a sliced client inventory.
        $owners = $this->rows($this->db->prepare("SELECT request_id FROM {$this->table} WHERE BINARY request_id<>BINARY %s"
            . ' AND (LOWER(lead_id)=%s OR LOWER(event_id)=%s) LIMIT 1 FOR UPDATE', $request, strtolower($row['lead_id']), strtolower($row['event_id'])));
        if ($owners !== []) throw new Failure('CAPTURE_SHARED_RECEIPT');
        return $row;
    }

    private static function binding(array $row): array
    {
        return ['key'=>$row['request_id'], 'request_id'=>$row['request_id'], 'request_ids'=>[$row['request_id']],
            'lead_id'=>$row['lead_id'], 'event_id'=>$row['event_id'], 'fingerprint'=>$row['fingerprint'],
            'evidence_reference'=>self::CONTRACT, 'evidence_hash'=>Workflow::digest(['contract'=>self::CONTRACT,'row'=>$row])];
    }

    public function inventory(string $requestId): array
    {
        return $this->transaction($requestId, function () use ($requestId) {
            $row = $this->current($requestId);
            return $row === null ? [] : [self::binding($row)];
        });
    }

    public function read(string $key): ?array
    {
        return $this->transaction($key, function () use ($key) {
            $row = $this->current($key);
            return $row === null ? null : self::binding($row);
        });
    }

    public function removeExact(array $binding): void
    {
        $key = $binding['key'] ?? null;
        if (!is_string($key)) throw new Failure('CAPTURE_BINDING_INVALID');
        $this->transaction($key, function () use ($key, $binding) {
            $row = $this->current($key);
            if ($row === null) throw new Failure('CAPTURE_RESOURCE_MISSING');
            if (Workflow::digest(self::binding($row)) !== Workflow::digest($binding)) throw new Failure('CAPTURE_BINDING_CHANGED');
            $where = []; $values = [];
            foreach (self::SCHEMA as $field => $type) {
                $where[] = str_ends_with($type, ' unsigned') ? "{$field}=%d" : "BINARY {$field}=BINARY %s";
                $values[] = $row[$field];
            }
            if ($this->query($this->db->prepare("DELETE FROM {$this->table} WHERE " . implode(' AND ', $where), ...$values)) !== 1) {
                throw new Failure('CAPTURE_DELETE_UNCONFIRMED');
            }
            if ($this->current($key) !== null) throw new Failure('CAPTURE_DELETE_UNCONFIRMED');
        }, true);
        if ($this->read($key) !== null) throw new Failure('CAPTURE_DELETE_UNCONFIRMED');
    }
}
