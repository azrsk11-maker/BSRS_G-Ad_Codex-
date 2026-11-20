// Local stdio driver only; actual PHP replies feed trusted-source VM contexts, never a provider.
import assert from 'node:assert/strict';
import {createInterface} from 'node:readline';
import {composedPage, COMPOSED_SERVICES} from './website-tracking/tracking-system/composed-delivery-fixture.mjs';

// Examine every raw entry before filtering/dedup. Never mutate the command sink or print its values.
function assertNativeCommandPrivacy(f, receipt, setup, observed) {
  const need = (ok, code) => { if (!ok) throw new Error(code); };
  const exact = (object, keys) => object && typeof object === 'object' && !Array.isArray(object)
    && Object.keys(object).sort().join(',') === [...keys].sort().join(',');
  const service = setup.service ?? 'rent';
  need(Object.hasOwn(COMPOSED_SERVICES, service), 'RAW_UNKNOWN_SERVICE');
  const role = COMPOSED_SERVICES[service].role, path = '/enquire/' + service + '/';
  const origin = 'https://blackswanrealestate.ae', page = origin + path;
  const secrets = new Set([f.state.id, receipt.lead_id, f.state.proof, ...observed.decisions, ...observed.leases]);
  for (const key of ['signature', 'session_hash', 'generation', 'audience']) secrets.add(f.admission?.[key]);
  for (const request of f.state.requests) {
    secrets.add(request.body); secrets.add(request.admission);
    const body = JSON.parse(request.body);
    for (const key of ['name', 'email', 'phone']) secrets.add(body[key]);
  }
  secrets.add(setup.snapshot.decision_version);
  const scanned = [];
  for (const frame of f.frames) {
    secrets.add(frame.config?.lease_token);
    const privacy = {cookie_expires: 0, cookie_update: false, cookie_domain: 'none', cookie_prefix: frame.config.cookie_prefix,
      cookie_flags: 'SameSite=Strict;Secure', allow_google_signals: false, allow_ad_personalization_signals: false,
      send_page_view: false, page_location: page, page_referrer: '', page_title: 'Black Swan Real Estate Enquiries'};
    for (const raw of frame.contentWindow.dataLayer ?? []) {
      if (!Array.isArray(raw) && Object.prototype.toString.call(raw) !== '[object Arguments]') {
        need(exact(raw, ['gtm.start', 'event']) && raw.event === 'gtm.js' && Number.isSafeInteger(raw['gtm.start']), 'RAW_BOOTSTRAP_SHAPE');
        scanned.push(raw); continue;
      }
      const args = JSON.parse(JSON.stringify(Array.from(raw))), command = args[0];
      if (command === 'event' || command === 'config') {
        need(args.length === 3, 'RAW_COMMAND_ARITY');
        const p = args[2], expected = {...privacy};
        if (command === 'config') {
          need(args[1] === (frame.config.purpose === 'analytics' ? frame.config.measurement_id : frame.config.ads_send_to.split('/')[0]), 'RAW_CONFIG_DESTINATION');
        } else if (args[1] === 'conversion') {
          need(frame.config.purpose === 'advertising', 'RAW_ADS_PURPOSE');
          expected.send_to = frame.config.ads_send_to; expected.transaction_id = receipt.event_id;
        } else {
          need(frame.config.purpose === 'analytics' && ['page_view', 'generate_lead'].includes(args[1]), 'RAW_ANALYTICS_EVENT');
          expected.send_to = frame.config.measurement_id;
          if (args[1] === 'generate_lead') Object.assign(expected, {schema_version: '1.0.0', site_scope: 'BSRE_REAL_ESTATE', page_path: path, role});
        }
        need(exact(p, Object.keys(expected)) && Object.entries(expected).every(([key, value]) => p[key] === value), 'RAW_PARAMETER_ALLOWLIST');
        // The actual Ads correlation ID is required, even if related to the request ID.
        // Mask only that validated field in a private scan copy; the real sink is untouched.
        if (command === 'event' && args[1] === 'conversion') p.transaction_id = '[ALLOWED_NATIVE_TRANSACTION_ID]';
      } else if (command === 'consent') {
        const keys = ['analytics_storage', 'ad_storage', 'ad_user_data', 'ad_personalization'];
        need(args.length === 3 && ['default', 'update'].includes(args[1]) && exact(args[2], keys)
          && keys.every(key => ['granted', 'denied'].includes(args[2][key])) && args[2].ad_personalization === 'denied', 'RAW_CONSENT_SHAPE');
      } else if (command === 'set') {
        const allowed = {ads_data_redaction: true, url_passthrough: false, allow_ad_personalization_signals: false, allow_google_signals: false};
        need(args.length === 3 && Object.hasOwn(allowed, args[1]) && args[2] === allowed[args[1]], 'RAW_SET_SHAPE');
      } else if (command === 'js') {
        need(args.length === 2 && typeof args[1] === 'string' && /^\d{4}-\d{2}-\d{2}T[0-9:.]+Z$/.test(args[1]), 'RAW_CLOCK_SHAPE');
      } else need(false, 'RAW_UNKNOWN_COMMAND');
      scanned.push(args);
    }
  }
  const serialized = JSON.stringify(scanned);
  for (const value of secrets) if (typeof value === 'string' && value.length >= 6)
    need(!serialized.includes(value), 'RAW_PRIVATE_VALUE_LEAK');
}

const started = performance.now(), input = createInterface({input: process.stdin, crlfDelay: Infinity});
let waiting;
input.on('line', line => {
  const pending = waiting; waiting = null;
  if (!pending) throw new Error('Unexpected composed pipe reply');
  clearTimeout(pending.timeout);
  try { pending.resolve(JSON.parse(line)); } catch (error) { pending.reject(error); }
});
input.on('close', () => { if (waiting) { clearTimeout(waiting.timeout); waiting.reject(new Error('Composed pipe EOF')); waiting = null; } });
function command(value) {
  return new Promise((resolve, reject) => {
    assert.ok(!waiting, 'Only one composed pipe request may be outstanding');
    waiting = {resolve, reject, timeout: setTimeout(() => { waiting = null; reject(new Error('Composed pipe timeout')); }, 10000)};
    process.stdout.write(JSON.stringify(value) + '\n');
  });
}
let phase = 'session', caseKey = 'original';
try {
  const setup = await command({op: 'session'});
  const observed = {decisions: new Set([setup.snapshot.decision_version]), leases: new Set()};
  const f = composedPage({loseAcknowledgement: true, native: {...setup,
    request: data => command({op: 'request', ...data}),
    runtimeGet: url => command({op: 'runtime_get', url}),
    leasePost: async data => {
      observed.leases.add(JSON.parse(data.body).lease_token);
      const result = await command({op: 'lease_post', ...data}); observed.leases.add(result.body.lease_token); return result;
    },
    changeConsent: async flags => {
      assert.equal(flags.analytics, flags.advertising);
      const snapshot = (await command({op: 'consent', allowed: flags.analytics})).snapshot;
      observed.decisions.add(snapshot.decision_version); return snapshot;
    },
  }});
  phase = 'composed-client';
  await f.pump(false); await f.submit(); await f.pump(false);
  assert.equal(f.conversions().length, 0);
  await f.submit(); await f.pump(true); await f.submit(); await f.pump(true);
  const receipt = await command({op: 'inspect', request_id: f.state.id});
  assert.equal(f.state.requests.length, 2);
  assert.equal(f.state.requests[0].body, f.state.requests[1].body);
  assert.equal(f.state.requests[0].admission, f.state.requests[1].admission);
  assert.equal(f.conversions().length, 1);
  assert.equal(f.conversions()[0].args[2].transaction_id, receipt.event_id);
  assert.equal(f.conversions()[0].args[2].send_to, 'AW-18394393537/SYNTHETIC_COMPOSED_NOT_REAL');
  assert.equal(f.commands().filter(e => e.args[1] === 'generate_lead').length, 1);
  assert.ok(f.frames.every(frame => frame.asset && frame.config.gtm_id === 'GTM-NW8WXKRF'));
  assertNativeCommandPrivacy(f, receipt, setup, observed);
  phase = 'consent-and-guards';
  await f.choice({analytics: false, advertising: false}); await f.pump(true);
  await f.choice({analytics: true, advertising: true}); await f.pump(true);
  assert.equal(f.conversions().length, 1);
  assertNativeCommandPrivacy(f, receipt, setup, observed);
  const guards = await command({op: 'guards'}); assert.equal(guards.ok, true);
  await f.retire();
  phase = 'role-purpose-matrix';
  for (const service of Object.keys(COMPOSED_SERVICES)) {
    for (const permission of ['both', 'analytics', 'advertising', 'denied', 'default']) {
      caseKey = service + ':' + permission;
      const setup = await command({op: 'matrix_session', service, permission});
      const observed = {decisions: new Set([setup.snapshot.decision_version]), leases: new Set()};
      const scenario = composedPage({service, loseAcknowledgement: true, native: {...setup,
        request: data => command({op: 'request', ...data}),
        runtimeGet: url => command({op: 'runtime_get', url}),
        leasePost: async data => {
          observed.leases.add(JSON.parse(data.body).lease_token);
          const reply = await command({op: 'lease_post', ...data}); observed.leases.add(reply.body.lease_token); return reply;
        },
      }});
      await scenario.pump(false); await scenario.submit(); await scenario.pump(false);
      assert.equal(scenario.conversions().length, 0);
      await scenario.submit(); await scenario.pump(true); await scenario.submit(); await scenario.pump(true);
      const inspected = await command({op: 'inspect', request_id: scenario.state.id});
      const expectedAds = Number(setup.snapshot.known && setup.snapshot.preferences.ad_measurement);
      const expectedAnalytics = Number(setup.snapshot.known && setup.snapshot.preferences.analytics);
      assert.equal(scenario.state.requests.length, 2);
      assert.equal(scenario.state.requests[0].body, scenario.state.requests[1].body);
      assert.equal(scenario.state.requests[0].admission, scenario.state.requests[1].admission);
      assert.equal(scenario.conversions().length, expectedAds);
      const analyticsCommands = scenario.commands().filter(e => e.args[1] === 'generate_lead').length;
      assert.equal(analyticsCommands, expectedAnalytics);
      assert.equal(inspected.event_id, scenario.state.accepted.event_id);
      if (expectedAds) assert.equal(scenario.conversions()[0].args[2].transaction_id, inspected.event_id);
      assertNativeCommandPrivacy(scenario, inspected, setup, observed);
      const rawEntries = scenario.frames.reduce((n, frame) => n + (frame.contentWindow.dataLayer?.length ?? 0), 0);
      if (!expectedAds && !expectedAnalytics) assert.equal(rawEntries, 0);
      const finished = await command({op: 'matrix_finish', case_key: setup.case_key,
        ads_commands: scenario.conversions().length, analytics_commands: analyticsCommands, raw_entries: rawEntries,
        privacy_checked: true, request_attempts: scenario.state.requests.length, no_vendor_fetch: true});
      assert.equal(finished.ok, true);
      // Destroy optional contexts before replacing server-side session/store/receiver state.
      await scenario.retire();
    }
  }
  const checks = {actual_rest_configs: true, one_native_command: true, exact_transaction: true, exact_retry: true,
    analytics_once: true, withdraw_no_replay: true, no_vendor_fetch: true, raw_command_privacy: true};
  const done = await command({op: 'complete', checks}); assert.equal(done.ok, true);
  input.close();
} catch (error) {
  const code = /^[A-Z][A-Z0-9_]{1,80}$/.test(error.message) ? error.message
    : error.code === 'ERR_ASSERTION' ? 'NATIVE_ASSERTION_FAILED' : 'NATIVE_DRIVER_FAILED';
  process.stderr.write(JSON.stringify({phase, case: caseKey, status: 'DIAGNOSTIC_FAILURE', elapsed_seconds: (performance.now() - started) / 1000,
    error_code: code}) + '\n');
  input.close(); process.exitCode = 1;
}
