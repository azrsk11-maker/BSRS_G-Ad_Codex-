<?php
declare(strict_types=1);
/** Explicit candidate drop-in. Never install over an existing provider drop-in. */
if (!defined('BSRE_CANONICAL_LEASE_ENABLED') || BSRE_CANONICAL_LEASE_ENABLED === false) return;
if (BSRE_CANONICAL_LEASE_ENABLED !== true || !defined('ABSPATH') || !defined('WP_CONTENT_DIR')
    || !class_exists('wpdb', false)) throw new RuntimeException('CANONICAL_BOOTSTRAP_INVALID');
global $wpdb;
if (isset($wpdb)) throw new RuntimeException('CANONICAL_DATABASE_ALREADY_CREATED');
foreach (['BSRE_CANONICAL_LEASE_SOURCE_SHA256', 'BSRE_CANONICAL_LEASE_PRODUCER_SHA256', 'BSRE_CANONICAL_LEASE_BOOTSTRAPPED'] as $bsreBinding) {
    if (defined($bsreBinding)) throw new RuntimeException('CANONICAL_BINDING_ALREADY_DEFINED');
}
if (defined('SAVEQUERIES') && SAVEQUERIES) throw new RuntimeException('CANONICAL_QUERY_LOGGING_FORBIDDEN');
foreach (array_merge(get_declared_classes(), get_declared_interfaces(), get_declared_traits()) as $bsreSymbol) {
    if (strncasecmp($bsreSymbol, 'BSRE\\', 5) === 0) throw new RuntimeException('CANONICAL_NAMESPACE_OCCUPIED');
}
$bsreContent = rtrim(WP_CONTENT_DIR, '/');
if ($bsreContent !== __DIR__ || realpath($bsreContent) !== $bsreContent
    || realpath($bsreContent . '/db.php') !== $bsreContent . '/db.php'
    || (defined('WP_PLUGIN_DIR') && WP_PLUGIN_DIR !== $bsreContent . '/plugins')) throw new RuntimeException('CANONICAL_LAYOUT_INVALID');
$bsreRoot = $bsreContent . '/plugins/bsre-enquiries';
$bsreManifestPath = $bsreRoot . '/includes/candidate/runtime/canonical-source.json';
if (realpath($bsreManifestPath) !== $bsreManifestPath || !is_file($bsreManifestPath)
    || filesize($bsreManifestPath) > 65536) throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED');
$bsreManifestBytes = file_get_contents($bsreManifestPath);
if (!is_string($bsreManifestBytes) || !hash_equals('__BSRE_CODE_MANIFEST_SHA256__', hash('sha256', $bsreManifestBytes))) throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED');
try { $bsreManifest = json_decode($bsreManifestBytes, true, 16, JSON_THROW_ON_ERROR); }
catch (Throwable $bsreError) { throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED'); }
if (!is_array($bsreManifest)) throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED');
$bsreKeys = array_keys($bsreManifest); sort($bsreKeys);
if ($bsreKeys !== ['deployment_prohibited', 'files', 'profile', 'schema']
    || $bsreManifest['schema'] !== 'bsre-canonical-lease-source-v1'
    || $bsreManifest['profile'] !== 'G35_CANONICAL_LEASE_CODE_ONLY'
    || $bsreManifest['deployment_prohibited'] !== true || !is_array($bsreManifest['files'])
    || count($bsreManifest['files']) !== 55) throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED');
foreach ($bsreManifest['files'] as $bsreRelative => $bsreDigest) {
    if (!is_string($bsreRelative) || !preg_match('~^[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$~D', $bsreRelative)
        || in_array('.', explode('/', $bsreRelative), true) || in_array('..', explode('/', $bsreRelative), true)
        || !is_string($bsreDigest) || !preg_match('/^[a-f0-9]{64}$/D', $bsreDigest)) throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED');
    $bsreFile = $bsreRoot . '/' . $bsreRelative;
    if (realpath($bsreFile) !== $bsreFile || !is_file($bsreFile)
        || !hash_equals($bsreDigest, hash_file('sha256', $bsreFile))) throw new RuntimeException('CANONICAL_SOURCE_UNVERIFIED');
}
$bsreProducer = $bsreRoot . '/includes/candidate/runtime/CanonicalCaptureProducer.php';
if (realpath($bsreProducer) !== $bsreProducer || !is_file($bsreProducer)
    || !hash_equals('__BSRE_PRODUCER_SHA256__', hash_file('sha256', $bsreProducer))) throw new RuntimeException('CANONICAL_PRODUCER_UNVERIFIED');
foreach (['DB_USER', 'DB_PASSWORD', 'DB_NAME', 'DB_HOST'] as $bsreConstant) {
    if (!defined($bsreConstant) || !is_string(constant($bsreConstant))) throw new RuntimeException('CANONICAL_DATABASE_CONFIG_INVALID');
}
if (DB_NAME === '' || DB_HOST === '') throw new RuntimeException('CANONICAL_DATABASE_CONFIG_INVALID');
require_once $bsreRoot . '/includes/candidate/closed-enquiry-retention/Workflow.php';
require_once $bsreRoot . '/includes/candidate/closed-enquiry-retention/LeaseBoundWpdb.php';
define('BSRE_CANONICAL_LEASE_SOURCE_SHA256', '__BSRE_BOUND_MANIFEST_SHA256__');
define('BSRE_CANONICAL_LEASE_PRODUCER_SHA256', '__BSRE_BOUND_PRODUCER_SHA256__');
// This is the first canonical object, in the normal core db.php initialization seam.
$wpdb = new \BSRE\ClosedRetention\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
if ($wpdb->get_var('SELECT DATABASE()') !== DB_NAME) throw new RuntimeException('CANONICAL_DATABASE_UNVERIFIED');
define('BSRE_CANONICAL_LEASE_BOOTSTRAPPED', true);
// No prefix/options/repository/user checks run before core initializes them.
