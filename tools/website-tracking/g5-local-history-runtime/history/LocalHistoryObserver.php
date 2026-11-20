<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\HistoryLocalV1;
use BSRE\ActualRetention as A;
use BSRE\ActualRetention\PreferenceV1 as V;
use BSRE\ClosedRetention as C;
require_once __DIR__.'/VerifiedAdmission.php';
require_once __DIR__.'/../preference/ActualPreferenceRetention.php';

/** Purpose-specific live borrow identity. It never acquires/releases the journal lease or ends a transaction. */
final class BorrowedHistoryContext {
    private string $connection;private string $savepoint;
    public function __construct(private C\LeaseBoundWpdb $db,private A\RuntimePolicy $policy,private A\CanonicalCaptureProducer $producer,
        private int $startedAt,private int $snapshotAt,private int $startedMono) {
        $id=$db->custodyConnectionId();if($id===null)V\Guard::fail('G39_BORROWED_CUSTODY_REQUIRED');$this->connection=$id;
        $this->savepoint='g39_'.bin2hex(random_bytes(16));
        $this->facts(null);$db->last_error='';
        if($db->query('SAVEPOINT '.$this->savepoint)===false||$db->last_error!=='')V\Guard::fail('G39_SNAPSHOT_GUARD_UNAVAILABLE');
        $this->assertCurrent();
    }
    public function boundTo(C\LeaseBoundWpdb $db,A\RuntimePolicy $policy): bool {return$db===$this->db&&$policy===$this->policy;}
    public function connectionId(): string {return$this->connection;}
    public function snapshotGuardHash(): string {return hash('sha256',$this->savepoint);}
    public function elapsedMs(): int {return intdiv(hrtime(true)-$this->startedMono,1000000);}
    private function facts(?V\Policy $preference): void {
        LocalHistoryObserver::wholeObservationDeadline($this->startedAt,$this->snapshotAt,time(),$this->elapsedMs());
        if($preference!==null){if($preference->base!==$this->policy)V\Guard::fail('G39_JOURNAL_COMPOSITION_CONFLICT');$preference->actor();}else $this->policy->actor();
        $this->producer->assertCurrent($this->db);$this->sessionFacts();
    }
    private function sessionFacts(): void {
        $this->db->last_error='';
        $lock='bsre-g5-'.substr($this->policy->scope(),0,48);
        $row=$this->db->get_row($this->db->prepare('SELECT DATABASE() AS selected_database,CONNECTION_ID() AS connection_id,@@session.in_transaction AS in_transaction,@@session.tx_read_only AS tx_read_only,@@session.tx_isolation AS tx_isolation,IS_USED_LOCK(%s) AS lock_owner',$lock),ARRAY_A);
        if($this->db->last_error!==''||!is_array($row)||!$this->db->custodyIsActive()||$this->db->custodyConnectionId()!==$this->connection||
            ($row['selected_database']??null)!==$this->policy->database||(string)($row['connection_id']??'')!==$this->connection||
            (string)($row['lock_owner']??'')!==$this->connection||(string)($row['in_transaction']??'')!=='1'||
            (string)($row['tx_read_only']??'')!=='1'||($row['tx_isolation']??null)!=='REPEATABLE-READ')V\Guard::fail('G39_SNAPSHOT_REPLACED');
    }
    public function assertCurrent(?V\Policy $preference=null): void {
        $this->facts($preference);
        // RELEASE proves the existing marker survived. Recreate only after success, with no callback between commands.
        // ROLLBACK TO is intentionally absent: MariaDB can release metadata locks acquired after that marker.
        $previous=$this->db->suppress_errors(true);$ok=false;
        try{
            $this->db->last_error='';
            if($this->db->query('RELEASE SAVEPOINT '.$this->savepoint)!==false&&$this->db->last_error===''){
                $this->db->last_error='';$ok=$this->db->query('SAVEPOINT '.$this->savepoint)!==false&&$this->db->last_error==='';
            }
        }
        finally{$this->db->suppress_errors($previous);}
        if(!$ok)V\Guard::fail('G39_SNAPSHOT_REPLACED');
        $this->sessionFacts();
        LocalHistoryObserver::wholeObservationDeadline($this->startedAt,$this->snapshotAt,time(),$this->elapsedMs());
    }
}

/** Current local state only. This object cannot attest whole-business history or authorize exports. */
final class LocalHistoryObserver {
    public const SCHEMA='bsre-g39-local-history-observation-v2';
    public const UNRESOLVED=['AUTHORITATIVE_WHOLE_LEDGER_SCOPE_UNBOUND','INDEPENDENT_HISTORY_PRODUCER_NOT_ENROLLED','EXTERNAL_ANCHORS_HAVE_NO_AGGREGATE_READ_LEASE'];
    private string $ledger;
    private bool $running=false;
    public function __construct(private C\LeaseBoundWpdb $db,private A\RuntimePolicy $policy,
        private A\CanonicalCaptureProducer $producer,private A\ActualReceiverJournal|A\ActualPurgeJournal $journal,
        private string $sourceVersion,private V\SignedTransport $transport,private V\IndependentKeys $keys,
        private V\SnapshotKeys $snapshotKeys,private C\Admission $admission,string $readonlyLedgerPath,private string $expectedLedgerSha) {
        V\Guard::hash($expectedLedgerSha);V\Guard::hash($sourceVersion);
        $real=realpath($readonlyLedgerPath);
        if($real===false||$real!==$readonlyLedgerPath||is_link($readonlyLedgerPath)||!is_file($readonlyLedgerPath)||is_writable($readonlyLedgerPath))V\Guard::fail('G39_READONLY_SERVER_LEDGER_REQUIRED');
        $this->ledger=$real;
        if($journal->runtimePolicy()!==$policy)V\Guard::fail('G39_JOURNAL_COMPOSITION_CONFLICT');
        $this->guard();
    }
    private function guard(): void {
        $this->policy->actor();$this->producer->assertCurrent($this->db);
        if($this->db->prefix!==$this->policy->prefix)V\Guard::fail('G39_PREFIX_CHANGED');
    }
    private function ledgerBytes(): string {
        clearstatcache(true,$this->ledger);$before=lstat($this->ledger);
        if(!is_array($before)||is_link($this->ledger)||realpath($this->ledger)!==$this->ledger||!is_file($this->ledger)||is_writable($this->ledger)||$before['size']<2||$before['size']>2097152)V\Guard::fail('G39_READONLY_SERVER_LEDGER_REQUIRED');
        $raw=file_get_contents($this->ledger);clearstatcache(true,$this->ledger);$after=lstat($this->ledger);
        if(!is_string($raw)||!is_array($after)||strlen($raw)!==$before['size']||hash('sha256',$raw)!==$this->expectedLedgerSha)V\Guard::fail('G39_LEDGER_BYTES_CHANGED');
        foreach(['dev','ino','mode','size','mtime','ctime'] as $field)if($before[$field]!==$after[$field])V\Guard::fail('G39_LEDGER_BYTES_CHANGED');
        // Syntax only: this does not manufacture authoritative ledger provenance or a completeness claim.
        $value=json_decode($raw,true,64,JSON_THROW_ON_ERROR);if(!is_array($value)||array_is_list($value))V\Guard::fail('G39_LEDGER_OBJECT_REQUIRED');
        return $raw;
    }
    private function scalar(string $sql): string {
        $this->guard();$this->db->last_error='';$value=$this->db->get_var($sql);
        if($this->db->last_error!==''||(!is_int($value)&&!is_string($value)))V\Guard::fail('G39_SQL_UNAVAILABLE');return(string)$value;
    }
    private function statement(string $sql): void {
        if(!in_array($sql,['SET SESSION TRANSACTION READ ONLY','SET SESSION TRANSACTION READ WRITE','START TRANSACTION WITH CONSISTENT SNAPSHOT','ROLLBACK'],true))V\Guard::fail('G39_READ_ONLY_SQL_REQUIRED');
        $this->guard();$this->db->last_error='';if($this->db->query($sql)===false||$this->db->last_error!=='')V\Guard::fail('G39_SQL_UNAVAILABLE');
    }
    private function lease(string $connection): void {
        $this->guard();$lock='bsre-g5-'.substr($this->policy->scope(),0,48);
        if(!$this->db->custodyIsActive()||$this->db->custodyConnectionId()!==$connection||$this->scalar('SELECT CONNECTION_ID()')!==$connection||
            $this->scalar($this->db->prepare('SELECT IS_USED_LOCK(%s)',$lock))!==$connection||$this->scalar('SELECT @@session.in_transaction')!=='1'||
            $this->scalar('SELECT @@session.tx_read_only')!=='1'||$this->scalar('SELECT @@session.tx_isolation')!=='REPEATABLE-READ')V\Guard::fail('G39_READ_ONLY_SNAPSHOT_REQUIRED');
    }
    /** Clock predicate only; callers must already have verified the existing signed CURRENT envelope. */
    public static function retainedProofDeadline(array $proof,int $observed): int {
        $s=$proof['statement']??null;
        if(!is_array($s)||!is_int($s['issued_at']??null)||!is_int($s['expires_at']??null)||$s['issued_at']<=0||
            $s['issued_at']>$observed||$s['issued_at']<$observed-30||$s['expires_at']<=$observed||
            $s['expires_at']>$s['issued_at']+60)V\Guard::fail('G39_OBSERVATION_PROOF_STALE');
        return min($s['expires_at'],$s['issued_at']+30);
    }
    /** Bound physical snapshot age as well as fresh proof ages; a delayed read can never be relabeled current. */
    public static function wholeObservationDeadline(int $started,int $snapshot,int $observed,int $elapsedMs): int {
        if($started<=0||$snapshot<$started||$observed<$snapshot||$observed>=$started+30||$elapsedMs<0||$elapsedMs>=30000)V\Guard::fail('G39_OBSERVATION_SNAPSHOT_STALE');
        return $started+30;
    }
    public function observe(string $closureLeaseId): array {
        if($this->running)V\Guard::fail('G39_OBSERVER_REENTRY');$this->running=true;
        $startedAt=time();$startedMono=hrtime(true);
        try{$result=$this->journal->locked($closureLeaseId,function()use($startedAt,$startedMono):array{
            $this->guard();$connection=$this->db->custodyConnectionId();
            if($connection===null||$this->scalar('SELECT @@session.in_transaction')!=='0'||$this->scalar('SELECT @@session.tx_isolation')!=='REPEATABLE-READ')V\Guard::fail('G39_TRANSACTION_CONTEXT_REQUIRED');
            $originalReadOnly=$this->scalar('SELECT @@session.tx_read_only');if(!in_array($originalReadOnly,['0','1'],true))V\Guard::fail('G39_TRANSACTION_CONTEXT_REQUIRED');
            $started=false;$changedReadOnly=false;
            try{
                if($originalReadOnly==='0'){$this->statement('SET SESSION TRANSACTION READ ONLY');$changedReadOnly=true;}
                $snapshotAt=time();$this->statement('START TRANSACTION WITH CONSISTENT SNAPSHOT');$started=true;
                $context=new BorrowedHistoryContext($this->db,$this->policy,$this->producer,$startedAt,$snapshotAt,$startedMono);
                $ledger=$this->ledgerBytes();$admission=new VerifiedAdmission($this->admission);
                $context->assertCurrent();try{$firstAdmission=$admission->read(time());}finally{$context->assertCurrent();}
                $config=\BSRE\RetentionAdmission\configuration();
                $wp=$firstAdmission['wp'];unset($wp['routes_installed'],$wp['store_installed']);
                if($wp!==$config)V\Guard::fail('G39_ADMISSION_CONFIGURATION_CHANGED');
                $admissionHash=VerifiedAdmission::configurationHash($firstAdmission);
                $journal=$this->journal->localHistoryCheckpoint($this->db,$this->policy,$this->producer,$context);
                $partitions=[];$stores=[];$expires=$firstAdmission['expires_at'];$vetoes=[];
                $inventoryPolicy=new V\Policy($this->policy,$this->sourceVersion,'00');$inventoryProofs=new V\Proofs($inventoryPolicy,$this->transport,$this->keys);
                $inventoryStore=new V\AtomicStore($this->db,$inventoryPolicy,$this->producer,new V\Custody($inventoryPolicy,$inventoryProofs,$this->snapshotKeys),$inventoryProofs);
                $physical=$inventoryStore->readAllBorrowedPhysicalHistory($context);
                if($physical['base_scope']!==$this->policy->scope()||$physical['connection_id']!==$connection)V\Guard::fail('G39_PHYSICAL_SNAPSHOT_BINDING_INVALID');
                $inventory=$physical['inventory'];$inventorySet=array_fill_keys($inventory,true);
                if($journal['incomplete'])$vetoes[]='SUBMITTED_JOURNAL_INCOMPLETE';
                if($journal['admission_floor']!==null&&$journal['admission_floor']!==$admissionHash)$vetoes[]='SUBMITTED_ADMISSION_FLOOR_CONFLICT';
                for($i=0;$i<256;$i++){
                    $partition=sprintf('%02x',$i);$p=new V\Policy($this->policy,$this->sourceVersion,$partition);
                    $proofs=new V\Proofs($p,$this->transport,$this->keys);$custody=new V\Custody($p,$proofs,$this->snapshotKeys);
                    $store=new V\AtomicStore($this->db,$p,$this->producer,$custody,$proofs);
                    if(isset($inventorySet[$partition])){
                        $row=$physical['rows'][$partition];$op=$row['operation_id'];
                        if(!isset($physical['audit'][$op]))V\Guard::fail('G39_PHYSICAL_AUDIT_COVERAGE_INVALID');
                        $entry=$store->authenticateBorrowedPhysicalHistory($row,$physical['audit'][$op],$context);
                    }else $entry=['partition'=>$partition,'scope'=>$p->scope(),'observation'=>'ZERO_ANCHOR_AND_PHYSICAL_ABSENCE','anchor'=>V\Custody::zero(),'body_sha256'=>null,'floor_generation'=>0,'proofs'=>[]];
                    $partitions[]=$entry;$stores[]=$store;
                    if(($entry['observation']==='ANCHORED_LEDGER')!==isset($inventorySet[$partition]))V\Guard::fail('G39_PREFERENCE_CONTROL_INVENTORY_CHANGED');
                    if($entry['floor_generation']>0)$vetoes[]='PREFERENCE_COMPACTED_HISTORY:'.$partition;
                }
                // Both original per-scope CURRENT rounds follow the typed physical read. No batch service operation exists.
                for($round=0;$round<2;$round++)foreach($stores as $i=>$store){$proof=$store->currentBorrowedPhysicalAnchor($partitions[$i]['anchor'],$context);$partitions[$i]['proofs'][]=$proof;$expires=min($expires,$proof['statement']['expires_at']);}
                $lastJournal=$this->journal->localHistoryCheckpoint($this->db,$this->policy,$this->producer,$context);
                if($lastJournal!==$journal)V\Guard::fail('G39_SUBMITTED_JOURNAL_CHANGED');
                $context->assertCurrent();try{$lastAdmission=$admission->read(time());}finally{$context->assertCurrent();}
                if(VerifiedAdmission::configurationHash($lastAdmission)!==$admissionHash||\BSRE\RetentionAdmission\configuration()!==$config)V\Guard::fail('G39_ADMISSION_CONFIGURATION_CHANGED');
                if($this->ledgerBytes()!==$ledger)V\Guard::fail('G39_LEDGER_BYTES_CHANGED');$context->assertCurrent();
                if($inventoryStore->readAllBorrowedPhysicalHistory($context)!==$physical)V\Guard::fail('G39_PREFERENCE_CONTROL_INVENTORY_CHANGED');
                $actor=$this->policy->actor();$context->assertCurrent();
                $observed=time();$elapsedMs=$context->elapsedMs();$expires=min($expires,$lastAdmission['expires_at'],self::wholeObservationDeadline($startedAt,$snapshotAt,$observed,$elapsedMs));
                foreach($partitions as $entry)foreach($entry['proofs'] as $proof)$expires=min($expires,self::retainedProofDeadline($proof,$observed));
                if($observed>=$expires)V\Guard::fail('G39_OBSERVATION_EXPIRED');
                $result=['schema'=>self::SCHEMA,'authority'=>'LOCAL_OBSERVATION_ONLY','base_scope'=>$this->policy->scope(),'actor'=>$actor,
                    'observation_started_at'=>$startedAt,'snapshot_started_at'=>$snapshotAt,'elapsed_ms'=>$elapsedMs,'snapshot_guard_sha256'=>$context->snapshotGuardHash(),
                    'observed_at'=>$observed,'expires_at'=>$expires,'connection_id'=>$connection,'journal'=>$journal,'control_inventory'=>$inventory,'partitions'=>$partitions,
                    'inputs'=>['ledger_sha256'=>hash('sha256',$ledger),'ledger_bytes'=>strlen($ledger),'admission_sha256'=>C\Workflow::digest($lastAdmission),
                        'admission_configuration_sha256'=>$admissionHash,'admission'=>$lastAdmission],
                    'local_vetoes'=>$vetoes,'unresolved_authority'=>self::UNRESOLVED];
                $result['digest']=C\Workflow::digest($result);return$result;
            }finally{
                $clean=true;
                // Cleanup uses only the original reconnect-denying handle, even after semantic revocation.
                try{
                    $this->db->last_error='';
                    if($started&&($this->db->query('ROLLBACK')===false||$this->db->last_error!==''))$clean=false;
                    $this->db->last_error='';
                    if($changedReadOnly&&($this->db->query('SET SESSION TRANSACTION READ WRITE')===false||$this->db->last_error!==''))$clean=false;
                    $this->db->last_error='';$facts=$this->db->get_row('SELECT CONNECTION_ID() AS connection_id,@@session.in_transaction AS in_transaction,@@session.tx_read_only AS tx_read_only',ARRAY_A);
                    if($this->db->last_error!==''||!is_array($facts)||(string)($facts['connection_id']??'')!==$connection||(string)($facts['in_transaction']??'')!=='0'||(string)($facts['tx_read_only']??'')!==$originalReadOnly)$clean=false;
                }catch(\Throwable $ignored){$clean=false;}
                if(!$clean){$this->journal->quarantineLocalHistoryRead($this->db);V\Guard::fail('G39_READ_CLEANUP_UNCONFIRMED');}
            }
        });
            // The final gate is after read-transaction cleanup AND the enclosing journal's lease release.
            $completedAt=time();$elapsedMs=intdiv(hrtime(true)-$startedMono,1000000);
            $expires=min($result['expires_at'],self::wholeObservationDeadline($startedAt,$result['snapshot_started_at'],$completedAt,$elapsedMs));
            foreach($result['partitions'] as $entry)foreach($entry['proofs'] as $proof)$expires=min($expires,self::retainedProofDeadline($proof,$completedAt));
            if($completedAt>=$expires)V\Guard::fail('G39_OBSERVATION_EXPIRED');
            $result['completed_at']=$completedAt;$result['elapsed_ms']=$elapsedMs;$result['expires_at']=$expires;
            unset($result['digest']);$result['digest']=C\Workflow::digest($result);
            // Pure serialization must not extend the accepted return window either.
            self::wholeObservationDeadline($startedAt,$result['snapshot_started_at'],time(),intdiv(hrtime(true)-$startedMono,1000000));
            if(time()>=$result['expires_at'])V\Guard::fail('G39_OBSERVATION_EXPIRED');return$result;
        }finally{$this->running=false;}
    }
}
