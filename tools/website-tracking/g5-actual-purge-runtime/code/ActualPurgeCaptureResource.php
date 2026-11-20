<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
use BSRE\ClosedRetention\Workflow;
use BSRE\ClosedRetention\Failure;
require_once __DIR__ . '/ActualPurgeJournal.php';
require_once __DIR__ . '/CaptureRules.php';

/** Separate runtime port. Original WpCaptureResource and its lab guard are unchanged.
 * No route, installation hook, scheduler, receiver transport or provider permission.
 */
final class ActualPurgeCaptureResource implements \BSRE\ClosedRetention\ResourceAdapter
{
    use CaptureRules;
    private const CONTRACT = 'bsre-wp-capture-resource-v1';
    private string $table;
    private bool $purpose = true;
    private ?string $activeRequest = null;
    private bool $mutating = false;

    public function __construct(private \BSRE\ClosedRetention\LeaseBoundWpdb $db, private ActualPurgeJournal $journal,
        private RuntimePolicy $policy, private CanonicalCaptureProducer $producer, private PurgeBoundary $boundary)
    {
        if (!$boundary->boundTo($db,$producer,$policy) || $journal->purgeBoundary()!==$boundary) RuntimePolicy::fail('ACTUAL_PURGE_CAPTURE_COMPOSITION_CONFLICT');
        $this->table=$policy->prefix.'bsre_consent_captures'; $this->guard();
    }
    public function boundTo(ActualPurgeJournal $j,PurgeBoundary $b,RuntimePolicy $p): bool { return $this->journal===$j && $this->boundary===$b && $this->policy===$p; }
    private function guard(): void
    {
        $this->policy->actor();
        if ($this->db->prefix!==$this->policy->prefix || (defined('SAVEQUERIES')&&SAVEQUERIES) || ($this->db->save_queries??false)) RuntimePolicy::fail('CAPTURE_CONNECTION_BINDING_INVALID');
        $this->db->last_error='';
        if ((string)$this->db->get_var('SELECT DATABASE()')!==$this->policy->database || $this->db->last_error!=='') RuntimePolicy::fail('G5_DATABASE_CHANGED');
        $this->producer->assertCurrent($this->db);
    }
    private function custody(): void
    {
        $this->guard();
        if ($this->activeRequest===null) RuntimePolicy::fail('CAPTURE_OPERATION_SCOPE_REQUIRED');
        $this->journal->assertProviderCustody($this->db,$this->activeRequest,$this->mutating);
        $this->boundary->check('capture_sql_boundary');
    }
    private function query(string $sql): int
    {
        $this->custody(); $this->db->last_error=''; $n=$this->db->query($sql);
        if ($n===false || $this->db->last_error!=='') RuntimePolicy::fail('CAPTURE_STORAGE_UNVERIFIED'); return (int)$n;
    }
    private function scalar(string $sql): string
    {
        $this->custody(); $this->db->last_error=''; $v=$this->db->get_var($sql);
        if ($this->db->last_error!=='' || (!is_string($v)&&!is_int($v))) RuntimePolicy::fail('CAPTURE_STORAGE_UNVERIFIED'); return (string)$v;
    }
    private function rows(string $sql): array
    {
        $this->custody(); $this->db->last_error=''; $v=$this->db->get_results($sql,ARRAY_A);
        if ($this->db->last_error!=='' || !is_array($v)) RuntimePolicy::fail('CAPTURE_STORAGE_UNVERIFIED'); return $v;
    }
    private function columns(): array { return self::SCHEMA+self::PURPOSE_SCHEMA; }
    private function transaction(string $key, callable $operation, bool $mutation=false)
    {
        $this->guard(); self::uuid($key);
        if ($this->activeRequest!==null) RuntimePolicy::fail('CAPTURE_OPERATION_BUSY');
        $this->activeRequest=$key; $this->mutating=$mutation;
        try {
            $this->custody();
            if ($this->scalar('SELECT @@session.in_transaction')!=='0') RuntimePolicy::fail('CAPTURE_TRANSACTION_ALREADY_ACTIVE');
            if (!in_array(strtoupper($this->scalar('SELECT @@session.tx_isolation')),['REPEATABLE-READ','SERIALIZABLE'],true)) RuntimePolicy::fail('CAPTURE_TRANSACTION_ISOLATION_UNVERIFIED');
            $committing=false;
            try {
                $this->query('START TRANSACTION');
                $this->rows($this->db->prepare("SELECT request_id FROM {$this->table} WHERE request_id=%s LIMIT 2 FOR UPDATE",$key));
                $this->schema(); $result=$operation(); $committing=true; $this->query('COMMIT');
                if ($this->scalar('SELECT @@session.in_transaction')!=='0') RuntimePolicy::fail('CAPTURE_COMMIT_UNCERTAIN');
                $this->custody(); return $result;
            } catch (\Throwable $error) {
                try { $this->db->last_error=''; $ok=$this->db->query('ROLLBACK')!==false && $this->db->last_error==='' && (string)$this->db->get_var('SELECT @@session.in_transaction')==='0'; }
                catch (\Throwable $ignored) { $ok=false; }
                if ($committing) RuntimePolicy::fail('CAPTURE_COMMIT_UNCERTAIN');
                if (!$ok) RuntimePolicy::fail('CAPTURE_ROLLBACK_UNCERTAIN');
                throw $error;
            }
        } finally { $this->activeRequest=null; $this->mutating=false; }
    }
    private function current(string $request): ?array
    {
        $rows=$this->rows($this->db->prepare("SELECT * FROM {$this->table} WHERE request_id=%s LIMIT 2 FOR UPDATE",$request));
        if ($rows===[]) return null;
        if (count($rows)!==1) RuntimePolicy::fail('CAPTURE_DUPLICATE_IDENTITY');
        $row=self::normalize($rows[0],true); $this->producer->assertPurposeRecord($row);
        if ($row['request_id']!==$request) RuntimePolicy::fail('CAPTURE_IDENTITY_INVALID');
        $closure=$this->journal->assertProviderCustody($this->db,$request,$this->mutating,$this->mutating?self::binding($row):null);
        if ($closure===null || $row['created_at']>strtotime($closure['accepted_at_utc'])
            || $row['lead_id']!==$closure['lead_id'] || $row['event_id']!==$closure['event_id']) RuntimePolicy::fail('CAPTURE_CLOSURE_LINKAGE_CONFLICT');
        $owners=$this->rows($this->db->prepare("SELECT request_id FROM {$this->table} WHERE BINARY request_id<>BINARY %s AND (LOWER(lead_id)=%s OR LOWER(event_id)=%s) LIMIT 1 FOR UPDATE",$request,strtolower($row['lead_id']),strtolower($row['event_id'])));
        if ($owners!==[]) RuntimePolicy::fail('CAPTURE_SHARED_RECEIPT');
        return $row;
    }
    public function inventory(string $requestId): array
    {
        return $this->transaction($requestId,function()use($requestId){$r=$this->current($requestId);return $r===null?[]:[self::binding($r)];});
    }
    public function read(string $key): ?array
    {
        return $this->transaction($key,function()use($key){$r=$this->current($key);return $r===null?null:self::binding($r);});
    }
    public function removeExact(array $binding): void
    {
        $key=$binding['key']??null; if(!is_string($key)) RuntimePolicy::fail('CAPTURE_BINDING_INVALID');
        $this->transaction($key,function()use($key,$binding){
            $r=$this->current($key); if($r===null) RuntimePolicy::fail('CAPTURE_RESOURCE_MISSING');
            if(Workflow::digest(self::binding($r))!==Workflow::digest($binding)) RuntimePolicy::fail('CAPTURE_BINDING_CHANGED');
            [$where,$values]=self::exactPredicate($r,true);
            if($this->query($this->db->prepare("DELETE FROM {$this->table} WHERE {$where}",...$values))!==1 || $this->current($key)!==null) RuntimePolicy::fail('CAPTURE_DELETE_UNCONFIRMED');
        },true);
        if($this->read($key)!==null) RuntimePolicy::fail('CAPTURE_DELETE_UNCONFIRMED');
    }
}
