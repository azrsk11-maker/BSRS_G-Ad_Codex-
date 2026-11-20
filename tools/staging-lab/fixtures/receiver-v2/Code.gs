/* Reference implementation: deploy/configure/verify before live integration. */
var LEAD_HEADERS = ['request_id','lead_id','event_id','accepted_at_utc','payload_sha256','payload_json','email_status','email_attempts','email_next_attempt_at','email_last_error','email_sent_at_utc','name','phone','email','role','campaign','landing_page','contact_consent','marketing_consent','lead_status','assigned_to','qualification_status','qualified_at_utc','person_duplicate_of','staff_notes','email_attempt_started_at_utc'];
var LEAD_TAB = 'Google Ads Leads';
var LEAD_RECIPIENT = 'marketing@blackswanrealestate.ae';

function routingConfig_() {
  var p = PropertiesService.getScriptProperties().getProperties();
  if (!p.LEAD_SHEET_ID || !/^[\w-]{20,160}$/.test(p.LEAD_SHEET_ID) || !p.HMAC_SECRET || p.HMAC_SECRET.length < 32) throw new Error('NOT_CONFIGURED');
  return { sheetId:p.LEAD_SHEET_ID, secret:p.HMAC_SECRET, enabled:p.ROUTING_ENABLED === 'true', mail:p.MAIL_ENABLED === 'true' };
}
function leadSheet_(cfg) {
  var s = SpreadsheetApp.openById(cfg.sheetId).getSheetByName(LEAD_TAB);
  if (!s || JSON.stringify(s.getRange(1,1,1,LEAD_HEADERS.length).getValues()[0]) !== JSON.stringify(LEAD_HEADERS)) throw new Error('SHEET_NOT_INITIALIZED');
  return s;
}
function initializeLeadRouting() {
  var lock = LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var book = SpreadsheetApp.openById(routingConfig_().sheetId);
    var s = book.getSheetByName(LEAD_TAB) || book.insertSheet(LEAD_TAB);
    if (s.getLastRow() > 0) { leadSheet_(routingConfig_()); return; }
    s.getRange(1,1,1,LEAD_HEADERS.length).setValues([LEAD_HEADERS]);
    s.setFrozenRows(1); SpreadsheetApp.flush();
  } finally { lock.releaseLock(); }
}
function json_(value) { return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON); }
function hex_(bytes) { return bytes.map(function(b) { return ('0' + (b & 255).toString(16)).slice(-2); }).join(''); }
function same_(a,b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  var n = 0; for (var i=0; i<a.length; i++) n |= a.charCodeAt(i) ^ b.charCodeAt(i); return n === 0;
}
function authenticate_(e,cfg) {
  var raw = e && e.postData && e.postData.contents;
  if (typeof raw !== 'string' || raw.length > 26000) throw new Error('AUTH_FAILED');
  var env; try { env = JSON.parse(raw); } catch (_) { throw new Error('AUTH_FAILED'); }
  if (!env || typeof env !== 'object' || Array.isArray(env) || env.version !== 1 || typeof env.body !== 'string' || env.body.length > 18000 || !/^\d{13}$/.test(String(env.timestamp)) || Math.abs(Date.now()-Number(env.timestamp)) > 300000 || !/^[a-f0-9]{64}$/.test(env.signature || '')) throw new Error('AUTH_FAILED');
  var mac = hex_(Utilities.computeHmacSha256Signature('v1\n'+env.timestamp+'\n'+env.body,cfg.secret,Utilities.Charset.UTF_8));
  if (!same_(mac,env.signature)) throw new Error('AUTH_FAILED');
  try { return JSON.parse(env.body); } catch (_) { throw new Error('VALIDATION_FAILED'); }
}
function text_(v,max,required) {
  if (v === undefined || v === null) v = '';
  if (typeof v !== 'string' || v.length > max || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(v)) throw new Error('VALIDATION_FAILED');
  v = v.trim(); if (required && !v) throw new Error('VALIDATION_FAILED'); return v;
}
function metadataUrl_(value) {
  if (typeof value !== 'string' || value.length > 2000 || /[\\\s]/.test(value)) return '';
  var m = /^(https?):\/\/([a-z0-9.-]+)(?::([0-9]{1,5}))?(\/[^?#]*)?(?:[?#].*)?$/i.exec(value);
  if (!m || (m[3] && (Number(m[3]) < 1 || Number(m[3]) > 65535))) return '';
  return m[1].toLowerCase()+'://'+m[2].toLowerCase()+(m[3] ? ':'+m[3] : '')+(m[4] || '/');
}
function attribution_(value) {
  var out = {first:null,last:null};
  if (value && (typeof value !== 'object' || Array.isArray(value))) throw new Error('VALIDATION_FAILED');
  ['first','last'].forEach(function(touch) {
    var v = value && value[touch];
    if (!v) return;
    if (typeof v !== 'object' || Array.isArray(v) || (v.parameters && (typeof v.parameters !== 'object' || Array.isArray(v.parameters)))) throw new Error('VALIDATION_FAILED');
    var normalized = {landing_page:metadataUrl_(v.landing_page),referrer:metadataUrl_(v.referrer),timestamp:null,parameters:{}};
    if (Number.isSafeInteger(v.timestamp) && v.timestamp > 0 && v.timestamp <= 8640000000000000) normalized.timestamp = v.timestamp;
    ['utm_source','utm_medium','utm_campaign','utm_content','utm_term','gclid','gbraid','wbraid'].forEach(function(k) {
      if (v.parameters && Object.prototype.hasOwnProperty.call(v.parameters,k)) normalized.parameters[k] = text_(v.parameters[k],256,false);
    });
    out[touch] = normalized;
  }); return out;
}
function oneOf_(value,allowed,required) { if ((!value && required) || (value && allowed.indexOf(value) < 0)) throw new Error('VALIDATION_FAILED'); }
function validateLead_(p) {
  if (!p || typeof p !== 'object' || Array.isArray(p) || p.contact_consent !== true || typeof p.marketing_consent !== 'boolean' || text_(p.website,200,false)) throw new Error('VALIDATION_FAILED');
  var n = { request_id:text_(p.request_id,36,true), role:text_(p.role,20,true), name:text_(p.name,200,true), phone:text_(p.phone,35,true), email:text_(p.email,254,false) };
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(n.request_id) || ['off_plan','resale','tenant','seller','landlord'].indexOf(n.role) < 0 || !/^[+()\d .-]{7,35}$/.test(n.phone) || n.phone.replace(/\D/g,'').length < 7 || n.phone.replace(/\D/g,'').length > 15 || (n.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(n.email)) || /[\r\n]/.test(n.name)) throw new Error('VALIDATION_FAILED');
  var owner = n.role === 'seller' || n.role === 'landlord';
  ['country','area','budget','timeline','funding','property_type','authority'].forEach(function(k) { n[k] = text_(p[k],200,k === 'country' || k === 'area' || k === 'property_type' || (!owner && (k === 'budget' || k === 'timeline')) || (owner && k === 'authority')); });
  n.property_details = text_(p.property_details,1500,owner);
  oneOf_(n.property_type,['Apartment','Townhouse','Villa','Other / to discuss'],true);
  oneOf_(n.authority,['owner','authorized_representative'],owner);
  oneOf_(n.funding,['Cash / own funds','Mortgage arranged','Mortgage to be arranged','To discuss'],false);
  var timelines = {off_plan:['Within 1 month','In 1–3 months','In 3–6 months','More than 6 months / exploring'],resale:['Within 1 month','In 1–3 months','In 3–6 months','More than 6 months / exploring'],tenant:['Immediate / move now','Within 30 days','Later / exploring'],seller:['As soon as practical','Within 3 months','Later / discussing options'],landlord:['Vacant / available to discuss now','Expected within 30 days','Later / date to discuss']};
  oneOf_(n.timeline,timelines[n.role],!owner);
  n.contact_consent = true; n.marketing_consent = p.marketing_consent;
  n.campaign = text_(p.campaign,160,false) || 'Unattributed';
  n.landing_page = metadataUrl_(text_(p.landing_page,2000,true));
  if (!/^https:\/\/(?:[a-z0-9-]+\.)*blackswanrealestate\.ae(?:\/|$)/i.test(n.landing_page) || /[\r\n]/.test(n.campaign)) throw new Error('VALIDATION_FAILED');
  n.attribution = attribution_(p.attribution);
  if (!Number.isSafeInteger(p.started_at) || p.started_at <= 0 || p.started_at > 8640000000000000) throw new Error('VALIDATION_FAILED');
  n.started_at = p.started_at; return n;
}
function safeCell_(v) { var s = String(v); return /^[\s]*[=+\-@]/.test(s) || /^[\t\r\n]/.test(s) ? "'"+s : s; }
function existingLead_(s,id,column) {
  if (s.getLastRow() < 2) return null;
  var rows = s.getRange(2,1,s.getLastRow()-1,LEAD_HEADERS.length).getValues(), found = null;
  rows.forEach(function(row,i) { if (row[column] === id) { if (found) throw new Error('DUPLICATE_ROWS_RECONCILE'); found = { number:i+2, values:row }; } });
  return found;
}
function doPost(e) {
  var lock, held = false;
  try {
    var cfg = routingConfig_(); if (!cfg.enabled) throw new Error('ROUTING_DISABLED');
    var p = validateLead_(authenticate_(e,cfg));
    var serialized = JSON.stringify(p), fingerprint = hex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,serialized,Utilities.Charset.UTF_8));
    lock = LockService.getScriptLock(); if (!lock.tryLock(10000)) return json_({accepted:false,code:'BUSY',retryable:true}); held = true;
    var s = leadSheet_(cfg), old = existingLead_(s,p.request_id,0);
    if (old) {
      if (!same_(old.values[4],fingerprint)) return json_({accepted:false,code:'REQUEST_ID_CONFLICT',retryable:false});
      return json_({accepted:true,lead_id:old.values[1],event_id:old.values[2]});
    }
    var now = new Date().toISOString(), lead = 'BSRE-'+Utilities.getUuid(), event = 'evt_'+Utilities.getUuid();
    var row = [p.request_id,lead,event,now,fingerprint,serialized,'QUEUED',0,now,'','',p.name,p.phone,p.email,p.role,p.campaign,p.landing_page,true,p.marketing_consent,'NEW_UNASSIGNED','','UNREVIEWED','','','',''];
    s.appendRow(row.map(function(v) { return typeof v === 'string' ? safeCell_(v) : v; }));
    SpreadsheetApp.flush(); // Durable row + outbox precede the acknowledgement.
    return json_({accepted:true,lead_id:lead,event_id:event});
  } catch (err) {
    var known = ['AUTH_FAILED','VALIDATION_FAILED','NOT_CONFIGURED','ROUTING_DISABLED','SHEET_NOT_INITIALIZED','DUPLICATE_ROWS_RECONCILE'];
    var code = known.indexOf(err.message) >= 0 ? err.message : 'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID';
    return json_({accepted:false,code:code,retryable:code === 'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID'});
  } finally { if (held) lock.releaseLock(); }
}
function mailState_(s,row,status,attempts,next,error,sent,started) {
  s.getRange(row,7,1,5).setValues([[status,attempts,next || '',error || '',sent || '']]);
  s.getRange(row,26,1,1).setValues([[started || '']]); SpreadsheetApp.flush();
}
function processLeadOutbox() {
  var cfg = routingConfig_(); if (!cfg.mail) return {mail_enabled:false};
  var lock = LockService.getScriptLock(); if (!lock.tryLock(1000)) return {busy:true};
  var sent = 0, attempted = 0;
  try {
    var s = leadSheet_(cfg); if (s.getLastRow() < 2) return {sent:0};
    var rows = s.getRange(2,1,s.getLastRow()-1,LEAD_HEADERS.length).getValues();
    for (var i=0; i<rows.length && attempted<5; i++) {
      var r=rows[i], row=i+2, status=r[6], attempts=Number(r[7]) || 0;
      if (status === 'SENDING') {
        if (!r[25] || Date.now()-Date.parse(r[25]) > 900000) mailState_(s,row,'AMBIGUOUS',attempts,'','STALE_SEND_RECONCILE','','');
        continue;
      }
      if (['QUEUED','RETRY_WAIT'].indexOf(status) < 0 || (r[8] && Date.parse(r[8]) > Date.now())) continue;
      // These failures occur before sendEmail is called and are safe to retry.
      var quota;
      try { quota = MailApp.getRemainingDailyQuota(); }
      catch (_) { mailState_(s,row,'RETRY_WAIT',attempts,new Date(Date.now()+3600000).toISOString(),'QUOTA_CHECK_FAILED','',''); break; }
      if (quota < 1) { mailState_(s,row,'RETRY_WAIT',attempts,new Date(Date.now()+3600000).toISOString(),'MAIL_QUOTA_EXHAUSTED','',''); break; }
      var p;
      try { p=JSON.parse(r[5]); } catch (_) { mailState_(s,row,'NEEDS_REVIEW',attempts,'','PAYLOAD_INVALID','',''); continue; }
      attempts++; attempted++; var started = new Date().toISOString();
      mailState_(s,row,'SENDING',attempts,'','','',started);
      try {
        MailApp.sendEmail({to:LEAD_RECIPIENT,noReply:true,name:'Black Swan Real Estate Enquiries',subject:'G-Ad | '+p.campaign+' | '+p.name+' | '+r[1],body:'Lead ID: '+r[1]+'\nEvent ID: '+r[2]+'\nAccepted UTC: '+r[3]+'\nStatus: Unassigned; not yet sales qualified.\n\n'+JSON.stringify(p,null,2)});
        mailState_(s,row,'SENT',attempts,'','',new Date().toISOString(),started); sent++;
      } catch (_) {
        // A provider exception or post-send persistence error may follow delivery.
        mailState_(s,row,'AMBIGUOUS',attempts,'','SEND_OR_COMMIT_AMBIGUOUS','',started);
      }
    } return {sent:sent};
  } finally { lock.releaseLock(); }
}
function reconcileLeadEmail(leadId,outcome) {
  if (['confirmed_sent','confirmed_not_sent'].indexOf(outcome) < 0) throw new Error('RECONCILIATION_REQUIRED');
  var lock=LockService.getScriptLock(); lock.waitLock(10000);
  try {
    var s=leadSheet_(routingConfig_()), found=existingLead_(s,leadId,1);
    if (!found || ['SENDING','AMBIGUOUS'].indexOf(found.values[6]) < 0) throw new Error('RECONCILIATION_REQUIRED');
    mailState_(s,found.number,outcome === 'confirmed_sent' ? 'SENT' : 'QUEUED',found.values[7],outcome === 'confirmed_not_sent' ? new Date().toISOString() : '','MANUALLY_RECONCILED',outcome === 'confirmed_sent' ? found.values[10] : '','');
  } finally { lock.releaseLock(); }
}
