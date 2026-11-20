<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

const MEASUREMENT_SETTINGS_OPTION = 'bsre_measurement_settings_v1';
function measurement_settings(): array {
    $off = ['schema' => 1, 'config_version' => 'disabled', 'enabled' => false, 'analytics_enabled' => false, 'advertising_enabled' => false, 'ads_send_to' => ''];
    $value = get_option(MEASUREMENT_SETTINGS_OPTION, null);
    if (!is_array($value)) return $off;
    $keys = array_keys($value); sort($keys);
    if ($keys !== ['ads_send_to','advertising_enabled','analytics_enabled','config_version','enabled','schema'] || $value['schema'] !== 1 || !is_string($value['config_version']) || !preg_match('/^gm1-[a-f0-9]{32}$/D', $value['config_version'])) return $off;
    foreach (['enabled','analytics_enabled','advertising_enabled'] as $flag) if (!is_bool($value[$flag])) return $off;
    if (!is_string($value['ads_send_to']) || ($value['ads_send_to'] !== '' && !preg_match('/^AW-18394393537\/[A-Za-z0-9_-]{1,128}$/D', $value['ads_send_to']))) return $off;
    if ($value['advertising_enabled'] && $value['ads_send_to'] === '') return $off;
    return $value;
}
function measurement_public_configuration(): array {
    $settings = measurement_settings();
    return ['enabled' => $settings['enabled'], 'analytics_enabled' => $settings['enabled'] && $settings['analytics_enabled'], 'advertising_enabled' => $settings['enabled'] && $settings['advertising_enabled'] && $settings['ads_send_to'] !== '', 'runtime_endpoint' => rest_url('bsre/v1/measurement/runtime'), 'status_endpoint' => rest_url('bsre/v1/measurement/status'), 'config_version' => $settings['config_version']];
}
function measurement_settings_choice(array $posted): array {
    $flags = [];
    foreach (['enabled','analytics_enabled','advertising_enabled'] as $flag) {
        if (isset($posted[$flag]) && $posted[$flag] !== '1') throw new \InvalidArgumentException('Invalid measurement control.');
        $flags[$flag] = isset($posted[$flag]);
    }
    $send_to = $posted['ads_send_to'] ?? '';
    if (!is_string($send_to) || ($send_to !== '' && !preg_match('/^AW-18394393537\/[A-Za-z0-9_-]{1,128}$/D', $send_to))) throw new \InvalidArgumentException('Use the exact reviewed Ads destination, or leave it blank while advertising is off.');
    if ($flags['advertising_enabled'] && $send_to === '') throw new \InvalidArgumentException('Advertising requires the exact reviewed Ads destination.');
    return ['schema' => 1, 'config_version' => 'gm1-' . bin2hex(random_bytes(16))] + $flags + ['ads_send_to' => $send_to];
}
function measurement_settings_admin_guard(): void {
    if (!current_user_can('manage_options')) throw new \RuntimeException('CAPABILITY_REQUIRED');
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') throw new \RuntimeException('POST_REQUIRED');
    check_admin_referer('bsre_measurement_settings');
    if (!is_ssl() || !real_estate_home(home_url('/'))) throw new \RuntimeException('HTTPS_REAL_ESTATE_REQUIRED');
}
function admin_measurement_settings(): void {
    try {
        measurement_settings_admin_guard();
        $value = measurement_settings_choice(wp_unslash($_POST));
        update_option(MEASUREMENT_SETTINGS_OPTION, $value, false);
        if (get_option(MEASUREMENT_SETTINGS_OPTION) !== $value) throw new \RuntimeException('SETTINGS_NOT_SAVED');
    } catch (\Throwable $e) { wp_die('Measurement settings were not saved. Check access, the form nonce, HTTPS site and exact destination.', 'Measurement settings unavailable', ['response' => 400]); return; }
    wp_safe_redirect(admin_url('tools.php?page=bsre-enquiries'));
    exit;
}
add_action('admin_post_bsre_measurement_settings', __NAMESPACE__ . '\\admin_measurement_settings');
function render_measurement_settings_controls(): void {
    if (!current_user_can('manage_options')) return;
    $value = measurement_settings();
    echo '<h2>Enquiry measurement release controls</h2><p>Default: off. Enable only after the isolated container, destinations and consent/QA checks pass. Turning the master control off blocks new runtime loads and the next runtime lease check stops active frames. These controls do not change campaign status, bidding or budgets.</p><p>Configuration: ' . esc_html($value['config_version']) . '; GTM-NW8WXKRF; analytics G-W01P9W3NWE. The advertising destination requires its actual reviewed action label.</p><form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="bsre_measurement_settings">';
    wp_nonce_field('bsre_measurement_settings');
    foreach (['enabled' => 'Master measurement enabled','analytics_enabled' => 'Analytics destination enabled','advertising_enabled' => 'Advertising destination enabled'] as $key => $label) echo '<p><label><input type="checkbox" name="' . esc_attr($key) . '" value="1"' . ($value[$key] ? ' checked' : '') . '> ' . esc_html($label) . '</label></p>';
    echo '<p><label>Exact Ads destination <input type="text" name="ads_send_to" maxlength="160" value="' . esc_attr($value['ads_send_to']) . '" autocomplete="off"></label></p><button type="submit" class="button">Save measurement controls</button></form>';
}
