<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

/** Trusted server source, never a request-body adapter. No production implementation is installed. */
interface ClosureCollectionSource
{
    public function observe(string $requestId, int $now): ?array;
}

final class UnverifiedClosureCollectionSource implements ClosureCollectionSource
{
    public function observe(string $requestId, int $now): ?array { return null; }
}

/** Insert-only internal capability; namespace custody and the target closure lease must already be held. */
interface ClosureCollectorWriter
{
    public function assertCollectionTarget(array $target, bool $allowExact = false): void;
    public function insertClosure(array $target): void;
}

/** A hash binds observations; only the authenticated source adapter can establish their truth. */
final class CollectionSnapshot
{
    public const CONTRACT = 'bsre-closure-collection-source-v1';
    private const FACTS = ['status', 'request_id', 'lead_id', 'event_id', 'accepted_at_utc', 'closed_at_utc',
        'evidence_reference', 'evidence_hash', 'outcome_ids', 'mail_message_ids', 'email_status'];

    public static function target(array $frame, string $requestId, string $actor, int $recordedAt, int $now): array
    {
        self::validate($frame, $now);
        if ($frame['facts']['request_id'] !== $requestId || $actor === '' || strlen($actor) > 256
            || trim($actor) !== $actor || preg_match('/[\x00-\x1f\x7f]/', $actor)
            || $recordedAt < 1 || $recordedAt > $now) self::fail('COLLECTION_SOURCE_IDENTITY_CONFLICT');
        $facts = [];
        foreach (self::FACTS as $key) $facts[$key] = $frame['facts'][$key];
        $target = ['schema_version' => 1, 'closure_id' => $requestId, 'revision' => 1] + $facts;
        $target['reviewer'] = $actor;
        $target['recorded_at_utc'] = gmdate('Y-m-d\TH:i:s\Z', $recordedAt);
        Workflow::validateClosureRecord($target, $now);
        return $target;
    }

    /** Refreshing a bounded observation cannot renew the exact owner's creation deadline. */
    public static function fingerprint(array $frame, int $now): string
    {
        self::validate($frame, $now);
        unset($frame['observed_at'], $frame['valid_until']);
        return Workflow::digest($frame);
    }

    private static function validate(array $frame, int $now): void
    {
        self::keys($frame, ['contract', 'facts', 'source_hash', 'source_generation', 'observed_at', 'valid_until',
            'authoritative', 'complete', 'sender_fence', 'retirement_intent', 'mailbox', 'mailbox_coverage',
            'includes_trash', 'attempt_count', 'send_started_at_utc', 'sent_at_utc']);
        if ($frame['contract'] !== self::CONTRACT || !is_array($frame['facts']) || $frame['authoritative'] !== true
            || $frame['complete'] !== true || $frame['sender_fence'] !== 'ABSENT' || $frame['retirement_intent'] !== 'NONE'
            || $frame['mailbox'] !== 'marketing@blackswanrealestate.ae' || $frame['mailbox_coverage'] !== 'COMPLETE'
            || $frame['includes_trash'] !== true) self::fail('COLLECTION_SOURCE_UNVERIFIED');
        self::keys($frame['facts'], self::FACTS);
        foreach (['source_hash', 'source_generation'] as $key) {
            if (!is_string($frame[$key]) || !preg_match('/^[a-f0-9]{64}$/D', $frame[$key])) self::fail('COLLECTION_SOURCE_INVALID');
        }
        if ($now < 1 || !is_int($frame['observed_at']) || !is_int($frame['valid_until']) || $frame['observed_at'] < 1
            || $frame['observed_at'] > $now || $frame['valid_until'] <= $frame['observed_at']
            || $frame['valid_until'] - $frame['observed_at'] > 900 || $now >= $frame['valid_until']) self::fail('COLLECTION_SOURCE_STALE');
        $facts = $frame['facts'];
        // Validate all facts and chronology independently of any owner-selected target timestamp.
        $probe = ['schema_version' => 1, 'closure_id' => $facts['request_id'], 'revision' => 1] + $facts;
        $probe['reviewer'] = 'collection-source-validation';
        $probe['recorded_at_utc'] = gmdate('Y-m-d\TH:i:s\Z', $frame['observed_at']);
        Workflow::validateClosureRecord($probe, $now);
        if (!is_int($frame['attempt_count']) || $frame['attempt_count'] < 0 || $frame['attempt_count'] > 1000000) self::fail('COLLECTION_OUTBOX_UNVERIFIED');
        if ($facts['email_status'] === 'SENT') {
            $start = self::stamp($frame['send_started_at_utc']);
            $sent = self::stamp($frame['sent_at_utc']);
            if ($frame['attempt_count'] < 1 || $facts['mail_message_ids'] === [] || $start < self::stamp($facts['accepted_at_utc'])
                || $sent < $start || $sent > $frame['observed_at']) self::fail('COLLECTION_OUTBOX_UNVERIFIED');
        } elseif (!in_array($facts['email_status'], ['QUEUED', 'RETRY_WAIT', 'NEEDS_REVIEW'], true)
            || $facts['mail_message_ids'] !== [] || $frame['attempt_count'] !== 0
            || $frame['send_started_at_utc'] !== null || $frame['sent_at_utc'] !== null) self::fail('COLLECTION_OUTBOX_UNVERIFIED');
    }

    private static function stamp($value): int
    {
        if (!is_string($value) || !preg_match('/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/D', $value)) self::fail('COLLECTION_SOURCE_TIME_INVALID');
        $stamp = strtotime($value);
        if ($stamp === false || gmdate('Y-m-d\TH:i:s\Z', $stamp) !== $value) self::fail('COLLECTION_SOURCE_TIME_INVALID');
        return $stamp;
    }

    private static function keys(array $value, array $expected): void
    {
        $keys = array_keys($value); sort($keys); sort($expected);
        if ($keys !== $expected) self::fail('COLLECTION_SOURCE_INVALID');
    }

    private static function fail(string $code): never { throw new Failure($code); }
}
