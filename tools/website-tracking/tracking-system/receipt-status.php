<?php
declare(strict_types=1);

namespace BSRE\ReceiptRecovery;

const STATUS_PURPOSE = 'bsre-receipt-status-v1';

/** A separate signature domain keeps a read request distinct from lead intake. */
function status_request(string $request, string $secret, int $epochMs): array
{
    if (!preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/', $request)
        || strlen($secret) < 32 || !preg_match('/\A[0-9]{13}\z/', (string) $epochMs)) {
        throw new \InvalidArgumentException('Invalid receipt lookup');
    }
    $timestamp = (string) $epochMs;
    return ['version' => 1, 'purpose' => STATUS_PURPOSE, 'request_id' => $request,
        'timestamp' => $timestamp,
        'signature' => hash_hmac('sha256', STATUS_PURPOSE . "\n{$timestamp}\n{$request}", $secret)];
}

/** Accept only the exact receipt contract for the requested UUID. */
function status_receipt($value, string $request): ?array
{
    if (!$value instanceof \stdClass) return null;
    $keys = array_keys(get_object_vars($value));
    sort($keys);
    if ($keys !== ['event_id', 'lead_id', 'request_id', 'status']
        || ($value->status ?? null) !== 'ACCEPTED' || ($value->request_id ?? null) !== $request) return null;
    foreach (['lead_id' => 'BSRE-', 'event_id' => 'evt_'] as $field => $prefix) {
        if (!is_string($value->$field) || !preg_match('/\A' . $prefix
            . '[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/i', $value->$field)) return null;
    }
    return ['lead_id' => $value->lead_id, 'event_id' => $value->event_id];
}
