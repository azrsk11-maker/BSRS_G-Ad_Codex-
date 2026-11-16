<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
require_once __DIR__.'/ActualRetirementPort.php';
require_once __DIR__.'/../closed-enquiry-retention/ActualReceiverJournal.php';
use BSRE\ActualRetention\ReceiverV1\{Guard,ReceiverRuntimeProof};
use BSRE\ClosedRetention\{RetirementIntent,NoMailCopyProof,Workflow};

/** Consumed operational path, separate from the immutable synthetic owner controller/workflow. */
final class ActualReceiverWorkflow {
    public function __construct(private ActualReceiverJournal $journal,private ActualRetirementPort $port,
        private \BSRE\ClosedRetention\LeaseBoundWpdb $db,private CanonicalCaptureProducer $producer) {
        Guard::need($journal->receiverProof()===$port->proof(),'G5_RECEIVER_CONSUMER_POLICY_CONFLICT');
    }
    private function current():void {$this->journal->runtimePolicy()->actor();$this->producer->assertCurrent($this->db);}
    /** The exact approved plan is durably recorded before the first mutable source call. */
    public function retire(array $record,int $now):array {
        Guard::now($now);$this->current();RetirementIntent::validateRecord($record,time());
        Guard::need($record['plan']['actor']===$this->journal->runtimePolicy()->actor(),'G5_RECEIVER_OWNER_INTENT_CONFLICT');
        return $this->journal->locked($record['plan']['closure_id'],function()use($record):array{
            $this->current();
            if($record['revision']===0)$this->journal->stageRetirement($record,time());
            $this->journal->assertRetirementSource($record,time());
            $this->journal->registerReceiverIntent($record,time());
            // Inspection is positive exact identity+zero-attempt evidence. Missing rows never clear.
            $inspection=$this->port->inspect($record['plan']['scope'],time());
            Guard::need($inspection!==null,'G5_RECEIVER_INSPECTION_UNVERIFIED');
            $this->port->proof()->inspection($inspection,$record['plan']['scope'],time());
            $this->journal->assertRetirementSource($record,time());$this->current();
            $proof=$this->port->retire($record['plan']['scope'],$record,time());
            Guard::need($proof!==null,'G5_RECEIVER_SOURCE_ACK_UNCERTAIN');
            $hash=$this->port->proof()->fence($record,$proof,time());$this->current();
            if($record['phase']==='INTENT_RECORDED'){
                $record['phase']='FENCE_CONFIRMED';$record['proof_hash']=$hash;$record['hold_codes']=[];
                $this->journal->save($record);
            }
            // New journal validates this actual proof domain; the synthetic verifier is never called.
            $this->journal->commitRetirement($record,$proof,time());
            if($record['phase']!=='RETIREMENT_RECORDED'){$record['phase']='RETIREMENT_RECORDED';$this->journal->save($record);}
            Guard::need($this->journal->closure($record['plan']['closure_id'])===$record['plan']['after'],'G5_RECEIVER_COMMIT_UNCONFIRMED');return $record;
        });
    }
    /** Recovery repeats the same durable intent; source fence/status checks make it idempotent. */
    public function recover(array $record,int $now):array {
        Guard::need($record['revision']>0,'G5_RECEIVER_DURABLE_INTENT_REQUIRED');return $this->retire($record,$now);
    }
    /** Consumes a completed, independently approved purge job. Never removes mail or intake rows. */
    public function cleanup(array $record,int $now):array {
        Guard::now($now);$this->current();$plan=$record['plan']??null;
        Guard::need(is_array($plan)&&isset($plan['closure_id'],$plan['digest'],$plan['no_mail_copy']['scope'],$plan['no_mail_copy']['proof_hash'])
            &&($record['state']??null)==='COMPLETE'&&is_int($record['completed_at']??null)&&$record['completed_at']>0
            &&$record['completed_at']<=PHP_INT_MAX-30*86400&&$now>=$record['completed_at']+30*86400,'G5_RECEIVER_CLEANUP_WINDOW_OR_PLAN_HELD');
        $unsigned=$plan;unset($unsigned['digest']);Guard::need(Workflow::digest($unsigned)===$plan['digest'],'G5_RECEIVER_CLEANUP_PLAN_CONFLICT');
        return $this->journal->locked($plan['closure_id'],function()use($record,$plan):array{
            $this->current();Guard::need($this->journal->journal($plan['digest'])===$record,'G5_RECEIVER_DURABLE_CLEANUP_REQUIRED');
            $closure=$this->journal->closure($plan['closure_id']);$scope=$plan['no_mail_copy']['scope'];
            Guard::need(is_array($closure)&&$scope===NoMailCopyProof::scope($closure,$scope['admission_hash'],$scope['fingerprint']),'G5_RECEIVER_CLEANUP_SCOPE_CONFLICT');
            if(($record['no_copy_cleanup']??null)===null){
                $ticket=$this->port->prepareCleanup($scope,time());Guard::need($ticket!==null&&strlen(Guard::canonical($ticket))<=16384,'G5_RECEIVER_CLEANUP_TICKET_UNVERIFIED');
                $record['no_copy_cleanup']=$ticket;$this->journal->save($record);
                Guard::need($this->journal->journal($plan['digest'])===$record,'G5_RECEIVER_DURABLE_CLEANUP_REQUIRED');
            }
            $ticket=$record['no_copy_cleanup'];$readback=$this->port->readback($scope,time(),true,$ticket);Guard::need($readback!==null,'G5_RECEIVER_CLEANUP_CUSTODY_UNVERIFIED');
            $raw=$this->port->proof()->ticket($ticket,$scope,time());
            Guard::need($this->port->proof()->readback($readback,$scope,time(),true,$raw)===$plan['no_mail_copy']['proof_hash'],'G5_RECEIVER_CLEANUP_FENCE_CHANGED');
            $this->current();Guard::need($this->port->forget($scope,time(),$ticket),'G5_RECEIVER_FORGET_ACK_UNCERTAIN');return $record;
        });
    }
}
