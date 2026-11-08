import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';

// Execute the preserved WordPress runtime with synthetic IDs and no network.
const source = readFileSync(new URL('../../staging-lab/fixtures/bsre-enquiries/assets/google-runtime.js', import.meta.url), 'utf8');
const origin = 'https://blackswanrealestate.ae';
const nonce = '00000000-0000-4000-8000-000000000001';
const pagePath = '/enquire/rent/';
const destination = 'AW-999999999/TEST_ONLY';
const receipt = {event_name: 'accepted_enquiry', page_path: pagePath, role: 'tenant', transaction_id: 'TEST_ONLY_RECEIPT'};

function fixture(purpose = 'advertising', leaseAllowed = true) {
  const analytics = purpose === 'analytics';
  const config = {
    version: '1.0.0', enabled: true, purpose, origin, gtm_id: 'GTM-TESTONLY',
    measurement_id: analytics ? 'G-TESTONLY' : '', ads_send_to: analytics ? '' : destination,
    cookie_prefix: analytics ? 'bsre_enq_analytics' : 'bsre_enq_ads',
    status_endpoint: origin + '/wp-json/bsre/v1/measurement/status',
    config_version: 'gm1-' + 'a'.repeat(32), lease_seconds: 30,
    lease_token: `ml1|${Math.floor(Date.now() / 1000) + 60}|${'b'.repeat(64)}`,
  };
  const scripts = [], navigation = [];
  let allowed = true, receive;
  const parent = {BSREMeasurement: {canLoad: () => allowed}, postMessage() {}};
  const window = {
    parent, location: {origin, replace: url => navigation.push(url)},
    setTimeout() {}, clearTimeout() {}, setInterval() {}, clearInterval() {},
    addEventListener(type, fn) { assert.equal(type, 'message'); receive = fn; },
    async fetch(url) {
      assert.equal(url, config.status_endpoint);
      return {ok: leaseAllowed, json: async () => ({...config, ok: leaseAllowed})};
    },
  };
  const document = {
    getElementById: () => ({textContent: JSON.stringify(config)}),
    createElement: () => ({}), head: {appendChild: script => scripts.push(script)},
  };
  runInNewContext(source, {window, document, URL, AbortController});
  const send = (data, source = parent) => receive({origin, source, data: {purpose, version: config.version, nonce, ...data}});
  return {
    scripts, navigation, window,
    deny: () => { allowed = false; },
    init: (source) => send({type: 'bsre-runtime-init', config_version: config.config_version, page_path: pagePath, page_view: true}, source),
    event: (sequence, payload) => send({type: 'bsre-runtime-event', sequence, payload}),
    events: () => (window.dataLayer ?? []).filter(entry => entry[0] === 'event').map(entry => [entry[1], entry[2]]),
  };
}

test('preserved runtime emits one native Ads command for a repeated receipt in one frame', async () => {
  const f = fixture();
  await f.init({});
  assert.equal(f.scripts.length, 0);
  await f.init();
  assert.equal(f.scripts.length, 1);
  assert.equal(f.window.BSREGoogleRuntime.activate(), true);
  assert.equal(f.window.BSREGoogleRuntime.activate(), false);
  f.scripts[1].onload();
  await f.event(1, {...receipt, email: 'test@example.invalid'});
  await f.event(2, receipt);
  await f.event(3, receipt);
  assert.equal(f.events().length, 1);
  const [[name, payload]] = f.events();
  assert.equal(name, 'conversion');
  assert.equal(payload.send_to, destination);
  assert.equal(payload.transaction_id, receipt.transaction_id);
  assert.equal(payload.page_location, origin + pagePath);
  assert.equal(payload.page_referrer, '');
  assert.equal(Object.hasOwn(payload, 'email'), false);
});

test('lease denial and withdrawal stop Google script insertion or later commands', async () => {
  const denied = fixture('advertising', false);
  await denied.init();
  assert.equal(denied.scripts.length, 0);
  assert.deepEqual(denied.navigation, ['about:blank']);

  const active = fixture();
  await active.init();
  active.window.BSREGoogleRuntime.activate();
  active.scripts[1].onload();
  active.deny();
  await active.event(1, receipt);
  assert.equal(active.events().length, 0);
  assert.deepEqual(active.navigation, ['about:blank']);
});

test('analytics frame emits one explicit page view and rejects private receipt fields', async () => {
  const f = fixture('analytics');
  await f.init();
  f.window.BSREGoogleRuntime.activate();
  f.scripts[1].onload();
  const parameters = {schema_version: '1.0.0', site_scope: 'BSRE_REAL_ESTATE', page_path: pagePath, role: 'tenant'};
  await f.event(1, {event_name: 'generate_lead', parameters: {...parameters, gclid: 'TEST_ONLY_CLICK'}});
  await f.event(2, {event_name: 'generate_lead', parameters});
  const events = f.events();
  assert.equal(events.length, 2);
  assert.equal(events[0][0], 'page_view');
  assert.equal(events[1][0], 'generate_lead');
  assert.equal(events[1][1].send_to, 'G-TESTONLY');
  assert.equal(events[1][1].send_page_view, false);
  assert.equal(Object.hasOwn(events[1][1], 'gclid'), false);
});
