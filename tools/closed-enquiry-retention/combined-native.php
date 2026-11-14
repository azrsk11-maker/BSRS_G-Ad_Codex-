<?php
declare(strict_types=1);
/** One actual route/Purpose27/Intake26/SQL-Journal enquiry; external services remain synthetic. */
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
$_SERVER['REQUEST_METHOD'] = 'POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/retention-admission/store.php';
require '/opt/lab/purpose/purpose-attribution.php';
require '/opt/lab/retention-admission/intake.php';
require '/opt/lab/receipt-recovery/receipt-recovery-wordpress.php';
require '/opt/lab/retention-admission/retention-admission.php';
require_once __DIR__ . '/fixtures.php';
require_once __DIR__ . '/WpCaptureResource.php';
require_once __DIR__ . '/ReceiverPipe.php';
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
use BSRE\RetentionAdmission as A;
use BSRE\ClosedRetention as C;

define('BSRE_PURPOSE_ATTRIBUTION_ENABLED', true);
define('BSRE_RETENTION_ADMISSION_ENABLED', true);
define('BSRE_RETENTION_ADMISSION_GENERATION', str_repeat('a', 64));
define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT', time() - 2000);
define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
define('BSRE_ROUTING_ENABLED', true);
add_action('rest_api_init', 'BSRE\\PurposeAttribution\\register_routes');
add_action('rest_api_init', 'BSRE\\ReceiptRecovery\\register_routes');
add_action('rest_api_init', 'BSRE\\RetentionAdmission\\register_routes', 1000);
$checks = []; $forwards = []; $calls = 0;
function combinedCheck(string $name, bool $ok): void
{
    global $checks;
    if (!$ok) throw new RuntimeException('Combined native assertion failed: ' . $name);
    $checks[$name] = true;
}
function combinedDb(): C\LeaseBoundWpdb
{
    global $table_prefix;
    $db = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->set_prefix($table_prefix); $db->prefix = C\WpCaptureResource::COMBINED_PREFIX;
    $db->suppress_errors(true); return $db;
}
function combinedHttpsHome($url, $path): string
{
    return 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/'));
}
function combinedApi(string $route, string $body, array $headers): WP_REST_Response
{
    global $calls;
    $_SERVER['REMOTE_ADDR'] = '198.51.100.' . (++$calls + 100);
    $request = new WP_REST_Request('POST', '/bsre/v1/' . $route);
    foreach (array_merge(['origin'=>'https://blackswanrealestate.ae', 'sec-fetch-site'=>'same-origin',
        'content-type'=>'application/json'], $headers) as $key=>$value) $request->set_header($key, $value);
    $request->set_body($body);
    $previous = array_intersect_key($_SERVER, array_flip(['HTTPS','SERVER_PORT']));
    $_SERVER['HTTPS'] = 'on'; $_SERVER['SERVER_PORT'] = '443';
    add_filter('home_url', 'combinedHttpsHome', 10, 2);
    try { return rest_do_request($request); }
    finally {
        remove_filter('home_url', 'combinedHttpsHome', 10);
        foreach (['HTTPS','SERVER_PORT'] as $key) {
            if (array_key_exists($key, $previous)) $_SERVER[$key] = $previous[$key];
            else unset($_SERVER[$key]);
        }
    }
}
$db = combinedDb(); $wpdb = $db;
$journal = new C\LabSqlJournal($db); $journal->install();
combinedCheck('new_namespace_has_no_borrowed_floor_or_history', $journal->admissionFloor() === null && !$journal->historyIncomplete());
$owner = get_user_by('login', 'synthetic_owner'); wp_set_current_user($owner->ID);
$privacy = wp_insert_post(['post_type'=>'page', 'post_status'=>'publish', 'post_name'=>'combined-synthetic-privacy',
    'post_title'=>'SYNTHETIC NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID', $privacy);
E\install(); combinedCheck('actual_purpose_27_schema_installed', P\install_consent_storage());
$store = new P\WpConsentRepository($db); P\Runtime::$store = $store;
$store->choose(str_repeat('e', 64), ['analytics'=>false,'ad_measurement'=>false], 'SYNTHETIC_SHARED_NOTICE', time());
wp_set_current_user(0);
$pipe = new SyntheticReceiverPipe();
$wpGate = A\readback(); $receiverGate = $wpGate; unset($receiverGate['routes_installed'], $receiverGate['store_installed']);
$wpSources = [];
foreach ([$store, A\Runtime::class, P\Runtime::class] as $source) {
    $wpSources[] = hash_file('sha256', (new ReflectionClass($source))->getFileName());
}
$sourceHashes = ['wp'=>C\Workflow::digest($wpSources), 'receiver'=>$pipe->call('metadata')['source_hash']];
$stable = ['wp'=>$wpGate, 'receiver'=>$receiverGate, 'source_hashes'=>$sourceHashes, 'restore_policy_hash'=>str_repeat('f', 64)];
$admissionHash = C\Workflow::digest($stable);
$cold = $pipe->call('cold_init', ['now'=>time(), 'admission_hash'=>$admissionHash, 'descriptor'=>$receiverGate]);
combinedCheck('same_source_receiver_cold_starts_without_enquiry', $cold['rows'] === 0 && $cold['source_hash'] === $sourceHashes['receiver']);
combinedCheck('actual_receiver_configuration_matches_actual_wp', $pipe->call('configure',
    ['descriptor'=>$receiverGate, 'synthetic_hmac'=>BSRE_LEAD_HMAC_SECRET]) === $receiverGate);
$admission = new class($pipe, $sourceHashes) implements C\Admission {
    public function __construct(private SyntheticReceiverPipe $pipe, private array $sourceHashes) {}
    public function readback(int $now): ?array
    {
        return ['wp'=>A\readback(), 'receiver'=>$this->pipe->call('admission_descriptor', ['now'=>$now]),
            'source_hashes'=>$this->sourceHashes, 'restore_policy_hash'=>str_repeat('f',64),
            'evidence_reference'=>'SYNTHETIC_LOCAL_ACTUAL_SOURCE_READBACK', 'evidence_hash'=>str_repeat('e',64),
            'observed_at'=>$now, 'expires_at'=>$now+300];
    }
};
add_filter('pre_http_request', function($pre, $args, $url) use ($pipe) {
    global $forwards;
    combinedCheck('relay_uses_only_explicit_synthetic_destination', $url === BSRE_LEAD_RECEIVER_URL);
    $forwards[] = $args['body'];
    $reply = $pipe->call('post_wire', ['raw'=>$args['body'], 'now'=>time()]);
    return ['headers'=>[], 'body'=>wp_json_encode($reply), 'response'=>['code'=>200]];
}, PHP_INT_MAX, 3);
$_COOKIE = [E\COOKIE=>bin2hex(random_bytes(32))];
$headers = ['x-bsre-csrf'=>E\csrf_token($_COOKIE[E\COOKIE], time()-3, wp_salt('auth'))];
$prepared = combinedApi('receipt-recovery/proof', '{}', $headers)->get_data();
combinedCheck('actual_guarded_issuer_created_request_and_admission', isset($prepared['admission'])
    && $prepared['request_id'] === $prepared['admission']['request_id']);
$payload = ['request_id'=>$prepared['request_id'], 'role'=>'tenant', 'name'=>'SYNTHETIC combined enquiry',
    'phone'=>'+971500000000', 'email'=>'fixture@example.invalid', 'country'=>'UAE', 'area'=>'Synthetic',
    'budget'=>'To discuss', 'timeline'=>'Immediate / move now', 'funding'=>'To discuss', 'property_type'=>'Apartment',
    'property_details'=>'', 'authority'=>'', 'contact_consent'=>true, 'marketing_consent'=>false, 'campaign'=>'SYNTHETIC',
    'landing_page'=>'https://blackswanrealestate.ae/enquire/rent/', 'website'=>'', 'started_at'=>(time()-5)*1000];
$wire = wp_json_encode($payload); $empty = ['first'=>null,'last'=>null];
$purposeBody = wp_json_encode(['version'=>1,'wire_body'=>$wire,'attribution'=>['version'=>1,'analytics'=>$empty,'advertising'=>$empty]]);
$withProof = $headers + ['x-bsre-admission'=>wp_json_encode($prepared['admission'])];
$accepted = combinedApi('purpose-lead', $purposeBody, $withProof)->get_data();
combinedCheck('actual_purpose_route_accepted_same_receiver_enquiry', ($accepted['accepted'] ?? false) === true && count($forwards) === 1);
$envelope = json_decode($forwards[0], true, 32, JSON_THROW_ON_ERROR);
combinedCheck('exact_actual_signed_wire_reached_no_copy_receiver', $envelope['body'] === $wire
    && $envelope['admission'] === $prepared['admission']);
combinedCheck('route_restored_local_host_before_provider', !is_ssl() && home_url() === 'http://bsre.invalid');
$identity = $pipe->call('admitted_identity', ['request_id'=>$prepared['request_id']]);
combinedCheck('actual_intake26_receipts_match_actual_route', $identity['lead_id'] === $accepted['lead_id']
    && $identity['event_id'] === $accepted['event_id'] && $identity['columns'] === 26 && $identity['email_status'] === 'QUEUED'
    && $identity['email_attempts'] === 0);
$capture = new C\WpCaptureResource($db, $journal, $store);
$table = C\WpCaptureResource::COMBINED_PREFIX . 'bsre_consent_captures';
$row = $db->get_row($db->prepare("SELECT * FROM {$table} WHERE request_id=%s", $prepared['request_id']), ARRAY_A);
combinedCheck('same_enquiry_has_all27_actual_sql_columns', is_array($row) && count($row) === 27
    && (int)$row['purpose_version'] === 1 && $row['fingerprint'] === hash('sha256',$wire));

// Named fixture aging changes two acceptance timestamps before any resource binding/fence/plan.
// PHP custody intentionally retains real time(); this supplies no genuine elapsed-time or closure evidence.
$f = C\fixture(); $f['now'] = time(); $f['journal'] = $journal; $f['admission'] = $admission;
$f['closure']['closure_id'] = $prepared['request_id'];
foreach (['request_id','lead_id','event_id'] as $key) $f['closure'][$key] = $identity[$key];
$f['closure']['email_status'] = 'RETIRED_NO_COPY'; $f['closure']['mail_message_ids'] = []; $f['closure']['revision']++;
$aged = gmdate('Y-m-d\TH:i:s.000\Z', strtotime($f['closure']['accepted_at_utc']));
combinedCheck('exact_sdk_acceptance_fixture_aged_before_review', $pipe->call('fixture_age_acceptance',
    ['request_id'=>$identity['request_id'], 'lead_id'=>$identity['lead_id'], 'event_id'=>$identity['event_id'],
        'previous_accepted_at_utc'=>$identity['accepted_at_utc'], 'accepted_at_utc'=>$aged]) === true);
combinedCheck('exact_sql_creation_fixture_aged_before_review', $db->query($db->prepare("UPDATE {$table} SET created_at=%d"
    . ' WHERE request_id=%s AND BINARY lead_id=BINARY %s AND BINARY event_id=BINARY %s AND created_at=%d',
    strtotime($f['closure']['accepted_at_utc']), $identity['request_id'], $identity['lead_id'], $identity['event_id'], (int)$row['created_at'])) === 1);
$journal->putClosure($f['closure']);
$f['adapters']['email']->rows = [];
foreach ($f['adapters']['outcome']->rows as &$outcome) {
    foreach (['request_id','lead_id','event_id','fingerprint'] as $key) $outcome[$key] = $identity[$key];
    $outcome['request_ids'] = [$identity['request_id']];
}
unset($outcome);
$scope = C\NoMailCopyProof::scope($f['closure'], $admissionHash, $identity['fingerprint']);
$pipe->call('retire', ['scope'=>$scope,'now'=>$f['now']]); // Explicit trusted synthetic authority, not an owner grant.
$intake = new SyntheticReceiverIntakeResource($pipe, $journal, $scope);
$f['adapters']['capture'] = $capture; $f['adapters']['intake'] = $intake;
$f['workflow'] = new C\Workflow($journal, $f['adapters'], $f['authority'], $admission, $pipe);
$beforeShared = [];
foreach (['state','history'] as $part) $beforeShared[$part] = $db->get_results('SELECT * FROM '
    . C\WpCaptureResource::COMBINED_PREFIX . 'bsre_consent_' . $part . ' ORDER BY ' . ($part === 'state' ? 'subject_key' : 'receipt'), ARRAY_A);
$plan = C\approved($f);
$stores = array_column($plan['resources'], 'store');
$captureStep = array_search('capture', $stores, true); $intakeStep = array_search('intake', $stores, true);
combinedCheck('one_plan_binds_both_concrete_providers_and_same_identity', is_int($captureStep) && is_int($intakeStep)
    && count($plan['resources']) === 4 && $plan['resources'][$captureStep]['binding']['request_id'] === $identity['request_id']
    && $plan['resources'][$intakeStep]['binding']['request_id'] === $identity['request_id']
    && $plan['resources'][$captureStep]['binding']['evidence_reference'] === 'bsre-wp-capture-resource-v1'
    && $plan['resources'][$intakeStep]['binding']['evidence_reference'] === 'bsre-intake26-complete-row-v1');
$freshDb = combinedDb(); $freshJournal = new C\LabSqlJournal($freshDb); $intentSeen = false;
$intake->beforeDelete = function() use ($freshJournal,$plan,$captureStep,$intakeStep,&$intentSeen) {
    $job = $freshJournal->journal($plan['digest']);
    $intentSeen = $job !== null && $job['steps'][$captureStep] === 'CONFIRMED_ABSENT'
        && $job['steps'][$intakeStep] === 'INTENT_RECORDED' && $freshJournal->historyIncomplete()
        && $freshJournal->admissionFloor() === $plan['admission_hash'];
};
$intake->loseDeleteAcknowledgement = true;
$first = $f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
combinedCheck('same_sql_job_committed_capture_absence_and_intake_intent_before_sdk_delete', $intentSeen);
combinedCheck('lost_sdk_ack_holds_one_actual_sql_workflow', $first['status'] === 'HELD'
    && $freshJournal->journal($plan['digest'])['steps'][$intakeStep] === 'INTENT_RECORDED');
$freshStore = new P\WpConsentRepository($freshDb); P\Runtime::$store = $freshStore;
$freshCapture = new C\WpCaptureResource($freshDb, $freshJournal, $freshStore);
$freshIntake = new SyntheticReceiverIntakeResource($pipe, $freshJournal, $scope);
$freshAdapters = array_replace($f['adapters'], ['capture'=>$freshCapture, 'intake'=>$freshIntake]);
$resumed = new C\Workflow($freshJournal, $freshAdapters, $f['authority'], $admission, $pipe);
$result = $resumed->execute($plan, 'synthetic-owner', time());
combinedCheck('fresh_actual_sql_journal_resumes_same_plan_to_complete', $result['status'] === 'COMPLETE'
    && $result['confirmed_absent'] === 4 && $freshJournal->journal($plan['digest'])['state'] === 'COMPLETE');
$stats = $pipe->call('stats');
combinedCheck('actual_sdk_deleted_intake_once_without_mail_or_retry_delete', $stats['rows'] === 0 && $stats['mail'] === 0
    && $stats['intake_deletes'] === 1 && $freshIntake->deletes === 0);
combinedCheck('both_concrete_provider_inventories_confirm_absence', $freshJournal->locked($scope['closure_id'],
    fn()=>$freshCapture->inventory($scope['request_id']) === [] && $freshIntake->inventory($scope['request_id']) === []));
foreach (['state','history'] as $part) {
    $after = $freshDb->get_results('SELECT * FROM ' . C\WpCaptureResource::COMBINED_PREFIX . 'bsre_consent_' . $part
        . ' ORDER BY ' . ($part === 'state' ? 'subject_key' : 'receipt'), ARRAY_A);
    combinedCheck('shared_consent_' . $part . '_preserved', $after === $beforeShared[$part]);
}
// Expiry is an actual-source backdated signed-proof fixture, not a 900-second wall-clock wait.
$expired = A\sign_new_request($scope['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, A\configuration(), time()-1000);
$before = count($forwards);
$replay = combinedApi('purpose-lead', $purposeBody, $headers+['x-bsre-admission'=>wp_json_encode($expired),'x-bsre-consent-retry'=>'1']);
combinedCheck('expired_actual_source_proof_stops_before_relay_and_sql_recreation', $replay->get_status() !== 200 && count($forwards) === $before
    && $freshJournal->locked($scope['closure_id'],fn()=>$freshCapture->inventory($scope['request_id'])) === []);
combinedCheck('original_exact_receiver_envelope_stays_sender_fenced',
    $pipe->call('post_wire',['raw'=>$forwards[0],'now'=>time()])['code'] === 'NO_COPY_REQUEST_RETIRED');
$new = combinedApi('receipt-recovery/proof', '{}', $headers)->get_data();
$payload['request_id'] = $new['request_id']; $payload['started_at'] = (time()-5)*1000;
$newWire = wp_json_encode($payload);
$healthyBody = wp_json_encode(['version'=>1,'wire_body'=>$newWire,'attribution'=>['version'=>1,'analytics'=>$empty,'advertising'=>$empty]]);
$healthy = combinedApi('purpose-lead', $healthyBody, $headers+['x-bsre-admission'=>wp_json_encode($new['admission'])])->get_data();
combinedCheck('healthy_new_server_uuid_still_admitted_through_actual_route', ($healthy['accepted'] ?? false) === true
    && $new['request_id'] !== $scope['request_id'] && $pipe->call('stats')['rows'] === 1 && $pipe->call('stats')['mail'] === 0);
combinedCheck('same_completed_enquiry_stays_absent_after_healthy_admission',
    $resumed->execute($plan,'synthetic-owner',time())['status'] === 'COMPLETE');
combinedCheck('history_and_admission_floor_remain_persisted', $freshJournal->historyIncomplete()
    && $freshJournal->admissionFloor() === $plan['admission_hash']);
echo json_encode(['phase'=>'combined_closed_enquiry_native','checks'=>$checks,
    'composition'=>'ONE guarded WordPress enquiry, actual Purpose27 SQL capture, source-derived Intake26 SDK and MariaDB Journal Workflow',
    'synthetic_data_only'=>true,'aging'=>'Exact synthetic SQL creation/SDK acceptance aging before bindings/fence/plan',
    'expiry'=>'Actual-source backdated signed-proof fixture; no wall-clock expiry wait',
    'doubles'=>['Google services','closure/business evidence','sender retirement authority','mailbox/runtime/backup custody','outcome and empty email resources','owner approval'],
    'real_provider_acceptance'=>false,'durable_absence_claimed'=>false,'production_authorized'=>false], JSON_THROW_ON_ERROR) . "\n";
