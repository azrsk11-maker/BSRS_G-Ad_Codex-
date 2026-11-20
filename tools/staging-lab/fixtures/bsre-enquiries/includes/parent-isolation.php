<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;

// Exact native serialization reviewed on 22 October. No normalization or CMS writes.
const OWNED_HUB_SHA256 = 'cee16c9bc1a3f711ec440a0f46533e5b05d8a68aa474629fd740852d71c44df5';
const OWNED_HUB_PAGE_ID = 26750;

/** Fixed packaged names, bounded reads and warning-free failure before output. */
function owned_parent_source(string $name): ?string {
    if (!in_array($name, ['hub','off-plan','resale','rent','sell','let'], true)) return null;
    $body = @file_get_contents(dirname(__DIR__) . '/templates/source/' . $name . '.html', false, null, 0, 40001);
    return is_string($body) && strlen($body) <= 40000 ? $body : null;
}

/** Scope reserves a response, independently of whether its native binding is valid. */
function owned_parent_raw_scope(): ?array {
    if (!is_ssl() || is_admin() || !in_array($_SERVER['REQUEST_METHOD'] ?? '', ['GET', 'HEAD'], true)
        || (defined('REST_REQUEST') && REST_REQUEST) || (defined('DOING_AJAX') && DOING_AJAX)
        || (defined('DOING_CRON') && DOING_CRON) || (defined('WP_CLI') && WP_CLI)
        || (defined('XMLRPC_REQUEST') && XMLRPC_REQUEST)) return null;
    $home = home_url('/');
    if (!is_string($home) || !real_estate_home($home) || parse_url($home, PHP_URL_PATH) !== '/') return null;
    $uri = $_SERVER['REQUEST_URI'] ?? null;
    if (!is_string($uri) || !str_starts_with($uri, '/') || str_starts_with($uri, '//') || preg_match('/[\x00-\x20\x7f\\\\#]/', $uri)) return null;
    $path = explode('?', $uri, 2)[0];
    if (!in_array($path, ['/enquire/', '/enquire/off-plan/', '/enquire/resale/', '/enquire/rent/', '/enquire/sell/', '/enquire/let/'], true)) return null;
    return $path === '/enquire/' ? ['kind' => 'hub', 'slug' => '', 'path' => $path]
        : ['kind' => 'service', 'slug' => substr($path, 9, -1), 'path' => $path];
}

function owned_parent_scope(): ?array {
    return is_feed() || is_embed() || is_trackback() ? null : owned_parent_raw_scope();
}

// An advisory page-cache opt-out only. An earlier cache/CDN may ignore this.
if (owned_parent_raw_scope() !== null && !defined('DONOTCACHEPAGE')) define('DONOTCACHEPAGE', true);

/** Only fixed, query/fragment-free HTTPS URLs on this home origin are allowed. */
function owned_parent_url($url, string $path = ''): string {
    if (!is_string($url) || origin($url) !== origin(home_url('/'))) return '';
    $parts = parse_url($url);
    if (!is_array($parts) || isset($parts['query']) || isset($parts['fragment'])
        || !preg_match('~^/[A-Za-z0-9/_.%\-]*$~D', $parts['path'] ?? '')
        || ($path !== '' && ($parts['path'] ?? '') !== $path)) return '';
    return $url;
}

function owned_parent_asset(string $asset): string {
    if (!in_array($asset, ['assets.css','consent.css','hub.css','consent-bridge.js','wordpress.js','lead.js','google-measurement.js'], true)) return '';
    $base = plugin_dir_url(dirname(__DIR__) . '/bsre-enquiries.php');
    if (owned_parent_url($base) === '' || !str_ends_with($base, '/')) return '';
    return $base . 'assets/' . $asset;
}

/** Re-evaluated after the native query; the nonce cache never caches a verdict. */
function owned_parent_binding(array $scope): array {
    $held = ['mode' => 'held', 'reason' => 'This enquiry page is awaiting a verified page binding.', 'scope' => $scope, 'id' => 0];
    $id = $scope['kind'] === 'hub' ? managed_native_page_id(get_option('bsre_parent_draft', 0)) : registered_service_page_id($scope['slug']);
    if ($scope['kind'] === 'hub' && $id !== OWNED_HUB_PAGE_ID) return $held;
    if (!$id || !is_page() || managed_native_page_id(get_queried_object_id()) !== $id || get_post_type($id) !== 'page') return $held;
    if ($scope['kind'] === 'hub' && get_post_meta($id, '_bsre_parent', true) !== '1') return $held;
    if (get_post_field('post_password', $id, 'raw') !== '') return $held;
    if (get_page_uri($id) !== trim($scope['path'], '/')) return $held;
    if ($scope['kind'] === 'service') {
        $parent = managed_native_page_id(get_option('bsre_parent_draft', 0));
        if ($parent !== OWNED_HUB_PAGE_ID || managed_native_page_id(get_post_field('post_parent', $id, 'raw')) !== $parent
            || get_post_type($parent) !== 'page' || get_post_meta($parent, '_bsre_parent', true) !== '1'
            || get_page_uri($parent) !== 'enquire' || !in_array(get_post_status($parent), ['draft','publish'], true)
            || get_post_field('post_password', $parent, 'raw') !== '') return $held;
    }
    $status = get_post_status($id);
    $preview = is_preview() && in_array($status, ['draft', 'publish'], true) && current_user_can('edit_post', $id);
    if (is_preview() && !$preview) return $held;
    if ($status !== 'publish' && !$preview) return $held;
    $canonical = '';
    if ($preview) {
        // A supported canonical-path preview still needs the exact native hierarchy.
        // Root-query ?page_id previews are deliberately outside this isolation scope.
        // The exact native hierarchy above authorizes only the canonical preview.
    } else {
        $canonical = owned_parent_url(get_permalink($id), $scope['path']);
        if ($canonical === '') return $held;
    }
    if ($scope['kind'] === 'hub') {
        $native = get_post_field('post_content', $id, 'raw');
        $source = owned_parent_source('hub');
        if (!is_string($native) || !is_string($source) || hash('sha256', $native) !== OWNED_HUB_SHA256 || hash('sha256', $source) !== OWNED_HUB_SHA256) {
            $held['reason'] = 'This enquiry hub is awaiting review of its saved content.';
            return $held;
        }
    } elseif (owned_parent_source($scope['slug']) === null) {
        $held['reason'] = 'This enquiry form is temporarily unavailable.';
        return $held;
    }
    return ['mode' => $preview ? 'preview' : 'live', 'reason' => '', 'scope' => $scope, 'id' => $id, 'canonical' => $canonical];
}

function owned_parent_nonce(): string {
    static $nonce = null;
    if ($nonce !== null) return $nonce;
    try { $nonce = bin2hex(random_bytes(24)); } catch (\Throwable $e) { $nonce = ''; }
    return $nonce;
}

function owned_parent_google_off(): array {
    return ['enabled' => false, 'analytics_enabled' => false, 'advertising_enabled' => false,
        'runtime_endpoint' => '', 'status_endpoint' => '', 'config_version' => 'disabled'];
}

/** This document's public capabilities; no option, cookie or server flag is changed. */
function owned_parent_document(array $scope): array {
    $binding = owned_parent_binding($scope);
    $lead = ['contextEndpoint' => '', 'leadEndpoint' => ''];
    $interactive = $binding['mode'] === 'live';
    if ($interactive && $scope['kind'] === 'service') {
        $interactive = ready();
        if ($interactive) {
            $lead['contextEndpoint'] = owned_parent_url(rest_url('bsre/v1/context'), '/wp-json/bsre/v1/context');
            $lead['leadEndpoint'] = owned_parent_url(rest_url('bsre/v1/lead'), '/wp-json/bsre/v1/lead');
            $interactive = $lead['contextEndpoint'] !== '' && $lead['leadEndpoint'] !== '';
        }
        if (!$interactive) {
            $lead = ['contextEndpoint' => '', 'leadEndpoint' => ''];
            $binding['mode'] = 'held';
            $binding['reason'] = 'This enquiry form is temporarily unavailable. Your details have not been sent.';
        }
    }
    $google = $interactive ? measurement_public_configuration() : owned_parent_google_off();
    foreach (['runtime_endpoint' => '/wp-json/bsre/v1/measurement/runtime', 'status_endpoint' => '/wp-json/bsre/v1/measurement/status'] as $key => $path) {
        if ($interactive && owned_parent_url($google[$key] ?? null, $path) === '') $google = owned_parent_google_off();
    }
    return ['binding' => $binding, 'lead' => $lead, 'google' => $google,
        'full_assets' => $interactive, 'nonce' => owned_parent_nonce()];
}

/** Establish before body; an earlier emitter cannot be retracted by this helper. */
function owned_parent_send_headers(array $document): bool {
    if (headers_sent()) return false;
    // Refusal responses need private, noncached metadata even when their nonce
    // or local asset prerequisite fails. Never emit collection markup on failure.
    nocache_headers();
    header('Cache-Control: no-store, private, max-age=0', true);
    header('X-Robots-Tag: noindex, nofollow', false);
    header('Referrer-Policy: no-referrer', true);
    header('Content-Type: text/html; charset=UTF-8', true);
    if (!preg_match('/^[a-f0-9]{48}$/D', $document['nonce'])) return false;
    $styles = [];
    foreach (['consent.css', 'hub.css', 'assets.css'] as $name) {
        $url = owned_parent_asset($name);
        if ($url === '') return false;
        $styles[] = $url;
    }
    $connect = [];
    foreach (['consent/context', 'consent/update'] as $endpoint) {
        $url = owned_parent_url(rest_url('bsre/v1/' . $endpoint), '/wp-json/bsre/v1/' . $endpoint);
        if ($url !== '') $connect[] = $url;
    }
    foreach ($document['lead'] as $url) if ($url !== '') $connect[] = $url;
    $frames = !empty($document['google']['enabled']) && (!empty($document['google']['analytics_enabled']) || !empty($document['google']['advertising_enabled']))
        ? $document['google']['runtime_endpoint'] : "'none'";
    $policy = "default-src 'none'; base-uri 'none'; object-src 'none'; worker-src 'none'; form-action 'none'; frame-ancestors 'self'; "
        . "script-src 'nonce-" . $document['nonce'] . "'; script-src-attr 'none'; style-src " . implode(' ', $styles) . "; style-src-attr 'none'; "
        . 'connect-src ' . ($connect ? implode(' ', array_unique($connect)) : "'none'") . '; frame-src ' . $frames . "; img-src 'none'; font-src 'none'";
    header('Content-Security-Policy: ' . $policy, false);
    return true;
}

/** Generic inert response: no native content, inputs, lead or measurement assets. */
function owned_parent_held(array $document, bool $headers_ok): void {
    status_header(503);
    if (($_SERVER['REQUEST_METHOD'] ?? '') === 'HEAD') return;
    $reason = $headers_ok ? $document['binding']['reason'] : 'This enquiry page cannot establish its required response protection. Your details have not been sent.';
    echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Enquiry page unavailable | Black Swan Real Estate</title>';
    if ($headers_ok) echo '<link rel="stylesheet" href="' . esc_url(owned_parent_asset('hub.css') . '?ver=' . PLUGIN_VERSION) . '">';
    echo '</head><body class="bsre-hub"><main id="main"><h1>Enquiry page unavailable</h1><p>' . esc_html($reason) . '</p><p><a href="https://blackswanrealestate.ae/property-enquiry-privacy-notice/">Property enquiry privacy notice</a></p></main>';
    if ($headers_ok) echo render_frontend_scripts([], owned_parent_google_off(), $document['nonce'], false);
    echo '</body></html>';
}

// Query-dependent authority is deliberately not cached during send_headers.
add_action('send_headers', function (): void {
    if (owned_parent_raw_scope() !== null) owned_parent_nonce();
}, -10000);

// Reserve the response after the native query, before ordinary redirects or a
// theme/Canvas template selector. A later template_include filter cannot undo it.
add_action('template_redirect', function (): void {
    if (owned_parent_scope() === null) return;
    require dirname(__DIR__) . '/templates/page.php';
    exit;
}, -10000);
