<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\HistoryLocalV1;
use BSRE\ActualRetention as A;
use BSRE\ActualRetention\PreferenceV1 as V;
use BSRE\ClosedRetention as C;
require_once __DIR__.'/VerifiedAdmission.php';
require_once __DIR__.'/../preference/ActualPreferenceRetention.php';

/** Current local state only. This object cannot attest whole-business history or authorize exports. */
final class LocalHistoryObserver {
    public const SCHEMA='bsre-g39-local-history-observation-v1';
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
    public function observe(string $closureLeaseId): array {
        if($this->running)V\Guard::fail('G39_OBSERVER_REENTRY');$this->running=true;
        try{return $this->journal->locked($closureLeaseId,function():array{
            $this->guard();$connection=$this->db->custodyConnectionId();
            if($connection===null||$this->scalar('SELECT @@session.in_transaction')!=='0'||$this->scalar('SELECT @@session.tx_isolation')!=='REPEATABLE-READ')V\Guard::fail('G39_TRANSACTION_CONTEXT_REQUIRED');
            $originalReadOnly=$this->scalar('SELECT @@session.tx_read_only');if(!in_array($originalReadOnly,['0','1'],true))V\Guard::fail('G39_TRANSACTION_CONTEXT_REQUIRED');
            $started=false;$changedReadOnly=false;
            try{
                if($originalReadOnly==='0'){$this->statement('SET SESSION TRANSACTION READ ONLY');$changedReadOnly=true;}
                $this->statement('START TRANSACTION WITH CONSISTENT SNAPSHOT');$started=true;$this->lease($connection);
                $ledger=$this->ledgerBytes();$admission=new VerifiedAdmission($this->admission);
                $firstAdmission=$admission->read(time());$config=\BSRE\RetentionAdmission\configuration();
                $wp=$firstAdmission['wp'];unset($wp['routes_installed'],$wp['store_installed']);
                if($wp!==$config)V\Guard::fail('G39_ADMISSION_CONFIGURATION_CHANGED');
                $admissionHash=VerifiedAdmission::configurationHash($firstAdmission);
                $journal=$this->journal->localHistoryCheckpoint($this->db,$this->policy,$this->producer);
                $partitions=[];$stores=[];$expires=$firstAdmission['expires_at'];$vetoes=[];
                $inventoryPolicy=new V\Policy($this->policy,$this->sourceVersion,'00');$inventoryProofs=new V\Proofs($inventoryPolicy,$this->transport,$this->keys);
                $inventoryStore=new V\AtomicStore($this->db,$inventoryPolicy,$this->producer,new V\Custody($inventoryPolicy,$inventoryProofs,$this->snapshotKeys),$inventoryProofs);
                $inventory=$inventoryStore->observeBorrowedControlInventory();$inventorySet=array_fill_keys($inventory,true);
                if($journal['incomplete'])$vetoes[]='SUBMITTED_JOURNAL_INCOMPLETE';
                if($journal['admission_floor']!==null&&$journal['admission_floor']!==$admissionHash)$vetoes[]='SUBMITTED_ADMISSION_FLOOR_CONFLICT';
                for($i=0;$i<256;$i++){
                    $partition=sprintf('%02x',$i);$p=new V\Policy($this->policy,$this->sourceVersion,$partition);
                    $proofs=new V\Proofs($p,$this->transport,$this->keys);$custody=new V\Custody($p,$proofs,$this->snapshotKeys);
                    $store=new V\AtomicStore($this->db,$p,$this->producer,$custody,$proofs);
                    $entry=$store->observeBorrowedHistory();$partitions[]=$entry;$stores[]=$store;
                    if(($entry['observation']==='ANCHORED_LEDGER')!==isset($inventorySet[$partition]))V\Guard::fail('G39_PREFERENCE_CONTROL_INVENTORY_CHANGED');
                    $expires=min($expires,$entry['proofs'][0]['statement']['expires_at']);
                    if($entry['floor_generation']>0)$vetoes[]='PREFERENCE_COMPACTED_HISTORY:'.$partition;
                }
                foreach($stores as $i=>$store){$proof=$store->recheckBorrowedHistory($partitions[$i]['anchor']);$partitions[$i]['proofs'][]=$proof;$expires=min($expires,$proof['statement']['expires_at']);}
                $lastJournal=$this->journal->localHistoryCheckpoint($this->db,$this->policy,$this->producer);
                if($lastJournal!==$journal)V\Guard::fail('G39_SUBMITTED_JOURNAL_CHANGED');
                $lastAdmission=$admission->read(time());
                if(VerifiedAdmission::configurationHash($lastAdmission)!==$admissionHash||\BSRE\RetentionAdmission\configuration()!==$config)V\Guard::fail('G39_ADMISSION_CONFIGURATION_CHANGED');
                if($this->ledgerBytes()!==$ledger)V\Guard::fail('G39_LEDGER_BYTES_CHANGED');$this->lease($connection);
                if($inventoryStore->observeBorrowedControlInventory()!==$inventory)V\Guard::fail('G39_PREFERENCE_CONTROL_INVENTORY_CHANGED');
                $observed=time();$expires=min($expires,$lastAdmission['expires_at']);
                foreach($partitions as $entry)foreach($entry['proofs'] as $proof)$expires=min($expires,self::retainedProofDeadline($proof,$observed));
                if($observed>=$expires)V\Guard::fail('G39_OBSERVATION_EXPIRED');
                $result=['schema'=>self::SCHEMA,'authority'=>'LOCAL_OBSERVATION_ONLY','base_scope'=>$this->policy->scope(),'actor'=>$this->policy->actor(),
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
        });}finally{$this->running=false;}
    }
}
