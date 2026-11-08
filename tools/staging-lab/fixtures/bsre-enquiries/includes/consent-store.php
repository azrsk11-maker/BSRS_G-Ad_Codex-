<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

interface ConsentRepository {
    public function current(string $subject): ?array;
    public function choose(string $subject, array $flags, string $notice, int $now, bool $uncertain = false): array;
    public function stage(array $capture): array;
    public function link(string $request, string $fingerprint, string $lead, string $event): array;
    public function uncertain(string $request, string $fingerprint): void;
    public function revoked(string $subject, int $revision, string $purpose): bool;
    public function exportRows(array $requests): array;
}

/** Restricted WordPress DB sidecar. No lead bodies, contacts, keys or public reads. */
final class WpConsentRepository implements ConsentRepository {
    private $db;
    private string $state;
    private string $history;
    private string $captures;
    public function __construct($db) {
        $this->db = $db;
        $this->state = $db->prefix . 'bsre_consent_state';
        $this->history = $db->prefix . 'bsre_consent_history';
        $this->captures = $db->prefix . 'bsre_consent_captures';
    }
    private function row(string $sql): ?array {
        $this->db->last_error = '';
        $value = $this->db->get_row($sql, ARRAY_A);
        if ($this->db->last_error !== '') throw new \RuntimeException('Consent storage unavailable.');
        return is_array($value) ? $value : null;
    }
    private function query(string $sql): int {
        $result = $this->db->query($sql);
        if ($result === false) throw new \RuntimeException('Consent storage unavailable.');
        return (int) $result;
    }
    private function transaction(callable $work) {
        $this->query('START TRANSACTION');
        try { $result = $work(); $this->query('COMMIT'); return $result; }
        catch (\Throwable $e) { $this->db->query('ROLLBACK'); throw $e; }
    }
    public function current(string $subject): ?array {
        return $this->row($this->db->prepare("SELECT * FROM {$this->state} WHERE subject_key=%s", $subject));
    }
    public function choose(string $subject, array $flags, string $notice, int $now, bool $uncertain = false): array {
        return $this->transaction(function () use ($subject, $flags, $notice, $now, $uncertain) {
            $this->query($this->db->prepare("INSERT IGNORE INTO {$this->state} (subject_key,revision,receipt,analytics,ad_measurement,personalization,notice_version,changed_at,expires_at,uncertain) VALUES (%s,0,'',0,0,0,'',0,0,1)", $subject));
            $previous = $this->row($this->db->prepare("SELECT * FROM {$this->state} WHERE subject_key=%s FOR UPDATE", $subject));
            if (!$previous) throw new \RuntimeException('Consent storage unavailable.');
            if ($uncertain && (int) $previous['uncertain'] === 1 && (int) $previous['revision'] > 0) return $previous;
            $revision = (int) $previous['revision'] + 1;
            $receipt = bin2hex(random_bytes(16));
            $expires = $now + CONSENT_PREFERENCE_SECONDS;
            $this->query($this->db->prepare("INSERT INTO {$this->history} (receipt,subject_key,revision,analytics,ad_measurement,personalization,notice_version,changed_at,uncertain) VALUES (%s,%s,%d,%d,%d,0,%s,%d,%d)", $receipt, $subject, $revision, $flags['analytics'] ? 1 : 0, $flags['ad_measurement'] ? 1 : 0, $notice, $now, $uncertain ? 1 : 0));
            $this->query($this->db->prepare("UPDATE {$this->state} SET revision=%d,receipt=%s,analytics=%d,ad_measurement=%d,personalization=0,notice_version=%s,changed_at=%d,expires_at=%d,uncertain=%d WHERE subject_key=%s", $revision, $receipt, $flags['analytics'] ? 1 : 0, $flags['ad_measurement'] ? 1 : 0, $notice, $now, $expires, $uncertain ? 1 : 0, $subject));
            return ['subject_key' => $subject, 'revision' => $revision, 'receipt' => $receipt, 'analytics' => $flags['analytics'] ? 1 : 0, 'ad_measurement' => $flags['ad_measurement'] ? 1 : 0, 'personalization' => 0, 'notice_version' => $notice, 'changed_at' => $now, 'expires_at' => $expires, 'uncertain' => $uncertain ? 1 : 0];
        });
    }
    public function stage(array $capture): array {
        return $this->transaction(function () use ($capture) {
            $this->query($this->db->prepare("INSERT IGNORE INTO {$this->captures} (request_id,fingerprint,subject_key,original_revision,decision_version,notice_version,analytics,ad_measurement,personalization,preference_expires_at,eligible,known,created_at,state,uncertain,delivery_pending,click_capture_state,gclid_first,gclid_last,gclid_first_captured_ms,gclid_last_captured_ms,lead_id,event_id) VALUES (%s,%s,%s,%d,%s,%s,%d,%d,0,%d,%d,%d,%d,'STAGED',%d,0,%s,%s,%s,%d,%d,'','')", $capture['request_id'], $capture['fingerprint'], $capture['subject_key'], $capture['original_revision'], $capture['decision_version'], $capture['notice_version'], $capture['analytics'], $capture['ad_measurement'], $capture['preference_expires_at'], $capture['eligible'], $capture['known'], $capture['created_at'], $capture['uncertain'], $capture['click_capture_state'], $capture['gclid_first'], $capture['gclid_last'], $capture['gclid_first_captured_ms'], $capture['gclid_last_captured_ms']));
            $row = $this->row($this->db->prepare("SELECT * FROM {$this->captures} WHERE request_id=%s FOR UPDATE", $capture['request_id']));
            if (!$row) throw new \RuntimeException('Consent storage unavailable.');
            if (!hash_equals($row['fingerprint'], $capture['fingerprint'])) throw new \DomainException('REQUEST_ID_CONFLICT');
            return $row;
        });
    }
    public function link(string $request, string $fingerprint, string $lead, string $event): array {
        return $this->transaction(function () use ($request, $fingerprint, $lead, $event) {
            $row = $this->row($this->db->prepare("SELECT * FROM {$this->captures} WHERE request_id=%s FOR UPDATE", $request));
            if (!$row || !hash_equals($row['fingerprint'], $fingerprint)) throw new \RuntimeException('Consent evidence missing.');
            if ($row['lead_id'] !== '' && ($row['lead_id'] !== $lead || $row['event_id'] !== $event)) throw new \RuntimeException('Consent receipt conflict.');
            $this->query($this->db->prepare("UPDATE {$this->captures} SET state='ACCEPTED',lead_id=%s,event_id=%s,delivery_pending=0 WHERE request_id=%s AND fingerprint=%s", $lead, $event, $request, $fingerprint));
            $row['state'] = 'ACCEPTED'; $row['lead_id'] = $lead; $row['event_id'] = $event; $row['delivery_pending'] = 0;
            return $row;
        });
    }
    public function uncertain(string $request, string $fingerprint): void {
        $this->query($this->db->prepare("UPDATE {$this->captures} SET delivery_pending=1 WHERE request_id=%s AND fingerprint=%s", $request, $fingerprint));
    }
    public function revoked(string $subject, int $revision, string $purpose): bool {
        return $this->withdrawalSince($subject, $revision, $purpose, false);
    }
    private function withdrawalSince(string $subject, int $revision, string $purpose, bool $locking): bool {
        if (!in_array($purpose, ['analytics','ad_measurement'], true)) return true;
        $lock = $locking ? ' FOR UPDATE' : '';
        return $this->row($this->db->prepare("SELECT receipt FROM {$this->history} WHERE subject_key=%s AND revision>%d AND ({$purpose}=0 OR uncertain=1) LIMIT 1{$lock}", $subject, $revision)) !== null;
    }
    public function exportRows(array $requests): array {
        // Each subject's current state and withdrawal history use current locking
        // reads. A plain history SELECT could reuse an earlier subject's RR read
        // view and miss a committed withdrawal/regrant before this subject lock.
        // Privacy updates wait only for this short transaction, not a later upload.
        return $this->transaction(function () use ($requests) {
            $rows = [];
            foreach ($requests as $request) {
                $row = $this->row($this->db->prepare("SELECT * FROM {$this->captures} WHERE request_id=%s FOR UPDATE", $request));
                if ($row) {
                    $row['_current'] = $row['subject_key'] !== '' ? $this->row($this->db->prepare("SELECT * FROM {$this->state} WHERE subject_key=%s FOR UPDATE", $row['subject_key'])) : null;
                    $row['_ad_withdrawn'] = $row['subject_key'] === '' || $this->withdrawalSince($row['subject_key'], (int) $row['original_revision'], 'ad_measurement', true);
                }
                $rows[$request] = $row;
            }
            return $rows;
        });
    }
}

function install_consent_storage(): bool {
    global $wpdb;
    try {
        require_once ABSPATH . 'wp-admin/includes/upgrade.php';
        $collation = $wpdb->get_charset_collate();
        $state = $wpdb->prefix . 'bsre_consent_state';
        $history = $wpdb->prefix . 'bsre_consent_history';
        $captures = $wpdb->prefix . 'bsre_consent_captures';
        dbDelta("CREATE TABLE {$state} (
            subject_key char(64) NOT NULL,
            revision bigint unsigned NOT NULL,
            receipt char(32) NOT NULL,
            analytics tinyint unsigned NOT NULL DEFAULT 0,
            ad_measurement tinyint unsigned NOT NULL DEFAULT 0,
            personalization tinyint unsigned NOT NULL DEFAULT 0,
            notice_version varchar(64) NOT NULL,
            changed_at bigint unsigned NOT NULL,
            expires_at bigint unsigned NOT NULL,
            uncertain tinyint unsigned NOT NULL DEFAULT 1,
            PRIMARY KEY  (subject_key)
        ) ENGINE=InnoDB {$collation};");
        dbDelta("CREATE TABLE {$history} (
            receipt char(32) NOT NULL,
            subject_key char(64) NOT NULL,
            revision bigint unsigned NOT NULL,
            analytics tinyint unsigned NOT NULL DEFAULT 0,
            ad_measurement tinyint unsigned NOT NULL DEFAULT 0,
            personalization tinyint unsigned NOT NULL DEFAULT 0,
            notice_version varchar(64) NOT NULL,
            changed_at bigint unsigned NOT NULL,
            uncertain tinyint unsigned NOT NULL DEFAULT 0,
            PRIMARY KEY  (receipt),
            UNIQUE KEY subject_revision (subject_key,revision)
        ) ENGINE=InnoDB {$collation};");
        dbDelta("CREATE TABLE {$captures} (
            request_id char(36) NOT NULL,
            fingerprint char(64) NOT NULL,
            subject_key char(64) NOT NULL,
            original_revision bigint unsigned NOT NULL DEFAULT 0,
            decision_version char(32) NOT NULL,
            notice_version varchar(64) NOT NULL,
            analytics tinyint unsigned NOT NULL DEFAULT 0,
            ad_measurement tinyint unsigned NOT NULL DEFAULT 0,
            personalization tinyint unsigned NOT NULL DEFAULT 0,
            preference_expires_at bigint unsigned NOT NULL DEFAULT 0,
            eligible tinyint unsigned NOT NULL DEFAULT 0,
            known tinyint unsigned NOT NULL DEFAULT 0,
            created_at bigint unsigned NOT NULL,
            state varchar(16) NOT NULL,
            uncertain tinyint unsigned NOT NULL DEFAULT 1,
            delivery_pending tinyint unsigned NOT NULL DEFAULT 1,
            click_capture_state varchar(16) NOT NULL DEFAULT 'UNAVAILABLE',
            gclid_first varchar(256) NOT NULL DEFAULT '',
            gclid_last varchar(256) NOT NULL DEFAULT '',
            gclid_first_captured_ms bigint unsigned NOT NULL DEFAULT 0,
            gclid_last_captured_ms bigint unsigned NOT NULL DEFAULT 0,
            lead_id varchar(64) NOT NULL,
            event_id varchar(64) NOT NULL,
            PRIMARY KEY  (request_id),
            KEY subject_revision (subject_key,original_revision),
            KEY lead_id (lead_id)
        ) ENGINE=InnoDB {$collation};");
        foreach ([$state,$history,$captures] as $table) {
            $row = $wpdb->get_row($wpdb->prepare('SHOW TABLE STATUS WHERE Name=%s', $table), ARRAY_A);
            if (!is_array($row) || strtolower((string) ($row['Engine'] ?? '')) !== 'innodb') return false;
        }
        // dbDelta may fail without throwing. Do not advertise schema 2 until all
        // privacy fields exist; old rows remain UNAVAILABLE, never backfilled.
        foreach (['delivery_pending','click_capture_state','gclid_first','gclid_last','gclid_first_captured_ms','gclid_last_captured_ms'] as $column) {
            if (!$wpdb->get_row($wpdb->prepare("SHOW COLUMNS FROM {$captures} WHERE Field=%s", $column), ARRAY_A)) return false;
        }
        update_option('bsre_consent_schema_version', '2', false);
        return get_option('bsre_consent_schema_version') === '2';
    } catch (\Throwable $e) { return false; }
}
// Normal plugin file updates do not rerun activation hooks. An authenticated
// administrator visit performs this scoped schema migration before live QA.
add_action('admin_init', function (): void {
    if (current_user_can('manage_options') && get_option('bsre_consent_schema_version') !== '2') install_consent_storage();
});
