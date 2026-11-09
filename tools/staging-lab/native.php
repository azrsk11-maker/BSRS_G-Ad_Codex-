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
// The next isolated phase creates its own enquiry pages in this synthetic database.
foreach ([$rent, $hub, $public] as $fixture_id) {
    check_lab('removed_search_fixture_' . $fixture_id, wp_delete_post($fixture_id, true) instanceof WP_Post);
}
check_lab('search_fixture_cleanup', get_page_by_path('enquire') === null &&
    $before === (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts}"));
check_lab('cron_disabled', DISABLE_WP_CRON === true);
check_lab('http_policy_blocks_external', is_wp_error(wp_remote_get('https://example.invalid', ['timeout' => 1])));
echo json_encode(['phase' => 'native_wordpress', 'status' => 'PASS', 'wordpress' => $wp_version, 'php' => PHP_VERSION, 'database' => $wpdb->get_var('SELECT VERSION()'), 'checks' => $checks, 'synthetic_database_only' => true, 'production_acceptance' => false], JSON_UNESCAPED_SLASHES) . "\n";
