<?php
declare(strict_types=1);
namespace BSRE\RetentionReview;
if (!defined('ABSPATH')) exit;
require_once __DIR__ . '/RetentionInventory.php';

/** Real SQL candidate, deliberately restricted to the disposable synthetic lab.
 * No hooks, scheduler, public route or live authority is installed by this file.
 */
final class PreferenceRetirement {
    private $db;
    private $clock;
    public function __construct($db, ?callable $clock = null) {
        if (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB !== true ||
            wp_get_environment_type() !== 'local' || $db->prefix !== 'retention_synthetic_' ||
            home_url() !== 'http://bsre.invalid') throw new \RuntimeException('ISOLATED_LAB_ONLY');
        $this->db = $db; $this->clock = $clock ?? fn() => time();
    }
    private function query(string $sql): int {
        $result = $this->db->query($sql);
        if ($result === false) throw new \RuntimeException('RETENTION_STORAGE_UNAVAILABLE');
        return (int) $result;
    }
    private function transaction(callable $fn) {
        $this->query('START TRANSACTION');
        try { $result = $fn(); $this->query('COMMIT'); return $result; }
        catch (\Throwable $e) { $this->db->query('ROLLBACK'); throw $e; }
    }
    public function installLabAudit(): void {
        $this->query("CREATE TABLE IF NOT EXISTS {$this->db->prefix}bsre_retention_audit (plan_hash char(64) PRIMARY KEY, applied_at bigint unsigned NOT NULL, actor bigint unsigned NOT NULL, deleted_rows int unsigned NOT NULL) ENGINE=InnoDB");
    }
    private function authorize(): void {
        if (!current_user_can('manage_options')) throw new \RuntimeException('OWNER_REQUIRED');
    }
    private function snapshot(bool $lock): array {
        $data = ['kind' => RetentionInventory::KIND]; $total = 0;
        foreach (['state','history','captures'] as $part) {
            $table = $this->db->prefix . 'bsre_consent_' . $part;
            $engine = $this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s', $table), ARRAY_A);
            if (!is_array($engine) || strtolower($engine['Engine']) !== 'innodb') throw new \RuntimeException('TRANSACTIONAL_SCHEMA_REQUIRED');
            $this->db->last_error = '';
            $pk = ['state'=>'subject_key','history'=>'receipt','captures'=>'request_id'][$part];
            $data[$part] = $this->db->get_results("SELECT * FROM {$table} ORDER BY {$pk} LIMIT 1001" . ($lock ? ' FOR UPDATE' : ''), ARRAY_A);
            if ($this->db->last_error !== '' || !is_array($data[$part])) throw new \RuntimeException('RETENTION_STORAGE_UNAVAILABLE');
            $total += count($data[$part]);
            if ($total > RetentionInventory::MAX_ROWS) throw new \RuntimeException('BOUNDED_SNAPSHOT_EXCEEDED');
        }
        return $data;
    }
    private static function digest(array $value): string { return hash('sha256', json_encode($value, JSON_THROW_ON_ERROR)); }
    private function makePlan(array $snapshot, int $now): array {
        $review = RetentionInventory::plan($snapshot, $now, true);
        $eligible = [];
        foreach ($review['rows'] as $row) if ($row['classification'] === 'AGE_ELIGIBLE_FOR_REVIEW') $eligible[] = $row['row_ref'];
        return ['version'=>1, 'scope'=>'SYNTHETIC_NEVER_SUBMITTED_PREFERENCES', 'created_at'=>$now,
            'expires_at'=>$now+900, 'snapshot_hash'=>self::digest($snapshot), 'eligible'=>$eligible];
    }
    /** Private plan contains pseudonymous row references; never log/publish it. */
    public function preview(): array {
        $this->authorize();
        return $this->transaction(fn() => $this->makePlan($this->snapshot(false), ($this->clock)()));
    }
    public static function approval(array $plan): string { return 'DELETE_SYNTHETIC_PREFERENCES:' . self::digest($plan); }
    public function apply(array $plan, string $approval): array {
        $this->authorize();
        if (!defined('BSRE_RETENTION_APPLY_ENABLED') || BSRE_RETENTION_APPLY_ENABLED !== true) throw new \RuntimeException('APPLY_DISABLED');
        if (!hash_equals(self::approval($plan), $approval)) throw new \RuntimeException('EXACT_PLAN_APPROVAL_REQUIRED');
        $now = ($this->clock)();
        if (!isset($plan['created_at'],$plan['expires_at']) || !is_int($plan['created_at']) || !is_int($plan['expires_at']) || $now < $plan['created_at'] || $now >= $plan['expires_at'] || $plan['expires_at'] !== $plan['created_at']+900) throw new \RuntimeException('PLAN_EXPIRED_OR_INVALID');
        return $this->transaction(function() use ($plan,$now) {
            $audit = $this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s', $this->db->prefix.'bsre_retention_audit'), ARRAY_A);
            if (!is_array($audit) || strtolower($audit['Engine']) !== 'innodb') throw new \RuntimeException('TRANSACTIONAL_AUDIT_REQUIRED');
            $snapshot = $this->snapshot(true);
            $expected = $this->makePlan($snapshot, $plan['created_at']);
            if (!hash_equals(self::digest($expected), self::digest($plan))) throw new \RuntimeException('PLAN_STALE_OR_ALTERED');
            $deleted = 0;
            // Exact approved rows only; no capture, intake, outbox or mail DELETE.
            foreach ($plan['eligible'] as $ref) {
                [$table,$id] = explode(':',$ref,2);
                if (!in_array($table,['bsre_consent_state','bsre_consent_history'],true)) throw new \RuntimeException('ROW_SCOPE_INVALID');
                $pk = $table === 'bsre_consent_state' ? 'subject_key' : 'receipt';
                $deleted += $this->query($this->db->prepare("DELETE FROM {$this->db->prefix}{$table} WHERE {$pk}=%s", $id));
            }
            if ($deleted !== count($plan['eligible'])) throw new \RuntimeException('DELETE_COUNT_CONFLICT');
            $hash = self::digest($plan);
            $this->query($this->db->prepare("INSERT INTO {$this->db->prefix}bsre_retention_audit (plan_hash,applied_at,actor,deleted_rows) VALUES (%s,%d,%d,%d)", $hash,$now,get_current_user_id(),$deleted));
            return ['scope'=>'SYNTHETIC_ONLY','plan_hash'=>$hash,'deleted_rows'=>$deleted,'production_acceptance'=>false];
        });
    }
}
