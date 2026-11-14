<?php
/** Backend integration only; every DB row and identity is disposable/synthetic. */
use BSRE\Enquiries as E;
$_SERVER['HTTPS'] = 'on';
$_SERVER['SERVER_PORT'] = '443';
$_SERVER['REQUEST_METHOD'] = 'POST';
$_SERVER['REMOTE_ADDR'] = '198.51.100.7';
require '/opt/wordpress/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/plugin.php';
$checks = [];
function plugin_check(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Plugin native check failed: ' . $name);
    $checks[$name] = true;
}
$admin = get_user_by('login', 'synthetic_owner');
wp_set_current_user($admin->ID);
$activated = activate_plugin('bsre-enquiries/bsre-enquiries.php');
plugin_check('real_plugin_activation', !is_wp_error($activated) && is_plugin_active('bsre-enquiries/bsre-enquiries.php'));
plugin_check('rate_schema_v1', get_option('bsre_schema_version') === '1');
plugin_check('consent_schema_v2', get_option('bsre_consent_schema_version') === '2');
foreach (['state', 'history', 'captures'] as $table) {
    $status = $wpdb->get_row($wpdb->prepare('SHOW TABLE STATUS LIKE %s', $wpdb->esc_like($wpdb->prefix . 'bsre_consent_' . $table)), ARRAY_A);
    plugin_check('innodb_' . $table, is_array($status) && strtolower($status['Engine']) === 'innodb');
}
plugin_check('routing_unconfigured', !E\ready());
$measurement = E\measurement_settings();
plugin_check('measurement_controls_off', !$measurement['enabled'] && !$measurement['analytics_enabled'] && !$measurement['advertising_enabled'] && $measurement['ads_send_to'] === '');
// Lab-only origin override: no web server, DNS resolution or production request.
add_filter('home_url', fn() => 'https://blackswanrealestate.ae');
wp_set_current_user(0);
$_COOKIE = [];
function plugin_api(string $route, string $body = '{}', array $headers = []): WP_REST_Response {
    $_SERVER['REQUEST_METHOD'] = 'POST';
    $request = new WP_REST_Request('POST', '/bsre/v1/' . $route);
    foreach (array_merge(['origin' => 'https://blackswanrealestate.ae', 'sec-fetch-site' => 'same-origin', 'content-type' => 'application/json'], $headers) as $key => $value) $request->set_header($key, $value);
    $request->set_body($body);
    return rest_do_request($request);
}
plugin_check('lead_context_fail_closed', plugin_api('context')->get_status() === 503);
plugin_check('lead_receive_fail_closed', plugin_api('lead')->get_status() === 503);
plugin_check('anonymous_eligible_before_test_markers', E\measurement_eligible());
plugin_check('cross_origin_denied', plugin_api('consent/context', '{}', ['origin' => 'https://example.invalid'])->get_status() === 403);
plugin_check('cross_site_denied', plugin_api('consent/context', '{}', ['sec-fetch-site' => 'cross-site'])->get_status() === 403);
plugin_check('non_json_denied', plugin_api('consent/context', '{}', ['content-type' => 'text/plain'])->get_status() === 415);
plugin_check('oversize_denied', plugin_api('consent/context', '{"padding":"' . str_repeat('x', 1025) . '"}')->get_status() === 413);
plugin_check('invalid_context_denied', plugin_api('consent/context', '{"extra":true}')->get_status() === 400);
$context_response = plugin_api('consent/context');
$context = $context_response->get_data();
plugin_check('context_without_intake', $context_response->get_status() === 200 && $context['ok'] && !$context['known'] && !$context['preferences']['analytics'] && !$context['preferences']['ad_measurement']);
$session = $_COOKIE[E\CONSENT_SESSION_COOKIE];
$token = $context['csrf_token'];
$choice = json_encode(['analytics' => false, 'ad_measurement' => true, 'personalization' => false, 'notice_version' => E\CONSENT_NOTICE_VERSION]);
foreach (['missing' => '', 'tampered' => $token . 'x', 'expired' => E\consent_csrf($session, time() - 7201, wp_salt('auth')), 'lead_purpose' => E\csrf_token($session, time(), wp_salt('auth'))] as $name => $bad_token) {
    $bad = plugin_api('consent/update', $choice, ['x-bsre-consent-csrf' => $bad_token]);
    plugin_check('csrf_' . $name . '_denied', $bad->get_status() === 403 && $bad->get_data()['code'] === 'CONSENT_CSRF_FAILED');
}
$_COOKIE[E\CONSENT_SESSION_COOKIE] = str_repeat('f', 64);
plugin_check('csrf_wrong_session_denied', plugin_api('consent/update', $choice, ['x-bsre-consent-csrf' => $token])->get_status() === 403);
$_COOKIE[E\CONSENT_SESSION_COOKIE] = $session;
foreach (['duplicate' => str_replace('"analytics":false', '"analytics":false,"analytics":true', $choice), 'non_boolean' => str_replace('"analytics":false', '"analytics":"false"', $choice), 'personalization' => str_replace('"personalization":false', '"personalization":true', $choice)] as $name => $invalid) {
    plugin_check($name . '_choice_denied', plugin_api('consent/update', $invalid, ['x-bsre-consent-csrf' => $token])->get_status() === 400);
}
$grant_response = plugin_api('consent/update', $choice, ['x-bsre-consent-csrf' => $token]);
$grant = $grant_response->get_data();
plugin_check('advertising_only_grant_persisted', $grant_response->get_status() === 200 && $grant['known'] && !$grant['preferences']['analytics'] && $grant['preferences']['ad_measurement'] && !$grant['preferences']['personalization']);
$store = E\consent_repository();
$current = E\consent_current($store);
$subject = $current['row']['subject_key'];
$original_revision = (int) $current['row']['revision'];
plugin_check('preference_validity_180_days', abs($current['row']['expires_at'] - time() - 15552000) <= 2);
plugin_check('durable_history_written', (int) $wpdb->get_var($wpdb->prepare("SELECT COUNT(*) FROM {$wpdb->prefix}bsre_consent_history WHERE subject_key=%s", $subject)) === 1);

// An eligible synthetic capture is exercised ONLY in this network-none lab.
$request_id = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
$raw = json_encode(['request_id' => $request_id, 'name' => 'Synthetic lab fixture', 'attribution' => ['first' => ['parameters' => ['gclid' => 'SYNTHETIC_NOT_FOR_UPLOAD'], 'timestamp' => time() * 1000]]]);
$handle = E\consent_stage_submission($raw, false, null, $grant['decision_version']);
plugin_check('original_capture_staged', $handle['recorded'] && !$handle['conflict'] && (int) $handle['row']['known'] === 1 && $handle['row']['gclid_first'] === 'SYNTHETIC_NOT_FOR_UPLOAD' && (int) $handle['row']['analytics'] === 0);
$receipt = ['lead_id' => 'BSRE-11111111-1111-4111-8111-111111111111', 'event_id' => 'evt_22222222-2222-4222-8222-222222222222'];
$accepted = E\consent_link_accepted($handle, $receipt, $raw);
plugin_check('same_subject_receipt_linked', $accepted['known'] && $accepted['preferences']['ad_measurement']);
$export_before = E\consent_export_document([$request_id], $store);
plugin_check('local_permission_evidence_eligible', $export_before['rows'][0]['export_eligible'] === true);
$denial = str_replace('"ad_measurement":true', '"ad_measurement":false', $choice);
plugin_check('withdrawal_saved', plugin_api('consent/update', $denial, ['x-bsre-consent-csrf' => $token])->get_status() === 200);
plugin_check('regrant_saved', plugin_api('consent/update', $choice, ['x-bsre-consent-csrf' => $token])->get_status() === 200);
plugin_check('withdrawal_history_not_erased', $store->revoked($subject, $original_revision, 'ad_measurement'));
$export_after = E\consent_export_document([$request_id], $store);
plugin_check('withdrawn_capture_export_blocked', !$export_after['rows'][0]['export_eligible'] && $export_after['rows'][0]['gclid_first'] === '' && in_array('AD_PERMISSION_WITHDRAWN_OR_HISTORY_UNKNOWN', $export_after['rows'][0]['blocked_reasons'], true));
$retry = E\consent_stage_submission($raw, true);
plugin_check('retry_keeps_original_evidence', $retry['recorded'] && $retry['row']['original_revision'] === $handle['row']['original_revision'] && $retry['row']['decision_version'] === $handle['row']['decision_version']);
plugin_check('changed_body_conflict', E\consent_stage_submission(str_replace('Synthetic lab fixture', 'Changed synthetic fixture', $raw), true)['conflict']);
$saved_cookies = $_COOKIE;
$_COOKIE = [];
plugin_check('different_browser_cannot_borrow_grant', !E\consent_link_accepted($handle, $receipt, $raw)['known']);
$_COOKIE = $saved_cookies;
$_COOKIE[E\CONSENT_PENDING_COOKIE] = 'pending';
$pending = E\consent_current($store);
$again = E\consent_current($store);
plugin_check('pending_withdrawal_fail_closed', !$pending['snapshot']['known'] && !$pending['snapshot']['preferences']['ad_measurement']);
plugin_check('pending_read_idempotent', (int) $pending['row']['revision'] === (int) $again['row']['revision'] && (int) $again['row']['uncertain'] === 1);
unset($_COOKIE[E\CONSENT_PENDING_COOKIE]);
$_COOKIE[E\MEASUREMENT_QA_COOKIE] = E\measurement_qa_token(wp_salt('auth'), time());
plugin_check('qa_after_logout_excluded', !E\measurement_eligible());
$_COOKIE[E\MEASUREMENT_QA_COOKIE] = 'malformed';
plugin_check('malformed_qa_excluded', !E\measurement_eligible());
unset($_COOKIE[E\MEASUREMENT_QA_COOKIE]);
wp_set_current_user($admin->ID);
plugin_check('admin_excluded', !E\measurement_eligible());
wp_set_current_user(0);
$_COOKIE[LOGGED_IN_COOKIE] = 'uncertain';
plugin_check('uncertain_auth_cookie_excluded', !E\measurement_eligible());
unset($_COOKIE[LOGGED_IN_COOKIE]);
plugin_check('marked_test_excluded', !E\measurement_eligible('{"name":"TEST synthetic"}'));

// Planned fault injection ONLY into synthetic tables; finally restores schema.
$history = $wpdb->prefix . 'bsre_consent_history';
$held = $history . '_held';
$fault_subject = str_repeat('b', 64);
$prior_errors = $wpdb->suppress_errors(true);
plugin_check('fault_table_held', $wpdb->query("RENAME TABLE {$history} TO {$held}") !== false);
try {
    $failed = false;
    try { $store->choose($fault_subject, ['analytics' => true, 'ad_measurement' => true], E\CONSENT_NOTICE_VERSION, time()); }
    catch (RuntimeException $e) { $failed = true; }
    plugin_check('failed_choice_rolls_back', $failed && $store->current($fault_subject) === null);
} finally {
    plugin_check('fault_table_restored', $wpdb->query("RENAME TABLE {$held} TO {$history}") !== false && $wpdb->get_var($wpdb->prepare('SHOW TABLES LIKE %s', $wpdb->esc_like($history))) === $history);
    $wpdb->suppress_errors($prior_errors);
}
update_option('bsre_consent_schema_version', 'unavailable', false);
$_COOKIE = [];
$unavailable_response = plugin_api('consent/context');
$unavailable = $unavailable_response->get_data();
plugin_check('missing_storage_context_denied', $unavailable_response->get_status() === 200 && $unavailable['ok'] === true && !$unavailable['known'] && !$unavailable['preferences']['analytics'] && !$unavailable['preferences']['ad_measurement']);
$failed_update = plugin_api('consent/update', $choice, ['x-bsre-consent-csrf' => $unavailable['csrf_token']]);
plugin_check('missing_storage_update_fail_closed', $failed_update->get_status() === 503 && !$failed_update->get_data()['known']);
update_option('bsre_consent_schema_version', '2', false);
echo json_encode(['phase' => 'primary_plugin_backend', 'status' => 'PASS', 'version' => E\PLUGIN_VERSION, 'checks' => $checks, 'synthetic_only' => true, 'browser_acceptance' => false, 'retention_deletion_implemented' => false, 'production_acceptance' => false], JSON_UNESCAPED_SLASHES) . "\n";
