import {createHash} from 'node:crypto';

// Derive a review candidate without changing the preserved receiver fixture.
export function buildReceiptStatusCandidate(bytes) {
  if (createHash('sha256').update(bytes).digest('hex') !== '6669cb28e5267a49e061427b736cdbdbad87bee6cbb946e99483d9439f61fa38') {
    throw new Error('RECEIVER_STATUS_SOURCE_CHANGED');
  }
  let code = Buffer.from(bytes).toString('utf8');
  const newline = code.includes('\r\n') ? '\r\n' : '\n';
  function replace(before, after) {
    const anchor = before.replaceAll('\n', newline);
    if (code.split(anchor).length !== 2) throw new Error('RECEIVER_STATUS_ANCHOR_CHANGED');
    code = code.replace(anchor, after.replaceAll('\n', newline));
  }
  replace('function doPost(e) {', `// Receipt recovery has a separate purpose-bound signature and never sends mail.
function receiptStatusEnvelope_(e) {
  var raw = e && e.postData && e.postData.contents;
  if (typeof raw !== 'string' || raw.length > 26000) return null;
  var value;
  try { value = JSON.parse(raw); } catch (_) { return null; }
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  if (!Object.prototype.hasOwnProperty.call(value, 'purpose') && !Object.prototype.hasOwnProperty.call(value, 'request_id')) return null;
  return {value:value,length:raw.length};
}
function receiptStatus_(envelope,cfg) {
  var unknown = {status:'UNCONFIRMED'}, lock, held = false;
  try {
    var value = envelope.value;
    if (envelope.length > 512 || Object.keys(value).sort().join(',') !== 'purpose,request_id,signature,timestamp,version'
      || value.version !== 1 || value.purpose !== 'bsre-receipt-status-v1'
      || typeof value.request_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(value.request_id)
      || typeof value.timestamp !== 'string' || !/^\\d{13}$/.test(value.timestamp)
      || Math.abs(Date.now()-Number(value.timestamp)) > 300000
      || typeof value.signature !== 'string' || !/^[a-f0-9]{64}$/.test(value.signature)) return json_(unknown);
    var signed = 'bsre-receipt-status-v1\\n'+value.timestamp+'\\n'+value.request_id;
    var expected = hex_(Utilities.computeHmacSha256Signature(signed,cfg.secret,Utilities.Charset.UTF_8));
    if (!same_(expected,value.signature)) return json_(unknown);
    lock = LockService.getScriptLock();
    if (!lock.tryLock(10000)) return json_(unknown);
    held = true;
    var found = existingLead_(leadSheet_(cfg),value.request_id,0);
    if (!found || typeof found.values[1] !== 'string' || typeof found.values[2] !== 'string'
      || !/^BSRE-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(found.values[1])
      || !/^evt_[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(found.values[2])) return json_(unknown);
    var stored = found.values[5], fingerprint = found.values[4];
    if (typeof stored !== 'string' || stored.length > 18000 || typeof fingerprint !== 'string') return json_(unknown);
    var normalized = validateLead_(JSON.parse(stored));
    if (normalized.request_id !== value.request_id || JSON.stringify(normalized) !== stored
      || !same_(hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,stored,Utilities.Charset.UTF_8)),fingerprint)) return json_(unknown);
    return json_({status:'ACCEPTED',request_id:value.request_id,lead_id:found.values[1],event_id:found.values[2]});
  } catch (_) {
    return json_(unknown);
  } finally {
    if (held) lock.releaseLock();
  }
}
function doPost(e) {`);
  replace("    var cfg = routingConfig_(); if (!cfg.enabled) throw new Error('ROUTING_DISABLED');\n    var p = validateLead_(authenticate_(e,cfg));", `    var cfg = routingConfig_(); if (!cfg.enabled) throw new Error('ROUTING_DISABLED');
    var statusEnvelope = receiptStatusEnvelope_(e);
    if (statusEnvelope) return receiptStatus_(statusEnvelope,cfg);
    var p = validateLead_(authenticate_(e,cfg));`);
  return code;
}
