<?php
// Appended by fixed test derivation only. All witness/keys/evidence here are synthetic.
require_once WP_PLUGIN_DIR.'/bsre-enquiries/includes/candidate/closed-enquiry-retention/ActualCaptureResource.php';
wp_set_current_user($owner->ID);
$canonicalChecks=[];
$canonicalProgress='/tmp/g35-custody-'.$canonicalMode.'.json';
function canonical_check(string $name,bool $pass):void {
    global $canonicalChecks,$canonicalProgress;
    if(array_key_exists($name,$canonicalChecks))throw new RuntimeException('G35 duplicate custody assertion');
    $canonicalChecks[$name]=$pass;$bytes=json_encode($canonicalChecks,JSON_THROW_ON_ERROR);
    if(file_put_contents($canonicalProgress,$bytes,LOCK_EX)!==strlen($bytes))throw new RuntimeException('G35 custody evidence unavailable');
    if(!$pass)throw new RuntimeException('G35 custody assertion failed: '.$name);
}
function canonical_denied(callable $operation,?string $code=null):bool {
    try{$operation();return false;}catch(Throwable $error){return $code===null||$error->getMessage()===$code;}
}
// This policy exercises the owned-origin branch in the isolated fixture, not deployment authority.
$policy=new G5\RuntimePolicy(DB_NAME,$wpdb->prefix,'https://blackswanrealestate.ae',(int)$owner->ID);
$pair=sodium_crypto_sign_keypair();$witness=new SyntheticWitness(sodium_crypto_sign_secretkey($pair));
$custody=new G5\ActualRecoveryCustody($policy->scope(),$witness,new SyntheticKeys(),sodium_crypto_sign_publickey($pair));
$evidence=new SyntheticEvidence();$authority=new G5\OwnerAuthority($policy,$evidence);
$journal=new G5\ActualJournal($wpdb,$policy,$custody,$authority,$evidence);
$journal->initialize();
require '/opt/lab/g35/purpose-native.php';
foreach(canonical_purpose_native_checks($canonicalProducer,$wpdb,$journal) as $name=>$pass)canonical_check('purpose_'.$name,$pass);
$table=$wpdb->prefix.'bsre_consent_captures';
$beforeRows=$wpdb->get_results("SELECT * FROM {$table} ORDER BY request_id",ARRAY_A);
canonical_check('actual_intake_rows_ten',is_array($beforeRows)&&count($beforeRows)===10);
$requestId=$beforeRows[0]['request_id'];
$journal->locked($requestId,function()use($canonicalProducer,$wpdb){
    $canonicalProducer->assertCurrent($wpdb);
    canonical_check('journal_custody_uses_same_global',G\repository()->database()===$wpdb&&$wpdb===$GLOBALS['wpdb']&&$wpdb->custodyIsActive());
});
canonical_check('normal_custody_releases',!$wpdb->custodyIsActive());
$capture=new G5\ActualCaptureResource($wpdb,$journal,$policy,$canonicalProducer);
canonical_check('missing_operational_closure_still_holds',canonical_denied(fn()=>$journal->locked($requestId,fn()=>$capture->read($requestId)),'G5_COLLECTOR_CUSTODY_UNIMPLEMENTED'));
canonical_check('missing_closure_does_not_mutate_intake',$wpdb->get_results("SELECT * FROM {$table} ORDER BY request_id",ARRAY_A)===$beforeRows);
$wpdb->save_queries=true;
canonical_check('dynamic_query_logging_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));$wpdb->save_queries=false;
$interceptor=fn($query)=>$query;add_filter('query',$interceptor);
canonical_check('query_interceptor_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));remove_filter('query',$interceptor);
$prefix=$wpdb->prefix;$wpdb->prefix='g35_foreign_synthetic_';
canonical_check('changed_prefix_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));$wpdb->prefix=$prefix;
$wpdb->query('USE information_schema');
canonical_check('changed_actual_database_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));$wpdb->query('USE bsre_synthetic');
$wpdb->query('START TRANSACTION');
canonical_check('unowned_transaction_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));$wpdb->query('ROLLBACK');
$wpdb->beginCustody();
canonical_check('unowned_manual_custody_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));$wpdb->endCustody();
$other=new Closed\LeaseBoundWpdb(DB_USER,DB_PASSWORD,DB_NAME,DB_HOST);$other->prefix=$prefix;$other->suppress_errors(true);
canonical_check('second_handle_cannot_become_producer',canonical_denied(fn()=>$canonicalProducer->assertCurrent($other)));
$original=$wpdb;$wpdb=$other;
canonical_check('global_replacement_rejected',canonical_denied(fn()=>$canonicalProducer->assertCurrent($original)));$wpdb=$original;
$other->close();unset($other);$canonicalProducer->assertCurrent($wpdb);
canonical_check('restored_original_binding_revalidates',G\repository()->database()===$wpdb);
if($canonicalMode==='loss'){
    $observer=new mysqli('localhost','root','','bsre_synthetic',0,'/tmp/bsre.sock');
    $connection=(int)$wpdb->get_var('SELECT CONNECTION_ID()');$oldStore=G\repository();
    canonical_check('separate_observer_connection',(int)$observer->thread_id!==$connection);
    $error='';
    try{$journal->locked($requestId,function()use($wpdb,$observer,$connection){
        if(!$observer->query('KILL CONNECTION '.$connection))throw new RuntimeException('G35_KILL_FIXTURE_FAILED');
        $wpdb->query('SELECT 1');
    });}catch(Throwable $failure){$error=$failure->getMessage();}
    canonical_check('lease_loss_quarantines_journal',$error==='G5_LEASE_RELEASE_UNCONFIRMED'&&$wpdb->custodyIsActive());
    canonical_check('lost_handle_cannot_reconnect',$wpdb->check_connection(false)===false&&$wpdb->db_connect(false)===false);
    canonical_check('held_repository_cannot_reconnect',canonical_denied(fn()=>$oldStore->database()));
    canonical_check('producer_cannot_reuse_lost_handle',canonical_denied(fn()=>$canonicalProducer->assertCurrent($wpdb)));
    canonical_check('journal_cannot_reuse_uncertain_lease',canonical_denied(fn()=>$journal->locked($requestId,fn()=>null),'G5_CUSTODY_RECONCILIATION_REQUIRED'));
    $observed=$observer->query("SELECT * FROM {$table} ORDER BY request_id")->fetch_all(MYSQLI_ASSOC);
    canonical_check('observer_proves_rows_preserved_after_loss',$observed===$beforeRows);$observer->close();
}else{
    canonical_check('all_guards_preserve_actual_rows',$wpdb->get_results("SELECT * FROM {$table} ORDER BY request_id",ARRAY_A)===$beforeRows);
}
echo wp_json_encode(['phase'=>'g35_canonical_custody','mode'=>$canonicalMode,'checks'=>$canonicalChecks,'runtime_isolation'=>$isolation,
    'limits'=>'Real canonical G2/G3 and G5 custody with synthetic witness/evidence; operational ports/provider/browser/production remain held.'])."\n";
