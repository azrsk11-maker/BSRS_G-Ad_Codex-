import {buildReceiptClientCandidate} from './build-receipt-client-candidate.mjs';

// Compose with the reviewed receipt candidate; keep the captured source intact.
export function buildAttributionClientCandidate(bytes) {
  let code = buildReceiptClientCandidate(bytes);
  function replace(before, after) {
    if (code.split(before).length !== 2) throw new Error('ATTRIBUTION_CLIENT_ANCHOR_CHANGED');
    code = code.replace(before, after);
  }
  replace('  function touchNow(keys, analytics) {', '  function touchNow(keys, analytics, capturedAt, captureId) {');
  replace("timestamp: Date.now(), parameters: parameters };", "timestamp: capturedAt, parameters: parameters, capture_id: captureId };");
  replace("timestamp: value.timestamp, parameters: parameters };", `timestamp: value.timestamp, parameters: parameters,
      capture_id: typeof value.capture_id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value.capture_id) ? value.capture_id : '' };`);
  replace('    const refused = event && event.detail && event.detail.refused;',
    '    const refused = event && event.detail && event.detail.refused;\n    const capturedAt = Date.now();');
  replace('    function refreshTouch(key, keys, analytics, permitted, purpose) {', `    let captureId = '';
    if (eligible && ((allowed.analytics && !pageTouch.analytics && !queryConsumed.analytics)
      || (allowed.advertising && !pageTouch.advertising && !queryConsumed.advertising))) {
      try {
        const id = uuid();
        if (/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id)) captureId = id;
      } catch (_) { /* Missing correlation denies mixed-purpose merging, never intake. */ }
    }
    function refreshTouch(key, keys, analytics, permitted, purpose) {`);
  replace('pageTouch[purpose] = touchNow(keys, analytics);', 'pageTouch[purpose] = touchNow(keys, analytics, capturedAt, captureId);');
  const anchor = '      const result = { first: first, last: last };';
  replace(anchor, `      if (purpose === 'analytics' && now) {
        const previous = validTouch(stored && stored.last, keys, analytics);
        const internalReferrer = now.referrer && new URL(now.referrer).origin === window.location.origin;
        // The owned pages use no-referrer. A queryless continuation without a
        // referrer cannot establish a new acquisition. Keep the observed source.
        // URL parameters remain attribution hints, never permission or identity.
        if (previous && (internalReferrer || (!Object.keys(now.parameters).length && !now.referrer))) last = previous;
      }
${anchor}`);
  replace(`      const base = ad && Object.keys(ad.parameters).length ? ad : analytics || ad;
      result[key] = { landing_page: base.landing_page, referrer: analytics ? analytics.referrer : '', timestamp: base.timestamp, parameters: Object.assign({}, analytics ? analytics.parameters : {}, ad ? ad.parameters : {}) };`,
  `      const base = ad && Object.keys(ad.parameters).length ? ad : analytics || ad;
      // Merge purpose-specific metadata only when it describes the same capture.
      // A later click must not inherit an older source's UTM or referrer fields.
      const sameCapture = analytics && ad && analytics.capture_id && analytics.capture_id === ad.capture_id
        && analytics.landing_page === ad.landing_page && analytics.timestamp === ad.timestamp;
      const analyticsForBase = base === analytics || sameCapture ? analytics : null;
      result[key] = { landing_page: base.landing_page, referrer: analyticsForBase ? analyticsForBase.referrer : '', timestamp: base.timestamp, parameters: Object.assign({}, analyticsForBase ? analyticsForBase.parameters : {}, ad ? ad.parameters : {}) };`);
  return code;
}
