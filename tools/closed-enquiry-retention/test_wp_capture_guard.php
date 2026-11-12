<?php
declare(strict_types=1);
/** Host/custody rejection checks only; no SQL engine or provider-success claim. */
class wpdb
{
    public string $prefix = 'closed_capture_synthetic_';
    public int $queries = 0;
    public bool $save_queries = false;
    public function suppress_errors($value = true): bool { return true; }
    public function query($sql) { $this->queries++; throw new RuntimeException('Guard test must not issue SQL'); }
    public function check_connection($allow_bail = true) { return false; }
    public function db_connect($allow_bail = true) { return false; }
}
$captureEnvironment = 'local'; $captureHome = 'http://bsre.invalid';
function wp_get_environment_type(): string { return $GLOBALS['captureEnvironment']; }
function home_url(): string { return $GLOBALS['captureHome']; }
function add_action(...$arguments): void {}
require __DIR__ . '/WpCaptureResource.php';
use BSRE\ClosedRetention as C;
$db = new C\LeaseBoundWpdb();
$uninitializedJournal = (new ReflectionClass(C\LabSqlJournal::class))->newInstanceWithoutConstructor();
$checks = [];
function captureGuardCheck(string $name, callable $operation, string $code): void
{
    global $checks;
    try { $operation(); throw new RuntimeException('Capture guard did not reject'); }
    catch (C\Failure $error) { if ($error->getMessage() !== $code) throw $error; }
    $checks[$name] = true;
}
captureGuardCheck('default_disabled', fn()=>new C\WpCaptureResource($db,$uninitializedJournal),'CAPTURE_ISOLATED_LAB_ONLY');
define('BSRE_CLOSED_RETENTION_LAB',true);
$captureEnvironment='production';
captureGuardCheck('production_environment_denied',fn()=>new C\WpCaptureResource($db,$uninitializedJournal),'CAPTURE_ISOLATED_LAB_ONLY');
$captureEnvironment='local';$captureHome='https://example.invalid';
captureGuardCheck('nonlocal_origin_denied',fn()=>new C\WpCaptureResource($db,$uninitializedJournal),'CAPTURE_ISOLATED_LAB_ONLY');
$captureHome='http://bsre.invalid';$db->prefix='wp_';
captureGuardCheck('ordinary_database_prefix_denied',fn()=>new C\WpCaptureResource($db,$uninitializedJournal),'CAPTURE_ISOLATED_LAB_ONLY');
$db->prefix=C\WpCaptureResource::PREFIX;
captureGuardCheck('unloaded_original_source_denied',fn()=>new C\WpCaptureResource($db,$uninitializedJournal),'CAPTURE_SOURCE_UNVERIFIED');
define('ABSPATH',__DIR__.'/');
require __DIR__.'/../staging-lab/fixtures/bsre-enquiries/includes/consent-store.php';
$journal=new C\LabSqlJournal($db);
$provider=new C\WpCaptureResource($db,$journal);
captureGuardCheck('inventory_requires_actual_journal_lease',fn()=>$provider->inventory('00000000-0000-4000-8000-000000000001'),'CLOSURE_LEASE_REQUIRED');
captureGuardCheck('read_requires_actual_journal_lease',fn()=>$provider->read('00000000-0000-4000-8000-000000000001'),'CLOSURE_LEASE_REQUIRED');
captureGuardCheck('delete_requires_actual_journal_lease',fn()=>$provider->removeExact(['key'=>'00000000-0000-4000-8000-000000000001']),'CLOSURE_LEASE_REQUIRED');
$other=new C\LeaseBoundWpdb();
captureGuardCheck('same_namespace_different_connection_denied',fn()=>$journal->assertProviderCustody($other,'00000000-0000-4000-8000-000000000001'),'CAPTURE_CONNECTION_CONFLICT');
$db->prefix='wp_';
captureGuardCheck('prefix_rechecked_before_operation',fn()=>$provider->read('00000000-0000-4000-8000-000000000001'),'CAPTURE_ISOLATED_LAB_ONLY');
$db->prefix=C\WpCaptureResource::PREFIX;$captureEnvironment='production';
captureGuardCheck('environment_rechecked_before_operation',fn()=>$provider->inventory('00000000-0000-4000-8000-000000000001'),'CAPTURE_ISOLATED_LAB_ONLY');
$captureEnvironment='local';$db->save_queries=true;
captureGuardCheck('dynamic_connection_query_recording_denied',fn()=>$provider->read('00000000-0000-4000-8000-000000000001'),'CAPTURE_QUERY_LOGGING_UNVERIFIED');
$db->save_queries=false;define('SAVEQUERIES',true);
captureGuardCheck('wordpress_query_recording_denied',fn()=>$provider->read('00000000-0000-4000-8000-000000000001'),'CAPTURE_QUERY_LOGGING_UNVERIFIED');
if($db->queries!==0||$other->queries!==0)throw new RuntimeException('Rejected capture guard issued SQL');
echo json_encode(['phase'=>'wp_capture_guard','checks'=>count($checks),'status'=>'PASS','sql_queries'=>0,'native_provider_executed'=>false],JSON_THROW_ON_ERROR)."\n";
