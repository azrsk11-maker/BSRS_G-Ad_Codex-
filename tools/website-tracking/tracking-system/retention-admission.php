<?php
declare(strict_types=1);

namespace BSRE\RetentionAdmission;

use BSRE\Enquiries as Intake;
use BSRE\PurposeAttribution as Purpose;

const CONTRACT = 'bsre-retention-admission-v1';
const MAX_AGE_SECONDS = 900;

final class Runtime
{
    public static ?array $proof = null;
    public static string $session = '';
}

function descriptor(bool $enabled, string $generation, int $activated, string $audience): array
{
    if ($enabled && (!preg_match('/^[a-f0-9]{64}$/D', $generation) || $activated <= 0
        || !preg_match('/^[a-f0-9]{64}$/D', $audience))) {
        throw new \InvalidArgumentException('ADMISSION_CONFIGURATION_INVALID');
    }
    return ['contract' => CONTRACT, 'mode' => $enabled ? 'ENFORCED' : 'DISABLED',
        'generation' => $enabled ? $generation : '', 'activated_at' => $enabled ? $activated : 0,
        'max_age_seconds' => MAX_AGE_SECONDS, 'audience' => $enabled ? $audience : ''];
}

function configuration(): array
{
    $enabled = defined('BSRE_RETENTION_ADMISSION_ENABLED') && BSRE_RETENTION_ADMISSION_ENABLED === true;
    $value = descriptor($enabled,
        defined('BSRE_RETENTION_ADMISSION_GENERATION') ? BSRE_RETENTION_ADMISSION_GENERATION : '',
        defined('BSRE_RETENTION_ADMISSION_ACTIVATED_AT') ? BSRE_RETENTION_ADMISSION_ACTIVATED_AT : 0,
        defined('BSRE_LEAD_RECEIVER_URL') ? hash('sha256', BSRE_LEAD_RECEIVER_URL) : '');
    if ($enabled && $value['activated_at'] > time()) throw new \RuntimeException('ADMISSION_CONFIGURATION_INVALID');
    return $value;
}

function signature(array $proof, string $secret): string
{
    if (strlen($secret) < 32) throw new \InvalidArgumentException('ADMISSION_SECRET_INVALID');
    return hash_hmac('sha256', CONTRACT . "\n" . $proof['request_id'] . "\n" . $proof['issued_at']
        . "\n" . $proof['expires_at'] . "\n" . $proof['session_hash'] . "\n" . $proof['generation']
        . "\n" . $proof['audience'], $secret);
}

/** Called only with the fresh UUID returned by the guarded recovery proof handler. */
function sign_new_request(string $request, string $session, string $secret, array $gate, int $now): array
{
    if (!preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $request)
        || strlen($session) < 32 || $gate['mode'] !== 'ENFORCED' || $now < $gate['activated_at']) {
        throw new \InvalidArgumentException('ADMISSION_CONTEXT_INVALID');
    }
    $proof = ['version' => 1, 'request_id' => $request, 'issued_at' => $now,
        'expires_at' => $now + MAX_AGE_SECONDS, 'session_hash' => hash('sha256', $session),
        'generation' => $gate['generation'], 'audience' => $gate['audience']];
    $proof['signature'] = signature($proof, $secret);
    return $proof;
}

function valid_proof(?array $proof, string $request, ?string $session, string $secret, array $gate, int $now, bool $fresh): bool
{
    if ($proof === null || $gate['mode'] !== 'ENFORCED' || strlen($secret) < 32) return false;
    $keys = array_keys($proof); sort($keys);
    if ($keys !== ['audience','expires_at','generation','issued_at','request_id','session_hash','signature','version']
        || $proof['version'] !== 1 || $proof['request_id'] !== $request
        || !is_int($proof['issued_at']) || !is_int($proof['expires_at'])
        || $proof['issued_at'] <= 0 || $proof['issued_at'] > $now
        || $proof['expires_at'] - $proof['issued_at'] !== MAX_AGE_SECONDS
        || !is_string($proof['generation']) || !preg_match('/^[a-f0-9]{64}$/D', $proof['generation'])
        || !is_string($proof['audience']) || $proof['audience'] !== $gate['audience']
        || !is_string($proof['session_hash']) || !preg_match('/^[a-f0-9]{64}$/D', $proof['session_hash'])
        || !is_string($proof['signature']) || !preg_match('/^[a-f0-9]{64}$/D', $proof['signature'])
        || ($session !== null && (strlen($session) < 32 || !hash_equals(hash('sha256', $session), $proof['session_hash'])))) return false;
    if ($fresh && ($now >= $proof['expires_at'] || $proof['issued_at'] < $gate['activated_at']
        || $proof['generation'] !== $gate['generation'])) return false;
    return hash_equals(signature($proof, $secret), $proof['signature']);
}

/** Runs inside the capture transaction, before any INSERT. Purge must lock the same row. */
function assert_capture($db, array $capture): void
{
    $gate = configuration();
    if ($gate['mode'] !== 'ENFORCED') return;
    $db->last_error = '';
    $rows = $db->get_results($db->prepare("SELECT request_id,fingerprint FROM {$db->prefix}bsre_consent_captures WHERE request_id=%s FOR UPDATE", $capture['request_id']), ARRAY_A);
    if ($db->last_error !== '' || !is_array($rows) || count($rows) > 1) throw new \RuntimeException('ADMISSION_STORAGE_UNAVAILABLE');
    if ($rows) {
        if (!hash_equals($rows[0]['fingerprint'], $capture['fingerprint'])) throw new \DomainException('REQUEST_ID_CONFLICT');
        return;
    }
    if (!defined('BSRE_LEAD_HMAC_SECRET') || !valid_proof(Runtime::$proof, $capture['request_id'], Runtime::$session,
        BSRE_LEAD_HMAC_SECRET, $gate, time(), true)) throw new \RuntimeException('ADMISSION_REQUIRED');
}

function envelope(string $raw, string $secret, int $milliseconds): array
{
    $value = Intake\envelope($raw, $secret, $milliseconds);
    if (configuration()['mode'] === 'ENFORCED' && Runtime::$proof !== null) $value['admission'] = Runtime::$proof;
    return $value;
}

/** The original handler validates empty body, origin, CSRF and rate limits before minting a UUID. */
function proof(\WP_REST_Request $request): \WP_REST_Response
{
    $result = \BSRE\ReceiptRecovery\handle($request, 'proof');
    $gate = configuration();
    if ($gate['mode'] !== 'ENFORCED' || $result->get_status() !== 200) return $result;
    $body = $result->get_data();
    try {
        $body['admission'] = sign_new_request($body['request_id'], $_COOKIE[Intake\COOKIE] ?? '',
            BSRE_LEAD_HMAC_SECRET, $gate, time());
    } catch (\Throwable $error) { return Intake\response(503, ['status' => 'UNCONFIRMED']); }
    return Intake\response(200, $body);
}

function receive(\WP_REST_Request $request, bool $purpose): \WP_REST_Response
{
    if (configuration()['mode'] !== 'ENFORCED') return $purpose ? Purpose\receive($request) : Purpose\receive_wire($request);
    $session = $_COOKIE[Intake\COOKIE] ?? '';
    if (!is_string($session) || !Intake\same_origin_request($request)
        || !Intake\valid_csrf((string) $request->get_header('x-bsre-csrf'), $session, wp_salt('auth'), time())) {
        return Intake\reply(403, 'CSRF_FAILED');
    }
    $header = $request->get_header('x-bsre-admission');
    $claim = null;
    if ($header !== null && $header !== '') {
        try {
            if (!is_string($header) || strlen($header) > 700) throw new \RuntimeException('ADMISSION_INVALID');
            $parsed = Intake\consent_choice_object($header);
            if (!$parsed instanceof \stdClass) throw new \RuntimeException('ADMISSION_INVALID');
            $claim = get_object_vars($parsed);
            if (!valid_proof($claim, $claim['request_id'] ?? '', $session, BSRE_LEAD_HMAC_SECRET, configuration(), time(), false)) {
                throw new \RuntimeException('ADMISSION_INVALID');
            }
        } catch (\Throwable $error) { return Intake\reply(400, 'ADMISSION_INVALID'); }
    }
    $previousProof = Runtime::$proof; $previousSession = Runtime::$session;
    Runtime::$proof = $claim; Runtime::$session = $session;
    try { return $purpose ? Purpose\receive($request) : Purpose\receive_wire($request); }
    finally { Runtime::$proof = $previousProof; Runtime::$session = $previousSession; }
}

function receive_legacy(\WP_REST_Request $request): \WP_REST_Response { return receive($request, false); }
function receive_purpose(\WP_REST_Request $request): \WP_REST_Response { return receive($request, true); }

function register_routes(): void
{
    if (configuration()['mode'] !== 'ENFORCED') return;
    foreach (['/lead' => 'receive_legacy', '/purpose-lead' => 'receive_purpose', '/receipt-recovery/proof' => 'proof'] as $route => $callback) {
        register_rest_route('bsre/v1', $route, ['methods' => 'POST', 'permission_callback' => '__return_true',
            'callback' => __NAMESPACE__ . '\\' . $callback], true);
    }
}

/** Configuration readback alone is not deployment or all-path enforcement evidence. */
function readback(): array
{
    $value = configuration();
    $expected = ['/bsre/v1/lead' => 'receive_legacy', '/bsre/v1/purpose-lead' => 'receive_purpose', '/bsre/v1/receipt-recovery/proof' => 'proof'];
    $routes = rest_get_server()->get_routes();
    $installed = true;
    foreach ($expected as $path => $callback) {
        $callbacks = [];
        foreach ($routes[$path] ?? [] as $handler) {
            if (is_array($handler) && is_array($handler['methods'] ?? null) && ($handler['methods']['POST'] ?? false)) {
                $callbacks[] = $handler['callback'] ?? null;
            }
        }
        $installed = $installed && $callbacks === [__NAMESPACE__ . '\\' . $callback];
    }
    $value['routes_installed'] = $installed;
    $store = Purpose\repository();
    $value['store_installed'] = method_exists($store, 'admissionContract') && $store->admissionContract() === CONTRACT;
    return $value;
}
