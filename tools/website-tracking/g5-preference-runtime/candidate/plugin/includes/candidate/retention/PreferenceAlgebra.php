<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\PreferenceV1;
/** Pure reviewed algebra only. All authority and SQL ownership live in the consuming runtime. */
final class Algebra {
    public static function rowHash(array $row): string { ksort($row); return hash('sha256',json_encode($row,JSON_THROW_ON_ERROR)); }
    private static function uint($value): int {
        if (is_int($value) && $value>=0) return $value;
        if (!is_string($value) || !preg_match('/^(0|[1-9][0-9]*)$/D',$value) || strlen($value)>strlen((string)PHP_INT_MAX) || (strlen($value)===strlen((string)PHP_INT_MAX) && strcmp($value,(string)PHP_INT_MAX)>0)) throw new \RuntimeException('LEDGER_INTEGER_OUT_OF_RANGE');
        return (int)$value;
    }
    private static function clock(int $now,int $window): void {
        if ($now<0 || $now>PHP_INT_MAX-$window) throw new \RuntimeException('LEDGER_CLOCK_INVALID');
    }
    private static function anchor(int $sequence,string $hash,array $floor): array {
        if ($floor['generation']===0) return ['sequence'=>$sequence,'hash'=>$hash];
        $anchor=['version'=>2,'sequence'=>$sequence,'hash'=>$hash,'floor'=>$floor];
        $anchor['anchor_sha256']=self::rowHash($anchor);
        return $anchor;
    }
    public static function compactionPlan(array $ledger,int $now,array $trustedAnchor): array {
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
    public static function restorePlan(array $snapshot,array $metadata,array $trustedAnchor,array $ledger,int $now): array {
        $keys=array_keys($metadata); sort($keys);
        $required=['version','source','createdAtMs','expiresAtMs','snapshotSha256','deletionLedgerWatermark']; sort($required);
        if ($keys!==$required || $metadata['version']!==1 || $metadata['source']!=='ACTUAL_PREFERENCE_SNAPSHOT_V1' ||
            !is_int($metadata['createdAtMs']) || !is_int($metadata['expiresAtMs']) || !is_int($metadata['deletionLedgerWatermark']) ||
            $metadata['createdAtMs']<=0 || $metadata['expiresAtMs']-$metadata['createdAtMs']!==2592000000 ||
            $now*1000<$metadata['createdAtMs'] || $now*1000>=$metadata['expiresAtMs'] || $metadata['deletionLedgerWatermark']<0 ||
            !is_string($metadata['snapshotSha256']) || !hash_equals(hash('sha256',json_encode($snapshot,JSON_THROW_ON_ERROR)),$metadata['snapshotSha256'])) throw new \RuntimeException('BACKUP_METADATA_INVALID_OR_EXPIRED');
        if ($trustedAnchor!==$ledger['anchor'] || $metadata['deletionLedgerWatermark']>$ledger['anchor']['sequence']) throw new \RuntimeException('CURRENT_LEDGER_ANCHOR_REQUIRED');
        if ($ledger['floor']['generation']>0 && ($snapshot['state'] || $snapshot['history'] || $snapshot['captures'])) throw new \RuntimeException('COMPACTED_HISTORY_REQUIRES_RECONCILIATION');
        $retired=[]; $subjects=[];
        foreach($ledger['rows'] as $row) { $retired[$row['receipt']]=$row; $subjects[$row['subject_key']]=true; }
        // Validate exact schema/size/choice types using the existing bounded helper.
        SnapshotFormat::plan($snapshot,$now,true);
        \BSRE\PurposeRetention\RetentionInventory::assertRestoreReferences($snapshot,$retired);
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
    public static function references(array $snapshot,array $ledger,int $now): array {
        if ($ledger['floor']['generation']>0 && ($snapshot['state'] || $snapshot['history'] || $snapshot['captures'])) throw new \RuntimeException('COMPACTED_HISTORY_REQUIRES_RECONCILIATION');
        $retired=[]; $subjects=[];
        foreach($ledger['rows'] as $row) { $retired[$row['receipt']]=$row; $subjects[$row['subject_key']]=true; }
        // Validate exact schema/size/choice types using the existing bounded helper.
        SnapshotFormat::plan($snapshot,$now,true);
        \BSRE\PurposeRetention\RetentionInventory::assertRestoreReferences($snapshot,$retired);
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
        return $eligible;
    }
    public static function append(array $snapshot,array $plan,int $now,array $ledger): array {
        $anchor=$ledger['anchor']; $planHash=Guard::digest($plan);
        $pending=count(array_filter($snapshot['history'],fn($row)=>in_array('bsre_consent_history:'.$row['receipt'],$plan['details']['eligible'],true)));
        if (count($ledger['rows'])+$pending>1000) throw new \RuntimeException('LEDGER_CAPACITY_EXCEEDED');
        self::clock($now,2592000);
        if ($now<$ledger['floor']['compacted_at'] || self::uint($anchor['sequence'])>PHP_INT_MAX-$pending) throw new \RuntimeException('LEDGER_CLOCK_OR_SEQUENCE_INVALID');
        foreach($snapshot['history'] as $history) {
            if (!in_array('bsre_consent_history:'.$history['receipt'],$plan['details']['eligible'],true)) continue;
            $row=['sequence_no'=>++$anchor['sequence'],'previous_hash'=>$anchor['hash'],'subject_key'=>$history['subject_key'],'receipt'=>$history['receipt'],'revision'=>(int)$history['revision'],'row_hash'=>self::rowHash($history),'retired_at'=>$now,'expires_at'=>$now+2592000,'plan_hash'=>$planHash];
            $row['chain_hash']=self::rowHash($row); $anchor['hash']=$row['chain_hash'];
            $ledger['rows'][]=$row;
        }
        return ['anchor'=>self::anchor($anchor['sequence'],$anchor['hash'],$ledger['floor']),'floor'=>$ledger['floor'],'rows'=>$ledger['rows']];
    }
    public static function validate(array $ledger): array {
        Guard::keys($ledger,['anchor','floor','rows']);Guard::keys($ledger['floor'],['sequence','hash','generation','compacted_at']);
        if(!is_array($ledger['rows'])||!array_is_list($ledger['rows'])||count($ledger['rows'])>1000)Guard::fail('PREFERENCE_LEDGER_UNBOUNDED');
        $floorRow=['sequence_no'=>$ledger['floor']['sequence'],'chain_hash'=>$ledger['floor']['hash'],'generation'=>$ledger['floor']['generation'],'compacted_at'=>$ledger['floor']['compacted_at']];
        $checkpoint=['sequence_no'=>$ledger['anchor']['sequence'],'chain_hash'=>$ledger['anchor']['hash']];$rows=$ledger['rows'];
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
    public static function empty(): array { $floor=['sequence'=>0,'hash'=>str_repeat('0',64),'generation'=>0,'compacted_at'=>0];return ['anchor'=>self::anchor(0,str_repeat('0',64),$floor),'floor'=>$floor,'rows'=>[]]; }
}
