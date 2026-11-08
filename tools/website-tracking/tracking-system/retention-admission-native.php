<?php
/** Actual isolated WordPress/store handlers and a network-free pinned receiver. */
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
use BSRE\RetentionAdmission as A;

define('WP_ENVIRONMENT_TYPE', 'local');
$_SERVER['HTTPS'] = 'on'; $_SERVER['SERVER_PORT'] = '443'; $_SERVER['REQUEST_METHOD'] = 'POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/retention-admission/store.php';
require '/opt/lab/purpose/purpose-attribution.php';
require '/opt/lab/retention-admission/intake.php';
require '/opt/lab/receipt-recovery/receipt-recovery-wordpress.php';
require '/opt/lab/retention-admission/retention-admission.php';
define('BSRE_PURPOSE_ATTRIBUTION_ENABLED', true);
define('BSRE_RETENTION_ADMISSION_ENABLED', true);
define('BSRE_RETENTION_ADMISSION_GENERATION', str_repeat('a', 64));
define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT', time() - 2000);
define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
define('BSRE_ROUTING_ENABLED', true);
add_filter('home_url', fn($url, $path) => 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/')), 10, 2);
add_action('rest_api_init', 'BSRE\\PurposeAttribution\\register_routes');
add_action('rest_api_init', 'BSRE\\ReceiptRecovery\\register_routes');
add_action('rest_api_init', 'BSRE\\RetentionAdmission\\register_routes', 1000);
$checks = []; $forwards = [];
function admission_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Admission native check failed: ' . $name);
    $checks[$name] = true;
}
$owner = get_user_by('login', 'synthetic_owner'); wp_set_current_user($owner->ID);
$privacy = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish', 'post_name' => 'admission-synthetic-privacy', 'post_title' => 'SYNTHETIC NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID', $privacy);
$wpdb->prefix = 'admission_synthetic_';
E\install(); // Installs the original guarded rate table for this isolated prefix.
admission_check('additive_store_installed', P\install_consent_storage());
P\Runtime::$store = new P\WpConsentRepository($wpdb);
admission_check('original_wire_ready', E\ready());
wp_set_current_user(0);
$bridge = proc_open(['node', '/opt/lab/tracking-system/retention-admission-bridge.mjs'], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $pipes);
admission_check('receiver_started', is_resource($bridge)); stream_set_timeout($pipes[1], 10);
function admission_receiver(array $value): array {
    global $pipes;
    $line = wp_json_encode($value) . "\n";
    if (fwrite($pipes[0], $line) !== strlen($line) || !fflush($pipes[0])) throw new RuntimeException('Admission pipe write failed');
    $reply = fgets($pipes[1], 100000);
    if ($reply === false || !str_ends_with($reply, "\n")) throw new RuntimeException('Admission pipe timed out');
    return json_decode($reply, true, 32, JSON_THROW_ON_ERROR);
}
$gate = A\configuration();
admission_receiver(['op' => 'configure', 'properties' => ['RETENTION_ADMISSION_REQUIRED' => 'true',
    'RETENTION_ADMISSION_GENERATION' => $gate['generation'], 'RETENTION_ADMISSION_AUDIENCE' => $gate['audience'],
    'RETENTION_ADMISSION_ACTIVATED_AT' => (string) $gate['activated_at']]]);
add_filter('pre_http_request', function ($pre, $args, $url) {
    global $forwards;
    admission_check('only_synthetic_receiver_destination', $url === BSRE_LEAD_RECEIVER_URL);
    $forwards[] = $args['body'];
    $reply = admission_receiver(['op' => 'post', 'raw' => $args['body']]);
    return ['headers' => [], 'body' => wp_json_encode($reply), 'response' => ['code' => 200]];
}, PHP_INT_MAX, 3);
$apiCalls = 0;
function admission_api(string $route, string $body, array $headers = []): WP_REST_Response {
    global $apiCalls;
    $_SERVER['REMOTE_ADDR'] = '198.51.100.' . (++$apiCalls + 100);
    $request = new WP_REST_Request('POST', '/bsre/v1/' . $route);
    foreach (array_merge(['origin' => 'https://blackswanrealestate.ae', 'sec-fetch-site' => 'same-origin', 'content-type' => 'application/json'], $headers) as $key => $value) $request->set_header($key, $value);
    $request->set_body($body);
    return rest_do_request($request);
}
$_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))];
$csrf = E\csrf_token($_COOKIE[E\COOKIE], time() - 3, wp_salt('auth'));
$headers = ['x-bsre-csrf' => $csrf];
$prepared = admission_api('receipt-recovery/proof', '{}', $headers)->get_data();
admission_check('real_prepare_selects_matching_uuid', isset($prepared['admission']) && $prepared['request_id'] === $prepared['admission']['request_id']);
$selected = admission_api('receipt-recovery/proof', wp_json_encode(['request_id' => $prepared['request_id']]), $headers);
admission_check('caller_selected_uuid_mint_denied', $selected->get_status() === 400);
$readback = A\readback();
admission_check('all_post_routes_and_store_enforced', $readback['routes_installed'] && $readback['store_installed']);
$payload = ['request_id' => $prepared['request_id'], 'role' => 'tenant', 'name' => 'SYNTHETIC admission',
    'phone' => '+971500000000', 'email' => 'fixture@example.invalid', 'country' => 'UAE', 'area' => 'Synthetic',
    'budget' => 'To discuss', 'timeline' => 'Immediate / move now', 'funding' => 'To discuss', 'property_type' => 'Apartment',
    'property_details' => '', 'authority' => '', 'contact_consent' => true, 'marketing_consent' => false,
    'campaign' => 'SYNTHETIC', 'landing_page' => 'https://blackswanrealestate.ae/enquire/rent/', 'website' => '', 'started_at' => (time() - 5) * 1000];
$wire = wp_json_encode($payload);
$before = count($forwards);
$missing = admission_api('lead', $wire, $headers);
admission_check('legacy_unknown_without_admission_denied_before_forward', $missing->get_status() !== 200 && count($forwards) === $before);
admission_check('legacy_unknown_has_no_capture', (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_captures") === 0);
$withProof = $headers + ['x-bsre-admission' => wp_json_encode($prepared['admission'])];
$accepted = admission_api('lead', $wire, $withProof)->get_data();
admission_check('real_legacy_entry_accepts_proved_request', ($accepted['accepted'] ?? false) === true);
$forwarded = json_decode(end($forwards), true, 32, JSON_THROW_ON_ERROR);
admission_check('wire_body_exact_and_proof_is_outside', $forwarded['body'] === $wire && isset($forwarded['admission']) && !str_contains($wire, 'session_hash'));
$withoutHeader = admission_api('lead', $wire, $headers)->get_data();
admission_check('known_legacy_retry_without_header_keeps_receipt', ($withoutHeader['lead_id'] ?? null) === $accepted['lead_id']);
$expired = A\sign_new_request($prepared['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, $gate, time() - 1000);
$expiredHeaders = $headers + ['x-bsre-admission' => wp_json_encode($expired), 'x-bsre-consent-retry' => '1'];
$replayed = admission_api('lead', $wire, $expiredHeaders)->get_data();
admission_check('known_expired_proof_keeps_receipt', ($replayed['lead_id'] ?? null) === $accepted['lead_id'] && ($replayed['event_id'] ?? null) === $accepted['event_id']);
$changed = $payload; $changed['area'] = 'Changed';
admission_check('known_changed_body_conflicts', admission_api('lead', wp_json_encode($changed), $withProof)->get_status() === 409);
admission_check('synthetic_purge_transaction_started', $wpdb->query('START TRANSACTION') !== false);
$locked = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s FOR UPDATE", $payload['request_id']), ARRAY_A);
admission_check('synthetic_purge_locks_one_capture', is_array($locked));
admission_check('synthetic_purge_removes_one_capture', $wpdb->delete($wpdb->prefix . 'bsre_consent_captures', ['request_id' => $payload['request_id']]) === 1);
admission_check('synthetic_purge_commits', $wpdb->query('COMMIT') !== false);
admission_receiver(['op' => 'purge_synthetic', 'request_id' => $payload['request_id']]);
$before = count($forwards);
$denied = admission_api('lead', $wire, $expiredHeaders);
admission_check('purged_expired_request_stops_before_forward', $denied->get_status() !== 200 && count($forwards) === $before);
admission_check('purged_expired_request_does_not_recreate_capture', (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_captures") === 0);
$oldEnvelope = E\envelope($wire, BSRE_LEAD_HMAC_SECRET, (int) floor(microtime(true) * 1000)); $oldEnvelope['admission'] = $expired;
admission_check('direct_receiver_expired_replay_denied', admission_receiver(['op' => 'post', 'raw' => wp_json_encode($oldEnvelope)])['code'] === 'ADMISSION_REQUIRED');
$next = admission_api('receipt-recovery/proof', '{}', $headers)->get_data();
$nextHeaders = $headers + ['x-bsre-admission' => wp_json_encode($next['admission'])];
admission_check('fresh_other_uuid_proof_cannot_revive_old_body', admission_api('lead', $wire, $nextHeaders)->get_status() !== 200);
$payload['request_id'] = $next['request_id'];
$purposeWire = wp_json_encode($payload);
$emptyHistory = ['first' => null, 'last' => null];
$purposeBody = wp_json_encode(['version' => 1, 'wire_body' => $purposeWire,
    'attribution' => ['version' => 1, 'analytics' => $emptyHistory, 'advertising' => $emptyHistory]]);
$purposeAccepted = admission_api('purpose-lead', $purposeBody, $nextHeaders)->get_data();
admission_check('purpose_entry_uses_same_admission_contract', ($purposeAccepted['accepted'] ?? false) === true);
$purposeRow = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $next['request_id']), ARRAY_A);
admission_check('purpose_history_keeps_own_schema', is_array($purposeRow) && (int) $purposeRow['purpose_version'] === 1);
admission_check('fresh_proof_did_not_revive_retired_uuid', (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $prepared['request_id'])) === 0);
$wpdb->delete($wpdb->prefix . 'bsre_consent_captures', ['request_id' => $next['request_id']]);
admission_receiver(['op' => 'purge_synthetic', 'request_id' => $next['request_id']]);
$snapshot = admission_receiver(['op' => 'snapshot']);
admission_check('no_resurrected_receiver_row_or_email', $snapshot['rows'] === 0 && $snapshot['mail'] === 0 && $snapshot['columns'] === 26);
$client = proc_open(['node', '/opt/lab/tracking-system/retention-admission-client.mjs'], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $clientPipes);
admission_check('actual_client_started', is_resource($client)); stream_set_timeout($clientPipes[1], 15);
$clientDone = false;
while (($line = fgets($clientPipes[1], 100000)) !== false) {
    $message = json_decode($line, true, 32, JSON_THROW_ON_ERROR);
    if ($message['op'] === 'setup') {
        $_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))];
        $clientCsrf = E\csrf_token($_COOKIE[E\COOKIE], time() - 3, wp_salt('auth'));
        $reply = ['csrf' => $clientCsrf];
    } elseif ($message['op'] === 'request') {
        $path = parse_url($message['url'], PHP_URL_PATH);
        admission_check('client_uses_only_owned_admission_paths', $message['url'] === 'https://blackswanrealestate.ae' . $path
            && in_array($path, ['/wp-json/bsre/v1/lead', '/wp-json/bsre/v1/receipt-recovery/proof'], true));
        if (str_ends_with($path, '/lead')) {
            $sent = json_decode($message['body'], true, 16, JSON_THROW_ON_ERROR);
            admission_check('actual_client_contact_is_synthetic', $sent['name'] === 'SYNTHETIC admission client' && $sent['email'] === 'fixture@example.invalid');
        }
        $response = admission_api(substr($path, strlen('/wp-json/bsre/v1/')), $message['body'], $message['headers']);
        $reply = ['status' => $response->get_status(), 'body' => $response->get_data()];
    } elseif ($message['op'] === 'complete') {
        $clientDone = true;
        $stored = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $message['request_id']), ARRAY_A);
        admission_check('actual_client_receipt_is_durable', is_array($stored) && $stored['state'] === 'ACCEPTED' && $stored['lead_id'] !== '');
        $reply = ['ok' => true];
    } else throw new RuntimeException('Unknown admission client operation');
    $encoded = wp_json_encode($reply) . "\n";
    if (fwrite($clientPipes[0], $encoded) !== strlen($encoded) || !fflush($clientPipes[0])) throw new RuntimeException('Admission client IPC failed');
    if ($clientDone) break;
}
fclose($clientPipes[0]); fclose($clientPipes[1]);
admission_check('actual_client_finished', proc_close($client) === 0 && $clientDone);
fclose($pipes[0]); fclose($pipes[1]); admission_check('receiver_exit', proc_close($bridge) === 0);
echo wp_json_encode(['phase' => 'retention_admission_native', 'status' => 'PASS', 'checks' => $checks,
    'synthetic_only' => true, 'production_purge_authorized' => false]) . "\n";
