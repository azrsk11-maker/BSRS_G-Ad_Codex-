<?php
declare(strict_types=1);
define('ABSPATH',__DIR__.'/');
function wp_get_environment_type(){return 'local';}function home_url(){return 'http://bsre.invalid';}
function current_user_can($cap){return true;}function get_current_user_id(){return 1;}
require __DIR__.'/SelectiveChoiceRetirement.php';
use BSRE\RetentionReview\PerChoice\PurposeV1\PurposeChoicePlanner as P;
use BSRE\RetentionReview\PerChoice\PerChoicePlanner as B;
use BSRE\RetentionReview\PerChoice\ApplicationV1\SelectiveChoiceRetirement as C;
$checks=[];$now=2000000000;
function pt(string $name,bool $ok):void{global$checks;if(!$ok)throw new RuntimeException('Synthetic purpose choice assertion failed: '.$name);$checks[$name]=true;}
function ph(callable $fn,string $code='PURPOSE_CHOICE_LINEAGE_UNRESOLVED'):bool{try{$fn();return false;}catch(Throwable $e){return $e->getMessage()===$code;}}
function fixture():array{
    global$now;$subject=str_repeat('a',64);$old=$now-500*86400;$history=[];
    foreach([[1,$old,1],[2,$old+100,1],[3,$old+200,1],[4,$old+300,0],[5,$now-86400,1]]as[$revision,$time,$grant])$history[]=['receipt'=>str_repeat((string)$revision,32),'subject_key'=>$subject,'revision'=>$revision,'analytics'=>$grant,'ad_measurement'=>$grant,'personalization'=>0,'notice_version'=>'SYNTHETIC_NOTICE','changed_at'=>$time,'uncertain'=>0];
    $state=$history[4]+['expires_at'=>$history[4]['changed_at']+15552000];$original=$history[2];
    $capture=['request_id'=>'11111111-1111-4111-8111-111111111111','fingerprint'=>str_repeat('f',64),'subject_key'=>$subject,'original_revision'=>3,'decision_version'=>$original['receipt'],'notice_version'=>$original['notice_version'],'analytics'=>1,'ad_measurement'=>1,'personalization'=>0,'preference_expires_at'=>$original['changed_at']+15552000,'eligible'=>1,'known'=>1,'created_at'=>$old+260,'state'=>'ACCEPTED','uncertain'=>0,'delivery_pending'=>0,'click_capture_state'=>'ABSENT','gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0,'lead_id'=>'BSRE-SYNTHETIC-LEAD','event_id'=>'evt_synthetic_event','purpose_version'=>1,'purpose_hash'=>str_repeat('d',64),'purpose_record_hash'=>'','purpose_json'=>''];
    $touch=(object)['capture_id'=>'22222222-2222-4222-8222-222222222222','decision_version'=>$history[1]['receipt'],'notice_version'=>'SYNTHETIC_NOTICE','landing_page'=>'https://blackswanrealestate.ae/enquire/rent/','referrer'=>'','timestamp'=>($old+101)*1000,'parameters'=>(object)['gclid'=>'Exact_Click.A~9'],'original_revision'=>2,'expires_at'=>$old+100+15552000];
    $record=(object)['version'=>1,'analytics'=>(object)['first'=>null,'last'=>null],'advertising'=>(object)['first'=>$touch,'last'=>clone$touch]];
    $capture=bindRecord($capture,$record);return ['kind'=>'SYNTHETIC_INCOMPLETE','state'=>[$state],'history'=>$history,'captures'=>[$capture]];
}
function bindRecord(array $capture,$record):array{$capture['purpose_json']=json_encode($record,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES|JSON_UNESCAPED_UNICODE);$capture['purpose_record_hash']=hash('sha256',$capture['fingerprint']."\n".$capture['purpose_hash']."\n".$capture['purpose_json']);return$capture;}
function pc(array $s):array{global$now;return ['kind'=>B::COVERAGE,'snapshot_sha256'=>B::digest($s),'status'=>'COMPLETE_SYNTHETIC','observed_at'=>$now,'valid_until'=>$now+3600,'history_pruned'=>false];}
function pp(array $s):array{global$now;return P::plan($s,pc($s),$now,true);}
pt('default_off_does_not_inspect',P::plan([],[],-1)['mode']==='DISABLED');
$s=fixture();$before=serialize($s);$r=pp($s);$due=array_column(array_filter($r['rows'],fn($x)=>$x['classification']==='DUE_UNREFERENCED_SYNTHETIC_REVIEW'),'row_ref');
pt('older_nested_decision_and_all_later_withdrawals_protected',$due===['bsre_consent_history:'.str_repeat('1',32)]);
pt('full_extended_snapshot_and_coverage_bound',$r['snapshot_sha256']===B::digest($s)&&$r['coverage_sha256']===B::digest(pc($s)));
pt('deterministic_immutable_no_execution_authority',$r===pp($s)&&serialize($s)===$before&&!$r['apply_supported']&&!$r['production_authorized']);
$aliasedCapture=$s['captures'][0];$aliased=$s;$aliased['captures'][0]=&$aliasedCapture;$coverage=pc($aliased);$aliasedHash=$coverage['snapshot_sha256'];$coverage['snapshot_sha256']=&$aliasedHash;
$aliasBefore=serialize($aliased);$coverageBefore=serialize($coverage);$aliasResult=P::plan($aliased,$coverage,$now,true);
pt('aliased_capture_and_coverage_unchanged_after_success',serialize($aliased)===$aliasBefore&&serialize($coverage)===$coverageBefore&&$aliasResult['snapshot_sha256']===$aliasedHash);
$aliasedCapture['purpose_record_hash']=str_repeat('0',64);$coverage=pc($aliased);$aliasedHash=$coverage['snapshot_sha256'];$coverage['snapshot_sha256']=&$aliasedHash;$aliasBefore=serialize($aliased);$coverageBefore=serialize($coverage);
pt('aliased_capture_and_coverage_unchanged_after_rejection',ph(fn()=>P::plan($aliased,$coverage,$now,true))&&serialize($aliased)===$aliasBefore&&serialize($coverage)===$coverageBefore);
unset($aliased,$aliasedCapture,$coverage,$aliasedHash);$s=fixture();
$badCoverage=pc($s);$badCoverage['snapshot_sha256']=str_repeat('0',64);$bad=P::plan($s,$badCoverage,$now,true);pt('full_input_mismatch_holds_all_due',in_array('COVERAGE_SNAPSHOT_MISMATCH',$bad['global_reasons'],true)&&$bad['counts']['due_unreferenced_choice_rows']===0);
foreach(['missing_field','empty_payload','bad_hash','known_zero','legacy_zero','wrong_shape','unknown_field','cross_subject','revision_mismatch','future_touch','next_choice_boundary','expired_at_capture','withdrawal_before_capture','duplicate_capture_id_conflict','unsupported_parameter','analytics_click','partial_slot','empty_parameter','blank_parameter','foreign_origin','insecure_origin','foreign_port','oversized_utf16','ineligible_touch','uppercase_capture_id']as$case){
    $bad=$s;$capture=$bad['captures'][0];$record=json_decode($capture['purpose_json']);$touch=$record->advertising->first;
    if($case==='missing_field')unset($capture['purpose_hash']);
    elseif($case==='empty_payload')$capture=bindRecord($capture,null);
    elseif($case==='bad_hash')$capture['purpose_record_hash']=str_repeat('0',64);
    elseif($case==='known_zero')$capture['known']=0;
    elseif($case==='legacy_zero'){$capture['purpose_version']=0;$capture['purpose_hash']='';$capture['purpose_record_hash']='';$capture['purpose_json']='';}
    elseif($case==='wrong_shape'){$record->advertising=[];$capture=bindRecord($capture,$record);}
    elseif($case==='unknown_field'){$touch->extra='SYNTHETIC';$capture=bindRecord($capture,$record);}
    elseif($case==='cross_subject'){$bad['history'][1]['subject_key']=str_repeat('b',64);}
    elseif($case==='revision_mismatch'){$touch->original_revision=1;$capture=bindRecord($capture,$record);}
    elseif($case==='future_touch'){$touch->timestamp=($capture['created_at']+1)*1000;$capture=bindRecord($capture,$record);}
    elseif($case==='next_choice_boundary'){$touch->timestamp=$bad['history'][2]['changed_at']*1000;$capture=bindRecord($capture,$record);}
    elseif($case==='expired_at_capture'){$touch->expires_at=$capture['created_at'];$capture=bindRecord($capture,$record);}
    elseif($case==='withdrawal_before_capture'){$bad['history'][1]['ad_measurement']=0;}
    elseif($case==='duplicate_capture_id_conflict'){$record->advertising->last->parameters->gclid='Changed';$capture=bindRecord($capture,$record);}
    elseif($case==='unsupported_parameter'){$touch->parameters->contact='SYNTHETIC';$capture=bindRecord($capture,$record);}
    elseif($case==='analytics_click'){$record->analytics=clone$record->advertising;$capture=bindRecord($capture,$record);}
    elseif($case==='partial_slot'){$record->advertising->last=null;$capture=bindRecord($capture,$record);}
    elseif($case==='empty_parameter'){$touch->parameters->utm_source='';$capture=bindRecord($capture,$record);}
    elseif($case==='blank_parameter'){$touch->parameters->utm_source='   ';$capture=bindRecord($capture,$record);}
    elseif($case==='foreign_origin'){$touch->landing_page='https://other.example.invalid/enquire/rent/';$capture=bindRecord($capture,$record);}
    elseif($case==='insecure_origin'){$touch->landing_page='http://blackswanrealestate.ae/enquire/rent/';$capture=bindRecord($capture,$record);}
    elseif($case==='foreign_port'){$touch->landing_page='https://blackswanrealestate.ae:444/enquire/rent/';$capture=bindRecord($capture,$record);}
    elseif($case==='oversized_utf16'){$touch->parameters->utm_content=str_repeat("\u{1F600}",129);$capture=bindRecord($capture,$record);}
    elseif($case==='ineligible_touch'){$capture['eligible']=0;}
    elseif($case==='uppercase_capture_id'){$touch->capture_id='AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA';$capture=bindRecord($capture,$record);}
    // Keep paired same-ID touches identical so a separate duplicate-conflict guard cannot mask a missing field validator.
    if(in_array($case,['unknown_field','revision_mismatch','future_touch','next_choice_boundary','expired_at_capture','unsupported_parameter','empty_parameter','blank_parameter','foreign_origin','insecure_origin','foreign_port','oversized_utf16','uppercase_capture_id'],true)){
        $record->advertising->last=clone$touch;$capture=bindRecord($capture,$record);
    }
    $bad['captures'][0]=$capture;pt($case.'_holds_whole_batch',ph(fn()=>pp($bad)));
}
$unicode=$s;$unicodeRecord=json_decode($unicode['captures'][0]['purpose_json']);$unicodeRecord->advertising->first->parameters->utm_content=str_repeat("\u{1F600}",128);$unicodeRecord->advertising->last=clone$unicodeRecord->advertising->first;$unicode['captures'][0]=bindRecord($unicode['captures'][0],$unicodeRecord);
pt('valid_utf16_boundary_preserves_supported_text',pp($unicode)['counts']['due_unreferenced_choice_rows']===1);
$empty=$s;$record=json_decode($empty['captures'][0]['purpose_json']);$record->advertising=(object)['first'=>null,'last'=>null];$empty['captures'][0]=bindRecord($empty['captures'][0],$record);
pt('explicit_absent_purpose_does_not_invent_old_reference',pp($empty)['counts']['due_unreferenced_choice_rows']===2);
$plain=$s;foreach(P::EXTRA as$key)unset($plain['captures'][0][$key]);pt('plain_baseline_unchanged_selects_older_unreferenced_revision',B::plan($plain,pc($plain),$now,true)['counts']['due_unreferenced_choice_rows']===2);
$db=(object)['prefix'=>C::PURPOSE_PREFIX];pt('factory_default_off_before_io',ph(fn()=>C::purposeLab($db),'SELECTIVE_COMPONENT_DISABLED'));
define('BSRE_PER_CHOICE_LAB_ENABLED',true);define('BSRE_RETENTION_LAB',true);define('BSRE_PER_CHOICE_APPLY_ENABLED',true);
pt('purpose_component_has_separate_enable',ph(fn()=>C::purposeLab($db),'SELECTIVE_PURPOSE_COMPONENT_DISABLED'));define('BSRE_PER_CHOICE_PURPOSE_LAB_ENABLED',true);
$control=C::purposeLab($db);pt('purpose_apply_separately_disabled_before_io',ph(fn()=>$control->apply([],'' ,[]),'SELECTIVE_PURPOSE_APPLY_DISABLED'));
pt('plain_default_refuses_purpose_namespace',ph(fn()=>new C($db),'SELECTIVE_ISOLATED_LAB_ONLY'));
$db->prefix=C::PREFIX;pt('purpose_factory_refuses_plain_namespace',ph(fn()=>$control->anchor(),'SELECTIVE_ISOLATED_LAB_ONLY'));
pt('unsupported_mode_refused_before_io',ph(fn()=>new C($db,null,'CUSTOM'),'SELECTIVE_MODE_INVALID'));
echo json_encode(['scope'=>'SYNTHETIC_PURPOSE_CHOICE_INTEGRATION','status'=>'PASS','checks'=>$checks,'native_sql_executed'=>false,'production_acceptance'=>false],JSON_THROW_ON_ERROR)."\n";
