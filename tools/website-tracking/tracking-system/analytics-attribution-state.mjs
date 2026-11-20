/** Pure PRIVATE analytics-purpose context. No browser producer/storage/SDK/network.
 * Catalog, registry, permission and evidence are trusted test inputs, not authentication.
 * Raw URLs/referrers/free-form UTMs/ad IDs are never admitted. An exact reviewed
 * business-code catalog narrows metadata; syntax alone cannot prove privacy.
 */
import {permissionAllowed} from './contract.mjs';
import {acceptedReceiptContext} from './attribution-state.mjs';

const ID = /^[A-Za-z][A-Za-z0-9._:-]{0,127}$/;
const CODE = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const CONTROL = /\p{C}/u;
const UTM = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_id', 'utm_term', 'utm_content'];
const ACQUISITION = ['acquisition_id', 'observed_at', 'campaign_key', 'landing_page_id', 'source_key', 'metadata', 'evidence'];
const TOUCH = [...ACQUISITION, 'source_version', 'original_analytics'];
function need(ok, code) { if (!ok) throw new Error(code); }
function fields(value, allowed, complete = true) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const keys = Reflect.ownKeys(value);
  return (!complete || keys.length === allowed.length) && keys.every(key => typeof key === 'string' &&
    allowed.includes(key) && Object.getOwnPropertyDescriptor(value, key)?.enumerable === true &&
    Object.hasOwn(Object.getOwnPropertyDescriptor(value, key), 'value'));
}
function stamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/.test(value)) return NaN;
  const result = Date.parse(value);
  return Number.isFinite(result) && new Date(result).toISOString() ===
    (value.includes('.') ? value : value.replace('Z', '.000Z')) ? result : NaN;
}
function immutable(value) {
  const clone = structuredClone(value);
  const freeze = item => { if (item && typeof item === 'object') { Object.values(item).forEach(freeze); Object.freeze(item); } return item; };
  return freeze(clone);
}
function identifier(value) { return typeof value === 'string' && ID.test(value) && !CONTROL.test(value); }
function businessCode(value) { return typeof value === 'string' && CODE.test(value) && !CONTROL.test(value); }
function metadata(value) {
  need(fields(value, UTM, false), 'ANALYTICS_METADATA_FIELDS_INVALID');
  const output = {};
  for (const key of UTM) if (Object.hasOwn(value, key)) {
    need(businessCode(value[key]), 'ANALYTICS_REVIEWED_SOURCE_CODE_REQUIRED');
    output[key] = value[key];
  }
  return output;
}
export function createAnalyticsSources(records) {
  need(Array.isArray(records) && records.length > 0 && records.length <= 4096, 'ANALYTICS_SOURCE_CATALOG_REQUIRED');
  const sources = new Map();
  for (const row of records) {
    need(fields(row, ['source_key', 'source_version', 'campaign_key', 'landing_page_id', 'metadata', 'review_reference']) &&
      businessCode(row.source_key) && !sources.has(row.source_key) &&
      typeof row.source_version === 'string' && /^\d{1,5}\.\d{1,5}\.\d{1,5}$/.test(row.source_version) && !CONTROL.test(row.source_version) &&
      typeof row.campaign_key === 'string' && /^BSRE-C\d{4}$/.test(row.campaign_key) && !CONTROL.test(row.campaign_key) &&
      typeof row.landing_page_id === 'string' && /^BSRE-LP\d{4}$/.test(row.landing_page_id) && !CONTROL.test(row.landing_page_id) &&
      identifier(row.review_reference), 'ANALYTICS_SOURCE_CATALOG_ROW_INVALID');
    sources.set(row.source_key, immutable({...row, metadata: metadata(row.metadata)}));
  }
  return Object.freeze({resolve(key) { const row = sources.get(key); return row ? immutable(row) : null; }});
}
function options(value) {
  need(fields(value, ['session_id', 'consent', 'registry', 'sources', 'now']) && identifier(value.session_id) &&
    Number.isSafeInteger(value.now) && value.now >= 0 && value.now <= 8640000000000000 &&
    typeof value.registry?.resolve === 'function' && typeof value.sources?.resolve === 'function',
  'ANALYTICS_ATTRIBUTION_OPTIONS_INVALID');
}
function base(value, configuration) {
  const {registry, sources, now} = configuration;
  need(identifier(value.acquisition_id) && Number.isFinite(stamp(value.observed_at)) && stamp(value.observed_at) <= now,
    'ANALYTICS_ACQUISITION_TIME_OR_ID_INVALID');
  const page = registry.resolve(value.campaign_key), source = sources.resolve(value.source_key);
  need(page?.context?.campaign_key === value.campaign_key && page.context.landing_page_id === value.landing_page_id &&
    source?.campaign_key === value.campaign_key && source.landing_page_id === value.landing_page_id,
  'ANALYTICS_REVIEWED_SOURCE_BINDING_REQUIRED');
  need(fields(value.evidence, ['source', 'verified', 'reference']) && value.evidence.source === 'validated_external_acquisition' &&
    value.evidence.verified === true && identifier(value.evidence.reference), 'ANALYTICS_EXTERNAL_EVIDENCE_REQUIRED');
  const safe = metadata(value.metadata);
  need(Object.keys(safe).every(key => Object.hasOwn(source.metadata, key) && safe[key] === source.metadata[key]),
    'ANALYTICS_METADATA_NOT_REVIEWED');
  return {acquisition_id: value.acquisition_id, observed_at: new Date(stamp(value.observed_at)).toISOString(),
    campaign_key: value.campaign_key, landing_page_id: value.landing_page_id, source_key: value.source_key,
    metadata: safe, evidence: {source: value.evidence.source, verified: true, reference: value.evidence.reference},
    source_version: source.source_version};
}
function stored(value, configuration) {
  need(fields(value, TOUCH), 'ANALYTICS_STORED_TOUCH_INVALID');
  const rebuilt = base(value, configuration), original = value.original_analytics;
  need(value.source_version === rebuilt.source_version && fields(original, ['granted', 'expires_at']) &&
    original.granted === true && Number.isFinite(stamp(original.expires_at)) &&
    stamp(original.expires_at) > stamp(value.observed_at), 'ANALYTICS_ORIGINAL_PERMISSION_OR_SOURCE_INVALID');
  return {...rebuilt, original_analytics: {granted: true, expires_at: new Date(stamp(original.expires_at)).toISOString()}};
}
function active(previous, configuration) {
  if (previous === null || previous === undefined || previous.session_id !== configuration.session_id) return null;
  need(fields(previous, ['schema_version', 'purpose', 'session_id', 'first_touch', 'latest_touch']) &&
    previous.schema_version === 1 && previous.purpose === 'analytics', 'ANALYTICS_STATE_INVALID');
  const first = stored(previous.first_touch, configuration), latest = stored(previous.latest_touch, configuration);
  need(stamp(first.observed_at) <= stamp(latest.observed_at), 'ANALYTICS_TOUCH_ORDER_INVALID');
  if (stamp(first.original_analytics.expires_at) <= configuration.now || stamp(latest.original_analytics.expires_at) <= configuration.now) return null;
  if (first.acquisition_id === latest.acquisition_id) need(JSON.stringify(first) === JSON.stringify(latest), 'ANALYTICS_ACQUISITION_CONFLICT');
  return {schema_version: 1, purpose: 'analytics', session_id: configuration.session_id, first_touch: first, latest_touch: latest};
}
export function reduceAnalyticsAttribution(previous, action, configuration) {
  need(action && ['acquisition', 'internal_navigation', 'withdrawal'].includes(action.type) &&
    fields(action, action.type === 'acquisition' ? ['type', 'acquisition'] : ['type']), 'ANALYTICS_ACTION_INVALID');
  if (action.type === 'withdrawal') return null; // Independent of unavailable intake/configuration.
  options(configuration);
  if (!Number.isFinite(stamp(configuration.consent?.expires_at)) ||
    !permissionAllowed(configuration.consent, 'analytics', configuration.now)) return null;
  const state = active(previous, configuration);
  if (action.type === 'internal_navigation') return immutable(state);
  need(fields(action.acquisition, ACQUISITION), 'ANALYTICS_ACQUISITION_FIELDS_INVALID');
  const incoming = base(action.acquisition, configuration);
  if (state) {
    const existing = [state.first_touch, state.latest_touch].find(t => t.acquisition_id === incoming.acquisition_id);
    if (existing) {
      need(Object.keys(incoming).every(key => JSON.stringify(incoming[key]) === JSON.stringify(existing[key])), 'ANALYTICS_ACQUISITION_CONFLICT');
      return immutable(state); // Never upgrade an originally captured grant on a retry.
    }
    need(stamp(incoming.observed_at) >= stamp(state.latest_touch.observed_at), 'ANALYTICS_OUT_OF_ORDER_ACQUISITION');
  }
  // Missing/cleared history cannot be reconstructed under a later grant. Known
  // immutable retries were handled above. Delayed fresh observations need an
  // authenticated original-capture adapter and are deliberately unsupported.
  need(stamp(incoming.observed_at) === configuration.now, 'ANALYTICS_FRESH_CAPTURE_TIME_REQUIRED');
  const touch = {...incoming, original_analytics: {granted: true, expires_at: new Date(stamp(configuration.consent.expires_at)).toISOString()}};
  return immutable({schema_version: 1, purpose: 'analytics', session_id: configuration.session_id,
    first_touch: state?.first_touch ?? touch, latest_touch: touch});
}

export function analyticsAcceptedReceiptContext(previous, receipt, evidence, configuration) {
  // Reuse the unchanged receipt validator with no advertising state; this does
  // not require advertising permission or promote any advertising context.
  const {session_id, consent, registry, now} = configuration ?? {};
  acceptedReceiptContext(null, receipt, evidence, {session_id, consent, registry, now});
  const next = reduceAnalyticsAttribution(previous, {type: 'internal_navigation'}, configuration);
  return immutable({next_state: next, attribution: receipt.original_analytics && next ?
    {first_touch: next.first_touch, latest_touch: next.latest_touch} : null});
}
