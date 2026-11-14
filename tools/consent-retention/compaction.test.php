<?php
declare(strict_types=1);
/** Synthetic planning/guard checks. Real SQL behavior is tested separately. */
define('ABSPATH', __DIR__ . '/');
define('ARRAY_A','ARRAY_A');
define('BSRE_RETENTION_LAB',true);
$owner=true; $environment='local'; $origin='http://bsre.invalid';
function current_user_can($cap): bool { return $GLOBALS['owner']; }
function get_current_user_id(): int { return 1; }
function wp_get_environment_type(): string { return $GLOBALS['environment']; }
function home_url(): string { return $GLOBALS['origin']; }
require __DIR__.'/PreferenceRetirement.php';
use BSRE\RetentionReview\RetirementLedger;
use BSRE\RetentionReview\PreferenceRetirement;

final class CompactionFixtureDb {
    public string $prefix='retention_synthetic_';
    public string $last_error='';
    public int $writes=0;
    public $transaction='0';
    public array $rows=[];
    public array $checkpoint=['id'=>'1','sequence_no'=>'0','chain_hash'=>''];
    public array $floor=['id'=>'1','sequence_no'=>'0','chain_hash'=>'','generation'=>'0','compacted_at'=>'0'];
    public function __construct() { $this->checkpoint['chain_hash']=$this->floor['chain_hash']=str_repeat('0',64); }
    public function prepare($sql,...$args): string { return vsprintf(str_replace('%s',"'%s'",$sql),$args); }
    public function get_row($sql,$mode): ?array {
        if (str_starts_with($sql,'SHOW TABLE STATUS')) return ['Engine'=>'InnoDB'];
        return str_contains($sql,'retirement_checkpoint') ? $this->checkpoint : $this->floor;
    }
    public function get_results($sql,$mode): array { return $this->rows; }
    public function get_var($sql) { return $this->transaction; }
    public function query($sql) { ++$this->writes; throw new RuntimeException('SYNTHETIC_UNEXPECTED_MUTATION'); }
}
$checks=[];
function cc(string $name,bool $ok): void { global $checks; if(!$ok)throw new RuntimeException('Synthetic compaction check failed: '.$name); $checks[$name]=true; }
function cd(callable $call,string $code): bool { try{$call();return false;}catch(Throwable $e){return $e->getMessage()===$code;} }
$db=new CompactionFixtureDb(); $ledger=new RetirementLedger($db); $control=new PreferenceRetirement($db,fn()=>2000000000);
$empty=$ledger->read(false); $now=2000000000;
cc('direct_preview_disabled_before_io',cd(fn()=>$ledger->compactionPlan($empty,$now,$empty['anchor']),'COMPACTION_DISABLED') && $db->writes===0);
cc('direct_mutation_disabled_before_io',cd(fn()=>$ledger->compact([], '', [],$now),'COMPACTION_DISABLED') && $db->writes===0);
cc('wrapper_preview_disabled_before_io',cd(fn()=>$control->previewLedgerCompaction($empty['anchor']),'COMPACTION_DISABLED') && $db->writes===0);
$db->prefix='retention_compaction_synthetic_';
cc('second_prefix_default_disabled',cd(fn()=>new RetirementLedger($db),'ISOLATED_LAB_ONLY'));
$db->prefix='retention_synthetic_';
define('BSRE_RETENTION_COMPACTION_ENABLED',true);
$plan=$ledger->compactionPlan($empty,$now,$empty['anchor']);
cc('no_due_rows_preserve_genesis', $plan['delete_sequences']===[] && $plan['after_floor']===$empty['floor'] && !isset($empty['anchor']['version']));
cc('separate_apply_default_disabled',cd(fn()=>$ledger->compact($plan,PreferenceRetirement::compactionApproval($plan),$empty['anchor'],$now),'COMPACTION_DISABLED'));
$owner=false;
cc('direct_preview_requires_owner',cd(fn()=>$ledger->compactionPlan($empty,$now,$empty['anchor']),'OWNER_REQUIRED'));
$owner=true;
$db->prefix='live_';
cc('mutable_prefix_rechecked',cd(fn()=>$ledger->compactionPlan($empty,$now,$empty['anchor']),'ISOLATED_LAB_ONLY'));
$db->prefix='retention_synthetic_'; $environment='production';
cc('environment_rechecked',cd(fn()=>$ledger->compactionPlan($empty,$now,$empty['anchor']),'ISOLATED_LAB_ONLY'));
$environment='local'; $origin='https://example.invalid';
cc('origin_rechecked',cd(fn()=>$ledger->compactionPlan($empty,$now,$empty['anchor']),'ISOLATED_LAB_ONLY'));
$origin='http://bsre.invalid';
cc('clock_overflow_and_negative_hold',cd(fn()=>$ledger->compactionPlan($empty,PHP_INT_MAX,$empty['anchor']),'LEDGER_CLOCK_INVALID') && cd(fn()=>$ledger->compactionPlan($empty,-1,$empty['anchor']),'LEDGER_CLOCK_INVALID'));
cc('different_anchor_holds',cd(fn()=>$ledger->compactionPlan($empty,$now,['sequence'=>1,'hash'=>str_repeat('0',64)]),'CURRENT_LEDGER_ANCHOR_REQUIRED'));
$chain=$empty; $previous=str_repeat('0',64);
foreach([$now,$now+10,$now-10] as $index=>$expiry) {
    $row=['sequence_no'=>$index+1,'previous_hash'=>$previous,'subject_key'=>str_repeat('a',64),'receipt'=>str_pad((string)($index+1),32,'0',STR_PAD_LEFT),'revision'=>1,'row_hash'=>str_repeat('b',64),'retired_at'=>$expiry-2592000,'expires_at'=>$expiry,'plan_hash'=>str_repeat('c',64)];
    $row['chain_hash']=RetirementLedger::rowHash($row); $previous=$row['chain_hash']; $chain['rows'][]=$row;
}
$chain['anchor']=['sequence'=>3,'hash'=>$previous];
$prefix=$ledger->compactionPlan($chain,$now,$chain['anchor']);
cc('exact_boundary_and_contiguous_prefix_only',$prefix['delete_sequences']===[1] && $prefix['after_floor']['sequence']===1 && $prefix['after_floor']['generation']===1);
cc('plan_contains_no_private_row_fields',!preg_match('/subject_key|receipt|retired_at|row_hash/',json_encode($prefix,JSON_THROW_ON_ERROR)));
$db->checkpoint['sequence_no']='18446744073709551615';
cc('unsigned_db_overflow_rejected',cd(fn()=>$ledger->read(false),'LEDGER_INTEGER_OUT_OF_RANGE'));
$db->checkpoint['sequence_no']='0';
$snapshot=['history'=>[['receipt'=>str_repeat('d',32),'subject_key'=>str_repeat('e',64),'revision'=>1]]];
cc('retained_capacity_check_preserved',cd(fn()=>$ledger->record($snapshot,['eligible'=>['bsre_consent_history:'.str_repeat('d',32)]],$now,['anchor'=>['sequence'=>1000,'hash'=>str_repeat('0',64)],'rows'=>array_fill(0,1000,[])]),'LEDGER_CAPACITY_EXCEEDED'));
define('BSRE_RETENTION_APPLY_ENABLED',true);
cc('direct_exact_approval_required',cd(fn()=>$ledger->compact($plan,'bad',$empty['anchor'],$now),'EXACT_COMPACTION_APPROVAL_REQUIRED'));
$db->transaction='1';
cc('caller_transaction_never_committed_or_rolled_back',cd(fn()=>$ledger->compact($plan,PreferenceRetirement::compactionApproval($plan),$empty['anchor'],$now),'EXISTING_TRANSACTION_FORBIDDEN') && $db->writes===0);
$db->transaction=null;
cc('unknown_transaction_state_holds',cd(fn()=>$ledger->compact($plan,PreferenceRetirement::compactionApproval($plan),$empty['anchor'],$now),'TRANSACTION_STATE_UNAVAILABLE') && $db->writes===0);
echo json_encode(['scope'=>'SYNTHETIC_LEDGER_COMPACTION_GUARDS','status'=>'PASS','checks'=>$checks,'production_authorized'=>false],JSON_THROW_ON_ERROR)."\n";
