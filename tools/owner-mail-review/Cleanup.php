<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;
require_once __DIR__ . '/OwnerMailReview.php';
use BSRE\ClosedRetention\Journal;
use BSRE\ClosedRetention\Workflow;

/** Separate exact-plan authorization. Works from the authoritative journal after UI-cache expiry. */
final class CleanupController
{
    private Workflow $workflow;
    private ReviewAuthority $authority;
    private Journal $journal;
    private Session $session;
    public function __construct(Workflow $workflow, ReviewAuthority $authority, Journal $journal, Session $session)
    {
        $this->workflow = $workflow; $this->authority = $authority; $this->journal = $journal; $this->session = $session;
    }
    private function action(string $operation, string $digest = ''): string { return 'bsre-owner-mail-cleanup/' . $operation . '/' . $digest; }
    public function handle(string $method, array $input, int $now): array
    {
        Guard::lab(); $actor = $this->session->actor();
        if ($now < 1) Guard::fail('CLOCK_INVALID');
        if ($method === 'GET' && $input === []) return ['status' => 'CLEANUP_REVIEW', 'plan' => null];
        if ($method !== 'POST') Guard::fail('METHOD_NOT_ALLOWED');
        $keys = array_keys($input); sort($keys);
        if ($keys !== ['nonce', 'operation', 'plan_digest']) Guard::fail('INPUT_SCHEMA_INVALID');
        $operation = $input['operation']; $digest = Guard::hash($input['plan_digest']);
        if (!in_array($operation, ['review_cleanup', 'expire'], true) || !is_string($input['nonce'])
            || !$this->session->verify($input['nonce'], $this->action($operation, $operation === 'expire' ? $digest : ''))) Guard::fail('CSRF_REJECTED');
        $record = $this->journal->journal($digest);
        if ($record === null) return ['status' => 'NO_PRIVATE_JOURNAL', 'plan' => null];
        $plan = $record['plan'];
        if ($plan['digest'] !== $digest) Guard::fail('EXACT_PLAN_CONFLICT');
        if ($operation === 'review_cleanup') return ['status' => 'REVIEW_EXACT_CLEANUP', 'plan' => $plan];
        $this->authority->authorizeCleanup($actor, $digest, $now);
        try { $result = $this->workflow->expire($plan, $actor, $now); }
        finally { $this->authority->clearCleanup(); }
        return ['status' => $result['status'], 'plan' => null, 'hold_codes' => $result['hold_codes']];
    }
    public function render(array $view): string
    {
        Guard::lab(); $this->session->actor();
        $e = fn($s) => htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
        $html = '<section aria-labelledby="bsre-cleanup-title"><h1 id="bsre-cleanup-title">Private retention journal cleanup</h1><p role="status">' . $e($view['status']) . '</p>'
            . '<p>This separate owner action scrubs private workflow records only after the recovery window. Unfinished provider work remains subject to manual reconciliation.</p>';
        foreach ($view['hold_codes'] ?? [] as $code) $html .= '<p role="alert">' . $e($code) . '</p>';
        if ($view['plan'] === null) {
            $html .= '<form method="post"><input type="hidden" name="operation" value="review_cleanup"><input type="hidden" name="nonce" value="'
                . $e($this->session->nonce($this->action('review_cleanup'))) . '"><label for="bsre-cleanup-digest">Exact plan digest from private review evidence</label>'
                . '<input id="bsre-cleanup-digest" name="plan_digest" required pattern="[a-f0-9]{64}" maxlength="64" autocomplete="off"><button type="submit">Review exact private cleanup</button></form>';
        } else {
            $plan = $view['plan'];
            $html .= '<pre aria-label="Exact private plan for cleanup">' . $e(json_encode($plan, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)) . '</pre>'
                . '<form method="post"><input type="hidden" name="operation" value="expire"><input type="hidden" name="plan_digest" value="' . $e($plan['digest'])
                . '"><input type="hidden" name="nonce" value="' . $e($this->session->nonce($this->action('expire', $plan['digest'])))
                . '"><button type="submit">Authorize cleanup of this exact private journal</button></form>';
        }
        return $html . '</section>';
    }
}
