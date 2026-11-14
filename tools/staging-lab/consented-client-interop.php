<?php
/** Synthetic consented client -> real WordPress -> pinned receiver. */
use BSRE\Enquiries as Intake;

$_SERVER['HTTPS'] = 'on';
$_SERVER['SERVER_PORT'] = '443';
$_SERVER['REQUEST_METHOD'] = 'POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/receipt-recovery/receipt-recovery-wordpress.php';
add_action('rest_api_init', 'BSRE\\ReceiptRecovery\\register_routes');
add_filter('home_url', fn($url, $path) => 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/')), 10, 2);

$checks = [];
$scenarios = [];
$current = [];
$rawBodies = [];
$receipts = [];
$inspected = [];
$withdrawals = [];
$leadRequests = 0;
$receiverCalls = 0;
function consented_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Consented client check failed: ' . $name);
    $checks[$name] = true;
}
function consented_api(string $path, array $body = [], array $headers = []): WP_REST_Response {
    $request = new WP_REST_Request('POST', '/bsre/v1/' . $path);
    foreach (array_merge(['origin' => 'https://blackswanrealestate.ae', 'sec-fetch-site' => 'same-origin',
        'content-type' => 'application/json'], $headers) as $name => $value) $request->set_header($name, $value);
    $request->set_body($body ? wp_json_encode($body) : '{}');
    return rest_do_request($request);
}
function consented_choice(array $scenario, string $csrf, bool $deny = false): array {
    $response = consented_api('consent/update', [
        'analytics' => !$deny && $scenario['analytics'], 'ad_measurement' => !$deny && $scenario['advertising'],
        'personalization' => false, 'notice_version' => Intake\CONSENT_NOTICE_VERSION,
    ], ['x-bsre-consent-csrf' => $csrf]);
    consented_check('real_consent_update_succeeds', $response->get_status() === 200 && $response->get_data()['known'] === true);
    return $response->get_data();
}

wp_set_current_user(get_user_by('login', 'synthetic_owner')->ID);
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$drafts = Intake\ensure_drafts(false);
foreach ($drafts['pages'] as $id) wp_update_post(['ID' => $id, 'post_status' => 'publish']);
$privacy = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish',
    'post_name' => 'synthetic-consented-privacy', 'post_title' => 'SYNTHETIC CONSENTED LAB NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID', $privacy);
define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
define('BSRE_ROUTING_ENABLED', true);
consented_check('five_native_routes_ready', count(Intake\live_paths()) === 5 && Intake\ready());
wp_set_current_user(0);

$receiver = proc_open(['node', '/opt/lab/receiver-bridge.mjs'], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $receiverPipes);
consented_check('receiver_started', is_resource($receiver));
stream_set_timeout($receiverPipes[1], 10);
function consented_receiver(array $command): array {
    global $receiverPipes;
    $line = wp_json_encode($command) . "\n";
    if (fwrite($receiverPipes[0], $line) !== strlen($line)) throw new RuntimeException('Receiver pipe write failed');
    fflush($receiverPipes[0]);
    $reply = fgets($receiverPipes[1], 1000000);
    if ($reply === false || !str_ends_with($reply, "\n")) throw new RuntimeException('Receiver reply incomplete');
    return json_decode($reply, true, 512, JSON_THROW_ON_ERROR);
}
add_filter('pre_http_request', function($pre, $args, $url) use (&$receiverCalls, &$receipts) {
    consented_check('receiver_is_local_pipe_destination', $url === BSRE_LEAD_RECEIVER_URL);
    $receiverCalls++;
    $envelope = json_decode($args['body'], true, 16, JSON_THROW_ON_ERROR);
    $payload = json_decode($envelope['body'], true, 32, JSON_THROW_ON_ERROR);
    $receipt = consented_receiver(['op' => 'post', 'raw' => $args['body']]);
    consented_check('receiver_accepts_real_client_envelope', ($receipt['accepted'] ?? false) === true);
    $receipts[$payload['request_id']] = $receipt;
    return ['headers' => [], 'body' => wp_json_encode($receipt), 'response' => ['code' => 200]];
}, PHP_INT_MAX, 3);

$client = proc_open(['node', '/opt/lab/consented-client-interop.mjs'], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $clientPipes);
consented_check('client_started', is_resource($client));
stream_set_timeout($clientPipes[1], 20);
$complete = false;
$roles = ['off-plan' => 'off_plan', 'resale' => 'resale', 'rent' => 'tenant', 'sell' => 'seller', 'let' => 'landlord'];
while (($line = fgets($clientPipes[1], 1000000)) !== false) {
    consented_check('client_pipe_message_complete', str_ends_with($line, "\n"));
    $message = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
    $operation = $message['op'] ?? '';
    if ($operation === 'session') {
        $scenario = $message['scenario'];
        consented_check('scenario_is_supported_synthetic_role', ($roles[$scenario['slug'] ?? ''] ?? '') === ($scenario['role'] ?? '')
            && is_bool($scenario['analytics'] ?? null) && is_bool($scenario['advertising'] ?? null));
        $key = $scenario['slug'] . '-' . (int) $scenario['analytics'] . (int) $scenario['advertising'];
        consented_check('each_scenario_runs_once', !isset($scenarios[$key]));
        // The pipe has no browser cookie jar. Seed the anonymous intake cookie;
        // consent/context and consent/update issue their own real signed cookies.
        $_COOKIE = [Intake\COOKIE => bin2hex(random_bytes(32))];
        $_SERVER['REMOTE_ADDR'] = '198.51.100.' . (50 + count($scenarios));
        $context = consented_api('context');
        consented_check('real_lead_context_succeeds', $context->get_status() === 200);
        $consent = consented_api('consent/context');
        consented_check('real_consent_context_succeeds', $consent->get_status() === 200 && $consent->get_data()['ok'] === true);
        $csrf = $consent->get_data()['csrf_token'];
        $snapshot = consented_choice($scenario, $csrf);
        $current = ['key' => $key, 'scenario' => $scenario, 'snapshot' => $snapshot, 'consent_csrf' => $csrf];
        $scenarios[$key] = $current;
        // Use a mature synthetic challenge to avoid twenty wall-clock sleeps.
        $reply = ['csrf' => Intake\csrf_token($_COOKIE[Intake\COOKIE], time() - 3, wp_salt('auth')),
            'snapshot' => $snapshot, 'utm_source' => 'SYNTHETIC_SOURCE', 'gclid' => 'Synthetic_Click_Ab9'];
    } elseif ($operation === 'request') {
        $path = parse_url($message['url'] ?? '', PHP_URL_PATH);
        consented_check('client_uses_only_local_intake_routes', ($message['url'] ?? '') === 'https://blackswanrealestate.ae' . $path
            && in_array($path, ['/wp-json/bsre/v1/lead', '/wp-json/bsre/v1/receipt-recovery/proof'], true));
        consented_check('client_request_is_authenticated_post', ($message['method'] ?? '') === 'POST'
            && ($message['credentials'] ?? '') === 'same-origin');
        $request = new WP_REST_Request('POST', substr($path, strlen('/wp-json')));
        foreach ($message['headers'] as $name => $value) $request->set_header($name, $value);
        $request->set_header('origin', 'https://blackswanrealestate.ae');
        $request->set_header('sec-fetch-site', 'same-origin');
        $request->set_body($message['body']);
        if ($path === '/wp-json/bsre/v1/lead') {
            $payload = json_decode($message['body'], true, 32, JSON_THROW_ON_ERROR);
            consented_check('only_synthetic_contact_data_enters_intake', str_starts_with($payload['name'] ?? '', 'SYNTHETIC consent lab ')
                && ($payload['email'] ?? '') === 'fixture@example.invalid' && ($payload['phone'] ?? '') === '+971500000000');
            consented_check('actual_payload_role_and_destination_match_scenario', $payload['role'] === $current['scenario']['role']
                && $payload['landing_page'] === 'https://blackswanrealestate.ae/enquire/' . $current['scenario']['slug'] . '/');
            consented_check('actual_original_decision_header', $request->get_header('x-bsre-consent-decision') === $current['snapshot']['decision_version']);
            consented_check('private_capture_token_absent_from_wire', !str_contains($message['body'], 'capture_id'));
            $current['request_id'] = $payload['request_id'];
            $rawBodies[$payload['request_id']] = $message['body'];
            $leadRequests++;
        }
        $response = rest_do_request($request);
        $reply = ['status' => $response->get_status(), 'body' => $response->get_data()];
    } elseif ($operation === 'inspect' || $operation === 'withdraw') {
        $id = $message['request_id'] ?? '';
        consented_check('inspection_is_current_synthetic_request', $id === ($current['request_id'] ?? null) && isset($rawBodies[$id]));
        $capture = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $id), ARRAY_A);
        $scenario = $current['scenario'];
        $values = [];
        if ($operation === 'inspect') {
            consented_check('scenario_inspected_once_' . $current['key'], !isset($inspected[$current['key']]));
            $inspected[$current['key']] = true;
            $values['raw_fingerprint_matches_actual_request'] = $capture['fingerprint'] === hash('sha256', $rawBodies[$id]);
            $values['original_choice_is_known_and_eligible'] = (int) $capture['known'] === 1 && (int) $capture['eligible'] === 1;
            $values['original_choice_matches_actual_server_decision'] = $capture['decision_version'] === $current['snapshot']['decision_version']
                && (int) $capture['analytics'] === (int) $scenario['analytics'] && (int) $capture['ad_measurement'] === (int) $scenario['advertising'];
            $values['durable_receipt_matches_actual_receiver'] = $capture['state'] === 'ACCEPTED' && (int) $capture['delivery_pending'] === 0
                && $capture['lead_id'] === $receipts[$id]['lead_id'] && $capture['event_id'] === $receipts[$id]['event_id'];
            $expected = $scenario['advertising'] ? 'Synthetic_Click_Ab9' : '';
            $values['server_captures_only_permitted_exact_click'] = $capture['gclid_first'] === $expected && $capture['gclid_last'] === $expected
                && $capture['click_capture_state'] === ($scenario['advertising'] ? 'CAPTURED' : 'NOT_PERMITTED');
            $export = Intake\consent_export_document([$id], Intake\consent_repository())['rows'][0];
            $values['local_permission_export_matches_ad_choice'] = $export['export_eligible'] === $scenario['advertising'];
            $values['private_capture_has_no_contact_body'] = !array_intersect(['name', 'phone', 'email', 'payload_json', 'capture_id'], array_keys($capture));
        } else {
            consented_check('scenario_withdrawn_once_' . $current['key'], isset($inspected[$current['key']]) && !isset($withdrawals[$current['key']]));
            $withdrawals[$current['key']] = true;
            $withdrawn = consented_choice($scenario, $current['consent_csrf'], true);
            $export = Intake\consent_export_document([$id], Intake\consent_repository())['rows'][0];
            $values['withdrawal_saved'] = !$withdrawn['preferences']['analytics'] && !$withdrawn['preferences']['ad_measurement'];
            $values['withdrawal_omits_exported_clicks'] = !$export['export_eligible'] && $export['gclid_first'] === '' && $export['gclid_last'] === '';
            consented_choice($scenario, $current['consent_csrf']);
            $after = Intake\consent_export_document([$id], Intake\consent_repository())['rows'][0];
            $values['regrant_does_not_restore_original_export'] = !$after['export_eligible'] && $after['gclid_first'] === '' && $after['gclid_last'] === '';
            $saved = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $id), ARRAY_A);
            $values['original_capture_survives_withdrawal_and_regrant'] = $saved === $capture;
        }
        foreach ($values as $name => $value) consented_check($current['key'] . '_' . $name, $value);
        $reply = ['checks' => $values];
    } elseif ($operation === 'complete') {
        consented_check('all_client_assertions_passed', count($message['checks'] ?? []) >= 200
            && count(array_filter($message['checks'], fn($value) => $value !== true)) === 0);
        $checks = array_merge($checks, $message['checks']);
        $complete = true;
        $reply = ['complete' => true];
    } else {
        throw new RuntimeException('Unsupported consented client operation');
    }
    $encoded = wp_json_encode($reply) . "\n";
    consented_check('client_pipe_reply_written', fwrite($clientPipes[0], $encoded) === strlen($encoded));
    fflush($clientPipes[0]);
    if ($complete) break;
}
fclose($clientPipes[0]); fclose($clientPipes[1]);
consented_check('client_finished', proc_close($client) === 0 && $complete);
consented_check('twenty_unique_scenarios_and_one_intake_each', count($scenarios) === 20 && $leadRequests === 20 && $receiverCalls === 20 && count($rawBodies) === 20);
consented_check('all_twenty_scenarios_inspected_and_withdrawn', count($inspected) === 20 && count($withdrawals) === 20);
for ($batch = 0; $batch < 4; $batch++) $state = consented_receiver(['op' => 'outbox']);
consented_check('twenty_durable_rows_and_email_copies', count($state['rows']) === 20 && count($state['mail']) === 20);
$again = consented_receiver(['op' => 'outbox']);
consented_check('outbox_recheck_has_no_duplicate_email', count($again['mail']) === 20);
foreach ($state['rows'] as $index => $row) {
    $normalized = json_decode($row[5], true, 32, JSON_THROW_ON_ERROR);
    $id = $row[0];
    $original = json_decode($rawBodies[$id], true, 32, JSON_THROW_ON_ERROR);
    consented_check('receiver_row_' . $index . '_keeps_attribution', $normalized['attribution'] === $original['attribution']);
    consented_check('receiver_row_' . $index . '_normalized_fingerprint', $row[4] === hash('sha256', $row[5]));
    consented_check('receiver_row_' . $index . '_same_id_email', str_contains($state['mail'][$index]['subject'], $row[1]));
}
fclose($receiverPipes[0]); fclose($receiverPipes[1]);
consented_check('receiver_finished', proc_close($receiver) === 0);
echo wp_json_encode(['phase' => 'consented_client_wordpress_receiver', 'status' => 'PASS', 'checks' => $checks,
    'scenarios' => 20, 'synthetic_only' => true, 'dom_and_storage_are_doubles' => true,
    'network_transport_is_pipe' => true, 'google_services_are_doubles' => true,
    'browser_consent_bridge_accepted' => false, 'qualified_import_accepted' => false, 'production_acceptance' => false]) . "\n";
