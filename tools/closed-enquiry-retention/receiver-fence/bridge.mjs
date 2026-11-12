import {createInterface} from 'node:readline';
import {receiverLab, sourceHash, canonical} from './lab.mjs';

// Trusted synthetic source / service substitution over local pipes. No network or Google client.
let r;
for await (const line of createInterface({input: process.stdin, crlfDelay: Infinity})) {
  try {
    if (line.length > 32768) throw Error('SYNTHETIC_BRIDGE_INPUT_INVALID');
    const message = JSON.parse(line);
    let value;
    if (message.action === 'metadata') value = {source_hash: sourceHash};
    else if (message.action === 'init') {
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
      if (message.action === 'retire') value = r.context.closedNoCopyRetire(message.scope);
      else if (message.action === 'readback') value = r.context.closedNoCopyReadback(message.scope, message.cleanup, message.ticket);
      else if (message.action === 'prepare_cleanup') value = r.context.closedNoCopyPrepareCleanup(message.scope);
      else if (message.action === 'forget') value = r.context.closedNoCopyForget(message.scope, message.ticket);
      else if (message.action === 'state') {
        const allowed = ['mailbox', 'complete', 'trash', 'staleMailbox', 'restoreFenced', 'backupsExpiredThrough', 'runtimeStale', 'storageFault'];
        if (!allowed.includes(message.key)) throw Error('SYNTHETIC_BRIDGE_STATE_INVALID');
        r.state[message.key] = message.value; value = true;
      } else if (message.action === 'purge') {
        const lock = r.context.LockService.getScriptLock(); lock.waitLock();
        try {
          const index = r.rows.findIndex(row => row[0] === message.scope.request_id);
          if (index < 1) throw Error('SYNTHETIC_PURGE_ROW_MISSING');
          r.context.closedNoCopyRow_(r.rows[index], message.scope);
          if (r.rows[index][6] !== 'RETIRED_NO_COPY') throw Error('SYNTHETIC_PURGE_NOT_RETIRED');
          r.rows.splice(index, 1); value = true;
        } finally { lock.releaseLock(); }
      } else if (message.action === 'stats') value = {rows: r.rows.length - 1, mail: r.mail.length,
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
