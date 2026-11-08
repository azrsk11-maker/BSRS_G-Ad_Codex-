(async function () {
  const bridge = window.BSREConsentBridge;
  const denied = () => !bridge.permissions().advertising && !bridge.permissions().analytics;
  const check = (condition, name) => { if (!condition) throw new Error(name); };
  async function eventually(predicate, name) {
    const deadline = Date.now() + 4000;
    while (!predicate() && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    check(predicate(), name);
  }
  try {
    check(window.isSecureContext && location.protocol === 'https:', 'secure_context');
    check(await bridge.refresh(), 'context_request');
    if (location.pathname === '/browser-peer') return;
    if (location.pathname === '/browser') {
      check(!bridge.getSnapshot().known && denied(), 'fresh_default_denied');
      check(document.querySelectorAll('#bsre-consent input[type=checkbox]').length === 2, 'native_dom');
      check(await bridge.save({analytics: false, ad_measurement: true, personalization: false}), 'advertising_choice');
      check(bridge.permissions().advertising && !bridge.permissions().analytics, 'purpose_separation');
      location.replace('/browser-return');
      return;
    }
    if (location.pathname === '/browser-pending') {
      check(denied() && bridge.isPending(), 'pending_denial_survives_reload');
      check(!bridge.measurementEligible(), 'pending_not_eligible');
      check(await bridge.save({analytics: false, ad_measurement: false, personalization: false}), 'retry_acknowledged');
      check(denied() && !bridge.isPending(), 'retry_stays_denied');
      await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'PASS'})});
      return;
    }
    check(bridge.permissions().advertising && !bridge.permissions().analytics, 'cookie_across_navigation');
    check(!document.cookie.includes('__Host-bsre_consent='), 'preference_cookie_httponly');
    document.cookie = 'bsre_enq_ads_lab=1; Path=/; Secure; SameSite=Strict';
    document.cookie = 'unrelated_lab=1; Path=/; Secure; SameSite=Strict';
    sessionStorage.setItem('BSRE_AD_ATTRIBUTION_V1', 'synthetic');
    check(document.cookie.includes('bsre_enq_ads_lab=1'), 'owned_cookie_seeded');
    const peer = document.createElement('iframe');
    peer.src = '/browser-peer';
    document.body.append(peer);
    await eventually(() => peer.contentWindow.BSREConsentBridge?.permissions().advertising === true, 'peer_starts_granted');
    const saved = bridge.save({analytics: false, ad_measurement: false, personalization: false});
    check(denied() && bridge.isPending(), 'synchronous_withdrawal');
    check(sessionStorage.getItem('BSRE_AD_ATTRIBUTION_V1') === null, 'owned_storage_cleared');
    check(!document.cookie.includes('bsre_enq_ads_lab=') && document.cookie.includes('unrelated_lab=1'), 'scoped_cookie_cleanup');
    await eventually(() => peer.contentWindow.BSREConsentBridge?.permissions().advertising === false, 'peer_denies_after_withdrawal');
    if (window.BSREProbeWithdrawalOutage) {
      check(!await saved && denied() && bridge.isPending(), 'server_outage_fails_closed');
      check(peer.contentWindow.BSREConsentBridge.isPending(), 'peer_stays_pending_after_outage');
      location.replace('/browser-pending');
      return;
    }
    check(await saved && denied() && !bridge.isPending(), 'withdrawal_acknowledged');
    check(await bridge.refresh() && bridge.getSnapshot().known && denied(), 'withdrawal_readback');
    await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'PASS'})});
  } catch (error) {
    await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'FAIL', check: error.message})});
  }
}());
