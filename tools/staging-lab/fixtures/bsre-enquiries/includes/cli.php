<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH') || !defined('WP_CLI') || !WP_CLI) exit;

/** Create exactly five native draft pages and one draft routing parent.
 *
 * ## OPTIONS
 * [--dry-run]
 * : Check collisions and report the plan without writing.
 */
function create_drafts($args, $assoc): void {
    try { $result = ensure_drafts(isset($assoc['dry-run'])); }
    catch (\RuntimeException $e) { \WP_CLI::error($e->getMessage()); return; }
    foreach ($result['pages'] as $slug => $id) \WP_CLI::log($slug . ': page ' . $id . ', ' . get_post_status($id));
    $messages = [
        'planned' => 'Would create one draft /enquire parent and five noindex service drafts. No changes made.',
        'existing' => 'Existing five-page registry preserved. No content or status changed.',
        'created' => 'Created five draft service pages and a draft routing parent. No publication, routing enablement, Ads edits or CRM writes.',
    ];
    \WP_CLI::success($messages[$result['status']]);
}
\WP_CLI::add_command('bsre create-drafts', __NAMESPACE__ . '\\create_drafts');
