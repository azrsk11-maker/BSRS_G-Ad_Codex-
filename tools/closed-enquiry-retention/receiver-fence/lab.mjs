import assert from 'node:assert/strict';
import {createHash, createHmac, randomUUID} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {lab} from '../../staging-lab/receiver-lab.mjs';
import {buildNoMailCopyReceiver} from './build-candidate.mjs';

const source = readFileSync(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs', import.meta.url));
const built = buildNoMailCopyReceiver(source);
export const sourceHash = createHash('sha256').update(built).digest('hex');
export function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
export function digest(value) { return createHash('sha256').update(JSON.stringify(canonical(value))).digest('hex'); }

/** Synthetic service doubles only; lock instrumentation observes the actual source's lock calls. */
export function receiverLab(options = {}) {
  const r = lab(built);
  const state = {clock: options.now ?? Math.floor(Date.now() / 1000), held: false, busy: false,
    storageFault: false, mailbox: 'ABSENT', complete: true, trash: true, staleMailbox: false,
    restoreFenced: true, backupsExpiredThrough: 0, runtimeStale: false, operations: [], onFenceWrite: null,
    epoch: 'e'.repeat(64), revision: 1, prunedThrough: 0, ownerIntents: {}, authorizationDelay: 0};
  const stored = options.properties ?? r.properties;
  const cfg = {generation: 'a'.repeat(64), audience: 'b'.repeat(64)};
  Object.assign(stored, {RETENTION_ADMISSION_REQUIRED: 'true', RETENTION_ADMISSION_GENERATION: cfg.generation,
    RETENTION_ADMISSION_AUDIENCE: cfg.audience, RETENTION_ADMISSION_ACTIVATED_AT: String(state.clock - 2000)});
  if (options.properties && stored['bsre.closed-no-copy.floor']) {
    const prior = JSON.parse(stored['bsre.closed-no-copy.floor']); state.epoch = prior.epoch; state.revision = prior.revision; state.prunedThrough = prior.pruned_through;
    stored.RETENTION_ADMISSION_ACTIVATED_AT = String(prior.activated_at);
  }
  const requireLock = operation => { assert.equal(state.held, true, `${operation} must hold actual receiver ScriptLock`); state.operations.push(operation); };
  r.context.LockService = {getScriptLock: () => ({tryLock() {
    if (state.held || state.busy) return false;
    state.held = true; return true;
  }, waitLock() { if (state.held || state.busy) throw Error('synthetic lock busy'); state.held = true; },
  releaseLock() { assert.equal(state.held, true); state.held = false; }})};
  r.context.PropertiesService = {getScriptProperties: () => ({getProperties: () => ({...stored}),
    getProperty(key) { requireLock('property-read'); return Object.hasOwn(stored, key) ? stored[key] : null; },
    setProperty(key, value) {
      requireLock('fence-write'); if (state.storageFault) throw Error('synthetic storage unavailable');
      stored[key] = value; if (state.onFenceWrite) state.onFenceWrite(); return this;
    }, deleteProperty(key) { requireLock('fence-delete'); if (state.storageFault) throw Error('synthetic storage unavailable'); delete stored[key]; return this; }})};
  const MailApp = r.context.MailApp;
  r.context.MailApp = {getRemainingDailyQuota: () => { requireLock('quota-read'); return MailApp.getRemainingDailyQuota(); },
    sendEmail: value => { requireLock('actual-source-send'); return MailApp.sendEmail(value); }};
  r.context.Date = class extends Date {
    constructor(...args) { super(...(args.length ? args : [state.clock * 1000])); }
    static now() { return state.clock * 1000; }
  };
  const floor = () => ({contract: 'bsre-closed-no-mail-copy-v1', namespace: 'SYNTHETIC_BSRE_NO_COPY',
    epoch: state.epoch, revision: state.revision, pruned_through: state.prunedThrough, generation: cfg.generation, audience: cfg.audience,
    activated_at: Number(stored.RETENTION_ADMISSION_ACTIVATED_AT), admission_hash: options.admissionHash ?? 'd'.repeat(64),
    source_hash: sourceHash, restore_policy_hash: 'f'.repeat(64)});
  const keys = Object.keys(canonical(floor()));
  const metadata = options.metadata ?? (options.properties ? [] : [keys, keys.map(key => floor()[key])]);
  const metaSheet = {getLastRow() { requireLock('store-metadata-read'); return metadata.length; },
    getRange(row, column, height = 1, width = 1) { return {
      getValues() { requireLock('store-metadata-read'); return Array.from({length: height}, (_, i) => Array.from({length: width}, (_, j) => metadata[row - 1 + i]?.[column - 1 + j] ?? '')); },
      setValues(values) { requireLock('store-metadata-write'); values.forEach((line, i) => { metadata[row - 1 + i] ??= []; line.forEach((value, j) => { metadata[row - 1 + i][column - 1 + j] = value; }); }); },
    }; }};
  const originalSheets = r.context.SpreadsheetApp;
  r.context.SpreadsheetApp = {flush: () => originalSheets.flush(), openById(id) {
    const book = originalSheets.openById(id);
    return {...book, getSheetByName: name => name === 'BSRE Synthetic Retention Runtime' ? metaSheet : book.getSheetByName(name)};
  }};
  r.context.BSRE_SYNTHETIC_NO_COPY_LAB = true;
  r.context.BSREClosedNoCopyRuntime = {readback(now) {
    requireLock('runtime-readback');
    const descriptor = {contract: 'bsre-retention-admission-v1', mode: 'ENFORCED', generation: cfg.generation,
      activated_at: Number(stored.RETENTION_ADMISSION_ACTIVATED_AT), max_age_seconds: 900, audience: cfg.audience};
    return {contract: 'bsre-closed-no-mail-copy-v1', namespace: 'SYNTHETIC_BSRE_NO_COPY', epoch: state.epoch,
      revision: state.revision, pruned_through: state.prunedThrough, admission_hash: options.admissionHash ?? 'd'.repeat(64),
      admission_descriptor_hash: digest(descriptor), source_hash: sourceHash, restore_policy_hash: 'f'.repeat(64),
      observed_at: state.runtimeStale ? now - 301 : now, expires_at: state.runtimeStale ? now : now + 300,
      recovery: {contract: 'bsre-retention-admission-v1', window_seconds: 2592000,
        restore_fenced: state.restoreFenced, backups_expired_through: state.backupsExpiredThrough}};
  }, advanceRetirement(previous) {
    requireLock('external-epoch-advance');
    assert.equal(digest(previous), digest(floor()));
    state.epoch = digest({nonce: randomUUID()}); state.revision++;
    stored['bsre.closed-no-copy.floor'] = JSON.stringify(canonical(floor()));
  }, advancePrune(previous, revision) {
    requireLock('external-prune-boundary');
    assert.equal(digest(previous), digest(floor()));
    state.epoch = digest({nonce: randomUUID()}); state.revision++;
    state.prunedThrough = Math.max(state.prunedThrough, revision);
    stored['bsre.closed-no-copy.floor'] = JSON.stringify(canonical(floor()));
  }, cleanupReceipt(scopeHash, fenceHash, floorHash, storeHash, now) {
    requireLock('cleanup-custody-receipt');
    return {contract: 'bsre-no-copy-cleanup-v1', scope_hash: scopeHash, fence_hash: fenceHash,
      external_floor_hash: floorHash, store_hash: storeHash, backups_expired_through: state.backupsExpiredThrough,
      observed_at: now, expires_at: now + 300, evidence_reference: 'SYNTHETIC_EXPIRED_BACKUPS_AND_CURRENT_REAPPLICATION', evidence_hash: '8'.repeat(64)};
  }};
  r.context.BSREClosedNoCopyOwnerIntent = {readback(intentDigest) {
    requireLock('owner-intent-readback');
    state.clock += state.authorizationDelay;
    return state.ownerIntents[intentDigest] ?? null;
  }};
  r.context.BSREClosedNoCopyMailbox = {readback(scope, now) {
    requireLock('mailbox-readback');
    return {scope_hash: digest(scope), mailbox: 'marketing@blackswanrealestate.ae', result: state.mailbox,
      complete: state.complete, includes_trash: state.trash, observed_at: state.staleMailbox ? now - 301 : now,
      expires_at: state.staleMailbox ? now : now + 300, evidence_reference: 'SYNTHETIC_COMPLETE_MAILBOX_READBACK', evidence_hash: '9'.repeat(64)};
  }};
  // Explicit external test setup. No production bootstrap/reset-floor function exists.
  if (!options.properties) stored['bsre.closed-no-copy.floor'] = JSON.stringify(canonical(floor()));
  // Explicit synthetic operator reapplication, separate from normal reads. Never adopts a restored epoch.
  const reapply = () => {
    const lock = r.context.LockService.getScriptLock(); lock.waitLock();
    try {
      const gate = r.context.closedNoCopyControl_();
      const fences = Object.keys(stored).filter(key => /^bsre\.closed-no-copy\.[a-f0-9]{8}-/.test(key));
      const metadataCurrent = JSON.stringify(metadata) === JSON.stringify([keys, keys.map(key => floor()[key])]);
      if (!metadataCurrent && r.rows.length > 1 && (state.prunedThrough > 0 || fences.length === 0))
        throw Error('NO_COPY_RESTORE_RECONCILIATION_REQUIRED');
      for (const key of fences) {
        const fence = r.context.closedNoCopyFence_(key.slice('bsre.closed-no-copy.'.length), gate);
        const row = r.rows.find(row => row[0] === fence.body.scope.request_id);
        if (row) {
          r.context.closedNoCopyRow_(row, fence.body.scope);
          assert.equal(row[7], 0); assert.equal(row[10], ''); assert.equal(row[25], '');
          row[6] = 'RETIRED_NO_COPY';
        }
      }
      metadata.splice(0, metadata.length, keys, keys.map(key => floor()[key]));
      r.context.closedNoCopyGate_();
    } finally { lock.releaseLock(); }
  };
  const claim = id => {
    const proof = {version: 1, request_id: id, issued_at: state.clock, expires_at: state.clock + 900,
      session_hash: 'c'.repeat(64), generation: cfg.generation, audience: cfg.audience};
    proof.signature = createHmac('sha256', stored.HMAC_SECRET).update(['bsre-retention-admission-v1', id, proof.issued_at,
      proof.expires_at, proof.session_hash, proof.generation, proof.audience].join('\n')).digest('hex');
    return proof;
  };
  const post = (payload, changes = {}) => r.post(payload, {timestamp: String(state.clock * 1000), admission: claim(payload.request_id), ...changes});
  const admit = (payload = r.payload()) => {
    payload.started_at = state.clock * 1000 - 5000;
    const accepted = post(payload); assert.equal(accepted.accepted, true); return {payload, accepted};
  };
  const scope = (closureHash = '1'.repeat(64)) => ({contract: 'bsre-closed-no-mail-copy-v1',
    closure_id: '00000000-0000-4000-8000-000000000001', closure_revision: 1, closure_hash: closureHash,
    request_id: r.rows[1][0], lead_id: r.rows[1][1], event_id: r.rows[1][2], fingerprint: r.rows[1][4], admission_hash: options.admissionHash ?? 'd'.repeat(64)});
  return {...r, post, admit, scope, state, stored, claim, built, sourceHash, metadata, reapply, floor};
}
