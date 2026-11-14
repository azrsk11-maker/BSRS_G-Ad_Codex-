/* Loaded by a server-authorized same-origin iframe. Container inventory must
   contain only the reviewed local bootstrap call; no autonomous Google tags. */
(function () {
  'use strict';
  const VERSION = '1.0.0';
  let config;
  try { config = JSON.parse(document.getElementById('bsre-runtime-config').textContent); } catch (_) { return; }
  if (!config || config.version !== VERSION || config.enabled !== true || !['analytics','advertising'].includes(config.purpose) || !/^https:\/\/(?:www\.)?blackswanrealestate\.ae$/.test(config.origin || '') || config.origin !== window.location.origin || window.parent === window || !/^GTM-[A-Z0-9]+$/.test(config.gtm_id || '')) return;
  const analytics = config.purpose === 'analytics';
  if (analytics ? (!/^G-[A-Z0-9]+$/.test(config.measurement_id || '') || config.ads_send_to !== '' || config.cookie_prefix !== 'bsre_enq_analytics') : (!/^AW-[0-9]+\/[A-Za-z0-9_-]+$/.test(config.ads_send_to || '') || config.measurement_id !== '' || config.cookie_prefix !== 'bsre_enq_ads')) return;
  let statusEndpoint;
  try { statusEndpoint = new URL(config.status_endpoint); if (statusEndpoint.protocol !== 'https:' || statusEndpoint.origin !== config.origin || statusEndpoint.username || statusEndpoint.password || statusEndpoint.search || statusEndpoint.hash) return; } catch (_) { return; }
  if (!/^gm1-[a-f0-9]{32}$/.test(config.config_version || '') || config.lease_seconds !== 30 || !/^ml1\|[0-9]{10,11}\|[a-f0-9]{64}$/.test(config.lease_token || '')) return;
  // The Ads destination has a verified legacy Analytics destination. Disable
  // those exact Analytics IDs in this disposable frame before any Google load
  // or command; never change the parent/shared tag or infer other destinations.
  window['ga-disable-G-5LSDD336PQ'] = true;
  if (!analytics) window['ga-disable-G-W01P9W3NWE'] = true;
  let leaseToken = config.lease_token, leaseExpires = Number(leaseToken.split('|')[1]) * 1000;
  let initialized = false, activated = false, active = false, stopped = false;
  let nonce = '', pagePath = '', referrer = '', pageView = false, lastSequence = 0, leaseTimer, leaseRequest, executionExpires = 0;
  const seen = new Set();
  function permitted() {
    try { return !stopped && Date.now() < leaseExpires && window.parent.BSREMeasurement.canLoad(config.purpose) === true; } catch (_) { return false; }
  }
  function allowed() { return permitted() && Date.now() < executionExpires; }
  function post(type) { window.parent.postMessage({ type, version: VERSION, purpose: config.purpose, nonce }, config.origin); }
  function command() { if (!stopped) window.dataLayer.push(arguments); }
  function addScript(url, onload) {
    if (!allowed()) return false;
    const script = document.createElement('script'); script.async = true; script.src = url; script.referrerPolicy = 'origin';
    if (onload) script.onload = onload;
    document.head.appendChild(script); return true;
  }
  function stop() {
    stopped = true; active = false;
    window.clearInterval(leaseTimer);
    if (analytics) window['ga-disable-' + config.measurement_id] = true;
    // Do not issue a consent ping after withdrawal. The parent immediately
    // destroys this execution context; already in-flight requests cannot be unsent.
  }
  function revoke() {
    if (stopped) return;
    stop(); post('bsre-runtime-revoked');
    // Retire this browsing context even if the parent is busy. Already-sent
    // traffic cannot be unsent; this prevents further controller execution.
    window.location.replace('about:blank');
  }
  async function checkLease() {
    if (!permitted() || executionExpires > 0 && Date.now() >= executionExpires) { revoke(); return false; }
    if (leaseRequest) return leaseRequest;
    leaseRequest = (async function () {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 5000);
      try {
        const response = await window.fetch(statusEndpoint.href, { method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({purpose:config.purpose,lease_token:leaseToken,config_version:config.config_version}),signal:controller.signal });
        const next = await response.json();
        if (!response.ok || next.ok !== true || next.enabled !== true || next.version !== VERSION || next.purpose !== config.purpose || next.config_version !== config.config_version || next.lease_seconds !== 30 || !/^ml1\|[0-9]{10,11}\|[a-f0-9]{64}$/.test(next.lease_token || '')) throw new Error('Runtime lease denied');
        const expiry = Number(next.lease_token.split('|')[1]) * 1000;
        if (expiry <= Date.now() || expiry > Date.now() + 121000 || stopped || executionExpires > 0 && Date.now() >= executionExpires) throw new Error('Runtime lease invalid');
        leaseToken = next.lease_token; leaseExpires = expiry; executionExpires = Date.now() + next.lease_seconds * 1000; return true;
      } catch (_) { revoke(); return false; }
      finally { window.clearTimeout(timeout); leaseRequest = null; }
    }());
    return leaseRequest;
  }
  function privacy() { return { cookie_expires: 0, cookie_update: false, cookie_domain: 'none', cookie_prefix: config.cookie_prefix, cookie_flags: 'SameSite=Strict;Secure', allow_google_signals: false, allow_ad_personalization_signals: false, send_page_view: false, page_location: config.origin + pagePath, page_referrer: referrer, page_title: 'Black Swan Real Estate Enquiries' }; }
  function activate() {
    if (activated || !initialized || stopped) return false;
    if (!allowed()) { revoke(); return false; }
    activated = true;
    const id = analytics ? config.measurement_id : config.ads_send_to.split('/')[0];
    command('consent','default',{ analytics_storage:'denied', ad_storage:'denied', ad_user_data:'denied', ad_personalization:'denied' });
    command('consent','update',{ analytics_storage:analytics?'granted':'denied', ad_storage:analytics?'denied':'granted', ad_user_data:analytics?'denied':'granted', ad_personalization:'denied' });
    command('set','ads_data_redaction',true); command('set','url_passthrough',false);
    command('set','allow_ad_personalization_signals',false);
    command('set','allow_google_signals',false);
    command('js',new Date());
    command('config',id,privacy());
    return addScript('https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(id), function () {
      if (!allowed()) { revoke(); return; }
      active = true;
      if (analytics && pageView) command('event','page_view',Object.assign({},privacy(),{ send_to:config.measurement_id }));
      post('bsre-runtime-active');
    });
  }
  function receive(payload) {
    if (!allowed()) { revoke(); return; }
    if (!active || !payload || typeof payload !== 'object') return;
    if (analytics) {
      if (Object.keys(payload).sort().join(',') !== 'event_name,parameters' || !['generate_lead','form_start','whatsapp_click','telephone_click'].includes(payload.event_name)) return;
      const p = payload.parameters;
      if (!p || Object.keys(p).some(key => !['schema_version','site_scope','page_path','role','cta_location'].includes(key)) || p.schema_version !== '1.0.0' || p.site_scope !== 'BSRE_REAL_ESTATE' || p.page_path !== pagePath || !['off_plan','resale','tenant','seller','landlord','unknown'].includes(p.role) || Object.prototype.hasOwnProperty.call(p,'cta_location') && !['header','hero','form','footer','sticky','other'].includes(p.cta_location)) return;
      command('event',payload.event_name,Object.assign({},privacy(),p,{ send_to:config.measurement_id }));
    } else {
      if (Object.keys(payload).sort().join(',') !== 'event_name,page_path,role,transaction_id' || payload.event_name !== 'accepted_enquiry' || payload.page_path !== pagePath || typeof payload.transaction_id !== 'string' || !/^[A-Za-z0-9._:-]{1,64}$/.test(payload.transaction_id) || seen.has(payload.transaction_id) || !['off_plan','resale','tenant','seller','landlord'].includes(payload.role)) return;
      seen.add(payload.transaction_id);
      command('event','conversion',Object.assign({},privacy(),{ send_to:config.ads_send_to, transaction_id:payload.transaction_id }));
    }
  }
  window.BSREGoogleRuntime = Object.freeze({ activate, stop });
  window.addEventListener('message', async function (event) {
    const data = event.data;
    if (event.origin !== config.origin || event.source !== window.parent || !data || data.version !== VERSION || data.purpose !== config.purpose) return;
    if (!permitted()) { if (initialized) revoke(); return; }
    if (data.type === 'bsre-runtime-init' && !initialized) {
      if (data.config_version !== config.config_version || typeof data.nonce !== 'string' || !/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(data.nonce) || typeof data.page_view !== 'boolean' || !/^\/enquire\/(?:(?:off-plan|resale|rent|sell|let)\/)?$/.test(data.page_path || '')) return;
      try { const url = data.referrer_origin ? new URL(data.referrer_origin) : null; if (url && (!['http:','https:'].includes(url.protocol) || url.origin !== data.referrer_origin)) return; referrer = url ? url.origin : ''; } catch (_) { return; }
      initialized = true; nonce = data.nonce; pagePath = data.page_path; pageView = analytics && data.page_view;
      if (!await checkLease()) return;
      leaseTimer = window.setInterval(checkLease, 15000);
      window.dataLayer = window.dataLayer || [];
      command('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
      window.dataLayer.push({ 'gtm.start':Date.now(), event:'gtm.js' });
      addScript('https://www.googletagmanager.com/gtm.js?id=' + encodeURIComponent(config.gtm_id));
    } else if (data.type === 'bsre-runtime-event' && initialized && data.nonce === nonce && Number.isSafeInteger(data.sequence) && data.sequence > lastSequence && data.sequence <= 1000000000) { lastSequence = data.sequence; receive(data.payload); }
  });
  post('bsre-runtime-ready');
}());
