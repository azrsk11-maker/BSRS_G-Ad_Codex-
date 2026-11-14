<?php
/** Informational probe in the existing isolated runtime, before WordPress starts. */
declare(strict_types=1);

function namespace_probe(string $binary, array $flags): array
{
    $process = proc_open(array_merge([$binary], $flags, ['/bin/true']),
        [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    if (!is_resource($process)) return ['status' => 'START_FAILED'];
    fclose($pipes[0]);
    stream_set_blocking($pipes[1], false);
    stream_set_blocking($pipes[2], false);
    $start = microtime(true);
    $error = '';
    do {
        stream_get_contents($pipes[1], 2048);
        $error .= stream_get_contents($pipes[2], max(0, 2048 - strlen($error)));
        $state = proc_get_status($process);
        if (!$state['running']) break;
        if (microtime(true) - $start >= 2) {
            proc_terminate($process, 9);
            foreach ([1, 2] as $stream) fclose($pipes[$stream]);
            proc_close($process);
            return ['status' => 'TIMEOUT'];
        }
        usleep(10000);
    } while (true);
    foreach ([1, 2] as $stream) fclose($pipes[$stream]);
    proc_close($process);
    return ['status' => $state['exitcode'] === 0 ? 'SUCCEEDED' : 'DENIED_OR_FAILED',
        'exit_code' => $state['exitcode'],
        'operation_not_permitted_reported' => str_contains($error, 'Operation not permitted')];
}

$status = file_get_contents('/proc/self/status');
$binary = null;
foreach (['/usr/bin/unshare', '/bin/unshare'] as $candidate) {
    if (is_executable($candidate)) { $binary = $candidate; break; }
}
$user = $binary ? namespace_probe($binary, ['--user', '--map-root-user']) : ['status' => 'COMMAND_UNAVAILABLE'];
$mount = $binary && $user['status'] === 'SUCCEEDED'
    ? namespace_probe($binary, ['--user', '--map-root-user', '--mount'])
    : ['status' => 'NOT_ATTEMPTED'];
echo json_encode([
    'phase' => 'browser_sandbox_prerequisites',
    'scope' => 'INFORMATIONAL_CURRENT_CONTAINER_ONLY',
    'no_new_privileges' => preg_match('/^NoNewPrivs:\s*1$/m', $status) === 1,
    'user_namespace_probe' => $user,
    'user_mount_namespace_probe' => $mount,
    'chromium_installed_or_started' => false,
    'browser_sandbox_accepted' => false,
    'isolation_settings_changed' => false,
    'wordpress_started' => false,
], JSON_THROW_ON_ERROR) . "\n";
