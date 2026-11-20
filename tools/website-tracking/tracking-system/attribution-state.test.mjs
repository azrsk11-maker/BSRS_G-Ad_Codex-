import test from 'node:test';
import assert from 'node:assert/strict';
import {createRegistry, PrototypeLedger, prepareDestinations} from './contract.mjs';
import {reduceAttribution, acceptedReceiptContext} from './attribution-state.mjs';

// Synthetic, offline fixtures only; never authentic campaigns, clicks or leads.
const NOW = Date.parse('2026-11-08T08:00:00Z');
const PAGE = {campaign_key: 'BSRE-C0001', landing_page_id: 'BSRE-LP0001', path: '/lp/bsre-c0001/',
  page_version: '0.0.1', page_family: 'TEST', property_destination: 'dubai',
  property_segment: 'residential_offplan', transaction_intent: 'buy', language: 'en',
  ctas: [{cta_id: 'bsre-test-form', cta_type: 'form', cta_position: 'body', form_id: 'test-form', destination_key: 'test-intake'}]};
const registry = createRegistry([PAGE]);
function consent(overrides = {}) { return {verified: true, server_eligible: true,
  expires_at: '2026-11-08T10:00:00Z', analytics: false, advertising: true, ad_user_data: false,
  personalization: false, qa: false, admin: false, ...overrides}; }
function config(overrides = {}) { return {session_id: 'TEST_ONLY_session_A', consent: consent(), registry, now: NOW, ...overrides}; }
function acquisition(id = 'TEST_ONLY_A', at = NOW, click = 'TEST_ONLY_Exact-Aa_1') { return {type: 'acquisition', acquisition: {
  acquisition_id: id, observed_at: new Date(at).toISOString(), campaign_key: PAGE.campaign_key,
  landing_page_id: PAGE.landing_page_id, click_ids: {gclid: click, gbraid: 'TEST_ONLY_Braid-Aa_2'},
  evidence: {source: 'validated_external_acquisition', verified: true, reference: 'TEST_ONLY_external-proof'},
}}; }
function receipt(overrides = {}) { return {accepted: true, durable: true, lead_id: 'TEST_ONLY_lead',
  event_id: 'bsre-event-00000000-0000-4000-8000-000000000001', original_analytics: false,
  original_advertising: true, original_ad_user_data: false, ...overrides}; }
const accepted = {source: 'server_confirmed', verified: true, reference: 'TEST_ONLY_durable-proof'};

test('A/internal/B/accepted receipt keeps first and latest separate with exact advertising-only IDs', () => {
  const a = reduceAttribution(null, acquisition(), config());
  const internal = reduceAttribution(a, {type: 'internal_navigation'}, config({now: NOW + 1000}));
  assert.deepEqual(internal, a);
  const b = reduceAttribution(internal, acquisition('TEST_ONLY_B', NOW + 2000, 'TEST_ONLY_Exact-Bb_2'), config({now: NOW + 2000}));
  assert.equal(b.first_touch.acquisition_id, 'TEST_ONLY_A');
  assert.equal(b.latest_touch.acquisition_id, 'TEST_ONLY_B');
  assert.equal(b.first_touch.click_ids.gclid, 'TEST_ONLY_Exact-Aa_1');
  const context = acceptedReceiptContext(b, receipt(), accepted, config({now: NOW + 3000}));
  assert.deepEqual(context.attribution.first_touch, a.first_touch);
  assert.deepEqual(context.attribution.latest_touch, b.latest_touch);
  assert.equal(context.network_calls, 0);
  assert.equal(context.deployment_authorized, false);
  assert.equal(context.attribution.first_touch.original_permissions.analytics, false);
  assert.equal(context.attribution.first_touch.original_permissions.ad_user_data, false);
});

test('unknown, expired, malformed, unverified, ineligible, admin or QA permission drops owned state', () => {
  const a = reduceAttribution(null, acquisition(), config());
  for (const choice of [{}, consent({verified: false}), consent({server_eligible: false}),
    consent({admin: true}), consent({qa: true}), consent({advertising: false}), consent({advertising: 'true'}),
    consent({personalization: true}), consent({expires_at: '2026-11-08T08:00:00Z'}),
    consent({expires_at: '2026-11-08T09:00:00+00:00'}), consent({expires_at: '2027-02-31T10:00:00Z'}),
    {...consent(), unexpected: true}]) {
    const cfg = config({consent: choice});
    assert.equal(reduceAttribution(a, {type: 'internal_navigation'}, cfg), null);
    const context = acceptedReceiptContext(a, receipt(), accepted, cfg);
    assert.equal(context.next_state, null);
    assert.equal(context.attribution, null);
  }
});

test('withdrawal clears the reducer slot immediately and neither a new session nor a later grant revives it', () => {
  const a = reduceAttribution(null, acquisition(), config());
  let slot = reduceAttribution(a, {type: 'withdrawal'}, config());
  assert.equal(slot, null);
  assert.equal(reduceAttribution(a, {type: 'withdrawal'}, null), null);
  assert.equal(reduceAttribution(slot, {type: 'internal_navigation'}, config()), null);
  assert.equal(reduceAttribution(a, {type: 'internal_navigation'}, config({session_id: 'TEST_ONLY_session_B'})), null);
  const fresh = reduceAttribution(a, acquisition('TEST_ONLY_C', NOW + 1000), config({session_id: 'TEST_ONLY_session_B', now: NOW + 1000}));
  assert.equal(fresh.first_touch.acquisition_id, 'TEST_ONLY_C');
  assert.equal(fresh.latest_touch.acquisition_id, 'TEST_ONLY_C');
});

test('expired original permission cannot be renewed into previously captured attribution', () => {
  const a = reduceAttribution(null, acquisition(), config({consent: consent({expires_at: '2026-11-08T08:00:01Z'})}));
  assert.equal(reduceAttribution(a, {type: 'internal_navigation'}, config({now: NOW + 2000})), null);
  const b = reduceAttribution(a, acquisition('TEST_ONLY_B', NOW + 2000), config({now: NOW + 2000}));
  assert.equal(b.first_touch.acquisition_id, 'TEST_ONLY_B');
});

test('external evidence and reviewed campaign binding are mandatory; internal URL/referrer/UTM cannot create acquisition', () => {
  for (const mutate of [
    a => { a.acquisition.evidence.verified = false; },
    a => { a.acquisition.evidence.source = 'self_referrer'; },
    a => { a.acquisition.campaign_key = 'BSRE-C9999'; },
    a => { a.acquisition.landing_page_id = 'BSRE-LP9999'; },
    a => { a.acquisition.utm_campaign = 'TEST_ONLY_unreviewed'; },
    a => { a.acquisition.referrer = 'https://example.invalid/'; },
    a => { delete a.acquisition.evidence; },
  ]) { const value = acquisition(); mutate(value); assert.throws(() => reduceAttribution(null, value, config())); }
  assert.throws(() => reduceAttribution(null, {type: 'internal_navigation', url: PAGE.path}, config()), /ACTION_INVALID/);
  assert.equal(reduceAttribution(null, {type: 'internal_navigation'}, config()), null);
});

test('oversize, control, unsupported fields, future/out-of-order timestamps and identity conflicts reject without trimming', () => {
  for (const value of ['TEST_ONLY\nclick', ' TEST_ONLY_click', 'x'.repeat(513), 'TEST_ONLY.click'])
    assert.throws(() => reduceAttribution(null, acquisition('TEST_ONLY_A', NOW, value), config()), /UNSUPPORTED_OR_OVERSIZED/);
  for (const mutate of [
    a => { a.acquisition.acquisition_id = 'x'.repeat(129); },
    a => { a.acquisition.acquisition_id = 'TEST_ONLY\u0000id'; },
    a => { a.acquisition.click_ids.email = 'TEST_ONLY@example.invalid'; },
    a => { a.acquisition.observed_at = '2026-02-31T08:00:00Z'; },
  ]) { const value = acquisition(); mutate(value); assert.throws(() => reduceAttribution(null, value, config())); }
  assert.throws(() => reduceAttribution(null, acquisition('TEST_ONLY_A', NOW + 1), config()), /TIME_INVALID/);
  const a = reduceAttribution(null, acquisition(), config());
  assert.throws(() => reduceAttribution(a, acquisition('TEST_ONLY_A', NOW, 'TEST_ONLY_different'), config()), /CONFLICT/);
  const b = reduceAttribution(a, acquisition('TEST_ONLY_B', NOW + 1000), config({now: NOW + 1000}));
  assert.throws(() => reduceAttribution(b, acquisition('TEST_ONLY_C', NOW + 500), config({now: NOW + 1000})), /OUT_OF_ORDER/);
  assert.deepEqual(reduceAttribution(b, acquisition(), config({now: NOW + 1000})), b);
});

test('retries retain original flags and returned snapshots cannot mutate earlier state or inputs', () => {
  const input = acquisition(), cfg = config(), before = structuredClone({input, consent: cfg.consent});
  const a = reduceAttribution(null, input, cfg);
  input.acquisition.click_ids.gclid = 'TEST_ONLY_input_changed';
  assert.equal(a.first_touch.click_ids.gclid, before.input.acquisition.click_ids.gclid);
  assert.throws(() => { a.first_touch.click_ids.gclid = 'TEST_ONLY_mutation'; }, TypeError);
  const again = reduceAttribution(a, acquisition(), config({consent: consent({analytics: true, ad_user_data: true})}));
  assert.equal(again.first_touch.original_permissions.ad_user_data, false);
  assert.equal(again.latest_touch.original_permissions.analytics, false);
  assert.notEqual(again, a);
  const reordered = acquisition();
  reordered.acquisition.click_ids = {gbraid: 'TEST_ONLY_Braid-Aa_2', gclid: 'TEST_ONLY_Exact-Aa_1'};
  reordered.acquisition.evidence = {reference: 'TEST_ONLY_external-proof', verified: true, source: 'validated_external_acquisition'};
  reordered.acquisition.observed_at = '2026-11-08T08:00:00Z';
  assert.deepEqual(reduceAttribution(a, reordered, config()), a);
  const r = receipt(), context = acceptedReceiptContext(a, r, accepted, config());
  r.lead_id = 'TEST_ONLY_changed';
  assert.equal(context.receipt.lead_id, 'TEST_ONLY_lead');
  assert.throws(() => { context.attribution.latest_touch.click_ids.gclid = 'TEST_ONLY_mutation'; }, TypeError);
});

test('durable server acceptance is mandatory but a valid enquiry context needs neither a click nor advertising permission', () => {
  const a = reduceAttribution(null, acquisition(), config());
  for (const r of [receipt({accepted: false}), receipt({durable: false}), receipt({original_advertising: 'true'}),
    {...receipt(), phone: 'TEST_ONLY_not_allowed'}])
    assert.throws(() => acceptedReceiptContext(a, r, accepted, config()), /DURABLE_RECEIPT/);
  assert.throws(() => acceptedReceiptContext(a, receipt(), {...accepted, source: 'browser'}, config()), /ACCEPTANCE_EVIDENCE/);
  assert.equal(acceptedReceiptContext(null, receipt(), accepted, config()).attribution, null);
  assert.equal(acceptedReceiptContext(a, receipt({original_advertising: false}), accepted, config()).attribution, null);
  const noClick = acquisition(); noClick.acquisition.click_ids = {};
  const withoutId = reduceAttribution(null, noClick, config());
  assert.deepEqual(withoutId.first_touch.click_ids, {});
  assert.equal(acceptedReceiptContext(a, receipt(), accepted, config({consent: consent({advertising: false})})).attribution, null);
});

test('private receipt attribution never enters existing GA4 preparation and is rejected as an event field', () => {
  const a = reduceAttribution(null, acquisition(), config());
  const context = acceptedReceiptContext(a, receipt(), accepted, config());
  const raw = {event: 'form_accepted', schema_version: 1, campaign_key: PAGE.campaign_key,
    landing_page_id: PAGE.landing_page_id, page_version: PAGE.page_version,
    internal_event_id: receipt().event_id, receipt: receipt({original_analytics: true}), evidence: accepted};
  const settings = {registry, consent: consent({analytics: true, advertising: false}), now: NOW,
    mappings: {ga4: {approved: true, measurement_id: 'G-TESTONLY00', evidence_ref: 'TEST_ONLY_mapping', producer: 'single_reviewed_web_producer'}},
    ledger: new PrototypeLedger()};
  const result = prepareDestinations(raw, settings);
  assert.equal(result.network_calls, 0);
  assert.doesNotMatch(JSON.stringify(result.output), /TEST_ONLY_Exact|Braid|first_touch|latest_touch|session_id|original_permissions/);
  assert.throws(() => prepareDestinations({...raw, attribution: context.attribution}, settings), /UNKNOWN_EVENT_FIELD/);
});

test('all provided UTM and Google ID fields stay exact, private, purpose-gated and independent across A/B snapshots', () => {
  const incoming = acquisition();
  incoming.acquisition.metadata = {
    utm_source: ' TEST_ONLY_Source ', utm_medium: 'TEST_ONLY_CPC', utm_campaign: 'TEST_ONLY_Campaign_A',
    utm_id: 'TEST_ONLY-id-A', utm_term: 'TEST_ONLY_contact@example.invalid',
    utm_content: 'TEST_ONLY phone +999 123 456 789', google_campaign_id: '00012345678901234567890',
    ad_group_id: '00023456789012345678901', creative_id: '00034567890123456789012',
  };
  const original = structuredClone(incoming.acquisition.metadata);
  const a = reduceAttribution(null, incoming, config());
  assert.deepEqual(a.first_touch.metadata, original);
  assert.deepEqual(a.latest_touch.metadata, original);
  assert.equal(a.first_touch.original_permissions.analytics, false);
  incoming.acquisition.metadata.utm_source = 'TEST_ONLY_changed_after_capture';
  assert.deepEqual(a.first_touch.metadata, original);
  const next = acquisition('TEST_ONLY_B', NOW + 1000);
  next.acquisition.metadata = {utm_source: 'TEST_ONLY_B', utm_campaign: 'TEST_ONLY_Campaign_B', creative_id: '00099'};
  const b = reduceAttribution(a, next, config({now: NOW + 1000}));
  assert.deepEqual(b.first_touch.metadata, original);
  assert.deepEqual(b.latest_touch.metadata, next.acquisition.metadata);
  assert.equal(Object.hasOwn(b.latest_touch.metadata, 'utm_term'), false);
  const context = acceptedReceiptContext(b, receipt(), accepted, config({now: NOW + 1000}));
  assert.deepEqual(context.attribution.first_touch.metadata, original);
  assert.throws(() => { context.attribution.latest_touch.metadata.utm_source = 'TEST_ONLY_mutation'; }, TypeError);
  assert.equal(reduceAttribution(a, {type: 'internal_navigation'}, config({consent: consent({advertising: false})})), null);
  const noMetadata = reduceAttribution(null, acquisition(), config());
  assert.deepEqual(noMetadata.first_touch.metadata, {});
  const raw = {event: 'form_accepted', schema_version: 1, campaign_key: PAGE.campaign_key,
    landing_page_id: PAGE.landing_page_id, page_version: PAGE.page_version,
    internal_event_id: receipt().event_id, receipt: receipt({original_analytics: true}), evidence: accepted};
  const result = prepareDestinations(raw, {registry, consent: consent({analytics: true, advertising: false}), now: NOW,
    mappings: {ga4: {approved: true, measurement_id: 'G-TESTONLY00', evidence_ref: 'TEST_ONLY_mapping', producer: 'single_reviewed_web_producer'}},
    ledger: new PrototypeLedger()});
  assert.doesNotMatch(JSON.stringify(result.output), /utm_|google_campaign_id|ad_group_id|creative_id|TEST_ONLY_Campaign|example\.invalid|999 123/);
});

test('private metadata rejects unknown keys, bad types, controls, oversized text, raw URLs and non-string/non-digit Google IDs', () => {
  for (const metadata of [
    null, [], {utm_source: null}, {utm_source: 3}, {utm_source: ''}, {utm_source: 'TEST_ONLY\u0000source'},
    {utm_term: 'TEST_ONLY\nterm'}, {utm_content: 'x'.repeat(513)}, {utm_unknown: 'TEST_ONLY_unknown'},
    {url: 'https://example.invalid/'}, {referrer: 'https://example.invalid/'},
    {utm_source: 'https://example.invalid/path?TEST_ONLY=value'}, {utm_source: 'www.example.invalid'},
    {google_campaign_id: 123}, {google_campaign_id: 'TEST_ONLY_fake'}, {ad_group_id: '1e3'},
    {ad_group_id: '-1'}, {creative_id: ' 123'}, {creative_id: '1.0'}, {creative_id: '9'.repeat(33)},
  ]) {
    const value = acquisition(); value.acquisition.metadata = metadata;
    assert.throws(() => reduceAttribution(null, value, config()));
  }
  const boundary = acquisition();
  boundary.acquisition.metadata = {utm_term: 'x'.repeat(512), creative_id: '9'.repeat(32)};
  const a = reduceAttribution(null, boundary, config());
  assert.equal(a.first_touch.metadata.utm_term.length, 512);
  assert.equal(a.first_touch.metadata.creative_id.length, 32);
  const reordered = acquisition();
  reordered.acquisition.metadata = {creative_id: '9'.repeat(32), utm_term: 'x'.repeat(512)};
  assert.deepEqual(reduceAttribution(a, reordered, config()), a);
  const conflict = structuredClone(reordered); conflict.acquisition.metadata.utm_term = 'TEST_ONLY_changed';
  assert.throws(() => reduceAttribution(a, conflict, config()), /CONFLICT/);
});
