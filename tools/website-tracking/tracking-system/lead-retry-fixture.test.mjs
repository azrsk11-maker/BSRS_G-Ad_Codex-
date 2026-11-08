import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';
import {buildReloadGuardCandidate} from './build-reload-guard-candidate.mjs';
import {buildReceiptClientCandidate} from './build-receipt-client-candidate.mjs';

const source = readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/lead.js', import.meta.url), 'utf8');
const origin = 'https://blackswanrealestate.ae';
const snapshot = {known: true, acknowledged: true, measurement_eligible: true,
  preferences: {analytics: true, ad_measurement: true}, decision_version: 'test-consent', notice_version: 'test-notice'};
const receipt = {accepted: true, lead_id: 'TEST_ONLY_LEAD', event_id: 'TEST_ONLY_EVENT', measurement: snapshot};

function page({uuid, store, reply, client = source, recovery}) {
  const handlers = new Map(), requests = [], ads = [], ga4 = [];
  const button = {dataset: {}, textContent: 'Submit'}, status = {dataset: {}};
  const form = {
    dataset: {role: 'tenant', landingPath: '/enquire/rent/'},
    elements: {namedItem: name => ({name: {value: 'Synthetic Fixture'}, contact_consent: {checked: true}})[name]},
    querySelector: selector => selector === '[data-bsre-status]' ? status : button,
    reportValidity: () => true, addEventListener: (type, listener) => handlers.set(type, listener),
  };
  const window = {
    location: new URL(origin + '/enquire/rent/'), crypto: {randomUUID: () => uuid},
    BSRELeadConfig: {endpoint: origin + '/wp-json/bsre/v1/lead', measurementEligible: true},
    BSREConsentBridge: {permissions: () => ({analytics: true, advertising: true}), measurementEligible: () => true,
      getSnapshot: () => snapshot, normalizeSnapshot: value => value},
    sessionStorage: {getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key)},
    setTimeout() {}, clearTimeout() {}, addEventListener() {}, dispatchEvent() {}, CustomEvent: class {},
    async fetch(url, request) {
      if (recovery && url.startsWith(origin + '/wp-json/bsre/v1/receipt-recovery/')) return recovery(url, request);
      assert.equal(url, window.BSRELeadConfig.endpoint);
      requests.push(request);
      return {ok: true, json: async () => reply(requests.length)};
    },
  };
  const document = {readyState: 'complete', referrer: '', querySelector: () => form,
    querySelectorAll: selector => selector === 'form[data-bsre-form]' ? [form] : []};
  runInNewContext(client, {window, document, URL, AbortController});
  window.BSREMeasurement.connect('ads', event => ads.push(event));
  window.BSREMeasurement.connect('ga4', event => ga4.push(event));
  return {submit: () => handlers.get('submit')({preventDefault() {}}), requests, ads, ga4, status};
}

test('lost acknowledgement retries the exact body and emits one accepted event per destination', async () => {
  const f = page({uuid: '00000000-0000-4000-8000-000000000001', store: new Map(), reply(attempt) {
    if (attempt === 1) throw new Error('Synthetic lost acknowledgement');
    return receipt;
  }});
  await f.submit();
  assert.equal(f.ads.length + f.ga4.length, 0);
  await f.submit();
  await f.submit();
  assert.equal(f.requests.length, 2);
  assert.equal(f.requests[0].body, f.requests[1].body);
  assert.equal(f.requests[1].headers['X-BSRE-Consent-Retry'], '1');
  assert.equal(f.ads.length, 1);
  assert.equal(f.ads[0].transaction_id, receipt.event_id);
  assert.equal(f.ga4.length, 1);
  assert.equal(f.ga4[0].event_name, 'generate_lead');
  assert.equal(Object.hasOwn(f.ga4[0].parameters, 'event_id'), false);
});

test('recovery client uses server UUID, then recovers a receipt without replaying intake or measurement', async () => {
  const client = buildReceiptClientCandidate(Buffer.from(source));
  const store = new Map();
  const uuid = '00000000-0000-4000-8000-000000000011';
  const proof = uuid + '.1800000000.' + 'a'.repeat(64);
  let linked = false;
  const recovery = async (url, request) => {
    assert.equal(request.method, 'POST');
    assert.equal(request.cache, 'no-store');
    const body = JSON.parse(request.body);
    if (url.endsWith('/proof')) {
      assert.deepEqual(body, {});
      return {ok: true, json: async () => ({request_id: uuid, proof})};
    }
    assert.deepEqual(body, {proof});
    return {ok: true, json: async () => linked ? {status: 'ACCEPTED', reference: receipt.lead_id} : {status: 'UNCONFIRMED'}};
  };
  const first = page({client, store, recovery, reply: () => { throw new Error('Synthetic lost acknowledgement'); }});
  await first.submit();
  assert.equal(JSON.parse(first.requests[0].body).request_id, uuid);
  assert.equal(store.get('BSRE_PENDING_ENQUIRY_V1'), proof);
  const reload = page({client, store, recovery, reply: () => assert.fail('Unexpected intake')});
  await reload.submit();
  assert.equal(reload.status.dataset.state, 'error');
  linked = true;
  await reload.submit();
  assert.equal(reload.status.dataset.state, 'success');
  assert.match(reload.status.textContent, /TEST_ONLY_LEAD/);
  assert.equal(reload.requests.length + reload.ads.length + reload.ga4.length, 0);
  assert.equal(store.has('BSRE_PENDING_ENQUIRY_V1'), false);
});

test('candidate holds a fresh submission after reload until the original attempt resolves', async () => {
  const client = buildReloadGuardCandidate(Buffer.from(source));
  const store = new Map();
  const first = page({client, uuid: '00000000-0000-4000-8000-000000000001', store, reply(attempt) {
    if (attempt === 1) throw new Error('Synthetic lost acknowledgement');
    return receipt;
  }});
  await first.submit();
  assert.equal(store.get('BSRE_PENDING_ENQUIRY_V1'), '1');
  const reloaded = page({client, uuid: '00000000-0000-4000-8000-000000000002', store, reply: () => receipt});
  await reloaded.submit();
  assert.equal(reloaded.requests.length, 0);
  assert.match(reloaded.status.textContent, /earlier enquiry.*unconfirmed/);
  await first.submit();
  assert.equal(first.requests[0].body, first.requests[1].body);
  assert.equal(first.ads.length, 1);
  assert.equal(store.has('BSRE_PENDING_ENQUIRY_V1'), false);
  await reloaded.submit();
  assert.equal(reloaded.requests.length, 1);
});

test('a known receipt is suppressed after same-session reload, but the form creates a new request UUID', async () => {
  const store = new Map();
  const first = page({uuid: '00000000-0000-4000-8000-000000000001', store, reply: () => receipt});
  await first.submit();
  assert.equal(first.ads.length, 1);
  // Return a deliberately repeated receipt to isolate the browser's receipt guard.
  const reloaded = page({uuid: '00000000-0000-4000-8000-000000000002', store, reply: () => receipt});
  await reloaded.submit();
  assert.equal(reloaded.status.dataset.state, 'success');
  assert.equal(reloaded.ads.length + reloaded.ga4.length, 0);
  assert.notEqual(JSON.parse(reloaded.requests[0].body).request_id, JSON.parse(first.requests[0].body).request_id);
});
