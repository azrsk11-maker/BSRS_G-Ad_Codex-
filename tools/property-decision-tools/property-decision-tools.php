<?php
/**
 * Plugin Name: Black Swan Property Decision Tools — Integration Candidate
 * Description: User-input-only property scenarios; disabled until explicitly enabled for reviewed integration.
 * Version: 0.1.0
 * Requires PHP: 8.2
 */
declare(strict_types=1);

namespace BSRE\PropertyDecisionTools;

if (!defined('ABSPATH')) {
    return;
}

const TOOLS = [
    'net_yield', 'cash_needed', 'rent_buy', 'offplan_cashflow', 'ready_offplan',
    'rental_movein', 'occupancy_cost', 'office_fit', 'seller_proceeds', 'landlord_vacancy',
];

function enabled(): bool
{
    return defined('BSRE_PROPERTY_DECISION_TOOLS_ENABLED') && BSRE_PROPERTY_DECISION_TOOLS_ENABLED === true;
}

/** No endpoints, submissions, settings, writes, measurement or remote services. */
function render_shortcode(array|string $attributes = []): string
{
    if (!enabled()) {
        return '';
    }
    $attributes = shortcode_atts(['tool' => ''], is_array($attributes) ? $attributes : [], 'bsre_property_decision_tools');
    if (!is_string($attributes['tool']) || ($attributes['tool'] !== '' && !in_array($attributes['tool'], TOOLS, true))) {
        return '';
    }
    $id = wp_unique_id('bsre-property-tools-');
    $base = plugin_dir_url(__FILE__);
    wp_enqueue_style('bsre-property-decision-tools', $base . 'tools.css', [], '0.1.0');
    wp_enqueue_script('bsre-property-decision-engine', $base . 'engine.js', [], '0.1.0', true);
    wp_enqueue_script('bsre-property-decision-ui', $base . 'ui.js', ['bsre-property-decision-engine'], '0.1.0', true);
    return '<section id="' . esc_attr($id) . '" class="bsre-property-tools" data-bsre-property-tools data-tool="' . esc_attr($attributes['tool']) . '" aria-labelledby="' . esc_attr($id . '-title') . '">'
        . '<h2 id="' . esc_attr($id . '-title') . '">Explore a property scenario</h2>'
        . '<p>Use your own figures. No contact details are required. These tools do not send or save your figures.</p>'
        . '<div data-bsre-tool-mount><p>JavaScript is needed to calculate a scenario. No figures are submitted by this tool.</p></div>'
        . '</section>';
}

function register(): void
{
    if (enabled()) {
        add_shortcode('bsre_property_decision_tools', __NAMESPACE__ . '\\render_shortcode');
    }
}

if (enabled()) {
    add_action('init', __NAMESPACE__ . '\\register');
}
