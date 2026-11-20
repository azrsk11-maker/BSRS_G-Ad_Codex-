<?php
declare(strict_types=1);
/** Prepared fixed isolated real-WordPress test. Synthetic identities only; no browser/provider acceptance. */
$isolation=[
    'cli'=>PHP_SAPI==='cli' && count($argv)===1,
    'non_root'=>function_exists('posix_geteuid') && posix_geteuid()!==0,
    'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
    'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
    'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
    'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
    'readonly_application'=>!is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g34/plugins'),
    'database_already_started'=>is_dir('/tmp/database') && file_exists('/tmp/bsre.sock'),
    'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach($isolation as $label=>$pass)if(!$pass)throw new RuntimeException('G4 runtime isolation failed: '.$label);
define('WP_ENVIRONMENT_TYPE','local');define('WP_PLUGIN_DIR','/opt/lab/g34/plugins');
define('BSRE_G3_ROUTE_CONTEXT_ENABLED',true);define('BSRE_G2_SHARED_REPOSITORY_ENABLED',true);
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);define('BSRE_RETENTION_ADMISSION_ENABLED',true);
define('BSRE_RETENTION_ADMISSION_GENERATION',str_repeat('a',64));define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',time()-2000);
define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));define('BSRE_ROUTING_ENABLED',true);
$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='GET';$_SERVER['REQUEST_URI']='/enquire/';
require '/opt/wordpress/wp-load.php';require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
use BSRE\Enquiries as E;use BSRE\SharedRepository as G;use BSRE\NativeTracking\NativePageContext as N;
if(DB_NAME!=='bsre_synthetic'||DB_HOST!=='localhost:/tmp/bsre.sock'||DB_USER!=='root'||DB_PASSWORD!=='')throw new RuntimeException('G4_FIXED_DATABASE_REQUIRED');
add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
add_filter('pre_http_request',function(){throw new RuntimeException('G4_NETWORK_FORBIDDEN');},PHP_INT_MAX);
add_filter('pre_wp_mail',function(){throw new RuntimeException('G4_MAIL_FORBIDDEN');},PHP_INT_MAX);
$checks=[];$readQueries=0;
function g4check(string $name,bool $pass):void{
    global $checks;
    if(isset($checks[$name]))throw new RuntimeException('G4 duplicate check: '.$name);
    $checks[$name]=$pass;file_put_contents('/tmp/g4-native-context-progress.json',json_encode($checks,JSON_THROW_ON_ERROR));
    if(!$pass)throw new RuntimeException('G4 native assertion failed: '.$name);
}
function g4query(int $id):void{
    $GLOBALS['wp_query']=new WP_Query(['page_id'=>$id,'post_type'=>'page']);$GLOBALS['wp_the_query']=$GLOBALS['wp_query'];
    $_SERVER['REQUEST_URI']=parse_url((string)get_permalink($id),PHP_URL_PATH) ?: '/';
}
function g4read(callable $operation){
    $filter=static function(string $sql):string{global $readQueries;$readQueries++;if(!preg_match('/^\s*(SELECT|SHOW)\b/i',$sql))throw new RuntimeException('G4_CONTEXT_WRITE_FORBIDDEN');return $sql;};
    add_filter('query',$filter,PHP_INT_MAX);try{return $operation();}finally{remove_filter('query',$filter,PHP_INT_MAX);}
}
function g4invalid(array $value):bool{try{new N($value);return false;}catch(InvalidArgumentException $e){return true;}}
$owner=get_user_by('login','synthetic_owner');if(!$owner)throw new RuntimeException('G4_OWNER_REQUIRED');wp_set_current_user($owner->ID);
g4check('port_loaded_by_selected_g34_bootstrap',class_exists(N::class,false) && WP_PLUGIN_DIR==='/opt/lab/g34/plugins');
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$hubSource=E\owned_parent_source('hub');g4check('packaged_hub_and_guard_coherent',is_string($hubSource) && hash('sha256',$hubSource)===E\OWNED_HUB_SHA256);
// Prior isolated phases share the fixed synthetic core tables. Preserve their rows and consent data.
// Baseline may have removed its search fixture; G3 may instead own /enquire/ at another native ID.
$priorHub=get_page_by_path('enquire',OBJECT,'page');$fixedHub=get_post(E\OWNED_HUB_PAGE_ID);
$existingServices=get_option('bsre_draft_pages',[]);$priorHubId=$priorHub instanceof WP_Post ? $priorHub->ID : 0;
if(!is_array($existingServices))throw new RuntimeException('G4_SYNTHETIC_REGISTRY_RECONCILIATION_REQUIRED');
if($fixedHub!==null && (!($fixedHub instanceof WP_Post) || $fixedHub->ID!==$priorHubId))throw new RuntimeException('G4_FIXED_HUB_COLLISION');
if($priorHub!==null){
    if(!($priorHub instanceof WP_Post) || $priorHub->post_type!=='page' || get_page_uri($priorHubId)!=='enquire'
        || get_post_meta($priorHubId,'_bsre_parent',true)!=='1' || $priorHub->post_password!==''
        || !in_array($priorHub->post_status,['draft','publish'],true))throw new RuntimeException('G4_KNOWN_SYNTHETIC_HUB_REQUIRED');
    $registeredParent=E\managed_native_page_id(get_option('bsre_parent_draft',0));
    if($registeredParent!==$priorHubId && !($priorHubId===E\OWNED_HUB_PAGE_ID && $registeredParent===0 && $priorHub->post_title==='Synthetic discovery fixture hub'))throw new RuntimeException('G4_KNOWN_SYNTHETIC_HUB_REQUIRED');
    foreach($existingServices as $slug=>$id){
        $id=E\managed_native_page_id($id);
        if(!isset(E\SERVICES[$slug]) || !$id || get_post_type($id)!=='page' || get_post_meta($id,'_bsre_service',true)!==$slug
            || E\managed_native_page_id(get_post_field('post_parent',$id,'raw'))!==$priorHubId || get_page_uri($id)!=='enquire/'.$slug
            || get_post_field('post_password',$id,'raw')!=='' || !in_array(get_post_status($id),['draft','publish'],true))throw new RuntimeException('G4_KNOWN_SYNTHETIC_SERVICE_REQUIRED');
    }
}elseif($existingServices!==[] || E\managed_native_page_id(get_option('bsre_parent_draft',0))!==0)throw new RuntimeException('G4_ORPHAN_SYNTHETIC_REGISTRY');
g4check('known_synthetic_native_fixture_reconciled',true);
// Preserve a differently numbered G3 hub as a separate row. No deletion or identity rewrite is used.
if($priorHubId && $priorHubId!==E\OWNED_HUB_PAGE_ID){
    $retainedSlug='g4-prior-synthetic-enquire-'.$priorHubId;
    if(get_page_by_path($retainedSlug,OBJECT,'page')!==null)throw new RuntimeException('G4_RETAINED_HUB_COLLISION');
    $renamed=wp_update_post(['ID'=>$priorHubId,'post_name'=>$retainedSlug],true);
    if(is_wp_error($renamed) || $renamed!==$priorHubId || get_post($priorHubId)===null)throw new RuntimeException('G4_RETAINED_HUB_UNCONFIRMED');
}
$hubData=['post_type'=>'page','post_status'=>'publish','post_name'=>'enquire','post_content'=>$hubSource,'meta_input'=>['_bsre_parent'=>'1']];
if($fixedHub instanceof WP_Post){$hubData['ID']=$fixedHub->ID;$hub=wp_update_post(wp_slash($hubData),true);}
else{$hubData['import_id']=E\OWNED_HUB_PAGE_ID;$hubData['post_title']='SYNTHETIC G4 enquiry hub';$hub=wp_insert_post(wp_slash($hubData),true);}
g4check('actual_native_hub_saved_exactly',!is_wp_error($hub) && $hub===E\OWNED_HUB_PAGE_ID && get_post_field('post_content',$hub,'raw')===$hubSource);
$services=[];
foreach(E\SERVICES as $slug=>$service){
    $existingId=E\managed_native_page_id($existingServices[$slug]??null);
    if($existingId){$id=wp_update_post(['ID'=>$existingId,'post_parent'=>$hub,'post_status'=>'publish'],true);}
    else{
        if(get_page_by_path('enquire/'.$slug,OBJECT,'page')!==null)throw new RuntimeException('G4_UNREGISTERED_SERVICE_COLLISION');
        $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_parent'=>$hub,'post_name'=>$slug,'post_title'=>'SYNTHETIC G4 '.$slug,'post_content'=>'SYNTHETIC NATIVE FIXTURE','meta_input'=>['_bsre_service'=>$slug]],true);
    }
    if(is_wp_error($id))throw new RuntimeException('G4_SERVICE_FIXTURE_FAILED');$services[$slug]=$id;
}
g4check('existing_synthetic_service_ids_preserved',array_diff_assoc(array_map('intval',$existingServices),$services)===[]);
g4check('prior_synthetic_hub_row_preserved',$priorHubId===0 || get_post($priorHubId) instanceof WP_Post);
update_option('bsre_parent_draft',$hub,false);update_option('bsre_draft_pages',$services,false);
$public=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g4-synthetic-contact','post_title'=>'SYNTHETIC G4 public contact'],true);
$unreviewed=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g4-unreviewed','post_title'=>'SYNTHETIC UNREVIEWED'],true);
if(is_wp_error($public)||is_wp_error($unreviewed))throw new RuntimeException('G4_PUBLIC_FIXTURE_FAILED');
$privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g4-synthetic-privacy','post_title'=>'SYNTHETIC G4 NOTICE'],true);
if(is_wp_error($privacy))throw new RuntimeException('G4_PRIVACY_FIXTURE_FAILED');define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);
$registry=['schema'=>1,'revision'=>'SYNTHETIC-G4-v2','catalog'=>['campaign_key'=>['BSRE-C0001'],'landing_page_id'=>['BSRE-LP0001'],'page_version'=>['0.0.1'],'page_family'=>['TEST'],'language'=>['en']],
    'pages'=>[['native_page_id'=>$public,'page_path'=>'/g4-synthetic-contact/','page_context'=>['campaign_key'=>'BSRE-C0001','landing_page_id'=>'BSRE-LP0001','page_version'=>'0.0.1','page_family'=>'TEST','language'=>'en'],
        'forms'=>['BSRE-TEST-ENQUIRY'],'ctas'=>[['cta_id'=>'BSRE-TEST-HERO-PHONE','cta_type'=>'phone','cta_position'=>'hero','destination_key'=>'TEST_PHONE']]]]];
define('BSRE_NATIVE_TRACKING_REGISTRY',$registry);$port=N::wordpress();
$wpdb->prefix='g4_context_synthetic_';E\install();g4check('actual_g2_migration_for_selected_g3_profile',G\migrate());
wp_set_current_user(0);
foreach(E\SERVICES as $slug=>$service){
    g4query($services[$slug]);$scope=['kind'=>'service','slug'=>$slug,'path'=>'/enquire/'.$slug.'/'];
    $binding=g4read(fn()=>E\owned_parent_binding($scope));$context=g4read(fn()=>$port->current());
    g4check('actual_owned_binding_'.$slug,$binding['mode']==='live' && $binding['id']===$services[$slug]);
    g4check('trusted_native_service_'.$slug,$context!==null && $context['page_path']===$scope['path'] && $context['role']===$service['role'] && (array)$context['page_context']===[]);
}
g4query($hub);g4check('actual_owned_hub_binding',g4read(fn()=>E\owned_parent_binding(['kind'=>'hub','slug'=>'','path'=>'/enquire/']))['mode']==='live');
g4check('trusted_native_hub',g4read(fn()=>$port->current())['page_path']==='/enquire/');
g4query($public);$context=g4read(fn()=>$port->current());
g4check('reviewed_public_native_page',$context!==null && $context['page_path']==='/g4-synthetic-contact/' && $context['role']==='unknown' && $context['page_context']->campaign_key==='BSRE-C0001');
g4check('stable_form_and_cta_ids',g4read(fn()=>$port->component('form','BSRE-TEST-ENQUIRY'))===['form_id'=>'BSRE-TEST-ENQUIRY'] && g4read(fn()=>$port->component('cta','BSRE-TEST-HERO-PHONE'))===$registry['pages'][0]['ctas'][0]);
g4check('unknown_components_fail_closed',g4read(fn()=>$port->component('form','BSRE-UNKNOWN'))===null && g4read(fn()=>$port->component('cta','BSRE-UNKNOWN'))===null);
$_GET=['campaign_key'=>'BSRE-C9999','email'=>'PRIVATE_TEST@example.invalid','native_page_id'=>$unreviewed];$_POST=['campaign'=>'PRIVATE_TEST','page_path'=>'/arbitrary/'];$_SERVER['REQUEST_URI']='/g4-synthetic-contact/?email=PRIVATE_TEST%40example.invalid&campaign_key=BSRE-C9999';
$after=g4read(fn()=>$port->current());g4check('query_and_submitted_metadata_ignored',wp_json_encode($after)===wp_json_encode($context) && !str_contains(wp_json_encode($after),'PRIVATE_TEST') && !str_contains(wp_json_encode($after),'C9999'));
g4query($unreviewed);g4check('actual_unreviewed_page_held',g4read(fn()=>$port->current())===null);
g4query($public);g4check('metadata_rehydrates_for_current_query',wp_json_encode(g4read(fn()=>$port->current()))===wp_json_encode($context));
$changed=$registry;$changed['revision']='SYNTHETIC-G4-v3';$updated=new N($changed);g4check('new_reviewed_server_config_rehydrates',g4read(fn()=>$updated->current())['registry_revision']==='SYNTHETIC-G4-v3');
$stale=$registry;$stale['pages'][0]['page_path']='/g4-stale-route/';g4check('stale_reviewed_path_held',g4read(fn()=>(new N($stale))->current())===null);
wp_update_post(['ID'=>$public,'post_status'=>'draft']);g4query($public);g4check('actual_draft_page_held',g4read(fn()=>$port->current())===null);wp_update_post(['ID'=>$public,'post_status'=>'publish']);g4query($public);
$GLOBALS['wp_query']->is_preview=true;g4check('preview_page_held',g4read(fn()=>$port->current())===null);$GLOBALS['wp_query']->is_preview=false;
wp_update_post(['ID'=>$public,'post_password'=>'SYNTHETIC_PASSWORD']);g4query($public);g4check('password_page_held',g4read(fn()=>$port->current())===null);wp_update_post(['ID'=>$public,'post_password'=>'']);
$_SERVER['HTTPS']='off';$_SERVER['SERVER_PORT']='80';g4query($public);g4check('http_context_held',g4read(fn()=>$port->current())===null);$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';
update_post_meta($services['off-plan'],'_bsre_service','resale');g4query($services['off-plan']);g4check('actual_service_registry_meta_conflict_held',g4read(fn()=>$port->current())===null);update_post_meta($services['off-plan'],'_bsre_service','off-plan');
$corrupt=$services;$corrupt['off-plan']=(string)$services['off-plan'].'x';update_option('bsre_draft_pages',$corrupt,false);g4query($services['off-plan']);g4check('corrupt_native_registry_identity_held',g4read(fn()=>$port->current())===null);update_option('bsre_draft_pages',$services,false);
wp_update_post(['ID'=>$hub,'post_content'=>'SYNTHETIC UNREVIEWED HUB CHANGE']);g4query($hub);g4check('actual_hub_body_guard_preserved',g4read(fn()=>$port->current())===null);wp_update_post(wp_slash(['ID'=>$hub,'post_content'=>$hubSource]));
$bad=$registry;$bad['pages'][0]['page_context']['email']='PRIVATE_TEST@example.invalid';g4check('pii_extra_metadata_rejected',g4invalid($bad));
$bad=$registry;$bad['catalog']['property_id']=['PRIVATE_TEST@example.invalid'];g4check('pii_catalog_value_rejected',g4invalid($bad));
$bad=$registry;$bad['pages'][0]['page_context']['page_family']='UNREVIEWED';g4check('unreviewed_catalog_value_rejected',g4invalid($bad));
$bad=$registry;$bad['pages'][0]['page_path']='/PRIVATE_TEST%40example.invalid/';g4check('encoded_pii_path_rejected',g4invalid($bad));
$bad=$registry;unset($bad['pages'][0]['page_context']['landing_page_id']);g4check('partial_campaign_identity_rejected',g4invalid($bad));
$bad=$registry;$bad['pages'][0]['ctas'][0]['destination_url']='tel:+971500000000';g4check('arbitrary_cta_destination_rejected',g4invalid($bad));
$bad=$registry;$bad['pages'][0]['page_context']['attribution']=['first'=>'PRIVATE_TEST'];g4check('private_history_cannot_enter_public_metadata',g4invalid($bad));
g4check('no_query_time_writes',$readQueries>0);
echo wp_json_encode(['phase'=>'g4_native_page_context','status'=>'SYNTHETIC_NATIVE_ONLY','checks'=>$checks,'runtime_isolation'=>$isolation,'readonly_context_sql_queries'=>$readQueries,'network_calls'=>0,'provider_events'=>0,'public_page_fixture'=>'SYNTHETIC_ONLY','limits'=>'Actual isolated WP_Query/native ownership and server metadata only; not browser/TLS/provider/human acceptance.'])."\n";
