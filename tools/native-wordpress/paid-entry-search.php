<?php
/** Staging candidate for the two existing Option A paid-entry pages. */
namespace BSRE\NativePlanning;

if (!defined('ABSPATH')) return;

function paid_entry_search_ids(): array {
    if (rtrim(home_url('/'), '/') !== 'https://blackswanrealestate.ae') return [];
    $ids = [];
    foreach ([26750 => 'enquire', 26753 => 'enquire/rent'] as $id => $path) {
        if (get_post_type($id) === 'page' && get_page_uri($id) === $path) $ids[] = $id;
    }
    return $ids;
}

function paid_entry_search_args(array $args): array {
    $ids = paid_entry_search_ids();
    if (!$ids) return $args;
    // WP_Query gives post__in precedence over post__not_in.
    if (!empty($args['post__in'])) {
        $args['post__in'] = array_values(array_diff((array) $args['post__in'], $ids)) ?: [0];
    }
    $args['post__not_in'] = array_values(array_unique(array_merge((array) ($args['post__not_in'] ?? []), $ids)));
    return $args;
}

if (defined('BSRE_PAID_ENTRY_SEARCH_EXCLUSION_ENABLED') && BSRE_PAID_ENTRY_SEARCH_EXCLUSION_ENABLED === true) {
    add_filter('rest_post_search_query', static function (array $args): array {
        return current_user_can('edit_pages') ? $args : paid_entry_search_args($args);
    });
    add_action('pre_get_posts', static function (\WP_Query $query): void {
        if (is_admin() || !$query->is_main_query() || !$query->is_search()) return;
        $args = paid_entry_search_args(['post__in' => $query->get('post__in'), 'post__not_in' => $query->get('post__not_in')]);
        foreach ($args as $key => $value) $query->set($key, $value);
    });
}
