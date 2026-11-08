<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

add_action('admin_menu', function (): void {
    add_management_page('Black Swan Real Estate Enquiries', 'BSRE Enquiries', 'manage_options', 'bsre-enquiries', __NAMESPACE__ . '\\admin_page');
});
add_action('admin_post_bsre_create_drafts', __NAMESPACE__ . '\\admin_create_drafts');

function admin_create_drafts(): void {
    if (!current_user_can('manage_options')) wp_die('You do not have permission to manage these drafts.', '', ['response' => 403]);
    if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') wp_die('Use the draft creation form.', '', ['response' => 405]);
    check_admin_referer('bsre_create_drafts');
    try {
        $result = ensure_drafts(false);
        $notice = ['type' => 'success', 'message' => $result['status'] === 'existing' ? 'The existing five service drafts were preserved. No content or publication status changed.' : 'Five service drafts and one routing parent draft were created. All remain unpublished; routing was not enabled.'];
    } catch (\RuntimeException $e) {
        $notice = ['type' => 'error', 'message' => $e->getMessage()];
    }
    set_transient('bsre_admin_notice_' . get_current_user_id(), $notice, 60);
    wp_safe_redirect(admin_url('tools.php?page=bsre-enquiries'));
    exit;
}

function admin_page(): void {
    if (!current_user_can('manage_options')) wp_die('You do not have permission to view this page.', '', ['response' => 403]);
    $receiver = defined('BSRE_LEAD_RECEIVER_URL') ? BSRE_LEAD_RECEIVER_URL : '';
    $secret = defined('BSRE_LEAD_HMAC_SECRET') ? BSRE_LEAD_HMAC_SECRET : '';
    $checks = [
        'HTTPS Black Swan Real Estate home' => real_estate_home(home_url('/')) && is_ssl(),
        'Rate-limit schema marker' => get_option('bsre_schema_version') === '1',
        'Protected consent schema version 2' => get_option('bsre_consent_schema_version') === '2',
        'Receiver deployment URL configured' => is_string($receiver) && valid_receiver($receiver),
        'Server signing secret configured' => is_string($secret) && strlen($secret) >= 32,
        'Published site privacy notice configured' => privacy_url() !== '',
        'At least one registered service at its published path' => count(live_paths()) > 0,
        'Routing enable flag' => defined('BSRE_ROUTING_ENABLED') && BSRE_ROUTING_ENABLED === true,
    ];
    echo '<div class="wrap"><h1>Black Swan Real Estate Enquiries</h1>';
    $notice_key = 'bsre_admin_notice_' . get_current_user_id();
    $notice = get_transient($notice_key);
    if (is_array($notice)) {
        delete_transient($notice_key);
        $class = ($notice['type'] ?? '') === 'success' ? 'notice-success' : 'notice-error';
        echo '<div class="notice ' . esc_attr($class) . '"><p>' . esc_html($notice['message'] ?? '') . '</p></div>';
    }
    echo '<p>Create the five Real Estate service drafts: off-plan, resale, rent, sell and let, plus their enquiry routing parent. Business Setup is excluded.</p>';
    echo '<p>This action creates drafts only. Existing registered pages are preserved. Publication, secret configuration, routing enablement and tracking setup are outside this action.</p>';
    echo '<form method="post" action="' . esc_url(admin_url('admin-post.php')) . '"><input type="hidden" name="action" value="bsre_create_drafts">';
    wp_nonce_field('bsre_create_drafts');
    submit_button('Create service drafts');
    echo '</form><h2>Configuration readiness</h2><p>These checks describe local configuration. Live WordPress, delivery, consent and tracking checks still need to pass.</p><table class="widefat striped"><tbody>';
    foreach ($checks as $label => $ok) echo '<tr><th scope="row">' . esc_html($label) . '</th><td>' . ($ok ? 'Configured' : 'Missing / inactive') . '</td></tr>';
    echo '</tbody></table>';
    render_measurement_qa_controls();
    echo '<h2>Service pages</h2><ul>';
    foreach (SERVICES as $slug => $details) {
        $id = registered_service_page_id($slug);
        echo '<li>' . esc_html($details['title']) . ': ';
        if ($id && get_post_meta($id, '_bsre_service', true) === $slug) echo '<a href="' . esc_url(get_edit_post_link($id)) . '">page ' . (int) $id . '</a> — ' . esc_html(get_post_status($id) ?: 'missing');
        else echo 'not registered';
        echo '</li>';
    }
    echo '</ul><p>All managed pages retain noindex/nofollow. The original telephone and WhatsApp links are preserved. Google Ads budgets are managed separately; this plugin does not enforce a daily media spending ceiling.</p></div>';
}
