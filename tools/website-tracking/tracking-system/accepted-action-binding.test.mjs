import {test} from 'node:test';
import assert from 'node:assert/strict';
import {validateAcceptedActionBinding as validate} from './validate-accepted-action-binding.mjs';

const policy = () => ({mode: 'DIFFERENT_VALUES', fallback_aed: 0});
function fixture() {
  return {
    wordpress: {tag_id: 'AW-999999999', conversion_label: 'TEST_ONLY', evidence_ref: 'synthetic-wp'},
    ads: {action_id: '999999999', tag_id: 'AW-999999999', conversion_label: 'TEST_ONLY',
      optimization: 'SECONDARY', count: 'ONE', value_policy: policy(), accepted_enquiry_routes: ['NATIVE_WEB'],
      custom_bidding_goal: 'EXCLUDED', source_binding: 'UNVERIFIED', evidence_ref: 'synthetic-ads'},
    decision: null, runtime_evidence: {deduplication: 'UNVERIFIED', reference: null},
  };
}
const held = result => {
  assert.equal(result.status, 'HELD_DIAGNOSTIC_ONLY'); assert.equal(result.diagnostic_only, true);
  assert.equal(result.deployment_prohibited, true); assert.equal(result.release_ready, false);
  assert.equal(result.network_calls, 0); assert.equal(result.stages.count_proves_dedup, false);
  assert.ok(result.holds.includes('PROVIDER_DEDUP_NOT_INDEPENDENTLY_VERIFIED'));
};

test('matching observations remain held for missing canonical policy, owned source and provider evidence', () => {
  const result = validate(fixture()); held(result);
  assert.equal(result.stages.identifiers, 'CONSISTENT_NOT_RUNTIME_ACCEPTANCE');
  for (const code of ['DEC05_CANONICAL_POLICY_MISSING', 'OWNED_SOURCE_EVIDENCE_MISSING', 'RUNTIME_DEDUP_EVIDENCE_MISSING']) assert.ok(result.holds.includes(code));
});

test('provided decisions, paths and reported matches never become authority or runtime acceptance', () => {
  const f = fixture(); f.decision = {action_id: f.ads.action_id, value_policy: policy(), reference: 'synthetic/owner-record'};
  f.ads.source_binding = 'REPORTED_MATCH';
  f.runtime_evidence = {deduplication: 'REPORTED_MATCH', reference: 'synthetic/provider-record'};
  const result = validate(f); held(result);
  assert.equal(result.stages.canonical, 'REPORTED_CONSISTENT_NOT_AUTHORITY_VERIFIED');
  assert.ok(result.holds.includes('DEC05_AUTHORITY_NOT_INDEPENDENTLY_VERIFIED'));
  assert.ok(result.holds.includes('OWNED_SOURCE_NOT_INDEPENDENTLY_VERIFIED'));
  const output = JSON.stringify(result);
  for (const privateValue of ['TEST_ONLY', 'AW-999999999', '999999999', 'synthetic/owner-record', 'synthetic/provider-record']) assert.equal(output.includes(privateValue), false);
});

test('tag or label mismatch and substituted canonical action produce distinct holds', () => {
  for (const field of ['tag_id', 'conversion_label']) {
    const f = fixture(); f.wordpress[field] = field === 'tag_id' ? 'AW-888888888' : 'OTHER_TEST';
    const result = validate(f); held(result); assert.equal(result.stages.identifiers, 'MISMATCH');
    assert.ok(result.holds.includes('WORDPRESS_ADS_IDENTIFIER_MISMATCH'));
  }
  const f = fixture(); f.decision = {action_id: '888888888', value_policy: policy(), reference: 'synthetic-decision'};
  assert.ok(validate(f).holds.includes('DEC05_REPORTED_POLICY_CONFLICT'));
});

test('Secondary, custom-goal exclusion and a single native route remain explicit requirements', () => {
  for (const [field, value, code] of [
    ['optimization', 'PRIMARY', 'SECONDARY_REQUIRED'], ['custom_bidding_goal', 'INCLUDED', 'CUSTOM_BIDDING_GOAL_EXCLUSION_REQUIRED'],
    ['accepted_enquiry_routes', ['NATIVE_WEB', 'GA4_IMPORT'], 'SINGLE_NATIVE_ACCEPTED_ROUTE_REQUIRED'],
    ['accepted_enquiry_routes', ['GA4_IMPORT'], 'SINGLE_NATIVE_ACCEPTED_ROUTE_REQUIRED'],
    ['accepted_enquiry_routes', [], 'SINGLE_NATIVE_ACCEPTED_ROUTE_REQUIRED'],
  ]) {
    const f = fixture(); f.ads[field] = value; const result = validate(f); held(result); assert.ok(result.holds.includes(code));
  }
});

test('unknown/conflicting value policy and reported runtime/source mismatch cannot pass', () => {
  const f = fixture(); f.ads.value_policy = {mode: 'UNSET', fallback_aed: null};
  assert.ok(validate(f).holds.includes('VALUE_POLICY_UNRESOLVED'));
  f.decision = {action_id: f.ads.action_id, value_policy: policy(), reference: 'synthetic-decision'};
  assert.ok(validate(f).holds.includes('DEC05_REPORTED_POLICY_CONFLICT'));
  f.ads.source_binding = 'REPORTED_MISMATCH'; f.runtime_evidence = {deduplication: 'REPORTED_MISMATCH', reference: 'synthetic-runtime'};
  const result = validate(f); held(result);
  assert.ok(result.holds.includes('OWNED_SOURCE_REPORTED_MISMATCH')); assert.ok(result.holds.includes('RUNTIME_DEDUP_REPORTED_MISMATCH'));
});

test('CountONE and CountEVERY are classifications, never dedup evidence', () => {
  for (const count of ['ONE', 'EVERY', 'UNVERIFIED']) { const f = fixture(); f.ads.count = count; const r = validate(f); held(r); assert.equal(r.stages.count_policy, count); }
});

test('strict bounded objects reject unknown/contact/event fields, missing fields and booleans-as-authority', () => {
  for (const mutate of [f => f.email = 'synthetic@example.invalid', f => f.ads.event_body = {},
    f => f.wordpress.approved = true, f => delete f.ads.action_id, f => f.ads.source_binding = true,
    f => f.runtime_evidence.deduplication = true, f => f.decision = true, f => f.ads.value_policy.fallback_aed = '0',
    f => f.ads.value_policy.fallback_aed = NaN, f => f.ads.value_policy.fallback_aed = Infinity,
    f => f.ads.value_policy.fallback_aed = -1, f => f.ads.value_policy.fallback_aed = 1e10,
    f => f.ads.value_policy.fallback_aed = -0, f => f.ads.action_id = 999999999,
    f => f.wordpress.conversion_label = 'TEST_ONLY\n', f => f.ads.evidence_ref = 'x'.repeat(193),
    f => f.ads.evidence_ref = 'contact@example.invalid', f => f.ads.accepted_enquiry_routes = ['NATIVE_WEB', 'NATIVE_WEB'],
    f => f.runtime_evidence = {deduplication: 'REPORTED_MATCH', reference: null}]) {
    const f = fixture(); mutate(f); assert.throws(() => validate(f));
  }
});

test('inherited, symbol, sparse-array and accessor fields are rejected without invoking accessors', () => {
  const inherited = fixture(); inherited.ads = Object.assign(Object.create({approved: true}), inherited.ads);
  assert.throws(() => validate(inherited));
  const symbol = fixture(); symbol.ads[Symbol('hidden')] = true; assert.throws(() => validate(symbol));
  const sparse = fixture(); sparse.ads.accepted_enquiry_routes = Array(1); assert.throws(() => validate(sparse));
  let called = false; const accessor = fixture();
  Object.defineProperty(accessor.ads, 'conversion_label', {get() { called = true; return 'TEST_ONLY'; }});
  assert.throws(() => validate(accessor), /ACCESSOR/); assert.equal(called, false);
  const arrayAccessor = fixture();
  Object.defineProperty(arrayAccessor.ads.accepted_enquiry_routes, '0', {get() { called = true; return 'NATIVE_WEB'; }});
  assert.throws(() => validate(arrayAccessor)); assert.equal(called, false);
});
