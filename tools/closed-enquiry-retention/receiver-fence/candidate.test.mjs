import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {buildNoMailCopyReceiver} from './build-candidate.mjs';
import {receiverLab, digest} from './lab.mjs';

function retired() {
  const r = receiverLab(); const {payload, accepted} = r.admit(); const scope = r.scope();
  const proof = r.context.closedNoCopyRetire(scope);
  return {r, payload, accepted, scope, proof, key: 'bsre.closed-no-copy.' + scope.request_id};
}
function status(r, id) {
  const timestamp = String(r.state.clock * 1000), purpose = 'bsre-receipt-status-v1';
  const signature = createHmac('sha256', r.stored.HMAC_SECRET).update(`${purpose}\n${timestamp}\n${id}`).digest('hex');
  return r.postWire(JSON.stringify({version: 1, purpose, timestamp, request_id: id, signature}));
}

test('exact immutable input pin and unique source hooks remain mandatory', () => {
  const original = readFileSync(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs', import.meta.url));
  assert.throws(() => buildNoMailCopyReceiver(Buffer.concat([original, Buffer.from(' ')])), /SOURCE_CHANGED/);
  const r = receiverLab();
  assert.match(r.built.toString(), /if \(!closedNoCopyMaySend_\(r\)\) continue/);
  r.context.BSRE_SYNTHETIC_NO_COPY_LAB = false;
  assert.equal(r.post(r.payload()).accepted, false);
  assert.equal(r.rows.length, 1);
});

test('actual sender, retry, status and reconciliation consult the same ScriptLock fence', () => {
  const {r, payload, accepted, scope, proof} = retired();
  assert.equal(r.rows[1].length, 26);
  assert.equal(r.rows[1][6], 'RETIRED_NO_COPY');
  assert.equal(proof.scope_hash, digest(scope));
  assert.equal(proof.row_state, 'RETIRED');
  assert.equal(r.context.processLeadOutbox().sent, 0);
  assert.equal(r.post(payload).accepted, false);
  assert.equal(r.post(payload).code, 'NO_COPY_REQUEST_RETIRED');
  assert.equal(r.post(payload).retryable, false);
  assert.equal(status(r, payload.request_id).status, 'UNCONFIRMED');
  r.rows[1][6] = 'AMBIGUOUS'; // Restored/edited outbox status cannot bypass the independent fence.
  assert.throws(() => r.context.reconcileLeadEmail(accepted.lead_id, 'confirmed_not_sent'), /RETIRED/);
  assert.equal(r.rows[1][6], 'AMBIGUOUS');
  assert.equal(r.context.processLeadOutbox().sent, 0);
  assert.equal(r.mail.length, 0);
  assert.ok(r.state.operations.includes('fence-write'));
  assert.ok(r.state.operations.includes('mailbox-readback'));
});

test('healthy older queued mail continues past a retired row without a global time cutoff', () => {
  const {r} = retired();
  r.admit(); r.rows[2][3] = '2020-01-01T00:00:00.000Z';
  assert.equal(r.context.processLeadOutbox().sent, 1);
  assert.equal(r.rows[1][6], 'RETIRED_NO_COPY');
  assert.equal(r.rows[2][6], 'SENT');
  assert.equal(r.mail.length, 1);
});

test('unrelated retirement advances the store epoch without invalidating an earlier exact fence', () => {
  const {r, scope, proof} = retired(); r.admit();
  const second = {...scope, closure_id: r.payload().request_id, request_id: r.rows[2][0],
    lead_id: r.rows[2][1], event_id: r.rows[2][2], fingerprint: r.rows[2][4]};
  r.context.closedNoCopyRetire(second);
  const refreshed = r.context.closedNoCopyReadback(scope);
  assert.equal(refreshed.fence_hash, proof.fence_hash);
  assert.equal(refreshed.epoch, proof.epoch);
  assert.ok(refreshed.current_store.revision > proof.current_store.revision);
  r.admit(); assert.equal(r.context.processLeadOutbox().sent, 1);
});

test('fresh complete affirmative mailbox absence is required independently of zero attempts', () => {
  for (const mutate of [r => delete r.context.BSREClosedNoCopyMailbox,
    r => {r.state.mailbox = 'UNKNOWN';}, r => {r.state.mailbox = 'PRESENT';},
    r => {r.state.complete = false;}, r => {r.state.trash = false;}, r => {r.state.staleMailbox = true;}]) {
    const r = receiverLab(); r.admit(); mutate(r);
    assert.throws(() => r.context.closedNoCopyRetire(r.scope()), /NO_COPY/);
    assert.equal(r.rows[1][6], 'QUEUED');
    assert.equal(Object.keys(r.stored).some(key => key.startsWith('bsre.closed-no-copy.000')), false);
    assert.equal(r.mail.length, 0);
  }
});

test('SENDING, AMBIGUOUS, prior attempts and prior send timestamps never infer no copy', () => {
  for (const mutate of [r => {r.rows[1][6] = 'SENDING';}, r => {r.rows[1][6] = 'AMBIGUOUS';},
    r => {r.rows[1][7] = 1;}, r => {r.rows[1][10] = '2026-01-01T00:00:00Z';},
    r => {r.rows[1][25] = '2026-01-01T00:00:00Z';}]) {
    const r = receiverLab(); r.admit(); mutate(r);
    assert.throws(() => r.context.closedNoCopyRetire(r.scope()), /OUTBOX_AMBIGUOUS/);
    assert.equal(r.mail.length, 0);
  }
});

test('actual confirmed-not-sent reconciliation retains attempted history and cannot mint NEVER_SENT', () => {
  const r = receiverLab(); const {accepted} = r.admit();
  r.rows[1][6] = 'AMBIGUOUS'; r.rows[1][7] = 1; r.rows[1][25] = new Date().toISOString();
  r.context.reconcileLeadEmail(accepted.lead_id, 'confirmed_not_sent');
  assert.equal(r.rows[1][6], 'QUEUED');
  assert.equal(r.rows[1][25], '');
  assert.equal(r.rows[1][7], 1);
  assert.throws(() => r.context.closedNoCopyRetire(r.scope()), /OUTBOX_AMBIGUOUS/);
  assert.equal(r.mail.length, 0);
});

test('closure revision, original identities and normalized body fingerprint bind retirement', () => {
  const {r, scope} = retired();
  for (const changed of [{...scope, closure_revision: 2}, {...scope, closure_hash: '7'.repeat(64)},
    {...scope, fingerprint: '8'.repeat(64)}, {...scope, event_id: 'evt_' + r.payload().request_id}]) {
    assert.throws(() => r.context.closedNoCopyRetire(changed), /NO_COPY/);
    assert.throws(() => r.context.closedNoCopyReadback(changed), /NO_COPY/);
  }
  r.rows[1][5] += ' ';
  assert.throws(() => r.context.closedNoCopyReadback(scope), /ROW_CONFLICT/);
});

test('mixed normalized payload cannot borrow another request column and receipt identity', () => {
  const r = receiverLab(); r.admit(); r.admit();
  r.rows[1][4] = r.rows[2][4]; r.rows[1][5] = r.rows[2][5];
  assert.throws(() => r.context.closedNoCopyRetire(r.scope()), /ROW_CONFLICT/);
  assert.equal(r.rows[1][6], 'QUEUED');
  assert.equal(r.mail.length, 0);
});

test('fence storage acknowledgement precedes status mutation; lock contention cannot race a sender', () => {
  const r = receiverLab(); r.admit(); r.state.storageFault = true;
  assert.throws(() => r.context.closedNoCopyRetire(r.scope()), /storage unavailable/);
  assert.equal(r.rows[1][6], 'QUEUED');
  assert.throws(() => r.context.processLeadOutbox(), /STORE_EPOCH_CONFLICT/);
  assert.throws(() => r.reapply(), /RESTORE_RECONCILIATION_REQUIRED/);
  const next = receiverLab(); next.admit();
  let senderBlocked = false;
  next.state.onFenceWrite = () => { senderBlocked = next.context.processLeadOutbox().busy === true; };
  next.context.closedNoCopyRetire(next.scope());
  assert.equal(senderBlocked, true);
  assert.equal(next.context.processLeadOutbox().sent, 0);
  assert.equal(next.mail.length, 0);
});

test('missing/corrupt fence never supplies readback or requeue authority and other mail remains deliverable', () => {
  for (const corrupt of [null, '{bad', '{}']) {
    const {r, scope, key, payload, accepted} = retired();
    if (corrupt === null) delete r.stored[key]; else r.stored[key] = corrupt;
    assert.throws(() => r.context.closedNoCopyReadback(scope), /NO_COPY/);
    assert.equal(r.post(payload).accepted, false);
    assert.throws(() => r.context.reconcileLeadEmail(accepted.lead_id, 'confirmed_not_sent'), /NO_COPY/);
    r.admit();
    assert.equal(r.context.processLeadOutbox().sent, 1);
    assert.equal(r.mail.length, 1);
  }
});

test('fresh namespace floor is mandatory inside every actual writer and known receipt path', () => {
  for (const mutate of [r => delete r.stored['bsre.closed-no-copy.floor'],
    r => {r.stored['bsre.closed-no-copy.floor'] = '{}';},
    r => {r.state.runtimeStale = true;}, r => {r.state.restoreFenced = false;},
    r => delete r.context.BSREClosedNoCopyRuntime]) {
    const r = receiverLab(); const {payload, accepted} = r.admit(); mutate(r);
    assert.throws(() => r.context.processLeadOutbox(), /NO_COPY/);
    assert.equal(r.post(payload).accepted, false);
    assert.equal(status(r, payload.request_id).status, 'UNCONFIRMED');
    r.rows[1][6] = 'AMBIGUOUS';
    assert.throws(() => r.context.reconcileLeadEmail(accepted.lead_id, 'confirmed_not_sent'), /NO_COPY/);
    assert.equal(r.rows[1][6], 'AMBIGUOUS'); assert.equal(r.mail.length, 0);
  }
});

test('actual restorable epoch, namespace and admission metadata must match the independent floor on every path', () => {
  for (const field of ['epoch', 'namespace', 'generation', 'activated_at', 'audience']) {
    const r = receiverLab(); const {payload, accepted} = r.admit();
    const index = r.metadata[0].indexOf(field); r.metadata[1][index] = field === 'activated_at' ? 1 : 'stale';
    assert.throws(() => r.context.processLeadOutbox(), /STORE_EPOCH_CONFLICT/);
    assert.equal(r.post(payload).accepted, false);
    assert.equal(status(r, payload.request_id).status, 'UNCONFIRMED');
    r.rows[1][6] = 'AMBIGUOUS';
    assert.throws(() => r.context.reconcileLeadEmail(accepted.lead_id, 'confirmed_not_sent'), /STORE_EPOCH_CONFLICT/);
    assert.equal(r.mail.length, 0);
  }
});

test('pinned fence survives a fresh receiver VM and blocks a restored queued row', () => {
  const {r, scope} = retired();
  const next = receiverLab({properties: {...r.stored}, metadata: r.metadata.map(row => [...row]), now: r.state.clock});
  next.rows.push([...r.rows[1]]); next.rows[1][6] = 'QUEUED';
  assert.equal(next.context.processLeadOutbox().sent, 0);
  assert.throws(() => next.context.closedNoCopyReadback(scope), /ROW_CONFLICT/);
});

test('purged unknown request stays fenced and old admission cannot recreate it after private expiry', () => {
  const {r, scope, payload, key} = retired(), oldProof = r.claim(scope.request_id);
  const restored = [...r.rows[1]];
  r.rows.splice(1, 1);
  assert.equal(r.context.closedNoCopyReadback(scope).row_state, 'ABSENT');
  assert.equal(r.post(payload).accepted, false);
  assert.throws(() => r.context.closedNoCopyPrepareCleanup(scope), /RECOVERY_UNVERIFIED/);
  r.state.clock += 2592000;
  assert.throws(() => r.context.closedNoCopyPrepareCleanup(scope), /RECOVERY_UNVERIFIED/);
  assert.ok(Object.hasOwn(r.stored, key));
  r.state.backupsExpiredThrough = r.state.clock;
  const ticket = r.context.closedNoCopyPrepareCleanup(scope);
  assert.equal(r.context.closedNoCopyForget(scope, ticket), true);
  assert.equal(Object.hasOwn(r.stored, key), false);
  assert.equal(r.post(payload, {admission: oldProof}).code, 'ADMISSION_REQUIRED');
  // A restore namespace is untrusted until current retention has been reapplied by the external authority.
  r.rows.push(restored); r.rows[1][6] = 'QUEUED'; r.state.restoreFenced = false;
  assert.throws(() => r.context.processLeadOutbox(), /RECOVERY_UNVERIFIED/);
  assert.equal(status(r, payload.request_id).status, 'UNCONFIRMED');
  assert.equal(r.mail.length, 0);
});

test('actual pre-fence queued snapshot stays held after identifier prune and attempted reapplication', () => {
  const r = receiverLab(); const {payload, accepted} = r.admit();
  const snapshot = {row: [...r.rows[1]], metadata: r.metadata.map(row => [...row])};
  const scope = r.scope(); r.context.closedNoCopyRetire(scope); r.rows.splice(1, 1);
  r.state.clock += 2592000; r.state.backupsExpiredThrough = r.state.clock;
  const ticket = r.context.closedNoCopyPrepareCleanup(scope);
  r.context.closedNoCopyForget(scope, ticket);
  r.rows.push(snapshot.row); r.metadata.splice(0, r.metadata.length, ...snapshot.metadata);
  assert.equal(r.state.restoreFenced, true); // A boolean cannot override the actual stale store epoch.
  assert.throws(() => r.context.processLeadOutbox(), /STORE_EPOCH_CONFLICT/);
  assert.equal(r.post(payload).accepted, false);
  assert.equal(status(r, payload.request_id).status, 'UNCONFIRMED');
  assert.throws(() => r.context.reconcileLeadEmail(accepted.lead_id, 'confirmed_not_sent'), /STORE_EPOCH_CONFLICT/);
  assert.throws(() => r.reapply(), /RESTORE_RECONCILIATION_REQUIRED/);
  assert.equal(r.context.closedNoCopyNow_(), r.state.clock);
  assert.equal(r.rows[1][6], 'QUEUED'); assert.equal(r.mail.length, 0);
});

test('signed cleanup intent supports lost-ack retry without treating missing fence alone as proof', () => {
  const {r, scope} = retired(); r.rows.splice(1, 1); r.state.clock += 2592000;
  r.state.backupsExpiredThrough = r.state.clock;
  const ticket = r.context.closedNoCopyPrepareCleanup(scope);
  assert.equal(r.context.closedNoCopyForget(scope, ticket), true);
  assert.throws(() => r.context.closedNoCopyReadback(scope, true), /FENCE_MISSING/);
  assert.equal(r.context.closedNoCopyReadback(scope, true, ticket).row_state, 'ABSENT');
  assert.equal(r.context.closedNoCopyForget(scope, ticket), true);
  const changed = structuredClone(ticket); changed.body.issued_at--;
  assert.throws(() => r.context.closedNoCopyForget(scope, changed), /TICKET_INVALID/);
});
