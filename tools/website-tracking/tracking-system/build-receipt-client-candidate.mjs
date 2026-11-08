import {buildReloadGuardCandidate} from './build-reload-guard-candidate.mjs';

// Lab client. The captured plugin remains the input and is never rewritten.
export function buildReceiptClientCandidate(bytes) {
  let code = buildReloadGuardCandidate(bytes);
  function replace(before, after) {
    if (code.split(before).length !== 2) throw new Error('RECOVERY_CLIENT_ANCHOR_CHANGED');
    code = code.replace(before, after);
  }
  replace("  const PENDING_ENQUIRY_KEY = 'BSRE_PENDING_ENQUIRY_V1';", String.raw`  const PENDING_ENQUIRY_KEY = 'BSRE_PENDING_ENQUIRY_V1';
  function recoveryProof() {
    try { return window.sessionStorage.getItem(PENDING_ENQUIRY_KEY); }
    catch (_) { return null; }
  }
  function validProof(value) {
    return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.[1-9][0-9]{0,10}\.[0-9a-f]{64}$/.test(value);
  }
  async function recoveryRequest(endpoint, operation, body) {
    const url = new URL(endpoint);
    if (!url.pathname.endsWith('/bsre/v1/lead')) throw new Error('Unsupported recovery endpoint');
    url.pathname = url.pathname.slice(0, -4) + 'receipt-recovery/' + operation;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 10000);
    try {
      const response = await window.fetch(url.href, {method: 'POST', credentials: 'same-origin',
        cache: 'no-store', headers: requestHeaders(false, null), body: JSON.stringify(body), signal: controller.signal});
      if (!response.ok) throw new Error('Receipt recovery unavailable');
      return await response.json();
    } finally { window.clearTimeout(timeout); }
  }`);
  replace("    try { return window.sessionStorage.getItem(PENDING_ENQUIRY_KEY) === '1'; }", '    try { return recoveryProof() !== null; }');
  replace('  function markPendingEnquiry(pending) {', '  function markPendingEnquiry(pending, proof) {');
  replace("window.sessionStorage.setItem(PENDING_ENQUIRY_KEY, '1')", 'window.sessionStorage.setItem(PENDING_ENQUIRY_KEY, proof)');
  replace("    let requestId = '';", "    let requestId = '';\n    let attemptProof = '';");
  replace('        markPendingEnquiry(true);', '        markPendingEnquiry(true, attemptProof);');
  replace(`      if (!attemptBody && hasPendingEnquiry()) {
        showStatus(status, 'Receipt of an earlier enquiry in this tab is still unconfirmed. Please contact us by phone or WhatsApp to check it before submitting again.', 'error');
        return;
      }
      try { requestId = requestId || uuid(); } catch (_) {`, String.raw`      if (!attemptBody) {
        pending = true;
        button.disabled = true;
        try {
          if (hasPendingEnquiry()) {
            const proof = recoveryProof();
            if (!validProof(proof)) throw new Error('Recovery proof unavailable');
            const result = await recoveryRequest(endpoint, 'status', {proof});
            if (result?.status !== 'ACCEPTED' || typeof result.reference !== 'string' || !/^[A-Za-z0-9._:-]{1,150}$/.test(result.reference)) {
              throw new Error('Receipt unconfirmed');
            }
            markPendingEnquiry(false);
            completed = true;
            button.textContent = 'Enquiry received';
            button.dataset.complete = 'true';
            showStatus(status, 'Your earlier enquiry was received. Reference: ' + result.reference + '.', 'success');
            return;
          }
          const result = await recoveryRequest(endpoint, 'proof', {});
          if (!validProof(result?.proof) || result.request_id !== result.proof.split('.')[0]) throw new Error('Invalid recovery proof');
          requestId = result.request_id;
          attemptProof = result.proof;
        } catch (_) {
          showStatus(status, hasPendingEnquiry() ? 'Your earlier enquiry is still unconfirmed. Please contact us by phone or WhatsApp to check it.' : 'The form could not prepare a secure enquiry. Please try again or contact us by phone or WhatsApp.', 'error');
          return;
        } finally {
          pending = false;
          if (!completed) button.disabled = false;
        }
      }
      try { requestId = requestId || uuid(); } catch (_) {`);
  return code;
}
