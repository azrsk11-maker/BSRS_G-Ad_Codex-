<?php
declare(strict_types=1);
namespace BSRE\ActualRetention\PreferenceV1;
require_once __DIR__.'/PreferenceCustody.php';
require_once __DIR__.'/PreferenceAlgebra.php';

/** Sole SQL transaction owner. Consent writes, encrypted ledger and audit commit together. */
final class AtomicStore {
    private string $table;private string $audit;private string $lock;
    private bool $leased=false;private bool $transaction=false;private bool $uncertain=false;
    private bool $targetsVerified=false;private ?int $coverageDeadline=null;
    private ?int $planDeadline=null;private ?Authorization $authorization=null;
    private array $referenceCatalogs=[];
    private ?array $lastLedger=null;
    public function __construct(private \BSRE\ClosedRetention\LeaseBoundWpdb $db,private Policy $policy,
        private \BSRE\ActualRetention\CanonicalCaptureProducer $producer,private Custody $custody,private Proofs $proofs) {
        $this->table=$policy->base->prefix.'bsre_pref_runtime';$this->audit=$policy->base->prefix.'bsre_pref_audit';
        $this->lock='bsre-g5-'.substr($policy->base->scope(),0,48);
        if(strlen($this->table)>64||strlen($this->audit)>64)Guard::fail('PREFERENCE_TABLE_BINDING_INVALID');
    }
    private function guard(bool $reconcile=false): void {
        Guard::enabled();$this->policy->actor();
        if($this->uncertain&&!$reconcile)Guard::fail('PREFERENCE_QUARANTINED');
        if($this->db->prefix!==$this->policy->base->prefix)Guard::fail('PREFERENCE_PREFIX_CHANGED');
        $this->producer->assertCurrent($this->db);
    }
    private function query(string $sql): int {
        $this->guard(true);
        if(preg_match('/^(?:CREATE|DELETE|INSERT|UPDATE|COMMIT)\b/i',ltrim($sql))===1){
            if($this->authorization===null)Guard::fail('PREFERENCE_MUTATION_AUTHORIZATION_REQUIRED');
            $this->authorization->assertCurrent();
        }
        if($this->planDeadline!==null&&preg_match('/^(?:DELETE|INSERT|UPDATE|COMMIT)\b/i',ltrim($sql))===1&&time()>=$this->planDeadline)Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
        if($this->coverageDeadline!==null&&preg_match('/^(?:DELETE|INSERT|UPDATE|COMMIT)\b/i',ltrim($sql))===1&&time()>=$this->coverageDeadline)Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
        $this->db->last_error='';$r=$this->db->query($sql);
        if($r===false||$this->db->last_error!=='')Guard::fail('PREFERENCE_SQL_UNAVAILABLE');return(int)$r;
    }
    private function scalar(string $sql): string {
        $this->guard(true);$this->db->last_error='';$r=$this->db->get_var($sql);
        if($this->db->last_error!==''||(!is_string($r)&&!is_int($r)))Guard::fail('PREFERENCE_SQL_UNAVAILABLE');return(string)$r;
    }
    private function rows(string $sql,int $limit): array {
        $this->guard(true);$this->db->last_error='';$r=$this->db->get_results($sql,ARRAY_A);
        if($this->db->last_error!==''||!is_array($r)||count($r)>$limit)Guard::fail('PREFERENCE_SQL_UNAVAILABLE');return$r;
    }
    public function session(callable $operation,bool $reconcile=false): mixed {
        $this->guard($reconcile);
        if($this->leased||$this->db->custodyIsActive())Guard::fail('PREFERENCE_CUSTODY_BUSY');
        if($this->scalar('SELECT @@session.in_transaction')!=='0'||$this->scalar('SELECT @@session.tx_isolation')!=='REPEATABLE-READ')Guard::fail('PREFERENCE_TRANSACTION_CONTEXT_REQUIRED');
        $held=false;$this->db->beginCustody();
        try {
            // Exact lock required by the immutable canonical producer; shared with G5 closure operations.
            // assertCurrent requires the named lock once custody is active: acquire it
            // through the original reconnect-denying connection before rechecking producer.
            $this->db->last_error='';
            if((string)$this->db->get_var($this->db->prepare('SELECT GET_LOCK(%s,0)',$this->lock))!=='1'||$this->db->last_error!=='')Guard::fail('PREFERENCE_CUSTODY_BUSY');
            $held=true;$this->leased=true;$this->lease();
            return$operation();
        } finally {
            $released=!$held;
            try {
                if($this->transaction)$released=false;
                elseif($held){
                    // Cleanup is bound to the original reconnect-denying connection.
                    // Owner/source revocation is not permission to keep a healthy lease.
                    $this->db->last_error='';
                    $raw=$this->db->get_row($this->db->prepare('SELECT CONNECTION_ID() AS connection_id,@@session.in_transaction AS in_transaction,IS_USED_LOCK(%s) AS lock_owner',$this->lock),ARRAY_A);
                    $id=$this->db->custodyConnectionId();
                    if($this->db->last_error===''&&is_array($raw)&&$id!==null&&(string)$raw['connection_id']===$id&&
                        (string)$raw['in_transaction']==='0'&&(string)$raw['lock_owner']===$id){
                        $this->db->last_error='';
                        $released=(string)$this->db->get_var($this->db->prepare('SELECT RELEASE_LOCK(%s)',$this->lock))==='1'&&$this->db->last_error==='';
                    }
                }
            }catch(\Throwable $ignored){$released=false;}
            $this->leased=false;
            if($released)$this->db->endCustody();
            else{$this->uncertain=true;Guard::fail('PREFERENCE_CONNECTION_QUARANTINED');}
        }
    }
    private function lease(): void {
        $this->guard(true);$id=$this->db->custodyConnectionId();
        if(!$this->leased||!$this->db->custodyIsActive()||$id===null||$this->scalar('SELECT CONNECTION_ID()')!==$id||
            $this->scalar($this->db->prepare('SELECT IS_USED_LOCK(%s)',$this->lock))!==$id)Guard::fail('PREFERENCE_CUSTODY_LOST');
    }
    /** Explicit owner-approved initializer only; never invoked by reads/plugin load. */
    public function initialize(Authorization $authorization): void {
        $this->authorization=$authorization;try{$authorization->assertCurrent();
        if($authorization->action!=='INITIALIZE'||$authorization->digest!==Guard::digest(['initialize'=>$this->policy->scope()]))Guard::fail('PREFERENCE_MUTATION_AUTHORIZATION_MISMATCH');$this->lease();
        if($this->custody->current()!==Custody::zero())Guard::fail('PREFERENCE_INITIALIZATION_NOT_FRESH');
        $this->query("CREATE TABLE IF NOT EXISTS {$this->table} (id char(2) NOT NULL PRIMARY KEY, operation_revision bigint unsigned NOT NULL, body_hash char(64) NOT NULL, body mediumtext NOT NULL, status varchar(24) NOT NULL, operation_id char(64) NOT NULL, before_anchor mediumtext NOT NULL, after_anchor mediumtext NOT NULL) ENGINE=InnoDB");
        $this->query("CREATE TABLE IF NOT EXISTS {$this->audit} (operation_id char(64) NOT NULL PRIMARY KEY, action varchar(24) NOT NULL, plan_hash char(64) NOT NULL, actor bigint unsigned NOT NULL, applied_at bigint unsigned NOT NULL, affected_rows int unsigned NOT NULL, confirmed tinyint unsigned NOT NULL) ENGINE=InnoDB");
        $this->schema();
        if($this->raw(false)!==null)Guard::fail('PREFERENCE_ALREADY_INITIALIZED');
        $this->commit('INITIALIZE',Guard::digest(['initialize'=>$this->policy->scope()]),Custody::zero(),Algebra::empty(),0,true);
        }finally{$this->authorization=null;}
    }
    private function schema(): void {
        $this->lease();
        $this->metadataVisibility([$this->table,$this->audit]);
        $schemas=[$this->table=>['id'=>'char(2)','operation_revision'=>'bigint unsigned','body_hash'=>'char(64)','body'=>'mediumtext','status'=>'varchar(24)','operation_id'=>'char(64)','before_anchor'=>'mediumtext','after_anchor'=>'mediumtext'],
            $this->audit=>['operation_id'=>'char(64)','action'=>'varchar(24)','plan_hash'=>'char(64)','actor'=>'bigint unsigned','applied_at'=>'bigint unsigned','affected_rows'=>'int unsigned','confirmed'=>'tinyint unsigned']];
        foreach($schemas as $table=>$fields){
            $status=$this->rows($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$table),1);
            if(count($status)!==1||strtolower((string)($status[0]['Engine']??''))!=='innodb')Guard::fail('PREFERENCE_SCHEMA_UNVERIFIED');
            $columns=$this->rows("SHOW FULL COLUMNS FROM {$table}",count($fields));
            if(count($columns)!==count($fields))Guard::fail('PREFERENCE_SCHEMA_UNVERIFIED');
            foreach($columns as $i=>$c){
                $name=array_keys($fields)[$i];$type=preg_replace('/^(tinyint|bigint|int)\([0-9]+\)/','$1',strtolower((string)($c['Type']??'')));
                if(($c['Field']??null)!==$name||$type!==$fields[$name]||($c['Null']??null)!=='NO'||($c['Extra']??null)!=='')Guard::fail('PREFERENCE_SCHEMA_UNVERIFIED');
            }
            $indexes=$this->rows("SHOW INDEX FROM {$table}",1);$pk=$table===$this->table?'id':'operation_id';
            if(count($indexes)!==1||($indexes[0]['Key_name']??null)!=='PRIMARY'||($indexes[0]['Column_name']??null)!==$pk||
                (string)($indexes[0]['Non_unique']??'')!=='0'||(string)($indexes[0]['Seq_in_index']??'')!=='1'||
                ($indexes[0]['Sub_part']??null)!==null||strtoupper((string)($indexes[0]['Index_type']??''))!=='BTREE')Guard::fail('PREFERENCE_SCHEMA_UNVERIFIED');
            if($this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE=%s',$table))!=='0'||
                $this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL AND ((TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s) OR (REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME=%s))',$table,$table))!=='0')Guard::fail('PREFERENCE_SCHEMA_UNVERIFIED');
        }
    }
    private function metadataVisibility(array $tables): void {
        $global=$this->scalar("SELECT COUNT(DISTINCT PRIVILEGE_TYPE) FROM information_schema.USER_PRIVILEGES WHERE GRANTEE=CONCAT(QUOTE(SUBSTRING_INDEX(CURRENT_USER(),'@',1)),'@',QUOTE(SUBSTRING_INDEX(CURRENT_USER(),'@',-1))) AND PRIVILEGE_TYPE IN ('SELECT','TRIGGER')");
        if($global==='2')return;
        // A DB/table-scoped WP account must not be asked for global grants.
        // In layouts unable to expose all cross-schema incoming constraints,
        // a separately keyed complete observer is required; absence holds.
        $identity=$this->rows('SELECT @@server_id AS server_id,@@hostname AS hostname,@@port AS port,DATABASE() AS database_name',1);
        if(count($identity)!==1)Guard::fail('PREFERENCE_METADATA_VISIBILITY_UNSUPPORTED_GRANT_LAYOUT');
        sort($tables,SORT_STRING);
        $request=['server_hash'=>Guard::digest($identity[0]),'database'=>$this->policy->base->database,'connection_id'=>$this->db->custodyConnectionId(),'transaction_active'=>$this->transaction,'tables'=>$tables];
        $c=$this->proofs->request('preference-metadata','COMPLETE_CONSTRAINT_VISIBILITY',$request);
        Guard::keys($c,['binding','contract','all_incoming_schemas_visible','tables']);
        if($c['binding']!==$request||$c['contract']!=='mariadb-full-constraint-visibility-v1'||$c['all_incoming_schemas_visible']!==true||!is_array($c['tables']))Guard::fail('PREFERENCE_METADATA_VISIBILITY_UNSUPPORTED_GRANT_LAYOUT');
        Guard::keys($c['tables'],$tables);
        foreach($c['tables'] as $entry){
            if(!is_array($entry))Guard::fail('PREFERENCE_METADATA_VISIBILITY_UNSUPPORTED_GRANT_LAYOUT');
            Guard::keys($entry,['triggers','incoming_foreign_keys','outgoing_foreign_keys']);
            if($entry!==['triggers'=>0,'incoming_foreign_keys'=>0,'outgoing_foreign_keys'=>0])Guard::fail('PREFERENCE_SCHEMA_SIDE_EFFECT_HELD');
        }
    }
    private function consentMutationSchema(): void {
        if(!$this->transaction)Guard::fail('PREFERENCE_TRANSACTION_REQUIRED');
        $tables=[];foreach(['state','history'] as $kind)$tables[]=$this->policy->base->prefix.'bsre_consent_'.$kind;
        $this->metadataVisibility($tables);
        foreach(['state','history'] as $kind){
            $table=$this->policy->base->prefix.'bsre_consent_'.$kind;
            $status=$this->rows($this->db->prepare('SHOW TABLE STATUS WHERE Name=%s',$table),1);
            if(count($status)!==1||strtolower((string)($status[0]['Engine']??''))!=='innodb')Guard::fail('PREFERENCE_CONSENT_SCHEMA_UNVERIFIED');
            $fields=\BSRE\RetentionReview\RetentionInventory::COLUMNS[$kind];$columns=$this->rows("SHOW FULL COLUMNS FROM {$table}",count($fields));
            if(count($columns)!==count($fields))Guard::fail('PREFERENCE_CONSENT_SCHEMA_UNVERIFIED');
            foreach($columns as $i=>$c){
                $name=$fields[$i];$expected=in_array($name,['analytics','ad_measurement','personalization','uncertain'],true)?'tinyint unsigned':
                    (in_array($name,['revision','changed_at','expires_at'],true)?'bigint unsigned':(['subject_key'=>'char(64)','receipt'=>'char(32)','notice_version'=>'varchar(64)'][$name]??''));
                $type=preg_replace('/^(tinyint|bigint)\([0-9]+\)/','$1',strtolower((string)($c['Type']??'')));
                $default=in_array($name,['analytics','ad_measurement','personalization'],true)?'0':($name==='uncertain'?($kind==='state'?'1':'0'):null);
                if(($c['Field']??null)!==$name||$type!==$expected||($c['Null']??null)!=='NO'||($c['Extra']??null)!==''||
                    !array_key_exists('Default',$c)||($default===null?$c['Default']!==null:(string)$c['Default']!==$default))Guard::fail('PREFERENCE_CONSENT_SCHEMA_UNVERIFIED');
            }
            $indexes=$this->rows("SHOW INDEX FROM {$table}",$kind==='state'?1:3);$got=[];
            foreach($indexes as $index){
                if((string)($index['Non_unique']??'')!=='0'||($index['Sub_part']??null)!==null||strtoupper((string)($index['Index_type']??''))!=='BTREE')Guard::fail('PREFERENCE_CONSENT_INDEX_UNVERIFIED');
                $got[$index['Key_name']][Guard::uint($index['Seq_in_index'])]=$index['Column_name'];
            }
            foreach($got as &$parts){ksort($parts);$parts=array_values($parts);}unset($parts);ksort($got);
            $expected=$kind==='state'?['PRIMARY'=>['subject_key']]:['PRIMARY'=>['receipt'],'subject_revision'=>['subject_key','revision']];
            if($got!==$expected)Guard::fail('PREFERENCE_CONSENT_INDEX_UNVERIFIED');
            if($this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() AND EVENT_OBJECT_TABLE=%s',$table))!=='0'||
                $this->scalar($this->db->prepare('SELECT COUNT(*) FROM information_schema.KEY_COLUMN_USAGE WHERE REFERENCED_TABLE_NAME IS NOT NULL AND ((TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s) OR (REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME=%s))',$table,$table))!=='0')Guard::fail('PREFERENCE_CONSENT_SIDE_EFFECT_HELD');
        }
        $this->targetsVerified=true;
    }
    private function raw(bool $lock): ?array {
        $this->lease();$r=$this->rows($this->db->prepare("SELECT * FROM {$this->table} WHERE id=%s ORDER BY id LIMIT 2",$this->policy->partition).($lock?' FOR UPDATE':''),1);
        if($r===[])return null;$r=$r[0];
        if((string)$r['id']!==$this->policy->partition||!is_string($r['body'])||!is_string($r['body_hash'])||hash('sha256',$r['body'])!==$r['body_hash']||
            !in_array($r['status'],['READY','PENDING_ANCHOR'],true))Guard::fail('PREFERENCE_CONTROL_INVALID');
        Guard::hash($r['operation_id']);$r['operation_revision']=Guard::uint($r['operation_revision']);
        $r['before']=Guard::json($r['before_anchor']);$r['after']=Guard::json($r['after_anchor']);
        Custody::anchor($r['before']);Custody::anchor($r['after']);
        if($r['after']['operation_revision']!==$r['operation_revision']||$r['after']['state_hash']!==$r['body_hash']||
            $r['after']['operation_revision']!==$r['before']['operation_revision']+1)Guard::fail('PREFERENCE_CONTROL_INVALID');
        $state=$this->custody->open($r['body'],$r['operation_revision']);Guard::keys($state,['schema','ledger','intent']);
        if($state['schema']!==1||!is_array($state['intent']))Guard::fail('PREFERENCE_CONTROL_INVALID');
        $intent=$state['intent'];Guard::keys($intent,['operation','action','plan_hash','before','affected','actor','at','key_transition','authorized_until']);
        if($intent['operation']!==$r['operation_id']||$intent['before']!==$r['before']||!is_int($intent['actor'])||$intent['actor']<1||
            !in_array($intent['action'],Policy::ACTIONS,true)||!is_int($intent['at'])||$intent['at']<1||$intent['at']>time()||
            !is_int($intent['affected'])||$intent['affected']<0||!is_int($intent['authorized_until'])||$intent['authorized_until']<=$intent['at'])Guard::fail('PREFERENCE_INTENT_BINDING_INVALID');
        Guard::hash($intent['plan_hash']);
        $audit=$this->rows($this->db->prepare("SELECT * FROM {$this->audit} WHERE operation_id=%s",$intent['operation']),1);
        if(count($audit)!==1||$audit[0]['action']!==$intent['action']||$audit[0]['plan_hash']!==$intent['plan_hash']||
            Guard::uint($audit[0]['actor'])!==$intent['actor']||Guard::uint($audit[0]['applied_at'])!==$intent['at']||
            Guard::uint($audit[0]['affected_rows'])!==$intent['affected']||
            Guard::uint($audit[0]['confirmed'])!==($r['status']==='READY'?1:0))Guard::fail('PREFERENCE_AUDIT_BINDING_INVALID');
        $r['state']=$state;return$r;
    }
    public function current(bool $lock=false): array {
        $this->schema();$r=$this->raw($lock);
        if($r===null)Guard::fail('PREFERENCE_NOT_INITIALIZED');
        if($r['status']!=='READY')Guard::fail('PREFERENCE_PENDING_ANCHOR_RECONCILIATION_REQUIRED');
        if($this->custody->current()!==$r['after'])Guard::fail('PREFERENCE_INDEPENDENT_ANCHOR_MISMATCH');
        $state=$r['state'];
        $ledger=Algebra::validate($state['ledger']);
        if(Custody::next($r['before'],$ledger,$r['body_hash'])!==$r['after'])Guard::fail('PREFERENCE_LEDGER_ANCHOR_MISMATCH');
        $this->lastLedger=$ledger;
        return['anchor'=>$r['after'],'ledger'=>$ledger,'key_id'=>Guard::json($r['body'],1500000)['key_id']];
    }
    public function discover(string $cursor): array {
        $this->lease();if($cursor!==''&&(preg_match('/^[a-f0-9]{64}$/D',$cursor)!==1||substr($cursor,0,2)!==$this->policy->partition))Guard::fail('PREFERENCE_CURSOR_INVALID');
        $lo=$this->policy->partition.str_repeat('0',62);$hi=$this->policy->partition.str_repeat('f',62);$after=$cursor===''?'':$cursor;$p=$this->policy->base->prefix;
        $sql=$this->db->prepare("SELECT subject_key FROM {$p}bsre_consent_state WHERE subject_key BETWEEN %s AND %s AND subject_key>%s UNION SELECT subject_key FROM {$p}bsre_consent_history WHERE subject_key BETWEEN %s AND %s AND subject_key>%s ORDER BY subject_key LIMIT 33",$lo,$hi,$after,$lo,$hi,$after);
        $rows=$this->rows($sql,33);$subjects=array_column($rows,'subject_key');$more=count($subjects)>32;$subjects=array_slice($subjects,0,32);
        SnapshotFormat::subjects($subjects,$this->policy->partition,true);
        return['partition'=>$this->policy->partition,'subjects'=>$subjects,'next'=>$more?end($subjects):null,'complete'=>!$more];
    }
    public function snapshot(bool $lock,array $subjects,bool $empty=false): array {
        $this->lease();if($lock&&!$this->transaction)Guard::fail('PREFERENCE_TRANSACTION_REQUIRED');
        SnapshotFormat::subjects($subjects,$this->policy->partition,$empty);
        $snapshot=['kind'=>SnapshotFormat::KIND,'batch'=>['partition'=>$this->policy->partition,'subjects'=>$subjects,'references'=>['version'=>0,'hash'=>str_repeat('0',64)]],
            'state'=>[],'history'=>[],'captures'=>[]];$total=0;
        if($subjects===[])return$snapshot;
        $in=implode(',',array_fill(0,count($subjects),'%s'));
        // REPEATABLE READ next-key/gap locks serialize G2 choose/stage even though G2 does not take the G5 named lock.
        foreach(['state'=>'subject_key','history'=>'receipt'] as $part=>$pk){
            $table=$this->policy->base->prefix.'bsre_consent_'.$part;
            $snapshot[$part]=$this->rows($this->db->prepare("SELECT * FROM {$table} WHERE subject_key IN ({$in}) ORDER BY {$pk} LIMIT 1001",...$subjects).($lock?' FOR UPDATE':''),1000);
            $total+=count($snapshot[$part]);if($total>\BSRE\PurposeRetention\RetentionInventory::MAX_ROWS)Guard::fail('PREFERENCE_SNAPSHOT_UNBOUNDED');
        }
        $table=$this->policy->base->prefix.'bsre_consent_captures';
        $batchKey=Guard::digest($subjects);
        if($this->lastLedger===null)Guard::fail('PREFERENCE_CURRENT_LEDGER_REQUIRED');
        $retired=[];foreach($this->lastLedger['rows'] as $row)if(in_array($row['subject_key'],$subjects,true))
            $retired[]=['subject_key'=>$row['subject_key'],'receipt'=>$row['receipt'],'revision'=>$row['revision'],'row_hash'=>$row['row_hash']];
        // The initial signed catalog is fenced while this transaction holds the
        // same subject/receipt locks. A remote observer cannot see our uncommitted
        // consent changes, so post-write readback reuses that exact fenced catalog.
        $catalog=$lock&&isset($this->referenceCatalogs[$batchKey])?$this->referenceCatalogs[$batchKey]:
            $this->proofs->references($subjects,Guard::digest(['state'=>$snapshot['state'],'history'=>$snapshot['history']]),$retired,$this->lastLedger['anchor'],$this->db->custodyConnectionId(),$lock);
        if($lock)$this->referenceCatalogs[$batchKey]=$catalog;
        $direct=$this->rows($this->db->prepare("SELECT request_id FROM {$table} WHERE subject_key IN ({$in}) ORDER BY request_id LIMIT 1001",...$subjects).($lock?' FOR UPDATE':''),1000);
        foreach($direct as $r)if(!in_array($r['request_id'],$catalog['requests'],true))Guard::fail('PREFERENCE_REFERENCE_INDEX_OMISSION');
        if($catalog['requests']!==[]){
            $ids=implode(',',array_fill(0,count($catalog['requests']),'%s'));
            $snapshot['captures']=$this->rows($this->db->prepare("SELECT * FROM {$table} WHERE request_id IN ({$ids}) ORDER BY request_id LIMIT 1001",...$catalog['requests']).($lock?' FOR UPDATE':''),1000);
        }
        if(count($snapshot['captures'])!==count($catalog['requests']))Guard::fail('PREFERENCE_REFERENCE_INDEX_STALE');
        foreach($snapshot['captures'] as $capture)if(($catalog['capture_hashes'][$capture['request_id']]??null)!==Algebra::rowHash($capture))Guard::fail('PREFERENCE_REFERENCE_INDEX_STALE');
        $total+=count($snapshot['captures']);if($total>\BSRE\PurposeRetention\RetentionInventory::MAX_ROWS)Guard::fail('PREFERENCE_SUBJECT_BATCH_UNBOUNDED');
        $snapshot['batch']['references']=$catalog['head'];
        if($lock)$this->useCoverage($catalog['fenced_until']);
        // SELECT FOR UPDATE above holds the actual table MDL until this owner's
        // transaction ends. Recheck constraints only after those locks exist.
        if($lock)$this->consentMutationSchema();
        SnapshotFormat::plan($snapshot,time(),true);
        foreach($snapshot['captures'] as $capture)$this->producer->assertPurposeRecord($capture);
        return$snapshot;
    }
    private function transaction(callable $work): mixed {
        $this->lease();if($this->transaction||$this->scalar('SELECT @@session.in_transaction')!=='0')Guard::fail('PREFERENCE_NESTED_TRANSACTION_DENIED');
        $committing=false;$this->query('START TRANSACTION');$this->transaction=true;$this->targetsVerified=false;$this->referenceCatalogs=[];
        try{
            $this->raw(true);
            $this->rows("SELECT operation_id FROM {$this->audit} ORDER BY operation_id LIMIT 1 FOR UPDATE",1);
            // Control and audit MDL are now held too: pre-transaction metadata is advisory.
            $this->schema();
            $result=$work();
            if(is_array($result)&&isset($result['coverage_expires_at'])&&time()>=$result['coverage_expires_at'])Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
            // Run semantic/deadline checks before marking a COMMIT as dispatched.
            $this->guard(true);
            if($this->planDeadline!==null&&time()>=$this->planDeadline)Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
            if($this->coverageDeadline!==null&&time()>=$this->coverageDeadline)Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
            if($this->authorization===null)Guard::fail('PREFERENCE_MUTATION_AUTHORIZATION_REQUIRED');
            $this->authorization->assertCurrent();$committing=true;$this->db->last_error='';$commit=$this->db->query('COMMIT');
            if($commit===false||$this->db->last_error!=='')Guard::fail('PREFERENCE_COMMIT_UNCONFIRMED');
            $this->transaction=false;
            if($this->scalar('SELECT @@session.in_transaction')!=='0')Guard::fail('PREFERENCE_COMMIT_UNCONFIRMED');
            $this->coverageDeadline=null;$this->referenceCatalogs=[];return$result;
        }catch(\Throwable $error){
            $ok=false;
            try{$this->db->last_error='';$ok=$this->db->query('ROLLBACK')!==false&&$this->db->last_error===''&&(string)$this->db->get_var('SELECT @@session.in_transaction')==='0';}catch(\Throwable $ignored){}
            if($ok)$this->transaction=false;$this->coverageDeadline=null;$this->referenceCatalogs=[];
            if(!$ok||$committing){$this->uncertain=true;Guard::fail('PREFERENCE_COMMIT_OR_ROLLBACK_UNCERTAIN');}
            throw$error;
        }
    }
    /** Callback executes under checkpoint then all consent locks; it must return the new ledger/count. */
    public function mutate(string $action,array $plan,Authorization $authorization,callable $work): array {
        if(!is_int($plan['expires_at']??null)||time()>=$plan['expires_at'])Guard::fail('PREFERENCE_ORIGINAL_PLAN_EXPIRED');
        $this->planDeadline=$plan['expires_at'];$this->authorization=$authorization;
        try{if($authorization->action!==$action||$authorization->digest!==Guard::digest($plan)||$authorization->expiresAt!==$this->planDeadline)Guard::fail('PREFERENCE_MUTATION_AUTHORIZATION_MISMATCH');
        $this->guard();$this->schema();
        $pending=$this->transaction(function()use($action,$plan,$work){
            $current=$this->current(true);$snapshot=$this->snapshot(true,$plan['subjects'],$action==='COMPACT');
            if($current['anchor']!==$plan['anchor']||Guard::digest($snapshot)!==$plan['snapshot_hash'])Guard::fail('PREFERENCE_PLAN_STALE');
            $this->authorization->assertCurrent();$result=$work($current['ledger'],$snapshot);
            if(!is_array($result)||!isset($result['ledger'],$result['affected'],$result['coverage_expires_at'])||time()>=$result['coverage_expires_at'])Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
            return$this->writePending($action,Guard::digest($plan),$current['anchor'],$result['ledger'],$result['affected'],false,$result['key_transition']??null)+['coverage_expires_at'=>$result['coverage_expires_at']];
        });
        return$this->confirm($pending);}finally{$this->planDeadline=null;$this->authorization=null;}
    }
    private function commit(string $action,string $digest,array $before,array $ledger,int $affected,bool $initial): array {
        $pending=$this->transaction(fn()=>$this->writePending($action,$digest,$before,$ledger,$affected,$initial));
        return$this->confirm($pending);
    }
    private function writePending(string $action,string $digest,array $before,array $ledger,int $affected,bool $initial,?array $keyTransition=null): array {
        $this->lease();if(!$this->transaction)Guard::fail('PREFERENCE_TRANSACTION_REQUIRED');
        Guard::hash($digest);$ledger=Algebra::validate($ledger);
        $op=bin2hex(random_bytes(32));$at=time();$revision=$before['operation_revision']+1;
        $intent=['operation'=>$op,'action'=>$action,'plan_hash'=>$digest,'before'=>$before,'affected'=>$affected,'actor'=>$this->policy->base->ownerId,'at'=>$at,'key_transition'=>$keyTransition,'authorized_until'=>$this->planDeadline??$at+30];
        $body=$this->custody->seal(['schema'=>1,'ledger'=>$ledger,'intent'=>$intent],$revision);$bodyHash=hash('sha256',$body);
        $after=Custody::next($before,$ledger,$bodyHash);
        $b=json_encode($before,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);$a=json_encode($after,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES);
        $sql=$initial?$this->db->prepare("INSERT INTO {$this->table} VALUES (%s,%d,%s,%s,'PENDING_ANCHOR',%s,%s,%s)",$this->policy->partition,$revision,$bodyHash,$body,$op,$b,$a):
            $this->db->prepare("UPDATE {$this->table} SET operation_revision=%d,body_hash=%s,body=%s,status='PENDING_ANCHOR',operation_id=%s,before_anchor=%s,after_anchor=%s WHERE id=%s AND operation_revision=%d AND status='READY' AND BINARY body_hash=BINARY %s",$revision,$bodyHash,$body,$op,$b,$a,$this->policy->partition,$before['operation_revision'],$before['state_hash']);
        if($this->query($sql)!==1)Guard::fail('PREFERENCE_CHECKPOINT_CAS_CONFLICT');
        if($this->query($this->db->prepare("INSERT INTO {$this->audit} VALUES (%s,%s,%s,%d,%d,%d,0)",$op,$action,$digest,$this->policy->base->ownerId,$at,$affected))!==1)Guard::fail('PREFERENCE_AUDIT_WRITE_CONFLICT');
        return['operation'=>$op,'before'=>$before,'after'=>$after,'body'=>$body,'affected'=>$affected];
    }
    private function confirm(array $pending): array {
        try{
            $stored=$this->raw(false);
            if($stored===null||$stored['status']!=='PENDING_ANCHOR'||$stored['operation_id']!==$pending['operation']||
                $stored['after']!==$pending['after']||$stored['body']!==$pending['body'])Guard::fail('PREFERENCE_DURABLE_INTENT_UNCONFIRMED');
            $this->custody->advance($pending['before'],$pending['after'],$pending['operation'],$this->authorization);
            if($stored['state']['intent']['key_transition']!==null)$this->custody->finishCompaction($stored['state']['intent']['key_transition'],$stored['after'],$stored['operation_id'],$this->authorization);
            return$this->finalize($stored);
        }catch(\Throwable $error){$this->uncertain=true;Guard::fail('PREFERENCE_DURABLE_INTENT_RECONCILIATION_REQUIRED');}
    }
    private function finalize(array $stored): array {
        $this->transaction(function()use($stored){
            $now=$this->raw(true);
            if($now===null||$now['operation_id']!==$stored['operation_id']||$now['after']!==$stored['after']||
                $this->custody->current()!==$stored['after'])Guard::fail('PREFERENCE_RECONCILIATION_CONFLICT');
            if($now['status']==='PENDING_ANCHOR'){
                if($this->query($this->db->prepare("UPDATE {$this->table} SET status='READY' WHERE id=%s AND operation_id=%s AND status='PENDING_ANCHOR'",$this->policy->partition,$stored['operation_id']))!==1||
                    $this->query($this->db->prepare("UPDATE {$this->audit} SET confirmed=1 WHERE operation_id=%s AND confirmed=0",$stored['operation_id']))!==1)Guard::fail('PREFERENCE_CONFIRMATION_CONFLICT');
            }
        });
        $this->uncertain=false;$current=$this->current(false);
        return['operation'=>$stored['operation_id'],'anchor'=>$current['anchor'],'status'=>'COMMITTED_AND_ANCHORED'];
    }
    public function reconcile(string $operation,Authorization $authorization): array {
        $this->authorization=$authorization;try{$authorization->assertCurrent();
        if($authorization->action!=='RECONCILE'||$authorization->digest!==Guard::digest(['reconcile'=>$operation,'scope'=>$this->policy->scope()]))Guard::fail('PREFERENCE_MUTATION_AUTHORIZATION_MISMATCH');
        $this->lease();Guard::hash($operation);$this->schema();$stored=$this->raw(false);
        if($stored===null||$stored['operation_id']!==$operation)Guard::fail('PREFERENCE_EXACT_PENDING_INTENT_REQUIRED');
        $actual=$this->custody->current();
        if($actual===$stored['before'])$this->custody->advance($stored['before'],$stored['after'],$operation,$authorization);
        elseif($actual!==$stored['after'])Guard::fail('PREFERENCE_RECONCILIATION_CONFLICT');
        if($stored['state']['intent']['key_transition']!==null)$this->custody->finishCompaction($stored['state']['intent']['key_transition'],$stored['after'], $operation,$authorization);
        return$this->finalize($stored);}finally{$this->authorization=null;}
    }
    public function deleteExact(array $snapshot,array $refs,int $expiresAt): int {
        $this->useCoverage($expiresAt);
        if(!$this->targetsVerified)Guard::fail('PREFERENCE_CONSENT_SCHEMA_LOCK_REQUIRED');$deleted=0;
        foreach($refs as $ref){
            if(time()>=$expiresAt)Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
            $parts=explode(':',$ref,2);if(count($parts)!==2||!in_array($parts[0],['bsre_consent_state','bsre_consent_history'],true))Guard::fail('PREFERENCE_ROW_SCOPE_INVALID');
            $kind=$parts[0]==='bsre_consent_state'?'state':'history';$pk=$kind==='state'?'subject_key':'receipt';$matches=array_values(array_filter($snapshot[$kind],fn($row)=>$row[$pk]===$parts[1]));
            if(count($matches)!==1)Guard::fail('PREFERENCE_EXACT_ROW_REQUIRED');
            $deleted+=$this->query($this->db->prepare("DELETE FROM {$this->policy->base->prefix}{$parts[0]} WHERE {$pk}=%s",$parts[1]));
        }
        if($deleted!==count($refs))Guard::fail('PREFERENCE_DELETE_COUNT_CONFLICT');return$deleted;
    }
    /** Preference-only merge. Never inserts, changes or deletes capture/intake/outbox/receiver data. */
    public function mergePreferences(array $live,array $backup,array $skip,int $expiresAt): int {
        $this->useCoverage($expiresAt);
        if(!$this->targetsVerified)Guard::fail('PREFERENCE_CONSENT_SCHEMA_LOCK_REQUIRED');$changed=0;
        $captures=[];foreach($live['captures'] as $r)$captures[$r['request_id']]=$r;
        foreach($backup['captures'] as $r)if(!isset($captures[$r['request_id']])||Algebra::rowHash($captures[$r['request_id']])!==Algebra::rowHash($r))Guard::fail('PREFERENCE_CAPTURE_RESTORE_FORBIDDEN');
        foreach(['history'=>'receipt','state'=>'subject_key'] as $kind=>$pk){
            $table=$this->policy->base->prefix.'bsre_consent_'.$kind;$current=[];$revisions=[];
            foreach($live[$kind] as $row){$current[$row[$pk]]=$row;if($kind==='history')$revisions[$row['subject_key'].':'.$row['revision']]=$row['receipt'];}
            foreach($backup[$kind] as $row){
                if(time()>=$expiresAt)Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
                if(in_array('bsre_consent_'.$kind.':'.$row[$pk],$skip,true))continue;
                $old=$current[$row[$pk]]??null;
                if($old!==null){
                    if(Algebra::rowHash($old)===Algebra::rowHash($row))continue;
                    if($kind==='state'&&Guard::uint($old['revision'])>Guard::uint($row['revision']))continue;
                    // A newly chosen receipt may reuse a retired revision number. Never replace it.
                    if($kind==='history'||Guard::uint($old['revision'])>=Guard::uint($row['revision']))Guard::fail('PREFERENCE_RESTORE_IDENTITY_CONFLICT');
                }
                if($kind==='history'&&isset($revisions[$row['subject_key'].':'.$row['revision']]))Guard::fail('PREFERENCE_RESTORE_REVISION_CONFLICT');
                $columns=\BSRE\RetentionReview\RetentionInventory::COLUMNS[$kind];Guard::keys($row,$columns);
                if($old===null){
                    $fields=implode(',',$columns);$placeholders=implode(',',array_fill(0,count($columns),'%s'));
                    $n=$this->query($this->db->prepare("INSERT INTO {$table} ({$fields}) VALUES ({$placeholders})",...array_map(fn($f)=>$row[$f],$columns)));
                }else{
                    $set=implode(',',array_map(fn($f)=>$f.'=%s',$columns));
                    $n=$this->query($this->db->prepare("UPDATE {$table} SET {$set} WHERE subject_key=%s AND receipt=%s AND revision=%d",...array_merge(array_map(fn($f)=>$row[$f],$columns),[$old['subject_key'],$old['receipt'],Guard::uint($old['revision'])])));
                }
                if($n!==1)Guard::fail('PREFERENCE_RESTORE_WRITE_CONFLICT');$changed++;
            }
        }
        return$changed;
    }
    public function useCoverage(int $expiresAt): void {
        if(!$this->transaction||$expiresAt<=time()||$expiresAt>time()+30)Guard::fail('PREFERENCE_COVERAGE_EXPIRED');
        $this->coverageDeadline=$this->coverageDeadline===null?$expiresAt:min($expiresAt,$this->coverageDeadline);
    }
}
