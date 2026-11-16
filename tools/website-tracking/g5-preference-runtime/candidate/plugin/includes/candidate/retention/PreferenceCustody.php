<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\PreferenceV1;
require_once __DIR__.'/PreferenceContracts.php';

/** Independent preference anchor. It is never passed to the closure journal's revision/hash ABI. */
final class Custody {
    public function __construct(private Policy $policy,private Proofs $proofs,private SnapshotKeys $keys=new HeldKeys()) {}
    public static function zero(): array {
        return ['version'=>1,'operation_revision'=>0,'sequence'=>0,'chain_hash'=>str_repeat('0',64),
            'floor_sequence'=>0,'floor_hash'=>str_repeat('0',64),'floor_generation'=>0,'compacted_at'=>0,'state_hash'=>str_repeat('0',64)];
    }
    public static function anchor(array $a): void {
        Guard::keys($a,array_keys(self::zero()));
        if($a['version']!==1)Guard::fail('PREFERENCE_ANCHOR_INVALID');
        foreach(['operation_revision','sequence','floor_sequence','floor_generation','compacted_at'] as $k)if(!is_int($a[$k])||$a[$k]<0)Guard::fail('PREFERENCE_ANCHOR_INVALID');
        foreach(['chain_hash','floor_hash','state_hash'] as $k)Guard::hash($a[$k]);
        if($a['floor_sequence']>$a['sequence']||
            ($a['sequence']===0)!==($a['chain_hash']===str_repeat('0',64))||
            ($a['operation_revision']===0)!==($a['state_hash']===str_repeat('0',64))||
            ($a['floor_generation']===0 && ($a['floor_sequence']!==0||$a['floor_hash']!==str_repeat('0',64)||$a['compacted_at']!==0))||
            ($a['floor_generation']>0 && ($a['floor_sequence']===0||$a['compacted_at']===0)))Guard::fail('PREFERENCE_ANCHOR_INVALID');
    }
    public static function next(array $before,array $ledger,string $stateHash): array {
        self::anchor($before);Guard::hash($stateHash);
        if($before['operation_revision']===PHP_INT_MAX)Guard::fail('PREFERENCE_SEQUENCE_EXHAUSTED');
        $a=['version'=>1,'operation_revision'=>$before['operation_revision']+1,'sequence'=>$ledger['anchor']['sequence'],
            'chain_hash'=>$ledger['anchor']['hash'],'floor_sequence'=>$ledger['floor']['sequence'],'floor_hash'=>$ledger['floor']['hash'],
            'floor_generation'=>$ledger['floor']['generation'],'compacted_at'=>$ledger['floor']['compacted_at'],'state_hash'=>$stateHash];
        self::anchor($a);
        if($a['sequence']<$before['sequence']||$a['floor_sequence']<$before['floor_sequence']||
            $a['floor_generation']<$before['floor_generation']||$a['floor_generation']>$before['floor_generation']+1)Guard::fail('PREFERENCE_ANCHOR_REGRESSION');
        return $a;
    }
    public function current(): array {
        $c=$this->proofs->request('preference-anchor','CURRENT',[]);Guard::keys($c,['anchor']);
        if(!is_array($c['anchor']))Guard::fail('PREFERENCE_ANCHOR_INVALID');self::anchor($c['anchor']);return $c['anchor'];
    }
    public function advance(array $before,array $after,string $operation,Authorization $authorization): void {
        self::anchor($before);self::anchor($after);Guard::hash($operation);
        if($after['operation_revision']!==$before['operation_revision']+1)Guard::fail('PREFERENCE_ANCHOR_REGRESSION');
        $authorizedUntil=$authorization->expiresAt;
        if(time()>=$authorizedUntil)Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
        // The independent CAS service must enforce authorized_until atomically,
        // not merely sign a fresh receipt after an expired action.
        $c=$this->proofs->mutation('preference-anchor','COMPARE_AND_SWAP',['before'=>$before,'after'=>$after,'operation'=>$operation,'authorized_until'=>$authorizedUntil],$authorization);
        Guard::keys($c,['before','after','operation','durable','authorized_until']);
        if($c!==['before'=>$before,'after'=>$after,'operation'=>$operation,'durable'=>true,'authorized_until'=>$authorizedUntil]||$this->current()!==$after)Guard::fail('PREFERENCE_CAS_UNCONFIRMED');
    }
    public function seal(array $state,int $revision): string {
        if($revision<1)Guard::fail('PREFERENCE_CIPHER_SCOPE_INVALID');
        $id=$this->keys->activeId();
        if(preg_match('/^[A-Za-z0-9_-]{1,64}$/D',$id)!==1)Guard::fail('PREFERENCE_ENCRYPTION_KEY_UNCONFIGURED');
        $key=$this->keys->key($id);
        if(!function_exists('sodium_crypto_aead_xchacha20poly1305_ietf_encrypt')||strlen($key)!==32)Guard::fail('PREFERENCE_ENCRYPTION_KEY_UNCONFIGURED');
        $plain=json_encode($state,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
        if(strlen($plain)>1048576)Guard::fail('PREFERENCE_STATE_UNBOUNDED');
        $nonce=random_bytes(24);
        try{$cipher=sodium_crypto_aead_xchacha20poly1305_ietf_encrypt($plain,$this->policy->scope().':'.$revision.':'.$id,$nonce,$key);}
        finally{sodium_memzero($key);}
        return json_encode(['version'=>1,'key_id'=>$id,'nonce'=>base64_encode($nonce),'cipher'=>base64_encode($cipher)],JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
    }
    public function open(string $raw,int $revision): array {
        $e=Guard::json($raw,1500000);Guard::keys($e,['version','key_id','nonce','cipher']);
        if($e['version']!==1||$revision<1||!is_string($e['key_id'])||preg_match('/^[A-Za-z0-9_-]{1,64}$/D',$e['key_id'])!==1||
            !is_string($e['nonce'])||!is_string($e['cipher']))Guard::fail('PREFERENCE_CIPHER_SCOPE_INVALID');
        $key=$this->keys->key($e['key_id']);$nonce=base64_decode($e['nonce'],true);$cipher=base64_decode($e['cipher'],true);
        if(strlen($key)!==32||!is_string($nonce)||strlen($nonce)!==24||!is_string($cipher))Guard::fail('PREFERENCE_CIPHER_SCOPE_INVALID');
        try{$plain=sodium_crypto_aead_xchacha20poly1305_ietf_decrypt($cipher,$this->policy->scope().':'.$revision.':'.$e['key_id'],$nonce,$key);}
        finally{sodium_memzero($key);}
        if(!is_string($plain))Guard::fail('PREFERENCE_CIPHER_AUTHENTICATION_FAILED');
        return Guard::json($plain);
    }
    public function backup(array $snapshot,array $anchor,Authorization $authorization): array {
        self::anchor($anchor);$now=time();if($now>intdiv(PHP_INT_MAX,1000)-2592000)Guard::fail('PREFERENCE_CLOCK_INVALID');
        $hash=hash('sha256',json_encode($snapshot,JSON_THROW_ON_ERROR));
        $payload=['snapshot_hash'=>$hash,'anchor'=>$anchor,'created_at'=>$now,'expires_at'=>$now+2592000];
        // Provider stores an authenticated encrypted snapshot under a separately expiring key;
        // it must not restore the current independent preference ledger/checkpoint.
        $c=$this->proofs->mutation('preference-snapshot','STORE',$payload+['snapshot'=>$snapshot],$authorization);
        Guard::keys($c,['snapshot_id','snapshot_hash','created_at','expires_at','key_expires_at','ledger_excluded','encrypted']);
        if(!is_string($c['snapshot_id'])||preg_match('/^[a-f0-9]{64}$/D',$c['snapshot_id'])!==1||$c['snapshot_hash']!==$hash||
            $c['created_at']!==$now||$c['expires_at']!==$now+2592000||$c['key_expires_at']!==$c['expires_at']||
            $c['ledger_excluded']!==true||$c['encrypted']!==true)Guard::fail('PREFERENCE_SNAPSHOT_CUSTODY_HELD');
        return ['snapshot_id'=>$c['snapshot_id'],'expires_at'=>$c['expires_at']];
    }
    public function quarantine(string $snapshotId,array $anchor): array {
        Guard::hash($snapshotId);self::anchor($anchor);
        $c=$this->proofs->request('preference-snapshot','QUARANTINE',['snapshot_id'=>$snapshotId,'current_anchor'=>$anchor]);
        Guard::keys($c,['snapshot_id','snapshot','metadata','current_anchor','key_expires_at','quarantined','ledger_excluded']);
        if($c['snapshot_id']!==$snapshotId||$c['current_anchor']!==$anchor||$c['quarantined']!==true||$c['ledger_excluded']!==true||
            !is_array($c['snapshot'])||!is_array($c['metadata']))Guard::fail('PREFERENCE_SNAPSHOT_CUSTODY_HELD');
        $m=$c['metadata'];Guard::keys($m,['version','source','createdAtMs','expiresAtMs','snapshotSha256','deletionLedgerWatermark']);
        if($m['version']!==1||$m['source']!=='ACTUAL_PREFERENCE_SNAPSHOT_V1'||!is_int($m['createdAtMs'])||!is_int($m['expiresAtMs'])||
            $m['createdAtMs']<1||$m['expiresAtMs']-$m['createdAtMs']!==2592000000||
            $m['createdAtMs']>time()*1000||$m['expiresAtMs']<=time()*1000||!is_int($c['key_expires_at'])||
            $c['key_expires_at']*1000!==$m['expiresAtMs']||
            $m['snapshotSha256']!==hash('sha256',json_encode($c['snapshot'],JSON_THROW_ON_ERROR)))
            Guard::fail('PREFERENCE_SNAPSHOT_EXPIRED_OR_CHANGED');
        return ['snapshot'=>$c['snapshot'],'metadata'=>$m];
    }
    public function expire(string $snapshotId,Authorization $authorization): void {
        Guard::hash($snapshotId);
        $c=$this->proofs->mutation('preference-snapshot','EXPIRE',['snapshot_id'=>$snapshotId],$authorization);
        Guard::keys($c,['snapshot_id','absent','key_absent','expired_at']);
        if($c['snapshot_id']!==$snapshotId||$c['absent']!==true||$c['key_absent']!==true||!is_int($c['expired_at'])||$c['expired_at']>time())
            Guard::fail('PREFERENCE_SNAPSHOT_EXPIRY_UNCONFIRMED');
    }
    public function prepareCompaction(string $oldKey,array $anchor,array $floor,string $planHash,Authorization $authorization): array {
        $c=$this->proofs->mutation('preference-keys','PREPARE_COMPACTION',['old_key'=>$oldKey,'anchor'=>$anchor,'after_floor'=>$floor,'plan_hash'=>$planHash],$authorization);
        Guard::keys($c,['old_key','new_key','plan_hash','after_floor','earlier_snapshot_catalog_complete','earlier_snapshots_absent','earlier_snapshot_keys_absent']);
        if($c['old_key']!==$oldKey||$c['plan_hash']!==$planHash||$c['after_floor']!==$floor||$c['earlier_snapshot_catalog_complete']!==true||
            $c['earlier_snapshots_absent']!==true||$c['earlier_snapshot_keys_absent']!==true||!is_string($c['new_key'])||
            preg_match('/^[A-Za-z0-9_-]{1,64}$/D',$c['new_key'])!==1||$c['new_key']===$oldKey||$this->keys->activeId()!==$c['new_key'])
            Guard::fail('PREFERENCE_COMPACTION_KEY_CUSTODY_HELD');
        return['old_key'=>$oldKey,'new_key'=>$c['new_key'],'plan_hash'=>$planHash,'after_floor'=>$floor];
    }
    public function finishCompaction(array $transition,array $anchor,string $operation,Authorization $authorization): void {
        Guard::keys($transition,['old_key','new_key','plan_hash','after_floor']);
        $c=$this->proofs->mutation('preference-keys','FINISH_COMPACTION',['transition'=>$transition,'anchor'=>$anchor,'operation'=>$operation],$authorization);
        Guard::keys($c,['transition','anchor','operation','old_key_absent','catalog_complete']);
        if($c['transition']!==$transition||$c['anchor']!==$anchor||$c['operation']!==$operation||$c['old_key_absent']!==true||$c['catalog_complete']!==true)
            Guard::fail('PREFERENCE_COMPACTION_KEY_EXPIRY_UNCONFIRMED');
    }
}
