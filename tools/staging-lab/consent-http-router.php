<?php
/** Loopback-only HTTP fixture. Emulates the upstream TLS termination flag. */
declare(strict_types=1);

$routes = [
    '/context' => '/bsre/v1/consent/context',
    '/update' => '/bsre/v1/consent/update',
];
$path = $_SERVER['REQUEST_URI'] ?? '';
$route = $routes[$path] ?? null;
if (PHP_SAPI !== 'cli-server' || ($_SERVER['REMOTE_ADDR'] ?? '') !== '127.0.0.1') {
    http_response_code(404);
    return;
}
$browserOrigin = 'https://127.0.0.1:18764';
if (($_SERVER['HTTP_HOST'] ?? '') === '127.0.0.1:18764') {
    header("Content-Security-Policy: default-src 'none'; script-src 'self'; connect-src 'self'; frame-src 'self'; base-uri 'none'");
    header('Cache-Control: no-store');
    if ($path === '/browser' || $path === '/browser-return') {
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><meta charset="utf-8"><title>Synthetic consent test</title><body>'
            . '<script defer src="/browser-config.js"></script><script defer src="/bridge.js"></script>'
            . '<script defer src="/browser-test.js"></script></body>';
        return;
    }
    if (in_array($path, ['/browser-config.js', '/bridge.js', '/browser-test.js'], true)) {
        header('Content-Type: text/javascript; charset=utf-8');
        if ($path === '/browser-config.js') {
            echo 'window.BSRETrackingConfig={cmpProviderId:"bsre_first_party_v1",'
                . 'consentContextEndpoint:location.origin+"/context",consentUpdateEndpoint:location.origin+"/update"};';
        } else {
            readfile($path === '/bridge.js'
                ? '/opt/wordpress/wp-content/plugins/bsre-enquiries/assets/consent-bridge.js'
                : '/opt/lab/consent-browser.js');
        }
        return;
    }
    if ($path === '/browser-result' && ($_SERVER['REQUEST_METHOD'] ?? '') === 'POST'
        && ($_SERVER['HTTP_ORIGIN'] ?? '') === $browserOrigin) {
        $result = file_get_contents('php://input', false, null, 0, 1024);
        file_put_contents('/tmp/bsre-consent-browser-result.json', $result, LOCK_EX);
        http_response_code(204);
        return;
    }
    // The pinned plugin checks its production hostname. Translate only the
    // exact disposable browser origin after the browser sends it itself.
    if (($_SERVER['HTTP_ORIGIN'] ?? '') === $browserOrigin) {
        $_SERVER['HTTP_ORIGIN'] = 'https://blackswanrealestate.ae';
    }
}
if ($route === null) {
    http_response_code(404);
    return;
}
$_SERVER['HTTPS'] = 'on';
$_GET['rest_route'] = $route;
require '/opt/wordpress/wp-load.php';
add_filter('home_url', static fn() => 'https://blackswanrealestate.ae');
require '/opt/wordpress/wp-blog-header.php';
