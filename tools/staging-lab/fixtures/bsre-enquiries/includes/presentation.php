<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

/** Independent first-party preference controls, even when intake is held. */
function tracking_configuration(): array {
    return [
        'cmpProviderId' => 'bsre_first_party_v1',
        'consentContextEndpoint' => owned_parent_url(rest_url('bsre/v1/consent/context'), '/wp-json/bsre/v1/consent/context'),
        'consentUpdateEndpoint' => owned_parent_url(rest_url('bsre/v1/consent/update'), '/wp-json/bsre/v1/consent/update'),
        'privacyUrl' => owned_parent_url(privacy_url()),
        'preferenceDays' => 180,
    ];
}

/** Direct owned output only; no enqueue flushing, theme/content hooks or ambient bus. */
function render_frontend_scripts(array $lead_config = [], ?array $google_override = null, string $nonce = '', bool $full_assets = false): string {
    static $emitted = false;
    if ($emitted || $nonce === '' || !hash_equals(owned_parent_nonce(), $nonce)) return '';
    $names = $full_assets ? ['consent-bridge.js','wordpress.js','lead.js','google-measurement.js'] : ['consent-bridge.js'];
    $urls = [];
    foreach (array_merge(['consent.css'], $names) as $name) {
        $urls[$name] = owned_parent_asset($name);
        if ($urls[$name] === '') return '';
    }
    $emitted = true;
    $lead_config = $full_assets ? array_merge(['contextEndpoint' => '', 'leadEndpoint' => ''], $lead_config) : ['contextEndpoint' => '', 'leadEndpoint' => ''];
    $google = $full_assets && is_array($google_override) ? $google_override : owned_parent_google_off();
    $flags = JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT;
    $html = '<link rel="stylesheet" href="' . esc_url($urls['consent.css'] . '?ver=' . PLUGIN_VERSION) . '">';
    $html .= '<script nonce="' . esc_attr($nonce) . '">window.BSREWordPress=' . wp_json_encode($lead_config, $flags)
        . ';window.BSRELeadConfig={endpoint:"",measurementEligible:false};window.BSRETrackingConfig='
        . wp_json_encode(tracking_configuration(), $flags)
        . ';window.BSREGoogleConfig=' . wp_json_encode($google, $flags) . ';</script>';
    foreach ($names as $asset) $html .= '<script nonce="' . esc_attr($nonce) . '" src="' . esc_url($urls[$asset] . '?ver=' . PLUGIN_VERSION) . '" defer></script>';
    return $html;
}

// The canonical hub is rendered directly. No wp_footer injection is registered.
