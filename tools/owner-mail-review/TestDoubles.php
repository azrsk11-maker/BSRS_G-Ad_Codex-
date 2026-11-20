<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;
require_once __DIR__ . '/OwnerMailReview.php';
require_once __DIR__ . '/../closed-enquiry-retention/fixtures.php';
use BSRE\ClosedRetention as C;

/** Synthetic test custody only; never selected by application code. */
final class MemoryStore implements Store
{
    public array $jobs = [];
    public int $reads = 0;
    public $afterSave = null;
    private array $leases = [];
    public function locked(string $id, callable $operation)
    {
        if (isset($this->leases[$id])) Guard::fail('REVIEW_BUSY');
        $this->leases[$id] = true;
        try { return $operation(); } finally { unset($this->leases[$id]); }
    }
    public function load(string $id): ?array { $this->reads++; return $this->jobs[$id] ?? null; }
    public function save(array &$job): void
    {
        if (!isset($this->leases[$job['id']])) Guard::fail('REVIEW_LEASE_REQUIRED');
        if (($this->jobs[$job['id']]['revision'] ?? 0) !== $job['revision']) Guard::fail('REVIEW_REVISION_OR_STORAGE_CONFLICT');
        $job['revision']++; $this->jobs[$job['id']] = $job;
        if ($this->afterSave) ($this->afterSave)($job);
    }
    public function pruneExpired(int $now): void
    {
        foreach ($this->jobs as $id => $job) if ($job['cleanup_after'] <= $now) unset($this->jobs[$id]);
    }
}

final class SyntheticSession implements Session
{
    public bool $allowed = true;
    public string $identity = 'synthetic-owner';
    public string $token = 'synthetic-session-1';
    public function actor(): string { if (!$this->allowed) Guard::fail('OWNER_SESSION_REQUIRED'); return $this->identity; }
    public function nonce(string $action): string { return hash('sha256', $this->actor() . '/' . $this->token . '/' . $action); }
    public function verify(string $nonce, string $action): bool { return hash_equals($this->nonce($action), $nonce); }
}

/** Complete surface has two explicit synthetic sets. Test operator mutates sets outside Controller. */
final class SyntheticMailReadback implements MailReadback
{
    public C\MemoryResource $mail;
    public array $trash = [];
    public array $overrides = [];
    public bool $throw = false;
    public int $reads = 0;
    public function __construct(C\MemoryResource $mail) { $this->mail = $mail; }
    public function observe(array $manifest, int $now): array
    {
        $this->reads++;
        if ($this->throw) throw new \RuntimeException('PRIVATE_PROVIDER_CANARY');
        $binding = $manifest['binding'];
        return array_replace(['status' => isset($this->mail->rows[$binding['key']]) || isset($this->trash[$binding['key']]) ? 'PRESENT' : 'ABSENT',
            'mailbox' => $binding['mailbox'], 'message_id' => $binding['message_id'], 'binding_hash' => C\Workflow::digest($binding),
            'authoritative' => true, 'complete_surface' => true, 'includes_trash' => true, 'observed_at' => $now,
            'evidence_reference' => 'synthetic-independent-mailbox-observation', 'evidence_hash' => str_repeat('a', 64)], $this->overrides);
    }
}

function fixture(?Store $store = null, ?Session $session = null): array
{
    $f = C\fixture();
    $store ??= new MemoryStore(); $session ??= new SyntheticSession();
    $authority = new ReviewAuthority($store, $session);
    $workflow = new C\Workflow($f['journal'], $f['adapters'], $authority, $f['admission']);
    $readback = new SyntheticMailReadback($f['adapters']['email']);
    $controller = new Controller($workflow, $authority, $store, $session, $readback);
    return array_merge($f, compact('store', 'session', 'readback', 'controller', 'authority', 'workflow'));
}

/** Exercise the actual rendered form fields, including action-scoped nonce. */
function form(Controller $controller, array $view, string $operation): array
{
    preg_match_all('/<form method="post">(.*?)<\/form>/s', $controller->render($view), $forms);
    foreach ($forms[1] as $body) {
        preg_match_all('/<input type="hidden" name="([^"]+)" value="([^"]*)">/', $body, $inputs, PREG_SET_ORDER);
        $values = [];
        foreach ($inputs as $input) $values[html_entity_decode($input[1], ENT_QUOTES, 'UTF-8')] = html_entity_decode($input[2], ENT_QUOTES, 'UTF-8');
        if (($values['operation'] ?? '') === $operation) return $values;
    }
    throw new \RuntimeException('Synthetic form not rendered: ' . $operation);
}

function prepare(array $f): array
{
    $input = form($f['controller'], ['status' => 'READY', 'job' => null], 'prepare');
    $input['closure_id'] = $f['closure']['closure_id'];
    return $f['controller']->handle('POST', $input, $f['now']);
}

function approve(array $f, array $view): array
{
    return $f['controller']->handle('POST', form($f['controller'], $view, 'approve'), $f['now']);
}

function handoff(array $f, array $view): array
{
    return form($f['controller'], $view, 'receipt') + ['evidence_reference' => 'synthetic-owner-action', 'evidence_hash' => str_repeat('9', 64)];
}
