<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
require_once __DIR__.'/PreferenceAtomicStore.php';
use BSRE\ActualRetention\PreferenceV1 as V;

/** Consumed owner runtime. No public route/hook/automatic migration or provider configuration. */
final class ActualPreferenceRetention {
    private function __construct(private V\Policy $policy,private V\Proofs $proofs,
        private V\Custody $custody,private V\AtomicStore $store) {}
    public static function bind(\BSRE\ClosedRetention\LeaseBoundWpdb $db,RuntimePolicy $binding,string $sourceVersion,string $partition,
        ?V\SignedTransport $transport=null,?V\IndependentKeys $independentKeys=null,?V\SnapshotKeys $encryptionKeys=null): self {
        V\Guard::enabled(); // Before source/owner/SQL/key/provider access.
        $policy=new V\Policy($binding,$sourceVersion,$partition);$policy->actor();
        $producer=new CanonicalCaptureProducer($db);
        $proofs=new V\Proofs($policy,$transport??new V\HeldTransport(),$independentKeys??new V\HeldKeys());
        $custody=new V\Custody($policy,$proofs,$encryptionKeys??new V\HeldKeys());
        return new self($policy,$proofs,$custody,new V\AtomicStore($db,$policy,$producer,$custody,$proofs));
    }
    public function previewDigest(string $action): string {
        if(!in_array($action,['RETIRE','RESTORE','COMPACT','BACKUP'],true))V\Guard::fail('PREFERENCE_ACTION_INVALID');
        return V\Guard::digest(['scope'=>$this->policy->scope(),'preview'=>$action]);
    }
    public function initialize(string $nonce): array {
        $digest=V\Guard::digest(['initialize'=>$this->policy->scope()]);
        $this->policy->authorize('INITIALIZE',$digest,$nonce);$authorization=$this->proofs->approval('INITIALIZE',$digest);
        return$this->store->session(function()use($authorization){$this->store->initialize($authorization);return['status'=>'INITIALIZED','anchor'=>$this->store->current()['anchor']];});
    }
    private function makePlan(string $action,array $current,array $snapshot,int $created,array $details): array {
        if($created<1||$created>PHP_INT_MAX-900)V\Guard::fail('PREFERENCE_PLAN_CLOCK_INVALID');
        return['contract'=>V\Policy::CONTRACT,'scope'=>$this->policy->scope(),'source'=>$this->policy->source(),
            'actor'=>$this->policy->actor(),'action'=>$action,'created_at'=>$created,'expires_at'=>$created+900,
            'anchor'=>$current['anchor'],'subjects'=>$snapshot['batch']['subjects'],'snapshot_hash'=>V\Guard::digest($snapshot),'details'=>$details];
    }
    private function authorize(array $plan,string $action,string $nonce): V\Authorization {
        V\Guard::keys($plan,['contract','scope','source','actor','action','created_at','expires_at','anchor','subjects','snapshot_hash','details']);
        if($plan['contract']!==V\Policy::CONTRACT||$plan['scope']!==$this->policy->scope()||$plan['source']!==$this->policy->source()||
            $plan['actor']!==$this->policy->actor()||$plan['action']!==$action||!is_int($plan['created_at'])||!is_int($plan['expires_at'])||
            $plan['created_at']<1||$plan['created_at']>PHP_INT_MAX-900||$plan['expires_at']!==$plan['created_at']+900||
            time()<$plan['created_at']||time()>=$plan['expires_at']||!is_array($plan['anchor'])||!is_array($plan['details']))V\Guard::fail('PREFERENCE_PLAN_EXPIRED_OR_INVALID');
        V\Custody::anchor($plan['anchor']);V\Guard::hash($plan['snapshot_hash']);$hash=V\Guard::digest($plan);
        V\SnapshotFormat::subjects($plan['subjects'],$this->policy->partition,$action==='COMPACT');
        $this->policy->authorize($action,$hash,$nonce);$authorization=$this->proofs->approval($action,$hash,$plan['expires_at']);
        if(time()>=$plan['expires_at'])V\Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');return$authorization;
    }
    private static function refs(array $snapshot,int $now): array {
        $review=V\SnapshotFormat::plan($snapshot,$now,true);$refs=[];
        foreach($review['rows'] as $row)if($row['classification']==='AGE_ELIGIBLE_FOR_REVIEW')$refs[]=$row['row_ref'];
        return$refs;
    }
    /** Private receipt/revision targets; these are never emitted by a public endpoint/log. */
    private static function targets(array $snapshot,array $refs): array {
        $out=[];
        foreach(['state'=>'subject_key','history'=>'receipt'] as $kind=>$pk)foreach($snapshot[$kind] as $row){
            $ref='bsre_consent_'.$kind.':'.$row[$pk];if(!in_array($ref,$refs,true))continue;
            $out[]=['row_ref'=>$ref,'subject_key'=>$row['subject_key'],'receipt'=>$row['receipt'],
                'revision'=>V\Guard::uint($row['revision']),'row_hash'=>V\Algebra::rowHash($row)];
        }
        usort($out,fn($a,$b)=>strcmp($a['row_ref'],$b['row_ref']));return$out;
    }
    public function discover(string $cursor,string $nonce): array {
        $this->policy->authorize('RETIRE',V\Guard::digest(['scope'=>$this->policy->scope(),'discover'=>$cursor]),$nonce);
        return$this->store->session(fn()=>$this->store->discover($cursor));
    }
    public function preview(array $subjects,string $nonce): array {
        $this->policy->authorize('RETIRE',$this->previewDigest('RETIRE'),$nonce);
        return$this->store->session(function()use($subjects){
            $current=$this->store->current();$snapshot=$this->store->snapshot(false,$subjects);$now=time();
            $refs=self::refs($snapshot,$now);$plan=$this->makePlan('RETIRE',$current,$snapshot,$now,['eligible'=>$refs,'targets'=>self::targets($snapshot,$refs)]);
            $this->proofs->coverage($plan['snapshot_hash'],$plan['details']['targets'],'RETIRE',V\Guard::digest($plan),$plan['expires_at']);
            return$plan;
        });
    }
    public function apply(array $plan,string $nonce): array {
        $authorization=$this->authorize($plan,'RETIRE',$nonce);$hash=$authorization->digest;
        return$this->store->session(fn()=>$this->store->mutate('RETIRE',$plan,$authorization,function($ledger,$snapshot)use($plan,$hash,$authorization){
            $refs=self::refs($snapshot,$plan['created_at']);$details=['eligible'=>$refs,'targets'=>self::targets($snapshot,$refs)];
            if($details!==$plan['details'])V\Guard::fail('PREFERENCE_PLAN_STALE_OR_ALTERED');
            if($refs===[])V\Guard::fail('PREFERENCE_NO_RETIREMENT_TARGETS');
            $until=$this->proofs->coverage($plan['snapshot_hash'],$details['targets'],'RETIRE',$hash,$plan['expires_at']);
            $deleted=$this->store->deleteExact($snapshot,$refs,$until);
            return['ledger'=>V\Algebra::append($snapshot,$plan,time(),$ledger),'affected'=>$deleted,'coverage_expires_at'=>$until];
        }));
    }
    private function restoreDetails(array $current,array $live,array $package,int $created,string $snapshotId): array {
        $backup=$package['snapshot'];$m=$package['metadata'];
        $backupPlan=V\Algebra::restorePlan($backup,$m,$current['ledger']['anchor'],$current['ledger'],$created);
        // Validate CURRENT captures and nested purpose touches independently of the backup.
        $liveRefs=V\Algebra::references($live,$current['ledger'],time());
        $targets=self::targets($live,$liveRefs);$mergeRefs=[];
        foreach(['state'=>'subject_key','history'=>'receipt'] as $kind=>$pk){
            $have=[];foreach($live[$kind] as $row)$have[$row[$pk]]=$row;
            foreach($backup[$kind] as $row){
                $ref='bsre_consent_'.$kind.':'.$row[$pk];if(in_array($ref,$backupPlan['eligible'],true))continue;
                $old=$have[$row[$pk]]??null;
                if($old!==null&&(V\Algebra::rowHash($old)===V\Algebra::rowHash($row)||
                    $kind==='state'&&V\Guard::uint($old['revision'])>V\Guard::uint($row['revision'])))continue;
                $mergeRefs[]=$ref;
            }
        }
        $targets=array_merge($targets,self::targets($backup,$mergeRefs));
        usort($targets,fn($a,$b)=>strcmp($a['row_ref'],$b['row_ref']));
        return['snapshot_id'=>$snapshotId,'backup_hash'=>V\Guard::digest($backup),'metadata_hash'=>V\Guard::digest($m),
            'skip_backup'=>$backupPlan['eligible'],'delete_current'=>$liveRefs,'targets'=>$targets];
    }
    public function previewRestore(string $snapshotId,string $nonce): array {
        V\Guard::hash($snapshotId);$this->policy->authorize('RESTORE',$this->previewDigest('RESTORE'),$nonce);
        return$this->store->session(function()use($snapshotId){
            $current=$this->store->current();$package=$this->custody->quarantine($snapshotId,$current['anchor']);$now=time();
            V\SnapshotFormat::plan($package['snapshot'],$now,true);
            $live=$this->store->snapshot(false,$package['snapshot']['batch']['subjects']);
            return$this->makePlan('RESTORE',$current,$live,$now,$this->restoreDetails($current,$live,$package,$now,$snapshotId));
        });
    }
    public function restore(array $plan,string $nonce): array {
        $authorization=$this->authorize($plan,'RESTORE',$nonce);$hash=$authorization->digest;
        return$this->store->session(fn()=>$this->store->mutate('RESTORE',$plan,$authorization,function($ledger,$live)use($plan,$hash,$authorization){
            $current=['anchor'=>$plan['anchor'],'ledger'=>$ledger];$id=$plan['details']['snapshot_id']??'';V\Guard::hash($id);
            $package=$this->custody->quarantine($id,$current['anchor']);
            $expected=$this->restoreDetails($current,$live,$package,$plan['created_at'],$id);
            // Recheck package expiry at execution, not merely at preview time.
            V\Algebra::restorePlan($package['snapshot'],$package['metadata'],$ledger['anchor'],$ledger,time());
            if($expected!==$plan['details'])V\Guard::fail('PREFERENCE_RESTORE_PLAN_STALE');
            $until=$this->proofs->coverage($plan['snapshot_hash'],$expected['targets'],'RESTORE',$hash,$plan['expires_at']);
            $deleted=$this->store->deleteExact($live,$expected['delete_current'],$until);
            $afterDelete=$this->store->snapshot(true,$plan['subjects']);
            $merged=$this->store->mergePreferences($afterDelete,$package['snapshot'],$expected['skip_backup'],$until);
            $after=$this->store->snapshot(true,$plan['subjects']);
            if(V\Algebra::references($after,$ledger,time())!==[]||$after['captures']!==$live['captures'])V\Guard::fail('PREFERENCE_RESTORE_REFERENCE_RECHECK_FAILED');
            return['ledger'=>$ledger,'affected'=>$deleted+$merged,'coverage_expires_at'=>$until];
        }));
    }
    public function previewCompaction(string $nonce): array {
        $this->policy->authorize('COMPACT',$this->previewDigest('COMPACT'),$nonce);
        return$this->store->session(function(){
            $current=$this->store->current();$snapshot=$this->store->snapshot(false,[],true);$now=time();
            $math=V\Algebra::compactionPlan($current['ledger'],$now,$current['ledger']['anchor']);
            return$this->makePlan('COMPACT',$current,$snapshot,$now,['algebra'=>$math,'key_id'=>$current['key_id']]);
        });
    }
    public function compact(array $plan,string $nonce): array {
        $authorization=$this->authorize($plan,'COMPACT',$nonce);$hash=$authorization->digest;
        return$this->store->session(fn()=>$this->store->mutate('COMPACT',$plan,$authorization,function($ledger,$snapshot)use($plan,$hash,$authorization){
            $math=V\Algebra::compactionPlan($ledger,$plan['created_at'],$ledger['anchor']);
            if($math!==($plan['details']['algebra']??null)||!is_string($plan['details']['key_id']??null))V\Guard::fail('PREFERENCE_COMPACTION_PLAN_STALE');
            if($math['delete_sequences']===[])V\Guard::fail('PREFERENCE_NO_EXPIRED_LEDGER_PREFIX');
            $until=$this->proofs->coverage($plan['snapshot_hash'],[],'COMPACT',$hash,$plan['expires_at']);
            $this->store->useCoverage($until);
            $transition=$this->custody->prepareCompaction($plan['details']['key_id'],$plan['anchor'],$math['after_floor'],$hash,$authorization);
            $remaining=array_values(array_filter($ledger['rows'],fn($row)=>!in_array($row['sequence_no'],$math['delete_sequences'],true)));
            if(count($ledger['rows'])-count($remaining)!==count($math['delete_sequences']))V\Guard::fail('PREFERENCE_COMPACTION_COUNT_CONFLICT');
            $after=V\Algebra::validate(['anchor'=>$ledger['anchor'],'floor'=>$math['after_floor'],'rows'=>$remaining]);
            return['ledger'=>$after,'affected'=>count($math['delete_sequences']),'coverage_expires_at'=>$until,'key_transition'=>$transition];
        }));
    }
    public function previewBackup(array $subjects,string $nonce): array {
        $this->policy->authorize('BACKUP',$this->previewDigest('BACKUP'),$nonce);
        return$this->store->session(fn()=>$this->makePlan('BACKUP',$this->store->current(),$this->store->snapshot(false,$subjects),time(),[]));
    }
    public function backup(array $plan,string $nonce): array {
        $authorization=$this->authorize($plan,'BACKUP',$nonce);$snapshotResult=null;
        $result=$this->store->session(function()use($plan,$authorization,&$snapshotResult){return$this->store->mutate('BACKUP',$plan,$authorization,function($ledger,$snapshot)use($plan,$authorization,&$snapshotResult){
            $snapshotResult=$this->custody->backup($snapshot,$plan['anchor'],$authorization);
            return['ledger'=>$ledger,'affected'=>0,'coverage_expires_at'=>time()+30];
        });});
        return$result+['snapshot'=>$snapshotResult];
    }
    public function expireBackup(string $snapshotId,string $nonce): array {
        V\Guard::hash($snapshotId);$digest=V\Guard::digest(['expire_snapshot'=>$snapshotId,'scope'=>$this->policy->scope()]);
        $this->policy->authorize('EXPIRE_BACKUP',$digest,$nonce);$authorization=$this->proofs->approval('EXPIRE_BACKUP',$digest);
        $this->custody->expire($snapshotId,$authorization);return['status'=>'SNAPSHOT_AND_KEY_ABSENT','snapshot_id'=>$snapshotId];
    }
    public function reconcile(string $operation,string $nonce): array {
        V\Guard::hash($operation);$hash=V\Guard::digest(['reconcile'=>$operation,'scope'=>$this->policy->scope()]);
        $this->policy->authorize('RECONCILE',$hash,$nonce);$authorization=$this->proofs->approval('RECONCILE',$hash);
        return$this->store->session(fn()=>$this->store->reconcile($operation,$authorization),true);
    }
    /** Integration must consume this gate before claiming complete first-ever history. */
    public function assertQualificationHistoryComplete(): void {
        $this->store->session(function(){if($this->store->current()['ledger']['floor']['generation']>0)V\Guard::fail('PREFERENCE_COMPACTED_HISTORY_INCOMPLETE');});
    }
}
