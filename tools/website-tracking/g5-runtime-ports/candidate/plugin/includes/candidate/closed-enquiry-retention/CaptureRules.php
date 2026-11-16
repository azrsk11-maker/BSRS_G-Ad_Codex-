<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
use BSRE\ClosedRetention\Failure;
use BSRE\ClosedRetention\Workflow;
/** Pure rules extracted exactly; no old class guard, authority or fixture is installed here. */
trait CaptureRules
{
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
    private const PURPOSE_SCHEMA = ['purpose_version'=>'tinyint unsigned', 'purpose_hash'=>'char(64)',
        'purpose_record_hash'=>'char(64)', 'purpose_json'=>'mediumtext'];
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
        $schema = $this->columns();
        if (count($columns) !== count($schema)) throw new Failure('CAPTURE_SCHEMA_UNVERIFIED');
        foreach (array_keys($schema) as $index => $field) {
            $column = $columns[$index];
            $type = strtolower((string) ($column['Type'] ?? ''));
            $type = preg_replace('/^(bigint|tinyint)\([0-9]+\)/', '$1', $type);
            if (($column['Field'] ?? null) !== $field || $type !== $schema[$field]
                || ($column['Null'] ?? null) !== ($field === 'purpose_json' ? 'YES' : 'NO') || ($column['Extra'] ?? null) !== '') {
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

    private static function uuid(string $value): void
    {
        if (!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $value)) {
            throw new Failure('CAPTURE_IDENTITY_INVALID');
        }
    }

    /** Canonical SQL types preserve every reviewed column without returning its private values. */
    private static function normalize(array $row, bool $purpose = false): array
    {
        $schema = self::SCHEMA + ($purpose ? self::PURPOSE_SCHEMA : []);
        if (array_keys($row) !== array_keys($schema)) throw new Failure('CAPTURE_ROW_INVALID');
        foreach ($schema as $field => $type) {
            $value = $row[$field];
            if (str_ends_with($type, ' unsigned')) {
                if (is_string($value) && preg_match('/^(0|[1-9][0-9]*)$/D', $value)
                    && (strlen($value) < strlen((string) PHP_INT_MAX)
                        || (strlen($value) === strlen((string) PHP_INT_MAX) && strcmp($value, (string) PHP_INT_MAX) <= 0))) $value = (int) $value;
                if (!is_int($value) || $value < 0 || ($type === 'tinyint unsigned' && $value > 1)) throw new Failure('CAPTURE_ROW_INVALID');
            } elseif ($type === 'mediumtext') {
                if ($value !== null && (!is_string($value) || strlen($value) > 48000)) throw new Failure('CAPTURE_ROW_INVALID');
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
        if ($purpose) {
            if ($row['purpose_version'] === 0) {
                if ($row['purpose_hash'] !== '' || $row['purpose_record_hash'] !== ''
                    || !in_array($row['purpose_json'], [null, ''], true)) throw new Failure('CAPTURE_PURPOSE_INVALID');
            } else {
                try { \BSRE\PurposeAttribution\assert_record($row); }
                catch (\Throwable $error) { throw new Failure('CAPTURE_PURPOSE_INVALID'); }
            }
        }
        // Consent refusal, expiry, QA ineligibility and uncertainty are retained facts, never approval or delivery failure.
        return $row;
    }

    private static function binding(array $row): array
    {
        return ['key'=>$row['request_id'], 'request_id'=>$row['request_id'], 'request_ids'=>[$row['request_id']],
            'lead_id'=>$row['lead_id'], 'event_id'=>$row['event_id'], 'fingerprint'=>$row['fingerprint'],
            'evidence_reference'=>self::CONTRACT, 'evidence_hash'=>Workflow::digest(['contract'=>self::CONTRACT,'row'=>$row])];
    }

    private static function exactPredicate(array $row, bool $purpose): array
    {
        $where = []; $values = [];
        foreach (self::SCHEMA + ($purpose ? self::PURPOSE_SCHEMA : []) as $field => $type) {
            if ($row[$field] === null) { $where[] = "{$field} IS NULL"; continue; }
            $where[] = str_ends_with($type, ' unsigned') ? "{$field}=%d" : "BINARY {$field}=BINARY %s";
            $values[] = $row[$field];
        }
        return [implode(' AND ', $where), $values];
    }

}
