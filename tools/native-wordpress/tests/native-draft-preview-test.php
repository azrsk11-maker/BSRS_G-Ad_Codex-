<?php
// Isolated WordPress read doubles. Never load wp-load.php or contact production.
define('ABSPATH', __DIR__ . '/');
define('OBJECT', 'OBJECT');
$admin = true; $origin = 'https://blackswanrealestate.ae'; $posts = []; $writes = 0; $checks = 0;
function current_user_can($cap) { global $admin; return $admin && $cap === 'manage_options'; }
function wp_verify_nonce($nonce, $action) { return $nonce === 'valid-test-nonce' && $action === 'bsre_native_page_preview'; }
function home_url($unused) { global $origin; return $origin . '/'; }
function get_posts($args) {
    global $posts; $result = [];
    foreach ($posts as $id => $post) if (($post['meta'][$args['meta_key']] ?? null) === $args['meta_value']) $result[] = $id;
    return array_slice($result, 0, $args['numberposts']);
}
function get_post_meta($id, $key, $single) { global $posts; return $posts[$id]['meta'][$key] ?? ''; }
function get_page_uri($id) { global $posts; return $posts[$id]['path']; }
function get_page_by_path($path, $format, $type) {
    global $posts;
    foreach ($posts as $id => $post) if ($post['path'] === $path) return (object) ['ID' => $id];
    return null;
}
function wp_insert_post($unused) { global $writes; $writes++; throw new RuntimeException('Unexpected write'); }
function wp_update_post($unused) { global $writes; $writes++; throw new RuntimeException('Unexpected write'); }
function wp_delete_post($unused) { global $writes; $writes++; throw new RuntimeException('Unexpected delete'); }
function check($condition, $message) { global $checks; if (!$condition) throw new RuntimeException($message); $checks++; }
function rejects($callback, $text) {
    try { $callback(); } catch (RuntimeException $error) {
        check(strpos($error->getMessage(), $text) !== false, 'Wrong rejection: ' . $error->getMessage()); return;
    }
    throw new RuntimeException('Expected rejection: ' . $text);
}
require dirname(__DIR__) . '/native-draft-preview.php';
$manifest = ['schema' => 'bsre-native-page-plan-v1', 'mode' => 'PLAN_ONLY', 'page_count' => 360,
    'site_origin_expected' => 'https://blackswanrealestate.ae',
    'native_policy' => ['apply_supported' => false, 'publication_allowed' => false, 'post_status' => 'draft'], 'pages' => []];
for ($i = 1; $i <= 360; $i++) {
    $key = sprintf('BSRE-C%04d', $i);
    $manifest['pages'][] = ['campaign_key' => $key, 'landing_page_id' => sprintf('BSRE-LP%04d', $i),
        'proposed_path' => '/lp/' . strtolower($key) . '/', 'path_status' => 'PROPOSED_NOT_VERIFIED',
        'content_state' => 'BLOCKED_SOURCE_REQUIRED', 'actual_url' => null, 'cms_page_id' => null];
}
$preview = function ($value = null, $nonce = 'valid-test-nonce', $mode = 'dry-run') use (&$manifest) {
    return \BSRE\NativePlanning\preview($value ?? $manifest, 'BSRE-C0001', $nonce, $mode);
};
rejects(fn() => $preview(), 'disabled');
define('BSRE_NATIVE_PLANNER_PREVIEW_ENABLED', true);
$admin = false; rejects(fn() => $preview(), 'authorized administrator'); $admin = true;
rejects(fn() => $preview(null, 'bad-nonce'), 'authorized administrator');
rejects(fn() => $preview(null, 'valid-test-nonce', 'apply'), 'Write mode');
$origin = 'https://business-setup.invalid'; rejects(fn() => $preview(), 'origin'); $origin = 'https://blackswanrealestate.ae';
$result = $preview();
check(in_array('NATIVE_PARENT_ROUTE_UNVERIFIED', $result['blocked_reasons'], true), 'Missing parent was not blocked');
$posts = [10 => ['path' => 'lp', 'meta' => []]];
$result = $preview();
check($result['draft_request']['post_status'] === 'draft' && $result['draft_request']['post_content'] === '', 'Unexpected page content/status');
check($result['draft_request']['post_parent'] === 10 && $result['actual_url'] === null, 'Parent/URL inference failed');
$bad = $manifest; $bad['pages'][1]['landing_page_id'] = $bad['pages'][0]['landing_page_id'];
rejects(fn() => $preview($bad), 'duplicated');
$bad = $manifest; $bad['pages'][0]['proposed_path'] = '/lp/../admin/';
foreach (['google_campaign_id' => '12345678901', 'page_version' => 1] as $field => $value) {
    $bound = $manifest; $bound['pages'][1][$field] = $value;
    rejects(fn() => $preview($bound), 'already deployed');
}
rejects(fn() => $preview($bad), 'Invalid');
$bad = $manifest; $bad['native_policy']['post_status'] = 'publish';
rejects(fn() => $preview($bad), 'draft-only');
$posts[11] = ['path' => 'lp/bsre-c0001', 'meta' => []];
rejects(fn() => $preview(), 'already belongs');
$posts[11]['meta'] = ['_bsre_campaign_key' => 'BSRE-C0001', '_bsre_landing_page_id' => 'BSRE-LP0001'];
check($preview()['status'] === 'EXISTING_PRESERVED', 'Existing matching page was not preserved');
$posts[11]['path'] = 'another-route'; rejects(fn() => $preview(), 'ownership or route');
$posts[11]['path'] = 'lp/bsre-c0001';
$posts[12] = $posts[11]; rejects(fn() => $preview(), 'Duplicate CMS identity'); unset($posts[12]);
$posts[11]['meta']['_bsre_campaign_key'] = 'BSRE-C0002'; rejects(fn() => $preview(), 'ownership or route');
check($writes === 0, 'A WordPress write was attempted');
echo json_encode(['status' => 'PASS', 'checks' => $checks, 'wordpress_writes' => $writes]) . PHP_EOL;
