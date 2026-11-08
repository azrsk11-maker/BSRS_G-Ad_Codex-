<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;
$scope = owned_parent_scope();
if ($scope === null) return;
$document = owned_parent_document($scope);
$headers_ok = owned_parent_send_headers($document);
if (!$headers_ok || $document['binding']['mode'] === 'held') { owned_parent_held($document, $headers_ok); return; }
if ($scope['kind'] === 'hub') { require __DIR__ . '/hub.php'; return; }
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'HEAD') return;
$slug = $scope['slug']; // Fixed six-path map, never an input-derived filename.
$html = owned_parent_source($slug);
if (!is_string($html)) { $document['binding']['reason'] = 'This enquiry form is temporarily unavailable.'; owned_parent_held($document, true); return; }
$html = str_replace('../assets.css', esc_url(owned_parent_asset('assets.css') . '?ver=' . PLUGIN_VERSION), $html);
$html = str_replace('<a href="../index.html">View all drafts</a>', 'Black Swan Real Estate property enquiries.', $html);
$html = preg_replace('~<script>window\.BSRELeadConfig[^<]*</script><script src="\.\./lead\.js" defer></script>~', '', $html);
if ($document['binding']['mode'] === 'live') $html = str_replace('</head>', '<link rel="canonical" href="' . esc_url($document['binding']['canonical']) . '"></head>', $html);
$privacy = owned_parent_url(privacy_url());
if ($privacy !== '') $html = str_replace('<div class="consent-block">', '<p class="purpose">Read the <a href="' . esc_url($privacy) . '">privacy notice</a> before submitting.</p><div class="consent-block">', $html);
if ($document['binding']['mode'] === 'preview') {
    $html = preg_replace('~<div class="preview" role="note">.*?</div>~s', '<div class="preview" role="note">Authorised draft preview. This form cannot send details or start measurement.</div>', $html, 1);
    $html = preg_replace('~(<form\b[^>]*>)~', '$1<fieldset disabled><legend>Unsent draft preview</legend>', $html, 1);
    $html = str_replace('</form>', '</fieldset></form>', $html);
} else {
    $html = preg_replace('~<div class="preview" role="note">.*?</div>~s', '<div class="preview" role="note">Service enquiry page · Black Swan Real Estate</div>', $html, 1);
}
$html = str_replace('</body>', render_frontend_scripts($document['lead'], $document['google'], $document['nonce'], $document['full_assets']) . '</body>', $html);
echo $html; // Packaged HTML; dynamic URL/config values are independently escaped.
