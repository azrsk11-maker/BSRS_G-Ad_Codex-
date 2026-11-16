<?php
declare(strict_types=1);
namespace BSRE\ProfileTransport;
use BSRE\Enquiries as E;
use BSRE\PurposeAttribution as P;
use BSRE\RetentionAdmission as A;
use BSRE\ReceiptRecovery as R;
use BSRE\SharedRepository as G;

const CONTRACT='bsre-profile-transport-v1';
function selected(): bool { return defined('BSRE_G3_ROUTE_CONTEXT_ENABLED') && BSRE_G3_ROUTE_CONTEXT_ENABLED===true; }
/** Configuration/schema readiness only; never a provider or production certificate. */
function ready(): bool {
    if (!selected() || !defined('BSRE_G2_SHARED_REPOSITORY_ENABLED') || BSRE_G2_SHARED_REPOSITORY_ENABLED!==true
        || !defined('BSRE_PURPOSE_ATTRIBUTION_ENABLED') || BSRE_PURPOSE_ATTRIBUTION_ENABLED!==true
        || !function_exists('BSRE\\SharedRepository\\repository') || !function_exists('BSRE\\RetentionAdmission\\configuration')) return false;
    try {
        if (!E\ready() || A\configuration()['mode']!=='ENFORCED') return false;
        G\repository();
        return true;
    } catch (\Throwable $error) { return false; }
}
function held(): \WP_REST_Response { return E\reply(503,'PROFILE_UNAVAILABLE',true); }
function context(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return held();
    $result=E\context($request);
    if ($result->get_status()!==200) return $result;
    $endpoint=E\owned_parent_url(rest_url('bsre/v1/purpose-lead'),'/wp-json/bsre/v1/purpose-lead');
    if ($endpoint==='') return held();
    $body=$result->get_data();
    $body['transport']=['contract'=>CONTRACT,'purpose_endpoint'=>$endpoint,'admission_required'=>true];
    return E\response(200,$body);
}
function receive_legacy(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return held();
    return A\receive_legacy($request);
}
function receive_purpose(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return held();
    return A\receive_purpose($request);
}
function proof(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return held();
    return A\proof($request);
}
function status(\WP_REST_Request $request): \WP_REST_Response {
    if (!ready()) return held();
    return R\handle($request,'status');
}
/** Explicit final owners prevent A's DISABLED early-return reopening the base receiver. */
function register_routes(): void {
    if (!selected()) return;
    if (function_exists('BSRE\\PurposeAttribution\\register_routes')) P\register_routes();
    if (function_exists('BSRE\\ReceiptRecovery\\register_routes')) R\register_routes();
    foreach (['/context'=>'context','/lead'=>'receive_legacy','/purpose-lead'=>'receive_purpose',
        '/receipt-recovery/proof'=>'proof','/receipt-recovery/status'=>'status'] as $route=>$callback) {
        register_rest_route('bsre/v1',$route,['methods'=>'POST','permission_callback'=>'__return_true',
            'callback'=>__NAMESPACE__.'\\'.$callback],true);
    }
}
function boot(): void {
    if (!selected()) return;
    if (function_exists('BSRE\\PurposeAttribution\\legacy_guard')) add_filter('rest_pre_dispatch','BSRE\\PurposeAttribution\\legacy_guard',10,3);
    add_action('rest_api_init',__NAMESPACE__.'\\register_routes',2000);
}
