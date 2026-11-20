<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
require_once __DIR__.'/ReceiverContracts.php';
use BSRE\ActualRetention\ReceiverV1\{ReceiverPolicy,ReceiverRuntimeProof,ControlTransport,Guard};
use BSRE\ClosedRetention\{NoMailRetirement,RetirementIntent,Workflow};

/** Actual typed adapter. Default OFF; independently signed evidence, not lead HMAC, establishes authority. */
final class ActualRetirementPort implements NoMailRetirement {
    public function __construct(private ReceiverPolicy $policy,private ControlTransport $transport,private ReceiverRuntimeProof $proof) {
        Guard::need($proof->policy()===$policy,'G5_RECEIVER_POLICY_CONFLICT');
    }
    public function proof():ReceiverRuntimeProof{return $this->proof;}
    private function call(string $operation,array $scope,array $args,int $now):?array {
        if(!$this->policy->enabled())return null;
        Guard::now($now);$actor=$this->policy->actor();$this->proof->ready();$this->proof->scope($scope);
        Guard::need(defined('BSRE_LEAD_HMAC_SECRET')&&is_string(BSRE_LEAD_HMAC_SECRET)&&strlen(BSRE_LEAD_HMAC_SECRET)>=32,'G5_RECEIVER_TRANSPORT_NOT_CONFIGURED');
        $body=Guard::canonical($args);Guard::need(strlen($body)<=49152,'G5_RECEIVER_REQUEST_BOUND');$nonce=bin2hex(random_bytes(32));$stamp=(int)floor(microtime(true)*1000);
        $message=ReceiverPolicy::CONTROL."\n".$stamp."\n".$nonce."\n".$operation."\n".$actor."\n".$body;
        $env=['control_contract'=>ReceiverPolicy::CONTROL,'control_version'=>1,'timestamp'=>$stamp,'challenge'=>$nonce,'operation'=>$operation,'actor'=>$actor,'body'=>$body,'signature'=>hash_hmac('sha256',$message,BSRE_LEAD_HMAC_SECRET)];
        $requestHash=Workflow::digest(['operation'=>$operation,'body'=>$body]);$raw=$this->transport->exchange(Guard::canonical($env));
        $this->proof->verify($raw,$operation,$scope,$nonce,$requestHash,time());
        return ['contract'=>ReceiverPolicy::RESULT,'operation'=>$operation,'scope_hash'=>Workflow::digest($scope),'challenge'=>$nonce,'request_hash'=>$requestHash,'receipt'=>$raw];
    }
    public function inspect(array $scope,int $now):?array {
        $r=$this->call('inspect',$scope,['scope'=>$scope],$now);if($r!==null)$this->proof->inspection($r,$scope,time());return $r;
    }
    public function retire(array $scope,array $record,int $now):?array {
        RetirementIntent::validateRecord($record,$now);Guard::need($record['plan']['scope']===$scope,'G5_RECEIVER_SCOPE_INVALID');
        $r=$this->call('retire',$scope,['scope'=>$scope,'intent_digest'=>$record['plan']['digest']],$now);if($r!==null)$this->proof->fence($record,$r,time());return $r;
    }
    public function readback(array $scope,int $now,bool $cleanup=false,?array $ticket=null):?array {
        $rawTicket=$ticket===null?null:$this->proof->ticket($ticket,$scope,$now);
        $r=$this->call('readback',$scope,['scope'=>$scope,'cleanup'=>$cleanup,'ticket'=>$rawTicket],$now);
        if($r!==null)$this->proof->readback($r,$scope,time(),$cleanup,$rawTicket);return $r;
    }
    public function prepareCleanup(array $scope,int $now):?array {
        $r=$this->call('prepare_cleanup',$scope,['scope'=>$scope],$now);if($r!==null)$this->proof->ticket($r,$scope,time());return $r;
    }
    public function forget(array $scope,int $now,array $ticket):bool {
        if(!$this->policy->enabled())return false;$rawTicket=$this->proof->ticket($ticket,$scope,$now);
        $r=$this->call('forget',$scope,['scope'=>$scope,'ticket'=>$rawTicket],$now);if($r===null)return false;
        $claims=$this->proof->value($r,'forget',$scope,['scope'=>$scope,'ticket'=>$rawTicket],time());
        Guard::need($claims['result']===true,'G5_RECEIVER_FORGET_ACK_UNCERTAIN');return true;
    }
}
