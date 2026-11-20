import assert from 'node:assert/strict';
import {createHmac} from 'node:crypto';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {lab} from '../../staging-lab/receiver-lab.mjs';
import {createClientPage} from '../../staging-lab/client-page.mjs';
import {buildRetentionAdmissionClient, buildRetentionAdmissionIntake, buildRetentionAdmissionReceiver, buildRetentionAdmissionStore} from './build-retention-admission-candidate.mjs';

const source = readFileSync(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs', import.meta.url));
const plugin = new URL('../../staging-lab/fixtures/bsre-enquiries/', import.meta.url);
const secret = 'synthetic-secret-never-production-0000';
const generation = 'a'.repeat(64), audience = 'b'.repeat(64);
const now = Math.floor(Date.now() / 1000);
function claim(id, issued = now) {
  const proof = {version: 1, request_id: id, issued_at: issued, expires_at: issued + 900,
    session_hash: 'c'.repeat(64), generation, audience};
  proof.signature = createHmac('sha256', secret).update(['bsre-retention-admission-v1', id, issued,
    proof.expires_at, proof.session_hash, generation, audience].join('\n')).digest('hex');
  return proof;
}
function receiver() {
  const instance = lab(buildRetentionAdmissionReceiver(source));
  Object.assign(instance.properties, {RETENTION_ADMISSION_REQUIRED: 'true',
    RETENTION_ADMISSION_GENERATION: generation, RETENTION_ADMISSION_AUDIENCE: audience,
    RETENTION_ADMISSION_ACTIVATED_AT: String(now - 2000)});
  return instance;
}

test('unknown receiver rows require current audience-bound admission, preserving wire and 26 columns', () => {
  const r = receiver(), p = r.payload();
  assert.equal(r.post(p).code, 'ADMISSION_REQUIRED');
  const accepted = r.post(p, {admission: claim(p.request_id)});
  assert.equal(accepted.accepted, true);
  assert.equal(r.rows.length, 2);
  assert.equal(r.rows[1].length, 26);
  assert.equal(JSON.parse(r.rows[1][5]).request_id, p.request_id);
  assert.equal(Object.hasOwn(JSON.parse(r.rows[1][5]), 'admission'), false);
});

test('known identical receipts survive expiry while unknown purged UUIDs cannot resurrect', () => {
  const r = receiver(), p = r.payload(), proof = claim(p.request_id);
  const accepted = r.post(p, {admission: proof});
  assert.equal(accepted.accepted, true);
  r.context.Date = class extends Date {static now() { return (now + 900) * 1000; }};
  const currentEnvelope = {timestamp: String((now + 900) * 1000), admission: proof};
  assert.deepEqual(r.post(p, currentEnvelope), accepted);
  assert.equal(r.post({...p, area: 'Changed'}, currentEnvelope).code, 'REQUEST_ID_CONFLICT');
  r.rows.splice(1, 1); // Synthetic fixture simulates an approved completed purge.
  assert.equal(r.post(p, currentEnvelope).code, 'ADMISSION_REQUIRED');
  assert.equal(r.rows.length, 1);
  assert.equal(r.mail.length, 0);
});

test('proof substitutions, altered fields, stale generations and wrong audiences cannot insert', () => {
  const r = receiver(), p = r.payload(), original = claim(p.request_id);
  const variants = [null, {...original, extra: true}, {...original, signature: '0'.repeat(64)},
    {...original, request_id: r.payload().request_id}, {...original, expires_at: original.expires_at + 1},
    {...original, issued_at: String(original.issued_at)}, {...original, generation: 'd'.repeat(64)},
    {...original, audience: 'e'.repeat(64)}, {...original, session_hash: 'f'.repeat(64)}];
  for (const admission of variants) assert.equal(r.post(p, {admission}).code, 'ADMISSION_REQUIRED');
  assert.equal(r.rows.length, 1);
});

test('legacy mode is preserved, enforced mode closes unknown legacy inserts but retains known receipts', () => {
  const r = receiver();
  r.properties.RETENTION_ADMISSION_REQUIRED = 'false';
  const p = r.payload(), accepted = r.post(p);
  assert.equal(accepted.accepted, true);
  r.properties.RETENTION_ADMISSION_REQUIRED = 'true';
  assert.deepEqual(r.post(p), accepted);
  assert.equal(r.post(r.payload()).code, 'ADMISSION_REQUIRED');
  r.properties.RETENTION_ADMISSION_GENERATION = '';
  assert.equal(r.post(r.payload(), {admission: claim(p.request_id)}).code, 'NOT_CONFIGURED');
});

test('source-derived WP store checks admission inside transaction before INSERT and keeps envelope body', () => {
  const store = buildRetentionAdmissionStore(readFileSync(new URL('includes/consent-store.php', plugin)));
  assert.ok(store.indexOf('assert_capture($this->db, $capture)') < store.indexOf('INSERT IGNORE INTO {$this->captures}'));
  assert.match(store, /admissionContract/);
  const intake = buildRetentionAdmissionIntake(readFileSync(new URL('bsre-enquiries.php', plugin)), readFileSync(new URL('includes/consent.php', plugin)));
  assert.match(intake, /use function BSRE\\RetentionAdmission\\envelope/);
  assert.match(intake, /ADMISSION_UNCONFIRMED/);
  assert.match(intake, /\$outgoing = wp_json_encode\(envelope\(\$raw,/);
});

test('actual client preserves admission proof across unchanged retries and never adds it to wire body', async () => {
  const built = buildRetentionAdmissionClient(readFileSync(new URL('assets/lead.js', plugin)));
  const id = '11111111-1111-4111-8111-111111111111';
  const proof = claim(id), requests = [];
  let attempts = 0;
  const client = 'window.BSRELeadConfig.retentionAdmissionRequired = true;\n' + built;
  const page = createClientPage({client, origin: 'https://blackswanrealestate.ae', slug: 'rent', role: 'tenant',
    timeline: 'Immediate / move now', csrf: 'SYNTHETIC', store: new Map(), request: async request => {
      if (request.url.endsWith('/proof')) return {status: 200, body: {request_id: id, proof: id + '.' + now + '.' + 'a'.repeat(64), admission: proof}};
      requests.push(request); attempts++;
      return attempts === 1 ? {status: 503, body: {accepted: false, retryable: true}} : {status: 200, body: {accepted: true, lead_id: 'BSRE-synthetic', event_id: 'evt_synthetic'}};
    }});
  await page.submit(); await page.submit();
  assert.equal(requests.length, 2);
  assert.equal(requests[0].body, requests[1].body);
  assert.equal(requests[0].headers['X-BSRE-Admission'], JSON.stringify(proof));
  assert.equal(requests[0].headers['X-BSRE-Admission'], requests[1].headers['X-BSRE-Admission']);
  assert.equal(Object.hasOwn(JSON.parse(requests[0].body), 'admission'), false);
});

test('required client admission cannot fall back to an unproved UUID', async () => {
  const client = 'window.BSRELeadConfig.retentionAdmissionRequired = true;\n' + buildRetentionAdmissionClient(readFileSync(new URL('assets/lead.js', plugin)));
  let intake = 0;
  const page = createClientPage({client, origin: 'https://blackswanrealestate.ae', slug: 'rent', role: 'tenant',
    timeline: 'Immediate / move now', csrf: 'SYNTHETIC', store: new Map(), request: async request => {
      if (request.url.endsWith('/proof')) return {status: 503, body: {}};
      intake++; return {status: 200, body: {accepted: true}};
    }});
  await page.submit();
  assert.equal(intake, 0);
  assert.equal(page.status.dataset.state, 'error');
});
