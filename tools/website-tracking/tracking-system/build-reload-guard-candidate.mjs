import {createHash} from 'node:crypto';

// Keep the captured WordPress fixture intact. This candidate stores a flag only.
export function buildReloadGuardCandidate(bytes) {
  if (createHash('sha256').update(bytes).digest('hex') !== '3d469cccef9891702ba1462e29f17ba3135261fff23ea2a40c052aa6afb99154') {
    throw new Error('ENQUIRY_CLIENT_SOURCE_CHANGED');
  }
  let code = Buffer.from(bytes).toString('utf8');
  function replace(before, after) {
    if (code.split(before).length !== 2) throw new Error('ENQUIRY_CLIENT_ANCHOR_CHANGED');
    code = code.replace(before, after);
  }
  replace('  function attachForm(form) {', `  const PENDING_ENQUIRY_KEY = 'BSRE_PENDING_ENQUIRY_V1';
  function hasPendingEnquiry() {
    try { return window.sessionStorage.getItem(PENDING_ENQUIRY_KEY) === '1'; }
    catch (_) { return false; }
  }
  function markPendingEnquiry(pending) {
    try {
      if (pending) window.sessionStorage.setItem(PENDING_ENQUIRY_KEY, '1');
      else window.sessionStorage.removeItem(PENDING_ENQUIRY_KEY);
    } catch (_) { /* Keep same-page intake usable when session storage is unavailable. */ }
  }
  function attachForm(form) {`);
  replace('      try { requestId = requestId || uuid(); } catch (_) {', `      if (!attemptBody && hasPendingEnquiry()) {
        showStatus(status, 'Receipt of an earlier enquiry in this tab is still unconfirmed. Please contact us by phone or WhatsApp to check it before submitting again.', 'error');
        return;
      }
      try { requestId = requestId || uuid(); } catch (_) {`);
  replace('        const response = await window.fetch(endpoint,', '        markPendingEnquiry(true);\n        const response = await window.fetch(endpoint,');
  replace("            requestId = ''; attemptBody = '';", "            markPendingEnquiry(false);\n            requestId = ''; attemptBody = '';");
  replace('        completed = true;', '        markPendingEnquiry(false);\n        completed = true;');
  return code;
}
