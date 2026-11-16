<?php
declare(strict_types=1);
/** Fixed synthetic candidate only; does not activate the ordinary or production plugin. */
$mode=$argv[1]??'enforced';
if(count($argv)>2 || !in_array($mode,['enforced','inactive','missing-store','disabled','malformed'],true)) throw new RuntimeException('G3_FIXED_MODE_ONLY');
$isolation=[
    'cli'=>PHP_SAPI==='cli','non_root'=>function_exists('posix_geteuid') && posix_geteuid()!==0,
    'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
    'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
    'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
    'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
    'readonly_application'=>!is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g3/plugins'),
    'database_already_started'=>is_dir('/tmp/database') && file_exists('/tmp/bsre.sock'),
    'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach($isolation as $label=>$pass)if(!$pass)throw new RuntimeException('G3 runtime isolation failed: '.$label);
define('WP_ENVIRONMENT_TYPE','local');define('WP_PLUGIN_DIR','/opt/lab/g3/plugins');
define('BSRE_G3_ROUTE_CONTEXT_ENABLED',$mode!=='inactive');define('BSRE_G2_SHARED_REPOSITORY_ENABLED',$mode!=='missing-store');
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);define('BSRE_RETENTION_ADMISSION_ENABLED',$mode!=='disabled');
define('BSRE_RETENTION_ADMISSION_GENERATION',$mode==='malformed'?'bad':str_repeat('a',64));
define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',time()-2000);
define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));define('BSRE_ROUTING_ENABLED',true);
$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='POST';
require '/opt/wordpress/wp-load.php';require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
use BSRE\Enquiries as E;use BSRE\SharedRepository as G;use BSRE\RetentionAdmission as A;
if(DB_NAME!=='bsre_synthetic'||DB_HOST!=='localhost:/tmp/bsre.sock'||DB_USER!=='root'||DB_PASSWORD!==''
    || $wpdb->get_var('SELECT DATABASE()')!=='bsre_synthetic')throw new RuntimeException('G3_FIXED_DATABASE_REQUIRED');
add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
$owner=get_user_by('login','synthetic_owner');if(!$owner)throw new RuntimeException('G3_OWNER_REQUIRED');wp_set_current_user($owner->ID);
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$pages=E\ensure_drafts(false);foreach($pages['pages'] as $id)wp_update_post(['ID'=>$id,'post_status'=>'publish']);
$privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g3-synthetic-privacy-'.$mode,'post_title'=>'SYNTHETIC G3 NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);$wpdb->prefix='g3_'.str_replace('-','_',$mode).'_synthetic_';
E\install();if($mode!=='missing-store' && !G\migrate())throw new RuntimeException('G3_MIGRATION_FAILED');
$checks=[];$forwards=[];$apiCount=0;
function g3check(string $name,bool $pass):void{global $checks;if(!$pass||isset($checks[$name]))throw new RuntimeException('G3 native assertion failed: '.$name);$checks[$name]=true;}
g3check('original_wire_can_route_without_profile',E\ready());g3check('five_real_native_service_paths',count(E\live_paths())===5);
wp_set_current_user(0);$_COOKIE=[E\COOKIE=>bin2hex(random_bytes(32))];
function g3api(string $route,string $body='{}',array $headers=[]):WP_REST_Response{
    global $apiCount;$_SERVER['REMOTE_ADDR']='198.51.100.'.(++$apiCount+60);
    $request=new WP_REST_Request('POST','/bsre/v1/'.$route);
    foreach(array_merge(['origin'=>'https://blackswanrealestate.ae','sec-fetch-site'=>'same-origin','content-type'=>'application/json'],$headers) as $key=>$value)$request->set_header($key,$value);
    $request->set_body($body);return rest_do_request($request);
}
add_filter('pre_wp_mail',function(){throw new RuntimeException('G3_MAIL_FORBIDDEN');},PHP_INT_MAX);
if($mode!=='enforced'){
    add_filter('pre_http_request',function(){throw new RuntimeException('G3_NETWORK_FORBIDDEN');},PHP_INT_MAX);
    if($mode==='inactive'){
        $context=g3api('context');g3check('inactive_context_preserves_original',$context->get_status()===200 && !isset($context->get_data()['transport']));
        $routes=rest_get_server()->get_routes();g3check('inactive_base_callback_unchanged',$routes['/bsre/v1/lead'][0]['callback']==='BSRE\\Enquiries\\receive');
    }else{
        foreach(['context','lead','purpose-lead','receipt-recovery/proof','receipt-recovery/status'] as $route){
            $response=g3api($route);g3check('held_'.$route,$response->get_status()===503 && $response->get_data()['code']==='PROFILE_UNAVAILABLE');
        }
        $routes=rest_get_server()->get_routes();
        g3check('held_final_route_owner',str_starts_with($routes['/bsre/v1/lead'][0]['callback'],'BSRE\\ProfileTransport\\'));
    }
    echo wp_json_encode(['phase'=>'g3_route_context','mode'=>$mode,'checks'=>$checks,'runtime_isolation'=>$isolation,'forward_count'=>0])."\n";exit(0);
}
$bridge=proc_open(['node','/opt/lab/tracking-system/retention-admission-bridge.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
if(!is_resource($bridge))throw new RuntimeException('G3_RECEIVER_BRIDGE_FAILED');stream_set_timeout($pipes[1],10);
function g3receiver(array $message):array{global $pipes;$line=wp_json_encode($message)."\n";if(fwrite($pipes[0],$line)!==strlen($line)||!fflush($pipes[0]))throw new RuntimeException('G3_BRIDGE_WRITE_FAILED');$reply=fgets($pipes[1],100000);if($reply===false||!str_ends_with($reply,"\n"))throw new RuntimeException('G3_BRIDGE_READ_FAILED');return json_decode($reply,true,32,JSON_THROW_ON_ERROR);}
$gate=A\configuration();g3receiver(['op'=>'configure','properties'=>['RETENTION_ADMISSION_REQUIRED'=>'true','RETENTION_ADMISSION_GENERATION'=>$gate['generation'],'RETENTION_ADMISSION_AUDIENCE'=>$gate['audience'],'RETENTION_ADMISSION_ACTIVATED_AT'=>(string)$gate['activated_at']]]);
add_filter('pre_http_request',function($pre,$args,$url){global $forwards;if($url!==BSRE_LEAD_RECEIVER_URL)throw new RuntimeException('G3_FOREIGN_DESTINATION');$forwards[]=$args['body'];$reply=g3receiver(['op'=>'post','raw'=>$args['body']]);return ['headers'=>[],'body'=>wp_json_encode($reply),'response'=>['code'=>200]];},PHP_INT_MAX,3);
try{
    $context=g3api('context');$data=$context->get_data();
    g3check('context_exposes_only_reviewed_transport',$context->get_status()===200 && $data['transport']===['contract'=>'bsre-profile-transport-v1','purpose_endpoint'=>'https://blackswanrealestate.ae/wp-json/bsre/v1/purpose-lead','admission_required'=>true]);
    $routes=rest_get_server()->get_routes();foreach(['context','lead','purpose-lead','receipt-recovery/proof','receipt-recovery/status'] as $route)g3check('final_owner_'.$route,str_starts_with($routes['/bsre/v1/'.$route][0]['callback'],'BSRE\\ProfileTransport\\'));
    foreach(E\SERVICES as $slug=>$service)foreach(['lead','purpose-lead'] as $route){
        $name=$slug.'_'.$route;$_COOKIE=[E\COOKIE=>bin2hex(random_bytes(32))];$headers=['x-bsre-csrf'=>E\csrf_token($_COOKIE[E\COOKIE],time()-3,wp_salt('auth'))];
        $prepared=g3api('receipt-recovery/proof','{}',$headers)->get_data();g3check($name.'_proof_generated',isset($prepared['admission']) && $prepared['request_id']===$prepared['admission']['request_id']);
        $p=['request_id'=>$prepared['request_id'],'role'=>$service['role'],'name'=>'SYNTHETIC G3','phone'=>'+971500000000','email'=>'fixture@example.invalid','country'=>'UAE','area'=>'Synthetic','budget'=>'To discuss','timeline'=>['off-plan'=>'Within 1 month','resale'=>'Within 1 month','rent'=>'Immediate / move now','sell'=>'As soon as practical','let'=>'Vacant / available to discuss now'][$slug],'funding'=>'To discuss','property_type'=>'Apartment','property_details'=>in_array($slug,['sell','let'],true)?'SYNTHETIC identified property':'','authority'=>in_array($slug,['sell','let'],true)?'owner':'','contact_consent'=>true,'marketing_consent'=>false,'campaign'=>'SYNTHETIC','landing_page'=>'https://blackswanrealestate.ae/enquire/'.$slug.'/','website'=>'','started_at'=>(time()-5)*1000];
        $wire=wp_json_encode($p);$empty=['first'=>null,'last'=>null];$body=$route==='lead'?$wire:wp_json_encode(['version'=>1,'wire_body'=>$wire,'attribution'=>['version'=>1,'analytics'=>$empty,'advertising'=>$empty]]);
        $before=count($forwards);$missing=g3api($route,$body,$headers);g3check($name.'_missing_proof_no_forward',$missing->get_status()===503 && count($forwards)===$before);
        $proofHeaders=$headers+['x-bsre-admission'=>wp_json_encode($prepared['admission'])];$accepted=g3api($route,$body,$proofHeaders)->get_data();g3check($name.'_accepted',($accepted['accepted']??false)===true);
        $outer=json_decode(end($forwards),true,32,JSON_THROW_ON_ERROR);g3check($name.'_wire_preserved',$outer['body']===$wire && isset($outer['admission']));
        $retry=g3api($route,$body,$proofHeaders)->get_data();g3check($name.'_retry_same_receipt',$retry['lead_id']===$accepted['lead_id'] && $retry['event_id']===$accepted['event_id']);
        $row=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$p['request_id']),ARRAY_A);
        g3check($name.'_common_store_linked',is_array($row) && $row['lead_id']===$accepted['lead_id'] && $row['event_id']===$accepted['event_id'] && (int)$row['known']===0 && (int)$row['analytics']===0 && (int)$row['ad_measurement']===0);
        $status=g3api('receipt-recovery/status',wp_json_encode(['proof'=>$prepared['proof']]),$headers)->get_data();g3check($name.'_status_same_receipt',($status['status']??null)==='ACCEPTED' && ($status['reference']??null)===$accepted['lead_id'] && !isset($status['event_id']));
        if($route==='purpose-lead')g3check($name.'_legacy_conflict_preserved',g3api('lead',$wire,$proofHeaders)->get_status()===409);
    }
    $snapshot=g3receiver(['op'=>'snapshot']);g3check('exact_receiver_row_and_email_count',$snapshot['rows']===10 && $snapshot['mail']===10 && $snapshot['columns']===26);
    echo wp_json_encode(['phase'=>'g3_route_context','mode'=>$mode,'checks'=>$checks,'runtime_isolation'=>$isolation,'forward_count'=>count($forwards),'limits'=>'Actual isolated routes/storage and pinned receiver service doubles; no browser/provider/production acceptance.'])."\n";
}finally{fclose($pipes[0]);fclose($pipes[1]);if(proc_close($bridge)!==0)throw new RuntimeException('G3_BRIDGE_EXIT_FAILED');}
