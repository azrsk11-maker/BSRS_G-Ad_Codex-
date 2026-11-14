<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

/** Response protection only. Never a page/transport/measurement approval. */
function enquiry_seo_reserved_request(): bool {
    if (is_admin()
        || (defined('WP_CLI') && WP_CLI)
        || (defined('DOING_AJAX') && DOING_AJAX)
        || (defined('DOING_CRON') && DOING_CRON)
        || (defined('REST_REQUEST') && REST_REQUEST)
        || (defined('XMLRPC_REQUEST') && XMLRPC_REQUEST)
        || is_feed() || is_embed() || is_trackback()) return false;
    $method = $_SERVER['REQUEST_METHOD'] ?? '';
    if (!in_array($method, ['GET', 'HEAD'], true)) return false;
    $home = home_url('/');
    if (!is_string($home) || !real_estate_home($home) || parse_url($home, PHP_URL_PATH) !== '/') return false;
    $uri = $_SERVER['REQUEST_URI'] ?? null;
    if (!is_string($uri) || $uri === '' || $uri[0] !== '/' || str_starts_with($uri, '//')
        || preg_match('/[\x00-\x20\x7f\\\\#]/', $uri)) return false;
    $query = strpos($uri, '?');
    $path = $query === false ? $uri : substr($uri, 0, $query);
    return in_array($path, ['/enquire/', '/enquire/off-plan/', '/enquire/resale/',
        '/enquire/rent/', '/enquire/sell/', '/enquire/let/'], true);
}

function enquiry_seo_send_headers(): void {
    if (!enquiry_seo_reserved_request() || headers_sent()) return;
    nocache_headers();
    // Append, never replace: existing generic/per-bot restrictions survive.
    // Absence of nofollow is the default; this never relaxes older nofollow.
    header('X-Robots-Tag: noindex', false);
}
add_action('send_headers', __NAMESPACE__ . '\\enquiry_seo_send_headers', PHP_INT_MAX);
