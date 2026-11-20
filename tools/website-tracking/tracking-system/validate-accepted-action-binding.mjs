// Strict object API, no JSON parser, file/network access, event sender or acceptance authority.
const need = (condition, code) => { if (!condition) throw new Error(code); };
function record(value, keys) {
  need(value !== null && typeof value === 'object' &&
    [Object.prototype, null].includes(Object.getPrototypeOf(value)), 'BINDING_RECORD_REQUIRED');
  const own = Reflect.ownKeys(value);
  need(own.length === keys.length && own.every(k => keys.includes(k)), 'BINDING_FIELDS_INVALID');
  for (const key of keys) need(Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), 'value'), 'BINDING_ACCESSOR_PROHIBITED');
}
function text(value, pattern) {
  need(typeof value === 'string' && value.length <= 192 && !/[\x00-\x20\x7f-\uffff]/.test(value) && pattern.test(value), 'BINDING_TEXT_INVALID');
}
const reference = value => text(value, /^[A-Za-z0-9][A-Za-z0-9._:/#-]{0,191}$/);
const choice = (value, allowed) => need(allowed.includes(value), 'BINDING_ENUM_INVALID');
function policy(value) {
  record(value, ['mode', 'fallback_aed']);
  choice(value.mode, ['DIFFERENT_VALUES', 'FIXED', 'UNSET']);
  need(value.fallback_aed === null || (typeof value.fallback_aed === 'number' &&
    Number.isFinite(value.fallback_aed) && value.fallback_aed >= 0 && value.fallback_aed <= 1e9 &&
    !Object.is(value.fallback_aed, -0)), 'BINDING_VALUE_INVALID');
  need(value.mode !== 'UNSET' || value.fallback_aed === null, 'BINDING_UNSET_VALUE_CONFLICT');
}
const samePolicy = (a, b) => a.mode === b.mode && a.fallback_aed === b.fallback_aed;

export function validateAcceptedActionBinding(input) {
  record(input, ['wordpress', 'ads', 'decision', 'runtime_evidence']);
  const {wordpress: wp, ads, decision, runtime_evidence: runtime} = input;
  record(wp, ['tag_id', 'conversion_label', 'evidence_ref']);
  record(ads, ['action_id', 'tag_id', 'conversion_label', 'optimization', 'count', 'value_policy',
    'accepted_enquiry_routes', 'custom_bidding_goal', 'source_binding', 'evidence_ref']);
  text(wp.tag_id, /^AW-[0-9]{6,15}$/); text(ads.tag_id, /^AW-[0-9]{6,15}$/);
  for (const label of [wp.conversion_label, ads.conversion_label]) text(label, /^[A-Za-z0-9_-]{5,100}$/);
  text(ads.action_id, /^[1-9][0-9]{3,19}$/); reference(wp.evidence_ref); reference(ads.evidence_ref);
  choice(ads.optimization, ['SECONDARY', 'PRIMARY', 'UNVERIFIED']);
  choice(ads.count, ['ONE', 'EVERY', 'UNVERIFIED']);
  choice(ads.custom_bidding_goal, ['EXCLUDED', 'INCLUDED', 'UNVERIFIED']);
  choice(ads.source_binding, ['UNVERIFIED', 'REPORTED_MATCH', 'REPORTED_MISMATCH']);
  policy(ads.value_policy);
  const routes = ads.accepted_enquiry_routes;
  need(Array.isArray(routes) && Object.getPrototypeOf(routes) === Array.prototype &&
    routes.length <= 2 && Reflect.ownKeys(routes).length === routes.length + 1, 'BINDING_ROUTES_INVALID');
  for (let i = 0; i < routes.length; i++) {
    need(Object.hasOwn(Object.getOwnPropertyDescriptor(routes, String(i)) ?? {}, 'value'), 'BINDING_ROUTES_INVALID');
    choice(routes[i], ['NATIVE_WEB', 'GA4_IMPORT']);
  }
  need(new Set(routes).size === routes.length, 'BINDING_DUPLICATE_ROUTE');
  if (decision !== null) {
    record(decision, ['action_id', 'value_policy', 'reference']);
    text(decision.action_id, /^[1-9][0-9]{3,19}$/); policy(decision.value_policy); reference(decision.reference);
  }
  record(runtime, ['deduplication', 'reference']);
  choice(runtime.deduplication, ['UNVERIFIED', 'REPORTED_MATCH', 'REPORTED_MISMATCH']);
  if (runtime.reference !== null) reference(runtime.reference);
  need(runtime.deduplication === 'UNVERIFIED' || runtime.reference !== null, 'BINDING_RUNTIME_REFERENCE_MISSING');

  const holds = ['DIAGNOSTIC_INPUTS_NOT_INDEPENDENT_AUTHORITY', 'OWNED_SOURCE_NOT_INDEPENDENTLY_VERIFIED',
    'PROVIDER_DEDUP_NOT_INDEPENDENTLY_VERIFIED', 'BROWSER_FRAME_AND_RELEASE_ACCEPTANCE_REQUIRED'];
  const identifiers = wp.tag_id === ads.tag_id && wp.conversion_label === ads.conversion_label;
  if (!identifiers) holds.push('WORDPRESS_ADS_IDENTIFIER_MISMATCH');
  const route = routes.length === 1 && routes[0] === 'NATIVE_WEB';
  if (!route) holds.push('SINGLE_NATIVE_ACCEPTED_ROUTE_REQUIRED');
  if (ads.optimization !== 'SECONDARY') holds.push('SECONDARY_REQUIRED');
  if (ads.custom_bidding_goal !== 'EXCLUDED') holds.push('CUSTOM_BIDDING_GOAL_EXCLUSION_REQUIRED');
  if (ads.value_policy.mode === 'UNSET' || ads.value_policy.fallback_aed === null) holds.push('VALUE_POLICY_UNRESOLVED');
  let canonical = 'MISSING';
  if (decision === null) holds.push('DEC05_CANONICAL_POLICY_MISSING');
  else if (decision.action_id !== ads.action_id || !samePolicy(decision.value_policy, ads.value_policy)) {
    canonical = 'REPORTED_POLICY_CONFLICT'; holds.push('DEC05_REPORTED_POLICY_CONFLICT');
  } else {
    canonical = 'REPORTED_CONSISTENT_NOT_AUTHORITY_VERIFIED'; holds.push('DEC05_AUTHORITY_NOT_INDEPENDENTLY_VERIFIED');
  }
  if (ads.source_binding === 'UNVERIFIED') holds.push('OWNED_SOURCE_EVIDENCE_MISSING');
  if (ads.source_binding === 'REPORTED_MISMATCH') holds.push('OWNED_SOURCE_REPORTED_MISMATCH');
  if (runtime.deduplication === 'UNVERIFIED') holds.push('RUNTIME_DEDUP_EVIDENCE_MISSING');
  if (runtime.deduplication === 'REPORTED_MISMATCH') holds.push('RUNTIME_DEDUP_REPORTED_MISMATCH');

  // Deliberately return static classifications only, never labels, evidence paths, IDs or event payloads.
  return Object.freeze({status: 'HELD_DIAGNOSTIC_ONLY', diagnostic_only: true, deployment_prohibited: true,
    release_ready: false, network_calls: 0, stages: Object.freeze({
      identifiers: identifiers ? 'CONSISTENT_NOT_RUNTIME_ACCEPTANCE' : 'MISMATCH',
      route: route ? 'SINGLE_NATIVE_REPORTED' : 'MISSING_OR_MULTIPLE_OR_IMPORT', canonical,
      owned_source: ads.source_binding, provider_dedup: runtime.deduplication,
      count_policy: ads.count, count_proves_dedup: false,
    }), holds: Object.freeze(holds)});
}
