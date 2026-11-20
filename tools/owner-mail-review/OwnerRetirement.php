<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;

require_once __DIR__ . '/OwnerMailReview.php';
require_once __DIR__ . '/../closed-enquiry-retention/RetirementIntent.php';
use BSRE\ClosedRetention\Failure;
use BSRE\ClosedRetention\Journal;
use BSRE\ClosedRetention\NoMailRetirement;
use BSRE\ClosedRetention\NoMailRetirementProof;
use BSRE\ClosedRetention\RetirementIntent;
use BSRE\ClosedRetention\RetirementWriter;
use BSRE\ClosedRetention\UnverifiedNoMailRetirement;
use BSRE\ClosedRetention\Workflow;

/**
 * Explicit synthetic-lab controller. No route/hook/collector/purge or fence-cleanup capability.
 * UI jobs are disposable reviews; only typed Journal intents authorize sender retirement.
 * Real collectors, mailbox/custody authority and production authorization remain unavailable.
 */
final class OwnerRetirementController
{
    private Workflow $workflow;
    private Journal&RetirementWriter $journal;
    private Store $store;
    private Session $session;
    private NoMailRetirement $retirer;

    public function __construct(Workflow $workflow, Journal&RetirementWriter $journal, Store $store,
        Session $session, ?NoMailRetirement $retirer = null)
    {
        if (!$workflow->usesJournal($journal)) Guard::fail('RETIREMENT_JOURNAL_MISMATCH');
        $this->workflow = $workflow; $this->journal = $journal; $this->store = $store;
        $this->session = $session; $this->retirer = $retirer ?? new UnverifiedNoMailRetirement();
    }

    /** Caller supplies server time. Authentication precedes any private read, nonce or maintenance. */
    public function handle(string $method, array $input, int $now): array
    {
        Guard::lab(); $actor = Guard::text($this->session->actor());
        if ($now < 1) Guard::fail('CLOCK_INVALID');
        if ($method === 'GET') {
            if ($input === []) return $this->view('READY');
            self::keys($input, ['job']); $id = Guard::hash($input['job']);
            return $this->store->locked($id, function () use ($id, $actor, $now) {
                $job = $this->ownedJob($id, $actor, $now);
                return $this->view($job['status'], $job, null, $job['hold_codes']);
            });
        }
        if ($method !== 'POST') Guard::fail('METHOD_NOT_ALLOWED');
        $operation = Guard::text($input['operation'] ?? null, 16);
        if ($operation === 'prepare') {
            self::keys($input, ['operation', 'nonce', 'closure_id']);
            $this->csrf($input['nonce'], $this->action('prepare'));
            $closureId = self::uuid($input['closure_id']); $id = bin2hex(random_bytes(32));
            return $this->store->locked($id, function () use ($closureId, $id, $actor, $now) {
                return $this->journal->locked($closureId, function () use ($closureId, $id, $actor, $now) {
                    $this->sameActor($actor); $this->journal->assertRetirementOpen();
                    $before = $this->journal->closure($closureId);
                    if ($before === null) Guard::fail('CLOSURE_BASELINE_REQUIRED');
                    if (($before['closure_id'] ?? null) !== $closureId) Guard::fail('CLOSURE_IDENTITY_CONFLICT');
                    $after = RetirementIntent::target($before);
                    $context = $this->workflow->retirementContext($before, $after, $actor, $now);
                    self::keys($context, ['scope', 'admission_hash', 'inventory_hash']);
                    $plan = ['schema_version' => 1, 'contract' => RetirementIntent::CONTRACT, 'closure_id' => $closureId,
                        'actor' => $actor, 'before' => $before, 'after' => $after, 'before_hash' => Workflow::digest($before),
                        'after_hash' => Workflow::digest($after), 'scope' => $context['scope'], 'admission_hash' => $context['admission_hash'],
                        'inventory_hash' => $context['inventory_hash'], 'created_at' => $now, 'expires_at' => $now + 900];
                    $plan['digest'] = Workflow::digest($plan); RetirementIntent::validatePlan($plan, $now);
                    $job = ['schema_version' => 1, 'id' => $id, 'revision' => 0, 'actor' => $actor, 'plan' => $plan,
                        'approved_at' => null, 'cleanup_after' => $plan['expires_at'], 'manifest' => null, 'declarations' => [],
                        'verified_receipts' => [], 'status' => 'REVIEW_EXACT_RETIREMENT', 'hold_codes' => []];
                    $this->sameActor($actor); $this->store->save($job);
                    return $this->view($job['status'], $job);
                });
            });
        }
        if ($operation === 'approve') {
            self::keys($input, ['operation', 'nonce', 'job', 'plan_digest']);
            $id = Guard::hash($input['job']); $digest = Guard::hash($input['plan_digest']);
            $this->csrf($input['nonce'], $this->action('approve', $id, $digest));
            return $this->store->locked($id, function () use ($id, $digest, $actor, $now) {
                $job = $this->ownedJob($id, $actor, $now);
                if ($job['plan']['digest'] !== $digest) Guard::fail('EXACT_PLAN_CONFLICT');
                return $this->journal->locked($job['plan']['closure_id'], function () use (&$job, $digest, $actor, $now) {
                    $this->sameActor($actor); $record = $this->journal->journal($digest);
                    try {
                        if ($record === null) {
                            if ($job['approved_at'] !== null || $job['manifest'] !== null) Guard::fail('RETIREMENT_INTENT_UNVERIFIED');
                            if ($now >= $job['plan']['expires_at']) Guard::fail('PLAN_EXPIRED');
                            $this->context($job['plan'], $actor, $now);
                            $record = ['schema_version' => 1, 'contract' => RetirementIntent::CONTRACT, 'revision' => 0,
                                'plan' => $job['plan'], 'approved_at' => $now, 'recovery_until' => $now + 30 * 86400,
                                'phase' => 'INTENT_RECORDED', 'proof_hash' => null, 'hold_codes' => []];
                            RetirementIntent::validateRecord($record, $now);
                            $this->sameActor($actor); $this->journal->stageRetirement($record, $now); // BEFORE every source inspect/write.
                            $record = $this->authoritative($digest, $actor, $now);
                            if ($record === null) Guard::fail('RETIREMENT_INTENT_UNVERIFIED');
                        }
                        $this->exactRecord($record, $job['plan'], $actor, $now);
                        $record = $this->proceed($record, $actor, $now);
                    } catch (\Throwable $error) {
                        $record = $this->hold($digest, $actor, $now, self::code($error));
                    }
                    if ($record === null) return $this->missing();
                    $job['approved_at'] = $record['approved_at']; $job['cleanup_after'] = $record['recovery_until'];
                    $job['manifest'] = ['contract' => RetirementIntent::CONTRACT, 'intent_digest' => $digest];
                    $job['status'] = $record['hold_codes'] === [] ? $record['phase'] : 'HELD'; $job['hold_codes'] = $record['hold_codes'];
                    $this->sameActor($actor); $this->store->save($job);
                    return $this->view($job['status'], $job, $record, $job['hold_codes']);
                });
            });
        }
        if (!in_array($operation, ['review_intent', 'recover', 'expire'], true)) Guard::fail('ACTION_INVALID');
        self::keys($input, ['operation', 'nonce', 'intent_digest']); $digest = Guard::hash($input['intent_digest']);
        $this->csrf($input['nonce'], $this->action($operation, '', $operation === 'review_intent' ? '' : $digest));
        $record = $this->authoritative($digest, $actor, $now);
        if ($record === null) return $this->missing();
        return $this->journal->locked($record['plan']['closure_id'], function () use ($operation, $digest, $actor, $now) {
            $record = $this->authoritative($digest, $actor, $now);
            if ($record === null) return $this->missing();
            if ($operation === 'review_intent') return $this->view($record['hold_codes'] === [] ? $record['phase'] : 'HELD', null, $record, $record['hold_codes']);
            if ($operation === 'expire') {
                if ($now < $record['recovery_until']) return $this->view('HELD', null, $record, ['RECOVERY_WINDOW_ACTIVE']);
                $this->sameActor($actor);
                try { $removed = $this->journal->scrubRetirement($record, $now); }
                catch (\Throwable $error) {
                    $fresh = $this->authoritative($digest, $actor, $now); // Resolve an ambiguous commit before any future retry.
                    if ($fresh === null) return $this->missing();
                    return $this->view('HELD', null, $fresh, [self::code($error)]) + ['manual_reconciliation_required' => true,
                        'source_fence_modified' => false, 'provider_completion_verified' => false];
                }
                return $this->view($removed ? 'PRIVATE_RETIREMENT_INTENT_EXPIRED' : 'NO_PRIVATE_RETIREMENT_INTENT', null, null,
                    ['MANUAL_RECONCILIATION_REQUIRED']) + ['manual_reconciliation_required' => true,
                    'source_fence_modified' => false, 'provider_completion_verified' => false];
            }
            try { $record = $this->proceed($record, $actor, $now); }
            catch (\Throwable $error) { $record = $this->hold($digest, $actor, $now, self::code($error)); }
            return $record === null ? $this->missing()
                : $this->view($record['hold_codes'] === [] ? $record['phase'] : 'HELD', null, $record, $record['hold_codes']);
        });
    }

    /** Same closure lease covers context, authoritative intent, source action and protected CAS. */
    private function proceed(array $record, string $actor, int $now): array
    {
        $plan = $record['plan']; RetirementIntent::validateRecord($record, $now);
        if ($now >= $record['recovery_until']) Guard::fail('RECOVERY_WINDOW_EXPIRED');
        $this->context($plan, $actor, $now);
        $this->sameActor($actor); $this->journal->assertRetirementSource($record, $now);
        try { $frame = $this->retirer->inspect($plan['scope'], $now); }
        catch (\Throwable $error) { Guard::fail('RETIREMENT_SOURCE_UNCERTAIN'); }
        $inspection = NoMailRetirementProof::verify($frame, $plan['scope'], $now);
        if ($inspection['state'] === 'RETIRED') $proof = $inspection['proof'];
        else {
            if ($record['phase'] !== 'INTENT_RECORDED' || $record['proof_hash'] !== null) Guard::fail('RETIREMENT_FENCE_STATE_CONFLICT');
            if ($now >= $plan['expires_at']) Guard::fail('PLAN_EXPIRED');
            $this->context($plan, $actor, $now); $this->sameActor($actor); $this->journal->assertRetirementSource($record, $now);
            try { $proof = $this->retirer->retire($plan['scope'], $record, $now); }
            catch (\Throwable $error) { Guard::fail('RETIREMENT_SOURCE_UNCERTAIN'); }
            if ($proof === null) Guard::fail('RETIREMENT_SOURCE_UNVERIFIED');
        }
        $hash = RetirementIntent::verifiedFence($record, $proof, $now);
        if ($record['phase'] === 'INTENT_RECORDED') {
            $record['phase'] = 'FENCE_CONFIRMED'; $record['proof_hash'] = $hash; $record['hold_codes'] = [];
            $this->sameActor($actor); $this->journal->save($record); // Durable proof binding BEFORE closure CAS.
            $fresh = $this->authoritative($plan['digest'], $actor, $now);
            if ($fresh === null || $fresh['phase'] !== 'FENCE_CONFIRMED' || $fresh['proof_hash'] !== $hash) Guard::fail('RETIREMENT_INTENT_UNVERIFIED');
            $record = $fresh;
        }
        $this->sameActor($actor); $this->journal->assertRetirementSource($record, $now);
        $this->journal->commitRetirement($record, $proof, $now);
        if ($record['phase'] !== 'RETIREMENT_RECORDED' || $record['hold_codes'] !== []) {
            $record['phase'] = 'RETIREMENT_RECORDED'; $record['hold_codes'] = [];
            $this->sameActor($actor); $this->journal->save($record);
        }
        return $record;
    }

    private function context(array $plan, string $actor, int $now): void
    {
        $this->sameActor($actor); $this->journal->assertRetirementOpen();
        $context = $this->workflow->retirementContext($plan['before'], $plan['after'], $actor, $now);
        self::keys($context, ['scope', 'admission_hash', 'inventory_hash']);
        foreach (['scope', 'admission_hash', 'inventory_hash'] as $key) if ($context[$key] !== $plan[$key]) Guard::fail('RETIREMENT_CONTEXT_CHANGED');
    }
    private function authoritative(string $digest, string $actor, int $now): ?array
    {
        $this->sameActor($actor); $record = $this->journal->journal($digest);
        if ($record === null) return null;
        RetirementIntent::validateRecord($record, $now);
        if ($record['plan']['digest'] !== $digest || $record['plan']['actor'] !== $actor) Guard::fail('RETIREMENT_OWNER_REQUIRED');
        return $record;
    }
    private function exactRecord(array $record, array $plan, string $actor, int $now): void
    {
        RetirementIntent::validateRecord($record, $now);
        if ($record['plan'] !== $plan || $record['plan']['actor'] !== $actor) Guard::fail('RETIREMENT_INTENT_CONFLICT');
    }
    private function hold(string $digest, string $actor, int $now, string $code): ?array
    {
        // A failed write may already have committed: reread, never overwrite with a stale revision.
        $record = $this->authoritative($digest, $actor, $now);
        if ($record === null) return null;
        if ($record['hold_codes'] !== [$code]) {
            $record['hold_codes'] = [$code]; $this->sameActor($actor); $this->journal->save($record);
        }
        return $record;
    }
    private function ownedJob(string $id, string $actor, int $now): array
    {
        $this->sameActor($actor); $job = $this->store->load($id);
        if ($job === null || $job['actor'] !== $actor || $now >= $job['cleanup_after']) Guard::fail('REVIEW_NOT_FOUND');
        RetirementIntent::validatePlan($job['plan'], $now);
        if ($job['plan']['actor'] !== $actor) Guard::fail('RETIREMENT_OWNER_REQUIRED');
        if ($job['approved_at'] === null) {
            if ($job['manifest'] !== null || $job['cleanup_after'] !== $job['plan']['expires_at']) Guard::fail('RETIREMENT_UI_INVALID');
        } elseif (!is_int($job['approved_at']) || $job['approved_at'] < $job['plan']['created_at'] || $job['approved_at'] >= $job['plan']['expires_at']
            || $job['approved_at'] > $now || $job['cleanup_after'] !== $job['approved_at'] + 30 * 86400
            || $job['manifest'] !== ['contract' => RetirementIntent::CONTRACT, 'intent_digest' => $job['plan']['digest']]) Guard::fail('RETIREMENT_UI_INVALID');
        return $job;
    }
    private function view(string $status, ?array $job = null, ?array $intent = null, array $codes = []): array
    {
        return ['status' => $status, 'job' => $job, 'intent' => $intent, 'hold_codes' => $codes];
    }
    private function missing(): array
    {
        return $this->view('NO_PRIVATE_RETIREMENT_INTENT', null, null, ['MANUAL_RECONCILIATION_REQUIRED'])
            + ['manual_reconciliation_required' => true, 'source_fence_modified' => false, 'provider_completion_verified' => false];
    }
    private function sameActor(string $actor): void
    {
        if (!hash_equals($this->session->actor(), $actor)) Guard::fail('OWNER_SESSION_REQUIRED');
    }
    private function csrf($nonce, string $action): void
    {
        if (!is_string($nonce) || !$this->session->verify($nonce, $action)) Guard::fail('CSRF_REJECTED');
    }
    private function action(string $operation, string $id = '', string $digest = ''): string
    {
        return 'bsre-owner-retirement/' . Workflow::digest([$operation, $id, $digest]);
    }
    private static function keys(array $value, array $expected): void
    {
        $keys = array_keys($value); sort($keys); sort($expected);
        if ($keys !== $expected) Guard::fail('INPUT_SCHEMA_INVALID');
    }
    private static function uuid($value): string
    {
        if (!is_string($value) || !preg_match('/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/D', $value)) Guard::fail('INPUT_INVALID');
        return $value;
    }
    private static function code(\Throwable $error): string
    {
        return ($error instanceof ReviewFailure || $error instanceof Failure) && preg_match('/^[A-Z][A-Z0-9_]{1,63}$/D', $error->getMessage())
            ? $error->getMessage() : 'RETIREMENT_STORAGE_UNCERTAIN';
    }

    /** Private escaped forms only. Recovery/expiry review does not grant a provider operation. */
    public function render(array $view): string
    {
        Guard::lab(); $actor = $this->session->actor();
        $job = $view['job'] ?? null; $record = $view['intent'] ?? null;
        if (($job !== null && $job['actor'] !== $actor) || ($record !== null && $record['plan']['actor'] !== $actor)) Guard::fail('RETIREMENT_OWNER_REQUIRED');
        $e = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $hidden = fn($name, $value) => '<input type="hidden" name="' . $name . '" value="' . $e($value) . '">';
        $html = '<section aria-labelledby="bsre-retirement-title"><h1 id="bsre-retirement-title">Private sender retirement</h1><p role="status">' . $e($view['status']) . '</p>'
            . '<p>Review one due closed enquiry. Sender retirement grants no purge permission. Recovery keeps the original intent and deadline.</p>';
        foreach ($view['hold_codes'] ?? [] as $code) $html .= '<p role="alert">' . $e($code) . '</p>';
        if ($job === null && $record === null) {
            $html .= '<form method="post">' . $hidden('operation', 'prepare') . $hidden('nonce', $this->session->nonce($this->action('prepare')))
                . '<label for="bsre-retire-closure">Existing closure ID</label><input id="bsre-retire-closure" name="closure_id" maxlength="36" autocomplete="off" required><button type="submit">Review exact sender retirement</button></form>';
        }
        if ($job !== null) {
            $html .= '<pre aria-label="Exact private retirement plan">' . $e(json_encode($job['plan'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>';
            if ($record === null) $html .= '<form method="post">' . $hidden('operation', 'approve') . $hidden('job', $job['id']) . $hidden('plan_digest', $job['plan']['digest'])
                . $hidden('nonce', $this->session->nonce($this->action('approve', $job['id'], $job['plan']['digest']))) . '<button type="submit">Approve this exact sender retirement</button></form>';
        }
        if ($record !== null) {
            $digest = $record['plan']['digest'];
            $html .= '<pre aria-label="Authoritative private retirement intent">' . $e(json_encode($record, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>';
            foreach (['recover' => 'Reconcile this exact retirement', 'expire' => 'Scrub expired private intent; keep closure and sender fence'] as $operation => $label) {
                $html .= '<form method="post">' . $hidden('operation', $operation) . $hidden('intent_digest', $digest)
                    . $hidden('nonce', $this->session->nonce($this->action($operation, '', $digest))) . '<button type="submit">' . $e($label) . '</button></form>';
            }
        }
        $html .= '<form method="post">' . $hidden('operation', 'review_intent') . $hidden('nonce', $this->session->nonce($this->action('review_intent')))
            . '<label for="bsre-retire-digest">Authoritative intent digest from private evidence</label><input id="bsre-retire-digest" name="intent_digest" pattern="[a-f0-9]{64}" maxlength="64" autocomplete="off" required><button type="submit">Review private intent for recovery or expiry</button></form>';
        return $html . '</section>';
    }
}
