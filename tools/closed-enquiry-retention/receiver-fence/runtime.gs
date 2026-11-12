/* Lab-only extension. No HTTP route, real provider, scheduler or deployment is supplied. */
var CLOSED_NO_COPY_CONTRACT = 'bsre-closed-no-mail-copy-v1';
var CLOSED_NO_COPY_WINDOW = 2592000;
var CLOSED_NO_COPY_FLOOR = 'bsre.closed-no-copy.floor';
var CLOSED_NO_COPY_META_TAB = 'BSRE Synthetic Retention Runtime';
function closedNoCopyFail_(code) { throw new Error(code); }
function closedNoCopyKeys_(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).sort().join(',') !== keys.slice().sort().join(',')) closedNoCopyFail_('NO_COPY_SCHEMA_INVALID');
}
function closedNoCopyCanonical_(value) {
  if (Array.isArray(value)) return value.map(closedNoCopyCanonical_);
  if (value && typeof value === 'object') {
    var sorted = {}; Object.keys(value).sort().forEach(function(key) { sorted[key] = closedNoCopyCanonical_(value[key]); }); return sorted;
  }
  return value;
}
function closedNoCopyHash_(value) {
  return hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,JSON.stringify(closedNoCopyCanonical_(value)),Utilities.Charset.UTF_8));
}
function closedNoCopyHashShape_(value) { return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value); }
function closedNoCopyNow_() { return Math.floor(Date.now()/1000); }
function closedNoCopyFresh_(value, now) {
  if (!Number.isSafeInteger(value.observed_at) || value.observed_at <= 0 || value.observed_at > now
      || !Number.isSafeInteger(value.expires_at) || value.expires_at <= now
      || value.expires_at > value.observed_at + 300) closedNoCopyFail_('NO_COPY_OBSERVATION_STALE');
}
function closedNoCopyLab_() {
  if (typeof BSRE_SYNTHETIC_NO_COPY_LAB !== 'boolean' || BSRE_SYNTHETIC_NO_COPY_LAB !== true
      || typeof ScriptApp !== 'undefined') closedNoCopyFail_('ISOLATED_LAB_ONLY');
}
function closedNoCopyFloor_(gate) {
  var descriptor=retentionAdmissionDescriptor_();
  return {contract:CLOSED_NO_COPY_CONTRACT,namespace:gate.namespace,epoch:gate.epoch,revision:gate.revision,pruned_through:gate.pruned_through,
    generation:descriptor.generation,activated_at:descriptor.activated_at,audience:descriptor.audience,
    admission_hash:gate.admission_hash,restore_policy_hash:gate.restore_policy_hash,source_hash:gate.source_hash};
}
/** Trusted runtime adapter must attest the current namespace after retention reapplication. */
function closedNoCopyControl_() {
  closedNoCopyLab_();
  if (typeof BSREClosedNoCopyRuntime !== 'object' || !BSREClosedNoCopyRuntime
      || typeof BSREClosedNoCopyRuntime.readback !== 'function') closedNoCopyFail_('NO_COPY_RUNTIME_UNVERIFIED');
  var now = closedNoCopyNow_(), gate = BSREClosedNoCopyRuntime.readback(now);
  closedNoCopyKeys_(gate,['contract','namespace','epoch','revision','pruned_through','admission_hash','admission_descriptor_hash','source_hash',
    'restore_policy_hash','observed_at','expires_at','recovery']);
  if (gate.contract !== CLOSED_NO_COPY_CONTRACT || gate.namespace !== 'SYNTHETIC_BSRE_NO_COPY'
      || !Number.isSafeInteger(gate.revision) || gate.revision < 1 || !Number.isSafeInteger(gate.pruned_through)
      || gate.pruned_through < 0 || gate.pruned_through > gate.revision) closedNoCopyFail_('NO_COPY_RUNTIME_UNVERIFIED');
  ['epoch','admission_hash','source_hash','restore_policy_hash','admission_descriptor_hash'].forEach(function(key) {
    if (!closedNoCopyHashShape_(gate[key])) closedNoCopyFail_('NO_COPY_RUNTIME_UNVERIFIED');
  });
  closedNoCopyFresh_(gate,now);
  var descriptor = retentionAdmissionDescriptor_();
  if (descriptor.mode !== 'ENFORCED' || closedNoCopyHash_(descriptor) !== gate.admission_descriptor_hash)
    closedNoCopyFail_('NO_COPY_ADMISSION_UNVERIFIED');
  closedNoCopyKeys_(gate.recovery,['contract','window_seconds','restore_fenced','backups_expired_through']);
  if (gate.recovery.contract !== 'bsre-retention-admission-v1' || gate.recovery.window_seconds !== CLOSED_NO_COPY_WINDOW
      || gate.recovery.restore_fenced !== true || !Number.isSafeInteger(gate.recovery.backups_expired_through)
      || gate.recovery.backups_expired_through < 0 || gate.recovery.backups_expired_through > now)
    closedNoCopyFail_('NO_COPY_RECOVERY_UNVERIFIED');
  var raw = PropertiesService.getScriptProperties().getProperty(CLOSED_NO_COPY_FLOOR);
  if (typeof raw !== 'string' || raw !== JSON.stringify(closedNoCopyCanonical_(closedNoCopyFloor_(gate))))
    closedNoCopyFail_('NO_COPY_FLOOR_UNVERIFIED');
  return gate;
}
function closedNoCopyStore_(gate) {
  var floor=closedNoCopyCanonical_(closedNoCopyFloor_(gate)), keys=Object.keys(floor);
  var sheet=SpreadsheetApp.openById(routingConfig_().sheetId).getSheetByName(CLOSED_NO_COPY_META_TAB);
  if (!sheet || sheet.getLastRow() !== 2
      || JSON.stringify(sheet.getRange(1,1,1,keys.length).getValues()[0]) !== JSON.stringify(keys))
    closedNoCopyFail_('NO_COPY_STORE_UNVERIFIED');
  var values=sheet.getRange(2,1,1,keys.length).getValues()[0], actual={};
  keys.forEach(function(key,index) { actual[key]=values[index]; });
  if (JSON.stringify(actual) !== JSON.stringify(floor)) closedNoCopyFail_('NO_COPY_STORE_EPOCH_CONFLICT');
  return {sheet:sheet,body:actual};
}
function closedNoCopyGate_() {
  var gate=closedNoCopyControl_(); closedNoCopyStore_(gate); return gate;
}
function closedNoCopyAdvance_(gate) {
  if (typeof BSREClosedNoCopyRuntime.advanceRetirement !== 'function') closedNoCopyFail_('NO_COPY_EPOCH_AUTHORITY_UNVERIFIED');
  BSREClosedNoCopyRuntime.advanceRetirement(closedNoCopyFloor_(gate));
  var next=closedNoCopyControl_(), before=closedNoCopyFloor_(gate), after=closedNoCopyFloor_(next);
  if (next.revision !== gate.revision + 1 || next.epoch === gate.epoch) closedNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
  delete before.epoch; delete before.revision; delete after.epoch; delete after.revision;
  if (closedNoCopyHash_(before) !== closedNoCopyHash_(after)) closedNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
  return next;
}
function closedNoCopyStamp_(before,after) {
  var store=closedNoCopyStore_(before), floor=closedNoCopyCanonical_(closedNoCopyFloor_(after));
  store.sheet.getRange(2,1,1,Object.keys(floor).length).setValues([Object.values(floor)]); SpreadsheetApp.flush();
  closedNoCopyStore_(after);
}
function closedNoCopyScope_(scope, gate) {
  closedNoCopyKeys_(scope,['contract','closure_id','closure_revision','closure_hash','request_id','lead_id','event_id','fingerprint','admission_hash']);
  var uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
  if (scope.contract !== CLOSED_NO_COPY_CONTRACT || typeof scope.closure_id !== 'string' || !uuid.test(scope.closure_id)
      || typeof scope.request_id !== 'string' || !uuid.test(scope.request_id)
      || typeof scope.lead_id !== 'string' || scope.lead_id.slice(0,5) !== 'BSRE-' || !uuid.test(scope.lead_id.slice(5))
      || typeof scope.event_id !== 'string' || scope.event_id.slice(0,4) !== 'evt_' || !uuid.test(scope.event_id.slice(4))
      || !Number.isSafeInteger(scope.closure_revision) || scope.closure_revision < 1
      || !closedNoCopyHashShape_(scope.closure_hash) || !closedNoCopyHashShape_(scope.fingerprint)
      || scope.admission_hash !== gate.admission_hash) closedNoCopyFail_('NO_COPY_SCOPE_CONFLICT');
}
function closedNoCopyKey_(requestId) { return 'bsre.closed-no-copy.' + requestId; }
function closedNoCopyMac_(body) {
  return hex_(Utilities.computeHmacSha256Signature(CLOSED_NO_COPY_CONTRACT+'\n'+JSON.stringify(closedNoCopyCanonical_(body)),routingConfig_().secret,Utilities.Charset.UTF_8));
}
function closedNoCopyFence_(requestId, gate) {
  var raw = PropertiesService.getScriptProperties().getProperty(closedNoCopyKey_(requestId));
  if (raw === null) return null;
  if (typeof raw !== 'string' || raw.length > 4096) closedNoCopyFail_('NO_COPY_FENCE_CORRUPT');
  var value; try { value=JSON.parse(raw); } catch (_) { closedNoCopyFail_('NO_COPY_FENCE_CORRUPT'); }
  closedNoCopyKeys_(value,['body','signature']);
  var body=value.body;
  var bodyKeys=['scope','scope_hash','created_at','expires_at','floor'];
  if (Object.prototype.hasOwnProperty.call(body,'owner_intent_digest')) {
    bodyKeys.push('owner_intent_digest');
    if (!closedNoCopyHashShape_(body.owner_intent_digest)) closedNoCopyFail_('NO_COPY_FENCE_CORRUPT');
  }
  closedNoCopyKeys_(body,bodyKeys);
  closedNoCopyScope_(body.scope,gate);
  var current=closedNoCopyFloor_(gate), prior=body.floor;
  closedNoCopyKeys_(prior,Object.keys(current));
  var stableCurrent=closedNoCopyCanonical_(current), stablePrior=closedNoCopyCanonical_(prior);
  delete stableCurrent.epoch; delete stableCurrent.revision; delete stablePrior.epoch; delete stablePrior.revision;
  delete stableCurrent.pruned_through; delete stablePrior.pruned_through;
  if (body.scope.request_id !== requestId || body.scope_hash !== closedNoCopyHash_(body.scope)
      || !closedNoCopyHashShape_(prior.epoch) || !Number.isSafeInteger(prior.revision) || prior.revision < 1 || prior.revision > current.revision
      || !Number.isSafeInteger(prior.pruned_through) || prior.pruned_through < 0 || prior.pruned_through > current.pruned_through
      || closedNoCopyHash_(stablePrior) !== closedNoCopyHash_(stableCurrent)
      || !Number.isSafeInteger(body.created_at) || body.created_at <= 0 || body.created_at > closedNoCopyNow_()
      || body.expires_at !== body.created_at + CLOSED_NO_COPY_WINDOW
      || !same_(closedNoCopyMac_(body),value.signature)) closedNoCopyFail_('NO_COPY_FENCE_CORRUPT');
  return value;
}
function closedNoCopyRow_(row, scope) {
  if (row.length !== LEAD_HEADERS.length || row[0] !== scope.request_id || row[1] !== scope.lead_id
      || row[2] !== scope.event_id || row[4] !== scope.fingerprint || typeof row[5] !== 'string'
      || hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,row[5],Utilities.Charset.UTF_8)) !== scope.fingerprint)
    closedNoCopyFail_('NO_COPY_ROW_CONFLICT');
  var normalized=validateLead_(JSON.parse(row[5]));
  if (normalized.request_id !== scope.request_id || JSON.stringify(normalized) !== row[5]) closedNoCopyFail_('NO_COPY_ROW_CONFLICT');
}
function closedNoCopyMailbox_(scope, now) {
  if (typeof BSREClosedNoCopyMailbox !== 'object' || !BSREClosedNoCopyMailbox
      || typeof BSREClosedNoCopyMailbox.readback !== 'function') closedNoCopyFail_('NO_COPY_MAILBOX_UNVERIFIED');
  var value=BSREClosedNoCopyMailbox.readback(scope,now);
  closedNoCopyKeys_(value,['scope_hash','mailbox','result','complete','includes_trash','observed_at','expires_at','evidence_reference','evidence_hash']);
  if (value.scope_hash !== closedNoCopyHash_(scope) || value.mailbox !== LEAD_RECIPIENT || value.result !== 'ABSENT'
      || value.complete !== true || value.includes_trash !== true || !closedNoCopyHashShape_(value.evidence_hash)
      || typeof value.evidence_reference !== 'string' || value.evidence_reference.length < 1
      || value.evidence_reference.length > 256 || value.evidence_reference.trim() !== value.evidence_reference
      || /[\x00-\x1f\x7f]/.test(value.evidence_reference))
    closedNoCopyFail_('NO_COPY_MAILBOX_UNVERIFIED');
  closedNoCopyFresh_(value,now); return value;
}
function closedNoCopyAssertRequest_(requestId) {
  if (closedNoCopyFence_(requestId,closedNoCopyGate_())) closedNoCopyFail_('NO_COPY_REQUEST_RETIRED');
}
function closedNoCopyAssertMutable_(row) {
  if (!closedNoCopyMaySend_(row)) closedNoCopyFail_('NO_COPY_REQUEST_RETIRED');
}
function closedNoCopyMaySend_(row) {
  var gate=closedNoCopyGate_(), fence;
  // Uncertain custody defers this row, preserving delivery of unrelated healthy rows.
  // The separate exact readback still rejects missing/corrupt fences as unverified.
  try { fence=closedNoCopyFence_(row[0],gate); }
  catch (_) { return false; }
  if (fence) return false;
  if (row[6] === 'RETIRED_NO_COPY') return false;
  return true;
}
/** Callable local capability only. Fence commits before changing the existing outbox status cell. */
function closedNoCopyRetire(scope) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try { return closedNoCopyRetireLocked_(scope,null); }
  finally { lock.releaseLock(); }
}
/** Separate owner capability; a real independently authenticated intent adapter is not supplied. */
function closedNoCopyRetireAuthorized(scope, intentDigest) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var gate=closedNoCopyGate_(); closedNoCopyScope_(scope,gate);
    if (!closedNoCopyHashShape_(intentDigest) || typeof BSREClosedNoCopyOwnerIntent !== 'object'
        || !BSREClosedNoCopyOwnerIntent || typeof BSREClosedNoCopyOwnerIntent.readback !== 'function')
      closedNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    var now=closedNoCopyNow_(), authorization=BSREClosedNoCopyOwnerIntent.readback(intentDigest,now);
    if (!authorization) closedNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    closedNoCopyKeys_(authorization,['contract','intent_digest','actor','scope_hash','approved_at','create_before','recovery_until']);
    if (authorization.contract !== 'bsre-owner-no-mail-authorization-v1' || authorization.intent_digest !== intentDigest
        || authorization.scope_hash !== closedNoCopyHash_(scope) || typeof authorization.actor !== 'string'
        || authorization.actor.length < 1 || authorization.actor.length > 256 || authorization.actor.trim() !== authorization.actor
        || /[\x00-\x1f\x7f]/.test(authorization.actor)
        || !Number.isSafeInteger(authorization.approved_at) || authorization.approved_at <= 0 || authorization.approved_at > now
        || !Number.isSafeInteger(authorization.create_before) || authorization.create_before <= authorization.approved_at
        || authorization.create_before > authorization.approved_at + 900
        || authorization.recovery_until !== authorization.approved_at + CLOSED_NO_COPY_WINDOW)
      closedNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    return closedNoCopyRetireLocked_(scope,authorization);
  } finally { lock.releaseLock(); }
}
function closedNoCopyRetireLocked_(scope, authorization) {
    var gate=closedNoCopyGate_(); closedNoCopyScope_(scope,gate);
    var s=leadSheet_(routingConfig_()), found=existingLead_(s,scope.request_id,0);
    if (!found) closedNoCopyFail_('NO_COPY_ROW_MISSING');
    closedNoCopyRow_(found.values,scope);
    var fence=closedNoCopyFence_(scope.request_id,gate), row=found.values;
    if (fence && fence.body.scope_hash !== closedNoCopyHash_(scope)) closedNoCopyFail_('NO_COPY_SCOPE_CONFLICT');
    if (authorization && fence && fence.body.owner_intent_digest !== authorization.intent_digest) closedNoCopyFail_('RETIREMENT_OWNER_INTENT_CONFLICT');
    if (row[7] !== 0 || row[10] !== '' || row[25] !== ''
        || ['QUEUED','RETRY_WAIT','NEEDS_REVIEW','RETIRED_NO_COPY'].indexOf(row[6]) < 0)
      closedNoCopyFail_('NO_COPY_OUTBOX_AMBIGUOUS');
    if (row[6] === 'RETIRED_NO_COPY' && !fence) closedNoCopyFail_('NO_COPY_FENCE_MISSING');
    closedNoCopyMailbox_(scope,closedNoCopyNow_());
    if (authorization) {
      var instant=closedNoCopyNow_();
      if ((!fence && instant >= authorization.create_before) || instant >= authorization.recovery_until
          || (fence && (fence.body.created_at < authorization.approved_at || fence.body.created_at >= authorization.create_before)))
        closedNoCopyFail_('RETIREMENT_AUTHORIZATION_EXPIRED');
    }
    var priorGate=gate;
    if (!fence) {
      gate=closedNoCopyAdvance_(gate);
      var now=closedNoCopyNow_();
      if (authorization && (now >= authorization.create_before || now >= authorization.recovery_until)) closedNoCopyFail_('RETIREMENT_AUTHORIZATION_EXPIRED');
      var body={scope:scope,scope_hash:closedNoCopyHash_(scope),created_at:now,
        expires_at:now+CLOSED_NO_COPY_WINDOW,floor:closedNoCopyFloor_(gate)};
      if (authorization) body.owner_intent_digest=authorization.intent_digest;
      fence={body:body,signature:closedNoCopyMac_(body)};
      var raw=JSON.stringify(fence), props=PropertiesService.getScriptProperties();
      props.setProperty(closedNoCopyKey_(scope.request_id),raw);
      if (props.getProperty(closedNoCopyKey_(scope.request_id)) !== raw) closedNoCopyFail_('NO_COPY_FENCE_UNCONFIRMED');
    }
    mailState_(s,found.number,'RETIRED_NO_COPY',0,'','','','');
    // A pre-retirement snapshot retains its previous epoch and cannot reopen after fence pruning.
    // An interrupted transition remains held until an explicit current-retention reapplication.
    if (gate.epoch !== priorGate.epoch) {
      closedNoCopyStamp_(priorGate,gate);
    }
    return closedNoCopyReadbackLocked_(scope,false);
}
/** Missing row/fence or errors never establish a positively eligible UNRETIRED state. */
function closedNoCopyInspectRetirement(scope) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var gate=closedNoCopyGate_(); closedNoCopyScope_(scope,gate);
    var found=existingLead_(leadSheet_(routingConfig_()),scope.request_id,0);
    if (!found) closedNoCopyFail_('NO_COPY_ROW_MISSING');
    closedNoCopyRow_(found.values,scope);
    var fence=closedNoCopyFence_(scope.request_id,gate), row=found.values;
    if (fence) return {contract:'bsre-no-mail-retirement-inspection-v1',scope_hash:closedNoCopyHash_(scope),state:'RETIRED',
      proof:closedNoCopyReadbackLocked_(scope,false)};
    if (row[7] !== 0 || row[10] !== '' || row[25] !== '' || ['QUEUED','RETRY_WAIT','NEEDS_REVIEW'].indexOf(row[6]) < 0)
      closedNoCopyFail_('NO_COPY_OUTBOX_AMBIGUOUS');
    var now=closedNoCopyNow_(), store=closedNoCopyStore_(gate).body;
    return {contract:'bsre-no-mail-retirement-inspection-v1',scope_hash:closedNoCopyHash_(scope),state:'UNRETIRED',
      current_store:store,external_floor_hash:closedNoCopyHash_(store),source_hash:gate.source_hash,restore_policy_hash:gate.restore_policy_hash,
      mailbox:closedNoCopyMailbox_(scope,now),row_status:row[6],attempt_count:row[7],send_started_at:row[25],sent_at:row[10],
      observed_at:now,expires_at:now+300};
  } finally { lock.releaseLock(); }
}
function closedNoCopyReadbackLocked_(scope, cleanup, ticket) {
  var gate=closedNoCopyGate_(); closedNoCopyScope_(scope,gate);
  var fence=closedNoCopyFence_(scope.request_id,gate), now=closedNoCopyNow_();
  if (!fence && cleanup && ticket) fence=closedNoCopyTicketFence_(ticket,scope,gate,now);
  if (!fence || fence.body.scope_hash !== closedNoCopyHash_(scope)) closedNoCopyFail_('NO_COPY_FENCE_MISSING');
  if ((!cleanup && now >= fence.body.expires_at) || (cleanup && (now < fence.body.expires_at
      || gate.recovery.backups_expired_through < fence.body.created_at))) closedNoCopyFail_('NO_COPY_RECOVERY_UNVERIFIED');
  var found=existingLead_(leadSheet_(routingConfig_()),scope.request_id,0);
  if (found) {
    closedNoCopyRow_(found.values,scope);
    if (found.values[6] !== 'RETIRED_NO_COPY' || found.values[7] !== 0 || found.values[10] !== '' || found.values[25] !== '')
      closedNoCopyFail_('NO_COPY_ROW_CONFLICT');
  }
  var currentStore=closedNoCopyStore_(gate).body, fenceHash=closedNoCopyHash_(fence), receipt=null;
  if (cleanup) receipt=closedNoCopyCleanupReceipt_(scope,fenceHash,currentStore,gate,now);
  var proof={schema_version:1,scope:scope,scope_hash:fence.body.scope_hash,fence_hash:fenceHash,
    epoch:fence.body.floor.epoch,fence_revision:fence.body.floor.revision,source_hash:gate.source_hash,restore_policy_hash:gate.restore_policy_hash,
    fence_created_at:fence.body.created_at,fence_expires_at:fence.body.expires_at,row_state:found?'RETIRED':'ABSENT',
    mailbox:closedNoCopyMailbox_(scope,now),observed_at:now,expires_at:now+300,recovery:gate.recovery,
    current_store:currentStore,external_floor_hash:closedNoCopyHash_(closedNoCopyFloor_(gate)),cleanup_receipt:receipt};
  if (fence.body.owner_intent_digest) proof.owner_intent_digest=fence.body.owner_intent_digest;
  return proof;
}
function closedNoCopyCleanupReceipt_(scope,fenceHash,store,gate,now) {
  if (typeof BSREClosedNoCopyRuntime.cleanupReceipt !== 'function') closedNoCopyFail_('NO_COPY_CUSTODY_UNVERIFIED');
  var scopeHash=closedNoCopyHash_(scope), floorHash=closedNoCopyHash_(closedNoCopyFloor_(gate)), storeHash=closedNoCopyHash_(store);
  var receipt=BSREClosedNoCopyRuntime.cleanupReceipt(scopeHash,fenceHash,floorHash,storeHash,now);
  closedNoCopyKeys_(receipt,['contract','scope_hash','fence_hash','external_floor_hash','store_hash',
    'backups_expired_through','observed_at','expires_at','evidence_reference','evidence_hash']);
  if (receipt.contract !== 'bsre-no-copy-cleanup-v1' || receipt.scope_hash !== scopeHash || receipt.fence_hash !== fenceHash
      || receipt.external_floor_hash !== floorHash || receipt.store_hash !== storeHash
      || receipt.backups_expired_through !== gate.recovery.backups_expired_through
      || !closedNoCopyHashShape_(receipt.evidence_hash) || typeof receipt.evidence_reference !== 'string'
      || receipt.evidence_reference.length < 1 || receipt.evidence_reference.length > 256)
    closedNoCopyFail_('NO_COPY_CUSTODY_UNVERIFIED');
  closedNoCopyFresh_(receipt,now); return receipt;
}
function closedNoCopyReadback(scope, cleanup, ticket) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try { return closedNoCopyReadbackLocked_(scope,cleanup === true,ticket); } finally { lock.releaseLock(); }
}
function closedNoCopyTicketMac_(body) {
  return hex_(Utilities.computeHmacSha256Signature('bsre-no-copy-cleanup-ticket-v1\n'+JSON.stringify(closedNoCopyCanonical_(body)),routingConfig_().secret,Utilities.Charset.UTF_8));
}
function closedNoCopyTicketFence_(ticket,scope,gate,now) {
  closedNoCopyKeys_(ticket,['body','signature']);
  var body=ticket.body; closedNoCopyKeys_(body,['contract','fence','floor','issued_at']);
  var floor=closedNoCopyFloor_(gate), prior=body.floor;
  closedNoCopyKeys_(prior,Object.keys(floor));
  if (body.contract !== 'bsre-no-copy-cleanup-ticket-v1' || !Number.isSafeInteger(body.issued_at) || body.issued_at > now
      || !same_(ticket.signature,closedNoCopyTicketMac_(body)) || prior.pruned_through < body.fence.body.floor.revision
      || prior.revision > floor.revision || prior.pruned_through > floor.pruned_through)
    closedNoCopyFail_('NO_COPY_CLEANUP_TICKET_INVALID');
  var currentStable=closedNoCopyCanonical_(floor), priorStable=closedNoCopyCanonical_(prior);
  ['epoch','revision','pruned_through'].forEach(function(key) { delete currentStable[key]; delete priorStable[key]; });
  if (closedNoCopyHash_(currentStable) !== closedNoCopyHash_(priorStable)
      || body.fence.body.scope_hash !== closedNoCopyHash_(scope) || !same_(body.fence.signature,closedNoCopyMac_(body.fence.body)))
    closedNoCopyFail_('NO_COPY_CLEANUP_TICKET_INVALID');
  closedNoCopyScope_(body.fence.body.scope,gate);
  return body.fence;
}
/** Historical signed intent is kept only in the existing private workflow journal. */
function closedNoCopyPrepareCleanup(scope) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var proof=closedNoCopyReadbackLocked_(scope,true), gate=closedNoCopyGate_();
    var fence=closedNoCopyFence_(scope.request_id,gate);
    if (typeof BSREClosedNoCopyRuntime.advancePrune !== 'function') closedNoCopyFail_('NO_COPY_EPOCH_AUTHORITY_UNVERIFIED');
    BSREClosedNoCopyRuntime.advancePrune(closedNoCopyFloor_(gate),fence.body.floor.revision);
    var next=closedNoCopyControl_(), before=closedNoCopyFloor_(gate), after=closedNoCopyFloor_(next);
    if (next.revision !== gate.revision + 1 || next.epoch === gate.epoch
        || next.pruned_through !== Math.max(gate.pruned_through,fence.body.floor.revision)) closedNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
    ['epoch','revision','pruned_through'].forEach(function(key) { delete before[key]; delete after[key]; });
    if (closedNoCopyHash_(before) !== closedNoCopyHash_(after)) closedNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
    closedNoCopyStamp_(gate,next);
    // Recheck the fresh custody receipt against the newly stamped actual store and external floor.
    closedNoCopyReadbackLocked_(scope,true);
    var body={contract:'bsre-no-copy-cleanup-ticket-v1',fence:fence,floor:closedNoCopyFloor_(next),issued_at:closedNoCopyNow_()};
    return {body:body,signature:closedNoCopyTicketMac_(body)};
  } finally { lock.releaseLock(); }
}
/** Backup/restore authority is mandatory; missing state never means a fence expired successfully. */
function closedNoCopyForget(scope,ticket) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var gate=closedNoCopyGate_(); closedNoCopyTicketFence_(ticket,scope,gate,closedNoCopyNow_());
    closedNoCopyReadbackLocked_(scope,true,ticket);
    var props=PropertiesService.getScriptProperties(); props.deleteProperty(closedNoCopyKey_(scope.request_id));
    if (props.getProperty(closedNoCopyKey_(scope.request_id)) !== null) closedNoCopyFail_('NO_COPY_CUSTODY_UNCONFIRMED');
    return true;
  } finally { lock.releaseLock(); }
}
