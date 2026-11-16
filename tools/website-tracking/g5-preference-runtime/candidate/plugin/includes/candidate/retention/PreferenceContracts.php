<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\PreferenceV1;

/** Server-owned transport configuration. The return value is authenticated below, never trusted as an array. */
interface SignedTransport { public function exchange(string $operation, array $request): string; }
interface IndependentKeys { public function publicKey(string $service, string $keyId): string; }
interface SnapshotKeys {
    public function activeId(): string;
    public function key(string $id): string;
}
final class HeldTransport implements SignedTransport {
    public function exchange(string $operation,array $request): string { Guard::fail('PREFERENCE_PROVIDER_UNCONFIGURED'); }
}
final class HeldKeys implements IndependentKeys, SnapshotKeys {
    public function publicKey(string $service,string $keyId): string { Guard::fail('PREFERENCE_INDEPENDENT_KEY_UNCONFIGURED'); }
    public function activeId(): string { Guard::fail('PREFERENCE_ENCRYPTION_KEY_UNCONFIGURED'); }
    public function key(string $id): string { Guard::fail('PREFERENCE_ENCRYPTION_KEY_UNCONFIGURED'); }
}
final class Guard {
    public static function fail(string $code): never { throw new \RuntimeException($code); }
    public static function enabled(): void {
        if(!defined('BSRE_G5_PREFERENCE_RUNTIME_ENABLED') || BSRE_G5_PREFERENCE_RUNTIME_ENABLED!==true) self::fail('PREFERENCE_RUNTIME_DISABLED');
    }
    public static function keys(array $v,array $expected): void {
        $actual=array_keys($v);sort($actual);sort($expected);
        if($actual!==$expected)self::fail('PREFERENCE_SCHEMA_INVALID');
    }
    public static function hash(string $v): void { if(preg_match('/^[a-f0-9]{64}$/D',$v)!==1)self::fail('PREFERENCE_HASH_INVALID'); }
    public static function uint(mixed $v): int {
        if(is_int($v)&&$v>=0)return $v;
        if(is_string($v)&&preg_match('/^(0|[1-9][0-9]*)$/D',$v)===1 &&
            (strlen($v)<strlen((string)PHP_INT_MAX) || strlen($v)===strlen((string)PHP_INT_MAX)&&strcmp($v,(string)PHP_INT_MAX)<=0))return(int)$v;
        self::fail('PREFERENCE_INTEGER_INVALID');
    }
    public static function digest(array $v): string { return \BSRE\ClosedRetention\Workflow::digest($v); }
    public static function json(string $raw,int $maximum=1048576): array {
        if(strlen($raw)>$maximum)self::fail('PREFERENCE_DOCUMENT_UNBOUNDED');
        $v=json_decode($raw,true,48,JSON_THROW_ON_ERROR);
        // Canonical transport encoding rejects duplicate keys, alternate numeric forms and invisible suffixes.
        if(!is_array($v)||json_encode($v,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)!==$raw)self::fail('PREFERENCE_JSON_NOT_CANONICAL');
        return $v;
    }
}
/** Actual-domain envelope; legacy kind exists only inside the pure validation projection. */
final class SnapshotFormat {
    public const KIND='ACTUAL_PREFERENCE_SUBJECT_BATCH_V1';
    public static function subjects(array $subjects,string $partition,bool $empty=false): array {
        if(preg_match('/^[a-f0-9]{2}$/D',$partition)!==1||!array_is_list($subjects)||count($subjects)>32||(!$empty&&$subjects===[]))Guard::fail('PREFERENCE_SUBJECT_BATCH_INVALID');
        foreach($subjects as $s)if(!is_string($s)||preg_match('/^[a-f0-9]{64}$/D',$s)!==1||substr($s,0,2)!==$partition)Guard::fail('PREFERENCE_SUBJECT_PARTITION_CONFLICT');
        $sorted=$subjects;sort($sorted,SORT_STRING);
        if($sorted!==$subjects||count(array_unique($subjects))!==count($subjects))Guard::fail('PREFERENCE_SUBJECT_BATCH_INVALID');
        return$subjects;
    }
    public static function plan(array $snapshot,int $now,bool $enabled): array {
        Guard::keys($snapshot,['kind','batch','state','history','captures']);
        if($snapshot['kind']!==self::KIND||!is_array($snapshot['batch']))Guard::fail('PREFERENCE_SNAPSHOT_DOMAIN_INVALID');
        $b=$snapshot['batch'];Guard::keys($b,['partition','subjects','references']);
        self::subjects($b['subjects'],$b['partition'],true);Guard::keys($b['references'],['version','hash']);
        Guard::uint($b['references']['version']);Guard::hash($b['references']['hash']);
        $projected=['kind'=>\BSRE\RetentionReview\RetentionInventory::KIND,'state'=>$snapshot['state'],'history'=>$snapshot['history'],'captures'=>$snapshot['captures']];
        foreach(['state','history'] as $part)foreach($snapshot[$part] as $row)if(!in_array($row['subject_key']??null,$b['subjects'],true))Guard::fail('PREFERENCE_SNAPSHOT_SCOPE_CONFLICT');
        $review=\BSRE\PurposeRetention\RetentionInventory::plan($projected,$now,$enabled);
        // Preserve all original holds; additionally hold cross-subject primary/nested references.
        $receiptSubjects=[];$refSubjects=[];$blocked=[];
        foreach($snapshot['history'] as $row)$receiptSubjects[$row['receipt']]=$row['subject_key'];
        foreach(['state'=>'subject_key','history'=>'receipt'] as $kind=>$pk)foreach($snapshot[$kind] as $row)$refSubjects['bsre_consent_'.$kind.':'.$row[$pk]]=$row['subject_key'];
        foreach($snapshot['captures'] as $capture){
            $refs=[$capture['decision_version']];
            if((int)($capture['purpose_version']??0)===1){
                $record=json_decode($capture['purpose_json'],true,16,JSON_THROW_ON_ERROR);
                foreach(['analytics','advertising'] as $purpose)foreach(['first','last'] as $slot)if(isset($record[$purpose][$slot]['decision_version']))$refs[]=$record[$purpose][$slot]['decision_version'];
            }
            foreach($refs as $ref)if(isset($receiptSubjects[$ref]))$blocked[$receiptSubjects[$ref]]=true;
        }
        foreach($review['rows'] as &$row)if(isset($blocked[$refSubjects[$row['row_ref']]??''])){
            $row['classification']='HOLD';$row['reasons'][]='ACTUAL_LIVE_PERMISSION_REFERENCE';
        }unset($row);
        return$review;
    }
}
final class Policy {
    public const CONTRACT='bsre-preference-runtime-v1';
    public const ACTIONS=['INITIALIZE','RETIRE','RESTORE','COMPACT','BACKUP','EXPIRE_BACKUP','RECONCILE'];
    public function __construct(public readonly \BSRE\ActualRetention\RuntimePolicy $base,public readonly string $sourceVersion,public readonly string $partition) {
        Guard::hash($sourceVersion);if(preg_match('/^[a-f0-9]{2}$/D',$partition)!==1)Guard::fail('PREFERENCE_PARTITION_INVALID');
    }
    // Stable across source revisions: changing code must never reset independent floors.
    // Fixed two-hex partitions cannot be split/reassigned to escape old retirement custody.
    public function scope(): string { return hash('sha256',self::CONTRACT.'|'.$this->base->scope().'|partition:'.$this->partition); }
    public function actor(): string { Guard::enabled();$this->sources();return $this->base->actor(); }
    public function source(): array {
        Guard::enabled();$this->sources();
        foreach(['BSRE_CANONICAL_LEASE_SOURCE_SHA256','BSRE_CANONICAL_LEASE_PRODUCER_SHA256'] as $c)if(!defined($c)||!is_string(constant($c)))Guard::fail('PREFERENCE_CANONICAL_SOURCE_REQUIRED');
        return ['preference'=>$this->sourceVersion,'canonical'=>BSRE_CANONICAL_LEASE_SOURCE_SHA256,
            'producer'=>BSRE_CANONICAL_LEASE_PRODUCER_SHA256,'admission'=>Guard::digest(\BSRE\RetentionAdmission\configuration())];
    }
    public function authorize(string $action,string $digest,string $nonce): string {
        $actor=$this->actor();Guard::hash($digest);
        if(!in_array($action,self::ACTIONS,true)||!function_exists('wp_verify_nonce')||
            !wp_verify_nonce($nonce,'bsre-pref-v1|'.$this->scope().'|'.$action.'|'.$digest))Guard::fail('PREFERENCE_OWNER_ACTION_NONCE_REQUIRED');
        return $actor;
    }
    private function sources(): void {
        $path=__DIR__.'/preference-source.json';
        if(!defined('BSRE_G5_PREFERENCE_SOURCE_SHA256')||BSRE_G5_PREFERENCE_SOURCE_SHA256!==$this->sourceVersion||
            !is_file($path)||is_link($path)||realpath($path)!==$path)Guard::fail('PREFERENCE_SOURCE_UNBOUND');
        $raw=file_get_contents($path);
        if(!is_string($raw)||strlen($raw)>65536||hash('sha256',$raw)!==$this->sourceVersion)Guard::fail('PREFERENCE_SOURCE_CHANGED');
        $m=json_decode($raw,true,8,JSON_THROW_ON_ERROR);Guard::keys($m,['contract','files']);
        if($m['contract']!==self::CONTRACT||!is_array($m['files'])||count($m['files'])!==5)Guard::fail('PREFERENCE_SOURCE_UNBOUND');
        $expected=['ActualPreferenceRetention.php','PreferenceAlgebra.php','PreferenceAtomicStore.php','PreferenceContracts.php','PreferenceCustody.php'];
        $names=array_keys($m['files']);sort($names);sort($expected);if($names!==$expected)Guard::fail('PREFERENCE_SOURCE_UNBOUND');
        foreach($m['files'] as $name=>$sha){
            Guard::hash($sha);$file=__DIR__.'/'.$name;
            if(is_link($file)||realpath($file)!==$file||hash_file('sha256',$file)!==$sha)Guard::fail('PREFERENCE_SOURCE_CHANGED');
        }
    }
}
/** Fresh independent Ed25519 statements. WP's receiver-HMAC key is not an authority key. */
/** Only an independently verified exact approval can construct mutable authority. */
final class Authorization {
    private function __construct(public readonly string $action,public readonly string $digest,
        public readonly int $expiresAt,private array $approval) {}
    public static function approve(Proofs $proofs,string $action,string $digest,int $expiresAt): self {
        Guard::hash($digest);if($expiresAt<=time())Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
        $approval=null;$c=$proofs->request('owner-approval','APPROVE',['action'=>$action,'plan_hash'=>$digest,'expires_at'=>$expiresAt],$approval);
        Guard::keys($c,['approved','action','plan_hash','expires_at']);
        if($c!==['approved'=>true,'action'=>$action,'plan_hash'=>$digest,'expires_at'=>$expiresAt]||!is_array($approval))Guard::fail('PREFERENCE_EXACT_APPROVAL_REQUIRED');
        $self=new self($action,$digest,$expiresAt,$approval);$self->assertCurrent();return$self;
    }
    public function assertCurrent(): void {if(time()>=$this->expiresAt)Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');}
    public function payload(): array {return['action'=>$this->action,'plan_hash'=>$this->digest,'authorized_until'=>$this->expiresAt,'approval'=>$this->approval];}
}
final class Proofs {
    public function __construct(private Policy $policy,private SignedTransport $transport=new HeldTransport(),private IndependentKeys $keys=new HeldKeys()) {}
    public function request(string $service,string $operation,array $payload,?array &$attestation=null): array {
        $source=$this->policy->source();$actor=$this->policy->actor();$challenge=bin2hex(random_bytes(32));
        $request=['contract'=>Policy::CONTRACT,'service'=>$service,'operation'=>$operation,'scope'=>$this->policy->scope(),
            'source'=>$source,'actor'=>$actor,'challenge'=>$challenge,'payload'=>$payload];
        $e=Guard::json($this->transport->exchange($operation,$request));Guard::keys($e,['key_id','statement','signature']);
        if(!is_string($e['key_id'])||preg_match('/^[A-Za-z0-9_-]{1,64}$/D',$e['key_id'])!==1||!is_array($e['statement'])||!is_string($e['signature']))Guard::fail('PREFERENCE_AUTHENTICATED_PROOF_REQUIRED');
        $s=$e['statement'];Guard::keys($s,['contract','service','operation','scope','source','actor','challenge','request_hash','issued_at','expires_at','claims']);
        foreach(['contract','service','operation','scope','source','actor','challenge'] as $name)if($s[$name]!==$request[$name])Guard::fail('PREFERENCE_PROOF_BINDING_CHANGED');
        $now=time();$sig=base64_decode($e['signature'],true);$key=$this->keys->publicKey($service,$e['key_id']);
        if($s['request_hash']!==Guard::digest($request)||!is_int($s['issued_at'])||!is_int($s['expires_at'])||
            $s['issued_at']>$now||$s['issued_at']<$now-30||$s['expires_at']<=$now||$s['expires_at']>$s['issued_at']+60||
            !is_array($s['claims'])||!is_string($sig)||base64_encode($sig)!==$e['signature']||
            !function_exists('sodium_crypto_sign_verify_detached')||strlen($key)!==SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES||
            strlen($sig)!==SODIUM_CRYPTO_SIGN_BYTES||!sodium_crypto_sign_verify_detached($sig,Guard::digest($s),$key))
            Guard::fail('PREFERENCE_AUTHENTICATED_PROOF_REQUIRED');
        $attestation=$e;return $s['claims'];
    }
    public function approval(string $action,string $digest,?int $expiresAt=null): Authorization {
        return Authorization::approve($this,$action,$digest,$expiresAt??time()+30);
    }
    public function mutation(string $service,string $operation,array $payload,Authorization $authorization): array {
        $authorization->assertCurrent();$binding=$authorization->payload();
        $allowed=['preference-snapshot:STORE'=>['BACKUP'],'preference-snapshot:EXPIRE'=>['EXPIRE_BACKUP'],
            'preference-keys:PREPARE_COMPACTION'=>['COMPACT'],'preference-keys:FINISH_COMPACTION'=>['COMPACT','RECONCILE'],
            'preference-anchor:COMPARE_AND_SWAP'=>['INITIALIZE','RETIRE','RESTORE','COMPACT','BACKUP','RECONCILE']];
        if(!in_array($authorization->action,$allowed[$service.':'.$operation]??[],true))Guard::fail('PREFERENCE_MUTATION_ACTION_MISMATCH');
        if(array_key_exists('authorization',$payload))Guard::fail('PREFERENCE_AUTHORIZATION_COLLISION');
        // Service MUST authenticate the independent approval and enforce this same
        // immutable deadline atomically before every external effect, even after I/O.
        $c=$this->request($service,$operation,$payload+['authorization'=>$binding]);
        if(($c['authorization_hash']??null)!==Guard::digest($binding))Guard::fail('PREFERENCE_MUTATION_AUTHORIZATION_UNCONFIRMED');
        unset($c['authorization_hash']);$authorization->assertCurrent();return$c;
    }
    public function references(array $subjects,string $stateHistoryHash,array $retired,array $ledgerAnchor,?string $connection,bool $locked): array {
        SnapshotFormat::subjects($subjects,$this->policy->partition);Guard::hash($stateHistoryHash);
        $payload=['partition'=>$this->policy->partition,'subjects'=>$subjects,'state_history_hash'=>$stateHistoryHash,
            'retired'=>$retired,'ledger_anchor'=>$ledgerAnchor,'connection_id'=>$connection,'locked'=>$locked];
        $c=$this->request('preference-reference-index','COMPLETE_BATCH_REFERENCES',$payload);
        Guard::keys($c,['binding','requests','capture_hashes','head','unlinked_exclusion_complete','fenced_until']);
        if($c['binding']!==$payload||$c['unlinked_exclusion_complete']!==true||!is_array($c['requests'])||!array_is_list($c['requests'])||
            count($c['requests'])>1000||!is_array($c['capture_hashes'])||!is_array($c['head'])||!is_int($c['fenced_until'])||
            $c['fenced_until']<=time()||$c['fenced_until']>time()+30)Guard::fail('PREFERENCE_REFERENCE_COVERAGE_HELD');
        $ids=$c['requests'];$sorted=$ids;sort($sorted,SORT_STRING);
        if($ids!==$sorted||count(array_unique($ids))!==count($ids))Guard::fail('PREFERENCE_REFERENCE_COVERAGE_HELD');
        foreach($ids as $id)if(!is_string($id)||preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/Di',$id)!==1)Guard::fail('PREFERENCE_REFERENCE_COVERAGE_HELD');
        Guard::keys($c['capture_hashes'],$ids);foreach($c['capture_hashes'] as $hash)Guard::hash($hash);
        Guard::keys($c['head'],['version','hash']);Guard::uint($c['head']['version']);Guard::hash($c['head']['hash']);return$c;
    }
    public function coverage(string $snapshotHash,array $targets,string $action,string $planHash,int $planExpiresAt): int {
        Guard::hash($snapshotHash);Guard::hash($planHash);
        if(!in_array($action,['RETIRE','RESTORE','COMPACT'],true)||!array_is_list($targets)||count($targets)>1000)Guard::fail('PREFERENCE_COVERAGE_SCOPE_INVALID');
        if(time()>=$planExpiresAt)Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
        $c=$this->request('preference-coverage','COVERAGE',['snapshot_hash'=>$snapshotHash,'targets'=>$targets,'targets_hash'=>Guard::digest($targets),'action'=>$action,'plan_hash'=>$planHash,'plan_expires_at'=>$planExpiresAt]);
        Guard::keys($c,['complete','snapshot_hash','targets_hash','action','plan_hash','purpose','bases','source_heads','history_complete','coverage_expires_at']);
        if($c['complete']!==true||!is_bool($c['history_complete'])||($action!=='COMPACT'&&$c['history_complete']!==true)||
            $c['snapshot_hash']!==$snapshotHash||$c['targets_hash']!==Guard::digest($targets)||$c['action']!==$action||$c['plan_hash']!==$planHash||
            !is_int($c['coverage_expires_at'])||$c['coverage_expires_at']<=time()||$c['coverage_expires_at']>time()+30||
            !is_array($c['source_heads'])||!is_array($c['bases'])||!array_is_list($c['bases']))Guard::fail('PREFERENCE_COVERAGE_HELD');
        $purpose=['RETIRE'=>'RETENTION_BASIS','RESTORE'=>'RESTORE_REFERENCE_CUSTODY','COMPACT'=>'RECOVERY_EXPIRY_CUSTODY'][$action];
        if($c['purpose']!==$purpose)Guard::fail('PREFERENCE_COVERAGE_PURPOSE_CONFLICT');
        if($action==='RETIRE'){
            if(count($c['bases'])!==count($targets))Guard::fail('PREFERENCE_RETENTION_BASIS_INCOMPLETE');
            foreach($targets as $i=>$target){
                $basis=$c['bases'][$i];if(!is_array($basis))Guard::fail('PREFERENCE_RETENTION_BASIS_INCOMPLETE');
                Guard::keys($basis,['target_hash','kind','all_roles_complete','all_enquiries_resolved','last_closed_at','closure_set_hash']);
                if($basis['target_hash']!==Guard::digest($target)||$basis['all_roles_complete']!==true||$basis['all_enquiries_resolved']!==true||
                    !is_int($basis['last_closed_at'])||!is_string($basis['closure_set_hash']))Guard::fail('PREFERENCE_RETENTION_BASIS_INCOMPLETE');
                Guard::hash($basis['closure_set_hash']);
                if($basis['kind']==='NEVER_SUBMITTED'){
                    if($basis['last_closed_at']!==0||$basis['closure_set_hash']!==str_repeat('0',64))Guard::fail('PREFERENCE_RETENTION_BASIS_INVALID');
                }elseif($basis['kind']==='CLOSED_ENQUIRIES'){
                    if($basis['last_closed_at']<1||$basis['last_closed_at']>time()||$basis['closure_set_hash']===str_repeat('0',64)||
                        \BSRE\RetentionReview\RetentionInventory::anniversary($basis['last_closed_at'])>time())Guard::fail('PREFERENCE_ENQUIRY_RETENTION_NOT_DUE');
                }else Guard::fail('PREFERENCE_RETENTION_BASIS_INVALID');
            }
        }elseif($c['bases']!==[])Guard::fail('PREFERENCE_COVERAGE_PURPOSE_CONFLICT');
        Guard::keys($c['source_heads'],['g1_g2_p','intake26','outbox','receiver','history','closure']);
        foreach($c['source_heads'] as $head){if(!is_array($head))Guard::fail('PREFERENCE_COVERAGE_HELD');Guard::keys($head,['version','hash']);Guard::uint($head['version']);Guard::hash($head['hash']);}
        // The independently operated collector must hold its exact source/fence
        // versions through this deadline, including pending receiver/outbox work.
        // This attests the exact receipt/revision targets, never an inferred empty SQL set.
        if(time()>=$planExpiresAt)Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
        return min($c['coverage_expires_at'],$planExpiresAt);
    }
}
