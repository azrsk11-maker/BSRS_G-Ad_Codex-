/* Same-origin WP session bootstrap. No analytics decisions, tags, PII or secrets. */
(function () {
  'use strict';
  const config = window.BSREWordPress || {};
  window.BSRELeadConfig = { endpoint: '', measurementEligible: false };
  function safe(value) {
    try { const url = new URL(value); return url.protocol === 'https:' && url.origin === window.location.origin && !url.username && !url.password ? url.href : ''; }
    catch (_) { return ''; }
  }
  const contextEndpoint = safe(config.contextEndpoint);
  const leadEndpoint = safe(config.leadEndpoint);
  if (!contextEndpoint || !leadEndpoint) return;
  let refreshing;
  async function refresh() {
    if (refreshing) return refreshing;
    refreshing = (async function () {
      window.BSRELeadConfig = { endpoint: '', measurementEligible: false };
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 10000);
      try {
        const response = await window.fetch(contextEndpoint, { method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: { 'Content-Type': 'application/json' }, body: '{}', signal: controller.signal });
        const result = await response.json();
        if (!response.ok || !/^[0-9]{10}\.[a-f0-9]{64}$/.test(result.csrf_token || '') || result.expires_in !== 7200 || result.minimum_delay_ms !== 2100) return;
        // The server enforces the age too; client timestamps are not trusted.
        await new Promise(resolve => window.setTimeout(resolve, result.minimum_delay_ms));
        window.BSRELeadConfig = { endpoint: leadEndpoint, csrfToken: result.csrf_token, csrfHeader: 'X-BSRE-CSRF', measurementEligible: result.measurement_eligible === true };
        window.dispatchEvent(new window.CustomEvent('bsre:transport-ready'));
      } catch (_) { /* Original lead client shows its explicit unsent fallback. */ }
      finally { window.clearTimeout(timeout); }
    }());
    try { await refreshing; } finally { refreshing = null; }
  }
  refresh();
  // Token renewal changes only transport metadata; the original client's pending
  // request body and UUID stay intact after an uncertain attempt.
  window.setInterval(refresh, 60 * 60 * 1000);
  window.addEventListener('pageshow', event => { if (event.persisted) refresh(); });
}());
