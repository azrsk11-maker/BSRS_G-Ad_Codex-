<?php
declare(strict_types=1);
/** Pure row/source-boundary checks. No database or native acceptance claim. */
class wpdb
{
    public string $prefix = 'closed_capture_synthetic_';
    public bool $save_queries = false;
    public int $queries = 0;
    public function suppress_errors($value = true): bool { return true; }
    public function query($sql) { $this->queries++; throw new RuntimeException('No SQL permitted'); }
}
function wp_get_environment_type(): string { return 'local'; }
function home_url(): string { return 'http://bsre.invalid'; }
function add_action(...$arguments): void {}
define('ABSPATH', __DIR__ . '/');
define('BSRE_CLOSED_RETENTION_LAB', true);
require __DIR__ . '/../staging-lab/fixtures/bsre-enquiries/includes/consent-store.php';
require __DIR__ . '/../website-tracking/tracking-system/purpose-attribution.php';
require __DIR__ . '/WpCaptureResource.php';
use BSRE\ClosedRetention as C;
use BSRE\Enquiries as E;
$checks = [];
function purposeCheck(string $name, bool $ok): void
{
    global $checks;
    if (!$ok) throw new RuntimeException('Capture purpose assertion failed: ' . $name);
    $checks[$name] = true;
}
function purposeDenied(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (C\Failure $error) { return $error->getMessage() === $code; }
}
$normalize = new ReflectionMethod(C\WpCaptureResource::class, 'normalize');
$binding = new ReflectionMethod(C\WpCaptureResource::class, 'binding');
$predicate = new ReflectionMethod(C\WpCaptureResource::class, 'exactPredicate');
$row = ['request_id'=>'00000000-0000-4000-8000-000000000001', 'fingerprint'=>str_repeat('1',64),
    'subject_key'=>'', 'original_revision'=>'0', 'decision_version'=>str_repeat('2',32), 'notice_version'=>'SYNTHETIC',
    'analytics'=>'0', 'ad_measurement'=>'0', 'personalization'=>'0', 'preference_expires_at'=>'0',
    'eligible'=>'0', 'known'=>'0', 'created_at'=>'1700000000', 'state'=>'ACCEPTED', 'uncertain'=>'1',
    'delivery_pending'=>'0', 'click_capture_state'=>'NOT_PERMITTED', 'gclid_first'=>'', 'gclid_last'=>'',
    'gclid_first_captured_ms'=>'0', 'gclid_last_captured_ms'=>'0',
    'lead_id'=>'BSRE-00000000-0000-4000-8000-000000000002', 'event_id'=>'evt_00000000-0000-4000-8000-000000000003'];
$legacy = $normalize->invoke(null, $row);
purposeCheck('original_23_columns_still_supported', count($legacy) === 23 && $legacy['known'] === 0);
$purpose = $row + ['purpose_version'=>'0', 'purpose_hash'=>'', 'purpose_record_hash'=>'', 'purpose_json'=>null];
$null = $normalize->invoke(null, $purpose, true);
purposeCheck('historical_27_column_legacy_null_preserved', count($null) === 27 && $null['purpose_json'] === null);
$purpose['purpose_json']=''; $empty = $normalize->invoke(null, $purpose, true);
purposeCheck('null_and_empty_have_distinct_complete_row_evidence',
    $binding->invoke(null,$null)['evidence_hash'] !== $binding->invoke(null,$empty)['evidence_hash']);
[$nullSql,$nullValues]=$predicate->invoke(null,$null,true);
[$emptySql,$emptyValues]=$predicate->invoke(null,$empty,true);
purposeCheck('null_delete_predicate_preserves_sql_null_semantics',str_ends_with($nullSql,'purpose_json IS NULL')
    && count($nullValues)===26 && str_ends_with($emptySql,'BINARY purpose_json=BINARY %s')
    && count($emptyValues)===27 && $emptyValues[26]==='');
$purpose['purpose_json']='{"synthetic":true}';
purposeCheck('version_zero_cannot_hide_purpose_json', purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_PURPOSE_INVALID'));
$purpose['purpose_json']='';$purpose['purpose_hash']=str_repeat('a',64);
purposeCheck('version_zero_cannot_hide_purpose_hash', purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_PURPOSE_INVALID'));
$purpose['purpose_version']='1';$purpose['purpose_json']='{"version":1,"synthetic":true}';
$purpose['purpose_record_hash']=hash('sha256',$purpose['fingerprint']."\n".$purpose['purpose_hash']."\n".$purpose['purpose_json']);
$valid=$normalize->invoke(null,$purpose,true);
purposeCheck('purpose_integrity_uses_actual_runtime', $valid['purpose_version']===1);
$first=$binding->invoke(null,$valid);
$purpose['purpose_json']='{"version":1,"synthetic":"changed"}';
purposeCheck('changed_purpose_body_with_old_hash_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_PURPOSE_INVALID'));
$purpose['purpose_record_hash']=hash('sha256',$purpose['fingerprint']."\n".$purpose['purpose_hash']."\n".$purpose['purpose_json']);
$changed=$binding->invoke(null,$normalize->invoke(null,$purpose,true));
purposeCheck('valid_changed_purpose_body_invalidates_reviewed_binding', $changed['evidence_hash']!==$first['evidence_hash']);
[$jsonSql,$jsonValues]=$predicate->invoke(null,$normalize->invoke(null,$purpose,true),true);
purposeCheck('exact_delete_binds_unmodified_private_json_bytes',str_ends_with($jsonSql,'BINARY purpose_json=BINARY %s')
    && $jsonValues[26]===$purpose['purpose_json']);
purposeCheck('private_purpose_values_not_returned_in_binding', !array_key_exists('purpose_json',$changed)
    && !array_key_exists('subject_key',$changed) && !str_contains(json_encode($changed,JSON_THROW_ON_ERROR),'synthetic'));
$purpose['purpose_json']=null;
purposeCheck('version_one_null_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_PURPOSE_INVALID'));
$purpose['purpose_json']=str_repeat('x',48001);
purposeCheck('oversized_purpose_text_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_ROW_INVALID'));
$purpose['purpose_json']='"'.str_repeat('x',47998).'"';
$purpose['purpose_record_hash']=hash('sha256',$purpose['fingerprint']."\n".$purpose['purpose_hash']."\n".$purpose['purpose_json']);
purposeCheck('exact_48000_byte_text_boundary_retained',strlen($normalize->invoke(null,$purpose,true)['purpose_json'])===48000);
$purpose['purpose_hash']=str_repeat('z',64);
purposeCheck('nonhex_purpose_hash_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_PURPOSE_INVALID'));
$purpose['purpose_hash']=null;
purposeCheck('null_purpose_hash_type_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_ROW_INVALID'));
$purpose=$row+['purpose_version'=>2,'purpose_hash'=>'','purpose_record_hash'=>'','purpose_json'=>''];
purposeCheck('unsupported_purpose_version_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_ROW_INVALID'));
purposeCheck('candidate_columns_require_explicit_candidate_store',purposeDenied(fn()=>$normalize->invoke(null,$purpose),'CAPTURE_ROW_INVALID'));
$purpose['purpose_version']='01';
purposeCheck('noncanonical_integer_spelling_denied',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_ROW_INVALID'));
$purpose=$row+['purpose_version'=>0,'purpose_hash'=>'','purpose_record_hash'=>'','purpose_json'=>'','unexpected'=>'private'];
purposeCheck('unexpected_column_cannot_escape_complete_binding',purposeDenied(fn()=>$normalize->invoke(null,$purpose,true),'CAPTURE_ROW_INVALID'));
$db=new C\LeaseBoundWpdb();$journal=new C\LabSqlJournal($db);
$store=new E\WpConsentRepository($db);
$provider=new C\WpCaptureResource($db,$journal,$store);
purposeCheck('explicit_original_repository_keeps_custody_guard',purposeDenied(fn()=>$provider->read($row['request_id']),'CLOSURE_LEASE_REQUIRED'));
$other=new C\LeaseBoundWpdb();
purposeCheck('repository_on_another_connection_denied_before_sql',purposeDenied(
    fn()=>new C\WpCaptureResource($db,$journal,new E\WpConsentRepository($other)),'CAPTURE_SOURCE_UNVERIFIED'));
$foreign=new class implements E\ConsentRepository {
    public function current(string $subject): ?array { return null; }
    public function choose(string $subject,array $flags,string $notice,int $now,bool $uncertain=false): array { return []; }
    public function stage(array $capture): array { return []; }
    public function link(string $request,string $fingerprint,string $lead,string $event): array { return []; }
    public function uncertain(string $request,string $fingerprint): void {}
    public function revoked(string $subject,int $revision,string $purpose): bool { return true; }
    public function exportRows(array $requests): array { return []; }
};
purposeCheck('foreign_repository_class_denied_before_sql',purposeDenied(fn()=>new C\WpCaptureResource($db,$journal,$foreign),'CAPTURE_SOURCE_UNVERIFIED'));
purposeCheck('pure_checks_issue_zero_sql',$db->queries===0&&$other->queries===0);
echo json_encode(['phase'=>'wp_capture_purpose_pure','status'=>'PASS','checks'=>count($checks),
    'sql_queries'=>0,'native_acceptance'=>false],JSON_THROW_ON_ERROR)."\n";
