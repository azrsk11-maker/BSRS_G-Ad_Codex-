<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

/** Shared, collision-safe operation for WP-admin and optional WP-CLI. */
function ensure_drafts(bool $dry_run = false): array {
    if (!real_estate_home(home_url('/')) || !is_ssl()) throw new \RuntimeException('A verified HTTPS Black Swan Real Estate site is required. No drafts were created.');
    if (!$dry_run && !add_option('bsre_draft_creation_lock', time(), '', false)) throw new \RuntimeException('Draft creation is already locked. Inspect any partial BSRE drafts before recovery.');
    try {
        // Read/preflight only after acquiring the write lock, including reruns.
        $missing = new \stdClass();
        $existing = get_option('bsre_draft_pages', $missing);
        if ($existing !== $missing) {
            if (!is_array($existing) || count($existing) !== count(SERVICES) || array_diff(array_keys($existing), array_keys(SERVICES))) throw new \RuntimeException('Existing BSRE page registry needs manual reconciliation; no pages changed.');
            foreach (SERVICES as $slug => $unused) {
                $id = managed_native_page_id($existing[$slug] ?? null);
                if (!$id || get_post_type($id) !== 'page' || get_post_meta($id, '_bsre_service', true) !== $slug) throw new \RuntimeException('Existing BSRE page registry needs manual reconciliation; no pages changed.');
            }
            return ['status' => 'existing', 'pages' => $existing];
        }
        if (get_page_by_path('enquire', OBJECT, 'page')) throw new \RuntimeException('/enquire already exists. Review the collision before any draft creation.');
        foreach (SERVICES as $slug => $details) if (get_page_by_path('enquire/' . $slug, OBJECT, 'page')) throw new \RuntimeException('A planned service path already exists; no pages changed.');
        if ($dry_run) return ['status' => 'planned', 'pages' => []];
        $hub = '<p>Contact Black Swan Real Estate about your Dubai property requirements.</p><ul>';
        foreach (SERVICES as $slug => $details) $hub .= '<li><a href="' . esc_url(home_url('/enquire/' . $slug . '/')) . '">' . esc_html($details['title']) . '</a></li>';
        $hub .= '</ul>';
        $parent = wp_insert_post(['post_type' => 'page', 'post_status' => 'draft', 'post_title' => 'Black Swan Real Estate Enquiries', 'post_name' => 'enquire', 'post_content' => $hub, 'meta_input' => ['_bsre_parent' => '1']], true);
        if (is_wp_error($parent)) throw new \RuntimeException('Parent draft could not be created. Inspect WordPress errors.');
        $ids = [];
        foreach (SERVICES as $slug => $details) {
            $id = wp_insert_post(['post_type' => 'page', 'post_status' => 'draft', 'post_title' => $details['title'], 'post_name' => $slug, 'post_parent' => $parent, 'post_content' => 'Black Swan Real Estate ' . $details['title'] . '. This draft renders the reviewed packaged landing template. Delivery stays disabled until verified dependencies are configured.', 'meta_input' => ['_bsre_service' => $slug]], true);
            if (is_wp_error($id)) throw new \RuntimeException('Partial draft creation: stop and reconcile BSRE-marked drafts. No page was published.');
            $ids[$slug] = (int) $id;
        }
        update_option('bsre_draft_pages', $ids, false);
        update_option('bsre_parent_draft', (int) $parent, false);
        return ['status' => 'created', 'pages' => $ids];
    } finally {
        if (!$dry_run) delete_option('bsre_draft_creation_lock');
    }
}
