<?php
declare(strict_types=1);

namespace BSRE\ReceiptRecovery;

use BSRE\Enquiries as Intake;

require_once __DIR__ . '/receipt-recovery.php';

// The isolated lab explicitly registers these handlers. The installed plugin
// has no registration or include for this candidate.
function register_routes(): void
{
    foreach (['proof', 'status'] as $operation) {
        register_rest_route('bsre/v1', '/receipt-recovery/' . $operation, [
            'methods' => 'POST', 'permission_callback' => '__return_true',
            'callback' => static fn (\WP_REST_Request $request) => handle($request, $operation),
        ]);
    }
}

function handle(\WP_REST_Request $request, string $operation): \WP_REST_Response
{
    global $wpdb;
    $now = time();
    $session = $_COOKIE[Intake\COOKIE] ?? '';
    $secret = wp_salt('auth');
    if ($request->get_method() !== 'POST' || !Intake\same_origin_request($request)
        || !is_string($session) || !Intake\valid_csrf((string) $request->get_header('x-bsre-csrf'), $session, $secret, $now)) {
        return Intake\response(403, ['status' => 'UNCONFIRMED']);
    }
    if (strlen($request->get_body()) > 256
        || !preg_match('~\Aapplication/json(?:\s*;\s*charset=utf-8)?\z~i', (string) $request->get_header('content-type'))) {
        return Intake\response(400, ['status' => 'UNCONFIRMED']);
    }
    $body = json_decode($request->get_body(), false, 3);
    if (!$body instanceof \stdClass || ($operation === 'proof' ? get_object_vars($body) !== []
        : array_keys(get_object_vars($body)) !== ['proof'] || !is_string($body->proof))) {
        return Intake\response(400, ['status' => 'UNCONFIRMED']);
    }
    $ip = Intake\client_address();
    if (!$ip || Intake\limited('receipt-recovery:' . $ip, 60, 30)
        || Intake\limited('receipt-recovery-session:' . $session, 60, 15)) {
        return Intake\response(429, ['status' => 'UNCONFIRMED']);
    }
    if ($operation === 'proof') {
        try {
            // Only mint for a new server-selected UUID. A caller cannot bind an
            // existing enquiry reference to a different session.
            $id = wp_generate_uuid4();
            return Intake\response(200, ['request_id' => $id, 'proof' => issue($id, $session, $secret, $now), 'expires_in' => RECOVERY_SECONDS]);
        } catch (\InvalidArgumentException $error) {
            return Intake\response(400, ['status' => 'UNCONFIRMED']);
        }
    }
    return Intake\response(200, recover($body->proof, $session, $secret, $now, static function (string $id) use ($wpdb) {
        $table = $wpdb->prefix . 'bsre_consent_captures';
        return $wpdb->get_row($wpdb->prepare(
            "SELECT request_id,state,delivery_pending,lead_id,event_id FROM {$table} WHERE request_id=%s LIMIT 1", $id
        ), ARRAY_A);
    }));
}
