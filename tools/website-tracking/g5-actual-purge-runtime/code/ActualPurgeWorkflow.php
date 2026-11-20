<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
use BSRE\ClosedRetention\Admission;
use BSRE\ActualRetention\ReceiverV1\Guard;
require_once __DIR__.'/ActualPurgeEngine.php';
require_once __DIR__.'/ActualPurgeResources.php';
require_once __DIR__.'/ActualPurgeCaptureResource.php';

/** Single consumed composition. The generic synthetic Workflow is never instantiated here. */
final class ActualPurgeWorkflow {
    private ActualPurgeEngine $engine;
    public function __construct(private RuntimePolicy $policy,private ActualPurgeJournal $journal,private PurgeBoundary $b,
        OwnerAuthority $authority,Admission $admission,ActualRetirementPort $receiver,ActualPurgeCaptureResource $capture,
        ActualIntake26Resource $intake,ActualOutcome40Resource $outcome,ActualMarketingManualMailResource $mail) {
        Guard::need($journal->runtimePolicy()===$policy&&$receiver->proof()===$journal->receiverProof()&&$b->samePolicy($policy)&&$journal->purgeBoundary()===$b
            &&$journal->purgeAuthority()===$authority&&$capture->boundTo($journal,$b,$policy)
            &&$intake->boundTo($b)&&$outcome->boundTo($b)&&$mail->boundTo($b),'ACTUAL_PURGE_COMPOSITION_CONFLICT');
        $this->engine=new ActualPurgeEngine(new PurgeJournalBoundary($journal,$b),
            ['intake'=>$intake,'outcome'=>$outcome,'email'=>$mail,'capture'=>new PurgeCaptureBoundary($capture,$b)],
            new PurgeAuthorityBoundary($authority,$b),new PurgeAdmissionBoundary($admission,$b),new ActualPurgeNoCopy($receiver,$b),$b);
    }
    private function run(string $closureId,?array $plan,string $action,callable $operation) {
        $this->b->begin($closureId,$plan,$action);try{return $operation();}finally{$this->b->end();}
    }
    public function prepare(string $closureId):array{return $this->run($closureId,null,'REVIEW',fn()=>$this->engine->prepare($closureId,$this->policy->actor(),time()));}
    public function execute(array $plan):array{return $this->run($plan['closure_id'],$plan,'PURGE',fn()=>$this->engine->execute($plan,$this->policy->actor(),time()));}
    public function ownerMailAction(array $plan):?array{return $this->run($plan['closure_id'],$plan,'PURGE',fn()=>$this->engine->ownerMailAction($plan,$this->policy->actor(),time()));}
    public function expire(array $plan):array{return $this->run($plan['closure_id'],$plan,'EXPIRE_PRIVATE_JOURNAL',fn()=>$this->engine->expire($plan,$this->policy->actor(),time()));}
}
