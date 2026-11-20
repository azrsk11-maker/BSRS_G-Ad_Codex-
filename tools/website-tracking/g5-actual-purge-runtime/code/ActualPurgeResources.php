<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
use BSRE\ClosedRetention\{ResourceAdapter,Workflow};
use BSRE\ActualRetention\ReceiverV1\Guard;
require_once __DIR__.'/PurgeBoundary.php';

/** Typed enrollment factories consume the distinct service contracts, never a request URL/key. */
final class PurgeResources {
    public static function intake(RuntimePolicy $p,Intake26Transport $t,string $keyId,string $key,string $source,PurgeBoundary $b):ActualIntake26Resource {
        return new ActualIntake26Resource(new PurgeResourceGateway('intake',new SignedPurgeService($p,$t,$keyId,$key,$source),$b),$b);
    }
    public static function outcome(RuntimePolicy $p,Outcome40Transport $t,string $keyId,string $key,string $source,PurgeBoundary $b):ActualOutcome40Resource {
        return new ActualOutcome40Resource(new PurgeResourceGateway('outcome',new SignedPurgeService($p,$t,$keyId,$key,$source),$b),$b);
    }
    public static function mail(RuntimePolicy $p,MarketingMailReadTransport $t,string $keyId,string $key,string $source,PurgeBoundary $b):ActualMarketingManualMailResource {
        return new ActualMarketingManualMailResource(new PurgeResourceGateway('email',new SignedPurgeService($p,$t,$keyId,$key,$source),$b),$b);
    }
}

/** Consumed signed server ABI. No network endpoint, OAuth scope or provider identity is guessed. */
final class PurgeResourceGateway {
    public function __construct(private string $store,private SignedPurgeService $service,private PurgeBoundary $b) {
        Guard::need(in_array($store,['intake','outcome','email'],true)&&$b->accepts($service),'ACTUAL_PURGE_STORE_OR_POLICY_INVALID');
    }
    public function boundTo(string $store,PurgeBoundary $b):bool{return $store===$this->store&&$b===$this->b;}
    public function call(string $operation,array $arguments):array {
        Guard::need(in_array($operation,['inventory','read','remove_exact'],true),'ACTUAL_PURGE_OPERATION_INVALID');
        if($operation==='remove_exact'){
            Guard::need($this->store!=='email','ACTUAL_PURGE_MAIL_MANUAL_ONLY');
            $this->b->assertMutation($this->store,$arguments['binding']);
        }
        $claim=$this->b->claim($this->store.':'.$operation,$arguments['binding']??null);
        $idempotency=null;
        if($operation==='remove_exact'){
            $index=null;foreach($claim['record']['plan']['resources'] as $i=>$resource)if($resource['store']===$this->store&&$resource['binding']===$arguments['binding'])$index=$i;
            Guard::need($index!==null&&is_int($claim['record']['intent_at'][$index]??null),'ACTUAL_PURGE_DURABLE_INTENT_REQUIRED');
            $idempotency=Workflow::digest(['plan_digest'=>$claim['plan']['digest'],'store'=>$this->store,
                'binding'=>$arguments['binding'],'intent_at'=>$claim['record']['intent_at'][$index]]);
        }
        $request=['store'=>$this->store,'operation'=>$operation,'arguments'=>$arguments,'custody'=>$claim,'idempotency_key'=>$idempotency];
        $r=$this->b->io($this->store.':'.$operation,fn()=>$this->service->call('resource',$request),$arguments['binding']??null);
        Guard::keys($r,['request_hash','store','schema','schema_hash','complete_surface','trash_included','shared_identity_absent','metadata_bound','wire_v1_preserved','outbox_reconciled','result']);
        $schema=['intake'=>'Intake26','outcome'=>'Outcome40','email'=>'MarketingExactMessageV1'][$this->store];
        // Actual inspected source contracts: canonical Intake26 headers and original Outcome40 schema bytes.
        $schemaHash=['intake'=>'0dcac495bed4beda7a027c5d21d0d8b1caaa8a307e6eb815e3566c46f41369ca',
            'outcome'=>'bf477cc0cc4a161775abd702777898c6046d5dfcf0f2ae0e86fe078a3a63d9df','email'=>null][$this->store];
        Guard::need($r['request_hash']===Workflow::digest($request)&&$r['store']===$this->store&&$r['schema']===$schema
            &&$r['schema_hash']===$schemaHash
            &&$r['complete_surface']===true&&$r['shared_identity_absent']===true&&$r['metadata_bound']===true
            &&$r['wire_v1_preserved']===true&&$r['outbox_reconciled']===true
            &&($this->store==='email'?$r['trash_included']===true:$r['trash_included']===null),'ACTUAL_PURGE_RESOURCE_CUSTODY_HELD');
        // Result is deliberately explicit: missing replies and partial searches are never absence.
        Guard::need(is_array($r['result']),'ACTUAL_PURGE_RESOURCE_RESULT_INVALID');return $r['result'];
    }
    public function inventory(string $requestId):array {
        $r=$this->call('inventory',['request_id'=>$requestId]);Guard::keys($r,['bindings']);
        Guard::need(is_array($r['bindings'])&&array_is_list($r['bindings'])&&count($r['bindings'])<=100,'ACTUAL_PURGE_INVENTORY_INVALID');return $r['bindings'];
    }
    public function read(string $key):?array {
        $r=$this->call('read',['key'=>$key]);Guard::keys($r,['state','binding']);
        Guard::need(in_array($r['state'],['PRESENT','ABSENT'],true)&&($r['state']==='ABSENT'?$r['binding']===null:is_array($r['binding'])),'ACTUAL_PURGE_READ_UNVERIFIED');return $r['binding'];
    }
    public function removeExact(array $binding):void {
        $r=$this->call('remove_exact',['binding'=>$binding]);Guard::keys($r,['confirmed_absent','binding_hash']);
        Guard::need($r['confirmed_absent']===true&&$r['binding_hash']===Workflow::digest($binding),'ACTUAL_PURGE_DELETE_UNCONFIRMED');
    }
}
final class ActualIntake26Resource implements ResourceAdapter {
    public function __construct(private PurgeResourceGateway $g,private PurgeBoundary $b){Guard::need($g->boundTo('intake',$b),'ACTUAL_PURGE_RESOURCE_POLICY_CONFLICT');}
    public function boundTo(PurgeBoundary $b):bool{return $b===$this->b;}
    public function inventory(string $id):array{return $this->g->inventory($id);}
    public function read(string $key):?array{return $this->g->read($key);}
    public function removeExact(array $binding):void{$this->g->removeExact($binding);}
}
final class ActualOutcome40Resource implements ResourceAdapter {
    public function __construct(private PurgeResourceGateway $g,private PurgeBoundary $b){Guard::need($g->boundTo('outcome',$b),'ACTUAL_PURGE_RESOURCE_POLICY_CONFLICT');}
    public function boundTo(PurgeBoundary $b):bool{return $b===$this->b;}
    public function inventory(string $id):array{return $this->g->inventory($id);}
    public function read(string $key):?array{return $this->g->read($key);}
    public function removeExact(array $binding):void{$this->g->removeExact($binding);}
}
/** Physical mail deletion has no automatic path. Read includes all Marketing mail and Trash. */
final class ActualMarketingManualMailResource implements ResourceAdapter {
    public function __construct(private PurgeResourceGateway $g,private PurgeBoundary $b){Guard::need($g->boundTo('email',$b),'ACTUAL_PURGE_RESOURCE_POLICY_CONFLICT');}
    public function boundTo(PurgeBoundary $b):bool{return $b===$this->b;}
    public function inventory(string $id):array{return $this->g->inventory($id);}
    public function read(string $key):?array{return $this->g->read($key);}
    public function removeExact(array $binding):void{Guard::need(false,'ACTUAL_PURGE_MAIL_MANUAL_ONLY');}
}
final class PurgeCaptureBoundary implements ResourceAdapter {
    public function __construct(private ActualPurgeCaptureResource $capture,private PurgeBoundary $b){}
    public function inventory(string $id):array{return $this->b->io('capture_inventory',fn()=>$this->capture->inventory($id));}
    public function read(string $key):?array{return $this->b->io('capture_read',fn()=>$this->capture->read($key));}
    public function removeExact(array $binding):void{$this->b->assertMutation('capture',$binding);$this->b->io('capture_remove_exact',fn()=>$this->capture->removeExact($binding),$binding);}
}
