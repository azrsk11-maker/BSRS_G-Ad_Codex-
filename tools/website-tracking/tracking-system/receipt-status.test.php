<?php
declare(strict_types=1);
require __DIR__ . '/receipt-status.php';
use function BSRE\ReceiptRecovery\status_request;
use function BSRE\ReceiptRecovery\status_receipt;

$checks = 0;
function verify(bool $condition): void {
    global $checks;
    if (!$condition) throw new RuntimeException('Receipt status contract failed at check ' . ($checks + 1));
    $checks++;
}
$id = '11111111-1111-4111-8111-111111111111';
$secret = str_repeat('synthetic-', 4);
$request = status_request($id, $secret, 1794150000000);
verify($request['signature'] === hash_hmac('sha256', "bsre-receipt-status-v1\n1794150000000\n{$id}", $secret));
verify(!isset($request['body']) && count($request) === 5);
$accepted = (object) ['status' => 'ACCEPTED', 'request_id' => $id,
    'lead_id' => 'BSRE-22222222-2222-4222-8222-222222222222', 'event_id' => 'evt_33333333-3333-4333-8333-333333333333'];
verify(status_receipt($accepted, $id) !== null);
foreach (['request_id' => '44444444-4444-4444-8444-444444444444', 'status' => 'UNCONFIRMED',
    'lead_id' => 'BSRE-invalid', 'event_id' => 'evt_invalid'] as $key => $value) {
    $bad = clone $accepted;
    $bad->$key = $value;
    verify(status_receipt($bad, $id) === null);
}
$extra = clone $accepted;
$extra->email = 'fixture@example.invalid';
verify(status_receipt($extra, $id) === null);
verify(status_receipt((array) $accepted, $id) === null);
verify(status_receipt((object) ['accepted' => false, 'code' => 'VALIDATION_FAILED'], $id) === null);
foreach ([$id . 'x', '11111111-1111-1111-8111-111111111111'] as $bad) {
    try { status_request($bad, $secret, 1794150000000); verify(false); }
    catch (InvalidArgumentException $expected) { verify(true); }
}
echo json_encode(['receipt_status_contract' => 'PASS', 'checks' => $checks]) . "\n";
