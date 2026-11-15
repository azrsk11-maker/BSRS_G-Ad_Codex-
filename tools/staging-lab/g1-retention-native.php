<?php
declare(strict_types=1);
namespace BSRE\G1RetentionLab;
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;

/** Actual store/SQL interposition only; no mocked query results or policy-purge claim. */
final class RetireBeforeStage implements P\ConsentRepository {
    private P\ConsentRepository $inner;
    private $db;
    private string $retire;
    public ?array $observed = null;
    public function __construct(P\ConsentRepository $inner, $db, string $retire) {
        if (!in_array($retire,['none','both','state','history'],true)) throw new \RuntimeException('G1_FIXED_CASE_ONLY');
        $this->inner=$inner; $this->db=$db; $this->retire=$retire;
    }
    public function database() { return $this->inner->database(); }
    public function admissionContract(): string { return $this->inner->admissionContract(); }
    public function current(string $s): ?array { return $this->inner->current($s); }
    public function choose(string $s,array $f,string $n,int $now,bool $u=false): array { return $this->inner->choose($s,$f,$n,$now,$u); }
    public function stage(array $capture): array {
        $this->observed=$capture;
        if ($this->retire!=='none') {
            if ($capture['subject_key']==='') throw new \RuntimeException('G1_EXPECTED_SUBJECT');
            if ($this->db->query('START TRANSACTION')===false) throw new \RuntimeException('G1_SQL_FAILED');
            try {
                foreach (['state','history'] as $kind) {
                    if ($this->retire!==$kind && $this->retire!=='both') continue;
                    $n=$this->db->delete($this->db->prefix.'bsre_consent_'.$kind,['subject_key'=>$capture['subject_key']]);
                    if ($n===false || $n<1) throw new \RuntimeException('G1_RETIREMENT_NOT_COMMITTED');
                }
                if ($this->db->query('COMMIT')===false) throw new \RuntimeException('G1_SQL_FAILED');
            } catch (\Throwable $e) { $this->db->query('ROLLBACK'); throw $e; }
        }
        return $this->inner->stage($capture);
    }
    public function link(string $r,string $f,string $l,string $e): array { return $this->inner->link($r,$f,$l,$e); }
    public function uncertain(string $r,string $f): void { $this->inner->uncertain($r,$f); }
    public function revoked(string $s,int $r,string $p): bool { return $this->inner->revoked($s,$r,$p); }
    public function exportRows(array $r): array { return $this->inner->exportRows($r); }
}

function runG1RetentionNative(): void {
    global $wpdb, $forwards, $checks;
    if (wp_get_environment_type()!=='local' || $wpdb->prefix!=='admission_g1_synthetic_') throw new \RuntimeException('G1_ISOLATED_MODE_REQUIRED');
    $base=P\Runtime::$store;
    if (!$base instanceof P\WpConsentRepository) throw new \RuntimeException('G1_ACTUAL_STORE_REQUIRED');
    $cases=[
        ['legacy_unknown','lead','none',false,'none',true],
        ['purpose_unknown','purpose-lead','none',false,'none',true],
        ['legacy_denied','lead','deny',true,'none',true],
        ['purpose_denied','purpose-lead','deny',true,'none',true],
        ['purpose_known_grant','purpose-lead','grant',true,'none',true],
        ['legacy_v0_grant_retired','lead','grant',true,'both',false],
        ['legacy_v0_history_retired','lead','grant',true,'history',false],
        ['legacy_v0_state_retired','lead','grant',true,'state',false],
        ['purpose_known_retired','purpose-lead','grant',true,'both',false],
        ['legacy_unknown_stale_subject','lead','grant',false,'both',true],
        ['purpose_unknown_stale_subject','purpose-lead','grant',false,'both',true],
    ];
    foreach ($cases as [$label,$route,$choiceKind,$sendDecision,$retire,$shouldAccept]) {
        $_COOKIE=[E\COOKIE=>bin2hex(random_bytes(32))];
        $choice=null;
        if ($choiceKind!=='none') {
            $subject=bin2hex(random_bytes(16)); $key=E\consent_subject_key($subject);
            $choice=$base->choose($key,['analytics'=>$choiceKind==='grant','ad_measurement'=>false],E\CONSENT_NOTICE_VERSION,time()-10);
            $_COOKIE[E\CONSENT_COOKIE]=E\consent_cookie_token($subject,$choice['expires_at'],wp_salt('auth'));
        }
        $headers=['x-bsre-csrf'=>E\csrf_token($_COOKIE[E\COOKIE],time()-3,wp_salt('auth'))];
        $prepared=\admission_api('receipt-recovery/proof','{}',$headers)->get_data();
        \admission_check('g1_'.$label.'_real_admission_prepared',isset($prepared['request_id'],$prepared['admission']));
        $headers['x-bsre-admission']=wp_json_encode($prepared['admission']);
        if ($sendDecision) $headers['x-bsre-consent-decision']=$choice['receipt'];
        $payload=['request_id'=>$prepared['request_id'],'role'=>'tenant','name'=>'SYNTHETIC G1 '.$label,
            'phone'=>'+971500000000','email'=>'fixture@example.invalid','country'=>'UAE','area'=>'Synthetic',
            'budget'=>'To discuss','timeline'=>'Immediate / move now','funding'=>'To discuss','property_type'=>'Apartment',
            'property_details'=>'','authority'=>'','contact_consent'=>true,'marketing_consent'=>false,
            'campaign'=>'SYNTHETIC','landing_page'=>'https://blackswanrealestate.ae/enquire/rent/','website'=>'','started_at'=>(time()-5)*1000];
        $wire=wp_json_encode($payload);
        $side=['version'=>1,'analytics'=>['first'=>null,'last'=>null],'advertising'=>['first'=>null,'last'=>null]];
        if ($choiceKind==='grant') {
            $touch=['capture_id'=>wp_generate_uuid4(),'decision_version'=>$choice['receipt'],'notice_version'=>E\CONSENT_NOTICE_VERSION,
                'landing_page'=>'https://blackswanrealestate.ae/enquire/rent/','referrer'=>'','timestamp'=>(time()-1)*1000,'parameters'=>(object)['utm_source'=>'synthetic_g1']];
            $side['analytics']=['first'=>$touch,'last'=>$touch];
        }
        $body=$route==='lead' ? $wire : wp_json_encode(['version'=>1,'wire_body'=>$wire,'attribution'=>$side]);
        $probe=new RetireBeforeStage($base,$wpdb,$retire); P\Runtime::$store=$probe;
        $before=count($forwards);
        try { $response=\admission_api($route,$body,$headers); }
        finally { P\Runtime::$store=$base; }
        $data=$response->get_data();
        $row=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$prepared['request_id']),ARRAY_A);
        \admission_check('g1_'.$label.'_actual_stage_observed',is_array($probe->observed));
        \admission_check('g1_'.$label.'_known_matches_server_snapshot',(int)$probe->observed['known']===($sendDecision?1:0));
        if ($shouldAccept) {
            \admission_check('g1_'.$label.'_accepted',($data['accepted']??false)===true && count($forwards)===$before+1 && is_array($row));
            \admission_check('g1_'.$label.'_receipt_linked',($row['state']??'')==='ACCEPTED' && $row['lead_id']===$data['lead_id'] && $row['event_id']===$data['event_id']);
            foreach (['known','eligible','analytics','ad_measurement','personalization','preference_expires_at',
                'click_capture_state','gclid_first','gclid_last','gclid_first_captured_ms','gclid_last_captured_ms',
                'purpose_version','purpose_hash','purpose_record_hash','purpose_json'] as $column) {
                \admission_check('g1_'.$label.'_persisted_column_'.$column,array_key_exists($column,$row));
            }
            // Here first attempts run without QA/login markers. Eligibility is
            // known && measurement_eligible(raw), not an optional-purpose grant:
            // acknowledged denial stays eligible=1, unknown must be eligible=0.
            $expectedKnown=$sendDecision ? 1 : 0;
            $expectedAnalytics=$sendDecision && $choiceKind==='grant' ? 1 : 0;
            $dbInt=static fn($actual,int $expected): bool => $actual===$expected || $actual===(string)$expected;
            \admission_check('g1_'.$label.'_persisted_consent_contract',
                $dbInt($row['known'],$expectedKnown) && $dbInt($row['eligible'],$expectedKnown)
                && $dbInt($row['analytics'],$expectedAnalytics) && $dbInt($row['ad_measurement'],0)
                && $dbInt($row['personalization'],0));
            // All fixed cases deny advertising, including the analytics grant.
            \admission_check('g1_'.$label.'_persisted_no_click_evidence',
                $row['click_capture_state']==='NOT_PERMITTED' && $row['gclid_first']==='' && $row['gclid_last']===''
                && $dbInt($row['gclid_first_captured_ms'],0) && $dbInt($row['gclid_last_captured_ms'],0));
            if (!$sendDecision) \admission_check('g1_'.$label.'_unknown_has_no_preference_expiry',$dbInt($row['preference_expires_at'],0));
            if ($route==='purpose-lead') {
                \admission_check('g1_'.$label.'_purpose_v1',(int)$row['purpose_version']===1);
                $stored=json_decode($row['purpose_json'],true,16,JSON_THROW_ON_ERROR);
                foreach (['analytics','advertising'] as $purpose) {
                    \admission_check('g1_'.$label.'_persisted_'.$purpose.'_shape',isset($stored[$purpose]) && is_array($stored[$purpose])
                        && array_key_exists('first',$stored[$purpose]) && array_key_exists('last',$stored[$purpose]));
                }
                \admission_check('g1_'.$label.'_purpose_evidence',($label==='purpose_known_grant')
                    ? ($stored['analytics']['first']['parameters']['utm_source']??null)==='synthetic_g1'
                        && ($stored['analytics']['last']['parameters']['utm_source']??null)==='synthetic_g1'
                        && $stored['advertising']['first']===null && $stored['advertising']['last']===null
                    : $stored['analytics']['first']===null && $stored['analytics']['last']===null && $stored['advertising']['first']===null && $stored['advertising']['last']===null);
            } else \admission_check('g1_'.$label.'_legacy_v0',(int)$row['purpose_version']===0
                && $row['purpose_hash']==='' && $row['purpose_record_hash']==='' && $row['purpose_json']==='');
            if (!$sendDecision || $choiceKind==='deny') {
                \admission_check('g1_'.$label.'_no_optional_grants',(int)$row['analytics']===0 && (int)$row['ad_measurement']===0);
            }
        } else {
            \admission_check('g1_'.$label.'_held_before_forward',$response->get_status()===503 && ($data['code']??null)==='ADMISSION_UNCONFIRMED' && ($data['accepted']??false)!==true && count($forwards)===$before);
            \admission_check('g1_'.$label.'_no_capture_resurrection',$row===null);
        }
        if ($retire!=='none') {
            foreach (['state','history'] as $kind) {
                if ($retire!==$kind && $retire!=='both') continue;
                $n=(int)$wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_{$kind} WHERE subject_key=%s",$probe->observed['subject_key']));
                \admission_check('g1_'.$label.'_'.$kind.'_still_retired',$n===0);
            }
        }
        if ($label==='legacy_unknown_stale_subject') {
            // Same accepted raw wire, now claiming retired known purpose touches:
            // the existing v0 record must never upgrade to a v1 grant/sidecar.
            $oldRow=$row; $beforeUpgrade=count($forwards);
            $upgrade=\admission_api('purpose-lead',wp_json_encode(['version'=>1,'wire_body'=>$wire,'attribution'=>$side]),
                $headers+['x-bsre-consent-decision'=>$choice['receipt']]);
            $afterRow=$wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s",$prepared['request_id']),ARRAY_A);
            \admission_check('g1_unknown_v0_retired_sidecar_upgrade_conflicts',$upgrade->get_status()===409 && count($forwards)===$beforeUpgrade);
            \admission_check('g1_unknown_v0_retired_sidecar_cannot_upgrade',$afterRow===$oldRow && (int)$afterRow['known']===0 && (int)$afterRow['purpose_version']===0);
        }
    }
    echo wp_json_encode(['phase'=>'g1_retention_known_evidence','cases'=>count($cases),'checks'=>$checks,
        'limits'=>'Actual PHP/SQL handlers with deterministic committed-deletion interposition; not concurrent processes or policy-purge authorization.'])."\n";
}
