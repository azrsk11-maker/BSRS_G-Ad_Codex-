import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';
import {buildFrameDeliveryCandidate} from './build-frame-delivery-candidate.mjs';

const original = readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/google-measurement.js', import.meta.url));
const candidate = buildFrameDeliveryCandidate(original);
const runtime = readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/google-runtime.js', import.meta.url), 'utf8');
const origin = 'https://blackswanrealestate.ae';
const handshakeNonce = '00000000-0000-4000-8000-000000000001';
const receipt = Object.freeze({event_name: 'accepted_enquiry', transaction_id: 'TEST_ONLY_RECEIPT'});

function fixture(source, purpose = 'advertising') {
  const listeners = new Map(), posts = [], frames = [], send = new Map(), timers = new Map();
  let now = 0, timer = 0;
  const window = {
    location: new URL(origin + '/enquire/rent/'), crypto: {randomUUID: () => handshakeNonce},
    BSREGoogleConfig: {enabled: true, advertising_enabled: purpose === 'advertising', analytics_enabled: purpose === 'analytics',
      config_version: 'gm1-' + 'a'.repeat(32), runtime_endpoint: origin + '/wp-json/bsre/v1/measurement/runtime'},
    BSREMeasurement: {canLoad: () => true, connect: (key, callback) => send.set(key, callback)},
    BSREConsentBridge: {}, BSRELead: {advertisingContext: () => ({})},
    addEventListener: (name, callback) => listeners.set(name, callback),
    setTimeout: callback => { timers.set(++timer, callback); return timer; },
    clearTimeout: id => timers.delete(id),
  };
  const document = {referrer: '', cookie: '', body: {appendChild: frame => frames.push(frame)},
    createElement: () => ({contentWindow: {postMessage: message => posts.push(message)}, setAttribute() {}, remove() {}})};
  runInNewContext(source, {window, document, URL, Date: {now: () => now}});
  const message = (type, frame = frames.at(-1), nonce = handshakeNonce) => listeners.get('message')({origin,
    source: frame.contentWindow, data: {type, purpose, version: '1.0.0', nonce}});
  return {frames, message, timers, post: send.get(purpose === 'analytics' ? 'ga4' : 'ads'),
    events: () => posts.filter(item => item.type === 'bsre-runtime-event'),
    withdraw: () => listeners.get('bsre:consent-will-change')({detail: {}}),
    recreate: () => listeners.get('bsre:consent-changed')(),
    expire: () => { now = 30000; }};
}

test('preserved orchestrator drops an accepted receipt before the iframe is active', () => {
  const f = fixture(original.toString('utf8'));
  assert.equal(f.post(receipt), false);
  f.message('bsre-runtime-ready');
  f.message('bsre-runtime-active');
  assert.equal(f.events().length, 0);
});

test('candidate hands a pending receipt to the preserved child, which emits one native command', async () => {
  const f = fixture(candidate);
  const frame = f.frames[0];
  const scripts = [];
  const config = {
    version: '1.0.0', enabled: true, purpose: 'advertising', origin,
    gtm_id: 'GTM-TESTONLY', measurement_id: '', ads_send_to: 'AW-999999999/TEST_ONLY',
    cookie_prefix: 'bsre_enq_ads', status_endpoint: origin + '/wp-json/bsre/v1/measurement/status',
    config_version: 'gm1-' + 'a'.repeat(32), lease_seconds: 30,
    lease_token: `ml1|${Math.floor(Date.now() / 1000) + 60}|${'b'.repeat(64)}`,
  };
  const messages = [];
  let receive;
  const parent = {
    BSREMeasurement: {canLoad: () => true},
    postMessage(data, target) {
      assert.equal(target, origin);
      messages.push(() => f.message(data.type, frame, data.nonce));
    },
  };
  const window = {
    parent, location: {origin, replace: () => assert.fail('Unexpected frame retirement')},
    setTimeout() {}, clearTimeout() {}, setInterval() {}, clearInterval() {},
    addEventListener(type, fn) { assert.equal(type, 'message'); receive = fn; },
    async fetch(url) {
      assert.equal(url, config.status_endpoint);
      return {ok: true, json: async () => ({...config, ok: true})};
    },
  };
  frame.contentWindow.postMessage = (data, target) => {
    assert.equal(target, origin);
    messages.push(() => receive({origin, source: parent, data: structuredClone(data)}));
  };
  const document = {
    getElementById: () => ({textContent: JSON.stringify(config)}),
    createElement: () => ({}), head: {appendChild: script => scripts.push(script)},
  };
  const drain = async () => { while (messages.length) await messages.shift()(); };
  runInNewContext(runtime, {window, document, URL, AbortController});
  const payload = {...receipt, page_path: '/enquire/rent/', role: 'tenant'};
  assert.equal(f.post(payload), true);
  await drain();
  assert.equal(scripts.length, 1);
  assert.equal(window.BSREGoogleRuntime.activate(), true);
  scripts[1].onload();
  await drain();
  // Replay after activation to exercise the real child's receipt deduplication.
  assert.equal(f.post(payload), true);
  await drain();
  const conversions = window.dataLayer.filter(entry => entry[0] === 'event' && entry[1] === 'conversion');
  assert.equal(conversions.length, 1);
  assert.equal(conversions[0][2].send_to, config.ads_send_to);
  assert.equal(conversions[0][2].transaction_id, receipt.transaction_id);
});

test('candidate posts queued receipt once after the correct frame handshake', () => {
  const f = fixture(candidate);
  assert.equal(f.post(receipt), true);
  f.message('bsre-runtime-active');
  f.message('bsre-runtime-ready');
  f.message('bsre-runtime-active', undefined, 'wrong');
  assert.equal(f.events().length, 0);
  f.message('bsre-runtime-active');
  f.message('bsre-runtime-active');
  assert.equal(f.events().length, 1);
  assert.equal(f.events()[0].payload, receipt);
  assert.equal(f.timers.size, 0);
});

test('withdrawal prevents replay into a replacement frame and expired events never post', () => {
  const f = fixture(candidate);
  f.post(receipt);
  f.withdraw();
  assert.equal(f.timers.size, 0);
  f.recreate();
  assert.equal(f.frames.length, 2);
  f.post(receipt);
  f.expire();
  f.message('bsre-runtime-ready');
  f.message('bsre-runtime-active');
  assert.equal(f.events().length, 0);
  assert.equal(f.timers.size, 0);
});

test('analytics queues accepted leads only and caps pending records', () => {
  const f = fixture(candidate, 'analytics');
  assert.equal(f.post({event_name: 'form_start'}), false);
  for (let i = 0; i < 32; i++) assert.equal(f.post({event_name: 'generate_lead'}), true);
  assert.equal(f.post({event_name: 'generate_lead'}), false);
  f.message('bsre-runtime-ready');
  f.message('bsre-runtime-active');
  assert.equal(f.events().length, 32);
});
