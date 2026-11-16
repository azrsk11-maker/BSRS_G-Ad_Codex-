<?php
declare(strict_types=1);
namespace BSRE\G36Native;
use BSRE\Enquiries as E;

/** Test-only helpers. Never included by the generated plugin or production bootstrap. */
function need(bool $ok,string $code):void { if(!$ok)throw new \RuntimeException($code); }
function fixed():void {
    global $wpdb;
    need(PHP_SAPI==='cli' && defined('WP_CONTENT_DIR') && WP_CONTENT_DIR==='/opt/lab/g36/wp-content'
        && defined('WP_ENVIRONMENT_TYPE') && WP_ENVIRONMENT_TYPE==='local'
        && DB_NAME==='bsre_synthetic' && DB_HOST==='localhost:/tmp/bsre.sock' && DB_USER==='root' && DB_PASSWORD===''
        && get_class($wpdb)==='BSRE\\ClosedRetention\\LeaseBoundWpdb' && $GLOBALS['wpdb']===$wpdb
        && $wpdb->get_var('SELECT DATABASE()')==='bsre_synthetic'
        && defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED') && BSRE_CANONICAL_LEASE_BOOTSTRAPPED===true
        && !is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g36'), 'G36_FIXED_CANONICAL_LAB_REQUIRED');
}
function sourceManifest():array {
    fixed();$base=WP_PLUGIN_DIR.'/bsre-enquiries/';$file=$base.'includes/candidate/runtime/canonical-source.json';
    need(realpath($file)===$file && !is_link($file),'G36_MANIFEST_PATH_UNVERIFIED');
    $raw=file_get_contents($file);need(is_string($raw) && strlen($raw)<65536 && hash('sha256',$raw)===BSRE_CANONICAL_LEASE_SOURCE_SHA256,'G36_MANIFEST_MARKER_CHANGED');
    $m=json_decode($raw,true,16,JSON_THROW_ON_ERROR);$keys=array_keys($m);sort($keys);
    need($keys===['deployment_prohibited','files','profile','schema'] && $m['schema']==='bsre-canonical-lease-source-v1'
        && $m['profile']==='G36_COUPLED_CANONICAL_LEASE_V3' && $m['deployment_prohibited']===true && count($m['files'])===64,'G36_MANIFEST_SHAPE_CHANGED');
    foreach($m['files'] as $path=>$sha){
        need(is_string($path) && preg_match('~^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$~D',$path)===1
            && !in_array('..',explode('/',$path),true) && !in_array('.',explode('/',$path),true)
            && is_string($sha) && preg_match('/^[a-f0-9]{64}$/D',$sha)===1
            && realpath($base.$path)===$base.$path && !is_link($base.$path) && hash_file('sha256',$base.$path)===$sha,'G36_SOURCE_MEMBER_CHANGED');
    }
    return $m;
}
/** Only the already-owned synthetic hierarchy may be reused; no accepted consent row is deleted. */
function reconcile():array {
    fixed();$manifest=sourceManifest();
    need(current_user_can('manage_options') && E\OWNED_HUB_PAGE_ID===26750,'G36_SYNTHETIC_OWNER_REQUIRED');
    $source=E\owned_parent_source('hub');need(is_string($source) && hash('sha256',$source)===E\OWNED_HUB_SHA256
        && $manifest['files']['templates/source/hub.html']===E\OWNED_HUB_SHA256,'G36_CANDIDATE_HUB_UNVERIFIED');
    $prior=get_page_by_path('enquire',OBJECT,'page');$fixed=get_post(E\OWNED_HUB_PAGE_ID);
    $services=get_option('bsre_draft_pages',[]);$parent=E\managed_native_page_id(get_option('bsre_parent_draft',0));
    need(is_array($services),'G36_REGISTRY_UNVERIFIED');$priorId=$prior instanceof \WP_Post ? $prior->ID : 0;
    need($fixed===null || $fixed instanceof \WP_Post && $fixed->ID===$priorId,'G36_FIXED_HUB_COLLISION');
    if($prior!==null){
        need($prior instanceof \WP_Post && $prior->post_type==='page' && $prior->post_password===''
            && get_page_uri($priorId)==='enquire' && get_post_meta($priorId,'_bsre_parent',true)==='1'
            && in_array($prior->post_status,['draft','publish'],true) && $parent===$priorId,'G36_KNOWN_SYNTHETIC_HUB_REQUIRED');
        need(count($services)===5 && array_diff(array_keys($services),array_keys(E\SERVICES))===[],'G36_KNOWN_SERVICE_SET_REQUIRED');
        foreach($services as $slug=>$id){
            $id=E\managed_native_page_id($id);need($id>0 && get_post_type($id)==='page' && get_post_meta($id,'_bsre_service',true)===$slug
                && E\managed_native_page_id(get_post_field('post_parent',$id,'raw'))===$priorId && get_page_uri($id)==='enquire/'.$slug
                && get_post_field('post_password',$id,'raw')==='' && in_array(get_post_status($id),['draft','publish'],true),'G36_KNOWN_SYNTHETIC_SERVICE_REQUIRED');
        }
    }else need($services===[] && $parent===0,'G36_ORPHAN_SYNTHETIC_REGISTRY');
    // Orphan children at the future fixed ID can acquire /enquire/<slug> only after insertion.
    // Inspect their raw native parent association now, before any hub or service write.
    $children=get_posts(['post_type'=>['page','attachment'],'post_status'=>['publish','pending','draft','auto-draft','future','private','inherit','trash'],
        'post_parent'=>$priorId ?: E\OWNED_HUB_PAGE_ID,'posts_per_page'=>7,'fields'=>'ids','orderby'=>'ID','order'=>'ASC','suppress_filters'=>true]);
    $expectedChildren=array_map('intval',array_values($services));sort($expectedChildren);sort($children);
    need($children===$expectedChildren,'G36_UNREGISTERED_NATIVE_CHILD_COLLISION');
    if($priorId && $priorId!==E\OWNED_HUB_PAGE_ID){
        $futureChildren=get_posts(['post_type'=>['page','attachment'],'post_status'=>['publish','pending','draft','auto-draft','future','private','inherit','trash'],
            'post_parent'=>E\OWNED_HUB_PAGE_ID,'posts_per_page'=>1,'fields'=>'ids','suppress_filters'=>true]);
        need($futureChildren===[],'G36_FUTURE_FIXED_HUB_CHILD_COLLISION');
    }
    foreach(E\SERVICES as $slug=>$unused)if(!isset($services[$slug]))need(get_page_by_path('enquire/'.$slug,OBJECT,'page')===null,'G36_UNREGISTERED_SERVICE_COLLISION');
    // Validate every source and collision before the first fixture write.
    if($priorId && $priorId!==E\OWNED_HUB_PAGE_ID){
        $slug='g36-prior-synthetic-enquire-'.$priorId;need(get_page_by_path($slug,OBJECT,'page')===null,'G36_RETAINED_HUB_COLLISION');
        $changed=wp_update_post(['ID'=>$priorId,'post_name'=>$slug],true);need(!is_wp_error($changed) && $changed===$priorId,'G36_RETAINED_HUB_UNCONFIRMED');
    }
    $data=['post_type'=>'page','post_status'=>'publish','post_name'=>'enquire','post_content'=>$source,'meta_input'=>['_bsre_parent'=>'1']];
    if($fixed instanceof \WP_Post){$data['ID']=$fixed->ID;$hub=wp_update_post(wp_slash($data),true);}
    else{$data['import_id']=E\OWNED_HUB_PAGE_ID;$data['post_title']='SYNTHETIC G36 enquiry hub';$hub=wp_insert_post(wp_slash($data),true);}
    need(!is_wp_error($hub) && $hub===E\OWNED_HUB_PAGE_ID && get_post_field('post_content',$hub,'raw')===$source,'G36_EXACT_HUB_WRITE_UNCONFIRMED');
    $next=[];
    foreach(E\SERVICES as $slug=>$unused){
        $old=E\managed_native_page_id($services[$slug]??null);
        if($old)$id=wp_update_post(['ID'=>$old,'post_parent'=>$hub,'post_status'=>'publish'],true);
        else{
            $id=wp_insert_post(['post_type'=>'page','post_status'=>'publish','post_parent'=>$hub,'post_name'=>$slug,'post_title'=>'SYNTHETIC G36 '.$slug,
                'post_content'=>'SYNTHETIC NATIVE FIXTURE','meta_input'=>['_bsre_service'=>$slug]],true);
        }
        need(!is_wp_error($id) && is_int($id) && $id>0 && (!$old || $old===$id),'G36_SERVICE_ID_UNCONFIRMED');$next[$slug]=$id;
    }
    update_option('bsre_parent_draft',$hub,false);update_option('bsre_draft_pages',$next,false);
    need(E\managed_native_page_id(get_option('bsre_parent_draft',0))===$hub && get_option('bsre_draft_pages')===$next
        && (!$priorId || get_post($priorId) instanceof \WP_Post),'G36_FIXTURE_READBACK_FAILED');
    return ['hub'=>$hub,'services'=>$next,'prior_preserved'=>!$priorId || get_post($priorId) instanceof \WP_Post];
}
/** Hashes of synthetic retained rows only, never rows or identifiers in public receipts. */
function captures():array {
    global $wpdb;fixed();$tables=$wpdb->get_col('SHOW TABLES');need(is_array($tables) && count($tables)<=256,'G36_TABLE_BOUND');$out=[];
    foreach($tables as $table)if(is_string($table) && preg_match('/^[a-z][a-z0-9_]{0,80}_bsre_consent_captures$/D',$table)===1){
        $rows=$wpdb->get_results('SELECT * FROM `'.$table.'` ORDER BY request_id LIMIT 1001',ARRAY_A);
        need(is_array($rows) && count($rows)<=1000 && $wpdb->last_error==='','G36_CAPTURE_SNAPSHOT_UNAVAILABLE');$out[$table]=hash('sha256',json_encode($rows,JSON_THROW_ON_ERROR));
    }
    ksort($out);return $out;
}
function hooks():array {$out=[];foreach($GLOBALS['wp_filter'] as $name=>$hook)$out[$name]=$hook->callbacks;return $out;}
function denied(callable $operation):bool {try{$operation();return false;}catch(\Throwable $e){return $e->getMessage()==='ISOLATED_LAB_ONLY';}}
/** Class loading is deliberately separate from any owner operation, install or preference mutation. */
function modules():array {
    global $wpdb;$manifest=sourceManifest();$base=WP_PLUGIN_DIR.'/bsre-enquiries/';
    $nine=array_merge(array_map(fn($n)=>'includes/candidate/owner-mail-review/'.$n.'.php',['Cleanup','OwnerClosure','OwnerCollection','OwnerMailReview','OwnerRetirement','WordPress']),
        array_map(fn($n)=>'includes/candidate/purpose-retention/'.$n.'.php',['PreferenceRetirement','RetirementLedger','purpose-retention']));
    $beforeRows=captures();$routes=rest_get_server()->get_routes();$beforeHooks=hooks();$queryCount=$wpdb->num_queries;$noise='';
    ob_start();try{
        foreach($nine as $path){need(isset($manifest['files'][$path]),'G36_EXTRA_MODULE_UNBOUND');require_once $base.$path;}
    }finally{$noise=(string)ob_get_clean();}
    $checks=['extra_nine_class_load_no_output'=>$noise==='', 'extra_nine_class_load_no_sql'=>$queryCount===$wpdb->num_queries,
        'extra_nine_no_hooks'=>hooks()===$beforeHooks,'extra_nine_no_routes'=>rest_get_server()->get_routes()===$routes];
    $checks['extra_nine_source_paths_bound']=count(array_intersect(array_map(fn($p)=>$base.$p,$nine),get_included_files()))===9;
    $checks['extra_nine_classes_resolve']=class_exists('BSRE\\OwnerMailReview\\WordPressSession',false)
        && class_exists('BSRE\\OwnerMailReview\\WordPressStore',false) && class_exists('BSRE\\PurposeRetention\\PreferenceRetirement',false)
        && class_exists('BSRE\\PurposeRetention\\RetirementLedger',false) && class_exists('BSRE\\PurposeRetention\\RetentionInventory',false);
    $checks['owner_mail_original_lab_guard']=denied(fn()=>\BSRE\OwnerMailReview\Guard::lab());
    $checks['purpose_original_lab_guard']=denied(fn()=>new \BSRE\PurposeRetention\PreferenceRetirement($wpdb));
    $checks['purpose_ledger_original_lab_guard']=denied(fn()=>new \BSRE\PurposeRetention\RetirementLedger($wpdb));
    $lab=new \ReflectionMethod('BSRE\\ClosedRetention\\Workflow','lab');$checks['workflow_original_lab_guard']=denied(fn()=>$lab->invoke(null));
    $checks['no_operational_flags_enabled']=(!defined('BSRE_OWNER_MAIL_REVIEW_LAB') || BSRE_OWNER_MAIL_REVIEW_LAB!==true)
        && (!defined('BSRE_CLOSED_RETENTION_LAB') || BSRE_CLOSED_RETENTION_LAB!==true) && (!defined('BSRE_RETENTION_LAB') || BSRE_RETENTION_LAB!==true);
    $checks['missing_preference_port_held']=!file_exists($base.'includes/candidate/retention/ActualPreferenceRetention.php') && !class_exists('BSRE\\ActualRetention\\ActualPreferenceRetention',false);
    $checks['missing_receiver_port_held']=!file_exists($base.'includes/candidate/receiver/ActualRetirementPort.php') && !class_exists('BSRE\\ActualRetention\\ActualRetirementPort',false);
    $checks['extra_nine_capture_rows_unchanged']=captures()===$beforeRows;
    return $checks;
}
