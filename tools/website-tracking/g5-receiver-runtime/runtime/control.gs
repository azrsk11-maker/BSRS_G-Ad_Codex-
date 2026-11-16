/* Explicit operational codec candidate. No endpoint/key/enrolment is supplied or generated. */
var ACTUAL_CONTROL_CONTRACT = 'bsre-receiver-control-v1';
var ACTUAL_CONTROL_ACTIVATION = 'bsre.actual-receiver.activation-v1';
function actualReceiverFail_(code) { throw new Error(code); }
function actualReceiverMode_() {
  var p=PropertiesService.getScriptProperties();
  return p.getProperty('BSRE_ACTUAL_RETIREMENT_ENABLED')==='true' || p.getProperty(ACTUAL_CONTROL_ACTIVATION)!==null;
}
function actualReceiverAuthorityConfig_() {
  var p=PropertiesService.getScriptProperties().getProperties(), lead=routingConfig_();
  if(p.BSRE_ACTUAL_RETIREMENT_ENABLED!=='true')actualReceiverFail_('ACTUAL_RECEIVER_DISABLED');
  var url=p.BSRE_RECEIVER_AUTHORITY_URL, secret=p.BSRE_RECEIVER_AUTHORITY_SECRET;
  if(typeof url!=='string'||!/^https:\/\/[A-Za-z0-9.-]+(?::443)?\/[A-Za-z0-9/_-]+$/.test(url)
      ||/^https:\/\/(?:localhost|[0-9.]+)(?:[:/]|$)/i.test(url)
      ||typeof secret!=='string'||secret.length<32||secret===lead.secret)actualReceiverFail_('ACTUAL_AUTHORITY_NOT_CONFIGURED');
  for(var key of ['BSRE_RECEIVER_NAMESPACE','BSRE_RECEIVER_SOURCE_SHA256'])
    if(typeof p[key]!=='string'||!/^[a-f0-9]{64}$/.test(p[key]))actualReceiverFail_('ACTUAL_ENROLMENT_NOT_CONFIGURED');
  if(typeof p.BSRE_RECEIVER_EVIDENCE_KEY_ID!=='string'||! /^[A-Za-z0-9_-]{1,64}$/.test(p.BSRE_RECEIVER_EVIDENCE_KEY_ID))actualReceiverFail_('ACTUAL_ENROLMENT_NOT_CONFIGURED');
  return {url:url,secret:secret,namespace:p.BSRE_RECEIVER_NAMESPACE,source:p.BSRE_RECEIVER_SOURCE_SHA256,key_id:p.BSRE_RECEIVER_EVIDENCE_KEY_ID};
}
function actualControlCanonicalJSON_(value) { return JSON.stringify(actualNoCopyCanonical_(value)); }
function actualControlHash_(value) { return actualNoCopyHash_(value); }
function actualControlMac_(text,key) { return hex_(Utilities.computeHmacSha256Signature(text,key,Utilities.Charset.UTF_8)); }
/** Receiver-only authenticated service transport. Its secret MUST NOT be the WordPress lead HMAC. */
function actualAuthorityRequest_(operation,args) {
  var cfg=actualReceiverAuthorityConfig_(), now=actualNoCopyNow_();
  var nonce=Utilities.getUuid().replace(/-/g,'')+Utilities.getUuid().replace(/-/g,'');
  var request={contract:'bsre-receiver-authority-request-v1',operation:operation,namespace:cfg.namespace,source:cfg.source,
    challenge:nonce,issued_at:now,arguments:args},body=actualControlCanonicalJSON_(request),hash=actualControlHash_(request);
  var mac=actualControlMac_('bsre-receiver-authority-request-v1\n'+body,cfg.secret);
  var reply=UrlFetchApp.fetch(cfg.url,{method:'post',contentType:'application/json',payload:actualControlCanonicalJSON_({body:body,mac:mac}),
    followRedirects:false,muteHttpExceptions:true,validateHttpsCertificates:true});
  if(reply.getResponseCode()!==200)actualReceiverFail_('ACTUAL_AUTHORITY_UNAVAILABLE');
  var raw=reply.getContentText();if(typeof raw!=='string'||raw.length>131072)actualReceiverFail_('ACTUAL_AUTHORITY_UNVERIFIED');
  // Verification uses the trusted receiver clock after the remote I/O. Request and
  // approval timestamps remain unchanged; elapsed transport time renews no authority.
  now=actualNoCopyNow_();
  var outer;try{outer=JSON.parse(raw);}catch(_){actualReceiverFail_('ACTUAL_AUTHORITY_UNVERIFIED');}
  actualNoCopyKeys_(outer,['body','mac']);
  if(actualControlCanonicalJSON_(outer)!==raw||typeof outer.body!=='string'||!same_(outer.mac,actualControlMac_('bsre-receiver-authority-response-v1\n'+outer.body,cfg.secret)))actualReceiverFail_('ACTUAL_AUTHORITY_UNVERIFIED');
  var result;try{result=JSON.parse(outer.body);}catch(_){actualReceiverFail_('ACTUAL_AUTHORITY_UNVERIFIED');}
  actualNoCopyKeys_(result,['contract','operation','namespace','source','challenge','request_hash','issued_at','expires_at','result']);
  if(actualControlCanonicalJSON_(result)!==outer.body||result.contract!=='bsre-receiver-authority-response-v1'||result.operation!==operation
    ||result.namespace!==cfg.namespace||result.source!==cfg.source||result.challenge!==nonce||result.request_hash!==hash
    ||!Number.isSafeInteger(result.issued_at)||result.issued_at>now||result.issued_at<now-30
    ||!Number.isSafeInteger(result.expires_at)||result.expires_at<=now||result.expires_at>result.issued_at+60)actualReceiverFail_('ACTUAL_AUTHORITY_UNVERIFIED');
  return result.result;
}
/** Explicit receiver-owned half of the remote CAS. The service never writes local Properties. */
function actualRuntimeAdvance_(operation,before,revision) {
  var props=PropertiesService.getScriptProperties(),prior=actualControlCanonicalJSON_(actualNoCopyCanonical_(before));
  if(props.getProperty(ACTUAL_NO_COPY_FLOOR)!==prior)actualReceiverFail_('ACTUAL_LOCAL_FLOOR_CONFLICT');
  var args={before:before};if(operation==='runtime.advance_prune')args.revision=revision;
  var next=actualAuthorityRequest_(operation,args),now=actualNoCopyNow_();
  actualNoCopyKeys_(next,['contract','namespace','epoch','revision','pruned_through','admission_hash','admission_descriptor_hash','source_hash','restore_policy_hash','observed_at','expires_at','recovery']);
  var descriptor=retentionAdmissionDescriptor_();
  if(descriptor.mode!=='ENFORCED'||next.admission_descriptor_hash!==actualNoCopyHash_(descriptor))actualReceiverFail_('ACTUAL_ADMISSION_CHANGED');
  actualNoCopyFresh_(next,now);actualNoCopyKeys_(next.recovery,['contract','window_seconds','restore_fenced','backups_expired_through']);
  if(next.recovery.contract!=='bsre-retention-admission-v1'||next.recovery.window_seconds!==ACTUAL_NO_COPY_WINDOW||next.recovery.restore_fenced!==true
    ||!Number.isSafeInteger(next.recovery.backups_expired_through)||next.recovery.backups_expired_through<0||next.recovery.backups_expired_through>now)actualReceiverFail_('ACTUAL_RECOVERY_UNVERIFIED');
  var after=actualNoCopyFloor_(next),expectedPruned=before.pruned_through;
  if(operation==='runtime.advance_prune'){
    if(!Number.isSafeInteger(revision)||revision<1||revision>before.revision)actualReceiverFail_('ACTUAL_PRUNE_CONFLICT');
    expectedPruned=Math.max(before.pruned_through,revision);
  }
  if(!Number.isSafeInteger(after.revision)||after.revision!==before.revision+1||!actualNoCopyHashShape_(after.epoch)||after.epoch===before.epoch
    ||after.pruned_through!==expectedPruned)actualReceiverFail_('ACTUAL_FLOOR_CAS_CONFLICT');
  var left=actualNoCopyCanonical_(before),right=actualNoCopyCanonical_(after);
  ['epoch','revision','pruned_through'].forEach(function(k){delete left[k];delete right[k];});
  if(actualNoCopyHash_(left)!==actualNoCopyHash_(right))actualReceiverFail_('ACTUAL_FLOOR_SCOPE_CONFLICT');
  // Remote CAS precedes this write. Any missing/failed acknowledgement keeps stores
  // divergent and all future gate reads held until explicit authoritative recovery.
  var raw=actualControlCanonicalJSON_(after);props.setProperty(ACTUAL_NO_COPY_FLOOR,raw);
  if(props.getProperty(ACTUAL_NO_COPY_FLOOR)!==raw)actualReceiverFail_('ACTUAL_LOCAL_FLOOR_UNCONFIRMED');return next;
}
// These are consumed by the separately derived actual algebra. They grant no authority from caller arrays.
var BSREActualNoCopyRuntime={
  readback:function(now){return actualAuthorityRequest_('runtime.current',{now:now});},
  advanceRetirement:function(before){return actualRuntimeAdvance_('runtime.advance_retirement',before);},
  advancePrune:function(before,revision){return actualRuntimeAdvance_('runtime.advance_prune',before,revision);},
  cleanupReceipt:function(scopeHash,fenceHash,floorHash,storeHash,now){return actualAuthorityRequest_('runtime.cleanup_receipt',{scope_hash:scopeHash,fence_hash:fenceHash,floor_hash:floorHash,store_hash:storeHash,now:now});}
};
var BSREActualNoCopyMailbox={readback:function(scope,now){return actualAuthorityRequest_('mailbox.current_including_trash',{scope:scope,now:now});}};
var BSREActualNoCopyOwnerIntent={readback:function(intent,now){return actualAuthorityRequest_('owner_intent.current',{intent_digest:intent,now:now});}};
function actualReceiverGate_(){return actualReceiverMode_()?actualNoCopyGate_():closedNoCopyGate_();}
function actualReceiverAssertRequest_(id){return actualReceiverMode_()?actualNoCopyAssertRequest_(id):closedNoCopyAssertRequest_(id);}
function actualReceiverAssertMutable_(row){return actualReceiverMode_()?actualNoCopyAssertMutable_(row):closedNoCopyAssertMutable_(row);}
function actualReceiverMaySend_(row){return actualReceiverMode_()?actualNoCopyMaySend_(row):closedNoCopyMaySend_(row);}
function actualControlRequest_(e) {
  var raw=e&&e.postData&&e.postData.contents;if(typeof raw!=='string'||raw.length>65536)actualReceiverFail_('ACTUAL_CONTROL_AUTH_FAILED');
  var env;try{env=JSON.parse(raw);}catch(_){actualReceiverFail_('ACTUAL_CONTROL_AUTH_FAILED');}
  actualNoCopyKeys_(env,['control_contract','control_version','timestamp','challenge','operation','actor','body','signature']);
  if(actualControlCanonicalJSON_(env)!==raw)actualReceiverFail_('ACTUAL_CONTROL_NONCANONICAL_OR_DUPLICATE_JSON');
  if(env.control_contract!==ACTUAL_CONTROL_CONTRACT||env.control_version!==1||!Number.isSafeInteger(env.timestamp)||Math.abs(Date.now()-env.timestamp)>30000
      ||typeof env.challenge!=='string'||!/^[a-f0-9]{64}$/.test(env.challenge)||typeof env.actor!=='string'||!/^wp-user:[1-9][0-9]{0,17}$/.test(env.actor)||typeof env.body!=='string'||env.body.length>49152
      ||['inspect','retire','readback','prepare_cleanup','forget'].indexOf(env.operation)<0)actualReceiverFail_('ACTUAL_CONTROL_AUTH_FAILED');
  var signed=ACTUAL_CONTROL_CONTRACT+'\n'+env.timestamp+'\n'+env.challenge+'\n'+env.operation+'\n'+env.actor+'\n'+env.body;
  if(!same_(env.signature,actualControlMac_(signed,routingConfig_().secret)))actualReceiverFail_('ACTUAL_CONTROL_AUTH_FAILED');
  var args;try{args=JSON.parse(env.body);}catch(_){actualReceiverFail_('ACTUAL_CONTROL_SCHEMA_INVALID');}
  if(actualControlCanonicalJSON_(args)!==env.body)actualReceiverFail_('ACTUAL_CONTROL_SCHEMA_INVALID');
  return {envelope:env,args:args,request_hash:actualControlHash_({operation:env.operation,body:env.body})};
}
function actualControlHandle_(e) {
  var req=actualControlRequest_(e),env=req.envelope,args=req.args,cfg=actualReceiverAuthorityConfig_(),proof;
  // No operation creates the physical namespace or current/backup authority. Activation
  // is an independently enrolled durable marker, checked before any caller-controlled action.
  // Each public actual-algebra operation checks the durable activation marker under
  // its own ScriptLock before touching the row/fence; this dispatcher never nests it.
  if(env.operation==='inspect'){actualNoCopyKeys_(args,['scope']);proof=actualNoCopyInspectRetirement(args.scope);}
  else if(env.operation==='retire'){actualNoCopyKeys_(args,['scope','intent_digest']);proof=actualNoCopyRetireAuthorized(args.scope,args.intent_digest,env.actor);}
  else if(env.operation==='readback'){actualNoCopyKeys_(args,['scope','cleanup','ticket']);if(typeof args.cleanup!=='boolean')actualReceiverFail_('ACTUAL_CONTROL_SCHEMA_INVALID');proof=actualNoCopyReadback(args.scope,args.cleanup,args.ticket);}
  else if(env.operation==='prepare_cleanup'){actualNoCopyKeys_(args,['scope']);proof=actualNoCopyPrepareCleanup(args.scope);}
  else {actualNoCopyKeys_(args,['scope','ticket']);proof=actualNoCopyForget(args.scope,args.ticket);}
  // The independent service must attest exact receiver-only authenticated observation,
  // durable action/identity/current history/mail/snapshot floor, not merely echo it.
  var statement=actualAuthorityRequest_('attest_control_result',{operation:env.operation,actor:env.actor,scope:args.scope,challenge:env.challenge,
    request_hash:req.request_hash,admission:retentionAdmissionDescriptor_(),observed_result:proof});
  actualNoCopyKeys_(statement,['key_id','statement','signature']);
  if(statement.key_id!==cfg.key_id)actualReceiverFail_('ACTUAL_SIGNER_NOT_ENROLLED');
  return json_(statement); // PHP verifies independent Ed25519; transport HMAC is never that proof.
}
function doPost(e) {
  var raw=e&&e.postData&&e.postData.contents,env=null;
  if(typeof raw==='string'&&raw.length<=65536){try{env=JSON.parse(raw);}catch(_){}}
  // An original v1 envelope always uses the original lead path, including its exact errors.
  if(!env||env.version===1||env.control_contract!==ACTUAL_CONTROL_CONTRACT||env.control_version!==1)return actualLegacyLeadPost_(e);
  try{return actualControlHandle_(e);}catch(_){return json_({control_contract:ACTUAL_CONTROL_CONTRACT,accepted:false,code:'ACTUAL_CONTROL_HELD',reconciliation_required:true});}
}
