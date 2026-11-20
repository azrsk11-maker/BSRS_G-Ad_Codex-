<?php
/** Actual JS client -> WordPress routes -> pinned receiver through local pipes. */
use BSRE\Enquiries as Intake;

$_SERVER['HTTPS'] = 'on';
$_SERVER['SERVER_PORT'] = '443';
$_SERVER['REQUEST_METHOD'] = 'POST';
require '/opt/wordpress/wp-load.php';
require '/opt/lab/receipt-recovery/receipt-recovery-wordpress.php';
add_action('rest_api_init', 'BSRE\\ReceiptRecovery\\register_routes');
add_filter('home_url', fn($url, $path) => 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/')), 10, 2);

$checks = [];
$receiverCalls = 0;
$leadRequests = 0;
$sessions = 0;
$requestIds = [];
$upstreamMode = in_array('--upstream', $argv, true);
$statusCalls = 0;
$acceptedReceipts = [];
$originalCaptures = [];
if ($upstreamMode) define('BSRE_RECEIPT_STATUS_ENABLED', true);
function client_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Client integration check failed: ' . $name);
    $checks[$name] = true;
}

wp_set_current_user(get_user_by('login', 'synthetic_owner')->ID);
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$drafts = Intake\ensure_drafts(false);
foreach ($drafts['pages'] as $id) wp_update_post(['ID' => $id, 'post_status' => 'publish']);
$privacy = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish',
    'post_name' => 'synthetic-client-privacy', 'post_title' => 'SYNTHETIC CLIENT LAB NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID', $privacy);
define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
define('BSRE_ROUTING_ENABLED', true);
client_check('five_synthetic_native_routes_ready', count(Intake\live_paths()) === 5 && Intake\ready());
wp_set_current_user(0);

$receiverCommand = ['node', '/opt/lab/receiver-bridge.mjs'];
if ($upstreamMode) array_push($receiverCommand, '--receipt-status', '/opt/lab/tracking-system/build-receipt-status-candidate.mjs');
$receiver = proc_open($receiverCommand, [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $receiverPipes);
client_check('receiver_process_started', is_resource($receiver));
stream_set_timeout($receiverPipes[1], 10);
function client_receiver(array $command): array {
    global $receiverPipes;
    $line = wp_json_encode($command) . "\n";
    if (fwrite($receiverPipes[0], $line) !== strlen($line)) throw new RuntimeException('Receiver pipe write failed');
    fflush($receiverPipes[0]);
    $reply = fgets($receiverPipes[1], 1000000);
    if ($reply === false || !str_ends_with($reply, "\n")) throw new RuntimeException('Receiver pipe reply incomplete');
    return json_decode($reply, true, 512, JSON_THROW_ON_ERROR);
}
add_filter('pre_http_request', function($pre, $args, $url) use (&$receiverCalls, &$statusCalls, &$acceptedReceipts, $upstreamMode) {
    client_check('receiver_destination_is_synthetic_only', $url === BSRE_LEAD_RECEIVER_URL);
    $envelope = json_decode($args['body'], true, 16, JSON_THROW_ON_ERROR);
    if (($envelope['purpose'] ?? '') === 'bsre-receipt-status-v1') {
        $statusCalls++;
        client_check('status_lookup_requires_upstream_mode', $upstreamMode);
        client_check('status_lookup_has_no_contact_payload', array_keys($envelope) === ['version', 'purpose', 'request_id', 'timestamp', 'signature']);
        $receipt = client_receiver(['op' => 'post', 'raw' => $args['body']]);
        return ['headers' => [], 'body' => wp_json_encode($receipt), 'response' => ['code' => 200]];
    }
    $receiverCalls++;
    $receipt = client_receiver(['op' => 'post', 'raw' => $args['body']]);
    client_check('receiver_accepts_actual_client_payload', ($receipt['accepted'] ?? false) === true);
    if ($upstreamMode) {
        $payload = json_decode($envelope['body'], true, 32, JSON_THROW_ON_ERROR);
        $acceptedReceipts[$payload['request_id']] = $receipt;
        return new WP_Error('synthetic_upstream_acknowledgement_lost');
    }
    return ['headers' => [], 'body' => wp_json_encode($receipt), 'response' => ['code' => 200]];
}, PHP_INT_MAX, 3);

$clientCommand = ['node', '/opt/lab/client-interop.mjs'];
if ($upstreamMode) $clientCommand[] = '--upstream';
$client = proc_open($clientCommand, [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $clientPipes);
client_check('client_process_started', is_resource($client));
stream_set_timeout($clientPipes[1], 20);
$complete = false;
while (($line = fgets($clientPipes[1], 1000000)) !== false) {
    client_check('client_pipe_message_complete', str_ends_with($line, "\n"));
    $message = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
    $operation = $message['op'] ?? '';
    if ($operation === 'session') {
        $sessions++;
        $_COOKIE = [Intake\COOKIE => bin2hex(random_bytes(32))];
        $_SERVER['REMOTE_ADDR'] = '198.51.100.' . (210 + $sessions);
        // A mature synthetic challenge avoids wall-clock sleeps in this CLI lab.
        $reply = ['csrf' => Intake\csrf_token($_COOKIE[Intake\COOKIE], time() - 3, wp_salt('auth'))];
    } elseif ($operation === 'stats') {
        $last = $requestIds ? $requestIds[count($requestIds) - 1] : '';
        $reply = ['lead_requests' => $leadRequests, 'receiver_calls' => $receiverCalls,
            'status_calls' => $statusCalls, 'accepted_reference' => $acceptedReceipts[$last]['lead_id'] ?? null];
    } elseif ($operation === 'request') {
        $path = parse_url($message['url'] ?? '', PHP_URL_PATH);
        client_check('client_uses_only_allowed_local_routes',
            ($message['url'] ?? '') === 'https://blackswanrealestate.ae' . $path
            && in_array($path, ['/wp-json/bsre/v1/lead', '/wp-json/bsre/v1/receipt-recovery/proof', '/wp-json/bsre/v1/receipt-recovery/status'], true));
        client_check('client_uses_authenticated_post', ($message['method'] ?? '') === 'POST'
            && ($message['credentials'] ?? '') === 'same-origin');
        $request = new WP_REST_Request('POST', substr($path, strlen('/wp-json')));
        foreach ($message['headers'] as $key => $value) $request->set_header($key, $value);
        // Browsers supply these transport headers. This pipe has no HTTP stack.
        $request->set_header('origin', 'https://blackswanrealestate.ae');
        $request->set_header('sec-fetch-site', 'same-origin');
        $request->set_body($message['body']);
        if ($path === '/wp-json/bsre/v1/lead') {
            $leadRequests++;
            $payload = json_decode($message['body'], true, 32, JSON_THROW_ON_ERROR);
            client_check('only_synthetic_client_data_enters_intake', str_starts_with($payload['name'] ?? '', 'TEST synthetic client ')
                && ($payload['email'] ?? '') === 'fixture@example.invalid');
            $requestIds[] = $payload['request_id'];
        }
        $response = rest_do_request($request);
        $reply = ['status' => $response->get_status(), 'body' => $response->get_data()];
        if ($upstreamMode && $path === '/wp-json/bsre/v1/lead') {
            $originalCaptures[$payload['request_id']] = $wpdb->get_row($wpdb->prepare(
                "SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $payload['request_id']
            ), ARRAY_A);
            client_check('upstream_loss_precedes_wordpress_linkage', $reply['status'] === 503
                && $originalCaptures[$payload['request_id']]['state'] === 'STAGED'
                && (int) $originalCaptures[$payload['request_id']]['delivery_pending'] === 1);
        }
        if (str_ends_with($path, '/status')) {
            client_check('recovery_response_is_reference_only', array_keys($reply['body']) === ['status', 'reference']
                && $reply['body']['status'] === 'ACCEPTED');
        }
    } elseif ($operation === 'complete') {
        client_check('all_client_checks_passed', count($message['checks'] ?? []) === 45
            && count(array_filter($message['checks'], fn($value) => $value !== true)) === 0);
        $checks = array_merge($checks, $message['checks']);
        $complete = true;
        $reply = ['complete' => true];
    } else {
        throw new RuntimeException('Unsupported client pipe operation');
    }
    $encoded = wp_json_encode($reply) . "\n";
    client_check('client_pipe_reply_written', fwrite($clientPipes[0], $encoded) === strlen($encoded));
    fflush($clientPipes[0]);
    if ($complete) break;
}
fclose($clientPipes[0]);
fclose($clientPipes[1]);
client_check('client_completed_cleanly', proc_close($client) === 0 && $complete);
client_check('one_intake_and_receiver_call_per_role', $sessions === 5 && $leadRequests === 5 && $receiverCalls === 5
    && count(array_unique($requestIds)) === 5);
$state = client_receiver(['op' => 'outbox']);
client_check('exactly_five_synthetic_rows_and_mails', count($state['rows']) === 5 && count($state['mail']) === 5);
$again = client_receiver(['op' => 'outbox']);
client_check('outbox_retry_does_not_duplicate_mail', count($again['mail']) === 5);
$slots = implode(',', array_fill(0, count($requestIds), '%s'));
$captures = $wpdb->get_results($wpdb->prepare(
    "SELECT state,delivery_pending,lead_id,event_id FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id IN ({$slots})", ...$requestIds
), ARRAY_A);
client_check('all_five_wordpress_receipts_durably_linked', count($captures) === 5
    && count(array_filter($captures, fn($row) => $row['state'] !== 'ACCEPTED' || (int) $row['delivery_pending'] !== 0
        || $row['lead_id'] === '' || $row['event_id'] === '')) === 0);
if ($upstreamMode) {
    client_check('one_read_only_receiver_lookup_per_role', $statusCalls === 5);
    foreach ($originalCaptures as $id => $original) {
        $current = $wpdb->get_row($wpdb->prepare(
            "SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $id
        ), ARRAY_A);
        client_check('recovered_ids_match_receiver_' . count($checks), $current['lead_id'] === $acceptedReceipts[$id]['lead_id']
            && $current['event_id'] === $acceptedReceipts[$id]['event_id']);
        foreach (['state', 'delivery_pending', 'lead_id', 'event_id'] as $key) {
            unset($current[$key], $original[$key]);
        }
        client_check('original_capture_evidence_preserved_' . count($checks), $current === $original);
    }
    $before = $statusCalls;
    foreach (['invalid', BSRE\ReceiptRecovery\issue($requestIds[0], $_COOKIE[Intake\COOKIE], wp_salt('auth'), time() - 901),
        BSRE\ReceiptRecovery\issue(wp_generate_uuid4(), $_COOKIE[Intake\COOKIE], wp_salt('auth'), time()),
        BSRE\ReceiptRecovery\issue($requestIds[0], str_repeat('a', 64), wp_salt('auth'), time())] as $proof) {
        $request = new WP_REST_Request('POST', '/bsre/v1/receipt-recovery/status');
        $request->set_header('origin', 'https://blackswanrealestate.ae');
        $request->set_header('content-type', 'application/json');
        $request->set_header('x-bsre-csrf', Intake\csrf_token($_COOKIE[Intake\COOKIE], time() - 3, wp_salt('auth')));
        $request->set_body(wp_json_encode(['proof' => $proof]));
        client_check('unauthorized_or_absent_capture_unconfirmed_' . count($checks),
            rest_do_request($request)->get_data() === ['status' => 'UNCONFIRMED']);
    }
    client_check('invalid_proofs_and_missing_capture_do_not_query_receiver', $statusCalls === $before);
    $lastId = $requestIds[count($requestIds) - 1];
    Intake\consent_repository()->uncertain($lastId, $originalCaptures[$lastId]['fingerprint']);
    $request->set_body(wp_json_encode(['proof' => BSRE\ReceiptRecovery\issue($lastId,
        $_COOKIE[Intake\COOKIE], wp_salt('auth'), time())]));
    $rechecked = rest_do_request($request)->get_data();
    client_check('late_timeout_flag_reconciles_without_receipt_replacement', $rechecked === [
        'status' => 'ACCEPTED', 'reference' => $acceptedReceipts[$lastId]['lead_id']]
        && $statusCalls === $before + 1);
    $id = $requestIds[0];
    try {
        Intake\consent_repository()->link($id, $originalCaptures[$id]['fingerprint'],
            'BSRE-' . wp_generate_uuid4(), 'evt_' . wp_generate_uuid4());
        throw new RuntimeException('Conflicting receipt was accepted');
    } catch (RuntimeException $error) {
        client_check('established_receipt_cannot_be_replaced', $error->getMessage() === 'Consent receipt conflict.');
    }
}
fclose($receiverPipes[0]);
fclose($receiverPipes[1]);
client_check('receiver_completed_cleanly', proc_close($receiver) === 0);
echo wp_json_encode(['phase' => $upstreamMode ? 'wordpress_upstream_receipt_recovery' : 'wordpress_client_receiver_interop', 'status' => 'PASS', 'checks' => $checks,
    'synthetic_only' => true, 'dom_and_storage_are_doubles' => true, 'network_transport_is_pipe' => true,
    'google_services_are_doubles' => true, 'browser_acceptance' => false, 'production_acceptance' => false]) . "\n";
