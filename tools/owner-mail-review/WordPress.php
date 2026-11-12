<?php
declare(strict_types=1);
namespace BSRE\OwnerMailReview;
require_once __DIR__ . '/OwnerMailReview.php';
require_once __DIR__ . '/Cleanup.php';
require_once __DIR__ . '/OwnerClosure.php';

/** Re-evaluated on every read, mutation, nonce issuance and Authority call. */
final class WordPressSession implements Session
{
    private int $ownerId;
    public function __construct(int $ownerId)
    {
        Guard::lab();
        if ($ownerId < 1) Guard::fail('OWNER_ID_REQUIRED');
        $this->ownerId = $ownerId;
    }
    public function actor(): string
    {
        Guard::lab();
        if (!function_exists('is_user_logged_in') || !is_user_logged_in()
            || get_current_user_id() !== $this->ownerId || !current_user_can('manage_options')) Guard::fail('OWNER_SESSION_REQUIRED');
        return 'wp-user:' . $this->ownerId;
    }
    public function nonce(string $action): string { $this->actor(); return wp_create_nonce($action); }
    public function verify(string $nonce, string $action): bool
    {
        $this->actor();
        return wp_verify_nonce($nonce, $action) !== false;
    }
}

/** Dedicated private local-lab table. No REST, options, front-end endpoint, scheduler or install hook. */
final class WordPressStore implements Store
{
    private $db;
    private string $table;
    private array $leases = [];
    public function __construct($db)
    {
        Guard::lab();
        if ($db->prefix !== 'owner_mail_review_synthetic_') Guard::fail('SYNTHETIC_STORE_REQUIRED');
        $this->db = $db; $this->table = $db->prefix . 'jobs';
    }
    public function install(): void
    {
        Guard::lab();
        $this->query("CREATE TABLE IF NOT EXISTS {$this->table} (id char(64) PRIMARY KEY, revision bigint unsigned NOT NULL, cleanup_after bigint unsigned NOT NULL, body mediumtext NOT NULL) ENGINE=InnoDB");
    }
    public function locked(string $id, callable $operation)
    {
        Guard::lab(); Guard::hash($id);
        $name = 'bsre-owner-mail-' . substr($id, 0, 40);
        if (isset($this->leases[$id]) || (string) $this->db->get_var($this->db->prepare('SELECT GET_LOCK(%s,0)', $name)) !== '1') Guard::fail('REVIEW_BUSY');
        $this->leases[$id] = true;
        try { return $operation(); }
        finally { unset($this->leases[$id]); $this->db->get_var($this->db->prepare('SELECT RELEASE_LOCK(%s)', $name)); }
    }
    public function load(string $id): ?array
    {
        Guard::lab(); Guard::hash($id);
        $this->db->last_error = '';
        $row = $this->db->get_row($this->db->prepare("SELECT revision,cleanup_after,body FROM {$this->table} WHERE id=%s", $id), ARRAY_A);
        if ($this->db->last_error !== '') Guard::fail('REVIEW_STORAGE_UNCERTAIN');
        if ($row === null) return null;
        if (!is_string($row['body']) || strlen($row['body']) > 262144) Guard::fail('REVIEW_STORAGE_INVALID');
        $job = json_decode($row['body'], true, 40, JSON_THROW_ON_ERROR);
        if (!is_array($job)) Guard::fail('REVIEW_STORAGE_INVALID');
        $keys = array_keys($job); sort($keys);
        $expected = ['schema_version', 'id', 'revision', 'actor', 'plan', 'approved_at', 'cleanup_after', 'manifest',
            'declarations', 'verified_receipts', 'status', 'hold_codes']; sort($expected);
        if ($keys !== $expected || $job['id'] !== $id || !is_int($job['revision']) || $job['revision'] < 1
            || (string) $job['revision'] !== (string) $row['revision'] || !is_int($job['cleanup_after'])
            || (string) $job['cleanup_after'] !== (string) $row['cleanup_after'] || $job['schema_version'] !== 1
            || !is_string($job['actor']) || !is_array($job['plan']) || !is_array($job['verified_receipts'])
            || !is_array($job['declarations']) || !is_array($job['hold_codes']) || !is_string($job['status'])
            || ($job['approved_at'] !== null && !is_int($job['approved_at']))
            || ($job['manifest'] !== null && !is_array($job['manifest']))) Guard::fail('REVIEW_STORAGE_INVALID');
        return $job;
    }
    public function save(array &$job): void
    {
        Guard::lab(); Guard::hash($job['id']);
        if (!isset($this->leases[$job['id']])) Guard::fail('REVIEW_LEASE_REQUIRED');
        $next = $job; $next['revision']++;
        $json = json_encode($next, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
        if (strlen($json) > 262144) Guard::fail('REVIEW_STORAGE_LIMIT');
        if ($job['revision'] === 0) {
            $sql = $this->db->prepare("INSERT IGNORE INTO {$this->table} (id,revision,cleanup_after,body) VALUES (%s,1,%d,%s)",
                $job['id'], $next['cleanup_after'], $json);
        } else {
            $sql = $this->db->prepare("UPDATE {$this->table} SET revision=%d,cleanup_after=%d,body=%s WHERE id=%s AND revision=%d",
                $next['revision'], $next['cleanup_after'], $json, $job['id'], $job['revision']);
        }
        if ($this->db->query($sql) !== 1 || $this->load($job['id']) !== $next) Guard::fail('REVIEW_REVISION_OR_STORAGE_CONFLICT');
        $job = $next;
    }
    public function pruneExpired(int $now): void
    {
        Guard::lab();
        if ($now < 1) Guard::fail('CLOCK_INVALID');
        $this->db->last_error = '';
        $ids = $this->db->get_col($this->db->prepare("SELECT id FROM {$this->table} WHERE cleanup_after<=%d LIMIT 100", $now));
        if ($this->db->last_error !== '' || !is_array($ids)) Guard::fail('REVIEW_STORAGE_UNCERTAIN');
        foreach ($ids as $id) {
            $this->locked($id, function () use ($id, $now) {
                $job = $this->load($id);
                if ($job !== null && $job['cleanup_after'] <= $now) {
                    $this->query($this->db->prepare("DELETE FROM {$this->table} WHERE id=%s AND revision=%d AND cleanup_after<=%d", $id, $job['revision'], $now));
                }
            });
        }
    }
    private function query(string $sql): void
    {
        if ($this->db->query($sql) === false) Guard::fail('REVIEW_STORAGE_UNCERTAIN');
    }
}

/** Explicit callable only. Lab harness may supply this as its protected screen callback. */
function serve(Controller|CleanupController|OwnerClosureController $controller): void
{
    Guard::lab();
    try {
        $method = $_SERVER['REQUEST_METHOD'] ?? '';
        $input = $method === 'POST' ? wp_unslash($_POST) : (isset($_GET['job']) ? ['job' => wp_unslash($_GET['job'])] : []);
        $view = $controller->handle($method, $input, time());
        $html = $controller->render($view);
        nocache_headers();
        header('Content-Type: text/html; charset=UTF-8');
        header('X-Robots-Tag: noindex, nofollow, noarchive');
        header('Referrer-Policy: no-referrer');
        header("Content-Security-Policy: default-src 'none'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'");
        echo $html;
    } catch (\Throwable $error) {
        nocache_headers(); status_header(403);
        // Do not reflect provider exceptions, submitted fields, closure IDs or mailbox records.
        $code = $error instanceof ReviewFailure ? $error->getMessage() : 'REVIEW_HELD';
        echo '<p role="alert">' . esc_html($code) . '</p>';
    }
}
