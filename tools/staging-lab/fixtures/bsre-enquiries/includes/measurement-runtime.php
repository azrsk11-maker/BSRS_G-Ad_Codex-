<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

/** Public destination identifiers only. Deployment remains disabled until the
 * reviewed container and real destination settings are deliberately enabled. */
function measurement_runtime_configuration(string $purpose): array {
    $valid = in_array($purpose, ['analytics','advertising'], true);
    $settings = measurement_settings();
    return ['version' => '1.0.0', 'enabled' => $valid && $settings['enabled'] && ($purpose === 'analytics' ? $settings['analytics_enabled'] : $settings['advertising_enabled'] && $settings['ads_send_to'] !== ''), 'purpose' => $purpose, 'origin' => origin(home_url('/')), 'gtm_id' => 'GTM-NW8WXKRF', 'measurement_id' => $purpose === 'analytics' ? 'G-W01P9W3NWE' : '', 'ads_send_to' => $purpose === 'advertising' ? $settings['ads_send_to'] : '', 'cookie_prefix' => $purpose === 'analytics' ? 'bsre_enq_analytics' : 'bsre_enq_ads', 'config_version' => $settings['config_version'], 'status_endpoint' => rest_url('bsre/v1/measurement/status')];
}
function measurement_runtime_query(array $params): ?array {
    $purpose = $params['purpose'] ?? null;
    if (!is_string($purpose) || !in_array($purpose, ['analytics','advertising'], true)) return null;
    $allowed = $purpose === 'analytics' ? ['purpose'] : ['purpose','gclid','gbraid','wbraid'];
    if (array_diff(array_keys($params), $allowed)) return null;
    foreach (array_diff($allowed, ['purpose']) as $key) {
        if (array_key_exists($key, $params) && (!is_string($params[$key]) || !preg_match('/^[A-Za-z0-9._~-]{1,256}$/D', $params[$key]))) return null;
    }
    return $params;
}
function measurement_lease_token(string $purpose, string $session, string $version, int $now, string $decision): string {
    if (!in_array($purpose, ['analytics','advertising'], true) || !preg_match('/^[a-f0-9]{64}$/D', $session) || !preg_match('/^gm1-[a-f0-9]{32}$/D', $version) || !preg_match('/^[a-f0-9]{32}$/D', $decision)) throw new \RuntimeException('Lease unavailable.');
    $expires = $now + 120;
    return 'ml1|' . $expires . '|' . hash_hmac('sha256', 'bsre-measurement-lease-v1|' . $purpose . '|' . $session . '|' . $version . '|' . $decision . '|' . $expires, wp_salt('auth'));
}
function measurement_valid_lease(string $token, string $purpose, string $session, string $version, int $now, string $decision): bool {
    if (!preg_match('/^ml1\|([1-9][0-9]{0,10})\|([a-f0-9]{64})$/D', $token, $m) || (int) $m[1] <= $now || (int) $m[1] > $now + 120) return false;
    try { return hash_equals(measurement_lease_token($purpose, $session, $version, (int) $m[1] - 120, $decision), $token); }
    catch (\Throwable $e) { return false; }
}
function measurement_runtime_permission(string $purpose, ?ConsentRepository $repository): bool {
    if (!measurement_eligible()) return false;
    try {
        $snapshot = consent_current(consent_repository($repository))['snapshot'];
        $flag = $purpose === 'analytics' ? 'analytics' : 'ad_measurement';
        return $snapshot['known'] && $snapshot['acknowledged'] && $snapshot['measurement_eligible'] && $snapshot['preferences'][$flag];
    } catch (\Throwable $e) { return false; }
}
function measurement_runtime_revision(?ConsentRepository $repository): string {
    try { $snapshot = consent_current(consent_repository($repository))['snapshot']; return $snapshot['known'] && $snapshot['acknowledged'] ? $snapshot['decision_version'] : 'none'; }
    catch (\Throwable $e) { return 'none'; }
}
function measurement_status(\WP_REST_Request $request, ?ConsentRepository $repository = null): \WP_REST_Response {
    $deny = static function (int $status = 403): \WP_REST_Response { return response($status, ['ok' => false, 'version' => '1.0.0', 'enabled' => false]); };
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST' || !is_ssl() || !real_estate_home(home_url('/')) || !same_origin_request($request)) return $deny();
    if (!preg_match('~^application/json(?:\s*;\s*charset=utf-8)?$~iD', (string) $request->get_header('content-type')) || strlen($request->get_body()) > 512) return $deny();
    try {
        $raw = $request->get_body(); $choice = json_decode($raw, false, 8, JSON_THROW_ON_ERROR);
        if (!is_object($choice)) return $deny();
        $keys = array_keys(get_object_vars($choice)); sort($keys);
        preg_match_all('/"(purpose|lease_token|config_version)"\s*:/', $raw, $literal);
        if ($keys !== ['config_version','lease_token','purpose'] || count($literal[1]) !== 3 || count(array_unique($literal[1])) !== 3 || !is_string($choice->purpose) || !in_array($choice->purpose, ['analytics','advertising'], true) || !is_string($choice->lease_token) || !is_string($choice->config_version)) return $deny();
        $config = measurement_runtime_configuration($choice->purpose);
        $session = $_COOKIE[CONSENT_SESSION_COOKIE] ?? '';
        $decision = measurement_runtime_revision($repository);
        if (!$config['enabled'] || !hash_equals($config['config_version'], $choice->config_version) || !is_string($session) || !measurement_valid_lease($choice->lease_token, $choice->purpose, $session, $choice->config_version, time(), $decision)) return $deny();
        // Per random browser session and purpose: two frames behind one NAT do
        // not share a global IP allowance. This does not count enquiry requests.
        if (limited('measurement-lease:' . $session . ':' . $choice->purpose, 60, 20)) return $deny(429);
        if (!measurement_runtime_permission($choice->purpose, $repository)) return $deny();
        return response(200, ['ok' => true, 'version' => '1.0.0', 'enabled' => true, 'purpose' => $choice->purpose, 'config_version' => $config['config_version'], 'lease_token' => measurement_lease_token($choice->purpose, $session, $config['config_version'], time(), $decision), 'lease_seconds' => 30]);
    } catch (\Throwable $e) { return $deny(); }
}
function measurement_runtime(\WP_REST_Request $request, ?ConsentRepository $repository = null): \WP_REST_Response {
    $headers = ['Cache-Control' => 'no-store, private, max-age=0', 'Content-Type' => 'text/html; charset=UTF-8', 'X-Content-Type-Options' => 'nosniff', 'X-Frame-Options' => 'SAMEORIGIN', 'Referrer-Policy' => 'origin'];
    $deny = static function () use ($headers): \WP_REST_Response { return new \WP_REST_Response('<!doctype html><html lang="en"><meta charset="utf-8"><title>Measurement unavailable</title></html>', 403, $headers); };
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'GET' || !is_ssl() || !real_estate_home(home_url('/')) || !measurement_eligible()) return $deny();
    // Parent uses referrerPolicy=origin. Never accept or echo a full form URL.
    if (origin((string) $request->get_header('referer')) !== origin(home_url('/')) || $request->get_header('sec-fetch-site') !== 'same-origin' || $request->get_header('sec-fetch-dest') !== 'iframe') return $deny();
    $params = measurement_runtime_query($request->get_query_params());
    if ($params === null) return $deny();
    $config = measurement_runtime_configuration($params['purpose']);
    if (!$config['enabled']) return $deny();
    if (!measurement_runtime_permission($params['purpose'], $repository)) return $deny();
    $session = $_COOKIE[CONSENT_SESSION_COOKIE] ?? '';
    try { $config['lease_token'] = measurement_lease_token($params['purpose'], is_string($session) ? $session : '', $config['config_version'], time(), measurement_runtime_revision($repository)); $config['lease_seconds'] = 30; }
    catch (\Throwable $e) { return $deny(); }
    $asset = plugin_dir_url(dirname(__DIR__) . '/bsre-enquiries.php') . 'assets/google-runtime.js?ver=' . PLUGIN_VERSION;
    if (origin($asset) !== origin(home_url('/'))) return $deny();
    // JSON is inert and hex escaped. No lead/contact/signing secret is copied
    // into HTML. The purpose-bound lease token stays in local configuration and
    // local status POSTs, never vendor payloads. Ad IDs remain in this frame URL.
    $json = wp_json_encode($config, JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT);
    if (!is_string($json)) return $deny();
    $headers['Content-Security-Policy'] = "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; connect-src 'self' https://www.googletagmanager.com https://*.google-analytics.com https://www.google-analytics.com https://www.google.com https://www.googleadservices.com https://googleads.g.doubleclick.net https://stats.g.doubleclick.net; img-src https://*.google-analytics.com https://www.google-analytics.com https://www.google.com https://www.googleadservices.com https://googleads.g.doubleclick.net https://stats.g.doubleclick.net; frame-src https://www.googletagmanager.com";
    $html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><title>Enquiry measurement runtime</title></head><body><script id="bsre-runtime-config" type="application/json">' . $json . '</script><script src="' . esc_url($asset) . '" defer></script></body></html>';
    return new \WP_REST_Response($html, 200, $headers);
}
add_action('rest_api_init', function (): void {
    register_rest_route('bsre/v1', '/measurement/runtime', ['methods' => 'GET', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\measurement_runtime']);
    register_rest_route('bsre/v1', '/measurement/status', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\measurement_status']);
});
// WordPress REST normally JSON encodes strings. Serve HTML only for our exact
// successful/denied runtime response; every other endpoint keeps its protocol.
add_filter('rest_pre_serve_request', function ($served, $result, $request) {
    if ($served || !($request instanceof \WP_REST_Request) || $request->get_route() !== '/bsre/v1/measurement/runtime' || !($result instanceof \WP_REST_Response)) return $served;
    $headers = $result->get_headers();
    if (($headers['Content-Type'] ?? '') !== 'text/html; charset=UTF-8' || !is_string($result->get_data())) return $served;
    echo $result->get_data();
    return true;
}, 10, 3);
