<?php
declare(strict_types=1);
namespace BSRE\ActualRetention;
require_once __DIR__ . '/../runtime/G5Contracts.php';

/** AEAD journal custody plus fresh independent signed anti-restore anchors. No default key/service. */
final class ActualRecoveryCustody
{
    public function __construct(private string $scope, private AnchorTransport $transport,
        private EncryptionKeys $keys, private string $trustedPublicKey)
    {
        RuntimePolicy::hash($scope);
        if (!function_exists('sodium_crypto_sign_verify_detached') || !function_exists('sodium_crypto_aead_xchacha20poly1305_ietf_encrypt')
            || strlen($trustedPublicKey) !== SODIUM_CRYPTO_SIGN_PUBLICKEYBYTES) RuntimePolicy::fail('G5_AUTHENTICATED_CUSTODY_REQUIRED');
    }

    public function scope(): string { return $this->scope; }

    public function current(): array
    {
        $nonce = bin2hex(random_bytes(32));
        return $this->verify($this->transport->current($this->scope, $nonce), $nonce, null);
    }

    public function advance(array $before, array $after): void
    {
        self::anchor($before); self::anchor($after);
        if ($before['revision'] >= PHP_INT_MAX || $after['revision'] !== $before['revision'] + 1) RuntimePolicy::fail('G5_ANCHOR_SEQUENCE_INVALID');
        $nonce = bin2hex(random_bytes(32));
        $actual = $this->verify($this->transport->advance($this->scope, $before, $after, $nonce), $nonce, $before);
        if ($actual !== $after || $this->current() !== $after) RuntimePolicy::fail('G5_ANCHOR_ADVANCE_UNCONFIRMED');
    }

    private function verify(array $receipt, string $nonce, ?array $before): array
    {
        $keys = array_keys($receipt); sort($keys);
        if ($keys !== ['signature', 'statement'] || !is_array($receipt['statement']) || !is_string($receipt['signature'])) RuntimePolicy::fail('G5_ANCHOR_AUTHENTICATION_REQUIRED');
        $s = $receipt['statement']; $fields = array_keys($s); sort($fields);
        if ($fields !== ['anchor', 'challenge', 'contract', 'expires_at', 'issued_at', 'previous', 'scope']) RuntimePolicy::fail('G5_ANCHOR_AUTHENTICATION_REQUIRED');
        $sig = base64_decode($receipt['signature'], true);
        $message = \BSRE\ClosedRetention\Workflow::digest($s);
        if (!is_string($sig) || strlen($sig) !== SODIUM_CRYPTO_SIGN_BYTES
            || !sodium_crypto_sign_verify_detached($sig, $message, $this->trustedPublicKey)
            || $s['contract'] !== 'bsre-current-anchor-v1' || $s['scope'] !== $this->scope || $s['challenge'] !== $nonce
            || $s['previous'] !== $before || !is_int($s['issued_at']) || !is_int($s['expires_at'])
            || $s['issued_at'] > time() || $s['issued_at'] < time() - 30
            || $s['expires_at'] <= time() || $s['expires_at'] > $s['issued_at'] + 60 || !is_array($s['anchor'])) RuntimePolicy::fail('G5_ANCHOR_AUTHENTICATION_REQUIRED');
        self::anchor($s['anchor']);
        return $s['anchor'];
    }

    public static function anchor(array $anchor): void
    {
        if (array_keys($anchor) !== ['revision', 'hash'] || !is_int($anchor['revision']) || $anchor['revision'] < 0
            || !is_string($anchor['hash'])) RuntimePolicy::fail('G5_ANCHOR_INVALID');
        RuntimePolicy::hash($anchor['hash']);
        if (($anchor['revision'] === 0) !== ($anchor['hash'] === str_repeat('0', 64))) RuntimePolicy::fail('G5_ANCHOR_INVALID');
    }

    public function seal(array $state, int $revision): string
    {
        if ($revision < 1) RuntimePolicy::fail('G5_ANCHOR_INVALID');
        $id = $this->keys->activeId();
        if (!preg_match('/^[A-Za-z0-9_-]{1,64}$/D', $id)) RuntimePolicy::fail('G5_CUSTODY_KEY_REQUIRED');
        $key = $this->keys->key($id);
        if (strlen($key) !== SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_KEYBYTES) RuntimePolicy::fail('G5_CUSTODY_KEY_REQUIRED');
        $nonce = random_bytes(SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES);
        $plain = json_encode($state, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
        if (strlen($plain) > 1048576) RuntimePolicy::fail('G5_JOURNAL_CAPACITY_HOLD');
        try { $cipher = sodium_crypto_aead_xchacha20poly1305_ietf_encrypt($plain, $this->scope . ':' . $revision . ':' . $id, $nonce, $key); }
        finally { sodium_memzero($key); }
        return json_encode(['version'=>1, 'key_id'=>$id, 'nonce'=>base64_encode($nonce), 'cipher'=>base64_encode($cipher)], JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES);
    }

    public function open(string $body, int $revision): array
    {
        if (strlen($body) > 1500000 || $revision < 1) RuntimePolicy::fail('G5_JOURNAL_INVALID');
        $e = json_decode($body, true, 8, JSON_THROW_ON_ERROR);
        if (!is_array($e) || array_keys($e) !== ['version', 'key_id', 'nonce', 'cipher'] || $e['version'] !== 1
            || !is_string($e['key_id']) || !preg_match('/^[A-Za-z0-9_-]{1,64}$/D', $e['key_id'])
            || !is_string($e['nonce']) || !is_string($e['cipher'])) RuntimePolicy::fail('G5_JOURNAL_INVALID');
        $key = $this->keys->key($e['key_id']); $nonce = base64_decode($e['nonce'], true); $cipher = base64_decode($e['cipher'], true);
        if (strlen($key) !== SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_KEYBYTES || !is_string($nonce)
            || strlen($nonce) !== SODIUM_CRYPTO_AEAD_XCHACHA20POLY1305_IETF_NPUBBYTES || !is_string($cipher)) RuntimePolicy::fail('G5_CUSTODY_KEY_REQUIRED');
        try { $plain = sodium_crypto_aead_xchacha20poly1305_ietf_decrypt($cipher, $this->scope . ':' . $revision . ':' . $e['key_id'], $nonce, $key); }
        finally { sodium_memzero($key); }
        if (!is_string($plain)) RuntimePolicy::fail('G5_JOURNAL_AUTHENTICATION_FAILED');
        $state = json_decode($plain, true, 48, JSON_THROW_ON_ERROR);
        if (!is_array($state)) RuntimePolicy::fail('G5_JOURNAL_INVALID');
        return $state;
    }
}
