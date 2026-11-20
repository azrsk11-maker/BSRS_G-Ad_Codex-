<?php
/** Pure protocol functions. No WordPress globals or lead persistence. */
namespace BSRE\Enquiries;

const UUID_V4 = '/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/iD';
const SERVICES = [
    'off-plan' => ['role' => 'off_plan', 'title' => 'Dubai Off-Plan Property Enquiry'],
    'resale' => ['role' => 'resale', 'title' => 'Dubai Resale Property Buyer Enquiry'],
    'rent' => ['role' => 'tenant', 'title' => 'Find a Dubai Rental Property'],
    'sell' => ['role' => 'seller', 'title' => 'Sell Your Dubai Property'],
    'let' => ['role' => 'landlord', 'title' => 'Let Your Dubai Property'],
];

function origin(string $url): string {
    if (preg_match('/[\\\\\s]/u', $url)) return '';
    $p = parse_url($url);
    if (!is_array($p) || ($p['scheme'] ?? '') !== 'https' || empty($p['host']) || isset($p['user']) || isset($p['pass'])) return '';
    return 'https://' . strtolower($p['host']) . (isset($p['port']) && $p['port'] !== 443 ? ':' . $p['port'] : '');
}

function real_estate_home(string $home): bool {
    return (bool) preg_match('~^https://(?:www\.)?blackswanrealestate\.ae$~D', origin($home));
}

function valid_receiver(string $url): bool {
    return (bool) preg_match('~^https://script\.google\.com/macros/s/[A-Za-z0-9_-]+/exec$~D', $url);
}

function text($v, int $max, bool $required = false): bool {
    if (!is_string($v) || !preg_match('//u', $v) || preg_match('/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/u', $v)) return false;
    // UTF-16 code units match JavaScript String.length in the signed receiver.
    preg_match_all('/./us', $v, $chars);
    $units = 0;
    foreach ($chars[0] as $char) $units += strlen($char) === 4 ? 2 : 1;
    return $units <= $max && (!$required || trim($v) !== '');
}

function allowed($v, array $values, bool $required): bool {
    return $v === '' ? !$required : in_array($v, $values, true);
}

function valid_touch($value): bool {
    if ($value === null) return true;
    if (!is_object($value)) return false;
    if (array_diff(array_keys(get_object_vars($value)), ['landing_page','referrer','timestamp','parameters'])) return false;
    if (isset($value->parameters) && !is_object($value->parameters)) return false;
    $keys = ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','gclid','gbraid','wbraid'];
    if (isset($value->parameters) && array_diff(array_keys(get_object_vars($value->parameters)), $keys)) return false;
    foreach (['landing_page', 'referrer'] as $field) {
        if (isset($value->$field) && !text($value->$field, 2000)) return false;
    }
    foreach ($keys as $key) {
        if (isset($value->parameters) && property_exists($value->parameters, $key) && !text($value->parameters->$key, 256)) return false;
    }
    return true;
}

function validate_payload(string $raw, string $home, array $live_paths): bool {
    if (strlen($raw) > 18000 || !preg_match('//u', $raw)) return false;
    try { $p = json_decode($raw, false, 32, JSON_THROW_ON_ERROR); } catch (\Throwable $e) { return false; }
    if (!is_object($p) || ($p->contact_consent ?? null) !== true || !is_bool($p->marketing_consent ?? null) || ($p->website ?? null) !== '') return false;
    $keys = ['request_id','role','name','phone','email','country','area','budget','timeline','funding','property_type','property_details','authority','contact_consent','marketing_consent','campaign','landing_page','attribution','website','started_at'];
    if (array_diff(array_keys(get_object_vars($p)), $keys)) return false;
    if (!text($p->request_id ?? null, 36, true) || !preg_match(UUID_V4, $p->request_id)) return false;
    $service = null;
    foreach (SERVICES as $slug => $details) if (($p->role ?? null) === $details['role']) $service = $slug;
    if ($service === null || !isset($live_paths[$service])) return false;
    foreach (['name' => 200, 'phone' => 35, 'country' => 200, 'area' => 200, 'property_type' => 200] as $key => $max) if (!text($p->$key ?? null, $max, true)) return false;
    if (preg_match('/[\r\n]/', $p->name) || !preg_match('/^[+()\d .-]{7,35}$/D', $p->phone)) return false;
    $digits = preg_replace('/\D/', '', $p->phone);
    if (strlen($digits) < 7 || strlen($digits) > 15 || !text($p->email ?? '', 254)) return false;
    if (($p->email ?? '') !== '' && !preg_match('/^[^\s@]+@[^\s@]+\.[^\s@]+$/uD', $p->email)) return false;
    $owner = in_array($service, ['sell', 'let'], true);
    foreach (['budget','timeline','funding','authority'] as $key) {
        if (!text($p->$key ?? '', 200, (!$owner && in_array($key, ['budget','timeline'], true)) || ($owner && $key === 'authority'))) return false;
    }
    if (!text($p->property_details ?? '', 1500, $owner)) return false;
    if (!allowed($p->property_type, ['Apartment','Townhouse','Villa','Other / to discuss'], true)) return false;
    if (!allowed($p->authority ?? '', ['owner','authorized_representative'], $owner)) return false;
    if (!allowed($p->funding ?? '', ['Cash / own funds','Mortgage arranged','Mortgage to be arranged','To discuss'], false)) return false;
    $buyer = ['Within 1 month','In 1–3 months','In 3–6 months','More than 6 months / exploring'];
    $timelines = [
        'off-plan' => $buyer, 'resale' => $buyer,
        'rent' => ['Immediate / move now','Within 30 days','Later / exploring'],
        'sell' => ['As soon as practical','Within 3 months','Later / discussing options'],
        'let' => ['Vacant / available to discuss now','Expected within 30 days','Later / date to discuss'],
    ];
    if (!allowed($p->timeline ?? '', $timelines[$service], !$owner)) return false;
    if (!text($p->campaign ?? '', 160) || preg_match('/[\r\n]/', $p->campaign ?? '')) return false;
    if (!text($p->landing_page ?? null, 2000, true) || origin($p->landing_page) !== origin($home)) return false;
    if ((parse_url($p->landing_page, PHP_URL_PATH) ?: '/') !== $live_paths[$service] || parse_url($p->landing_page, PHP_URL_QUERY) !== null || parse_url($p->landing_page, PHP_URL_FRAGMENT) !== null) return false;
    if (!is_int($p->started_at ?? null) || $p->started_at <= 0 || $p->started_at > 8640000000000000) return false;
    if (isset($p->attribution) && !is_object($p->attribution)) return false;
    if (isset($p->attribution) && array_diff(array_keys(get_object_vars($p->attribution)), ['first','last'])) return false;
    foreach (['first','last'] as $key) if (!valid_touch($p->attribution->$key ?? null)) return false;
    return true;
}

function envelope(string $raw, string $secret, int $epoch_ms): array {
    if (strlen($secret) < 32 || strlen($raw) > 18000) throw new \InvalidArgumentException('NOT_CONFIGURED');
    $timestamp = (string) $epoch_ms;
    return ['version' => 1, 'timestamp' => $timestamp, 'body' => $raw, 'signature' => hash_hmac('sha256', "v1\n{$timestamp}\n{$raw}", $secret)];
}

function csrf_token(string $session, int $issued, string $salt): string {
    return $issued . '.' . hash_hmac('sha256', "bsre-csrf-v1\n{$issued}\n{$session}", $salt);
}

function valid_csrf(string $token, string $session, string $salt, int $now): bool {
    if (!preg_match('/^[a-f0-9]{64}$/D', $session) || !preg_match('/^([0-9]{10})\.[a-f0-9]{64}$/D', $token, $m)) return false;
    $age = $now - (int) $m[1];
    return $age >= 2 && $age <= 7200 && hash_equals(csrf_token($session, (int) $m[1], $salt), $token);
}

/** Relay only a durable receiver receipt. Unknown/ambiguous results keep the UUID. */
function receiver_result($result): array {
    if (is_object($result) && ($result->accepted ?? null) === true && preg_match('/^BSRE-[\w-]{36}$/D', $result->lead_id ?? '') && preg_match('/^evt_[\w-]{36}$/D', $result->event_id ?? '')) {
        return [200, ['accepted' => true, 'lead_id' => $result->lead_id, 'event_id' => $result->event_id]];
    }
    $code = is_object($result) ? ($result->code ?? '') : '';
    if ($code === 'VALIDATION_FAILED') return [400, ['accepted' => false, 'code' => $code, 'retryable' => false]];
    if ($code === 'REQUEST_ID_CONFLICT') return [409, ['accepted' => false, 'code' => $code, 'retryable' => false]];
    return [503, ['accepted' => false, 'code' => 'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID', 'retryable' => true]];
}
