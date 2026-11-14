<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

/** Trusted provider readback, never a declaration supplied by the owner or closure row. */
interface NoMailCopy
{
    public function readback(array $scope, int $now, bool $cleanup = false, ?array $ticket = null): ?array;
    public function prepareCleanup(array $scope, int $now): ?array;
    /** Requires authenticated backup expiry/restore reapplication, including interrupted jobs. */
    public function forget(array $scope, int $now, array $ticket): bool;
}

/** Server-owned capability. Inspection positively reads the exact row; absence is not clearance. */
interface NoMailRetirement extends NoMailCopy
{
    public function inspect(array $scope, int $now): ?array;
    public function retire(array $scope, array $record, int $now): ?array;
}

final class UnverifiedNoMailRetirement implements NoMailRetirement
{
    public function inspect(array $scope, int $now): ?array { return null; }
    public function retire(array $scope, array $record, int $now): ?array { return null; }
    public function readback(array $scope, int $now, bool $cleanup = false, ?array $ticket = null): ?array { return null; }
    public function prepareCleanup(array $scope, int $now): ?array { return null; }
    public function forget(array $scope, int $now, array $ticket): bool { return false; }
}

final class NoMailRetirementProof
{
    public const CONTRACT = 'bsre-no-mail-retirement-inspection-v1';

    public static function verify(?array $value, array $scope, int $now): array
    {
        if ($value === null) throw new Failure('RETIREMENT_INSPECTION_UNVERIFIED');
        if (($value['contract'] ?? null) !== self::CONTRACT || ($value['scope_hash'] ?? null) !== Workflow::digest($scope)) throw new Failure('RETIREMENT_INSPECTION_CONFLICT');
        if (($value['state'] ?? null) === 'RETIRED') {
            self::keys($value, ['contract', 'scope_hash', 'state', 'proof']);
            if (!is_array($value['proof'])) throw new Failure('RETIREMENT_INSPECTION_UNVERIFIED');
            $hash = NoMailCopyProof::verify($value['proof'], $scope, $now);
            if ($value['proof']['row_state'] !== 'RETIRED') throw new Failure('RETIREMENT_ROW_NOT_RETIRED');
            return ['state' => 'RETIRED', 'proof_hash' => $hash, 'proof' => $value['proof']];
        }
        self::keys($value, ['contract', 'scope_hash', 'state', 'current_store', 'source_hash', 'restore_policy_hash',
            'external_floor_hash', 'mailbox', 'row_status', 'attempt_count', 'send_started_at', 'sent_at', 'observed_at', 'expires_at']);
        if ($value['state'] !== 'UNRETIRED' || !in_array($value['row_status'], ['QUEUED', 'RETRY_WAIT', 'NEEDS_REVIEW'], true)
            || $value['attempt_count'] !== 0 || $value['send_started_at'] !== '' || $value['sent_at'] !== '') throw new Failure('RETIREMENT_OUTBOX_UNVERIFIED');
        foreach (['source_hash', 'restore_policy_hash', 'external_floor_hash'] as $key) {
            if (!is_string($value[$key]) || !preg_match('/^[a-f0-9]{64}$/D', $value[$key])) throw new Failure('RETIREMENT_INSPECTION_UNVERIFIED');
        }
        NoMailCopyProof::verifyStore($value['current_store'], $scope, $value['source_hash'], $value['restore_policy_hash'], $value['external_floor_hash'], $now);
        NoMailCopyProof::verifyMailbox($value['mailbox'], $scope, $now);
        if (!is_int($value['observed_at']) || $value['observed_at'] <= 0 || $value['observed_at'] > $now
            || !is_int($value['expires_at']) || $value['expires_at'] <= $now || $value['expires_at'] > $value['observed_at'] + 300) throw new Failure('RETIREMENT_INSPECTION_STALE');
        return ['state' => 'UNRETIRED', 'proof_hash' => null, 'proof' => null];
    }

    private static function keys(array $value, array $expected): void
    {
        $keys = array_keys($value); sort($keys); sort($expected);
        if ($keys !== $expected) throw new Failure('RETIREMENT_INSPECTION_SCHEMA_INVALID');
    }
}

final class UnverifiedNoMailCopy implements NoMailCopy
{
    public function readback(array $scope, int $now, bool $cleanup = false, ?array $ticket = null): ?array { return null; }
    public function prepareCleanup(array $scope, int $now): ?array { return null; }
    public function forget(array $scope, int $now, array $ticket): bool { return false; }
}

final class NoMailCopyProof
{
    public const CONTRACT = 'bsre-closed-no-mail-copy-v1';
    public const RECOVERY = 30 * 86400;

    public static function scope(array $closure, string $admissionHash, string $fingerprint): array
    {
        return ['contract' => self::CONTRACT, 'closure_id' => $closure['closure_id'],
            'closure_revision' => $closure['revision'], 'closure_hash' => Workflow::digest($closure),
            'request_id' => $closure['request_id'], 'lead_id' => $closure['lead_id'],
            'event_id' => $closure['event_id'], 'fingerprint' => $fingerprint, 'admission_hash' => $admissionHash];
    }

    /** Refreshable observation and mailbox evidence do not change the exact approved fence. */
    public static function verify(?array $value, array $scope, int $now, bool $cleanup = false): string
    {
        if ($value === null) self::fail('NO_COPY_UNVERIFIED');
        $keys = ['schema_version', 'scope', 'scope_hash', 'fence_hash', 'epoch', 'fence_revision', 'source_hash',
            'restore_policy_hash', 'fence_created_at', 'fence_expires_at', 'row_state', 'mailbox',
            'observed_at', 'expires_at', 'recovery', 'current_store', 'external_floor_hash', 'cleanup_receipt'];
        if (array_key_exists('owner_intent_digest', $value)) { $keys[] = 'owner_intent_digest'; self::hash($value['owner_intent_digest']); }
        self::keys($value, $keys);
        if ($value['schema_version'] !== 1 || !is_array($value['scope']) || Workflow::digest($value['scope']) !== Workflow::digest($scope)
            || $value['scope_hash'] !== Workflow::digest($scope)
            || !in_array($value['row_state'], ['RETIRED', 'ABSENT'], true)) self::fail('NO_COPY_SCOPE_CONFLICT');
        foreach (['fence_hash', 'epoch', 'source_hash', 'restore_policy_hash'] as $key) self::hash($value[$key]);
        $store = $value['current_store'];
        self::verifyStore($store, $scope, $value['source_hash'], $value['restore_policy_hash'], $value['external_floor_hash'], $now);
        if (!is_int($value['fence_revision']) || $value['fence_revision'] < 1
            || $value['fence_revision'] > $store['revision']) self::fail('NO_COPY_STORE_UNVERIFIED');
        self::fresh($value, $now);
        if (!is_int($value['fence_created_at']) || $value['fence_created_at'] <= 0
            || $value['fence_created_at'] > $now || !is_int($value['fence_expires_at'])
            || $value['fence_expires_at'] !== $value['fence_created_at'] + self::RECOVERY
            || (!$cleanup && $now >= $value['fence_expires_at'])) self::fail('NO_COPY_CUSTODY_EXPIRED');
        self::verifyMailbox($value['mailbox'], $scope, $now);
        $recovery = $value['recovery'];
        self::keys($recovery, ['contract', 'window_seconds', 'restore_fenced', 'backups_expired_through']);
        if ($recovery['contract'] !== 'bsre-retention-admission-v1' || $recovery['window_seconds'] !== self::RECOVERY
            || $recovery['restore_fenced'] !== true || !is_int($recovery['backups_expired_through'])
            || $recovery['backups_expired_through'] < 0 || $recovery['backups_expired_through'] > $now)
            self::fail('NO_COPY_RECOVERY_UNVERIFIED');
        if ($cleanup && ($now < $value['fence_expires_at']
            || $recovery['backups_expired_through'] < $value['fence_created_at'])) self::fail('NO_COPY_RECOVERY_UNVERIFIED');
        if ($cleanup) {
            $receipt = $value['cleanup_receipt'];
            self::keys($receipt, ['contract', 'scope_hash', 'fence_hash', 'external_floor_hash', 'store_hash',
                'backups_expired_through', 'observed_at', 'expires_at', 'evidence_reference', 'evidence_hash']);
            if ($receipt['contract'] !== 'bsre-no-copy-cleanup-v1' || $receipt['scope_hash'] !== $value['scope_hash']
                || $receipt['fence_hash'] !== $value['fence_hash'] || $receipt['external_floor_hash'] !== $value['external_floor_hash']
                || $receipt['store_hash'] !== Workflow::digest($store)
                || $receipt['backups_expired_through'] !== $recovery['backups_expired_through']) self::fail('NO_COPY_CUSTODY_UNVERIFIED');
            self::fresh($receipt, $now); self::hash($receipt['evidence_hash']);
            if (!is_string($receipt['evidence_reference']) || $receipt['evidence_reference'] === ''
                || strlen($receipt['evidence_reference']) > 256) self::fail('NO_COPY_CUSTODY_UNVERIFIED');
        } elseif ($value['cleanup_receipt'] !== null) self::fail('NO_COPY_SCHEMA_INVALID');
        return Workflow::digest(['scope' => $scope, 'fence_hash' => $value['fence_hash'], 'epoch' => $value['epoch'],
            'source_hash' => $value['source_hash'], 'restore_policy_hash' => $value['restore_policy_hash'],
            'fence_revision' => $value['fence_revision'], 'fence_created_at' => $value['fence_created_at'], 'fence_expires_at' => $value['fence_expires_at']]);
    }

    /** Shared physical-store binding; validation only, never creates runtime authority. */
    public static function verifyStore($store, array $scope, string $sourceHash, string $restoreHash, string $floorHash, int $now): void
    {
        self::keys($store, ['contract', 'namespace', 'epoch', 'revision', 'pruned_through', 'generation',
            'activated_at', 'audience', 'admission_hash', 'source_hash', 'restore_policy_hash']);
        foreach (['epoch', 'generation', 'audience', 'admission_hash', 'source_hash', 'restore_policy_hash'] as $key) self::hash($store[$key]);
        if ($store['contract'] !== self::CONTRACT || $store['namespace'] !== 'SYNTHETIC_BSRE_NO_COPY'
            || !is_int($store['revision']) || $store['revision'] < 1 || !is_int($store['pruned_through'])
            || $store['pruned_through'] < 0 || $store['pruned_through'] > $store['revision']
            || !is_int($store['activated_at']) || $store['activated_at'] < 1 || $store['activated_at'] > $now
            || $store['admission_hash'] !== $scope['admission_hash'] || $store['source_hash'] !== $sourceHash
            || $store['restore_policy_hash'] !== $restoreHash
            || $floorHash !== Workflow::digest($store)) self::fail('NO_COPY_STORE_UNVERIFIED');
    }

    public static function verifyMailbox($mail, array $scope, int $now): void
    {
        self::keys($mail, ['scope_hash', 'mailbox', 'result', 'complete', 'includes_trash',
            'observed_at', 'expires_at', 'evidence_reference', 'evidence_hash']);
        if ($mail['scope_hash'] !== Workflow::digest($scope) || $mail['mailbox'] !== 'marketing@blackswanrealestate.ae'
            || $mail['result'] !== 'ABSENT' || $mail['complete'] !== true || $mail['includes_trash'] !== true)
            self::fail('NO_COPY_MAILBOX_UNVERIFIED');
        self::fresh($mail, $now);
        self::hash($mail['evidence_hash']);
        if (!is_string($mail['evidence_reference']) || $mail['evidence_reference'] === ''
            || strlen($mail['evidence_reference']) > 256 || trim($mail['evidence_reference']) !== $mail['evidence_reference']
            || preg_match('/[\x00-\x1f\x7f]/', $mail['evidence_reference']))
            self::fail('NO_COPY_MAILBOX_UNVERIFIED');
    }

    private static function fresh(array $value, int $now): void
    {
        if (!is_int($value['observed_at']) || !is_int($value['expires_at']) || $value['observed_at'] <= 0
            || $value['observed_at'] > $now || $value['expires_at'] <= $now
            || $value['expires_at'] > $value['observed_at'] + 300) self::fail('NO_COPY_OBSERVATION_STALE');
    }
    private static function hash($value): void
    {
        if (!is_string($value) || !preg_match('/^[a-f0-9]{64}$/D', $value)) self::fail('NO_COPY_SCOPE_CONFLICT');
    }
    private static function keys($value, array $keys): void
    {
        if (!is_array($value)) self::fail('NO_COPY_SCHEMA_INVALID');
        $actual = array_keys($value); sort($actual); sort($keys);
        if ($actual !== $keys) self::fail('NO_COPY_SCHEMA_INVALID');
    }
    private static function fail(string $code): never { throw new Failure($code); }
}
