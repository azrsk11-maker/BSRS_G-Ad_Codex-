import {createInterface} from 'node:readline';
import {receiverLab, sourceHash, canonical} from './lab.mjs';

// Trusted synthetic source / service substitution over local pipes. No network or Google client.
let r;
let coldConfigured = false;
let fixtureAgingClosed = false;
const agedRequests = new Set();
const syntheticKey = 'synthetic-key-'.repeat(4);
for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
  try {
    if (line.length > 32768) throw Error('SYNTHETIC_BRIDGE_INPUT_INVALID');
    const message = JSON.parse(line);
    let value;
    if (message.action === 'metadata') value = {source_hash: sourceHash};
    else if (message.action === 'cold_init') {
      if (r || !Number.isSafeInteger(message.now) || message.now <= 0
          || !message.descriptor || !/^[a-f0-9]{64}$/.test(message.admission_hash)) throw Error('SYNTHETIC_COLD_INIT_INVALID');
      r = receiverLab({now: message.now, admissionHash: message.admission_hash, descriptor: message.descriptor});
      value = {rows: r.rows.length - 1, source_hash: sourceHash};
    }
    else if (message.action === 'init') {
      if (r) throw Error('SYNTHETIC_BRIDGE_ALREADY_INITIALIZED');
      r = receiverLab({now: message.accepted_at, admissionHash: message.admission_hash});
      r.admit(); r.state.clock = message.now;
      r.stored.RETENTION_ADMISSION_ACTIVATED_AT = String(message.activated_at);
      // Explicit trusted synthetic activation before any retirement, mirrored into both stores.
      r.stored['bsre.closed-no-copy.floor'] = JSON.stringify(canonical(r.floor()));
      r.metadata[1] = r.metadata[0].map(key => r.floor()[key]);
      value = {request_id: r.rows[1][0], lead_id: r.rows[1][1], event_id: r.rows[1][2], fingerprint: r.rows[1][4]};
    } else {
      if (!r) throw Error('SYNTHETIC_BRIDGE_NOT_INITIALIZED');
      if (message.now !== undefined) r.state.clock = message.now;
      if (message.action === 'configure') {
        if (coldConfigured || r.rows.length !== 1 || message.synthetic_hmac !== syntheticKey
            || JSON.stringify(canonical(message.descriptor)) !== JSON.stringify(canonical(r.context.retentionAdmissionDescriptor_())))
          throw Error('SYNTHETIC_CONFIGURE_INVALID');
        r.stored.HMAC_SECRET = syntheticKey; coldConfigured = true;
        value = r.context.retentionAdmissionDescriptor_();
      }
      else if (message.action === 'post_wire') {
        if (!coldConfigured || typeof message.raw !== 'string' || message.raw.length > 24000) throw Error('SYNTHETIC_POST_WIRE_INVALID');
        value = r.postWire(message.raw);
      }
      else if (message.action === 'admission_descriptor') value = r.context.retentionAdmissionDescriptor_();
      else if (message.action === 'admitted_identity') {
        const matches = r.rows.slice(1).filter(row => row[0] === message.request_id);
        if (matches.length !== 1) throw Error('SYNTHETIC_ADMITTED_IDENTITY_INVALID');
        const row = matches[0];
        value = {request_id: row[0], lead_id: row[1], event_id: row[2], accepted_at_utc: row[3],
          fingerprint: row[4], columns: row.length, email_status: row[6], email_attempts: row[7]};
      }
      else if (message.action === 'fixture_age_acceptance') {
        // Explicit elapsed-time fixture setup only, before any fence, binding or reviewed plan.
        const matches = r.rows.map((row, index) => row[0] === message.request_id ? index : -1).filter(index => index > 0);
        const stamp = Date.parse(message.accepted_at_utc);
        if (fixtureAgingClosed || agedRequests.has(message.request_id) || matches.length !== 1
            || !Number.isFinite(stamp) || new Date(stamp).toISOString() !== message.accepted_at_utc
            || Object.keys(r.state.ownerIntents).length || Object.keys(r.state.purgeIntents).length
            || Object.keys(r.stored).some(key => /^bsre\.closed-no-copy\.[a-f0-9]{8}-/.test(key)))
          throw Error('SYNTHETIC_AGING_INVALID');
        const number = matches[0] + 1, row = r.rows[number - 1];
        if (row[1] !== message.lead_id || row[2] !== message.event_id || row[3] !== message.previous_accepted_at_utc
            || stamp >= Date.parse(row[3]) || row[6] !== 'QUEUED' || row[7] !== 0 || row[10] !== '' || row[25] !== '' || r.mail.length)
          throw Error('SYNTHETIC_AGING_INVALID');
        const lock = r.context.LockService.getScriptLock(); lock.waitLock(10000);
        try { r.context.SpreadsheetApp.openById(r.stored.LEAD_SHEET_ID).getSheetByName(r.context.LEAD_TAB)
          .getRange(number, 4, 1, 1).setValues([[message.accepted_at_utc]]); }
        finally { lock.releaseLock(); }
        agedRequests.add(message.request_id);
        value = true;
      }
      else if (message.action === 'retire') { fixtureAgingClosed = true; value = r.context.closedNoCopyRetire(message.scope); }
      else if (message.action === 'inspect_retirement') value = r.context.closedNoCopyInspectRetirement(message.scope);
      else if (message.action === 'authorize_retirement') {
        // Explicit trusted local test substitution, not a live authority or an HTTP endpoint.
        r.state.ownerIntents[message.claim.intent_digest] = message.claim; value = true;
      }
      else if (message.action === 'retire_authorized') { fixtureAgingClosed = true; value = r.context.closedNoCopyRetireAuthorized(message.scope, message.intent_digest); }
      else if (message.action === 'readback') value = r.context.closedNoCopyReadback(message.scope, message.cleanup, message.ticket);
      else if (message.action === 'prepare_cleanup') value = r.context.closedNoCopyPrepareCleanup(message.scope);
      else if (message.action === 'forget') value = r.context.closedNoCopyForget(message.scope, message.ticket);
      else if (message.action === 'intake_inventory') { fixtureAgingClosed = true; value = r.context.closedIntakeInventory(message.scope); }
      else if (message.action === 'authorize_intake_purge') {
        // Only the local PHP adapter's held Journal supplies this synthetic authority substitution.
        r.state.purgeIntents[message.claim.intent_digest] = message.claim; value = true;
      }
      else if (message.action === 'intake_remove_exact') value = r.context.closedIntakeRemoveExact(message.scope, message.binding, message.intent_digest);
      else if (message.action === 'state') {
        const allowed = ['mailbox', 'complete', 'trash', 'staleMailbox', 'restoreFenced', 'backupsExpiredThrough', 'runtimeStale', 'storageFault'];
        if (!allowed.includes(message.key)) throw Error('SYNTHETIC_BRIDGE_STATE_INVALID');
        r.state[message.key] = message.value; value = true;
      } else if (message.action === 'stats') value = {rows: r.rows.length - 1, mail: r.mail.length,
        intake_deletes: r.state.intakeDeletes,
        private_fences: Object.keys(r.stored).filter(key => /^bsre\.closed-no-copy\.[a-f0-9]{8}-/.test(key)).length,
        floor_present: Object.hasOwn(r.stored, 'bsre.closed-no-copy.floor')};
      else throw Error('SYNTHETIC_BRIDGE_ACTION_INVALID');
    }
    process.stdout.write(JSON.stringify({ok: true, value}) + '\n');
  } catch (error) {
    const code = /^[A-Z][A-Z0-9_]{1,63}$/.test(error.message) ? error.message : 'SYNTHETIC_BRIDGE_FAILURE';
    process.stdout.write(JSON.stringify({ok: false, error: code}) + '\n');
  }
}
