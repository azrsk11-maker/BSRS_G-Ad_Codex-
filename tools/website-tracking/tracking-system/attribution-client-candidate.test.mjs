import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {test} from 'node:test';
import {buildAttributionClientCandidate} from './build-attribution-client-candidate.mjs';

const original = readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/lead.js', import.meta.url));
const candidate = buildAttributionClientCandidate(original);
const origin = 'https://blackswanrealestate.ae';
const analyticsKey = 'BSRE_ATTRIBUTION_V1';
const advertisingKey = 'BSRE_AD_ATTRIBUTION_V1';

// All browser objects and replies are local doubles. No provider is contacted.
function page({store = new Map(), path = '/enquire/rent/', referrer = '', analytics = true,
  advertising = false, eligible = true, known = true, formPresent = true,
  blockedStorage = false, client = candidate, reply, name = 'Synthetic attribution fixture', now = Date.now(),
  secureId = randomUUID} = {}) {
  const handlers = new Map();
  const windowHandlers = new Map();
  const requests = [];
  const measurements = [];
  const button = {dataset: {}, textContent: 'Submit'};
  const status = {dataset: {}};
  let flags = {analytics, advertising};
  let currentKnown = known;
  const values = {name, phone: '+971500000000', email: 'fixture@example.invalid', country: 'UAE',
    area: 'Synthetic area', budget: 'To discuss', timeline: 'Immediate / move now',
    funding: 'To discuss', property_type: 'Apartment', property_details: '', authority: ''};
  const form = {
    dataset: {role: 'tenant', landingPath: '/enquire/rent/'},
    elements: {namedItem(key) {
      if (key === 'contact_consent') return {checked: true};
      if (key === 'marketing_consent') return {checked: false};
      return {value: values[key] || ''};
    }},
    querySelector: selector => selector === '[data-bsre-status]' ? status : button,
    reportValidity: () => true,
    addEventListener: (kind, handler) => handlers.set(kind, handler),
  };
  const window = {
    location: new URL(origin + path), crypto: {randomUUID: secureId},
    BSRELeadConfig: {endpoint: origin + '/wp-json/bsre/v1/lead', measurementEligible: eligible},
    BSREConsentBridge: {
      permissions: () => currentKnown ? flags : {analytics: false, advertising: false},
      measurementEligible: () => eligible,
      getSnapshot: () => ({known: currentKnown, acknowledged: currentKnown,
        measurement_eligible: eligible, preferences: {analytics: flags.analytics, ad_measurement: flags.advertising},
        decision_version: 'synthetic-choice', notice_version: 'synthetic-notice'}),
      normalizeSnapshot: value => value,
    },
    sessionStorage: {
      getItem(key) { if (blockedStorage) throw new Error('Blocked'); return store.get(key) ?? null; },
      setItem(key, value) { if (blockedStorage) throw new Error('Blocked'); store.set(key, value); },
      removeItem(key) { if (blockedStorage) throw new Error('Blocked'); store.delete(key); },
    },
    setTimeout() {}, clearTimeout() {}, dispatchEvent() {}, CustomEvent: class {},
    addEventListener: (kind, handler) => windowHandlers.set(kind, handler),
    async fetch(url, request) {
      if (url.endsWith('/receipt-recovery/proof')) return {ok: false};
      requests.push(request);
      if (reply) return reply(request, requests.length);
      return {ok: true, json: async () => ({accepted: true, lead_id: 'SYNTHETIC_LEAD', event_id: 'SYNTHETIC_EVENT'})};
    },
  };
  const document = {readyState: 'complete', referrer,
    querySelector: () => formPresent ? form : null,
    querySelectorAll: selector => formPresent && selector === 'form[data-bsre-form]' ? [form] : []};
  class Clock extends Date { static now() { return now; } }
  runInNewContext(client, {window, document, URL, AbortController, Date: Clock});
  window.BSREMeasurement.connect('ads', event => measurements.push(event));
  window.BSREMeasurement.connect('ga4', event => measurements.push(event));
  return {
    requests, measurements, store,
    submit: () => handlers.get('submit')({preventDefault() {}}),
    advanceTime(value) { now = value; },
    choice(next, reason = 'choice') {
      flags = next;
      currentKnown = reason !== 'expired' && reason !== 'unknown';
      // Mirrors the captured bridge's owned-storage clearing before its event.
      if (!currentKnown || !flags.analytics) store.delete(analyticsKey);
      if (!currentKnown || !flags.advertising) store.delete(advertisingKey);
      windowHandlers.get('bsre:consent-changed')({detail: {reason,
        refused: {analytics: !flags.analytics, advertising: !flags.advertising}}});
    },
  };
}

function stored(store, key = analyticsKey) {
  return JSON.parse(store.get(key));
}

function publicAttribution(value) {
  return Object.fromEntries(Object.entries(value).map(([key, touch]) => {
    if (!touch) return [key, null];
    const {capture_id, ...publicTouch} = touch;
    return [key, publicTouch];
  }));
}

test('candidate is source-pinned and reproduces the original internal-navigation defect', () => {
  assert.throws(() => buildAttributionClientCandidate(Buffer.from('altered')), /SOURCE_CHANGED/);
  const store = new Map();
  page({store, client: original.toString(), formPresent: false, path: '/enquire/?utm_source=SYNTHETIC_A'});
  page({store, client: original.toString(), path: '/enquire/rent/'});
  assert.equal(stored(store).last.landing_page, origin + '/enquire/rent/');
  assert.deepEqual(stored(store).last.parameters, {});
});

test('analytics acquisition survives no-referrer hub to service and actual intake carries current page separately', async () => {
  const store = new Map();
  page({store, formPresent: false, path: '/enquire/?utm_source=SYNTHETIC_A&utm_campaign=SYNTHETIC_CAMPAIGN'});
  const before = stored(store);
  const service = page({store});
  await service.submit();
  const payload = JSON.parse(service.requests[0].body);
  assert.deepEqual(payload.attribution, publicAttribution(before));
  assert.equal(payload.landing_page, origin + '/enquire/rent/');
  assert.equal(payload.attribution.last.landing_page, origin + '/enquire/');
  assert.equal(payload.attribution.last.parameters.utm_source, 'SYNTHETIC_A');
  assert.equal(Object.hasOwn(payload.attribution.last.parameters, 'gclid'), false);
  assert.equal(service.measurements.length, 0);
});

test('same-origin navigation does not overwrite analytics acquisition even with internal UTM hints', () => {
  const store = new Map();
  page({store, formPresent: false, path: '/enquire/?utm_source=SYNTHETIC_A'});
  const before = stored(store);
  page({store, referrer: origin + '/enquire/', path: '/enquire/rent/?utm_source=INTERNAL_HINT'});
  assert.deepEqual(stored(store), before);
});

test('a later external acquisition updates latest while preserving first', async () => {
  const store = new Map();
  page({store, formPresent: false, path: '/enquire/?utm_source=SYNTHETIC_A'});
  const first = stored(store).first;
  page({store, formPresent: false, referrer: 'https://search.example.invalid/results', path: '/enquire/?utm_source=SYNTHETIC_B'});
  const latest = stored(store).last;
  const service = page({store, referrer: origin + '/enquire/'});
  await service.submit();
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution, publicAttribution({first, last: latest}));
  assert.equal(latest.parameters.utm_source, 'SYNTHETIC_B');
});

test('queryless external referral remains a new observed analytics touch', () => {
  const store = new Map();
  page({store, formPresent: false, path: '/enquire/?utm_source=SYNTHETIC_A'});
  page({store, referrer: 'https://referral.example.invalid/path'});
  assert.equal(stored(store).last.referrer, 'https://referral.example.invalid/path');
  assert.equal(stored(store).last.landing_page, origin + '/enquire/rent/');
  assert.deepEqual(stored(store).last.parameters, {});
});

test('advertising-only permission retains exact click bytes and excludes analytics hints', async () => {
  const store = new Map();
  page({store, formPresent: false, analytics: false, advertising: true,
    path: '/enquire/?utm_source=ANALYTICS_DENIED&gclid=Synthetic-Click_Ab9'});
  const before = stored(store, advertisingKey);
  const service = page({store, analytics: false, advertising: true});
  await service.submit();
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution, publicAttribution(before));
  assert.equal(store.has(analyticsKey), false);
  assert.equal(before.last.parameters.gclid, 'Synthetic-Click_Ab9');
  assert.equal(Object.hasOwn(before.last.parameters, 'utm_source'), false);
});

test('both purposes survive hub to service with independent permitted parameters', async () => {
  const store = new Map();
  page({store, formPresent: false, advertising: true,
    path: '/enquire/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_Ab9'});
  const service = page({store, advertising: true});
  await service.submit();
  const payload = JSON.parse(service.requests[0].body);
  assert.equal(payload.attribution.last.parameters.utm_source, 'SYNTHETIC_A');
  assert.equal(payload.attribution.last.parameters.gclid, 'Synthetic-Click_Ab9');
  assert.equal(payload.attribution.last.landing_page, origin + '/enquire/');
  assert.equal(payload.landing_page, origin + '/enquire/rent/');
  assert.equal(stored(store).first.capture_id, stored(store, advertisingKey).first.capture_id);
  assert.match(stored(store).first.capture_id, /^[0-9a-f-]{36}$/);
  assert.equal(service.requests[0].body.includes('capture_id'), false);
});

test('a later advertising click cannot inherit older analytics UTM or referrer metadata', async () => {
  const store = new Map();
  page({store, formPresent: false, advertising: true, now: 1000,
    referrer: 'https://source.example.invalid/first',
    path: '/enquire/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_A'});
  const first = stored(store).first;
  page({store, formPresent: false, advertising: true, now: 2000,
    path: '/enquire/?gclid=Synthetic-Click_B'});
  const service = page({store, advertising: true, now: 3000});
  await service.submit();
  const result = JSON.parse(service.requests[0].body).attribution;
  assert.equal(result.first.parameters.utm_source, 'SYNTHETIC_A');
  assert.equal(result.first.parameters.gclid, 'Synthetic-Click_A');
  assert.equal(result.last.parameters.gclid, 'Synthetic-Click_B');
  assert.equal(Object.hasOwn(result.last.parameters, 'utm_source'), false);
  assert.equal(result.last.referrer, '');
  assert.equal(result.last.timestamp, 2000);
  assert.deepEqual(stored(store).last, first);
});

test('a later analytics-only acquisition cannot be merged into an older advertising click', async () => {
  const store = new Map();
  page({store, formPresent: false, advertising: true, now: 1000,
    path: '/enquire/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_A'});
  page({store, formPresent: false, advertising: true, now: 2000,
    referrer: 'https://source.example.invalid/second', path: '/enquire/?utm_source=SYNTHETIC_B'});
  const service = page({store, advertising: true, now: 3000});
  await service.submit();
  const latest = JSON.parse(service.requests[0].body).attribution.last;
  assert.deepEqual(latest.parameters, {gclid: 'Synthetic-Click_A'});
  assert.equal(latest.referrer, '');
  assert.equal(latest.timestamp, 1000);
  assert.equal(stored(store).last.parameters.utm_source, 'SYNTHETIC_B');
});

test('different page captures at the same timestamp and path do not merge their purposes', async () => {
  const store = new Map();
  page({store, formPresent: false, advertising: true, now: 1000,
    path: '/enquire/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_A'});
  page({store, formPresent: false, advertising: true, now: 1000,
    path: '/enquire/?gclid=Synthetic-Click_B'});
  assert.notEqual(stored(store).last.capture_id, stored(store, advertisingKey).last.capture_id);
  const service = page({store, advertising: true, now: 2000});
  await service.submit();
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution.last.parameters, {gclid: 'Synthetic-Click_B'});
});

test('legacy slots without private correlation never imply matching captures', async () => {
  const touch = {landing_page: origin + '/enquire/', referrer: '', timestamp: 1000, parameters: {utm_source: 'SYNTHETIC_A'}};
  const adTouch = {...touch, parameters: {gclid: 'Synthetic-Click_A'}};
  const store = new Map([[analyticsKey, JSON.stringify({first: touch, last: touch})],
    [advertisingKey, JSON.stringify({first: adTouch, last: adTouch})]]);
  const service = page({store, advertising: true, now: 2000});
  await service.submit();
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution.last.parameters, {gclid: 'Synthetic-Click_A'});
});

test('capture correlation failure leaves intake available and prevents mixed metadata', async () => {
  const store = new Map();
  page({store, formPresent: false, advertising: true,
    path: '/enquire/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_A',
    secureId() { throw new Error('Synthetic random source unavailable'); }});
  const service = page({store, advertising: true});
  await service.submit();
  assert.equal(service.requests.length, 1);
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution.last.parameters, {gclid: 'Synthetic-Click_A'});
});

test('newly permitted purpose captures use the grant-time clock, not page initialization time', async () => {
  const store = new Map();
  const service = page({store, now: 1000, known: false, analytics: false, advertising: false,
    path: '/enquire/rent/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_A'});
  assert.equal(store.size, 0);
  service.advanceTime(5000);
  service.choice({analytics: true, advertising: true});
  await service.submit();
  const latest = JSON.parse(service.requests[0].body).attribution.last;
  assert.equal(stored(store).last.timestamp, 5000);
  assert.equal(stored(store, advertisingKey).last.timestamp, 5000);
  assert.equal(latest.timestamp, 5000);
  assert.equal(latest.parameters.utm_source, 'SYNTHETIC_A');
  assert.equal(latest.parameters.gclid, 'Synthetic-Click_A');
});

test('withdrawal and same-page regrant do not resurrect acquisition', async () => {
  const store = new Map();
  const service = page({store, advertising: true, path: '/enquire/rent/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_Ab9'});
  service.choice({analytics: false, advertising: false});
  assert.equal(store.has(analyticsKey), false);
  assert.equal(store.has(advertisingKey), false);
  service.choice({analytics: true, advertising: true});
  await service.submit();
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution, {first: null, last: null});
  assert.deepEqual(stored(store), {first: null, last: null});
  assert.deepEqual(stored(store, advertisingKey), {first: null, last: null});
  page({store, formPresent: false, advertising: true, path: '/enquire/?utm_source=SYNTHETIC_B&gclid=Synthetic-Click_New'});
  assert.equal(stored(store).first.parameters.utm_source, 'SYNTHETIC_B');
  assert.equal(stored(store, advertisingKey).first.parameters.gclid, 'Synthetic-Click_New');
});

test('unknown, expired, refused, QA and admin contexts do not attach acquisition', async () => {
  for (const options of [
    {known: false}, {analytics: false, advertising: false}, {eligible: false},
    {name: 'TEST synthetic QA'},
  ]) {
    const service = page({path: '/enquire/rent/?utm_source=SYNTHETIC_A&gclid=Synthetic-Click_Ab9', advertising: true, ...options});
    await service.submit();
    assert.deepEqual(JSON.parse(service.requests[0].body).attribution, {first: null, last: null});
    assert.equal(service.measurements.length, 0);
  }
  const expired = page({path: '/enquire/rent/?utm_source=SYNTHETIC_A'});
  expired.choice({analytics: false, advertising: false}, 'expired');
  await expired.submit();
  assert.deepEqual(JSON.parse(expired.requests[0].body).attribution, {first: null, last: null});
});

test('blocked storage preserves intake but cannot recover earlier-page attribution', async () => {
  const store = new Map();
  page({store, blockedStorage: true, formPresent: false, path: '/enquire/?utm_source=SYNTHETIC_A'});
  const service = page({store, blockedStorage: true});
  await service.submit();
  assert.equal(service.requests.length, 1);
  assert.deepEqual(JSON.parse(service.requests[0].body).attribution.last.parameters, {});
  assert.equal(store.size, 0);
});

test('attribution candidate preserves the immutable request body across an uncertain retry', async () => {
  const service = page({path: '/enquire/rent/?utm_source=SYNTHETIC_A', reply(request, count) {
    if (count === 1) throw new Error('Synthetic uncertain receipt');
    return {ok: true, json: async () => ({accepted: true, lead_id: 'SYNTHETIC_LEAD', event_id: 'SYNTHETIC_EVENT'})};
  }});
  await service.submit();
  await service.submit();
  assert.equal(service.requests.length, 2);
  assert.equal(service.requests[0].body, service.requests[1].body);
  assert.equal(service.requests[1].headers['X-BSRE-Consent-Retry'], '1');
});
