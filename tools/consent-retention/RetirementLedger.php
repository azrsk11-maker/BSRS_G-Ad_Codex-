<?php
declare(strict_types=1);
namespace BSRE\RetentionReview;
if (!defined('ABSPATH')) exit;

/** Current lab ledger stays outside the three-table recovery snapshot.
 * Production custody/anchors are not implemented by this candidate.
 */
final class RetirementLedger {
    private $db;
    public function __construct($db) {
        $prefix=$db->prefix==='retention_synthetic_' || (defined('BSRE_RETENTION_COMPACTION_ENABLED') && BSRE_RETENTION_COMPACTION_ENABLED===true && $db->prefix==='retention_compaction_synthetic_');
        if (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB!==true || wp_get_environment_type()!=='local' || !$prefix || home_url()!=='http://bsre.invalid') throw new \RuntimeException('ISOLATED_LAB_ONLY');
        $this->db=$db;
    }
    private function query(string $sql): int {
        $n=$this->db->query($sql);
        if ($n===false) throw new \RuntimeException('LEDGER_STORAGE_UNAVAILABLE');
        return (int)$n;
    }
    public static function rowHash(array $row): string { ksort($row); return hash('sha256',json_encode($row,JSON_THROW_ON_ERROR)); }
    private static function uint($value): int {
        if (is_int($value) && $value>=0) return $value;
        if (!is_string($value) || !preg_match('/^(0|[1-9][0-9]*)$/D',$value) || strlen($value)>strlen((string)PHP_INT_MAX) || (strlen($value)===strlen((string)PHP_INT_MAX) && strcmp($value,(string)PHP_INT_MAX)>0)) throw new \RuntimeException('LEDGER_INTEGER_OUT_OF_RANGE');
        return (int)$value;
    }
    private static function clock(int $now,int $window): void {
        if ($now<0 || $now>PHP_INT_MAX-$window) throw new \RuntimeException('LEDGER_CLOCK_INVALID');
    }
    public function compactionGuard(bool $apply=false): void {
        if (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB!==true || wp_get_environment_type()!=='local' || home_url()!=='http://bsre.invalid' || !in_array($this->db->prefix,['retention_synthetic_','retention_compaction_synthetic_'],true)) throw new \RuntimeException('ISOLATED_LAB_ONLY');
        if (!current_user_can('manage_options')) throw new \RuntimeException('OWNER_REQUIRED');
        if (!defined('BSRE_RETENTION_COMPACTION_ENABLED') || BSRE_RETENTION_COMPACTION_ENABLED!==true || ($apply && (!defined('BSRE_RETENTION_APPLY_ENABLED') || BSRE_RETENTION_APPLY_ENABLED!==true))) throw new \RuntimeException('COMPACTION_DISABLED');
    }
    private static function anchor(int $sequence,string $hash,array $floor): array {
        if ($floor['generation']===0) return ['sequence'=>$sequence,'hash'=>$hash];
        $anchor=['version'=>2,'sequence'=>$sequence,'hash'=>$hash,'floor'=>$floor];
        $anchor['anchor_sha256']=self::rowHash($anchor);
        return $anchor;
    }
    public function install(): void {
        $p=$this->db->prefix;
        $this->query("CREATE TABLE IF NOT EXISTS {$p}bsre_retirement_checkpoint (id tinyint PRIMARY KEY, sequence_no bigint unsigned NOT NULL, chain_hash char(64) NOT NULL) ENGINE=InnoDB");
        $this->query("CREATE TABLE IF NOT EXISTS {$p}bsre_retirement_ledger (sequence_no bigint unsigned PRIMARY KEY, previous_hash char(64) NOT NULL, chain_hash char(64) NOT NULL, subject_key char(64) NOT NULL, receipt char(32) NOT NULL, revision bigint unsigned NOT NULL, row_hash char(64) NOT NULL, retired_at bigint unsigned NOT NULL, expires_at bigint unsigned NOT NULL, plan_hash char(64) NOT NULL) ENGINE=InnoDB");
        $this->query("CREATE TABLE IF NOT EXISTS {$p}bsre_retirement_floor (id tinyint PRIMARY KEY, sequence_no bigint unsigned NOT NULL, chain_hash char(64) NOT NULL, generation bigint unsigned NOT NULL, compacted_at bigint unsigned NOT NULL) ENGINE=InnoDB");
        $this->query("CREATE TABLE IF NOT EXISTS {$p}bsre_ledger_compaction_audit (plan_hash char(64) PRIMARY KEY, applied_at bigint unsigned NOT NULL, actor bigint unsigned NOT NULL, deleted_rows int unsigned NOT NULL, floor_sequence bigint unsigned NOT NULL, floor_generation bigint unsigned NOT NULL, anchor_sha256 char(64) NOT NULL) ENGINE=InnoDB");
        $this->query($this->db->prepare("INSERT IGNORE INTO {$p}bsre_retirement_checkpoint VALUES (1,0,%s)",str_repeat('0',64)));
        $this->query($this->db->prepare("INSERT IGNORE INTO {$p}bsre_retirement_floor VALUES (1,0,%s,0,0)",str_repeat('0',64)));
    }
    /** Caller owns the transaction. Lock checkpoint before consent tables. */
    public function read(bool $lock): array {
        $p=$this->db->prefix;
        foreach (['checkpoint','floor','ledger'] as $part) {
            $table=$p.'bsre_retirement_'.$part;
            $r=$this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$table),ARRAY_A);
            if (!$r || strtolower($r['Engine'])!=='innodb') throw new \RuntimeException('TRANSACTIONAL_LEDGER_REQUIRED');
        }
        $checkpoint=$this->db->get_row("SELECT * FROM {$p}bsre_retirement_checkpoint WHERE id=1".($lock?' FOR UPDATE':''),ARRAY_A);
        $floorRow=$this->db->get_row("SELECT * FROM {$p}bsre_retirement_floor WHERE id=1".($lock?' FOR UPDATE':''),ARRAY_A);
        $this->db->last_error='';
        $rows=$this->db->get_results("SELECT * FROM {$p}bsre_retirement_ledger ORDER BY sequence_no LIMIT 1001".($lock?' FOR UPDATE':''),ARRAY_A);
        if (!$checkpoint || !$floorRow || $this->db->last_error!=='' || !is_array($rows) || count($rows)>1000) throw new \RuntimeException('LEDGER_MISSING_OR_UNBOUNDED');
        $floor=['sequence'=>self::uint($floorRow['sequence_no']),'hash'=>$floorRow['chain_hash'],'generation'=>self::uint($floorRow['generation']),'compacted_at'=>self::uint($floorRow['compacted_at'])];
        if (!is_string($floor['hash']) || !preg_match('/^[a-f0-9]{64}$/D',$floor['hash']) || ($floor['generation']===0 && ($floor['sequence']!==0 || $floor['hash']!==str_repeat('0',64) || $floor['compacted_at']!==0)) || ($floor['generation']>0 && ($floor['sequence']===0 || $floor['compacted_at']===0))) throw new \RuntimeException('LEDGER_FLOOR_INVALID');
        $sequence=$floor['sequence']; $hash=$floor['hash'];
        foreach($rows as &$row) {
            foreach(['sequence_no','revision','retired_at','expires_at'] as $k) $row[$k]=self::uint($row[$k]);
            if ($sequence===PHP_INT_MAX || $row['retired_at']>PHP_INT_MAX-2592000 || $row['sequence_no']!==++$sequence || $row['previous_hash']!==$hash || $row['expires_at']!==$row['retired_at']+2592000) throw new \RuntimeException('LEDGER_CHAIN_INVALID');
            $claimed=$row['chain_hash']; unset($row['chain_hash']);
            $hash=self::rowHash($row); $row['chain_hash']=$claimed;
            if (!hash_equals($hash,$claimed)) throw new \RuntimeException('LEDGER_CHAIN_INVALID');
        }
        unset($row);
        if (self::uint($checkpoint['sequence_no'])!==$sequence || !is_string($checkpoint['chain_hash']) || !hash_equals($checkpoint['chain_hash'],$hash)) throw new \RuntimeException('LEDGER_CHECKPOINT_MISMATCH');
        return ['anchor'=>self::anchor($sequence,$hash,$floor),'floor'=>$floor,'rows'=>$rows];
    }
    public function record(array $snapshot,array $plan,int $now,array $ledger): array {
        $anchor=$ledger['anchor']; $planHash=hash('sha256',json_encode($plan,JSON_THROW_ON_ERROR));
        $pending=count(array_filter($snapshot['history'],fn($row)=>in_array('bsre_consent_history:'.$row['receipt'],$plan['eligible'],true)));
        if (count($ledger['rows'])+$pending>1000) throw new \RuntimeException('LEDGER_CAPACITY_EXCEEDED');
        self::clock($now,2592000);
        if ($now<$ledger['floor']['compacted_at'] || self::uint($anchor['sequence'])>PHP_INT_MAX-$pending) throw new \RuntimeException('LEDGER_CLOCK_OR_SEQUENCE_INVALID');
        foreach($snapshot['history'] as $history) {
            if (!in_array('bsre_consent_history:'.$history['receipt'],$plan['eligible'],true)) continue;
            $row=['sequence_no'=>++$anchor['sequence'],'previous_hash'=>$anchor['hash'],'subject_key'=>$history['subject_key'],'receipt'=>$history['receipt'],'revision'=>(int)$history['revision'],'row_hash'=>self::rowHash($history),'retired_at'=>$now,'expires_at'=>$now+2592000,'plan_hash'=>$planHash];
            $row['chain_hash']=self::rowHash($row); $anchor['hash']=$row['chain_hash'];
            if ($this->db->insert($this->db->prefix.'bsre_retirement_ledger',$row)===false) throw new \RuntimeException('LEDGER_STORAGE_UNAVAILABLE');
        }
        $this->query($this->db->prepare("UPDATE {$this->db->prefix}bsre_retirement_checkpoint SET sequence_no=%d,chain_hash=%s WHERE id=1",$anchor['sequence'],$anchor['hash']));
        return self::anchor($anchor['sequence'],$anchor['hash'],$ledger['floor']);
    }
    /** Private exact plan. No subject/receipt IDs are retained after pruning. */
    public function compactionPlan(array $ledger,int $now,array $trustedAnchor): array {
        $this->compactionGuard();
        self::clock($now,900);
        if ($trustedAnchor!==$ledger['anchor']) throw new \RuntimeException('CURRENT_LEDGER_ANCHOR_REQUIRED');
        if ($now<$ledger['floor']['compacted_at']) throw new \RuntimeException('LEDGER_CLOCK_INVALID');
        $sequences=[]; $floor=$ledger['floor'];
        foreach($ledger['rows'] as $row) {
            if ($row['expires_at']>$now) break; // Only an expired contiguous prefix may be removed.
            $sequences[]=$row['sequence_no']; $floor['sequence']=$row['sequence_no']; $floor['hash']=$row['chain_hash'];
        }
        if ($sequences) {
            if ($floor['generation']===PHP_INT_MAX) throw new \RuntimeException('LEDGER_GENERATION_EXHAUSTED');
            ++$floor['generation']; $floor['compacted_at']=$now;
        }
        return ['version'=>1,'scope'=>'SYNTHETIC_LEDGER_COMPACTION','created_at'=>$now,'expires_at'=>$now+900,'ledger_anchor'=>$ledger['anchor'],'ledger_sha256'=>self::rowHash($ledger),'delete_sequences'=>$sequences,'after_floor'=>$floor];
    }
    /** Owns transaction, locked readback and audit even when called directly. */
    public function compact(array $plan,string $approval,array $trustedAnchor,int $now): array {
        $this->compactionGuard(true); self::clock($now,900);
        if (!hash_equals('COMPACT_SYNTHETIC_LEDGER:'.hash('sha256',json_encode($plan,JSON_THROW_ON_ERROR)),$approval)) throw new \RuntimeException('EXACT_COMPACTION_APPROVAL_REQUIRED');
        if (!isset($plan['created_at'],$plan['expires_at']) || !is_int($plan['created_at']) || !is_int($plan['expires_at']) || $plan['created_at']<0 || $plan['created_at']>PHP_INT_MAX-900 || $now<$plan['created_at'] || $now>=$plan['expires_at'] || $plan['expires_at']!==$plan['created_at']+900) throw new \RuntimeException('PLAN_EXPIRED_OR_INVALID');
        $this->db->last_error='';
        $transaction=$this->db->get_var('SELECT @@session.in_transaction');
        if ($this->db->last_error!=='' || !in_array($transaction,[0,1,'0','1'],true)) throw new \RuntimeException('TRANSACTION_STATE_UNAVAILABLE');
        if ((string)$transaction!=='0') throw new \RuntimeException('EXISTING_TRANSACTION_FORBIDDEN');
        $this->query('START TRANSACTION');
        try {
            $ledger=$this->read(true);
            if ($trustedAnchor!==$ledger['anchor']) throw new \RuntimeException('CURRENT_LEDGER_ANCHOR_REQUIRED');
            $expected=$this->compactionPlan($ledger,$plan['created_at'],$trustedAnchor);
            if (!hash_equals(self::rowHash($expected),self::rowHash($plan))) throw new \RuntimeException('COMPACTION_PLAN_STALE_OR_ALTERED');
            $p=$this->db->prefix;
            $audit=$this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$p.'bsre_ledger_compaction_audit'),ARRAY_A);
            if (!$audit || strtolower($audit['Engine'])!=='innodb') throw new \RuntimeException('TRANSACTIONAL_AUDIT_REQUIRED');
            $deleted=0;
            foreach($plan['delete_sequences'] as $sequence) $deleted+=$this->query($this->db->prepare("DELETE FROM {$p}bsre_retirement_ledger WHERE sequence_no=%d AND expires_at<=%d",$sequence,$now));
            if ($deleted!==count($plan['delete_sequences'])) throw new \RuntimeException('COMPACTION_DELETE_COUNT_CONFLICT');
            $result=['deleted_rows'=>0,'anchor'=>$ledger['anchor'],'history_gap'=>$ledger['floor']['generation']>0];
            if ($deleted>0) {
                $floor=$plan['after_floor'];
                $changed=$this->query($this->db->prepare("UPDATE {$p}bsre_retirement_floor SET sequence_no=%d,chain_hash=%s,generation=%d,compacted_at=%d WHERE id=1 AND generation=%d",$floor['sequence'],$floor['hash'],$floor['generation'],$floor['compacted_at'],$ledger['floor']['generation']));
                if ($changed!==1) throw new \RuntimeException('COMPACTION_FLOOR_CONFLICT');
                $after=$this->read(true);
                $this->query($this->db->prepare("INSERT INTO {$p}bsre_ledger_compaction_audit (plan_hash,applied_at,actor,deleted_rows,floor_sequence,floor_generation,anchor_sha256) VALUES (%s,%d,%d,%d,%d,%d,%s)",hash('sha256',json_encode($plan,JSON_THROW_ON_ERROR)),$now,get_current_user_id(),$deleted,$floor['sequence'],$floor['generation'],$after['anchor']['anchor_sha256']));
                $result=['deleted_rows'=>$deleted,'anchor'=>$after['anchor'],'history_gap'=>true];
            }
            $this->query('COMMIT');
            return $result;
        } catch(\Throwable $error) { $this->db->query('ROLLBACK'); throw $error; }
    }
    /** Verified package metadata is supplied separately from the CURRENT anchor.
     * Return exact private row references; never delete captures during restore.
     */
    public function restorePlan(array $snapshot,array $metadata,array $trustedAnchor,array $ledger,int $now): array {
        $keys=array_keys($metadata); sort($keys);
        $required=['version','source','createdAtMs','expiresAtMs','snapshotSha256','deletionLedgerWatermark']; sort($required);
        if ($keys!==$required || $metadata['version']!==1 || $metadata['source']!=='SYNTHETIC_BSRE_LAB' ||
            !is_int($metadata['createdAtMs']) || !is_int($metadata['expiresAtMs']) || !is_int($metadata['deletionLedgerWatermark']) ||
            $metadata['createdAtMs']<=0 || $metadata['expiresAtMs']-$metadata['createdAtMs']!==2592000000 ||
            $now*1000<$metadata['createdAtMs'] || $now*1000>=$metadata['expiresAtMs'] || $metadata['deletionLedgerWatermark']<0 ||
            !is_string($metadata['snapshotSha256']) || !hash_equals(hash('sha256',json_encode($snapshot,JSON_THROW_ON_ERROR)),$metadata['snapshotSha256'])) throw new \RuntimeException('BACKUP_METADATA_INVALID_OR_EXPIRED');
        if ($trustedAnchor!==$ledger['anchor'] || $metadata['deletionLedgerWatermark']>$ledger['anchor']['sequence']) throw new \RuntimeException('CURRENT_LEDGER_ANCHOR_REQUIRED');
        if ($ledger['floor']['generation']>0 && ($snapshot['state'] || $snapshot['history'] || $snapshot['captures'])) throw new \RuntimeException('COMPACTED_HISTORY_REQUIRES_RECONCILIATION');
        $retired=[]; $subjects=[];
        foreach($ledger['rows'] as $row) { $retired[$row['receipt']]=$row; $subjects[$row['subject_key']]=true; }
        // Validate exact schema/size/choice types using the existing bounded helper.
        RetentionInventory::plan($snapshot,$now,true);
        $eligible=[];
        $historyByReceipt=[];
        foreach($snapshot['history'] as $history) $historyByReceipt[$history['receipt']]=$history;
        foreach($snapshot['captures'] as $capture) {
            if ($capture['subject_key']==='' || isset($retired[$capture['decision_version']]) ||
                (isset($subjects[$capture['subject_key']]) && (int)$capture['known']!==1)) throw new \RuntimeException('RESTORED_CAPTURE_REQUIRES_RECONCILIATION');
            if (isset($subjects[$capture['subject_key']])) {
                $original=$historyByReceipt[$capture['decision_version']]??null;
                if (!$original || $original['subject_key']!==$capture['subject_key'] || (int)$original['revision']!==(int)$capture['original_revision']) throw new \RuntimeException('RESTORED_CAPTURE_REQUIRES_RECONCILIATION');
            }
        }
        foreach($snapshot['history'] as $history) {
            $row=$retired[$history['receipt']]??null;
            if (!$row) continue;
            if ($row['expires_at']<=$now) throw new \RuntimeException('RESTORED_RETIRED_ROW_OUTSIDE_WINDOW');
            if ($row['subject_key']!==$history['subject_key'] || !hash_equals($row['row_hash'],self::rowHash($history))) throw new \RuntimeException('RESTORE_ROW_IDENTITY_CONFLICT');
            $eligible[]='bsre_consent_history:'.$history['receipt'];
        }
        foreach($snapshot['state'] as $state) {
            $row=$retired[$state['receipt']]??null;
            if (!$row) continue; // Later choice with a new receipt must survive.
            $history=$state; unset($history['expires_at']);
            if ($row['expires_at']<=$now || $row['subject_key']!==$state['subject_key'] || !hash_equals($row['row_hash'],self::rowHash($history))) throw new \RuntimeException('RESTORE_ROW_IDENTITY_CONFLICT');
            $eligible[]='bsre_consent_state:'.$state['subject_key'];
        }
        sort($eligible);
        return ['version'=>1,'scope'=>'SYNTHETIC_RESTORE_REDELETION','created_at'=>$now,'expires_at'=>$now+900,'snapshot_hash'=>hash('sha256',json_encode($snapshot,JSON_THROW_ON_ERROR)),'ledger_anchor'=>$ledger['anchor'],'backup'=>$metadata,'eligible'=>$eligible];
    }
}
