<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

const OFFPLAN_COUNTRY_PATHS = [
    '/off-plan-dubai-en-de/' => 'en-DE', '/off-plan-dubai-de-de/' => 'de-DE',
    '/off-plan-dubai-en-fr/' => 'en-FR', '/off-plan-dubai-fr-fr/' => 'fr-FR',
    '/off-plan-dubai-en-tw/' => 'en-TW', '/off-plan-dubai-zh-hant-tw/' => 'zh-Hant-TW',
];

function offplan_country_page_ids(): array {
    $stored = get_option('bsre_offplan_country_page_ids_v1', []);
    if (!is_array($stored) || count($stored) > count(OFFPLAN_COUNTRY_PATHS)) return [];
    $ids = [];
    foreach ($stored as $path => $supplied) {
        $id = managed_native_page_id($supplied);
        if (!isset(OFFPLAN_COUNTRY_PATHS[$path]) || !$id || in_array($id, [26750, 26751, 26752, 26753, 26754, 26755, 26865], true)
            || in_array($id, $ids, true)) return [];
        $ids[$path] = $id;
    }
    return $ids;
}

function offplan_country_request_scope(string $path, string $query): ?array {
    if ($path !== '/' && !isset(OFFPLAN_COUNTRY_PATHS[$path])) return null;
    if ($path === '/') {
        if (!preg_match('/\Apage_id=([1-9][0-9]{0,19})&preview=true\z/', $query, $match)) return null;
        $path = array_search(managed_native_page_id($match[1]), offplan_country_page_ids(), true);
    }
    if (!is_string($path) || !isset(OFFPLAN_COUNTRY_PATHS[$path])) return null;
    return ['kind' => 'service', 'slug' => 'off-plan', 'path' => $path,
        'country_alias' => OFFPLAN_COUNTRY_PATHS[$path]];
}

function offplan_country_binding(array $scope, array $held): array {
    $path = $scope['path'];
    $ids = offplan_country_page_ids();
    $id = $ids[$path] ?? 0;
    $slug = trim($path, '/');
    if (!$id || OFFPLAN_COUNTRY_PATHS[$path] !== $scope['country_alias']
        || !is_page() || managed_native_page_id(get_queried_object_id()) !== $id
        || get_post_type($id) !== 'page' || get_page_template_slug($id) !== ''
        || !in_array(get_post_field('post_parent', $id, 'raw'), [0, '0'], true)
        || get_post_field('post_password', $id, 'raw') !== ''
        || get_post_field('post_name', $id, 'raw') !== $slug || get_page_uri($id) !== $slug) return $held;
    $paths = live_paths();
    if (registered_service_page_id('off-plan') !== 26751 || ($paths['off-plan'] ?? null) !== '/enquire/off-plan/') return $held;
    // Public rendering requires alias-aware intake and an independently verified
    // measurement boundary. This review overlay exposes editor previews only.
    if (!is_preview() || !in_array(get_post_status($id), ['draft', 'publish'], true) || !current_user_can('edit_post', $id)) return $held;
    return ['mode' => 'preview', 'reason' => '', 'scope' => $scope, 'id' => $id, 'canonical' => ''];
}
