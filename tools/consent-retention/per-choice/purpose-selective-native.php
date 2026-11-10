<?php
declare(strict_types=1);
/** Real purpose endpoint and SQL in one synthetic namespace; Google remains a pipe service double. */
define('WP_ENVIRONMENT_TYPE','local');define('BSRE_RETENTION_LAB',true);
define('BSRE_PER_CHOICE_LAB_ENABLED',true);define('BSRE_PER_CHOICE_APPLY_ENABLED',true);
define('BSRE_PER_CHOICE_PURPOSE_LAB_ENABLED',true);define('BSRE_PER_CHOICE_PURPOSE_APPLY_ENABLED',true);
$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='POST';
require '/opt/wordpress/wp-load.php';require '/opt/lab/purpose/store.php';
require '/opt/lab/purpose/purpose-attribution.php';require '/opt/lab/purpose/intake.php';
require __DIR__.'/SelectiveChoiceRetirement.php';
use BSRE\Enquiries as E;use BSRE\PurposeAttribution as A;
use BSRE\RetentionReview\PerChoice\PerChoicePlanner as B;
use BSRE\RetentionReview\PerChoice\ApplicationV1\SelectiveChoiceRetirement as C;
$endpointHome=false;add_filter('home_url',fn($url,$path)=>($GLOBALS['endpointHome']?'https://blackswanrealestate.ae':'http://bsre.invalid').($path===''?'':'/'.ltrim($path,'/')),10,2);
$owner=get_user_by('login','synthetic_owner');wp_set_current_user($owner->ID);$checks=[];$clock=time()+500*86400;
function px(string $name,bool $ok):void{global$checks;if(!$ok)throw new RuntimeException('Synthetic purpose selective assertion failed: '.$name);$checks[$name]=true;}
function pd(string $class='wpdb'){$db=new $class(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);$db->set_prefix('synthetic_');$db->prefix=C::PURPOSE_PREFIX;$db->suppress_errors(true);return$db;}
function pcntl($db=null):C{return C::purposeLab($db??$GLOBALS['db'],fn()=>$GLOBALS['clock']);}
function pq(string $sql):void{if($GLOBALS['db']->query($sql)===false)throw new RuntimeException('Synthetic purpose fixture SQL failed');}
function pheld(callable $fn,string $code):bool{try{$fn();return false;}catch(Throwable $e){return $e->getMessage()===$code;}}
function pplan(C $control):array{$source=$control->reviewSource();$coverage=['kind'=>B::COVERAGE,'snapshot_sha256'=>B::digest($source['snapshot']),'status'=>'COMPLETE_SYNTHETIC','observed_at'=>$GLOBALS['clock'],'valid_until'=>$GLOBALS['clock']+3600,'history_pruned'=>false];return[$control->preview($coverage,$source['anchor']),$source];}
class PurposeFaultDb extends wpdb {
    public string $fault='';public $beforeDelete=null;public bool $pauseChoice=false;
    public function query($sql){
        if($this->pauseChoice&&str_contains($sql,'bsre_consent_state')&&str_contains($sql,'FOR UPDATE')){
            $result=parent::query($sql);$this->pauseChoice=false;echo "LOCKED\n";fflush(STDOUT);stream_set_timeout(STDIN,5);
            if(trim((string)fgets(STDIN))!=='CONTINUE')throw new RuntimeException('Synthetic choice release unavailable');return$result;
        }
        if($this->beforeDelete!==null&&str_starts_with($sql,'DELETE FROM '.C::PURPOSE_PREFIX.'bsre_consent_')){$callback=$this->beforeDelete;$this->beforeDelete=null;$callback();}
        if($this->fault==='delete'&&str_starts_with($sql,'DELETE FROM '.C::PURPOSE_PREFIX.'bsre_consent_')){$this->fault='';return false;}
        if($this->fault==='audit'&&str_starts_with($sql,'INSERT INTO '.C::PURPOSE_PREFIX.'bsre_choice_audit')){$this->fault='';return false;}
        if($this->fault==='checkpoint'&&str_starts_with($sql,'UPDATE '.C::PURPOSE_PREFIX.'bsre_choice_control')){$this->fault='';return false;}
        if($sql==='COMMIT'&&in_array($this->fault,['commit-before','commit-after'],true)){$mode=$this->fault;$this->fault='';if($mode==='commit-after')parent::query($sql);return false;}
        return parent::query($sql);
    }
}
$db=pd();
if(in_array($argv[1]??'',['apply-worker','stage-worker','choose-worker'],true)){
    stream_set_timeout(STDIN,5);$input=json_decode(trim((string)fgets(STDIN,100000)),true,20,JSON_THROW_ON_ERROR);
    if($argv[1]==='choose-worker'){$db->close();$db=pd(PurposeFaultDb::class);$db->pauseChoice=true;}
    echo 'READY:'.$db->get_var('SELECT CONNECTION_ID()')."\n";fflush(STDOUT);
    try{
        if($argv[1]==='choose-worker'){(new A\WpConsentRepository($db))->choose($input['subject'],['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,$input['at']);echo "CHOSEN\n";}
        elseif($argv[1]==='stage-worker'){A\Runtime::$submission=['fingerprint'=>$input['capture']['fingerprint'],'sidecar'=>$input['sidecar']];(new A\WpConsentRepository($db))->stage($input['capture']);echo "STAGED\n";}
        else{pcntl()->apply($input['plan'],$input['ack'],$input['anchor']);echo "APPLIED\n";}
    }catch(Throwable $e){echo match($e->getMessage()){'PURPOSE_EVIDENCE_RETIRED'=>"RETIRED\n",'SELECTIVE_PLAN_STALE_OR_ALTERED'=>"STALE\n",default=>"UNCLASSIFIED_HOLD\n"};}
    fflush(STDOUT);exit;
}
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));define('BSRE_ROUTING_ENABLED',true);
add_action('rest_api_init','BSRE\\PurposeAttribution\\register_routes');
$privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'purpose-choice-synthetic-notice','post_title'=>'SYNTHETIC LAB NOTICE']);define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);
$receiverProcess=proc_open(['node','/opt/lab/receiver-bridge.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$receiverPipes);
px('synthetic_receiver_started',is_resource($receiverProcess));stream_set_timeout($receiverPipes[1],5);
function pr(array $command):array{global$receiverPipes;$line=json_encode($command,JSON_THROW_ON_ERROR)."\n";if(fwrite($receiverPipes[0],$line)!==strlen($line))throw new RuntimeException('Synthetic receiver write unavailable');fflush($receiverPipes[0]);$reply=fgets($receiverPipes[1],1000000);if($reply===false||!str_ends_with($reply,"\n"))throw new RuntimeException('Synthetic receiver read unavailable');return json_decode($reply,true,32,JSON_THROW_ON_ERROR);}
$lastReceipt=null;$lastBody='';add_filter('pre_http_request',function($pre,$args,$url){
    px('receiver_network_intercepted',$url===BSRE_LEAD_RECEIVER_URL);$outer=json_decode($args['body'],true,12,JSON_THROW_ON_ERROR);px('exact_original_wire_preserved',$outer['body']===$GLOBALS['lastBody']&&!str_contains($outer['body'],'purpose_'));
    $receipt=pr(['op'=>'post','raw'=>$args['body']]);px('pinned_receiver_receipt_accepted',($receipt['accepted']??false)===true);$GLOBALS['lastReceipt']=$receipt;
    return ['headers'=>[],'body'=>wp_json_encode($receipt),'response'=>['code'=>200]];
},PHP_INT_MAX,3);
function pfixture():array{
    global$db,$wpdb,$clock,$endpointHome,$lastBody,$lastReceipt,$owner;
    wp_set_current_user($owner->ID);$endpointHome=false;
    px('controller_home_remains_explicit_isolated_origin',home_url()==='http://bsre.invalid'&&wp_get_environment_type()==='local');
    foreach(['bsre_choice_audit','bsre_choice_control','bsre_consent_captures','bsre_consent_history','bsre_consent_state','bsre_rate_limits']as$table)pq('DROP TABLE IF EXISTS '.C::PURPOSE_PREFIX.$table);
    $control=pcntl();$control->installLabTables();$main=$wpdb;$wpdb=$db;
    try{E\install();px('purpose_schema_installed_in_controller_database',A\install_consent_storage());$store=new A\WpConsentRepository($db);A\Runtime::$store=$store;
        $_COOKIE=[E\COOKIE=>bin2hex(random_bytes(32))];$subject=E\consent_subject_key($_COOKIE[E\COOKIE]);$now=time();$on=['analytics'=>true,'ad_measurement'=>true];
        $first=$store->choose($subject,$on,E\CONSENT_NOTICE_VERSION,$now-600);$second=$store->choose($subject,$on,E\CONSENT_NOTICE_VERSION,$now-300);$third=$store->choose($subject,$on,E\CONSENT_NOTICE_VERSION,$now-100);
        $endpointHome=true;wp_set_current_user(0);$_SERVER['REMOTE_ADDR']='198.51.100.180';
        $wire=['request_id'=>wp_generate_uuid4(),'role'=>'tenant','name'=>'SYNTHETIC purpose selective','phone'=>'+971500000000','email'=>'fixture@example.invalid','country'=>'UAE','area'=>'Synthetic fixture','budget'=>'To discuss','timeline'=>'Immediate / move now','funding'=>'To discuss','property_type'=>'Apartment','property_details'=>'SYNTHETIC NOT INVENTORY','authority'=>'','contact_consent'=>true,'marketing_consent'=>false,'campaign'=>'SYNTHETIC_LAB_ONLY','landing_page'=>'https://blackswanrealestate.ae/enquire/rent/','website'=>'','started_at'=>($now-5)*1000];$lastBody=wp_json_encode($wire);
        $touch=['capture_id'=>wp_generate_uuid4(),'decision_version'=>$second['receipt'],'notice_version'=>E\CONSENT_NOTICE_VERSION,'landing_page'=>$wire['landing_page'],'referrer'=>'','timestamp'=>($now-250)*1000,'parameters'=>(object)['gclid'=>'Exact_Click.A~9']];$analytics=$touch;$analytics['capture_id']=wp_generate_uuid4();$analytics['parameters']=(object)['utm_source'=>'SYNTHETIC_FIRST'];
        $sidecar=['version'=>1,'analytics'=>['first'=>$analytics,'last'=>$analytics],'advertising'=>['first'=>$touch,'last'=>$touch]];
        $request=new WP_REST_Request('POST','/bsre/v1/purpose-lead');foreach(['origin'=>'https://blackswanrealestate.ae','sec-fetch-site'=>'same-origin','content-type'=>'application/json','x-bsre-csrf'=>E\csrf_token($_COOKIE[E\COOKIE],$now-3,wp_salt('auth')),'x-bsre-consent-decision'=>$third['receipt']]as$k=>$v)$request->set_header($k,$v);
        $request->set_body(wp_json_encode(['version'=>1,'wire_body'=>$lastBody,'attribution'=>$sidecar]));$response=rest_do_request($request);
        px('actual_purpose_endpoint_accepts_and_links_receipt',$response->get_status()===200&&$response->get_data()['lead_id']===$lastReceipt['lead_id']);
        $capture=$db->get_row($db->prepare('SELECT * FROM '.C::PURPOSE_PREFIX.'bsre_consent_captures WHERE request_id=%s',$wire['request_id']),ARRAY_A);A\assert_record($capture);$record=json_decode($capture['purpose_json'],true,12,JSON_THROW_ON_ERROR);
        px('older_both_purpose_refs_persist_exact_click',($record['advertising']['first']['original_revision']??null)===2&&($record['analytics']['last']['original_revision']??null)===2&&$record['advertising']['last']['parameters']['gclid']==='Exact_Click.A~9'&&(int)$capture['original_revision']===3);
        $when=(int)$capture['created_at'];$store->choose($subject,['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,$when+1);$store->choose($subject,$on,E\CONSENT_NOTICE_VERSION,$when+2);
        wp_set_current_user($owner->ID);$private=A\private_history($db,$wire['request_id'],$when+3);px('withdrawal_regrant_denies_original_private_context',$private['analytics']['first']===null&&$private['advertising']['first']===null);
        $store->choose(str_repeat('c',64),['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,$now-1000);$clock=$when+500*86400;
        return [$control,$capture,$first,$sidecar,$subject];
    }finally{$wpdb=$main;$endpointHome=false;wp_set_current_user($owner->ID);}
}
function pworker(string $operation,array $input):array{
    $process=proc_open([PHP_BINARY,'-d','sendmail_path=/bin/false',__FILE__,$operation],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
    if(!is_resource($process))throw new RuntimeException('Synthetic worker unavailable');$raw=json_encode($input,JSON_THROW_ON_ERROR)."\n";
    try{if(fwrite($pipes[0],$raw)!==strlen($raw))throw new RuntimeException('Synthetic worker input unavailable');fflush($pipes[0]);stream_set_timeout($pipes[1],5);$ready=trim((string)fgets($pipes[1]));if(!preg_match('/^READY:([0-9]+)$/D',$ready,$match))throw new RuntimeException('Synthetic worker readiness unavailable');return[$process,$pipes,(int)$match[1]];}
    catch(Throwable $e){proc_terminate($process,9);foreach($pipes as$pipe)if(is_resource($pipe))fclose($pipe);proc_close($process);throw$e;}
}
function pstop(array &$worker):void{if(!$worker)return;[$process,$pipes]=$worker;proc_terminate($process,9);foreach($pipes as$pipe)if(is_resource($pipe))fclose($pipe);proc_close($process);$worker=[];}
function pout(array &$worker):array{[$process,$pipes]=$worker;fclose($pipes[0]);$line=trim((string)fgets($pipes[1]));if($line==='')throw new RuntimeException('Synthetic worker result unavailable');fclose($pipes[1]);$exit=proc_close($process);$worker=[];return[$line,$exit];}
function pwait($observer,int $waiting,int $blocking):bool{
    $deadline=microtime(true)+5;do{$observer->last_error='';$count=$observer->get_var($observer->prepare('SELECT COUNT(*) FROM information_schema.INNODB_LOCK_WAITS w JOIN information_schema.INNODB_TRX wt ON w.requesting_trx_id=wt.trx_id JOIN information_schema.INNODB_TRX bt ON w.blocking_trx_id=bt.trx_id WHERE wt.trx_mysql_thread_id=%d AND bt.trx_mysql_thread_id=%d',$waiting,$blocking));if($observer->last_error!=='')throw new RuntimeException('Synthetic lock observation unavailable');if((int)$count>0)return true;usleep(200000);}while(microtime(true)<$deadline);return false;
}

try{
    [$control,$capture]=pfixture();[$plan,$before]=pplan($control);px('only_older_unreferenced_and_unsubmitted_rows_selected',$plan['deleted_state']===1&&$plan['deleted_history']===2&&count($plan['selected'])===3);
    $applied=$control->apply($plan,C::labAcknowledgement($plan),$before['anchor']);$after=$control->reviewSource();
    px('nested_history_withdrawals_and_all_four_fields_preserved',$applied['deleted_rows']===3&&count($after['snapshot']['history'])===4&&$after['snapshot']['captures']===$before['snapshot']['captures']);
    px('exact_readback_and_permanent_gap_hold',$control->reconcileLast($plan,$after['anchor'])['last_operation_reconciled']&&pheld(fn()=>pplan($control),'SELECTIVE_HISTORY_RECONCILIATION_REQUIRED'));
    foreach(['hash','missing_nested','cross_subject','partial_payload','known_zero']as$case){
        [$control,$capture]=pfixture();$record=json_decode($capture['purpose_json']);
        if($case==='hash')$capture['purpose_record_hash']=str_repeat('0',64);
        elseif($case==='known_zero')$capture['known']=0;
        else{if($case==='missing_nested')$record->advertising->first->decision_version=str_repeat('0',32);elseif($case==='cross_subject'){$other=$db->get_var('SELECT receipt FROM '.C::PURPOSE_PREFIX."bsre_consent_history WHERE subject_key='".str_repeat('c',64)."'");$record->advertising->first->decision_version=$other;}else unset($record->analytics->last);
            $capture['purpose_json']=json_encode($record,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);$capture['purpose_record_hash']=hash('sha256',$capture['fingerprint']."\n".$capture['purpose_hash']."\n".$capture['purpose_json']);}
        px($case.'_fixture_updated',$db->update(C::PURPOSE_PREFIX.'bsre_consent_captures',$capture,['request_id'=>$capture['request_id']])!==false);
        px($case.'_holds_whole_sql_batch',pheld(fn()=>pplan($control),'SELECTIVE_PURPOSE_LINEAGE_UNRESOLVED')&&(int)$db->get_var('SELECT COUNT(*) FROM '.C::PURPOSE_PREFIX.'bsre_choice_audit')===0);
    }
    foreach(['delete','audit','checkpoint']as$fault){[$control]=pfixture();[$plan,$before]=pplan($control);$faultDb=pd(PurposeFaultDb::class);$faultDb->fault=$fault;
        px($fault.'_fault_rolls_back_full_extended_source',pheld(fn()=>pcntl($faultDb)->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_STORAGE_UNAVAILABLE')&&B::digest($control->reviewSource()['snapshot'])===$plan['source_hash']&&$control->anchor()===$before['anchor']);$faultDb->close();}
    foreach(['commit-before','commit-after']as$fault){[$control]=pfixture();[$plan,$before]=pplan($control);$faultDb=pd(PurposeFaultDb::class);$uncertain=pcntl($faultDb);$faultDb->fault=$fault;
        px($fault.'_ambiguous_response_holds',pheld(fn()=>$uncertain->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_COMMIT_AMBIGUOUS_READBACK_REQUIRED')&&pheld(fn()=>$uncertain->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_FRESH_READBACK_REQUIRED'));$faultDb->close();$fresh=pcntl();$source=$fresh->reviewSource();
        px($fault.'_fresh_readback_resolves_without_redelete',$fault==='commit-before'?$source===$before:($source['snapshot']['captures']===$before['snapshot']['captures']&&$fresh->reconcileLast($plan,$source['anchor'])['last_operation_reconciled']));}
    [$control,$capture]=pfixture();[$plan,$before]=pplan($control);$changed=$capture;$changed['purpose_hash']=str_repeat('9',64);$changed['purpose_record_hash']=hash('sha256',$changed['fingerprint']."\n".$changed['purpose_hash']."\n".$changed['purpose_json']);$db->update(C::PURPOSE_PREFIX.'bsre_consent_captures',$changed,['request_id'=>$capture['request_id']]);
    px('four_field_change_invalidates_old_plan',pheld(fn()=>$control->apply($plan,C::labAcknowledgement($plan),$before['anchor']),'SELECTIVE_PLAN_STALE_OR_ALTERED'));

    // Actual producer choose owns a state row; writer must wait, then refuse the changed source.
    [$control,$capture,,,$subject]=pfixture();[$plan,$before]=pplan($control);$observer=pd();$choose=[];$apply=[];
    try{$choose=pworker('choose-worker',['subject'=>$subject,'at'=>(int)$capture['created_at']+3]);px('actual_choose_transaction_reaches_locked_state',trim((string)fgets($choose[1][1]))==='LOCKED');
        $apply=pworker('apply-worker',['plan'=>$plan,'ack'=>C::labAcknowledgement($plan),'anchor'=>$before['anchor']]);px('actual_choice_blocks_selective_snapshot',pwait($observer,$apply[2],$choose[2]));
        fwrite($choose[1][0],"CONTINUE\n");fflush($choose[1][0]);px('actual_choose_commits',pout($choose)===['CHOSEN',0]);px('changed_choice_prevents_stale_retirement',pout($apply)===['STALE',0]&&$control->anchor()===$before['anchor']);
    }finally{pstop($apply);pstop($choose);$observer->close();}

    // Opposite ordering: actual source stage waits for writer, then cannot recreate retired original evidence.
    [$control,$capture,$first,$sidecar]=pfixture();[$plan,$before]=pplan($control);$pause=pd(PurposeFaultDb::class);$observer=pd();$worker=[];
    $stale=$capture;$stale['request_id']=wp_generate_uuid4();$stale['fingerprint']=hash('sha256','SYNTHETIC STALE PURPOSE');$stale['original_revision']=1;$stale['decision_version']=$first['receipt'];$stale['preference_expires_at']=$first['expires_at'];$stale['created_at']=$first['changed_at']+1;$stale['state']='STAGED';$stale['lead_id']='';$stale['event_id']='';
    $blocking=(int)$pause->get_var('SELECT CONNECTION_ID()');$pause->beforeDelete=function()use(&$worker,$stale,$sidecar,$observer,$blocking){$worker=pworker('stage-worker',['capture'=>$stale,'sidecar'=>$sidecar]);try{px('actual_purpose_stage_waits_for_full_writer_snapshot',pwait($observer,$worker[2],$blocking));}catch(Throwable $e){pstop($worker);throw$e;}};
    try{$result=pcntl($pause)->apply($plan,C::labAcknowledgement($plan),$before['anchor']);px('retired_original_not_resurrected_by_actual_purpose_store',pout($worker)===['RETIRED',0]&&$result['deleted_rows']===3&&B::digest($control->reviewSource()['snapshot'])===$plan['expected_after_hash']);}
    finally{pstop($worker);$pause->close();$observer->close();}
    $outbox=pr(['op'=>'snapshot']);px('receiver_remains_synthetic_and_schema_unchanged',count($outbox['headers'])===26&&count($outbox['rows'])>0);
    echo wp_json_encode(['phase'=>'purpose_selective_retention_integration','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'google_is_double'=>true,'production_acceptance'=>false,'reopen_authorized'=>false])."\n";
}finally{foreach($receiverPipes as$pipe)if(is_resource($pipe))fclose($pipe);$status=proc_close($receiverProcess);if($status!==0)throw new RuntimeException('Synthetic receiver exit unavailable');}
