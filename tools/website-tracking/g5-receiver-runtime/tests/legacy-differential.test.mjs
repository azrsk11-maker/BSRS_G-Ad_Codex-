import assert from 'node:assert/strict';
import {createHash, createHmac} from 'node:crypto';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import {buildActualRetirementReceiver} from '../build-candidate.mjs';

const sourceRoot = new URL('../../../../', import.meta.url);
const {receiverLab} = await import(new URL('tools/closed-enquiry-retention/receiver-fence/lab.mjs', sourceRoot));
const {buildNoMailCopyReceiver} = await import(new URL(
  'tools/closed-enquiry-retention/receiver-fence/build-candidate.mjs', sourceRoot));
const original = readFileSync(new URL('tools/staging-lab/fixtures/receiver-v2/Code.gs', sourceRoot));
const baselineCode = buildNoMailCopyReceiver(original);
assert.equal(baselineCode.length, 50830);
assert.equal(createHash('sha256').update(baselineCode).digest('hex'),
  '00b62f1edc8996ab4f566a80155715a85f741bc5d68e7a0a54c94fc4ef2cbdc5');
const candidateCode = buildActualRetirementReceiver(baselineCode);
assert.ok(Buffer.isBuffer(baselineCode));
assert.ok(Buffer.isBuffer(candidateCode));
const fixedNow = Date.UTC(2026, 10, 16, 12, 0, 0);
const secret = 'synthetic-secret-never-production-0000'; // Existing lab transport fixture, never authority.
const generation = 'a'.repeat(64), audience = 'b'.repeat(64);
const clone = value => JSON.parse(JSON.stringify(value));
const uuid = number => `10000000-0000-4000-8000-${String(number).padStart(12, '0')}`;

// Prefix only the capability VM, not generated source. No real provider exists.
// Function declarations are hoisted, so the authority helper is counted during
// initialization too; the candidate's declaration must retain that wrapper.
const prefix = Buffer.from(`
var __differentialNow=${fixedNow}, __differentialUuid=0;
var __differentialFetchCalls=0, __differentialAuthorityCalls=0;
var __differentialNativeDate=Date;
Date=class extends __differentialNativeDate {
  constructor(...args){super(...(args.length?args:[__differentialNow]));}
  static now(){return __differentialNow;}
};
Utilities.getUuid=function(){return '20000000-0000-4000-8000-'+String(++__differentialUuid).padStart(12,'0');};
var UrlFetchApp={fetch:function(){__differentialFetchCalls++;throw Error('UNEXPECTED_AUTHORITY_FETCH');},
  fetchAll:function(){__differentialFetchCalls++;throw Error('UNEXPECTED_AUTHORITY_FETCH');}};
var __differentialOriginalAuthority=typeof actualAuthorityRequest_==='function'?actualAuthorityRequest_:null;
var __differentialAuthorityWrapper=null;
if(__differentialOriginalAuthority){
  __differentialAuthorityWrapper=function(){__differentialAuthorityCalls++;return __differentialOriginalAuthority.apply(this,arguments);};
  actualAuthorityRequest_=__differentialAuthorityWrapper;
}
`);

function instance(code) {
  // Reuse the actual selected receiver's synthetic fence/runtime/Sheet service
  // fixture, then evaluate each exact source against the same capabilities.
  const state = receiverLab({now: Math.floor(fixedNow / 1000)});
  vm.runInContext(Buffer.concat([prefix, code]).toString(), state.context, {timeout: 1000});
  state.now = fixedNow;
  state.payloadFixed = (number = 1, changes = {}) => ({...state.payload(), request_id: uuid(number),
    started_at: fixedNow - 5000, ...changes});
  state.postFixed = (payload, changes = {}) => {
    const body = JSON.stringify(payload);
    const envelope = {version: 1, body, timestamp: String(state.now),
      admission: admission(payload.request_id, Math.floor(state.now / 1000)), ...changes};
    if (!Object.hasOwn(changes, 'signature')) envelope.signature = createHmac('sha256', secret)
      .update(`v1\n${envelope.timestamp}\n${envelope.body}`).digest('hex');
    return state.postWire(JSON.stringify(envelope));
  };
  state.advance = milliseconds => { state.now += milliseconds; state.context.__differentialNow = state.now;
    state.state.clock = Math.floor(state.now / 1000); };
  state.setBusy = value => { state.state.busy = value; };
  return state;
}

function pair() {
  const a = instance(baselineCode), b = instance(candidateCode);
  assert.equal(b.context.actualAuthorityRequest_, b.context.__differentialAuthorityWrapper,
    'candidate must expose and retain the counted authority seam');
  assert.equal(typeof b.context.actualAuthorityRequest_, 'function');
  return [a, b];
}

function snapshot(state) {
  return clone({rows: state.rows, mail: state.mail, properties: state.properties,
    metadata: state.metadata, legacyState: {...state.state,
      // Looking up the new default-OFF flag adds locked property reads. Compare
      // every product state and other operation; the fixture itself enforces
      // ScriptLock on every property read, including these extra config reads.
      operations: state.state.operations.filter(operation => operation !== 'property-read')},
    uuidCalls: state.context.__differentialUuid,
    fetchCalls: state.context.__differentialFetchCalls,
    authorityCalls: state.context.__differentialAuthorityCalls});
}

function equivalent(states) {
  assert.deepEqual(snapshot(states[1]), snapshot(states[0]));
  assert.equal(states[1].context.__differentialFetchCalls, 0, 'default-OFF must never contact authority');
  assert.equal(states[1].context.__differentialAuthorityCalls, 0, 'default-OFF must never invoke authority helper');
}

function step(states, action) {
  const replies = states.map(action).map(value => value === undefined ? null : clone(value));
  assert.deepEqual(replies[1], replies[0]);
  equivalent(states);
  return replies[0];
}

function admission(id, issued = Math.floor(fixedNow / 1000)) {
  const value = {version: 1, request_id: id, issued_at: issued, expires_at: issued + 900,
    session_hash: 'c'.repeat(64), generation, audience};
  value.signature = createHmac('sha256', secret).update(['bsre-retention-admission-v1', id, issued,
    value.expires_at, value.session_hash, generation, audience].join('\n')).digest('hex');
  return value;
}

test('default-OFF valid wire-v1 preserves every Intake26 cell and makes zero authority calls', () => {
  for (const flag of [undefined, 'false']) {
    const states = pair();
    if (flag !== undefined) for (const state of states) state.properties.BSRE_ACTUAL_RETIREMENT_ENABLED = flag;
    const receipt = step(states, state => state.postFixed(state.payloadFixed()));
    assert.equal(receipt.accepted, true);
    assert.equal(states[0].rows.length, 2);
    assert.equal(states[0].rows[1].length, 26);
    assert.equal(states[0].rows[1][6], 'QUEUED');
    assert.equal(states[0].mail.length, 0);
    assert.equal(JSON.parse(states[0].rows[1][5]).request_id, uuid(1));
  }
});

test('default-OFF invalid auth/version/time/body/contact cases preserve rejection and no writes', () => {
  const states = pair();
  for (const change of [{signature: '0'.repeat(64)}, {version: 2}, {timestamp: '1000000000000'}])
    assert.equal(step(states, state => state.postFixed(state.payloadFixed(), change)).code, 'AUTH_FAILED');
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(1, {contact_consent: false}))).code,
    'VALIDATION_FAILED');
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(1, {name: ''}))).code,
    'VALIDATION_FAILED');
  step(states, state => state.postWire('{broken-json'));
  assert.equal(states[0].rows.length, 1);
});

test('default-OFF exact and normalized duplicates preserve IDs while changed body conflicts', () => {
  const states = pair(), receipt = step(states, state => state.postFixed(state.payloadFixed()));
  assert.deepEqual(step(states, state => state.postFixed(state.payloadFixed())), receipt);
  assert.deepEqual(step(states, state => state.postFixed(state.payloadFixed(1, {name: '  TEST synthetic  '}))), receipt);
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(1, {area: 'Changed'}))).code,
    'REQUEST_ID_CONFLICT');
  assert.equal(states[0].rows.length, 2);
});

test('default-OFF lock-busy and disabled routing preserve refusal without appending', () => {
  const states = pair();
  for (const state of states) state.setBusy(true);
  assert.equal(step(states, state => state.postFixed(state.payloadFixed())).code, 'BUSY');
  for (const state of states) { state.setBusy(false); state.properties.ROUTING_ENABLED = 'false'; }
  assert.equal(step(states, state => state.postFixed(state.payloadFixed())).code, 'ROUTING_DISABLED');
  assert.equal(states[0].rows.length, 1);
});

test('default-OFF lost flush acknowledgement recovers the same persisted row without resend', () => {
  const states = pair();
  for (const state of states) state.failFlush();
  assert.equal(step(states, state => state.postFixed(state.payloadFixed())).code,
    'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID');
  assert.equal(states[0].rows.length, 2);
  assert.equal(step(states, state => state.postFixed(state.payloadFixed())).accepted, true);
  assert.equal(states[0].rows.length, 2);
  assert.equal(states[0].mail.length, 0);
});

test('default-OFF duplicate stored identities require reconciliation without overwrite', () => {
  const states = pair();
  step(states, state => state.postFixed(state.payloadFixed()));
  for (const state of states) state.rows.push([...state.rows[1]]);
  assert.equal(step(states, state => state.postFixed(state.payloadFixed())).code, 'DUPLICATE_ROWS_RECONCILE');
  assert.equal(states[0].rows.length, 3);
});

test('default-OFF normal outbox sends once with identical recipient, body and receipt IDs', () => {
  const states = pair();
  step(states, state => state.postFixed(state.payloadFixed()));
  step(states, state => state.context.processLeadOutbox());
  assert.equal(states[0].rows[1][6], 'SENT');
  assert.equal(states[0].mail.length, 1);
  assert.equal(states[0].mail[0].to, 'marketing@blackswanrealestate.ae');
  step(states, state => state.context.processLeadOutbox());
  assert.equal(states[0].mail.length, 1);
});

test('default-OFF ambiguous send and post-send commit fault never blindly retry', () => {
  for (const fault of ['send', 'commit']) {
    const states = pair();
    step(states, state => state.postFixed(state.payloadFixed()));
    for (const state of states) {
      if (fault === 'send') state.setSendFault(true);
      else {
        const flush = state.context.SpreadsheetApp.flush;
        let calls = 0;
        state.context.SpreadsheetApp.flush = () => { if (++calls === 2) throw Error('synthetic post-send commit'); return flush(); };
      }
    }
    step(states, state => state.context.processLeadOutbox());
    assert.equal(states[0].rows[1][6], 'AMBIGUOUS');
    assert.equal(states[0].mail.length, 1);
    step(states, state => state.context.processLeadOutbox());
    assert.equal(states[0].mail.length, 1);
  }
});

test('default-OFF quota exhaustion remains a pre-send retry with no attempt upgrade', () => {
  const states = pair();
  step(states, state => state.postFixed(state.payloadFixed()));
  for (const state of states) state.setQuota(0);
  step(states, state => state.context.processLeadOutbox());
  assert.equal(states[0].rows[1][6], 'RETRY_WAIT');
  assert.equal(states[0].rows[1][7], 0);
  assert.equal(states[0].mail.length, 0);
  for (const state of states) { state.setQuota(100); state.rows[1][8] = ''; }
  step(states, state => state.context.processLeadOutbox());
  assert.equal(states[0].mail.length, 1);
});

test('default-OFF preserves all five role wire payloads and Intake26/outbox identities', () => {
  for (const [role, slug, timeline] of [['off_plan', 'off-plan', 'Within 1 month'],
    ['resale', 'resale', 'Within 1 month'], ['tenant', 'rent', 'Immediate / move now'],
    ['seller', 'sell', 'As soon as practical'], ['landlord', 'let', 'Vacant / available to discuss now']]) {
    const states = pair();
    const changes = {role, timeline, landing_page: `https://blackswanrealestate.ae/enquire/${slug}/`,
      ...(['seller', 'landlord'].includes(role) ? {authority: 'owner', property_details: 'SYNTHETIC PROPERTY ONLY'} : {})};
    assert.equal(step(states, state => state.postFixed(state.payloadFixed(1, changes))).accepted, true);
    assert.equal(states[0].rows[1].length, 26);
    step(states, state => state.context.processLeadOutbox());
    assert.equal(states[0].mail.length, 1);
  }
});

test('default-OFF preserves ENFORCED admission validation and keeps proofs outside wire body', () => {
  const states = pair();
  for (const state of states) Object.assign(state.properties, {RETENTION_ADMISSION_REQUIRED: 'true',
    RETENTION_ADMISSION_GENERATION: generation, RETENTION_ADMISSION_AUDIENCE: audience,
    RETENTION_ADMISSION_ACTIVATED_AT: String(Math.floor(fixedNow / 1000) - 2000)});
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(), {admission: null})).code, 'ADMISSION_REQUIRED');
  const proof = admission(uuid(1));
  for (const changed of [{...proof, signature: '0'.repeat(64)}, {...proof, audience: 'e'.repeat(64)},
    {...proof, extra: true}]) assert.equal(step(states, state => state.postFixed(state.payloadFixed(),
    {admission: changed})).code, 'ADMISSION_REQUIRED');
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(), {admission: proof})).accepted, true);
  assert.equal(states[0].rows[1].length, 26);
  assert.equal(Object.hasOwn(JSON.parse(states[0].rows[1][5]), 'admission'), false);
  for (const state of states) state.advance(900000);
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(), {admission: proof})).accepted, true);
  for (const state of states) state.rows.splice(1, 1); // Isolated approved-purge simulation only.
  assert.equal(step(states, state => state.postFixed(state.payloadFixed(), {admission: proof})).code,
    'ADMISSION_REQUIRED');
  assert.equal(states[0].rows.length, 1);
});

test('default-OFF receipt-status v1 readback and failed authentication remain unchanged', () => {
  const states = pair();
  const receipt = step(states, state => state.postFixed(state.payloadFixed()));
  const request = {version: 1, purpose: 'bsre-receipt-status-v1', request_id: uuid(1), timestamp: String(fixedNow)};
  request.signature = createHmac('sha256', secret).update(
    `bsre-receipt-status-v1\n${request.timestamp}\n${request.request_id}`).digest('hex');
  const status = step(states, state => state.postWire(JSON.stringify(request)));
  assert.equal(status.status, 'ACCEPTED');
  assert.equal(status.lead_id, receipt.lead_id);
  assert.equal(status.event_id, receipt.event_id);
  assert.equal(step(states, state => state.postWire(JSON.stringify({...request, signature: '0'.repeat(64)}))).status,
    'UNCONFIRMED');
});

test('default-OFF preserves original synthetic origin/runtime/floor/admission failure guards', () => {
  for (const mutation of [state => { state.context.BSRE_SYNTHETIC_NO_COPY_LAB = false; },
    state => { state.state.runtimeStale = true; }, state => { state.state.restoreFenced = false; },
    state => { state.properties['bsre.closed-no-copy.floor'] = '{}'; },
    state => { state.properties.RETENTION_ADMISSION_GENERATION = 'd'.repeat(64); },
    state => { state.metadata[1][state.metadata[0].indexOf('source_hash')] = '0'.repeat(64); }]) {
    const states = pair();
    for (const state of states) mutation(state);
    const result = step(states, state => state.postFixed(state.payloadFixed()));
    assert.equal(result.accepted, false);
    assert.equal(states[0].rows.length, 1);
    assert.equal(states[0].mail.length, 0);
  }
});
