<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

const MEASUREMENT_QA_COOKIE = '__Host-bsre_qa';
const MEASUREMENT_QA_SECONDS = 7200;

/** Separate, short-lived QA exclusion. No lead signing key or personal data. */
function measurement_qa_token(string $salt, int $issued, ?string $nonce = null): string {
    if (strlen($salt) < 32 || $issued < 1 || $issued > PHP_INT_MAX - MEASUREMENT_QA_SECONDS) throw new \RuntimeException('QA exclusion unavailable.');
    $nonce = $nonce ?? bin2hex(random_bytes(16));
    if (!preg_match('/^[a-f0-9]{32}$/D', $nonce)) throw new \RuntimeException('QA exclusion unavailable.');
    $data = 'q1|' . $issued . '|' . ($issued + MEASUREMENT_QA_SECONDS) . '|' . $nonce;
    return $data . '|' . hash_hmac('sha256', 'bsre-measurement-qa-v1|' . $data, $salt);
}

function valid_measurement_qa_token($value, string $salt, int $now): bool {
    if (!is_string($value) || strlen($value) > 160 || strlen($salt) < 32) return false;
    if (!preg_match('/^q1\|([1-9][0-9]{0,10})\|([1-9][0-9]{0,10})\|([a-f0-9]{32})\|([a-f0-9]{64})$/D', $value, $parts)) return false;
    $issued = (int) $parts[1];
    $expires = (int) $parts[2];
    if ($issued > $now || $expires <= $now || $expires - $issued !== MEASUREMENT_QA_SECONDS) return false;
    $data = 'q1|' . $parts[1] . '|' . $parts[2] . '|' . $parts[3];
    return hash_equals(hash_hmac('sha256', 'bsre-measurement-qa-v1|' . $data, $salt), $parts[4]);
}

/** Denial metadata only: this never grants consent or changes accepted leads. */
function measurement_eligible(?string $raw = null): bool {
    if (!is_ssl() || !real_estate_home(home_url('/'))) return false;
    if (!function_exists('is_user_logged_in') || !function_exists('wp_validate_auth_cookie') || !defined('LOGGED_IN_COOKIE')) return false;
    if (is_user_logged_in()) return false;
    // REST cookie authentication may clear current_user without a WP REST nonce.
    // Validate the independent core cookie, not just the current_user value.
    if (array_key_exists(LOGGED_IN_COOKIE, $_COOKIE)) {
        $cookie = $_COOKIE[LOGGED_IN_COOKIE];
        if (!is_string($cookie) || $cookie === '' || strlen($cookie) > 4096) return false;
        try {
            if (wp_validate_auth_cookie(wp_unslash($cookie), 'logged_in')) return false;
        } catch (\Throwable $e) {
            return false;
        }
        // A stale/malformed present WP identity cookie is also excluded, rather
        // than allowing an uncertain admin identity to become measurement-eligible.
        return false;
    }
    // Both a valid marker and a malformed-present marker fail closed. A valid
    // signed marker intentionally survives WP logout until its two-hour expiry.
    if (array_key_exists(MEASUREMENT_QA_COOKIE, $_COOKIE)) return false;
    if ($raw !== null) {
        if (strlen($raw) > 18000) return false;
        try { $payload = json_decode($raw, false, 16, JSON_THROW_ON_ERROR); }
        catch (\Throwable $e) { return false; }
        if (!is_object($payload) || !isset($payload->name) || !is_string($payload->name)) return false;
        // Supplemental deny only, never trusted QA authorization. No name or
        // other submitted field is added to the measurement response.
        if (preg_match('/^\s*TEST(?:$|[\s_-])/iu', $payload->name)) return false;
    }
    return true;
}

function admin_measurement_qa(): void {
    if (!current_user_can('manage_options')) wp_die('You do not have permission to manage QA exclusion.', '', ['response' => 403]);
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') wp_die('Use the QA exclusion form.', '', ['response' => 405]);
    check_admin_referer('bsre_measurement_qa');
    if (!is_ssl() || !real_estate_home(home_url('/'))) wp_die('QA exclusion requires the HTTPS Real Estate site.', '', ['response' => 403]);
    $mode = $_POST['qa_mode'] ?? '';
    if (!is_string($mode) || !in_array($mode, ['enable', 'clear'], true)) wp_die('Choose a valid QA exclusion action.', '', ['response' => 400]);
    if (headers_sent()) wp_die('QA exclusion could not be updated.', '', ['response' => 503]);
    try {
        $now = time();
        $value = $mode === 'enable' ? measurement_qa_token(wp_salt('auth'), $now) : '';
        $expires = $mode === 'enable' ? $now + MEASUREMENT_QA_SECONDS : $now - 3600;
        nocache_headers();
        $saved = setcookie(MEASUREMENT_QA_COOKIE, $value, ['expires' => $expires, 'path' => '/', 'secure' => true, 'httponly' => true, 'samesite' => 'Strict']);
        if (!$saved) throw new \RuntimeException('QA exclusion could not be updated.');
    } catch (\Throwable $e) {
        wp_die('QA exclusion could not be updated.', '', ['response' => 503]);
    }
    if ($mode === 'enable') $_COOKIE[MEASUREMENT_QA_COOKIE] = $value;
    else unset($_COOKIE[MEASUREMENT_QA_COOKIE]);
    wp_safe_redirect(admin_url('tools.php?page=bsre-enquiries'));
    exit;
}
add_action('admin_post_bsre_measurement_qa', __NAMESPACE__ . '\\admin_measurement_qa');

function render_measurement_qa_controls(): void {
    if (!current_user_can('manage_options')) return;
    $present = array_key_exists(MEASUREMENT_QA_COOKIE, $_COOKIE);
    $valid = false;
    if ($present) {
        try { $valid = valid_measurement_qa_token($_COOKIE[MEASUREMENT_QA_COOKIE], wp_salt('auth'), time()); }
        catch (\Throwable $e) { $valid = false; }
    }
    echo '<h2>Measurement QA exclusion</h2><p>';
    echo $valid ? 'QA exclusion is active for this browser.' : ($present ? 'A QA marker is present but invalid or expired. Measurement remains excluded until it is cleared.' : 'No QA exclusion marker is active for this browser.');
    echo '</p><p>Enable exclusion before testing, including before logging out for guest QA. The signed browser marker lasts two hours and survives WordPress logout. It does not change enquiry delivery or grant analytics or advertising consent. An expired marker that remains in a request stays excluded until cleared.</p>';
    foreach (['enable' => 'Enable QA exclusion for two hours', 'clear' => 'Clear QA exclusion'] as $mode => $label) {
        echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="bsre_measurement_qa"><input type="hidden" name="qa_mode" value="' . esc_attr($mode) . '">';
        wp_nonce_field('bsre_measurement_qa');
        submit_button($label, $mode === 'enable' ? 'secondary' : 'delete');
        echo '</form>';
    }
    if (function_exists(__NAMESPACE__ . '\\render_consent_export_controls')) render_consent_export_controls();
    if (function_exists(__NAMESPACE__ . '\\render_measurement_settings_controls')) render_measurement_settings_controls();
}
