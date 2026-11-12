<?php
declare(strict_types=1);
/** Actual route/store/provider integration; synthetic aging and receiver deletion only. */
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
$_SERVER['REQUEST_METHOD']='POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/retention-admission/store.php';
require '/opt/lab/purpose/purpose-attribution.php';
require '/opt/lab/retention-admission/intake.php';
require '/opt/lab/receipt-recovery/receipt-recovery-wordpress.php';
require '/opt/lab/retention-admission/retention-admission.php';
require_once __DIR__.'/fixtures.php';
require_once __DIR__.'/WpCaptureResource.php';
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
use BSRE\RetentionAdmission as A;
use BSRE\ClosedRetention as C;
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);
define('BSRE_RETENTION_ADMISSION_ENABLED',true);
define('BSRE_RETENTION_ADMISSION_GENERATION',str_repeat('a',64));
define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',time()-2000);
define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));
define('BSRE_ROUTING_ENABLED',true);
add_action('rest_api_init','BSRE\\PurposeAttribution\\register_routes');
add_action('rest_api_init','BSRE\\ReceiptRecovery\\register_routes');
add_action('rest_api_init','BSRE\\RetentionAdmission\\register_routes',1000);
$checks=[];$forwards=[];
function acCheck(string $name,bool $ok): void
{
    global $checks;
    if(!$ok)throw new RuntimeException('Admission capture native assertion failed: '.$name);
    $checks[$name]=true;
}
function acDenied(callable $operation,string $code): bool
{
    try{$operation();return false;}catch(C\Failure $error){return $error->getMessage()===$code;}
}
function acConnection(): C\LeaseBoundWpdb
{
    global $table_prefix;
    $db=new C\LeaseBoundWpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);
    $db->set_prefix($table_prefix);$db->prefix=C\WpCaptureResource::PREFIX;$db->suppress_errors(true);
    return $db;
}
$db=acConnection();$wpdb=$db;
$journal=new C\LabSqlJournal($db);$journal->install();
$owner=get_user_by('login','synthetic_owner');wp_set_current_user($owner->ID);
$privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'admission-capture-synthetic-privacy','post_title'=>'SYNTHETIC NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);
E\install();acCheck('actual_additive_27_column_schema_installed',P\install_consent_storage());
$store=new P\WpConsentRepository($db);P\Runtime::$store=$store;
$store->choose(str_repeat('e',64),['analytics'=>false,'ad_measurement'=>false],'SYNTHETIC_SHARED_NOTICE',time());
wp_set_current_user(0);
$bridge=proc_open(['node','/opt/lab/tracking-system/retention-admission-bridge.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
acCheck('isolated_actual_source_receiver_started',is_resource($bridge));stream_set_timeout($pipes[1],10);
function acReceiver(array $value): array
{
    global $pipes;
    $line=wp_json_encode($value)."\n";
    if(fwrite($pipes[0],$line)!==strlen($line)||!fflush($pipes[0]))throw new RuntimeException('Synthetic admission pipe write failed');
    $reply=fgets($pipes[1],100000);
    if(!is_string($reply)||!str_ends_with($reply,"\n"))throw new RuntimeException('Synthetic admission pipe timed out');
    return json_decode($reply,true,32,JSON_THROW_ON_ERROR);
}
$gate=A\configuration();
acReceiver(['op'=>'configure','properties'=>['RETENTION_ADMISSION_REQUIRED'=>'true',
    'RETENTION_ADMISSION_GENERATION'=>$gate['generation'],'RETENTION_ADMISSION_AUDIENCE'=>$gate['audience'],
    'RETENTION_ADMISSION_ACTIVATED_AT'=>(string)$gate['activated_at']]]);
add_filter('pre_http_request',function($pre,$args,$url){
    global $forwards;
    acCheck('relay_destination_is_synthetic_only',$url===BSRE_LEAD_RECEIVER_URL);
    $forwards[]=$args['body'];
    $reply=acReceiver(['op'=>'post','raw'=>$args['body']]);
    return ['headers'=>[],'body'=>wp_json_encode($reply),'response'=>['code'=>200]];
},PHP_INT_MAX,3);
function acHttpsHome($url,$path): string
{
    return 'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/'));
}
$apiCalls=0;
function acApi(string $route,string $body,array $headers=[]): WP_REST_Response
{
    global $apiCalls;
    $_SERVER['REMOTE_ADDR']='198.51.100.'.(++$apiCalls+100);
    $request=new WP_REST_Request('POST','/bsre/v1/'.$route);
    foreach(array_merge(['origin'=>'https://blackswanrealestate.ae','sec-fetch-site'=>'same-origin','content-type'=>'application/json'],$headers)as$key=>$value)$request->set_header($key,$value);
    $request->set_body($body);
    // Existing route fixture requires its HTTPS site. No provider runs with this filter installed.
    $previous = array_intersect_key($_SERVER, array_flip(['HTTPS','SERVER_PORT']));
    $_SERVER['HTTPS']='on'; $_SERVER['SERVER_PORT']='443';
    add_filter('home_url','acHttpsHome',10,2);
    try{return rest_do_request($request);}finally{
        remove_filter('home_url','acHttpsHome',10);
        foreach(['HTTPS','SERVER_PORT']as$key){
            if(array_key_exists($key,$previous))$_SERVER[$key]=$previous[$key];
            else unset($_SERVER[$key]);
        }
    }
}
$_COOKIE=[E\COOKIE=>bin2hex(random_bytes(32))];
$headers=['x-bsre-csrf'=>E\csrf_token($_COOKIE[E\COOKIE],time()-3,wp_salt('auth'))];
$prepared=acApi('receipt-recovery/proof','{}',$headers)->get_data();
acCheck('guarded_route_issued_server_uuid',isset($prepared['admission'])&&$prepared['request_id']===$prepared['admission']['request_id']);
acCheck('caller_cannot_prepare_old_uuid',acApi('receipt-recovery/proof',wp_json_encode(['request_id'=>$prepared['request_id']]),$headers)->get_status()===400);
acCheck('route_ssl_context_restored_before_provider',!is_ssl()&&home_url()==='http://bsre.invalid');
$provider=new C\WpCaptureResource($db,$journal,$store);
acCheck('actual_selected_store_and_all_routes_enforced',A\readback()['routes_installed']&&A\readback()['store_installed']);
$other=acConnection();
acCheck('provider_cannot_borrow_other_store_connection',acDenied(fn()=>new C\WpCaptureResource($other,new C\LabSqlJournal($other),$store),'CAPTURE_CONNECTION_CONFLICT'));
P\Runtime::$store=new P\WpConsentRepository($other);
acCheck('runtime_store_replacement_rejected',acDenied(fn()=>$provider->read($prepared['request_id']),'CAPTURE_CONNECTION_CONFLICT'));
P\Runtime::$store=$store;
$hideLead=static function(array $routes): array { unset($routes['/bsre/v1/lead']); return $routes; };
add_filter('rest_endpoints',$hideLead,PHP_INT_MAX);
try{
    acCheck('missing_actual_route_rejected_before_provider_sql',acDenied(fn()=>$provider->read($prepared['request_id']),'CAPTURE_ADMISSION_UNVERIFIED'));
}finally{remove_filter('rest_endpoints',$hideLead,PHP_INT_MAX);}
acCheck('original_route_registry_restored_after_fault',A\readback()['routes_installed']===true);
add_filter('home_url','acHttpsHome',10,2);
try{acCheck('https_route_fixture_cannot_open_provider',acDenied(fn()=>$provider->read($prepared['request_id']),'CAPTURE_ISOLATED_LAB_ONLY'));}
finally{remove_filter('home_url','acHttpsHome',10);}
$payload=['request_id'=>$prepared['request_id'],'role'=>'tenant','name'=>'SYNTHETIC capture admission',
    'phone'=>'+971500000000','email'=>'fixture@example.invalid','country'=>'UAE','area'=>'Synthetic',
    'budget'=>'To discuss','timeline'=>'Immediate / move now','funding'=>'To discuss','property_type'=>'Apartment',
    'property_details'=>'','authority'=>'','contact_consent'=>true,'marketing_consent'=>false,'campaign'=>'SYNTHETIC',
    'landing_page'=>'https://blackswanrealestate.ae/enquire/rent/','website'=>'','started_at'=>(time()-5)*1000];
$wire=wp_json_encode($payload);$withProof=$headers+['x-bsre-admission'=>wp_json_encode($prepared['admission'])];
$before=count($forwards);
acCheck('unproved_unknown_stops_before_relay',acApi('lead',$wire,$headers)->get_status()!==200&&count($forwards)===$before);
$accepted=acApi('lead',$wire,$withProof)->get_data();
acCheck('actual_legacy_route_stages_and_links',($accepted['accepted']??false)===true);
$known=acApi('lead',$wire,$headers)->get_data();
acCheck('known_retry_keeps_stable_receipt_without_proof',($known['lead_id']??null)===$accepted['lead_id']&&($known['event_id']??null)===$accepted['event_id']);
$expired=A\sign_new_request($payload['request_id'],$_COOKIE[E\COOKIE],BSRE_LEAD_HMAC_SECRET,$gate,time()-1000);
$expiredHeaders=$headers+['x-bsre-admission'=>wp_json_encode($expired),'x-bsre-consent-retry'=>'1'];
$knownExpired=acApi('lead',$wire,$expiredHeaders)->get_data();
acCheck('known_expired_proof_keeps_stable_receipt',($knownExpired['lead_id']??null)===$accepted['lead_id']);
$changed=$payload;$changed['area']='Changed';
acCheck('actual_known_body_conflict_rejected',acApi('lead',wp_json_encode($changed),$withProof)->get_status()===409);
$table=C\WpCaptureResource::PREFIX.'bsre_consent_captures';
function acClosure(array $accepted,string $request): array
{
    $closure=C\fixture()['closure'];$closure['closure_id']=$request;$closure['request_id']=$request;
    $closure['lead_id']=$accepted['lead_id'];$closure['event_id']=$accepted['event_id'];
    return $closure;
}
$closure=acClosure($accepted,$payload['request_id']);$journal->putClosure($closure);
$locked=fn(callable $operation)=>$journal->locked($closure['closure_id'],$operation);
acCheck('fresh_capture_cannot_borrow_historical_due_closure',
    $locked(fn()=>acDenied(fn()=>$provider->read($payload['request_id']),'CAPTURE_CLOSURE_TIME_CONFLICT')));
// Explicit aging simulates elapsed business time; it supplies no genuine closure evidence.
acCheck('synthetic_elapsed_time_fixture_aged_before_review',$db->query($db->prepare("UPDATE {$table} SET created_at=%d,purpose_json=NULL WHERE request_id=%s",
    strtotime($closure['accepted_at_utc']),$payload['request_id']))===1);
$legacy=$locked(fn()=>$provider->read($payload['request_id']));
acCheck('legacy_v0_null_row_bound_by_actual_provider',$legacy!==null);
$beforeShared=[];
foreach(['state','history']as$part)$beforeShared[$part]=$db->get_results('SELECT * FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_'.$part.' ORDER BY '.($part==='state'?'subject_key':'receipt'),ARRAY_A);
$locked(fn()=>$provider->removeExact($legacy));
acCheck('actual_provider_deleted_exact_nullable_legacy_capture',$locked(fn()=>$provider->read($payload['request_id']))===null);
acReceiver(['op'=>'purge_synthetic','request_id'=>$payload['request_id']]);
$before=count($forwards);$replay=acApi('lead',$wire,$expiredHeaders);
acCheck('expired_replay_stops_before_relay_after_actual_delete',$replay->get_status()!==200&&count($forwards)===$before);
acCheck('expired_replay_cannot_recreate_capture',$locked(fn()=>$provider->inventory($payload['request_id']))===[]);
$oldEnvelope=E\envelope($wire,BSRE_LEAD_HMAC_SECRET,(int)floor(microtime(true)*1000));$oldEnvelope['admission']=$expired;
acCheck('actual_receiver_rejects_direct_expired_replay',acReceiver(['op'=>'post','raw'=>wp_json_encode($oldEnvelope)])['code']==='ADMISSION_REQUIRED');
$next=acApi('receipt-recovery/proof','{}',$headers)->get_data();
$nextHeaders=$headers+['x-bsre-admission'=>wp_json_encode($next['admission'])];
$before=count($forwards);
acCheck('fresh_other_uuid_proof_cannot_revive_old_request',acApi('lead',$wire,$nextHeaders)->get_status()!==200&&count($forwards)===$before);
$payload['request_id']=$next['request_id'];$purposeWire=wp_json_encode($payload);
$empty=['first'=>null,'last'=>null];
$purposeBody=wp_json_encode(['version'=>1,'wire_body'=>$purposeWire,'attribution'=>['version'=>1,'analytics'=>$empty,'advertising'=>$empty]]);
$purposeAccepted=acApi('purpose-lead',$purposeBody,$nextHeaders)->get_data();
acCheck('fresh_other_request_accepted_on_actual_purpose_route',($purposeAccepted['accepted']??false)===true);
$purposeClosure=acClosure($purposeAccepted,$next['request_id']);$journal->putClosure($purposeClosure);
acCheck('purpose_elapsed_time_fixture_aged_before_review',$db->query($db->prepare("UPDATE {$table} SET created_at=%d WHERE request_id=%s",strtotime($purposeClosure['accepted_at_utc']),$next['request_id']))===1);
$purposeLocked=fn(callable $operation)=>$journal->locked($purposeClosure['closure_id'],$operation);
$purposeBinding=$purposeLocked(fn()=>$provider->read($next['request_id']));
$purposeRow=$db->get_row($db->prepare("SELECT * FROM {$table} WHERE request_id=%s",$next['request_id']),ARRAY_A);
acCheck('all_27_actual_purpose_columns_bound',count($purposeRow)===27&&(int)$purposeRow['purpose_version']===1&&$purposeBinding!==null);
$changedJson=str_replace('"version":1','"version":1,"synthetic_change":true',$purposeRow['purpose_json']);
$changedHash=hash('sha256',$purposeRow['fingerprint']."\n".$purposeRow['purpose_hash']."\n".$changedJson);
acCheck('synthetic_purpose_row_change_committed',$db->query($db->prepare("UPDATE {$table} SET purpose_json=%s,purpose_record_hash=%s WHERE request_id=%s",$changedJson,$changedHash,$next['request_id']))===1);
acCheck('valid_changed_purpose_bytes_invalidate_exact_review',
    $purposeLocked(fn()=>acDenied(fn()=>$provider->removeExact($purposeBinding),'CAPTURE_BINDING_CHANGED')));
acCheck('original_purpose_bytes_restored_for_original_plan',$db->query($db->prepare("UPDATE {$table} SET purpose_json=%s,purpose_record_hash=%s WHERE request_id=%s",$purposeRow['purpose_json'],$purposeRow['purpose_record_hash'],$next['request_id']))===1);
$purposeLocked(fn()=>$provider->removeExact($purposeBinding));
acCheck('actual_provider_deleted_exact_purpose_row',$purposeLocked(fn()=>$provider->read($next['request_id']))===null);
acReceiver(['op'=>'purge_synthetic','request_id'=>$next['request_id']]);
$expiredPurpose=A\sign_new_request($next['request_id'],$_COOKIE[E\COOKIE],BSRE_LEAD_HMAC_SECRET,$gate,time()-1000);
$before=count($forwards);
acCheck('actual_purpose_route_blocks_deleted_expired_replay',acApi('purpose-lead',$purposeBody,$headers+['x-bsre-admission'=>wp_json_encode($expiredPurpose)])->get_status()!==200&&count($forwards)===$before);
foreach(['state','history']as$part){
    $after=$db->get_results('SELECT * FROM '.C\WpCaptureResource::PREFIX.'bsre_consent_'.$part.' ORDER BY '.($part==='state'?'subject_key':'receipt'),ARRAY_A);
    acCheck('shared_consent_'.$part.'_preserved',$after===$beforeShared[$part]);
}
$snapshot=acReceiver(['op'=>'snapshot']);
acCheck('no_receiver_recreation_or_mail',$snapshot['rows']===0&&$snapshot['mail']===0&&$snapshot['columns']===26);
fclose($pipes[0]);fclose($pipes[1]);acCheck('isolated_receiver_finished',proc_close($bridge)===0);
echo json_encode(['phase'=>'admission_capture_native','checks'=>$checks,'provider'=>'Actual source-derived admission store, guarded WordPress routes and MariaDB capture provider',
    'synthetic_data_only'=>true,'business_time_aging'=>'Explicit synthetic SQL fixture only','genuine_closure_evidence'=>false,
    'receiver_deletion'=>'Synthetic fixture operation, not provider acceptance','real_restore_acceptance'=>'HELD',
    'durable_absence_claimed'=>false,'production_authorized'=>false],JSON_THROW_ON_ERROR)."\n";
