/**
 * PRIVATE offline attribution contract: no browser storage, DOM, network or writes.
 *
 * Implements separate first/latest permitted acquisition snapshots, not a Google
 * attribution model. Current instructions require SESSION-ONLY click identifiers:
 * older 180-day attribution-persistence proposals are NOT implemented. The
 * separately approved 180-day preference-validity policy does not extend this
 * state beyond its session. Withdrawal drops the reducer's owned state at once.
 *
 * Registry values and verified consent/evidence are TRUSTED TEST INPUTS, not
 * cryptographic authentication. A reviewed server/browser bridge must supply
 * actual permission, session and acquisition authority before integration.
 * Unknown URLs, self-referrers or UTMs never establish an acquisition here.
 * Optional metadata retains exactly the six specified UTM fields and three
 * Google ID fields, under the same advertising-purpose/session-only boundary.
 * UTM strings may contain contact/free text: these PRIVATE bounded fields are
 * NOT a PII-safety assertion. No raw URL/referrer fields are accepted; obvious
 * URL-valued UTM strings also reject. There is no decoding, trimming or truncation.
 *
 * Returned receipt contexts are PRIVATE and are not wire-1 compatible payloads
 * or GA4/Ads payloads. Never spread them into analytics events. Enquiry intake
 * remains outside this module and does not require consent or a click ID.
 * Browser persistence, main-site integration and WT-017 acceptance remain open.
 */
import {captureClickIds, permissionAllowed} from './contract.mjs';

const ID = /^[A-Za-z][A-Za-z0-9._:-]{0,127}$/;
const UUID = /^bsre-event-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const CONTROL = /\p{C}/u;
const PERMISSION_FIELDS = ['analytics', 'advertising', 'ad_user_data', 'expires_at'];
const INPUT_TOUCH_FIELDS = ['acquisition_id', 'observed_at', 'campaign_key', 'landing_page_id', 'click_ids', 'evidence'];
const BASE_TOUCH_FIELDS = [...INPUT_TOUCH_FIELDS, 'metadata'];
const TOUCH_FIELDS = [...BASE_TOUCH_FIELDS, 'original_permissions'];
const UTM_FIELDS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_id', 'utm_term', 'utm_content'];
const GOOGLE_ID_FIELDS = ['google_campaign_id', 'ad_group_id', 'creative_id'];
// Conservative supported-input bounds, not claims about provider maximums or
// genuine resource identities. In particular, IDs never pass through Number().
const MAX_UTM_CODE_UNITS = 512;
const MAX_GOOGLE_ID_DIGITS = 32;

function need(ok, code) { if (!ok) throw new Error(code); }
function exact(value, keys) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value, key));
}
function identifier(value) { return typeof value === 'string' && ID.test(value) && !CONTROL.test(value); }
function stamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) return NaN;
  const time = Date.parse(value);
  if (!Number.isFinite(time)) return NaN;
  const canonical = value.endsWith('.000Z') || /\.\d{3}Z$/.test(value) ? value : value.replace(/Z$/, '.000Z');
  return new Date(time).toISOString() === canonical ? time : NaN;
}
function immutable(value) {
  const copy = structuredClone(value);
  function freeze(item) {
    if (item && typeof item === 'object') { Object.values(item).forEach(freeze); Object.freeze(item); }
    return item;
  }
  return freeze(copy);
}
function permitted(consent, now) {
  return Number.isFinite(stamp(consent?.expires_at)) && permissionAllowed(consent, 'advertising', now);
}
function options(value) {
  need(exact(value, ['session_id', 'consent', 'registry', 'now']), 'ATTRIBUTION_OPTIONS_INVALID');
  need(identifier(value.session_id), 'ATTRIBUTION_SESSION_INVALID');
  need(Number.isSafeInteger(value.now) && value.now >= 0 && value.now <= 8640000000000000,
    'ATTRIBUTION_CLOCK_INVALID');
  need(value.registry && typeof value.registry.resolve === 'function', 'ATTRIBUTION_REGISTRY_REQUIRED');
}
function binding(value, registry) {
  need(typeof value.campaign_key === 'string' && /^BSRE-C\d{4}$/.test(value.campaign_key) &&
    typeof value.landing_page_id === 'string' && /^BSRE-LP\d{4}$/.test(value.landing_page_id),
  'ATTRIBUTION_CAMPAIGN_BINDING_INVALID');
  const page = registry.resolve(value.campaign_key);
  need(page?.context?.campaign_key === value.campaign_key &&
    page.context.landing_page_id === value.landing_page_id, 'ATTRIBUTION_CAMPAIGN_NOT_REVIEWED');
}
function privateMetadata(value) {
  need(value !== null && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).every(key => [...UTM_FIELDS, ...GOOGLE_ID_FIELDS].includes(key)),
  'ATTRIBUTION_PRIVATE_METADATA_FIELDS_INVALID');
  const output = {};
  for (const key of [...UTM_FIELDS, ...GOOGLE_ID_FIELDS]) {
    if (!Object.hasOwn(value, key)) continue;
    const cell = value[key];
    need(typeof cell === 'string' && cell.length > 0 && !CONTROL.test(cell),
      'ATTRIBUTION_PRIVATE_METADATA_VALUE_INVALID');
    if (GOOGLE_ID_FIELDS.includes(key)) {
      need(cell.length <= MAX_GOOGLE_ID_DIGITS && /^[0-9]+$/.test(cell),
        'ATTRIBUTION_PRIVATE_GOOGLE_ID_INVALID');
    } else {
      need(cell.length <= MAX_UTM_CODE_UNITS, 'ATTRIBUTION_PRIVATE_METADATA_OVERSIZED');
      // This is only a supported-input guard. Encoded/free-form text remains
      // private and unreviewed; no heuristic certifies it safe for disclosure.
      need(!/\b[a-z][a-z0-9+.-]*:\/\/|(?:^|\s)www\.|^\//i.test(cell),
        'ATTRIBUTION_URL_METADATA_NOT_SUPPORTED');
    }
    output[key] = cell;
  }
  return output;
}
function touchBase(value, registry, consent, now) {
  need(identifier(value.acquisition_id), 'ATTRIBUTION_ACQUISITION_ID_INVALID');
  const at = stamp(value.observed_at);
  need(Number.isFinite(at) && at <= now, 'ATTRIBUTION_ACQUISITION_TIME_INVALID');
  binding(value, registry);
  need(exact(value.evidence, ['source', 'verified', 'reference']) &&
    value.evidence.source === 'validated_external_acquisition' && value.evidence.verified === true &&
    identifier(value.evidence.reference), 'ATTRIBUTION_EXTERNAL_EVIDENCE_REQUIRED');
  // Existing supported-input rule preserves exact ID bytes and rejects excess,
  // controls and unsupported fields; it never trims, lowercases or truncates.
  const captured = captureClickIds(value.click_ids, consent, now);
  const clickIds = Object.fromEntries(['gclid', 'gbraid', 'wbraid']
    .filter(key => Object.hasOwn(captured, key)).map(key => [key, captured[key]]));
  return {acquisition_id: value.acquisition_id, observed_at: new Date(at).toISOString(),
    campaign_key: value.campaign_key, landing_page_id: value.landing_page_id,
    click_ids: clickIds, metadata: Object.hasOwn(value, 'metadata') ? privateMetadata(value.metadata) : {},
    evidence: {source: value.evidence.source,
      verified: true, reference: value.evidence.reference}};
}
function storedTouch(value, registry, consent, now) {
  need(exact(value, TOUCH_FIELDS), 'ATTRIBUTION_TOUCH_INVALID');
  const base = touchBase(value, registry, consent, now);
  const p = value.original_permissions;
  need(exact(p, PERMISSION_FIELDS) && typeof p.analytics === 'boolean' && p.advertising === true &&
    typeof p.ad_user_data === 'boolean' && Number.isFinite(stamp(p.expires_at)) &&
    stamp(p.expires_at) > stamp(value.observed_at), 'ATTRIBUTION_ORIGINAL_PERMISSION_INVALID');
  return {...base, original_permissions: {analytics: p.analytics, advertising: true,
    ad_user_data: p.ad_user_data, expires_at: new Date(stamp(p.expires_at)).toISOString()}};
}
function activeState(previous, {session_id, consent, registry, now}) {
  if (previous === null || previous === undefined) return null;
  // A new session must not rehydrate or even inspect old private touches.
  if (previous?.session_id !== session_id) return null;
  need(exact(previous, ['schema_version', 'session_id', 'first_touch', 'latest_touch']) &&
    previous.schema_version === 1, 'ATTRIBUTION_STATE_INVALID');
  const first = storedTouch(previous.first_touch, registry, consent, now);
  const latest = storedTouch(previous.latest_touch, registry, consent, now);
  need(stamp(first.observed_at) <= stamp(latest.observed_at), 'ATTRIBUTION_TOUCH_ORDER_INVALID');
  if (stamp(first.original_permissions.expires_at) <= now || stamp(latest.original_permissions.expires_at) <= now) return null;
  if (first.acquisition_id === latest.acquisition_id)
    need(JSON.stringify(first) === JSON.stringify(latest), 'ATTRIBUTION_ACQUISITION_CONFLICT');
  return {schema_version: 1, session_id, first_touch: first, latest_touch: latest};
}
function sameAcquisition(stored, incoming) {
  // Current grants cannot upgrade the original grant on a retry.
  return BASE_TOUCH_FIELDS.every(key => JSON.stringify(stored[key]) === JSON.stringify(incoming[key]));
}

export function reduceAttribution(previous, action, configuration) {
  need(action && ['acquisition', 'internal_navigation', 'withdrawal'].includes(action.type), 'ATTRIBUTION_ACTION_INVALID');
  need(exact(action, action.type === 'acquisition' ? ['type', 'acquisition'] : ['type']), 'ATTRIBUTION_ACTION_INVALID');
  // Withdrawal is unconditional: unavailable registry/session/permission input
  // cannot prevent the caller from clearing its owned reducer slot.
  if (action.type === 'withdrawal') return null;
  options(configuration);
  // No state is returned on revocation or any unavailable/unverified permission.
  if (!permitted(configuration.consent, configuration.now)) return null;
  const state = activeState(previous, configuration);
  if (action.type === 'internal_navigation') return immutable(state);
  need(exact(action.acquisition, action.acquisition && Object.hasOwn(action.acquisition, 'metadata')
    ? BASE_TOUCH_FIELDS : INPUT_TOUCH_FIELDS), 'ATTRIBUTION_ACQUISITION_INVALID');
  const incoming = touchBase(action.acquisition, configuration.registry, configuration.consent, configuration.now);
  if (state) {
    const existing = [state.first_touch, state.latest_touch].find(t => t.acquisition_id === incoming.acquisition_id);
    if (existing) {
      need(sameAcquisition(existing, incoming), 'ATTRIBUTION_ACQUISITION_CONFLICT');
      return immutable(state);
    }
    need(stamp(incoming.observed_at) >= stamp(state.latest_touch.observed_at), 'ATTRIBUTION_OUT_OF_ORDER_ACQUISITION');
  }
  const touch = {...incoming, original_permissions: {
    analytics: configuration.consent.analytics, advertising: true,
    ad_user_data: configuration.consent.ad_user_data,
    expires_at: new Date(stamp(configuration.consent.expires_at)).toISOString(),
  }};
  return immutable({schema_version: 1, session_id: configuration.session_id,
    first_touch: state?.first_touch ?? touch, latest_touch: touch});
}

export function acceptedReceiptContext(previous, receipt, evidence, configuration) {
  options(configuration);
  need(exact(receipt, ['accepted', 'durable', 'lead_id', 'event_id', 'original_analytics',
    'original_advertising', 'original_ad_user_data']) && receipt.accepted === true && receipt.durable === true &&
    identifier(receipt.lead_id) && typeof receipt.event_id === 'string' && UUID.test(receipt.event_id) &&
    ['original_analytics', 'original_advertising', 'original_ad_user_data'].every(k => typeof receipt[k] === 'boolean'),
  'ATTRIBUTION_DURABLE_RECEIPT_REQUIRED');
  need(exact(evidence, ['source', 'verified', 'reference']) && evidence.source === 'server_confirmed' &&
    evidence.verified === true && identifier(evidence.reference), 'ATTRIBUTION_ACCEPTANCE_EVIDENCE_REQUIRED');
  // Return the next owned state explicitly so expiry/session changes cannot
  // leave a stale reference in the caller's reducer slot. Caller owns disposal
  // of prior immutable snapshots; JavaScript cannot erase arbitrary old copies.
  const next = reduceAttribution(previous, {type: 'internal_navigation'}, configuration);
  return immutable({scope: 'PRIVATE_ACCEPTED_RECEIPT_ATTRIBUTION_SESSION_ONLY',
    status: 'private_context_only_not_delivered', next_state: next,
    receipt: structuredClone(receipt),
    attribution: receipt.original_advertising && next ? {
      first_touch: next.first_touch, latest_touch: next.latest_touch,
    } : null,
    resource_ids_verified: false, deployment_authorized: false, network_calls: 0});
}
