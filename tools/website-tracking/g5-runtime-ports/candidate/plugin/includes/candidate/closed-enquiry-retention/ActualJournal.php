<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
require_once __DIR__ . '/../recovery/ActualRecoveryCustody.php';

/** Real WPDB persistence, immediate durable writes, independent anti-restore anchor.
 * One bounded encrypted document makes closure/index/history completeness indivisible.
 * SQL and independent custody are not a distributed transaction: uncertainty HOLDS.
 */
final class ActualJournal implements \BSRE\ClosedRetention\Journal, \BSRE\ClosedRetention\ClosureWriter,
    \BSRE\ClosedRetention\RetirementWriter, \BSRE\ClosedRetention\ClosureCollectorWriter
{
    use \BSRE\ClosedRetention\RetirementJournal { commitRetirement as private commitRetirementDomain; }
    use \BSRE\ClosedRetention\ClosureCollectionJournal;
    private string $table;
    private string $lock;
    private ?string $lease = null;
    private bool $uncertain = false;
    private static array $active = [];

    public function __construct(private \BSRE\ClosedRetention\LeaseBoundWpdb $db, private RuntimePolicy $policy,
        private ActualRecoveryCustody $custody, private OwnerAuthority $authority,
        private OperationalEvidence $evidence = new HeldEvidence())
    {
        $this->table = $policy->prefix . 'bsre_g5_journal';
        $this->lock = 'bsre-g5-' . substr($policy->scope(), 0, 48);
        if ($custody->scope() !== $policy->scope() || !$authority->boundTo($policy,$evidence)) RuntimePolicy::fail('G5_AUTHORITY_CUSTODY_BINDING_CONFLICT');
        $this->guard();
    }

    private function guard(): void
    {
        $this->policy->actor();
        if ($this->uncertain) RuntimePolicy::fail('G5_CUSTODY_RECONCILIATION_REQUIRED');
        if ($this->db->prefix !== $this->policy->prefix || (defined('SAVEQUERIES') && SAVEQUERIES)
            || ($this->db->save_queries ?? false)) RuntimePolicy::fail('G5_CONNECTION_BINDING_INVALID');
        $this->db->last_error = '';
        if ((string) $this->db->get_var('SELECT DATABASE()') !== $this->policy->database || $this->db->last_error !== '') RuntimePolicy::fail('G5_DATABASE_CHANGED');
    }

    /** Explicit nominated-owner operation only. Never called on public reads or plugin load. */
    public function initialize(): void
    {
        $digest = \BSRE\ClosedRetention\Workflow::digest(['scope'=>$this->policy->scope(), 'operation'=>'INITIALIZE_JOURNAL', 'schema'=>1]);
        if (!$this->authority->canApply($this->policy->actor(), $digest, time(), 'INITIALIZE_JOURNAL')) RuntimePolicy::fail('G5_EXACT_APPROVAL_REQUIRED');
        $this->locked('00000000-0000-4000-8000-000000000000', function () {
            $this->query("CREATE TABLE IF NOT EXISTS {$this->table} (id tinyint unsigned PRIMARY KEY, revision bigint unsigned NOT NULL, body_hash char(64) NOT NULL, body mediumtext NOT NULL) ENGINE=InnoDB");
            $this->schema();
            $anchor = $this->custody->current(); $row = $this->raw();
            if ($row !== null || $anchor !== ['revision'=>0, 'hash'=>str_repeat('0', 64)]) RuntimePolicy::fail('G5_JOURNAL_ALREADY_INITIALIZED_OR_RESTORED');
            $this->write(['schema_version'=>1, 'closures'=>[], 'jobs'=>[], 'incomplete'=>false, 'expired_unresolved'=>0, 'admission_floor'=>null], true);
        });
    }

    public function locked(string $closureId, callable $operation)
    {
        $this->guard(); self::uuid($closureId);
        if ($this->lease !== null || isset(self::$active[$this->lock]) || $this->db->custodyIsActive()) RuntimePolicy::fail('G5_LEASE_BUSY');
        self::$active[$this->lock] = true;
        $held = false;
        try {
            $this->db->beginCustody();
            if ($this->scalar('SELECT @@session.in_transaction') !== '0') RuntimePolicy::fail('G5_TRANSACTION_ALREADY_ACTIVE');
            if ($this->scalar($this->db->prepare('SELECT GET_LOCK(%s,0)', $this->lock)) !== '1') RuntimePolicy::fail('G5_LEASE_BUSY');
            $held = true; $this->lease = $closureId;
            $this->assertCurrentLease();
            return $operation();
        } finally {
            // Semantic holds/owner revocation cannot prevent releasing the original live
            // connection's lock. LeaseBoundWpdb still forbids reconnect on this raw path.
            $released=!$held;
            try {
                if ($held) {
                    $this->db->last_error='';
                    $released=(string)$this->db->get_var($this->db->prepare('SELECT RELEASE_LOCK(%s)',$this->lock))==='1' && $this->db->last_error==='';
                }
            } catch (\Throwable $ignored) { $released=false; }
            finally {
                $this->lease=null; unset(self::$active[$this->lock]);
                if ($released) $this->db->endCustody();
            }
            if (!$released) { $this->uncertain=true; RuntimePolicy::fail('G5_LEASE_RELEASE_UNCONFIRMED'); }
        }
    }

    private function assertCurrentLease(): void
    {
        $this->guard();
        if ($this->lease === null || !$this->db->custodyIsActive()) RuntimePolicy::fail('G5_CLOSURE_LEASE_REQUIRED');
        $id = $this->db->custodyConnectionId();
        if ($id === null || $this->scalar('SELECT CONNECTION_ID()') !== $id
            || $this->scalar($this->db->prepare('SELECT IS_USED_LOCK(%s)', $this->lock)) !== $id) RuntimePolicy::fail('G5_CONNECTION_LEASE_LOST');
    }
    private function assertClosureLease(string $id): void
    {
        $this->assertCurrentLease();
        if ($this->lease !== $id) RuntimePolicy::fail('G5_CLOSURE_SCOPE_CONFLICT');
    }

    private function query(string $sql): int
    {
        $this->guard(); $this->db->last_error = '';
        $n = $this->db->query($sql);
        if ($n === false || $this->db->last_error !== '') RuntimePolicy::fail('G5_STORAGE_UNVERIFIED');
        return (int) $n;
    }
    private function scalar(string $sql): string
    {
        $this->guard(); $this->db->last_error = ''; $v = $this->db->get_var($sql);
        if ($this->db->last_error !== '' || (!is_string($v) && !is_int($v))) RuntimePolicy::fail('G5_STORAGE_UNVERIFIED');
        return (string) $v;
    }
    private function rows(string $sql): array
    {
        $this->guard(); $this->db->last_error = ''; $v = $this->db->get_results($sql, ARRAY_A);
        if ($this->db->last_error !== '' || !is_array($v)) RuntimePolicy::fail('G5_STORAGE_UNVERIFIED');
        return $v;
    }
    private function schema(): void
    {
        $visibility = $this->scalar("SELECT COUNT(DISTINCT PRIVILEGE_TYPE) FROM information_schema.USER_PRIVILEGES WHERE GRANTEE=CONCAT(QUOTE(SUBSTRING_INDEX(CURRENT_USER(),'@',1)),'@',QUOTE(SUBSTRING_INDEX(CURRENT_USER(),'@',-1))) AND PRIVILEGE_TYPE IN ('SELECT','TRIGGER')");
        if ($visibility !== '2') RuntimePolicy::fail('G5_METADATA_VISIBILITY_UNVERIFIED');
        $s = $this->rows($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s', $this->table));
        if (count($s) !== 1 || strtolower((string) ($s[0]['Engine'] ?? '')) !== 'innodb') RuntimePolicy::fail('G5_SCHEMA_UNVERIFIED');
        $expected = ['id'=>'tinyint unsigned', 'revision'=>'bigint unsigned', 'body_hash'=>'char(64)', 'body'=>'mediumtext'];
        $columns = $this->rows("SHOW FULL COLUMNS FROM {$this->table}");
        if (count($columns) !== 4) RuntimePolicy::fail('G5_SCHEMA_UNVERIFIED');
        foreach ($columns as $i=>$c) {
            $field = array_keys($expected)[$i];
            $type = preg_replace('/^(tinyint|bigint)\([0-9]+\)/', '$1', strtolower((string) ($c['Type'] ?? '')));
            if (($c['Field'] ?? null) !== $field || $type !== $expected[$field] || ($c['Null'] ?? null) !== 'NO' || ($c['Extra'] ?? null) !== '') RuntimePolicy::fail('G5_SCHEMA_UNVERIFIED');
        }
        $indices = $this->rows("SHOW INDEX FROM {$this->table}");
        if (count($indices) !== 1 || ($indices[0]['Key_name'] ?? null) !== 'PRIMARY' || ($indices[0]['Column_name'] ?? null) !== 'id'
            || (string) ($indices[0]['Non_unique'] ?? '') !== '0' || (string) ($indices[0]['Seq_in_index'] ?? '') !== '1'
            || ($indices[0]['Sub_part'] ?? null) !== null || strtoupper((string) ($indices[0]['Index_type'] ?? '')) !== 'BTREE') RuntimePolicy::fail('G5_SCHEMA_UNVERIFIED');
        if ($this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE=%s', $this->table)) !== '0'
            || $this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL AND ((TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s) OR (REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME=%s))', $this->table, $this->table)) !== '0') RuntimePolicy::fail('G5_SCHEMA_UNVERIFIED');
    }
    private function raw(bool $lock = false): ?array
    {
        $this->assertCurrentLease();
        $rows = $this->rows("SELECT id,revision,body_hash,body FROM {$this->table} ORDER BY id LIMIT 2" . ($lock ? ' FOR UPDATE' : ''));
        if ($rows === []) return null;
        if (count($rows) !== 1 || (string) $rows[0]['id'] !== '1' || !preg_match('/^[1-9][0-9]{0,17}$/D', (string) $rows[0]['revision'])
            || !is_string($rows[0]['body_hash']) || !is_string($rows[0]['body'])
            || !hash_equals($rows[0]['body_hash'], hash('sha256', $rows[0]['body']))) RuntimePolicy::fail('G5_JOURNAL_INVALID');
        return $rows[0];
    }
    private function state(): array
    {
        $this->assertCurrentLease(); $this->schema(); $row = $this->raw();
        if ($row === null) RuntimePolicy::fail('G5_JOURNAL_MISSING');
        if ($this->custody->current() !== ['revision'=>(int) $row['revision'], 'hash'=>$row['body_hash']]) RuntimePolicy::fail('G5_CURRENT_ANCHOR_MISMATCH');
        $state = $this->custody->open($row['body'], (int) $row['revision']);
        if (array_keys($state) !== ['schema_version','closures','jobs','incomplete','expired_unresolved','admission_floor']
            || $state['schema_version'] !== 1 || !is_array($state['closures']) || !is_array($state['jobs'])
            || !is_bool($state['incomplete']) || !is_int($state['expired_unresolved']) || $state['expired_unresolved'] < 0
            || count($state['closures']) > 1000 || count($state['jobs']) > 1000) RuntimePolicy::fail('G5_JOURNAL_INVALID');
        if ($state['admission_floor'] !== null) RuntimePolicy::hash($state['admission_floor']);
        return $state;
    }
    private function write(array $state, bool $initial = false): void
    {
        $this->assertCurrentLease(); $this->schema();
        if ($this->scalar('SELECT @@session.in_transaction') !== '0') RuntimePolicy::fail('G5_TRANSACTION_ALREADY_ACTIVE');
        $started = false; $committing = false;
        try {
            $this->query('START TRANSACTION'); $started = true; $row = $this->raw(true);
            $before = $row === null ? ['revision'=>0,'hash'=>str_repeat('0',64)] : ['revision'=>(int)$row['revision'],'hash'=>$row['body_hash']];
            if (($row === null) !== $initial || $this->custody->current() !== $before) RuntimePolicy::fail('G5_CURRENT_ANCHOR_MISMATCH');
            if ($before['revision'] >= PHP_INT_MAX) RuntimePolicy::fail('G5_ANCHOR_SEQUENCE_INVALID');
            $revision = $before['revision'] + 1; $body = $this->custody->seal($state, $revision); $hash = hash('sha256', $body);
            $sql = $initial ? $this->db->prepare("INSERT INTO {$this->table} (id,revision,body_hash,body) VALUES (1,%d,%s,%s)", $revision,$hash,$body)
                : $this->db->prepare("UPDATE {$this->table} SET revision=%d,body_hash=%s,body=%s WHERE id=1 AND revision=%d AND BINARY body_hash=BINARY %s",$revision,$hash,$body,$before['revision'],$before['hash']);
            if ($this->query($sql) !== 1) RuntimePolicy::fail('G5_REVISION_CONFLICT');
            $committing = true; $this->query('COMMIT'); $started = false;
            if ($this->scalar('SELECT @@session.in_transaction') !== '0') RuntimePolicy::fail('G5_COMMIT_UNCERTAIN');
            $stored = $this->raw();
            if ($stored === null || (int)$stored['revision'] !== $revision || $stored['body_hash'] !== $hash || $stored['body'] !== $body) RuntimePolicy::fail('G5_DURABLE_READBACK_FAILED');
            $this->custody->advance($before, ['revision'=>$revision,'hash'=>$hash]);
            if ($this->state() !== $state) RuntimePolicy::fail('G5_DURABLE_READBACK_FAILED');
        } catch (\Throwable $error) {
            if ($started) {
                try { $this->db->last_error=''; $ok=$this->db->query('ROLLBACK')!==false && $this->db->last_error==='' && (string)$this->db->get_var('SELECT @@session.in_transaction')==='0'; }
                catch (\Throwable $ignored) { $ok=false; }
                if (!$ok) { $this->uncertain=true; RuntimePolicy::fail('G5_ROLLBACK_UNCERTAIN'); }
            }
            if ($committing) { $this->uncertain=true; RuntimePolicy::fail('G5_COMMIT_OR_CUSTODY_UNCERTAIN'); }
            throw $error;
        }
    }

    public function closure(string $closureId): ?array { self::uuid($closureId); return $this->state()['closures'][$closureId] ?? null; }
    public function journal(string $planId): ?array { RuntimePolicy::hash($planId); return $this->state()['jobs'][$planId] ?? null; }
    private function collectionRows(): array { return $this->state()['closures']; }
    private function unresolvedRetirementCount(): int { return $this->state()['expired_unresolved']; }
    private function createCollectedClosure(array $target): void
    {
        $id=$target['closure_id']; $this->assertClosureLease($id);
        if (!$this->authority->canApply($this->policy->actor(), \BSRE\ClosedRetention\Workflow::digest($target), time(), 'COLLECT')
            || !$this->evidence->collectionCustody($target,time())) RuntimePolicy::fail('G5_EXACT_COLLECTION_APPROVAL_REQUIRED');
        $s=$this->state(); if (isset($s['closures'][$id])) RuntimePolicy::fail('G5_CLOSURE_EXISTS');
        $s['closures'][$id]=$target; $this->write($s);
    }
    private function assertNoClosureJobs(string $id, ?string $except = null): void
    {
        foreach ($this->state()['jobs'] as $digest=>$job) {
            if (!is_array($job) || ($job['plan']['digest']??null)!==$digest || !is_string($job['plan']['closure_id']??null)) RuntimePolicy::fail('G5_JOB_REGISTRY_UNVERIFIED');
            if ($digest!==$except && $job['plan']['closure_id']===$id) RuntimePolicy::fail('CLOSURE_JOB_RECONCILIATION_REQUIRED');
        }
    }
    public function replaceClosure(array $before, array $after): void
    {
        $this->assertClosureLease($before['closure_id']); $this->assertRetirementOpen(); $this->assertNoClosureJobs($before['closure_id']);
        if (!$this->authority->canApply($this->policy->actor(), \BSRE\ClosedRetention\Workflow::digest(['before'=>$before,'after'=>$after]), time(), 'EDIT_CLOSURE')) RuntimePolicy::fail('G5_EXACT_CLOSURE_APPROVAL_REQUIRED');
        if (!$this->evidence->collectionCustody($after,time())) RuntimePolicy::fail('G5_CLOSURE_SOURCE_CUSTODY_HELD');
        $this->writeClosure($before,$after);
    }
    public function commitRetirement(array $record, array $proof, int $now): void
    {
        $this->assertClosureLease($record['plan']['closure_id']??'');
        if (!$this->authority->canApply($this->policy->actor(),$record['plan']['digest']??'', $now,'RETIRE_NO_COPY')
            || !$this->evidence->retirementCustody($record,$proof,$now)) RuntimePolicy::fail('G5_RETIREMENT_CUSTODY_HELD');
        $this->commitRetirementDomain($record,$proof,$now);
    }
    private function writeClosure(array $before, array $after): void
    {
        $id=$before['closure_id']; $this->assertClosureLease($id);
        \BSRE\ClosedRetention\Workflow::validateClosureRecord($before,time()); \BSRE\ClosedRetention\Workflow::validateClosureRecord($after,time());
        $s=$this->state();
        if (($s['closures'][$id]??null)!==$before || $after['closure_id']!==$id || $after['revision']!==$before['revision']+1) RuntimePolicy::fail('CLOSURE_REVISION_CONFLICT');
        foreach (['request_id','lead_id','event_id','accepted_at_utc','outcome_ids','mail_message_ids'] as $key) if ($after[$key]!==$before[$key]) RuntimePolicy::fail('G5_IMMUTABLE_LINKAGE_CHANGED');
        $s['closures'][$id]=$after; $this->write($s);
    }
    public function save(array &$record): void
    {
        $id=$record['plan']['closure_id']??''; $digest=$record['plan']['digest']??''; $this->assertClosureLease($id); RuntimePolicy::hash($digest);
        if (!is_int($record['revision']??null) || $record['revision']<0 || $record['revision']>=PHP_INT_MAX) RuntimePolicy::fail('G5_JOB_REVISION_INVALID');
        $unsigned=$record['plan']; unset($unsigned['digest']);
        $action=($record['contract']??null)===\BSRE\ClosedRetention\RetirementIntent::CONTRACT ? 'RETIRE_NO_COPY' : 'PURGE';
        if (\BSRE\ClosedRetention\Workflow::digest($unsigned)!==$digest || !$this->authority->canApply($this->policy->actor(),$digest,time(),$action)) RuntimePolicy::fail('G5_EXACT_JOB_APPROVAL_REQUIRED');
        if ($action==='RETIRE_NO_COPY') \BSRE\ClosedRetention\RetirementIntent::validateRecord($record,time());
        $s=$this->state(); $old=$s['jobs'][$digest]??null;
        if (($old===null && $record['revision']!==0) || ($old!==null && (($old['revision']??null)!==$record['revision'] || ($old['plan']??null)!==$record['plan']))) RuntimePolicy::fail('G5_JOB_REVISION_CONFLICT');
        if ($old!==null) foreach (['started_at','approved_at','recovery_until'] as $key) if (array_key_exists($key,$old) && ($record[$key]??null)!==$old[$key]) RuntimePolicy::fail('G5_RECOVERY_DEADLINE_CHANGED');
        $next=$record; $next['revision']++; $s['jobs'][$digest]=$next; $this->write($s);
        if ($this->journal($digest)!==$next) RuntimePolicy::fail('G5_DURABLE_READBACK_FAILED'); $record=$next;
    }
    public function markHistoryIncomplete(): void { $s=$this->state(); if (!$s['incomplete']) { $s['incomplete']=true; $this->write($s); } }
    public function historyIncomplete(): bool { return $this->state()['incomplete']; }
    public function pinAdmissionFloor(string $policyHash): void
    {
        RuntimePolicy::hash($policyHash); $s=$this->state();
        if ($s['admission_floor']!==null && $s['admission_floor']!==$policyHash) RuntimePolicy::fail('G5_ADMISSION_FLOOR_CONFLICT');
        if ($s['admission_floor']===null) { $s['admission_floor']=$policyHash; $this->write($s); }
    }
    public function admissionFloor(): ?string { return $this->state()['admission_floor']; }
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void
    {
        $this->assertClosureLease($closureId); RuntimePolicy::hash($planId); $s=$this->state(); $r=$s['jobs'][$planId]??null;
        if (!is_array($r) || ($r['plan']['closure_id']??null)!==$closureId) RuntimePolicy::fail('G5_RECOVERY_RECORD_REQUIRED');
        if (($r['contract']??null)===\BSRE\ClosedRetention\RetirementIntent::CONTRACT) {
            \BSRE\ClosedRetention\RetirementIntent::validateRecord($r,time());
            if (!$keepClosure) RuntimePolicy::fail('G5_RETIREMENT_CLOSURE_PRESERVATION_REQUIRED');
            $until=$r['recovery_until'];
        } else {
            $complete=($r['state']??null)==='COMPLETE';
            if (!$keepClosure && !$complete) RuntimePolicy::fail('G5_UNRESOLVED_CLOSURE_PRESERVATION_REQUIRED');
            $base=$complete ? ($r['completed_at']??null) : ($r['started_at']??null);
            $until=is_int($base)&&$base>0&&$base<=PHP_INT_MAX-30*86400 ? $base+30*86400 : null;
        }
        if (!is_int($until) || time()<$until || !$this->authority->canApply($this->policy->actor(),$planId,time(),'EXPIRE_PRIVATE_JOURNAL')) RuntimePolicy::fail('G5_RECOVERY_EXPIRY_HELD');
        if ($keepClosure && $s['expired_unresolved']>=PHP_INT_MAX) RuntimePolicy::fail('G5_HISTORY_FLOOR_CAPACITY_HOLD');
        unset($s['jobs'][$planId]); if ($keepClosure) $s['expired_unresolved']++; else unset($s['closures'][$closureId]);
        $s['incomplete']=true; $this->write($s);
    }

    /** Exact current lease, durable owner intent and independent receiver/custody proof. */
    public function assertProviderCustody(\BSRE\ClosedRetention\LeaseBoundWpdb $db, string $requestId, bool $mutation=false, ?array $binding=null): ?array
    {
        if ($db!==$this->db) RuntimePolicy::fail('CAPTURE_CONNECTION_CONFLICT');
        $this->assertCurrentLease(); $this->assertRetirementOpen(); $closure=$this->closure($this->lease);
        if ($closure===null) RuntimePolicy::fail('G5_COLLECTOR_CUSTODY_UNIMPLEMENTED');
        \BSRE\ClosedRetention\Workflow::validateClosureRecord($closure,time(),$mutation);
        if ($closure['request_id']!==$requestId || $closure['closure_id']!==$this->lease) RuntimePolicy::fail('CAPTURE_CLOSURE_SCOPE_CONFLICT');
        if (!$mutation) return $closure;
        if (!in_array($closure['email_status'],['SENT','RETIRED_NO_COPY'],true)) RuntimePolicy::fail('CAPTURE_CLOSURE_SCOPE_CONFLICT');
        $eligible=[];
        foreach ($this->state()['jobs'] as $record) {
            $p=$record['plan']??null;
            if (!is_array($p) || ($p['closure_id']??null)!==$this->lease || ($p['closure_hash']??null)!==\BSRE\ClosedRetention\Workflow::digest($closure)) continue;
            foreach ($p['resources']??[] as $i=>$resource) if (($resource['store']??null)==='capture' && ($resource['binding']['key']??null)===$requestId && ($record['steps'][$i]??null)==='INTENT_RECORDED') $eligible[]=['record'=>$record,'binding'=>$resource['binding'],'intent_at'=>$record['intent_at'][$i]??null];
        }
        if (count($eligible)!==1) RuntimePolicy::fail('G5_CAPTURE_CUSTODY_HELD');
        $record=$eligible[0]['record']; $now=time(); $started=$record['started_at']??null; $intent=$eligible[0]['intent_at'];
        if (!is_int($started) || !is_int($intent) || $started<1 || $intent<$started || $intent>$now || $now>=$started+30*86400
            || $started<($record['plan']['created_at']??PHP_INT_MAX) || $started>=($record['plan']['expires_at']??0)) RuntimePolicy::fail('G5_CAPTURE_RECOVERY_WINDOW_HELD');
        if (!$this->historyIncomplete() || $this->admissionFloor()!==($record['plan']['admission_hash']??null)
            || !$this->authority->canApply($this->policy->actor(),$record['plan']['digest'],time(),'PURGE')
            || !$this->evidence->captureCustody($closure,$record,$requestId,time())) RuntimePolicy::fail('G5_CAPTURE_CUSTODY_HELD');
        if ($binding!==null && \BSRE\ClosedRetention\Workflow::digest($binding)!==\BSRE\ClosedRetention\Workflow::digest($eligible[0]['binding'])) RuntimePolicy::fail('G5_CAPTURE_APPROVAL_BINDING_CHANGED');
        return $closure;
    }
    private static function uuid(string $id): void { if (!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D',$id)) RuntimePolicy::fail('G5_IDENTITY_INVALID'); }
}
