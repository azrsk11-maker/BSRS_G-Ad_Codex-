/** Explicit held review-input successor. Historical pins/maps are never rewritten. */
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

const moduleRoot=new URL('./',import.meta.url);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const need=(ok,code)=>{if(!ok)throw Error(code);};
const queue='tools/qualified-export-source/source_queue.py';
const expected={
 schema:'bsre-g39-current-input-context-v1',context_id:'RETENTION_EXPIRY_INPUT_V1',mode:'ENGINEERING_ONLY_HELD',
 base:{source_pins_sha256:'57cb91efe6b6f4349d413723125c30b4b123ad9cb924b8f94dc2ec5623a0c4a7',input_map_sha256:'daf999e3e8360829cc6cd06d7c2cc629fb539b857581b99270a277001d2ad031',accepted_runtime_source_head:'c6fab35e579fb942c28c0ae6d91a81f5c0be8cef',input_count:26},
 change:{path:queue,role:'REVIEW_CONTEXT_STILL_PIN_REQUIRED',before:{sha256:'efc094cd32b60702fa65ba53f11a5d079ba5713f25bed86c2b3346547ba65392',bytes:29937},after:{bytes:30344,sha256:'5f48da6b20cc55586056fc37f9fcb8ccacc7ced4236a553bd8cdafdd40c35c39'}},
 invariants:{unchanged_input_count:25,native_runtime_file_count:25,native_case_count:43,native_manifest_sha256:'e3b69f721aafeda0242982b35ce96b8b2b61f9f92df54c34f9cd4362593e2fde'},
 authority:{production_authorized:false,export_authorized:false,provider_accepted:false,business_evidence_accepted:false,release_authorized:false}
};
function same(a,b){
 if(a===null||b===null||typeof a!=='object'||typeof b!=='object')return a===b;
 const ak=Object.keys(a).sort(),bk=Object.keys(b).sort();
 return JSON.stringify(ak)===JSON.stringify(bk)&&ak.every(k=>same(a[k],b[k]));
}
function freeze(value){if(value&&typeof value==='object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}

export function currentInputProfile(){
 need(arguments.length===0,'G39_CONTEXT_NO_ARGUMENTS');
 const raw=readFileSync(new URL('CURRENT_INPUT_CONTEXT.json',moduleRoot));
 const descriptor=JSON.parse(raw.toString('utf8'));
 need(same(descriptor,expected),'G39_CONTEXT_DESCRIPTOR_CHANGED');
 const sourceRaw=readFileSync(new URL('SOURCE_PINS.json',moduleRoot));
 const mapRaw=readFileSync(new URL('MATERIALIZER_INPUT_MAP.json',moduleRoot));
 need(sha(sourceRaw)===descriptor.base.source_pins_sha256&&sha(mapRaw)===descriptor.base.input_map_sha256,
      'G39_CONTEXT_HISTORICAL_INPUTS_CHANGED');
 const pins=JSON.parse(sourceRaw.toString('utf8')),inputMap=JSON.parse(mapRaw.toString('utf8'));
 need(pins.accepted_head===descriptor.base.accepted_runtime_source_head&&Object.keys(pins.files).length===26&&
      same(pins.files[queue],descriptor.change.before)&&inputMap.files[queue].role===descriptor.change.role&&
      Object.keys(inputMap.files).length===26,'G39_CONTEXT_BASE_BINDING_CHANGED');
 pins.files[queue]={...descriptor.change.after};
 inputMap.files[queue]={...inputMap.files[queue],...descriptor.change.after};
 const receipt={schema:'bsre-g39-current-input-context-receipt-v1',context_id:descriptor.context_id,
  descriptor_sha256:sha(raw),historical_source_pins_sha256:sha(sourceRaw),historical_input_map_sha256:sha(mapRaw),
  effective_source_pins_sha256:sha(JSON.stringify(pins)),changed_input:descriptor.change,
  input_count:26,unchanged_input_count:25,frozen_runtime_manifest_sha256:descriptor.invariants.native_manifest_sha256,
  native_operational_behavior_changed:false,current_head_native_accepted:false,...descriptor.authority};
 return freeze({pins,inputMap,receipt});
}
