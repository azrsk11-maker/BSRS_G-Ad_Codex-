/** New default-OFF operational receiver derivative. Original selected receiver remains immutable. */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
export const SELECTED_RECEIVER_SHA256='00b62f1edc8996ab4f566a80155715a85f741bc5d68e7a0a54c94fc4ef2cbdc5';
export const digest=value=>createHash('sha256').update(value).digest('hex');
const need=(ok,code)=>{if(!ok)throw new Error(code);};
function edit(text,before,after,edits,label){
  need(text.split(before).length===2,'ACTUAL_RECEIVER_ANCHOR_CHANGED:'+label);
  const offset=Buffer.byteLength(text.slice(0,text.indexOf(before)));
  edits.push({label,offset,before,after});return text.replace(before,after);
}
export function deriveActualRetirementReceiver(selected){
  need(Buffer.isBuffer(selected)&&selected.length===50830&&digest(selected)===SELECTED_RECEIVER_SHA256,'ACTUAL_RECEIVER_SELECTED_BASE_CHANGED');
  const before=selected.toString('utf8');let text=before;const edits=[];
  text=edit(text,'function doPost(e) {','function actualLegacyLeadPost_(e) {',edits,'ISOLATED_CONTROL_DISPATCH');
  // Keep every old guarded function unchanged. Only these exact caller sites select the
  // new operational domain after explicit activation; durable activation cannot fall back.
  for(const [a,b,label] of [
    ['    closedNoCopyGate_();\n    admissionGate', '    actualReceiverGate_();\n    admissionGate','POST_GATE'],
    ['    closedNoCopyAssertRequest_(p.request_id);','    actualReceiverAssertRequest_(p.request_id);','POST_REPLAY_FENCE'],
    ['      closedNoCopyAssertMutable_(old.values);','      actualReceiverAssertMutable_(old.values);','POST_EXISTING_FENCE'],
    ['      if (!closedNoCopyMaySend_(r)) continue;','      if (!actualReceiverMaySend_(r)) continue;','OUTBOX_FENCE'],
    ['    closedNoCopyGate_();\n    var s=leadSheet_', '    actualReceiverGate_();\n    var s=leadSheet_','STAFF_GATE'],
    ['    var s=leadSheet_(routingConfig_()), found=existingLead_(s,leadId,1);\n    if (found) closedNoCopyAssertMutable_(found.values);',
      '    var s=leadSheet_(routingConfig_()), found=existingLead_(s,leadId,1);\n    if (found) actualReceiverAssertMutable_(found.values);','STAFF_ROW_FENCE'],
    ['    var found = existingLead_(leadSheet_(cfg),value.request_id,0);\n    if (found) closedNoCopyAssertMutable_(found.values);',
      '    var found = existingLead_(leadSheet_(cfg),value.request_id,0);\n    if (found) actualReceiverAssertMutable_(found.values);','STATUS_ROW_FENCE']
  ])text=edit(text,a,b,edits,label);
  // The status lookup has its own exact three-line gate, deliberately separate from staff.
  text=edit(text,'    closedNoCopyGate_();\n    closedNoCopyAssertRequest_(value.request_id);',
    '    actualReceiverGate_();\n    actualReceiverAssertRequest_(value.request_id);',edits,'RECOVERY_STATUS_GATE');
  let recovered=Buffer.from(text);
  for(const e of [...edits].reverse()){
    const after=Buffer.from(e.after);need(recovered.subarray(e.offset,e.offset+after.length).equals(after),'ACTUAL_RECEIVER_REVERSE_ANCHOR');
    recovered=Buffer.concat([recovered.subarray(0,e.offset),Buffer.from(e.before),recovered.subarray(e.offset+after.length)]);
  }
  need(recovered.equals(selected),'ACTUAL_RECEIVER_REVERSE_FAILED');
  const control=readFileSync(new URL('./runtime/control.gs',import.meta.url),'utf8');
  const actual=readFileSync(new URL('./runtime/no-copy.gs',import.meta.url),'utf8');
  return {bytes:Buffer.from(text+'\n'+actual+'\n'+control),receipt:{selected_preimage_sha256:SELECTED_RECEIVER_SHA256,
    ordered_edits:edits,selected_base_reverse_verified:true,old_guarded_functions_preserved:true,
    default_enabled:false,provider_accepted:false,production_authorized:false}};
}
export function buildActualRetirementReceiver(selected){return deriveActualRetirementReceiver(selected).bytes;}
