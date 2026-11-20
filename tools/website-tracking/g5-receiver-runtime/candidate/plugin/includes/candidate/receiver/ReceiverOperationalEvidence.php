<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\ReceiverV1;
require_once __DIR__.'/ReceiverContracts.php';
use BSRE\ClosedRetention\Workflow;

/** Approval reads and a distinct durable-intent registration; a credential never creates approval. */
interface ReviewTransport { public function exchange(string $operation,array $request):string; }
final class WordPressReviewTransport implements ReviewTransport {
    public function exchange(string $operation,array $request):string {
        Guard::need(in_array($operation,['approval','capture_custody','collection_custody','register_owner_intent'],true),'G5_RECEIVER_REVIEW_OPERATION_INVALID');
        Guard::need(defined('BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED')&&BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED===true
            &&defined('BSRE_RECEIVER_REVIEW_SERVICE_URL')&&is_string(BSRE_RECEIVER_REVIEW_SERVICE_URL)
            &&preg_match('~^https://[A-Za-z0-9.-]+(?::443)?/[A-Za-z0-9/_-]+$~D',BSRE_RECEIVER_REVIEW_SERVICE_URL)===1
            &&defined('BSRE_RECEIVER_REVIEW_CLIENT_TOKEN')&&is_string(BSRE_RECEIVER_REVIEW_CLIENT_TOKEN)&&strlen(BSRE_RECEIVER_REVIEW_CLIENT_TOKEN)>=32
            &&(!defined('BSRE_LEAD_HMAC_SECRET')||BSRE_RECEIVER_REVIEW_CLIENT_TOKEN!==BSRE_LEAD_HMAC_SECRET),'G5_RECEIVER_REVIEW_SERVICE_NOT_CONFIGURED');
        $body=Guard::canonical(['contract'=>'bsre-receiver-review-request-v1','operation'=>$operation,'request'=>$request]);
        Guard::need(strlen($body)<=2097152,'G5_RECEIVER_REVIEW_REQUEST_BOUND');
        $reply=wp_safe_remote_post(BSRE_RECEIVER_REVIEW_SERVICE_URL,['timeout'=>10,'redirection'=>0,'sslverify'=>true,'limit_response_size'=>131073,
            'headers'=>['Content-Type'=>'application/json','Authorization'=>'Bearer '.BSRE_RECEIVER_REVIEW_CLIENT_TOKEN],'body'=>$body]);
        Guard::need(!is_wp_error($reply)&&wp_remote_retrieve_response_code($reply)===200,'G5_RECEIVER_REVIEW_SERVICE_UNAVAILABLE');
        $raw=wp_remote_retrieve_body($reply);Guard::need(is_string($raw)&&strlen($raw)<=131072,'G5_RECEIVER_REVIEW_SERVICE_UNAVAILABLE');return $raw;
    }
}
/** Consumed by the existing OwnerAuthority and the new ActualReceiverJournal. No permissive callback. */
final class ReceiverOperationalEvidence implements \BSRE\ActualRetention\OperationalEvidence {
    public function __construct(private ReceiverPolicy $policy,private ReceiverRuntimeProof $proof,private ReviewTransport $service) {
        Guard::need($proof->policy()===$policy,'G5_RECEIVER_POLICY_CONFLICT');
    }
    public function boundTo(ReceiverRuntimeProof $proof):bool{return $this->proof===$proof&&$proof->policy()===$this->policy;}
    private function read(string $operation,array $scope,int $now):array {
        Guard::need($this->policy->enabled(),'G5_RECEIVER_DISABLED');
        Guard::now($now);$actor=$this->policy->actor();$this->proof->ready();$nonce=bin2hex(random_bytes(32));
        $request=['actor'=>$actor,'scope'=>$scope,'source'=>$this->policy->sources(),'challenge'=>$nonce];
        $hash=Workflow::digest(['operation'=>$operation,'body'=>Guard::canonical($request)]);
        $raw=$this->service->exchange($operation,$request);
        return $this->proof->verify($raw,$operation,$scope,$nonce,$hash,time());
    }
    /** The independent service MUST verify approval, fresh current anchor and decrypted exact journal entry, then durably record it before attesting. */
    public function registerIntent(array $record,array $binding,int $now):void {
        \BSRE\ClosedRetention\RetirementIntent::validateRecord($record,$now);
        Guard::keys($binding,['contract','policy','record','anchor','encrypted_body','encrypted_hash']);
        Guard::need($binding['contract']==='bsre-actual-receiver-durable-intent-v1'&&$binding['policy']===$this->policy->owner->scope()
            &&$binding['record']===$record&&is_array($binding['anchor'])&&is_string($binding['encrypted_body'])
            &&$binding['encrypted_hash']===hash('sha256',$binding['encrypted_body'])&&$binding['anchor']['hash']===$binding['encrypted_hash'],'G5_RECEIVER_INTENT_BINDING_INVALID');
        $c=$this->read('register_owner_intent',$binding,$now);$result=$c['result'];
        Guard::need($c['intent_digest']===$record['plan']['digest']&&is_array($result),'G5_RECEIVER_INTENT_REGISTRATION_UNVERIFIED');
        Guard::keys($result,['registered','intent_digest','record_hash','anchor']);
        Guard::need($result['registered']===true&&$result['intent_digest']===$record['plan']['digest']
            &&$result['record_hash']===Workflow::digest($record)&&Guard::canonical($result['anchor'])===Guard::canonical($binding['anchor']),'G5_RECEIVER_INTENT_REGISTRATION_UNVERIFIED');
    }
    public function approved(string $actor,string $action,string $digest,int $now):bool {
        try {
            if(!$this->policy->enabled()||$actor!==$this->policy->actor()||!in_array($action,['PURGE','EXPIRE_PRIVATE_JOURNAL','COLLECT','EDIT_CLOSURE','INITIALIZE_JOURNAL','RETIRE_NO_COPY'],true))return false;
            Guard::hash($digest);$c=$this->read('approval',['policy'=>$this->policy->owner->scope(),'action'=>$action,'digest'=>$digest],$now);
            return $c['result']===true&&($action!=='RETIRE_NO_COPY'||$c['intent_digest']===$digest);
        }catch(\Throwable $e){return false;}
    }
    /** Physical Marketing mail deletion remains manual; this port never supplies deletion/OAuth. */
    public function mailReceipt(string $actor,string $digest,string $messageId):?array{return null;}
    public function captureCustody(array $closure,array $record,string $request,int $now):bool {
        try{$c=$this->read('capture_custody',['closure'=>$closure,'record'=>$record,'request_id'=>$request],$now);return $c['result']===true;}catch(\Throwable $e){return false;}
    }
    public function collectionCustody(array $target,int $now):bool {
        try{$c=$this->read('collection_custody',['target'=>$target],$now);return $c['result']===true;}catch(\Throwable $e){return false;}
    }
    public function retirementCustody(array $record,array $proof,int $now):bool {
        try{if(!$this->policy->enabled())return false;$this->proof->fence($record,$proof,$now);return true;}catch(\Throwable $e){return false;}
    }
}
