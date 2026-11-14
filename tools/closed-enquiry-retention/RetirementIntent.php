<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

/** Separate authoritative sender-retirement intent. It is never a purge plan or a provider grant. */
final class RetirementIntent
{
    public const CONTRACT = 'bsre-owner-no-mail-retirement-v1';
    public const AUTHORIZATION = 'bsre-owner-no-mail-authorization-v1';

    public static function target(array $before): array
    {
        if (!isset($before['revision']) || !is_int($before['revision']) || $before['revision'] >= PHP_INT_MAX) self::fail('RETIREMENT_TARGET_INVALID');
        return array_replace($before, ['revision' => $before['revision'] + 1, 'email_status' => 'RETIRED_NO_COPY']);
    }

    public static function validatePlan(array $plan, int $now): void
    {
        self::keys($plan, ['schema_version', 'contract', 'closure_id', 'actor', 'before', 'after', 'before_hash', 'after_hash',
            'scope', 'admission_hash', 'inventory_hash', 'created_at', 'expires_at', 'digest']);
        if ($plan['schema_version'] !== 1 || $plan['contract'] !== self::CONTRACT || !is_string($plan['actor'])
            || $plan['actor'] === '' || strlen($plan['actor']) > 256 || trim($plan['actor']) !== $plan['actor']
            || preg_match('/[\x00-\x1f\x7f]/', $plan['actor']) || !is_array($plan['before']) || !is_array($plan['after'])
            || !is_int($plan['created_at']) || $plan['created_at'] < 1 || $plan['created_at'] > $now
            || $plan['expires_at'] !== $plan['created_at'] + 900) self::fail('RETIREMENT_PLAN_INVALID');
        Workflow::validateClosureRecord($plan['before'], $plan['created_at'], true);
        Workflow::validateClosureRecord($plan['after'], $plan['created_at'], true);
        if ($plan['closure_id'] !== $plan['before']['closure_id'] || $plan['after'] !== self::target($plan['before'])
            || !in_array($plan['before']['email_status'], ['QUEUED', 'RETRY_WAIT', 'NEEDS_REVIEW'], true)
            || $plan['before']['mail_message_ids'] !== [] || $plan['before_hash'] !== Workflow::digest($plan['before'])
            || $plan['after_hash'] !== Workflow::digest($plan['after'])) self::fail('RETIREMENT_TARGET_INVALID');
        foreach (['before_hash', 'after_hash', 'admission_hash', 'inventory_hash', 'digest'] as $key) self::hash($plan[$key]);
        if (!is_array($plan['scope']) || !isset($plan['scope']['fingerprint'])) self::fail('RETIREMENT_SCOPE_INVALID');
        self::hash($plan['scope']['fingerprint']);
        if ($plan['scope'] !== NoMailCopyProof::scope($plan['after'], $plan['admission_hash'], $plan['scope']['fingerprint'])) self::fail('RETIREMENT_SCOPE_INVALID');
        $unsigned = $plan; unset($unsigned['digest']);
        if ($plan['digest'] !== Workflow::digest($unsigned)) self::fail('RETIREMENT_PLAN_INVALID');
    }

    public static function validateRecord(array $record, int $now): void
    {
        self::keys($record, ['schema_version', 'contract', 'revision', 'plan', 'approved_at', 'recovery_until', 'phase', 'proof_hash', 'hold_codes']);
        if ($record['schema_version'] !== 1 || $record['contract'] !== self::CONTRACT || !is_int($record['revision'])
            || $record['revision'] < 0 || !is_array($record['plan'])) self::fail('RETIREMENT_INTENT_INVALID');
        self::validatePlan($record['plan'], $now);
        if (!is_int($record['approved_at']) || $record['approved_at'] < $record['plan']['created_at']
            || $record['approved_at'] >= $record['plan']['expires_at'] || $record['approved_at'] > $now
            || $record['recovery_until'] !== $record['approved_at'] + NoMailCopyProof::RECOVERY
            || !in_array($record['phase'], ['INTENT_RECORDED', 'FENCE_CONFIRMED', 'RETIREMENT_RECORDED'], true)
            || !is_array($record['hold_codes']) || !array_is_list($record['hold_codes']) || count($record['hold_codes']) > 10) self::fail('RETIREMENT_INTENT_INVALID');
        foreach ($record['hold_codes'] as $code) if (!is_string($code) || !preg_match('/^[A-Z][A-Z0-9_]{1,63}$/D', $code)) self::fail('RETIREMENT_INTENT_INVALID');
        if ($record['phase'] === 'INTENT_RECORDED') {
            if ($record['proof_hash'] !== null) self::fail('RETIREMENT_INTENT_INVALID');
        } else self::hash($record['proof_hash']);
    }

    public static function authorization(array $record): array
    {
        return ['contract' => self::AUTHORIZATION, 'intent_digest' => $record['plan']['digest'],
            'actor' => $record['plan']['actor'], 'scope_hash' => Workflow::digest($record['plan']['scope']),
            'approved_at' => $record['approved_at'], 'create_before' => $record['plan']['expires_at'],
            'recovery_until' => $record['recovery_until']];
    }

    /** Checks the exact persisted owner intent, strict physical row state and fixed fence window. */
    public static function verifiedFence(array $record, array $proof, int $now): string
    {
        self::validateRecord($record, $now);
        $hash = NoMailCopyProof::verify($proof, $record['plan']['scope'], $now);
        if (($proof['owner_intent_digest'] ?? null) !== $record['plan']['digest']
            || $proof['row_state'] !== 'RETIRED' || $proof['fence_created_at'] < $record['approved_at']
            || $proof['fence_created_at'] >= $record['plan']['expires_at'] || $now >= $record['recovery_until']) self::fail('RETIREMENT_FENCE_UNVERIFIED');
        if ($record['proof_hash'] !== null && $record['proof_hash'] !== $hash) self::fail('RETIREMENT_FENCE_CHANGED');
        return $hash;
    }

    private static function keys(array $value, array $expected): void
    {
        $keys = array_keys($value); sort($keys); sort($expected);
        if ($keys !== $expected) self::fail('RETIREMENT_SCHEMA_INVALID');
    }
    private static function hash($value): void
    {
        if (!is_string($value) || !preg_match('/^[a-f0-9]{64}$/D', $value)) self::fail('RETIREMENT_HASH_INVALID');
    }
    private static function fail(string $code): never { throw new Failure($code); }
}
