<?php
/** Run only in the existing isolated synthetic WordPress Actions lab. */
declare(strict_types=1);
// Check kernel/process boundaries BEFORE loading WordPress or its database configuration.
// Outer CI isolation remains mandatory; these checks do not create a sandbox.
if (PHP_SAPI !== 'cli' || !is_dir('/sys/class/net')
    || array_values(array_diff(scandir('/sys/class/net'), ['.', '..'])) !== ['lo']
    || !is_readable('/proc/net/route')
    || count(preg_split('/\r?\n/', trim(file_get_contents('/proc/net/route')))) !== 1
    || !function_exists('posix_geteuid') || posix_geteuid() === 0
    || !is_file('/opt/wordpress/wp-load.php')) {
    throw new RuntimeException('This acceptance harness requires the disposable network-none lab.');
}
require '/opt/wordpress/wp-load.php';
if (!defined('DB_NAME') || DB_NAME !== 'bsre_synthetic' || $wpdb->prefix !== 'synthetic_'
    || !defined('WP_HOME') || WP_HOME !== 'http://bsre.invalid'
    || !defined('WP_HTTP_BLOCK_EXTERNAL') || WP_HTTP_BLOCK_EXTERNAL !== true) {
    throw new RuntimeException('Synthetic database, origin and isolation guards required.');
}
$checks = [];
function property_native_check(string $name, bool $ok): void {
    if (!$ok) throw new RuntimeException('Native property tool check failed: ' . $name);
    $GLOBALS['checks'][$name] = true;
}
$before = (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts}");
$writes = [];
$http_calls = 0;
add_filter('query', static function ($sql) use (&$writes) {
    if (!preg_match('/^\s*(SELECT|SHOW|DESCRIBE|EXPLAIN)\b/i', $sql)) $writes[] = $sql;
    return $sql;
});
add_filter('pre_http_request', static function ($result) use (&$http_calls) { $http_calls++; return $result; }, 1);
$engine = 'bsre-property-decision-engine';
$ui = 'bsre-property-decision-ui';
$style = 'bsre-property-decision-tools';
require '/opt/wordpress/wp-content/plugins/bsre-property-decision-tools/property-decision-tools.php';
property_native_check('disabled_by_default', !\BSRE\PropertyDecisionTools\enabled() && !shortcode_exists('bsre_property_decision_tools'));
property_native_check('disabled_render_empty', \BSRE\PropertyDecisionTools\render_shortcode() === '');
\BSRE\PropertyDecisionTools\register();
property_native_check('disabled_register_held', !shortcode_exists('bsre_property_decision_tools'));
property_native_check('disabled_no_assets', !wp_script_is($engine, 'enqueued') && !wp_script_is($ui, 'enqueued') && !wp_style_is($style, 'enqueued'));
define('BSRE_PROPERTY_DECISION_TOOLS_ENABLED', true);
\BSRE\PropertyDecisionTools\register();
property_native_check('enabled_native_shortcode', shortcode_exists('bsre_property_decision_tools'));
property_native_check('unknown_tool_empty', do_shortcode('[bsre_property_decision_tools tool="unverified"]') === '');
property_native_check('untrusted_tool_empty', \BSRE\PropertyDecisionTools\render_shortcode(['tool' => '"><script>bad</script>']) === '');
property_native_check('invalid_tool_no_assets', !wp_script_is($engine, 'enqueued') && !wp_script_is($ui, 'enqueued'));
$all = do_shortcode('[bsre_property_decision_tools]');
property_native_check('real_shortcode_mount', str_contains($all, 'data-bsre-property-tools') && str_contains($all, 'data-tool=""'));
foreach (\BSRE\PropertyDecisionTools\TOOLS as $tool) {
    $html = do_shortcode('[bsre_property_decision_tools tool="' . $tool . '"]');
    property_native_check('selection_' . $tool, str_contains($html, 'data-tool="' . $tool . '"') && str_contains($html, 'No contact details are required.'));
}
$second = do_shortcode('[bsre_property_decision_tools tool="office_fit"]');
preg_match('/<section id="([^"]+)"/', $all, $first_id);
preg_match('/<section id="([^"]+)"/', $second, $second_id);
property_native_check('unique_accessible_mounts', isset($first_id[1], $second_id[1]) && $first_id[1] !== $second_id[1]
    && str_contains($all, 'aria-labelledby="' . $first_id[1] . '-title"'));
$scripts = wp_scripts();
$styles = wp_styles();
$expected = 'http://bsre.invalid/wp-content/plugins/bsre-property-decision-tools/';
property_native_check('real_local_asset_urls', $scripts->registered[$engine]->src === $expected . 'engine.js'
    && $scripts->registered[$ui]->src === $expected . 'ui.js' && $styles->registered[$style]->src === $expected . 'tools.css');
property_native_check('engine_dependency_and_footer', $scripts->registered[$ui]->deps === [$engine]
    && $scripts->get_data($engine, 'group') === 1 && $scripts->get_data($ui, 'group') === 1);
property_native_check('no_inline_measurement_or_localized_values', !$scripts->get_data($engine, 'data') && !$scripts->get_data($ui, 'data')
    && !$scripts->get_data($engine, 'after') && !$scripts->get_data($ui, 'after'));
property_native_check('no_server_form_or_remote_embed', !preg_match('~<(?:form|input|script|iframe)\b~i', $all));
property_native_check('assets_exist_in_native_plugin', is_file(WP_PLUGIN_DIR . '/bsre-property-decision-tools/engine.js')
    && is_file(WP_PLUGIN_DIR . '/bsre-property-decision-tools/ui.js') && is_file(WP_PLUGIN_DIR . '/bsre-property-decision-tools/tools.css'));
property_native_check('no_outbound_http', $http_calls === 0);
property_native_check('no_database_writes', $writes === [] && $before === (int) $wpdb->get_var("SELECT COUNT(*) FROM {$wpdb->posts}"));
echo json_encode(['phase' => 'native_property_decision_tools', 'status' => 'PASS', 'wordpress' => $wp_version,
    'checks' => $checks, 'synthetic_database_only' => true, 'browser_acceptance' => false, 'production_acceptance' => false], JSON_THROW_ON_ERROR) . "\n";
