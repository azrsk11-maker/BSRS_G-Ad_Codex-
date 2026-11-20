/* Derived operational algebra; separate authenticated authority is mandatory and configuration is default OFF. */
var ACTUAL_NO_COPY_CONTRACT = 'bsre-closed-no-mail-copy-v1';
var ACTUAL_NO_COPY_WINDOW = 2592000;
var ACTUAL_NO_COPY_FLOOR = 'bsre.actual-no-copy.floor.v1';
var ACTUAL_NO_COPY_META_TAB = 'BSRE Runtime Retention v1';
function actualNoCopyFail_(code) { throw new Error(code); }
function actualNoCopyKeys_(value, keys) {
  if (!value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).sort().join(',') !== keys.slice().sort().join(',')) actualNoCopyFail_('NO_COPY_SCHEMA_INVALID');
}
function actualNoCopyCanonical_(value) {
  if (Array.isArray(value)) return value.map(actualNoCopyCanonical_);
  if (value && typeof value === 'object') {
    var sorted = {}; Object.keys(value).sort().forEach(function(key) { sorted[key] = actualNoCopyCanonical_(value[key]); }); return sorted;
  }
  return value;
}
function actualNoCopyHash_(value) {
  return hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,JSON.stringify(actualNoCopyCanonical_(value)),Utilities.Charset.UTF_8));
}
function actualNoCopyHashShape_(value) { return typeof value === 'string' && /^[a-f0-9]{64}$/.test(value); }
function actualNoCopyNow_() { return Math.floor(Date.now()/1000); }
function actualNoCopyFresh_(value, now) {
  if (!Number.isSafeInteger(value.observed_at) || value.observed_at <= 0 || value.observed_at > now
      || !Number.isSafeInteger(value.expires_at) || value.expires_at <= now
      || value.expires_at > value.observed_at + 300) actualNoCopyFail_('NO_COPY_OBSERVATION_STALE');
}
function actualNoCopyLab_() {
  var cfg=actualReceiverAuthorityConfig_(); // Separate receiver-only service/enrolment, never the lead HMAC.
  if(PropertiesService.getScriptProperties().getProperty(ACTUAL_CONTROL_ACTIVATION)!==actualControlCanonicalJSON_({namespace:cfg.namespace,source:cfg.source}))
    actualNoCopyFail_('ACTUAL_ENROLMENT_UNVERIFIED');
}
function actualNoCopyFloor_(gate) {
  var descriptor=retentionAdmissionDescriptor_();
  return {contract:ACTUAL_NO_COPY_CONTRACT,namespace:gate.namespace,epoch:gate.epoch,revision:gate.revision,pruned_through:gate.pruned_through,
    generation:descriptor.generation,activated_at:descriptor.activated_at,audience:descriptor.audience,
    admission_hash:gate.admission_hash,restore_policy_hash:gate.restore_policy_hash,source_hash:gate.source_hash};
}
/** Trusted runtime adapter must attest the current namespace after retention reapplication. */
function actualNoCopyControl_() {
  actualNoCopyLab_();
  if (typeof BSREActualNoCopyRuntime !== 'object' || !BSREActualNoCopyRuntime
      || typeof BSREActualNoCopyRuntime.readback !== 'function') actualNoCopyFail_('NO_COPY_RUNTIME_UNVERIFIED');
  var gate = BSREActualNoCopyRuntime.readback(actualNoCopyNow_()), now = actualNoCopyNow_();
  actualNoCopyKeys_(gate,['contract','namespace','epoch','revision','pruned_through','admission_hash','admission_descriptor_hash','source_hash',
    'restore_policy_hash','observed_at','expires_at','recovery']);
  if (gate.contract !== ACTUAL_NO_COPY_CONTRACT || gate.namespace !== actualReceiverAuthorityConfig_().namespace
      || !Number.isSafeInteger(gate.revision) || gate.revision < 1 || !Number.isSafeInteger(gate.pruned_through)
      || gate.pruned_through < 0 || gate.pruned_through > gate.revision) actualNoCopyFail_('NO_COPY_RUNTIME_UNVERIFIED');
  ['epoch','admission_hash','source_hash','restore_policy_hash','admission_descriptor_hash'].forEach(function(key) {
    if (!actualNoCopyHashShape_(gate[key])) actualNoCopyFail_('NO_COPY_RUNTIME_UNVERIFIED');
  });
  actualNoCopyFresh_(gate,now);
  var descriptor = retentionAdmissionDescriptor_();
  if (descriptor.mode !== 'ENFORCED' || actualNoCopyHash_(descriptor) !== gate.admission_descriptor_hash)
    actualNoCopyFail_('NO_COPY_ADMISSION_UNVERIFIED');
  actualNoCopyKeys_(gate.recovery,['contract','window_seconds','restore_fenced','backups_expired_through']);
  if (gate.recovery.contract !== 'bsre-retention-admission-v1' || gate.recovery.window_seconds !== ACTUAL_NO_COPY_WINDOW
      || gate.recovery.restore_fenced !== true || !Number.isSafeInteger(gate.recovery.backups_expired_through)
      || gate.recovery.backups_expired_through < 0 || gate.recovery.backups_expired_through > now)
    actualNoCopyFail_('NO_COPY_RECOVERY_UNVERIFIED');
  var raw = PropertiesService.getScriptProperties().getProperty(ACTUAL_NO_COPY_FLOOR);
  if (typeof raw !== 'string' || raw !== JSON.stringify(actualNoCopyCanonical_(actualNoCopyFloor_(gate))))
    actualNoCopyFail_('NO_COPY_FLOOR_UNVERIFIED');
  return gate;
}
function actualNoCopyStore_(gate) {
  var floor=actualNoCopyCanonical_(actualNoCopyFloor_(gate)), keys=Object.keys(floor);
  var sheet=SpreadsheetApp.openById(routingConfig_().sheetId).getSheetByName(ACTUAL_NO_COPY_META_TAB);
  if (!sheet || sheet.getLastRow() !== 2
      || JSON.stringify(sheet.getRange(1,1,1,keys.length).getValues()[0]) !== JSON.stringify(keys))
    actualNoCopyFail_('NO_COPY_STORE_UNVERIFIED');
  var values=sheet.getRange(2,1,1,keys.length).getValues()[0], actual={};
  keys.forEach(function(key,index) { actual[key]=values[index]; });
  if (JSON.stringify(actual) !== JSON.stringify(floor)) actualNoCopyFail_('NO_COPY_STORE_EPOCH_CONFLICT');
  return {sheet:sheet,body:actual};
}
function actualNoCopyGate_() {
  var gate=actualNoCopyControl_(); actualNoCopyStore_(gate); return gate;
}
function actualNoCopyAdvance_(gate) {
  if (typeof BSREActualNoCopyRuntime.advanceRetirement !== 'function') actualNoCopyFail_('NO_COPY_EPOCH_AUTHORITY_UNVERIFIED');
  BSREActualNoCopyRuntime.advanceRetirement(actualNoCopyFloor_(gate));
  var next=actualNoCopyControl_(), before=actualNoCopyFloor_(gate), after=actualNoCopyFloor_(next);
  if (next.revision !== gate.revision + 1 || next.epoch === gate.epoch) actualNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
  delete before.epoch; delete before.revision; delete after.epoch; delete after.revision;
  if (actualNoCopyHash_(before) !== actualNoCopyHash_(after)) actualNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
  return next;
}
function actualNoCopyStamp_(before,after) {
  var store=actualNoCopyStore_(before), floor=actualNoCopyCanonical_(actualNoCopyFloor_(after));
  store.sheet.getRange(2,1,1,Object.keys(floor).length).setValues([Object.values(floor)]); SpreadsheetApp.flush();
  actualNoCopyStore_(after);
}
function actualNoCopyScope_(scope, gate) {
  actualNoCopyKeys_(scope,['contract','closure_id','closure_revision','closure_hash','request_id','lead_id','event_id','fingerprint','admission_hash']);
  var uuid = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
  if (scope.contract !== ACTUAL_NO_COPY_CONTRACT || typeof scope.closure_id !== 'string' || !uuid.test(scope.closure_id)
      || typeof scope.request_id !== 'string' || !uuid.test(scope.request_id)
      || typeof scope.lead_id !== 'string' || scope.lead_id.slice(0,5) !== 'BSRE-' || !uuid.test(scope.lead_id.slice(5))
      || typeof scope.event_id !== 'string' || scope.event_id.slice(0,4) !== 'evt_' || !uuid.test(scope.event_id.slice(4))
      || !Number.isSafeInteger(scope.closure_revision) || scope.closure_revision < 1
      || !actualNoCopyHashShape_(scope.closure_hash) || !actualNoCopyHashShape_(scope.fingerprint)
      || scope.admission_hash !== gate.admission_hash) actualNoCopyFail_('NO_COPY_SCOPE_CONFLICT');
}
function actualNoCopyKey_(requestId) { return 'bsre.actual-no-copy.v1.' + requestId; }
function actualNoCopyMac_(body) {
  return hex_(Utilities.computeHmacSha256Signature(ACTUAL_NO_COPY_CONTRACT+'\n'+JSON.stringify(actualNoCopyCanonical_(body)),routingConfig_().secret,Utilities.Charset.UTF_8));
}
function actualNoCopyFence_(requestId, gate) {
  var raw = PropertiesService.getScriptProperties().getProperty(actualNoCopyKey_(requestId));
  if (raw === null) return null;
  if (typeof raw !== 'string' || raw.length > 4096) actualNoCopyFail_('NO_COPY_FENCE_CORRUPT');
  var value; try { value=JSON.parse(raw); } catch (_) { actualNoCopyFail_('NO_COPY_FENCE_CORRUPT'); }
  actualNoCopyKeys_(value,['body','signature']);
  var body=value.body;
  var bodyKeys=['scope','scope_hash','created_at','expires_at','floor'];
  if (Object.prototype.hasOwnProperty.call(body,'owner_intent_digest')) {
    bodyKeys.push('owner_intent_digest');
    if (!actualNoCopyHashShape_(body.owner_intent_digest)) actualNoCopyFail_('NO_COPY_FENCE_CORRUPT');
  }
  actualNoCopyKeys_(body,bodyKeys);
  actualNoCopyScope_(body.scope,gate);
  var current=actualNoCopyFloor_(gate), prior=body.floor;
  actualNoCopyKeys_(prior,Object.keys(current));
  var stableCurrent=actualNoCopyCanonical_(current), stablePrior=actualNoCopyCanonical_(prior);
  delete stableCurrent.epoch; delete stableCurrent.revision; delete stablePrior.epoch; delete stablePrior.revision;
  delete stableCurrent.pruned_through; delete stablePrior.pruned_through;
  if (body.scope.request_id !== requestId || body.scope_hash !== actualNoCopyHash_(body.scope)
      || !actualNoCopyHashShape_(prior.epoch) || !Number.isSafeInteger(prior.revision) || prior.revision < 1 || prior.revision > current.revision
      || !Number.isSafeInteger(prior.pruned_through) || prior.pruned_through < 0 || prior.pruned_through > current.pruned_through
      || actualNoCopyHash_(stablePrior) !== actualNoCopyHash_(stableCurrent)
      || !Number.isSafeInteger(body.created_at) || body.created_at <= 0 || body.created_at > actualNoCopyNow_()
      || body.expires_at !== body.created_at + ACTUAL_NO_COPY_WINDOW
      || !same_(actualNoCopyMac_(body),value.signature)) actualNoCopyFail_('NO_COPY_FENCE_CORRUPT');
  return value;
}
function actualNoCopyRow_(row, scope) {
  if (row.length !== LEAD_HEADERS.length || row[0] !== scope.request_id || row[1] !== scope.lead_id
      || row[2] !== scope.event_id || row[4] !== scope.fingerprint || typeof row[5] !== 'string'
      || hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,row[5],Utilities.Charset.UTF_8)) !== scope.fingerprint)
    actualNoCopyFail_('NO_COPY_ROW_CONFLICT');
  var normalized=validateLead_(JSON.parse(row[5]));
  if (normalized.request_id !== scope.request_id || JSON.stringify(normalized) !== row[5]) actualNoCopyFail_('NO_COPY_ROW_CONFLICT');
}
function actualNoCopyMailbox_(scope, now) {
  if (typeof BSREActualNoCopyMailbox !== 'object' || !BSREActualNoCopyMailbox
      || typeof BSREActualNoCopyMailbox.readback !== 'function') actualNoCopyFail_('NO_COPY_MAILBOX_UNVERIFIED');
  var value=BSREActualNoCopyMailbox.readback(scope,now); now=actualNoCopyNow_();
  actualNoCopyKeys_(value,['scope_hash','mailbox','result','complete','includes_trash','observed_at','expires_at','evidence_reference','evidence_hash']);
  if (value.scope_hash !== actualNoCopyHash_(scope) || value.mailbox !== LEAD_RECIPIENT || value.result !== 'ABSENT'
      || value.complete !== true || value.includes_trash !== true || !actualNoCopyHashShape_(value.evidence_hash)
      || typeof value.evidence_reference !== 'string' || value.evidence_reference.length < 1
      || value.evidence_reference.length > 256 || value.evidence_reference.trim() !== value.evidence_reference
      || /[\x00-\x1f\x7f]/.test(value.evidence_reference))
    actualNoCopyFail_('NO_COPY_MAILBOX_UNVERIFIED');
  actualNoCopyFresh_(value,now); return value;
}
function actualNoCopyAssertRequest_(requestId) {
  if (actualNoCopyFence_(requestId,actualNoCopyGate_())) actualNoCopyFail_('NO_COPY_REQUEST_RETIRED');
}
function actualNoCopyAssertMutable_(row) {
  if (!actualNoCopyMaySend_(row)) actualNoCopyFail_('NO_COPY_REQUEST_RETIRED');
}
function actualNoCopyMaySend_(row) {
  var gate=actualNoCopyGate_(), fence;
  // Uncertain custody defers this row, preserving delivery of unrelated healthy rows.
  // The separate exact readback still rejects missing/corrupt fences as unverified.
  try { fence=actualNoCopyFence_(row[0],gate); }
  catch (_) { return false; }
  if (fence) return false;
  if (row[6] === 'RETIRED_NO_COPY') return false;
  return true;
}
/** Separate owner capability; a real independently authenticated intent adapter is not supplied. */
function actualNoCopyRetireAuthorized(scope, intentDigest, expectedActor) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var gate=actualNoCopyGate_(); actualNoCopyScope_(scope,gate);
    if (!actualNoCopyHashShape_(intentDigest) || typeof BSREActualNoCopyOwnerIntent !== 'object'
        || !BSREActualNoCopyOwnerIntent || typeof BSREActualNoCopyOwnerIntent.readback !== 'function')
      actualNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    var now=actualNoCopyNow_(), authorization=BSREActualNoCopyOwnerIntent.readback(intentDigest,now); now=actualNoCopyNow_();
    if (!authorization || authorization.actor !== expectedActor) actualNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    actualNoCopyKeys_(authorization,['contract','intent_digest','actor','scope_hash','approved_at','create_before','recovery_until']);
    if (authorization.contract !== 'bsre-owner-no-mail-authorization-v1' || authorization.intent_digest !== intentDigest
        || authorization.scope_hash !== actualNoCopyHash_(scope) || typeof authorization.actor !== 'string'
        || authorization.actor.length < 1 || authorization.actor.length > 256 || authorization.actor.trim() !== authorization.actor
        || /[\x00-\x1f\x7f]/.test(authorization.actor)
        || !Number.isSafeInteger(authorization.approved_at) || authorization.approved_at <= 0 || authorization.approved_at > now
        || !Number.isSafeInteger(authorization.create_before) || authorization.create_before <= authorization.approved_at
        || authorization.create_before > authorization.approved_at + 900
        || authorization.recovery_until !== authorization.approved_at + ACTUAL_NO_COPY_WINDOW)
      actualNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    return actualNoCopyRetireLocked_(scope,authorization);
  } finally { lock.releaseLock(); }
}
function actualNoCopyRetireLocked_(scope, authorization) {
    if (!authorization) actualNoCopyFail_('RETIREMENT_AUTHORITY_UNVERIFIED');
    var gate=actualNoCopyGate_(); actualNoCopyScope_(scope,gate);
    var s=leadSheet_(routingConfig_()), found=existingLead_(s,scope.request_id,0);
    if (!found) actualNoCopyFail_('NO_COPY_ROW_MISSING');
    actualNoCopyRow_(found.values,scope);
    var fence=actualNoCopyFence_(scope.request_id,gate), row=found.values;
    if (fence && fence.body.scope_hash !== actualNoCopyHash_(scope)) actualNoCopyFail_('NO_COPY_SCOPE_CONFLICT');
    if (authorization && fence && fence.body.owner_intent_digest !== authorization.intent_digest) actualNoCopyFail_('RETIREMENT_OWNER_INTENT_CONFLICT');
    if (row[7] !== 0 || row[10] !== '' || row[25] !== ''
        || ['QUEUED','RETRY_WAIT','NEEDS_REVIEW','RETIRED_NO_COPY'].indexOf(row[6]) < 0)
      actualNoCopyFail_('NO_COPY_OUTBOX_AMBIGUOUS');
    if (row[6] === 'RETIRED_NO_COPY' && !fence) actualNoCopyFail_('NO_COPY_FENCE_MISSING');
    actualNoCopyMailbox_(scope,actualNoCopyNow_());
    if (authorization) {
      var instant=actualNoCopyNow_();
      if ((!fence && instant >= authorization.create_before) || instant >= authorization.recovery_until
          || (fence && (fence.body.created_at < authorization.approved_at || fence.body.created_at >= authorization.create_before)))
        actualNoCopyFail_('RETIREMENT_AUTHORIZATION_EXPIRED');
    }
    var priorGate=gate;
    if (!fence) {
      gate=actualNoCopyAdvance_(gate);
      var now=actualNoCopyNow_();
      if (authorization && (now >= authorization.create_before || now >= authorization.recovery_until)) actualNoCopyFail_('RETIREMENT_AUTHORIZATION_EXPIRED');
      var body={scope:scope,scope_hash:actualNoCopyHash_(scope),created_at:now,
        expires_at:now+ACTUAL_NO_COPY_WINDOW,floor:actualNoCopyFloor_(gate)};
      if (authorization) body.owner_intent_digest=authorization.intent_digest;
      fence={body:body,signature:actualNoCopyMac_(body)};
      var raw=JSON.stringify(fence), props=PropertiesService.getScriptProperties();
      props.setProperty(actualNoCopyKey_(scope.request_id),raw);
      if (props.getProperty(actualNoCopyKey_(scope.request_id)) !== raw) actualNoCopyFail_('NO_COPY_FENCE_UNCONFIRMED');
    }
    mailState_(s,found.number,'RETIRED_NO_COPY',0,'','','','');
    // A pre-retirement snapshot retains its previous epoch and cannot reopen after fence pruning.
    // An interrupted transition remains held until an explicit current-retention reapplication.
    if (gate.epoch !== priorGate.epoch) {
      actualNoCopyStamp_(priorGate,gate);
    }
    return actualNoCopyReadbackLocked_(scope,false);
}
/** Missing row/fence or errors never establish a positively eligible UNRETIRED state. */
function actualNoCopyInspectRetirement(scope) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var gate=actualNoCopyGate_(); actualNoCopyScope_(scope,gate);
    var found=existingLead_(leadSheet_(routingConfig_()),scope.request_id,0);
    if (!found) actualNoCopyFail_('NO_COPY_ROW_MISSING');
    actualNoCopyRow_(found.values,scope);
    var fence=actualNoCopyFence_(scope.request_id,gate), row=found.values;
    if (fence) return {contract:'bsre-no-mail-retirement-inspection-v1',scope_hash:actualNoCopyHash_(scope),state:'RETIRED',
      proof:actualNoCopyReadbackLocked_(scope,false)};
    if (row[7] !== 0 || row[10] !== '' || row[25] !== '' || ['QUEUED','RETRY_WAIT','NEEDS_REVIEW'].indexOf(row[6]) < 0)
      actualNoCopyFail_('NO_COPY_OUTBOX_AMBIGUOUS');
    var store=actualNoCopyStore_(gate).body, mailbox=actualNoCopyMailbox_(scope,actualNoCopyNow_()), now=actualNoCopyNow_();
    actualNoCopyFresh_(gate,now);
    return {contract:'bsre-no-mail-retirement-inspection-v1',scope_hash:actualNoCopyHash_(scope),state:'UNRETIRED',
      current_store:store,external_floor_hash:actualNoCopyHash_(store),source_hash:gate.source_hash,restore_policy_hash:gate.restore_policy_hash,
      mailbox:mailbox,row_status:row[6],attempt_count:row[7],send_started_at:row[25],sent_at:row[10],
      observed_at:now,expires_at:now+300};
  } finally { lock.releaseLock(); }
}
function actualNoCopyReadbackLocked_(scope, cleanup, ticket) {
  var gate=actualNoCopyGate_(); actualNoCopyScope_(scope,gate);
  var fence=actualNoCopyFence_(scope.request_id,gate), now=actualNoCopyNow_();
  if (!fence && cleanup && ticket) fence=actualNoCopyTicketFence_(ticket,scope,gate,now);
  if (!fence || fence.body.scope_hash !== actualNoCopyHash_(scope)) actualNoCopyFail_('NO_COPY_FENCE_MISSING');
  if ((!cleanup && now >= fence.body.expires_at) || (cleanup && (now < fence.body.expires_at
      || gate.recovery.backups_expired_through < fence.body.created_at))) actualNoCopyFail_('NO_COPY_RECOVERY_UNVERIFIED');
  var found=existingLead_(leadSheet_(routingConfig_()),scope.request_id,0);
  if (found) {
    actualNoCopyRow_(found.values,scope);
    if (found.values[6] !== 'RETIRED_NO_COPY' || found.values[7] !== 0 || found.values[10] !== '' || found.values[25] !== '')
      actualNoCopyFail_('NO_COPY_ROW_CONFLICT');
  }
  var currentStore=actualNoCopyStore_(gate).body, fenceHash=actualNoCopyHash_(fence), receipt=null;
  if (cleanup) receipt=actualNoCopyCleanupReceipt_(scope,fenceHash,currentStore,gate,now);
  var mailbox=actualNoCopyMailbox_(scope,actualNoCopyNow_()); now=actualNoCopyNow_();
  actualNoCopyFresh_(gate,now); if (receipt) actualNoCopyFresh_(receipt,now);
  if ((!cleanup && now >= fence.body.expires_at) || (cleanup && now < fence.body.expires_at)) actualNoCopyFail_('NO_COPY_RECOVERY_UNVERIFIED');
  var proof={schema_version:1,scope:scope,scope_hash:fence.body.scope_hash,fence_hash:fenceHash,
    epoch:fence.body.floor.epoch,fence_revision:fence.body.floor.revision,source_hash:gate.source_hash,restore_policy_hash:gate.restore_policy_hash,
    fence_created_at:fence.body.created_at,fence_expires_at:fence.body.expires_at,row_state:found?'RETIRED':'ABSENT',
    mailbox:mailbox,observed_at:now,expires_at:now+300,recovery:gate.recovery,
    current_store:currentStore,external_floor_hash:actualNoCopyHash_(actualNoCopyFloor_(gate)),cleanup_receipt:receipt};
  if (fence.body.owner_intent_digest) proof.owner_intent_digest=fence.body.owner_intent_digest;
  return proof;
}
function actualNoCopyCleanupReceipt_(scope,fenceHash,store,gate,now) {
  if (typeof BSREActualNoCopyRuntime.cleanupReceipt !== 'function') actualNoCopyFail_('NO_COPY_CUSTODY_UNVERIFIED');
  var scopeHash=actualNoCopyHash_(scope), floorHash=actualNoCopyHash_(actualNoCopyFloor_(gate)), storeHash=actualNoCopyHash_(store);
  var receipt=BSREActualNoCopyRuntime.cleanupReceipt(scopeHash,fenceHash,floorHash,storeHash,now); now=actualNoCopyNow_();
  actualNoCopyKeys_(receipt,['contract','scope_hash','fence_hash','external_floor_hash','store_hash',
    'backups_expired_through','observed_at','expires_at','evidence_reference','evidence_hash']);
  if (receipt.contract !== 'bsre-no-copy-cleanup-v1' || receipt.scope_hash !== scopeHash || receipt.fence_hash !== fenceHash
      || receipt.external_floor_hash !== floorHash || receipt.store_hash !== storeHash
      || receipt.backups_expired_through !== gate.recovery.backups_expired_through
      || !actualNoCopyHashShape_(receipt.evidence_hash) || typeof receipt.evidence_reference !== 'string'
      || receipt.evidence_reference.length < 1 || receipt.evidence_reference.length > 256)
    actualNoCopyFail_('NO_COPY_CUSTODY_UNVERIFIED');
  actualNoCopyFresh_(receipt,now); return receipt;
}
function actualNoCopyReadback(scope, cleanup, ticket) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try { return actualNoCopyReadbackLocked_(scope,cleanup === true,ticket); } finally { lock.releaseLock(); }
}
function actualNoCopyTicketMac_(body) {
  return hex_(Utilities.computeHmacSha256Signature('bsre-no-copy-cleanup-ticket-v1\n'+JSON.stringify(actualNoCopyCanonical_(body)),routingConfig_().secret,Utilities.Charset.UTF_8));
}
function actualNoCopyTicketFence_(ticket,scope,gate,now) {
  actualNoCopyKeys_(ticket,['body','signature']);
  var body=ticket.body; actualNoCopyKeys_(body,['contract','fence','floor','issued_at']);
  var floor=actualNoCopyFloor_(gate), prior=body.floor;
  actualNoCopyKeys_(prior,Object.keys(floor));
  if (body.contract !== 'bsre-no-copy-cleanup-ticket-v1' || !Number.isSafeInteger(body.issued_at) || body.issued_at > now
      || !same_(ticket.signature,actualNoCopyTicketMac_(body)) || prior.pruned_through < body.fence.body.floor.revision
      || prior.revision > floor.revision || prior.pruned_through > floor.pruned_through)
    actualNoCopyFail_('NO_COPY_CLEANUP_TICKET_INVALID');
  var currentStable=actualNoCopyCanonical_(floor), priorStable=actualNoCopyCanonical_(prior);
  ['epoch','revision','pruned_through'].forEach(function(key) { delete currentStable[key]; delete priorStable[key]; });
  if (actualNoCopyHash_(currentStable) !== actualNoCopyHash_(priorStable)
      || body.fence.body.scope_hash !== actualNoCopyHash_(scope) || !same_(body.fence.signature,actualNoCopyMac_(body.fence.body)))
    actualNoCopyFail_('NO_COPY_CLEANUP_TICKET_INVALID');
  actualNoCopyScope_(body.fence.body.scope,gate);
  return body.fence;
}
/** Historical signed intent is kept only in the existing private workflow journal. */
function actualNoCopyPrepareCleanup(scope) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var proof=actualNoCopyReadbackLocked_(scope,true), gate=actualNoCopyGate_();
    var fence=actualNoCopyFence_(scope.request_id,gate);
    if (typeof BSREActualNoCopyRuntime.advancePrune !== 'function') actualNoCopyFail_('NO_COPY_EPOCH_AUTHORITY_UNVERIFIED');
    BSREActualNoCopyRuntime.advancePrune(actualNoCopyFloor_(gate),fence.body.floor.revision);
    var next=actualNoCopyControl_(), before=actualNoCopyFloor_(gate), after=actualNoCopyFloor_(next);
    if (next.revision !== gate.revision + 1 || next.epoch === gate.epoch
        || next.pruned_through !== Math.max(gate.pruned_through,fence.body.floor.revision)) actualNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
    ['epoch','revision','pruned_through'].forEach(function(key) { delete before[key]; delete after[key]; });
    if (actualNoCopyHash_(before) !== actualNoCopyHash_(after)) actualNoCopyFail_('NO_COPY_EPOCH_CONFLICT');
    actualNoCopyStamp_(gate,next);
    // Recheck the fresh custody receipt against the newly stamped actual store and external floor.
    actualNoCopyReadbackLocked_(scope,true);
    var body={contract:'bsre-no-copy-cleanup-ticket-v1',fence:fence,floor:actualNoCopyFloor_(next),issued_at:actualNoCopyNow_()};
    return {body:body,signature:actualNoCopyTicketMac_(body)};
  } finally { lock.releaseLock(); }
}
/** Backup/restore authority is mandatory; missing state never means a fence expired successfully. */
function actualNoCopyForget(scope,ticket) {
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var gate=actualNoCopyGate_(); actualNoCopyTicketFence_(ticket,scope,gate,actualNoCopyNow_());
    actualNoCopyReadbackLocked_(scope,true,ticket);
    var props=PropertiesService.getScriptProperties(); props.deleteProperty(actualNoCopyKey_(scope.request_id));
    if (props.getProperty(actualNoCopyKey_(scope.request_id)) !== null) actualNoCopyFail_('NO_COPY_CUSTODY_UNCONFIRMED');
    return true;
  } finally { lock.releaseLock(); }
}
