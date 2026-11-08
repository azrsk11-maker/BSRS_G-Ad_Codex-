/* Optional owned-page orchestrator. Vendor code runs only in disposable,
   server-authorized purpose-specific contexts; the enquiry form is untouched. */
(function () {
  'use strict';
  const config = window.BSREGoogleConfig || {};
  const VERSION = '1.0.0';
  const frames = new Map();
  const revoked = new Set();
  let viewReserved = false;
  function safeEndpoint(value) {
    try { const url = new URL(value); return url.protocol === 'https:' && url.origin === window.location.origin && !url.username && !url.password && !url.search && !url.hash ? url : null; } catch (_) { return null; }
  }
  const endpoint = safeEndpoint(config.runtime_endpoint);
  const configured = config.enabled === true && /^gm1-[a-f0-9]{32}$/.test(config.config_version || '') && endpoint && window.BSREMeasurement && window.BSREConsentBridge;
  function allowed(purpose) {
    return Boolean(configured && !revoked.has(purpose) && (purpose === 'analytics' ? config.analytics_enabled === true : purpose === 'advertising' && config.advertising_enabled === true) && window.BSREMeasurement.canLoad(purpose));
  }
  function pagePath() { const value = window.location.pathname; return /^\/enquire\/(?:(?:off-plan|resale|rent|sell|let)\/)?$/.test(value) ? value : ''; }
  function referrerOrigin() { try { const url = new URL(document.referrer); return ['https:', 'http:'].includes(url.protocol) ? url.origin : ''; } catch (_) { return ''; } }
  function clearCookies(purpose) {
    const prefix = purpose === 'analytics' ? 'bsre_enq_analytics_' : 'bsre_enq_ads_';
    try {
      String(document.cookie || '').split(';').forEach(item => {
        const name = item.trim().split('=')[0];
        if (!name.startsWith(prefix) || !/^[A-Za-z0-9_]+$/.test(name)) return;
        document.cookie = name + '=; Max-Age=0; Path=/; Secure; SameSite=Strict';
        // Clear an own-prefix cookie even if a vendor unexpectedly used the
        // current domain instead of the configured host-only scope.
        document.cookie = name + '=; Max-Age=0; Path=/; Domain=' + window.location.hostname + '; Secure; SameSite=Strict';
      });
    } catch (_) { /* Future dispatch remains blocked even if deletion fails. */ }
  }
  function retire(purpose, clear = true) {
    const state = frames.get(purpose);
    if (state) {
      state.active = false;
      try { if (state.frame.contentWindow.BSREGoogleRuntime) state.frame.contentWindow.BSREGoogleRuntime.stop(); } catch (_) { /* Frame may be denied/not yet loaded. */ }
      state.frame.remove();
      frames.delete(purpose);
    }
    if (clear) clearCookies(purpose);
  }
  function create(purpose) {
    if (!allowed(purpose) || frames.has(purpose) || !pagePath() || !document.body) return;
    let nonce;
    try { nonce = window.crypto.randomUUID(); } catch (_) { return; }
    const url = new URL(endpoint.href);
    url.searchParams.set('purpose', purpose);
    if (purpose === 'advertising') {
      const context = window.BSRELead.advertisingContext();
      ['gclid','gbraid','wbraid'].forEach(key => {
        const value = context[key];
        if (typeof value === 'string' && value.length <= 256 && /^[A-Za-z0-9._~-]+$/.test(value)) url.searchParams.set(key, value);
      });
    }
    const frame = document.createElement('iframe');
    frame.hidden = true; frame.title = 'Optional ' + purpose + ' runtime';
    frame.setAttribute('aria-hidden', 'true'); frame.setAttribute('tabindex', '-1');
    frame.setAttribute('sandbox', 'allow-scripts allow-same-origin');
    frame.referrerPolicy = 'origin';
    const state = { frame, purpose, nonce, active: false, initialized: false, view: false, sequence: 0 };
    frames.set(purpose, state);
    frame.src = url.href;
    document.body.appendChild(frame);
  }
  function sync() {
    ['analytics','advertising'].forEach(purpose => { if (!allowed(purpose)) { if (frames.has(purpose)) retire(purpose); } else create(purpose); });
  }
  function send(purpose, payload) {
    const state = frames.get(purpose);
    if (!state || !state.active || !allowed(purpose)) return false;
    state.frame.contentWindow.postMessage({ type: 'bsre-runtime-event', version: VERSION, purpose, nonce: state.nonce, sequence: ++state.sequence, payload }, window.location.origin);
    return true;
  }
  window.addEventListener('message', function (event) {
    if (event.origin !== window.location.origin || !event.data || event.data.version !== VERSION) return;
    const state = frames.get(event.data.purpose);
    if (!state || event.source !== state.frame.contentWindow || !allowed(state.purpose)) return;
    if (event.data.type === 'bsre-runtime-ready' && !state.initialized) {
      state.initialized = true;
      state.view = state.purpose === 'analytics' && !viewReserved;
      if (state.view) viewReserved = true;
      state.frame.contentWindow.postMessage({ type: 'bsre-runtime-init', version: VERSION, config_version: config.config_version, purpose: state.purpose, nonce: state.nonce, page_path: pagePath(), referrer_origin: referrerOrigin(), page_view: state.view }, window.location.origin);
    } else if (event.data.type === 'bsre-runtime-active' && event.data.nonce === state.nonce && state.initialized) state.active = true;
    else if (event.data.type === 'bsre-runtime-revoked' && event.data.nonce === state.nonce && state.initialized) { revoked.add(state.purpose); retire(state.purpose); }
  });
  // This event occurs before optional storage cleanup and the update POST.
  window.addEventListener('bsre:consent-will-change', function (event) {
    ['analytics','advertising'].forEach(purpose => { if (!event.detail || event.detail[purpose] !== true) retire(purpose); });
  });
  window.addEventListener('bsre:consent-changed', sync);
  window.addEventListener('bsre:transport-ready', sync);
  window.addEventListener('pagehide', function () { ['analytics','advertising'].forEach(purpose => retire(purpose, false)); });
  if (configured) {
    window.BSREMeasurement.connect('ga4', payload => send('analytics', payload));
    window.BSREMeasurement.connect('ads', payload => send('advertising', payload));
  }
  window.BSREGoogle = Object.freeze({ sync, active: purpose => Boolean(frames.get(purpose) && frames.get(purpose).active) });
  sync();
}());
