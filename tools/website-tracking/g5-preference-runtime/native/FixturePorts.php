<?php
declare(strict_types=1);
namespace BSRE\PreferenceNative;
use BSRE\ActualRetention\PreferenceV1 as V;
use BSRE\ClosedRetention\Workflow as W;

/** Test fixtures only. This file is excluded from the five-file runtime source manifest. */
function fixed(): void {
    global $wpdb;
    if(PHP_SAPI!=='cli'||!defined('WP_ENVIRONMENT_TYPE')||WP_ENVIRONMENT_TYPE!=='local'||DB_NAME!=='bsre_synthetic'||
        DB_HOST!=='localhost:/tmp/bsre.sock'||DB_USER!=='root'||DB_PASSWORD!==''||
        get_class($wpdb)!=='BSRE\\ClosedRetention\\LeaseBoundWpdb'||!str_starts_with($wpdb->prefix,'g37_pref_')||
        is_writable('/opt/wordpress')||is_writable('/opt/lab/g36')||is_writable('/opt/lab/g37-pref'))throw new \RuntimeException('G37_FIXED_SYNTHETIC_FIXTURE_REQUIRED');
}
final class Keys implements V\SnapshotKeys {
    public array $values=[];public string $active='native-ledger-0';public bool $failSeal=false;
    public function __construct(){fixed();$this->values[$this->active]=random_bytes(32);}
    public function activeId(): string {fixed();if($this->failSeal){$this->failSeal=false;throw new \RuntimeException('G37_INJECTED_KEY_FAILURE');}return$this->active;}
    public function key(string $id): string {fixed();if(!isset($this->values[$id]))throw new \RuntimeException('G37_FIXTURE_KEY_ABSENT');return$this->values[$id];}
}
final class Services implements V\SignedTransport,V\IndependentKeys {
    public array $anchor;public array $anchors=[];public array $snapshots=[];public array $snapshotKeys=[];public int $calls=0;
    public bool $badSignature=false;public bool $denyCoverage=false;public bool $loseCasAck=false;public bool $rollbackKey=false;
    public bool $earlyClosure=false;public bool $closedBasis=false;public bool $expiredSnapshot=false;public bool $denyCatalog=false;
    public int $approvalDelaySeconds=0;public int $casCalls=0;public ?string $delayMutation=null;public ?int $referenceDelayUntil=null;public int $mutableCalls=0;
    public ?\Closure $onCoverage=null;
    private string $secret;private string $public;
    private int $rotation=0;
    public function __construct(public Keys $keys){
        fixed();$pair=sodium_crypto_sign_keypair();$this->secret=sodium_crypto_sign_secretkey($pair);$this->public=sodium_crypto_sign_publickey($pair);$this->anchor=V\Custody::zero();
    }
    public function publicKey(string $service,string $keyId): string {fixed();if($keyId!=='synthetic-native-authority')throw new \RuntimeException('G37_FIXTURE_KEY_ID');return$this->public;}
    public function setAnchor(string $scope,array $anchor): void {fixed();$this->anchors[$scope]=$anchor;$this->anchor=$anchor;}
    public function exchange(string $operation,array $request): string {
        fixed();$this->calls++;$p=$request['payload'];$service=$request['service'];$claims=null;
        $mutable=in_array($service.':'.$operation,['preference-snapshot:STORE','preference-snapshot:EXPIRE','preference-keys:PREPARE_COMPACTION','preference-keys:FINISH_COMPACTION','preference-anchor:COMPARE_AND_SWAP'],true);
        $authorizationHash=null;
        if($mutable){
            $a=$p['authorization']??null;if(!is_array($a))throw new \RuntimeException('G37_INDEPENDENT_APPROVAL_REQUIRED');
            V\Guard::keys($a,['action','plan_hash','authorized_until','approval']);$e=$a['approval'];
            if(!is_array($e))throw new \RuntimeException('G37_INDEPENDENT_APPROVAL_REQUIRED');
            V\Guard::keys($e,['key_id','statement','signature']);$st=$e['statement'];$sig=base64_decode($e['signature'],true);
            if(!is_array($st)||$e['key_id']!=='synthetic-native-authority'||!is_string($sig)||strlen($sig)!==64||
                !sodium_crypto_sign_verify_detached($sig,W::digest($st),$this->public)||$st['contract']!==$request['contract']||
                $st['service']!=='owner-approval'||$st['operation']!=='APPROVE'||$st['scope']!==$request['scope']||
                $st['source']!==$request['source']||$st['actor']!==$request['actor']||
                $st['claims']!==['approved'=>true,'action'=>$a['action'],'plan_hash'=>$a['plan_hash'],'expires_at'=>$a['authorized_until']])
                throw new \RuntimeException('G37_INDEPENDENT_APPROVAL_REQUIRED');
            $allowed=['STORE'=>['BACKUP'],'EXPIRE'=>['EXPIRE_BACKUP'],'PREPARE_COMPACTION'=>['COMPACT'],
                'FINISH_COMPACTION'=>['COMPACT','RECONCILE'],'COMPARE_AND_SWAP'=>['INITIALIZE','RETIRE','RESTORE','COMPACT','BACKUP','RECONCILE']];
            if(!in_array($a['action'],$allowed[$operation],true))throw new \RuntimeException('G37_INDEPENDENT_ACTION_DENIED');
            if($this->delayMutation===$operation){$this->delayMutation=null;while(microtime(true)<$a['authorized_until']+0.25)usleep(100000);}
            // Delayed transport does not renew independently verified authority.
            if(!is_int($a['authorized_until'])||time()>=$a['authorized_until']||$st['expires_at']<=time())throw new \RuntimeException('G37_EXPIRED_INDEPENDENT_MUTATION_DENIED');
            $this->mutableCalls++;$authorizationHash=W::digest($a);
        }

        if($service==='owner-approval'&&$operation==='APPROVE'){
            if($this->approvalDelaySeconds>0){$until=max(microtime(true)+$this->approvalDelaySeconds,$p['expires_at']+0.25);$this->approvalDelaySeconds=0;while(microtime(true)<$until)usleep(100000);}
            $claims=['approved'=>true,'action'=>$p['action'],'plan_hash'=>$p['plan_hash'],'expires_at'=>$p['expires_at']];
        }
        elseif($service==='preference-anchor'&&$operation==='CURRENT')$claims=['anchor'=>$this->anchors[$request['scope']]??V\Custody::zero()];
        elseif($service==='preference-anchor'&&$operation==='COMPARE_AND_SWAP'){
            if(!is_int($p['authorized_until']??null)||time()>=$p['authorized_until'])throw new \RuntimeException('G37_EXPIRED_INDEPENDENT_CAS_DENIED');
            $this->casCalls++;
            $actual=$this->anchors[$request['scope']]??V\Custody::zero();
            if($actual!==$p['before']&&$actual!==$p['after'])throw new \RuntimeException('G37_FIXTURE_CAS_CONFLICT');
            $this->setAnchor($request['scope'],$p['after']);
            if($this->loseCasAck){$this->loseCasAck=false;throw new \RuntimeException('G37_INJECTED_CAS_ACK_LOSS');}
            $claims=['before'=>$p['before'],'after'=>$p['after'],'operation'=>$p['operation'],'durable'=>true,'authorized_until'=>$p['authorized_until']];
        }elseif($service==='preference-reference-index'){
            global $wpdb;
            if($this->referenceDelayUntil!==null){$until=$this->referenceDelayUntil;$this->referenceDelayUntil=null;while(microtime(true)<$until+0.25)usleep(100000);}
            $in=implode(',',array_fill(0,count($p['subjects']),'%s'));
            $history=$wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_history WHERE subject_key IN ({$in}) ORDER BY receipt",...$p['subjects']),ARRAY_A);
            $receipts=array_merge(array_column($history,'receipt'),array_column($p['retired'],'receipt'));$requests=[];$hashes=[];
            // Independent native collector fixture: actual SQL rows, no returned rows/IDs in receipts.
            $cursor='';$scanned=0;
            do{
             $wpdb->last_error='';$rows=$wpdb->get_results($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id>%s ORDER BY request_id LIMIT 257",$cursor),ARRAY_A);
             if($wpdb->last_error!==''||!is_array($rows)||count($rows)>257||$scanned>10000)throw new \RuntimeException('G37_FIXTURE_REFERENCE_COLLECTOR_BOUND');
             foreach($rows as $r){
                $relevant=in_array($r['subject_key'],$p['subjects'],true)||in_array($r['decision_version'],$receipts,true);
                if((int)$r['purpose_version']===1){
                    $record=json_decode($r['purpose_json'],true,16,JSON_THROW_ON_ERROR);
                    foreach(['analytics','advertising'] as $purpose)foreach(['first','last'] as $slot)if(in_array($record[$purpose][$slot]['decision_version']??null,$receipts,true))$relevant=true;
                }
                if($relevant){$requests[]=$r['request_id'];$hashes[$r['request_id']]=V\Algebra::rowHash($r);}
                $cursor=$r['request_id'];$scanned++;
             }
            }while(count($rows)===257);
            if(count($requests)>1000)throw new \RuntimeException('G37_FIXTURE_REFERENCE_RESULT_BOUND');
            sort($requests,SORT_STRING);ksort($hashes);
            $claims=['binding'=>$p,'requests'=>$requests,'capture_hashes'=>$hashes,'head'=>['version'=>1,'hash'=>W::digest($hashes)],'unlinked_exclusion_complete'=>!$this->denyCatalog,'fenced_until'=>time()+30];
        }elseif($service==='preference-coverage'){
            if($this->onCoverage!==null){$hook=$this->onCoverage;$this->onCoverage=null;$hook();}
            $heads=[];foreach(['g1_g2_p','intake26','outbox','receiver','history','closure'] as $name)$heads[$name]=['version'=>1,'hash'=>W::digest(['SYNTHETIC_NATIVE_ONLY',$name,$p['snapshot_hash']])];
            $bases=[];
            if($p['action']==='RETIRE')foreach($p['targets'] as $t)$bases[]=['target_hash'=>W::digest($t),'kind'=>$this->closedBasis?'CLOSED_ENQUIRIES':'NEVER_SUBMITTED',
                'all_roles_complete'=>true,'all_enquiries_resolved'=>true,'last_closed_at'=>$this->closedBasis?time()-($this->earlyClosure?86400:400*86400):0,
                'closure_set_hash'=>$this->closedBasis?hash('sha256','SYNTHETIC_CLOSED_SET'):str_repeat('0',64)];
            $claims=['complete'=>!$this->denyCoverage,'snapshot_hash'=>$p['snapshot_hash'],'targets_hash'=>$p['targets_hash'],'action'=>$p['action'],'plan_hash'=>$p['plan_hash'],
                'purpose'=>['RETIRE'=>'RETENTION_BASIS','RESTORE'=>'RESTORE_REFERENCE_CUSTODY','COMPACT'=>'RECOVERY_EXPIRY_CUSTODY'][$p['action']],
                'bases'=>$bases,'source_heads'=>$heads,'history_complete'=>true,'coverage_expires_at'=>time()+30];
            if($this->rollbackKey&&$p['action']==='RETIRE'){$this->keys->failSeal=true;$this->rollbackKey=false;}
        }elseif($service==='preference-snapshot'&&$operation==='STORE'){
            $id=W::digest(['snapshot'=>$p['snapshot_hash'],'anchor'=>$p['anchor'],'created'=>$p['created_at']]);$key=random_bytes(32);$nonce=random_bytes(24);
            $metadata=['version'=>1,'source'=>'ACTUAL_PREFERENCE_SNAPSHOT_V1','createdAtMs'=>$p['created_at']*1000,'expiresAtMs'=>$p['expires_at']*1000,
                'snapshotSha256'=>$p['snapshot_hash'],'deletionLedgerWatermark'=>$p['anchor']['sequence']];
            $this->snapshots[$id]=['metadata'=>$metadata,'nonce'=>$nonce,'cipher'=>sodium_crypto_aead_xchacha20poly1305_ietf_encrypt(json_encode($p['snapshot'],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES),$id,$nonce,$key)];
            $this->snapshotKeys[$id]=['key'=>$key,'expires'=>$p['expires_at']];
            $claims=['snapshot_id'=>$id,'snapshot_hash'=>$p['snapshot_hash'],'created_at'=>$p['created_at'],'expires_at'=>$p['expires_at'],'key_expires_at'=>$p['expires_at'],'ledger_excluded'=>true,'encrypted'=>true];
        }elseif($service==='preference-snapshot'&&$operation==='QUARANTINE'){
            $id=$p['snapshot_id'];$package=$this->snapshots[$id]??null;$key=$this->snapshotKeys[$id]??null;
            if($package===null||$key===null)throw new \RuntimeException('G37_FIXTURE_SNAPSHOT_ABSENT');
            $plain=sodium_crypto_aead_xchacha20poly1305_ietf_decrypt($package['cipher'],$id,$package['nonce'],$key['key']);
            if(!is_string($plain))throw new \RuntimeException('G37_FIXTURE_SNAPSHOT_CIPHER');
            $metadata=$package['metadata'];$expires=$key['expires'];
            if($this->expiredSnapshot){$metadata['createdAtMs']=(time()-2592001)*1000;$metadata['expiresAtMs']=$metadata['createdAtMs']+2592000000;$expires=intdiv($metadata['expiresAtMs'],1000);}
            $claims=['snapshot_id'=>$id,'snapshot'=>json_decode($plain,true,48,JSON_THROW_ON_ERROR),'metadata'=>$metadata,'current_anchor'=>$p['current_anchor'],
                'key_expires_at'=>$expires,'quarantined'=>true,'ledger_excluded'=>true];
        }elseif($service==='preference-snapshot'&&$operation==='EXPIRE'){
            $id=$p['snapshot_id'];if(isset($this->snapshotKeys[$id])&&$this->snapshotKeys[$id]['expires']>time())throw new \RuntimeException('G37_FIXTURE_EARLY_SNAPSHOT_DELETE_DENIED');
            unset($this->snapshotKeys[$id],$this->snapshots[$id]);$claims=['snapshot_id'=>$id,'absent'=>true,'key_absent'=>true,'expired_at'=>time()];
        }elseif($service==='preference-keys'&&$operation==='PREPARE_COMPACTION'){
            $new='native-ledger-'.(++$this->rotation);$this->keys->values[$new]=random_bytes(32);$this->keys->active=$new;
            $claims=['old_key'=>$p['old_key'],'new_key'=>$new,'plan_hash'=>$p['plan_hash'],'after_floor'=>$p['after_floor'],
                'earlier_snapshot_catalog_complete'=>true,'earlier_snapshots_absent'=>$this->snapshots===[],'earlier_snapshot_keys_absent'=>$this->snapshotKeys===[]];
        }elseif($service==='preference-keys'&&$operation==='FINISH_COMPACTION'){
            unset($this->keys->values[$p['transition']['old_key']]);$claims=['transition'=>$p['transition'],'anchor'=>$p['anchor'],'operation'=>$p['operation'],'old_key_absent'=>true,'catalog_complete'=>true];
        }
        if(!is_array($claims))throw new \RuntimeException('G37_FIXTURE_OPERATION_UNSUPPORTED');
        if($mutable)$claims['authorization_hash']=$authorizationHash;
        $statement=['contract'=>$request['contract'],'service'=>$service,'operation'=>$operation,'scope'=>$request['scope'],'source'=>$request['source'],'actor'=>$request['actor'],
            'challenge'=>$request['challenge'],'request_hash'=>W::digest($request),'issued_at'=>time(),'expires_at'=>time()+30,'claims'=>$claims];
        $signature=sodium_crypto_sign_detached(W::digest($statement),$this->secret);
        if($this->badSignature)$signature=str_repeat("\0",64);
        return json_encode(['key_id'=>'synthetic-native-authority','statement'=>$statement,'signature'=>base64_encode($signature)],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
    }
}
