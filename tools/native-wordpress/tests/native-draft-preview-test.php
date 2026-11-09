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
function get_post_type($id) { global $posts; return $posts[$id]['type'] ?? null; }
function add_filter($hook, $callback) { $GLOBALS['search_hooks'][$hook] = $callback; }
function add_action($hook, $callback) { $GLOBALS['search_hooks'][$hook] = $callback; }
function is_admin() { return $GLOBALS['admin_search'] ?? false; }
class WP_Query {
    public function __construct(public array $vars, private bool $main = true, private bool $search = true) {}
    public function is_main_query() { return $this->main; }
    public function is_search() { return $this->search; }
    public function get($key) { return $this->vars[$key] ?? null; }
    public function set($key, $value) { $this->vars[$key] = $value; }
}
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
$manifest = json_decode(file_get_contents(dirname(__DIR__) . '/native-page-manifest.json'), true, 512, JSON_THROW_ON_ERROR);
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
$reordered = $manifest;
$reordered['pages'] = array_reverse($manifest['pages']);
check($preview($reordered) === $result, 'Registry ordering changed the planning preview');
$bad = $manifest; $bad['pages'][1]['landing_page_id'] = $bad['pages'][0]['landing_page_id'];
rejects(fn() => $preview($bad), 'duplicated');
$bad = $manifest; $bad['pages'][0]['proposed_path'] = '/lp/../admin/';
$swapped = $manifest;
$swapped['pages'][0]['landing_page_id'] = $manifest['pages'][1]['landing_page_id'];
$swapped['pages'][1]['landing_page_id'] = $manifest['pages'][0]['landing_page_id'];
rejects(fn() => $preview($swapped), 'reviewed registry');
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
define('BSRE_PAID_ENTRY_SEARCH_EXCLUSION_ENABLED', true);
require dirname(__DIR__) . '/paid-entry-search.php';
$posts[26750] = ['path' => 'enquire', 'type' => 'page'];
$posts[26753] = ['path' => 'enquire/rent', 'type' => 'page'];
$search_hooks['pre_get_posts']($search = new WP_Query(['post__not_in' => [91]]));
check($search->vars['post__not_in'] === [91, 26750, 26753], 'Public search did not preserve existing exclusions');
$search_hooks['pre_get_posts']($direct = new WP_Query([], true, false));
check($direct->vars === [], 'Direct pages must remain untouched');
$search_hooks['pre_get_posts']($secondary = new WP_Query([], false));
check($secondary->vars === [], 'Secondary queries must remain untouched');
$admin_search = true;
$search_hooks['pre_get_posts']($private = new WP_Query([]));
check($private->vars === [], 'Admin search must remain untouched');
$admin_search = false;
$rest = $search_hooks['rest_post_search_query'];
check($rest(['post__in' => [26750, 26753]])['post__in'] === [0], 'REST include-only exclusions broadened the query');
$posts[26753]['path'] = 'other';
check($rest([])['post__not_in'] === [26750], 'Mismatched page identity was excluded');
$origin = 'https://business-setup.invalid';
check($rest([]) === [], 'An unrelated site was affected');
check($writes === 0, 'A WordPress write was attempted');
echo json_encode(['status' => 'PASS', 'checks' => $checks, 'wordpress_writes' => $writes]) . PHP_EOL;
