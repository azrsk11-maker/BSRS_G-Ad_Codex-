<?php
/** Isolated native REST/Node composition; loaded only by the literal admission lab mode. */
namespace BSRE\ComposedDeliveryLab;
use BSRE\Enquiries as E;
use BSRE\RetentionAdmission as A;

function check(string $name, bool $ok): void { \admission_check('composed_' . $name, $ok); }
function fields(array $message, array $expected): void {
    $keys = array_keys($message); sort($keys); sort($expected);
    check('ipc_exact_fields', $keys === $expected);
}
function post(string $route, string $body = '{}', array $headers = []): \WP_REST_Response {
    $old = $_SERVER['REQUEST_METHOD']; $_SERVER['REQUEST_METHOD'] = 'POST';
    try { return \admission_api($route, $body, $headers); }
    finally { $_SERVER['REQUEST_METHOD'] = $old; }
}
function choice(array &$current, bool $allowed): array {
    $result = post('consent/update', wp_json_encode(['analytics' => $allowed, 'ad_measurement' => $allowed,
        'personalization' => false, 'notice_version' => E\CONSENT_NOTICE_VERSION]), ['x-bsre-consent-csrf' => $current['choice_csrf']]);
    $snapshot = $result->get_data();
    check('actual_consent_update', $result->get_status() === 200 && $snapshot['known'] === true
        && $snapshot['preferences']['analytics'] === $allowed && $snapshot['preferences']['ad_measurement'] === $allowed);
    return $current['snapshot'] = $snapshot;
}
function runtime_get(string $url, string $variant = 'normal'): \WP_REST_Response {
    $parts = parse_url($url);
    check('runtime_exact_owned_endpoint', ($parts['scheme'] ?? '') === 'https' && ($parts['host'] ?? '') === 'blackswanrealestate.ae'
        && ($parts['path'] ?? '') === '/wp-json/bsre/v1/measurement/runtime'
        && !array_intersect(array_keys($parts), ['user', 'pass', 'port', 'fragment']));
    $old = $_SERVER; $user = get_current_user_id(); $cookies = $_COOKIE;
    try {
        $_SERVER['REQUEST_METHOD'] = 'GET';
        if ($variant === 'http') { $_SERVER['HTTPS'] = 'off'; $_SERVER['SERVER_PORT'] = '80'; }
        if ($variant === 'qa') $_COOKIE[E\MEASUREMENT_QA_COOKIE] = E\measurement_qa_token(wp_salt('auth'), time());
        if ($variant === 'logged_in') wp_set_current_user(get_user_by('login', 'synthetic_owner')->ID);
        $request = new \WP_REST_Request('GET', '/bsre/v1/measurement/runtime');
        parse_str($parts['query'] ?? '', $query); $request->set_query_params($query);
        $request->set_header('referer', $variant === 'foreign_referrer' ? 'https://example.invalid/' : 'https://blackswanrealestate.ae/');
        $request->set_header('sec-fetch-site', 'same-origin');
        $request->set_header('sec-fetch-dest', $variant === 'wrong_destination' ? 'document' : 'iframe');
        return rest_do_request($request);
    } finally { $_SERVER = $old; $_COOKIE = $cookies; wp_set_current_user($user); }
}
function pack(\WP_REST_Response $response): array {
    return ['status' => $response->get_status(), 'body' => $response->get_data(), 'headers' => $response->get_headers()];
}
function guarded_cases(array &$current, array $settings, &$mapped): void {
    global $wpdb, $forwards;
    $url = 'https://blackswanrealestate.ae/wp-json/bsre/v1/measurement/runtime?purpose=advertising';
    $mapped = false;
    try { check('unmapped_asset_origin_denied', runtime_get($url)->get_status() === 403); }
    finally { $mapped = true; }
    $ok = runtime_get($url); check('mapped_actual_runtime_html', $ok->get_status() === 200 && is_string($ok->get_data()));
    foreach (['http', 'qa', 'logged_in', 'foreign_referrer', 'wrong_destination'] as $variant)
        check('runtime_denies_' . $variant, runtime_get($url, $variant)->get_status() === 403);
    check('unknown_query_denied', runtime_get($url . '&unexpected=1')->get_status() === 403);
    foreach (['enabled', 'advertising_enabled'] as $flag) {
        $off = $settings; $off[$flag] = false; update_option(E\MEASUREMENT_SETTINGS_OPTION, $off, false);
        try { check('runtime_denies_' . $flag . '_off', runtime_get($url)->get_status() === 403); }
        finally { update_option(E\MEASUREMENT_SETTINGS_OPTION, $settings, false); }
    }
    preg_match('~<script id="bsre-runtime-config" type="application/json">([^<]+)</script>~', $ok->get_data(), $match);
    check('actual_runtime_has_config', isset($match[1]));
    $config = json_decode($match[1], true, 16, JSON_THROW_ON_ERROR);
    $lease = ['purpose' => 'advertising', 'lease_token' => $config['lease_token'], 'config_version' => $config['config_version']];
    check('real_lease_positive', post('measurement/status', wp_json_encode($lease))->get_status() === 200);
    $expired = $lease;
    $expired['lease_token'] = E\measurement_lease_token('advertising', $_COOKIE[E\CONSENT_SESSION_COOKIE], $config['config_version'], time() - 121, E\measurement_runtime_revision(null));
    check('authentic_expired_lease_denied', post('measurement/status', wp_json_encode($expired))->get_status() === 403);
    $rotated = $settings; $rotated['config_version'] = 'gm1-' . str_repeat('b', 32);
    update_option(E\MEASUREMENT_SETTINGS_OPTION, $rotated, false);
    try { check('config_rotation_denies_old_lease', post('measurement/status', wp_json_encode($lease))->get_status() === 403); }
    finally { update_option(E\MEASUREMENT_SETTINGS_OPTION, $settings, false); }
    choice($current, false);
    check('withdrawal_denies_runtime', runtime_get($url)->get_status() === 403);
    check('withdrawal_denies_lease', post('measurement/status', wp_json_encode($lease))->get_status() === 403);
    choice($current, true);
    check('regrant_does_not_revive_old_lease', post('measurement/status', wp_json_encode($lease))->get_status() === 403);

    $issued = post('receipt-recovery/proof', '{}', ['x-bsre-csrf' => $current['csrf']]);
    $prepared = $issued->get_data();
    check('negative_admission_gets_actual_proof', $issued->get_status() === 200 && is_array($prepared)
        && is_string($prepared['request_id'] ?? null) && is_array($prepared['admission'] ?? null)
        && ($prepared['admission']['request_id'] ?? null) === $prepared['request_id']
        && A\valid_proof($prepared['admission'], $prepared['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, A\configuration(), time(), true));
    $payload = json_decode($current['wire'], true, 16, JSON_THROW_ON_ERROR); $payload['request_id'] = $prepared['request_id'];
    $wire = wp_json_encode($payload); $before = count($forwards);
    $headers = ['x-bsre-csrf' => $current['csrf'], 'x-bsre-consent-decision' => $current['snapshot']['decision_version']];
    $invalid = $prepared['admission']; $invalid['signature'] = str_repeat('0', 64);
    $expiryNow = time(); $expiryGate = A\configuration();
    $expiredProof = A\sign_new_request($prepared['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, $expiryGate, $expiryNow - 1000);
    check('expiry_fixture_only_time_is_stale', $expiredProof['issued_at'] >= $expiryGate['activated_at']
        && $expiredProof['issued_at'] <= $expiryNow && $expiredProof['expires_at'] <= $expiryNow
        && $expiredProof['generation'] === $expiryGate['generation'] && $expiredProof['audience'] === $expiryGate['audience']
        && $expiredProof['request_id'] === $prepared['request_id']
        && $expiredProof['session_hash'] === hash('sha256', $_COOKIE[E\COOKIE]));
    check('authentic_expired_proof_wrapper_still_accepts', A\valid_proof($expiredProof, $prepared['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, $expiryGate, $expiryNow, false));
    check('expired_proof_was_fresh_at_issue', A\valid_proof($expiredProof, $prepared['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, $expiryGate, $expiredProof['issued_at'], true));
    check('expired_proof_is_not_fresh_now', !A\valid_proof($expiredProof, $prepared['request_id'], $_COOKIE[E\COOKIE], BSRE_LEAD_HMAC_SECRET, $expiryGate, $expiryNow, true));
    check('negative_uuid_has_no_existing_capture', (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $prepared['request_id'])) === 0);
    // Authentic expired proofs may recover existing accepted requests; a fresh UUID fails at the store.
    $expected = ['missing' => [503, 'ADMISSION_UNCONFIRMED'], 'invalid' => [400, 'ADMISSION_INVALID'],
        'expired' => [503, 'ADMISSION_UNCONFIRMED']];
    foreach (['missing' => null, 'invalid' => $invalid, 'expired' => $expiredProof] as $name => $proof) {
        $sent = $headers; if ($proof !== null) $sent['x-bsre-admission'] = wp_json_encode($proof);
        $response = post('lead', $wire, $sent);
        [$expectedStatus, $expectedCode] = $expected[$name];
        $data = $response->get_data();
        check('actual_admission_' . $name . '_denied_before_forward', $response->get_status() === $expectedStatus
            && is_array($data) && ($data['code'] ?? null) === $expectedCode && count($forwards) === $before);
    }
    check('denied_admission_creates_no_capture', (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $prepared['request_id'])) === 0);
}

function runComposedDeliveryInterop(): void {
    global $wpdb, $bridge, $pipes, $checks, $forwards;
    $started = microtime(true); $phase = 'setup'; $client = null; $clientPipes = []; $complete = false;
    $oldCookies = $_COOKIE; $oldServer = $_SERVER; $oldUser = get_current_user_id();
    $oldSettings = get_option(E\MEASUREMENT_SETTINGS_OPTION, null); $mapped = false;
    $assetFilter = static function ($url, $path, $plugin) use (&$mapped) {
        if ($mapped && $path === '' && $plugin === WP_PLUGIN_DIR . '/bsre-enquiries/bsre-enquiries.php')
            return 'https://blackswanrealestate.ae/wp-content/plugins/bsre-enquiries';
        return $url;
    };
    try {
        define('BSRE_RECEIPT_STATUS_ENABLED', true);
        $GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
        $settings = E\measurement_settings_choice(['enabled' => '1', 'analytics_enabled' => '1', 'advertising_enabled' => '1',
            'ads_send_to' => 'AW-18394393537/SYNTHETIC_COMPOSED_NOT_REAL']);
        update_option(E\MEASUREMENT_SETTINGS_OPTION, $settings, false);
        check('actual_settings_accept_public_prefix_fictional_label', E\measurement_settings()['ads_send_to'] === $settings['ads_send_to']);
        $otherAsset = plugins_url('assets/unrelated.js', WP_PLUGIN_DIR . '/other/other.php');
        add_filter('plugins_url', $assetFilter, 10, 3);
        check('narrow_filter_leaves_other_plugin_unchanged', plugins_url('assets/unrelated.js', WP_PLUGIN_DIR . '/other/other.php') === $otherAsset);
        $client = proc_open(['node', '/opt/lab/composed-delivery-interop.mjs'], [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $clientPipes);
        check('node_started', is_resource($client)); stream_set_timeout($clientPipes[1], 15);
        $current = []; $sessionDone = false; $inspected = false; $guardsDone = false;
        while (($line = fgets($clientPipes[1], 100000)) !== false) {
            check('ipc_bounded_complete_line', str_ends_with($line, "\n"));
            $message = json_decode($line, true, 32, JSON_THROW_ON_ERROR); $phase = $message['op'] ?? 'invalid';
            if ($phase === 'session') {
                fields($message, ['op']); check('one_session_only', !$sessionDone); $sessionDone = true;
                $_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))]; wp_set_current_user(0);
                $context = post('consent/context')->get_data(); check('actual_consent_context', isset($context['csrf_token']));
                $current['choice_csrf'] = $context['csrf_token']; choice($current, true);
                $current['csrf'] = E\csrf_token($_COOKIE[E\COOKIE], time() - 3, wp_salt('auth'));
                $unmapped = runtime_get('https://blackswanrealestate.ae/wp-json/bsre/v1/measurement/runtime?purpose=advertising');
                check('initial_unmapped_origin_denied', $unmapped->get_status() === 403); $mapped = true;
                $readback = A\readback(); check('actual_admission_routes_and_store', $readback['routes_installed'] && $readback['store_installed']);
                $reply = ['snapshot' => $current['snapshot'], 'csrf' => $current['csrf'], 'publicConfig' => E\measurement_public_configuration()];
            } elseif ($phase === 'request') {
                fields($message, ['op', 'url', 'method', 'body', 'headers']);
                check('request_session_and_bounds', $sessionDone && $message['method'] === 'POST' && is_string($message['body']) && strlen($message['body']) <= 18000 && is_array($message['headers']));
                foreach ($message['headers'] as $key => $value) check('request_header_allowlist', is_string($key) && is_string($value)
                    && strlen($value) <= 4096 && in_array(strtolower($key), ['content-type', 'x-bsre-csrf', 'x-bsre-consent-decision', 'x-bsre-consent-retry', 'x-bsre-admission'], true));
                $allowed = ['lead', 'receipt-recovery/proof', 'receipt-recovery/status'];
                $route = substr($message['url'], strlen('https://blackswanrealestate.ae/wp-json/bsre/v1/'));
                check('request_exact_owned_route', in_array($route, $allowed, true) && $message['url'] === 'https://blackswanrealestate.ae/wp-json/bsre/v1/' . $route);
                if ($route === 'lead') {
                    $payload = json_decode($message['body'], true, 16, JSON_THROW_ON_ERROR);
                    check('only_synthetic_tenant_body', ($payload['name'] ?? '') === 'SYNTHETIC composition fixture' && ($payload['email'] ?? '') === 'fixture@example.invalid'
                        && ($payload['role'] ?? '') === 'tenant' && ($payload['landing_page'] ?? '') === 'https://blackswanrealestate.ae/enquire/rent/' && !isset($payload['wire_body']));
                    if (isset($current['wire'])) check('retry_body_exact', $current['wire'] === $message['body']);
                    $current['wire'] = $message['body']; $current['id'] = $payload['request_id'];
                }
                $actual = post($route, $message['body'], $message['headers']); $reply = pack($actual);
                if ($route === 'lead' && ($reply['body']['accepted'] ?? false)) $current['receipt'] = $reply['body'];
            } elseif ($phase === 'runtime_get') {
                fields($message, ['op', 'url']); check('runtime_session_required', $sessionDone);
                $reply = pack(runtime_get($message['url']));
            } elseif ($phase === 'lease_post') {
                fields($message, ['op', 'url', 'body', 'method']);
                check('lease_exact_route', $sessionDone && $message['url'] === 'https://blackswanrealestate.ae/wp-json/bsre/v1/measurement/status'
                    && $message['method'] === 'POST' && is_string($message['body']) && strlen($message['body']) <= 512);
                $reply = pack(post('measurement/status', $message['body']));
            } elseif ($phase === 'consent') {
                fields($message, ['op', 'allowed']); check('boolean_consent_choice', $sessionDone && is_bool($message['allowed']));
                $reply = ['snapshot' => choice($current, $message['allowed'])];
            } elseif ($phase === 'inspect') {
                fields($message, ['op', 'request_id']); check('inspect_one_current_id', $message['request_id'] === $current['id']);
                $row = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $current['id']), ARRAY_A);
                check('durable_capture_matches_exact_wire', is_array($row) && $row['state'] === 'ACCEPTED' && $row['fingerprint'] === hash('sha256', $current['wire']));
                check('actual_capture_and_receiver_receipt_match', $row['lead_id'] === $current['receipt']['lead_id'] && $row['event_id'] === $current['receipt']['event_id']);
                check('actual_signed_forward_exists', count($forwards) >= 1);
                foreach ($forwards as $raw) {
                    $env = json_decode($raw, true, 32, JSON_THROW_ON_ERROR);
                    check('signed_wire_unchanged_admission_outside', $env['version'] === 1 && $env['body'] === $current['wire'] && isset($env['admission']['signature']));
                }
                $snapshot = \admission_receiver(['op' => 'snapshot']);
                check('receiver_one_row_no_mail_intake26', $snapshot['rows'] === 1 && $snapshot['mail'] === 0 && $snapshot['columns'] === 26);
                $inspected = true; $reply = ['event_id' => $row['event_id'], 'lead_id' => $row['lead_id']];
            } elseif ($phase === 'guards') {
                fields($message, ['op']); check('guards_after_composition', $inspected && !$guardsDone);
                guarded_cases($current, $settings, $mapped); $guardsDone = true; $reply = ['ok' => true];
            } elseif ($phase === 'complete') {
                fields($message, ['op', 'checks']);
                check('native_completion_has_independent_facts', $inspected && $guardsDone && is_array($message['checks']) && count($message['checks']) === 8
                    && count(array_filter($message['checks'], static fn($value) => $value !== true)) === 0);
                check('node_checks_exact', array_keys($message['checks']) === ['actual_rest_configs', 'one_native_command', 'exact_transaction', 'exact_retry', 'analytics_once', 'withdraw_no_replay', 'no_vendor_fetch', 'raw_command_privacy']);
                check('no_extra_native_captures', (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_captures") === 1);
                $snapshot = \admission_receiver(['op' => 'snapshot']); check('final_receiver_still_one_no_mail', $snapshot['rows'] === 1 && $snapshot['mail'] === 0);
                $complete = true; $reply = ['ok' => true];
            } else throw new \RuntimeException('Unknown composed lab operation');
            $encoded = wp_json_encode($reply) . "\n";
            check('ipc_reply_written', fwrite($clientPipes[0], $encoded) === strlen($encoded) && fflush($clientPipes[0]));
            if ($complete) break;
        }
        fclose($clientPipes[0]); fclose($clientPipes[1]); $clientPipes = [];
        check('node_clean_exit', proc_close($client) === 0 && $complete); $client = null;
    } catch (\Throwable $error) {
        $code = preg_match('/^Admission native check failed: (composed_[a-z0-9_]+)$/D', $error->getMessage(), $failure)
            ? $failure[1] : 'COMPOSED_NATIVE_EXCEPTION';
        fwrite(STDERR, wp_json_encode(['phase' => 'composed_delivery_native', 'status' => 'DIAGNOSTIC_FAILURE',
            'operation' => $phase, 'elapsed_seconds' => microtime(true) - $started, 'error_code' => $code]) . "\n");
        throw new \RuntimeException('COMPOSED_NATIVE_FAILED');
    } finally {
        foreach ($clientPipes as $pipe) if (is_resource($pipe)) fclose($pipe);
        if (is_resource($client)) { proc_terminate($client); proc_close($client); }
        remove_filter('plugins_url', $assetFilter, 10);
        if ($oldSettings === null) delete_option(E\MEASUREMENT_SETTINGS_OPTION); else update_option(E\MEASUREMENT_SETTINGS_OPTION, $oldSettings, false);
        $_COOKIE = $oldCookies; $_SERVER = $oldServer; wp_set_current_user($oldUser);
        foreach ($pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
        if (is_resource($bridge)) check('receiver_clean_exit', proc_close($bridge) === 0);
    }
    echo wp_json_encode(['phase' => 'composed_delivery_native', 'status' => 'PASS', 'checks' => $checks,
        'elapsed_seconds' => microtime(true) - $started, 'synthetic_only' => true, 'browser_provider_accepted' => false]) . "\n";
}
