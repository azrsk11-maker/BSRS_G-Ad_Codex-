<?php
declare(strict_types=1);
define('BSRE_OWNER_MAIL_REVIEW_LAB', true);
define('BSRE_CLOSED_RETENTION_LAB', true);
function wp_get_environment_type(): string { return 'local'; }
function home_url(): string { return 'http://bsre.invalid'; }
require __DIR__ . '/TestDoubles.php';
require __DIR__ . '/Cleanup.php';
use BSRE\OwnerMailReview as O;
use BSRE\ClosedRetention as C;
$checks = [];
function check(string $name, bool $condition): void
{
    global $checks;
    if (!$condition) throw new RuntimeException('Owner mail review check failed: ' . $name);
    $checks[$name] = true;
}
function rejects(callable $operation, string $code): bool
{
    try { $operation(); return false; }
    catch (O\ReviewFailure $error) { return $error->getMessage() === $code; }
}
function waiting(): array
{
    $f = O\fixture(); $review = O\prepare($f); $view = O\approve($f, $review);
    return [$f, $view];
}

$f = O\fixture(); $review = O\prepare($f);
check('prepare_has_no_provider_action', array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 0 && $f['journal']->journals === []);
check('review_is_explicit_and_private', $review['status'] === 'REVIEW_EXACT_PLAN' && $review['job']['approved_at'] === null);
$html = $f['controller']->render($review);
check('accessible_review_contains_exact_plan', str_contains($html, 'aria-label="Exact private retention plan"') && str_contains($html, $review['job']['plan']['digest']) && str_contains($html, '<button type="submit">'));
$input = O\form($f['controller'], $review, 'approve'); $input['plan_digest'] = str_repeat('f', 64);
check('changed_digest_rejected_by_nonce', rejects(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$input = O\form($f['controller'], $review, 'approve'); $input['plan'] = $review['job']['plan'];
check('client_plan_upload_rejected', rejects(fn() => $f['controller']->handle('POST', $input, $f['now']), 'INPUT_SCHEMA_INVALID'));
$input = O\form($f['controller'], $review, 'approve'); $input['nonce'] = 'invalid';
check('csrf_cannot_record_approval', rejects(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED') && $f['store']->jobs[$review['job']['id']]['approved_at'] === null);
$f['session']->allowed = false; $reads = $f['store']->reads;
check('unauthenticated_read_precedes_storage', rejects(fn() => $f['controller']->handle('GET', ['job' => $review['job']['id']], $f['now']), 'OWNER_SESSION_REQUIRED') && $reads === $f['store']->reads);
$f['session']->allowed = true; $f['session']->identity = 'another-admin';
check('different_owner_cannot_read_plan', rejects(fn() => $f['controller']->handle('GET', ['job' => $review['job']['id']], $f['now']), 'REVIEW_NOT_FOUND'));
$f['session']->identity = 'synthetic-owner';
$view = O\approve($f, $review); $manifest = $view['job']['manifest'];
check('approval_records_intent_without_deleting', $view['status'] === 'AWAITING_OWNER_MAIL_ACTION' && $f['journal']->historyIncomplete()
    && $f['journal']->journal($review['job']['plan']['digest'])['steps'][0] === 'INTENT_RECORDED'
    && array_sum(array_map(fn($a) => $a->deletes, $f['adapters'])) === 0);
check('manifest_binds_fingerprint_and_message', $manifest['binding']['mailbox'] === 'marketing@blackswanrealestate.ae'
    && $manifest['plan_digest'] === $review['job']['plan']['digest'] && $manifest['binding']['fingerprint'] === str_repeat('2', 64));
check('approval_replay_is_safe', O\approve($f, $review)['status'] === 'AWAITING_OWNER_MAIL_ACTION' && $f['adapters']['email']->deletes === 0);
$handoff = O\handoff($f, $view);
check('owner_declaration_does_not_prove_absence', rejects(fn() => $f['controller']->handle('POST', $handoff, $f['now']), 'MAIL_ABSENCE_UNVERIFIED')
    && $f['store']->jobs[$view['job']['id']]['verified_receipts'] === [] && $f['adapters']['outcome']->deletes === 0);
$stored = $f['store']->jobs[$view['job']['id']];
check('declaration_committed_even_when_readback_held', count($stored['declarations']) === 1 && $stored['status'] === 'AWAITING_INDEPENDENT_READBACK');
$input = $handoff; $input['binding_hash'] = str_repeat('f', 64);
check('message_form_is_bound_by_nonce', rejects(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));
$input = $handoff; $input['authoritative'] = true;
check('caller_absence_boolean_rejected', rejects(fn() => $f['controller']->handle('POST', $input, $f['now']), 'INPUT_SCHEMA_INVALID'));
$f['readback']->throw = true;
check('provider_error_never_becomes_absence', rejects(fn() => $f['controller']->handle('POST', $handoff, $f['now']), 'MAIL_READBACK_UNCERTAIN') && $f['adapters']['outcome']->deletes === 0);
$f['readback']->throw = false;
$mail = $f['adapters']['email']->rows['synthetic-message-1']; unset($f['adapters']['email']->rows['synthetic-message-1']);
$f['readback']->trash['synthetic-message-1'] = $mail;
check('trash_copy_holds_handoff', rejects(fn() => $f['controller']->handle('POST', $handoff, $f['now']), 'MAIL_ABSENCE_UNVERIFIED'));
unset($f['readback']->trash['synthetic-message-1']);
foreach (['complete_surface' => false, 'includes_trash' => false, 'authoritative' => false,
    'message_id' => 'different-copy', 'mailbox' => 'other@example.invalid', 'binding_hash' => str_repeat('f', 64),
    'observed_at' => $f['now'] - 1] as $field => $bad) {
    $f['readback']->overrides = [$field => $bad];
    check('readback_rejects_' . $field, rejects(fn() => $f['controller']->handle('POST', $handoff, $f['now']), 'MAIL_ABSENCE_UNVERIFIED'));
}
$f['readback']->overrides = [];
$completed = $f['controller']->handle('POST', $handoff, $f['now']);
check('independent_absence_advances_existing_workflow', $completed['status'] === 'COMPLETE'
    && $f['adapters']['outcome']->deletes === 2 && $f['adapters']['capture']->deletes === 1 && $f['adapters']['intake']->deletes === 1 && $f['adapters']['email']->deletes === 0);
$receipt = $completed['job']['verified_receipts']['synthetic-message-1']['receipt'];
check('server_receipt_binds_declaration_and_proof', $receipt['actor'] === 'synthetic-owner' && $receipt['binding_hash'] === C\Workflow::digest($manifest['binding'])
    && $receipt['evidence_hash'] !== $handoff['evidence_hash']);
$readCount = $f['readback']->reads;
check('receipt_response_replay_has_no_repeated_delete', $f['controller']->handle('POST', $handoff, $f['now'])['status'] === 'COMPLETE'
    && $f['adapters']['outcome']->deletes === 2 && $readCount === $f['readback']->reads);
$conflict = $handoff; $conflict['evidence_hash'] = str_repeat('8', 64);
check('verified_receipt_cannot_be_replaced', rejects(fn() => $f['controller']->handle('POST', $conflict, $f['now']), 'RECEIPT_CONFLICT'));
$f['adapters']['email']->rows['synthetic-message-1'] = $mail;
$restored = $f['controller']->handle('POST', O\form($f['controller'], $completed, 'resume'), $f['now']);
check('recreated_copy_still_holds_completed_plan', $restored['status'] === 'HELD' && in_array('RESOURCE_SCOPE_CHANGED', $restored['job']['hold_codes'], true));

[$f, $view] = waiting();
$f['readback']->overrides = ['status' => 'ABSENT'];
$result = $f['controller']->handle('POST', O\handoff($f, $view), $f['now']);
check('workflow_independent_provider_read_remains_authority', $result['status'] === 'AWAITING_OWNER_MAIL_ACTION' && $f['adapters']['outcome']->deletes === 0);

[$f, $view] = waiting(); $input = O\handoff($f, $view);
unset($f['adapters']['email']->rows['synthetic-message-1']);
$f['admission']->refresh($f['now'] + 301); $f['readback']->overrides = ['observed_at' => $f['now']];
check('otherwise_valid_old_absence_readback_is_stale', rejects(fn() => $f['controller']->handle('POST', $input, $f['now'] + 301), 'MAIL_ABSENCE_UNVERIFIED'));
$f['readback']->overrides = ['observed_at' => $f['now'] + 302];
check('future_absence_readback_rejected', rejects(fn() => $f['controller']->handle('POST', $input, $f['now'] + 301), 'MAIL_ABSENCE_UNVERIFIED'));

$f = O\fixture(); $mail = $f['adapters']['email']->rows['synthetic-message-1'];
$mail['key'] = $mail['message_id'] = 'synthetic-message-2'; $mail['rfc822_message_id'] = '<synthetic-message-2@example.invalid>';
$f['adapters']['email']->rows[$mail['key']] = $mail;
$f['journal']->closures[$f['closure']['closure_id']]['mail_message_ids'][] = $mail['key'];
$view = O\approve($f, O\prepare($f)); $first = O\handoff($f, $view);
unset($f['adapters']['email']->rows['synthetic-message-1']);
$next = $f['controller']->handle('POST', $first, $f['now']);
check('each_exact_copy_gets_separate_owner_manifest', $next['status'] === 'AWAITING_OWNER_MAIL_ACTION' && $next['job']['manifest']['binding']['message_id'] === 'synthetic-message-2' && $f['adapters']['outcome']->deletes === 0);
check('prior_copy_receipt_cannot_advance_next_copy', rejects(fn() => $f['controller']->handle('POST', $first, $f['now']), 'EXACT_MESSAGE_CONFLICT'));
unset($f['adapters']['email']->rows['synthetic-message-2']);
check('all_exact_copies_require_independent_handoffs', $f['controller']->handle('POST', O\handoff($f, $next), $f['now'])['status'] === 'COMPLETE' && $f['adapters']['email']->deletes === 0);

[$f, $view] = waiting(); $input = O\handoff($f, $view);
unset($f['adapters']['email']->rows['synthetic-message-1']);
$f['journal']->closures[$f['closure']['closure_id']]['revision']++;
try { $f['controller']->handle('POST', $input, $f['now']); check('changed_closure_rejected_before_readback', false); }
catch (C\Failure $error) { check('changed_closure_rejected_before_readback', $error->getMessage() === 'CLOSURE_CHANGED_OR_REOPENED' && $f['readback']->reads === 0); }

[$f, $view] = waiting(); $input = O\handoff($f, $view);
unset($f['adapters']['email']->rows['synthetic-message-1']);
$f['store']->afterSave = function ($job) { if ($job['verified_receipts'] !== []) throw new RuntimeException('synthetic lost receipt response'); };
try { $f['controller']->handle('POST', $input, $f['now']); } catch (RuntimeException $error) {}
check('receipt_durable_before_workflow_resume', count($f['store']->jobs[$view['job']['id']]['verified_receipts']) === 1 && $f['adapters']['outcome']->deletes === 0);
$f['store']->afterSave = null;
check('lost_receipt_response_resumes_without_deleting_mail', $f['controller']->handle('POST', $input, $f['now'])['status'] === 'COMPLETE' && $f['adapters']['email']->deletes === 0);

$f = O\fixture(); $view = O\prepare($f); $input = O\form($f['controller'], $view, 'approve');
$f['store']->afterSave = function ($job) { if ($job['approved_at'] !== null) throw new RuntimeException('synthetic lost approval response'); };
try { $f['controller']->handle('POST', $input, $f['now']); } catch (RuntimeException $error) {}
check('approval_durable_before_workflow_intent', $f['store']->jobs[$view['job']['id']]['approved_at'] === $f['now'] && $f['journal']->journals === []);
$f['store']->afterSave = null;
check('lost_approval_response_can_resume', $f['controller']->handle('POST', $input, $f['now'])['status'] === 'AWAITING_OWNER_MAIL_ACTION');
$input['nonce'] = $f['session']->nonce('unrelated-form');
check('unrelated_form_nonce_rejected', rejects(fn() => $f['controller']->handle('POST', $input, $f['now']), 'CSRF_REJECTED'));

[$f, $view] = waiting(); $input = O\handoff($f, $view); $digest = $view['job']['plan']['digest'];
$later = $f['now'] + 30 * 86400;
check('post_after_cache_expiry_has_no_action', rejects(fn() => $f['controller']->handle('POST', $input, $later), 'REVIEW_NOT_FOUND')
    && $f['store']->jobs === [] && $f['adapters']['outcome']->deletes === 0 && $f['journal']->journal($digest) !== null);
$cleanup = new O\CleanupController($f['workflow'], $f['authority'], $f['journal'], $f['session']);
$reviewCleanup = ['operation' => 'review_cleanup', 'nonce' => $f['session']->nonce('bsre-owner-mail-cleanup/review_cleanup/'), 'plan_digest' => $digest];
$cleanupView = $cleanup->handle('POST', $reviewCleanup, $later);
check('expired_cache_does_not_block_authoritative_cleanup_review', $cleanupView['plan']['digest'] === $digest);
$expire = ['operation' => 'expire', 'nonce' => $f['session']->nonce('bsre-owner-mail-cleanup/expire/' . $digest), 'plan_digest' => $digest];
$early = $cleanup->handle('POST', $expire, $f['now'] + 1);
check('separate_cleanup_authorization_cannot_skip_window', $early['hold_codes'] === ['RECOVERY_WINDOW_ACTIVE']);
$cleaned = $cleanup->handle('POST', $expire, $later);
check('unresolved_cleanup_preserves_manual_reconciliation', $cleaned['status'] === 'PRIVATE_JOURNAL_EXPIRED'
    && $cleaned['hold_codes'] === ['MANUAL_RECONCILIATION_REQUIRED'] && $f['journal']->journal($digest) === null
    && $f['journal']->closure($f['closure']['closure_id']) !== null && $f['journal']->historyIncomplete());
check('cleanup_authority_cleared_after_request', !$f['authority']->canApply('synthetic-owner', $digest, $later, 'EXPIRE_PRIVATE_JOURNAL'));
check('cleanup_retry_does_not_claim_provider_completion', $cleanup->handle('POST', $expire, $later)['status'] === 'NO_PRIVATE_JOURNAL' && $f['adapters']['outcome']->deletes === 0);

[$f, $view] = waiting(); $input = O\handoff($f, $view); $mail = $f['adapters']['email']->rows['synthetic-message-1'];
unset($f['adapters']['email']->rows['synthetic-message-1']);
$default = new O\Controller($f['workflow'], $f['authority'], $f['store'], $f['session']);
check('default_readback_holds_absent_message', rejects(fn() => $default->handle('POST', $input, $f['now']), 'MAIL_ABSENCE_UNVERIFIED'));
$view['job']['manifest']['binding']['rfc822_message_id'] = '<script>alert(1)</script>';
check('private_message_identifiers_are_html_escaped', !str_contains($f['controller']->render($view), '<script>') && str_contains($f['controller']->render($view), '&lt;script&gt;'));

echo json_encode(['scope' => 'SYNTHETIC_OWNER_MAIL_REVIEW', 'checks' => count($checks), 'passed' => array_keys($checks), 'production_authorized' => false], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
