<?php
declare(strict_types=1);

/** Synthetic native timeout exercise. No production deployment or network use. */
$purposeConcurrencyWorker = PHP_SAPI === 'cli' && ($_SERVER['argv'][1] ?? '') === 'worker';
if ($purposeConcurrencyWorker) {
    $_SERVER['HTTPS'] = 'on';
    $_SERVER['SERVER_PORT'] = '443';
    $_SERVER['REQUEST_METHOD'] = 'POST';
    require '/opt/wordpress/wp-load.php';
    require '/opt/lab/purpose/store.php';
    require '/opt/lab/purpose/purpose-attribution.php';
    require '/opt/lab/purpose/intake.php';
}

/** Observe real MariaDB errors and transaction cleanup without replacing SQL. */
final class PurposeConcurrencyDb extends wpdb {
    public bool $timeoutObserved = false;
    public bool $rollbackObserved = false;
    public bool $stateLockObserved = false;

    public function query($query) {
        $result = parent::query($query);
        if ($result === false && mysqli_errno($this->dbh) === 1205) $this->timeoutObserved = true;
        if ($query === 'ROLLBACK' && $result !== false) $this->rollbackObserved = true;
        if ($result !== false && str_contains($query, 'bsre_consent_state') && str_contains($query, 'FOR UPDATE')) {
            $this->stateLockObserved = true;
        }
        return $result;
    }
}

/** Pause only after private_history has acquired its real capture row lock. */
final class PurposeConcurrencyReaderDb extends wpdb {
    public $afterCaptureLock = null;
    private bool $paused = false;

    public function get_results($query = null, $output = OBJECT) {
        $rows = parent::get_results($query, $output);
        if (!$this->paused && is_string($query) && str_contains($query, 'bsre_consent_captures')
            && str_contains($query, 'FOR UPDATE') && is_array($rows) && count($rows) === 1) {
            $this->paused = true;
            ($this->afterCaptureLock)();
        }
        return $rows;
    }
}

function purpose_concurrency_read($stream): array {
    $line = fgets($stream, 131072);
    if ($line === false || !str_ends_with($line, "\n")) throw new RuntimeException('PURPOSE_CONCURRENCY_PIPE_TIMEOUT');
    $value = json_decode($line, true, 16, JSON_THROW_ON_ERROR);
    if (!is_array($value)) throw new RuntimeException('PURPOSE_CONCURRENCY_PIPE_INVALID');
    return $value;
}

function purpose_concurrency_write($stream, array $value): void {
    $raw = json_encode($value, JSON_THROW_ON_ERROR) . "\n";
    if (fwrite($stream, $raw) !== strlen($raw) || !fflush($stream)) throw new RuntimeException('PURPOSE_CONCURRENCY_PIPE_FAILED');
}

function purpose_concurrency_worker(): void {
    $init = purpose_concurrency_read(STDIN);
    if (!is_string($init['body'] ?? null) || strlen($init['body']) > 64000
        || !is_array($init['cookies'] ?? null) || !is_array($init['headers'] ?? null)
        || !is_int($init['privacy_page'] ?? null) || !is_string($init['ip'] ?? null)) {
        throw new RuntimeException('PURPOSE_CONCURRENCY_INIT_INVALID');
    }
    define('BSRE_PURPOSE_ATTRIBUTION_ENABLED', true);
    define('BSRE_LEAD_RECEIVER_URL', 'https://script.google.com/macros/s/BSRE_SYNTHETIC_NOT_DEPLOYED/exec');
    define('BSRE_LEAD_HMAC_SECRET', str_repeat('synthetic-key-', 4));
    define('BSRE_ROUTING_ENABLED', true);
    define('BSRE_PRIVACY_NOTICE_PAGE_ID', $init['privacy_page']);
    add_filter('home_url', fn($url, $path) => 'https://blackswanrealestate.ae' . ($path === '' ? '' : '/' . ltrim($path, '/')), 10, 2);
    add_action('rest_api_init', 'BSRE\\PurposeAttribution\\register_routes');
    wp_set_current_user(0);
    $_COOKIE = $init['cookies'];
    $_SERVER['REMOTE_ADDR'] = $init['ip'];
    $db = new PurposeConcurrencyDb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->set_prefix($GLOBALS['wpdb']->prefix);
    $db->suppress_errors(true);
    if ($db->query('SET SESSION innodb_lock_wait_timeout=1') === false) throw new RuntimeException('PURPOSE_CONCURRENCY_TIMEOUT_UNAVAILABLE');
    $GLOBALS['wpdb'] = $db;
    \BSRE\PurposeAttribution\Runtime::$store = new \BSRE\PurposeAttribution\WpConsentRepository($db);
    add_filter('pre_http_request', function ($pre, $args, $url) {
        if ($url !== BSRE_LEAD_RECEIVER_URL) throw new RuntimeException('PURPOSE_CONCURRENCY_DESTINATION');
        purpose_concurrency_write(STDOUT, ['op' => 'receiver', 'raw' => $args['body']]);
        $reply = purpose_concurrency_read(STDIN);
        return ['headers' => [], 'body' => wp_json_encode($reply['body']), 'response' => ['code' => 200]];
    }, PHP_INT_MAX, 3);
    $request = new WP_REST_Request('POST', '/bsre/v1/purpose-lead');
    foreach ($init['headers'] as $name => $value) $request->set_header($name, $value);
    $request->set_body($init['body']);
    $response = rest_do_request($request);
    purpose_concurrency_write(STDOUT, ['op' => 'result', 'status' => $response->get_status(),
        'body' => $response->get_data(), 'timeout_1205' => $db->timeoutObserved,
        'rollback' => $db->rollbackObserved, 'state_lock' => $db->stateLockObserved]);
}

/** Runs inside the existing synthetic receiver harness and reports booleans only. */
function purpose_concurrency_test(array $current, string $body, array $baseline): array {
    global $wpdb;
    $checks = [];
    $id = $baseline['request_id'];
    $wire = json_decode($body, true, 16, JSON_THROW_ON_ERROR)['wire_body'];
    $owner = get_user_by('login', 'synthetic_owner');
    $previousUser = get_current_user_id();
    // Inspect without sending queued mail. The main harness drains its outbox.
    $beforeOutbox = purpose_receiver(['op' => 'snapshot']);
    $reader = new PurposeConcurrencyReaderDb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $reader->set_prefix($wpdb->prefix);
    $reader->suppress_errors(true);
    $workerResult = null;
    $reader->afterCaptureLock = function () use (&$checks, &$workerResult, $body, $wire, $current, $baseline, $wpdb) {
        $process = proc_open(['php', '-d', 'sendmail_path=/bin/false', '/opt/lab/purpose-concurrency.php', 'worker'],
            [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => STDERR], $pipes);
        if (!is_resource($process)) throw new RuntimeException('PURPOSE_CONCURRENCY_WORKER_FAILED');
        stream_set_timeout($pipes[1], 10);
        $completed = false;
        try {
            purpose_concurrency_write($pipes[0], ['body' => $body, 'cookies' => $_COOKIE,
                'privacy_page' => BSRE_PRIVACY_NOTICE_PAGE_ID, 'ip' => $_SERVER['REMOTE_ADDR'],
                'headers' => ['origin' => 'https://blackswanrealestate.ae', 'sec-fetch-site' => 'same-origin',
                    'content-type' => 'application/json', 'x-bsre-csrf' => $current['csrf'],
                    'x-bsre-consent-decision' => $current['snapshot']['decision_version'], 'x-bsre-consent-retry' => '1']]);
            for ($messageCount = 0; $messageCount < 3; $messageCount++) {
                $message = purpose_concurrency_read($pipes[1]);
                if (($message['op'] ?? '') === 'receiver') {
                    $outgoing = json_decode($message['raw'], true, 16, JSON_THROW_ON_ERROR);
                    $checks['timeout_forward_preserves_exact_wire'] = ($outgoing['body'] ?? null) === $wire;
                    $receipt = purpose_receiver(['op' => 'post', 'raw' => $message['raw']]);
                    purpose_concurrency_write($pipes[0], ['body' => $receipt]);
                } elseif (($message['op'] ?? '') === 'result') {
                    $workerResult = $message;
                    $completed = true;
                    break;
                } else throw new RuntimeException('PURPOSE_CONCURRENCY_UNEXPECTED_MESSAGE');
            }
            if (!$completed) throw new RuntimeException('PURPOSE_CONCURRENCY_WORKER_INCOMPLETE');
            fclose($pipes[0]); fclose($pipes[1]);
            $checks['timeout_worker_exits'] = proc_close($process) === 0;
            $process = null;
            $checks['real_timeout_1205_observed'] = $workerResult['timeout_1205'] === true;
            $checks['state_locked_before_capture_timeout'] = $workerResult['state_lock'] === true;
            $checks['timeout_transaction_rolled_back'] = $workerResult['rollback'] === true;
            $response = $workerResult['body'];
            $checks['timeout_keeps_healthy_intake'] = $workerResult['status'] === 200 && ($response['accepted'] ?? false) === true
                && ($response['lead_id'] ?? null) === $baseline['lead_id'] && ($response['event_id'] ?? null) === $baseline['event_id'];
            $checks['failed_sidecar_attempt_denies_measurement'] = ($response['measurement_eligible'] ?? null) === false
                && ($response['measurement']['preferences']['analytics'] ?? null) === false
                && ($response['measurement']['preferences']['ad_measurement'] ?? null) === false;
            // The reader still holds the capture lock. A separate state lock must
            // now succeed, proving the failed writer released its earlier lock.
            $probe = new wpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
            $probe->set_prefix($wpdb->prefix);
            $probe->suppress_errors(true);
            if ($probe->query('SET SESSION innodb_lock_wait_timeout=1') === false
                || $probe->query('START TRANSACTION') === false) throw new RuntimeException('PURPOSE_CONCURRENCY_PROBE_FAILED');
            try {
                $row = $probe->get_row($probe->prepare("SELECT subject_key FROM {$probe->prefix}bsre_consent_state WHERE subject_key=%s FOR UPDATE", $baseline['subject_key']), ARRAY_A);
                $checks['timeout_releases_state_lock'] = is_array($row) && $probe->last_error === '';
                if ($probe->query('COMMIT') === false) throw new RuntimeException('PURPOSE_CONCURRENCY_PROBE_FAILED');
            } finally { $probe->query('ROLLBACK'); $probe->close(); }
        } finally {
            if (is_resource($process)) {
                proc_terminate($process);
                foreach ($pipes as $pipe) if (is_resource($pipe)) fclose($pipe);
                proc_close($process);
            }
        }
    };
    try {
        wp_set_current_user($owner->ID);
        $history = \BSRE\PurposeAttribution\private_history($reader, $id, time());
        $checks['owner_read_completes_after_timeout'] = $history['status'] === 'PRIVATE_REVIEW_ONLY'
            && $history['analytics']['first'] !== null && $history['advertising']['first'] !== null;
    } finally { wp_set_current_user($previousUser); $reader->close(); }
    $afterTimeout = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $id), ARRAY_A);
    $checks['timeout_preserves_entire_capture'] = $afterTimeout === $baseline;
    $retry = purpose_request('purpose-lead', $body, ['x-bsre-csrf' => $current['csrf'],
        'x-bsre-consent-decision' => $current['snapshot']['decision_version'], 'x-bsre-consent-retry' => '1']);
    $retryBody = $retry->get_data();
    $checks['post_timeout_unchanged_retry_recovers'] = $retry->get_status() === 200
        && ($retryBody['lead_id'] ?? null) === $baseline['lead_id'] && ($retryBody['event_id'] ?? null) === $baseline['event_id'];
    $afterRetry = $wpdb->get_row($wpdb->prepare("SELECT * FROM {$wpdb->prefix}bsre_consent_captures WHERE request_id=%s", $id), ARRAY_A);
    $checks['retry_preserves_entire_capture'] = $afterRetry === $baseline;
    $afterOutbox = purpose_receiver(['op' => 'snapshot']);
    $checks['timeout_and_retry_do_not_duplicate_row_or_mail'] = $afterOutbox['rows'] === $beforeOutbox['rows']
        && $afterOutbox['mail'] === $beforeOutbox['mail'];
    return $checks;
}

if ($purposeConcurrencyWorker) purpose_concurrency_worker();
