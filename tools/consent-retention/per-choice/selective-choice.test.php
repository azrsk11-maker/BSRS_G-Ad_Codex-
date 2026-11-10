<?php
declare(strict_types=1);
define('ABSPATH',__DIR__.'/');define('ARRAY_A','ARRAY_A');
$GLOBALS['selective_env']='local';$GLOBALS['selective_home']='http://bsre.invalid';$GLOBALS['selective_owner']=true;$GLOBALS['selective_actor']=1;
function wp_get_environment_type(){return $GLOBALS['selective_env'];}
function home_url(){return $GLOBALS['selective_home'];}
function current_user_can($cap){return $GLOBALS['selective_owner'];}
function get_current_user_id(){return $GLOBALS['selective_actor'];}
require __DIR__.'/SelectiveChoiceRetirement.php';
use BSRE\RetentionReview\PerChoice\ApplicationV1\SelectiveChoiceRetirement as C;
final class NoNativeDb {
    public $prefix=C::PREFIX;public $last_error='';public $active='0';public $isolation='REPEATABLE-READ';public array $queries=[];public bool $rollbackThrows=false;public array $present=[];
    public function get_var($sql){$this->queries[]=$sql;return str_contains($sql,'in_transaction')?$this->active:$this->isolation;}
    public function query($sql){$this->queries[]=$sql;if($sql==='ROLLBACK'&&$this->rollbackThrows)throw new RuntimeException('PRIVATE_DRIVER_CONTENT');return 0;}
    public function prepare($sql,...$values){return vsprintf(str_replace('%s',"'%s'",$sql),$values);}
    public function get_row($sql,$format){$this->queries[]=$sql;foreach($this->present as$table)if(str_contains($sql,$table))return ['Engine'=>'InnoDB'];return null;}
    public function get_results($sql,$format){$this->queries[]=$sql;return [];}
}
$checks=[];
function sc(string $name,bool $value):void{global$checks;if(!$value)throw new RuntimeException('Synthetic selective guard assertion failed');$checks[$name]=true;}
function held(callable $fn,string $code):bool{try{$fn();return false;}catch(Throwable $e){return $e->getMessage()===$code;}}
$db=new NoNativeDb();sc('default_component_disabled_before_io',held(fn()=>new C($db),'SELECTIVE_COMPONENT_DISABLED')&&$db->queries===[]);
define('BSRE_PER_CHOICE_LAB_ENABLED',true);define('BSRE_RETENTION_LAB',true);
$clock=2000000000;$controller=new C($db,fn()=>$GLOBALS['clock']);sc('construction_is_not_storage_acceptance',$db->queries===[]);
$db->prefix='wp_';sc('mutable_prefix_rechecked_before_read',held(fn()=>$controller->anchor(),'SELECTIVE_ISOLATED_LAB_ONLY')&&$db->queries===[]);$db->prefix=C::PREFIX;
$GLOBALS['selective_env']='production';sc('environment_rechecked',held(fn()=>$controller->anchor(),'SELECTIVE_ISOLATED_LAB_ONLY'));$GLOBALS['selective_env']='local';
$GLOBALS['selective_home']='https://real.invalid';sc('origin_rechecked',held(fn()=>$controller->anchor(),'SELECTIVE_ISOLATED_LAB_ONLY'));$GLOBALS['selective_home']='http://bsre.invalid';
$GLOBALS['selective_owner']=false;sc('owner_rechecked',held(fn()=>$controller->anchor(),'SELECTIVE_OWNER_REQUIRED'));$GLOBALS['selective_owner']=true;
$GLOBALS['selective_actor']=0;sc('actor_required',held(fn()=>$controller->anchor(),'SELECTIVE_OWNER_REQUIRED'));$GLOBALS['selective_actor']=1;
sc('apply_separately_disabled',held(fn()=>$controller->apply([],'' ,[]),'SELECTIVE_APPLY_DISABLED')&&$db->queries===[]);
sc('schema_install_separately_disabled',held(fn()=>$controller->installLabTables(),'SELECTIVE_APPLY_DISABLED')&&$db->queries===[]);
define('BSRE_PER_CHOICE_APPLY_ENABLED',true);
$plan=['created_at'=>$clock,'expires_at'=>$clock+900];$ack=C::labAcknowledgement($plan);
sc('exact_lab_ack_not_owner_approval',str_starts_with($ack,'APPLY_SYNTHETIC_PER_CHOICE:')&&held(fn()=>$controller->apply($plan,'wrong',[]),'SELECTIVE_EXACT_LAB_ACK_REQUIRED')&&$db->queries===[]);
foreach(['expired'=>[$clock-901,$clock-1],'future'=>[$clock+1,$clock+901],'oversized_window'=>[$clock,$clock+901]]as$name=>[$created,$expires]){
    $bad=['created_at'=>$created,'expires_at'=>$expires];sc($name.'_plan_before_io',held(fn()=>$controller->apply($bad,C::labAcknowledgement($bad),[]),'SELECTIVE_PLAN_EXPIRED_OR_INVALID')&&$db->queries===[]);
}
$clock=-1;sc('negative_clock_holds',held(fn()=>$controller->apply($plan,$ack,[]),'SELECTIVE_CLOCK_INVALID'));$clock=4102444800;
sc('overflowing_window_holds',held(fn()=>$controller->apply($plan,$ack,[]),'SELECTIVE_CLOCK_INVALID'));$clock=2000000000;
$db->active='1';$db->queries=[];sc('existing_transaction_not_started_or_rolled_back',held(fn()=>$controller->anchor(),'SELECTIVE_CALLER_TRANSACTION_FORBIDDEN')&&$db->queries===['SELECT @@session.in_transaction']);
$db->queries=[];sc('ddl_cannot_commit_existing_caller_transaction',held(fn()=>$controller->installLabTables(),'SELECTIVE_CALLER_TRANSACTION_FORBIDDEN')&&$db->queries===['SELECT @@session.in_transaction']);
$db->active=null;$db->queries=[];sc('unknown_transaction_state_holds_before_ddl',held(fn()=>$controller->installLabTables(),'SELECTIVE_TRANSACTION_STATE_UNAVAILABLE')&&$db->queries===['SELECT @@session.in_transaction']);
$db->active='0';$db->isolation='READ-COMMITTED';$db->queries=[];
sc('isolation_refused_not_changed',held(fn()=>$controller->anchor(),'SELECTIVE_REPEATABLE_READ_REQUIRED')&&!in_array('START TRANSACTION',$db->queries,true)&&!in_array('ROLLBACK',$db->queries,true));$db->isolation='REPEATABLE-READ';
$db->present=['bsre_choice_control'];$db->queries=[];sc('partial_control_not_reinitialized',held(fn()=>$controller->installLabTables(),'SELECTIVE_PARTIAL_INSTALLATION')&&count(array_filter($db->queries,fn($q)=>str_starts_with($q,'CREATE')||str_starts_with($q,'INSERT')))===0);
$db->present=['bsre_consent_history'];$db->queries=[];sc('existing_consent_namespace_not_adopted_as_genesis',held(fn()=>$controller->installLabTables(),'SELECTIVE_PARTIAL_INSTALLATION')&&count(array_filter($db->queries,fn($q)=>str_starts_with($q,'CREATE')||str_starts_with($q,'INSERT')))===0);
$db->present=[];$db->rollbackThrows=true;$db->queries=[];sc('rollback_exception_sanitized_as_ambiguous_hold',held(fn()=>$controller->anchor(),'SELECTIVE_FRESH_READBACK_REQUIRED')&&in_array('ROLLBACK',$db->queries,true));
$db->queries=[];sc('uncertain_instance_cannot_apply_again',held(fn()=>$controller->apply($plan,$ack,[]),'SELECTIVE_FRESH_READBACK_REQUIRED')&&$db->queries===[]);
echo json_encode(['scope'=>'SYNTHETIC_SELECTIVE_CHOICE_GUARDS','status'=>'PASS','checks'=>$checks,'native_sql_executed'=>false,'production_acceptance'=>false],JSON_THROW_ON_ERROR)."\n";
