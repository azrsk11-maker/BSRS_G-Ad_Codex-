import assert from 'node:assert/strict';
import {createHash, createHmac, randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {lab} from '../../staging-lab/receiver-lab.mjs';
import {buildReceiptStatusCandidate} from './build-receipt-status-candidate.mjs';

const original = readFileSync(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs', import.meta.url));
const candidate = Buffer.from(buildReceiptStatusCandidate(original));
const purpose = 'bsre-receipt-status-v1';
const unconfirmed = {status: 'UNCONFIRMED'};

function statusEnvelope(fixture, requestId, changes = {}) {
  const value = {version: 1, purpose, request_id: requestId, timestamp: String(Date.now()), ...changes};
  if (!Object.hasOwn(changes, 'signature')) {
    value.signature = createHmac('sha256', fixture.properties.HMAC_SECRET)
      .update(`${purpose}\n${value.timestamp}\n${value.request_id}`).digest('hex');
  }
  return value;
}

function lookup(fixture, requestId, changes = {}) {
  return fixture.postWire(JSON.stringify(statusEnvelope(fixture, requestId, changes)));
}

function state(fixture) {
  return JSON.stringify({rows: fixture.rows, mail: fixture.mail, properties: fixture.properties});
}

test('receiver status candidate pins its source and keeps the original fixture intact', () => {
  assert.throws(() => buildReceiptStatusCandidate(Buffer.concat([original, Buffer.from('\n')])), /SOURCE_CHANGED/);
  assert.equal(createHash('sha256').update(original).digest('hex'), '6669cb28e5267a49e061427b736cdbdbad87bee6cbb946e99483d9439f61fa38');
  assert.equal(createHash('sha256').update(readFileSync(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs', import.meta.url))).digest('hex'), createHash('sha256').update(original).digest('hex'));
});

test('derived receiver preserves wire-v1 lead handling, 26 columns and retry identity', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  const accepted = fixture.post(payload);
  assert.equal(accepted.accepted, true);
  assert.equal(fixture.rows[1].length, 26);
  assert.deepEqual(fixture.post(payload), accepted);
  assert.equal(fixture.post({...payload, area: 'Changed synthetic area'}).code, 'REQUEST_ID_CONFLICT');
  assert.equal(fixture.rows.length, 2);
});

test('authenticated status returns the existing receipt without writes or private fields', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  const accepted = fixture.post(payload), before = state(fixture);
  assert.deepEqual(lookup(fixture, payload.request_id), {status: 'ACCEPTED', request_id: payload.request_id,
    lead_id: accepted.lead_id, event_id: accepted.event_id});
  assert.deepEqual(lookup(fixture, payload.request_id), {status: 'ACCEPTED', request_id: payload.request_id,
    lead_id: accepted.lead_id, event_id: accepted.event_id});
  assert.equal(state(fixture), before);
  assert.equal(fixture.mail.length, 0);
});

test('status accepts the receiver normal form for trimmed text and attribution', () => {
  const fixture = lab(candidate), payload = {...fixture.payload(), name: '  TEST synthetic caf\u00e9  ',
    country: ' UAE ', attribution: {first: {landing_page: 'https://blackswanrealestate.ae/enquire/rent/?utm_source=synthetic',
      referrer: 'https://example.invalid/path?discard=synthetic', timestamp: Date.now(), parameters: {utm_source: ' synthetic '}}}};
  const accepted = fixture.post(payload);
  assert.equal(accepted.accepted, true);
  assert.equal(JSON.parse(fixture.rows[1][5]).name, 'TEST synthetic caf\u00e9');
  assert.deepEqual(lookup(fixture, payload.request_id), {status: 'ACCEPTED', request_id: payload.request_id,
    lead_id: accepted.lead_id, event_id: accepted.event_id});
});

test('status authentication and schema failures occur before Sheet or lock access', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  fixture.post(payload);
  let sheetCalls = 0, lockCalls = 0;
  fixture.context.SpreadsheetApp.openById = () => { sheetCalls++; throw new Error('Unexpected Sheet access'); };
  fixture.context.LockService.getScriptLock = () => { lockCalls++; throw new Error('Unexpected lock access'); };
  const invalid = [
    {version: 2}, {purpose: 'wrong-purpose'}, {signature: '0'.repeat(64)},
    {signature: 'A'.repeat(64)}, {request_id: payload.request_id.toUpperCase()},
    {request_id: '../' + payload.request_id}, {request_id: 1}, {timestamp: Date.now()},
    {timestamp: '0000000000000'}, {timestamp: String(Date.now() - 301000)},
    {timestamp: String(Date.now() + 301000)}, {extra: true},
  ];
  for (const changes of invalid) assert.deepEqual(lookup(fixture, payload.request_id, changes), unconfirmed);
  for (const key of ['version', 'purpose', 'request_id', 'timestamp', 'signature']) {
    const value = statusEnvelope(fixture, payload.request_id);
    delete value[key];
    assert.deepEqual(fixture.postWire(JSON.stringify(value)), unconfirmed);
  }
  const oversized = JSON.stringify(statusEnvelope(fixture, payload.request_id)).replace('{', '{' + ' '.repeat(513));
  assert.deepEqual(fixture.postWire(oversized), unconfirmed);
  assert.equal(sheetCalls, 0);
  assert.equal(lockCalls, 0);
});

test('status signature is purpose-bound and cannot reuse a lead signature', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  fixture.post(payload);
  const value = statusEnvelope(fixture, payload.request_id);
  value.signature = createHmac('sha256', fixture.properties.HMAC_SECRET)
    .update(`v1\n${value.timestamp}\n${value.request_id}`).digest('hex');
  assert.deepEqual(fixture.postWire(JSON.stringify(value)), unconfirmed);
  assert.deepEqual(lookup(fixture, payload.request_id, {purpose: 'v1'}), unconfirmed);
});

test('status freshness accepts only the bounded time window', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  fixture.post(payload);
  const now = Date.now();
  fixture.context.Date = class extends Date { static now() { return now; } };
  for (const offset of [-300000, 300000]) {
    assert.equal(lookup(fixture, payload.request_id, {timestamp: String(now + offset)}).status, 'ACCEPTED');
  }
  for (const offset of [-300001, 300001]) {
    assert.deepEqual(lookup(fixture, payload.request_id, {timestamp: String(now + offset)}), unconfirmed);
  }
});

test('missing and duplicate receiver records remain unconfirmed without writes', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  assert.deepEqual(lookup(fixture, randomUUID()), unconfirmed);
  fixture.post(payload);
  fixture.rows.push([...fixture.rows[1]]);
  const before = state(fixture);
  assert.deepEqual(lookup(fixture, payload.request_id), unconfirmed);
  assert.equal(state(fixture), before);
});

test('corrupt receipt identifiers never become recovery confirmations', () => {
  for (const column of [1, 2]) {
    for (const corrupt of ['', 'wrong', 123, 'BSRE-' + randomUUID(), 'evt_' + randomUUID()]) {
      const fixture = lab(candidate), payload = fixture.payload();
      fixture.post(payload);
      if ((column === 1 && /^BSRE-/.test(corrupt)) || (column === 2 && /^evt_/.test(corrupt))) continue;
      fixture.rows[1][column] = corrupt;
      const before = state(fixture);
      assert.deepEqual(lookup(fixture, payload.request_id), unconfirmed);
      assert.equal(state(fixture), before);
    }
  }
});

test('status rejects corrupt payloads, fingerprints and mismatched stored request identities', () => {
  const mutations = [
    row => { row[5] = '{'; },
    row => { row[4] = '0'.repeat(64); },
    row => { row[4] = null; },
    row => {
      const payload = JSON.parse(row[5]);
      payload.request_id = randomUUID();
      row[5] = JSON.stringify(payload);
      row[4] = createHash('sha256').update(row[5]).digest('hex');
    },
    row => {
      const payload = JSON.parse(row[5]);
      payload.contact_consent = false;
      row[5] = JSON.stringify(payload);
      row[4] = createHash('sha256').update(row[5]).digest('hex');
    },
    row => {
      row[5] += ' ';
      row[4] = createHash('sha256').update(row[5]).digest('hex');
    },
  ];
  for (const mutate of mutations) {
    const fixture = lab(candidate), payload = fixture.payload();
    fixture.post(payload);
    mutate(fixture.rows[1]);
    const before = state(fixture);
    assert.deepEqual(lookup(fixture, payload.request_id), unconfirmed);
    assert.equal(state(fixture), before);
  }
});

test('busy lock and unavailable Sheet remain unconfirmed', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  fixture.post(payload);
  const before = state(fixture);
  fixture.setBusy(true);
  assert.deepEqual(lookup(fixture, payload.request_id), unconfirmed);
  fixture.setBusy(false);
  fixture.context.SpreadsheetApp.openById = () => { throw new Error('Synthetic unavailable Sheet'); };
  assert.deepEqual(lookup(fixture, payload.request_id), unconfirmed);
  assert.equal(state(fixture), before);
});

test('disabled routing retains the original rejection and performs no Sheet access', () => {
  const fixture = lab(candidate), payload = fixture.payload();
  fixture.properties.ROUTING_ENABLED = 'false';
  fixture.context.SpreadsheetApp.openById = () => assert.fail('Disabled Sheet access');
  assert.equal(lookup(fixture, payload.request_id).code, 'ROUTING_DISABLED');
  assert.equal(fixture.rows.length, 1);
});
