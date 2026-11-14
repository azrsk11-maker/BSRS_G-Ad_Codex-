<?php
/** Real WP /lead dispatch, synthetic pages/data, preempted mock receiver only. */
use BSRE\Enquiries as E;
$_SERVER['HTTPS'] = 'on'; $_SERVER['SERVER_PORT'] = '443';
$_SERVER['REQUEST_METHOD'] = 'POST';
require '/opt/wordpress/wp-load.php';
add_filter('home_url', fn($url, $path) => 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/')), 10, 2);
$checks = []; $ledger = []; $calls = 0; $lose_ack = false;
function receive_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Receive check failed: ' . $name);
    $checks[$name] = true;
}
wp_set_current_user(get_user_by('login', 'synthetic_owner')->ID);
$GLOBALS['wp_rewrite']->set_permalink_structure('/%postname%/');
$drafts = E\ensure_drafts(false);
foreach ($drafts['pages'] as $id) wp_update_post(['ID' => $id, 'post_status' => 'publish']);
$privacy = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish', 'post_name' => 'synthetic-privacy', 'post_title' => 'SYNTHETIC LAB NOTICE']);
define('BSRE_PRIVACY_NOTICE_PAGE_ID', $privacy);
define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
define('BSRE_ROUTING_ENABLED', true);
receive_check('five_synthetic_native_paths', count(E\live_paths()) === 5);
receive_check('synthetic_routing_ready', E\ready());
wp_set_current_user(0);
add_filter('pre_http_request', function ($pre, $args, $url) use (&$ledger, &$calls, &$lose_ack) {
    receive_check('mock_destination_only', $url === BSRE_LEAD_RECEIVER_URL);
    $calls++;
    $wire = json_decode($args['body'], true, 512, JSON_THROW_ON_ERROR);
    receive_check('wire_v1_signature_preserved', $wire['version'] === 1 && hash_equals(hash_hmac('sha256', "v1\n{$wire['timestamp']}\n{$wire['body']}", BSRE_LEAD_HMAC_SECRET), $wire['signature']));
    $payload = json_decode($wire['body'], true, 512, JSON_THROW_ON_ERROR);
    $id = $payload['request_id']; $fingerprint = hash('sha256', $wire['body']);
    if (isset($ledger[$id]) && $ledger[$id]['fingerprint'] !== $fingerprint) throw new RuntimeException('Mock body conflict');
    if (!isset($ledger[$id])) $ledger[$id] = ['fingerprint' => $fingerprint, 'receipt' => ['accepted' => true, 'lead_id' => 'BSRE-' . wp_generate_uuid4(), 'event_id' => 'evt_' . wp_generate_uuid4()]];
    if ($lose_ack) { $lose_ack = false; return new WP_Error('SYNTHETIC_LOST_ACK'); }
    return ['headers' => [], 'body' => wp_json_encode($ledger[$id]['receipt']), 'response' => ['code' => 200]];
}, PHP_INT_MAX, 3);
function submit_synthetic(string $raw, ?string $csrf = null): WP_REST_Response {
    $r = new WP_REST_Request('POST', '/bsre/v1/lead');
    foreach (['origin' => 'https://blackswanrealestate.ae', 'content-type' => 'application/json', 'sec-fetch-site' => 'same-origin', 'x-bsre-csrf' => $csrf ?? E\csrf_token($_COOKIE[E\COOKIE], time() - 3, wp_salt('auth'))] as $k => $v) $r->set_header($k, $v);
    $r->set_body($raw);
    return rest_do_request($r);
}
$timelines = ['off-plan' => 'Within 1 month', 'resale' => 'Within 1 month', 'rent' => 'Immediate / move now', 'sell' => 'As soon as practical', 'let' => 'Vacant / available to discuss now'];
$index = 10;
foreach (E\SERVICES as $slug => $service) {
    $_SERVER['REMOTE_ADDR'] = '198.51.100.' . $index++;
    $_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))];
    $p = ['request_id' => wp_generate_uuid4(), 'role' => $service['role'], 'name' => 'TEST synthetic ' . $slug, 'phone' => '+971500000000', 'email' => 'fixture@example.invalid', 'country' => 'UAE', 'area' => 'Synthetic fixture', 'budget' => 'To discuss', 'timeline' => $timelines[$slug], 'funding' => 'To discuss', 'property_type' => 'Apartment', 'property_details' => 'SYNTHETIC NOT INVENTORY', 'authority' => in_array($slug, ['sell', 'let']) ? 'owner' : '', 'contact_consent' => true, 'marketing_consent' => false, 'campaign' => 'SYNTHETIC_LAB_ONLY', 'landing_page' => 'https://blackswanrealestate.ae/enquire/' . $slug . '/', 'website' => '', 'started_at' => (time() - 5) * 1000];
    $raw = wp_json_encode($p); $before = $calls;
    receive_check($slug . '_csrf_denied_before_forward', submit_synthetic($raw, 'invalid')->get_status() === 403 && $calls === $before);
    $accepted = submit_synthetic($raw);
    receive_check($slug . '_accepted', $accepted->get_status() === 200 && $accepted->get_data()['accepted'] === true);
    receive_check($slug . '_test_measurement_excluded', $accepted->get_data()['measurement_eligible'] === false);
    $retry = submit_synthetic($raw);
    receive_check($slug . '_retry_same_receipt', $retry->get_data()['lead_id'] === $accepted->get_data()['lead_id'] && $retry->get_data()['event_id'] === $accepted->get_data()['event_id']);
    $changed = $p; $changed['area'] = 'Changed synthetic fixture'; $before = $calls;
    receive_check($slug . '_changed_body_blocked_before_forward', submit_synthetic(wp_json_encode($changed))->get_status() === 409 && $calls === $before);
    $changed = $p; $changed['request_id'] = wp_generate_uuid4(); $changed['contact_consent'] = false;
    receive_check($slug . '_contact_permission_required', submit_synthetic(wp_json_encode($changed))->get_status() === 400 && $calls === $before);
    $changed['contact_consent'] = true; $changed['landing_page'] .= '?unapproved=1';
    receive_check($slug . '_unapproved_path_query_denied', submit_synthetic(wp_json_encode($changed))->get_status() === 400 && $calls === $before);
}
$_SERVER['REMOTE_ADDR'] = '198.51.100.99';
$_COOKIE = [E\COOKIE => bin2hex(random_bytes(32))];
$p['request_id'] = wp_generate_uuid4(); $raw = wp_json_encode($p);
$lose_ack = true; $before = count($ledger);
$lost = submit_synthetic($raw);
receive_check('lost_ack_requires_same_id_retry', $lost->get_status() === 503 && $lost->get_data()['retryable'] === true);
$recovered = submit_synthetic($raw);
receive_check('lost_ack_reconciles_mock_receipt', $recovered->get_status() === 200 && count($ledger) === $before + 1 && $recovered->get_data()['lead_id'] === $ledger[$p['request_id']]['receipt']['lead_id']);
echo wp_json_encode(['phase' => 'five_role_receive', 'status' => 'PASS', 'checks' => $checks, 'synthetic_only' => true, 'receiver_idempotency_is_mock_assumption' => true, 'live_delivery_accepted' => false, 'production_acceptance' => false]) . "\n";
