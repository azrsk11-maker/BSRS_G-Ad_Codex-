<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

/** Private admin-download contract. Never registered as a REST route. */
const CONSENT_EXPORT_SCHEMA = 'bsre-consent-evidence-v1';
const CONSENT_EXPORT_LIMIT = 100;

function consent_export_requests($input): array {
    if (!is_string($input) || strlen($input) > 4000) throw new \InvalidArgumentException('Enter between 1 and 100 explicit request UUIDs.');
    $parts = preg_split('/[\s,]+/', trim($input), -1, PREG_SPLIT_NO_EMPTY);
    if (!$parts || count($parts) > CONSENT_EXPORT_LIMIT) throw new \InvalidArgumentException('Enter between 1 and 100 explicit request UUIDs.');
    $ids = [];
    foreach ($parts as $id) {
        if (!preg_match(UUID_V4, $id)) throw new \InvalidArgumentException('Only complete request UUIDs are accepted.');
        $id = strtolower($id);
        if (isset($ids[$id])) throw new \InvalidArgumentException('Duplicate request UUIDs are not accepted.');
        $ids[$id] = true;
    }
    return array_keys($ids);
}
function consent_export_iso(int $seconds): string { return $seconds > 0 ? gmdate('Y-m-d\TH:i:s\Z', $seconds) : ''; }
function consent_export_ms(int $milliseconds): string {
    return $milliseconds > 0 ? gmdate('Y-m-d\TH:i:s', intdiv($milliseconds, 1000)) . sprintf('.%03dZ', $milliseconds % 1000) : '';
}
function consent_export_valid_clicks(?array $capture, int $now): bool {
    if (!$capture || ($capture['click_capture_state'] ?? '') !== 'CAPTURED') return false;
    $found = false;
    foreach (['first','last'] as $touch) {
        $gclid = $capture['gclid_' . $touch] ?? null;
        $stamp = $capture['gclid_' . $touch . '_captured_ms'] ?? null;
        if (!is_string($gclid) || (!is_int($stamp) && (!is_string($stamp) || !preg_match('/^[0-9]{1,13}$/D', $stamp)))) return false;
        $stamp = (int) $stamp;
        if ($gclid === '') { if ($stamp !== 0) return false; continue; }
        if (!preg_match('/^[A-Za-z0-9._~-]{1,256}$/D', $gclid) || $stamp < 946684800000 || $stamp > $now * 1000 + 300000) return false;
        $found = true;
    }
    return $found;
}
function consent_export_document(array $requests, ConsentRepository $store): array {
    // Validate even internal callers; no broad/date-range/all-record export.
    $requests = consent_export_requests(implode("\n", $requests));
    $captures = $store->exportRows($requests);
    $now = time(); $rows = [];
    foreach ($requests as $request) {
        $capture = $captures[$request] ?? null;
        $current = $capture['_current'] ?? null;
        $original_known = $capture && (int) ($capture['known'] ?? 0) === 1;
        $permission_uncertain = !$capture || (int) ($capture['uncertain'] ?? 1) !== 0;
        $current_known = $current && (int) ($current['uncertain'] ?? 1) === 0 && (int) ($current['expires_at'] ?? 0) > $now && ($current['notice_version'] ?? '') === CONSENT_NOTICE_VERSION;
        $withdrawn = !$capture || ($capture['_ad_withdrawn'] ?? true) === true;
        $reasons = [];
        if (!$capture) $reasons[] = 'MISSING_ORIGINAL_EVIDENCE';
        $lead_valid = consent_valid_receipt_id($capture['lead_id'] ?? null, 'BSRE-');
        $event_valid = consent_valid_receipt_id($capture['event_id'] ?? null, 'evt_');
        if (($capture['state'] ?? '') !== 'ACCEPTED' || !$lead_valid || !$event_valid) $reasons[] = 'ACCEPTANCE_UNRESOLVED';
        if (!$original_known || $permission_uncertain) $reasons[] = 'ORIGINAL_PERMISSION_UNKNOWN';
        if ((int) ($capture['delivery_pending'] ?? 1) !== 0) $reasons[] = 'DELIVERY_UNRESOLVED';
        if ((int) ($capture['eligible'] ?? 0) !== 1) $reasons[] = 'QA_OR_TEST_OR_UNCLASSIFIED';
        if ((int) ($capture['ad_measurement'] ?? 0) !== 1) $reasons[] = 'ORIGINAL_AD_PERMISSION_DENIED';
        if (($capture['notice_version'] ?? '') !== CONSENT_NOTICE_VERSION) $reasons[] = 'NOTICE_VERSION_UNRECOGNIZED';
        if ((int) ($capture['preference_expires_at'] ?? 0) <= $now) $reasons[] = 'ORIGINAL_PERMISSION_EXPIRED';
        if (!$current_known) $reasons[] = 'CURRENT_PERMISSION_UNKNOWN';
        if (!$current_known || (int) ($current['ad_measurement'] ?? 0) !== 1) $reasons[] = 'CURRENT_AD_PERMISSION_DENIED';
        if ($withdrawn) $reasons[] = 'AD_PERMISSION_WITHDRAWN_OR_HISTORY_UNKNOWN';
        if (!consent_export_valid_clicks($capture, $now)) $reasons[] = 'NO_VALID_ORIGINAL_GCLID';
        $eligible = count($reasons) === 0;
        $rows[] = [
            'request_id' => $request,
            'lead_id' => $lead_valid ? $capture['lead_id'] : '', 'event_id' => $event_valid ? $capture['event_id'] : '',
            'capture_state' => $capture['state'] ?? 'MISSING',
            'original_decision_version' => preg_match('/^[a-f0-9]{32}$/D', $capture['decision_version'] ?? '') ? $capture['decision_version'] : 'none',
            'notice_version' => $capture['notice_version'] ?? CONSENT_NOTICE_VERSION,
            'original_analytics_grant' => $original_known && (int) ($capture['analytics'] ?? 0) === 1,
            'original_ad_measurement_grant' => $original_known && (int) ($capture['ad_measurement'] ?? 0) === 1,
            'original_test_eligible' => (int) ($capture['eligible'] ?? 0) === 1,
            'current_ad_measurement_grant' => $current_known && (int) ($current['ad_measurement'] ?? 0) === 1,
            'ad_withdrawn_since_capture' => $withdrawn,
            'capture_uncertain' => $permission_uncertain,
            'delivery_pending' => (int) ($capture['delivery_pending'] ?? 1) !== 0,
            'original_preference_expires_at_utc' => consent_export_iso((int) ($capture['preference_expires_at'] ?? 0)),
            'current_preference_expires_at_utc' => consent_export_iso((int) ($current['expires_at'] ?? 0)),
            'evidence_checked_at_utc' => consent_export_iso($now),
            'click_capture_state' => $capture['click_capture_state'] ?? 'UNAVAILABLE',
            'gclid_first' => $eligible ? $capture['gclid_first'] : '',
            'gclid_last' => $eligible ? $capture['gclid_last'] : '',
            'gclid_first_captured_at_utc' => $eligible ? consent_export_ms((int) $capture['gclid_first_captured_ms']) : '',
            'gclid_last_captured_at_utc' => $eligible ? consent_export_ms((int) $capture['gclid_last_captured_ms']) : '',
            'click_timestamp_source' => 'browser_landing_capture_not_google_verified',
            'export_eligible' => $eligible, 'blocked_reasons' => $reasons,
        ];
    }
    return ['schema' => CONSENT_EXPORT_SCHEMA, 'exported_at_utc' => consent_export_iso($now), 'notice_version' => CONSENT_NOTICE_VERSION, 'rows' => $rows];
}
function consent_export_admin_guard(): void {
    if (!current_user_can('manage_options')) throw new \RuntimeException('CAPABILITY_REQUIRED');
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') throw new \RuntimeException('POST_REQUIRED');
    check_admin_referer('bsre_consent_export');
    if (!is_ssl() || !real_estate_home(home_url('/'))) throw new \RuntimeException('HTTPS_REAL_ESTATE_REQUIRED');
}
function admin_consent_export(): void {
    try {
        consent_export_admin_guard();
        $requests = consent_export_requests(isset($_POST['request_ids']) ? wp_unslash($_POST['request_ids']) : null);
        $document = consent_export_document($requests, consent_repository());
        if (headers_sent()) throw new \RuntimeException('DOWNLOAD_UNAVAILABLE');
        nocache_headers();
        header('Cache-Control: no-store, private, max-age=0');
        header('Content-Type: application/json; charset=UTF-8');
        header('Content-Disposition: attachment; filename="bsre-private-consent-evidence.json"');
        header('X-Content-Type-Options: nosniff');
        echo wp_json_encode($document, JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        exit;
    } catch (\Throwable $e) {
        // Never echo exception/DB contents, IDs, clicked identifiers or cookies.
        wp_die('The private evidence download was not created. Check your access, explicit request UUIDs and consent storage.', 'Evidence download unavailable', ['response' => 400]);
    }
}
add_action('admin_post_bsre_consent_export', __NAMESPACE__ . '\\admin_consent_export');
function render_consent_export_controls(): void {
    if (!current_user_can('manage_options')) return;
    echo '<h2>Private consent evidence</h2><p>Download a bounded review snapshot for 1–100 explicit request UUIDs. This contains click identifiers only for eligible rows and does not upload conversions. Keep the download private and exclude it from continuation packages. Recheck permission before any later manual upload.</p><form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="bsre_consent_export">';
    wp_nonce_field('bsre_consent_export');
    echo '<label for="bsre-evidence-requests">Request UUIDs, one per line</label><br><textarea id="bsre-evidence-requests" name="request_ids" rows="5" cols="50" maxlength="4000" required autocomplete="off"></textarea><br><button type="submit" class="button">Download private JSON evidence</button></form>';
}
