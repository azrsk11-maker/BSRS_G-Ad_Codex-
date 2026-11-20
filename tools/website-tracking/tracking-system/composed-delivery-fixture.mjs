// Trusted-source VM test fixture. DOM/HTTP/SDK are doubles; no vendor code or sockets.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash, createHmac, randomUUID} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {lab} from '../../staging-lab/receiver-lab.mjs';
import {buildContactCompatibleRetentionAdmissionClientCandidate} from './build-contact-compatible-client-candidate.mjs';
import {buildFrameDeliveryCandidate} from './build-frame-delivery-candidate.mjs';

const origin = 'https://blackswanrealestate.ae'; // Source-enforced origin, never fetched.
const plugin = new URL('../../staging-lab/fixtures/bsre-enquiries/', import.meta.url);
const baseline = readFileSync(new URL('assets/lead.js', plugin));
const prefix = String.raw`/^https:\/\/wa\.me\/`, suffix = String.raw`(?:\?|$)/.test(href)`;
const raw = baseline.toString('utf8'), from = raw.indexOf(prefix) + prefix.length;
const target = Buffer.from(raw.slice(0, from) + '999999999991' + raw.slice(raw.indexOf(suffix, from)));
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const client = buildContactCompatibleRetentionAdmissionClientCandidate(baseline, target,
  {baseline_sha256: sha(baseline), target_sha256: sha(target)}).candidate;
const parentSource = buildFrameDeliveryCandidate(readFileSync(new URL('assets/google-measurement.js', plugin)));
const childSource = readFileSync(new URL('assets/google-runtime.js', plugin), 'utf8');
const clone = value => JSON.parse(JSON.stringify(value));
const response = body => ({ok: true, status: 200, json: async () => clone(body)});
const handlersFor = () => {
  const handlers = new Map();
  return {add(name, fn) { if (!handlers.has(name)) handlers.set(name, []); handlers.get(name).push(fn); },
    async emit(name, value) { for (const fn of handlers.get(name) ?? []) await fn(value); }};
};

export const COMPOSED_SERVICES = Object.freeze({
  'off-plan': Object.freeze({role: 'off_plan', timeline: 'Within 1 month', authority: ''}),
  resale: Object.freeze({role: 'resale', timeline: 'Within 1 month', authority: ''}),
  rent: Object.freeze({role: 'tenant', timeline: 'Immediate / move now', authority: ''}),
  sell: Object.freeze({role: 'seller', timeline: 'As soon as practical', authority: 'owner'}),
  let: Object.freeze({role: 'landlord', timeline: 'Vacant / available to discuss now', authority: 'owner'}),
});

export function receiverState() {
  return {receiver: lab(), id: randomUUID(), requests: [], accepted: null, capture: null};
}

export function composedPage({state = null, store = new Map(), analytics = true, advertising = true,
  eligible = true, name = 'SYNTHETIC composition fixture', blank = false, proofMode = 'valid',
  loseAcknowledgement = false, postFault = '', denyLease = false, native = null, service = 'rent'} = {}) {
  assert.ok(Object.hasOwn(COMPOSED_SERVICES, service), 'Unknown composed service');
  const definition = COMPOSED_SERVICES[service], pagePath = '/enquire/' + service + '/';
  state ??= native ? {requests: [], accepted: null} : receiverState();
  let nativeSnapshot = native?.snapshot;
  if (native) {
    assert.ok(nativeSnapshot && native.publicConfig && typeof native.request === 'function' &&
      typeof native.runtimeGet === 'function' && typeof native.leasePost === 'function');
    analytics = nativeSnapshot.preferences.analytics; advertising = nativeSnapshot.preferences.ad_measurement;
    eligible = nativeSnapshot.measurement_eligible;
  }
  let now = Date.now(), nextTimer = 0, faultUsed = false, lose = loseAcknowledgement;
  const timers = new Map(), tasks = [], frames = [], bus = [], requests = [], attempts = [];
  const events = handlersFor(), formEvents = handlersFor();
  let flags = {analytics, advertising};
  const snapshot = () => native ? clone(nativeSnapshot) : ({known: true, acknowledged: true, measurement_eligible: eligible,
    preferences: {analytics: flags.analytics, ad_measurement: flags.advertising},
    decision_version: 'a'.repeat(32), notice_version: 'synthetic-notice'});
  const issue = Math.floor(now / 1000);
  const admission = native ? null : (state.admission ??= {version: 1, request_id: state.id, issued_at: issue, expires_at: issue + 900,
    session_hash: 'c'.repeat(64), generation: 'd'.repeat(64), audience: 'e'.repeat(64), signature: 'f'.repeat(64)});
  const proof = native ? null : (state.proof ??= `${state.id}.${issue}.${'a'.repeat(64)}`);
  class Clock extends Date { constructor(...args) { super(...(args.length ? args : [now])); } static now() { return now; } }
  const timer = (callback, delay, repeat = false, owner = null) => {
    const id = ++nextTimer; timers.set(id, {callback, due: now + delay, repeat: repeat ? delay : 0, owner}); return id;
  };
  const button = {dataset: {}, textContent: 'Submit'}, status = {dataset: {}};
  const values = {name: blank ? '' : name, phone: '+971500000000', email: 'fixture@example.invalid', country: 'UAE',
    area: 'Synthetic', budget: 'To discuss', timeline: definition.timeline, funding: 'To discuss',
    property_type: 'Apartment', property_details: 'SYNTHETIC NOT INVENTORY', authority: definition.authority};
  const form = {dataset: {role: definition.role, landingPath: pagePath, campaign: 'SYNTHETIC'},
    elements: {namedItem: key => key === 'contact_consent' ? {checked: !blank} : key === 'marketing_consent' ? {checked: false} : {value: values[key] ?? ''}},
    querySelector: selector => selector === '[data-bsre-status]' ? status : button,
    reportValidity: () => !blank, addEventListener: (name, fn) => formEvents.add(name, fn)};

  // Explicit simulated WP acknowledgement boundary: forward the ORIGINAL body in signed wire-v1.
  // Admission is checked for exact test-header transport only, not authenticated by WordPress/PHP.
  async function http(url, options) {
    requests.push({url, options: {...options}});
    assert.equal(options.method, 'POST');
    if (native) {
      assert.ok(['/wp-json/bsre/v1/lead', '/wp-json/bsre/v1/receipt-recovery/proof',
        '/wp-json/bsre/v1/receipt-recovery/status'].some(path => url === origin + path), 'Unknown native HTTP request');
      const actual = await native.request({url, method: options.method, body: options.body, headers: options.headers});
      if (url.endsWith('/proof') && actual.status === 200) {
        state.id = actual.body.request_id; state.admission = actual.body.admission; state.proof = actual.body.proof;
      }
      if (url.endsWith('/lead')) {
        state.requests.push({body: options.body, admission: options.headers['X-BSRE-Admission']});
        if (actual.body.accepted === true) state.accepted = actual.body;
        if (lose) { lose = false; throw new Error('Synthetic acknowledgement loss after actual PHP response'); }
      }
      return {ok: actual.status >= 200 && actual.status < 300, status: actual.status, json: async () => clone(actual.body)};
    }
    if (url === origin + '/wp-json/bsre/v1/receipt-recovery/proof') {
      assert.equal(options.body, '{}');
      return response({request_id: state.id, proof,
        admission: proofMode === 'missing' ? null : proofMode === 'malformed' ? {...admission, expires_at: 0} : admission});
    }
    if (url === origin + '/wp-json/bsre/v1/receipt-recovery/status') {
      assert.deepEqual(JSON.parse(options.body), {proof});
      return response(state.accepted ? {status: 'ACCEPTED', reference: state.accepted.lead_id} : {status: 'UNCONFIRMED'});
    }
    assert.equal(url, origin + '/wp-json/bsre/v1/lead', 'Unknown HTTP request; purpose-envelope flattening prohibited');
    const payload = JSON.parse(options.body);
    assert.equal(Object.hasOwn(payload, 'wire_body'), false);
    assert.equal(payload.request_id, state.id);
    assert.equal(Object.hasOwn(payload, 'admission'), false);
    assert.equal(options.headers['X-BSRE-Admission'], JSON.stringify(admission));
    state.requests.push({body: options.body, admission: options.headers['X-BSRE-Admission']});
    const timestamp = String(Date.now()), body = options.body;
    const signature = createHmac('sha256', state.receiver.properties.HMAC_SECRET).update(`v1\n${timestamp}\n${body}`).digest('hex');
    const receipt = state.receiver.postWire(JSON.stringify({version: 1, body, timestamp, signature}));
    assert.equal(receipt.accepted, true, `Receiver rejected exact client wire: ${receipt.code}`);
    if (!state.accepted) { state.accepted = receipt; state.capture = clone(snapshot()); }
    assert.equal(receipt.event_id, state.accepted.event_id);
    if (lose) { lose = false; throw new Error('Synthetic browser acknowledgement loss after receiver acceptance'); }
    return response({...receipt, measurement: state.capture});
  }

  const window = {location: new URL(origin + pagePath), crypto: {randomUUID},
    BSRELeadConfig: {endpoint: origin + '/wp-json/bsre/v1/lead', retentionAdmissionRequired: true,
      measurementEligible: eligible, purposeAttributionEndpoint: '', ...(native ? {csrfToken: native.csrf} : {})},
    BSREConsentBridge: {permissions: () => ({...flags}), measurementEligible: () => eligible,
      getSnapshot: snapshot, normalizeSnapshot: value => value},
    sessionStorage: {getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value), removeItem: key => store.delete(key)},
    addEventListener: (name, fn) => events.add(name, fn),
    dispatchEvent: event => { bus.push(event); }, CustomEvent: class { constructor(type, options) { this.type = type; this.detail = options.detail; } },
    setTimeout: (fn, delay) => timer(fn, delay), clearTimeout: id => timers.delete(id), fetch: http,
  };
  const document = {readyState: 'complete', referrer: '', cookie: '', querySelector: () => form,
    querySelectorAll: selector => selector === 'form[data-bsre-form]' ? [form] : [],
    body: {appendChild(frame) { frames.push(frame); }},
    createElement(kind) {
      assert.equal(kind, 'iframe');
      const frame = {attributes: {}, scripts: [], removed: false, initialized: false,
        setAttribute(name, value) { this.attributes[name] = value; }, remove() { this.removed = true; }};
      const childEvents = handlersFor();
      const proxy = {get BSREMeasurement() { return window.BSREMeasurement; },
        postMessage(data, target) {
          assert.equal(target, origin);
          tasks.push(() => frame.removed ? undefined : events.emit('message', {origin, source: child, data: structuredClone(data)}));
        }};
      const child = {parent: proxy, location: {origin, replace: value => { assert.equal(value, 'about:blank'); frame.retired = true; }},
        addEventListener: (name, fn) => childEvents.add(name, fn),
        setTimeout: (fn, delay) => timer(fn, delay, false, frame), clearTimeout: id => timers.delete(id),
        setInterval: (fn, delay) => timer(fn, delay, true, frame), clearInterval: id => timers.delete(id),
        postMessage(data, target) {
          assert.equal(target, origin);
          if (data.type === 'bsre-runtime-init') frame.init = structuredClone(data);
          const isEvent = data.type === 'bsre-runtime-event';
          if (isEvent) attempts.push(structuredClone(data));
          const fault = isEvent && !faultUsed ? postFault : '';
          if (fault) faultUsed = true;
          if (fault !== 'before') tasks.push(() => frame.removed ? undefined : childEvents.emit('message', {origin, source: proxy, data: structuredClone(data)}));
          if (fault) throw new Error('Synthetic uncertain parent post ' + fault);
        },
        async fetch(url, options) {
          assert.equal(url, origin + '/wp-json/bsre/v1/measurement/status', 'Unknown child HTTP request');
          assert.equal(options.method, 'POST');
          if (native) {
            const actual = await native.leasePost({url, body: options.body, method: options.method});
            return {ok: actual.status >= 200 && actual.status < 300, json: async () => clone(actual.body)};
          }
          return response({...frame.config, ok: !denyLease});
        },
      };
      frame.contentWindow = child;
      frame.start = async () => {
        assert.equal(new URL(frame.src).origin, origin);
        assert.equal(new URL(frame.src).pathname, '/wp-json/bsre/v1/measurement/runtime');
        const purpose = new URL(frame.src).searchParams.get('purpose'), analytics = purpose === 'analytics';
        // Synthetic REST HTML/config, not execution of measurement-runtime.php or browser headers/CSP.
        if (native) {
          const actual = await native.runtimeGet(frame.src);
          if (actual.status !== 200) { frame.deniedStatus = actual.status; frame.removed = true; return; }
          assert.equal(typeof actual.body, 'string'); assert.ok(actual.body.length < 65536);
          const match = actual.body.match(/<script id="bsre-runtime-config" type="application\/json">([^<]+)<\/script><script src="([^"]+)" defer><\/script>/);
          assert.ok(match, 'Actual PHP runtime must provide inert config and one guarded asset');
          const asset = new URL(match[2]);
          assert.equal(asset.origin, origin); assert.equal(asset.pathname, '/wp-content/plugins/bsre-enquiries/assets/google-runtime.js');
          assert.equal(asset.searchParams.size, 1); assert.ok(asset.searchParams.has('ver'));
          frame.asset = asset.href; frame.config = JSON.parse(match[1]);
          assert.equal(frame.config.origin, origin); assert.equal(frame.config.purpose, purpose);
        } else frame.config = {version: '1.0.0', enabled: true, purpose, origin, gtm_id: 'GTM-TESTONLY',
          measurement_id: analytics ? 'G-TESTONLY' : '', ads_send_to: analytics ? '' : 'AW-999999999/TEST_ONLY',
          cookie_prefix: analytics ? 'bsre_enq_analytics' : 'bsre_enq_ads', status_endpoint: origin + '/wp-json/bsre/v1/measurement/status',
          config_version: 'gm1-' + 'a'.repeat(32), lease_seconds: 30, lease_token: `ml1|${Math.floor(now / 1000) + 60}|${'b'.repeat(64)}`};
        const doc = {getElementById: () => ({textContent: JSON.stringify(frame.config)}), createElement: () => ({}),
          head: {appendChild(script) {
            const url = new URL(script.src);
            assert.equal(url.origin, 'https://www.googletagmanager.com'); assert.equal(url.searchParams.size, 1);
            const id = url.searchParams.get('id');
            assert.ok(url.pathname === '/gtm.js' && id === frame.config.gtm_id || url.pathname === '/gtag/js' &&
              id === (analytics ? frame.config.measurement_id : frame.config.ads_send_to.split('/')[0]));
            frame.scripts.push(script); // Never fetch/execute the script; no synthetic provider dedup.
          }}};
        runInNewContext(childSource, {window: child, document: doc, URL, AbortController, Date: Clock}, {timeout: 1000});
        frame.initialized = true;
      };
      return frame;
    }};
  runInNewContext(client, {window, document, URL, AbortController, Date: Clock}, {timeout: 1000});
  window.BSREGoogleConfig = native ? native.publicConfig : {enabled: true, analytics_enabled: true, advertising_enabled: true,
    config_version: 'gm1-' + 'a'.repeat(32), runtime_endpoint: origin + '/wp-json/bsre/v1/measurement/runtime'};
  runInNewContext(parentSource, {window, document, URL, Date: Clock}, {timeout: 1000});

  async function pump(activate = false) {
    let processed = 0;
    for (let turn = 0; turn < 100; turn++) {
      for (const frame of frames) if (!frame.removed && !frame.initialized) await frame.start();
      while (tasks.length) {
        assert.ok(++processed <= 1000, 'Bounded message pump task limit');
        await tasks.shift()();
      }
      let changed = false;
      if (activate) for (const frame of frames) if (!frame.removed && frame.scripts.length === 1 && !frame.activationTried) {
        frame.activationTried = true; frame.contentWindow.BSREGoogleRuntime.activate();
        frame.scripts[1]?.onload?.(); changed = true;
      }
      if (!tasks.length && !changed) return;
    }
    throw new Error('Bounded message pump did not settle');
  }
  const commands = () => frames.flatMap(frame => (frame.contentWindow.dataLayer ?? [])
    .filter(entry => entry[0] === 'event').map(entry => ({purpose: frame.config.purpose, args: clone(Array.from(entry))})));
  return {state, store, frames, requests, status, button, bus, attempts, get admission() { return state.admission; }, window,
    retire: () => events.emit('pagehide', {}),
    submit: () => formEvents.emit('submit', {preventDefault() {}}), pump,
    commands, conversions: () => commands().filter(row => row.args[1] === 'conversion'),
    async choice(next) {
      await events.emit('bsre:consent-will-change', {detail: next});
      if (native) {
        assert.equal(typeof native.changeConsent, 'function');
        nativeSnapshot = await native.changeConsent(next);
        flags = {analytics: nativeSnapshot.preferences.analytics, advertising: nativeSnapshot.preferences.ad_measurement};
      } else flags = {...next};
      await events.emit('bsre:consent-changed', {detail: {reason: 'choice'}});
    },
    async advance(milliseconds) {
      now += milliseconds;
      for (const [id, item] of [...timers]) if (item.due <= now) {
        if (item.repeat) item.due = now + item.repeat; else timers.delete(id);
        if (!item.owner?.removed) await item.callback();
      }
    },
    replayInCurrentChild(payload) {
      const frame = [...frames].reverse().find(frame => !frame.removed && frame.config?.purpose === 'advertising');
      assert.ok(frame?.init);
      frame.contentWindow.postMessage({type: 'bsre-runtime-event', version: '1.0.0', purpose: 'advertising',
        nonce: frame.init.nonce, sequence: 1000, payload}, origin);
    },
    requestUnknown: () => http(origin + '/unexpected', {method: 'POST', body: '{}'}),
  };
}
