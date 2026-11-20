<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\ReceiverV1;
use BSRE\ClosedRetention\Workflow;
use BSRE\ActualRetention\RuntimePolicy;
require_once __DIR__.'/NoMailCopyAlgebra.php';

interface ControlTransport { public function exchange(string $canonicalEnvelope): string; }
interface IndependentKeys { public function publicKey(string $service,string $keyId): string; }

/** Immutable server policy; no URL, key or namespace is accepted from a frontend request. */
final class ReceiverPolicy {
    public const CONTROL='bsre-receiver-control-v1';
    public const EVIDENCE='bsre-actual-receiver-evidence-v1';
    public const SERVICE='receiver-retirement';
    public const RESULT='bsre-actual-receiver-result-v1';
    public function __construct(public readonly RuntimePolicy $owner,public readonly string $receiverSource,
        public readonly string $namespace,public readonly string $admission,public readonly string $generation,public readonly string $keyId) {
        foreach([$receiverSource,$namespace,$admission,$generation] as $hash)Guard::hash($hash);
        Guard::need(preg_match('/^[A-Za-z0-9_-]{1,64}$/D',$keyId)===1,'G5_RECEIVER_KEY_NOT_ENROLLED');
    }
    public function actor():string{return $this->owner->actor();}
    public function sources():array{return ['receiver'=>$this->receiverSource,'namespace'=>$this->namespace,'admission'=>$this->admission,'generation'=>$this->generation];}
    public function enabled():bool{return defined('BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED')&&BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED===true;}
}
final class Guard {
    public static function need(bool $ok,string $code):void{if(!$ok)throw new \BSRE\ClosedRetention\Failure($code);}
    public static function hash($v):void{self::need(is_string($v)&&preg_match('/^[a-f0-9]{64}$/D',$v)===1,'G5_RECEIVER_HASH_INVALID');}
    public static function keys(array $v,array $keys):void{$got=array_keys($v);sort($got);sort($keys);self::need($got===$keys,'G5_RECEIVER_SCHEMA_INVALID');}
    public static function now(int $now):void{self::need($now>0&&abs(time()-$now)<=5,'G5_RECEIVER_CLOCK_UNVERIFIED');}
    public static function canonical($v):string {
        if(is_array($v)){
            if(array_is_list($v))return '['.implode(',',array_map(self::canonical(...),$v)).']';
            ksort($v,SORT_STRING);$parts=[];foreach($v as $k=>$item)$parts[]=self::canonical((string)$k).':'.self::canonical($item);
            return '{'.implode(',',$parts).'}';
        }
        self::need($v===null||is_bool($v)||is_int($v)||is_string($v),'G5_RECEIVER_JSON_VALUE_INVALID');
        return json_encode($v,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
    }
    public static function decode(string $raw):array {
        self::need(strlen($raw)>0&&strlen($raw)<=131072,'G5_RECEIVER_REPLY_BOUND');
        $value=json_decode($raw,true,32,JSON_THROW_ON_ERROR);self::need(is_array($value)&&!array_is_list($value),'G5_RECEIVER_REPLY_INVALID');
        self::need(self::canonical($value)===$raw,'G5_RECEIVER_NONCANONICAL_OR_DUPLICATE_JSON');return $value;
    }
}
/** Uses only the already existing WordPress receiver URL/transport and lead HMAC. */
final class WordPressControlTransport implements ControlTransport {
    public function exchange(string $canonicalEnvelope):string {
        Guard::need(defined('BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED')&&BSRE_ACTUAL_RECEIVER_RETIREMENT_ENABLED===true,'G5_RECEIVER_DISABLED');
        Guard::need(defined('BSRE_LEAD_RECEIVER_URL')&&is_string(BSRE_LEAD_RECEIVER_URL)
            &&preg_match('~^https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec$~D',BSRE_LEAD_RECEIVER_URL)===1
            &&function_exists('BSRE\\Enquiries\\send_envelope'),'G5_RECEIVER_TRANSPORT_NOT_CONFIGURED');
        $reply=\BSRE\Enquiries\send_envelope(BSRE_LEAD_RECEIVER_URL,$canonicalEnvelope);
        Guard::need(!is_wp_error($reply)&&wp_remote_retrieve_response_code($reply)===200,'G5_RECEIVER_SOURCE_ACK_UNCERTAIN');
        $body=wp_remote_retrieve_body($reply);Guard::need(is_string($body)&&strlen($body)<=131072,'G5_RECEIVER_SOURCE_ACK_UNCERTAIN');return $body;
    }
}
/** Public verification keys come from explicit protected server enrollment; no key is generated. */
final class ServerIndependentKeys implements IndependentKeys {
    public function publicKey(string $service,string $keyId):string {
        Guard::need($service===ReceiverPolicy::SERVICE&&defined('BSRE_RECEIVER_EVIDENCE_PUBLIC_KEYS')&&is_array(BSRE_RECEIVER_EVIDENCE_PUBLIC_KEYS),'G5_RECEIVER_SIGNER_UNAVAILABLE');
        $encoded=BSRE_RECEIVER_EVIDENCE_PUBLIC_KEYS[$keyId]??null;Guard::need(is_string($encoded),'G5_RECEIVER_SIGNER_UNAVAILABLE');
        $key=base64_decode($encoded,true);Guard::need(is_string($key)&&strlen($key)===32&&base64_encode($key)===$encoded,'G5_RECEIVER_SIGNER_UNAVAILABLE');return $key;
    }
}
/** Shared-envelope shape agrees with the preference direction; receiver scope/claims are separate. */
final class ReceiverRuntimeProof {
    public function __construct(private ReceiverPolicy $policy,private IndependentKeys $keys) {}
    public function policy():ReceiverPolicy{return $this->policy;}
    public function ready():void {
        Guard::need(function_exists('sodium_crypto_sign_verify_detached'),'G5_RECEIVER_SIGNER_UNAVAILABLE');
        $key=$this->keys->publicKey(ReceiverPolicy::SERVICE,$this->policy->keyId);Guard::need(strlen($key)===32,'G5_RECEIVER_SIGNER_UNAVAILABLE');
    }
    public function verify(string $raw,string $operation,array $scope,string $challenge,string $requestHash,int $now,bool $historicalTicket=false):array {
        Guard::now($now);$this->ready();$actor=$this->policy->actor();Guard::hash($challenge);Guard::hash($requestHash);
        $env=Guard::decode($raw);Guard::keys($env,['key_id','statement','signature']);
        Guard::need($env['key_id']===$this->policy->keyId&&is_array($env['statement'])&&is_string($env['signature']),'G5_RECEIVER_SIGNER_UNVERIFIED');
        $s=$env['statement'];Guard::keys($s,['contract','service','operation','scope','source','actor','challenge','request_hash','issued_at','expires_at','claims']);
        Guard::need($s['contract']===ReceiverPolicy::EVIDENCE&&$s['service']===ReceiverPolicy::SERVICE&&$s['operation']===$operation
            &&$s['scope']===Workflow::digest($scope)&&is_array($s['source'])&&Guard::canonical($s['source'])===Guard::canonical($this->policy->sources())&&$s['actor']===$actor
            &&$s['challenge']===$challenge&&$s['request_hash']===$requestHash,'G5_RECEIVER_SIGNED_SCOPE_CONFLICT');
        Guard::need(is_int($s['issued_at'])&&$s['issued_at']>0&&$s['issued_at']<=$now&&($historicalTicket||$s['issued_at']>=$now-30)
            &&is_int($s['expires_at'])&&$s['expires_at']>$s['issued_at']&&($historicalTicket||$s['expires_at']>$now)&&$s['expires_at']<=$s['issued_at']+60,'G5_RECEIVER_SIGNED_PROOF_STALE');
        $signature=base64_decode($env['signature'],true);$key=$this->keys->publicKey(ReceiverPolicy::SERVICE,$env['key_id']);
        Guard::need(is_string($signature)&&strlen($signature)===64&&base64_encode($signature)===$env['signature']
            &&strlen($key)===32&&function_exists('sodium_crypto_sign_verify_detached')
            &&sodium_crypto_sign_verify_detached($signature,Workflow::digest($s),$key),'G5_RECEIVER_SIGNED_PROOF_UNVERIFIED');
        Guard::need(is_array($s['claims']),'G5_RECEIVER_SIGNED_CLAIMS_INVALID');$c=$s['claims'];Guard::keys($c,['result','intent_digest','current_history','receiver_only']);
        Guard::need($c['current_history']===true&&$c['receiver_only']===true,'G5_RECEIVER_COVERAGE_UNVERIFIED');
        if($c['intent_digest']!==null)Guard::hash($c['intent_digest']);return $c;
    }
    public function value(array $wrapped,string $operation,array $scope,array $args,int $now,bool $historicalTicket=false):array {
        Guard::keys($wrapped,['contract','operation','scope_hash','challenge','request_hash','receipt']);
        $hash=Workflow::digest(['operation'=>$operation,'body'=>Guard::canonical($args)]);
        Guard::need($wrapped['contract']===ReceiverPolicy::RESULT&&$wrapped['operation']===$operation
            &&$wrapped['scope_hash']===Workflow::digest($scope)&&$wrapped['request_hash']===$hash&&is_string($wrapped['receipt']),'G5_RECEIVER_RESULT_CONFLICT');
        return $this->verify($wrapped['receipt'],$operation,$scope,$wrapped['challenge'],$hash,$now,$historicalTicket);
    }
    public function scope(array $scope):void {
        Guard::keys($scope,['contract','closure_id','closure_revision','closure_hash','request_id','lead_id','event_id','fingerprint','admission_hash']);
        $uuid='/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D';
        Guard::need($scope['contract']===NoMailCopyAlgebra::CONTRACT&&is_int($scope['closure_revision'])&&$scope['closure_revision']>0
            &&$scope['closure_revision']<=9007199254740991&&is_string($scope['closure_id'])&&preg_match($uuid,$scope['closure_id'])===1
            &&is_string($scope['request_id'])&&preg_match($uuid,$scope['request_id'])===1
            &&is_string($scope['lead_id'])&&str_starts_with($scope['lead_id'],'BSRE-')&&preg_match($uuid,substr($scope['lead_id'],5))===1
            &&is_string($scope['event_id'])&&str_starts_with($scope['event_id'],'evt_')&&preg_match($uuid,substr($scope['event_id'],4))===1
            &&$scope['admission_hash']===$this->policy->admission,'G5_RECEIVER_SCOPE_INVALID');
        Guard::hash($scope['closure_hash']);Guard::hash($scope['fingerprint']);
    }
    private function rawProof(array $proof,array $scope,int $now,bool $cleanup=false):string {
        $this->scope($scope);
        Guard::need(($proof['source_hash']??null)===$this->policy->receiverSource
            &&($proof['current_store']['generation']??null)===$this->policy->generation,'G5_RECEIVER_SOURCE_VERSION_CONFLICT');
        return NoMailCopyAlgebra::verify($proof,$scope,$now,$this->policy->namespace,$cleanup);
    }
    public function inspection(array $wrapped,array $scope,int $now):array {
        $this->scope($scope);$claims=$this->value($wrapped,'inspect',$scope,['scope'=>$scope],$now);$r=$claims['result'];
        Guard::need(is_array($r),'G5_RECEIVER_INSPECTION_UNVERIFIED');
        Guard::need(($r['contract']??null)==='bsre-no-mail-retirement-inspection-v1'&&($r['scope_hash']??null)===Workflow::digest($scope),'G5_RECEIVER_INSPECTION_CONFLICT');
        if(($r['state']??null)==='RETIRED'){
            Guard::keys($r,['contract','scope_hash','state','proof']);$this->rawProof($r['proof'],$scope,$now);
            Guard::need($r['proof']['row_state']==='RETIRED','G5_RECEIVER_ROW_NOT_RETIRED');return $r;
        }
        Guard::keys($r,['contract','scope_hash','state','current_store','source_hash','restore_policy_hash','external_floor_hash','mailbox','row_status','attempt_count','send_started_at','sent_at','observed_at','expires_at']);
        Guard::need($r['contract']==='bsre-no-mail-retirement-inspection-v1'&&$r['scope_hash']===Workflow::digest($scope)
            &&$r['state']==='UNRETIRED'&&in_array($r['row_status'],['QUEUED','RETRY_WAIT','NEEDS_REVIEW'],true)
            &&$r['attempt_count']===0&&$r['send_started_at']===''&&$r['sent_at']===''&&$r['source_hash']===$this->policy->receiverSource
            &&($r['current_store']['generation']??null)===$this->policy->generation,'G5_RECEIVER_OUTBOX_AMBIGUOUS');
        NoMailCopyAlgebra::verifyStore($r['current_store'],$scope,$r['source_hash'],$r['restore_policy_hash'],$r['external_floor_hash'],$now,$this->policy->namespace);
        NoMailCopyAlgebra::verifyMailbox($r['mailbox'],$scope,$now);
        Guard::need(is_int($r['observed_at'])&&$r['observed_at']>0&&$r['observed_at']<=$now&&is_int($r['expires_at'])&&$r['expires_at']>$now&&$r['expires_at']<=$r['observed_at']+300,'G5_RECEIVER_INSPECTION_STALE');return $r;
    }
    public function fence(array $record,array $wrapped,int $now):string {
        \BSRE\ClosedRetention\RetirementIntent::validateRecord($record,$now);$p=$record['plan'];$scope=$p['scope'];
        $claims=$this->value($wrapped,'retire',$scope,['scope'=>$scope,'intent_digest'=>$p['digest']],$now);$proof=$claims['result'];
        Guard::need(is_array($proof)&&$claims['intent_digest']===$p['digest']&&($proof['owner_intent_digest']??null)===$p['digest'],'G5_RECEIVER_DURABLE_INTENT_CONFLICT');
        $hash=$this->rawProof($proof,$scope,$now);
        Guard::need($proof['row_state']==='RETIRED'&&$proof['fence_created_at']>=$record['approved_at']&&$proof['fence_created_at']<$p['expires_at']
            &&$now<$record['recovery_until']&&($record['proof_hash']===null||$record['proof_hash']===$hash),'G5_RECEIVER_FENCE_CONFLICT');return $hash;
    }
    public function readback(array $wrapped,array $scope,int $now,bool $cleanup,?array $rawTicket):string {
        $claims=$this->value($wrapped,'readback',$scope,['scope'=>$scope,'cleanup'=>$cleanup,'ticket'=>$rawTicket],$now);
        Guard::need(is_array($claims['result']),'G5_RECEIVER_READBACK_UNVERIFIED');return $this->rawProof($claims['result'],$scope,$now,$cleanup);
    }
    /** A historical signed ticket is transport material only; every destructive use rechecks fresh source/backup custody. */
    public function ticket(array $wrapped,array $scope,int $now):array {
        $this->scope($scope);
        $claims=$this->value($wrapped,'prepare_cleanup',$scope,['scope'=>$scope],$now,true);$ticket=$claims['result'];
        Guard::need(is_array($ticket),'G5_RECEIVER_CLEANUP_TICKET_UNVERIFIED');Guard::keys($ticket,['body','signature']);$body=$ticket['body'];
        Guard::need(is_array($body),'G5_RECEIVER_CLEANUP_TICKET_UNVERIFIED');Guard::keys($body,['contract','fence','floor','issued_at']);
        Guard::need($body['contract']==='bsre-no-copy-cleanup-ticket-v1'&&is_int($body['issued_at'])&&$body['issued_at']>0&&$body['issued_at']<=$now
            &&($body['fence']['body']['scope_hash']??null)===Workflow::digest($scope)&&($body['floor']['namespace']??null)===$this->policy->namespace
            &&($body['floor']['source_hash']??null)===$this->policy->receiverSource&&($body['floor']['generation']??null)===$this->policy->generation
            &&($body['floor']['admission_hash']??null)===$this->policy->admission,'G5_RECEIVER_CLEANUP_TICKET_UNVERIFIED');return $ticket;
    }
}
