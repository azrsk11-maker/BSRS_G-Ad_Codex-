<?php
declare(strict_types=1);
/** Fabricated policy examples only; no real enquiries, records or approval. */
require __DIR__ . '/PerChoicePlanner.php';
use BSRE\RetentionReview\PerChoice\PerChoicePlanner as P;
use BSRE\RetentionReview\RetentionInventory as R;

$checks = [];
function pc_check(string $name, bool $condition): void {
    global $checks;
    if (!$condition) throw new RuntimeException('Synthetic per-choice check failed: ' . $name);
    $checks[$name] = true;
}
function pc_invalid(callable $operation): bool {
    try { $operation(); return false; }
    catch (InvalidArgumentException $error) { return $error->getMessage() === 'INVALID_OR_UNBOUNDED_SYNTHETIC_PER_CHOICE_INPUT'; }
}
function pc_time(string $time): int { return (new DateTimeImmutable($time))->getTimestamp(); }
function pc_history(string $subject, string $receipt, int $revision, int $time, int $analytics = 0): array {
    return ['receipt'=>str_repeat($receipt,32), 'subject_key'=>str_repeat($subject,64), 'revision'=>$revision,
        'analytics'=>$analytics, 'ad_measurement'=>0, 'personalization'=>0, 'notice_version'=>'SYNTHETIC_NOTICE',
        'changed_at'=>$time, 'uncertain'=>0];
}
function pc_snapshot(array $history): array {
    $latest = [];
    foreach ($history as $row) $latest[$row['subject_key']] = $row;
    $state = [];
    foreach ($latest as $row) { $row['expires_at'] = $row['changed_at'] + 15552000; $state[] = $row; }
    return ['kind'=>R::KIND, 'state'=>$state, 'history'=>$history, 'captures'=>[]];
}
function pc_capture(array $original, string $state = 'ACCEPTED'): array {
    return ['request_id'=>'11111111-1111-4111-8111-111111111111', 'fingerprint'=>str_repeat('f',64),
        'subject_key'=>$original['subject_key'], 'original_revision'=>$original['revision'], 'decision_version'=>$original['receipt'],
        'notice_version'=>$original['notice_version'], 'analytics'=>$original['analytics'], 'ad_measurement'=>$original['ad_measurement'],
        'personalization'=>0, 'preference_expires_at'=>$original['changed_at']+15552000, 'eligible'=>1, 'known'=>1,
        'created_at'=>$original['changed_at']+60, 'state'=>$state, 'uncertain'=>0, 'delivery_pending'=>1,
        'click_capture_state'=>'ABSENT', 'gclid_first'=>'', 'gclid_last'=>'', 'gclid_first_captured_ms'=>0,
        'gclid_last_captured_ms'=>0, 'lead_id'=>$state==='ACCEPTED'?'BSRE-SYNTHETIC-LEAD':'',
        'event_id'=>$state==='ACCEPTED'?'evt_synthetic_event':''];
}
function pc_coverage(array $snapshot, int $now): array {
    return ['kind'=>P::COVERAGE, 'snapshot_sha256'=>P::digest($snapshot), 'status'=>'COMPLETE_SYNTHETIC',
        'observed_at'=>$now, 'valid_until'=>$now+3600, 'history_pruned'=>false];
}
function pc_plan(array $snapshot, int $now): array { return P::plan($snapshot,pc_coverage($snapshot,$now),$now,true); }
function pc_row(array $plan, string $ref): array {
    foreach ($plan['rows'] as $row) if ($row['row_ref'] === $ref) return $row;
    throw new RuntimeException('Synthetic fixture row missing');
}
function pc_due(array $plan): int { return $plan['counts']['due_unreferenced_choice_rows']; }

$now=pc_time('2026-11-10T14:00:00+04:00');
$old=pc_time('2025-10-10T14:00:00+04:00');
$recent=$now-86400;
$disabled=P::plan([],[], -1);
pc_check('default_disabled_does_not_inspect_inputs',$disabled['mode']==='DISABLED' && $disabled['rows']===[] && $disabled['apply_supported']===false);
$history=[pc_history('a','1',1,$old),pc_history('a','2',2,$recent)]; $snapshot=pc_snapshot($history);
$plan=pc_plan($snapshot,$now); $oldRef='bsre_consent_history:'.str_repeat('1',32);
pc_check('older_choice_due_despite_newer_active_choice',pc_due($plan)===1 && pc_row($plan,$oldRef)['classification']==='DUE_UNREFERENCED_SYNTHETIC_REVIEW');
pc_check('active_current_state_and_history_stay_held',count(array_filter($plan['rows'],fn($r)=>in_array('CURRENT_PREFERENCE_ACTIVE',$r['reasons'],true)))===2);
pc_check('pure_plan_never_grants_source_or_execution_authority',$plan['execution']==='NONE' && !$plan['source_authenticated'] && !$plan['production_authorized'] && !$plan['apply_supported']);
$before=serialize($snapshot); $repeat=pc_plan($snapshot,$now);
pc_check('unchanged_retry_is_deterministic_and_input_is_immutable',$plan===$repeat && serialize($snapshot)===$before);
$referenced=$snapshot; $outside='1'; $referenced['history'][0]['revision']=&$outside;
pc_plan($referenced,$now);
pc_check('baseline_normalizer_cannot_mutate_caller_php_references',$outside==='1');
$map=['z'=>1,'a'=>2]; $withReference=['map'=>&$map]; P::digest($withReference);
pc_check('digest_does_not_sort_caller_referenced_maps',array_keys($map)===['z','a']);
$tomorrow=pc_plan($snapshot,$now+86400);
pc_check('later_recheck_does_not_restart_original_deadline',pc_row($tomorrow,$oldRef)['deadline_dubai']===pc_row($plan,$oldRef)['deadline_dubai']);

$choice=pc_history('a','1',1,pc_time('2024-02-29T14:00:00+04:00')); $single=pc_snapshot([$choice]);
$boundary=pc_time('2025-02-28T14:00:00+04:00');
pc_check('dubai_leap_anniversary_not_due_one_second_before',pc_due(pc_plan($single,$boundary-1))===0);
pc_check('dubai_twelve_month_boundary_exactly_due',pc_due(pc_plan($single,$boundary))===2);
pc_check('preference_180_day_expiry_is_not_retention_deadline',pc_due(pc_plan($single,$choice['changed_at']+15552000))===0);

$snapshot['captures']=[pc_capture($history[0])]; $captured=pc_plan($snapshot,$now);
pc_check('submitted_original_and_later_withdrawal_history_protected',pc_due($captured)===0 && in_array('CAPTURE_AND_WITHDRAWAL_HISTORY_REQUIRED',pc_row($captured,$oldRef)['reasons'],true));
pc_check('current_authority_preserved_for_submitted_history',in_array('CURRENT_CAPTURE_AUTHORITY_REQUIRED',pc_row($captured,'bsre_consent_state:'.str_repeat('a',64))['reasons'],true));
pc_check('captures_are_never_choice_retirement_candidates',$captured['counts']['protected_capture_rows']===1 && count(array_filter($captured['rows'],fn($r)=>$r['classification']==='PROTECTED_CAPTURE_OUTSIDE_SCOPE'))===1);
$staged=$snapshot; $staged['captures']=[pc_capture($history[0],'STAGED')];
pc_check('in_flight_original_is_preserved',pc_due(pc_plan($staged,$now))===0);

$older=[pc_history('a','1',1,$old-200*86400),pc_history('a','2',2,$old-100*86400,1),pc_history('a','3',3,$old)];
$withdrawal=pc_snapshot($older); $withdrawal['captures']=[pc_capture($older[1])]; $withPlan=pc_plan($withdrawal,$now);
pc_check('only_history_before_earliest_capture_can_be_due',pc_due($withPlan)===1 && pc_row($withPlan,$oldRef)['classification']==='DUE_UNREFERENCED_SYNTHETIC_REVIEW');
pc_check('post_capture_refusal_and_regrant_history_is_needed',pc_row($withPlan,'bsre_consent_history:'.str_repeat('3',32))['classification']==='HOLD');
$beforeNext=$withdrawal; $beforeNext['captures'][0]['created_at']=$older[2]['changed_at']-1;
pc_check('original_capture_before_next_choice_remains_valid_after_later_processing',pc_due(pc_plan($beforeNext,$now+86400))===1);
foreach([0,1]as$offset){
    $afterNext=$withdrawal; $afterNext['captures'][0]['created_at']=$older[2]['changed_at']+$offset;
    pc_check('capture_at_or_after_next_choice_holds_subject_'.$offset,pc_due(pc_plan($afterNext,$now))===0);
}

$other=pc_history('b','4',1,$old); $two=pc_snapshot(array_merge($history,[$other]));
$unknown=pc_capture($history[0]); $unknown['known']=0; $two['captures']=[$unknown];
$unknownPlan=pc_plan($two,$now);
pc_check('uncertain_known_subject_holds_its_entire_history',pc_row($unknownPlan,$oldRef)['classification']==='HOLD');
pc_check('known_subject_uncertainty_does_not_invent_unrelated_lineage',pc_row($unknownPlan,'bsre_consent_history:'.str_repeat('4',32))['classification']==='DUE_UNREFERENCED_SYNTHETIC_REVIEW');
$two['captures'][0]['subject_key']='';
pc_check('unlinked_capture_holds_all_subject_exclusions',pc_due(pc_plan($two,$now))===0);
$two['captures'][0]['subject_key']=str_repeat('a',64);
$two['captures'][0]['known']=1;
$two['captures'][0]['decision_version']=$other['receipt'];
pc_check('receipt_resolving_to_another_subject_holds_globally',pc_due(pc_plan($two,$now))===0 && in_array('CAPTURE_SUBJECT_RECEIPT_CONFLICT',pc_plan($two,$now)['global_reasons'],true));

foreach ([['decision_version',str_repeat('e',32)],['original_revision',99],['analytics',1],['notice_version','SYNTHETIC_OTHER'],
          ['created_at',$now+1],['preference_expires_at',1],['uncertain',1],['state','UNKNOWN'],['event_id','']] as $index=>$change) {
    $broken=$snapshot; $broken['captures'][0][$change[0]]=$change[1];
    pc_check('ambiguous_capture_lineage_holds_'.$index,pc_due(pc_plan($broken,$now))===0);
}
$duplicate=$snapshot; $duplicate['captures'][]=$duplicate['captures'][0];
pc_check('duplicate_request_rows_do_not_become_new_proof',in_array('DUPLICATE_CAPTURE_REQUEST',pc_plan($duplicate,$now)['global_reasons'],true));
$duplicate['captures'][1]['fingerprint']=str_repeat('b',64);
pc_check('changed_body_retry_conflict_holds_globally',in_array('CONFLICTING_CAPTURE_RETRY',pc_plan($duplicate,$now)['global_reasons'],true));
$gap=pc_snapshot([$history[1]]);
pc_check('missing_historical_revision_is_not_assumed_retired',pc_due(pc_plan($gap,$now))===0);
$duplicateReceipt=pc_snapshot([$history[0],array_merge($other,['receipt'=>$history[0]['receipt']])]);
pc_check('receipt_reuse_cannot_cross_subjects_silently',pc_due(pc_plan($duplicateReceipt,$now))===0);

$plain=pc_snapshot($history);
foreach (['unknown','expired','future','mismatch','pruned'] as $case) {
    $coverage=pc_coverage($plain,$now);
    if($case==='unknown')$coverage['status']='UNKNOWN';
    if($case==='expired')$coverage['valid_until']=$now;
    if($case==='future')$coverage['observed_at']=$now+1;
    if($case==='mismatch')$coverage['snapshot_sha256']=str_repeat('0',64);
    if($case==='pruned')$coverage['history_pruned']=true;
    pc_check('coverage_hold_'.$case,pc_due(P::plan($plain,$coverage,$now,true))===0);
}
$coverage=pc_coverage($plain,$now); $coverage['verified_live']=true;
pc_check('extra_live_verified_boolean_cannot_bypass_contract',pc_invalid(fn()=>P::plan($plain,$coverage,$now,true)));
$coverage=pc_coverage($plain,$now); $coverage['observed_at']=$old-1;
pc_check('coverage_cannot_predate_snapshot_records',pc_due(P::plan($plain,$coverage,$now,true))===0);
$regression=$plain; $regression['history'][1]['changed_at']=$old-1; $regression['state'][0]['changed_at']=$old-1; $regression['state'][0]['expires_at']=$old-1+15552000;
pc_check('time_regression_holds_subject',pc_due(pc_plan($regression,$now))===0);
$future=$plain; $future['state'][0]['expires_at']+=1;
pc_check('unknown_current_preference_window_holds_subject',pc_due(pc_plan($future,$now))===0);
$strings=$plain;
foreach(['state','history']as$part)foreach($strings[$part]as&$row)foreach(['revision','analytics','ad_measurement','personalization','changed_at','expires_at','uncertain']as$key)if(isset($row[$key]))$row[$key]=(string)$row[$key];
unset($row);
pc_check('database_unsigned_strings_preserve_classification',pc_due(pc_plan($strings,$now))===1);
$tooMany=$plain; $tooMany['history']=array_fill(0,1001,$history[0]);
pc_check('bounded_snapshot_rejects_without_partial_plan',pc_invalid(fn()=>pc_plan($tooMany,$now)));
$malformed=$plain; $malformed['history'][0]['changed_at']=1.25;
pc_check('malformed_numeric_field_rejects_without_partial_plan',pc_invalid(fn()=>pc_plan($malformed,$now)));
pc_check('clock_is_explicit_and_bounded',pc_invalid(fn()=>P::plan($plain,pc_coverage($plain,$now),PHP_INT_MAX,true)));
$deep=[]; $nested=&$deep; for($i=0;$i<10;++$i){$nested['nested']=[];$nested=&$nested['nested'];} unset($nested);
pc_check('digest_depth_is_bounded',pc_invalid(fn()=>P::digest($deep)));
$cycle=[]; $cycle['self']=&$cycle;
pc_check('cyclic_array_cannot_exhaust_digest_recursion',pc_invalid(fn()=>P::digest($cycle)));
pc_check('digest_does_not_invoke_object_serializers',pc_invalid(fn()=>P::digest(['object'=>new stdClass()])));
pc_check('nonfinite_scalar_is_a_sanitized_failure',pc_invalid(fn()=>P::digest(['number'=>INF])));
$private=$snapshot; $private['captures'][0]['gclid_first']='SYNTHETIC_PRIVATE_CLICK';
$private['history'][0]['notice_version']='SYNTHETIC_PRIVATE_NOTICE';
$serialized=json_encode(pc_plan($private,$now),JSON_THROW_ON_ERROR);
pc_check('plan_does_not_echo_click_or_notice_or_lead_fields',!str_contains($serialized,'SYNTHETIC_PRIVATE_CLICK') && !str_contains($serialized,'SYNTHETIC_PRIVATE_NOTICE') && !str_contains($serialized,'BSRE-SYNTHETIC-LEAD'));
echo json_encode(['scope'=>'SYNTHETIC_PER_CHOICE_PLANNER','status'=>'PASS','checks'=>count($checks),
    'execution'=>'NONE','source_authenticated'=>false,'production_authorized'=>false],JSON_THROW_ON_ERROR)."\n";
