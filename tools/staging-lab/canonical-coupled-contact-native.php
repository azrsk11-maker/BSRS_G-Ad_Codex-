<?php
declare(strict_types=1);
/** Fixed synthetic G36 page ABI proof. Each mode is a fresh WordPress request/process. */
$mode=$argv[1]??'';$modes=['hub','off-plan','resale','rent','sell','let'];
if(count($argv)!==2 || !in_array($mode,$modes,true))throw new RuntimeException('G36_FIXED_CONTACT_MODE_REQUIRED');
$isolation=[
    'cli'=>PHP_SAPI==='cli','non_root'=>function_exists('posix_geteuid') && posix_geteuid()!==0,
    'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
    'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
    'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
    'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
    'readonly_application'=>!is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g36'),
    'database_already_started'=>is_dir('/tmp/database') && file_exists('/tmp/bsre.sock'),
    'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach($isolation as $pass)if(!$pass)throw new RuntimeException('G36_CONTACT_ISOLATION_REQUIRED');
$checks=[];$progress='/tmp/g36_contact_'.$mode.'_progress.json';
if(file_exists($progress)||is_link($progress))throw new RuntimeException('G36_FRESH_CONTACT_PROGRESS_REQUIRED');
$handle=fopen($progress,'x');if(!is_resource($handle))throw new RuntimeException('G36_CONTACT_PROGRESS_UNAVAILABLE');fclose($handle);
$completed=false;ob_start();
register_shutdown_function(static function()use(&$completed):void{if(!$completed){while(ob_get_level()>0)@ob_end_clean();fwrite(STDERR,"G36_CONTACT_INCOMPLETE\n");exit(1);}});
function g36contact(string $name,bool $pass):void {
    global $checks,$progress;if(array_key_exists($name,$checks))throw new RuntimeException('G36_DUPLICATE_CONTACT_CHECK');
    $checks[$name]=$pass;$bytes=json_encode($checks,JSON_THROW_ON_ERROR);
    if(file_put_contents($progress,$bytes,LOCK_EX)!==strlen($bytes))throw new RuntimeException('G36_CONTACT_PROGRESS_UNAVAILABLE');
    if(!$pass)throw new RuntimeException('G36_CONTACT_ASSERTION_FAILED:'.$name);
}
define('WP_ENVIRONMENT_TYPE','local');define('WP_CONTENT_DIR','/opt/lab/g36/wp-content');define('WP_PLUGIN_DIR',WP_CONTENT_DIR.'/plugins');
define('BSRE_CANONICAL_LEASE_ENABLED',true);define('BSRE_G3_ROUTE_CONTEXT_ENABLED',true);define('BSRE_G2_SHARED_REPOSITORY_ENABLED',true);
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED',true);define('BSRE_RETENTION_ADMISSION_ENABLED',true);
define('BSRE_RETENTION_ADMISSION_GENERATION',str_repeat('a',64));define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT',time()-2000);
define('BSRE_LEAD_RECEIVER_URL','https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET',str_repeat('synthetic-key-',4));define('BSRE_ROUTING_ENABLED',true);
$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_METHOD']='GET';$_SERVER['REQUEST_URI']='/enquire/';
require '/opt/wordpress/wp-load.php';require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
require_once '/opt/lab/g36/contact-abi.php';
use BSRE\Enquiries as E;use BSRE\SharedRepository as G;use BSRE\G36Native as N;
N\fixed();
add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
add_filter('plugins_url',fn($url)=>'https://blackswanrealestate.ae'.parse_url($url,PHP_URL_PATH));
add_filter('rest_url',fn($url,$route)=>'https://blackswanrealestate.ae/wp-json/'.ltrim($route,'/'),10,2);
$networkCalls=0;$mailCalls=0;
add_filter('pre_http_request',function()use(&$networkCalls){$networkCalls++;throw new RuntimeException('G36_CONTACT_NETWORK_FORBIDDEN');},PHP_INT_MAX);
add_filter('pre_wp_mail',function()use(&$mailCalls){$mailCalls++;throw new RuntimeException('G36_CONTACT_MAIL_FORBIDDEN');},PHP_INT_MAX);
$owner=get_user_by('login','synthetic_owner');N\need($owner instanceof WP_User,'G36_SYNTHETIC_OWNER_REQUIRED');wp_set_current_user($owner->ID);
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$beforeRows=N\captures();$fixture=N\reconcile();
g36contact('candidate_hub_exact_native_body',get_post_field('post_content',$fixture['hub'],'raw')===E\owned_parent_source('hub'));
g36contact('candidate_hub_guard_bound',hash('sha256',E\owned_parent_source('hub'))===E\OWNED_HUB_SHA256 && E\OWNED_HUB_PAGE_ID===26750);
g36contact('known_service_hierarchy_preserved',count($fixture['services'])===5 && $fixture['prior_preserved']);
g36contact('hub_reconciliation_preserves_retained_rows',N\captures()===$beforeRows);
$probe=wp_insert_post(['post_type'=>'page','post_status'=>'draft','post_parent'=>$fixture['hub'],'post_name'=>'g36-unregistered-child-'.$mode,
    'post_title'=>'SYNTHETIC G36 collision probe','post_content'=>'SYNTHETIC DISPOSABLE PROBE','meta_input'=>['_bsre_g36_native_fixture'=>'1']],true);
N\need(!is_wp_error($probe) && is_int($probe) && $probe>0,'G36_COLLISION_PROBE_FAILED');
$denied=false;$attemptedWrites=0;$readonlyQueries=0;$removed=null;
$readGuard=static function(string $sql)use(&$attemptedWrites,&$readonlyQueries):string{
    $readonlyQueries++;if(preg_match('/^\s*(?:SELECT|SHOW)\b/i',$sql)!==1){$attemptedWrites++;throw new RuntimeException('G36_RECONCILE_WRITE_FORBIDDEN');}return $sql;
};
try{
    add_filter('query',$readGuard,PHP_INT_MAX);
    try{N\reconcile();}catch(Throwable $e){$denied=$e->getMessage()==='G36_UNREGISTERED_NATIVE_CHILD_COLLISION';}
    finally{remove_filter('query',$readGuard,PHP_INT_MAX);}
}finally{
    N\need(get_post_meta($probe,'_bsre_g36_native_fixture',true)==='1' && E\managed_native_page_id(get_post_field('post_parent',$probe,'raw'))===$fixture['hub'],'G36_PROBE_CUSTODY_CHANGED');
    $removed=wp_delete_post($probe,true);
}
g36contact('unregistered_native_child_denied_before_fixture_writes',$denied && $attemptedWrites===0 && $readonlyQueries>0);
g36contact('only_new_synthetic_collision_probe_removed',$removed instanceof WP_Post && $removed->ID===$probe && get_post($probe)===null && N\captures()===$beforeRows);
$privacy=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_name'=>'g36-synthetic-privacy-'.$mode,'post_title'=>'SYNTHETIC G36 NOTICE'],true);
N\need(!is_wp_error($privacy) && is_int($privacy) && $privacy>0,'G36_PRIVACY_FIXTURE_FAILED');define('BSRE_PRIVACY_NOTICE_PAGE_ID',$privacy);
$wpdb->prefix='g36_abi_'.str_replace('-','_',$mode).'_synthetic_';E\install();N\need(G\migrate(),'G36_ABI_MIGRATION_FAILED');
$producer=new \BSRE\ActualRetention\CanonicalCaptureProducer($wpdb);$producer->assertCurrent($wpdb);
g36contact('canonical_first_global_and_repository',get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb' && G\repository()->database()===$wpdb);
$manifest=N\sourceManifest();g36contact('final_manifest64_runtime_bound',count($manifest['files'])===64);
foreach(N\modules() as $name=>$pass)g36contact($name,$pass);
$producer->assertCurrent($wpdb);g36contact('canonical_producer_after_class_only_load',true);
$id=$mode==='hub'?$fixture['hub']:$fixture['services'][$mode];
$GLOBALS['wp_query']=new WP_Query(['page_id'=>$id,'post_type'=>'page']);$GLOBALS['wp_the_query']=$GLOBALS['wp_query'];
$_SERVER['REQUEST_URI']=$mode==='hub'?'/enquire/':'/enquire/'.$mode.'/';wp_set_current_user(0);
$scope=E\owned_parent_scope();$document=is_array($scope)?E\owned_parent_document($scope):null;
g36contact('actual_wordpress_query_owned_and_live',get_queried_object_id()===$id && is_array($document) && $document['binding']['mode']==='live' && $document['full_assets']===true);
$body=E\owned_parent_source($mode);$wa=$mode==='hub'?0:3;$tel=$mode==='hub'?1:3;$display=in_array($mode,['hub','rent'],true)?1:2;
g36contact('candidate_source_contact_counts',is_string($body) && substr_count($body,'https://wa.me/19995550123')===$wa
    && substr_count($body,'tel:+19995550123')===$tel && substr_count($body,'+1 999 555 0123')===$display);
g36contact('candidate_source_original_contact_absent',!str_contains($body,'971568285677') && !str_contains($body,'+971 56 828 5677'));
$lead=file_get_contents(WP_PLUGIN_DIR.'/bsre-enquiries/assets/lead.js');
g36contact('served_contact_matcher_uses_candidate',is_string($lead) && substr_count($lead,'wa\\.me\\/19995550123')===1 && !str_contains($lead,'971568285677'));
$beforeRender=N\captures();
ob_start();require WP_PLUGIN_DIR.'/bsre-enquiries/templates/page.php';$html=(string)ob_get_clean();
g36contact('actual_template_renders_contact_counts',substr_count($html,'https://wa.me/19995550123')===$wa
    && substr_count($html,'tel:+19995550123')===$tel && substr_count($html,'+1 999 555 0123')===$display);
g36contact('actual_template_original_contact_absent',!str_contains($html,'971568285677') && !str_contains($html,'+971 56 828 5677'));
g36contact('actual_template_canonical_and_nonce',str_contains($html,'<link rel="canonical" href="https://blackswanrealestate.ae'.$_SERVER['REQUEST_URI'].'">')
    && substr_count($html,'<script nonce="'.$document['nonce'].'"')===5);
$assetBase='https://blackswanrealestate.ae/wp-content/plugins/bsre-enquiries/assets/';
$assets=true;foreach(['consent-bridge.js','wordpress.js','lead.js','google-measurement.js'] as $asset)$assets=$assets && substr_count($html,'src="'.$assetBase.$asset.'?ver='.E\PLUGIN_VERSION.'"')===1;
g36contact('actual_template_exact_scripts_once',$assets && substr_count($html,'window.BSREWordPress=')===1 && substr_count($html,'window.BSRENativePageContextConfig=')===1);
preg_match('/window\.BSRENativePageContextConfig=(.*?);window\.BSREGoogleConfig=/s',$html,$native);
$context=isset($native[1])?json_decode($native[1],true,16,JSON_THROW_ON_ERROR):null;
$expectedRole=$mode==='hub'?'unknown':E\SERVICES[$mode]['role'];
g36contact('g4_native_context_survives_presentation',is_array($context) && ($context['schema']??null)===1 && ($context['page_path']??null)===$_SERVER['REQUEST_URI'] && ($context['role']??null)===$expectedRole);
g36contact('frontend_once_guard_preserved',E\render_frontend_scripts($document['lead'],$document['google'],$document['nonce'],true)==='');
g36contact('render_preserves_retained_rows',N\captures()===$beforeRender);
g36contact('no_mail_network_or_provider_event',$mailCalls===0 && $networkCalls===0);
$producer->assertCurrent($wpdb);g36contact('same_canonical_producer_after_render',true);
while(ob_get_level()>0)ob_end_clean();
echo json_encode(['phase'=>'g36_coupled_contact_abi','mode'=>$mode,'checks'=>$checks,'runtime_isolation'=>$isolation,
    'synthetic_only'=>true,'network_calls'=>$networkCalls,'mail_calls'=>$mailCalls,'provider_events'=>0,'native_provider_accepted'=>false,
    'limits'=>'Actual isolated native template/config contact ABI only; no browser/SDK/provider/human/production acceptance.'],JSON_THROW_ON_ERROR)."\n";
$completed=true;
