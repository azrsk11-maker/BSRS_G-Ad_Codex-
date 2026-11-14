/* Owned enquiry pages only. No Google loader, inferred permission or lead fields. */
(function () {
  'use strict';
  const config = window.BSRETrackingConfig || {};
  const PENDING_KEY = 'BSRE_CONSENT_PENDING_V1';
  const PENDING_COOKIE = '__Host-bsre_consent_pending';
  const noticePattern = /^[a-zA-Z0-9._:-]{1,120}$/;
  const denied = Object.freeze({ analytics: false, ad_measurement: false, personalization: false });
  let snapshot = Object.freeze({ known: false, acknowledged: false, measurement_eligible: false, preferences: denied, decision_version: 'none', notice_version: '', preference_expires_at: 0, preference_days: 180 });
  let csrf = '';
  let csrfExpiresAt = 0;
  let generation = 0;
  let pending = readPending();
  let ui;
  let contextPromise;
  let expiryTimer;
  let requestedChoice = null;

  function endpoint(value) {
    try {
      const url = new URL(value);
      return url.protocol === 'https:' && url.origin === window.location.origin && !url.username && !url.password && !url.search && !url.hash ? url.href : '';
    } catch (_) { return ''; }
  }
  const contextEndpoint = endpoint(config.consentContextEndpoint);
  const updateEndpoint = endpoint(config.consentUpdateEndpoint);
  const configured = config.cmpProviderId === 'bsre_first_party_v1' && contextEndpoint && updateEndpoint;
  function readPending() {
    try { if (window.localStorage.getItem(PENDING_KEY) !== null) return true; } catch (_) { /* Cookie fallback. */ }
    try { return String(document.cookie || '').split(';').some(item => item.trim().split('=')[0] === PENDING_COOKIE); }
    catch (_) { return true; }
  }
  function markPending() {
    pending = true;
    let change = '';
    try { if (window.crypto && typeof window.crypto.randomUUID === 'function') change = window.crypto.randomUUID(); } catch (_) { /* Deny marker, not an authorization token. */ }
    if (!change) change = String(Date.now()) + ':' + String(generation) + ':' + String(Math.random());
    try { window.localStorage.setItem(PENDING_KEY, JSON.stringify({ version: 1, pending_since: Date.now(), change_id: change })); } catch (_) { /* This page still denies. */ }
    // Unsigned and deny-only: no client cookie can grant a purpose. This also
    // tells the next server request about an offline/unacknowledged withdrawal.
    try { document.cookie = PENDING_COOKIE + '=1; Max-Age=15552000; Path=/; Secure; SameSite=Strict'; } catch (_) { /* Current-page denial still applies. */ }
    return change;
  }
  function clearPending(change) {
    let stored;
    try { stored = window.localStorage.getItem(PENDING_KEY); } catch (_) { /* Cookie fallback. */ }
    if (stored !== undefined && stored !== null) {
      // A delayed acknowledgement from this tab cannot clear a newer pending
      // withdrawal in another tab, even before its storage event is delivered.
      try { if (JSON.parse(stored).change_id !== change) { pending = true; return; } }
      catch (_) { pending = true; return; }
    }
    try { window.localStorage.removeItem(PENDING_KEY); } catch (_) { /* Failure keeps denial. */ }
    try { document.cookie = PENDING_COOKIE + '=; Max-Age=0; Path=/; Secure; SameSite=Strict'; } catch (_) { /* A retained marker keeps denial. */ }
    pending = readPending();
  }
  function normalize(value) {
    try {
      if (!value || typeof value !== 'object' || !value.preferences || typeof value.preferences !== 'object') return null;
      const p = value.preferences;
      if (Object.keys(p).sort().join(',') !== 'ad_measurement,analytics,personalization' || typeof p.analytics !== 'boolean' || typeof p.ad_measurement !== 'boolean' || p.personalization !== false) return null;
      if (typeof value.known !== 'boolean' || typeof value.acknowledged !== 'boolean' || typeof value.measurement_eligible !== 'boolean' || !noticePattern.test(value.notice_version || '') || !noticePattern.test(value.decision_version || '') || value.preference_days !== 180 || !Number.isSafeInteger(value.preference_expires_at)) return null;
      if (value.known && (!value.acknowledged || value.decision_version === 'none' || value.preference_expires_at <= Math.floor(Date.now() / 1000))) return null;
      if (!value.known && (p.analytics || p.ad_measurement || value.decision_version !== 'none')) return null;
      return Object.freeze({ known: value.known, acknowledged: value.acknowledged, measurement_eligible: value.measurement_eligible, preferences: Object.freeze({ analytics: p.analytics, ad_measurement: p.ad_measurement, personalization: false }), decision_version: value.decision_version, notice_version: value.notice_version, preference_expires_at: value.preference_expires_at, preference_days: 180 });
    } catch (_) { return null; }
  }
  function permissions() {
    const current = !pending && snapshot.known && snapshot.acknowledged && snapshot.preference_expires_at > Math.floor(Date.now() / 1000);
    return Object.freeze({ analytics: Boolean(current && snapshot.preferences.analytics), advertising: Boolean(current && snapshot.preferences.ad_measurement), personalization: false });
  }
  // Consent-only held/preview documents do not load the Google orchestrator.
  // Retain its exact own-prefix/path/current-host cleanup boundary here too.
  function clearOwnedCookies(purpose) {
    const prefix = purpose === 'analytics' ? 'bsre_enq_analytics_' : 'bsre_enq_ads_';
    try {
      String(document.cookie || '').split(';').forEach(item => {
        const name = item.trim().split('=')[0];
        if (!name.startsWith(prefix) || !/^[A-Za-z0-9_]+$/.test(name)) return;
        document.cookie = name + '=; Max-Age=0; Path=/; Secure; SameSite=Strict';
        document.cookie = name + '=; Max-Age=0; Path=/; Domain=' + window.location.hostname + '; Secure; SameSite=Strict';
      });
    } catch (_) { /* Permission stays denied even when browser deletion fails. */ }
  }
  function cleanup(cookiePurposes = []) {
    const allowed = permissions();
    try {
      if (!allowed.analytics) window.sessionStorage.removeItem('BSRE_ATTRIBUTION_V1');
      if (!allowed.advertising) window.sessionStorage.removeItem('BSRE_AD_ATTRIBUTION_V1');
      if (!allowed.analytics && !allowed.advertising) window.sessionStorage.removeItem('BSRE_ACCEPTED_V1');
    } catch (_) { /* Optional state is not required for an enquiry. */ }
    cookiePurposes.forEach(clearOwnedCookies);
  }
  function publish(value, reason) {
    const previous = snapshot;
    snapshot = value;
    const p = permissions();
    // A vendor context must be retired synchronously before owned-key cleanup
    // and before the subsequent preference update can make a network request.
    window.dispatchEvent(new window.CustomEvent('bsre:consent-will-change', { detail: Object.freeze({ analytics: p.analytics, advertising: p.advertising }) }));
    let cookiePurposes;
    if (pending && requestedChoice) {
      cookiePurposes = ['analytics','advertising'].filter(purpose => purpose === 'analytics' ? !requestedChoice.analytics : !requestedChoice.ad_measurement);
    } else if (pending) cookiePurposes = ['analytics','advertising'];
    else cookiePurposes = ['analytics','advertising'].filter(purpose => {
      const key = purpose === 'analytics' ? 'analytics' : 'ad_measurement';
      return !p[purpose] && ((previous.known && previous.preferences[key]) || (snapshot.known && snapshot.acknowledged));
    });
    cleanup(cookiePurposes);
    window.BSREConsent = Object.freeze({ analytics: p.analytics, advertising: p.advertising, personalization: false });
    window.clearTimeout(expiryTimer);
    // Browser timers are signed 32-bit milliseconds. Re-read before that limit;
    // do not overflow a 180-day preference into an immediate expiry callback.
    if (!pending && snapshot.known) expiryTimer = window.setTimeout(function () {
      if (snapshot.preference_expires_at * 1000 <= Date.now()) deny('expired');
      else refresh();
    }, Math.min(2147483647, Math.max(1, snapshot.preference_expires_at * 1000 - Date.now())));
    window.dispatchEvent(new window.CustomEvent('bsre:consent-changed', { detail: Object.freeze({ reason: reason, pending: pending, refused: requestedChoice && pending ? Object.freeze({ analytics: !requestedChoice.analytics, advertising: !requestedChoice.ad_measurement }) : null }) }));
    renderState();
  }
  function deny(reason) {
    publish(Object.freeze(Object.assign({}, snapshot, { known: false, acknowledged: false, measurement_eligible: false, preferences: denied, decision_version: 'none', preference_expires_at: 0 })), reason);
  }
  async function request(url, body, token) {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 10000);
    try {
      const headers = { 'Content-Type': 'application/json' };
      if (token) headers['X-BSRE-Consent-CSRF'] = token;
      const response = await window.fetch(url, { method: 'POST', headers: headers, credentials: 'same-origin', cache: 'no-store', body: JSON.stringify(body), signal: controller.signal });
      const value = await response.json();
      if (!response.ok) throw new Error('Consent unavailable');
      return value;
    } finally { window.clearTimeout(timer); }
  }
  async function refresh() {
    if (!configured) { deny('unconfigured'); return false; }
    if (contextPromise) return contextPromise;
    const requestGeneration = generation;
    contextPromise = (async function () {
      try {
        const result = await request(contextEndpoint, {});
        const next = normalize(result);
        if (!next || !/^cc1\|[0-9]{10,11}\|[a-f0-9]{64}$/.test(result.csrf_token || '') || result.expires_in !== 7200) throw new Error('Invalid consent context');
        if (requestGeneration !== generation) return false;
        csrf = result.csrf_token;
        csrfExpiresAt = Date.now() + result.expires_in * 1000 - 10000;
        // A context read cannot undo an unacknowledged withdrawal, including
        // one carried from another page. Only an explicit saved choice can.
        if (pending || readPending()) { pending = true; snapshot = next; deny('pending'); }
        else publish(next, 'context');
        return true;
      } catch (_) {
        if (requestGeneration === generation) { csrf = ''; deny('unavailable'); setMessage('Optional measurement is off. Preferences could not be verified. You can still send an enquiry.'); }
        return false;
      } finally { contextPromise = null; }
    }());
    return contextPromise;
  }
  async function save(value) {
    if (!value || typeof value.analytics !== 'boolean' || typeof value.ad_measurement !== 'boolean' || value.personalization !== false) return false;
    const choice = { analytics: value.analytics, ad_measurement: value.ad_measurement, personalization: false };
    requestedChoice = choice;
    const requestGeneration = ++generation;
    const change = markPending();
    deny('pending');
    setMessage('Saving your preferences. Optional measurement stays off until confirmed.');
    try {
      if (!configured) throw new Error('Unconfigured');
      if (!csrf || Date.now() >= csrfExpiresAt || !noticePattern.test(snapshot.notice_version)) {
        if (contextPromise) await contextPromise;
        if (requestGeneration !== generation || !await refresh()) throw new Error('Context unavailable');
      }
      if (requestGeneration !== generation || !csrf || !snapshot.notice_version) return false;
      const result = await request(updateEndpoint, Object.assign({}, choice, { notice_version: snapshot.notice_version }), csrf);
      const next = normalize(result);
      if (requestGeneration !== generation) return false;
      if (!next || !next.known || !next.acknowledged || next.preferences.analytics !== choice.analytics || next.preferences.ad_measurement !== choice.ad_measurement) throw new Error('Unacknowledged preference');
      clearPending(change); requestedChoice = null;
      publish(next, 'saved');
      setMessage(pending ? 'Optional measurement is off. This browser could not clear its pending change; save again.' : 'Your preferences are saved. You can change them here at any time.');
      if (ui && !pending) setPanelOpen(false);
      return !pending;
    } catch (_) {
      if (requestGeneration === generation) { csrf = ''; csrfExpiresAt = 0; deny('pending'); setMessage('Optional measurement is off in this browser. The server has not confirmed this change. Keep this page open or return to preferences and save again.'); }
      return false;
    }
  }
  function setMessage(message) { if (ui) ui.status.textContent = message; }
  function setPanelOpen(open) {
    if (!ui) return;
    const restoreFocus = !open && !ui.panel.hidden && ui.panel.contains(document.activeElement);
    ui.panel.hidden = !open;
    ui.root.classList.toggle('is-open', open);
    ui.button.setAttribute('aria-expanded', String(open));
    if (restoreFocus) ui.button.focus();
  }
  function renderState() {
    if (!ui) return;
    const p = permissions();
    ui.analytics.checked = p.analytics;
    ui.advertising.checked = p.advertising;
    if (!snapshot.known || pending) ui.panel.hidden = false;
    setPanelOpen(!ui.panel.hidden);
  }
  function element(tag, text, attrs) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    Object.entries(attrs || {}).forEach(([key, value]) => node.setAttribute(key, value));
    return node;
  }
  function mount() {
    if (!configured || !document.body || typeof document.createElement !== 'function' || document.getElementById('bsre-consent')) return;
    const root = element('section', '', { id: 'bsre-consent', class: 'bsre-consent', 'aria-label': 'Optional measurement preferences' });
    const button = element('button', 'Measurement preferences', { type: 'button', class: 'bsre-consent-toggle', 'aria-controls': 'bsre-consent-panel', 'aria-expanded': 'false' });
    const panel = element('div', '', { id: 'bsre-consent-panel', class: 'bsre-consent-panel', role: 'region', 'aria-labelledby': 'bsre-consent-heading' });
    const heading = element('h2', 'Optional measurement', { id: 'bsre-consent-heading', tabindex: '-1' });
    panel.appendChild(heading);
    panel.appendChild(element('p', 'Choose optional measurement for these property enquiry pages. Your enquiry works if you reject optional measurement.'));
    function option(label, description) {
      const wrap = element('label', '', { class: 'bsre-consent-choice' });
      const input = element('input', '', { type: 'checkbox' });
      const copy = element('span'); copy.appendChild(element('strong', label)); copy.appendChild(element('span', description));
      wrap.appendChild(input); wrap.appendChild(copy); panel.appendChild(wrap); return input;
    }
    const analytics = option('Analytics', 'Measure visits and enquiry interactions to improve these pages.');
    const advertising = option('Ad measurement', 'Measure ad clicks and accepted enquiries. This does not enable personalized advertising.');
    panel.appendChild(element('p', 'Personalized advertising is off. These choices are separate from permission to contact you about your enquiry and optional marketing contact.'));
    panel.appendChild(element('p', 'Preferences last up to 180 days. This is separate from the retention period for enquiry records.'));
    const privacy = endpoint(config.privacyUrl);
    if (privacy) panel.appendChild(element('a', 'Read the property enquiry privacy notice', { href: privacy }));
    const status = element('p', '', { class: 'bsre-consent-status', role: 'status', 'aria-live': 'polite' });
    panel.appendChild(status);
    const actions = element('div', '', { class: 'bsre-consent-actions' });
    const reject = element('button', 'Reject optional measurement', { type: 'button' });
    const accept = element('button', 'Save choices', { type: 'button' });
    const close = element('button', 'Close preferences', { type: 'button' });
    actions.appendChild(reject); actions.appendChild(accept); actions.appendChild(close); panel.appendChild(actions);
    root.appendChild(button); root.appendChild(panel); document.body.appendChild(root);
    ui = { root, panel, button, status, analytics, advertising, reject, accept, close };
    panel.hidden = true;
    button.addEventListener('click', function () { setPanelOpen(panel.hidden); if (!panel.hidden) heading.focus(); });
    reject.addEventListener('click', () => save({ analytics: false, ad_measurement: false, personalization: false }));
    accept.addEventListener('click', () => save({ analytics: analytics.checked, ad_measurement: advertising.checked, personalization: false }));
    function closePanel() { setPanelOpen(false); button.focus(); }
    close.addEventListener('click', closePanel);
    panel.addEventListener('keydown', event => { if (event.key === 'Escape') closePanel(); });
    renderState();
  }
  window.BSREConsent = Object.freeze({ analytics: false, advertising: false, personalization: false });
  window.BSREConsentBridge = Object.freeze({
    getState: function () { const p = permissions(); return Object.freeze({ analytics_storage: p.analytics ? 'granted' : 'denied', ad_storage: p.advertising ? 'granted' : 'denied', ad_user_data: p.advertising ? 'granted' : 'denied', ad_personalization: 'denied' }); },
    getSnapshot: () => snapshot,
    permissions,
    measurementEligible: () => !pending && snapshot.measurement_eligible === true,
    isPending: () => pending,
    normalizeSnapshot: normalize,
    refresh,
    save,
    open: function () { setPanelOpen(true); }
  });
  window.addEventListener('storage', function (event) {
    if (event.key !== PENDING_KEY) return;
    ++generation; requestedChoice = null; pending = true; deny('cross-tab');
    if (event.newValue === null) { pending = readPending(); refresh(); }
  });
  window.addEventListener('pageshow', function (event) { if (event.persisted) { ++generation; requestedChoice = null; deny('refresh'); refresh(); } });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, { once: true }); else mount();
  if (pending) cleanup(['analytics','advertising']);
  refresh();
  if (configured) window.setInterval(refresh, 60 * 60 * 1000);
}());
