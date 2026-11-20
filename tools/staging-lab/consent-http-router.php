<?php
/** Loopback-only HTTP fixture. Emulates the upstream TLS termination flag. */
declare(strict_types=1);

$routes = [
    '/context' => '/bsre/v1/consent/context',
    '/update' => '/bsre/v1/consent/update',
];
$route = $routes[$_SERVER['REQUEST_URI'] ?? ''] ?? null;
if (PHP_SAPI !== 'cli-server' || ($_SERVER['REMOTE_ADDR'] ?? '') !== '127.0.0.1' || $route === null) {
    http_response_code(404);
    return;
}
$_SERVER['HTTPS'] = 'on';
$_GET['rest_route'] = $route;
require '/opt/wordpress/wp-load.php';
add_filter('home_url', static fn() => 'https://blackswanrealestate.ae');
require '/opt/wordpress/wp-blog-header.php';
