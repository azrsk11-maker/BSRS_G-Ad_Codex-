<?php
declare(strict_types=1);
require __DIR__ . '/receipt-recovery.php';

use function BSRE\ReceiptRecovery\{issue, recover};

function same($expected, $actual): void
{
    if ($expected !== $actual) throw new RuntimeException('Recovery assertion failed');
}

$id = '00000000-0000-4000-8000-000000000001';
$session = str_repeat('s', 32);
$secret = str_repeat('k', 32);
$now = 1800000000;
$proof = issue($id, $session, $secret, $now);
$row = ['request_id' => $id, 'state' => 'ACCEPTED', 'delivery_pending' => '0',
    'lead_id' => 'TEST_ONLY_REFERENCE', 'event_id' => 'TEST_ONLY_EVENT', 'gclid' => 'TEST_ONLY_PRIVATE'];
$unknown = ['status' => 'UNCONFIRMED'];
$lookup = function ($request) use ($id, $row) { same($id, $request); return $row; };
$calls = 0;
$mustNotLookup = function () use (&$calls) { $calls++; throw new RuntimeException('Unexpected lookup'); };
same(['status' => 'ACCEPTED', 'reference' => 'TEST_ONLY_REFERENCE'], recover($proof, $session, $secret, $now + 899, $lookup));
same($unknown, recover($proof, $session, $secret, $now + 900, $mustNotLookup));
same($unknown, recover($proof, $session, $secret, $now - 1, $mustNotLookup));
same($unknown, recover($proof, str_repeat('t', 32), $secret, $now, $mustNotLookup));
same($unknown, recover($proof, $session, str_repeat('z', 32), $now, $mustNotLookup));
same($unknown, recover('1' . substr($proof, 1), $session, $secret, $now, $mustNotLookup));
same(0, $calls);
foreach ([null, ['state' => 'STAGED'] + $row, ['delivery_pending' => '1'] + $row,
    ['request_id' => 'different'] + $row, ['event_id' => ''] + $row] as $candidate) {
    same($unknown, recover($proof, $session, $secret, $now, fn () => $candidate));
}
same($unknown, recover($proof, $session, $secret, $now, fn () => throw new RuntimeException('Unavailable')));
echo "Receipt recovery checks passed\n";
