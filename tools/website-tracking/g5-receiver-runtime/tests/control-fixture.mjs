import assert from 'node:assert/strict';
import {createHash, createHmac, createPrivateKey, createPublicKey, sign, verify} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {resolve, sep} from 'node:path';
import {pathToFileURL} from 'node:url';

import vm from 'node:vm';
import {buildActualRetirementReceiver} from '../build-candidate.mjs';

const suppliedRoot = process.env.BSRE_RECEIVER_TEST_SOURCE_ROOT;
const root = suppliedRoot ? (suppliedRoot.startsWith('file:') ? new URL(suppliedRoot) : pathToFileURL(resolve(suppliedRoot) + sep))
  : new URL('../../../../', import.meta.url);
const {receiverLab, canonical} = await import(new URL('tools/closed-enquiry-retention/receiver-fence/lab.mjs', root));
const {buildNoMailCopyReceiver} = await import(new URL('tools/closed-enquiry-retention/receiver-fence/build-candidate.mjs', root));
const original = readFileSync(new URL('tools/staging-lab/fixtures/receiver-v2/Code.gs', root));
const selected = buildNoMailCopyReceiver(original), candidate = buildActualRetirementReceiver(selected);
assert.equal(selected.length, 50830);
const hash = value => createHash('sha256').update(typeof value === 'string' ? value : json(value)).digest('hex');
const json = value => JSON.stringify(canonical(value));
const copy = value => JSON.parse(JSON.stringify(value));
const mac = (value, secret) => createHmac('sha256', secret).update(value).digest('hex');
const NOW = Math.floor(Date.UTC(2026, 10, 16, 12) / 1000);
const TRANSPORT_SECRET = 'synthetic-secret-never-production-0000';
const AUTHORITY_SECRET = 'synthetic-separate-authority-secret-0000000000000000';
const AUTHORITY_URL = 'https://authority.example.invalid/receiver';
const NAMESPACE = '9'.repeat(64), SOURCE = createHash('sha256').update(candidate).digest('hex');
const INTENT = '7'.repeat(64), ACTOR = 'wp-user:7';
const uuid = number => `30000000-0000-4000-8000-${String(number).padStart(12, '0')}`;
// RFC8032 public test vector1; imported, never generated or used as a real key.
const TEST_KEY = createPrivateKey({format: 'der', type: 'pkcs8', key: Buffer.from(
  '302e020100300506032b6570042204209d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60', 'hex')});
const TEST_PUBLIC = createPublicKey(TEST_KEY);
const TEST_PUBLIC_KEY_HEX = 'd75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a';
assert.equal(TEST_PUBLIC.export({format: 'der', type: 'spki'}).subarray(-32).toString('hex'), TEST_PUBLIC_KEY_HEX);

export function signEvidence(statement, keyId = 'synthetic-rfc8032') {
  return {key_id: keyId, statement: copy(statement),
    signature: sign(null, Buffer.from(hash(statement)), TEST_KEY).toString('base64')};
}

export function createActualControlFixture({now = NOW, actor = ACTOR, descriptor: admissionDescriptor,
  admissionHash = 'd'.repeat(64), enabled = true, configured = true, enrolled = true, mutateResponse} = {}) {
  assert.ok(Number.isSafeInteger(now) && now > 0);
  assert.match(actor, /^wp-user:[1-9][0-9]{0,17}$/); assert.match(admissionHash, /^[a-f0-9]{64}$/);
  const r = receiverLab({now, descriptor: admissionDescriptor, admissionHash});
  let nextUuid = 100, controlCount = 0;
  r.context.Utilities.getUuid = () => uuid(++nextUuid);
  const payload = {...r.payload(), request_id: uuid(1), started_at: now * 1000 - 5000};
  assert.equal(r.post(payload).accepted, true); // Actual selected synthetic receiver, before activation.
  vm.runInContext(candidate.toString(), r.context, {timeout: 1000});
  const knownScope = copy(r.scope()), calls = [], trace = [], faults = {localFloor: false};
  let used = false, authorized = false;
  const ownerIntents = new Map([[INTENT, {contract: 'bsre-owner-no-mail-authorization-v1', intent_digest: INTENT,
    actor, scope_hash: hash(knownScope), approved_at: now, create_before: now + 900, recovery_until: now + 2592000}]]);
  const remote = {epoch: 'e'.repeat(64), revision: 1, pruned: 0};
  const descriptor = () => copy(r.context.retentionAdmissionDescriptor_());
  const current = () => ({contract: 'bsre-closed-no-mail-copy-v1', namespace: NAMESPACE,
    epoch: remote.epoch, revision: remote.revision, pruned_through: remote.pruned,
    admission_hash: admissionHash, admission_descriptor_hash: hash(descriptor()), source_hash: SOURCE,
    restore_policy_hash: 'f'.repeat(64), observed_at: r.state.clock, expires_at: r.state.clock + 300,
    recovery: {contract: 'bsre-retention-admission-v1', window_seconds: 2592000,
      restore_fenced: true, backups_expired_through: 0}});
  const floor = () => ({contract: 'bsre-closed-no-mail-copy-v1', namespace: NAMESPACE,
    epoch: remote.epoch, revision: remote.revision, pruned_through: remote.pruned,
    generation: descriptor().generation, activated_at: descriptor().activated_at, audience: descriptor().audience,
    admission_hash: admissionHash, restore_policy_hash: 'f'.repeat(64), source_hash: SOURCE});
  if (enabled) r.properties.BSRE_ACTUAL_RETIREMENT_ENABLED = 'true';
  if (configured) Object.assign(r.properties, {BSRE_RECEIVER_AUTHORITY_URL: AUTHORITY_URL,
    BSRE_RECEIVER_AUTHORITY_SECRET: AUTHORITY_SECRET, BSRE_RECEIVER_NAMESPACE: NAMESPACE,
    BSRE_RECEIVER_SOURCE_SHA256: SOURCE, BSRE_RECEIVER_EVIDENCE_KEY_ID: 'synthetic-rfc8032'});
  const enroll = () => {
    assert.equal(used, false, 'synthetic enrollment must precede controls');
    r.properties[r.context.ACTUAL_CONTROL_ACTIVATION] = json({namespace: NAMESPACE, source: SOURCE});
    r.properties[r.context.ACTUAL_NO_COPY_FLOOR] = json(floor());
    const ordered = canonical(floor());
    r.metadata.splice(0, r.metadata.length, Object.keys(ordered), Object.values(ordered));
  };
  if (enrolled && enabled && configured) enroll();
  const bindKnownScope = scope => {
    assert.equal(used || authorized, false, 'scope binding must precede control and owner-intent registration');
    assert.deepEqual(Object.keys(scope).sort(), Object.keys(knownScope).sort());
    for (const key of ['contract', 'request_id', 'lead_id', 'event_id', 'fingerprint', 'admission_hash'])
      assert.equal(scope[key], knownScope[key], 'immutable receiver identity: ' + key);
    assert.match(scope.closure_id, /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
    assert.ok(Number.isSafeInteger(scope.closure_revision) && scope.closure_revision > 0);
    assert.match(scope.closure_hash, /^[a-f0-9]{64}$/);
    Object.assign(knownScope, copy(scope));
  };
  const authorizeIntent = record => {
    const p = record?.plan;
    assert.equal(record.contract, 'bsre-owner-no-mail-retirement-v1');
    assert.ok(Number.isSafeInteger(record.revision) && record.revision >= 1);
    assert.equal(p.actor, actor); assert.deepEqual(p.scope, knownScope);
    const unsigned = copy(p); delete unsigned.digest; assert.equal(hash(unsigned), p.digest);
    assert.ok(Number.isSafeInteger(record.approved_at) && record.approved_at >= p.created_at
      && record.approved_at <= r.state.clock && record.approved_at < p.expires_at);
    assert.equal(record.recovery_until, record.approved_at + 2592000);
    const value = {contract: 'bsre-owner-no-mail-authorization-v1', intent_digest: p.digest, actor,
      scope_hash: hash(knownScope), approved_at: record.approved_at, create_before: p.expires_at,
      recovery_until: record.recovery_until};
    ownerIntents.set(p.digest, value); authorized = true; return copy(value);
  };
  const fixtureAgeAcceptanceBeforeApproval = timestamp => {
    assert.equal(used || authorized, false, 'fixture age must be fixed before any control or approval');
    assert.ok(Number.isSafeInteger(timestamp) && timestamp > 0 && timestamp <= r.state.clock);
    r.rows[1][3] = new Date(timestamp * 1000).toISOString();
    return r.rows[1][3];
  };
  const properties = r.context.PropertiesService.getScriptProperties;
  r.context.PropertiesService.getScriptProperties = () => {
    const p = properties();
    return {...p, setProperty(key, value) {
      trace.push({event: 'property-write', key, held: r.state.held, row_state: r.rows[1][6]});
      return p.setProperty(key, value);
    }};
  };
  const sheets = r.context.SpreadsheetApp;
  r.context.SpreadsheetApp = {...sheets, openById(id) {
    const book = sheets.openById(id);
    return {...book, getSheetByName(name) {
      const actual = name === r.context.ACTUAL_NO_COPY_META_TAB;
      const sheet = book.getSheetByName(actual ? r.context.CLOSED_NO_COPY_META_TAB : name);
      if (!sheet) return sheet;
      return {...sheet, getRange(...args) {
        const range = sheet.getRange(...args);
        return {...range, setValues(values) {
          trace.push({event: actual ? 'metadata-write' : 'row-write', row: args[0], column: args[1],
            first: values[0]?.[0], held: r.state.held});
          return range.setValues(values);
        }};
      }};
    }};
  }};
  r.context.UrlFetchApp = {fetch(url, options) {
    assert.equal(url, AUTHORITY_URL);
    assert.equal(options.followRedirects, false); assert.equal(options.validateHttpsCertificates, true);
    assert.equal(options.method, 'post'); assert.equal(options.contentType, 'application/json');
    const outer = JSON.parse(options.payload);
    assert.deepEqual(Object.keys(outer).sort(), ['body', 'mac']);
    assert.equal(json(outer), options.payload);
    assert.equal(outer.mac, mac('bsre-receiver-authority-request-v1\n' + outer.body, AUTHORITY_SECRET));
    const request = JSON.parse(outer.body);
    assert.equal(json(request), outer.body);
    assert.equal(request.contract, 'bsre-receiver-authority-request-v1');
    assert.equal(request.namespace, NAMESPACE); assert.equal(request.source, SOURCE);
    assert.match(request.challenge, /^[a-f0-9]{64}$/);
    assert.equal(request.issued_at, r.state.clock);
    const operation = request.operation, args = request.arguments;
    calls.push({operation, arguments: copy(args), held: r.state.held, challenge: request.challenge});
    trace.push({event: 'authority', operation, held: r.state.held});
    assert.equal(r.state.held, operation !== 'attest_control_result', 'actual algebra owns ScriptLock; attestation follows release');
    let result;
    if (operation === 'runtime.current') result = current();
    else if (operation === 'mailbox.current_including_trash') {
      assert.deepEqual(args.scope, knownScope);
      result = {scope_hash: hash(knownScope), mailbox: 'marketing@blackswanrealestate.ae', result: 'ABSENT',
        complete: true, includes_trash: true, observed_at: r.state.clock, expires_at: r.state.clock + 300,
        evidence_reference: 'SYNTHETIC_MAILBOX_FIXTURE', evidence_hash: 'a'.repeat(64)};
    } else if (operation === 'owner_intent.current') {
      result = copy(ownerIntents.get(args.intent_digest) ?? null);
    } else if (operation === 'runtime.advance_retirement') {
      assert.deepEqual(args.before, floor());
      const localBefore = r.properties[r.context.ACTUAL_NO_COPY_FLOOR];
      remote.epoch = hash({previous: remote.epoch, revision: ++remote.revision});
      result = current();
      // The service changes only its independent state. The receiver must perform
      // the separately validated local property transition; no fake reaches in.
      assert.equal(r.properties[r.context.ACTUAL_NO_COPY_FLOOR], localBefore);
      if (faults.localFloor) r.state.storageFault = true;
    } else if (operation === 'attest_control_result') {
      assert.equal(args.actor, actor); assert.deepEqual(args.scope, knownScope);
      result = signEvidence({contract: 'bsre-actual-receiver-evidence-v1', service: 'receiver-retirement',
        operation: args.operation, scope: hash(args.scope),
        source: {receiver: SOURCE, namespace: NAMESPACE, admission: args.scope.admission_hash,
          generation: args.admission.generation}, actor: args.actor, challenge: args.challenge,
        request_hash: args.request_hash, issued_at: r.state.clock, expires_at: r.state.clock + 60,
        claims: {result: args.observed_result,
          intent_digest: args.observed_result?.owner_intent_digest || args.observed_result?.proof?.owner_intent_digest || null,
          current_history: true, receiver_only: true}});
    } else throw Error('UNEXPECTED_SYNTHETIC_AUTHORITY_OPERATION:' + operation);
    const response = {contract: 'bsre-receiver-authority-response-v1', operation, namespace: NAMESPACE, source: SOURCE,
      challenge: request.challenge, request_hash: hash(request), issued_at: r.state.clock,
      expires_at: r.state.clock + 60, result};
    if (mutateResponse) mutateResponse(response, request, calls);
    const body = json(response);
    const wire = {body, mac: mac('bsre-receiver-authority-response-v1\n' + body, AUTHORITY_SECRET)};
    return {getResponseCode: () => 200, getContentText: () => json(wire)};
  }, fetchAll() { throw Error('BULK_PROVIDER_API_FORBIDDEN_IN_FIXTURE'); }};
  const control = (operation = 'inspect', args = {scope: knownScope}, changes = {}) => {
    used = true;
    const env = {control_contract: 'bsre-receiver-control-v1', control_version: 1,
      timestamp: r.state.clock * 1000, challenge: hash('control-' + ++controlCount), operation, actor,
      body: json(args), ...changes};
    if (!Object.hasOwn(changes, 'signature')) env.signature = mac([env.control_contract, env.timestamp,
      env.challenge, env.operation, env.actor, env.body].join('\n'), TRANSPORT_SECRET);
    return r.postWire(json(env));
  };
  const postControl = raw => { used = true; return r.postWire(raw); };
  const identity = () => ({...copy(knownScope), accepted_at_utc: r.rows[1][3], payload_json: r.rows[1][5]});
  return {...r, receiver: r, control, postControl, postWire: postControl, calls, trace, knownScope, current, floor,
    remote, faults, enroll, bindKnownScope, authorizeIntent, ownerIntents, fixtureAgeAcceptanceBeforeApproval,
    identity, sourceHash: SOURCE, namespace: NAMESPACE, actor, signEvidence};
}


export {canonical, hash, json, copy, NOW, INTENT, ACTOR, TEST_PUBLIC, TEST_PUBLIC_KEY_HEX};
