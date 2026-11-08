<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

const CONSENT_NOTICE_VERSION = 'bsre-enquiry-consent-2026-10-19-v1';
const CONSENT_PREFERENCE_SECONDS = 15552000; // 180 days, separate from lead retention.
const CONSENT_COOKIE = '__Host-bsre_consent';
const CONSENT_SESSION_COOKIE = '__Host-bsre_consent_session';
const CONSENT_PENDING_COOKIE = '__Host-bsre_consent_pending';
require_once __DIR__ . '/consent-store.php';

function consent_denied_snapshot(): array {
    return ['preferences' => ['analytics' => false, 'ad_measurement' => false, 'personalization' => false], 'known' => false, 'acknowledged' => false, 'measurement_eligible' => false, 'decision_version' => 'none', 'notice_version' => CONSENT_NOTICE_VERSION, 'preference_expires_at' => 0, 'preference_days' => 180];
}
function consent_repository(?ConsentRepository $store = null): ConsentRepository {
    if ($store) return $store;
    global $wpdb;
    if (get_option('bsre_consent_schema_version') !== '2' || !is_object($wpdb)) throw new \RuntimeException('Consent storage unavailable.');
    return new WpConsentRepository($wpdb);
}
function consent_cookie_token(string $subject, int $expires, string $salt): string {
    if (!preg_match('/^[a-f0-9]{32}$/D', $subject) || strlen($salt) < 32) throw new \RuntimeException('Consent unavailable.');
    $body = 'cp1|' . $subject . '|' . $expires;
    return $body . '|' . hash_hmac('sha256', 'bsre-consent-cookie-v1|' . $body, $salt);
}
function consent_cookie_subject($cookie, string $salt, int $now): ?string {
    if (!is_string($cookie) || strlen($cookie) > 160 || strlen($salt) < 32 || !preg_match('/^cp1\|([a-f0-9]{32})\|([1-9][0-9]{0,10})\|([a-f0-9]{64})$/D', $cookie, $m)) return null;
    $expiry = (int) $m[2];
    if ($expiry <= $now || $expiry > $now + CONSENT_PREFERENCE_SECONDS) return null;
    $body = 'cp1|' . $m[1] . '|' . $m[2];
    return hash_equals(hash_hmac('sha256', 'bsre-consent-cookie-v1|' . $body, $salt), $m[3]) ? $m[1] : null;
}
function consent_subject_key(string $subject): string { return hash_hmac('sha256', 'bsre-consent-subject-v1|' . $subject, wp_salt('auth')); }
function consent_csrf(string $session, int $now, string $salt): string {
    $expires = $now + 7200;
    return 'cc1|' . $expires . '|' . hash_hmac('sha256', 'bsre-consent-csrf-v1|' . $session . '|' . $expires, $salt);
}
function valid_consent_csrf(string $token, string $session, int $now, string $salt): bool {
    if (!preg_match('/^[a-f0-9]{64}$/D', $session) || !preg_match('/^cc1\|([1-9][0-9]{0,10})\|([a-f0-9]{64})$/D', $token, $m)) return false;
    $expires = (int) $m[1];
    return $expires > $now && $expires <= $now + 7200 && strlen($salt) >= 32 && hash_equals(hash_hmac('sha256', 'bsre-consent-csrf-v1|' . $session . '|' . $m[1], $salt), $m[2]);
}
function consent_set_cookie(string $name, string $value, int $expires, bool $http_only = true): bool {
    if (headers_sent()) return false;
    $ok = setcookie($name, $value, ['expires' => $expires, 'path' => '/', 'secure' => true, 'httponly' => $http_only, 'samesite' => 'Strict']);
    if ($ok) { if ($expires > time()) $_COOKIE[$name] = $value; else unset($_COOKIE[$name]); }
    return $ok;
}
function consent_current(ConsentRepository $store, bool $observe_pending = true): array {
    $subject = consent_cookie_subject($_COOKIE[CONSENT_COOKIE] ?? null, wp_salt('auth'), time());
    if ($subject === null) return ['subject' => null, 'row' => null, 'snapshot' => consent_denied_snapshot()];
    $key = consent_subject_key($subject);
    $row = $store->current($key);
    if ($observe_pending && array_key_exists(CONSENT_PENDING_COOKIE, $_COOKIE)) {
        $row = $store->choose($key, ['analytics' => false, 'ad_measurement' => false], CONSENT_NOTICE_VERSION, time(), true);
    }
    $snapshot = consent_denied_snapshot();
    if ($row && (int) $row['expires_at'] > time() && (int) $row['uncertain'] === 0 && $row['notice_version'] === CONSENT_NOTICE_VERSION && !array_key_exists(CONSENT_PENDING_COOKIE, $_COOKIE)) {
        $snapshot = ['preferences' => ['analytics' => (int) $row['analytics'] === 1, 'ad_measurement' => (int) $row['ad_measurement'] === 1, 'personalization' => false], 'known' => true, 'acknowledged' => true, 'measurement_eligible' => measurement_eligible(), 'decision_version' => $row['receipt'], 'notice_version' => $row['notice_version'], 'preference_expires_at' => (int) $row['expires_at'], 'preference_days' => 180];
    }
    return ['subject' => $subject, 'row' => $row, 'snapshot' => $snapshot];
}
function consent_api_guard(\WP_REST_Request $request): ?\WP_REST_Response {
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') return response(405, ['ok' => false, 'code' => 'METHOD_NOT_ALLOWED'] + consent_denied_snapshot());
    if (!is_ssl() || !real_estate_home(home_url('/')) || !same_origin_request($request)) return response(403, ['ok' => false, 'code' => 'CONSENT_ORIGIN_FAILED'] + consent_denied_snapshot());
    if (!preg_match('~^application/json(?:\s*;\s*charset=utf-8)?$~iD', (string) $request->get_header('content-type'))) return response(415, ['ok' => false, 'code' => 'UNSUPPORTED_MEDIA_TYPE'] + consent_denied_snapshot());
    if (strlen($request->get_body()) > 1024) return response(413, ['ok' => false, 'code' => 'PAYLOAD_TOO_LARGE'] + consent_denied_snapshot());
    return null;
}
function consent_context(\WP_REST_Request $request, ?ConsentRepository $repository = null): \WP_REST_Response {
    if ($bad = consent_api_guard($request)) return $bad;
    try {
        $body = json_decode($request->get_body(), false, 8, JSON_THROW_ON_ERROR);
        if (!is_object($body) || get_object_vars($body) !== []) throw new \InvalidArgumentException();
    } catch (\Throwable $e) { return response(400, ['ok' => false, 'code' => 'CONSENT_INVALID'] + consent_denied_snapshot()); }
    $ip = client_address();
    if (!$ip || limited('consent-context:' . $ip, 60, 30)) return response(429, ['ok' => false, 'code' => 'RATE_LIMITED'] + consent_denied_snapshot());
    try {
        $session = $_COOKIE[CONSENT_SESSION_COOKIE] ?? '';
        if (!is_string($session) || !preg_match('/^[a-f0-9]{64}$/D', $session)) $session = bin2hex(random_bytes(32));
        if (!consent_set_cookie(CONSENT_SESSION_COOKIE, $session, time() + 7200)) throw new \RuntimeException();
        $snapshot = consent_denied_snapshot();
        try { $snapshot = consent_current(consent_repository($repository))['snapshot']; } catch (\Throwable $e) {}
        return response(200, ['ok' => true, 'csrf_token' => consent_csrf($session, time(), wp_salt('auth')), 'expires_in' => 7200] + $snapshot);
    } catch (\Throwable $e) { return response(503, ['ok' => false, 'code' => 'CONSENT_UNAVAILABLE'] + consent_denied_snapshot()); }
}
/** Reject duplicate decoded object keys, including escaped aliases. The JSON
 * decoder validates grammar first; quoted braces/key-like text stay values. */
function consent_choice_object(string $raw): object {
    $choice = json_decode($raw, false, 8, JSON_THROW_ON_ERROR);
    if (!is_object($choice)) throw new \InvalidArgumentException();
    $stack = []; $length = strlen($raw);
    for ($i = 0; $i < $length; $i++) {
        $c = $raw[$i];
        if ($c === '"') {
            $start = $i; $i++;
            while ($i < $length) { if ($raw[$i] === '\\') { $i += 2; continue; } if ($raw[$i] === '"') break; $i++; }
            $top = count($stack) - 1;
            if ($top >= 0 && $stack[$top]['object'] && $stack[$top]['key']) {
                $key = json_decode(substr($raw, $start, $i - $start + 1), false, 2, JSON_THROW_ON_ERROR);
                if (array_key_exists($key, $stack[$top]['seen'])) throw new \InvalidArgumentException();
                $stack[$top]['seen'][$key] = true; $stack[$top]['key'] = false;
            }
        } elseif ($c === '{') $stack[] = ['object' => true, 'key' => true, 'seen' => []];
        elseif ($c === '[') $stack[] = ['object' => false, 'key' => false, 'seen' => []];
        elseif ($c === '}' || $c === ']') array_pop($stack);
        elseif ($c === ',' && $stack && $stack[count($stack) - 1]['object']) $stack[count($stack) - 1]['key'] = true;
    }
    return $choice;
}
function consent_update(\WP_REST_Request $request, ?ConsentRepository $repository = null): \WP_REST_Response {
    if ($bad = consent_api_guard($request)) return $bad;
    $session = $_COOKIE[CONSENT_SESSION_COOKIE] ?? '';
    $token = (string) $request->get_header('x-bsre-consent-csrf');
    if (!is_string($session) || !valid_consent_csrf($token, $session, time(), wp_salt('auth'))) return response(403, ['ok' => false, 'code' => 'CONSENT_CSRF_FAILED'] + consent_denied_snapshot());
    if (limited('consent-update:' . $session, 60, 20)) return response(429, ['ok' => false, 'code' => 'RATE_LIMITED'] + consent_denied_snapshot());
    try {
        $choice_raw = $request->get_body();
        $choice = consent_choice_object($choice_raw);
        preg_match_all('/"(analytics|ad_measurement|personalization|notice_version)"\s*:/', $choice_raw, $literal_keys);
        if (count($literal_keys[1]) !== 4 || count(array_unique($literal_keys[1])) !== 4) throw new \InvalidArgumentException();
        $keys = array_keys(get_object_vars($choice)); sort($keys);
        if ($keys !== ['ad_measurement','analytics','notice_version','personalization'] || !is_bool($choice->analytics) || !is_bool($choice->ad_measurement) || $choice->personalization !== false || $choice->notice_version !== CONSENT_NOTICE_VERSION) throw new \InvalidArgumentException();
    } catch (\Throwable $e) { return response(400, ['ok' => false, 'code' => 'CONSENT_INVALID'] + consent_denied_snapshot()); }
    try {
        if (headers_sent()) throw new \RuntimeException();
        $store = consent_repository($repository);
        $current = consent_current($store); // Observed pending cookie records restrictive uncertainty first.
        $subject = $current['subject'] ?? bin2hex(random_bytes(16));
        $row = $store->choose(consent_subject_key($subject), ['analytics' => $choice->analytics, 'ad_measurement' => $choice->ad_measurement], CONSENT_NOTICE_VERSION, time());
        if (!consent_set_cookie(CONSENT_COOKIE, consent_cookie_token($subject, (int) $row['expires_at'], wp_salt('auth')), (int) $row['expires_at'])) throw new \RuntimeException();
        if (!consent_set_cookie(CONSENT_PENDING_COOKIE, '', time() - 3600, false)) throw new \RuntimeException();
        return response(200, ['ok' => true] + consent_current($store, false)['snapshot']);
    } catch (\Throwable $e) { return response(503, ['ok' => false, 'code' => 'CONSENT_UNAVAILABLE'] + consent_denied_snapshot()); }
}
add_action('rest_api_init', function (): void {
    register_rest_route('bsre/v1', '/consent/context', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\consent_context']);
    register_rest_route('bsre/v1', '/consent/update', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\consent_update']);
});

/** Attempt durable original evidence BEFORE forwarding. Storage failure does not
 * break healthy enquiry delivery; it always denies measurement/export evidence. */
function consent_request_is_retry(\WP_REST_Request $request): bool {
    // WordPress returns NULL for an absent header. A missing/empty header is a
    // first attempt; any nonempty retry marker can only restrict permission.
    $value = $request->get_header('x-bsre-consent-retry');
    return is_string($value) && $value !== '';
}
function consent_stage_submission(string $raw, bool $retry = false, ?ConsentRepository $repository = null, ?string $decision = null): array {
    $handle = ['recorded' => false, 'conflict' => false, 'row' => null, 'repository' => null];
    try {
        $payload = json_decode($raw, false, 16, JSON_THROW_ON_ERROR);
        if (!is_object($payload) || !is_string($payload->request_id ?? null) || !preg_match(UUID_V4, $payload->request_id)) return $handle;
        $store = consent_repository($repository);
        $state = consent_current($store);
        $snapshot = $state['snapshot'];
        // A client decision version can only narrow the server-validated choice.
        // This prevents a cookie grant arriving after the original submit event
        // from upgrading that event's initially denied/unknown decision.
        $known = !$retry && $snapshot['known'] && is_string($decision) && hash_equals($snapshot['decision_version'], $decision);
        $eligible = $known && measurement_eligible($raw);
        $ad_granted = $known && $snapshot['preferences']['ad_measurement'];
        $clicks = consent_capture_clicks($payload, $ad_granted && $eligible, time());
        $row = $store->stage(['request_id' => strtolower($payload->request_id), 'fingerprint' => hash('sha256', $raw), 'subject_key' => $state['row']['subject_key'] ?? '', 'original_revision' => (int) ($state['row']['revision'] ?? 0), 'decision_version' => $known ? $snapshot['decision_version'] : bin2hex(random_bytes(16)), 'notice_version' => CONSENT_NOTICE_VERSION, 'analytics' => $known && $snapshot['preferences']['analytics'] ? 1 : 0, 'ad_measurement' => $ad_granted ? 1 : 0, 'preference_expires_at' => $known ? $snapshot['preference_expires_at'] : 0, 'eligible' => $eligible ? 1 : 0, 'known' => $known ? 1 : 0, 'created_at' => time(), 'uncertain' => $retry ? 1 : 0] + $clicks);
        return ['recorded' => true, 'conflict' => false, 'row' => $row, 'repository' => $store];
    } catch (\DomainException $e) { $handle['conflict'] = true; return $handle; }
    catch (\Throwable $e) { return $handle; }
}
/** Whole, immutable browser capture. A client timestamp is not a verified Google
 * click time. Invalid/oversize values invalidate ALL click evidence, not intake. */
function consent_capture_clicks(object $payload, bool $permitted, int $now): array {
    $empty = ['click_capture_state' => $permitted ? 'MISSING' : 'NOT_PERMITTED', 'gclid_first' => '', 'gclid_last' => '', 'gclid_first_captured_ms' => 0, 'gclid_last_captured_ms' => 0];
    if (!$permitted) return $empty;
    $out = $empty;
    foreach (['first','last'] as $touch) {
        $record = $payload->attribution->$touch ?? null;
        if (!is_object($record) || !is_object($record->parameters ?? null) || !property_exists($record->parameters, 'gclid')) continue;
        $gclid = $record->parameters->gclid;
        $stamp = $record->timestamp ?? null;
        if (!is_string($gclid) || !preg_match('/^[A-Za-z0-9._~-]{1,256}$/D', $gclid) || (!is_int($stamp) && !is_float($stamp)) || !is_finite((float) $stamp) || floor((float) $stamp) !== (float) $stamp || $stamp < 946684800000 || $stamp > $now * 1000 + 300000) {
            $empty['click_capture_state'] = 'INVALID'; return $empty;
        }
        $out['gclid_' . $touch] = $gclid;
        $out['gclid_' . $touch . '_captured_ms'] = (int) $stamp;
        $out['click_capture_state'] = 'CAPTURED';
    }
    return $out;
}
function consent_mark_uncertain(array $handle): void {
    if (!$handle['recorded']) return;
    try { $handle['repository']->uncertain($handle['row']['request_id'], $handle['row']['fingerprint']); } catch (\Throwable $e) {}
}
function consent_capture_snapshot(array $row, ConsentRepository $store, bool $visitor_eligible): array {
    $denied = consent_denied_snapshot();
    if (($row['state'] ?? '') !== 'ACCEPTED' || (int) ($row['uncertain'] ?? 1) !== 0 || (int) ($row['known'] ?? 0) !== 1 || (int) ($row['preference_expires_at'] ?? 0) <= time()) return $denied;
    $current = $store->current($row['subject_key']);
    if (!$current || (int) $current['uncertain'] !== 0 || (int) $current['expires_at'] <= time() || $current['notice_version'] !== CONSENT_NOTICE_VERSION || $row['notice_version'] !== CONSENT_NOTICE_VERSION) return $denied;
    $flags = ['personalization' => false];
    foreach (['analytics','ad_measurement'] as $purpose) $flags[$purpose] = (int) $row[$purpose] === 1 && (int) $current[$purpose] === 1 && !$store->revoked($row['subject_key'], (int) $row['original_revision'], $purpose);
    return ['preferences' => ['analytics' => $flags['analytics'], 'ad_measurement' => $flags['ad_measurement'], 'personalization' => false], 'known' => true, 'acknowledged' => true, 'measurement_eligible' => (int) $row['eligible'] === 1 && $visitor_eligible, 'decision_version' => $row['decision_version'], 'notice_version' => $row['notice_version'], 'preference_expires_at' => min((int) $row['preference_expires_at'], (int) $current['expires_at']), 'preference_days' => 180];
}
function consent_link_accepted(array $handle, array $receipt, string $raw): array {
    if (!$handle['recorded']) return consent_denied_snapshot();
    try {
        if (!consent_valid_receipt_id($receipt['lead_id'] ?? null, 'BSRE-') || !consent_valid_receipt_id($receipt['event_id'] ?? null, 'evt_')) throw new \RuntimeException();
        $store = $handle['repository'];
        $row = $store->link($handle['row']['request_id'], $handle['row']['fingerprint'], $receipt['lead_id'], $receipt['event_id']);
        // Receipt metadata is private to the original signed preference subject.
        // An exact-body replay from a new/cleared browser may reconcile delivery
        // but cannot borrow the original browser's positive measurement choice.
        $current = consent_current($store);
        if (!$current['snapshot']['known'] || !is_array($current['row']) || !hash_equals($row['subject_key'], $current['row']['subject_key'])) return consent_denied_snapshot();
        return consent_capture_snapshot($row, $store, measurement_eligible($raw));
    } catch (\Throwable $e) { consent_mark_uncertain($handle); return consent_denied_snapshot(); }
}
function consent_valid_receipt_id($value, string $prefix): bool {
    return is_string($value) && str_starts_with($value, $prefix) && preg_match(UUID_V4, substr($value, strlen($prefix))) === 1;
}
