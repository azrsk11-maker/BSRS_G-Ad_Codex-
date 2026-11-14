<?php
declare(strict_types=1);
namespace BSRE\RetentionReview;
if (!defined('ABSPATH')) exit;
require_once __DIR__ . '/RetentionInventory.php';
require_once __DIR__ . '/RetirementLedger.php';

/** Real SQL candidate, deliberately restricted to the disposable synthetic lab.
 * No hooks, scheduler, public route or live authority is installed by this file.
 */
final class PreferenceRetirement {
    private $db;
    private $clock;
    private RetirementLedger $ledger;
    public function __construct($db, ?callable $clock = null) {
        $prefix=$db->prefix==='retention_synthetic_' || (defined('BSRE_RETENTION_COMPACTION_ENABLED') && BSRE_RETENTION_COMPACTION_ENABLED===true && $db->prefix==='retention_compaction_synthetic_');
        if (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB !== true ||
            wp_get_environment_type() !== 'local' || !$prefix ||
            home_url() !== 'http://bsre.invalid') throw new \RuntimeException('ISOLATED_LAB_ONLY');
        $this->db = $db; $this->clock = $clock ?? fn() => time();
        $this->ledger = new RetirementLedger($db);
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
        $this->query("CREATE TABLE IF NOT EXISTS {$this->db->prefix}bsre_restore_audit (plan_hash char(64) PRIMARY KEY, applied_at bigint unsigned NOT NULL, actor bigint unsigned NOT NULL, reapplied_rows int unsigned NOT NULL, ledger_sequence bigint unsigned NOT NULL) ENGINE=InnoDB");
        $this->ledger->install();
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
            $ledger = $this->ledger->read(true);
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
            $anchor = $this->ledger->record($snapshot,$plan,$now,$ledger);
            $hash = self::digest($plan);
            $this->query($this->db->prepare("INSERT INTO {$this->db->prefix}bsre_retention_audit (plan_hash,applied_at,actor,deleted_rows) VALUES (%s,%d,%d,%d)", $hash,$now,get_current_user_id(),$deleted));
            return ['scope'=>'SYNTHETIC_ONLY','plan_hash'=>$hash,'deleted_rows'=>$deleted,'ledger_anchor'=>$anchor,'production_acceptance'=>false];
        });
    }
    /** Private synthetic snapshot only; caller must encrypt and restrict it. */
    public function backupSnapshot(): array {
        $this->authorize();
        return $this->transaction(fn() => $this->snapshot(false));
    }
    public function ledgerAnchor(): array {
        $this->authorize();
        return $this->transaction(fn() => $this->ledger->read(false)['anchor']);
    }
    public function previewLedgerCompaction(array $trustedAnchor): array {
        $this->authorize();
        $this->ledger->compactionGuard();
        return $this->transaction(fn() => $this->ledger->compactionPlan($this->ledger->read(false),($this->clock)(),$trustedAnchor));
    }
    public static function compactionApproval(array $plan): string { return 'COMPACT_SYNTHETIC_LEDGER:'.self::digest($plan); }
    public function applyLedgerCompaction(array $plan,string $approval,array $trustedAnchor): array {
        $this->authorize();
        $result=$this->ledger->compact($plan,$approval,$trustedAnchor,($this->clock)());
        return ['scope'=>'SYNTHETIC_ONLY','deleted_ledger_rows'=>$result['deleted_rows'],'ledger_anchor'=>$result['anchor'],'history_gap_after_compaction'=>$result['history_gap'],'nonempty_restore_authorized'=>false,'production_acceptance'=>false];
    }
    public function previewRestore(array $metadata,array $trustedAnchor): array {
        $this->authorize();
        return $this->transaction(fn() => $this->ledger->restorePlan($this->snapshot(false),$metadata,$trustedAnchor,$this->ledger->read(false),($this->clock)()));
    }
    public static function restoreApproval(array $plan): string { return 'REDELETE_SYNTHETIC_RESTORE:' . self::digest($plan); }
    public function applyRestore(array $plan,string $approval,array $trustedAnchor): array {
        $this->authorize();
        if (!defined('BSRE_RETENTION_APPLY_ENABLED') || BSRE_RETENTION_APPLY_ENABLED!==true) throw new \RuntimeException('APPLY_DISABLED');
        if (!hash_equals(self::restoreApproval($plan),$approval)) throw new \RuntimeException('EXACT_RESTORE_APPROVAL_REQUIRED');
        $now=($this->clock)();
        if (!isset($plan['created_at'],$plan['expires_at']) || !is_int($plan['created_at']) || !is_int($plan['expires_at']) || $now<$plan['created_at'] || $now>=$plan['expires_at'] || $plan['expires_at']!==$plan['created_at']+900) throw new \RuntimeException('PLAN_EXPIRED_OR_INVALID');
        return $this->transaction(function() use ($plan,$trustedAnchor,$now) {
            $audit=$this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$this->db->prefix.'bsre_restore_audit'),ARRAY_A);
            if (!$audit || strtolower($audit['Engine'])!=='innodb') throw new \RuntimeException('TRANSACTIONAL_AUDIT_REQUIRED');
            $ledger=$this->ledger->read(true); $snapshot=$this->snapshot(true);
            $expected=$this->ledger->restorePlan($snapshot,$plan['backup'],$trustedAnchor,$ledger,$plan['created_at']);
            // Check package freshness at execution, in addition to plan freshness.
            $this->ledger->restorePlan($snapshot,$plan['backup'],$trustedAnchor,$ledger,$now);
            if (!hash_equals(self::digest($expected),self::digest($plan))) throw new \RuntimeException('RESTORE_PLAN_STALE_OR_ALTERED');
            $deleted=0;
            foreach($plan['eligible'] as $ref) {
                [$table,$id]=explode(':',$ref,2);
                $pk=$table==='bsre_consent_state'?'subject_key':'receipt';
                $deleted+=$this->query($this->db->prepare("DELETE FROM {$this->db->prefix}{$table} WHERE {$pk}=%s",$id));
            }
            if ($deleted!==count($plan['eligible'])) throw new \RuntimeException('RESTORE_DELETE_COUNT_CONFLICT');
            $this->query($this->db->prepare("INSERT INTO {$this->db->prefix}bsre_restore_audit (plan_hash,applied_at,actor,reapplied_rows,ledger_sequence) VALUES (%s,%d,%d,%d,%d)",self::digest($plan),$now,get_current_user_id(),$deleted,$ledger['anchor']['sequence']));
            return ['scope'=>'SYNTHETIC_ONLY','reapplied_rows'=>$deleted,'ledger_anchor'=>$ledger['anchor'],'reopen_authorized'=>false,'production_acceptance'=>false];
        });
    }
}
