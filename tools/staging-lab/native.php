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
check_lab('cron_disabled', DISABLE_WP_CRON === true);
check_lab('http_policy_blocks_external', is_wp_error(wp_remote_get('https://example.invalid', ['timeout' => 1])));
echo json_encode(['phase' => 'native_wordpress', 'status' => 'PASS', 'wordpress' => $wp_version, 'php' => PHP_VERSION, 'database' => $wpdb->get_var('SELECT VERSION()'), 'checks' => $checks, 'synthetic_database_only' => true, 'production_acceptance' => false], JSON_UNESCAPED_SLASHES) . "\n";
