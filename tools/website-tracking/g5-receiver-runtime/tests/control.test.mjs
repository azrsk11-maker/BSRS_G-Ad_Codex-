import assert from 'node:assert/strict';
import {verify} from 'node:crypto';
import test from 'node:test';
import {createActualControlFixture as fixture, hash, json, copy, NOW, INTENT, ACTOR, TEST_PUBLIC} from './control-fixture.mjs';
function held(result) {
  assert.equal(result.accepted, false); assert.equal(result.code, 'ACTUAL_CONTROL_HELD');
  assert.equal(result.reconciliation_required, true);
}
test('control default-OFF and lead-HMAC-only requests establish no authority or row mutation', () => {
  for (const options of [{enabled: false}, {configured: false}, {enrolled: false}]) {
    const r = fixture(options), before = copy(r.rows);
    held(r.control());
    assert.deepEqual(r.rows, before); assert.equal(r.mail.length, 0); assert.equal(r.calls.length, 0);
  }
});

test('control auth is actor/operation/body/time bound and rejects noncanonical/duplicate envelopes', () => {
  for (const change of [{signature: '0'.repeat(64)}, {timestamp: NOW * 1000 - 31000},
    {actor: 'wp-user:0'}, {operation: 'purge'}, {challenge: 'not-a-challenge'}]) {
    const r = fixture(); held(r.control('inspect', {scope: r.knownScope}, change));
    assert.equal(r.calls.length, 0); assert.equal(r.rows[1][6], 'QUEUED');
  }
  const r = fixture();
  held(r.postWire('{"control_contract":"bsre-receiver-control-v1","control_version":1,"control_version":1}'));
  assert.equal(r.calls.length, 0);
});

test('independent service MAC and fresh challenge/source/namespace/expiry bindings cannot be substituted', () => {
  const mutations = [response => { response.challenge = '0'.repeat(64); },
    response => { response.source = '0'.repeat(64); }, response => { response.namespace = '0'.repeat(64); },
    response => { response.expires_at = NOW; }, response => { response.issued_at = NOW + 1; },
    response => { response.request_hash = '0'.repeat(64); }, response => { response.operation = 'runtime.other'; }];
  for (const mutateResponse of mutations) {
    const r = fixture({mutateResponse}), before = copy(r.rows);
    held(r.control()); assert.deepEqual(r.rows, before); assert.equal(r.mail.length, 0);
  }
  const r = fixture();
  // Set the field on the original receiver fixture captured by the fake too.
  r.context.UrlFetchApp.fetch = ((original) => (url, options) => {
    const response = original(url, options), raw = JSON.parse(response.getContentText()); raw.mac = '0'.repeat(64);
    return {getResponseCode: () => 200, getContentText: () => json(raw)};
  })(r.context.UrlFetchApp.fetch);
  held(r.control()); assert.equal(r.rows[1][6], 'QUEUED');
});

test('positive inspect uses exact actual ScriptLock/Intake26 and independently authenticated service result', () => {
  const r = fixture(), before = copy(r.rows), result = r.control();
  assert.equal(result.key_id, 'synthetic-rfc8032');
  assert.equal(verify(null, Buffer.from(hash(result.statement)), TEST_PUBLIC, Buffer.from(result.signature, 'base64')), true);
  assert.equal(result.statement.operation, 'inspect');
  assert.deepEqual(r.rows, before); assert.equal(r.rows[1].length, 26); assert.equal(r.mail.length, 0);
  assert.ok(r.calls.some(call => call.operation === 'runtime.current'));
  assert.ok(r.calls.some(call => call.operation === 'mailbox.current_including_trash'));
  assert.equal(r.calls.at(-1).operation, 'attest_control_result');
  assert.equal(r.state.held, false);
});

test('positive retirement advances independent state then durably writes floor/fence/status/metadata in order', () => {
  const r = fixture(), ids = r.rows[1].slice(0, 6);
  const result = r.control('retire', {scope: r.knownScope, intent_digest: INTENT});
  assert.equal(result.key_id, 'synthetic-rfc8032');
  assert.equal(verify(null, Buffer.from(hash(result.statement)), TEST_PUBLIC, Buffer.from(result.signature, 'base64')), true);
  assert.equal(r.rows[1][6], 'RETIRED_NO_COPY'); assert.equal(r.rows[1][7], 0);
  assert.deepEqual(r.rows[1].slice(0, 6), ids); assert.equal(r.rows[1].length, 26); assert.equal(r.mail.length, 0);
  assert.equal(r.remote.revision, 2);
  assert.equal(r.properties[r.context.ACTUAL_NO_COPY_FLOOR], json(r.floor()));
  const at = predicate => r.trace.findIndex(predicate);
  const order = [at(x => x.event === 'authority' && x.operation === 'runtime.advance_retirement'),
    at(x => x.event === 'property-write' && x.key === r.context.ACTUAL_NO_COPY_FLOOR),
    at(x => x.event === 'property-write' && x.key.startsWith('bsre.actual-no-copy.v1.')),
    at(x => x.event === 'row-write' && x.first === 'RETIRED_NO_COPY'), at(x => x.event === 'metadata-write')];
  assert.ok(order.every(index => index >= 0));
  assert.deepEqual([...order].sort((a, b) => a - b), order);
  assert.ok(r.trace.filter(x => x.event.endsWith('write')).every(x => x.held));
  r.context.processLeadOutbox(); assert.equal(r.mail.length, 0);
  const repeated = r.control('retire', {scope: r.knownScope, intent_digest: INTENT});
  assert.equal(repeated.key_id, 'synthetic-rfc8032'); assert.equal(r.remote.revision, 2);
  assert.equal(r.rows.length, 2); assert.equal(r.mail.length, 0);
});

test('version1 collision is delegated to the old lead parser rather than the control parser', () => {
  const r = fixture({enabled: false});
  const env = {version: 1, control_contract: 'bsre-receiver-control-v1', control_version: 1,
    timestamp: String(NOW * 1000), body: '{}', signature: '0'.repeat(64)};
  const event = {postData: {contents: json(env)}};
  assert.deepEqual(r.postWire(json(env)), JSON.parse(r.context.actualLegacyLeadPost_(event).text));
  assert.equal(r.postWire(json(env)).code, 'AUTH_FAILED'); assert.equal(r.calls.length, 0);
});

test('independent advance followed by local floor-write failure holds without a fence or retired acknowledgement', () => {
  const r = fixture(), localBefore = r.properties[r.context.ACTUAL_NO_COPY_FLOOR];
  r.faults.localFloor = true;
  held(r.control('retire', {scope: r.knownScope, intent_digest: INTENT}));
  assert.equal(r.remote.revision, 2);
  assert.equal(r.properties[r.context.ACTUAL_NO_COPY_FLOOR], localBefore);
  assert.equal(r.rows[1][6], 'QUEUED');
  assert.equal(r.properties['bsre.actual-no-copy.v1.' + r.knownScope.request_id], undefined);
  assert.equal(r.mail.length, 0); assert.equal(r.state.held, false);
});

test('native fixture binds dynamic actor/admission and registered durable intent without changing physical identity', () => {
  const now = NOW + 100;
  const r = fixture({now, actor: 'wp-user:9', admissionHash: 'c'.repeat(64), descriptor: {
    contract: 'bsre-retention-admission-v1', mode: 'ENFORCED', generation: '4'.repeat(64),
    audience: '5'.repeat(64), activated_at: now - 2000, max_age_seconds: 900}});
  const physical = [r.knownScope.request_id, r.knownScope.lead_id, r.knownScope.event_id, r.knownScope.fingerprint];
  r.fixtureAgeAcceptanceBeforeApproval(NOW - 400 * 86400);
  const scope = {...r.knownScope, closure_hash: '6'.repeat(64), closure_revision: 2};
  r.bindKnownScope(scope);
  const plan = {actor: 'wp-user:9', scope, created_at: now, expires_at: now + 900};
  plan.digest = hash(plan);
  const record = {contract: 'bsre-owner-no-mail-retirement-v1', revision: 1, plan,
    approved_at: now, recovery_until: now + 2592000};
  r.authorizeIntent(record);
  assert.throws(() => r.fixtureAgeAcceptanceBeforeApproval(NOW - 401 * 86400));
  const result = r.control('retire', {scope, intent_digest: plan.digest});
  assert.equal(result.statement.actor, 'wp-user:9');
  assert.equal(result.statement.contract, 'bsre-actual-receiver-evidence-v1');
  assert.equal(result.statement.source.admission, 'c'.repeat(64));
  assert.equal(result.statement.claims.intent_digest, plan.digest);
  assert.equal(r.rows[1][6], 'RETIRED_NO_COPY');
  assert.deepEqual([r.knownScope.request_id, r.knownScope.lead_id, r.knownScope.event_id, r.knownScope.fingerprint], physical);
});

test('native fixture rejects identity substitution and scope binding after a control starts', () => {
  const r = fixture();
  assert.throws(() => r.bindKnownScope({...r.knownScope, event_id: 'evt_30000000-0000-4000-8000-000000000999'}));
  r.control();
  assert.throws(() => r.bindKnownScope({...r.knownScope, closure_hash: '8'.repeat(64)}));
});
