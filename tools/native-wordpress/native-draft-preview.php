<?php
/** Local review adapter only. No hooks, routes, UI, writes or publication handler. */
namespace BSRE\NativePlanning;

if (!defined('ABSPATH')) return;

function preview(array $manifest, string $campaign_key, string $nonce, string $mode = 'dry-run'): array {
    if (!defined('BSRE_NATIVE_PLANNER_PREVIEW_ENABLED') || BSRE_NATIVE_PLANNER_PREVIEW_ENABLED !== true) {
        throw new \RuntimeException('Native planning preview is disabled.');
    }
    if (!current_user_can('manage_options') || !wp_verify_nonce($nonce, 'bsre_native_page_preview')) {
        throw new \RuntimeException('An authorized administrator and valid preview nonce are required.');
    }
    if ($mode !== 'dry-run') throw new \RuntimeException('Write mode is not implemented or authorized.');
    if (($manifest['schema'] ?? '') !== 'bsre-native-page-plan-v1' ||
        ($manifest['mode'] ?? '') !== 'PLAN_ONLY' ||
        ($manifest['native_policy']['apply_supported'] ?? null) !== false ||
        ($manifest['native_policy']['publication_allowed'] ?? null) !== false ||
        ($manifest['native_policy']['post_status'] ?? '') !== 'draft') {
        throw new \RuntimeException('A draft-only planning manifest is required.');
    }
    if (($manifest['site_origin_expected'] ?? '') !== 'https://blackswanrealestate.ae' ||
        rtrim(home_url('/'), '/') !== $manifest['site_origin_expected']) {
        throw new \RuntimeException('Current CMS origin needs explicit reconciliation.');
    }
    $pages = $manifest['pages'] ?? [];
    if (!is_array($pages) || count($pages) !== 360 || ($manifest['page_count'] ?? null) !== 360) {
        throw new \RuntimeException('The 360-slot planning register is required.');
    }
    $seen_campaigns = []; $seen_pages = []; $seen_paths = []; $selected = null;
    foreach ($pages as $page) {
        if (!is_array($page)) throw new \RuntimeException('Invalid planning record.');
        $key = $page['campaign_key'] ?? ''; $landing = $page['landing_page_id'] ?? '';
        $path = $page['proposed_path'] ?? '';
        if (!is_string($key) || !preg_match('/^BSRE-C[0-9]{4}$/D', $key) ||
            !is_string($landing) || !preg_match('/^BSRE-LP[0-9]{4}$/D', $landing) ||
            $path !== '/lp/' . strtolower($key) . '/' ||
            isset($seen_campaigns[$key]) || isset($seen_pages[$landing]) || isset($seen_paths[$path]) ||
            ($page['content_state'] ?? '') !== 'BLOCKED_SOURCE_REQUIRED' ||
            ($page['path_status'] ?? '') !== 'PROPOSED_NOT_VERIFIED' ||
            ($page['actual_url'] ?? null) !== null || ($page['cms_page_id'] ?? null) !== null ||
            ($page['google_campaign_id'] ?? null) !== null || ($page['page_version'] ?? null) !== null) {
            throw new \RuntimeException('Invalid, duplicated or already deployed page mapping.');
        }
        $seen_campaigns[$key] = true; $seen_pages[$landing] = true; $seen_paths[$path] = true;
        if ($key === $campaign_key) $selected = $page;
    }
    if ($selected === null) throw new \RuntimeException('Select one registered campaign key.');
    $lookup = ['post_type' => 'page', 'post_status' => ['publish', 'future', 'draft', 'pending',
        'private', 'trash', 'auto-draft', 'inherit'], 'fields' => 'ids', 'numberposts' => 3,
        'suppress_filters' => false];
    $by_campaign = get_posts(array_merge($lookup, ['meta_key' => '_bsre_campaign_key', 'meta_value' => $campaign_key]));
    $by_landing = get_posts(array_merge($lookup, ['meta_key' => '_bsre_landing_page_id', 'meta_value' => $selected['landing_page_id']]));
    if (count($by_campaign) > 1 || count($by_landing) > 1) {
        throw new \RuntimeException('Duplicate CMS identity requires owner reconciliation.');
    }
    $campaign_id = (int) ($by_campaign[0] ?? 0); $landing_id = (int) ($by_landing[0] ?? 0);
    if ($campaign_id || $landing_id) {
        if ($campaign_id !== $landing_id || !$campaign_id ||
            get_post_meta($campaign_id, '_bsre_campaign_key', true) !== $campaign_key ||
            get_post_meta($campaign_id, '_bsre_landing_page_id', true) !== $selected['landing_page_id'] ||
            trim(get_page_uri($campaign_id), '/') !== trim($selected['proposed_path'], '/')) {
            throw new \RuntimeException('Existing campaign/page ownership or route conflicts.');
        }
        return ['status' => 'EXISTING_PRESERVED', 'cms_page_id' => $campaign_id,
                'writes_performed' => 0, 'draft_request' => null];
    }
    $collision = get_page_by_path(trim($selected['proposed_path'], '/'), OBJECT, 'page');
    if ($collision) throw new \RuntimeException('Proposed path already belongs to a CMS record.');
    $parent = get_page_by_path('lp', OBJECT, 'page');
    $blocks = ['CONTENT_EVIDENCE_REQUIRED', 'NATIVE_TEMPLATE_ACCEPTANCE_REQUIRED',
               'PAGE_VISIBILITY_ACCEPTANCE_REQUIRED', 'WRITE_IMPLEMENTATION_AND_APPROVAL_REQUIRED'];
    if (!$parent) $blocks[] = 'NATIVE_PARENT_ROUTE_UNVERIFIED';
    return ['status' => 'BLOCKED_PLAN_ONLY', 'campaign_key' => $campaign_key,
            'landing_page_id' => $selected['landing_page_id'], 'actual_url' => null,
            'writes_performed' => 0, 'blocked_reasons' => $blocks,
            'draft_request' => ['post_type' => 'page', 'post_status' => 'draft',
                'post_title' => 'Campaign planning record ' . $campaign_key,
                'post_name' => strtolower($campaign_key), 'post_parent' => $parent ? (int) $parent->ID : null,
                'post_content' => '', 'meta_input' => ['_bsre_campaign_key' => $campaign_key,
                    '_bsre_landing_page_id' => $selected['landing_page_id'],
                    '_bsre_proposed_path' => $selected['proposed_path'],
                    '_bsre_native_manifest_schema' => $manifest['schema']]]];
}
