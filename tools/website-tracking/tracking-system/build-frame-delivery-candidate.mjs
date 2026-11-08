import {createHash} from 'node:crypto';

// Derive a review candidate from the preserved fixture without changing its bytes.
export function buildFrameDeliveryCandidate(bytes) {
  const hash = createHash('sha256').update(bytes).digest('hex');
  if (hash !== '2e87c3c715d74e09b459d02d706f72008b2edcfd73d0401bd6bfcbee64e9b837') {
    throw new Error('FRAME_ORCHESTRATOR_SOURCE_CHANGED');
  }
  let code = Buffer.from(bytes).toString('utf8');
  function replace(before, after) {
    if (code.split(before).length !== 2) throw new Error('FRAME_ORCHESTRATOR_ANCHOR_CHANGED');
    code = code.replace(before, after);
  }
  replace('    if (state) {\n      state.active = false;', `    if (state) {
      state.active = false;
      for (const entry of state.pending) window.clearTimeout(entry.timer);
      state.pending.clear();`);
  replace('initialized: false, view: false, sequence: 0 };', 'initialized: false, view: false, sequence: 0, pending: new Set() };');
  replace(`  function send(purpose, payload) {
    const state = frames.get(purpose);
    if (!state || !state.active || !allowed(purpose)) return false;
    state.frame.contentWindow.postMessage({ type: 'bsre-runtime-event', version: VERSION, purpose, nonce: state.nonce, sequence: ++state.sequence, payload }, window.location.origin);
    return true;
  }`, `  function postEvent(state, payload) {
    if (!state.active || frames.get(state.purpose) !== state || !allowed(state.purpose)) return false;
    try {
      state.frame.contentWindow.postMessage({ type: 'bsre-runtime-event', version: VERSION, purpose: state.purpose, nonce: state.nonce, sequence: ++state.sequence, payload }, window.location.origin);
      return true;
    } catch (_) { return false; }
  }
  function send(purpose, payload) {
    const state = frames.get(purpose);
    if (!state || !allowed(purpose)) return false;
    if (state.active) return postEvent(state, payload);
    const acceptedEvent = purpose === 'analytics' ? 'generate_lead' : 'accepted_enquiry';
    if (payload?.event_name !== acceptedEvent || state.pending.size >= 32) return false;
    // A single frame owns the queue. There is no storage or retry after posting.
    const entry = {payload, expires: Date.now() + 30000};
    entry.timer = window.setTimeout(() => state.pending.delete(entry), 30000);
    state.pending.add(entry);
    return true;
  }
  function flush(state) {
    for (const entry of state.pending) {
      state.pending.delete(entry);
      window.clearTimeout(entry.timer);
      if (Date.now() < entry.expires) postEvent(state, entry.payload);
    }
  }`);
  replace("    } else if (event.data.type === 'bsre-runtime-active' && event.data.nonce === state.nonce && state.initialized) state.active = true;", `    } else if (event.data.type === 'bsre-runtime-active' && event.data.nonce === state.nonce && state.initialized) {
      state.active = true;
      flush(state);
    }`);
  return code;
}
