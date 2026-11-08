(async function () {
  const bridge = window.BSREConsentBridge;
  const denied = () => !bridge.permissions().advertising && !bridge.permissions().analytics;
  const check = (condition, name) => { if (!condition) throw new Error(name); };
  try {
    check(window.isSecureContext && location.protocol === 'https:', 'secure_context');
    check(await bridge.refresh(), 'context_request');
    if (location.pathname === '/browser') {
      check(!bridge.getSnapshot().known && denied(), 'fresh_default_denied');
      check(document.querySelectorAll('#bsre-consent input[type=checkbox]').length === 2, 'native_dom');
      check(await bridge.save({analytics: false, ad_measurement: true, personalization: false}), 'advertising_choice');
      check(bridge.permissions().advertising && !bridge.permissions().analytics, 'purpose_separation');
      location.replace('/browser-return');
      return;
    }
    check(bridge.permissions().advertising && !bridge.permissions().analytics, 'cookie_across_navigation');
    check(!document.cookie.includes('__Host-bsre_consent='), 'preference_cookie_httponly');
    document.cookie = 'bsre_enq_ads_lab=1; Path=/; Secure; SameSite=Strict';
    document.cookie = 'unrelated_lab=1; Path=/; Secure; SameSite=Strict';
    sessionStorage.setItem('BSRE_AD_ATTRIBUTION_V1', 'synthetic');
    check(document.cookie.includes('bsre_enq_ads_lab=1'), 'owned_cookie_seeded');
    const saved = bridge.save({analytics: false, ad_measurement: false, personalization: false});
    check(denied() && bridge.isPending(), 'synchronous_withdrawal');
    check(sessionStorage.getItem('BSRE_AD_ATTRIBUTION_V1') === null, 'owned_storage_cleared');
    check(!document.cookie.includes('bsre_enq_ads_lab=') && document.cookie.includes('unrelated_lab=1'), 'scoped_cookie_cleanup');
    check(await saved && denied() && !bridge.isPending(), 'withdrawal_acknowledged');
    check(await bridge.refresh() && bridge.getSnapshot().known && denied(), 'withdrawal_readback');
    await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'PASS'})});
  } catch (error) {
    await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'FAIL', check: error.message})});
  }
}());
