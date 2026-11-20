<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;

require_once __DIR__ . '/../closed-enquiry-retention/Workflow.php';
use BSRE\ClosedRetention\Workflow;
use BSRE\ClosedRetention\Authority;

/** Private custody only: plans, mailbox identifiers and evidence must never be public options or logs. */
interface Store
{
    public function locked(string $id, callable $operation);
    public function load(string $id): ?array;
    public function save(array &$job): void;
    public function pruneExpired(int $now): void;
}

interface Session
{
    /** Authenticated, explicitly nominated owner; never a request parameter. */
    public function actor(): string;
    public function nonce(string $action): string;
    public function verify(string $nonce, string $action): bool;
}

/** Server-owned independent readback; no implementation may infer absence from an owner declaration. */
interface MailReadback
{
    /**
     * Exact result schema is checked below. UNKNOWN/errors hold. ABSENT requires an authoritative,
     * complete marketing-mailbox observation, including Trash. No delete method or OAuth is provided.
     */
    public function observe(array $manifest, int $now): array;
}

final class UnverifiedReadback implements MailReadback
{
    public function observe(array $manifest, int $now): array { return ['status' => 'UNKNOWN']; }
}

final class Guard
{
    public static function lab(): void
    {
        if (!defined('BSRE_OWNER_MAIL_REVIEW_LAB') || BSRE_OWNER_MAIL_REVIEW_LAB !== true
            || !defined('BSRE_CLOSED_RETENTION_LAB') || BSRE_CLOSED_RETENTION_LAB !== true
            || !function_exists('wp_get_environment_type') || wp_get_environment_type() !== 'local'
            || !function_exists('home_url') || home_url() !== 'http://bsre.invalid') self::fail('ISOLATED_LAB_ONLY');
    }
    public static function fail(string $code): never { throw new ReviewFailure($code); }
    public static function text($value, int $max = 256): string
    {
        if (!is_string($value) || $value === '' || strlen($value) > $max || trim($value) !== $value
            || preg_match('/[\x00-\x1f\x7f]/', $value)) self::fail('INPUT_INVALID');
        return $value;
    }
    public static function hash($value): string
    {
        if (!is_string($value) || !preg_match('/^[a-f0-9]{64}$/D', $value)) self::fail('INPUT_INVALID');
        return $value;
    }
}

final class ReviewFailure extends \RuntimeException {}

/** Existing Workflow stays the sole purge engine. Only server-held exact approval/verified receipts pass. */
final class ReviewAuthority implements Authority
{
    private Store $store;
    private Session $session;
    private ?string $jobId = null;
    private ?array $cleanup = null;
    public function __construct(Store $store, Session $session) { $this->store = $store; $this->session = $session; }
    public function select(string $jobId): void { $this->jobId = Guard::hash($jobId); }
    /** Server-only one-request authorization, called by CleanupController after exact-plan nonce validation. */
    public function authorizeCleanup(string $actor, string $digest, int $now): void
    {
        if (!$this->canReview($actor)) Guard::fail('OWNER_SESSION_REQUIRED');
        $this->cleanup = [$actor, Guard::hash($digest), $now];
    }
    public function clearCleanup(): void { $this->cleanup = null; }
    public function canReview(string $actor): bool
    {
        try { Guard::lab(); return hash_equals($this->session->actor(), $actor); }
        catch (\Throwable $error) { return false; }
    }
    private function approved(string $actor, string $digest): ?array
    {
        if (!$this->canReview($actor) || $this->jobId === null) return null;
        $job = $this->store->load($this->jobId);
        return $job !== null && !array_key_exists('contract', $job['plan'])
            && $job['actor'] === $actor && $job['plan']['digest'] === $digest
            && is_int($job['approved_at']) ? $job : null;
    }
    public function canApply(string $actor, string $planDigest, int $now, string $action): bool
    {
        if ($action === 'EXPIRE_PRIVATE_JOURNAL') return $this->canReview($actor) && $this->cleanup === [$actor, $planDigest, $now];
        $job = $this->approved($actor, $planDigest);
        return $action === 'PURGE' && $job !== null && $job['approved_at'] <= $now && $now < $job['cleanup_after'];
    }
    public function mailReceipt(string $actor, string $planDigest, string $messageId): ?array
    {
        $job = $this->approved($actor, $planDigest);
        if ($job === null) return null;
        // Requests can supply declaration fields only. This map is populated after server readback.
        return $job['verified_receipts'][$messageId]['receipt'] ?? null;
    }
}

final class Controller
{
    private Workflow $workflow;
    private ReviewAuthority $authority;
    private Store $store;
    private Session $session;
    private MailReadback $readback;
    public function __construct(Workflow $workflow, ReviewAuthority $authority, Store $store, Session $session, ?MailReadback $readback = null)
    {
        $this->workflow = $workflow; $this->authority = $authority; $this->store = $store;
        $this->session = $session; $this->readback = $readback ?? new UnverifiedReadback();
    }

    /** No hook/route registration. Caller supplies a server clock, never a posted timestamp. */
    public function handle(string $method, array $input, int $now): array
    {
        Guard::lab();
        $actor = $this->session->actor(); // Authentication precedes reads, pruning and nonce issuance.
        if ($now < 1) Guard::fail('CLOCK_INVALID');
        $this->store->pruneExpired($now);
        if ($method === 'GET') {
            if ($input === []) return ['status' => 'READY', 'job' => null];
            self::keys($input, ['job']);
            $id = Guard::hash($input['job']);
            return $this->store->locked($id, function () use ($id, $actor, $now) {
                $job = $this->owned($id, $actor, $now);
                return ['status' => $job['status'], 'job' => $job];
            });
        }
        if ($method !== 'POST') Guard::fail('METHOD_NOT_ALLOWED');
        $action = Guard::text($input['operation'] ?? null, 16);
        if (!in_array($action, ['prepare', 'approve', 'receipt', 'resume'], true)) Guard::fail('ACTION_INVALID');
        if ($action === 'prepare') {
            self::keys($input, ['operation', 'nonce', 'closure_id']);
            $this->csrf($input['nonce'], $this->action('prepare', '', '', ''));
            $closure = Guard::text($input['closure_id'], 36);
            $plan = $this->workflow->prepare($closure, $actor, $now);
            $id = bin2hex(random_bytes(32));
            return $this->store->locked($id, function () use ($id, $plan, $actor) {
                $job = ['schema_version' => 1, 'id' => $id, 'revision' => 0, 'actor' => $actor, 'plan' => $plan,
                    'approved_at' => null, 'cleanup_after' => $plan['expires_at'], 'manifest' => null,
                    'declarations' => [], 'verified_receipts' => [], 'status' => 'REVIEW_EXACT_PLAN', 'hold_codes' => []];
                $this->store->save($job);
                return ['status' => $job['status'], 'job' => $job];
            });
        }
        $expected = ['operation', 'nonce', 'job', 'plan_digest'];
        if ($action === 'receipt') $expected = array_merge($expected, ['binding_hash', 'evidence_reference', 'evidence_hash']);
        self::keys($input, $expected);
        $id = Guard::hash($input['job']);
        $digest = Guard::hash($input['plan_digest']);
        $bindingHash = $action === 'receipt' ? Guard::hash($input['binding_hash']) : '';
        $this->csrf($input['nonce'], $this->action($action, $id, $digest, $bindingHash));
        return $this->store->locked($id, function () use ($id, $digest, $bindingHash, $action, $actor, $input, $now) {
            $job = $this->owned($id, $actor, $now);
            if (!hash_equals($job['plan']['digest'], $digest)) Guard::fail('EXACT_PLAN_CONFLICT');
            $this->authority->select($id);
            if ($action === 'approve') {
                if ($job['approved_at'] === null) {
                    if ($now < $job['plan']['created_at'] || $now >= $job['plan']['expires_at']) Guard::fail('PLAN_EXPIRED');
                    $job['approved_at'] = $now;
                    $job['cleanup_after'] = $now + 30 * 86400;
                    $this->store->save($job); // Committed before invoking the existing journaled workflow.
                }
            } elseif ($job['approved_at'] === null) Guard::fail('EXACT_APPROVAL_REQUIRED');
            if ($action === 'receipt') $this->collect($job, $bindingHash, $input, $now);
            $result = $this->workflow->execute($job['plan'], $actor, $now);
            $job['status'] = $result['status']; $job['hold_codes'] = $result['hold_codes'];
            if ($result['status'] === 'AWAITING_OWNER_MAIL_ACTION') {
                $manifest = $this->workflow->ownerMailAction($job['plan'], $actor, $now);
                if ($manifest === null) Guard::fail('MANIFEST_UNAVAILABLE');
                $job['manifest'] = $manifest;
            }
            $this->store->save($job);
            return ['status' => $job['status'], 'job' => $job];
        });
    }

    private function collect(array &$job, string $bindingHash, array $input, int $now): void
    {
        $manifest = $job['manifest'];
        if (!is_array($manifest) || $manifest['plan_digest'] !== $job['plan']['digest']
            || !hash_equals(Workflow::digest($manifest['binding']), $bindingHash)) Guard::fail('EXACT_MESSAGE_CONFLICT');
        // Recheck current closure, resource scope and binding through the existing authority engine.
        $current = $this->workflow->ownerMailAction($job['plan'], $job['actor'], $now);
        if ($current !== null && $current !== $manifest) Guard::fail('EXACT_MESSAGE_CONFLICT');
        $declaration = ['actor' => $job['actor'], 'plan_digest' => $job['plan']['digest'], 'binding_hash' => $bindingHash,
            'evidence_reference' => Guard::text($input['evidence_reference']), 'evidence_hash' => Guard::hash($input['evidence_hash'])];
        $message = $manifest['binding']['message_id'];
        if (isset($job['verified_receipts'][$message])) {
            if ($job['declarations'][$bindingHash] !== $declaration) Guard::fail('RECEIPT_CONFLICT');
            return; // Same handoff retry reuses committed receipt; Workflow independently rereads the provider.
        }
        $job['declarations'][$bindingHash] = $declaration;
        $job['status'] = 'AWAITING_INDEPENDENT_READBACK'; $job['hold_codes'] = ['MAIL_ABSENCE_UNVERIFIED'];
        $this->store->save($job); // An ambiguous probe cannot erase the owner handoff.
        try { $proof = $this->readback->observe($manifest, $now); }
        catch (\Throwable $error) { Guard::fail('MAIL_READBACK_UNCERTAIN'); }
        if (($proof['status'] ?? null) !== 'ABSENT') Guard::fail('MAIL_ABSENCE_UNVERIFIED');
        self::keys($proof, ['status', 'mailbox', 'message_id', 'binding_hash', 'authoritative', 'complete_surface',
            'includes_trash', 'observed_at', 'evidence_reference', 'evidence_hash']);
        if ($proof['status'] !== 'ABSENT' || $proof['authoritative'] !== true || $proof['complete_surface'] !== true
            || $proof['includes_trash'] !== true || $proof['mailbox'] !== 'marketing@blackswanrealestate.ae'
            || $proof['mailbox'] !== $manifest['binding']['mailbox'] || $proof['message_id'] !== $message
            || $proof['binding_hash'] !== $bindingHash || !is_int($proof['observed_at'])
            || $proof['observed_at'] < $manifest['intent_at'] || $proof['observed_at'] > $now
            || $proof['observed_at'] < $now - 300) Guard::fail('MAIL_ABSENCE_UNVERIFIED');
        Guard::text($proof['evidence_reference']); Guard::hash($proof['evidence_hash']);
        $receipt = ['schema_version' => 1, 'actor' => $job['actor'], 'plan_digest' => $job['plan']['digest'],
            'mailbox' => $proof['mailbox'], 'message_id' => $message, 'binding_hash' => $bindingHash,
            'observed_at' => $proof['observed_at'], 'evidence_reference' => $proof['evidence_reference'],
            'evidence_hash' => Workflow::digest(['declaration' => $declaration, 'independent_readback' => $proof])];
        $job['verified_receipts'][$message] = ['receipt' => $receipt, 'readback' => $proof];
        $this->store->save($job); // Lost response can safely resume without uploading or deleting mail.
    }

    private function owned(string $id, string $actor, int $now): array
    {
        $job = $this->store->load($id);
        if ($job === null || $job['actor'] !== $actor || $now >= $job['cleanup_after']) Guard::fail('REVIEW_NOT_FOUND');
        return $job;
    }
    private function csrf($nonce, string $action): void
    {
        if (!is_string($nonce) || !$this->session->verify($nonce, $action)) Guard::fail('CSRF_REJECTED');
    }
    private static function keys(array $input, array $expected): void
    {
        $actual = array_keys($input); sort($actual); sort($expected);
        if ($actual !== $expected) Guard::fail('INPUT_SCHEMA_INVALID');
    }
    private function action(string $operation, string $id, string $digest, string $binding): string
    {
        return 'bsre-owner-mail/' . Workflow::digest([$operation, $id, $digest, $binding]);
    }

    /** Private accessible HTML. No external resources, browser storage, analytics or uploads. */
    public function render(array $view): string
    {
        Guard::lab(); $this->session->actor();
        $e = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $hidden = fn($name, $value) => '<input type="hidden" name="' . $e($name) . '" value="' . $e($value) . '">';
        $html = '<section aria-labelledby="bsre-owner-mail-title"><h1 id="bsre-owner-mail-title">Owner mailbox retention review</h1>'
            . '<p>Synthetic local lab. Private owner review. Mailbox actions are performed by the owner in marketing@blackswanrealestate.ae.</p>'
            . '<p role="status">' . $e($view['status']) . '</p>';
        $job = $view['job'];
        if ($job === null) {
            return $html . '<form method="post">' . $hidden('operation', 'prepare')
                . $hidden('nonce', $this->session->nonce($this->action('prepare', '', '', '')))
                . '<label for="bsre-closure">Exact closure ID</label><input id="bsre-closure" name="closure_id" required maxlength="36" autocomplete="off">'
                . '<button type="submit">Prepare private review</button></form>'
                . '<form method="get"><label for="bsre-existing-review">Existing private review ID</label><input id="bsre-existing-review" name="job" required pattern="[a-f0-9]{64}" maxlength="64" autocomplete="off">'
                . '<button type="submit">Reopen private review</button></form></section>';
        }
        if ($job['actor'] !== $this->session->actor()) Guard::fail('REVIEW_NOT_FOUND');
        $html .= '<p>Private review ID: <code>' . $e($job['id']) . '</code></p><p>Plan digest: <code>' . $e($job['plan']['digest']) . '</code></p>'
            . '<p>Review the complete plan before approval. It includes the mailbox copies and associated enquiry records.</p>'
            . '<pre aria-label="Exact private retention plan">' . $e(json_encode($job['plan'], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>';
        foreach ($job['hold_codes'] as $code) $html .= '<p role="alert">' . $e($code) . '</p>';
        $form = function (string $operation, string $binding = '') use ($job, $hidden): string {
            $body = '<form method="post">' . $hidden('operation', $operation) . $hidden('job', $job['id'])
                . $hidden('plan_digest', $job['plan']['digest'])
                . $hidden('nonce', $this->session->nonce($this->action($operation, $job['id'], $job['plan']['digest'], $binding)));
            return $body . ($binding === '' ? '' : $hidden('binding_hash', $binding));
        };
        if ($job['approved_at'] === null) {
            $html .= '<p>Initial approval expires at ' . $e(gmdate('Y-m-d H:i:s \U\T\C', $job['plan']['expires_at'])) . '.</p>'
                . $form('approve') . '<button type="submit">Approve this exact plan and record intent</button></form>';
        } else {
            if ($job['manifest'] !== null && $job['status'] !== 'COMPLETE') {
                $m = $job['manifest']; $b = $m['binding'];
                $html .= '<h2>Exact owner mailbox action</h2><p>Identify this exact copy using all identifiers below. Delete this copy under the approved procedure and check Trash. A missing search result does not prove absence.</p><dl>';
                foreach (['mailbox', 'message_id', 'rfc822_message_id', 'fingerprint', 'request_id', 'lead_id', 'event_id'] as $key) {
                    $html .= '<dt>' . $e($key) . '</dt><dd><code>' . $e($b[$key]) . '</code></dd>';
                }
                $html .= '</dl><p>Owner handoff records your evidence reference and hash. Completion requires independent server readback over the complete mailbox including Trash.</p>'
                    . $form('receipt', Workflow::digest($b))
                    . '<label for="bsre-mail-evidence">Private owner action evidence reference</label><input id="bsre-mail-evidence" name="evidence_reference" required maxlength="256" autocomplete="off">'
                    . '<label for="bsre-mail-hash">Evidence SHA-256</label><input id="bsre-mail-hash" name="evidence_hash" required pattern="[a-f0-9]{64}" maxlength="64" autocomplete="off">'
                    . '<button type="submit">Record owner handoff and request independent readback</button></form>';
            }
            $html .= $form('resume') . '<button type="submit">Recheck and resume approved plan</button></form>';
        }
        return $html . '</section>';
    }
}
