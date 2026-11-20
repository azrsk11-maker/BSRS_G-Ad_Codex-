<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;

require_once __DIR__ . '/../closed-enquiry-retention/Workflow.php';
require_once __DIR__ . '/../closed-enquiry-retention/RetirementJournal.php';
require_once __DIR__ . '/../closed-enquiry-retention/ClosureCollectionJournal.php';
require_once __DIR__ . '/../closed-enquiry-retention/LeaseBoundWpdb.php';

/** Private, independently operated service. A PHP array is never authentication. */
interface AnchorTransport
{
    public function current(string $scope, string $challenge): array;
    /** Service MUST enforce durable compare-and-swap, including initial revision zero. */
    public function advance(string $scope, array $before, array $after, string $challenge): array;
}

/** Existing private custody supplies keys; this candidate creates no provider/signing key. */
interface EncryptionKeys
{
    public function activeId(): string;
    public function key(string $id): string;
}

/** Trusted server-side review/provider ports; absent dependencies remain held. */
interface OperationalEvidence
{
    public function approved(string $actor, string $action, string $digest, int $now): bool;
    public function mailReceipt(string $actor, string $digest, string $messageId): ?array;
    /** Must validate original wire/Intake26/outbox/receiver identity and current sender fence. */
    public function captureCustody(array $closure, array $record, string $request, int $now): bool;
    public function collectionCustody(array $target, int $now): bool;
    public function retirementCustody(array $record, array $proof, int $now): bool;
}

interface CaptureProducer
{
    /** Verify exact reviewed code, common repository/database, schema and ENFORCED admission readback. */
    public function assertCurrent(\BSRE\ClosedRetention\LeaseBoundWpdb $db): void;
    public function assertPurposeRecord(array $row): void;
}

final class HeldEvidence implements OperationalEvidence
{
    public function approved(string $actor, string $action, string $digest, int $now): bool { return false; }
    public function mailReceipt(string $actor, string $digest, string $messageId): ?array { return null; }
    public function captureCustody(array $closure, array $record, string $request, int $now): bool { return false; }
    public function collectionCustody(array $target, int $now): bool { return false; }
    public function retirementCustody(array $record, array $proof, int $now): bool { return false; }
}

/** Runtime-owned binding. No public request parameter, options hook or automatic activation. */
final class RuntimePolicy
{
    public function __construct(public readonly string $database, public readonly string $prefix,
        public readonly string $origin, public readonly int $ownerId, public readonly bool $isolatedLab = false)
    {
        if (!preg_match('/^[A-Za-z0-9_]{1,64}$/D', $database)
            || !preg_match('/^[A-Za-z0-9_]{1,40}_$/D', $prefix) || $ownerId < 1) self::fail('G5_BINDING_INVALID');
        if ($isolatedLab) {
            if ($database !== 'bsre_synthetic' || $prefix !== 'g5_durable_synthetic_' || $origin !== 'http://bsre.invalid') self::fail('G5_LAB_BINDING_INVALID');
        } elseif (!in_array($origin, ['https://blackswanrealestate.ae', 'https://www.blackswanrealestate.ae'], true)) self::fail('G5_DOMAIN_REQUIRED');
    }

    public function actor(): string
    {
        if (!function_exists('is_user_logged_in') || !is_user_logged_in()
            || get_current_user_id() !== $this->ownerId || !current_user_can('manage_options')
            || !function_exists('home_url') || rtrim(home_url(), '/') !== $this->origin) self::fail('G5_OWNER_DOMAIN_REQUIRED');
        if ($this->isolatedLab && (!defined('BSRE_G5_DURABLE_LAB') || BSRE_G5_DURABLE_LAB !== true
            || !function_exists('wp_get_environment_type') || wp_get_environment_type() !== 'local')) self::fail('G5_ISOLATED_LAB_REQUIRED');
        return 'wp-user:' . $this->ownerId;
    }

    public function scope(): string { return hash('sha256', 'bsre-g5-durable-v1|' . $this->database . '|' . $this->prefix . '|' . $this->origin); }
    public static function fail(string $code): never { throw new \BSRE\ClosedRetention\Failure($code); }
    public static function hash(string $value): void { if (!preg_match('/^[a-f0-9]{64}$/D', $value)) self::fail('G5_HASH_INVALID'); }
}

/** Rechecks nominated owner, exact approved action and independent evidence on each call. */
final class OwnerAuthority implements \BSRE\ClosedRetention\Authority
{
    public function __construct(private RuntimePolicy $policy, private OperationalEvidence $evidence = new HeldEvidence()) {}
    public function boundTo(RuntimePolicy $policy, OperationalEvidence $evidence): bool { return $this->policy === $policy && $this->evidence === $evidence; }
    public function canReview(string $actor): bool
    {
        try { return hash_equals($this->policy->actor(), $actor); } catch (\Throwable $e) { return false; }
    }
    public function canApply(string $actor, string $planDigest, int $now, string $action): bool
    {
        try {
            RuntimePolicy::hash($planDigest);
            return $this->canReview($actor) && $now > 0 && abs(time() - $now) <= 5
                && in_array($action, ['PURGE', 'EXPIRE_PRIVATE_JOURNAL', 'COLLECT', 'EDIT_CLOSURE', 'INITIALIZE_JOURNAL', 'RETIRE_NO_COPY'], true)
                && $this->evidence->approved($actor, $action, $planDigest, $now);
        } catch (\Throwable $e) { return false; }
    }
    public function mailReceipt(string $actor, string $planDigest, string $messageId): ?array
    {
        return $this->canReview($actor) ? $this->evidence->mailReceipt($actor, $planDigest, $messageId) : null;
    }
}
