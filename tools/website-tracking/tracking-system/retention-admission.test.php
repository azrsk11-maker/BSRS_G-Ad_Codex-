<?php
declare(strict_types=1);

namespace BSRE\PurposeAttribution {
    function repository() { return $GLOBALS['admission_test_store']; }
}
namespace {
    define('ARRAY_A', 'ARRAY_A');
    define('BSRE_RETENTION_ADMISSION_ENABLED', true);
    define('BSRE_RETENTION_ADMISSION_GENERATION', str_repeat('a', 64));
    define('BSRE_RETENTION_ADMISSION_ACTIVATED_AT', time() - 2000);
    define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/SYNTHETIC_ADMISSION/exec');
    define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
    require __DIR__ . '/retention-admission.php';

    use BSRE\RetentionAdmission as Admission;

    $checks = [];
    function check(string $name, bool $passed): void {
        global $checks;
        if (!$passed) throw new RuntimeException('Admission check failed: ' . $name);
        $checks[$name] = true;
    }
    function denies(callable $call, string $message): bool {
        try { $call(); return false; }
        catch (Throwable $error) { return $error->getMessage() === $message; }
    }
    final class AdmissionTestDb {
        public string $prefix = 'synthetic_';
        public string $last_error = '';
        public array $rows = [];
        public int $reads = 0;
        public bool $failure = false;
        public function prepare(string $sql, string $id): string { return str_replace('%s', $id, $sql); }
        public function get_results(string $sql, $format): array {
            $this->reads++;
            if (!str_contains($sql, 'FOR UPDATE')) throw new RuntimeException('Missing row lock');
            if ($this->failure) $this->last_error = 'SYNTHETIC';
            return $this->rows;
        }
    }
    final class AdmissionTestStore {
        public function admissionContract(): string { return Admission\CONTRACT; }
    }
    final class AdmissionTestServer {
        public array $routes = [];
        public function get_routes(): array { return $this->routes; }
    }
    function rest_get_server() { return $GLOBALS['admission_test_server']; }

    $id = '11111111-1111-4111-8111-111111111111';
    $otherId = '22222222-2222-4222-8222-222222222222';
    $session = str_repeat('s', 32);
    $now = time(); $gate = Admission\configuration();
    $proof = Admission\sign_new_request($id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now);
    check('fresh proof accepted', Admission\valid_proof($proof, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now, true));
    check('proof is receiver-bound', $proof['audience'] === hash('sha256', BSRE_LEAD_RECEIVER_URL));
    check('proof lifetime exactly 900 seconds', $proof['expires_at'] - $proof['issued_at'] === 900);
    check('other UUID denied', !Admission\valid_proof($proof, $otherId, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now, true));
    check('other session denied', !Admission\valid_proof($proof, $id, str_repeat('t', 32), BSRE_LEAD_HMAC_SECRET, $gate, $now, false));
    check('exact expiry denies insertion', !Admission\valid_proof($proof, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now + 900, true));
    check('known expiry can authenticate replay', Admission\valid_proof($proof, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now + 900, false));
    $newGate = $gate; $newGate['generation'] = str_repeat('b', 64); $newGate['activated_at'] = $now + 1;
    check('old generation denies insertion', !Admission\valid_proof($proof, $id, $session, BSRE_LEAD_HMAC_SECRET, $newGate, $now + 2, true));
    check('known old generation authenticates replay', Admission\valid_proof($proof, $id, $session, BSRE_LEAD_HMAC_SECRET, $newGate, $now + 2, false));
    foreach (['signature' => str_repeat('0', 64), 'audience' => str_repeat('d', 64), 'issued_at' => (string) $now, 'version' => '1'] as $key => $value) {
        $bad = $proof; $bad[$key] = $value;
        check('malformed or tampered ' . $key . ' denied', !Admission\valid_proof($bad, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now, false));
    }
    $bad = $proof; $bad['extra'] = true;
    check('extra proof property denied', !Admission\valid_proof($bad, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now, true));
    $bad = $proof; $bad['expires_at']++; $bad['signature'] = Admission\signature($bad, BSRE_LEAD_HMAC_SECRET);
    check('signed larger lifetime denied', !Admission\valid_proof($bad, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now, true));
    $bad = $proof; $bad['signature'] = hash_hmac('sha256', 'v1\n' . $id, BSRE_LEAD_HMAC_SECRET);
    check('other purpose signature denied', !Admission\valid_proof($bad, $id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now, true));

    $capture = ['request_id' => $id, 'fingerprint' => str_repeat('e', 64)];
    $db = new AdmissionTestDb();
    Admission\Runtime::$session = $session; Admission\Runtime::$proof = $proof;
    Admission\assert_capture($db, $capture);
    check('unknown proof checked under row lock', $db->reads === 1);
    Admission\Runtime::$proof = null;
    check('unknown unproved capture denied', denies(fn() => Admission\assert_capture($db, $capture), 'ADMISSION_REQUIRED'));
    $expired = Admission\sign_new_request($id, $session, BSRE_LEAD_HMAC_SECRET, $gate, $now - 1000);
    Admission\Runtime::$proof = $expired;
    check('unknown expired capture denied', denies(fn() => Admission\assert_capture($db, $capture), 'ADMISSION_REQUIRED'));
    $db->rows = [$capture];
    Admission\assert_capture($db, $capture);
    check('known matching capture retains receipt path', true);
    $db->rows[0]['fingerprint'] = str_repeat('f', 64);
    check('known changed body conflicts', denies(fn() => Admission\assert_capture($db, $capture), 'REQUEST_ID_CONFLICT'));
    $db->rows = [$capture, $capture];
    check('duplicate capture denied', denies(fn() => Admission\assert_capture($db, $capture), 'ADMISSION_STORAGE_UNAVAILABLE'));
    $db->rows = []; $db->failure = true;
    check('storage error denied', denies(fn() => Admission\assert_capture($db, $capture), 'ADMISSION_STORAGE_UNAVAILABLE'));

    $server = new AdmissionTestServer();
    $GLOBALS['admission_test_server'] = $server; $GLOBALS['admission_test_store'] = new AdmissionTestStore();
    foreach (['/lead' => 'receive_legacy', '/purpose-lead' => 'receive_purpose', '/receipt-recovery/proof' => 'proof'] as $path => $callback) {
        $server->routes['/bsre/v1' . $path] = [['methods' => ['POST' => true], 'callback' => 'BSRE\\RetentionAdmission\\' . $callback]];
    }
    check('exact routes and store detected', Admission\readback()['routes_installed'] && Admission\readback()['store_installed']);
    $server->routes['/bsre/v1/lead'][] = ['methods' => ['POST' => true], 'callback' => 'BSRE\\Enquiries\\receive'];
    check('additional legacy POST callback invalidates gate', !Admission\readback()['routes_installed']);
    echo json_encode(['phase' => 'retention_admission_pure', 'status' => 'PASS', 'checks' => count($checks), 'native_database_verified' => false]) . "\n";
}
