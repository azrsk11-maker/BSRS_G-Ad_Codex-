<?php
/** Synthetic HTTP preemption, never an actual Google endpoint or delivery test. */
require '/opt/wordpress/wp-load.php';
use BSRE\Enquiries as E;
$checks = [];
function transport_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Transport check failed: ' . $name);
    $checks[$name] = true;
}
$url = 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec';
$follow = 'https://script.googleusercontent.com/macros/echo?synthetic=1';
$mode = 'redirect'; $calls = [];
add_filter('pre_http_request', function ($preempt, $args, $target) use (&$mode, &$calls, $url, $follow) {
    $calls[] = ['url' => $target, 'args' => $args];
    if ($target !== $url && $target !== $follow) throw new RuntimeException('Unexpected mock destination');
    if ($mode === 'error') return new WP_Error('SYNTHETIC_TIMEOUT');
    if ($mode === '503') return ['headers' => [], 'body' => '', 'response' => ['code' => 503]];
    if ($target === $url) return ['headers' => ['location' => $mode === 'unsafe' ? 'https://example.invalid/macros/echo' : $follow], 'body' => '', 'response' => ['code' => 302]];
    return ['headers' => [], 'body' => '{"synthetic":true}', 'response' => ['code' => 200]];
}, PHP_INT_MAX, 3);
$raw = '{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","name":"TEST synthetic"}';
$secret = str_repeat('synthetic-key-', 4);
$envelope = E\envelope($raw, $secret, 1794117600000);
transport_check('wire_v1_exact_body', $envelope['version'] === 1 && $envelope['body'] === $raw);
transport_check('wire_signature', hash_equals(hash_hmac('sha256', "v1\n1794117600000\n" . $raw, $secret), $envelope['signature']));
$body = wp_json_encode($envelope);
$response = E\send_envelope($url, $body);
transport_check('mock_redirect_accepted', wp_remote_retrieve_response_code($response) === 200 && count($calls) === 2);
transport_check('post_preserves_envelope', $calls[0]['args']['method'] === 'POST' && $calls[0]['args']['body'] === $body);
transport_check('redirect_get_has_no_lead_body', $calls[1]['args']['method'] === 'GET' && empty($calls[1]['args']['body']));
transport_check('automatic_redirects_disabled', $calls[0]['args']['redirection'] === 0 && $calls[1]['args']['redirection'] === 0);
transport_check('tls_verification_enabled', $calls[0]['args']['sslverify'] === true && $calls[1]['args']['sslverify'] === true);
transport_check('bounded_response', $calls[0]['args']['limit_response_size'] === 8192 && $calls[1]['args']['limit_response_size'] === 8192);
$calls = []; $mode = 'unsafe';
transport_check('unsafe_redirect_rejected', is_wp_error(E\send_envelope($url, $body)) && count($calls) === 1);
$calls = []; $mode = 'error';
transport_check('timeout_preserved', is_wp_error(E\send_envelope($url, $body)) && count($calls) === 1);
$calls = []; $mode = '503';
transport_check('upstream_failure_preserved', wp_remote_retrieve_response_code(E\send_envelope($url, $body)) === 503 && count($calls) === 1);
echo json_encode(['phase' => 'signed_relay_transport', 'status' => 'PASS', 'checks' => $checks, 'http_preempted' => true, 'live_delivery_accepted' => false, 'five_role_receive_acceptance' => false]) . "\n";
