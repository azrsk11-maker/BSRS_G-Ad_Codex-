<?php
declare(strict_types=1);
/** Fixed isolated core-bootstrap proof only. SHORTINIT deliberately excludes plugin/route/producer acceptance. */
$mode=$argv[1]??'';
$modes=['disabled','enabled','malformed-flag','existing-global','namespace-collision','manifest-tampered','source-tampered','producer-tampered'];
if(count($argv)!==2 || !in_array($mode,$modes,true))throw new RuntimeException('G35_FIXED_BOOTSTRAP_MODE_REQUIRED');
$isolation=[
    'cli'=>PHP_SAPI==='cli',
    'non_root'=>function_exists('posix_geteuid') && posix_geteuid()!==0,
    'loopback_only'=>array_values(array_diff(scandir('/sys/class/net'),['.','..']))===['lo'],
    'no_routes'=>count(preg_split('/\r?\n/',trim(file_get_contents('/proc/net/route'))))===1,
    'no_capabilities'=>preg_match('/^CapEff:\s*0+$/m',file_get_contents('/proc/self/status'))===1,
    'no_new_privileges'=>preg_match('/^NoNewPrivs:\s*1$/m',file_get_contents('/proc/self/status'))===1,
    'readonly_application'=>!is_writable('/opt/wordpress') && !is_writable('/opt/reviewed') && !is_writable('/opt/lab/g35'),
    'database_already_started'=>is_dir('/tmp/database') && file_exists('/tmp/bsre.sock'),
    'no_docker_socket'=>!file_exists('/var/run/docker.sock'),
];
foreach($isolation as $ok)if(!$ok)throw new RuntimeException('G35_BOOTSTRAP_ISOLATION_REQUIRED');
$checks=[];$progress='/tmp/g35_bootstrap_'.$mode.'_progress.json';
if(file_exists($progress) || is_link($progress))throw new RuntimeException('G35_FRESH_PROGRESS_REQUIRED');
$progressHandle=@fopen($progress,'x');if(!is_resource($progressHandle))throw new RuntimeException('G35_PROGRESS_UNAVAILABLE');fclose($progressHandle);
$completed=false;
register_shutdown_function(static function()use(&$completed):void{
    if(!$completed){while(ob_get_level()>0)@ob_end_clean();fwrite(STDERR,"G35_BOOTSTRAP_INCOMPLETE\n");exit(1);}
});
function g35need(bool $ok,string $code):void{if(!$ok)throw new RuntimeException($code);}
function g35check(string $name,bool $ok):void{
    global $checks,$progress;
    g35need(!array_key_exists($name,$checks),'G35_DUPLICATE_CHECK');$checks[$name]=$ok;
    $body=json_encode($checks,JSON_THROW_ON_ERROR);g35need(file_put_contents($progress,$body,LOCK_EX)===strlen($body),'G35_PROGRESS_UNAVAILABLE');
    if(!$ok)throw new RuntimeException('G35_BOOTSTRAP_ASSERTION_FAILED:'.$name);
}
function g35keys(array $value,array $expected):bool{$actual=array_keys($value);sort($actual);sort($expected);return $actual===$expected;}
function g35relative($path):bool{
    return is_string($path) && strlen($path)<=240 && preg_match('~^wp-content/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+$~D',$path)===1
        && !in_array('.',explode('/',$path),true) && !in_array('..',explode('/',$path),true)
        && ($path==='wp-content/db.php' || str_starts_with($path,'wp-content/plugins/bsre-enquiries/'));
}
function g35read(string $path,int $maximum):string{
    g35need(realpath($path)===$path && is_file($path) && !is_link($path),'G35_SOURCE_PATH_UNVERIFIED');
    $size=filesize($path);g35need(is_int($size) && $size>0 && $size<=$maximum,'G35_SOURCE_SIZE_UNVERIFIED');
    $body=@file_get_contents($path);g35need(is_string($body) && strlen($body)===$size,'G35_SOURCE_READ_UNVERIFIED');return $body;
}
function g35site():array{
    $root='/opt/lab/g35';g35need(realpath($root)===$root && is_dir($root) && !is_link($root),'G35_FIXED_SITE_REQUIRED');
    $raw=g35read($root.'/BUILD.json',65536);$build=json_decode($raw,true,16,JSON_THROW_ON_ERROR);
    g35need(is_array($build) && g35keys($build,['profile','files']) && $build['profile']==='G35_CANONICAL_LEASE_CODE_ONLY'
        && is_array($build['files']) && array_is_list($build['files']) && count($build['files'])===58,'G35_BUILD_MANIFEST_INVALID');
    preg_match_all('/"(profile|files|path|sha256)"\s*:/',$raw,$literal);$counts=array_count_values($literal[1]);
    g35need($counts===['profile'=>1,'files'=>1,'path'=>58,'sha256'=>58] || ($counts['profile']??0)===1 && ($counts['files']??0)===1 && ($counts['path']??0)===58 && ($counts['sha256']??0)===58,'G35_BUILD_MANIFEST_DUPLICATE_KEYS');
    $files=[];$hashes=[];$total=0;
    foreach($build['files'] as $row){
        g35need(is_array($row) && g35keys($row,['path','sha256']) && g35relative($row['path']) && is_string($row['sha256'])
            && preg_match('/^[a-f0-9]{64}$/D',$row['sha256'])===1 && !isset($files[$row['path']]),'G35_BUILD_MEMBER_INVALID');
        $body=g35read($root.'/'.$row['path'],1048576);g35need(hash_equals($row['sha256'],hash('sha256',$body)),'G35_BUILD_MEMBER_CHANGED');
        $total+=strlen($body);g35need($total<=16777216,'G35_SITE_BYTE_BOUND');$files[$row['path']]=$body;$hashes[$row['path']]=$row['sha256'];
    }
    $prefix='wp-content/plugins/bsre-enquiries/';$manifestPath=$prefix.'includes/candidate/runtime/canonical-source.json';
    $producerPath=$prefix.'includes/candidate/runtime/CanonicalCaptureProducer.php';
    g35need(isset($files['wp-content/db.php'],$files[$manifestPath],$files[$producerPath]),'G35_REQUIRED_SITE_MEMBER_ABSENT');
    $manifest=json_decode($files[$manifestPath],true,16,JSON_THROW_ON_ERROR);
    g35need(is_array($manifest) && g35keys($manifest,['schema','profile','files','deployment_prohibited'])
        && $manifest['schema']==='bsre-canonical-lease-source-v1' && $manifest['profile']===$build['profile']
        && $manifest['deployment_prohibited']===true && is_array($manifest['files']) && count($manifest['files'])===55,'G35_CODE_MANIFEST_INVALID');
    $expected=['wp-content/db.php',$manifestPath,$producerPath];
    foreach($manifest['files'] as $relative=>$sha){
        $path=$prefix.$relative;g35need(is_string($relative) && g35relative($path) && is_string($sha) && isset($hashes[$path]) && $hashes[$path]===$sha,'G35_CODE_MEMBER_UNVERIFIED');$expected[]=$path;
    }
    $actual=array_keys($files);sort($actual);sort($expected);g35need($actual===$expected,'G35_SITE_SET_UNVERIFIED');
    // Exact fixed tree only: an unlisted cache/drop-in/provider must never execute before db.php.
    $seen=[];$entries=0;
    $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root.'/wp-content',FilesystemIterator::SKIP_DOTS),RecursiveIteratorIterator::SELF_FIRST);
    foreach($iterator as $item){
        g35need(++$entries<=512 && !$item->isLink(),'G35_SITE_REDIRECT_OR_SIZE');$path=$item->getPathname();
        g35need(realpath($path)===$path,'G35_SITE_REDIRECT_OR_SIZE');
        if($item->isFile()){$relative=substr($path,strlen($root)+1);g35need(isset($files[$relative]),'G35_UNLISTED_SITE_FILE');$seen[]=$relative;}
        else g35need($item->isDir(),'G35_UNEXPECTED_SITE_ENTRY');
    }
    sort($seen);g35need($seen===$actual,'G35_SITE_ENUMERATION_CHANGED');
    return ['root'=>$root,'files'=>$files,'hashes'=>$hashes,'manifest'=>$manifest,'manifest_path'=>$manifestPath,'producer_path'=>$producerPath];
}
function g35copy(array $site,string $mode):string{
    $root='/tmp/g35_'.$mode;g35need(dirname($root)==='/tmp' && realpath('/tmp')==='/tmp' && !file_exists($root) && !is_link($root),'G35_FRESH_TAMPER_ROOT_REQUIRED');
    g35need(@mkdir($root,0700) && realpath($root)===$root,'G35_TAMPER_ROOT_UNAVAILABLE');
    g35check('copy_fresh_fixed_destination',true);
    // Every source byte/hash was read and verified before the first write; no extra source trees are copied.
    foreach($site['files'] as $relative=>$bytes){
        g35need(g35relative($relative),'G35_COPY_PATH_INVALID');$path=$root.'/'.$relative;$dir=dirname($path);
        if(!is_dir($dir))g35need(@mkdir($dir,0700,true),'G35_COPY_DIRECTORY_UNAVAILABLE');
        g35need(realpath($dir)===$dir && str_starts_with($dir,$root.'/') && !file_exists($path) && !is_link($path),'G35_COPY_TARGET_INVALID');
        $handle=@fopen($path,'x');g35need(is_resource($handle),'G35_COPY_TARGET_UNAVAILABLE');
        try{g35need(fwrite($handle,$bytes)===strlen($bytes) && fflush($handle),'G35_COPY_WRITE_UNCONFIRMED');}finally{fclose($handle);}
        g35need(hash_file('sha256',$path)===$site['hashes'][$relative],'G35_COPY_READBACK_CHANGED');
    }
    g35check('copy_exact_58_verified_source_files',count($site['files'])===58);
    $target=match($mode){
        'manifest-tampered'=>$site['manifest_path'],
        'source-tampered'=>'wp-content/plugins/bsre-enquiries/includes/protocol.php',
        'producer-tampered'=>$site['producer_path'],
        default=>throw new RuntimeException('G35_TAMPER_MODE_INVALID'),
    };
    g35need(isset($site['files'][$target]),'G35_TAMPER_TARGET_UNVERIFIED');
    $addition=$mode==='manifest-tampered'?"\n":"\n// Fixed synthetic bootstrap tamper.\n";
    $handle=@fopen($root.'/'.$target,'ab');g35need(is_resource($handle),'G35_TAMPER_TARGET_UNAVAILABLE');
    try{g35need(fwrite($handle,$addition)===strlen($addition) && fflush($handle),'G35_TAMPER_WRITE_UNCONFIRMED');}finally{fclose($handle);}
    $changed=[];foreach($site['hashes'] as $relative=>$sha)if(hash_file('sha256',$root.'/'.$relative)!==$sha)$changed[]=$relative;
    g35check('copy_only_selected_tamper_changed',$changed===[$target]);return $root;
}
function g35symbols():array{
    $symbols=array_values(array_filter(array_merge(get_declared_classes(),get_declared_interfaces(),get_declared_traits()),fn($name)=>strncasecmp($name,'BSRE\\',5)===0));sort($symbols);return $symbols;
}
function g35markers():bool{return defined('BSRE_CANONICAL_LEASE_SOURCE_SHA256') || defined('BSRE_CANONICAL_LEASE_PRODUCER_SHA256') || defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED');}
function g35domainIncluded(string $content):bool{
    $prefix=$content.'/plugins/bsre-enquiries/includes/candidate/';
    foreach(get_included_files() as $path)if(str_starts_with($path,$prefix))return true;return false;
}
g35check('pre_no_wordpress_runtime',!defined('ABSPATH') && !class_exists('wpdb',false) && !isset($GLOBALS['wpdb']) && !function_exists('get_option'));
$site=g35site();g35check('pre_source58_manifest_and_hashes_verified',count($site['files'])===58);
$targetRoot=$site['root'];
if(in_array($mode,['manifest-tampered','source-tampered','producer-tampered'],true))$targetRoot=g35copy($site,$mode);
define('WP_CONTENT_DIR',$targetRoot.'/wp-content');define('SHORTINIT',true);define('WP_ENVIRONMENT_TYPE','local');
define('BSRE_CANONICAL_LEASE_ENABLED',$mode==='disabled'?false:($mode==='malformed-flag'?'true':true));
$preserved=null;
if($mode==='existing-global'){$preserved=new stdClass();$GLOBALS['wpdb']=$preserved;g35check('existing_nonwpdb_global_fixture_set',get_class($preserved)==='stdClass');}
if($mode==='namespace-collision'){$collision=new class{};g35check('namespace_user_class_alias_fixture_set',class_alias(get_class($collision),'BSRE\\ClosedRetention\\LeaseBoundWpdb'));}
$symbolsBefore=g35symbols();$failure=null;$noise='';
ob_start(static fn(string $value):string=>'');
try{require '/opt/wordpress/wp-load.php';}catch(Throwable $error){$failure=$error->getMessage();}finally{$noise=(string)ob_get_clean();}
g35check('boot_fixed_synthetic_database_configuration',defined('DB_NAME') && DB_NAME==='bsre_synthetic' && defined('DB_HOST') && DB_HOST==='localhost:/tmp/bsre.sock' && defined('DB_USER') && DB_USER==='root' && defined('DB_PASSWORD') && DB_PASSWORD==='');
g35check('boot_actual_core_dropin_included',in_array(WP_CONTENT_DIR.'/db.php',get_included_files(),true));
g35check('boot_emits_no_data',$noise==='');g35check('boot_core_shortinit_selected',SHORTINIT===true);
if($mode==='disabled'){
    g35check('disabled_no_failure',$failure===null);
    g35check('disabled_ordinary_wpdb_global',isset($GLOBALS['wpdb']) && get_class($GLOBALS['wpdb'])==='wpdb');
    g35check('disabled_no_bsre_symbols',g35symbols()===[]);
    g35check('disabled_no_binding_markers',!g35markers());
    g35check('disabled_no_domain_dependencies',!g35domainIncluded(WP_CONTENT_DIR));
    g35check('disabled_core_prefix_initialized',$wpdb->prefix==='synthetic_' && $wpdb->options==='synthetic_options');
    g35check('disabled_core_options_readable',is_string(get_option('siteurl')) && get_option('siteurl')!=='');
}elseif($mode==='enabled'){
    g35check('enabled_no_failure',$failure===null);
    $global=$GLOBALS['wpdb'];g35check('enabled_exact_first_global_class',get_class($global)==='BSRE\\ClosedRetention\\LeaseBoundWpdb');
    $classFile=WP_CONTENT_DIR.'/plugins/bsre-enquiries/includes/candidate/closed-enquiry-retention/LeaseBoundWpdb.php';
    $reflection=new ReflectionClass($global);$constructor=$reflection->getConstructor();
    g35check('enabled_original_reflection_source',$reflection->getFileName()===$classFile && hash_file('sha256',$classFile)==='a358c8f28a6186ce5bc452aa699c93ddd96fb71b58528f1e21acc9e42b854b58' && $constructor!==null && $constructor->getDeclaringClass()->getName()==='wpdb');
    g35check('enabled_source_manifest_marker',defined('BSRE_CANONICAL_LEASE_SOURCE_SHA256') && BSRE_CANONICAL_LEASE_SOURCE_SHA256===$site['hashes'][$site['manifest_path']]);
    g35check('enabled_producer_source_marker',defined('BSRE_CANONICAL_LEASE_PRODUCER_SHA256') && BSRE_CANONICAL_LEASE_PRODUCER_SHA256===$site['hashes'][$site['producer_path']]);
    g35check('enabled_bootstrap_marker',defined('BSRE_CANONICAL_LEASE_BOOTSTRAPPED') && BSRE_CANONICAL_LEASE_BOOTSTRAPPED===true);
    g35check('enabled_final_core_prefix_and_types',$wpdb->prefix==='synthetic_' && $wpdb->base_prefix==='synthetic_' && $wpdb->options==='synthetic_options' && $wpdb->posts==='synthetic_posts' && ($wpdb->field_types['ID']??null)==='%d');
    g35check('enabled_actual_selected_database',$wpdb->get_var('SELECT DATABASE()')==='bsre_synthetic');
    $server=$wpdb->get_var('SELECT VERSION()');g35check('enabled_supported_actual_server',is_string($server) && preg_match('/^(?:10\.11\.[0-9]+|11\.8\.9)-MariaDB(?:[-+][A-Za-z0-9.~+_-]+)?$/D',$server)===1);
    g35check('enabled_original_connection_not_leased',$wpdb->custodyIsActive()===false && $wpdb->custodyConnectionId()===null);
    g35check('enabled_core_options_readable',is_string(get_option('siteurl')) && get_option('siteurl')!=='');
    g35check('enabled_core_read_helpers',(int)$wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->options}")>0 && is_array($wpdb->get_row("SELECT option_name FROM {$wpdb->options} LIMIT 1",ARRAY_A)));
    g35check('enabled_query_logging_off',(!defined('SAVEQUERIES') || SAVEQUERIES===false) && !($wpdb->save_queries??false) && defined('WP_DEBUG') && WP_DEBUG===false);
    g35check('enabled_no_caller_transaction',(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0');
    // WordPress CRUD and rollback on a connection-local temporary table only; no post or persistent core row changes.
    $table='synthetic_g35_bootstrap_probe';$created=false;$transaction=false;
    try{
        $created=$wpdb->query("CREATE TEMPORARY TABLE {$table} (id int NOT NULL PRIMARY KEY, marker varchar(32) NOT NULL) ENGINE=InnoDB")!==false;
        g35check('enabled_temp_crud_created',$created);
        g35check('enabled_temp_baseline_insert',$wpdb->insert($table,['id'=>1,'marker'=>'baseline'],['%d','%s'])===1);
        $transaction=$wpdb->query('START TRANSACTION')!==false;g35check('enabled_transaction_started',$transaction && (string)$wpdb->get_var('SELECT @@session.in_transaction')==='1');
        g35check('enabled_wordpress_update_insert_delete',$wpdb->update($table,['marker'=>'changed'],['id'=>1],['%s'],['%d'])===1 && $wpdb->insert($table,['id'=>2,'marker'=>'new'],['%d','%s'])===1 && $wpdb->delete($table,['id'=>1],['%d'])===1);
        $during=$wpdb->get_results("SELECT id,marker FROM {$table} ORDER BY id",ARRAY_A);g35check('enabled_transaction_view',count($during)===1 && (int)$during[0]['id']===2 && $during[0]['marker']==='new');
        $rolled=$wpdb->query('ROLLBACK')!==false;if($rolled)$transaction=false;
        $restored=$wpdb->get_results("SELECT id,marker FROM {$table} ORDER BY id",ARRAY_A);g35check('enabled_rollback_restores_baseline',$rolled && count($restored)===1 && (int)$restored[0]['id']===1 && $restored[0]['marker']==='baseline');
        g35check('enabled_transaction_ended',(string)$wpdb->get_var('SELECT @@session.in_transaction')==='0');
    }finally{if($transaction)$wpdb->query('ROLLBACK');if($created)$wpdb->query("DROP TEMPORARY TABLE {$table}");}
    g35check('enabled_shared_global_unchanged',$GLOBALS['wpdb']===$global);
}else{
    $expected=match($mode){'malformed-flag'=>'CANONICAL_BOOTSTRAP_INVALID','existing-global'=>'CANONICAL_DATABASE_ALREADY_CREATED','namespace-collision'=>'CANONICAL_NAMESPACE_OCCUPIED','manifest-tampered','source-tampered'=>'CANONICAL_SOURCE_UNVERIFIED','producer-tampered'=>'CANONICAL_PRODUCER_UNVERIFIED'};
    g35check('refused_expected_generic_code',$failure===$expected);
    g35check('refused_no_new_global',$mode==='existing-global'?isset($GLOBALS['wpdb']) && $GLOBALS['wpdb']===$preserved:!isset($GLOBALS['wpdb']));
    g35check('refused_no_binding_markers',!g35markers());
    g35check('refused_no_domain_dependencies',!g35domainIncluded(WP_CONTENT_DIR));
    g35check('refused_no_ordinary_fallback',!isset($GLOBALS['wpdb']) || $GLOBALS['wpdb']===$preserved);
    g35check('refused_only_preexisting_namespace',g35symbols()===$symbolsBefore);
}
echo json_encode(['phase'=>'g35_canonical_lease_bootstrap','mode'=>$mode,'checks'=>$checks,'runtime_isolation'=>$isolation,'core_shortinit_only'=>true,'native_provider_accepted'=>false,'production_authorized'=>false],JSON_THROW_ON_ERROR)."\n";
$completed=true;
