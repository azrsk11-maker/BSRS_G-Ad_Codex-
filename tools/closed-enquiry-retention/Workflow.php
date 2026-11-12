<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;

require_once __DIR__ . '/../consent-retention/RetentionInventory.php';
require_once __DIR__ . '/NoMailCopy.php';

/** The adapter serializes closure edits with this lock; journal writes commit immediately. */
interface Journal
{
    public function locked(string $closureId, callable $operation);
    public function closure(string $closureId): ?array;
    public function journal(string $planId): ?array;
    public function save(array &$record): void;
    public function markHistoryIncomplete(): void;
    public function historyIncomplete(): bool;
    public function pinAdmissionFloor(string $policyHash): void;
    public function admissionFloor(): ?string;
    public function forget(string $closureId, string $planId, bool $keepClosure = false): void;
}

/** Internal protected writer; the same Journal closure lease must already be held. */
interface ClosureWriter
{
    public function replaceClosure(array $before, array $after): void;
}

/** Stable keys only. removeExact must compare the full binding and never delete by row number. */
interface ResourceAdapter
{
    public function inventory(string $requestId): array;
    /** null means confirmed absence in the complete authorized surface, including Trash for mail. */
    public function read(string $key): ?array;
    public function removeExact(array $binding): void;
}

interface Authority
{
    public function canReview(string $actor): bool;
    public function canApply(string $actor, string $planDigest, int $now, string $action): bool;
    public function mailReceipt(string $actor, string $planDigest, string $messageId): ?array;
}

/** Runtime-owned readback, never an owner-supplied true/complete flag. */
interface Admission
{
    public function readback(int $now): ?array;
}

final class UnverifiedAdmission implements Admission
{
    public function readback(int $now): ?array { return null; }
}

final class Workflow
{
    private const STORES = ['email', 'outcome', 'capture', 'intake'];
    private const MAX_RESOURCES = 100;
    private const PLAN_SECONDS = 900;
    private Journal $journal;
    private array $adapters;
    private Authority $authority;
    private Admission $admission;
    private NoMailCopy $noMailCopy;

    public function __construct(Journal $journal, array $adapters, Authority $authority, ?Admission $admission = null,
        ?NoMailCopy $noMailCopy = null)
    {
        $keys = array_keys($adapters);
        sort($keys);
        $expected = self::STORES;
        sort($expected);
        if ($keys !== $expected) self::fail('ADAPTER_SET_INVALID');
        foreach ($adapters as $adapter) if (!$adapter instanceof ResourceAdapter) self::fail('ADAPTER_SET_INVALID');
        $this->journal = $journal;
        $this->adapters = $adapters;
        $this->authority = $authority;
        $this->admission = $admission ?? new UnverifiedAdmission();
        $this->noMailCopy = $noMailCopy ?? new UnverifiedNoMailCopy();
    }

    /** Public result contains counts and codes only. */
    public function preview(string $closureId, int $now): array
    {
        self::lab();
        self::uuid($closureId);
        return $this->journal->locked($closureId, function () use ($closureId, $now) {
            try {
                $this->proposal($closureId, $now);
                return self::summary('READY_FOR_OWNER_REVIEW', []);
            } catch (\RuntimeException $error) {
                return self::summary('HELD', [self::safeCode($error)]);
            }
        });
    }

    /** Private return value. Keep the plan out of logs, analytics and public repositories. */
    public function prepare(string $closureId, string $actor, int $now): array
    {
        self::lab();
        self::uuid($closureId);
        if (!$this->authority->canReview($actor)) self::fail('OWNER_REVIEW_REQUIRED');
        return $this->journal->locked($closureId, function () use ($closureId, $now) {
            $plan = $this->proposal($closureId, $now);
            $plan['digest'] = self::digest($plan);
            return $plan;
        });
    }

    public function execute(array $plan, string $actor, int $now): array
    {
        self::lab();
        try {
            self::validatePlan($plan);
            if (!$this->authority->canApply($actor, $plan['digest'], $now, 'PURGE')) self::fail('EXACT_APPROVAL_REQUIRED');
        } catch (\Throwable $error) { return self::summary('HELD', [self::safeCode($error)]); }
        try { return $this->journal->locked($plan['closure_id'], function () use ($plan, $actor, $now) {
            $record = $this->journal->journal($plan['digest']);
            if ($record === null) {
                if ($now < $plan['created_at'] || $now >= $plan['expires_at']) self::fail('PLAN_EXPIRED');
                $fresh = $this->proposal($plan['closure_id'], $now);
                if ($fresh['closure_hash'] !== $plan['closure_hash'] || $fresh['resources'] !== $plan['resources']
                    || $fresh['admission_hash'] !== $plan['admission_hash']
                    || ($fresh['no_mail_copy'] ?? null) !== ($plan['no_mail_copy'] ?? null)) self::fail('PLAN_STALE');
                $record = ['plan' => $plan, 'revision' => 0, 'state' => 'PENDING', 'started_at' => $now,
                    'completed_at' => null, 'steps' => array_fill(0, count($plan['resources']), 'PENDING'),
                    'intent_at' => array_fill(0, count($plan['resources']), null), 'code' => ''];
                if (isset($plan['no_mail_copy'])) $record['no_copy_cleanup'] = null;
                $this->journal->save($record);
            } elseif ($record['plan'] !== $plan) {
                self::fail('JOURNAL_PLAN_CONFLICT');
            }
            self::validateJournal($record, $now);
            if ($record['state'] === 'COMPLETE') {
                if (!$this->journal->historyIncomplete()) return $this->hold($record, 'HISTORY_MARKER_UNVERIFIED');
                if (isset($plan['no_mail_copy'])) {
                    try { $this->recheck($plan, $now, false, null, true); }
                    catch (\Throwable $error) { return $this->hold($record, self::safeCode($error)); }
                }
                try { $this->assertRemaining($plan, $record['steps']); }
                catch (\Throwable $error) { return $this->hold($record, self::safeCode($error)); }
                foreach ($plan['resources'] as $resource) {
                    if ($this->adapters[$resource['store']]->read($resource['binding']['key']) !== null) {
                        return $this->hold($record, 'RESTORED_RESOURCE_REQUIRES_REVIEW');
                    }
                }
                return self::summary('COMPLETE', [], count($record['steps']));
            }
            if ($now < $record['started_at'] || $now >= $record['started_at'] + 30 * 86400) {
                return $this->hold($record, 'RECOVERY_WINDOW_EXPIRED');
            }
            try {
                $this->recheck($plan, $now);
                if ($this->journal->historyIncomplete() && $this->journal->admissionFloor() === null) self::fail('ADMISSION_FLOOR_UNVERIFIED');
                $this->journal->pinAdmissionFloor($plan['admission_hash']);
                if ($this->journal->admissionFloor() !== $plan['admission_hash']) self::fail('ADMISSION_FLOOR_UNVERIFIED');
                // Durable before any irreversible provider action. This method never clears it.
                $this->journal->markHistoryIncomplete();
                if (!$this->journal->historyIncomplete()) self::fail('HISTORY_MARKER_UNVERIFIED');
                foreach ($plan['resources'] as $index => $resource) {
                    if ($record['steps'][$index] === 'CONFIRMED_ABSENT') continue;
                    $this->assertRemaining($plan, $record['steps']);
                    $this->recheck($plan, $now);
                    if (!$this->journal->historyIncomplete()) self::fail('HISTORY_MARKER_UNVERIFIED');
                    $adapter = $this->adapters[$resource['store']];
                    $current = $adapter->read($resource['binding']['key']);
                    if ($current === null) {
                        if ($record['steps'][$index] !== 'INTENT_RECORDED') self::fail('RESOURCE_CHANGED_BEFORE_INTENT');
                        if ($resource['store'] === 'email') {
                            $this->verifyMailReceipt($actor, $plan, $resource['binding'], $record['intent_at'][$index], $now);
                        }
                        $record['steps'][$index] = 'CONFIRMED_ABSENT';
                        $this->journal->save($record);
                        continue;
                    }
                    if (self::binding($resource['store'], $current) !== $resource['binding']) self::fail('RESOURCE_BINDING_CHANGED');
                    if ($record['steps'][$index] === 'PENDING') {
                        $record['steps'][$index] = 'INTENT_RECORDED';
                        $record['intent_at'][$index] = $now;
                        $record['state'] = 'APPLYING';
                        $record['code'] = '';
                        $this->journal->save($record);
                    }
                    if ($resource['store'] === 'email') return self::summary('AWAITING_OWNER_MAIL_ACTION', []);
                    // No SQL transaction is claimed across providers. Readback resolves lost replies.
                    $adapter->removeExact($resource['binding']);
                    if ($adapter->read($resource['binding']['key']) !== null) self::fail('DELETE_UNCONFIRMED');
                    $record['steps'][$index] = 'CONFIRMED_ABSENT';
                    $this->journal->save($record);
                }
                $this->recheck($plan, $now, false, null, true);
                $this->assertAbsent($plan, $record['steps']);
                $record['state'] = 'COMPLETE';
                $record['completed_at'] = $now;
                $record['code'] = '';
                $this->journal->save($record);
                return self::summary('COMPLETE', [], count($record['steps']));
            } catch (\Throwable $error) {
                return $this->hold($record, self::safeCode($error));
            }
        }); } catch (\Throwable $error) { return self::summary('HELD', [self::safeCode($error)]); }
    }

    /** Private, exact mailbox operation for the already-journaled owner step. */
    public function ownerMailAction(array $plan, string $actor, int $now): ?array
    {
        self::lab(); self::validatePlan($plan);
        if (!$this->authority->canApply($actor, $plan['digest'], $now, 'PURGE')) self::fail('EXACT_APPROVAL_REQUIRED');
        return $this->journal->locked($plan['closure_id'], function () use ($plan, $now) {
            $record = $this->journal->journal($plan['digest']);
            if ($record === null || $record['plan'] !== $plan) return null;
            self::validateJournal($record, $now);
            if ($now >= $record['started_at'] + 30 * 86400 || !$this->journal->historyIncomplete()
                || $this->journal->admissionFloor() !== $plan['admission_hash']) return null;
            $this->recheck($plan, $now);
            $this->assertRemaining($plan, $record['steps']);
            foreach ($plan['resources'] as $index => $resource) {
                if ($resource['store'] !== 'email') break;
                if ($record['steps'][$index] !== 'INTENT_RECORDED') continue;
                $current = $this->adapters['email']->read($resource['binding']['key']);
                if ($current === null) return null;
                if (self::binding('email', $current) !== $resource['binding']) self::fail('RESOURCE_BINDING_CHANGED');
                return ['plan_digest' => $plan['digest'], 'binding' => $resource['binding'], 'intent_at' => $record['intent_at'][$index]];
            }
            return null;
        });
    }

    private function verifyMailReceipt(string $actor, array $plan, array $binding, int $intentAt, int $now): void
    {
        $receipt = $this->authority->mailReceipt($actor, $plan['digest'], $binding['message_id']);
        if ($receipt === null) self::fail('OWNER_MAIL_RECEIPT_REQUIRED');
        self::keys($receipt, ['schema_version', 'actor', 'plan_digest', 'mailbox', 'message_id', 'binding_hash',
            'observed_at', 'evidence_reference', 'evidence_hash']);
        if ($receipt['schema_version'] !== 1 || $receipt['actor'] !== $actor || $receipt['plan_digest'] !== $plan['digest']
            || $receipt['mailbox'] !== $binding['mailbox'] || $receipt['message_id'] !== $binding['message_id']
            || $receipt['binding_hash'] !== self::digest($binding) || !is_int($receipt['observed_at'])
            || $receipt['observed_at'] < $intentAt || $receipt['observed_at'] > $now) self::fail('OWNER_MAIL_RECEIPT_CONFLICT');
        self::bounded($receipt['evidence_reference'], 256); self::hash($receipt['evidence_hash']);
    }

    /** Removes completed private journal/closure identifiers after the recovery window. */
    public function expire(array $plan, string $actor, int $now): array
    {
        self::lab(); self::validatePlan($plan);
        if (!$this->authority->canApply($actor, $plan['digest'], $now, 'EXPIRE_PRIVATE_JOURNAL')) self::fail('EXACT_APPROVAL_REQUIRED');
        return $this->journal->locked($plan['closure_id'], function () use ($plan, $now) {
            $record = $this->journal->journal($plan['digest']);
            if ($record === null) return self::summary('NO_PRIVATE_JOURNAL', []);
            if ($record['plan'] !== $plan) self::fail('JOURNAL_PLAN_CONFLICT');
            self::validateJournal($record, $now);
            if ($record['state'] !== 'COMPLETE') {
                if ($now < $record['started_at'] + 30 * 86400) return self::summary('HELD', ['RECOVERY_WINDOW_ACTIVE']);
                $this->journal->markHistoryIncomplete();
                if (!$this->journal->historyIncomplete()) return self::summary('HELD', ['HISTORY_MARKER_UNVERIFIED']);
                if (isset($plan['no_mail_copy'])) {
                    try { $this->forgetNoMailCopy($plan, $record, $now); }
                    catch (\Throwable $error) { return self::summary('HELD', [self::safeCode($error)]); }
                }
                $this->journal->forget($plan['closure_id'], $plan['digest'], true);
                return self::summary('PRIVATE_JOURNAL_EXPIRED', ['MANUAL_RECONCILIATION_REQUIRED']);
            }
            if ($now < $record['completed_at'] + 30 * 86400) return self::summary('HELD', ['RECOVERY_WINDOW_ACTIVE']);
            if (!$this->journal->historyIncomplete()) return self::summary('HELD', ['HISTORY_MARKER_UNVERIFIED']);
            try {
                $this->recheck($plan, $now, true, $record['no_copy_cleanup'] ?? null, true); $this->assertAbsent($plan, $record['steps']);
                if (isset($plan['no_mail_copy'])) $this->forgetNoMailCopy($plan, $record, $now);
            }
            catch (\Throwable $error) { return self::summary('HELD', [self::safeCode($error)]); }
            $this->journal->forget($plan['closure_id'], $plan['digest']);
            return self::summary('PRIVATE_JOURNAL_EXPIRED', []);
        });
    }

    private function hold(array $record, string $code): array
    {
        $done = count(array_filter($record['steps'], fn($step) => $step === 'CONFIRMED_ABSENT'));
        $record['state'] = 'HELD';
        $record['completed_at'] = null;
        $record['code'] = $code;
        try { $this->journal->save($record); }
        catch (\Throwable $error) { return self::summary('HELD', ['JOURNAL_STORAGE_UNCERTAIN'], $done); }
        return self::summary('HELD', [$code], $done);
    }

    private function proposal(string $closureId, int $now): array
    {
        if ($now <= 0) self::fail('CLOCK_INVALID');
        $closure = $this->journal->closure($closureId);
        if ($closure === null) self::fail('CLOSURE_NOT_FOUND');
        self::validateClosureRecord($closure, $now, true);
        if ($closure['closure_id'] !== $closureId) self::fail('CLOSURE_IDENTITY_CONFLICT');
        $noCopy = $closure['email_status'] === 'RETIRED_NO_COPY';
        if ($closure['email_status'] !== 'SENT' && !$noCopy) self::fail('OUTBOX_NOT_RECONCILED');
        $gate = $this->verifiedAdmission($now);
        $resources = [];
        foreach (self::STORES as $store) {
            $inventory = $this->adapters[$store]->inventory($closure['request_id']);
            if (!array_is_list($inventory) || count($inventory) > self::MAX_RESOURCES) self::fail('INVENTORY_INVALID');
            foreach ($inventory as $binding) {
                $binding = self::binding($store, $binding);
                if ($binding['request_id'] !== $closure['request_id'] || $binding['lead_id'] !== $closure['lead_id']
                    || $binding['event_id'] !== $closure['event_id']) self::fail('RESOURCE_LINK_CONFLICT');
                $resources[] = ['store' => $store, 'binding' => $binding];
            }
        }
        if (count($resources) > self::MAX_RESOURCES) self::fail('INVENTORY_INVALID');
        usort($resources, fn($a, $b) => [array_search($a['store'], self::STORES, true), $a['binding']['key']]
            <=> [array_search($b['store'], self::STORES, true), $b['binding']['key']]);
        $keys = []; $counts = array_fill_keys(self::STORES, 0); $outcomes = []; $mail = [];
        foreach ($resources as $resource) {
            $key = $resource['store'] . '/' . $resource['binding']['key'];
            if (isset($keys[$key])) self::fail('DUPLICATE_RESOURCE');
            $keys[$key] = true;
            $counts[$resource['store']]++;
            if ($resource['store'] === 'outcome') $outcomes[] = $resource['binding']['key'];
            if ($resource['store'] === 'email') $mail[] = $resource['binding']['key'];
        }
        sort($outcomes); sort($mail);
        if ($counts['intake'] !== 1 || $counts['capture'] !== 1 || ($noCopy ? $counts['email'] !== 0 : $counts['email'] < 1)
            || $outcomes !== $closure['outcome_ids'] || $mail !== $closure['mail_message_ids']) self::fail('LINKAGE_INCOMPLETE');
        $plan = ['schema_version' => 1, 'closure_id' => $closureId, 'closure_hash' => self::digest($closure),
            'admission_hash' => self::admissionHash($gate), 'created_at' => $now, 'expires_at' => $now + self::PLAN_SECONDS,
            'resources' => $resources];
        if ($noCopy) {
            $intake = array_values(array_filter($resources, fn($resource) => $resource['store'] === 'intake'))[0];
            $scope = NoMailCopyProof::scope($closure, $plan['admission_hash'], $intake['binding']['fingerprint']);
            $proofHash = NoMailCopyProof::verify($this->noMailCopy->readback($scope, $now), $scope, $now);
            $plan['no_mail_copy'] = ['scope' => $scope, 'proof_hash' => $proofHash];
        }
        return $plan;
    }

    private function recheck(array $plan, int $now, bool $cleanup = false, ?array $ticket = null, bool $requireIntakeAbsent = false): void
    {
        $closure = $this->journal->closure($plan['closure_id']);
        if ($closure === null || self::digest($closure) !== $plan['closure_hash']) self::fail('CLOSURE_CHANGED_OR_REOPENED');
        if (self::admissionHash($this->verifiedAdmission($now)) !== $plan['admission_hash']) self::fail('ADMISSION_CHANGED');
        $floor = $this->journal->admissionFloor();
        if ($floor !== null && $floor !== $plan['admission_hash']) self::fail('ADMISSION_FLOOR_CONFLICT');
        if (isset($plan['no_mail_copy'])) {
            $scope = $plan['no_mail_copy']['scope'];
            if ($scope !== NoMailCopyProof::scope($closure, $plan['admission_hash'], $scope['fingerprint'])) self::fail('NO_COPY_SCOPE_CONFLICT');
            $readback = $this->noMailCopy->readback($scope, $now, $cleanup, $ticket);
            $hash = NoMailCopyProof::verify($readback, $scope, $now, $cleanup);
            if ($hash !== $plan['no_mail_copy']['proof_hash']) self::fail('NO_COPY_FENCE_CHANGED');
            if ($requireIntakeAbsent && $readback['row_state'] !== 'ABSENT') self::fail('NO_COPY_INTAKE_NOT_ABSENT');
        }
    }

    private function forgetNoMailCopy(array $plan, array &$record, int $now): void
    {
        $scope = $plan['no_mail_copy']['scope'];
        if (($record['no_copy_cleanup'] ?? null) === null) {
            $ticket = $this->noMailCopy->prepareCleanup($scope, $now);
            if ($ticket === null || strlen(json_encode($ticket, JSON_THROW_ON_ERROR)) > 16384) self::fail('NO_COPY_CUSTODY_UNVERIFIED');
            $record['no_copy_cleanup'] = $ticket;
            $this->journal->save($record); // Durable signed cleanup intent BEFORE deleting its receiver fence.
        }
        $ticket = $record['no_copy_cleanup'];
        $hash = NoMailCopyProof::verify($this->noMailCopy->readback($scope, $now, true, $ticket), $scope, $now, true);
        if ($hash !== $plan['no_mail_copy']['proof_hash']) self::fail('NO_COPY_FENCE_CHANGED');
        if (!$this->noMailCopy->forget($scope, $now, $ticket)) self::fail('NO_COPY_CUSTODY_UNCONFIRMED');
    }

    private function assertRemaining(array $plan, array $steps): void
    {
        $request = $plan['resources'][0]['binding']['request_id'];
        $expected = [];
        foreach ($plan['resources'] as $index => $resource) {
            $expected[$resource['store'] . '/' . $resource['binding']['key']] = [$resource, $steps[$index]];
        }
        $seen = [];
        foreach (self::STORES as $store) {
            $rows = $this->adapters[$store]->inventory($request);
            if (!array_is_list($rows) || count($rows) > self::MAX_RESOURCES) self::fail('INVENTORY_INVALID');
            foreach ($rows as $row) {
                $binding = self::binding($store, $row);
                $key = $store . '/' . $binding['key'];
                if (isset($seen[$key]) || !isset($expected[$key])) self::fail('RESOURCE_SCOPE_CHANGED');
                [$resource, $state] = $expected[$key];
                if ($binding !== $resource['binding'] || $state === 'CONFIRMED_ABSENT') self::fail('RESOURCE_SCOPE_CHANGED');
                $seen[$key] = true;
            }
        }
        foreach ($expected as $key => [$resource, $state]) {
            if (!isset($seen[$key]) && $state === 'PENDING') self::fail('RESOURCE_CHANGED_BEFORE_INTENT');
        }
    }

    private function assertAbsent(array $plan, array $steps): void
    {
        $this->assertRemaining($plan, $steps);
        foreach ($plan['resources'] as $resource) {
            if ($this->adapters[$resource['store']]->read($resource['binding']['key']) !== null) self::fail('RESOURCE_SCOPE_CHANGED');
        }
    }

    private function verifiedAdmission(int $now): array
    {
        $value = $this->admission->readback($now);
        if ($value === null) self::fail('ADMISSION_UNVERIFIED');
        self::keys($value, ['wp', 'receiver', 'source_hashes', 'restore_policy_hash', 'evidence_reference', 'evidence_hash', 'observed_at', 'expires_at']);
        self::bounded($value['evidence_reference'], 256);
        self::hash($value['evidence_hash']);
        self::hash($value['restore_policy_hash']);
        if (!is_int($value['observed_at']) || !is_int($value['expires_at']) || $value['observed_at'] > $now
            || $value['expires_at'] <= $now || $value['expires_at'] > $value['observed_at'] + 300) self::fail('ADMISSION_STALE');
        self::keys($value['source_hashes'], ['wp', 'receiver']);
        foreach (['wp', 'receiver'] as $surface) {
            self::hash($value['source_hashes'][$surface]);
            $gate = $value[$surface];
            $keys = ['contract', 'mode', 'generation', 'activated_at', 'max_age_seconds', 'audience'];
            if ($surface === 'wp') $keys = array_merge($keys, ['routes_installed', 'store_installed']);
            self::keys($gate, $keys);
            if ($gate['contract'] !== 'bsre-retention-admission-v1' || $gate['mode'] !== 'ENFORCED'
                || $gate['max_age_seconds'] !== 900 || !is_int($gate['activated_at'])
                || $gate['activated_at'] <= 0 || $gate['activated_at'] > $now) self::fail('ADMISSION_UNVERIFIED');
            self::hash($gate['generation']);
            self::hash($gate['audience']);
            if ($surface === 'wp' && ($gate['routes_installed'] !== true || $gate['store_installed'] !== true)) self::fail('ADMISSION_UNVERIFIED');
        }
        if ($value['wp']['generation'] !== $value['receiver']['generation']
            || $value['wp']['audience'] !== $value['receiver']['audience']
            || $value['wp']['activated_at'] !== $value['receiver']['activated_at']) self::fail('ADMISSION_GENERATION_CONFLICT');
        return $value;
    }

    private static function admissionHash(array $readback): string
    {
        // Fresh authenticated readback may rotate; the approved configuration cannot.
        return self::digest(['wp' => $readback['wp'], 'receiver' => $readback['receiver'],
            'source_hashes' => $readback['source_hashes'], 'restore_policy_hash' => $readback['restore_policy_hash']]);
    }

    /** Canonical record/chronology checks shared by protected amendments and due retirement. */
    public static function validateClosureRecord(array $value, int $now, bool $requireDue = false): void
    {
        self::closureRecord($value);
        if ($now <= 0) self::fail('CLOCK_INVALID');
        if ($requireDue && $value['status'] === 'OPEN') self::fail('ENQUIRY_OPEN');
        $accepted = self::stamp($value['accepted_at_utc']);
        $recorded = self::stamp($value['recorded_at_utc']);
        if ($accepted > $recorded || $recorded > $now) self::fail('CLOSURE_TIME_INVALID');
        if ($value['status'] !== 'OPEN') {
            $closed = self::stamp($value['closed_at_utc']);
            if ($closed < $accepted || $closed > $recorded) self::fail('CLOSURE_TIME_INVALID');
            if ($requireDue && \BSRE\RetentionReview\RetentionInventory::anniversary($closed) > $now) self::fail('RETENTION_NOT_DUE');
        }
    }

    private static function closureRecord(array $value): void
    {
        self::keys($value, ['schema_version', 'closure_id', 'revision', 'status', 'request_id', 'lead_id', 'event_id',
            'accepted_at_utc', 'closed_at_utc', 'recorded_at_utc', 'reviewer', 'evidence_reference', 'evidence_hash',
            'outcome_ids', 'mail_message_ids', 'email_status']);
        if ($value['schema_version'] !== 1 || !is_int($value['revision']) || $value['revision'] < 1
            || !in_array($value['status'], ['OPEN', 'CLOSED', 'UNSUCCESSFUL'], true)) self::fail('CLOSURE_INVALID');
        foreach (['closure_id', 'request_id'] as $key) self::uuid($value[$key]);
        self::receipt($value['lead_id'], 'BSRE-'); self::receipt($value['event_id'], 'evt_');
        foreach (['reviewer', 'evidence_reference'] as $key) self::bounded($value[$key], 256);
        self::hash($value['evidence_hash']);
        self::stamp($value['accepted_at_utc']); self::stamp($value['recorded_at_utc']);
        if ($value['status'] !== 'OPEN') self::stamp($value['closed_at_utc']);
        elseif ($value['closed_at_utc'] !== null) self::fail('CLOSURE_INVALID');
        foreach (['outcome_ids', 'mail_message_ids'] as $key) {
            if (!is_array($value[$key]) || !array_is_list($value[$key]) || count($value[$key]) > self::MAX_RESOURCES) self::fail('CLOSURE_INVALID');
            $sorted = $value[$key]; sort($sorted);
            if ($sorted !== $value[$key] || count(array_unique($sorted)) !== count($sorted)) self::fail('CLOSURE_INVALID');
            foreach ($sorted as $id) self::bounded($id, 256);
        }
        self::bounded($value['email_status'], 32);
    }

    private static function binding(string $store, array $value): array
    {
        $keys = ['key', 'request_id', 'request_ids', 'lead_id', 'event_id', 'fingerprint', 'evidence_reference', 'evidence_hash'];
        if ($store === 'email') $keys = array_merge($keys, ['mailbox', 'message_id', 'rfc822_message_id']);
        self::keys($value, $keys);
        self::bounded($value['key'], 256); self::uuid($value['request_id']);
        if ($value['request_ids'] !== [$value['request_id']]) self::fail('SHARED_RESOURCE_REQUIRES_REVIEW');
        self::receipt($value['lead_id'], 'BSRE-'); self::receipt($value['event_id'], 'evt_');
        self::hash($value['fingerprint']); self::hash($value['evidence_hash']); self::bounded($value['evidence_reference'], 256);
        if ($store === 'email') {
            if ($value['mailbox'] !== 'marketing@blackswanrealestate.ae' || $value['message_id'] !== $value['key']) self::fail('MAIL_BINDING_INVALID');
            self::bounded($value['rfc822_message_id'], 256);
        }
        return self::sorted($value);
    }

    private static function validatePlan(array $plan): void
    {
        $keys = ['schema_version', 'closure_id', 'closure_hash', 'admission_hash', 'created_at', 'expires_at', 'resources', 'digest'];
        if (array_key_exists('no_mail_copy', $plan)) $keys[] = 'no_mail_copy';
        self::keys($plan, $keys);
        self::uuid($plan['closure_id']); self::hash($plan['digest']);
        $copy = $plan; unset($copy['digest']);
        if ($plan['schema_version'] !== 1 || !hash_equals(self::digest($copy), $plan['digest'])
            || !is_int($plan['created_at']) || !is_int($plan['expires_at'])
            || $plan['expires_at'] !== $plan['created_at'] + self::PLAN_SECONDS
            || !is_array($plan['resources']) || !array_is_list($plan['resources'])
            || count($plan['resources']) > self::MAX_RESOURCES) self::fail('PLAN_INVALID');
        self::hash($plan['closure_hash']); self::hash($plan['admission_hash']);
        if (isset($plan['no_mail_copy'])) {
            self::keys($plan['no_mail_copy'], ['scope', 'proof_hash']);
            self::hash($plan['no_mail_copy']['proof_hash']);
            $scope = $plan['no_mail_copy']['scope'];
            self::keys($scope, ['contract', 'closure_id', 'closure_revision', 'closure_hash', 'request_id',
                'lead_id', 'event_id', 'fingerprint', 'admission_hash']);
            if ($scope['contract'] !== NoMailCopyProof::CONTRACT || $scope['closure_id'] !== $plan['closure_id']
                || $scope['closure_hash'] !== $plan['closure_hash'] || $scope['admission_hash'] !== $plan['admission_hash']
                || !is_int($scope['closure_revision']) || $scope['closure_revision'] < 1) self::fail('PLAN_INVALID');
            self::uuid($scope['request_id']); self::receipt($scope['lead_id'], 'BSRE-'); self::receipt($scope['event_id'], 'evt_');
            self::hash($scope['fingerprint']);
        }
        foreach ($plan['resources'] as $resource) {
            self::keys($resource, ['store', 'binding']);
            if (!in_array($resource['store'], self::STORES, true) || !is_array($resource['binding'])) self::fail('PLAN_INVALID');
            self::binding($resource['store'], $resource['binding']);
        }
    }

    private static function validateJournal(array $record, int $now): void
    {
        $keys = ['plan', 'revision', 'state', 'started_at', 'completed_at', 'steps', 'intent_at', 'code'];
        if (array_key_exists('no_copy_cleanup', $record)) $keys[] = 'no_copy_cleanup';
        self::keys($record, $keys);
        if (isset($record['no_copy_cleanup']) && (!is_array($record['no_copy_cleanup'])
            || strlen(json_encode($record['no_copy_cleanup'], JSON_THROW_ON_ERROR)) > 16384)) self::fail('JOURNAL_INVALID');
        if (!is_int($record['revision']) || $record['revision'] < 1 || !is_int($record['started_at'])
            || $record['started_at'] > $now || $record['started_at'] < 1 || !is_array($record['steps'])
            || !array_is_list($record['steps']) || count($record['steps']) !== count($record['plan']['resources'])
            || !is_array($record['intent_at']) || !array_is_list($record['intent_at'])
            || count($record['intent_at']) !== count($record['steps'])
            || !in_array($record['state'], ['PENDING', 'APPLYING', 'HELD', 'COMPLETE'], true)) self::fail('JOURNAL_INVALID');
        $unfinished = false;
        foreach ($record['steps'] as $index => $step) {
            if (!in_array($step, ['PENDING', 'INTENT_RECORDED', 'CONFIRMED_ABSENT'], true)
                || ($unfinished && $step === 'CONFIRMED_ABSENT')) self::fail('JOURNAL_INVALID');
            if ($step !== 'CONFIRMED_ABSENT') $unfinished = true;
            $intent = $record['intent_at'][$index];
            if ($step === 'PENDING' ? $intent !== null : (!is_int($intent) || $intent < $record['started_at'] || $intent > $now)) self::fail('JOURNAL_INVALID');
        }
        if ($record['state'] === 'COMPLETE') {
            if ($unfinished || !is_int($record['completed_at']) || $record['completed_at'] < $record['started_at']
                || $record['completed_at'] > $now) self::fail('JOURNAL_INVALID');
        } elseif ($record['completed_at'] !== null) self::fail('JOURNAL_INVALID');
        if (!is_string($record['code']) || strlen($record['code']) > 64) self::fail('JOURNAL_INVALID');
    }

    public static function digest(array $value): string
    {
        return hash('sha256', json_encode(self::sorted($value), JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES));
    }

    private static function sorted(array $value): array
    {
        if (!array_is_list($value)) ksort($value, SORT_STRING);
        foreach ($value as &$item) if (is_array($item)) $item = self::sorted($item);
        return $value;
    }

    private static function keys($value, array $expected): void
    {
        if (!is_array($value)) self::fail('SCHEMA_INVALID');
        $actual = array_keys($value); sort($actual); sort($expected);
        if ($actual !== $expected) self::fail('SCHEMA_INVALID');
    }
    private static function bounded($value, int $max): void
    {
        if (!is_string($value) || $value === '' || strlen($value) > $max || trim($value) !== $value
            || preg_match('/[\x00-\x1f\x7f]/', $value)) self::fail('VALUE_INVALID');
    }
    private static function hash($value): void { if (!is_string($value) || !preg_match('/^[a-f0-9]{64}$/D', $value)) self::fail('VALUE_INVALID'); }
    private static function uuid($value): void { if (!is_string($value) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $value)) self::fail('VALUE_INVALID'); }
    private static function receipt($value, string $prefix): void
    {
        if (!is_string($value) || !str_starts_with($value, $prefix)) self::fail('VALUE_INVALID');
        self::uuid(substr($value, strlen($prefix)));
    }
    private static function stamp($value): int
    {
        if (!is_string($value)) self::fail('TIME_INVALID');
        $date = \DateTimeImmutable::createFromFormat('!Y-m-d\TH:i:s\Z', $value, new \DateTimeZone('UTC'));
        if (!$date || $date->format('Y-m-d\TH:i:s\Z') !== $value) self::fail('TIME_INVALID');
        return $date->getTimestamp();
    }
    private static function summary(string $status, array $codes, int $confirmed = 0): array
    {
        return ['schema_version' => 1, 'scope' => 'SYNTHETIC_CLOSED_RETENTION', 'status' => $status,
            'confirmed_absent' => $confirmed, 'hold_codes' => $codes, 'production_authorized' => false];
    }
    private static function safeCode(\Throwable $error): string
    {
        return $error instanceof Failure ? $error->getMessage() : 'PROVIDER_OR_STORAGE_UNCERTAIN';
    }
    private static function fail(string $code): never { throw new Failure($code); }
    private static function lab(): void
    {
        if (!defined('BSRE_CLOSED_RETENTION_LAB') || BSRE_CLOSED_RETENTION_LAB !== true
            || !function_exists('wp_get_environment_type') || wp_get_environment_type() !== 'local'
            || !function_exists('home_url') || home_url() !== 'http://bsre.invalid') self::fail('ISOLATED_LAB_ONLY');
    }
}

final class Failure extends \RuntimeException {}
