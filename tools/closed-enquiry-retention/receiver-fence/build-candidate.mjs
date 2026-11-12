import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {buildRetentionAdmissionReceiver} from '../../website-tracking/tracking-system/build-retention-admission-candidate.mjs';

/** Instrument the exact pinned receiver; retain Intake26, signed wire-v1 and ScriptLock. */
export function buildNoMailCopyReceiver(bytes) {
  let code = buildRetentionAdmissionReceiver(bytes).toString('utf8');
  function replace(before, after) {
    if (code.split(before).length !== 2) throw new Error('NO_COPY_RECEIVER_ANCHOR_CHANGED');
    code = code.replace(before, after);
  }
  // Re-read the admission generation after lock acquisition as part of the current namespace gate.
  replace('    var admissionGate = retentionAdmissionDescriptor_();', '    var admissionGate;');
  replace('    var s = leadSheet_(cfg), old = existingLead_(s,p.request_id,0);',
    '    closedNoCopyGate_();\n    admissionGate = retentionAdmissionDescriptor_();\n    closedNoCopyAssertRequest_(p.request_id);\n    var s = leadSheet_(cfg), old = existingLead_(s,p.request_id,0);');
  replace('    if (old) {\n      if (!same_', '    if (old) {\n      closedNoCopyAssertMutable_(old.values);\n      if (!same_');
  replace('      var r=rows[i], row=i+2, status=r[6], attempts=Number(r[7]) || 0;',
    '      var r=rows[i], row=i+2, status=r[6], attempts=Number(r[7]) || 0;\n      if (!closedNoCopyMaySend_(r)) continue;');
  replace('    var s=leadSheet_(routingConfig_()), found=existingLead_(s,leadId,1);',
    '    closedNoCopyGate_();\n    var s=leadSheet_(routingConfig_()), found=existingLead_(s,leadId,1);\n    if (found) closedNoCopyAssertMutable_(found.values);');
  // Minimal status lookup must not turn a retired body into a new accepted receipt.
  replace('    var found = existingLead_(leadSheet_(cfg),value.request_id,0);',
    '    closedNoCopyGate_();\n    closedNoCopyAssertRequest_(value.request_id);\n    var found = existingLead_(leadSheet_(cfg),value.request_id,0);\n    if (found) closedNoCopyAssertMutable_(found.values);');
  replace("var known = ['AUTH_FAILED','VALIDATION_FAILED','NOT_CONFIGURED','ROUTING_DISABLED','SHEET_NOT_INITIALIZED','DUPLICATE_ROWS_RECONCILE'];",
    "var known = ['AUTH_FAILED','VALIDATION_FAILED','NOT_CONFIGURED','ROUTING_DISABLED','SHEET_NOT_INITIALIZED','DUPLICATE_ROWS_RECONCILE','NO_COPY_REQUEST_RETIRED'];");
  code += '\n' + readFileSync(new URL('./runtime.gs', import.meta.url), 'utf8');
  return Buffer.from(code, 'utf8');
}

export function noMailCopyReceiverHash(bytes) { return createHash('sha256').update(buildNoMailCopyReceiver(bytes)).digest('hex'); }
