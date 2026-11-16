<?php
declare(strict_types=1);
/** FUTURE isolated candidate-image check, not the ordinary/default plugin lane. */
// Mandatory isolation.php already ran before DB creation in the unchanged entrypoint.
// These later checks are runtime-safe and REQUIRE the existing isolated database.
$mode=count($argv)===1 ? 'enabled' : (($argv[1]??'')==='--disabled' && count($argv)===2 ? 'disabled' : (($argv[1]??'')==='--namespace-collision' && count($argv)===2 ? 'namespace-collision' : 'invalid'));
$runtimeIsolation=[
    'cli'=>PHP_SAPI==='cli' && $mode!=='invalid',
    'non_root'=>function_exists('posix_geteuid') && posix_geteuid()!==0,
    'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
    'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
    'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
    'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
    'readonly_application'=>!is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g2/plugins'),
    'database_already_started'=>is_dir('/tmp/database') && file_exists('/tmp/bsre.sock'),
    'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach ($runtimeIsolation as $name=>$ok) if (!$ok) throw new RuntimeException('G2 runtime isolation failed: '.$name);
define('WP_ENVIRONMENT_TYPE','local');
define('WP_PLUGIN_DIR','/opt/lab/g2/plugins');
if ($mode!=='disabled') define('BSRE_G2_SHARED_REPOSITORY_ENABLED',true);
$_SERVER['HTTPS']='on'; $_SERVER['SERVER_PORT']='443'; $_SERVER['REQUEST_METHOD']='POST';
if ($mode==='namespace-collision') {
    define('BSRE_G2_NAMESPACE_COLLISION_LAB',true);
    require __DIR__.'/g2-namespace-collision-fixture.php';
    try {
        require '/opt/wordpress/wp-load.php';
        require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
    }
    catch (Throwable $error) {
        if ($error->getMessage()!=='G2_NAMESPACE_OCCUPIED') throw new RuntimeException('G2_COLLISION_UNEXPECTED_FAILURE');
        echo json_encode(['phase'=>'g2_shared_repository_namespace_collision','pass'=>true,'runtime_isolation'=>$runtimeIsolation],JSON_THROW_ON_ERROR)."\n";
        exit(0);
    }
    throw new RuntimeException('G2_NAMESPACE_COLLISION_NOT_REJECTED');
}
require '/opt/wordpress/wp-load.php';
require_once WP_PLUGIN_DIR.'/bsre-enquiries/bsre-enquiries.php';
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
use BSRE\SharedRepository as G;
if (wp_get_environment_type()!=='local' || WP_PLUGIN_DIR!=='/opt/lab/g2/plugins'
    || DB_NAME!=='bsre_synthetic' || DB_HOST!=='localhost:/tmp/bsre.sock'
    || DB_USER!=='root' || DB_PASSWORD!=='') throw new RuntimeException('G2_CANDIDATE_IMAGE_REQUIRED');
if ($mode==='enabled' && !function_exists('BSRE\\SharedRepository\\repository')) throw new RuntimeException('G2_BOOTSTRAP_MISSING');
$checks=[];
function g2check(string $label,bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('G2 native check failed: '.$label);
    $checks[$label]=true;
}
function g2denied(callable $fn,string $code): bool {
    try { $fn(); return false; } catch (Throwable $e) { return $e->getMessage()===$code; }
}
add_filter('home_url',fn($url,$path)=>'https://blackswanrealestate.ae'.($path===''?'':'/'.ltrim($path,'/')),10,2);
$wpdb->prefix=$mode==='disabled' ? 'g2_disabled_synthetic_' : 'g2_shared_synthetic_';
$owner=get_user_by('login','synthetic_owner');
if (!$owner) throw new RuntimeException('G2_SYNTHETIC_OWNER_REQUIRED');
wp_set_current_user($owner->ID);
E\install(); g2check('baseline_schema2_installed',E\install_consent_storage());
if ($mode==='enabled') delete_option(G\SCHEMA_OPTION);
// Seed through the ACTUAL original class before migration, not a fake database.
$legacy=new E\WpConsentRepository($wpdb);
$id=wp_generate_uuid4();
$capture=['request_id'=>$id,'fingerprint'=>hash('sha256','SYNTHETIC G2 old row'),
    'subject_key'=>'','original_revision'=>0,'decision_version'=>str_repeat('a',32),'notice_version'=>E\CONSENT_NOTICE_VERSION,
    'analytics'=>0,'ad_measurement'=>0,'eligible'=>0,'known'=>0,'preference_expires_at'=>0,'created_at'=>time(),
    'uncertain'=>0,'click_capture_state'=>'NOT_PERMITTED','gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0];
$legacy->stage($capture);
$old=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$id),ARRAY_A);

if ($mode==='disabled') {
    g2check('disabled_profile_loads_no_shared_namespace',!function_exists('BSRE\\SharedRepository\\repository') && !class_exists('BSRE\\PurposeAttribution\\Runtime',false));
    $default=E\consent_repository();
    g2check('disabled_default_original_repository',get_class($default)===E\WpConsentRepository::class);
    $_COOKIE=[];
    $raw=wp_json_encode(['request_id'=>wp_generate_uuid4(),'name'=>'SYNTHETIC G2 disabled profile']);
    $handle=E\consent_stage_submission($raw);
    g2check('disabled_default_still_stages',$handle['recorded'] && get_class($handle['repository'])===E\WpConsentRepository::class && (int)$handle['row']['known']===0);
    $receipt=['lead_id'=>'BSRE-'.wp_generate_uuid4(),'event_id'=>'evt_'.wp_generate_uuid4()];
    E\consent_link_accepted($handle,$receipt,$raw);
    $stored=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$handle['row']['request_id']),ARRAY_A);
    g2check('disabled_default_still_links_receipts',$stored['state']==='ACCEPTED' && $stored['lead_id']===$receipt['lead_id'] && $stored['event_id']===$receipt['event_id']);
    g2check('disabled_additive_columns_absent',$wpdb->get_col("SHOW COLUMNS FROM {$wpdb->prefix}bsre_consent_captures LIKE 'purpose_%'")===[]);
    echo wp_json_encode(['phase'=>'g2_shared_repository_disabled','runtime_isolation'=>$runtimeIsolation,'checks'=>$checks])."\n";
    exit(0);
}

wp_set_current_user(0);
g2check('unready_default_does_not_fall_back',g2denied(fn()=>E\consent_repository(),'G2_SCHEMA_NOT_READY'));
g2check('anonymous_cannot_migrate',G\migrate()===false && get_option(G\SCHEMA_OPTION)!=='1');
wp_set_current_user($owner->ID);
// Conflicting and partial schemas are separate synthetic setup, never baseline migrations.
$table=$wpdb->prefix.'bsre_consent_captures';
if ($wpdb->query("ALTER TABLE `{$table}` ADD COLUMN `purpose_version` varchar(8) NOT NULL DEFAULT '0'")===false) throw new RuntimeException('G2_CONFLICT_SETUP_FAILED');
$conflictQueries=[];
$conflictObserver=static function(string $sql) use (&$conflictQueries): string { $conflictQueries[]=$sql; return $sql; };
add_filter('query',$conflictObserver,PHP_INT_MAX);
try { $conflictRejected=G\migrate()===false; }
finally { remove_filter('query',$conflictObserver,PHP_INT_MAX); }
$writes=array_filter($conflictQueries,static fn($sql)=>preg_match('/^\s*(ALTER|CREATE|DROP|INSERT|UPDATE|DELETE|REPLACE|TRUNCATE)\b/i',$sql)===1);
g2check('conflicting_additive_schema_rejected_without_writes',$conflictRejected && $writes===[] && get_option(G\SCHEMA_OPTION)!=='1');
$conflictRow=$wpdb->get_row($wpdb->prepare("SELECT * FROM `{$table}` WHERE request_id=%s",$id),ARRAY_A);
unset($conflictRow['purpose_version']);
g2check('conflicting_schema_preserves_original_row',$conflictRow===$old);
if ($wpdb->query("ALTER TABLE `{$table}` DROP COLUMN `purpose_version`")===false) throw new RuntimeException('G2_CONFLICT_CLEANUP_FAILED');
$ddl=G\additions()['purpose_version'];
if ($wpdb->query("ALTER TABLE `{$table}` ADD COLUMN `purpose_version` {$ddl}")===false) throw new RuntimeException('G2_PARTIAL_SETUP_FAILED');
update_option(G\SCHEMA_OPTION,'1',false);
g2check('partial_schema_not_ready',g2denied(fn()=>E\consent_repository(),'G2_ADDITIVE_SCHEMA_INCOMPLETE'));
g2check('actual_additive_migration_succeeds',G\migrate());
g2check('original_marker_preserved',get_option('bsre_consent_schema_version')==='2');
$after=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$id),ARRAY_A);
g2check('old_capture_default_purpose_unknown',(int)$after['purpose_version']===0 && $after['purpose_hash']==='' && $after['purpose_record_hash']==='' && $after['purpose_json']===null);
foreach (array_keys(G\additions()) as $key) unset($after[$key]);
g2check('all_original_row_bytes_preserved',$after===$old);
wp_set_current_user(0);
$canonical=E\consent_repository();
g2check('original_and_purpose_defaults_identical',$canonical===P\repository() && $canonical===E\consent_repository() && P\Runtime::$store===$canonical);
g2check('same_explicit_store_allowed',E\consent_repository($canonical)===$canonical);
g2check('foreign_original_store_rejected',g2denied(fn()=>E\consent_repository($legacy),'G2_STORE_CONFLICT'));
P\Runtime::$store=new P\WpConsentRepository($wpdb);
g2check('foreign_purpose_override_rejected',g2denied(fn()=>P\repository(),'G2_STORE_CONFLICT'));
P\Runtime::$store=$canonical;
$_COOKIE=[];
$raw=wp_json_encode(['request_id'=>wp_generate_uuid4(),'name'=>'SYNTHETIC G2 default stage']);
$handle=E\consent_stage_submission($raw);
g2check('actual_default_stage_uses_canonical_store',$handle['recorded'] && $handle['repository']===$canonical && (int)$handle['row']['known']===0);
$raw2=wp_json_encode(['request_id'=>wp_generate_uuid4(),'name'=>'SYNTHETIC G2 purpose stage']);
$other=P\stage_submission($raw2);
g2check('actual_purpose_stage_uses_canonical_store',$other['recorded'] && $other['repository']===$canonical);
$receipt=['lead_id'=>'BSRE-'.wp_generate_uuid4(),'event_id'=>'evt_'.wp_generate_uuid4()];
E\consent_link_accepted($handle,$receipt,$raw);
$stored=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$handle['row']['request_id']),ARRAY_A);
g2check('actual_default_link_preserves_receipts',$stored['lead_id']===$receipt['lead_id'] && $stored['event_id']===$receipt['event_id'] && $stored['state']==='ACCEPTED');
$prefix=$wpdb->prefix; $wpdb->prefix='g2_other_synthetic_';
g2check('prefix_switch_cannot_borrow_store',g2denied(fn()=>E\consent_repository(),'G2_DATABASE_CHANGED'));
$wpdb->prefix=$prefix;
if ($mode==='enabled') delete_option(G\SCHEMA_OPTION);
g2check('lost_readiness_marker_blocks_cached_store',g2denied(fn()=>P\repository(),'G2_SCHEMA_NOT_READY'));
wp_set_current_user($owner->ID);
g2check('migration_idempotent',G\migrate());
wp_set_current_user(0);
g2check('canonical_identity_after_idempotent_migration',E\consent_repository()===$canonical);
require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/g2-profile/bootstrap.php';
g2check('repeated_bootstrap_does_not_redeclare',E\consent_repository()===$canonical);
// Reproduce same-object/same-prefix USE with cached WP options/schema/store.
wp_set_current_user($owner->ID);
$configured=(string)$wpdb->get_var('SELECT DATABASE()');
g2check('configured_database_identity',$configured===DB_NAME);
$foreign='g2_foreign_synthetic';
if ($configured===$foreign || $wpdb->query('CREATE DATABASE `g2_foreign_synthetic`')===false) throw new RuntimeException('G2_FOREIGN_SETUP_FAILED');
$observedQueries=[];
$observeQuery=static function(string $sql) use (&$observedQueries): string { $observedQueries[]=$sql; return $sql; };
try {
    $objectId=spl_object_id($wpdb); $samePrefix=$wpdb->prefix;
    if (!$wpdb->select($foreign)) throw new RuntimeException('G2_FOREIGN_SELECT_FAILED');
    add_filter('query',$observeQuery,PHP_INT_MAX);
    g2check('same_object_same_prefix_database_switch',spl_object_id($wpdb)===$objectId && $wpdb->prefix===$samePrefix);
    g2check('foreign_default_selection_rejected',g2denied(fn()=>E\consent_repository(),'G2_DATABASE_CHANGED'));
    g2check('foreign_purpose_selection_rejected',g2denied(fn()=>P\repository(),'G2_DATABASE_CHANGED'));
    g2check('foreign_migration_rejected',G\migrate()===false);
    $onlyIdentity=true;
    foreach ($observedQueries as $query) if (trim($query)!=='SELECT DATABASE()') $onlyIdentity=false;
    g2check('foreign_attempts_only_read_connection_identity',$onlyIdentity && count($observedQueries)===3);
    $observedQueries=[];
    $heldOperations=[
        'database'=>fn()=>$canonical->database(),
        'admission_contract'=>fn()=>$canonical->admissionContract(),
        'current'=>fn()=>$canonical->current(str_repeat('a',64)),
        'choose'=>fn()=>$canonical->choose(str_repeat('a',64),['analytics'=>false,'ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time()),
        'stage'=>fn()=>$canonical->stage($capture),
        'link'=>fn()=>$canonical->link($id,$capture['fingerprint'],$receipt['lead_id'],$receipt['event_id']),
        'uncertain'=>fn()=>$canonical->uncertain($id,$capture['fingerprint']),
        'revoked'=>fn()=>$canonical->revoked(str_repeat('a',64),1,'analytics'),
        'export'=>fn()=>$canonical->exportRows([$id]),
    ];
    foreach ($heldOperations as $operation=>$call) g2check('foreign_held_'.$operation.'_rejected',g2denied($call,'G2_DATABASE_CHANGED'));
    $onlyIdentity=true;
    foreach ($observedQueries as $query) if (trim($query)!=='SELECT DATABASE()') $onlyIdentity=false;
    g2check('foreign_held_operations_only_read_connection_identity',$onlyIdentity && count($observedQueries)===count($heldOperations));
    remove_filter('query',$observeQuery,PHP_INT_MAX);
    g2check('foreign_database_has_no_tables',$wpdb->get_col('SHOW TABLES')===[]);
} finally {
    remove_filter('query',$observeQuery,PHP_INT_MAX);
    if (!$wpdb->select($configured)) throw new RuntimeException('G2_DATABASE_RESTORE_FAILED');
    if ($wpdb->query('DROP DATABASE `g2_foreign_synthetic`')===false) throw new RuntimeException('G2_FOREIGN_CLEANUP_FAILED');
}
wp_set_current_user(0);
g2check('canonical_store_after_database_restore',E\consent_repository()===$canonical);
echo wp_json_encode(['phase'=>'g2_shared_repository','runtime_isolation'=>$runtimeIsolation,'checks'=>$checks,
    'limits'=>'Storage/bootstrap/migration only; no provider, receiver delivery, G3 route ownership, transport, page context or production acceptance.'])."\n";
