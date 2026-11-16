<?php
declare(strict_types=1);
/** Fixed isolated fixture: each process uses its own first-global canonical wpdb. */
const G38_MODES = ['choose_commit','choose_rollback','stage_commit','stage_rollback'];
$worker = ($argv[1] ?? '') === 'worker';
$mode = $worker ? ($argv[2] ?? '') : ($argv[1] ?? '');
if (PHP_SAPI !== 'cli' || __FILE__!=='/opt/lab/g38/g2-retirement-races.php' || realpath(__FILE__)!==__FILE__ || count($argv) !== ($worker ? 3 : 2) || !in_array($mode,G38_MODES,true)) throw new RuntimeException('G38_FIXED_CLI_MODE_REQUIRED');
use BSRE\Enquiries as E;
use BSRE\SharedRepository as G;
use BSRE\RetentionAdmission as A;
use BSRE\ActualRetention as R;
use BSRE\ActualRetention\PreferenceV1 as V;
use BSRE\PreferenceNative as N;

function g38send($pipe,array $value): void {
    $raw=json_encode($value,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)."\n";
    if(strlen($raw)>16384||fwrite($pipe,$raw)!==strlen($raw)||!fflush($pipe))throw new RuntimeException('G38_PIPE_WRITE');
}
function g38read($pipe): array {
    stream_set_timeout($pipe,12);$raw=fgets($pipe,16386);
    if(!is_string($raw)||strlen($raw)>16384||!str_ends_with($raw,"\n"))throw new RuntimeException('G38_PIPE_READ');
    $value=json_decode($raw,true,24,JSON_THROW_ON_ERROR);
    if(!is_array($value))throw new RuntimeException('G38_PIPE_SHAPE');return$value;
}
function g38check(string $name,bool $ok): void {
    global $checks;$checks[$name]=$ok;
    // Persist evidence before any assertion can terminate the native experiment.
    g38send(STDERR,['phase'=>'g38_check','check'=>$name,'pass'=>$ok]);
    if(!$ok)throw new RuntimeException('G38_ASSERTION_FAILED');
}
function g38boot(string $mode): int {
    define('WP_ENVIRONMENT_TYPE','local');define('WP_CONTENT_DIR','/opt/lab/g36/wp-content');define('WP_PLUGIN_DIR',WP_CONTENT_DIR.'/plugins');
    foreach(['BSRE_CANONICAL_LEASE_ENABLED','BSRE_G3_ROUTE_CONTEXT_ENABLED','BSRE_G2_SHARED_REPOSITORY_ENABLED','BSRE_PURPOSE_ATTRIBUTION_ENABLED','BSRE_RETENTION_ADMISSION_ENABLED','BSRE_ROUTING_ENABLED','BSRE_G5_PREFERENCE_RUNTIME_ENABLED'] as $flag)define($flag,true);
    define('BSRE_RETENTION_ADMISSION_GENERATION',str_repeat('a',64));define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',time()-2000);
    define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));
    define('BSRE_G5_PREFERENCE_SOURCE_SHA256',hash_file('sha256','/opt/lab/g37-pref/runtime/preference-source.json'));
    $_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='GET';$_SERVER['REQUEST_URI']='/enquire/';
    require '/opt/wordpress/wp-load.php';require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
    global $wpdb;
    if(!defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED')||BSRE_CANONICAL_LEASE_BOOTSTRAPPED!==true||get_class($wpdb)!=='BSRE\\ClosedRetention\\LeaseBoundWpdb'||DB_NAME!=='bsre_synthetic'||DB_HOST!=='localhost:/tmp/bsre.sock'||DB_USER!=='root'||DB_PASSWORD!=='')throw new RuntimeException('G38_CANONICAL_SYNTHETIC_ONLY');
    add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
    add_filter('plugins_url',fn($url)=>'https://blackswanrealestate.ae'.parse_url($url,PHP_URL_PATH));
    add_filter('rest_url',fn($url,$route)=>'https://blackswanrealestate.ae/wp-json/'.ltrim($route,'/'),10,2);
    $GLOBALS['g38Network']=0;$GLOBALS['g38Mail']=0;
    add_filter('pre_http_request',function(){$GLOBALS['g38Network']++;throw new RuntimeException('G38_HTTP_FORBIDDEN');},PHP_INT_MAX);
    add_filter('pre_wp_mail',function(){$GLOBALS['g38Mail']++;throw new RuntimeException('G38_MAIL_FORBIDDEN');},PHP_INT_MAX);
    $owner=get_user_by('login','synthetic_owner');if(!$owner)throw new RuntimeException('G38_OWNER_REQUIRED');wp_set_current_user($owner->ID);
    $GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
    require_once '/opt/lab/g36/contact-abi.php';\BSRE\G36Native\reconcile();
    $wpdb->prefix='g37_pref_'.substr(hash('sha256','g38|'.$mode),0,12).'_synthetic_';
    $wpdb->suppress_errors(true);
    if($wpdb->query('SET SESSION innodb_lock_wait_timeout=8')===false)throw new RuntimeException('G38_WAIT_TIMEOUT_SETUP');
    return(int)$owner->ID;
}
function g38raw(bool $known): string {
    return $known?'{"request_id":"38111111-1111-4111-8111-111111111111","name":"SYNTHETIC G38 KNOWN"}':
        '{"request_id":"38222222-2222-4222-8222-222222222222","name":"SYNTHETIC G38 UNKNOWN"}';
}
function g38capture(array $choice,bool $known=true,?int $createdAt=null): array {
    $raw=g38raw($known);$body=json_decode($raw,true,4,JSON_THROW_ON_ERROR);
    return ['request_id'=>$body['request_id'],'fingerprint'=>hash('sha256',$raw),
        'subject_key'=>$choice['subject_key'],'original_revision'=>$known?(int)$choice['revision']:0,
        'decision_version'=>$choice['receipt'],'notice_version'=>E\CONSENT_NOTICE_VERSION,'analytics'=>0,'ad_measurement'=>0,
        'preference_expires_at'=>$known?(int)$choice['expires_at']:0,'eligible'=>0,'known'=>$known?1:0,'created_at'=>$createdAt??time(),
        'uncertain'=>0,'click_capture_state'=>'NOT_PERMITTED','gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0];
}
/** Compare persisted/returned rows independently with the ORIGINAL input and raw body. */
function g38matchesCapture(?array $row,array $original,string $originalRaw): bool {
    if($row===null||hash('sha256',$originalRaw)!==$original['fingerprint']||json_decode($originalRaw,true,4,JSON_THROW_ON_ERROR)['request_id']!==$original['request_id'])return false;
    $expected=$original+['personalization'=>0,'state'=>'STAGED','delivery_pending'=>0,'lead_id'=>'','event_id'=>'',
        'purpose_version'=>0,'purpose_hash'=>'','purpose_record_hash'=>'','purpose_json'=>''];
    $actualKeys=array_keys($row);$expectedKeys=array_keys($expected);sort($actualKeys);sort($expectedKeys);
    if($actualKeys!==$expectedKeys)return false;
    foreach($expected as $field=>$value){
        // wpdb may return exact decimal strings or native integers; no coercive casts.
        if(is_int($value)){if($row[$field]!==$value&&$row[$field]!==strval($value))return false;}
        elseif($row[$field]!==$value)return false;
    }
    return true;
}
/** Executed by native PHP: each identity/permission field must independently fail closed. */
function g38captureMatcherGuards(array $original,string $originalRaw): bool {
    $row=$original+['personalization'=>0,'state'=>'STAGED','delivery_pending'=>0,'lead_id'=>'','event_id'=>'',
        'purpose_version'=>0,'purpose_hash'=>'','purpose_record_hash'=>'','purpose_json'=>''];
    if(!g38matchesCapture($row,$original,$originalRaw))return false;
    foreach($row as $field=>$value){
        $altered=$row;$altered[$field]=is_int($value)?$value+1:$value.'CORRUPT';
        if(g38matchesCapture($altered,$original,$originalRaw))return false;
        $missing=$row;unset($missing[$field]);if(g38matchesCapture($missing,$original,$originalRaw))return false;
        if(is_int($value))$row[$field]=strval($value);
    }
    if(!g38matchesCapture($row,$original,$originalRaw)||g38matchesCapture($row+['extra'=>'CORRUPT'],$original,$originalRaw))return false;
    return !g38matchesCapture($row,$original,$originalRaw.' ');
}
function g38admit(array $capture): void {
    A\Runtime::$session=str_repeat('s',64);A\Runtime::$proof=A\sign_new_request($capture['request_id'],A\Runtime::$session,BSRE_LEAD_HMAC_SECRET,A\configuration(),time());
}
function g38rows(string $sql): array {
    global $wpdb;$wpdb->last_error='';$rows=$wpdb->get_results($sql,ARRAY_A);
    if($wpdb->last_error!==''||!is_array($rows)||count($rows)>1000)throw new RuntimeException('G38_READBACK_FAILED');return$rows;
}
function g38control(): array {
    global $wpdb;$rows=g38rows("SELECT * FROM {$wpdb->prefix}bsre_pref_runtime WHERE id='aa'");
    if(count($rows)!==1)throw new RuntimeException('G38_CONTROL_READBACK_FAILED');return$rows[0];
}

/** Own and bound exactly one independent process; never swap the global database. */
final class G38Child {
    private $process=null;private array $pipes=[];public int $connection;public int $pid;
    public function __construct(string $mode,array $choice,int $notice,array $originalCapture) {
        $this->process=proc_open(['php','-d','sendmail_path=/bin/false',__FILE__,'worker',$mode],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$this->pipes);
        if(!is_resource($this->process))throw new RuntimeException('G38_CHILD_START');
        try{
            $status=proc_get_status($this->process);$this->pid=(int)$status['pid'];
            g38send($this->pipes[0],['choice'=>$choice,'notice'=>$notice,'capture'=>$originalCapture]);$ready=g38read($this->pipes[1]);
            if(array_keys($ready)!==['op','connection','pid','canonical']||$ready['op']!=='ready'||!is_int($ready['connection'])||$ready['connection']<1||$ready['pid']!==$this->pid||$ready['canonical']!==true)throw new RuntimeException('G38_CHILD_READY');
            $this->connection=$ready['connection'];g38send($this->pipes[0],['op'=>'go']);
        }catch(Throwable $error){$this->stop();throw$error;}
    }
    public function live(): bool {return is_resource($this->process)&&proc_get_status($this->process)['running'];}
    public function observedProcess(): array {
        if(!is_resource($this->process))throw new RuntimeException('G38_CHILD_PROCESS_ABSENT');
        $status=proc_get_status($this->process);return['pid'=>$status['pid'],'running'=>$status['running']];
    }
    public function finish(): array {
        try{
            $result=g38read($this->pipes[1]);if(($result['op']??null)!=='result')throw new RuntimeException('G38_CHILD_RESULT');
            $deadline=hrtime(true)+2000000000;
            do{$status=proc_get_status($this->process);if(!$status['running'])break;usleep(10000);}while(hrtime(true)<$deadline);
            if($status['running']||$status['exitcode']!==0)throw new RuntimeException('G38_CHILD_EXIT');
            return$result;
        }finally{$this->stop();}
    }
    public function stop(): void {
        if(is_resource($this->process)){
            $status=proc_get_status($this->process);if($status['running'])proc_terminate($this->process,9);
            foreach($this->pipes as $pipe)if(is_resource($pipe))fclose($pipe);proc_close($this->process);
        }$this->process=null;$this->pipes=[];
    }
    public function __destruct(){$this->stop();}
}
function g38wait(G38Child $child,string $operation,string $lock): array {
    global $wpdb;$parent=(int)$wpdb->get_var('SELECT CONNECTION_ID()');
    if($child->connection===$parent||$parent<1||$child->pid===getmypid())throw new RuntimeException('G38_DISTINCT_PROCESSES_REQUIRED');
    $started=hrtime(true);$polls=0;$table=$wpdb->prefix.'bsre_consent_state';
    do{
        if(!$child->live())throw new RuntimeException('G38_CHILD_EXITED_BEFORE_WAIT');$wpdb->last_error='';
        $rows=$wpdb->get_results($wpdb->prepare('SELECT r.trx_mysql_thread_id AS waiter,b.trx_mysql_thread_id AS blocker,w.requesting_trx_id AS requesting_trx_id,w.blocking_trx_id AS blocking_trx_id,r.trx_query AS waiting_query,l.lock_table AS waiting_table,l.lock_index AS waiting_index FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX r ON r.trx_id=w.requesting_trx_id JOIN information_schema.INNODB_TRX b ON b.trx_id=w.blocking_trx_id JOIN information_schema.INNODB_LOCKS l ON l.lock_id=w.requested_lock_id WHERE r.trx_mysql_thread_id=%d AND b.trx_mysql_thread_id=%d',$child->connection,$parent),ARRAY_A);
        if($wpdb->last_error!==''||!is_array($rows))throw new RuntimeException('G38_LOCK_METADATA_UNAVAILABLE');$polls++;
        foreach($rows as $row){
            $query=$row['waiting_query']??'';$sqlOk=is_string($query)&&($operation==='choose'?str_starts_with($query,'INSERT IGNORE INTO '.$table.' '):str_starts_with($query,'SELECT * FROM '.$table.' WHERE subject_key=')&&str_ends_with($query,' FOR UPDATE'));
            if(!$sqlOk||str_replace(['`','"'],'',(string)$row['waiting_table'])!==DB_NAME.'.'.$table||$row['waiting_index']!=='PRIMARY')continue;
            if(strlen($query)>2048||!is_string($row['waiting_table'])||strlen($row['waiting_table'])>256||!is_string($row['waiting_index'])||strlen($row['waiting_index'])>64||preg_match('/^[1-9][0-9]{0,31}$/D',(string)$row['requesting_trx_id'])!==1||preg_match('/^[1-9][0-9]{0,31}$/D',(string)$row['blocking_trx_id'])!==1||(string)$row['requesting_trx_id']===(string)$row['blocking_trx_id'])throw new RuntimeException('G38_RAW_WAIT_METADATA_INVALID');
            // Preserve exact selected synthetic metadata. No expected table/query is
            // substituted and oversized observations are refused rather than truncated.
            $facts=$wpdb->get_row($wpdb->prepare('SELECT CONNECTION_ID() AS parent_connection,DATABASE() AS selected_database,@@session.in_transaction AS session_in_transaction,@@session.tx_isolation AS session_tx_isolation,IS_USED_LOCK(%s) AS named_lock_owner',$lock),ARRAY_A);
            $process=$child->observedProcess();$parentPid=getmypid();$custodyConnection=$wpdb->custodyConnectionId();$custodyActive=$wpdb->custodyIsActive();$canonicalClass=get_class($wpdb);
            $bootstrapped=defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED')&&BSRE_CANONICAL_LEASE_BOOTSTRAPPED===true;$sameObject=G\Runtime::$db===$wpdb;
            if($wpdb->last_error!==''||!is_array($facts)||(int)$facts['parent_connection']!==$parent||(int)$facts['named_lock_owner']!==$parent||$facts['selected_database']!==DB_NAME||(string)$facts['session_in_transaction']!=='1'||$facts['session_tx_isolation']!=='REPEATABLE-READ'||!$custodyActive||(string)$custodyConnection!==(string)$parent||$canonicalClass!=='BSRE\\ClosedRetention\\LeaseBoundWpdb'||!$bootstrapped||!$sameObject||$process['running']!==true||$process['pid']!==$child->pid||$parentPid===$process['pid'])throw new RuntimeException('G38_LOCK_OWNER_UNVERIFIED');
            return ['mechanism'=>'INNODB_LOCK_WAITS','real_wait'=>true,'child_live'=>$process['running'],'distinct_processes'=>true,'distinct_connections'=>true,
                'waiter'=>(int)$row['waiter'],'blocker'=>(int)$row['blocker'],'named_lock_owner'=>(int)$facts['named_lock_owner'],'state_primary_wait'=>true,
                'waiting_statement'=>$operation==='choose'?'INSERT_IGNORE_STATE':'SELECT_STATE_FOR_UPDATE','polls'=>$polls,'elapsed_ms'=>(hrtime(true)-$started)/1000000,
                'parent_pid'=>$parentPid,'child_pid'=>$process['pid'],'parent_connection'=>(int)$facts['parent_connection'],'child_connection'=>$child->connection,
                'requesting_trx_id'=>(string)$row['requesting_trx_id'],'blocking_trx_id'=>(string)$row['blocking_trx_id'],
                'waiting_table'=>$row['waiting_table'],'waiting_index'=>$row['waiting_index'],'waiting_query'=>$query,
                'selected_database'=>$facts['selected_database'],'database_prefix'=>$wpdb->prefix,'canonical_class'=>$canonicalClass,
                'canonical_bootstrapped'=>$bootstrapped,'canonical_g2_same_object'=>$sameObject,'custody_active'=>$custodyActive,
                'custody_connection'=>$custodyConnection,'session_in_transaction'=>(string)$facts['session_in_transaction'],'session_tx_isolation'=>$facts['session_tx_isolation']];
        }
        usleep(20000); // Backoff only: elapsed time is never accepted as wait evidence.
    }while(hrtime(true)-$started<4000000000);
    throw new RuntimeException('G38_REAL_SQL_WAIT_MISSING');
}

$isolation=['cli'=>PHP_SAPI==='cli','non_root'=>function_exists('posix_geteuid')&&posix_geteuid()!==0,
    'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
    'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
    'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
    'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
    'readonly_application'=>!is_writable('/opt/wordpress')&&!is_writable('/opt/lab/g36')&&!is_writable('/opt/lab/g37-pref')&&!is_writable('/opt/lab/g38')&&!is_writable(__FILE__),
    'database_already_started'=>is_dir('/tmp/database')&&file_exists('/tmp/bsre.sock'),'no_docker_socket'=>!file_exists('/var/run/docker.sock')];
foreach($isolation as $ok)if(!$ok)throw new RuntimeException('G38_ISOLATION_REQUIRED');
$checks=[];$child=null;$wait=null;$failure=null;$completed=false;$started=hrtime(true);ob_start();
register_shutdown_function(static function()use(&$completed,&$failure,&$child,&$checks,$mode):void{
    if($completed)return;if($child instanceof G38Child)$child->stop();while(ob_get_level())@ob_end_clean();
    $message=$failure instanceof Throwable?$failure->getMessage():'';
    $code=preg_match('/^[A-Z][A-Z0-9_]+$/D',$message)===1?$message:'G38_UNEXPECTED_FAILURE';
    g38send(STDERR,['phase'=>'g38_g2_race_diagnostic','status'=>'FAIL','mode'=>$mode,'checks'=>$checks,'error_code'=>$code,'native_provider_accepted'=>false]);
});
try{
    $init=$worker?g38read(STDIN):null;
    if($worker&&(array_keys($init)!==['choice','notice','capture']||!is_array($init['choice'])||!is_int($init['notice'])||!is_array($init['capture'])))throw new RuntimeException('G38_INIT');
    $owner=g38boot($mode);$operation=str_starts_with($mode,'choose_')?'choose':'stage';$rollback=str_ends_with($mode,'_rollback');
    if($worker){
        define('BSRE_PRIVACY_NOTICE_PAGE_ID',$init['notice']);$store=G\repository();
        while(ob_get_level())ob_end_clean();
        g38send(STDOUT,['op'=>'ready','connection'=>(int)$wpdb->get_var('SELECT CONNECTION_ID()'),'pid'=>getmypid(),'canonical'=>get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb']);
        if(g38read(STDIN)!==['op'=>'go'])throw new RuntimeException('G38_GO_REQUIRED');
        $result=null;$error=null;$capture=$init['capture'];
        try{
            if($operation==='choose')$result=$store->choose($init['choice']['subject_key'],['analytics'=>true,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time());
            else{g38admit($capture);$result=$store->stage($capture);}
        }catch(Throwable $e){$error=$e->getMessage()==='Consent evidence retired.'?'Consent evidence retired.':'G38_UNEXPECTED_CHILD_EXCEPTION';}
        g38send(STDOUT,['op'=>'result','error'=>$error,'row'=>$result,'transaction_closed'=>(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0','canonical'=>get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb','no_http_or_mail'=>$GLOBALS['g38Network']===0&&$GLOBALS['g38Mail']===0]);
        $completed=true;exit(0);
    }
    $notice=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g38-synthetic-'.$mode,'post_title'=>'SYNTHETIC G38 NOTICE'],true);
    if(is_wp_error($notice))throw new RuntimeException('G38_NOTICE_FIXTURE');define('BSRE_PRIVACY_NOTICE_PAGE_ID',$notice);
    E\install();if(!G\migrate())throw new RuntimeException('G38_G2_SCHEMA');
    require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/candidate/consent-retention/RetentionInventory.php';
    require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/candidate/purpose-retention/purpose-retention.php';
    require '/opt/lab/g37-pref/runtime/ActualPreferenceRetention.php';require '/opt/lab/g37-pref/FixturePorts.php';
    $base=new R\RuntimePolicy(DB_NAME,$wpdb->prefix,'https://blackswanrealestate.ae',$owner);$source=BSRE_G5_PREFERENCE_SOURCE_SHA256;
    $policy=new V\Policy($base,$source,'aa');$keys=new N\Keys();$services=new N\Services($keys);
    $runtime=R\ActualPreferenceRetention::bind($wpdb,$base,$source,'aa',$services,$services,$keys);
    $nonce=fn($action,$digest)=>wp_create_nonce('bsre-pref-v1|'.$policy->scope().'|'.$action.'|'.$digest);
    $runtime->initialize($nonce('INITIALIZE',V\Guard::digest(['initialize'=>$policy->scope()])));
    $subject='aa'.substr(hash('sha256','SYNTHETIC_G38_'.$mode),0,62);$store=G\repository();
    $choice=$store->choose($subject,['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time()-400*86400);
    // This immutable parent-owned input survives process handoff and every retry.
    $originalCapture=g38capture($choice);$knownRaw=g38raw(true);
    g38check('capture_matcher_rejects_identity_and_permission_corruption',g38captureMatcherGuards($originalCapture,$knownRaw));
    $plan=$runtime->preview([$subject],$nonce('RETIRE',$runtime->previewDigest('RETIRE')));
    g38check('exact_two_retirement_targets',count($plan['details']['eligible'])===2);
    $controlBefore=g38control();$anchorBefore=$services->anchor;$casBefore=$services->casCalls;
    $lock='bsre-g5-'.substr($base->scope(),0,48);
    $services->onCoverage=function()use($mode,$choice,$notice,$operation,$lock,$originalCapture,&$child,&$wait):void{
        $child=new G38Child($mode,$choice,$notice,$originalCapture);$wait=g38wait($child,$operation,$lock);
        g38send(STDERR,['phase'=>'g38_wait','mode'=>$mode]+$wait);
    };
    $services->rollbackKey=$rollback;$result=null;$error=null;
    try{$result=$runtime->apply($plan,$nonce('RETIRE',V\Guard::digest($plan)));}catch(Throwable $e){$error=$e->getMessage();}
    g38check('observed_real_wait',is_array($wait)&&$wait['real_wait']&&$wait['named_lock_owner']===$wait['blocker']);
    g38check('exact_retirement_outcome',$rollback?$error==='G37_INJECTED_KEY_FAILURE':$error===null&&($result['status']??'')==='COMMITTED_AND_ANCHORED');
    if(!$child instanceof G38Child)throw new RuntimeException('G38_CHILD_NOT_STARTED');$childResult=$child->finish();$child=null;
    $expectedError=$operation==='stage'&&!$rollback?'Consent evidence retired.':null;
    g38check('exact_child_outcome',$childResult['error']===$expectedError&&$childResult['transaction_closed']===true&&$childResult['canonical']===true&&$childResult['no_http_or_mail']===true);
    $state=$store->current($subject);$hist=g38rows($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_history WHERE subject_key=%s ORDER BY revision LIMIT 1001",$subject));
    $captures=g38rows("SELECT * FROM {$wpdb->prefix}bsre_consent_captures ORDER BY request_id LIMIT 1001");
    $control=g38control();$audit=g38rows("SELECT action,affected_rows,confirmed FROM {$wpdb->prefix}bsre_pref_audit WHERE action='RETIRE' LIMIT 1001");
    g38check('retirement_audit_anchor_atomic',$rollback?$control===$controlBefore&&$services->anchor===$anchorBefore&&$services->casCalls===$casBefore&&$audit===[]:
        $control['status']==='READY'&&$services->anchor['sequence']===1&&$services->anchor['operation_revision']===2&&$services->casCalls===$casBefore+1&&count($audit)===1&&(int)$audit[0]['affected_rows']===2&&(int)$audit[0]['confirmed']===1);
    $crypto=new V\Custody($policy,new V\Proofs($policy,$services,$services),$keys);
    $ledger=V\Algebra::validate($crypto->open($control['body'],(int)$control['operation_revision'])['ledger']);
    g38check('authenticated_ledger_exact_old_receipt',$rollback?$ledger===V\Algebra::empty():count($ledger['rows'])===1&&$ledger['rows'][0]['receipt']===$choice['receipt']&&$ledger['rows'][0]['subject_key']===$subject&&(int)$ledger['rows'][0]['revision']===1&&$ledger['anchor']['sequence']===1);
    if($operation==='choose'){
        $new=$childResult['row'];g38check('new_choice_exact_revision_and_permissions',is_array($new)&&is_array($state)&&$state['subject_key']===$subject&&$state['receipt']===$new['receipt']&&$new['receipt']!==$choice['receipt']&&(int)$state['revision']===($rollback?2:1)&&(int)$state['analytics']===1&&(int)$state['ad_measurement']===0&&(int)$state['personalization']===0&&$state['notice_version']===E\CONSENT_NOTICE_VERSION&&(int)$state['uncertain']===0&&(int)$state['changed_at']===$new['changed_at']&&(int)$state['expires_at']===$new['expires_at']);
        g38check('old_history_retained_only_after_rollback',count($hist)===($rollback?2:1)&&in_array($choice['receipt'],array_column($hist,'receipt'),true)===$rollback&&$captures===[]);
    }else{
        g38check('known_stage_matches_retirement_winner',$rollback?$state['receipt']===$choice['receipt']&&count($hist)===1&&count($captures)===1:$state===null&&$hist===[]&&$captures===[]);
        if($rollback)g38check('staged_exact_original_input_preserved',g38matchesCapture($captures[0],$originalCapture,$knownRaw)&&g38matchesCapture($childResult['row'],$originalCapture,$knownRaw));
    }
    $unknown=g38capture($choice,false);$unknownRaw=g38raw(false);g38admit($unknown);$unknownRow=$store->stage($unknown);
    $unknownStored=g38rows($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$unknown['request_id']));
    g38check('healthy_unknown_exact_original_input_preserved',count($unknownStored)===1&&g38matchesCapture($unknownStored[0],$unknown,$unknownRaw)&&g38matchesCapture($unknownRow,$unknown,$unknownRaw));
    // A retry's incoming current decision may differ; the original capture is immutable.
    $retryChoice=$store->choose($subject,['analytics'=>true,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time());
    $unknownRetry=g38capture($retryChoice,false,$unknown['created_at']);
    $unknownRetry['original_revision']=(int)$retryChoice['revision'];$unknownRetry['known']=1;$unknownRetry['eligible']=1;$unknownRetry['analytics']=1;
    $unknownRetry['preference_expires_at']=(int)$retryChoice['expires_at'];g38admit($unknownRetry);$unknownAgain=$store->stage($unknownRetry);
    $unknownStored=g38rows($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$unknown['request_id']));
    g38check('unknown_retry_keeps_original_decision',count($unknownStored)===1&&$unknownRetry['decision_version']!==$unknown['decision_version']&&g38matchesCapture($unknownStored[0],$unknown,$unknownRaw)&&g38matchesCapture($unknownAgain,$unknown,$unknownRaw));
    if($operation==='stage'&&$rollback){
        $knownRetry=g38capture($retryChoice,true,$originalCapture['created_at']);$knownRetry['analytics']=1;$knownRetry['eligible']=1;
        g38admit($knownRetry);$knownAgain=$store->stage($knownRetry);
        $knownStored=g38rows($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$originalCapture['request_id']));
        g38check('known_retry_keeps_original_decision',count($knownStored)===1&&$knownRetry['decision_version']!==$originalCapture['decision_version']&&g38matchesCapture($knownStored[0],$originalCapture,$knownRaw)&&g38matchesCapture($knownAgain,$originalCapture,$knownRaw));
    }
    g38check('canonical_lease_and_transaction_released',get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb'&&!$wpdb->custodyIsActive()&&(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0'&&$wpdb->get_var($wpdb->prepare('SELECT IS_USED_LOCK(%s)',$lock))===null);
    g38check('no_http_or_mail',$GLOBALS['g38Network']===0&&$GLOBALS['g38Mail']===0);
    g38check('bounded_duration',(hrtime(true)-$started)<60000000000);
    while(ob_get_level())ob_end_clean();
    g38send(STDOUT,['phase'=>'g38_g2_retirement_race','status'=>'PASS','mode'=>$mode,'checks'=>$checks,'wait'=>$wait,'runtime_isolation'=>$isolation,
        'synthetic_only'=>true,'actual_provider_accepted'=>false,'production_authorized'=>false,'full_operational_retention_accepted'=>false]);
    $completed=true;
}catch(Throwable $e){$failure=$e;exit(1);}
