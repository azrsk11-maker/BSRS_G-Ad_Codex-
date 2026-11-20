<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;

require_once __DIR__ . '/OwnerMailReview.php';
use BSRE\ClosedRetention\ClosureWriter;
use BSRE\ClosedRetention\Failure;
use BSRE\ClosedRetention\Journal;
use BSRE\ClosedRetention\Workflow;

/** Trusted server-owned readback of the actual sender and outstanding retirement custody. */
interface ClosureEditReadback
{
    public function readback(array $closure, int $now): ?array;
}

final class UnverifiedClosureEditReadback implements ClosureEditReadback
{
    public function readback(array $closure, int $now): ?array { return null; }
}

/**
 * Callable isolated-lab screen only: no hooks, routes, collectors, purge or sender capability.
 * The existing authoritative baseline and a trusted safety adapter are mandatory. Hashes bind
 * owner-supplied evidence bytes, not the truth of a real closure or live provider acceptance.
 */
final class OwnerClosureController
{
    public const CONTRACT = 'bsre-owner-closure-amendment-v1';
    public const SAFETY = 'bsre-owner-closure-edit-safety-v1';
    private const EDITABLE = ['status', 'closed_at_utc', 'evidence_reference', 'evidence_hash'];
    private const SERVER_FIELDS = ['revision', 'reviewer', 'recorded_at_utc'];
    private Journal&ClosureWriter $journal;
    private Store $store;
    private Session $session;
    private ClosureEditReadback $safety;

    public function __construct(Journal&ClosureWriter $journal, Store $store, Session $session,
        ?ClosureEditReadback $safety = null)
    {
        $this->journal = $journal; $this->store = $store; $this->session = $session;
        $this->safety = $safety ?? new UnverifiedClosureEditReadback();
    }

    /** Server clock only. GET never prunes or changes private custody. */
    public function handle(string $method, array $input, int $now): array
    {
        Guard::lab();
        $actor = Guard::text($this->session->actor()); // Before any read, nonce or cleanup.
        if ($now < 1) Guard::fail('CLOCK_INVALID');
        if ($method === 'GET') {
            if ($input === []) return ['status' => 'READY', 'job' => null];
            self::keys($input, ['job']); $id = Guard::hash($input['job']);
            return $this->store->locked($id, function () use ($id, $actor, $now) {
                return $this->view($this->owned($id, $actor, $now));
            });
        }
        if ($method !== 'POST') Guard::fail('METHOD_NOT_ALLOWED');
        $operation = Guard::text($input['operation'] ?? null, 16);
        if (!in_array($operation, ['prepare', 'approve', 'resume'], true)) Guard::fail('ACTION_INVALID');
        if ($operation === 'prepare') {
            self::keys($input, array_merge(['operation', 'nonce', 'closure_id'], self::EDITABLE));
            $this->csrf($input['nonce'], $this->action('prepare'));
            $closureId = self::uuid($input['closure_id']);
            $id = bin2hex(random_bytes(32));
            // One lock order throughout: opaque review job, then authoritative closure lease.
            return $this->store->locked($id, function () use ($id, $closureId, $actor, $input, $now) {
                return $this->journal->locked($closureId, function () use ($id, $closureId, $actor, $input, $now) {
                    $this->sameActor($actor);
                    $before = $this->journal->closure($closureId);
                    if ($before === null) Guard::fail('CLOSURE_BASELINE_REQUIRED');
                    if (($before['closure_id'] ?? null) !== $closureId) Guard::fail('CLOSURE_IDENTITY_CONFLICT');
                    Workflow::validateClosureRecord($before, $now);
                    $this->editable($before, $now);
                    if ($before['revision'] === PHP_INT_MAX) Guard::fail('CLOSURE_REVISION_INVALID');
                    $closedAt = $input['closed_at_utc'];
                    if ($closedAt === '') $closedAt = null; // Empty native form field represents explicit OPEN/null.
                    $after = array_replace($before, ['status' => $input['status'], 'closed_at_utc' => $closedAt,
                        'evidence_reference' => Guard::text($input['evidence_reference']), 'evidence_hash' => Guard::hash($input['evidence_hash']),
                        'revision' => $before['revision'] + 1, 'reviewer' => $actor, 'recorded_at_utc' => self::stamp($now)]);
                    Workflow::validateClosureRecord($after, $now);
                    $plan = ['schema_version' => 1, 'contract' => self::CONTRACT, 'closure_id' => $closureId,
                        'actor' => $actor, 'before' => $before, 'before_hash' => Workflow::digest($before),
                        'after' => $after, 'after_hash' => Workflow::digest($after), 'created_at' => $now, 'expires_at' => $now + 900];
                    $plan['digest'] = Workflow::digest($plan);
                    $job = ['schema_version' => 1, 'id' => $id, 'revision' => 0, 'actor' => $actor, 'plan' => $plan,
                        'approved_at' => null, 'cleanup_after' => $plan['expires_at'], 'manifest' => null,
                        'declarations' => [], 'verified_receipts' => [], 'status' => 'REVIEW_EXACT_CLOSURE_AMENDMENT', 'hold_codes' => []];
                    $this->sameActor($actor);
                    $this->store->save($job);
                    return $this->view($job);
                });
            });
        }
        self::keys($input, ['operation', 'nonce', 'job', 'plan_digest']);
        $id = Guard::hash($input['job']); $digest = Guard::hash($input['plan_digest']);
        $this->csrf($input['nonce'], $this->action($operation, $id, $digest));
        return $this->store->locked($id, function () use ($id, $digest, $operation, $actor, $now) {
            $job = $this->owned($id, $actor, $now);
            if (!hash_equals($job['plan']['digest'], $digest)) Guard::fail('EXACT_PLAN_CONFLICT');
            return $this->journal->locked($job['plan']['closure_id'], function () use (&$job, $operation, $actor, $now) {
                $this->sameActor($actor);
                $plan = $job['plan'];
                if ($operation === 'resume' && $job['approved_at'] === null) Guard::fail('EXACT_APPROVAL_REQUIRED');
                $current = $this->journal->closure($plan['closure_id']);
                if ($current === null) return $this->held($job, 'CLOSURE_BASELINE_REQUIRED');
                try {
                    Workflow::validateClosureRecord($current, $now);
                    $hash = Workflow::digest($current);
                    // Historical confirmation needs an already committed exact write intent.
                    if ($job['approved_at'] !== null && $job['manifest'] !== null && $hash === $plan['after_hash']) {
                        $this->editable($current, $now);
                        return $this->applied($job);
                    }
                    if ($hash !== $plan['before_hash']) Guard::fail('CLOSURE_BASELINE_CHANGED');
                    // Approval never permits a newly applied old plan, including a prior failed write.
                    if ($now >= $plan['expires_at']) Guard::fail('PLAN_EXPIRED');
                    $this->editable($current, $now);
                    $this->sameActor($actor);
                    if ($job['approved_at'] === null) {
                        $job['approved_at'] = $now; $job['cleanup_after'] = $now + 30 * 86400;
                        $job['manifest'] = ['contract' => self::CONTRACT, 'plan_digest' => $plan['digest'],
                            'before_hash' => $plan['before_hash'], 'after_hash' => $plan['after_hash'], 'intent_at' => $now];
                        $job['status'] = 'CLOSURE_AMENDMENT_INTENT_RECORDED'; $job['hold_codes'] = [];
                        $this->store->save($job); // Durable BEFORE the separate authoritative CAS.
                    }
                    $this->sameActor($actor);
                    $this->journal->replaceClosure($plan['before'], $plan['after']);
                    $readback = $this->journal->closure($plan['closure_id']);
                    if ($readback === null || Workflow::digest($readback) !== $plan['after_hash']) Guard::fail('CLOSURE_WRITE_UNCONFIRMED');
                    return $this->applied($job);
                } catch (\Throwable $error) { return $this->held($job, self::code($error)); }
            });
        });
    }

    private function editable(array $closure, int $now): void
    {
        if ($closure['email_status'] === 'RETIRED_NO_COPY') Guard::fail('RETIRED_CLOSURE_REQUIRES_RECONCILIATION');
        try { $value = $this->safety->readback($closure, $now); }
        catch (\Throwable $error) { Guard::fail('CLOSURE_EDIT_SAFETY_UNCERTAIN'); }
        if ($value === null) Guard::fail('CLOSURE_EDIT_SAFETY_UNVERIFIED');
        self::keys($value, ['contract', 'closure_hash', 'sender_fence', 'retirement_intent', 'authoritative',
            'observed_at', 'expires_at', 'evidence_reference', 'evidence_hash']);
        if ($value['contract'] !== self::SAFETY || $value['closure_hash'] !== Workflow::digest($closure)) Guard::fail('CLOSURE_EDIT_SAFETY_CONFLICT');
        if ($value['authoritative'] !== true || $value['sender_fence'] !== 'NONE' || $value['retirement_intent'] !== 'NONE') Guard::fail('CLOSURE_EDIT_BLOCKED');
        if (!is_int($value['observed_at']) || $value['observed_at'] <= 0 || $value['observed_at'] > $now
            || !is_int($value['expires_at']) || $value['expires_at'] <= $now || $value['expires_at'] > $value['observed_at'] + 300)
            Guard::fail('CLOSURE_EDIT_SAFETY_STALE');
        Guard::text($value['evidence_reference']); Guard::hash($value['evidence_hash']);
    }

    private function owned(string $id, string $actor, int $now): array
    {
        $this->sameActor($actor);
        $job = $this->store->load($id);
        if ($job === null || $job['actor'] !== $actor || $job['cleanup_after'] <= $now) Guard::fail('REVIEW_NOT_FOUND');
        $plan = $job['plan'];
        self::keys($plan, ['schema_version', 'contract', 'closure_id', 'actor', 'before', 'before_hash', 'after',
            'after_hash', 'created_at', 'expires_at', 'digest']);
        $unsigned = $plan; unset($unsigned['digest']);
        if ($plan['schema_version'] !== 1 || $plan['contract'] !== self::CONTRACT || $plan['actor'] !== $actor
            || !is_int($plan['created_at']) || $plan['created_at'] < 1 || $plan['created_at'] > $now
            || $plan['expires_at'] !== $plan['created_at'] + 900 || Workflow::digest($unsigned) !== $plan['digest']) Guard::fail('CLOSURE_PLAN_INVALID');
        self::uuid($plan['closure_id']); Guard::hash($plan['digest']);
        Workflow::validateClosureRecord($plan['before'], $now); Workflow::validateClosureRecord($plan['after'], $now);
        if ($plan['closure_id'] !== $plan['before']['closure_id'] || $plan['before_hash'] !== Workflow::digest($plan['before'])
            || $plan['after_hash'] !== Workflow::digest($plan['after']) || $plan['after']['revision'] !== $plan['before']['revision'] + 1
            || $plan['after']['reviewer'] !== $actor || $plan['after']['recorded_at_utc'] !== self::stamp($plan['created_at'])) Guard::fail('CLOSURE_PLAN_INVALID');
        foreach ($plan['before'] as $key => $value) {
            if (!in_array($key, array_merge(self::EDITABLE, self::SERVER_FIELDS), true) && $plan['after'][$key] !== $value) Guard::fail('CLOSURE_PLAN_INVALID');
        }
        if ($job['approved_at'] !== null) {
            if (!is_int($job['approved_at']) || $job['approved_at'] < $plan['created_at'] || $job['approved_at'] >= $plan['expires_at']
                || $job['approved_at'] > $now || $job['cleanup_after'] !== $job['approved_at'] + 30 * 86400) Guard::fail('CLOSURE_INTENT_INVALID');
            $intent = $job['manifest'];
            self::keys($intent, ['contract', 'plan_digest', 'before_hash', 'after_hash', 'intent_at']);
            if ($intent !== ['contract' => self::CONTRACT, 'plan_digest' => $plan['digest'], 'before_hash' => $plan['before_hash'],
                'after_hash' => $plan['after_hash'], 'intent_at' => $job['approved_at']]) Guard::fail('CLOSURE_INTENT_INVALID');
        } elseif ($job['manifest'] !== null || $job['cleanup_after'] !== $plan['expires_at']) Guard::fail('CLOSURE_INTENT_INVALID');
        return $job;
    }

    private function sameActor(string $actor): void
    {
        if (!hash_equals($this->session->actor(), $actor)) Guard::fail('OWNER_SESSION_REQUIRED');
    }
    private function applied(array &$job): array
    {
        $this->sameActor($job['actor']);
        if ($job['status'] === 'CLOSURE_AMENDMENT_APPLIED' && $job['hold_codes'] === []) return $this->view($job);
        $job['status'] = 'CLOSURE_AMENDMENT_APPLIED'; $job['hold_codes'] = [];
        $this->store->save($job); return $this->view($job);
    }
    private function held(array &$job, string $code): array
    {
        $this->sameActor($job['actor']);
        $job['status'] = 'HELD'; $job['hold_codes'] = [$code];
        $this->store->save($job); return $this->view($job);
    }
    private function view(array $job): array { return ['status' => $job['status'], 'job' => $job, 'hold_codes' => $job['hold_codes']]; }
    private function csrf($nonce, string $action): void
    {
        if (!is_string($nonce) || !$this->session->verify($nonce, $action)) Guard::fail('CSRF_REJECTED');
    }
    private function action(string $operation, string $id = '', string $digest = ''): string
    {
        return 'bsre-owner-closure/' . Workflow::digest([$operation, $id, $digest]);
    }
    private static function stamp(int $now): string { return gmdate('Y-m-d\TH:i:s\Z', $now); }
    private static function keys(array $value, array $expected): void
    {
        $actual = array_keys($value); sort($actual); sort($expected);
        if ($actual !== $expected) Guard::fail('INPUT_SCHEMA_INVALID');
    }
    private static function uuid($value): string
    {
        if (!is_string($value) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $value)) Guard::fail('INPUT_INVALID');
        return $value;
    }
    private static function code(\Throwable $error): string
    {
        if (in_array($error->getMessage(), ['CLOSURE_LEASE_REQUIRED', 'CLOSURE_JOB_RECONCILIATION_REQUIRED',
            'CLOSURE_REVISION_CONFLICT', 'CLOSURE_WRITE_UNCONFIRMED'], true)) return $error->getMessage();
        return ($error instanceof ReviewFailure || $error instanceof Failure) && preg_match('/^[A-Z][A-Z0-9_]{1,63}$/D', $error->getMessage())
            ? $error->getMessage() : 'CLOSURE_STORAGE_UNCERTAIN';
    }

    /** Escaped private review only; never includes external resources, analytics or provider actions. */
    public function render(array $view): string
    {
        Guard::lab(); $actor = $this->session->actor();
        if ($view['job'] !== null && $view['job']['actor'] !== $actor) Guard::fail('REVIEW_NOT_FOUND');
        $e = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $html = '<section aria-labelledby="bsre-closure-title"><h1 id="bsre-closure-title">Private closure amendment</h1><p role="status">' . $e($view['status']) . '</p>'
            . '<p>Amend an existing authoritative closure only. This action grants no sender retirement or purge permission.</p>';
        foreach ($view['hold_codes'] ?? [] as $code) $html .= '<p role="alert">' . $e($code) . '</p>';
        if ($view['job'] === null) {
            $html .= '<form method="post"><input type="hidden" name="operation" value="prepare"><input type="hidden" name="nonce" value="'
                . $e($this->session->nonce($this->action('prepare'))) . '"><label for="bsre-closure-id">Existing closure ID</label><input id="bsre-closure-id" name="closure_id" maxlength="36" autocomplete="off" required>'
                . '<label for="bsre-closure-status">Closure status</label><select id="bsre-closure-status" name="status"><option value="OPEN">OPEN</option><option value="CLOSED">CLOSED</option><option value="UNSUCCESSFUL">UNSUCCESSFUL</option></select>'
                . '<label for="bsre-closure-at">Actual closure UTC time (empty for OPEN)</label><input id="bsre-closure-at" name="closed_at_utc" maxlength="20" placeholder="YYYY-MM-DDTHH:MM:SSZ" autocomplete="off">'
                . '<label for="bsre-closure-evidence">Private evidence reference</label><input id="bsre-closure-evidence" name="evidence_reference" maxlength="256" autocomplete="off" required>'
                . '<label for="bsre-closure-hash">Evidence SHA256</label><input id="bsre-closure-hash" name="evidence_hash" pattern="[a-f0-9]{64}" maxlength="64" autocomplete="off" required><button type="submit">Review exact closure amendment</button></form>';
        } else {
            $job = $view['job']; $plan = $job['plan'];
            $html .= '<pre aria-label="Exact private closure amendment">' . $e(json_encode($plan, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>';
            $operation = $job['approved_at'] === null ? 'approve' : 'resume';
            $html .= '<form method="post"><input type="hidden" name="operation" value="' . $operation . '"><input type="hidden" name="job" value="' . $e($job['id'])
                . '"><input type="hidden" name="plan_digest" value="' . $e($plan['digest']) . '"><input type="hidden" name="nonce" value="'
                . $e($this->session->nonce($this->action($operation, $job['id'], $plan['digest']))) . '"><button type="submit">'
                . ($operation === 'approve' ? 'Approve this exact closure amendment' : 'Confirm or resume this exact amendment') . '</button></form>';
        }
        return $html . '</section>';
    }
}
