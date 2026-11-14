<?php
/** Local integration contract using WordPress doubles; not native WordPress acceptance. */
declare(strict_types=1);
define('ABSPATH', __DIR__ . '/');
$actions = $shortcodes = $styles = $scripts = [];
function add_action($hook, $callback): void { $GLOBALS['actions'][$hook][] = $callback; }
function add_shortcode($tag, $callback): void { $GLOBALS['shortcodes'][$tag] = $callback; }
function shortcode_atts($defaults, $attributes, $name): array { return array_merge($defaults, array_intersect_key($attributes, $defaults)); }
function wp_unique_id($prefix): string { static $id = 0; return $prefix . ++$id; }
function plugin_dir_url($file): string { return 'http://bsre.invalid/wp-content/plugins/bsre-property-decision-tools/'; }
function wp_enqueue_style($handle, $url, $dependencies, $version): void { $GLOBALS['styles'][$handle] = compact('url', 'dependencies', 'version'); }
function wp_enqueue_script($handle, $url, $dependencies, $version, $footer): void { $GLOBALS['scripts'][$handle] = compact('url', 'dependencies', 'version', 'footer'); }
function esc_attr($value): string { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
$checks = [];
function property_check(string $name, bool $ok): void {
    if (!$ok) throw new RuntimeException('Property tool contract failed: ' . $name);
    $GLOBALS['checks'][$name] = true;
}
require __DIR__ . '/property-decision-tools.php';
property_check('default_does_not_register_hooks', $actions === [] && $shortcodes === []);
property_check('default_render_is_empty', \BSRE\PropertyDecisionTools\render_shortcode() === '');
property_check('default_no_assets', $styles === [] && $scripts === []);
\BSRE\PropertyDecisionTools\register();
property_check('manual_register_cannot_bypass_default', $shortcodes === []);
define('BSRE_PROPERTY_DECISION_TOOLS_ENABLED', true);
\BSRE\PropertyDecisionTools\register();
property_check('enabled_callback_is_callable', is_callable($shortcodes['bsre_property_decision_tools'] ?? null));
property_check('invalid_tool_is_empty', \BSRE\PropertyDecisionTools\render_shortcode(['tool' => '<img src=x onerror=alert(1)>']) === '');
property_check('invalid_array_tool_is_empty', \BSRE\PropertyDecisionTools\render_shortcode(['tool' => []]) === '');
property_check('invalid_selection_enqueues_nothing', $styles === [] && $scripts === []);
$first = \BSRE\PropertyDecisionTools\render_shortcode(['tool' => 'rental_movein', 'title' => '<script>bad</script>']);
$second = \BSRE\PropertyDecisionTools\render_shortcode();
property_check('native_mount_and_selection', str_contains($first, 'data-bsre-property-tools') && str_contains($first, 'data-tool="rental_movein"'));
property_check('all_tools_selector_mount', str_contains($second, 'data-tool=""'));
property_check('no_form_or_user_input_submission_in_server_markup', !preg_match('~<(?:form|input|iframe|script)\b~i', $first));
property_check('untrusted_attributes_are_not_rendered', !str_contains($first, '<script>') && !str_contains($first, 'bad'));
property_check('unique_labelled_sections', str_contains($first, 'id="bsre-property-tools-1"') && str_contains($second, 'id="bsre-property-tools-2"') && str_contains($first, 'aria-labelledby="bsre-property-tools-1-title"'));
property_check('local_engine_then_ui_dependencies', count($scripts) === 2 && $scripts['bsre-property-decision-ui']['dependencies'] === ['bsre-property-decision-engine']);
property_check('assets_are_same_site_and_footer_only', count($styles) === 1 && array_reduce($scripts, fn($ok, $asset) => $ok && str_starts_with($asset['url'], 'http://bsre.invalid/wp-content/plugins/bsre-property-decision-tools/') && $asset['footer'] === true, true));
property_check('all_ten_shortcodes_are_supported', count(\BSRE\PropertyDecisionTools\TOOLS) === 10 && array_reduce(\BSRE\PropertyDecisionTools\TOOLS, fn($ok, $tool) => $ok && str_contains(\BSRE\PropertyDecisionTools\render_shortcode(['tool' => $tool]), 'data-tool="' . $tool . '"'), true));
echo json_encode(['phase' => 'property_tools_php_contract', 'status' => 'PASS', 'checks' => $checks, 'native_wordpress_acceptance' => false], JSON_THROW_ON_ERROR) . "\n";
