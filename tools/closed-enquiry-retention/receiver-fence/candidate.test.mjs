import assert from 'node:assert/strict';
import {createHmac, randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {buildNoMailCopyReceiver} from './build-candidate.mjs';
import {receiverLab, digest} from './lab.mjs';

async function coldBridge(operation) {
  const child = spawn(process.execPath, [fileURLToPath(new URL('./bridge.mjs', import.meta.url))], {stdio: ['pipe','pipe','inherit']});
  const lines = createInterface({input: child.stdout})[Symbol.asyncIterator]();
  const exit = new Promise((resolve, reject) => {child.once('exit', resolve); child.once('error', reject);});
  const call = async (action, values = {}) => {
    child.stdin.write(JSON.stringify({action, ...values}) + '\n');
    let timer;
    const line = await Promise.race([lines.next(), new Promise((_, reject) => {timer = setTimeout(() => reject(Error('Bridge timeout')), 5000);})])
      .finally(() => clearTimeout(timer));
    assert.equal(line.done, false); return JSON.parse(line.value);
  };
  try { await operation(call); }
  finally { child.stdin.end(); const code = await exit; assert.equal(code, 0); }
}
function externalEnvelope(now, descriptor) {
  const key = 'synthetic-key-'.repeat(4), payload = receiverLab({now}).payload();
  payload.started_at = now * 1000 - 5000;
  const body = JSON.stringify(payload), timestamp = String(now * 1000);
  const proof = {version: 1, request_id: payload.request_id, issued_at: now, expires_at: now + 900,
    session_hash: 'c'.repeat(64), generation: descriptor.generation, audience: descriptor.audience};
  proof.signature = createHmac('sha256', key).update(['bsre-retention-admission-v1', proof.request_id, proof.issued_at,
    proof.expires_at, proof.session_hash, proof.generation, proof.audience].join('\n')).digest('hex');
  return {payload, raw: JSON.stringify({version: 1, body, timestamp, admission: proof,
    signature: createHmac('sha256', key).update(`v1\n${timestamp}\n${body}`).digest('hex')})};
}

test('cold bridge accepts external exact signed wire only after one matching configuration', async () => {
  await coldBridge(async call => {
    const now = Math.floor(Date.now() / 1000), descriptor = {contract:'bsre-retention-admission-v1',mode:'ENFORCED',
      generation:'a'.repeat(64),audience:'7'.repeat(64),activated_at:now-2000,max_age_seconds:900};
    const wire = externalEnvelope(now, descriptor);
    assert.equal((await call('cold_init', {now, admission_hash:'d'.repeat(64), descriptor})).value.rows, 0);
    assert.equal((await call('post_wire', {raw:wire.raw})).error, 'SYNTHETIC_POST_WIRE_INVALID');
    assert.equal((await call('configure', {descriptor:{...descriptor,audience:'b'.repeat(64)},synthetic_hmac:'synthetic-key-'.repeat(4)})).error,
      'SYNTHETIC_CONFIGURE_INVALID');
    assert.deepEqual((await call('configure', {descriptor,synthetic_hmac:'synthetic-key-'.repeat(4)})).value, descriptor);
    assert.equal((await call('post_wire', {raw:wire.raw})).value.accepted, true);
    assert.equal((await call('admitted_identity', {request_id:wire.payload.request_id})).value.columns, 26);
    assert.equal((await call('configure', {descriptor,synthetic_hmac:'synthetic-key-'.repeat(4)})).error, 'SYNTHETIC_CONFIGURE_INVALID');
    assert.equal((await call('init', {now})).error, 'SYNTHETIC_BRIDGE_ALREADY_INITIALIZED');
    assert.equal((await call('stats')).value.rows, 1);
  });
});

test('cold bridge aging is exact fixture setup and cannot mutate a fenced acceptance', async () => {
  await coldBridge(async call => {
    const now = Math.floor(Date.now() / 1000), descriptor = {contract:'bsre-retention-admission-v1',mode:'ENFORCED',
      generation:'a'.repeat(64),audience:'7'.repeat(64),activated_at:now-2000,max_age_seconds:900};
    await call('cold_init', {now, admission_hash:'d'.repeat(64), descriptor});
    await call('configure', {descriptor,synthetic_hmac:'synthetic-key-'.repeat(4)});
    const wire = externalEnvelope(now, descriptor), broken = JSON.parse(wire.raw); broken.signature = '0'.repeat(64);
    assert.equal((await call('post_wire', {raw:JSON.stringify(broken)})).value.accepted, false);
    assert.equal((await call('stats')).value.rows, 0);
    await call('post_wire', {raw:wire.raw});
    const row = (await call('admitted_identity', {request_id:wire.payload.request_id})).value;
    const aging = {...row, previous_accepted_at_utc:row.accepted_at_utc, accepted_at_utc:'2025-01-01T12:00:00.000Z'};
    assert.equal((await call('fixture_age_acceptance', {...aging,lead_id:'BSRE-'+randomUUID()})).error, 'SYNTHETIC_AGING_INVALID');
    assert.equal((await call('fixture_age_acceptance', aging)).value, true);
    const after = (await call('admitted_identity', {request_id:row.request_id})).value;
    assert.equal(after.accepted_at_utc, aging.accepted_at_utc); assert.equal(after.fingerprint, row.fingerprint);
    const scope = {contract:'bsre-closed-no-mail-copy-v1',closure_id:row.request_id,closure_revision:2,closure_hash:'1'.repeat(64),
      request_id:row.request_id,lead_id:row.lead_id,event_id:row.event_id,fingerprint:row.fingerprint,admission_hash:'d'.repeat(64)};
    assert.equal((await call('retire', {scope,now})).ok, true);
    assert.equal((await call('fixture_age_acceptance', {...aging,previous_accepted_at_utc:after.accepted_at_utc,
      accepted_at_utc:'2024-01-01T12:00:00.000Z'})).error, 'SYNTHETIC_AGING_INVALID');
    assert.equal((await call('post_wire', {raw:wire.raw})).value.code, 'NO_COPY_REQUEST_RETIRED');
    assert.equal((await call('stats')).value.mail, 0);
  });
});

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
function intakePurgeFixture() {
  const value = retired(), {r, scope} = value;
  const binding = r.context.closedIntakeInventory(scope)[0];
  const claim = {contract: 'bsre-intake26-purge-intent-v1', scope_hash: digest(scope), binding_hash: digest(binding),
    plan_digest: '2'.repeat(64), journal_revision: 3, uncertainty_count: 0, source_hash: r.sourceHash,
    accepted_at_utc: r.rows[1][3].replace(/\.\d{3}Z$/, 'Z'),
    observed_at: r.state.clock, expires_at: r.state.clock + 300};
  claim.intent_digest = digest(claim); r.state.purgeIntents[claim.intent_digest] = claim;
  return {...value, binding, claim, remove: () => r.context.closedIntakeRemoveExact(scope, binding, claim.intent_digest)};
}

test('Intake26 exact SDK deletion freshly resolves identities, preserves healthy rows and keeps retired outbox quiescent', () => {
  const f = intakePurgeFixture(), {r, scope, binding} = f;
  r.admit(); const healthy = JSON.stringify(r.rows[2]);
  r.state.onPurgeRead = () => { [r.rows[1], r.rows[2]] = [r.rows[2], r.rows[1]]; };
  assert.equal(f.remove(), true);
  assert.equal(r.context.closedIntakeInventory(scope).length, 0);
  assert.equal(r.state.intakeDeletes, 1); assert.equal(JSON.stringify(r.rows[1]), healthy);
  assert.equal(binding.key, scope.request_id); assert.equal(binding.request_ids.length, 1);
  assert.equal(r.context.processLeadOutbox().sent, 1); assert.equal(r.mail.length, 1);
  assert.equal(r.post(f.payload).code, 'NO_COPY_REQUEST_RETIRED');
  assert.equal(status(r, scope.request_id).status, 'UNCONFIRMED');
  assert.ok(r.state.operations.includes('intake-delete-row'));
  assert.ok(r.state.operations.includes('purge-intent-readback'));
});

test('Intake binding hashes all26 cells without confusing the normalized payload fingerprint', () => {
  const f = intakePurgeFixture(), {r, scope, binding} = f;
  r.rows[1][24] = 'Changed synthetic staff note';
  const changed = r.context.closedIntakeInventory(scope)[0];
  assert.equal(changed.fingerprint, binding.fingerprint); assert.notEqual(changed.evidence_hash, binding.evidence_hash);
  assert.throws(f.remove, /INTAKE_BINDING_CHANGED/); assert.equal(r.state.intakeDeletes, 0);
});

test('Intake SDK finds complete identity history beyond10000 rows without transferring all26-cell payloads', () => {
  const f = intakePurgeFixture(), {r, scope} = f, target = r.rows.pop();
  for (let i = 0; i < 10050; i++) {
    const row = Array(26).fill(''); row[0] = `unrelated-request-${i}`; row[1] = `unrelated-lead-${i}`; row[2] = `unrelated-event-${i}`;
    r.rows.push(row);
  }
  r.rows.push(target); const before = r.state.valueReadCells;
  assert.equal(r.context.closedIntakeInventory(scope)[0].key, scope.request_id);
  assert.ok(r.state.valueReadCells - before < 100);
  assert.ok(r.state.finders.slice(-3).every(config => config.row === 2 && config.width === 3 && config.height === 10051));
  assert.equal(f.remove(), true); assert.equal(r.context.closedIntakeInventory(scope).length, 0);
  const alias = Array(26).fill(''); alias[2] = scope.request_id.toUpperCase(); r.rows.push(alias);
  assert.throws(() => r.context.closedIntakeInventory(scope), /INTAKE_IDENTITY_SHARED/);
});

test('Intake SDK complete-search provider errors never establish absence', () => {
  const f = intakePurgeFixture(); f.r.state.finderFault = true;
  assert.throws(() => f.r.context.closedIntakeInventory(f.scope)); assert.throws(f.remove);
  assert.equal(f.r.state.intakeDeletes, 0); assert.equal(f.r.rows.length, 2);
});

test('Intake source acceptance cannot borrow an older due closure even with a freshly reviewed full binding', () => {
  const f = intakePurgeFixture(), {r, scope, claim} = f;
  const canonical = claim.accepted_at_utc;
  r.rows[1][3] = new Date(Date.parse(canonical) + 365 * 86400000).toISOString();
  const binding = r.context.closedIntakeInventory(scope)[0];
  const bad = {...claim, binding_hash: digest(binding)}; delete bad.intent_digest; bad.intent_digest = digest(bad);
  r.state.purgeIntents[bad.intent_digest] = bad;
  assert.throws(() => r.context.closedIntakeRemoveExact(scope, binding, bad.intent_digest), /INTAKE_ACCEPTANCE_CONFLICT/);
  assert.equal(r.state.intakeDeletes, 0);
});

test('Intake deletion rechecks fence recovery deadline after a slow external mailbox read', () => {
  const f = intakePurgeFixture(), {r, claim, scope, binding} = f;
  r.state.clock = f.proof.fence_expires_at - 1;
  const fresh = {...claim, observed_at: r.state.clock, expires_at: r.state.clock + 300};
  delete fresh.intent_digest; fresh.intent_digest = digest(fresh); r.state.purgeIntents[fresh.intent_digest] = fresh;
  r.state.onMailboxRead = () => {r.state.clock += 2;};
  assert.throws(() => r.context.closedIntakeRemoveExact(scope, binding, fresh.intent_digest), /NO_COPY_RECOVERY_UNVERIFIED/);
  assert.equal(r.state.intakeDeletes, 0);
});

test('Intake complete surface rejects duplicate identities, aliases, formulas, extra columns and changed headers', () => {
  for (const mutate of [r => r.rows.push([...r.rows[1]]),
    r => { const row = [...r.rows[1]]; row[0] = r.payload().request_id; r.rows.push(row); },
    r => { const row = Array(26).fill(''); row[2] = r.rows[1][0]; r.rows.push(row); },
    r => { const row = [...r.rows[1]]; row[1] = row[1].toUpperCase(); r.rows.push(row); },
    r => {r.state.formulas['2:25'] = '=SYNTHETIC';}, r => r.rows[1].push('unbound column'),
    r => {r.admit(); r.rows[2].push('foreign row unbound column');},
    r => {r.rows[0][24] = 'unknown_header';}]) {
    const f = intakePurgeFixture(); mutate(f.r);
    assert.throws(() => f.r.context.closedIntakeInventory(f.scope), /INTAKE_|SHEET_NOT_INITIALIZED|NO_COPY_ROW/);
    assert.throws(f.remove); assert.equal(f.r.state.intakeDeletes, 0);
  }
});

test('Intake exact row refuses unbound notes, validation, merged/protected cells and rich links', () => {
  for (const mutate of [r => {r.state.notes['2:25'] = 'synthetic private note';},
    r => {r.state.validations['2:20'] = {synthetic: true};}, r => {r.state.merged = true;},
    r => {r.state.protections = [{type: 'RANGE'}];}, r => {r.state.protections = [{type: 'SHEET'}];},
    r => {r.state.links['2:25'] = 'https://example.invalid/extra-metadata';}]) {
    const f = intakePurgeFixture(); mutate(f.r);
    assert.throws(f.remove, /INTAKE_METADATA_UNVERIFIED/); assert.equal(f.r.state.intakeDeletes, 0);
  }
});

test('Intake deletion requires exact fresh independently supplied Journal intent under actual ScriptLock', () => {
  for (const mutate of [(f) => {delete f.r.context.BSREClosedIntakePurgeIntent;},
    f => {f.claim.scope_hash = '0'.repeat(64);}, f => {f.claim.binding_hash = '0'.repeat(64);},
    f => {f.claim.source_hash = '0'.repeat(64);}, f => {f.claim.uncertainty_count = 1;},
    f => {f.claim.journal_revision = 0;}, f => {f.claim.expires_at = f.r.state.clock;},
    f => {f.claim.contract = 'wrong-purpose';}]) {
    const f = intakePurgeFixture(); mutate(f); assert.throws(f.remove, /INTAKE_|NO_COPY_/);
    assert.equal(f.r.state.intakeDeletes, 0); assert.equal(f.r.rows.length, 2);
  }
});

test('Intake sender fence, external floor, mailbox and lock uncertainty prevent exact deletion', () => {
  for (const mutate of [f => {delete f.r.stored[f.key];}, f => {f.r.state.runtimeStale = true;},
    f => {f.r.state.mailbox = 'UNKNOWN';}, f => {f.r.state.busy = true;},
    f => {f.r.metadata[1][0] = 'changed';}, f => {f.r.context.ScriptApp = {}; }]) {
    const f = intakePurgeFixture(); mutate(f); assert.throws(f.remove);
    assert.equal(f.r.state.intakeDeletes, 0); assert.equal(f.r.rows.length, 2);
  }
});

test('Intake rechecks complete row and intent freshness after authority callbacks', () => {
  for (const mutate of [r => {r.rows[1][24] = 'changed during authority read';},
    r => {r.state.clock += 301;}, r => {r.rows[1][6] = 'QUEUED';}]) {
    const f = intakePurgeFixture(); f.r.state.onPurgeRead = () => mutate(f.r);
    assert.throws(f.remove); assert.equal(f.r.state.intakeDeletes, 0);
  }
});

test('Intake SDK interruption and lost acknowledgement leave authoritative row readback without repeated deletes', () => {
  for (const fault of ['before', 'after', 'noop']) {
    const f = intakePurgeFixture(); f.r.state.deleteFault = fault;
    assert.throws(f.remove, /INTAKE_DELETE_UNCERTAIN|INTAKE_DELETE_UNCONFIRMED/);
    assert.equal(f.r.context.closedIntakeInventory(f.scope).length, fault === 'after' ? 0 : 1);
    assert.equal(f.r.state.intakeDeletes, fault === 'after' ? 1 : 0);
    if (fault === 'after') { assert.throws(f.remove, /INTAKE_BINDING_CHANGED/); assert.equal(f.r.state.intakeDeletes, 1); }
  }
});

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

function ownerGrant(r, scope, digestValue = '6'.repeat(64)) {
  const now = r.state.clock;
  const claim = {contract: 'bsre-owner-no-mail-authorization-v1', intent_digest: digestValue,
    actor: 'synthetic-owner', scope_hash: digest(scope), approved_at: now, create_before: now + 900, recovery_until: now + 2592000};
  r.state.ownerIntents[digestValue] = claim;
  return claim;
}

test('positive inspection uses exact eligible row, complete mailbox and actual ScriptLock', () => {
  const r = receiverLab(); r.admit(); const scope = r.scope();
  const value = r.context.closedNoCopyInspectRetirement(scope);
  assert.equal(value.state, 'UNRETIRED'); assert.equal(value.scope_hash, digest(scope));
  assert.equal(value.attempt_count, 0); assert.equal(value.mailbox.complete, true);
  assert.equal(value.mailbox.includes_trash, true); assert.equal(r.mail.length, 0);
  assert.ok(r.state.operations.includes('mailbox-readback'));
  r.rows[1][7] = 1;
  assert.throws(() => r.context.closedNoCopyInspectRetirement(scope), /NO_COPY_OUTBOX_AMBIGUOUS/);
  r.rows.splice(1, 1);
  assert.throws(() => r.context.closedNoCopyInspectRetirement(scope), /NO_COPY_ROW_MISSING/);
});

test('owner source capability denies absent or wrong-purpose authority before fencing', () => {
  const r = receiverLab(); r.admit(); const scope = r.scope(), intent = '6'.repeat(64);
  assert.throws(() => r.context.closedNoCopyRetireAuthorized(scope, intent), /RETIREMENT_AUTHORITY_UNVERIFIED/);
  const claim = ownerGrant(r, scope); claim.contract = 'wrong-purpose';
  assert.throws(() => r.context.closedNoCopyRetireAuthorized(scope, intent), /RETIREMENT_AUTHORITY_UNVERIFIED/);
  assert.equal(r.rows[1][6], 'QUEUED'); assert.equal(r.state.revision, 1);
});

test('source checks creation deadline after owner callback inside actual ScriptLock', () => {
  const r = receiverLab(); r.admit(); const scope = r.scope(), claim = ownerGrant(r, scope);
  r.state.authorizationDelay = 901;
  assert.throws(() => r.context.closedNoCopyRetireAuthorized(scope, claim.intent_digest), /RETIREMENT_AUTHORIZATION_EXPIRED/);
  assert.equal(r.rows[1][6], 'QUEUED'); assert.equal(r.state.revision, 1);
  assert.ok(r.state.operations.includes('owner-intent-readback'));
});

test('exact authorized fence reconciles after deadline without creating or refreshing a fence', () => {
  const r = receiverLab(); r.admit(); const scope = r.scope(), claim = ownerGrant(r, scope);
  const first = r.context.closedNoCopyRetireAuthorized(scope, claim.intent_digest), revision = r.state.revision;
  assert.equal(first.owner_intent_digest, claim.intent_digest);
  r.state.clock += 901;
  const existing = r.context.closedNoCopyInspectRetirement(scope);
  assert.equal(existing.state, 'RETIRED'); assert.equal(existing.proof.fence_hash, first.fence_hash);
  const replay = r.context.closedNoCopyRetireAuthorized(scope, claim.intent_digest);
  assert.equal(replay.fence_hash, first.fence_hash); assert.equal(replay.fence_created_at, first.fence_created_at);
  assert.equal(r.state.revision, revision); assert.equal(r.mail.length, 0);
});

test('authorized owner path cannot adopt a legacy setup or another owner intent fence', () => {
  const r = receiverLab(); r.admit(); const scope = r.scope();
  r.context.closedNoCopyRetire(scope); const claim = ownerGrant(r, scope);
  assert.throws(() => r.context.closedNoCopyRetireAuthorized(scope, claim.intent_digest), /RETIREMENT_OWNER_INTENT_CONFLICT/);
  const other = receiverLab(); other.admit(); const nextScope = other.scope(), first = ownerGrant(other, nextScope);
  other.context.closedNoCopyRetireAuthorized(nextScope, first.intent_digest);
  const second = ownerGrant(other, nextScope, '7'.repeat(64));
  assert.throws(() => other.context.closedNoCopyRetireAuthorized(nextScope, second.intent_digest), /RETIREMENT_OWNER_INTENT_CONFLICT/);
});
