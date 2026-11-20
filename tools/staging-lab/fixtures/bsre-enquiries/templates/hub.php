<?php
namespace BSRE\Enquiries;
if (!defined('ABSPATH')) exit;
// Included only after page.php checks scope, native binding, exact body and headers.
if (!isset($document, $scope) || $scope['kind'] !== 'hub' || $document['binding']['mode'] === 'held') return;
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'HEAD') return;
$body = owned_parent_source('hub');
if (!is_string($body) || hash('sha256', $body) !== OWNED_HUB_SHA256) { $document['binding']['reason'] = 'The reviewed enquiry hub is unavailable.'; owned_parent_held($document, true); return; }
// Remove known static block comments and exactly the reviewed inline padding.
// No content filters, dynamic blocks, shortcode/theme or Elementor callbacks.
$body = preg_replace('~<!--.*?-->~s', '', $body);
$body = str_replace(' style="padding-top:32px;padding-right:24px;padding-bottom:64px;padding-left:24px"', '', $body);
echo '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><meta name="referrer" content="no-referrer"><title>Black Swan Real Estate Enquiries</title><link rel="stylesheet" href="' . esc_url(owned_parent_asset('hub.css') . '?ver=' . PLUGIN_VERSION) . '">';
if ($document['binding']['mode'] === 'live') echo '<link rel="canonical" href="' . esc_url($document['binding']['canonical']) . '">';
echo '</head><body class="bsre-hub"><a class="bsre-hub-skip" href="#main">Skip to enquiries</a><main id="main">';
if ($document['binding']['mode'] === 'preview') echo '<p role="note">Authorised draft preview. This page is not published; measurement is off.</p>';
echo $body . '</main>' . render_frontend_scripts([], $document['google'], $document['nonce'], $document['full_assets']) . '</body></html>';
