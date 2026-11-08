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
  function control(label) {
    const button = [...document.querySelectorAll('#bsre-consent button')].find(node => node.textContent === label);
    check(button, 'missing_control_' + label);
    return button;
  }
  try {
    check(window.isSecureContext && location.protocol === 'https:', 'secure_context');
    check(await bridge.refresh(), 'context_request');
    if (location.pathname === '/browser-peer') return;
    if (location.pathname === '/browser') {
      check(!bridge.getSnapshot().known && denied(), 'fresh_default_denied');
      const inputs = [...document.querySelectorAll('#bsre-consent input[type=checkbox]')];
      check(inputs.length === 2 && inputs.every(input => !input.checked), 'native_dom_defaults_off');
      check(inputs[0].labels[0].textContent.startsWith('Analytics') &&
        inputs[1].labels[0].textContent.startsWith('Ad measurement'), 'separate_labelled_choices');
      inputs[1].click();
      const save = control('Save choices');
      save.focus();
      save.click();
      await eventually(() => bridge.permissions().advertising && !bridge.isPending(), 'advertising_choice');
      check(bridge.permissions().advertising && !bridge.permissions().analytics, 'purpose_separation');
      const toggle = control('Measurement preferences');
      check(document.activeElement === toggle && toggle.getAttribute('aria-expanded') === 'false', 'save_restores_toggle_focus');
      toggle.click();
      const heading = document.getElementById('bsre-consent-heading');
      check(document.activeElement === heading && toggle.getAttribute('aria-expanded') === 'true', 'open_focuses_heading');
      heading.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
      check(document.activeElement === toggle && toggle.getAttribute('aria-expanded') === 'false', 'escape_restores_toggle_focus');
      location.replace('/browser-return');
      return;
    }
    if (location.pathname === '/browser-pending') {
      check(denied() && bridge.isPending(), 'pending_denial_survives_reload');
      check(!bridge.measurementEligible(), 'pending_not_eligible');
      control('Reject optional measurement').click();
      await eventually(() => denied() && !bridge.isPending(), 'retry_acknowledged');
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
    const peer = window.open('/browser-peer', '_blank');
    check(peer && peer !== window && peer.top === peer, 'peer_is_separate_tab');
    await eventually(() => peer.BSREConsentBridge?.permissions().advertising === true, 'peer_starts_granted');
    peer.sessionStorage.setItem('BSRE_AD_ATTRIBUTION_V1', 'peer-only');
    peer.sessionStorage.setItem('unrelated_probe', 'peer-only');
    check(sessionStorage.getItem('BSRE_AD_ATTRIBUTION_V1') === 'synthetic', 'peer_storage_is_independent');
    const saved = bridge.save({analytics: false, ad_measurement: false, personalization: false});
    check(denied() && bridge.isPending(), 'synchronous_withdrawal');
    check(sessionStorage.getItem('BSRE_AD_ATTRIBUTION_V1') === null, 'owned_storage_cleared');
    check(!document.cookie.includes('bsre_enq_ads_lab=') && document.cookie.includes('unrelated_lab=1'), 'scoped_cookie_cleanup');
    await eventually(() => peer.BSREConsentBridge?.permissions().advertising === false, 'peer_denies_after_withdrawal');
    check(peer.sessionStorage.getItem('BSRE_AD_ATTRIBUTION_V1') === null &&
      peer.sessionStorage.getItem('unrelated_probe') === 'peer-only', 'peer_scoped_storage_cleanup');
    if (window.BSREProbeWithdrawalOutage) {
      check(!await saved && denied() && bridge.isPending(), 'server_outage_fails_closed');
      check(peer.BSREConsentBridge.isPending(), 'peer_stays_pending_after_outage');
      peer.close();
      location.replace('/browser-pending');
      return;
    }
    check(await saved && denied() && !bridge.isPending(), 'withdrawal_acknowledged');
    peer.close();
    check(await bridge.refresh() && bridge.getSnapshot().known && denied(), 'withdrawal_readback');
    await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'PASS'})});
  } catch (error) {
    await fetch('/browser-result', {method: 'POST', body: JSON.stringify({status: 'FAIL', check: error.message})});
  }
}());
