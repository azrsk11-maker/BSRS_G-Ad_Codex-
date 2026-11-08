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
        if (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB!==true || wp_get_environment_type()!=='local' || $db->prefix!=='retention_synthetic_' || home_url()!=='http://bsre.invalid') throw new \RuntimeException('ISOLATED_LAB_ONLY');
        $this->db=$db;
    }
    private function query(string $sql): int {
        $n=$this->db->query($sql);
        if ($n===false) throw new \RuntimeException('LEDGER_STORAGE_UNAVAILABLE');
        return (int)$n;
    }
    public static function rowHash(array $row): string { ksort($row); return hash('sha256',json_encode($row,JSON_THROW_ON_ERROR)); }
    public function install(): void {
        $p=$this->db->prefix;
        $this->query("CREATE TABLE IF NOT EXISTS {$p}bsre_retirement_checkpoint (id tinyint PRIMARY KEY, sequence_no bigint unsigned NOT NULL, chain_hash char(64) NOT NULL) ENGINE=InnoDB");
        $this->query("CREATE TABLE IF NOT EXISTS {$p}bsre_retirement_ledger (sequence_no bigint unsigned PRIMARY KEY, previous_hash char(64) NOT NULL, chain_hash char(64) NOT NULL, subject_key char(64) NOT NULL, receipt char(32) NOT NULL, revision bigint unsigned NOT NULL, row_hash char(64) NOT NULL, retired_at bigint unsigned NOT NULL, expires_at bigint unsigned NOT NULL, plan_hash char(64) NOT NULL) ENGINE=InnoDB");
        $this->query($this->db->prepare("INSERT IGNORE INTO {$p}bsre_retirement_checkpoint VALUES (1,0,%s)",str_repeat('0',64)));
    }
    /** Caller owns the transaction. Lock checkpoint before consent tables. */
    public function read(bool $lock): array {
        $p=$this->db->prefix;
        foreach (['checkpoint','ledger'] as $part) {
            $table=$p.'bsre_retirement_'.$part;
            $r=$this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$table),ARRAY_A);
            if (!$r || strtolower($r['Engine'])!=='innodb') throw new \RuntimeException('TRANSACTIONAL_LEDGER_REQUIRED');
        }
        $checkpoint=$this->db->get_row("SELECT * FROM {$p}bsre_retirement_checkpoint WHERE id=1".($lock?' FOR UPDATE':''),ARRAY_A);
        $this->db->last_error='';
        $rows=$this->db->get_results("SELECT * FROM {$p}bsre_retirement_ledger ORDER BY sequence_no LIMIT 1001".($lock?' FOR UPDATE':''),ARRAY_A);
        if (!$checkpoint || $this->db->last_error!=='' || !is_array($rows) || count($rows)>1000) throw new \RuntimeException('LEDGER_MISSING_OR_UNBOUNDED');
        $sequence=0; $hash=str_repeat('0',64);
        foreach($rows as &$row) {
            foreach(['sequence_no','revision','retired_at','expires_at'] as $k) $row[$k]=(int)$row[$k];
            if ($row['sequence_no']!==++$sequence || $row['previous_hash']!==$hash || $row['expires_at']!==$row['retired_at']+2592000) throw new \RuntimeException('LEDGER_CHAIN_INVALID');
            $claimed=$row['chain_hash']; unset($row['chain_hash']);
            $hash=self::rowHash($row); $row['chain_hash']=$claimed;
            if (!hash_equals($hash,$claimed)) throw new \RuntimeException('LEDGER_CHAIN_INVALID');
        }
        unset($row);
        if ((int)$checkpoint['sequence_no']!==$sequence || !hash_equals($checkpoint['chain_hash'],$hash)) throw new \RuntimeException('LEDGER_CHECKPOINT_MISMATCH');
        return ['anchor'=>['sequence'=>$sequence,'hash'=>$hash],'rows'=>$rows];
    }
    public function record(array $snapshot,array $plan,int $now,array $ledger): array {
        $anchor=$ledger['anchor']; $planHash=hash('sha256',json_encode($plan,JSON_THROW_ON_ERROR));
        foreach($snapshot['history'] as $history) {
            if (!in_array('bsre_consent_history:'.$history['receipt'],$plan['eligible'],true)) continue;
            $row=['sequence_no'=>++$anchor['sequence'],'previous_hash'=>$anchor['hash'],'subject_key'=>$history['subject_key'],'receipt'=>$history['receipt'],'revision'=>(int)$history['revision'],'row_hash'=>self::rowHash($history),'retired_at'=>$now,'expires_at'=>$now+2592000,'plan_hash'=>$planHash];
            $row['chain_hash']=self::rowHash($row); $anchor['hash']=$row['chain_hash'];
            if ($this->db->insert($this->db->prefix.'bsre_retirement_ledger',$row)===false) throw new \RuntimeException('LEDGER_STORAGE_UNAVAILABLE');
        }
        $this->query($this->db->prepare("UPDATE {$this->db->prefix}bsre_retirement_checkpoint SET sequence_no=%d,chain_hash=%s WHERE id=1",$anchor['sequence'],$anchor['hash']));
        return $anchor;
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
