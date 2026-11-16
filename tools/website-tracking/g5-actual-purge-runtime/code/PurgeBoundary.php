<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
use BSRE\ClosedRetention\{Journal,ResourceAdapter,Authority,Admission,NoMailCopy,Workflow};
use BSRE\ActualRetention\ReceiverV1\Guard;

/** New reviewed server ABI. Implementations are protected server dependencies, never frontend input. */
interface PurgeServiceTransport { public function exchange(string $operation,array $request): string; }
interface Intake26Transport extends PurgeServiceTransport {}
interface Outcome40Transport extends PurgeServiceTransport {}
interface MarketingMailReadTransport extends PurgeServiceTransport {}

/** Independent signer enrollment is explicit; this candidate supplies neither endpoint nor key. */
final class SignedPurgeService {
    public function __construct(private RuntimePolicy $policy,private PurgeServiceTransport $transport,
        private string $keyId,private string $publicKey,private string $sourceHash) {
        Guard::hash($sourceHash);Guard::need(strlen($publicKey)===32&&preg_match('/^[A-Za-z0-9_-]{1,64}$/D',$keyId)===1,'ACTUAL_PURGE_ENROLLMENT_REQUIRED');
    }
    public function call(string $operation,array $body):array {
        $actor=$this->policy->actor();$nonce=bin2hex(random_bytes(32));
        $request=['contract'=>'bsre-actual-purge-request-v1','actor'=>$actor,'policy'=>$this->policy->scope(),
            'source_hash'=>$this->sourceHash,'operation'=>$operation,'challenge'=>$nonce,'body'=>$body];
        $raw=$this->transport->exchange($operation,$request);$now=time();$this->policy->actor();
        $env=Guard::decode($raw);Guard::keys($env,['key_id','statement','signature']);$s=$env['statement'];
        Guard::need(is_array($s),'ACTUAL_PURGE_SIGNATURE_UNVERIFIED');
        Guard::keys($s,['contract','actor','policy','source_hash','operation','challenge','request_hash','issued_at','expires_at','result']);
        Guard::need($env['key_id']===$this->keyId&&$s['contract']==='bsre-actual-purge-evidence-v1'
            &&$s['actor']===$actor&&$s['policy']===$this->policy->scope()&&$s['source_hash']===$this->sourceHash
            &&$s['operation']===$operation&&$s['challenge']===$nonce&&$s['request_hash']===Workflow::digest($request)
            &&is_int($s['issued_at'])&&$s['issued_at']>0&&$s['issued_at']<=$now&&$s['issued_at']>=$now-30
            &&is_int($s['expires_at'])&&$s['expires_at']>$now&&$s['expires_at']<=$s['issued_at']+60,'ACTUAL_PURGE_SIGNED_SCOPE_OR_CLOCK_CONFLICT');
        $sig=is_string($env['signature'])?base64_decode($env['signature'],true):false;
        Guard::need(is_string($sig)&&strlen($sig)===64&&base64_encode($sig)===$env['signature']
            &&function_exists('sodium_crypto_sign_verify_detached')&&sodium_crypto_sign_verify_detached($sig,Workflow::digest($s),$this->publicKey),'ACTUAL_PURGE_SIGNATURE_UNVERIFIED');
        Guard::need(is_array($s['result']),'ACTUAL_PURGE_RESULT_INVALID');return $s['result'];
    }
    public function boundTo(RuntimePolicy $policy):bool{return $this->policy===$policy;}
}

/** One immutable grant per invocation; a fresh receipt can never extend its deadline. */
final class PurgeBoundary {
    private ?array $grant=null;private ?array $plan=null;private ?array $record=null;private string $action='REVIEW';
    private ?string $closureId=null;private bool $active=false;private bool $journalObserved=false;
    public function __construct(private RuntimePolicy $policy,private \BSRE\ClosedRetention\LeaseBoundWpdb $db,
        private CanonicalCaptureProducer $producer,private SignedPurgeService $custody) {Guard::need($custody->boundTo($policy),'ACTUAL_PURGE_CUSTODY_POLICY_CONFLICT');}
    public function samePolicy(RuntimePolicy $policy):bool{return $policy===$this->policy;}
    public function boundTo(\BSRE\ClosedRetention\LeaseBoundWpdb $db,CanonicalCaptureProducer $producer,RuntimePolicy $policy):bool{return $db===$this->db&&$producer===$this->producer&&$policy===$this->policy;}
    public function accepts(SignedPurgeService $service):bool{return $service->boundTo($this->policy);}
    public function begin(string $closureId,?array $plan=null,string $action='REVIEW'):void {
        Guard::need(!$this->active&&in_array($action,['REVIEW','PURGE','EXPIRE_PRIVATE_JOURNAL'],true),'ACTUAL_PURGE_CONTEXT_BUSY');
        Guard::need($plan===null||($plan['closure_id']??null)===$closureId,'ACTUAL_PURGE_CONTEXT_CONFLICT');
        $this->active=true;$this->closureId=$closureId;$this->plan=$plan;$this->action=$action;$this->record=null;$this->grant=null;$this->journalObserved=false;
        try {
            $this->local();
            if($action!=='REVIEW'){
                Guard::need($plan!==null,'ACTUAL_PURGE_PLAN_REQUIRED');
                $g=$this->custody->call('approval',['action'=>$action,'plan'=>$plan]);
                Guard::keys($g,['actor','action','plan_digest','approved_at','approval_expires_at']);$now=time();
                Guard::need($g['actor']===$this->policy->actor()&&$g['action']===$action&&$g['plan_digest']===$plan['digest']
                    &&is_int($g['approved_at'])&&$g['approved_at']>0&&$g['approved_at']<=$now
                    &&is_int($g['approval_expires_at'])&&$g['approval_expires_at']>$now
                    &&$g['approval_expires_at']<=$g['approved_at']+900,'ACTUAL_PURGE_EXACT_APPROVAL_REQUIRED');$this->grant=$g;
            }
            $this->check();
        }catch(\Throwable $e){$this->end();throw $e;}
    }
    public function end():void{$this->active=false;$this->grant=null;$this->plan=null;$this->record=null;$this->closureId=null;$this->journalObserved=false;}
    private function local():void {
        Guard::need($this->active&&defined('BSRE_ACTUAL_PURGE_ENABLED')&&BSRE_ACTUAL_PURGE_ENABLED===true,'ACTUAL_PURGE_DISABLED');
        $this->policy->actor();$this->producer->assertCurrent($this->db);
        $now=time();if($this->action!=='REVIEW'&&$this->grant!==null){
            Guard::need($now>=$this->grant['approved_at']&&$now<$this->grant['approval_expires_at'],'ACTUAL_PURGE_APPROVAL_EXPIRED');
            if($this->action==='PURGE'&&$this->journalObserved&&$this->record===null)Guard::need($now>=$this->plan['created_at']&&$now<$this->plan['expires_at'],'ACTUAL_PURGE_PLAN_EXPIRED');
            if($this->action==='PURGE'&&$this->record!==null){
                $started=$this->record['started_at']??null;
                Guard::need(is_int($started)&&$started>0&&$started<=PHP_INT_MAX-2592000&&$now>=$started
                    &&($this->record['state']==='COMPLETE'||$now<$started+2592000),'ACTUAL_PURGE_RECOVERY_EXPIRED');
            }
        }
    }
    public function check(string $operation='workflow',?array $binding=null,?array $transition=null):void {
        $this->local();
        if($operation==='journal_sql_boundary')Guard::need(in_array($this->action,['PURGE','EXPIRE_PRIVATE_JOURNAL'],true),'ACTUAL_PURGE_REVIEW_IS_READ_ONLY');
        $request=['action'=>$this->action,'closure_id'=>$this->closureId,'plan'=>$this->plan,'grant'=>$this->grant,
            'record'=>$this->record,'operation'=>$operation,'binding'=>$binding,'transition'=>$transition];
        if($transition!==null){
            Guard::need(in_array($this->action,['PURGE','EXPIRE_PRIVATE_JOURNAL'],true),'ACTUAL_PURGE_REVIEW_IS_READ_ONLY');
            Guard::need(in_array($operation,['journal_anchor_advance','journal_anchor_advance:readback'],true),'ACTUAL_PURGE_ANCHOR_TRANSITION_SCOPE_INVALID');
            Guard::keys($transition,['before','after','encrypted_body']);
            Guard::need(is_array($transition['before'])&&is_array($transition['after'])&&is_string($transition['encrypted_body'])
                &&($transition['after']['revision']??0)===($transition['before']['revision']??-1)+1
                &&($transition['after']['hash']??null)===hash('sha256',$transition['encrypted_body']),'ACTUAL_PURGE_ANCHOR_TRANSITION_INVALID');
            Guard::keys($transition['before'],['revision','hash']);Guard::keys($transition['after'],['revision','hash']);
            Guard::hash($transition['before']['hash']);Guard::hash($transition['after']['hash']);
        }
        $v=$this->custody->call('boundary',$request);$this->local();
        Guard::keys($v,['request_hash','owner_approval','current_journal','current_sources','mail_and_trash','recovery_custody','history_floor']);
        Guard::need($v['request_hash']===Workflow::digest($request)&&$v['owner_approval']===true&&$v['current_journal']===true
            &&$v['current_sources']===true&&$v['mail_and_trash']===true&&$v['recovery_custody']===true&&$v['history_floor']===true,'ACTUAL_PURGE_CUSTODY_HELD');
    }
    public function io(string $operation,callable $operationFn,?array $binding=null) {
        $this->check($operation,$binding);$result=$operationFn();$this->check($operation.':readback',$binding);return $result;
    }
    public function observe(?array $record):void {
        if($record!==null){
            Guard::need($this->plan!==null&&($record['plan']??null)===$this->plan,'ACTUAL_PURGE_RECORD_CONFLICT');
            if($this->record!==null){
                Guard::need($record['started_at']===$this->record['started_at'],'ACTUAL_PURGE_RECOVERY_DEADLINE_CHANGED');
                if($this->record['completed_at']!==null)Guard::need($record['completed_at']===$this->record['completed_at'],'ACTUAL_PURGE_COMPLETION_DEADLINE_CHANGED');
            }
        }$this->record=$record;$this->journalObserved=true;
    }
    public function assertMutation(string $store,array $binding):void {
        Guard::need($this->action==='PURGE'&&$this->record!==null&&in_array($this->record['state'],['APPLYING','HELD'],true),'ACTUAL_PURGE_DURABLE_INTENT_REQUIRED');
        $matches=[];foreach($this->record['plan']['resources'] as $i=>$r)if($r['store']===$store&&$r['binding']===$binding)$matches[]=$i;
        Guard::need(count($matches)===1&&($this->record['steps'][$matches[0]]??null)==='INTENT_RECORDED','ACTUAL_PURGE_DURABLE_INTENT_REQUIRED');
        $this->check('remove_exact:'.$store,$binding);
    }
    public function claim(string $operation,?array $binding=null):array {
        $this->check($operation,$binding);return ['action'=>$this->action,'closure_id'=>$this->closureId,'plan'=>$this->plan,
            'grant'=>$this->grant,'record'=>$this->record,'operation'=>$operation,'binding'=>$binding];
    }
    public function manualMailReceipt(string $actor,string $digest,string $messageId):?array {
        $r=$this->io('manual_mail_receipt',fn()=>$this->custody->call('manual_mail_receipt',[
            'actor'=>$actor,'plan_digest'=>$digest,'message_id'=>$messageId,'custody'=>$this->claim('manual_mail_receipt')]));
        Guard::keys($r,['receipt']);Guard::need($r['receipt']===null||is_array($r['receipt']),'ACTUAL_PURGE_MAIL_RECEIPT_INVALID');return $r['receipt'];
    }
}

final class PurgeJournalBoundary implements Journal {
    public function __construct(private ActualPurgeJournal $journal,private PurgeBoundary $b){}
    public function locked(string $id,callable $fn){return $this->b->io('lease',fn()=>$this->journal->locked($id,$fn));}
    public function closure(string $id):?array{return $this->b->io('closure',fn()=>$this->journal->closure($id));}
    public function journal(string $id):?array{$r=$this->b->io('journal',fn()=>$this->journal->journal($id));$this->b->observe($r);return $r;}
    public function save(array &$record):void {
        $this->b->check('save_intent');$this->journal->save($record);
        // Observe the durable CAS result before the post-I/O check. No mutation follows uncertain storage.
        $this->b->observe($record);$this->b->check('save_intent:readback');
    }
    public function markHistoryIncomplete():void{$this->b->io('history_incomplete',fn()=>$this->journal->markHistoryIncomplete());}
    public function historyIncomplete():bool{return $this->b->io('history',fn()=>$this->journal->historyIncomplete());}
    public function pinAdmissionFloor(string $hash):void{$this->b->io('admission_floor_pin',fn()=>$this->journal->pinAdmissionFloor($hash));}
    public function admissionFloor():?string{return $this->b->io('admission_floor',fn()=>$this->journal->admissionFloor());}
    public function forget(string $id,string $plan,bool $keepClosure=false):void{$this->b->io('forget_journal',fn()=>$this->journal->forget($id,$plan,$keepClosure));$this->b->observe(null);}
}
final class PurgeAuthorityBoundary implements Authority {
    public function __construct(private OwnerAuthority $authority,private PurgeBoundary $b){}
    public function canReview(string $actor):bool{return $this->b->io('review',fn()=>$this->authority->canReview($actor));}
    public function canApply(string $actor,string $digest,int $now,string $action):bool{return $this->b->io('approval:'.$action,fn()=>$this->authority->canApply($actor,$digest,time(),$action));}
    public function mailReceipt(string $actor,string $digest,string $id):?array{return $this->b->manualMailReceipt($actor,$digest,$id);}
}
final class PurgeAdmissionBoundary implements Admission {
    public function __construct(private Admission $admission,private PurgeBoundary $b){}
    public function readback(int $now):?array{return $this->b->io('admission',fn()=>$this->admission->readback(time()));}
}
/** Preserves actual signed wrappers. Never converts them into SYNTHETIC_BSRE_NO_COPY. */
final class ActualPurgeNoCopy implements NoMailCopy {
    public function __construct(private ActualRetirementPort $port,private PurgeBoundary $b){}
    public function readback(array $s,int $now,bool $cleanup=false,?array $ticket=null):?array{return $this->b->io('receiver_readback',fn()=>$this->port->readback($s,time(),$cleanup,$ticket));}
    public function prepareCleanup(array $s,int $now):?array{return $this->b->io('receiver_cleanup_ticket',fn()=>$this->port->prepareCleanup($s,time()));}
    public function forget(array $s,int $now,array $ticket):bool{return $this->b->io('receiver_forget',fn()=>$this->port->forget($s,time(),$ticket));}
    public function verify(?array $wrapped,array $scope,int $now,bool $cleanup=false,?array $ticket=null):string {
        Guard::need($wrapped!==null,'ACTUAL_PURGE_FENCE_UNVERIFIED');$raw=$ticket===null?null:$this->port->proof()->ticket($ticket,$scope,time());
        return $this->port->proof()->readback($wrapped,$scope,time(),$cleanup,$raw);
    }
    public function rowState(array $wrapped,array $scope,int $now,bool $cleanup=false,?array $ticket=null):string {
        $raw=$ticket===null?null:$this->port->proof()->ticket($ticket,$scope,time());$this->verify($wrapped,$scope,time(),$cleanup,$ticket);
        $c=$this->port->proof()->value($wrapped,'readback',$scope,['scope'=>$scope,'cleanup'=>$cleanup,'ticket'=>$raw],time());return $c['result']['row_state'];
    }
}
