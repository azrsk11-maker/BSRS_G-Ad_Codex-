<?php
declare(strict_types=1);
define('ABSPATH', __DIR__);
function add_action(...$args): void {}
function home_url($path = ''): string { return 'https://blackswanrealestate.ae' . $path; }
$fixture = getenv('BSRE_PURPOSE_FIXTURE') ?: __DIR__ . '/../../staging-lab/fixtures/bsre-enquiries';
require $fixture . '/includes/protocol.php';
require $fixture . '/includes/consent.php';
require __DIR__ . '/purpose-attribution.php';
$retention = getenv('BSRE_RETENTION_SOURCE') ?: __DIR__ . '/../../consent-retention';
require $retention . '/RetentionInventory.php';
require __DIR__ . '/purpose-retention.php';
use BSRE\PurposeAttribution as P;
use BSRE\Enquiries as E;
$checks = 0;
function check(bool $ok): void { global $checks; if (!$ok) throw new RuntimeException('Purpose assertion failed'); $checks++; }
function rejected(callable $call): void { try { $call(); } catch (InvalidArgumentException $e) { check(true); return; } throw new RuntimeException('Expected rejection'); }
$now = 1794146400;
$touch = ['capture_id' => 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'decision_version' => str_repeat('a', 32),
    'notice_version' => E\CONSENT_NOTICE_VERSION, 'landing_page' => 'https://blackswanrealestate.ae/enquire/rent/?private=excluded',
    'referrer' => '', 'timestamp' => ($now - 30) * 1000, 'parameters' => ['gclid' => 'Exact_Click.Ab~9', 'utm_id' => 'SYNTHETIC_ID', 'google_campaign_id' => '000123']];
$wire = ['version' => 1, 'analytics' => ['first' => null, 'last' => null], 'advertising' => ['first' => $touch, 'last' => $touch]];
$object = fn($value) => json_decode(json_encode($value), false, 20, JSON_THROW_ON_ERROR);
$valid = P\normalize_sidecar($object($wire), $now);
check($valid['advertising']['first']['parameters']->gclid === 'Exact_Click.Ab~9');
check($valid['advertising']['first']['parameters']->google_campaign_id === '000123');
check($valid['advertising']['first']['landing_page'] === 'https://blackswanrealestate.ae/enquire/rent/');
foreach (['unknown' => 'x', 'email' => 'fixture@example.invalid'] as $key => $value) {
    $bad = $wire; $bad['advertising']['first']['parameters'][$key] = $value; rejected(fn() => P\normalize_sidecar($object($bad), $now));
}
foreach ([str_repeat('x',257), "raw\nvalue", ['array'], 123, ''] as $value) {
    $bad = $wire; $bad['advertising']['first']['parameters']['gclid'] = $value; rejected(fn() => P\normalize_sidecar($object($bad), $now));
}
foreach ([($now+301)*1000, ($now-30)*1000+0.5, '1794146370000'] as $stamp) {
    $bad = $wire; $bad['advertising']['first']['timestamp'] = $stamp; rejected(fn() => P\normalize_sidecar($object($bad), $now));
}
$bad = $wire; $bad['analytics'] = $bad['advertising']; rejected(fn() => P\normalize_sidecar($object($bad), $now));
$bad = $wire; $bad['advertising']['first']['referrer'] = 'https://example.invalid/'; rejected(fn() => P\normalize_sidecar($object($bad), $now));
$bad = $wire; $bad['advertising']['first']['landing_page'] = 'https://user:password@blackswanrealestate.ae/x'; rejected(fn() => P\normalize_sidecar($object($bad), $now));
$bad = $wire; $bad['advertising']['last']['timestamp']++; rejected(fn() => P\normalize_sidecar($object($bad), $now));
$current = ['revision' => 2, 'receipt' => str_repeat('b',32), 'analytics' => 1, 'ad_measurement' => 1,
    'notice_version' => E\CONSENT_NOTICE_VERSION, 'uncertain' => 0, 'expires_at' => $now+100];
$history = [array_diff_key($current,['expires_at'=>true]) + ['changed_at' => $now-60]];
$history[0]['revision'] = 1; $history[0]['receipt'] = str_repeat('a',32);
$history[] = array_diff_key($current,['expires_at'=>true]) + ['changed_at' => $now-10];
$verified = P\verified_touch($valid['advertising']['first'], 'advertising', $current, $history, $now);
check($verified !== null && $verified['original_revision'] === 1);
$badHistory = $history; $badHistory[0]['ad_measurement'] = 0;
check(P\verified_touch($valid['advertising']['first'], 'advertising', $current, $badHistory, $now) === null);
$badHistory = $history; $badHistory[1]['ad_measurement'] = 0;
check(P\verified_touch($valid['advertising']['first'], 'advertising', $current, $badHistory, $now) === null);
$badHistory = $history; $badHistory[1]['revision'] = 3;
check(P\verified_touch($valid['advertising']['first'], 'advertising', $current, $badHistory, $now) === null);
$badHistory = $history; $badHistory[1]['changed_at'] = $now-40;
check(P\verified_touch($valid['advertising']['first'], 'advertising', $current, $badHistory, $now) === null);
check(P\verified_touch($valid['advertising']['first'], 'advertising', $current, [], $now) === null);
$row = ['purpose_version'=>1,'fingerprint'=>str_repeat('c',64),'purpose_hash'=>str_repeat('d',64),'purpose_json'=>'{"version":1}'];
$row['purpose_record_hash'] = hash('sha256', $row['fingerprint']."\n".$row['purpose_hash']."\n".$row['purpose_json']);
P\assert_record($row); check(true);
$restorable = $row;
$restorable['purpose_json'] = json_encode(['advertising'=>['first'=>['decision_version'=>str_repeat('a',32)],'last'=>null],'analytics'=>['first'=>null,'last'=>null]]);
$restorable['purpose_record_hash'] = hash('sha256',$restorable['fingerprint']."\n".$restorable['purpose_hash']."\n".$restorable['purpose_json']);
\BSRE\PurposeRetention\RetentionInventory::assertRestoreReferences(['captures'=>[$restorable]],[]); check(true);
try { \BSRE\PurposeRetention\RetentionInventory::assertRestoreReferences(['captures'=>[$restorable]],[str_repeat('a',32)=>true]); check(false); }
catch (RuntimeException $e) { check($e->getMessage()==='RESTORED_CAPTURE_REQUIRES_RECONCILIATION'); }
\BSRE\PurposeRetention\RetentionInventory::assertRestoreReferences(['captures'=>[['request_id'=>'legacy']]],[]); check(true);
$capture = ['request_id'=>'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','fingerprint'=>str_repeat('c',64),'subject_key'=>'','original_revision'=>0,'decision_version'=>str_repeat('a',32),'notice_version'=>E\CONSENT_NOTICE_VERSION,'analytics'=>0,'ad_measurement'=>0,'personalization'=>0,'preference_expires_at'=>0,'eligible'=>0,'known'=>0,'created_at'=>$now,'state'=>'STAGED','uncertain'=>1,'delivery_pending'=>1,'click_capture_state'=>'NOT_PERMITTED','gclid_first'=>'','gclid_last'=>'','gclid_first_captured_ms'=>0,'gclid_last_captured_ms'=>0,'lead_id'=>'','event_id'=>'','purpose_version'=>0,'purpose_hash'=>'','purpose_record_hash'=>'','purpose_json'=>null];
$review = \BSRE\PurposeRetention\RetentionInventory::plan(['kind'=>\BSRE\RetentionReview\RetentionInventory::KIND,'state'=>[],'history'=>[],'captures'=>[$capture]],$now,true);
check($review['mode']==='REVIEW_ONLY');
$capture['purpose_version']=1;$capture['purpose_hash']=$restorable['purpose_hash'];$capture['purpose_record_hash']=$restorable['purpose_record_hash'];$capture['purpose_json']=$restorable['purpose_json'];
$review = \BSRE\PurposeRetention\RetentionInventory::plan(['kind'=>\BSRE\RetentionReview\RetentionInventory::KIND,'state'=>[],'history'=>[],'captures'=>[$capture]],$now,true);
check($review['mode']==='REVIEW_ONLY');
$row['purpose_json'] .= ' ';
try { P\assert_record($row); check(false); } catch (RuntimeException $e) { check($e->getMessage()==='PURPOSE_RECORD_CONFLICT'); }
echo json_encode(['phase'=>'purpose_attribution_pure','checks'=>$checks,'status'=>'PASS','native_database_verified'=>false]) . "\n";
