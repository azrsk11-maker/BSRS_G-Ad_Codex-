<?php
declare(strict_types=1);
namespace BSRE\RetentionReview\PerChoice\ApplicationV1;
if (!defined('ABSPATH')) exit;
require_once __DIR__.'/PerChoicePlanner.php';
require_once __DIR__.'/PurposeChoicePlanner.php';
use BSRE\RetentionReview\PerChoice\PerChoicePlanner as Planner;
use BSRE\RetentionReview\RetentionInventory;

final class SelectiveFailure extends \RuntimeException {}

/** First selective application in an explicitly enabled disposable lab, never a production writer. */
final class SelectiveChoiceRetirement {
    private $db; private $clock; private bool $commitUncertain=false; private bool $purposeMode=false;
    public const PREFIX='per_choice_synthetic_';
    public const SCOPE='SYNTHETIC_PER_CHOICE_APPLICATION_V1';
    public const PURPOSE_PREFIX='per_choice_purpose_synthetic_';
    public const PURPOSE_SCOPE='SYNTHETIC_PURPOSE_PER_CHOICE_APPLICATION_V1';
    private const ZERO='0000000000000000000000000000000000000000000000000000000000000000';
    public function __construct($db,?callable $clock=null,string $mode='PLAIN') {
        if(!in_array($mode,['PLAIN','PURPOSE_LAB'],true))self::fail('SELECTIVE_MODE_INVALID');
        $this->purposeMode=$mode==='PURPOSE_LAB';$this->db=$db;$this->clock=$clock??fn()=>time();$this->guard();
    }
    public static function purposeLab($db,?callable $clock=null): self {return new self($db,$clock,'PURPOSE_LAB');}
    private function prefix(): string {return $this->purposeMode?self::PURPOSE_PREFIX:self::PREFIX;}
    private function scope(): string {return $this->purposeMode?self::PURPOSE_SCOPE:self::SCOPE;}
    private static function fail(string $code): never { throw new SelectiveFailure($code); }
    private function guard(bool $apply=false): void {
        if (!defined('BSRE_PER_CHOICE_LAB_ENABLED') || BSRE_PER_CHOICE_LAB_ENABLED!==true) self::fail('SELECTIVE_COMPONENT_DISABLED');
        if($this->purposeMode&&(!defined('BSRE_PER_CHOICE_PURPOSE_LAB_ENABLED')||BSRE_PER_CHOICE_PURPOSE_LAB_ENABLED!==true))self::fail('SELECTIVE_PURPOSE_COMPONENT_DISABLED');
        if (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB!==true || wp_get_environment_type()!=='local' || home_url()!=='http://bsre.invalid' || $this->db->prefix!==$this->prefix()) self::fail('SELECTIVE_ISOLATED_LAB_ONLY');
        if (!current_user_can('manage_options') || get_current_user_id()<1) self::fail('SELECTIVE_OWNER_REQUIRED');
        if ($apply && (!defined('BSRE_PER_CHOICE_APPLY_ENABLED') || BSRE_PER_CHOICE_APPLY_ENABLED!==true)) self::fail('SELECTIVE_APPLY_DISABLED');
        if($apply&&$this->purposeMode&&(!defined('BSRE_PER_CHOICE_PURPOSE_APPLY_ENABLED')||BSRE_PER_CHOICE_PURPOSE_APPLY_ENABLED!==true))self::fail('SELECTIVE_PURPOSE_APPLY_DISABLED');
        if ($apply && $this->commitUncertain) self::fail('SELECTIVE_FRESH_READBACK_REQUIRED');
    }
    private function now(): int {
        try{$now=($this->clock)();}catch(\Throwable $error){self::fail('SELECTIVE_CLOCK_INVALID');}
        if (!is_int($now) || $now<1 || $now>4102443900) self::fail('SELECTIVE_CLOCK_INVALID');return $now;
    }
    private function query(string $sql): int {
        try{$result=$this->db->query($sql);}catch(\Throwable $error){self::fail('SELECTIVE_STORAGE_UNAVAILABLE');}
        if($result===false)self::fail('SELECTIVE_STORAGE_UNAVAILABLE');return(int)$result;
    }
    private function session(): void {
        $this->db->last_error='';$active=$this->db->get_var('SELECT @@session.in_transaction');
        if($this->db->last_error!=='' || !in_array($active,[0,1,'0','1'],true))self::fail('SELECTIVE_TRANSACTION_STATE_UNAVAILABLE');
        if((string)$active!=='0')self::fail('SELECTIVE_CALLER_TRANSACTION_FORBIDDEN');
        $this->db->last_error='';$isolation=$this->db->get_var('SELECT @@session.tx_isolation');
        if($this->db->last_error!=='' || $isolation!=='REPEATABLE-READ')self::fail('SELECTIVE_REPEATABLE_READ_REQUIRED');
    }
    private function transaction(callable $operation) {
        $this->session();
        $this->query('START TRANSACTION');
        try{$result=$operation();}catch(\Throwable $error){
            try{$rolledBack=$this->db->query('ROLLBACK');}catch(\Throwable $rollbackError){$rolledBack=false;}
            if($rolledBack===false){$this->commitUncertain=true;self::fail('SELECTIVE_FRESH_READBACK_REQUIRED');}
            if($error instanceof SelectiveFailure)throw $error;self::fail('SELECTIVE_OPERATION_UNAVAILABLE');
        }
        // A false COMMIT response cannot prove whether the server committed. Never blind-retry.
        try{$committed=$this->db->query('COMMIT');}catch(\Throwable $error){$committed=false;}
        if($committed===false){$this->commitUncertain=true;self::fail('SELECTIVE_COMMIT_AMBIGUOUS_READBACK_REQUIRED');}
        return $result;
    }
    private function engine(string $table): void {
        $this->db->last_error='';$row=$this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$table),ARRAY_A);
        if($this->db->last_error!=='' || !$row || strtolower((string)$row['Engine'])!=='innodb')self::fail('SELECTIVE_TRANSACTIONAL_TABLE_REQUIRED');
    }
    private static function uint($value): int {
        if(is_int($value)&&$value>=0)return $value;
        if(!is_string($value)||!preg_match('/^(0|[1-9][0-9]*)$/D',$value)||strlen($value)>strlen((string)PHP_INT_MAX)||(strlen($value)===strlen((string)PHP_INT_MAX)&&strcmp($value,(string)PHP_INT_MAX)>0))self::fail('SELECTIVE_INTEGER_INVALID');
        return(int)$value;
    }
    private function rawControl(): array {
        $table=$this->prefix().'bsre_choice_control';$this->engine($table);$this->db->last_error='';
        $rows=$this->db->get_results("SELECT * FROM {$table} ORDER BY id LIMIT 2 FOR UPDATE",ARRAY_A);
        if($this->db->last_error!==''||!is_array($rows)||count($rows)!==1||self::uint($rows[0]['id']??null)!==1)self::fail('SELECTIVE_CONTROL_INVALID');
        $row=$rows[0];$keys=array_keys($row);sort($keys);$expected=['id','generation','chain_hash','history_gap','last_plan_hash','snapshot_hash'];sort($expected);
        if($keys!==$expected || !in_array($row['history_gap'],[0,1,'0','1'],true))self::fail('SELECTIVE_CONTROL_INVALID');
        foreach(['chain_hash','last_plan_hash','snapshot_hash']as$key)if(!is_string($row[$key])||!preg_match('/^[a-f0-9]{64}$/D',$row[$key]))self::fail('SELECTIVE_CONTROL_INVALID');
        $anchor=['version'=>1,'generation'=>self::uint($row['generation']),'chain_hash'=>$row['chain_hash'],'history_incomplete'=>(bool)$row['history_gap'],'last_plan_hash'=>$row['last_plan_hash'],'snapshot_hash'=>$row['snapshot_hash']];
        if($anchor['generation']===0&&($anchor['chain_hash']!==self::ZERO||$anchor['history_incomplete']||$anchor['last_plan_hash']!==self::ZERO||$anchor['snapshot_hash']!==self::ZERO))self::fail('SELECTIVE_CONTROL_INVALID');
        $this->engine($table);return $anchor;
    }
    private function auditRows(): array {
        $table=$this->prefix().'bsre_choice_audit';$this->engine($table);$this->db->last_error='';
        $rows=$this->db->get_results("SELECT * FROM {$table} ORDER BY generation LIMIT 1001 FOR UPDATE",ARRAY_A);
        if($this->db->last_error!==''||!is_array($rows)||count($rows)>1000)self::fail('SELECTIVE_AUDIT_UNAVAILABLE');
        $this->engine($table);return $rows;
    }
    private static function genesis(): array {return ['version'=>1,'generation'=>0,'chain_hash'=>self::ZERO,'history_incomplete'=>false,'last_plan_hash'=>self::ZERO,'snapshot_hash'=>self::ZERO];}
    private static function nextAnchor(array $previous,array $record): array {
        return ['version'=>1,'generation'=>$record['generation'],'chain_hash'=>Planner::digest(['previous'=>$previous,'record'=>$record]),
            'history_incomplete'=>$previous['history_incomplete']||$record['deleted_history']>0,'last_plan_hash'=>$record['plan_hash'],'snapshot_hash'=>$record['after_hash']];
    }
    private function readControl(): array {
        $current=$this->rawControl();$audit=$this->auditRows();$previous=self::genesis();$lastTime=0;
        foreach($audit as$row){
            $keys=array_keys($row);sort($keys);$expected=['plan_hash','generation','before_hash','after_hash','before_anchor_hash','after_anchor_hash','deleted_state','deleted_history','applied_at','actor'];sort($expected);
            if($keys!==$expected||$previous['history_incomplete'])self::fail('SELECTIVE_AUDIT_CONTROL_MISMATCH');
            foreach(['plan_hash','before_hash','after_hash','before_anchor_hash','after_anchor_hash']as$key)if(!is_string($row[$key])||!preg_match('/^[a-f0-9]{64}$/D',$row[$key]))self::fail('SELECTIVE_AUDIT_CONTROL_MISMATCH');
            $record=[];foreach(['plan_hash','generation','before_hash','after_hash','deleted_state','deleted_history','applied_at','actor']as$key)$record[$key]=in_array($key,['generation','deleted_state','deleted_history','applied_at','actor'],true)?self::uint($row[$key]):$row[$key];
            if($previous['generation']===PHP_INT_MAX||$record['generation']!==$previous['generation']+1||$record['deleted_state']+$record['deleted_history']<1||$record['deleted_state']+$record['deleted_history']>1000||$record['actor']<1||$record['applied_at']<$lastTime||$row['before_anchor_hash']!==Planner::digest($previous))self::fail('SELECTIVE_AUDIT_CONTROL_MISMATCH');
            $next=self::nextAnchor($previous,$record);if($row['after_anchor_hash']!==Planner::digest($next))self::fail('SELECTIVE_AUDIT_CONTROL_MISMATCH');
            $previous=$next;$lastTime=$record['applied_at'];
        }
        if($current!==$previous)self::fail('SELECTIVE_AUDIT_CONTROL_MISMATCH');return $current;
    }
    private function snapshot(): array {
        $snapshot=['kind'=>RetentionInventory::KIND];$total=0;
        foreach(['state'=>'subject_key','history'=>'receipt','captures'=>'request_id']as$part=>$pk){
            $table=$this->prefix().'bsre_consent_'.$part;$this->engine($table);$this->db->last_error='';
            $snapshot[$part]=$this->db->get_results("SELECT * FROM {$table} ORDER BY {$pk} LIMIT 1001 FOR UPDATE",ARRAY_A);
            if($this->db->last_error!==''||!is_array($snapshot[$part]))self::fail('SELECTIVE_STORAGE_UNAVAILABLE');
            $total+=count($snapshot[$part]);if($total>RetentionInventory::MAX_ROWS)self::fail('SELECTIVE_SNAPSHOT_UNBOUNDED');
            $this->engine($table);
        }return $snapshot;
    }
    public function installLabTables(): void {
        $this->guard(true);$this->session();$p=$this->prefix();$present=[];
        foreach(['bsre_choice_control','bsre_choice_audit','bsre_consent_state','bsre_consent_history','bsre_consent_captures']as$table){
            $this->db->last_error='';$row=$this->db->get_row($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$p.$table),ARRAY_A);
            if($this->db->last_error!=='')self::fail('SELECTIVE_STORAGE_UNAVAILABLE');$present[$table]=(bool)$row;
        }
        if($present['bsre_choice_control']&&$present['bsre_choice_audit']){$this->transaction(fn()=>$this->readControl());return;}
        if(in_array(true,$present,true))self::fail('SELECTIVE_PARTIAL_INSTALLATION');
        $this->query("CREATE TABLE {$p}bsre_choice_control (id tinyint PRIMARY KEY,generation bigint unsigned NOT NULL,chain_hash char(64) NOT NULL,history_gap tinyint NOT NULL,last_plan_hash char(64) NOT NULL,snapshot_hash char(64) NOT NULL) ENGINE=InnoDB");
        $this->query("CREATE TABLE {$p}bsre_choice_audit (plan_hash char(64) PRIMARY KEY,generation bigint unsigned NOT NULL UNIQUE,before_hash char(64) NOT NULL,after_hash char(64) NOT NULL,before_anchor_hash char(64) NOT NULL,after_anchor_hash char(64) NOT NULL,deleted_state int unsigned NOT NULL,deleted_history int unsigned NOT NULL,applied_at bigint unsigned NOT NULL,actor bigint unsigned NOT NULL) ENGINE=InnoDB");
        $this->query($this->db->prepare("INSERT INTO {$p}bsre_choice_control VALUES (1,0,%s,0,%s,%s)",self::ZERO,self::ZERO,self::ZERO));
    }
    /** Private actual synthetic source; never print, export, or log its rows. */
    public function reviewSource(): array {
        $this->guard();return $this->transaction(fn()=>['anchor'=>$this->readControl(),'snapshot'=>$this->snapshot()]);
    }
    public function anchor(): array {$this->guard();return $this->transaction(fn()=>$this->readControl());}
    private function makePlan(array $snapshot,array $coverage,array $anchor,int $now): array {
        if($anchor['history_incomplete'])self::fail('SELECTIVE_HISTORY_RECONCILIATION_REQUIRED');
        if($this->purposeMode){
            try{$review=\BSRE\RetentionReview\PerChoice\PurposeV1\PurposeChoicePlanner::plan($snapshot,$coverage,$now,true);}
            catch(\Throwable $error){self::fail('SELECTIVE_PURPOSE_LINEAGE_UNRESOLVED');}
        }else $review=Planner::plan($snapshot,$coverage,$now,true);
        if($review['global_reasons'])self::fail('SELECTIVE_SOURCE_COVERAGE_UNRESOLVED');
        $unresolved=['HISTORY_GAP','CURRENT_HISTORY_LINEAGE_MISSING','HISTORY_TIME_REGRESSION','CURRENT_HISTORY_MISMATCH','CHOICE_CLOCK_UNRESOLVED','CHOICE_PERMISSION_UNRESOLVED','CAPTURE_LINEAGE_UNRESOLVED','CURRENT_PREFERENCE_WINDOW_UNRESOLVED','DUPLICATE_CURRENT_STATE','DUPLICATE_HISTORY_REVISION'];
        foreach($review['rows']as$row)if(array_intersect($row['reasons'],$unresolved))self::fail('SELECTIVE_SOURCE_COVERAGE_UNRESOLVED');
        $selected=[];$after=$snapshot;$counts=['state'=>0,'history'=>0];
        foreach($review['rows']as$row)if($row['classification']==='DUE_UNREFERENCED_SYNTHETIC_REVIEW')$selected[]=$row['row_ref'];
        foreach(['state'=>'subject_key','history'=>'receipt']as$part=>$pk){
            $after[$part]=array_values(array_filter($snapshot[$part],function($row)use($part,$pk,$selected,&$counts){
                if(in_array('bsre_consent_'.$part.':'.$row[$pk],$selected,true)){++$counts[$part];return false;}return true;
            }));
        }
        return ['version'=>1,'scope'=>$this->scope(),'created_at'=>$now,'expires_at'=>min($now+900,$coverage['valid_until']),
            'coverage'=>$coverage,'anchor'=>$anchor,'source_hash'=>Planner::digest($snapshot),'planner_hash'=>$review['plan_sha256'],
            'selected'=>$selected,'expected_after_hash'=>Planner::digest($after),'deleted_state'=>$counts['state'],'deleted_history'=>$counts['history']];
    }
    public function preview(array $coverage,array $currentAnchor): array {
        $this->guard();$now=$this->now();return $this->transaction(function()use($coverage,$currentAnchor,$now){
            $anchor=$this->readControl();if($anchor!==$currentAnchor)self::fail('SELECTIVE_CURRENT_ANCHOR_REQUIRED');
            return $this->makePlan($this->snapshot(),$coverage,$anchor,$now);
        });
    }
    /** Exact lab acknowledgement, not owner approval, source authentication or production authority. */
    public static function labAcknowledgement(array $plan): string {return 'APPLY_SYNTHETIC_PER_CHOICE:'.Planner::digest($plan);}
    public function apply(array $plan,string $labAcknowledgement,array $currentAnchor): array {
        $this->guard(true);$now=$this->now();
        if(!hash_equals(self::labAcknowledgement($plan),$labAcknowledgement))self::fail('SELECTIVE_EXACT_LAB_ACK_REQUIRED');
        if(!isset($plan['created_at'],$plan['expires_at'])||!is_int($plan['created_at'])||!is_int($plan['expires_at'])||$plan['created_at']<1||$plan['created_at']>4102443900||$plan['expires_at']<=$plan['created_at']||$plan['expires_at']>$plan['created_at']+900||$now<$plan['created_at']||$now>=$plan['expires_at'])self::fail('SELECTIVE_PLAN_EXPIRED_OR_INVALID');
        return $this->transaction(function()use($plan,$currentAnchor,$now){
            $before=$this->readControl();if($before!==$currentAnchor||($plan['anchor']??null)!==$before)self::fail('SELECTIVE_CURRENT_ANCHOR_REQUIRED');
            $audits=$this->auditRows();if($before['generation']!==count($audits))self::fail('SELECTIVE_AUDIT_CONTROL_MISMATCH');
            $snapshot=$this->snapshot();if(Planner::digest($snapshot)!==($plan['source_hash']??null))self::fail('SELECTIVE_PLAN_STALE_OR_ALTERED');
            $expected=$this->makePlan($snapshot,$plan['coverage']??[],$before,$plan['created_at']);
            if(!hash_equals(Planner::digest($expected),Planner::digest($plan)))self::fail('SELECTIVE_PLAN_STALE_OR_ALTERED');
            if(!$plan['selected'])return ['scope'=>$this->scope(),'status'=>'NO_ROWS_SELECTED','deleted_rows'=>0,'anchor'=>$before,'history_incomplete'=>false,'production_acceptance'=>false,'reopen_authorized'=>false];
            if($before['generation']===PHP_INT_MAX)self::fail('SELECTIVE_INTEGER_INVALID');
            $counts=['state'=>0,'history'=>0];
            foreach($plan['selected']as$ref){
                if(!is_string($ref)||!preg_match('/^bsre_consent_(state|history):([a-f0-9]+)$/D',$ref,$match))self::fail('SELECTIVE_ROW_SCOPE_INVALID');
                $part=$match[1];$pk=$part==='state'?'subject_key':'receipt';
                $counts[$part]+=$this->query($this->db->prepare('DELETE FROM '.$this->prefix().'bsre_consent_'.$part.' WHERE '.$pk.'=%s',$match[2]));
            }
            if($counts['state']!==$plan['deleted_state']||$counts['history']!==$plan['deleted_history'])self::fail('SELECTIVE_DELETE_COUNT_CONFLICT');
            $afterSnapshot=$this->snapshot();if(Planner::digest($afterSnapshot)!==$plan['expected_after_hash'])self::fail('SELECTIVE_RETAINED_STATE_CHANGED');
            $hash=Planner::digest($plan);$record=['plan_hash'=>$hash,'generation'=>$before['generation']+1,'before_hash'=>$plan['source_hash'],'after_hash'=>$plan['expected_after_hash'],
                'deleted_state'=>$counts['state'],'deleted_history'=>$counts['history'],'applied_at'=>$now,'actor'=>get_current_user_id()];$next=self::nextAnchor($before,$record);
            $this->query($this->db->prepare('INSERT INTO '.$this->prefix().'bsre_choice_audit VALUES (%s,%d,%s,%s,%s,%s,%d,%d,%d,%d)',$hash,$next['generation'],$plan['source_hash'],$plan['expected_after_hash'],Planner::digest($before),Planner::digest($next),$counts['state'],$counts['history'],$now,get_current_user_id()));
            $updated=$this->query($this->db->prepare('UPDATE '.$this->prefix().'bsre_choice_control SET generation=%d,chain_hash=%s,history_gap=%d,last_plan_hash=%s,snapshot_hash=%s WHERE id=1 AND generation=%d',$next['generation'],$next['chain_hash'],(int)$next['history_incomplete'],$hash,$next['snapshot_hash'],$before['generation']));
            if($updated!==1||$this->readControl()!==$next)self::fail('SELECTIVE_CONTROL_WRITE_CONFLICT');
            return ['scope'=>$this->scope(),'status'=>'SYNTHETIC_ROWS_APPLIED','deleted_rows'=>array_sum($counts),'anchor'=>$next,'history_incomplete'=>$next['history_incomplete'],'production_acceptance'=>false,'reopen_authorized'=>false];
        });
    }
    /** Read-only exact last-operation readback. It never clears a gap or authorizes reopening. */
    public function reconcileLast(array $plan,array $currentAnchor): array {
        $this->guard();return $this->transaction(function()use($plan,$currentAnchor){
            $anchor=$this->readControl();if($anchor!==$currentAnchor)self::fail('SELECTIVE_CURRENT_ANCHOR_REQUIRED');
            $hash=Planner::digest($plan);$audits=$this->auditRows();$row=end($audits);
            if(!$row||$anchor['last_plan_hash']!==$hash||$row['plan_hash']!==$hash||self::uint($row['generation'])!==$anchor['generation']||$row['after_anchor_hash']!==Planner::digest($anchor)||$row['before_anchor_hash']!==Planner::digest($plan['anchor']??[])||$row['before_hash']!==($plan['source_hash']??null)||$row['after_hash']!==($plan['expected_after_hash']??null)||self::uint($row['deleted_state'])!==($plan['deleted_state']??null)||self::uint($row['deleted_history'])!==($plan['deleted_history']??null))self::fail('SELECTIVE_RECONCILIATION_EVIDENCE_MISMATCH');
            if(Planner::digest($this->snapshot())!==$row['after_hash'])self::fail('SELECTIVE_RECONCILIATION_CURRENT_STATE_CHANGED');
            return ['scope'=>$this->scope(),'last_operation_reconciled'=>true,'history_incomplete'=>$anchor['history_incomplete'],'future_application_authorized'=>false,'production_acceptance'=>false,'reopen_authorized'=>false];
        });
    }
}
