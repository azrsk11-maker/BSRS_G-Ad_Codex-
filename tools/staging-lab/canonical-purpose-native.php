<?php
declare(strict_types=1);
/** Test-only postlude. Actual G2/P choose/context/writer; no capture INSERT, forward or provider. */
function canonical_purpose_native_checks(
    \BSRE\ActualRetention\CanonicalCaptureProducer $producer,
    \BSRE\ClosedRetention\LeaseBoundWpdb $db,
    \BSRE\ActualRetention\ActualJournal $journal
): array {
    global $wpdb;
    if(PHP_SAPI!=='cli' || !defined('WP_CONTENT_DIR') || WP_CONTENT_DIR!=='/opt/lab/g35/wp-content'
        || DB_NAME!=='bsre_synthetic' || DB_HOST!=='localhost:/tmp/bsre.sock' || DB_USER!=='root' || DB_PASSWORD!==''
        || $wpdb!==$db || !preg_match('/^[a-z][a-z0-9_]{0,38}_synthetic_$/D',$db->prefix)
        || $db->custodyIsActive()) throw new \RuntimeException('CANONICAL_PURPOSE_FIXED_G35_LAB_REQUIRED');
    $producer->assertCurrent($db);
    $checks=[];
    $check=static function(string $name,bool $ok)use(&$checks):void {
        $checks[$name]=$ok;
        file_put_contents('/tmp/g35-purpose-progress.json',json_encode($checks,JSON_THROW_ON_ERROR));
        if(!$ok)throw new \RuntimeException('CANONICAL_PURPOSE_NATIVE_CHECK_FAILED:'.$name);
    };
    $denied=static function(callable $work):bool {
        try{$work();return false;}catch(\Throwable $error){return $error->getMessage()==='CANONICAL_PRODUCER_PURPOSE_RECORD_INVALID';}
    };
    $count=static function()use($db):string {
        $db->last_error='';$n=$db->get_var("SELECT COUNT(*) FROM {$db->prefix}bsre_consent_captures");
        if($db->last_error!=='' || !preg_match('/^[0-9]+$/D',(string)$n))throw new \RuntimeException('CANONICAL_PURPOSE_CAPTURE_COUNT_UNVERIFIED');return (string)$n;
    };
    $beforeCount=$count();$savedCookies=$_COOKIE;$savedGet=$_GET;$savedUser=get_current_user_id();
    $savedUri=$_SERVER['REQUEST_URI']??null;$savedSubmission=\BSRE\PurposeAttribution\Runtime::$submission;
    $store=\BSRE\SharedRepository\repository();$rows=[];$inputs=[];$lastChoice=null;$nonce=bin2hex(random_bytes(16));
    $rebind=static function(array $row,$record):array {
        $row['purpose_json']=\BSRE\PurposeAttribution\canonical($record);
        $row['purpose_record_hash']=hash('sha256',$row['fingerprint']."\n".$row['purpose_hash']."\n".$row['purpose_json']);return $row;
    };
    $touch=static function(array $choice,int $stamp):array {
        return ['capture_id'=>wp_generate_uuid4(),'decision_version'=>$choice['receipt'],'notice_version'=>\BSRE\Enquiries\CONSENT_NOTICE_VERSION,
            'landing_page'=>rtrim(home_url(),'/').'/enquire/off-plan/','referrer'=>'','timestamp'=>$stamp*1000,
            'parameters'=>(object)['utm_source'=>'synthetic_canonical_purpose']];
    };
    $prepare=static function(string $label,?array $choice,array $side)use($db,$store,$journal,$savedUser,$producer,$nonce,$check,&$inputs):array {
        // Eligibility is produced by the real visitor context, not the logged-in owner's fixture session.
        wp_set_current_user(0);$_GET=[];$_SERVER['REQUEST_URI']='/enquire/';
        $context=\BSRE\Enquiries\consent_current($store,false);$snapshot=$context['snapshot'];
        $known=$snapshot['known']&&$snapshot['acknowledged'];
        $check($label.'_actual_server_known',$known===($choice!==null));
        if($choice!==null)$check($label.'_actual_server_receipt',$snapshot['decision_version']===$choice['receipt']);
        $capture=['request_id'=>wp_generate_uuid4(),'fingerprint'=>hash('sha256','SYNTHETIC_CANONICAL_PURPOSE|'.$nonce.'|'.$label),
            'subject_key'=>$context['row']['subject_key']??'','original_revision'=>(int)($context['row']['revision']??0),
            'decision_version'=>$known?$snapshot['decision_version']:bin2hex(random_bytes(16)),
            'notice_version'=>\BSRE\Enquiries\CONSENT_NOTICE_VERSION,'analytics'=>$known&&$snapshot['preferences']['analytics']?1:0,
            'ad_measurement'=>$known&&$snapshot['preferences']['ad_measurement']?1:0,'personalization'=>0,
            'preference_expires_at'=>$known?$snapshot['preference_expires_at']:0,'eligible'=>$known&&$snapshot['measurement_eligible']?1:0,
            'known'=>$known?1:0,'created_at'=>time(),'uncertain'=>0,'state'=>'STAGED'];
        $input=\BSRE\PurposeAttribution\normalize_sidecar(json_decode(wp_json_encode($side),false,16,JSON_THROW_ON_ERROR),time());
        $inputs[$label]=$input;
        wp_set_current_user($savedUser);
        $result=$journal->locked(wp_generate_uuid4(),static function()use($db,$producer,$capture,$input):array {
            // choose() already committed. prepare_capture() only reads/locks; no outer transaction
            // is invented around an actual repository method that owns START/COMMIT.
            \BSRE\PurposeAttribution\Runtime::$submission=['fingerprint'=>$capture['fingerprint'],'sidecar'=>$input];
            $row=$capture+\BSRE\PurposeAttribution\prepare_capture($db,$capture);
            $producer->assertPurposeRecord($row);return $row;
        });
        $check($label.'_writer_preserves_capture_permissions',$result['known']===$capture['known']&&$result['eligible']===$capture['eligible']&&$result['analytics']===$capture['analytics']&&$result['ad_measurement']===$capture['ad_measurement']);
        return $result;
    };
    try {
        foreach(['analytics'=>[true,false],'advertising'=>[false,true],'both'=>[true,true],'refusal'=>[false,false],'unknown'=>null] as $label=>$flags) {
            $_COOKIE=[];$_GET=[];$_SERVER['REQUEST_URI']='/enquire/';$choice=null;
            if($flags!==null){
                $subject=bin2hex(random_bytes(16));$key=\BSRE\Enquiries\consent_subject_key($subject);
                $check($label.'_fresh_synthetic_subject',$store->current($key)===null);
                // Actual server choice writes only this new synthetic preference/history subject.
                $choice=$store->choose($key,['analytics'=>$flags[0],'ad_measurement'=>$flags[1]],\BSRE\Enquiries\CONSENT_NOTICE_VERSION,time()-10);
                $_COOKIE[\BSRE\Enquiries\CONSENT_COOKIE]=\BSRE\Enquiries\consent_cookie_token($subject,$choice['expires_at'],wp_salt('auth'));
                if($flags[0]||$flags[1])$lastChoice=$choice;
            }
            $claim=$choice??$lastChoice;
            if($claim===null)throw new \RuntimeException('CANONICAL_PURPOSE_FIXTURE_CHOICE_REQUIRED');
            $a=$touch($claim,time()-2);$d=$touch($claim,time()-2);
            $side=['version'=>1,'analytics'=>['first'=>$a,'last'=>$a],'advertising'=>['first'=>$d,'last'=>$d]];
            $rows[$label]=$prepare($label,$choice,$side);
            $record=json_decode($rows[$label]['purpose_json'],true,16,JSON_THROW_ON_ERROR);
            foreach(['analytics','advertising'] as $purpose){
                $expected=$flags!==null&&($purpose==='analytics'?$flags[0]:$flags[1]);
                $check($label.'_'.$purpose.'_actual_writer_mask',($record[$purpose]['first']!==null)===$expected&&($record[$purpose]['last']!==null)===$expected);
            }
        }
        // Gaps/withdrawals are genuine SQL history; the actual writer independently masks slots.
        $_COOKIE=[];$subject=bin2hex(random_bytes(16));$key=\BSRE\Enquiries\consent_subject_key($subject);$now=time();
        $check('asymmetric_fresh_subject',$store->current($key)===null);
        $old=$store->choose($key,['analytics'=>true,'ad_measurement'=>true],\BSRE\Enquiries\CONSENT_NOTICE_VERSION,$now-30);
        $store->choose($key,['analytics'=>false,'ad_measurement'=>false],\BSRE\Enquiries\CONSENT_NOTICE_VERSION,$now-20);
        $current=$store->choose($key,['analytics'=>true,'ad_measurement'=>true],\BSRE\Enquiries\CONSENT_NOTICE_VERSION,$now-10);
        $_COOKIE[\BSRE\Enquiries\CONSENT_COOKIE]=\BSRE\Enquiries\consent_cookie_token($subject,$current['expires_at'],wp_salt('auth'));
        $first=$touch($old,$now-29);$last=$touch($current,$now-2);
        $side=['version'=>1,'analytics'=>['first'=>$first,'last'=>$last],'advertising'=>['first'=>$first,'last'=>$last]];
        $asymmetric=$prepare('asymmetric',$current,$side);$record=json_decode($asymmetric['purpose_json'],true,16,JSON_THROW_ON_ERROR);
        $check('asymmetric_actual_writer_first_masked_last_retained',$record['analytics']['first']===null&&$record['analytics']['last']!==null&&$record['advertising']['first']===null&&$record['advertising']['last']!==null);

        $producer->assertPurposeRecord($rows['both']);$check('both_retained_record_revalidation',true);
        $sqlStrings=$rows['both'];foreach(['created_at','known','eligible','analytics','ad_measurement','personalization','preference_expires_at'] as $key)$sqlStrings[$key]=(string)$sqlStrings[$key];
        $producer->assertPurposeRecord($sqlStrings);$check('actual_sql_integer_string_shape',true);
        $legacy=$rows['unknown'];$legacy['purpose_version']=0;$legacy['purpose_hash']='';$legacy['purpose_record_hash']='';$legacy['purpose_json']=null;
        $producer->assertPurposeRecord($legacy);$check('legacy_unknown_v0_healthy',true);
        $bad=$legacy;$bad['analytics']=1;$check('unknown_v0_grant_cannot_upgrade',$denied(static fn()=>$producer->assertPurposeRecord($bad)));
        $bad=$rows['both'];$bad['personalization']=1;$check('personalization_still_denied',$denied(static fn()=>$producer->assertPurposeRecord($bad)));
        $bad=$rows['both'];$bad['purpose_record_hash']=str_repeat('0',64);$check('tampered_bound_hash_rejected',$denied(static fn()=>$producer->assertPurposeRecord($bad)));
        $bad=$rows['both'];$bad['purpose_json']='{malformed';$bad['purpose_record_hash']=hash('sha256',$bad['fingerprint']."\n".$bad['purpose_hash']."\n".$bad['purpose_json']);
        $check('malformed_json_with_rebound_hash_rejected',$denied(static fn()=>$producer->assertPurposeRecord($bad)));
        $record=json_decode($rows['both']['purpose_json'],false,16,JSON_THROW_ON_ERROR);$record->analytics->first->capture_id=str_repeat('a',80);$bad=$rebind($rows['both'],$record);
        $check('oversized_touch_id_with_rebound_hash_rejected',$denied(static fn()=>$producer->assertPurposeRecord($bad)));
        // Explicit synthetic uniform time translation of a real-code writer record. It proves
        // retained-fact semantics only; it is not evidence of an actual historical capture.
        $historical=$rows['both'];$record=json_decode($historical['purpose_json'],false,16,JSON_THROW_ON_ERROR);$shift=200*86400;
        $historical['created_at']-=$shift;$historical['preference_expires_at']-=$shift;
        foreach(['analytics','advertising'] as $purpose)foreach(['first','last'] as $slot){$record->$purpose->$slot->timestamp-=$shift*1000;$record->$purpose->$slot->expires_at-=$shift;}
        $historicalInput=json_decode(\BSRE\PurposeAttribution\canonical($inputs['both']),false,16,JSON_THROW_ON_ERROR);
        foreach(['analytics','advertising'] as $purpose)foreach(['first','last'] as $slot)$historicalInput->$purpose->$slot->timestamp-=$shift*1000;
        $historicalInput=\BSRE\PurposeAttribution\normalize_sidecar($historicalInput,$historical['created_at']);
        $historical['purpose_hash']=hash('sha256',\BSRE\PurposeAttribution\canonical($historicalInput));
        $historical=$rebind($historical,$record);$producer->assertPurposeRecord($historical);
        $check('synthetic_time_translation_expired_now_valid_at_capture',$record->analytics->first->expires_at<time()&&$record->analytics->first->expires_at>$historical['created_at']);
        $check('capture_rows_unchanged',$count()===$beforeCount);
        return $checks;
    } finally {
        \BSRE\PurposeAttribution\Runtime::$submission=$savedSubmission;$_COOKIE=$savedCookies;$_GET=$savedGet;wp_set_current_user($savedUser);
        if($savedUri===null)unset($_SERVER['REQUEST_URI']);else $_SERVER['REQUEST_URI']=$savedUri;
    }
}
