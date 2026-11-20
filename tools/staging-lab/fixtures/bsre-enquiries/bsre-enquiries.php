<?php
/**
 * Plugin Name: Black Swan Real Estate Enquiry Drafts
 * Description: Five private landing drafts and a fail-closed, signed lead receiver relay. No CRM or Ads settings.
 * Version: 0.2.12
 * Requires at least: 6.4
 * Requires PHP: 8.1
 */
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;
const PLUGIN_VERSION = '0.2.12';
require_once __DIR__ . '/includes/protocol.php';
require_once __DIR__ . '/includes/measurement.php';
require_once __DIR__ . '/includes/consent.php';
require_once __DIR__ . '/includes/consent-export.php';
require_once __DIR__ . '/includes/measurement-settings.php';
require_once __DIR__ . '/includes/measurement-runtime.php';
require_once __DIR__ . '/includes/enquiry-seo.php';

const COOKIE = '__Host-bsre_session';

function table_name(): string { global $wpdb; return $wpdb->prefix . 'bsre_rate_limits'; }
function install(): void {
    global $wpdb;
    require_once ABSPATH . 'wp-admin/includes/upgrade.php';
    $table = table_name();
    dbDelta("CREATE TABLE {$table} (
        bucket char(64) NOT NULL,
        hits int unsigned NOT NULL DEFAULT 1,
        expires_at bigint unsigned NOT NULL,
        PRIMARY KEY  (bucket),
        KEY expires_at (expires_at)
    ) {$wpdb->get_charset_collate()};");
    update_option('bsre_schema_version', '1', false);
    install_consent_storage();
}
register_activation_hook(__FILE__, __NAMESPACE__ . '\\install');

/** Native IDs are positive integers or their exact canonical decimal spelling.
 * Never coerce corrupt metadata/registry values into ownership authority. */
function managed_native_page_id($value): int {
    if (is_int($value)) return $value > 0 ? $value : 0;
    if (!is_string($value) || !preg_match('/^[1-9][0-9]*$/D', $value)) return 0;
    $maximum = (string) PHP_INT_MAX;
    if (strlen($value) > strlen($maximum) || (strlen($value) === strlen($maximum) && strcmp($value, $maximum) > 0)) return 0;
    return (int) $value;
}

/** Typed registry/meta agreement is ownership only, never route/readiness approval. */
function registered_service_page_id(string $slug): int {
    if (!isset(SERVICES[$slug])) return 0;
    $pages = get_option('bsre_draft_pages', []);
    if (!is_array($pages)) return 0;
    $id = managed_native_page_id($pages[$slug] ?? null);
    return $id > 0 && get_post_type($id) === 'page' && get_post_meta($id, '_bsre_service', true) === $slug ? $id : 0;
}

/** Only registered published Real Estate landing pages can receive leads. */
function live_paths(): array {
    $paths = [];
    foreach (SERVICES as $slug => $unused) {
        $id = registered_service_page_id($slug);
        if (!$id || get_post_status($id) !== 'publish') continue;
        $url = get_permalink($id);
        if (!is_string($url) || origin($url) !== origin(home_url('/'))) continue;
        $path = parse_url($url, PHP_URL_PATH);
        if ($path !== '/enquire/' . $slug . '/' || parse_url($url, PHP_URL_QUERY) !== null || parse_url($url, PHP_URL_FRAGMENT) !== null) continue;
        $paths[$slug] = $path;
    }
    return $paths;
}

function privacy_url(): string {
    $id = defined('BSRE_PRIVACY_NOTICE_PAGE_ID') ? (int) BSRE_PRIVACY_NOTICE_PAGE_ID : 0;
    if (!$id || get_post_type($id) !== 'page' || get_post_status($id) !== 'publish') return '';
    $url = get_permalink($id);
    return origin($url) === origin(home_url('/')) ? $url : '';
}

function ready(): bool {
    $receiver = defined('BSRE_LEAD_RECEIVER_URL') ? BSRE_LEAD_RECEIVER_URL : '';
    $secret = defined('BSRE_LEAD_HMAC_SECRET') ? BSRE_LEAD_HMAC_SECRET : '';
    return defined('BSRE_ROUTING_ENABLED') && BSRE_ROUTING_ENABLED === true
        && is_string($receiver) && valid_receiver($receiver)
        && is_string($secret) && strlen($secret) >= 32
        && real_estate_home(home_url('/')) && is_ssl()
        && privacy_url() !== '' && count(live_paths()) > 0
        && get_option('bsre_schema_version') === '1';
}

function reply(int $status, string $code, bool $retryable = false): \WP_REST_Response {
    return response($status, ['accepted' => false, 'code' => $code, 'retryable' => $retryable]);
}
function response(int $status, array $body): \WP_REST_Response {
    return new \WP_REST_Response($body, $status, ['Cache-Control' => 'no-store, private, max-age=0', 'X-Content-Type-Options' => 'nosniff']);
}

function same_origin_request(\WP_REST_Request $request): bool {
    $actual = (string) $request->get_header('origin');
    // POST fetch supplies Origin. Never trust the Host or forwarded headers here.
    if ($actual !== origin(home_url('/'))) return false;
    $site = (string) $request->get_header('sec-fetch-site');
    return $site === '' || $site === 'same-origin';
}

/** Persistent atomic counters; no transients, raw IP storage or proxy header trust. */
function limited(string $identifier, int $seconds, int $maximum): bool {
    global $wpdb;
    $now = time();
    $start = intdiv($now, $seconds) * $seconds;
    $key = hash_hmac('sha256', $seconds . ':' . $start . ':' . $identifier, wp_salt('auth'));
    $table = table_name();
    $ok = $wpdb->query($wpdb->prepare("INSERT INTO {$table} (bucket,hits,expires_at) VALUES (%s,1,%d) ON DUPLICATE KEY UPDATE hits=hits+1", $key, $start + $seconds + 7200));
    if ($ok === false) return true; // A database fault cannot bypass protections.
    $hits = $wpdb->get_var($wpdb->prepare("SELECT hits FROM {$table} WHERE bucket=%s", $key));
    if ($hits === null) return true;
    // Buckets become deletion-eligible within roughly three hours. Actual
    // bounded deletion is opportunistic on later traffic, not a retention SLA.
    $wpdb->query($wpdb->prepare("DELETE FROM {$table} WHERE expires_at < %d LIMIT 100", $now));
    return (int) $hits > $maximum;
}

function client_address(): string {
    $ip = $_SERVER['REMOTE_ADDR'] ?? '';
    return is_string($ip) && filter_var($ip, FILTER_VALIDATE_IP) ? $ip : '';
}

function context(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return reply(503, 'NOT_CONFIGURED');
    if (!same_origin_request($request)) return reply(403, 'CSRF_FAILED');
    $ip = client_address();
    if (!$ip || limited('context:' . $ip, 60, 30)) return reply(429, 'RATE_LIMITED', true);
    $session = $_COOKIE[COOKIE] ?? '';
    if (!is_string($session) || !preg_match('/^[a-f0-9]{64}$/D', $session)) {
        try { $session = bin2hex(random_bytes(32)); } catch (\Throwable $e) { return reply(503, 'NOT_CONFIGURED'); }
    }
    if (headers_sent() || !setcookie(COOKIE, $session, ['expires' => time() + 7200, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Strict'])) return reply(503, 'NOT_CONFIGURED');
    $measurement = consent_denied_snapshot();
    try { $measurement = consent_current(consent_repository())['snapshot']; } catch (\Throwable $e) {}
    return response(200, ['csrf_token' => csrf_token($session, time(), wp_salt('auth')), 'expires_in' => 7200, 'minimum_delay_ms' => 2100, 'measurement_eligible' => measurement_eligible(), 'measurement' => $measurement]);
}

function receive(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return reply(503, 'NOT_CONFIGURED');
    if (!same_origin_request($request)) return reply(403, 'CSRF_FAILED');
    $type = (string) $request->get_header('content-type');
    if (!preg_match('~^application/json(?:\s*;\s*charset=utf-8)?$~iD', $type)) return reply(415, 'UNSUPPORTED_MEDIA_TYPE');
    $raw = $request->get_body();
    if (strlen($raw) > 18000) return reply(413, 'PAYLOAD_TOO_LARGE');
    $session = $_COOKIE[COOKIE] ?? '';
    $token = (string) $request->get_header('x-bsre-csrf');
    if (!is_string($session) || !valid_csrf($token, $session, wp_salt('auth'), time())) return reply(403, 'CSRF_FAILED');
    $ip = client_address();
    if (!$ip || limited('submit-minute:' . $ip, 60, 5) || limited('submit-hour:' . $ip, 3600, 30) || limited('submit-session:' . $session, 3600, 20)) return reply(429, 'RATE_LIMITED', true);
    // Honeypot, signed minimum-age challenge, origin, limits and schema are layered
    // abuse controls; none claims human verification or sales qualification.
    if (!validate_payload($raw, home_url('/'), live_paths())) return reply(400, 'VALIDATION_FAILED');
    // Consent evidence is a private sidecar, never a signed payload mutation.
    // Missing evidence denies measurement/exports without stopping valid intake.
    $capture = consent_stage_submission($raw, consent_request_is_retry($request), null, $request->get_header('x-bsre-consent-decision'));
    if ($capture['conflict']) return reply(409, 'REQUEST_ID_CONFLICT');
    try {
        $outgoing = wp_json_encode(envelope($raw, BSRE_LEAD_HMAC_SECRET, (int) floor(microtime(true) * 1000)), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
        if (!is_string($outgoing)) return reply(503, 'NOT_CONFIGURED');
        $upstream = send_envelope(BSRE_LEAD_RECEIVER_URL, $outgoing);
        if (is_wp_error($upstream) || wp_remote_retrieve_response_code($upstream) !== 200) {
            consent_mark_uncertain($capture);
            return reply(503, 'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID', true);
        }
        $result = json_decode(wp_remote_retrieve_body($upstream), false, 16, JSON_THROW_ON_ERROR);
        [$status, $body] = receiver_result($result);
        if ($status === 200 && ($body['accepted'] ?? false) === true) {
            $body['measurement'] = consent_link_accepted($capture, $body, $raw);
            $body['measurement_eligible'] = $body['measurement']['measurement_eligible'];
        } elseif ($status === 503) consent_mark_uncertain($capture);
        return response($status, $body);
    } catch (\Throwable $e) {
        consent_mark_uncertain($capture);
        return reply(503, 'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID', true);
    }
}

/** Google Apps Script returns a redirect for ContentService JSON. Follow only
 * its expected HTTPS Google content host, by GET, without forwarding the body. */
function send_envelope(string $url, string $body) {
    $args = ['method' => 'POST', 'headers' => ['Content-Type' => 'application/json; charset=utf-8'], 'body' => $body, 'timeout' => 15, 'redirection' => 0, 'sslverify' => true, 'limit_response_size' => 8192];
    $first = wp_safe_remote_request($url, $args);
    if (is_wp_error($first)) return $first;
    $code = wp_remote_retrieve_response_code($first);
    if (!in_array($code, [302,303], true)) return $first;
    $location = wp_remote_retrieve_header($first, 'location');
    $p = is_string($location) ? parse_url($location) : false;
    if (!$p || ($p['scheme'] ?? '') !== 'https' || ($p['host'] ?? '') !== 'script.googleusercontent.com' || isset($p['user']) || isset($p['pass']) || isset($p['port']) || ($p['path'] ?? '') !== '/macros/echo') return new \WP_Error('BSRE_REDIRECT_REJECTED');
    return wp_safe_remote_get($location, ['timeout' => 10, 'redirection' => 0, 'sslverify' => true, 'limit_response_size' => 8192]);
}

add_action('rest_api_init', function (): void {
    register_rest_route('bsre/v1', '/context', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\context']);
    register_rest_route('bsre/v1', '/lead', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\receive']);
});
// WordPress can append permissive CORS headers to REST responses. Remove them
// solely on this namespace, including method errors and unmatched route suffixes.
add_filter('rest_pre_serve_request', function ($served, $result, $request, $server) {
    if (str_starts_with($request->get_route(), '/bsre/v1/')) {
        header_remove('Access-Control-Allow-Origin');
        header_remove('Access-Control-Allow-Credentials');
        header_remove('Access-Control-Allow-Methods');
        header_remove('Access-Control-Allow-Headers');
    }
    return $served;
}, 99, 4);

function service_slug(): string {
    if (!is_page()) return '';
    $id = managed_native_page_id(get_queried_object_id());
    if (!$id) return '';
    $slug = get_post_meta($id, '_bsre_service', true);
    return is_string($slug) && isset(SERVICES[$slug]) && registered_service_page_id($slug) === $id ? $slug : '';
}
function managed_page(): bool {
    if (!is_page()) return false;
    if (service_slug() !== '') return true;
    $id = managed_native_page_id(get_queried_object_id());
    return $id > 0 && $id === managed_native_page_id(get_option('bsre_parent_draft', 0))
        && get_post_type($id) === 'page' && get_post_meta($id, '_bsre_parent', true) === '1';
}
add_filter('wp_robots', function (array $robots): array {
    if (managed_page()) { unset($robots['index'], $robots['follow']); $robots['noindex'] = true; $robots['nofollow'] = true; }
    return $robots;
});
add_action('template_redirect', function (): void {
    if (managed_page()) { nocache_headers(); header('X-Robots-Tag: noindex, nofollow', true); header('Referrer-Policy: no-referrer', true); }
});

require_once __DIR__ . '/includes/drafts.php';
require_once __DIR__ . '/includes/admin.php';
require_once __DIR__ . '/includes/parent-isolation.php';
require_once __DIR__ . '/includes/presentation.php';
if (defined('WP_CLI') && WP_CLI) require_once __DIR__ . '/includes/cli.php';
