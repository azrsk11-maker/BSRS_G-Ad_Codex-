<?php
declare(strict_types=1);
use BSRE\ActualRetention as A;use BSRE\ClosedRetention as C;use BSRE\ActualRetention\ReceiverV1 as R;
/** Positive fixed synthetic native consumer. No provider/network/mail/export capability. */
if(PHP_SAPI!=='cli'||!isset($isolation,$wpdb,$custody,$policy,$producer,$proof,$port,$owner,$rp,$descriptor)
    ||in_array(false,$isolation,true)||DB_NAME!=='bsre_synthetic'||$wpdb->prefix!=='g5_receiver_synthetic_'
    ||realpath(__DIR__)!=='/opt/lab/g5-receiver-runtime/tests')throw new RuntimeException('ACTUAL_PURGE_POSITIVE_FIXED_CONTEXT_REQUIRED');
require_once '/opt/lab/g5-receiver-runtime/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualPurgeWorkflow.php';
require_once __DIR__.'/approval-identity.php';

/** Separate SQL reader sees committed state, never the writer's uncommitted transaction. */
final class PositivePurgeService implements A\PurgeServiceTransport,A\Intake26Transport,A\Outcome40Transport,A\MarketingMailReadTransport,R\ReviewTransport {
    public array $approvals=[];public array $grants=[];public array $resources=['intake'=>[],'outcome'=>[],'email'=>[]];
    public array $receipts=[];public array $fixtures=[];public array $snapshots=[];public array $anchors=[];public array $dispatch=[];
    public array $deleteCounts=['intake'=>0,'outcome'=>0,'email'=>0];public array $removeAttempts=['intake'=>0,'outcome'=>0,'email'=>0];
    public ?string $wrongRead=null;public ?string $changedAck=null;public ?string $lostAck=null;public ?string $ambiguous=null;
    public bool $falseReceipt=false;public bool $expiredGrant=false;public int $transitions=0;
    public int $inventoryDelaySeconds=0;
    private \mysqli $reader;
    private string $readerConnection;
    public function __construct(private A\RuntimePolicy $policy,private A\ActualRecoveryCustody $custody,private R\ReceiverPolicy $receiverPolicy) {
        // This independent service reader must not register a second WordPress
        // placeholder callback in the canonical writer's global query hook.
        if(DB_HOST!=='localhost:/tmp/bsre.sock'||DB_NAME!=='bsre_synthetic')throw new RuntimeException('SYNTHETIC_REVIEW_DATABASE_REQUIRED');
        try{
            $this->reader=new \mysqli('localhost',DB_USER,DB_PASSWORD,DB_NAME,0,'/tmp/bsre.sock');
            $this->readerConnection=(string)$this->reader->thread_id;
            if(!$this->reader->set_charset('utf8mb4')||!$this->reader->autocommit(true)
                ||$this->reader->query('SET SESSION TRANSACTION READ ONLY')!==true)throw new RuntimeException('SYNTHETIC_REVIEW_READER_SETUP_FAILED');
            $facts=$this->readerFacts();
            if($facts['db_name']!=='bsre_synthetic'||(string)$facts['connection_id']!==$this->readerConnection
                ||(string)$facts['autocommit']!=='1'||(string)$facts['in_transaction']!=='0'||(string)$facts['tx_read_only']!=='1')throw new RuntimeException('SYNTHETIC_REVIEW_READER_FACTS_REQUIRED');
        }catch(Throwable $error){
            if(isset($this->reader)){try{$this->reader->close();}catch(Throwable $ignored){}}
            throw new RuntimeException('SYNTHETIC_REVIEW_READER_SETUP_FAILED');
        }
        $this->snapshots[0]=['schema_version'=>1,'closures'=>[],'jobs'=>[],'incomplete'=>false,'expired_unresolved'=>0,'admission_floor'=>null];
        $this->anchors[0]=['revision'=>0,'hash'=>str_repeat('0',64)];
    }
    private function read(string $sql):array {
        if(!str_starts_with($sql,'SELECT ')||(string)$this->reader->thread_id!==$this->readerConnection)throw new RuntimeException('SYNTHETIC_REVIEW_SELECT_ONLY');
        $result=$this->reader->query($sql);
        if(!$result instanceof \mysqli_result)throw new RuntimeException('SYNTHETIC_REVIEW_READ_FAILED');
        try{$rows=$result->fetch_all(MYSQLI_ASSOC);}finally{$result->free();}
        if(count($rows)>2||(string)$this->reader->thread_id!==$this->readerConnection)throw new RuntimeException('SYNTHETIC_REVIEW_READ_BOUND_OR_CONNECTION_CHANGED');
        return $rows;
    }
    public function readerFacts():array {
        $rows=$this->read('SELECT DATABASE() AS db_name,CONNECTION_ID() AS connection_id,@@session.autocommit AS autocommit,@@session.in_transaction AS in_transaction,@@session.tx_read_only AS tx_read_only');
        if(count($rows)!==1)throw new RuntimeException('SYNTHETIC_REVIEW_READER_FACTS_REQUIRED');return $rows[0];
    }
    public function allow(string $action,string $digest):void{$this->approvals[$action.':'.$digest]=true;}
    public function approve(array $plan,string $action='PURGE'):void {
        $this->allow($action,$plan['digest']);$k=$action.':'.$plan['digest'];
        if(!isset($this->grants[$k]))$this->grants[$k]=['actor'=>$this->policy->actor(),'action'=>$action,'plan_digest'=>$plan['digest'],
            'approved_at'=>time(),'approval_expires_at'=>time()+900];
    }
    private function row():?array {
        $count=$this->read("SELECT COUNT(*) AS row_count FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='g5_receiver_synthetic_bsre_g5_journal'")[0]['row_count'];
        if((string)$count==='0')return null;
        $rows=$this->read('SELECT revision,body_hash,body FROM g5_receiver_synthetic_bsre_g5_journal ORDER BY id LIMIT 2');
        if(!is_array($rows)||count($rows)>1)throw new RuntimeException('SYNTHETIC_REVIEW_JOURNAL_SHAPE');return $rows[0]??null;
    }
    public function state():array {
        $a=$this->custody->current();$r=$this->row();
        if($r===null){if($a!==['revision'=>0,'hash'=>str_repeat('0',64)])throw new RuntimeException('SYNTHETIC_REVIEW_ANCHOR_GAP');return $this->snapshots[0];}
        if($a!==['revision'=>(int)$r['revision'],'hash'=>$r['body_hash']]||$r['body_hash']!==hash('sha256',$r['body']))throw new RuntimeException('SYNTHETIC_REVIEW_ANCHOR_GAP');
        $s=$this->custody->open($r['body'],(int)$r['revision']);$this->snapshots[(int)$r['revision']]=$s;$this->anchors[(int)$r['revision']]=$a;return $s;
    }
    private function approved(array $c):bool {
        if($c['action']==='REVIEW')return $c['grant']===null;
        $g=$c['grant'];$p=$c['plan'];if(!is_array($g)||!is_array($p))return false;
        $known=$this->grants[$c['action'].':'.$p['digest']]??null;$now=time();
        if(!\BSRE\PurgeNative\ApprovalIdentity::same($g,$known)||!($this->approvals[$c['action'].':'.$p['digest']]??false)||$g['actor']!==$this->policy->actor()
            ||$now<$g['approved_at']||$now>=$g['approval_expires_at'])return false;
        return true;
    }
    private function transition(array $c):bool {
        $t=$c['transition'];$before=$t['before'];$after=$t['after'];$row=$this->row();$anchor=$this->custody->current();
        if(!is_array($row)||$after!==['revision'=>(int)$row['revision'],'hash'=>$row['body_hash']]
            ||$row['body']!==$t['encrypted_body']||hash('sha256',$row['body'])!==$after['hash']||$after['revision']!==$before['revision']+1
            ||!isset($this->snapshots[$before['revision']])||($this->anchors[$before['revision']]??null)!==$before)return false;
        if($c['operation']==='journal_anchor_advance'?$anchor!==$before:$anchor!==$after)return false;
        $old=$this->snapshots[$before['revision']];$new=$this->custody->open($row['body'],$after['revision']);
        if(array_keys($new)!==array_keys($old)||$new['schema_version']!==1||($old['incomplete']&&!$new['incomplete']))return false;
        $plan=$c['plan'];$id=$c['closure_id'];$digest=$plan['digest']??null;
        if($c['action']==='PURGE'){
            if(($old['closures'][$id]??null)!==($new['closures'][$id]??null)||$new['closures']!==$old['closures']
                ||$new['expired_unresolved']!==$old['expired_unresolved']||!in_array($new['admission_floor'],[$old['admission_floor'],$plan['admission_hash']],true))return false;
            $oldJobs=$old['jobs'];$newJobs=$new['jobs'];$next=$newJobs[$digest]??null;$previous=$oldJobs[$digest]??null;
            unset($oldJobs[$digest],$newJobs[$digest]);if($oldJobs!==$newJobs||!is_array($next)||$next['plan']!==$plan)return false;
            if($previous!==null){if($next['revision']!==$previous['revision']+1&&$next!==$previous)return false;
                if($next['started_at']!==$previous['started_at']||($previous['completed_at']!==null&&$next['completed_at']!==$previous['completed_at']))return false;
            }elseif($next['revision']!==1||$next['started_at']<$plan['created_at']||$next['started_at']>=$plan['expires_at']
                ||$next['started_at']<$c['grant']['approved_at']||time()>=$plan['expires_at'])return false;
        }elseif($c['action']==='EXPIRE_PRIVATE_JOURNAL'){
            $job=$old['jobs'][$digest]??null;if(!is_array($job)||$job['state']!=='COMPLETE'||time()<$job['completed_at']+2592000)return false;
            $expected=$old;unset($expected['jobs'][$digest],$expected['closures'][$id]);$expected['incomplete']=true;if($new!==$expected)return false;
        }else return false;
        $this->snapshots[$after['revision']]=$new;$this->anchors[$after['revision']]=$after;$this->transitions++;return true;
    }
    private function boundary(array $c):array {
        $ok=$this->approved($c);$current=false;
        if($ok){
            if(($c['transition']??null)!==null)$current=$this->transition($c);
            else {
                $s=$this->state();$r=$c['record'];$current=$r===null||($s['jobs'][$r['plan']['digest']]??null)===$r;
                if($c['operation']==='forget_journal:readback'&&$r!==null)$current=!isset($s['jobs'][$r['plan']['digest']]);
            }
        }
        return ['request_hash'=>C\Workflow::digest($c),'owner_approval'=>$ok,'current_journal'=>$current,'current_sources'=>true,
            'mail_and_trash'=>true,'recovery_custody'=>true,'history_floor'=>true];
    }
    private function binding(string $store,array $row,array $closure):array {
        $key=$store==='intake'?$closure['request_id']:($store==='outcome'?$row['outcome_id']:$row['message_id']);
        $b=['key'=>$key,'request_id'=>$closure['request_id'],'request_ids'=>[$closure['request_id']],'lead_id'=>$closure['lead_id'],
            'event_id'=>$closure['event_id'],'fingerprint'=>$store==='intake'?$row['payload_sha256']:C\Workflow::digest($row),
            'evidence_reference'=>'SYNTHETIC_COMPLETE_'.$store.'_V1','evidence_hash'=>C\Workflow::digest(['store'=>$store,'row'=>$row])];
        if($store==='email')$b+=['mailbox'=>'marketing@blackswanrealestate.ae','message_id'=>$row['message_id'],'rfc822_message_id'=>$row['rfc822_message_id']];
        ksort($b);return $b;
    }
    public function fixture(int $suffix):array {
        $id=sprintf('10000000-0000-4000-8000-%012d',$suffix);$lead='BSRE-'.sprintf('20000000-0000-4000-8000-%012d',$suffix);
        $event='evt_'.sprintf('30000000-0000-4000-8000-%012d',$suffix);$outcome=sprintf('40000000-0000-4000-8000-%012d',$suffix);$mail='synthetic-purge-message-'.$suffix;
        $c=['schema_version'=>1,'closure_id'=>$id,'revision'=>1,'status'=>'CLOSED','request_id'=>$id,'lead_id'=>$lead,'event_id'=>$event,
            'accepted_at_utc'=>'2023-01-01T00:00:00Z','closed_at_utc'=>'2023-01-02T00:00:00Z','recorded_at_utc'=>'2023-01-03T00:00:00Z',
            'reviewer'=>$this->policy->actor(),'evidence_reference'=>'SYNTHETIC_PURGE_CLOSURE','evidence_hash'=>str_repeat('a',64),
            'outcome_ids'=>[$outcome],'mail_message_ids'=>[$mail],'email_status'=>'SENT'];
        $headers=json_decode(file_get_contents(__DIR__.'/intake26-headers.json'),true,32,JSON_THROW_ON_ERROR);
        if(count($headers)!==26||hash('sha256',json_encode($headers,JSON_UNESCAPED_SLASHES))!=='0dcac495bed4beda7a027c5d21d0d8b1caaa8a307e6eb815e3566c46f41369ca')throw new RuntimeException('SYNTHETIC_INTAKE_SCHEMA_CHANGED');
        $wire=['schema_version'=>1,'request_id'=>$id,'role'=>'tenant','contact_consent'=>true,'marketing_consent'=>false,'synthetic'=>true];
        $intake=array_fill_keys($headers,'');$intake=array_replace($intake,['request_id'=>$id,'lead_id'=>$lead,'event_id'=>$event,
            'accepted_at_utc'=>'2023-01-01T00:00:00.000Z','payload_sha256'=>C\Workflow::digest($wire),'payload_json'=>json_encode($wire,JSON_THROW_ON_ERROR),
            'email_status'=>'SENT','email_attempts'=>1,'email_sent_at_utc'=>'2023-01-01T00:00:01.000Z','role'=>'tenant','contact_consent'=>true,'marketing_consent'=>false]);
        $schema=json_decode(file_get_contents(__DIR__.'/outcome40-schema.json'),true,64,JSON_THROW_ON_ERROR);$out=array_fill_keys(array_keys($schema['properties']),null);
        if(count($out)!==40)throw new RuntimeException('SYNTHETIC_OUTCOME_SCHEMA_CHANGED');
        $out=array_replace($out,['outcome_id'=>$outcome,'lead_id'=>$lead,'canonical_lead_id'=>$lead,'person_key'=>'SYNTHETIC_PRIVATE_OPAQUE_'.$suffix,
            'person_dedup_confirmed'=>false,'role'=>'tenant','stage'=>'lead_created','occurred_at_utc'=>'2023-01-01T00:00:00Z','recorded_at_utc'=>'2023-01-01T00:00:01Z',
            'recorded_by'=>'SYNTHETIC_OWNER','qualification_status'=>'TEST','is_test'=>true,'source_evidence_reference'=>'SYNTHETIC_OUTCOME40','export_state'=>'EXCLUDED']);
        $message=['message_id'=>$mail,'rfc822_message_id'=>'<'.$mail.'@bsre.invalid>','request_id'=>$id,'lead_id'=>$lead,'event_id'=>$event,'location'=>'INBOX','content'=>'SYNTHETIC EXACT COPY'];
        foreach(['intake'=>$intake,'outcome'=>$out,'email'=>$message] as $store=>$row){$b=$this->binding($store,$row,$c);$this->resources[$store][$b['key']]=['row'=>$row,'binding'=>$b];}
        $this->fixtures[$id]=['closure'=>$c,'intake'=>$intake,'outcome'=>$out,'message'=>$message];$this->allow('COLLECT',C\Workflow::digest($c));return $this->fixtures[$id];
    }
    public function manualDelete(array $action):void {
        $s=$this->state();$p=$action['plan_digest'];$job=$s['jobs'][$p]??null;$b=$action['binding'];
        if(!is_array($job)||$job['plan']['digest']!==$p||($this->resources['email'][$b['key']]['binding']??null)!==$b)throw new RuntimeException('SYNTHETIC_MANUAL_MANIFEST_CONFLICT');
        $matches=[];foreach($job['plan']['resources'] as $i=>$r)if($r['store']==='email'&&$r['binding']===$b&&$job['steps'][$i]==='INTENT_RECORDED'&&$job['intent_at'][$i]===$action['intent_at'])$matches[]=$i;
        if(count($matches)!==1)throw new RuntimeException('SYNTHETIC_MANUAL_INTENT_REQUIRED');
        unset($this->resources['email'][$b['key']]); // Explicit simulated human action, never a transport operation.
        $this->receipts[$p]=['schema_version'=>1,'actor'=>$this->policy->actor(),'plan_digest'=>$p,'mailbox'=>'marketing@blackswanrealestate.ae',
            'message_id'=>$b['message_id'],'binding_hash'=>C\Workflow::digest($b),'observed_at'=>time(),'evidence_reference'=>'SYNTHETIC_OWNER_MANUAL_MARKETING_AND_TRASH',
            'evidence_hash'=>C\Workflow::digest(['action'=>$action,'empty_inbox_and_trash'=>true])];
    }
    private function resource(array $b):array {
        $store=$b['store'];$op=$b['operation'];$claim=$b['custody'];$checks=$this->boundary($claim);
        if(in_array(false,array_values($checks),true))throw new RuntimeException('SYNTHETIC_RESOURCE_CUSTODY_HELD');
        if($op==='inventory'){if($this->inventoryDelaySeconds>0){$delay=$this->inventoryDelaySeconds;$this->inventoryDelaySeconds=0;sleep($delay);}$rows=[];foreach($this->resources[$store] as $r)if($r['binding']['request_id']===$b['arguments']['request_id'])$rows[]=$r['binding'];$result=['bindings'=>$rows];}
        elseif($op==='read'){$r=$this->resources[$store][$b['arguments']['key']]??null;$binding=$r['binding']??null;
            if($this->wrongRead===$store&&$binding!==null){$this->wrongRead=null;$binding['fingerprint']=str_repeat('9',64);}
            $result=['state'=>$r===null?'ABSENT':'PRESENT','binding'=>$binding];
        }elseif($op==='remove_exact'){
            if($store==='email')throw new RuntimeException('SYNTHETIC_MAIL_MANUAL_ONLY');$binding=$b['arguments']['binding'];$key=$binding['key'];$job=$claim['record'];
            $matches=[];foreach($job['plan']['resources'] as $i=>$r)if($r['store']===$store&&$r['binding']===$binding&&$job['steps'][$i]==='INTENT_RECORDED')$matches[]=$i;
            if(count($matches)!==1||($this->resources[$store][$key]['binding']??null)!==$binding)throw new RuntimeException('SYNTHETIC_EXACT_PROVIDER_BINDING_CONFLICT');
            $expected=C\Workflow::digest(['plan_digest'=>$claim['plan']['digest'],'store'=>$store,'binding'=>$binding,'intent_at'=>$job['intent_at'][$matches[0]]]);
            if($b['idempotency_key']!==$expected)throw new RuntimeException('SYNTHETIC_IDEMPOTENCY_CONFLICT');
            $this->removeAttempts[$store]++;if(isset($this->dispatch[$expected]))throw new RuntimeException('SYNTHETIC_AMBIGUOUS_REDISPATCH_FORBIDDEN');$this->dispatch[$expected]='INTENT';
            if($this->ambiguous===$store){$this->ambiguous=null;throw new RuntimeException('SYNTHETIC_PROVIDER_ACK_AMBIGUOUS_BEFORE_EFFECT');}
            unset($this->resources[$store][$key]);$this->deleteCounts[$store]++;$this->dispatch[$expected]='ABSENT';
            if($this->lostAck===$store){$this->lostAck=null;throw new RuntimeException('SYNTHETIC_PROVIDER_ACK_LOST_AFTER_EFFECT');}
            $hash=C\Workflow::digest($binding);if($this->changedAck===$store){$this->changedAck=null;$hash=str_repeat('8',64);}
            $result=['confirmed_absent'=>true,'binding_hash'=>$hash];
        }else throw new RuntimeException('SYNTHETIC_RESOURCE_OPERATION_UNKNOWN');
        return ['request_hash'=>C\Workflow::digest($b),'store'=>$store,'schema'=>['intake'=>'Intake26','outcome'=>'Outcome40','email'=>'MarketingExactMessageV1'][$store],
            'schema_hash'=>['intake'=>'0dcac495bed4beda7a027c5d21d0d8b1caaa8a307e6eb815e3566c46f41369ca','outcome'=>'bf477cc0cc4a161775abd702777898c6046d5dfcf0f2ae0e86fe078a3a63d9df','email'=>null][$store],
            'complete_surface'=>true,'trash_included'=>$store==='email'?true:null,'shared_identity_absent'=>true,'metadata_bound'=>true,'wire_v1_preserved'=>true,'outbox_reconciled'=>true,'result'=>$result];
    }
    public function exchange(string $operation,array $q):string {
        if(($q['contract']??null)!=='bsre-actual-purge-request-v1')return $this->receiverReview($operation,$q);
        if($q['actor']!==$this->policy->actor()||$q['policy']!==$this->policy->scope())throw new RuntimeException('SYNTHETIC_PURGE_SCOPE_CONFLICT');
        $b=$q['body'];
        if($operation==='approval'){$r=$this->grants[$b['action'].':'.$b['plan']['digest']]??null;if($r===null)throw new RuntimeException('SYNTHETIC_PURGE_NOT_APPROVED');if($this->expiredGrant)$r['approval_expires_at']=time();}
        elseif($operation==='boundary')$r=$this->boundary($b);
        elseif($operation==='resource')$r=$this->resource($b);
        elseif($operation==='manual_mail_receipt'){$r=['receipt'=>$this->receipts[$b['plan_digest']]??null];if($this->falseReceipt&&$r['receipt']!==null)$r['receipt']['binding_hash']=str_repeat('7',64);}
        else throw new RuntimeException('SYNTHETIC_PURGE_OPERATION_UNKNOWN');
        $s=['contract'=>'bsre-actual-purge-evidence-v1','actor'=>$q['actor'],'policy'=>$q['policy'],'source_hash'=>$q['source_hash'],'operation'=>$operation,
            'challenge'=>$q['challenge'],'request_hash'=>C\Workflow::digest($q),'issued_at'=>time(),'expires_at'=>time()+30,'result'=>$r];
        return R\Guard::canonical(['key_id'=>'synthetic-rfc8032','statement'=>$s,'signature'=>base64_encode(sodium_crypto_sign_detached(C\Workflow::digest($s),receiver_test_secret()))]);
    }
    private function receiverReview(string $operation,array $q):string {
        if($q['actor']!==$this->policy->actor()||$q['source']!==$this->receiverPolicy->sources())throw new RuntimeException('SYNTHETIC_RECEIVER_REVIEW_SCOPE');
        $b=$q['scope'];$result=false;
        if($operation==='approval')$result=($this->approvals[$b['action'].':'.$b['digest']]??false)===true;
        elseif($operation==='collection_custody')$result=($this->fixtures[$b['target']['closure_id']]['closure']??null)===$b['target'];
        elseif($operation==='capture_custody'){$s=$this->state();$record=$b['record'];$p=$record['plan'];$result=($s['jobs'][$p['digest']]??null)===$record
            &&($s['closures'][$p['closure_id']]??null)===$b['closure']&&$b['request_id']===$b['closure']['request_id']
            &&$s['incomplete']===true&&$s['admission_floor']===$p['admission_hash']&&($this->approvals['PURGE:'.$p['digest']]??false)===true;}
        else throw new RuntimeException('SYNTHETIC_RECEIVER_REVIEW_OPERATION');
        $s=['contract'=>R\ReceiverPolicy::EVIDENCE,'service'=>R\ReceiverPolicy::SERVICE,'operation'=>$operation,'scope'=>C\Workflow::digest($b),
            'source'=>$this->receiverPolicy->sources(),'actor'=>$q['actor'],'challenge'=>$q['challenge'],'request_hash'=>C\Workflow::digest(['operation'=>$operation,'body'=>R\Guard::canonical($q)]),
            'issued_at'=>time(),'expires_at'=>time()+60,'claims'=>['result'=>$result,'intent_digest'=>null,'current_history'=>true,'receiver_only'=>true]];
        return R\Guard::canonical(['key_id'=>'synthetic-rfc8032','statement'=>$s,'signature'=>base64_encode(sodium_crypto_sign_detached(C\Workflow::digest($s),receiver_test_secret()))]);
    }
}

final class PositivePurgeAdmission implements C\Admission {
    public function __construct(private array $wp,private string $wpSource,private string $receiverSource,private A\CanonicalCaptureProducer $producer,private C\LeaseBoundWpdb $db){}
    public function readback(int $now):?array {
        // This authoritative assertion verifies the exact final G3 routes/common store.
        // Do not rewrite the deprecated pre-G3 readback's false routes_installed flag.
        $this->producer->assertCurrent($this->db);$wp=$this->wp+['routes_installed'=>true,'store_installed'=>true];$receiver=$this->wp;return [
        'wp'=>$wp,'receiver'=>$receiver,'source_hashes'=>['wp'=>$this->wpSource,'receiver'=>$this->receiverSource],
        'restore_policy_hash'=>hash('sha256','SYNTHETIC_PURGE_RECOVERY_POLICY_V1'),'evidence_reference'=>'SYNTHETIC_INDEPENDENT_ADMISSION',
        'evidence_hash'=>hash('sha256','SYNTHETIC_ADMISSION_EVIDENCE'),'observed_at'=>time(),'expires_at'=>time()+300];}
}
function positiveCaptureRow(array $closure):array {
    $reflection=new ReflectionClass(A\ActualPurgeCaptureResource::class);$schema=$reflection->getConstant('SCHEMA')+$reflection->getConstant('PURPOSE_SCHEMA');$row=[];
    foreach($schema as $field=>$type)$row[$field]=str_ends_with($type,' unsigned')?0:'';
    $row=array_replace($row,['request_id'=>$closure['request_id'],'fingerprint'=>hash('sha256','SYNTHETIC_CAPTURE_'.$closure['request_id']),
        'decision_version'=>str_repeat('d',32),'notice_version'=>'SYNTHETIC_NOTICE','created_at'=>strtotime($closure['accepted_at_utc'])-1,
        'state'=>'ACCEPTED','uncertain'=>1,'click_capture_state'=>'NOT_PERMITTED','lead_id'=>$closure['lead_id'],'event_id'=>$closure['event_id'],'purpose_json'=>null]);return $row;
}
function positiveCaptureSeed(array $closure):void {
    global $wpdb;$row=positiveCaptureRow($closure);
    if($wpdb->insert('g5_receiver_synthetic_bsre_consent_captures',$row)!==1)throw new RuntimeException('SYNTHETIC_POSITIVE_CAPTURE_SEED_FAILED');
}
function positiveReadJob(A\PurgeBoundary $b,A\ActualPurgeJournal $j,array $plan):?array {$b->begin($plan['closure_id'],$plan,'PURGE');try{return $j->locked($plan['closure_id'],fn()=>$j->journal($plan['digest']));}finally{$b->end();}}

define('BSRE_ACTUAL_PURGE_ENABLED',true);
$positiveService=new PositivePurgeService($policy,$custody,$rp);
$positiveReaderFacts=$positiveService->readerFacts();$positiveWriterConnection=(string)$wpdb->get_var('SELECT CONNECTION_ID()');$producer->assertCurrent($wpdb);
receiver_check('purge_fixture_reader_is_distinct_read_only_and_preserves_canonical_hooks',
    $positiveReaderFacts['db_name']===DB_NAME&&(string)$positiveReaderFacts['connection_id']!==$positiveWriterConnection
    &&(string)$positiveReaderFacts['autocommit']==='1'&&(string)$positiveReaderFacts['in_transaction']==='0'&&(string)$positiveReaderFacts['tx_read_only']==='1');
$positiveSigned=new A\SignedPurgeService($policy,$positiveService,'synthetic-rfc8032',hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a'),hash('sha256','SYNTHETIC_PURGE_SERVICE_V2'));
$positiveBoundary=new A\PurgeBoundary($policy,$wpdb,$producer,$positiveSigned);
$positiveEvidence=new R\ReceiverOperationalEvidence($rp,$proof,$positiveService);$positiveAuthority=new A\OwnerAuthority($policy,$positiveEvidence);
// Separate fixture bootstrap: unchanged original guarded journal, not a REVIEW mutation grant.
$fixtureBootstrapJournal=new A\ActualReceiverJournal($wpdb,$policy,$custody,$positiveAuthority,$positiveEvidence,$proof,$producer);
$positiveService->allow('INITIALIZE_JOURNAL',C\Workflow::digest(['scope'=>$policy->scope(),'operation'=>'INITIALIZE_JOURNAL','schema'=>1]));
$fixtureBootstrapJournal->initialize();$positiveService->state();
$positiveJournal=new A\ActualPurgeJournal($wpdb,$policy,$custody,$positiveAuthority,$positiveEvidence,$proof,$producer,$positiveBoundary);
receiver_check('purge_fixture_bootstrap_uses_unchanged_guarded_journal',get_class($fixtureBootstrapJournal)==='BSRE\\ActualRetention\\ActualReceiverJournal');
$positiveCapture=new A\ActualPurgeCaptureResource($wpdb,$positiveJournal,$policy,$producer,$positiveBoundary);
$positiveAdmission=new PositivePurgeAdmission($descriptor,hash_file('sha256','/opt/lab/g36/wp-content/plugins/bsre-enquiries/bsre-enquiries.php'),$init['source_hash'],$producer,$wpdb);
$positiveKey=hex2bin('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a');$positiveSource=hash('sha256','SYNTHETIC_PURGE_SERVICE_V2');
$positiveIntake=A\PurgeResources::intake($policy,$positiveService,'synthetic-rfc8032',$positiveKey,$positiveSource,$positiveBoundary);
$positiveOutcome=A\PurgeResources::outcome($policy,$positiveService,'synthetic-rfc8032',$positiveKey,$positiveSource,$positiveBoundary);
$positiveMail=A\PurgeResources::mail($policy,$positiveService,'synthetic-rfc8032',$positiveKey,$positiveSource,$positiveBoundary);
$positiveWorkflow=new A\ActualPurgeWorkflow($policy,$positiveJournal,$positiveBoundary,$positiveAuthority,$positiveAdmission,$port,$positiveCapture,$positiveIntake,$positiveOutcome,$positiveMail);
$fixture=$positiveService->fixture(1);$closure=$fixture['closure'];positiveCaptureSeed($closure);
$fixtureBootstrapJournal->locked($closure['closure_id'],fn()=>$fixtureBootstrapJournal->insertClosure($closure));$positiveService->state();
$positiveBoundary->begin($closure['closure_id']);try{receiver_check('purge_review_cannot_mutate_actual_journal',receiver_denied(fn()=>$positiveJournal->locked($closure['closure_id'],fn()=>$positiveJournal->markHistoryIncomplete()),'ACTUAL_PURGE_REVIEW_IS_READ_ONLY'));}finally{$positiveBoundary->end();}
$positivePlan=$positiveWorkflow->prepare($closure['closure_id']);$positiveService->approve($positivePlan);
receiver_check('purge_positive_plan_has_exact_four_surfaces',array_column($positivePlan['resources'],'store')===['email','outcome','capture','intake']&&!isset($positivePlan['no_mail_copy']));
$pending=$positiveWorkflow->execute($positivePlan);receiver_check('purge_positive_persists_manual_intent_first',$pending['status']==='AWAITING_OWNER_MAIL_ACTION');
$action=$positiveWorkflow->ownerMailAction($positivePlan);receiver_check('purge_positive_manual_manifest_exact',$action!==null&&$action['plan_digest']===$positivePlan['digest']&&$action['binding']['mailbox']==='marketing@blackswanrealestate.ae');
$positiveService->manualDelete($action);$positiveService->falseReceipt=true;$held=$positiveWorkflow->execute($positivePlan);
receiver_check('purge_false_manual_receipt_holds',$held['status']==='HELD'&&in_array('OWNER_MAIL_RECEIPT_CONFLICT',$held['hold_codes'],true)&&array_sum($positiveService->deleteCounts)===0);$positiveService->falseReceipt=false;
$positiveService->wrongRead='outcome';$held=$positiveWorkflow->execute($positivePlan);
receiver_check('purge_wrong_row_holds_before_provider_mutation',$held['status']==='HELD'&&in_array('RESOURCE_BINDING_CHANGED',$held['hold_codes'],true)&&array_sum($positiveService->deleteCounts)===0);
$positiveService->changedAck='outcome';$positiveService->lostAck='intake';$held=$positiveWorkflow->execute($positivePlan);
receiver_check('purge_changed_ack_holds_after_single_exact_mutation',$held['status']==='HELD'&&$positiveService->deleteCounts['outcome']===1&&$positiveService->removeAttempts['outcome']===1);
$held=$positiveWorkflow->execute($positivePlan);
$lostAckCheck=$held['status']==='HELD'&&$positiveService->deleteCounts['intake']===1&&$positiveService->removeAttempts['outcome']===1;
if(!$lostAckCheck){
    // Failure-only bounded aggregates; never print a plan, record, identifier or signed body.
    $codes=$held['hold_codes']??null;$codesKnown=is_array($codes)&&count($codes)<=16;
    if($codesKnown)foreach($codes as $code)if(!is_string($code)||preg_match('/^[A-Z][A-Z0-9_]{0,95}$/D',$code)!==1){$codesKnown=false;break;}
    $countsKnown=true;foreach([$positiveService->deleteCounts,$positiveService->removeAttempts] as $counts){
        if(array_keys($counts)!==['intake','outcome','email']){$countsKnown=false;break;}
        foreach($counts as $count)if(!is_int($count)||$count<0||$count>1000){$countsKnown=false;break;}
    }
    $diagnostic=['phase'=>'g5_actual_purge_diagnostic','check'=>'lost_intake_ack','status'=>in_array($held['status']??null,['HELD','COMPLETE','AWAITING_OWNER_MAIL_ACTION'],true)?$held['status']:'UNVERIFIED',
        'hold_codes_known'=>$codesKnown,'hold_codes'=>$codesKnown?array_values($codes):[],
        'counts_known'=>$countsKnown,'delete_counts'=>$countsKnown?$positiveService->deleteCounts:[],
        'remove_attempts'=>$countsKnown?$positiveService->removeAttempts:[],
        'pending_lost_intake_ack'=>$positiveService->lostAck==='intake','pending_changed_outcome_ack'=>$positiveService->changedAck==='outcome',
        'provider_accepted'=>false,'production_authorized'=>false];
    fwrite(STDERR,json_encode($diagnostic,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)."\n");fflush(STDERR);
}
receiver_check('purge_lost_intake_ack_holds_without_redeleting_outcome',$lostAckCheck);
$completionInvocation=time();$complete=$positiveWorkflow->execute($positivePlan);$done=positiveReadJob($positiveBoundary,$positiveJournal,$positivePlan);
receiver_check('purge_positive_reconciles_same_job_to_complete',$complete['status']==='COMPLETE'&&$done['state']==='COMPLETE'&&$done['plan']===$positivePlan&&$done['steps']===array_fill(0,4,'CONFIRMED_ABSENT'));
receiver_check('purge_completion_uses_current_observation_time',$done['completed_at']>=$completionInvocation&&$done['completed_at']<=time());
receiver_check('purge_positive_real_capture_and_provider_absent',$wpdb->get_var($wpdb->prepare('SELECT COUNT(*) FROM g5_receiver_synthetic_bsre_consent_captures WHERE request_id=%s',$closure['request_id']))==='0'
    &&$positiveService->deleteCounts===['intake'=>1,'outcome'=>1,'email'=>0]);
$again=$positiveWorkflow->execute($positivePlan);$againJob=positiveReadJob($positiveBoundary,$positiveJournal,$positivePlan);
receiver_check('purge_complete_retry_keeps_deadlines_and_mutation_counts',$again['status']==='COMPLETE'&&$againJob['started_at']===$done['started_at']&&$againJob['completed_at']===$done['completed_at']&&$positiveService->removeAttempts===['intake'=>1,'outcome'=>1,'email'=>0]);
$positiveService->approve($positivePlan,'EXPIRE_PRIVATE_JOURNAL');$early=$positiveWorkflow->expire($positivePlan);
receiver_check('purge_positive_current_completion_cannot_expire_early',$early['status']==='HELD'&&in_array('RECOVERY_WINDOW_ACTIVE',$early['hold_codes'],true));

// Independent second job diagnoses a write whose reply is ambiguous and row remains present.
$fixture2=$positiveService->fixture(2);$closure2=$fixture2['closure'];positiveCaptureSeed($closure2);
$fixtureBootstrapJournal->locked($closure2['closure_id'],fn()=>$fixtureBootstrapJournal->insertClosure($closure2));$positiveService->state();
$ambiguousPlan=$positiveWorkflow->prepare($closure2['closure_id']);
$latePlan=$ambiguousPlan;$latePlan['created_at']=time()-898;$latePlan['expires_at']=$latePlan['created_at']+900;unset($latePlan['digest']);$latePlan['digest']=C\Workflow::digest($latePlan);$positiveService->approve($latePlan);$positiveService->inventoryDelaySeconds=3;
$late=$positiveWorkflow->execute($latePlan);receiver_check('purge_plan_expiring_across_proposal_io_cannot_start_job',$late['status']==='HELD'&&!isset($positiveService->state()['jobs'][$latePlan['digest']]));
$positiveService->inventoryDelaySeconds=0;$positiveService->approve($ambiguousPlan);$positiveService->expiredGrant=true;
receiver_check('purge_expired_grant_stops_before_job_or_mutation',receiver_denied(fn()=>$positiveWorkflow->execute($ambiguousPlan),'ACTUAL_PURGE_EXACT_APPROVAL_REQUIRED')&&!isset($positiveService->state()['jobs'][$ambiguousPlan['digest']]));$positiveService->expiredGrant=false;
$positiveWorkflow->execute($ambiguousPlan);$manual2=$positiveWorkflow->ownerMailAction($ambiguousPlan);$positiveService->manualDelete($manual2);$positiveService->ambiguous='outcome';
$held=$positiveWorkflow->execute($ambiguousPlan);$attempts=$positiveService->removeAttempts['outcome'];$heldAgain=$positiveWorkflow->execute($ambiguousPlan);
receiver_check('purge_ambiguous_present_row_is_never_redispatched',$held['status']==='HELD'&&$heldAgain['status']==='HELD'&&in_array('ACTUAL_AMBIGUOUS_WRITE_REVIEW_REQUIRED',$heldAgain['hold_codes'],true)&&$positiveService->removeAttempts['outcome']===$attempts);

// An old independently sealed historical fixture is added once; existing job timestamps never change.
$historical=$positiveService->fixture(3);$historicalClosure=$historical['closure'];$historicalBindings=[];
foreach(['email','outcome','intake'] as $store)foreach($positiveService->resources[$store] as $r)if($r['binding']['request_id']===$historicalClosure['request_id'])$historicalBindings[$store]=$r['binding'];
$historicalCaptureRow=positiveCaptureRow($historicalClosure);
$historicalBindings['capture']=['key'=>$historicalClosure['request_id'],'request_id'=>$historicalClosure['request_id'],'request_ids'=>[$historicalClosure['request_id']],
    'lead_id'=>$historicalClosure['lead_id'],'event_id'=>$historicalClosure['event_id'],'fingerprint'=>$historicalCaptureRow['fingerprint'],'evidence_reference'=>'bsre-wp-capture-resource-v1',
    'evidence_hash'=>C\Workflow::digest(['contract'=>'bsre-wp-capture-resource-v1','row'=>$historicalCaptureRow])];ksort($historicalBindings['capture']);
foreach(['email','outcome','intake'] as $store)foreach($positiveService->resources[$store] as $key=>$r)if($r['binding']['request_id']===$historicalClosure['request_id'])unset($positiveService->resources[$store][$key]);
$at=time()-31*86400;$historicalPlan=$positivePlan;$historicalPlan['closure_id']=$historicalClosure['closure_id'];$historicalPlan['closure_hash']=C\Workflow::digest($historicalClosure);
$historicalPlan['created_at']=$at-1;$historicalPlan['expires_at']=$at-1+900;$historicalResources=[];
foreach(['email','outcome','capture','intake'] as $store)$historicalResources[]=['store'=>$store,'binding'=>$historicalBindings[$store]];
$historicalPlan['resources']=$historicalResources;unset($historicalPlan['digest']);$historicalPlan['digest']=C\Workflow::digest($historicalPlan);
$historicalJob=['plan'=>$historicalPlan,'revision'=>4,'state'=>'COMPLETE','started_at'=>$at,'completed_at'=>$at+1,'steps'=>array_fill(0,4,'CONFIRMED_ABSENT'),'intent_at'=>array_fill(0,4,$at),'code'=>''];
$stateBeforeSeed=$positiveService->state();$seed=$stateBeforeSeed;$seed['closures'][$historicalClosure['closure_id']]=$historicalClosure;$seed['jobs'][$historicalPlan['digest']]=$historicalJob;
$beforeSeed=$custody->current();$nextRevision=$beforeSeed['revision']+1;$sealed=$custody->seal($seed,$nextRevision);$sealedHash=hash('sha256',$sealed);
if($wpdb->custodyIsActive()||$wpdb->get_var('SELECT @@session.in_transaction')!=='0')throw new RuntimeException('SYNTHETIC_HISTORICAL_SEED_ISOLATION_REQUIRED');
if($wpdb->query($wpdb->prepare('UPDATE g5_receiver_synthetic_bsre_g5_journal SET revision=%d,body_hash=%s,body=%s WHERE id=1 AND revision=%d AND BINARY body_hash=BINARY %s',
    $nextRevision,$sealedHash,$sealed,$beforeSeed['revision'],$beforeSeed['hash']))!==1)throw new RuntimeException('SYNTHETIC_HISTORICAL_FIXTURE_CAS_FAILED');
$custody->advance($beforeSeed,['revision'=>$nextRevision,'hash'=>$sealedHash]);
receiver_check('purge_old_fixture_is_sealed_current_and_does_not_rewrite_active_deadlines',$positiveService->state()===$seed&&$seed['jobs'][$positivePlan['digest']]===$done&&time()>=$historicalJob['completed_at']+2592000);
$positiveService->approve($historicalPlan,'EXPIRE_PRIVATE_JOURNAL');$expired=$positiveWorkflow->expire($historicalPlan);$afterExpiry=$positiveService->state();
receiver_check('purge_positive_historical_expiry_uses_real_clock_and_current_custody',$expired['status']==='PRIVATE_JOURNAL_EXPIRED'&&!isset($afterExpiry['jobs'][$historicalPlan['digest']])&&!isset($afterExpiry['closures'][$historicalClosure['closure_id']])
    &&$afterExpiry['jobs'][$positivePlan['digest']]===$done&&$afterExpiry['incomplete']===true&&$afterExpiry['admission_floor']===$positivePlan['admission_hash']);
receiver_check('purge_positive_anchor_transitions_verified',$positiveService->transitions>=10);
receiver_check('purge_positive_no_network_no_mail_no_global_replacement',$networkCalls===0&&$mailCalls===0&&$GLOBALS['wpdb']===$wpdb&&!$wpdb->custodyIsActive());
