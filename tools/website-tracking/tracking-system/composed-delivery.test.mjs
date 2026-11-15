import {test} from 'node:test';
import assert from 'node:assert/strict';
import {composedPage} from './composed-delivery-fixture.mjs';

test('full admission/contact client connects actual parent and child, retaining receiver identity and privacy', async () => {
  const f = composedPage(); await f.pump(true); await f.submit(); await f.pump(true);
  assert.equal(f.window.BSREMeasurement.connect('ads', () => assert.fail('Collector replacement')), false);
  assert.equal(f.state.receiver.rows.length, 2); assert.equal(f.state.requests.length, 1);
  assert.equal(f.state.requests[0].admission, JSON.stringify(f.admission));
  const wire = JSON.parse(f.state.requests[0].body);
  assert.equal(wire.request_id, f.state.id); assert.equal(Object.hasOwn(wire, 'admission'), false);
  assert.equal(f.conversions().length, 1);
  const payload = f.conversions()[0].args[2];
  assert.equal(payload.transaction_id, f.state.accepted.event_id);
  assert.equal(payload.transaction_id, f.state.receiver.rows[1][2]);
  assert.equal(f.state.receiver.rows[1].length, 26);
  assert.equal(payload.send_to, 'AW-999999999/TEST_ONLY');
  assert.equal(f.bus.filter(e => e.type === 'bsre:measurement' && e.detail.event === 'bsre_lead_accepted').length, 1);
  assert.equal(f.attempts.filter(e => e.payload.event_name === 'accepted_enquiry').length, 1);
  assert.equal(f.commands().filter(e => e.args[1] === 'generate_lead').length, 1);
  const sent = JSON.stringify(f.commands());
  for (const privateValue of ['fixture@example.invalid', '+971500000000', 'SYNTHETIC composition fixture',
    f.state.id, f.state.proof, f.admission.signature, 'decision_version', 'notice_version']) assert.equal(sent.includes(privateValue), false);
  assert.equal(Object.hasOwn(payload, 'value'), false); // Approved platform fallback is not a fabricated client value.
  assert.ok(f.frames.every(frame => frame.attributes.sandbox === 'allow-scripts allow-same-origin'));
});

test('purpose-specific permission combinations preserve intake without adding a second native route', async () => {
  for (const [analytics, advertising] of [[true, false], [false, true], [false, false]]) {
    const f = composedPage({analytics, advertising}); await f.pump(true); await f.submit(); await f.pump(true);
    assert.equal(f.state.receiver.rows.length, 2);
    assert.equal(f.conversions().length, Number(advertising));
    assert.equal(f.commands().filter(e => e.args[1] === 'generate_lead').length, Number(analytics));
  }
});

test('receipt before activation passes through real client connection and bounded candidate queue once', async () => {
  const f = composedPage(); await f.submit(); await f.pump(false);
  assert.equal(f.conversions().length, 0);
  await f.pump(true); assert.equal(f.conversions().length, 1);
  await f.pump(true); await f.submit(); await f.pump(true);
  assert.equal(f.conversions().length, 1); assert.equal(f.state.requests.length, 1);
});

test('lost browser acknowledgement retries exact wire/admission and forwards stable receiver event only once', async () => {
  const f = composedPage({loseAcknowledgement: true}); await f.pump(true);
  await f.submit(); await f.pump(true);
  assert.equal(f.conversions().length, 0); assert.equal(f.state.receiver.rows.length, 2);
  await f.submit(); await f.pump(true); await f.submit(); await f.pump(true);
  assert.equal(f.state.requests.length, 2);
  assert.equal(f.state.requests[0].body, f.state.requests[1].body);
  assert.equal(f.state.requests[0].admission, f.state.requests[1].admission);
  assert.equal(f.state.receiver.rows.length, 2); assert.equal(f.conversions().length, 1);
  assert.equal(f.conversions()[0].args[2].transaction_id, f.state.accepted.event_id);
});

test('blank reload recovers pending reference with no intake or measurement replay', async () => {
  const first = composedPage({loseAcknowledgement: true}); await first.submit();
  const reload = composedPage({state: first.state, store: first.store, blank: true});
  await reload.pump(true); await reload.submit(); await reload.pump(true);
  assert.equal(reload.status.dataset.state, 'success');
  assert.ok(reload.status.textContent.includes(first.state.accepted.lead_id));
  assert.equal(first.state.requests.length, 1); assert.equal(reload.conversions().length, 0);
  assert.equal(reload.commands().filter(e => e.args[1] === 'generate_lead').length, 0);
  assert.equal(reload.store.has('BSRE_PENDING_ENQUIRY_V1'), false);
});

test('missing/malformed required admission cannot submit and unknown HTTP cannot be flattened into wire', async () => {
  for (const proofMode of ['missing', 'malformed']) {
    const f = composedPage({proofMode}); await f.submit(); await f.pump(true);
    assert.equal(f.state.requests.length, 0); assert.equal(f.state.receiver.rows.length, 1);
    assert.equal(f.conversions().length, 0); assert.equal(f.status.dataset.state, 'error');
  }
  const f = composedPage(); await assert.rejects(f.requestUnknown(), /Unknown HTTP request/);
});

test('uncertain parent posting is consumed without blind retry before or after scheduling', async () => {
  for (const postFault of ['before', 'after']) {
    const f = composedPage({analytics: false, postFault}); await f.pump(true);
    await f.submit(); await f.pump(true); await f.submit(); await f.pump(true);
    assert.equal(f.attempts.length, 1); assert.equal(f.state.requests.length, 1);
    assert.equal(f.conversions().length, postFault === 'after' ? 1 : 0);
    // A recorded command is only an attempt. There is deliberately no provider acknowledgement mock.
  }
});

test('withdrawal retires queued receipts; a later grant cannot resurrect prior measurement', async () => {
  const f = composedPage(); await f.submit();
  await f.choice({analytics: false, advertising: false}); await f.pump(true);
  await f.choice({analytics: true, advertising: true}); await f.pump(true); await f.submit(); await f.pump(true);
  assert.equal(f.conversions().length, 0); assert.equal(f.state.requests.length, 1);
});

test('never-active SDK, denied lease and queue expiry cannot be reported as a native command', async () => {
  const never = composedPage(); await never.submit(); await never.pump(false);
  assert.equal(never.conversions().length, 0);
  const denied = composedPage({denyLease: true}); await denied.pump(true); await denied.submit(); await denied.pump(true);
  assert.equal(denied.conversions().length, 0); assert.ok(denied.frames.every(f => f.removed));
  const expired = composedPage(); await expired.submit(); await expired.advance(30000); await expired.pump(true);
  assert.equal(expired.conversions().length, 0);
});

test('TEST and ineligible QA forms retain synthetic intake without optional SDK loads', async () => {
  for (const options of [{name: 'TEST synthetic composition'}, {eligible: false}]) {
    const f = composedPage(options); await f.pump(true); await f.submit(); await f.pump(true);
    assert.equal(f.state.receiver.rows.length, 2); assert.equal(f.frames.length, 0); assert.equal(f.commands().length, 0);
  }
});

test('fresh child can attempt the same transaction again: explicit per-realm dedup limit, not provider proof', async () => {
  const f = composedPage({analytics: false}); await f.pump(true); await f.submit(); await f.pump(true);
  const payload = f.attempts[0].payload;
  assert.equal(f.conversions().length, 1);
  await f.choice({analytics: false, advertising: false}); await f.choice({analytics: false, advertising: true}); await f.pump(true);
  assert.equal(f.conversions().length, 1); // Actual client did not replay.
  f.replayInCurrentChild(payload); await f.pump(true);
  assert.equal(f.conversions().length, 2); // Adversarial parent injection into fresh child, not an ordinary form journey.
  assert.equal(f.conversions()[0].args[2].transaction_id, f.conversions()[1].args[2].transaction_id);
  assert.equal(f.state.receiver.rows.length, 2);
});

// Async interface unit checks only: these replies are NOT PHP execution evidence.
function asyncRestDouble(badAsset = false) {
  const reference = composedPage(), origin = 'https://blackswanrealestate.ae', leases = [];
  const version = 'gm1-' + 'a'.repeat(32), token = `ml1|${Math.floor(Date.now() / 1000) + 60}|${'b'.repeat(64)}`;
  return {leases, snapshot: reference.window.BSREConsentBridge.getSnapshot(), csrf: 'SYNTHETIC_CSRF',
    publicConfig: {enabled: true, analytics_enabled: true, advertising_enabled: true, config_version: version,
      runtime_endpoint: origin + '/wp-json/bsre/v1/measurement/runtime'},
    async request(data) {
      const r = await reference.window.fetch(data.url, {method: data.method, body: data.body, headers: data.headers});
      return {status: r.status, body: await r.json()};
    },
    async runtimeGet(url) {
      await Promise.resolve(); const purpose = new URL(url).searchParams.get('purpose'), analytics = purpose === 'analytics';
      const config = {version: '1.0.0', enabled: true, purpose, origin, gtm_id: 'GTM-ASYNCTEST',
        measurement_id: analytics ? 'G-ASYNCTEST' : '', ads_send_to: analytics ? '' : 'AW-18394393537/FICTIONAL_ASYNC_TEST',
        cookie_prefix: analytics ? 'bsre_enq_analytics' : 'bsre_enq_ads', config_version: version,
        status_endpoint: origin + '/wp-json/bsre/v1/measurement/status', lease_seconds: 30, lease_token: token};
      return {status: 200, body: `<script id="bsre-runtime-config" type="application/json">${JSON.stringify(config)}</script><script src="${badAsset ? 'https://example.invalid' : origin}/wp-content/plugins/bsre-enquiries/assets/google-runtime.js?ver=0.2.12" defer></script>`};
    },
    async leasePost(data) {
      await Promise.resolve(); const sent = JSON.parse(data.body); leases.push(sent);
      return {status: 200, body: {ok: true, enabled: true, version: '1.0.0', purpose: sent.purpose,
        config_version: version, lease_seconds: 30, lease_token: token}};
    },
  };
}

test('async REST/config/lease injection supports returned public prefix plus fictional label without vendor fetch', async () => {
  const native = asyncRestDouble(), f = composedPage({native});
  await f.pump(false); await f.submit(); await f.pump(true);
  assert.equal(native.leases.length, 2);
  assert.equal(f.conversions().length, 1);
  assert.equal(f.conversions()[0].args[2].send_to, 'AW-18394393537/FICTIONAL_ASYNC_TEST');
  assert.equal(f.conversions()[0].args[2].transaction_id, f.state.accepted.event_id);
  assert.ok(f.frames.every(frame => frame.asset.endsWith('google-runtime.js?ver=0.2.12')));
});

test('async returned runtime with foreign script origin is rejected before child execution', async () => {
  const f = composedPage({native: asyncRestDouble(true)});
  await assert.rejects(f.pump(true)); assert.equal(f.commands().length, 0);
});
