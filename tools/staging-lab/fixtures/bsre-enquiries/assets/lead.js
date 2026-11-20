/* Shared Black Swan enquiry client. Set a verified HTTPS endpoint before production.
   No CRM integration, tag injection, marketing automation or automatic qualification. */
(function () {
  'use strict';
  const ATTR_KEY = 'BSRE_ATTRIBUTION_V1';
  const AD_KEY = 'BSRE_AD_ATTRIBUTION_V1';
  const ACCEPTED_KEY = 'BSRE_ACCEPTED_V1';
  const ATTR_PARAMS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
  const AD_PARAMS = ['gclid', 'gbraid', 'wbraid'];
  const ROLES = new Set(['off_plan', 'resale', 'tenant', 'seller', 'landlord']);
  const accepted = new Set();
  let attribution = { first: null, last: null };
  let adAttribution = { first: null, last: null };
  const queryConsumed = { analytics: false, advertising: false };
  const pageTouch = { analytics: null, advertising: null };
  const retiredPurpose = { analytics: false, advertising: false };
  function permissions() {
    try {
      const bridge = window.BSREConsentBridge;
      const value = bridge && typeof bridge.permissions === 'function' ? bridge.permissions() : {};
      return { analytics: value.analytics === true, advertising: value.advertising === true };
    } catch (_) { return { analytics: false, advertising: false }; }
  }
  function analyticsAllowed() {
    return permissions().analytics;
  }
  function measurementEligible() {
    const bridge = window.BSREConsentBridge;
    return Boolean(bridge && typeof bridge.measurementEligible === 'function' && bridge.measurementEligible() && (!document.querySelector('form[data-bsre-form]') || (window.BSRELeadConfig && window.BSRELeadConfig.measurementEligible === true)));
  }
  function syntheticForm() {
    const form = document.querySelector('form[data-bsre-form]');
    return Boolean(form && /^\s*TEST(?:$|[\s_-])/i.test(valueOf(form, 'name')));
  }
  function sanitizeURL(value) {
    if (typeof value !== 'string' || !value.trim()) return '';
    try {
      const url = new URL(value, window.location.href);
      if (!['http:', 'https:'].includes(url.protocol)) return '';
      // No query, hash, username or password can reach analytics or the lead context.
      return url.origin + url.pathname;
    } catch (_) { return ''; }
  }
  function storageRead(key, allowed) {
    if (!allowed) return null;
    try { return JSON.parse(window.sessionStorage.getItem(key) || 'null'); } catch (_) { return null; }
  }
  function storageWrite(key, value, allowed) {
    if (!allowed) return;
    try { window.sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* In-memory fallback. */ }
  }
  function validParameter(value, opaque) {
    // The unchanged receiver allows 256 UTF-16 units. Reject unsupported IDs
    // whole: truncating an opaque click identifier creates a different ID.
    return typeof value === 'string' && value.length > 0 && value.length <= 256 && !/[\x00-\x1f\x7f]/.test(value) && (!opaque || /^[A-Za-z0-9._~-]+$/.test(value));
  }
  function touchNow(keys, analytics) {
    const url = new URL(window.location.href);
    const parameters = {};
    keys.forEach(function (key) {
      const values = url.searchParams.getAll(key);
      // Repeated click parameters are ambiguous; do not choose one silently.
      const value = values.length === 1 ? values[0] : '';
      if (validParameter(value, AD_PARAMS.includes(key))) parameters[key] = value;
    });
    return { landing_page: sanitizeURL(url.href), referrer: analytics ? sanitizeURL(document.referrer || '') : '', timestamp: Date.now(), parameters: parameters };
  }
  function validTouch(value, keys, analytics) {
    if (!value || typeof value !== 'object' || !Number.isFinite(value.timestamp)) return null;
    const parameters = {};
    keys.forEach(function (key) {
      if (value.parameters && validParameter(value.parameters[key], AD_PARAMS.includes(key))) parameters[key] = value.parameters[key];
    });
    return { landing_page: sanitizeURL(value.landing_page || ''), referrer: analytics && value.referrer ? sanitizeURL(value.referrer) : '', timestamp: value.timestamp, parameters: parameters };
  }
  function updateConsent(event) {
    const allowed = permissions();
    const eligible = measurementEligible() && !syntheticForm();
    const snapshot = currentSnapshot();
    const refused = event && event.detail && event.detail.refused;
    ['analytics', 'advertising'].forEach(purpose => {
      const key = purpose === 'analytics' ? 'analytics' : 'ad_measurement';
      if ((refused && refused[purpose]) || (snapshot && snapshot.known && !snapshot.preferences[key]) || (event && event.detail && ['cross-tab', 'expired'].includes(event.detail.reason))) {
        queryConsumed[purpose] = true; pageTouch[purpose] = null; retiredPurpose[purpose] = true;
      }
    });
    function refreshTouch(key, keys, analytics, permitted, purpose) {
      if (!eligible || !permitted) return { first: null, last: null };
      const stored = retiredPurpose[purpose] ? null : storageRead(key, true);
      if (!pageTouch[purpose] && !queryConsumed[purpose]) { pageTouch[purpose] = touchNow(keys, analytics); queryConsumed[purpose] = true; }
      const now = pageTouch[purpose];
      const first = validTouch(stored && stored.first, keys, analytics) || now;
      let last = now || validTouch(stored && stored.last, keys, analytics);
      // A queryless hub/service navigation is not a new advertising click.
      // Retain the actual latest permitted click touch, including its original
      // bytes and timestamp. Never reconstruct an already-lost older touch.
      if (purpose === 'advertising' && now && !Object.keys(now.parameters).length) {
        const previous = validTouch(stored && stored.last, keys, analytics);
        if (previous && Object.keys(previous.parameters).length) last = previous;
      }
      const result = { first: first, last: last };
      storageWrite(key, result, true);
      return result;
    }
    attribution = refreshTouch(ATTR_KEY, ATTR_PARAMS, true, allowed.analytics, 'analytics');
    adAttribution = refreshTouch(AD_KEY, AD_PARAMS, false, allowed.advertising, 'advertising');
    if (eligible && (allowed.analytics || allowed.advertising)) {
      const seen = storageRead(ACCEPTED_KEY, true);
      if (Array.isArray(seen)) seen.slice(-100).forEach(function (id) {
        if (typeof id === 'string' && /^[A-Za-z0-9._:-]{1,150}$/.test(id)) accepted.add(id);
      });
    }
  }
  function combinedAttribution() {
    const allowed = permissions();
    if (!measurementEligible() || syntheticForm()) return { first: null, last: null };
    const result = {};
    ['first', 'last'].forEach(function (key) {
      const analytics = allowed.analytics ? attribution[key] : null;
      const ad = allowed.advertising ? adAttribution[key] : null;
      if (!analytics && !ad) { result[key] = null; return; }
      const base = ad && Object.keys(ad.parameters).length ? ad : analytics || ad;
      result[key] = { landing_page: base.landing_page, referrer: analytics ? analytics.referrer : '', timestamp: base.timestamp, parameters: Object.assign({}, analytics ? analytics.parameters : {}, ad ? ad.parameters : {}) };
    });
    return result;
  }
  const dispatchRecords = new Map();
  const destinations = new Map();
  const receipts = new Set();
  function frozen(value) { Object.values(value).forEach(item => { if (item && typeof item === 'object') frozen(item); }); return Object.freeze(value); }
  function currentSnapshot() {
    try { return window.BSREConsentBridge.getSnapshot(); } catch (_) { return null; }
  }
  function safeCanonical(event) {
    if (!event || !['form_submit', 'form_start', 'whatsapp_click', 'telephone_click'].includes(event.event) || typeof event.event_id !== 'string' || !/^[A-Za-z0-9._:-]{1,150}$/.test(event.event_id) || typeof event.page_path !== 'string' || !/^\/enquire\/(?:(?:off-plan|resale|rent|sell|let)\/)?$/.test(event.page_path) || !ROLES.has(event.role) && event.role !== 'unknown') return null;
    const out = { event: event.event, event_id: event.event_id, schema_version: '1.0.0', site_scope: 'BSRE_REAL_ESTATE', page_path: event.page_path, role: event.role };
    if (event.cta_location) out.cta_location = ['header', 'hero', 'form', 'footer', 'sticky'].includes(event.cta_location) ? event.cta_location : 'other';
    return frozen(out);
  }
  function mapGA4(event) {
    const safe = safeCanonical(event);
    if (!safe) return null;
    const parameters = { schema_version: safe.schema_version, site_scope: safe.site_scope, page_path: safe.page_path, role: safe.role };
    if (safe.cta_location) parameters.cta_location = safe.cta_location;
    return frozen({ event_name: safe.event === 'form_submit' ? 'generate_lead' : safe.event, parameters: parameters });
  }
  function dispatch(destination, canonical, send) {
    const safe = safeCanonical(canonical);
    const record = safe && dispatchRecords.get(safe.event_id);
    const purpose = destination === 'ga4' ? 'analytics' : destination === 'ads' ? 'advertising' : '';
    if (!purpose || !record || record.canonical !== canonical || record.sent.has(destination) || !record.allowed[purpose] || !permissions()[purpose] || !measurementEligible() || syntheticForm() || Date.now() - record.created > 30000 || typeof send !== 'function') return false;
    if (destination === 'ads' && (canonical.event !== 'form_submit' || canonical.event_id.length > 64)) return false;
    // Consume before calling the destination. An uncertain provider callback is
    // never retried automatically or replayed after a later permission grant.
    record.sent.add(destination);
    const payload = destination === 'ga4' ? mapGA4(canonical) : frozen({ event_name: 'accepted_enquiry', transaction_id: canonical.event_id, page_path: canonical.page_path, role: canonical.role });
    try { return send(payload) !== false; } catch (_) { return false; }
  }
  window.BSREMeasurement = Object.freeze({
    version: '2.0.0',
    mapGA4,
    dispatch,
    canLoad: function (purpose) { return ['analytics', 'advertising'].includes(purpose) && measurementEligible() && !syntheticForm() && permissions()[purpose] === true; },
    connect: function (destination, send) { if (!['ga4', 'ads'].includes(destination) || destinations.has(destination) || typeof send !== 'function') return false; destinations.set(destination, send); return true; }
  });
  // Only controlled routes/enums reach the public v1 schema. Receipt metadata
  // and permission decisions belong to a separate immutable internal v2 bus.
  function emit(event, role, pagePath, ctaLocation, receipt) {
    const allowed = permissions();
    if (!measurementEligible() || syntheticForm() || (!allowed.analytics && !allowed.advertising)) return;
    if (!['form_start', 'bsre_lead_accepted', 'whatsapp_click', 'telephone_click'].includes(event)) return;
    if (!receipt && !allowed.analytics) return;
    const decision = currentSnapshot();
    if (!decision || !decision.known || !decision.acknowledged) return;
    const eventData = { event: receipt ? 'form_submit' : event, page_path: /^\/enquire\/(off-plan|resale|rent|sell|let)\/$/.test(pagePath) ? pagePath : '/enquire/', role: ROLES.has(role) ? role : 'unknown' };
    try { eventData.event_id = receipt ? receipt.event_id : uuid(); } catch (_) { return; }
    if (ctaLocation) eventData.cta_location = ctaLocation;
    let occurrence = { analytics: allowed.analytics, advertising: allowed.advertising };
    let original = decision;
    if (receipt) {
      const bridge = window.BSREConsentBridge;
      original = bridge.normalizeSnapshot(receipt.measurement);
      const capture = receipt.capture;
      if (!original || !original.known || !original.acknowledged || !original.measurement_eligible || !capture || !capture.known || !capture.acknowledged || receipts.has(receipt.event_id)) return;
      occurrence = { analytics: original.preferences.analytics && capture.preferences.analytics && allowed.analytics, advertising: original.preferences.ad_measurement && capture.preferences.ad_measurement && allowed.advertising };
      if (!occurrence.analytics && !occurrence.advertising) return;
      receipts.add(receipt.event_id);
    }
    const canonical = safeCanonical(eventData);
    if (!canonical) return;
    const envelope = frozen({ bus_version: '2.0.0', event: event, event_id: eventData.event_id, occurred_at_utc: new Date().toISOString(), context: { page_path: canonical.page_path, role: canonical.role }, receipt: receipt ? { lead_id: receipt.lead_id, event_id: receipt.event_id } : null, permission: { analytics: occurrence.analytics, ad_measurement: occurrence.advertising, personalization: false, decision_version: original.decision_version, notice_version: original.notice_version } });
    dispatchRecords.set(canonical.event_id, { canonical, allowed: occurrence, sent: new Set(), created: Date.now() });
    if (dispatchRecords.size > 100) dispatchRecords.delete(dispatchRecords.keys().next().value);
    window.dispatchEvent(new window.CustomEvent('bsre:measurement', { detail: envelope }));
    destinations.forEach((send, destination) => dispatch(destination, canonical, send));
  }
  function pageContext() {
    const form = document.querySelector('form[data-bsre-form]');
    return { role: form ? form.dataset.role : '', path: form ? form.dataset.landingPath : '/enquire/' };
  }
  function trackContact(kind, ctaLocation) {
    if (!['telephone', 'whatsapp'].includes(kind)) return;
    const context = pageContext();
    emit(kind === 'telephone' ? 'telephone_click' : 'whatsapp_click', context.role, context.path, ctaLocation);
  }
  function uuid() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    if (!window.crypto || !window.crypto.getRandomValues) throw new Error('Secure ID generation unavailable.');
    window.crypto.getRandomValues(bytes); bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
    return Array.from(bytes, function (b, i) { return ([4, 6, 8, 10].includes(i) ? '-' : '') + b.toString(16).padStart(2, '0'); }).join('');
  }
  function valueOf(form, name) {
    const field = form.elements.namedItem(name);
    return field && typeof field.value === 'string' ? field.value.trim() : '';
  }
  function checked(form, name) {
    const field = form.elements.namedItem(name);
    return Boolean(field && field.checked);
  }
  function showStatus(status, message, state) {
    status.hidden = false; status.dataset.state = state || 'notice'; status.textContent = message;
  }
  function safeEndpoint() {
    const endpoint = window.BSRELeadConfig && window.BSRELeadConfig.endpoint;
    if (typeof endpoint !== 'string' || !endpoint.trim()) return '';
    try {
      const url = new URL(endpoint, window.location.href);
      return url.protocol === 'https:' && !url.username && !url.password && !url.search && !url.hash && url.origin === window.location.origin ? url.href : '';
    } catch (_) { return ''; }
  }
  function requestHeaders(retry, capture) {
    const headers = { 'Content-Type': 'application/json' };
    const configured = window.BSRELeadConfig || {};
    const token = configured.csrfToken;
    const header = configured.csrfHeader || 'X-BSRE-CSRF';
    if (typeof token === 'string' && token && token.length <= 2048 && !/[\r\n]/.test(token) && ['X-BSRE-CSRF', 'X-WP-Nonce', 'X-CSRF-Token', 'X-XSRF-Token'].includes(header)) headers[header] = token;
    // Deny-only sidecar; the immutable signed v1 body remains byte-identical.
    if (retry) headers['X-BSRE-Consent-Retry'] = '1';
    // Matching a validated server revision can only preserve its existing
    // permission. Missing/unknown/mismatched revisions must deny server-side.
    headers['X-BSRE-Consent-Decision'] = capture && capture.known && capture.acknowledged && /^[A-Za-z0-9._:-]{1,120}$/.test(capture.decision_version) ? capture.decision_version : 'none';
    return headers;
  }
  function attachForm(form) {
    if (form.dataset.bsreInitialized === 'true') return;
    form.dataset.bsreInitialized = 'true';
    const status = form.querySelector('[data-bsre-status]');
    const button = form.querySelector('button[type="submit"]');
    const startedAt = Date.now();
    let requestId = '';
    // An uncertain request must be retried byte-for-byte with the same UUID.
    // These values remain in this form's memory only, never Web Storage.
    let attemptBody = '';
    let attemptFields = '';
    let attemptHadAttribution = false;
    let attemptHadAdIdentifiers = false;
    let attemptPermission = null;
    let started = false;
    let pending = false;
    let completed = false;
    const initialButton = button.textContent;
    function meaningfulStart(event) {
      const target = event.target;
      if (started || !target || target.name === 'website' || ['checkbox', 'hidden', 'submit'].includes(target.type) || !String(target.value || '').trim()) return;
      if (!['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return;
      started = true;
      emit('form_start', form.dataset.role, form.dataset.landingPath);
    }
    form.addEventListener('input', meaningfulStart);
    form.addEventListener('change', meaningfulStart);
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      if (pending || completed) return;
      if (!form.reportValidity()) return;
      const endpoint = safeEndpoint();
      if (!endpoint) {
        showStatus(status, 'Unpublished preview — your enquiry has not been sent. This draft does not save or transmit your details. You can contact Black Swan Real Estate using the telephone or WhatsApp links.', 'notice');
        return;
      }
      if (!ROLES.has(form.dataset.role) || !checked(form, 'contact_consent')) {
        showStatus(status, 'Please check the required enquiry details and contact consent before submitting.', 'error'); return;
      }
      if (valueOf(form, 'website')) {
        showStatus(status, 'We could not accept this enquiry. Please use the telephone or WhatsApp contact option.', 'error'); return;
      }
      try { requestId = requestId || uuid(); } catch (_) {
        showStatus(status, 'This browser could not prepare a secure enquiry. Please use the telephone or WhatsApp contact option.', 'error'); return;
      }
      const payload = {
        request_id: requestId, role: form.dataset.role, name: valueOf(form, 'name'), phone: valueOf(form, 'phone'), email: valueOf(form, 'email'),
        country: valueOf(form, 'country'), area: valueOf(form, 'area'), budget: valueOf(form, 'budget'), timeline: valueOf(form, 'timeline'), funding: valueOf(form, 'funding'),
        property_type: valueOf(form, 'property_type'), property_details: valueOf(form, 'property_details'), authority: valueOf(form, 'authority'),
        contact_consent: checked(form, 'contact_consent'), marketing_consent: checked(form, 'marketing_consent'),
        campaign: form.dataset.campaign || (window.BSRELeadConfig && window.BSRELeadConfig.campaign) || 'Service enquiry',
        landing_page: sanitizeURL(window.location.href), attribution: combinedAttribution(), website: '', started_at: startedAt
      };
      const currentFields = JSON.stringify(Object.assign({}, payload, { attribution: null }));
      if (attemptBody && currentFields !== attemptFields) {
        showStatus(status, 'Receipt of your earlier attempt is still unconfirmed. Some details have changed, so they have not been resent. Restore the original details to retry the same request, or contact us by phone or WhatsApp to check it. This prevents a duplicate enquiry.', 'error'); return;
      }
      if (attemptBody && attemptHadAttribution && (!analyticsAllowed() || retiredPurpose.analytics)) {
        showStatus(status, 'Receipt of your earlier attempt is still unconfirmed, and your analytics consent has changed. To respect your current choice, this request cannot be resent with its original attribution. Please contact us by phone or WhatsApp to check the earlier enquiry.', 'error'); return;
      }
      if (attemptBody && attemptHadAdIdentifiers && (!permissions().advertising || retiredPurpose.advertising)) {
        showStatus(status, 'Receipt of your earlier attempt is still unconfirmed, and your advertising permission has changed. Please contact us by phone or WhatsApp to check that enquiry before sending another request.', 'error'); return;
      }
      const retry = Boolean(attemptBody);
      if (!attemptBody) {
        attemptBody = JSON.stringify(payload); attemptFields = currentFields;
        attemptPermission = currentSnapshot();
        // Track the purposes actually used by this immutable attempt. A later
        // analytics grant must not classify an advertising-only touch as an
        // analytics-bearing body after analytics was previously retired.
        attemptHadAttribution = permissions().analytics && ['first', 'last'].some(touch => payload.attribution[touch] && attribution[touch]);
        attemptHadAdIdentifiers = ['first', 'last'].some(touch => payload.attribution[touch] && AD_PARAMS.some(key => Object.prototype.hasOwnProperty.call(payload.attribution[touch].parameters || {}, key)));
      }
      pending = true; button.disabled = true; button.textContent = 'Sending enquiry…';
      showStatus(status, 'Sending your enquiry securely…', 'notice');
      const controller = new AbortController();
      const timeout = window.setTimeout(function () { controller.abort(); }, 20000);
      try {
        const response = await window.fetch(endpoint, { method: 'POST', headers: requestHeaders(retry, attemptPermission), credentials: 'same-origin', body: attemptBody, signal: controller.signal });
        const result = await response.json();
        if (!response.ok) {
          if ([400, 422].includes(response.status) && result.accepted === false && result.code === 'VALIDATION_FAILED') {
            requestId = ''; attemptBody = ''; attemptFields = ''; attemptHadAttribution = false; attemptHadAdIdentifiers = false; attemptPermission = null;
            showStatus(status, 'The service rejected these details before accepting the enquiry. Please review your required fields and consent, then submit again. Your next corrected attempt will receive a new request reference.', 'error'); return;
          }
          if (response.status === 409 && result.code === 'REQUEST_ID_CONFLICT') {
            showStatus(status, 'The service could not reconcile this request reference. Your details have not been resent under a new reference. Please contact us by phone or WhatsApp to check the enquiry.', 'error'); return;
          }
          throw new Error('Unaccepted response');
        }
        const validId = function (id) { return typeof id === 'string' && /^[A-Za-z0-9._:-]{1,150}$/.test(id); };
        if (result.accepted !== true || !validId(result.lead_id) || !validId(result.event_id)) throw new Error('Missing durable receipt');
        completed = true;
        attemptBody = ''; attemptFields = ''; attemptHadAttribution = false; attemptHadAdIdentifiers = false;
        button.textContent = 'Enquiry received'; button.dataset.complete = 'true';
        showStatus(status, 'Your enquiry has been received. Reference: ' + result.lead_id + '. Black Swan Real Estate can now review your request. This receipt does not confirm property availability or qualification.', 'success');
        if (!accepted.has(result.lead_id)) {
          accepted.add(result.lead_id);
          const allowed = permissions();
          if (measurementEligible() && !syntheticForm()) storageWrite(ACCEPTED_KEY, Array.from(accepted).slice(-100), allowed.analytics || allowed.advertising);
          // Eligibility is rechecked by the server at receipt time. An old or
          // missing field is fail-closed for measurement, never for intake.
          emit('bsre_lead_accepted', form.dataset.role, form.dataset.landingPath, '', { lead_id: result.lead_id, event_id: result.event_id, measurement: result.measurement, capture: attemptPermission });
        }
      } catch (_) {
        showStatus(status, 'We could not confirm receipt. Your enquiry may not have been accepted. Please retry; the same request reference will be reused to prevent a duplicate, or contact us by phone or WhatsApp.', 'error');
      } finally {
        window.clearTimeout(timeout); pending = false;
        if (!completed) { button.disabled = false; button.textContent = initialButton; }
      }
    });
    button.disabled = false;
  }
  function init() {
    updateConsent();
    document.querySelectorAll('form[data-bsre-form]').forEach(attachForm);
    document.querySelectorAll('a[data-bsre-contact]').forEach(function (link) {
      if (link.dataset.bsreInitialized === 'true') return;
      link.dataset.bsreInitialized = 'true';
      link.addEventListener('click', function () {
        const kind = link.dataset.bsreContact;
        const href = link.getAttribute('href') || '';
        if ((kind === 'telephone' && href.startsWith('tel:')) || (kind === 'whatsapp' && /^https:\/\/wa\.me\/971568285677(?:\?|$)/.test(href))) trackContact(kind, link.dataset.ctaLocation);
      });
    });
  }
  window.BSRELead = Object.freeze({ init: init, sanitizeURL: sanitizeURL, trackContact: trackContact,
    advertisingContext: function () {
      if (!measurementEligible() || syntheticForm() || !permissions().advertising) return Object.freeze({});
      const last = adAttribution.last && adAttribution.last.parameters;
      const first = adAttribution.first && adAttribution.first.parameters;
      const source = last && AD_PARAMS.some(key => validParameter(last[key], true)) ? last : first || {};
      const out = {};
      AD_PARAMS.forEach(key => { if (validParameter(source[key], true)) out[key] = source[key]; });
      return Object.freeze(out);
    }
  });
  window.addEventListener('bsre:transport-ready', updateConsent);
  window.addEventListener('consentchanged', updateConsent);
  window.addEventListener('bsre:consent-changed', function (event) {
    const allowed = permissions();
    // Withdrawal permanently invalidates undelivered occurrence permissions;
    // a later grant cannot resurrect an earlier queued/observed event.
    dispatchRecords.forEach(record => {
      if (!allowed.analytics) record.allowed.analytics = false;
      if (!allowed.advertising) record.allowed.advertising = false;
    });
    updateConsent(event);
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
}());
