import test from 'node:test';
import assert from 'node:assert/strict';
import {createRegistry, PrototypeLedger, prepareDestinations} from './contract.mjs';
import {reduceAttribution} from './attribution-state.mjs';
import {createAnalyticsSources, reduceAnalyticsAttribution, analyticsAcceptedReceiptContext} from './analytics-attribution-state.mjs';
import {PrivatePurposeSidecarLedger as ActualPrivatePurposeSidecarLedger} from './private-purpose-sidecar.mjs';

// Entirely synthetic. These are not real campaigns, contacts, Google IDs or receipts.
const NOW = Date.parse('2026-11-10T08:00:00Z');
const page = number => ({campaign_key: `BSRE-C000${number}`, landing_page_id: `BSRE-LP000${number}`,
  path: `/lp/bsre-c000${number}/`, page_version: '0.0.1', page_family: 'TEST', property_destination: 'dubai',
  property_segment: 'residential_offplan', transaction_intent: 'buy', language: 'en',
  ctas: [{cta_id: 'bsre-test-form', cta_type: 'form', cta_position: 'body', form_id: 'test-form', destination_key: 'test-intake'}]});
const registry = createRegistry([page(1), page(2)]);
const source = (number = 1) => ({source_key: `TEST_ONLY_source_${number}`, source_version: '0.0.1',
  campaign_key: page(number).campaign_key, landing_page_id: page(number).landing_page_id,
  metadata: {utm_source: `TEST_ONLY_source_${number}`, utm_medium: 'TEST_ONLY_CPC', utm_campaign: `TEST_ONLY_campaign_${number}`,
    utm_id: `TEST_ONLY_id_${number}`, utm_term: 'TEST_ONLY_reviewed_intent', utm_content: 'TEST_ONLY_control'},
  review_reference: `TEST_ONLY_review_${number}`});
const sources = createAnalyticsSources([source(1), source(2)]);
const consent = (overrides = {}) => ({verified: true, server_eligible: true, expires_at: '2026-11-10T10:00:00Z',
  analytics: true, advertising: false, ad_user_data: false, personalization: false, qa: false, admin: false, ...overrides});
const config = (overrides = {}) => ({session_id: 'TEST_ONLY_session_A', consent: consent(), registry, sources, now: NOW, ...overrides});
function acquisition(number = 1, at = NOW, id = `TEST_ONLY_acquisition_${number}`) {
  return {type: 'acquisition', acquisition: {acquisition_id: id, observed_at: new Date(at).toISOString(),
    campaign_key: page(number).campaign_key, landing_page_id: page(number).landing_page_id,
    source_key: source(number).source_key, metadata: {...source(number).metadata},
    evidence: {source: 'validated_external_acquisition', verified: true, reference: `TEST_ONLY_external_${number}`}}};
}
function adAcquisition(number = 1, at = NOW, id = `TEST_ONLY_ad_${number}`) {
  const incoming = acquisition(number, at, id).acquisition;
  return {type: 'acquisition', acquisition: {acquisition_id: incoming.acquisition_id, observed_at: incoming.observed_at,
    campaign_key: incoming.campaign_key, landing_page_id: incoming.landing_page_id,
    click_ids: {gclid: `TEST_ONLY_Exact_Ad_${number}`}, metadata: {utm_campaign: `TEST_ONLY_ad_campaign_${number}`}, evidence: incoming.evidence}};
}
function adConfig(cfg) { const {session_id, consent, registry, now} = cfg; return {session_id, consent, registry, now}; }
function owned(cfg = config()) {
  return {analytics: reduceAnalyticsAttribution(null, acquisition(), cfg),
    advertising: reduceAttribution(null, adAcquisition(), adConfig(cfg))};
}
function receipt(number = 1, overrides = {}) { return {accepted: true, durable: true, lead_id: `TEST_ONLY_lead_${number}`,
  event_id: `bsre-event-00000000-0000-4000-8000-00000000000${number}`, original_analytics: true,
  original_advertising: true, original_ad_user_data: false, ...overrides}; }
const evidence = {source: 'server_confirmed', verified: true, reference: 'TEST_ONLY_durable_receipt'};
function originalCapture(state, accepted, cfg) {
  return {schema_version: 1, source: 'server_bound_original_intake_attribution', verified: true,
    reference: 'TEST_ONLY_original_capture', lead_id: accepted.lead_id, event_id: accepted.event_id,
    captured_at: new Date(cfg.now).toISOString(), session_id: cfg.session_id,
    captured_consent: {...cfg.consent, analytics: accepted.original_analytics,
      advertising: accepted.original_advertising, ad_user_data: accepted.original_ad_user_data},
    captured_states: structuredClone({analytics: accepted.original_analytics ? state.analytics : null,
      advertising: accepted.original_advertising ? state.advertising : null})};
}
// Test-only stand-in for an original-intake producer. Fixtures are captured ONCE
// per receipt; production supplies its independently authenticated envelope.
// Missing/changed proof cases below call the actual class directly.
class PrivatePurposeSidecarLedger extends ActualPrivatePurposeSidecarLedger {
  #fixtures = new Map();
  prepare(state, accepted, proof, cfg, capture) {
    if (capture === undefined) {
      if (!this.#fixtures.has(accepted.event_id)) this.#fixtures.set(accepted.event_id, originalCapture(state, accepted, cfg));
      capture = this.#fixtures.get(accepted.event_id);
    }
    return super.prepare(state, accepted, proof, cfg, capture);
  }
}

test('analytics-only A/internal/B preserves independent first/latest and registry binding without advertising IDs', () => {
  const a = reduceAnalyticsAttribution(null, acquisition(), config());
  const internal = reduceAnalyticsAttribution(a, {type: 'internal_navigation'}, config({now: NOW + 1000}));
  assert.deepEqual(a, internal);
  const b = reduceAnalyticsAttribution(internal, acquisition(2, NOW + 2000), config({now: NOW + 2000}));
  assert.equal(b.first_touch.campaign_key, 'BSRE-C0001');
  assert.equal(b.latest_touch.campaign_key, 'BSRE-C0002');
  assert.equal(b.first_touch.original_analytics.granted, true);
  const accepted = analyticsAcceptedReceiptContext(b, receipt(), evidence, config({now: NOW + 3000}));
  assert.deepEqual(accepted.attribution.first_touch, a.first_touch);
  assert.deepEqual(accepted.attribution.latest_touch, b.latest_touch);
  assert.doesNotMatch(JSON.stringify(accepted), /gclid|gbraid|wbraid|google_campaign_id|ad_group_id|creative_id|advertising/);
});

test('analytics purpose independently denies malformed, expired, unverified, ineligible, admin and QA states', () => {
  const a = owned().analytics;
  for (const choice of [{}, consent({analytics: false, advertising: true}), consent({analytics: 'true'}),
    consent({verified: false}), consent({server_eligible: false}), consent({admin: true}), consent({qa: true}),
    consent({personalization: true}), consent({expires_at: '2026-11-10T08:00:00Z'}),
    consent({expires_at: '2027-02-31T10:00:00Z'}), consent({expires_at: '2026-11-10T10:00:00+00:00'}), {...consent(), unknown: true}]) {
    assert.equal(reduceAnalyticsAttribution(a, {type: 'internal_navigation'}, config({consent: choice})), null);
  }
  assert.ok(reduceAnalyticsAttribution(null, acquisition(), config({consent: consent({advertising: true})})));
});

test('withdrawal works without configuration, and session changes or expired original permission cannot revive a touch', () => {
  const a = owned().analytics;
  assert.equal(reduceAnalyticsAttribution(a, {type: 'withdrawal'}, null), null);
  assert.equal(reduceAnalyticsAttribution(null, {type: 'internal_navigation'}, config()), null);
  assert.equal(reduceAnalyticsAttribution(a, {type: 'internal_navigation'}, config({session_id: 'TEST_ONLY_session_B'})), null);
  const short = reduceAnalyticsAttribution(null, acquisition(), config({consent: consent({expires_at: '2026-11-10T08:00:01Z'})}));
  assert.equal(reduceAnalyticsAttribution(short, {type: 'internal_navigation'}, config({now: NOW + 2000})), null);
  const fresh = reduceAnalyticsAttribution(short, acquisition(2, NOW + 2000), config({now: NOW + 2000}));
  assert.equal(fresh.first_touch.acquisition_id, 'TEST_ONLY_acquisition_2');
});

test('analytics metadata admits only exact reviewed business codes; raw/contact/token URL fields and all ad IDs reject', () => {
  for (const mutate of [
    incoming => { incoming.metadata.utm_source = 'TEST_ONLY_contact@example.invalid'; },
    incoming => { incoming.metadata.utm_source = '+999123456789'; },
    incoming => { incoming.metadata.utm_source = 'TEST_ONLY free text'; },
    incoming => { incoming.metadata.utm_source = 'TEST_ONLY%40token'; },
    incoming => { incoming.metadata.utm_source = 'TEST_ONLY_token_not_in_catalog'; },
    incoming => { incoming.metadata.utm_source = 'TEST_ONLY\n'; },
    incoming => { incoming.metadata.utm_source = 'x'.repeat(65); },
    incoming => { incoming.metadata.utm_source = 'https://example.invalid/path'; },
    incoming => { incoming.metadata.gclid = 'TEST_ONLY_click'; },
    incoming => { incoming.metadata.google_campaign_id = '000123'; },
    incoming => { incoming.metadata.ad_group_id = '000456'; },
    incoming => { incoming.metadata.creative_id = '000789'; },
    incoming => { incoming.metadata.utm_unknown = 'TEST_ONLY_unknown'; },
    incoming => { incoming.click_ids = {}; }, incoming => { incoming.referrer = 'https://example.invalid/'; },
    incoming => { incoming.url = 'https://example.invalid/'; }, incoming => { incoming.token = 'TEST_ONLY_secret'; },
  ]) {
    const input = acquisition(); mutate(input.acquisition);
    assert.throws(() => reduceAnalyticsAttribution(null, input, config({consent: consent({advertising: true})})));
  }
  const missing = acquisition(); missing.acquisition.metadata = {};
  assert.deepEqual(reduceAnalyticsAttribution(null, missing, config()).first_touch.metadata, {});
});

test('source catalog itself rejects unapproved fields and free-form values and freezes admitted source snapshots', () => {
  for (const mutate of [row => { row.metadata.gclid = 'TEST_ONLY_click'; }, row => { row.metadata.utm_term = 'TEST_ONLY@example.invalid'; },
    row => { row.metadata.utm_content = 'TEST_ONLY\u0000value'; }, row => { row.metadata.utm_id = '999123456789'; },
    row => { row.source_version = '0.0.1\n'; }, row => { row.review_reference = 'TEST_ONLY\n'; },
    row => { row.unapproved = true; }]) {
    const row = source(); mutate(row); assert.throws(() => createAnalyticsSources([row]));
  }
  assert.throws(() => createAnalyticsSources([source(), source()]));
  const row = source(), catalog = createAnalyticsSources([row]); row.metadata.utm_source = 'TEST_ONLY_mutated';
  assert.equal(catalog.resolve(source().source_key).metadata.utm_source, source().metadata.utm_source);
  assert.throws(() => { catalog.resolve(source().source_key).metadata.utm_source = 'TEST_ONLY_mutated'; }, TypeError);
});

test('unknown sources, changed versions, wrong purpose, unverified acquisition and mismatched campaign/page cannot rehydrate', () => {
  for (const mutate of [a => { a.source_key = 'TEST_ONLY_missing'; }, a => { a.landing_page_id = 'BSRE-LP0002'; },
    a => { a.campaign_key = 'BSRE-C9999'; }, a => { a.evidence.verified = false; }, a => { a.evidence.source = 'self_referrer'; }]) {
    const incoming = acquisition(); mutate(incoming.acquisition); assert.throws(() => reduceAnalyticsAttribution(null, incoming, config()));
  }
  const a = owned().analytics, changed = source(); changed.source_version = '0.0.2';
  assert.throws(() => reduceAnalyticsAttribution(a, {type: 'internal_navigation'}, config({sources: createAnalyticsSources([changed])})), /SOURCE_INVALID/);
  assert.throws(() => reduceAnalyticsAttribution({...a, purpose: 'advertising'}, {type: 'internal_navigation'}, config()), /STATE_INVALID/);
  assert.throws(() => reduceAnalyticsAttribution(a, {type: 'internal_navigation', url: page(2).path}, config()), /ACTION_INVALID/);
});

test('time ordering, exact retries, immutable metadata and original expiry are retained rather than upgraded', () => {
  const cfg = config({consent: consent({expires_at: '2026-11-10T09:00:00Z'})}), input = acquisition();
  const a = reduceAnalyticsAttribution(null, input, cfg); input.acquisition.metadata.utm_source = 'TEST_ONLY_mutated';
  assert.equal(a.first_touch.metadata.utm_source, source().metadata.utm_source);
  assert.throws(() => { a.first_touch.metadata.utm_source = 'TEST_ONLY_mutated'; }, TypeError);
  const again = reduceAnalyticsAttribution(a, acquisition(), config());
  assert.equal(again.first_touch.original_analytics.expires_at, '2026-11-10T09:00:00.000Z');
  const reordered = acquisition(); reordered.acquisition.metadata = Object.fromEntries(Object.entries(reordered.acquisition.metadata).reverse());
  assert.deepEqual(reduceAnalyticsAttribution(a, reordered, config()), a);
  const conflict = acquisition(); conflict.acquisition.metadata = {};
  assert.throws(() => reduceAnalyticsAttribution(a, conflict, config()), /CONFLICT/);
  assert.throws(() => reduceAnalyticsAttribution(a, acquisition(2, NOW + 1), config()), /TIME_OR_ID_INVALID/);
  const b = reduceAnalyticsAttribution(a, acquisition(2, NOW + 2000), config({now: NOW + 2000}));
  assert.throws(() => reduceAnalyticsAttribution(b, acquisition(1, NOW + 1000, 'TEST_ONLY_earlier'), config({now: NOW + 3000})), /OUT_OF_ORDER/);
  const badTime = acquisition(); badTime.acquisition.observed_at = '2026-02-31T08:00:00Z';
  assert.throws(() => reduceAnalyticsAttribution(null, badTime, config()));
  assert.throws(() => reduceAnalyticsAttribution(null, acquisition(), config({now: NOW + 1000})), /FRESH_CAPTURE_TIME/);
});

test('analytics receipt context independently reuses durable receipt validation and original analytics permission', () => {
  const a = owned().analytics;
  for (const bad of [receipt(1, {accepted: false}), receipt(1, {durable: false}), receipt(1, {original_analytics: 'true'}),
    {...receipt(), phone: 'TEST_ONLY_not_allowed'}]) assert.throws(() => analyticsAcceptedReceiptContext(a, bad, evidence, config()));
  assert.throws(() => analyticsAcceptedReceiptContext(a, receipt(), {...evidence, verified: false}, config()));
  assert.equal(analyticsAcceptedReceiptContext(a, receipt(1, {original_analytics: false}), evidence, config()).attribution, null);
  assert.equal(analyticsAcceptedReceiptContext(null, receipt(), evidence, config()).attribution, null);
});

test('private sidecar composes independently captured analytics/ad histories without merging their metadata', () => {
  const cfg = config({consent: consent({advertising: true})});
  const state = owned(cfg);
  state.analytics = reduceAnalyticsAttribution(state.analytics, acquisition(2, NOW + 1000), {...cfg, now: NOW + 1000});
  const result = new PrivatePurposeSidecarLedger().prepare(state, receipt(), evidence, {...cfg, now: NOW + 2000});
  assert.equal(result.sidecar.analytics.latest_touch.campaign_key, 'BSRE-C0002');
  assert.equal(result.sidecar.advertising.latest_touch.campaign_key, 'BSRE-C0001');
  assert.equal(result.sidecar.advertising.latest_touch.click_ids.gclid, 'TEST_ONLY_Exact_Ad_1');
  assert.equal(result.sidecar.analytics.latest_touch.metadata.utm_campaign, 'TEST_ONLY_campaign_2');
  assert.doesNotMatch(JSON.stringify(result.sidecar.analytics), /gclid|TEST_ONLY_Exact_Ad|TEST_ONLY_ad_campaign/);
  assert.equal(result.sidecar.wire_version_1_modified, false);
  assert.equal(result.sidecar.deployment_authorized, false);
  assert.equal(result.sidecar.network_calls, 0);
  assert.throws(() => { result.sidecar.analytics.latest_touch.source_key = 'TEST_ONLY_mutation'; }, TypeError);
});

test('analytics-only and advertising-only permissions prepare only their separate original permitted context', () => {
  for (const [choice, expected] of [[consent(), 'analytics'], [consent({analytics: false, advertising: true}), 'advertising']]) {
    const cfg = config({consent: choice}), result = new PrivatePurposeSidecarLedger().prepare(owned(cfg), receipt(), evidence, cfg);
    assert.ok(result.sidecar[expected]); assert.equal(result.sidecar[expected === 'analytics' ? 'advertising' : 'analytics'], null);
  }
  const cfg = config({consent: consent({advertising: true})});
  const none = new PrivatePurposeSidecarLedger().prepare(owned(cfg), receipt(1, {original_analytics: false, original_advertising: false}), evidence, cfg);
  assert.equal(none.sidecar.analytics, null); assert.equal(none.sidecar.advertising, null);
});

test('same receipt retries retain original accepted histories while returning current owned histories separately', () => {
  const cfg = config({consent: consent({advertising: true})}), ledger = new PrivatePurposeSidecarLedger();
  const first = ledger.prepare(owned(cfg), receipt(), evidence, cfg), later = {...cfg, now: NOW + 2000};
  const state = {analytics: reduceAnalyticsAttribution(first.next_state.analytics, acquisition(2, later.now), later),
    advertising: reduceAttribution(first.next_state.advertising, adAcquisition(2, later.now), adConfig(later))};
  const again = ledger.prepare(state, receipt(), evidence, later);
  assert.equal(again.status, 'same_receipt_context_preserved_not_delivered');
  assert.deepEqual(again.sidecar, first.sidecar);
  assert.equal(again.next_state.analytics.latest_touch.campaign_key, 'BSRE-C0002');
  assert.equal(again.next_state.advertising.latest_touch.campaign_key, 'BSRE-C0002');
  for (const bad of [receipt(1, {original_analytics: false}), receipt(1, {lead_id: 'TEST_ONLY_different'}),
    receipt(2, {lead_id: receipt().lead_id})]) assert.throws(() => ledger.prepare(state, bad, evidence, later), /CONFLICT/);
  assert.throws(() => ledger.prepare(state, receipt(), {...evidence, reference: 'TEST_ONLY_different'}, later), /CONFLICT/);
});

test('later purpose grants cannot upgrade a context missing at first acceptance', () => {
  const ledger = new PrivatePurposeSidecarLedger(), denied = config({consent: consent({analytics: false})});
  const first = ledger.prepare({analytics: null, advertising: null}, receipt(), evidence, denied);
  const granted = config({now: NOW + 1000, consent: consent({advertising: true})});
  const state = {analytics: reduceAnalyticsAttribution(null, acquisition(1, granted.now), granted),
    advertising: reduceAttribution(null, adAcquisition(1, granted.now), adConfig(granted))};
  const retried = ledger.prepare(state, receipt(), evidence, granted);
  assert.equal(first.sidecar.analytics, null); assert.equal(retried.sidecar.analytics, null); assert.equal(retried.sidecar.advertising, null);
  const newReceipt = ledger.prepare(state, receipt(2), evidence, granted);
  assert.ok(newReceipt.sidecar.analytics); assert.ok(newReceipt.sidecar.advertising);
});

test('explicit withdrawal clears only that owned purpose and cached receipt contexts, without configuration or regrant revival', () => {
  for (const purpose of ['analytics', 'advertising']) {
    const cfg = config({consent: consent({advertising: true})}), ledger = new PrivatePurposeSidecarLedger();
    const first = ledger.prepare(owned(cfg), receipt(), evidence, cfg), other = purpose === 'analytics' ? 'advertising' : 'analytics';
    const state = ledger.withdraw(first.next_state, purpose);
    assert.equal(state[purpose], null); assert.deepEqual(state[other], first.next_state[other]);
    const later = {...cfg, now: NOW + 1000}, input = {...state};
    input[purpose] = purpose === 'analytics' ? reduceAnalyticsAttribution(null, acquisition(2, later.now), later)
      : reduceAttribution(null, adAcquisition(2, later.now), adConfig(later));
    const retried = ledger.prepare(input, receipt(), evidence, later);
    assert.equal(retried.sidecar[purpose], null); assert.deepEqual(retried.sidecar[other], first.sidecar[other]);
    assert.ok(ledger.prepare(input, receipt(2), evidence, later).sidecar[purpose]);
  }
});

test('observed denial clears cached contexts across receipts; malformed ISO choices cannot bypass invalidation', () => {
  for (const purpose of ['analytics', 'advertising']) {
    const cfg = config({consent: consent({advertising: true})}), ledger = new PrivatePurposeSidecarLedger(), state = owned(cfg);
    ledger.prepare(state, receipt(), evidence, cfg); ledger.prepare(state, receipt(2), evidence, cfg);
    const denied = {...cfg, now: NOW + 1000, consent: consent({advertising: true, [purpose]: false})};
    const result = ledger.prepare(state, receipt(), evidence, denied);
    assert.equal(result.next_state[purpose], null);
    const retried = ledger.prepare(state, receipt(2), evidence, {...cfg, now: NOW + 2000});
    assert.equal(retried.sidecar[purpose], null);
  }
  const cfg = config({consent: consent({advertising: true})}), ledger = new PrivatePurposeSidecarLedger(), state = owned(cfg);
  ledger.prepare(state, receipt(), evidence, cfg); ledger.prepare(state, receipt(2), evidence, cfg);
  ledger.prepare(state, receipt(), evidence, {...cfg, now: NOW + 1000, consent: consent({advertising: true, expires_at: '2026-11-10T10:00:00+00:00'})});
  const retried = ledger.prepare(state, receipt(2), evidence, {...cfg, now: NOW + 2000});
  assert.equal(retried.sidecar.analytics, null); assert.equal(retried.sidecar.advertising, null);
});

test('a new session or expired original capture holds earlier accepted context even with a new current grant', () => {
  for (const invalidate of ['session', 'expiry']) {
    const cfg = config({consent: consent({advertising: true, expires_at: '2026-11-10T08:00:01Z'})});
    const ledger = new PrivatePurposeSidecarLedger(), first = ledger.prepare(owned(cfg), receipt(), evidence, cfg);
    const later = config({consent: consent({advertising: true}), now: NOW + 2000,
      ...(invalidate === 'session' ? {session_id: 'TEST_ONLY_session_B'} : {})});
    const input = {analytics: reduceAnalyticsAttribution(first.next_state.analytics, acquisition(2, later.now), later),
      advertising: reduceAttribution(first.next_state.advertising, adAcquisition(2, later.now), adConfig(later))};
    const retry = ledger.prepare(input, receipt(), evidence, later);
    assert.equal(retry.sidecar.analytics, null); assert.equal(retry.sidecar.advertising, null);
    assert.ok(retry.next_state.analytics); assert.ok(retry.next_state.advertising);
    assert.throws(() => ledger.prepare(input, receipt(), evidence, cfg), /CLOCK_REGRESSION/);
  }
});

test('failed receipt validation does not reserve a slot and both purposes share one session/clock configuration', () => {
  const cfg = config(), ledger = new PrivatePurposeSidecarLedger(), state = owned(cfg);
  assert.throws(() => ledger.prepare(state, receipt(1, {durable: false}), evidence, cfg), /DURABLE_RECEIPT/);
  assert.throws(() => ledger.prepare(state, receipt(), evidence, {...cfg, ad_config: adConfig(cfg)}), /OPTIONS_INVALID/);
  assert.equal(ledger.prepare(state, receipt(), evidence, cfg).status, 'private_sidecar_prepared_not_delivered');
  assert.throws(() => ledger.withdraw(state, 'personalization'), /WITHDRAWAL_INVALID/);
});

test('sidecars remain private and existing event normalization rejects them rather than transmitting contexts to GA4', () => {
  const cfg = config(), result = new PrivatePurposeSidecarLedger().prepare(owned(cfg), receipt(), evidence, cfg);
  const raw = {event: 'form_accepted', schema_version: 1, campaign_key: page(1).campaign_key,
    landing_page_id: page(1).landing_page_id, page_version: page(1).page_version,
    internal_event_id: receipt().event_id, receipt: receipt(), evidence};
  const settings = {registry, consent: consent(), now: NOW, ledger: new PrototypeLedger(),
    mappings: {ga4: {approved: true, measurement_id: 'G-TESTONLY00', evidence_ref: 'TEST_ONLY_mapping', producer: 'single_reviewed_web_producer'}}};
  const prepared = prepareDestinations(raw, settings);
  assert.doesNotMatch(JSON.stringify(prepared.output), /first_touch|latest_touch|utm_|source_key|session_id|original_analytics|TEST_ONLY_acquisition/);
  assert.throws(() => prepareDestinations({...raw, private_sidecar: result.sidecar}, settings), /UNKNOWN_EVENT_FIELD/);
});

test('missing original capture holds; first prepare after later navigation uses original intake histories rather than current ones', () => {
  const cfg = config({consent: consent({advertising: true})}), a = owned(cfg), original = originalCapture(a, receipt(), cfg);
  const later = {...cfg, now: NOW + 2000};
  const b = {analytics: reduceAnalyticsAttribution(a.analytics, acquisition(2, later.now), later),
    advertising: reduceAttribution(a.advertising, adAcquisition(2, later.now), adConfig(later))};
  const ledger = new ActualPrivatePurposeSidecarLedger();
  assert.throws(() => ledger.prepare(b, receipt(), evidence, later), /ORIGINAL_CAPTURE_REQUIRED/);
  assert.equal(ledger.contextCounts().receipt_slots, 0);
  const prepared = ledger.prepare(b, receipt(), evidence, later, original);
  assert.equal(prepared.sidecar.analytics.latest_touch.campaign_key, 'BSRE-C0001');
  assert.equal(prepared.sidecar.advertising.latest_touch.campaign_key, 'BSRE-C0001');
  assert.equal(prepared.next_state.analytics.latest_touch.campaign_key, 'BSRE-C0002');
  assert.equal(prepared.next_state.advertising.latest_touch.campaign_key, 'BSRE-C0002');
  assert.match(prepared.sidecar.capture_binding.snapshot_digest, /^[0-9a-f]{64}$/);
  const changed = originalCapture(b, receipt(), later);
  assert.throws(() => ledger.prepare(b, receipt(), evidence, later, changed), /RECEIPT_CONFLICT/);
  const afterIntake = structuredClone(changed); afterIntake.captured_at = original.captured_at;
  assert.throws(() => new ActualPrivatePurposeSidecarLedger().prepare(b, receipt(), evidence, later, afterIntake), /TIME_INVALID|TIME_OR_ID_INVALID/);
});

test('capture envelopes bind receipt, original permissions, session, exact timestamps and independently validated snapshot history', () => {
  const cfg = config({consent: consent({advertising: true})}), state = owned(cfg), original = originalCapture(state, receipt(), cfg);
  for (const mutate of [value => { value.lead_id = 'TEST_ONLY_other'; }, value => { value.event_id = receipt(2).event_id; },
    value => { value.verified = false; }, value => { value.source = 'browser_hint'; },
    value => { value.captured_at = new Date(NOW + 1).toISOString(); }, value => { value.captured_at = '2026-11-10T08:00:00+00:00'; },
    value => { value.captured_at = new Date(NOW - 1).toISOString(); }, value => { value.captured_consent.analytics = false; },
    value => { value.captured_states.analytics.session_id = 'TEST_ONLY_other_session'; },
    value => { value.captured_states.advertising = undefined; }, value => { value.token = 'TEST_ONLY_not_allowed'; }]) {
    const capture = structuredClone(original); mutate(capture);
    const ledger = new ActualPrivatePurposeSidecarLedger();
    assert.throws(() => ledger.prepare(state, receipt(), evidence, cfg, capture));
    assert.deepEqual(ledger.contextCounts(), {receipt_slots: 0, analytics_contexts: 0, advertising_contexts: 0});
  }
  const reordered = Object.fromEntries(Object.entries(original).reverse()), ledger = new ActualPrivatePurposeSidecarLedger();
  const first = ledger.prepare(state, receipt(), evidence, cfg, original);
  assert.deepEqual(ledger.prepare(state, receipt(), evidence, cfg, reordered).sidecar, first.sidecar);
});

test('observing a different session tombstones every receipt context before proof validation; A to B to A cannot revive another receipt', () => {
  const cfg = config({consent: consent({advertising: true})}), state = owned(cfg), ledger = new ActualPrivatePurposeSidecarLedger();
  const r1 = receipt(), r2 = receipt(2), c1 = originalCapture(state, r1, cfg), c2 = originalCapture(state, r2, cfg);
  ledger.prepare(state, r1, evidence, cfg, c1); ledger.prepare(state, r2, evidence, cfg, c2);
  assert.equal(ledger.contextCounts().advertising_contexts, 2);
  const sessionB = {...cfg, session_id: 'TEST_ONLY_session_B', now: NOW + 1000};
  assert.throws(() => ledger.prepare({analytics: null, advertising: null}, r1, evidence, sessionB), /ORIGINAL_CAPTURE_REQUIRED/);
  assert.deepEqual(ledger.contextCounts(), {receipt_slots: 2, analytics_contexts: 0, advertising_contexts: 0});
  const retry = ledger.prepare(state, r2, evidence, {...cfg, now: NOW + 2000}, c2);
  assert.equal(retry.sidecar.analytics, null); assert.equal(retry.sidecar.advertising, null);
  assert.ok(retry.next_state.analytics); assert.ok(retry.next_state.advertising);
});

test('expiry sweeps all receipt slots for only the expired purpose before an unrelated missing-proof failure', () => {
  for (const purpose of ['analytics', 'advertising']) {
    const cfg = config({consent: consent({advertising: true})}), short = {...cfg, consent: consent({advertising: true, expires_at: '2026-11-10T08:00:01Z'})};
    const state = owned(cfg), ledger = new ActualPrivatePurposeSidecarLedger(); state[purpose] = owned(short)[purpose];
    const r1 = receipt(), r2 = receipt(2), c1 = originalCapture(state, r1, cfg), c2 = originalCapture(state, r2, cfg);
    ledger.prepare(state, r1, evidence, cfg, c1); ledger.prepare(state, r2, evidence, cfg, c2);
    const later = {...cfg, now: NOW + 2000};
    assert.throws(() => ledger.prepare(state, r1, evidence, later), /ORIGINAL_CAPTURE_REQUIRED/);
    const other = purpose === 'analytics' ? 'advertising' : 'analytics';
    assert.equal(ledger.contextCounts()[purpose + '_contexts'], 0);
    assert.equal(ledger.contextCounts()[other + '_contexts'], 2);
    const retry = ledger.prepare(state, r2, evidence, later, c2);
    assert.equal(retry.sidecar[purpose], null); assert.ok(retry.sidecar[other]);
  }
});

test('purpose denial purges all its receipt contexts even when malformed state, missing configuration or clock checks abort preparation', () => {
  for (const purpose of ['analytics', 'advertising']) {
    const cfg = config({consent: consent({advertising: true})}), state = owned(cfg), ledger = new ActualPrivatePurposeSidecarLedger();
    const r1 = receipt(), r2 = receipt(2), c1 = originalCapture(state, r1, cfg), c2 = originalCapture(state, r2, cfg);
    ledger.prepare(state, r1, evidence, cfg, c1); ledger.prepare(state, r2, evidence, cfg, c2);
    const other = purpose === 'analytics' ? 'advertising' : 'analytics', broken = structuredClone(state);
    broken[other].first_touch = null;
    const denied = {...cfg, now: NOW + 1000, consent: consent({advertising: true, [purpose]: false})};
    assert.throws(() => ledger.prepare(broken, r1, evidence, denied, c1));
    assert.equal(ledger.contextCounts()[purpose + '_contexts'], 0);
    assert.equal(ledger.contextCounts()[other + '_contexts'], 2);
    const retry = ledger.prepare(state, r2, evidence, {...cfg, now: NOW + 2000}, c2);
    assert.equal(retry.sidecar[purpose], null); assert.ok(retry.sidecar[other]);
  }
  for (const missing of ['registry', 'sources', 'rollback']) {
    const cfg = config({consent: consent({advertising: true})}), state = owned(cfg), ledger = new ActualPrivatePurposeSidecarLedger();
    const r1 = receipt(), r2 = receipt(2), c1 = originalCapture(state, r1, cfg), c2 = originalCapture(state, r2, cfg);
    ledger.prepare(state, r1, evidence, cfg, c1); ledger.prepare(state, r2, evidence, cfg, c2);
    const broken = {...cfg, now: NOW + 1000, consent: consent({advertising: true, analytics: false})};
    if (missing === 'rollback') broken.now = NOW - 1; else delete broken[missing];
    assert.throws(() => ledger.prepare(state, r1, evidence, broken, c1));
    assert.equal(ledger.contextCounts().analytics_contexts, 0);
    const retry = ledger.prepare(state, r2, evidence, {...cfg, now: NOW + 2000}, c2);
    assert.equal(retry.sidecar.analytics, null); assert.ok(retry.sidecar.advertising);
  }
  const cfg = config({consent: consent({advertising: true})}), state = owned(cfg), ledger = new ActualPrivatePurposeSidecarLedger();
  const r1 = receipt(), r2 = receipt(2), c1 = originalCapture(state, r1, cfg), c2 = originalCapture(state, r2, cfg);
  ledger.prepare(state, r1, evidence, cfg, c1); ledger.prepare(state, r2, evidence, cfg, c2);
  const malformed = consent({advertising: true});
  Object.defineProperty(malformed, 'expires_at', {enumerable: true, get() { throw new Error('TEST_ONLY_accessor_rejected'); }});
  assert.throws(() => ledger.prepare(state, r1, evidence, {...cfg, consent: malformed, now: NOW + 1000}, c1));
  assert.deepEqual(ledger.contextCounts(), {receipt_slots: 2, analytics_contexts: 0, advertising_contexts: 0});
  const retry = ledger.prepare(state, r2, evidence, {...cfg, now: NOW + 2000}, c2);
  assert.equal(retry.sidecar.analytics, null); assert.equal(retry.sidecar.advertising, null);
});

test('explicit withdrawal purges its caches before malformed owned state can throw and does not erase the other purpose', () => {
  for (const purpose of ['analytics', 'advertising']) {
    const cfg = config({consent: consent({advertising: true})}), state = owned(cfg), ledger = new ActualPrivatePurposeSidecarLedger();
    const r1 = receipt(), r2 = receipt(2), c1 = originalCapture(state, r1, cfg), c2 = originalCapture(state, r2, cfg);
    ledger.prepare(state, r1, evidence, cfg, c1); ledger.prepare(state, r2, evidence, cfg, c2);
    assert.throws(() => ledger.withdraw(null, purpose), /STATE_REQUIRED/);
    const other = purpose === 'analytics' ? 'advertising' : 'analytics';
    assert.equal(ledger.contextCounts()[purpose + '_contexts'], 0);
    assert.equal(ledger.contextCounts()[other + '_contexts'], 2);
    const retried = ledger.prepare(state, r2, evidence, {...cfg, now: NOW + 1000}, c2);
    assert.equal(retried.sidecar[purpose], null); assert.ok(retried.sidecar[other]);
  }
});
