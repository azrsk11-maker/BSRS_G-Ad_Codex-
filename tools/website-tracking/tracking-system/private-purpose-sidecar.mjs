/** Versioned PRIVATE accepted-receipt sidecar, never wire-v1/GA4/Ads payload.
 * In-memory development consumer only: no browser producer/storage or delivery.
 * Current/original decisions are purpose-specific. Caller owns replacing returned
 * state and disposing prior immutable copies. Production needs authenticated
 * permissions/receipts, durable idempotency, protected lifecycle and integration.
 */
import {createHash} from 'node:crypto';
import {permissionAllowed} from './contract.mjs';
import {acceptedReceiptContext, reduceAttribution} from './attribution-state.mjs';
import {analyticsAcceptedReceiptContext, reduceAnalyticsAttribution} from './analytics-attribution-state.mjs';

function need(ok, code) { if (!ok) throw new Error(code); }
const ID = /^[A-Za-z][A-Za-z0-9._:-]{0,127}$/;
const CONTROL = /\p{C}/u;
function exact(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const actual = Reflect.ownKeys(value);
  return actual.length === keys.length && actual.every(key => typeof key === 'string' && keys.includes(key) &&
    Object.getOwnPropertyDescriptor(value, key)?.enumerable === true &&
    Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), 'value'));
}
function stamp(value) {
  const at = typeof value === 'string' ? Date.parse(value) : NaN;
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value) &&
    Number.isFinite(at) && new Date(at).toISOString() === (value.includes('.') ? value : value.replace('Z', '.000Z')) ? at : NaN;
}
function identifier(value) { return typeof value === 'string' && ID.test(value) && !CONTROL.test(value); }
function canonical(value) {
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical(value[key])).join(',') + '}';
}
function digest(value) { return createHash('sha256').update(canonical(value)).digest('hex'); }
function immutable(value) {
  const clone = structuredClone(value);
  const freeze = item => { if (item && typeof item === 'object') { Object.values(item).forEach(freeze); Object.freeze(item); } return item; };
  return freeze(clone);
}
function states(value) {
  need(exact(value, ['analytics', 'advertising']), 'PURPOSE_SIDECAR_STATE_REQUIRED');
}
function adOptions(configuration) {
  need(exact(configuration, ['session_id', 'consent', 'registry', 'sources', 'now']) &&
    identifier(configuration.session_id) && Number.isSafeInteger(configuration.now) &&
    configuration.now >= 0 && configuration.now <= 8640000000000000, 'PURPOSE_SIDECAR_OPTIONS_INVALID');
  const {session_id, consent, registry, now} = configuration;
  return {session_id, consent, registry, now};
}
function permitted(consent, purpose, now) {
  if (!exact(consent, ['verified', 'server_eligible', 'expires_at', 'analytics', 'advertising', 'ad_user_data', 'personalization', 'qa', 'admin'])) return false;
  return Number.isFinite(stamp(consent?.expires_at)) && permissionAllowed(consent, purpose, now);
}
function lifecycleObservation(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const cell = key => {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return descriptor?.enumerable === true && Object.hasOwn(descriptor, 'value') ? descriptor.value : undefined;
  };
  const session_id = cell('session_id'), now = cell('now');
  return identifier(session_id) && Number.isSafeInteger(now) && now >= 0 && now <= 8640000000000000
    ? {session_id, now, consent: cell('consent')} : null;
}
function capturedEnvelope(value, receipt, evidence, configuration) {
  need(exact(value, ['schema_version', 'source', 'verified', 'reference', 'lead_id', 'event_id', 'captured_at',
    'session_id', 'captured_consent', 'captured_states']) && value.schema_version === 1 &&
    value.source === 'server_bound_original_intake_attribution' && value.verified === true && identifier(value.reference) &&
    value.lead_id === receipt.lead_id && value.event_id === receipt.event_id && identifier(value.session_id) &&
    Number.isFinite(stamp(value.captured_at)) && stamp(value.captured_at) <= configuration.now,
  'PURPOSE_SIDECAR_ORIGINAL_CAPTURE_REQUIRED');
  const choice = value.captured_consent;
  need(exact(choice, ['verified', 'server_eligible', 'expires_at', 'analytics', 'advertising', 'ad_user_data', 'personalization', 'qa', 'admin']) &&
    ['verified', 'server_eligible', 'analytics', 'advertising', 'ad_user_data', 'personalization', 'qa', 'admin'].every(key => typeof choice[key] === 'boolean') &&
    Number.isFinite(stamp(choice.expires_at)) && choice.analytics === receipt.original_analytics &&
    choice.advertising === receipt.original_advertising && choice.ad_user_data === receipt.original_ad_user_data,
  'PURPOSE_SIDECAR_CAPTURE_PERMISSION_MISMATCH');
  states(value.captured_states);
  const original = {...configuration, now: stamp(value.captured_at), session_id: value.session_id, consent: choice};
  for (const purpose of ['analytics', 'advertising']) {
    const state = value.captured_states[purpose];
    need(state === null || state?.session_id === value.session_id, 'PURPOSE_SIDECAR_CAPTURE_SESSION_MISMATCH');
    need(permitted(choice, purpose, original.now) || state === null, 'PURPOSE_SIDECAR_CAPTURE_PERMISSION_MISMATCH');
  }
  const advertising = acceptedReceiptContext(value.captured_states.advertising, receipt, evidence, adOptions(original));
  const analytics = analyticsAcceptedReceiptContext(value.captured_states.analytics, receipt, evidence, original);
  // Expired or unrecognized snapshots must not silently become a valid empty
  // capture envelope. A real producer must explicitly record absence as null.
  need((value.captured_states.analytics === null || analytics.next_state !== null) &&
    (value.captured_states.advertising === null || advertising.next_state !== null), 'PURPOSE_SIDECAR_CAPTURE_HISTORY_INVALID');
  const captured = {analytics: analytics.next_state, advertising: advertising.next_state};
  const binding = {schema_version: 1, reference: value.reference, captured_at: new Date(original.now).toISOString(), session_id: value.session_id,
    snapshot_digest: digest({captured, captured_consent: choice, captured_at: new Date(original.now).toISOString(),
      session_id: value.session_id, source: value.source, reference: value.reference, lead_id: value.lead_id, event_id: value.event_id})};
  return {captured, binding};
}
export class PrivatePurposeSidecarLedger {
  #records = new Map();
  #leads = new Map();
  #lastNow = -1;

  contextCounts() {
    return Object.freeze({receipt_slots: this.#records.size,
      analytics_contexts: [...this.#records.values()].filter(row => row.captured.analytics !== null).length,
      advertising_contexts: [...this.#records.values()].filter(row => row.captured.advertising !== null).length});
  }

  withdraw(owned, purpose) {
    need(['analytics', 'advertising'].includes(purpose), 'PURPOSE_SIDECAR_WITHDRAWAL_INVALID');
    // Neither unavailable configuration nor an unavailable receiver can prevent
    // clearing this consumer's owned purpose. Previous returned references are
    // immutable copies and cannot be retroactively erased by JavaScript.
    for (const entry of this.#records.values()) entry.captured[purpose] = null;
    states(owned); // Invalid caller state cannot prevent the cache withdrawal.
    return immutable({...owned, [purpose]: purpose === 'analytics'
      ? reduceAnalyticsAttribution(owned.analytics, {type: 'withdrawal'}, null)
      : reduceAttribution(owned.advertising, {type: 'withdrawal'}, null)});
  }

  prepare(owned, receipt, evidence, configuration, original_capture) {
    const observation = lifecycleObservation(configuration);
    if (observation === null) {
      for (const entry of this.#records.values()) entry.captured = {analytics: null, advertising: null};
      throw new Error('PURPOSE_SIDECAR_OPTIONS_INVALID');
    }
    // Observe common session/clock/permission before unrelated receipt, source or
    // other-purpose validation may fail. Only conservative clearing happens here.
    // Sweep ALL receipt slots, preventing A→B→A or expiry/regrant resurrection.
    for (const entry of this.#records.values()) for (const purpose of ['analytics', 'advertising']) {
      const state = entry.captured[purpose];
      const permission = touch => purpose === 'analytics' ? touch.original_analytics : touch.original_permissions;
      if (!permitted(observation.consent, purpose, observation.now) || state &&
        (state.session_id !== observation.session_id || [state.first_touch, state.latest_touch].some(touch =>
          !Number.isFinite(stamp(permission(touch)?.expires_at)) || stamp(permission(touch).expires_at) <= observation.now))) entry.captured[purpose] = null;
    }
    need(observation.now >= this.#lastNow, 'PURPOSE_SIDECAR_CLOCK_REGRESSION');
    this.#lastNow = observation.now;
    const advertisingConfig = adOptions(configuration);
    states(owned);
    // Reuse unchanged advertising receipt/eligibility validation. Analytics does
    // not inherit advertising's grant or click IDs, even when both are allowed.
    const advertising = acceptedReceiptContext(owned.advertising, receipt, evidence, advertisingConfig);
    const analytics = analyticsAcceptedReceiptContext(owned.analytics, receipt, evidence, configuration);
    const next_state = {analytics: analytics.next_state, advertising: advertising.next_state};
    // Distinct immutable original-intake evidence is mandatory. Current owned
    // navigation is never substituted for a missing original captured history.
    const canonicalReceipt = Object.fromEntries(['accepted', 'durable', 'lead_id', 'event_id',
      'original_analytics', 'original_advertising', 'original_ad_user_data'].map(key => [key, receipt[key]]));
    const receiptFingerprint = digest({receipt: canonicalReceipt, evidence_reference: evidence.reference});
    const prior = this.#records.get(receipt.event_id);
    need(!prior || prior.receiptFingerprint === receiptFingerprint, 'PURPOSE_SIDECAR_RECEIPT_CONFLICT');
    const original = capturedEnvelope(original_capture, receipt, evidence, configuration);
    // Store only bounded hashes/opaque bindings, not raw touches/UTMs/ad IDs in
    // retry fingerprints. Hashes establish consistency, never authentication.
    const fingerprint = digest({receipt: canonicalReceipt, evidence_reference: evidence.reference, capture_binding: original.binding});
    need(!this.#leads.has(receipt.lead_id) || this.#leads.get(receipt.lead_id) === receipt.event_id, 'PURPOSE_SIDECAR_LEAD_EVENT_CONFLICT');
    need(!prior || prior.fingerprint === fingerprint, 'PURPOSE_SIDECAR_RECEIPT_CONFLICT');
    need(prior || this.#records.size < 10000, 'PURPOSE_SIDECAR_LEDGER_CAPACITY');

    const entry = prior ?? {fingerprint, receiptFingerprint, binding: original.binding, captured: structuredClone(original.captured)};
    const cachedAdvertising = acceptedReceiptContext(entry.captured.advertising, receipt, evidence, advertisingConfig);
    const cachedAnalytics = analyticsAcceptedReceiptContext(entry.captured.analytics, receipt, evidence, configuration);
    // Session/expiry invalidation is permanent in this in-memory receipt slot.
    entry.captured = {analytics: cachedAnalytics.next_state, advertising: cachedAdvertising.next_state};
    const sidecar = immutable({schema_version: 1, scope: 'PRIVATE_ACCEPTED_RECEIPT_PURPOSE_SIDECAR_ONLY',
      receipt: canonicalReceipt, capture_binding: entry.binding, analytics: cachedAnalytics.attribution, advertising: cachedAdvertising.attribution,
      wire_version_1_modified: false, deployment_authorized: false, network_calls: 0});
    this.#records.set(receipt.event_id, entry); this.#leads.set(receipt.lead_id, receipt.event_id); this.#lastNow = configuration.now;
    return immutable({status: prior ? 'same_receipt_context_preserved_not_delivered' : 'private_sidecar_prepared_not_delivered',
      next_state, sidecar});
  }
}
