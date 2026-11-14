<?php
declare(strict_types=1);
namespace BSRE\ClosedRetention;
require_once __DIR__ . '/LabAdapters.php';

function syntheticUuid(int $number): string
{
    return '00000000-0000-4000-8000-' . str_pad((string) $number, 12, '0', STR_PAD_LEFT);
}

function fixture(?Journal $journal = null): array
{
    $now = strtotime('2026-11-08T12:00:00Z');
    $closure = ['schema_version' => 1, 'closure_id' => syntheticUuid(1), 'revision' => 1,
        'status' => 'UNSUCCESSFUL', 'request_id' => syntheticUuid(2), 'lead_id' => 'BSRE-' . syntheticUuid(3),
        'event_id' => 'evt_' . syntheticUuid(4), 'accepted_at_utc' => '2025-01-01T12:00:00Z',
        'closed_at_utc' => '2025-11-08T12:00:00Z', 'recorded_at_utc' => '2025-11-09T12:00:00Z',
        'reviewer' => 'synthetic-owner', 'evidence_reference' => 'synthetic-closure-evidence',
        'evidence_hash' => str_repeat('1', 64), 'outcome_ids' => [syntheticUuid(5), syntheticUuid(6)],
        'mail_message_ids' => ['synthetic-message-1'], 'email_status' => 'SENT'];
    $common = ['request_id' => $closure['request_id'], 'request_ids' => [$closure['request_id']],
        'lead_id' => $closure['lead_id'], 'event_id' => $closure['event_id'],
        'fingerprint' => str_repeat('2', 64), 'evidence_reference' => 'synthetic-resource-evidence', 'evidence_hash' => str_repeat('3', 64)];
    $adapters = [];
    $adapters['intake'] = new MemoryResource(['synthetic-intake' => ['key' => 'synthetic-intake'] + $common]);
    $adapters['capture'] = new MemoryResource(['synthetic-capture' => ['key' => 'synthetic-capture'] + $common]);
    $outcomes = [];
    foreach ($closure['outcome_ids'] as $key) $outcomes[$key] = ['key' => $key] + $common;
    $adapters['outcome'] = new MemoryResource($outcomes);
    $mail = ['key' => 'synthetic-message-1', 'mailbox' => 'marketing@blackswanrealestate.ae',
        'message_id' => 'synthetic-message-1', 'rfc822_message_id' => '<synthetic-message@example.invalid>'] + $common;
    $adapters['email'] = new MemoryResource([$mail['key'] => $mail]);
    $journal ??= new MemoryJournal();
    if ($journal instanceof MemoryJournal) $journal->closures[$closure['closure_id']] = $closure;
    elseif ($journal instanceof LabSqlJournal) $journal->putClosure($closure);
    $authority = new LabAuthority();
    $admission = new LabAdmission($now);
    $workflow = new Workflow($journal, $adapters, $authority, $admission);
    return compact('now', 'closure', 'adapters', 'journal', 'authority', 'admission', 'workflow');
}

function approved(array &$fixture): array
{
    $plan = $fixture['workflow']->prepare($fixture['closure']['closure_id'], 'synthetic-owner', $fixture['now']);
    $fixture['authority']->approved = $plan['digest'];
    return $plan;
}

/** The test operator acts outside the workflow. No mail deletion adapter is called. */
function ownerAction(array &$fixture, array $plan, int $now): array
{
    $manifest = $fixture['workflow']->ownerMailAction($plan, 'synthetic-owner', $now);
    if ($manifest === null) throw new \RuntimeException('Missing synthetic owner mail manifest');
    $binding = $manifest['binding'];
    unset($fixture['adapters']['email']->rows[$binding['key']]);
    $receipt = ['schema_version' => 1, 'actor' => 'synthetic-owner', 'plan_digest' => $plan['digest'],
        'mailbox' => $binding['mailbox'], 'message_id' => $binding['message_id'], 'binding_hash' => Workflow::digest($binding),
        'observed_at' => $now, 'evidence_reference' => 'synthetic-owner-mail-action', 'evidence_hash' => str_repeat('9', 64)];
    $fixture['authority']->receipts[$plan['digest']][$binding['message_id']] = $receipt;
    if ($fixture['authority']->afterManualMail) ($fixture['authority']->afterManualMail)();
    return $manifest;
}

function executeWithOwnerMail(array &$fixture, array $plan, int $now): array
{
    $result = $fixture['workflow']->execute($plan, 'synthetic-owner', $now);
    // Fixture has one matching mail copy; this intentionally exercises only that owner action.
    if ($result['status'] === 'AWAITING_OWNER_MAIL_ACTION') {
        ownerAction($fixture, $plan, $now);
        return $fixture['workflow']->execute($plan, 'synthetic-owner', $now);
    }
    return $result;
}
