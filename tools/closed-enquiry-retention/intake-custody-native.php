<?php
declare(strict_types=1);
/** Actual MariaDB Journal + source-derived receiver; Google services remain synthetic. */
define('BSRE_CLOSED_RETENTION_LAB', true);
define('WP_ENVIRONMENT_TYPE', 'local');
require '/opt/wordpress/wp-load.php';
require_once __DIR__ . '/fixtures.php';
require_once __DIR__ . '/ReceiverPipe.php';
use BSRE\ClosedRetention as C;

function intakeCustodyDb(): C\LeaseBoundWpdb
{
    $db = new C\LeaseBoundWpdb(DB_USER, DB_PASSWORD, DB_NAME, DB_HOST);
    $db->prefix = 'closed_intake_synthetic_';
    return $db;
}
$checks = [];
function intakeCustodyCheck(string $name, bool $ok): void
{
    global $checks;
    if (!$ok) throw new RuntimeException('Intake custody native assertion failed: ' . $name);
    $checks[$name] = true;
}
function intakeCustodyDenied(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (C\Failure $error) { return $error->getMessage() === $code; }
}
$journal = new C\LabSqlJournal(intakeCustodyDb());
$journal->install();
$f = C\fixture($journal);
$pipe = new SyntheticReceiverPipe();
$f['admission']->value['source_hashes']['receiver'] = $pipe->call('metadata')['source_hash'];
$a = $f['admission']->value;
$admissionHash = C\Workflow::digest(['wp'=>$a['wp'], 'receiver'=>$a['receiver'],
    'source_hashes'=>$a['source_hashes'], 'restore_policy_hash'=>$a['restore_policy_hash']]);
$identity = $pipe->call('init', ['accepted_at'=>strtotime($f['closure']['accepted_at_utc']),
    'now'=>$f['now'], 'admission_hash'=>$admissionHash, 'activated_at'=>$a['receiver']['activated_at']]);
$f['closure'] = array_replace($f['closure'], array_intersect_key($identity, array_flip(['request_id','lead_id','event_id'])));
$f['closure']['email_status'] = 'RETIRED_NO_COPY';
$f['closure']['mail_message_ids'] = [];
$f['closure']['revision']++;
$journal->putClosure($f['closure']);
$f['adapters']['email']->rows = [];
foreach (['capture','outcome'] as $store) foreach ($f['adapters'][$store]->rows as &$row) {
    foreach (['request_id','lead_id','event_id','fingerprint'] as $key) $row[$key] = $identity[$key];
    $row['request_ids'] = [$identity['request_id']];
}
unset($row);
$scope = C\NoMailCopyProof::scope($f['closure'], $admissionHash, $identity['fingerprint']);
$pipe->call('retire', compact('scope')); // Explicit synthetic trusted setup, not owner authority.
$resource = new SyntheticReceiverIntakeResource($pipe, $journal, $scope);
$f['adapters']['intake'] = $resource;
$f['workflow'] = new C\Workflow($journal, $f['adapters'], $f['authority'], $f['admission'], $pipe);
$id = $f['closure']['closure_id'];
intakeCustodyCheck('unleased_sql_journal_cannot_read_receiver',
    intakeCustodyDenied(fn()=>$resource->inventory($scope['request_id']), 'CLOSURE_LEASE_REQUIRED'));
$binding = $journal->locked($id, fn()=>$resource->inventory($scope['request_id'])[0]);
intakeCustodyCheck('actual_sql_custody_reads_exact_source_binding', $binding['request_id'] === $scope['request_id']
    && $binding['evidence_reference'] === 'bsre-intake26-complete-row-v1');
$fresh = new C\LabSqlJournal(intakeCustodyDb());
$foreignResource = new SyntheticReceiverIntakeResource($pipe, $fresh, $scope);
$journal->locked($id, function () use ($foreignResource, $scope, $resource, $binding) {
    intakeCustodyCheck('fresh_connection_cannot_borrow_active_sql_lease',
        intakeCustodyDenied(fn()=>$foreignResource->inventory($scope['request_id']), 'CLOSURE_LEASE_REQUIRED'));
    intakeCustodyCheck('actual_sql_custody_without_saved_intent_cannot_delete',
        intakeCustodyDenied(fn()=>$resource->removeExact($binding), 'INTAKE_PURGE_INTENT_UNVERIFIED'));
});
$plan = C\approved($f);
$intakeStep = array_search('intake', array_column($plan['resources'], 'store'), true);
intakeCustodyCheck('reviewed_plan_contains_exact_sdk_binding', is_int($intakeStep)
    && $plan['resources'][$intakeStep]['binding'] === $binding);
$intentSeen = false;
$resource->beforeDelete = function () use ($journal, $fresh, $plan, $intakeStep, $scope, $binding, $pipe, &$intentSeen) {
    $job = $fresh->journal($plan['digest']);
    $claim = $journal->assertReceiverIntakeCustody($scope, $pipe->now, $binding, $pipe->call('metadata')['source_hash']);
    $intentSeen = $job !== null && $job['steps'][$intakeStep] === 'INTENT_RECORDED'
        && $fresh->historyIncomplete() && $fresh->admissionFloor() === $scope['admission_hash']
        && $claim['plan_digest'] === $plan['digest'] && $claim['journal_revision'] === $job['revision'];
};
$resource->loseDeleteAcknowledgement = true;
$first = $f['workflow']->execute($plan, 'synthetic-owner', $f['now']);
intakeCustodyCheck('actual_sql_write_intent_visible_before_sdk_delete', $intentSeen);
intakeCustodyCheck('sdk_lost_acknowledgement_holds_actual_sql_job', $first['status'] === 'HELD'
    && $fresh->journal($plan['digest'])['steps'][$intakeStep] === 'INTENT_RECORDED');
intakeCustodyCheck('source_sdk_deleted_row_once_before_lost_ack', $pipe->call('stats')['rows'] === 0
    && $pipe->call('stats')['intake_deletes'] === 1);
$f['admission']->refresh($f['now'] + 60);
$pipe->now = $f['now'] + 60;
$newResource = new SyntheticReceiverIntakeResource($pipe, $fresh, $scope);
$adapters = array_replace($f['adapters'], ['intake'=>$newResource]);
$resumed = new C\Workflow($fresh, $adapters, $f['authority'], $f['admission'], $pipe);
$result = $resumed->execute($plan, 'synthetic-owner', $pipe->now);
intakeCustodyCheck('fresh_actual_sql_job_reconciles_sdk_absence', $result['status'] === 'COMPLETE'
    && $result['confirmed_absent'] === 4);
intakeCustodyCheck('reconciliation_does_not_repeat_sdk_delete', $newResource->deletes === 0
    && $pipe->call('stats')['intake_deletes'] === 1 && $pipe->call('stats')['mail'] === 0);
echo json_encode(['phase'=>'intake_custody_native', 'checks'=>$checks,
    'journal'=>'Actual MariaDB with dedicated connection custody and persisted write intents',
    'receiver'=>'Actual source-derived SDK calls with synthetic Google services and authority',
    'business_records'=>'Synthetic closure, intake and outcome records only',
    'production_authorized'=>false, 'real_provider_acceptance'=>false], JSON_THROW_ON_ERROR) . "\n";
