<?php
define('WP_INSTALLING', true);
require '/opt/wordpress/wp-load.php';
require_once ABSPATH . 'wp-admin/includes/upgrade.php';
// The installer normally sends mail. Kernel isolation remains the actual boundary.
add_filter('pre_wp_mail', '__return_true');
$installation = wp_install('SYNTHETIC BSRE LAB', 'synthetic_owner', 'owner@example.invalid', false, '', 'synthetic-local-fixture-only');
if (is_wp_error($installation)) throw new RuntimeException('Synthetic WordPress installation failed');
wp_set_current_user($installation['user_id']);
require '/opt/reviewed/native-draft-preview.php';
$manifest = json_decode(file_get_contents('/opt/reviewed/native-page-manifest.json'), true, 512, JSON_THROW_ON_ERROR);
$checks = [];
function check_lab(string $name, bool $ok): void {
    global $checks;
    if (!$ok) throw new RuntimeException('Native lab check failed: ' . $name);
    $checks[$name] = true;
}
$nonce = wp_create_nonce('bsre_native_page_preview');
$preview_writes = [];
add_filter('query', function ($sql) use (&$preview_writes) {
    if (!preg_match('/^\s*(SELECT|SHOW|DESCRIBE|EXPLAIN)\b/i', $sql)) $preview_writes[] = $sql;
    return $sql;
});
try { \BSRE\NativePlanning\preview($manifest, 'BSRE-C0001', $nonce); throw new LogicException('Origin guard did not reject synthetic origin'); }
catch (RuntimeException $e) { check_lab('synthetic_origin_rejected', $e->getMessage() === 'Current CMS origin needs explicit reconciliation.'); }
// Test-only read filter exercises the approved-origin branch without contacting it.
add_filter('home_url', fn() => 'https://blackswanrealestate.ae');
$before = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts}");
$plan = \BSRE\NativePlanning\preview($manifest, 'BSRE-C0001', $nonce);
check_lab('real_wp_draft_plan', $plan['status'] === 'BLOCKED_PLAN_ONLY' && $plan['writes_performed'] === 0 && $plan['draft_request']['post_status'] === 'draft');
check_lab('missing_parent_held', in_array('NATIVE_PARENT_ROUTE_UNVERIFIED', $plan['blocked_reasons'], true));
try { \BSRE\NativePlanning\preview($manifest, 'BSRE-C0001', $nonce, 'apply'); throw new LogicException('Write guard failed'); }
catch (RuntimeException $e) { check_lab('apply_denied', $e->getMessage() === 'Write mode is not implemented or authorized.'); }
check_lab('post_count_unchanged', $before === (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts}"));
check_lab('preview_zero_sql_writes', $preview_writes === []);
$hub = wp_insert_post(['import_id' => 26750, 'post_type' => 'page', 'post_status' => 'publish',
    'post_name' => 'enquire', 'post_title' => 'Synthetic discovery fixture hub'], true);
$rent = wp_insert_post(['import_id' => 26753, 'post_type' => 'page', 'post_status' => 'publish',
    'post_parent' => $hub, 'post_name' => 'rent', 'post_title' => 'Synthetic discovery fixture rental'], true);
$public = wp_insert_post(['post_type' => 'page', 'post_status' => 'publish',
    'post_name' => 'guide', 'post_title' => 'Synthetic discovery fixture public guide'], true);
check_lab('synthetic_entry_identities', $hub === 26750 && $rent === 26753 && is_int($public) && $public > 0);
$search_args = ['s' => 'Synthetic discovery fixture', 'post_type' => 'page', 'fields' => 'ids'];
$main_search = static function () use ($search_args): array {
    $previous = $GLOBALS['wp_the_query'];
    $GLOBALS['wp_the_query'] = $query = new WP_Query();
    try { return $query->query($search_args); }
    finally { $GLOBALS['wp_the_query'] = $previous; }
};
$rest_search = static function (): array {
    $request = new WP_REST_Request('GET', '/wp/v2/search');
    $request->set_query_params(['search' => 'Synthetic discovery fixture', 'subtype' => 'page']);
    $response = rest_do_request($request);
    check_lab('rest_search_http_success', $response->get_status() === 200);
    return array_column($response->get_data(), 'id');
};
wp_set_current_user(0);
check_lab('before_main_search_has_all_three', count(array_intersect([$hub, $rent, $public], $main_search())) === 3);
check_lab('before_rest_search_has_all_three', count(array_intersect([$hub, $rent, $public], $rest_search())) === 3);
define('BSRE_PAID_ENTRY_SEARCH_EXCLUSION_ENABLED', true);
require '/opt/reviewed/paid-entry-search.php';
check_lab('main_search_retains_only_public_control', array_values(array_intersect([$hub, $rent, $public], $main_search())) === [$public]);
check_lab('rest_search_retains_only_public_control', array_values(array_intersect([$hub, $rent, $public], $rest_search())) === [$public]);
$direct = rest_do_request(new WP_REST_Request('GET', '/wp/v2/pages/26753'));
check_lab('direct_rest_page_remains_public', $direct->get_status() === 200 && ($direct->get_data()['id'] ?? null) === $rent);
wp_set_current_user($installation['user_id']);
check_lab('editor_rest_search_preserved', count(array_intersect([$hub, $rent, $public], $rest_search())) === 3);
try {
    // Render the packaged candidate through the actual plugin with native page ownership.
    $original_options = [];
    foreach (['permalink_structure' => '/%postname%/', 'bsre_parent_draft' => $hub,
        'bsre_draft_pages' => ['rent' => $rent], 'bsre_schema_version' => '1'] as $option => $value) {
        $original_options[$option] = get_option($option, false);
        update_option($option, $value);
    }
    remove_all_filters('home_url'); // Undo the earlier lab-only fixed-origin read stub.
    $lab_origin = static fn() => 'https://blackswanrealestate.ae';
    $lab_plugin_url = static fn($url) => 'https://blackswanrealestate.ae' . parse_url($url, PHP_URL_PATH);
    add_filter('pre_option_home', $lab_origin);
    add_filter('pre_option_siteurl', $lab_origin);
    add_filter('plugins_url', $lab_plugin_url);
    $lab_rest_url = static fn($url, $route) => 'https://blackswanrealestate.ae/wp-json/' . ltrim($route, '/');
    add_filter('rest_url', $lab_rest_url, 10, 2);
    update_post_meta($hub, '_bsre_parent', '1');
    update_post_meta($rent, '_bsre_service', 'rent');
    $wp_rewrite->init(); // Refresh the permalink structure cached at WordPress bootstrap.
    require '/opt/wordpress/wp-content/plugins/bsre-enquiries/bsre-enquiries.php';
    $_SERVER['REQUEST_METHOD'] = 'GET';
    $_SERVER['REQUEST_URI'] = '/enquire/rent/';
    $_SERVER['HTTPS'] = 'on';
    wp_set_current_user(0);
    $GLOBALS['wp_query'] = new WP_Query(['page_id' => $rent]);
    $scope = \BSRE\Enquiries\owned_parent_scope();
    check_lab('rental_copy_native_scope', is_array($scope));
    check_lab('rental_copy_native_registered_page', \BSRE\Enquiries\registered_service_page_id('rent') === $rent);
    check_lab('rental_copy_native_query', is_page() && get_queried_object_id() === $rent);
    check_lab('rental_copy_native_permalink', get_permalink($rent) === 'https://blackswanrealestate.ae/enquire/rent/');
    check_lab('rental_copy_native_live_binding', \BSRE\Enquiries\owned_parent_binding($scope)['mode'] === 'live');
    check_lab('rental_copy_native_routing_defaults_held', \BSRE\Enquiries\owned_parent_document($scope)['binding']['mode'] === 'held');
    define('BSRE_ROUTING_ENABLED', true);
    define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
    define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-rental-lab-', 2));
    define('BSRE_PRIVACY_NOTICE_PAGE_ID', $public);
    check_lab('rental_copy_native_synthetic_receiver_ready', \BSRE\Enquiries\ready());
    check_lab('rental_copy_native_document_live', \BSRE\Enquiries\owned_parent_document($scope)['binding']['mode'] === 'live');
    ob_start();
    require '/opt/wordpress/wp-content/plugins/bsre-enquiries/templates/page.php';
    $rental_html = ob_get_clean();
    check_lab('rental_copy_native_visible_wording', substr_count($rental_html, 'Choose when you need to move so we can review your rental requirements against your timeline.') === 1
        && !str_contains($rental_html, 'priority for this campaign'));
    check_lab('rental_copy_native_noscript', substr_count($rental_html, '<noscript><p class="noscript">To send an online enquiry, JavaScript is required. You can also use the contact options on this page.</p></noscript>') === 1);
    check_lab('rental_copy_native_form_and_canonical', str_contains($rental_html, 'data-role="tenant"')
        && str_contains($rental_html, 'rel="canonical" href="https://blackswanrealestate.ae/enquire/rent/"'));
    remove_filter('pre_option_home', $lab_origin);
    remove_filter('pre_option_siteurl', $lab_origin);
    remove_filter('plugins_url', $lab_plugin_url);
    remove_filter('rest_url', $lab_rest_url);
    foreach ($original_options as $option => $value) {
        if ($value === false) delete_option($option);
        else update_option($option, $value);
    }
} catch (Throwable $error) {
    fwrite(STDERR, 'Synthetic rental render failed: ' . $error->getMessage() . ' at line ' . $error->getLine() . "\n");
    exit(1);
}
// The next isolated phase creates its own enquiry pages in this synthetic database.
foreach ([$rent, $hub, $public] as $fixture_id) {
    check_lab('removed_search_fixture_' . $fixture_id, wp_delete_post($fixture_id, true) instanceof WP_Post);
}
check_lab('search_fixture_cleanup', get_page_by_path('enquire') === null &&
    $before === (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts}"));
check_lab('cron_disabled', DISABLE_WP_CRON === true);
check_lab('http_policy_blocks_external', is_wp_error(wp_remote_get('https://example.invalid', ['timeout' => 1])));
echo json_encode(['phase' => 'native_wordpress', 'status' => 'PASS', 'wordpress' => $wp_version, 'php' => PHP_VERSION, 'database' => $wpdb->get_var('SELECT VERSION()'), 'checks' => $checks, 'synthetic_database_only' => true, 'production_acceptance' => false], JSON_UNESCAPED_SLASHES) . "\n";
