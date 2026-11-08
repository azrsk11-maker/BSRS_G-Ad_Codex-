<?php
/** Real WordPress entry and SQL; synthetic pipe receiver with networking denied. */
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
$_SERVER['HTTPS']='on'; $_SERVER['SERVER_PORT']='443'; $_SERVER['REQUEST_METHOD']='POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/purpose/store.php';
require '/opt/lab/purpose/purpose-attribution.php';
require '/opt/lab/purpose/intake.php';
require '/opt/lab/receipt-recovery/receipt-recovery-wordpress.php';
require '/opt/lab/purpose-concurrency.php';
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);
define('BSRE_RECEIPT_STATUS_ENABLED',true);
define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4)); define('BSRE_ROUTING_ENABLED',true);
add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
add_action('rest_api_init','BSRE\\PurposeAttribution\\register_routes');
add_action('rest_api_init','BSRE\\ReceiptRecovery\\register_routes');
add_filter('rest_pre_dispatch','BSRE\\PurposeAttribution\\legacy_guard',10,3);
$checks=[];
function purpose_check(string $name,bool $ok):void{global $checks;if(!$ok)throw new RuntimeException('Purpose native check failed: '.$name);$checks[$name]=true;}
$owner=get_user_by('login','synthetic_owner'); wp_set_current_user($owner->ID);
purpose_check('additive_schema_installed',P\install_consent_storage());
purpose_check('original_consent_schema_still_v2',get_option('bsre_consent_schema_version')==='2');
$store=P\repository(); P\Runtime::$store=$store;
$privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'purpose-synthetic-privacy','post_title'=>'SYNTHETIC NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);
purpose_check('legacy_routing_ready',E\ready()); wp_set_current_user(0);
$bridge=proc_open(['node','/opt/lab/receiver-bridge.mjs','--receipt-status','/opt/lab/tracking-system/build-receipt-status-candidate.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$receiver);
purpose_check('receiver_started',is_resource($bridge));stream_set_timeout($receiver[1],15);
function purpose_receiver(array $value):array{global $receiver;$raw=wp_json_encode($value)."\n";if(fwrite($receiver[0],$raw)!==strlen($raw))throw new RuntimeException('Receiver write failed');fflush($receiver[0]);$line=fgets($receiver[1],1000000);if($line===false||!str_ends_with($line,"\n"))throw new RuntimeException('Receiver read failed');return json_decode($line,true,512,JSON_THROW_ON_ERROR);}
$loseAck=false;$receipts=[];$wireBodies=[];
add_filter('pre_http_request',function($pre,$args,$url)use(&$loseAck,&$receipts,&$wireBodies){
    purpose_check('outbound_destination_is_pipe_only',$url===BSRE_LEAD_RECEIVER_URL);
    $envelope=json_decode($args['body'],true,12,JSON_THROW_ON_ERROR);
    $response=purpose_receiver(['op'=>'post','raw'=>$args['body']]);
    if(isset($envelope['body'])){
        $body=$envelope['body'];$wire=json_decode($body,true,12,JSON_THROW_ON_ERROR);$id=$wire['request_id'];
        purpose_check('exact_wire_body_unchanged',($wireBodies[$id]??null)===$body);
        purpose_check('new_metadata_absent_from_receiver_wire',!str_contains($body,'purpose_')&&!str_contains($body,'decision_version')&&!str_contains($body,'utm_id')&&!str_contains($body,'google_campaign_id'));
        $receipts[$id]=$response;
        if($loseAck){$loseAck=false;return new WP_Error('SYNTHETIC_LOST_ACK');}
    }
    return ['headers'=>[],'body'=>wp_json_encode($response),'response'=>['code'=>200]];
},PHP_INT_MAX,3);
function purpose_request(string $route,string $body,array $headers=[]):WP_REST_Response{
    $request=new WP_REST_Request('POST','/bsre/v1/'.$route);
    foreach(array_merge(['origin'=>'https://blackswanrealestate.ae','sec-fetch-site'=>'same-origin','content-type'=>'application/json'], $headers)as$key=>$value)$request->set_header($key,$value);
    $request->set_body($body);return rest_do_request($request);
}
$client=proc_open(['node','/opt/lab/purpose-client-interop.mjs'],[0=>['pipe','r'],1=>['pipe','w'],2=>STDERR],$pipes);
purpose_check('client_started',is_resource($client));stream_set_timeout($pipes[1],20);
$current=[];$bodies=[];$scenarios=0;$complete=false;
while(($line=fgets($pipes[1],1000000))!==false){
    $message=json_decode($line,true,512,JSON_THROW_ON_ERROR);$op=$message['op']??'';
    if($op==='session'){
        $current=$message['scenario'];$scenarios++;$_SERVER['REMOTE_ADDR']='198.51.100.'.($scenarios+20);
        $_COOKIE=[E\COOKIE=>bin2hex(random_bytes(32))];
        $request=new WP_REST_Request('POST','/bsre/v1/consent/context');
        foreach(['origin'=>'https://blackswanrealestate.ae','sec-fetch-site'=>'same-origin','content-type'=>'application/json']as$key=>$value)$request->set_header($key,$value);
        $request->set_body('{}');$context=E\consent_context($request,$store)->get_data();
        $request->set_header('x-bsre-consent-csrf',$context['csrf_token']);
        $request->set_body(wp_json_encode(['analytics'=>$current['analytics'],'ad_measurement'=>$current['advertising'],'personalization'=>false,'notice_version'=>E\CONSENT_NOTICE_VERSION]));
        $snapshot=E\consent_update($request,$store)->get_data();
        purpose_check('real_choice_succeeds_'.$scenarios,($snapshot['known']??false)===true);
        $current['snapshot']=$snapshot;$current['choice_csrf']=$context['csrf_token'];
        $csrf=E\csrf_token($_COOKIE[E\COOKIE],time()-3,wp_salt('auth'));$current['csrf']=$csrf;
        $loseAck=$scenarios===4;
        $reply=['snapshot'=>$snapshot,'csrf'=>$csrf];
    }elseif($op==='request'){
        $path=parse_url($message['url'],PHP_URL_PATH);
        purpose_check('only_owned_endpoint',$message['url']==='https://blackswanrealestate.ae'.$path&&in_array($path,['/wp-json/bsre/v1/purpose-lead','/wp-json/bsre/v1/receipt-recovery/proof','/wp-json/bsre/v1/receipt-recovery/status'],true));
        if(str_ends_with($path,'/purpose-lead')){
            $envelope=json_decode($message['body'],true,12,JSON_THROW_ON_ERROR);$wire=json_decode($envelope['wire_body'],true,12,JSON_THROW_ON_ERROR);$id=$wire['request_id'];
            purpose_check('synthetic_contacts_only',str_starts_with($wire['name'],'SYNTHETIC purpose ')&&$wire['email']==='fixture@example.invalid');
            if($scenarios===1){
                $wrong=$wire;
                $wrong['request_id']=wp_generate_uuid4();
                $wrong['landing_page']='https://blackswanrealestate.ae/enquire/rent/';
                $invalid=$envelope;
                $invalid['wire_body']=wp_json_encode($wrong);
                $rejected=purpose_request('purpose-lead',wp_json_encode($invalid),$message['headers']);
                purpose_check('wrong_role_service_rejected_before_acceptance',$rejected->get_status()===400&&
                    ($rejected->get_data()['code']??null)==='VALIDATION_FAILED');
                $unexpected=$wpdb->get_var($wpdb->prepare("SELECT request_id FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$wrong['request_id']));
                purpose_check('wrong_role_service_creates_no_capture',$unexpected===null);
            }
            $wireBodies[$id]=$envelope['wire_body'];$bodies[$id]=$message['body'];$current['id']=$id;
        }
        $response=purpose_request(substr($path,strlen('/wp-json/bsre/v1/')),$message['body'],$message['headers']);
        $reply=['status'=>$response->get_status(),'body'=>$response->get_data()];
    }elseif($op==='inspect'){
        $id=$message['request_id'];purpose_check('inspect_current_request',$id===$current['id']);
        $row=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$id),ARRAY_A);
        if($scenarios===8) foreach(purpose_concurrency_test($current,$bodies[$id],$row)as$name=>$passed) purpose_check('concurrency_'.$name,$passed);
        P\assert_record($row);$saved=json_decode($row['purpose_json'],true,12,JSON_THROW_ON_ERROR);
        $values=['wire_hash_bound'=>$row['fingerprint']===hash('sha256',$wireBodies[$id]),'durable_ids_linked'=>$row['lead_id']===$receipts[$id]['lead_id']&&$row['event_id']===$receipts[$id]['event_id'],
            'four_slots_present'=>isset($saved['analytics'],$saved['advertising']),
            'analytics_capture_matches'=>$current['analytics']?($saved['analytics']['first']['parameters']['utm_source']==='FIRST'&&$saved['analytics']['last']['parameters']['utm_source']==='LATEST'):$saved['analytics']['first']===null,
            'advertising_capture_matches'=>$current['advertising']?($saved['advertising']['last']['parameters']['gclid']==='Exact_Click.A~9'):$saved['advertising']['first']===null];
        $same=purpose_request('purpose-lead',$bodies[$id],['x-bsre-csrf'=>$current['csrf'],'x-bsre-consent-decision'=>$current['snapshot']['decision_version'],'x-bsre-consent-retry'=>'1']);
        $values['unchanged_retry_same_receipt']=$same->get_status()===200&&$same->get_data()['lead_id']===$row['lead_id'];
        $changed=json_decode($bodies[$id],true,12,JSON_THROW_ON_ERROR);
        $changed['attribution']['analytics']['first']=null;$changed['attribution']['analytics']['last']=null;
        if(!$current['analytics']){$changed['attribution']['advertising']['first']=null;$changed['attribution']['advertising']['last']=null;}
        if(!$current['analytics']&&!$current['advertising']){$changed['wire_body']=str_replace('SYNTHETIC purpose','SYNTHETIC changed',$changed['wire_body']);}
        $conflict=purpose_request('purpose-lead',wp_json_encode($changed),['x-bsre-csrf'=>$current['csrf'],'x-bsre-consent-decision'=>$current['snapshot']['decision_version'],'x-bsre-consent-retry'=>'1']);
        $values['changed_sidecar_or_body_conflicts']=$conflict->get_status()===409;
        $downgrade=purpose_request('lead',$wireBodies[$id],['x-bsre-csrf'=>$current['csrf']]);
        $values['legacy_downgrade_conflicts']=$downgrade->get_status()===409;
        wp_set_current_user($owner->ID);$private=P\private_history($wpdb,$id,time());wp_set_current_user(0);
        $values['private_read_keeps_exact_ids']=!$current['advertising']||$private['advertising']['last']['parameters']->gclid==='Exact_Click.A~9';
        // Actual server choice withdrawal and regrant must not revive prior data.
        $request=new WP_REST_Request('POST','/bsre/v1/consent/update');
        foreach(['origin'=>'https://blackswanrealestate.ae','sec-fetch-site'=>'same-origin','content-type'=>'application/json','x-bsre-consent-csrf'=>$current['choice_csrf']]as$key=>$value)$request->set_header($key,$value);
        foreach([[false,false],[$current['analytics'],$current['advertising']]]as$flags){$request->set_body(wp_json_encode(['analytics'=>$flags[0],'ad_measurement'=>$flags[1],'personalization'=>false,'notice_version'=>E\CONSENT_NOTICE_VERSION]));E\consent_update($request,$store);}
        wp_set_current_user($owner->ID);$after=P\private_history($wpdb,$id,time());wp_set_current_user(0);
        $values['withdrawal_regrant_keeps_both_histories_denied']=$after['analytics']['first']===null&&$after['advertising']['first']===null;
        foreach($values as$name=>$passed)purpose_check($scenarios.'_'.$name,$passed);
        $reply=['checks'=>$values,'synthetic_capture'=>array_intersect_key($row,array_flip([
            'request_id','fingerprint','state','delivery_pending','uncertain','lead_id','event_id',
        ]))];
    }elseif($op==='complete'){$complete=true;$checks=array_merge($checks,$message['checks']);$reply=['ok'=>true];}
    else throw new RuntimeException('Unsupported purpose operation');
    $encoded=wp_json_encode($reply)."\n";fwrite($pipes[0],$encoded);fflush($pipes[0]);
    if($complete)break;
}
fclose($pipes[0]);fclose($pipes[1]);purpose_check('client_exit',proc_close($client)===0&&$complete&&$scenarios===20);
// The preserved receiver attempts at most five messages per outbox invocation.
// Drain the known twenty-row synthetic fixture in four bounded batches.
for ($batch = 1; $batch <= 4; $batch++) {
    $outbox = purpose_receiver(['op'=>'outbox']);
    purpose_check('outbox_batch_' . $batch, count($outbox['rows']) === 20
        && count($outbox['mail']) === $batch * 5 && count($outbox['headers']) === 26);
}
$recheck = purpose_receiver(['op'=>'outbox']);
purpose_check('outbox_recheck_has_no_duplicate_mail', count($recheck['mail']) === 20);
fclose($receiver[0]);fclose($receiver[1]);purpose_check('receiver_exit',proc_close($bridge)===0);
echo wp_json_encode(['phase'=>'purpose_client_wordpress_receiver','status'=>'PASS','checks'=>$checks,'synthetic_only'=>true,'browser_and_google_are_doubles'=>true,'retention_restore_accepted'=>false,'production_acceptance'=>false])."\n";
