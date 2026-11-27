<?php
namespace BSRE\Enquiries;
if (PHP_SAPI !== 'cli') exit;
define('ABSPATH', __DIR__);
require __DIR__ . '/offplan-country-pages.php';

const DRAFT_ALIAS = '/off-plan-dubai-de-de/';
$bindings = [];
$authorized = false;
$preview = false;

function get_option($name, $default) { return $GLOBALS['bindings']; }
function managed_native_page_id($value) { return (int) $value; }
function is_page() { return true; }
function get_queried_object_id() { return 30002; }
function get_post_type($id) { return 'page'; }
function get_page_template_slug($id) { return ''; }
function get_post_field($field, $id, $context) {
    return ['post_parent' => 0, 'post_password' => '', 'post_name' => 'off-plan-dubai-de-de'][$field];
}
function get_page_uri($id) { return 'off-plan-dubai-de-de'; }
function live_paths() { return ['off-plan' => '/enquire/off-plan/']; }
function registered_service_page_id($service) { return 26751; }
function get_post_status($id) { return 'publish'; }
function is_preview() { return $GLOBALS['preview']; }
function current_user_can($action, $id) { return $GLOBALS['authorized'] && $action === 'edit_post' && $id === 30002; }

function require_case(bool $condition, string $name): void {
    if (!$condition) throw new \RuntimeException($name);
}

$scope = offplan_country_request_scope(DRAFT_ALIAS, 'bsre_locale=fr-FR');
$held = ['mode' => 'held'];
require_case($scope['country_alias'] === 'de-DE', 'Locale substitution');
require_case(offplan_country_binding($scope, $held) === $held, 'Blank binding exposed route');
require_case(offplan_country_request_scope('/unrelated/', '') === null, 'Unrelated route changed');
$bindings = [DRAFT_ALIAS => 26751];
require_case(offplan_country_page_ids() === [], 'Main enquiry ID was reused');
$bindings = [DRAFT_ALIAS => 30002, '/off-plan-dubai-en-fr/' => 30002];
require_case(offplan_country_page_ids() === [], 'Duplicate alias ID accepted');
$bindings = [DRAFT_ALIAS => 30002];
require_case(offplan_country_binding($scope, $held) === $held, 'Public delivery enabled');
$preview = true;
require_case(offplan_country_binding($scope, $held) === $held, 'Anonymous preview enabled');
$authorized = true;
require_case(offplan_country_request_scope('/', 'page_id=30002&preview=true') === $scope, 'Native preview scope mismatch');
require_case(offplan_country_binding($scope, $held)['mode'] === 'preview', 'Authorized preview unavailable');
echo "Nine country preview scope checks passed.\n";
