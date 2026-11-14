<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;

require_once __DIR__ . '/OwnerMailReview.php';
use BSRE\ClosedRetention\ClosureCollectorWriter;
use BSRE\ClosedRetention\ClosureCollectionSource;
use BSRE\ClosedRetention\CollectionSnapshot;
use BSRE\ClosedRetention\Failure;
use BSRE\ClosedRetention\Journal;
use BSRE\ClosedRetention\UnverifiedClosureCollectionSource;
use BSRE\ClosedRetention\Workflow;

/** Private isolated collection only. No provider writes, sender capability or purge authority. */
final class OwnerCollectionController
{
    public const CONTRACT = 'bsre-owner-closure-collection-v1';
    private ClosureCollectionSource $source;

    public function __construct(private Workflow $workflow, private Journal&ClosureCollectorWriter $journal,
        private Store $store, private Session $session, ?ClosureCollectionSource $source = null)
    {
        if (!$workflow->usesJournal($journal)) Guard::fail('COLLECTION_JOURNAL_CONFLICT');
        $this->source = $source ?? new UnverifiedClosureCollectionSource();
    }

    /** Server clock only. GET never starts work or prunes custody. */
    public function handle(string $method, array $input, int $now): array
    {
        Guard::lab(); $actor = Guard::text($this->session->actor());
        if ($now < 1) Guard::fail('CLOCK_INVALID');
        if ($method === 'GET') {
            if ($input === []) return ['status' => 'READY', 'job' => null];
            self::keys($input, ['job']); $id = Guard::hash($input['job']);
            return $this->store->locked($id, fn() => $this->view($this->owned($id, $actor, $now)));
        }
        if ($method !== 'POST') Guard::fail('METHOD_NOT_ALLOWED');
        $operation = Guard::text($input['operation'] ?? null, 16);
        if (!in_array($operation, ['prepare', 'approve', 'resume'], true)) Guard::fail('ACTION_INVALID');
        if ($operation === 'prepare') {
            self::keys($input, ['operation', 'nonce', 'request_id']);
            $this->csrf($input['nonce'], $this->action('prepare'));
            $requestId = self::uuid($input['request_id']); $id = bin2hex(random_bytes(32));
            return $this->store->locked($id, function () use ($requestId, $id, $actor, $now) {
                return $this->journal->locked($requestId, function () use ($requestId, $id, $actor, $now) {
                    $this->sameActor($actor);
                    $frame = $this->observe($requestId, $now);
                    $this->sameActor($actor);
                    $after = CollectionSnapshot::target($frame, $requestId, $actor, $now, $now);
                    $fingerprint = CollectionSnapshot::fingerprint($frame, $now);
                    $context = $this->workflow->collectionContext($after, $actor, $now);
                    self::context($context);
                    $plan = ['schema_version' => 1, 'contract' => self::CONTRACT, 'closure_id' => $requestId,
                        'actor' => $actor, 'after' => $after, 'after_hash' => Workflow::digest($after),
                        'source_fingerprint' => $fingerprint, 'context' => $context,
                        'created_at' => $now, 'expires_at' => $now + 900];
                    $plan['digest'] = Workflow::digest($plan);
                    $job = ['schema_version' => 1, 'id' => $id, 'revision' => 0, 'actor' => $actor, 'plan' => $plan,
                        'approved_at' => null, 'cleanup_after' => $plan['expires_at'], 'manifest' => null,
                        'declarations' => [], 'verified_receipts' => [], 'status' => 'REVIEW_EXACT_CLOSURE_COLLECTION', 'hold_codes' => []];
                    $this->sameActor($actor); $this->saveConfirmed($job);
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
                $this->sameActor($actor); $plan = $job['plan'];
                if ($operation === 'resume' && $job['approved_at'] === null) Guard::fail('EXACT_APPROVAL_REQUIRED');
                try {
                    $current = $this->journal->closure($plan['closure_id']);
                    if ($job['approved_at'] !== null && $job['manifest'] !== null && $current === $plan['after']) {
                        $this->journal->assertCollectionTarget($plan['after'], true);
                        return $this->applied($job);
                    }
                    if ($current !== null) Guard::fail('COLLECTION_TARGET_ALREADY_EXISTS');
                    if ($now >= $plan['expires_at']) Guard::fail('PLAN_EXPIRED');
                    $this->fresh($plan, $actor, $now);
                    $this->sameActor($actor);
                    if ($job['approved_at'] === null) {
                        $job['approved_at'] = $now; $job['cleanup_after'] = $now + 30 * 86400;
                        $job['manifest'] = ['contract' => self::CONTRACT, 'plan_digest' => $plan['digest'],
                            'after_hash' => $plan['after_hash'], 'source_fingerprint' => $plan['source_fingerprint'], 'intent_at' => $now];
                        $job['status'] = 'CLOSURE_COLLECTION_INTENT_RECORDED'; $job['hold_codes'] = [];
                        $this->saveConfirmed($job); // Committed and independently reread BEFORE canonical insertion.
                    }
                    $this->fresh($plan, $actor, $now);
                    $this->sameActor($actor);
                    $this->journal->insertClosure($plan['after']);
                    if ($this->journal->closure($plan['closure_id']) !== $plan['after']) Guard::fail('CLOSURE_WRITE_UNCONFIRMED');
                    return $this->applied($job);
                } catch (\Throwable $error) { return $this->held($job, self::code($error)); }
            });
        });
    }

    private function observe(string $requestId, int $now): array
    {
        try { $frame = $this->source->observe($requestId, $now); }
        catch (\Throwable $error) { Guard::fail('CLOSURE_COLLECTION_SOURCE_UNCERTAIN'); }
        if ($frame === null) Guard::fail('CLOSURE_COLLECTION_SOURCE_UNVERIFIED');
        return $frame;
    }

    private function fresh(array $plan, string $actor, int $now): void
    {
        $frame = $this->observe($plan['closure_id'], $now);
        $this->sameActor($actor);
        $target = CollectionSnapshot::target($frame, $plan['closure_id'], $actor, $plan['created_at'], $now);
        if ($target !== $plan['after'] || CollectionSnapshot::fingerprint($frame, $now) !== $plan['source_fingerprint'])
            Guard::fail('COLLECTION_SOURCE_CHANGED');
        $context = $this->workflow->collectionContext($target, $actor, $now);
        self::context($context);
        if ($context !== $plan['context']) Guard::fail('COLLECTION_CONTEXT_CHANGED');
    }

    private function owned(string $id, string $actor, int $now): array
    {
        $this->sameActor($actor); $job = $this->store->load($id);
        if ($job === null || $job['actor'] !== $actor || $job['cleanup_after'] <= $now) Guard::fail('REVIEW_NOT_FOUND');
        $plan = $job['plan'];
        self::keys($plan, ['schema_version', 'contract', 'closure_id', 'actor', 'after', 'after_hash',
            'source_fingerprint', 'context', 'created_at', 'expires_at', 'digest']);
        $unsigned = $plan; unset($unsigned['digest']);
        if ($plan['schema_version'] !== 1 || $plan['contract'] !== self::CONTRACT || $plan['actor'] !== $actor
            || !is_int($plan['created_at']) || $plan['created_at'] < 1 || $plan['created_at'] > $now
            || $plan['expires_at'] !== $plan['created_at'] + 900 || Workflow::digest($unsigned) !== $plan['digest']) Guard::fail('COLLECTION_PLAN_INVALID');
        self::uuid($plan['closure_id']); Guard::hash($plan['digest']); Guard::hash($plan['after_hash']);
        Guard::hash($plan['source_fingerprint']); self::context($plan['context']);
        Workflow::validateClosureRecord($plan['after'], $now);
        if ($plan['after']['closure_id'] !== $plan['closure_id'] || $plan['after']['request_id'] !== $plan['closure_id']
            || $plan['after']['revision'] !== 1 || $plan['after']['reviewer'] !== $actor
            || $plan['after']['recorded_at_utc'] !== gmdate('Y-m-d\TH:i:s\Z', $plan['created_at'])
            || $plan['after']['email_status'] === 'RETIRED_NO_COPY' || Workflow::digest($plan['after']) !== $plan['after_hash']) Guard::fail('COLLECTION_PLAN_INVALID');
        if ($job['approved_at'] !== null) {
            if (!is_int($job['approved_at']) || $job['approved_at'] < $plan['created_at'] || $job['approved_at'] >= $plan['expires_at']
                || $job['approved_at'] > $now || $job['cleanup_after'] !== $job['approved_at'] + 30 * 86400) Guard::fail('COLLECTION_INTENT_INVALID');
            if ($job['manifest'] !== ['contract' => self::CONTRACT, 'plan_digest' => $plan['digest'],
                'after_hash' => $plan['after_hash'], 'source_fingerprint' => $plan['source_fingerprint'], 'intent_at' => $job['approved_at']]) Guard::fail('COLLECTION_INTENT_INVALID');
        } elseif ($job['manifest'] !== null || $job['cleanup_after'] !== $plan['expires_at']) Guard::fail('COLLECTION_INTENT_INVALID');
        return $job;
    }

    private static function context(array $context): void
    {
        self::keys($context, ['admission_hash', 'inventory_hash']);
        Guard::hash($context['admission_hash']); Guard::hash($context['inventory_hash']);
    }
    private function saveConfirmed(array &$job): void
    {
        $this->store->save($job);
        if ($this->store->load($job['id']) !== $job) Guard::fail('COLLECTION_INTENT_UNCONFIRMED');
    }
    private function sameActor(string $actor): void
    {
        if (!hash_equals($this->session->actor(), $actor)) Guard::fail('OWNER_SESSION_REQUIRED');
    }
    private function applied(array &$job): array
    {
        $this->sameActor($job['actor']);
        if ($job['status'] !== 'CLOSURE_COLLECTION_APPLIED' || $job['hold_codes'] !== []) {
            $job['status'] = 'CLOSURE_COLLECTION_APPLIED'; $job['hold_codes'] = []; $this->saveConfirmed($job);
        }
        return $this->view($job);
    }
    private function held(array &$job, string $code): array
    {
        $this->sameActor($job['actor']); $job['status'] = 'HELD'; $job['hold_codes'] = [$code];
        $this->saveConfirmed($job); return $this->view($job);
    }
    private function view(array $job): array { return ['status' => $job['status'], 'job' => $job, 'hold_codes' => $job['hold_codes']]; }
    private function csrf($nonce, string $action): void
    {
        if (!is_string($nonce) || !$this->session->verify($nonce, $action)) Guard::fail('CSRF_REJECTED');
    }
    private function action(string $operation, string $id = '', string $digest = ''): string
    {
        return 'bsre-owner-collection/' . Workflow::digest([$operation, $id, $digest]);
    }
    private static function uuid($value): string
    {
        if (!is_string($value) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $value)) Guard::fail('INPUT_INVALID');
        return $value;
    }
    private static function keys(array $value, array $expected): void
    {
        $actual = array_keys($value); sort($actual); sort($expected);
        if ($actual !== $expected) Guard::fail('INPUT_SCHEMA_INVALID');
    }
    private static function code(\Throwable $error): string
    {
        return ($error instanceof ReviewFailure || $error instanceof Failure) && preg_match('/^[A-Z][A-Z0-9_]{1,63}$/D', $error->getMessage())
            ? $error->getMessage() : 'CLOSURE_COLLECTION_STORAGE_UNCERTAIN';
    }

    public function render(array $view): string
    {
        Guard::lab(); $actor = $this->session->actor();
        if ($view['job'] !== null && $view['job']['actor'] !== $actor) Guard::fail('REVIEW_NOT_FOUND');
        $e = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $html = '<section aria-labelledby="bsre-collection-title"><h1 id="bsre-collection-title">Private closure collection</h1><p role="status">' . $e($view['status']) . '</p>'
            . '<p>Review a new closure from trusted source evidence. Collection grants no sender retirement or purge permission.</p>';
        foreach ($view['hold_codes'] ?? [] as $code) $html .= '<p role="alert">' . $e($code) . '</p>';
        if ($view['job'] === null) {
            $html .= '<form method="post"><input type="hidden" name="operation" value="prepare"><input type="hidden" name="nonce" value="'
                . $e($this->session->nonce($this->action('prepare'))) . '"><label for="bsre-collection-request">Source request ID</label><input id="bsre-collection-request" name="request_id" maxlength="36" autocomplete="off" required><button type="submit">Review exact closure collection</button></form>';
        } else {
            $job = $view['job']; $plan = $job['plan']; $operation = $job['approved_at'] === null ? 'approve' : 'resume';
            $html .= '<pre aria-label="Exact private closure collection">' . $e(json_encode($plan, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>'
                . '<form method="post"><input type="hidden" name="operation" value="' . $operation . '"><input type="hidden" name="job" value="' . $e($job['id'])
                . '"><input type="hidden" name="plan_digest" value="' . $e($plan['digest']) . '"><input type="hidden" name="nonce" value="'
                . $e($this->session->nonce($this->action($operation, $job['id'], $plan['digest']))) . '"><button type="submit">'
                . ($operation === 'approve' ? 'Approve this exact closure collection' : 'Confirm or resume this exact collection') . '</button></form>';
        }
        return $html . '</section>';
    }
}
