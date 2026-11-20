import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {buildPurposeStoreCandidate, buildPurposeIntakeCandidate, buildPurposeClientCandidate} from './build-purpose-attribution-candidate.mjs';
import {buildReceiptStatusCandidate} from './build-receipt-status-candidate.mjs';

function replace(source, before, after) {
  if (source.split(before).length !== 2) throw new Error('RETENTION_ADMISSION_ANCHOR_CHANGED');
  return source.replace(before, after);
}

/** Both legacy and purpose receive callbacks use this exact transactional store. */
export function buildRetentionAdmissionStore(bytes) {
  let source = replace(buildPurposeStoreCandidate(bytes),
    '            $capture += prepare_capture($this->db, $capture);',
    '            \\BSRE\\RetentionAdmission\\assert_capture($this->db, $capture);\n            $capture += prepare_capture($this->db, $capture);');
  return replace(source, '    public function database()', "    public function admissionContract(): string { return \\BSRE\\RetentionAdmission\\CONTRACT; }\n    public function database()");
}

export function buildRetentionAdmissionIntake(plugin, consent) {
  let source = buildPurposeIntakeCandidate(plugin, consent);
  source = replace(source, 'consent_capture_clicks,envelope,send_envelope', 'consent_capture_clicks,send_envelope');
  source = replace(source, 'function stage_submission(', 'use function BSRE\\RetentionAdmission\\envelope;\nfunction stage_submission(');
  source = replace(source, "    if ($capture['conflict']) return reply(409, 'REQUEST_ID_CONFLICT');",
    "    if ($capture['conflict']) return reply(409, 'REQUEST_ID_CONFLICT');\n    if (\\BSRE\\RetentionAdmission\\configuration()['mode'] === 'ENFORCED' && !$capture['recorded']) return reply(503, 'ADMISSION_UNCONFIRMED', true);");
  return source;
}

/** Extends the outer envelope only. Original wire body, row schema and outbox remain intact. */
export function buildRetentionAdmissionReceiver(bytes) {
  let source = buildReceiptStatusCandidate(bytes).replaceAll('\r\n', '\n');
  source = replace(source, 'function doPost(e) {', `function retentionAdmissionDescriptor_() {
  var p = PropertiesService.getScriptProperties().getProperties();
  var enabled = p.RETENTION_ADMISSION_REQUIRED === 'true';
  var generation = p.RETENTION_ADMISSION_GENERATION || '';
  var activated = Number(p.RETENTION_ADMISSION_ACTIVATED_AT || 0);
  var audience = p.RETENTION_ADMISSION_AUDIENCE || '';
  if (enabled && (!/^[a-f0-9]{64}$/.test(generation) || !Number.isSafeInteger(activated)
      || activated <= 0 || activated > Math.floor(Date.now()/1000) || !/^[a-f0-9]{64}$/.test(audience))) throw new Error('NOT_CONFIGURED');
  return {contract:'bsre-retention-admission-v1',mode:enabled?'ENFORCED':'DISABLED',generation:enabled?generation:'',
    activated_at:enabled?activated:0,max_age_seconds:900,audience:enabled?audience:''};
}
function admissionEnvelope_(e) {
  var env;
  try { env=JSON.parse(e.postData.contents); } catch (_) { return null; }
  return env && env.admission;
}
function validRetentionAdmission_(proof,id,cfg,gate) {
  if (!proof || typeof proof!=='object' || Array.isArray(proof)
    || Object.keys(proof).sort().join(',')!=='audience,expires_at,generation,issued_at,request_id,session_hash,signature,version'
    || proof.version!==1 || proof.request_id!==id
    || !Number.isSafeInteger(proof.issued_at) || !Number.isSafeInteger(proof.expires_at)
    || proof.issued_at<gate.activated_at || proof.issued_at>Math.floor(Date.now()/1000)
    || proof.expires_at-proof.issued_at!==900 || Math.floor(Date.now()/1000)>=proof.expires_at
    || proof.generation!==gate.generation || proof.audience!==gate.audience
    || typeof proof.session_hash!=='string' || !/^[a-f0-9]{64}$/.test(proof.session_hash)
    || typeof proof.signature!=='string' || !/^[a-f0-9]{64}$/.test(proof.signature)) return false;
  var signed='bsre-retention-admission-v1\\n'+proof.request_id+'\\n'+proof.issued_at+'\\n'+proof.expires_at
    +'\\n'+proof.session_hash+'\\n'+proof.generation+'\\n'+proof.audience;
  var expected=hex_(Utilities.computeHmacSha256Signature(signed,cfg.secret,Utilities.Charset.UTF_8));
  return same_(expected,proof.signature);
}
function doPost(e) {`);
  source = replace(source, '    var p = validateLead_(authenticate_(e,cfg));',
    '    var p = validateLead_(authenticate_(e,cfg));\n    var admissionGate = retentionAdmissionDescriptor_();');
  source = replace(source, "    var now = new Date().toISOString(), lead = 'BSRE-'+Utilities.getUuid(), event = 'evt_'+Utilities.getUuid();",
    "    if (admissionGate.mode === 'ENFORCED' && !validRetentionAdmission_(admissionEnvelope_(e),p.request_id,cfg,admissionGate)) return json_({accepted:false,code:'ADMISSION_REQUIRED',retryable:false});\n    var now = new Date().toISOString(), lead = 'BSRE-'+Utilities.getUuid(), event = 'evt_'+Utilities.getUuid();");
  return Buffer.from(source);
}

export function buildRetentionAdmissionClient(bytes) {
  let source = buildPurposeClientCandidate(bytes);
  source = replace(source, "    let attemptProof = '';", "    let attemptProof = '';\n    let attemptAdmission = null;");
  source = replace(source, '  function validProof(value) {', `  function admissionRequired() {
    return window.BSRELeadConfig && window.BSRELeadConfig.retentionAdmissionRequired === true;
  }
  function admissionShape(value, id) {
    return value && value.version === 1 && value.request_id === id && Number.isSafeInteger(value.issued_at)
      && Number.isSafeInteger(value.expires_at) && value.expires_at - value.issued_at === 900
      && ['session_hash','generation','audience','signature'].every(key => typeof value[key] === 'string' && /^[a-f0-9]{64}$/.test(value[key]));
  }
  function admissionHeaders(retry, permission, proof) {
    const headers = requestHeaders(retry, permission);
    if (admissionRequired() && proof) headers['X-BSRE-Admission'] = JSON.stringify(proof);
    return headers;
  }
  function validProof(value) {`);
  source = replace(source, '              attemptProof = result.proof;', '              attemptProof = result.proof;\n              attemptAdmission = result.admission || null;');
  source = replace(source, "          if (hasPendingEnquiry()) throw new Error('Another submission is pending');",
    "          if (admissionRequired() && !admissionShape(attemptAdmission, requestId)) throw new Error('Admission proof unavailable');\n          if (hasPendingEnquiry()) throw new Error('Another submission is pending');");
  source = replace(source, 'headers: requestHeaders(retry, attemptPermission),', 'headers: admissionHeaders(retry, attemptPermission, attemptAdmission),');
  return source;
}

export function retentionAdmissionSourceHash(bytes) { return createHash('sha256').update(bytes).digest('hex'); }

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [mode, input, second, output] = process.argv.slice(2);
  if (mode === 'store') writeFileSync(second, buildRetentionAdmissionStore(readFileSync(input)));
  else if (mode === 'intake') writeFileSync(output, buildRetentionAdmissionIntake(readFileSync(input), readFileSync(second)));
  else if (mode === 'client') writeFileSync(second, buildRetentionAdmissionClient(readFileSync(input)));
  else if (mode === 'receiver') writeFileSync(second, buildRetentionAdmissionReceiver(readFileSync(input)));
  else throw new Error('RETENTION_ADMISSION_BUILD_MODE_REQUIRED');
}
