<?php
declare(strict_types=1);

namespace BSRE\ReceiptRecovery;

// Offline candidate. A future endpoint must authenticate the same-origin session
// and supply a private lookup restricted to its own durable capture table.
const RECOVERY_SECONDS = 900;

function issue(string $request, string $session, string $secret, int $now): string
{
    if (!preg_match('/\A[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\z/', $request)
        || strlen($session) < 32 || strlen($secret) < 32 || $now <= 0 || strlen((string) $now) > 11) {
        throw new \InvalidArgumentException('Invalid recovery context');
    }
    $claim = $request . '.' . $now;
    return $claim . '.' . signature($claim, $session, $secret);
}

function signature(string $claim, string $session, string $secret): string
{
    return hash_hmac('sha256', 'bsre-receipt-recovery-v1|' . hash('sha256', $session) . '|' . $claim, $secret);
}

/** Returns a minimal confirmation only for a fully linked durable receipt. */
function recover(string $proof, string $session, string $secret, int $now, callable $lookup): array
{
    $unknown = ['status' => 'UNCONFIRMED'];
    if (strlen($session) < 32 || strlen($secret) < 32 || !preg_match(
        '/\A([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.([1-9][0-9]{0,10})\.([0-9a-f]{64})\z/', $proof, $parts
    )) return $unknown;
    [, $request, $issued, $mac] = $parts;
    if ((int) $issued > $now || $now - (int) $issued >= RECOVERY_SECONDS
        || !hash_equals(signature($request . '.' . $issued, $session, $secret), $mac)) return $unknown;
    try {
        $row = $lookup($request);
    } catch (\Throwable $error) {
        return $unknown;
    }
    if (!is_array($row) || ($row['request_id'] ?? null) !== $request || ($row['state'] ?? null) !== 'ACCEPTED'
        || !in_array($row['delivery_pending'] ?? null, [0, '0'], true)) return $unknown;
    foreach (['lead_id', 'event_id'] as $field) {
        if (!is_string($row[$field] ?? null) || !preg_match('/\A[A-Za-z0-9._:-]{1,150}\z/', $row[$field])) return $unknown;
    }
    // Recovery confirms receipt for the visitor. It has no measurement authority.
    return ['status' => 'ACCEPTED', 'reference' => $row['lead_id']];
}
