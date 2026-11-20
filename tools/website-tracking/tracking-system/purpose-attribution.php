<?php
declare(strict_types=1);
namespace BSRE\PurposeAttribution;

use BSRE\Enquiries as Intake;

/** Private, opt-in candidate. No public history/export endpoint or Google output. */
final class Runtime {
    public static ?ConsentRepository $store = null;
    public static ?array $submission = null;
}

function repository(): ConsentRepository {
    global $wpdb;
    return Runtime::$store ?? new WpConsentRepository($wpdb);
}
function exact_object($value, array $keys): bool {
    if (!$value instanceof \stdClass) return false;
    $actual = array_keys(get_object_vars($value));
    sort($actual); sort($keys);
    return $actual === $keys;
}
function canonical($value): string {
    return json_encode($value, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
}
function invalid(): void { throw new \InvalidArgumentException('PURPOSE_ATTRIBUTION_INVALID'); }
function clean_url($value): string {
    if (!is_string($value) || strlen($value) > 2000 || preg_match('/[\\\\\s\x00-\x1f\x7f]/u', $value)) invalid();
    if ($value === '') return '';
    $parts = parse_url($value);
    if (!is_array($parts) || !in_array($parts['scheme'] ?? '', ['http', 'https'], true)
        || !preg_match('/^[a-z0-9.-]+$/iD', $parts['host'] ?? '') || isset($parts['user']) || isset($parts['pass'])) invalid();
    return $parts['scheme'] . '://' . strtolower($parts['host'])
        . (isset($parts['port']) ? ':' . $parts['port'] : '') . ($parts['path'] ?? '/');
}
function normalize_touch($value, string $purpose, int $now): ?array {
    if ($value === null) return null;
    if (!exact_object($value, ['capture_id','decision_version','notice_version','landing_page','referrer','timestamp','parameters'])) invalid();
    if (!is_string($value->capture_id) || !preg_match(Intake\UUID_V4, $value->capture_id)
        || !is_string($value->decision_version) || !preg_match('/^[a-f0-9]{32}$/D', $value->decision_version)
        || $value->notice_version !== Intake\CONSENT_NOTICE_VERSION
        || !is_int($value->timestamp) || $value->timestamp < 946684800000 || $value->timestamp > $now * 1000 + 300000
        || !$value->parameters instanceof \stdClass) invalid();
    $allowed = ['utm_source','utm_medium','utm_campaign','utm_id','utm_term','utm_content','google_campaign_id','ad_group_id','creative_id'];
    if ($purpose === 'advertising') $allowed = array_merge($allowed, ['gclid','gbraid','wbraid']);
    $parameters = [];
    foreach (get_object_vars($value->parameters) as $key => $cell) {
        if (!in_array($key, $allowed, true) || !Intake\text($cell, 256, true)
            || preg_match('/[\p{C}]/u', $cell)) invalid();
        if (in_array($key, ['gclid','gbraid','wbraid'], true) && !preg_match('/^[A-Za-z0-9._~-]{1,256}$/D', $cell)) invalid();
        if (in_array($key, ['google_campaign_id','ad_group_id','creative_id'], true)
            && !preg_match('/^[0-9]{1,32}$/D', $cell)) invalid();
        $parameters[$key] = $cell;
    }
    ksort($parameters, SORT_STRING);
    $landing = clean_url($value->landing_page);
    if ($landing === '' || Intake\origin($landing) !== Intake\origin(home_url('/'))) invalid();
    $referrer = clean_url($value->referrer);
    if ($purpose === 'advertising' && $referrer !== '') invalid();
    return ['capture_id' => strtolower($value->capture_id), 'decision_version' => $value->decision_version,
        'notice_version' => $value->notice_version, 'landing_page' => $landing, 'referrer' => $referrer,
        'timestamp' => $value->timestamp, 'parameters' => (object) $parameters];
}
function normalize_sidecar($value, int $now): array {
    if (!exact_object($value, ['version','analytics','advertising']) || $value->version !== 1) invalid();
    $result = ['version' => 1];
    foreach (['analytics','advertising'] as $purpose) {
        if (!exact_object($value->$purpose, ['first','last'])) invalid();
        $first = normalize_touch($value->$purpose->first, $purpose, $now);
        $last = normalize_touch($value->$purpose->last, $purpose, $now);
        if (($first === null) !== ($last === null) || ($first && $first['timestamp'] > $last['timestamp'])) invalid();
        if ($first && $first['capture_id'] === $last['capture_id'] && canonical($first) !== canonical($last)) invalid();
        $result[$purpose] = ['first' => $first, 'last' => $last];
    }
    return $result;
}
function rows($db, string $sql): array {
    $db->last_error = '';
    $result = $db->get_results($sql, ARRAY_A);
    if ($db->last_error !== '' || !is_array($result) || count($result) > 1000) throw new \RuntimeException('PURPOSE_STORAGE_UNAVAILABLE');
    return $result;
}
function verified_touch(?array $touch, string $purpose, array $current, array $history, int $now): ?array {
    if ($touch === null) return null;
    $flag = $purpose === 'advertising' ? 'ad_measurement' : 'analytics';
    if ((int) ($current['uncertain'] ?? 1) !== 0 || (int) ($current[$flag] ?? 0) !== 1
        || (int) ($current['expires_at'] ?? 0) <= $now || ($current['notice_version'] ?? '') !== Intake\CONSENT_NOTICE_VERSION) return null;
    $original = null;
    $next = null;
    foreach ($history as $index => $row) {
        if (($row['receipt'] ?? '') === $touch['decision_version']) {
            if ($original !== null) return null;
            $original = $row;
            $next = $history[$index + 1] ?? null;
        }
    }
    if (!$original || (int) $original['uncertain'] !== 0 || (int) $original[$flag] !== 1
        || $original['notice_version'] !== $touch['notice_version']) return null;
    $start = (int) $original['changed_at'];
    $expires = $start + Intake\CONSENT_PREFERENCE_SECONDS;
    if ($touch['timestamp'] < $start * 1000 || $touch['timestamp'] >= $expires * 1000 || $expires <= $now
        || ($next && $touch['timestamp'] >= (int) $next['changed_at'] * 1000)) return null;
    $expected = (int) $original['revision'];
    $previous = $start;
    $last = null;
    foreach ($history as $row) {
        if ((int) $row['revision'] < (int) $original['revision']) continue;
        if ((int) $row['revision'] !== $expected++ || (int) $row['changed_at'] < $previous
            || (int) $row['uncertain'] !== 0 || (int) $row[$flag] !== 1
            || $row['notice_version'] !== Intake\CONSENT_NOTICE_VERSION) return null;
        $previous = (int) $row['changed_at'];
        $last = $row;
    }
    if (!$last || (int) $last['revision'] !== (int) $current['revision'] || $last['receipt'] !== $current['receipt']) return null;
    return $touch + ['original_revision' => (int) $original['revision'], 'expires_at' => $expires];
}
function prepare_capture($db, array $capture): array {
    $submission = Runtime::$submission;
    if (!$submission || !hash_equals($submission['fingerprint'], $capture['fingerprint'])) {
        return ['purpose_version' => 0, 'purpose_hash' => '', 'purpose_record_hash' => '', 'purpose_json' => ''];
    }
    $input = $submission['sidecar'];
    $record = ['version' => 1, 'analytics' => ['first' => null,'last' => null], 'advertising' => ['first' => null,'last' => null]];
    if ($capture['subject_key'] !== '') {
        $state = rows($db, $db->prepare("SELECT * FROM {$db->prefix}bsre_consent_state WHERE subject_key=%s FOR UPDATE", $capture['subject_key']));
        $history = rows($db, $db->prepare("SELECT * FROM {$db->prefix}bsre_consent_history WHERE subject_key=%s ORDER BY revision LIMIT 1001 FOR UPDATE", $capture['subject_key']));
        $current = count($state) === 1 ? $state[0] : [];
        if ((int) $capture['known'] === 1) {
            $original = array_values(array_filter($history, fn($row) => (int) $row['revision'] === (int) $capture['original_revision']
                && ($row['receipt'] ?? '') === $capture['decision_version']));
            if (!$current || count($original) !== 1) throw new \RuntimeException('PURPOSE_EVIDENCE_RETIRED');
        }
        foreach (['analytics','advertising'] as $purpose) {
            $flag = $purpose === 'advertising' ? 'ad_measurement' : 'analytics';
            if ((int) $capture['known'] !== 1 || (int) $capture['eligible'] !== 1 || (int) $capture[$flag] !== 1) continue;
            foreach (['first','last'] as $slot) $record[$purpose][$slot] = verified_touch($input[$purpose][$slot], $purpose, $current, $history, time());
        }
    }
    $hash = hash('sha256', canonical($input));
    $json = canonical($record);
    return ['purpose_version' => 1, 'purpose_hash' => $hash,
        'purpose_record_hash' => hash('sha256', $capture['fingerprint'] . "\n" . $hash . "\n" . $json), 'purpose_json' => $json];
}
function assert_record(array $row): void {
    if ((int) ($row['purpose_version'] ?? 0) === 0) return;
    if ((int) $row['purpose_version'] !== 1 || !is_string($row['purpose_json'] ?? null)
        || strlen($row['purpose_json']) > 48000 || !is_string($row['purpose_hash'] ?? null)
        || !preg_match('/^[a-f0-9]{64}$/D', $row['purpose_hash'])
        || !hash_equals(hash('sha256', $row['fingerprint'] . "\n" . $row['purpose_hash'] . "\n" . $row['purpose_json']), $row['purpose_record_hash'] ?? '')) {
        throw new \RuntimeException('PURPOSE_RECORD_CONFLICT');
    }
}
function receive(\WP_REST_Request $request): \WP_REST_Response {
    if (!defined('BSRE_PURPOSE_ATTRIBUTION_ENABLED') || BSRE_PURPOSE_ATTRIBUTION_ENABLED !== true) return Intake\reply(503, 'NOT_CONFIGURED');
    if (!Intake\same_origin_request($request)) return Intake\reply(403, 'CSRF_FAILED');
    if (!preg_match('~^application/json(?:\s*;\s*charset=utf-8)?$~iD', (string) $request->get_header('content-type'))) return Intake\reply(415, 'UNSUPPORTED_MEDIA_TYPE');
    $session = $_COOKIE[Intake\COOKIE] ?? '';
    if (!is_string($session) || !Intake\valid_csrf((string) $request->get_header('x-bsre-csrf'), $session, wp_salt('auth'), time())) return Intake\reply(403, 'CSRF_FAILED');
    if (strlen($request->get_body()) > 64000) return Intake\reply(413, 'PAYLOAD_TOO_LARGE');
    try {
        $value = Intake\consent_choice_object($request->get_body());
        if (!exact_object($value, ['version','wire_body','attribution']) || $value->version !== 1
            || !is_string($value->wire_body) || strlen($value->wire_body) > 18000) invalid();
        $sidecar = normalize_sidecar($value->attribution, time());
        // Duplicate object keys in the preserved wire are rejected as well.
        Intake\consent_choice_object($value->wire_body);
    } catch (\Throwable $error) { return Intake\reply(400, 'VALIDATION_FAILED'); }
    $previous = Runtime::$submission;
    Runtime::$submission = ['fingerprint' => hash('sha256', $value->wire_body), 'sidecar' => $sidecar];
    $inner = clone $request;
    $inner->set_body($value->wire_body);
    try { return receive_wire($inner); }
    finally { Runtime::$submission = $previous; }
}
function legacy_guard($result, $server, \WP_REST_Request $request) {
    if ($result !== null || $request->get_route() !== '/bsre/v1/lead'
        || !defined('BSRE_PURPOSE_ATTRIBUTION_ENABLED') || BSRE_PURPOSE_ATTRIBUTION_ENABLED !== true) return $result;
    // Invalid legacy traffic remains the original handler's responsibility.
    // No database lookup or duplicate-mode disclosure happens before its guards.
    $session = $_COOKIE[Intake\COOKIE] ?? '';
    if (strlen($request->get_body()) > 18000 || !Intake\same_origin_request($request)
        || !preg_match('~^application/json(?:\s*;\s*charset=utf-8)?$~iD', (string) $request->get_header('content-type'))
        || !is_string($session) || !Intake\valid_csrf((string) $request->get_header('x-bsre-csrf'), $session, wp_salt('auth'), time())) return $result;
    if (Intake\limited('purpose-legacy-lookup:' . $session, 60, 20)) return Intake\reply(429, 'RATE_LIMITED', true);
    try {
        $body = Intake\consent_choice_object($request->get_body());
        if (!is_string($body->request_id ?? null) || !preg_match(Intake\UUID_V4, $body->request_id)) return $result;
        global $wpdb;
        $db = Runtime::$store ? Runtime::$store->database() : $wpdb;
        $columns = rows($db, $db->prepare("SHOW COLUMNS FROM {$db->prefix}bsre_consent_captures WHERE Field=%s", 'purpose_version'));
        if (!$columns) return $result; // A legacy-only schema cannot contain v2 records.
        $found = rows($db, $db->prepare("SELECT purpose_version FROM {$db->prefix}bsre_consent_captures WHERE request_id=%s", strtolower($body->request_id)));
        if ($found && (int) $found[0]['purpose_version'] === 1) return Intake\reply(409, 'REQUEST_ID_CONFLICT');
    } catch (\Throwable $error) { return Intake\reply(503, 'PURPOSE_STORAGE_UNAVAILABLE', true); }
    return $result;
}
function register_routes(): void {
    register_rest_route('bsre/v1', '/purpose-lead', ['methods' => 'POST', 'permission_callback' => '__return_true', 'callback' => __NAMESPACE__ . '\\receive']);
}

/** Owner-only private read. Current permission rechecks never upgrade history. */
function private_history($db, string $request, int $now): array {
    if (!current_user_can('manage_options')) throw new \RuntimeException('OWNER_REQUIRED');
    $empty = ['status' => 'UNKNOWN', 'analytics' => ['first' => null,'last' => null], 'advertising' => ['first' => null,'last' => null]];
    if (!preg_match(Intake\UUID_V4, $request)) return $empty;
    if ($db->query('START TRANSACTION') === false) throw new \RuntimeException('PURPOSE_STORAGE_UNAVAILABLE');
    try {
        $captures = rows($db, $db->prepare("SELECT * FROM {$db->prefix}bsre_consent_captures WHERE request_id=%s FOR UPDATE", strtolower($request)));
        if (count($captures) !== 1) {
            if ($db->query('COMMIT') === false) throw new \RuntimeException('PURPOSE_STORAGE_UNAVAILABLE');
            return $empty;
        }
        $capture = $captures[0];
        assert_record($capture);
        if ((int) $capture['purpose_version'] !== 1 || $capture['state'] !== 'ACCEPTED'
            || (int) $capture['uncertain'] !== 0 || (int) $capture['delivery_pending'] !== 0
            || (int) $capture['known'] !== 1 || (int) $capture['eligible'] !== 1
            || !Intake\consent_valid_receipt_id($capture['lead_id'], 'BSRE-')
            || !Intake\consent_valid_receipt_id($capture['event_id'], 'evt_')) {
            if ($db->query('COMMIT') === false) throw new \RuntimeException('PURPOSE_STORAGE_UNAVAILABLE');
            return $empty;
        }
        $state = rows($db, $db->prepare("SELECT * FROM {$db->prefix}bsre_consent_state WHERE subject_key=%s FOR UPDATE", $capture['subject_key']));
        $history = rows($db, $db->prepare("SELECT * FROM {$db->prefix}bsre_consent_history WHERE subject_key=%s ORDER BY revision LIMIT 1001 FOR UPDATE", $capture['subject_key']));
        $stored = json_decode($capture['purpose_json'], true, 12, JSON_THROW_ON_ERROR);
        $result = $empty;
        $result['status'] = 'PRIVATE_REVIEW_ONLY';
        foreach (['analytics','advertising'] as $purpose) foreach (['first','last'] as $slot) {
            $touch = $stored[$purpose][$slot] ?? null;
            if ($touch !== null) {
                unset($touch['original_revision'], $touch['expires_at']);
                $touch['parameters'] = (object) $touch['parameters'];
                $result[$purpose][$slot] = verified_touch($touch, $purpose, $state[0] ?? [], $history, $now);
            }
        }
        if ($db->query('COMMIT') === false) throw new \RuntimeException('PURPOSE_STORAGE_UNAVAILABLE');
        return $result;
    } catch (\Throwable $error) {
        $db->query('ROLLBACK');
        throw $error;
    }
}
