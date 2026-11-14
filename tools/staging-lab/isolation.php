<?php
// No WordPress includes are permitted here. RFC5737 addresses are test probes.
$checks = [];
function verify(string $name, bool $ok): void {
    global $checks;
    $checks[$name] = $ok;
    if (!$ok) { fwrite(STDERR, "Isolation failed: $name\n"); exit(1); }
}
verify('non_root', function_exists('posix_geteuid') && posix_geteuid() !== 0);
$interfaces = array_values(array_diff(scandir('/sys/class/net'), ['.', '..']));
verify('loopback_only', $interfaces === ['lo']);
$routes = preg_split('/\r?\n/', trim(file_get_contents('/proc/net/route')));
verify('no_ipv4_routes', count($routes) === 1);
$status = file_get_contents('/proc/self/status');
verify('no_capabilities', preg_match('/^CapEff:\s*0+$/m', $status) === 1);
verify('no_new_privileges', preg_match('/^NoNewPrivs:\s*1$/m', $status) === 1);
verify('no_docker_socket', !file_exists('/var/run/docker.sock'));
verify('readonly_application', !is_writable('/opt/wordpress') && !is_writable('/opt/reviewed'));
verify('tmpfs_available', is_writable('/tmp') && !file_exists('/tmp/database'));
$server = stream_socket_server('tcp://127.0.0.1:0', $errno, $error);
verify('loopback_listener', $server !== false);
$address = stream_socket_get_name($server, false);
$client = stream_socket_client('tcp://' . $address, $errno, $error, 1);
$peer = stream_socket_accept($server, 1);
verify('positive_loopback_control', $client !== false && $peer !== false);
fwrite($client, 'synthetic');
verify('positive_loopback_transfer', fread($peer, 9) === 'synthetic');
fclose($client); fclose($peer); fclose($server);
foreach (['smtp' => 'tcp://192.0.2.1:25', 'https_socket' => 'tcp://192.0.2.1:443', 'ipv6_socket' => 'tcp://[2001:db8::1]:443'] as $name => $target) {
    $socket = @stream_socket_client($target, $errno, $error, 1);
    verify($name . '_denied', $socket === false);
}
$http = @file_get_contents('http://192.0.2.1/', false, stream_context_create(['http' => ['timeout' => 1]]));
verify('http_stream_denied', $http === false);
$dns = socket_create(AF_INET, SOCK_DGRAM, SOL_UDP);
verify('dns_probe_socket', $dns !== false);
// DNS transport must fail at the kernel, rather than merely return NXDOMAIN.
$query = hex2bin('123401000001000000000000') . "\x07example\x03com\0\x00\x01\x00\x01";
verify('dns_transport_denied', @socket_sendto($dns, $query, strlen($query), 0, '192.0.2.1', 53) === false);
socket_close($dns);
exec('curl --noproxy "*" --silent --connect-timeout 1 --max-time 2 http://192.0.2.1/ >/dev/null 2>&1', $unused, $exit);
verify('curl_denied', $exit !== 0);
// MariaDB package may install cron binaries; none may be running.
$comm = glob('/proc/[0-9]*/comm');
$schedulers = array_filter($comm, fn($p) => in_array(trim(@file_get_contents($p)), ['cron', 'crond', 'sendmail', 'exim4', 'postfix']));
verify('no_scheduler_or_mail_daemon', count($schedulers) === 0);
echo json_encode(['phase' => 'pre_wordpress_isolation', 'status' => 'PASS', 'checks' => $checks, 'wordpress_started' => false], JSON_UNESCAPED_SLASHES) . "\n";
