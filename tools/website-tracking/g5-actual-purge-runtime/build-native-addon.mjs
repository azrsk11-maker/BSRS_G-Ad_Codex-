/** Pure Source-ready G38 add-on. Runtime target/prefixes/progress are fixed, never options. */
import {readFileSync} from 'node:fs';
import {nativePacketFromInputs} from './build-native.mjs';import {sha} from './build.mjs';
export const FIXED_PURGE_ROOT='/opt/lab/g5-actual-purge-runtime';
export const PURGE_CASES=Object.freeze({
 held:Object.freeze({prefix:'g5_purge_held_synthetic_',progress:'/tmp/g5-purge-held-progress.json',entry:'tests/purge-held-native.php',phase:'g5_actual_purge_held'}),
 positive:Object.freeze({prefix:'g5_purge_positive_synthetic_',progress:'/tmp/g5-purge-positive-progress.json',entry:'tests/purge-positive-native.php',phase:'g5_actual_purge_positive'})
});
export const RECEIVER_INPUT_PATHS=Object.freeze([
 'build-candidate.mjs','runtime/control.gs','runtime/no-copy.gs',
 'candidate/plugin/includes/candidate/receiver/ReceiverContracts.php','candidate/plugin/includes/candidate/receiver/NoMailCopyAlgebra.php',
 'candidate/plugin/includes/candidate/receiver/ActualRetirementPort.php','candidate/plugin/includes/candidate/receiver/ReceiverOperationalEvidence.php',
 'candidate/plugin/includes/candidate/receiver/ActualReceiverWorkflow.php','candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php',
 'tests/control-fixture.mjs','tests/native-bridge.mjs'
]);
export const ACTUAL_PURGE_RUNTIME_PATHS=Object.freeze([
 ...RECEIVER_INPUT_PATHS,'tests/purge-held-native.php','tests/native-extension.php','tests/purge-positive-native.php','tests/native-positive.php',
 'tests/intake26-headers.json','tests/outcome40-schema.json','tests/foreign-capture-snapshot.php','tests/approval-identity.php',
 ...['ActualPurgeEngine.php','ActualPurgeJournal.php','ActualPurgeCaptureResource.php','ActualPurgeResources.php','ActualPurgeWorkflow.php','PurgeBoundary.php','CaptureRules.php'].map(n=>'candidate/plugin/includes/candidate/closed-enquiry-retention/'+n),
 'G38_BUILD.json'
]);
const need=(ok,code)=>{if(!ok)throw Error(code);};
function transform(bytes,mode,member){
 const original=Buffer.from(bytes);let text=original.toString('utf8');const edits=[];const c=PURGE_CASES[mode];
 function move(before,after,label){const count=text.split(before).length-1;need(count>0,'G38_ANCHOR_MISSING:'+label);for(let i=0;i<count;i++){const at=text.indexOf(before);edits.push({label,offset:Buffer.byteLength(text.slice(0,at)),before,after});text=text.slice(0,at)+after+text.slice(at+before.length);}}
 if(text.includes('/opt/lab/g5-receiver-runtime'))move('/opt/lab/g5-receiver-runtime',FIXED_PURGE_ROOT,'OWN_RUNTIME_ROOT');
 if(text.includes('g5_receiver_synthetic_'))move('g5_receiver_synthetic_',c.prefix,'OWN_CASE_NAMESPACE');
 if(text.includes('g5_receiver_foreign_synthetic_'))move('g5_receiver_foreign_synthetic_','g5_purge_held_foreign_synth_','OWN_FOREIGN_PROBE');
 if(text.includes('/tmp/g5-receiver-runtime-progress.json'))move('/tmp/g5-receiver-runtime-progress.json',c.progress,'OWN_CASE_PROGRESS');
 if(mode==='held'&&text.includes("'phase'=>'g5_receiver_runtime'"))move("'phase'=>'g5_receiver_runtime'","'phase'=>'g5_actual_purge_held'",'OWN_PHASE');
 if(member===c.entry){
  const before="$wpdb->prefix='"+c.prefix+"';E\\install();";
  const after="$wpdb->prefix='"+c.prefix+"';\n"+
   "require_once '/opt/lab/g36/contact-abi.php';\n"+
   "require_once __DIR__.'/foreign-capture-snapshot.php';\n"+
   "$purgeForeignBefore=\\BSRE\\G38PurgeLab\\snapshot();\n"+
   "if(!array_filter($purgeForeignBefore,fn($row)=>$row['rows']>=1100))throw new RuntimeException('G38_FOREIGN_SCALE_PREDECESSOR_REQUIRED');\n"+
   "$wpdb->last_error='';$purgeExisting=$wpdb->get_col($wpdb->prepare('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND BINARY LEFT(TABLE_NAME,%d)=BINARY %s ORDER BY TABLE_NAME LIMIT 2',strlen($wpdb->prefix),$wpdb->prefix));\n"+
   "if($wpdb->last_error!==''||$purgeExisting!==[])throw new RuntimeException('G38_FRESH_CASE_NAMESPACE_REQUIRED');\nE\\install();";
  need(text.split(before).length===2,'G38_FRESH_NAMESPACE_ANCHOR_CHANGED');move(before,after,'FRESH_NAMESPACE_AND_FOREIGN_SNAPSHOT');
  const foreign="$purgeForeignAfter=\\BSRE\\G38PurgeLab\\snapshot();\n"+
   "unset($purgeForeignAfter['"+c.prefix+"bsre_consent_captures']);\n"+
   "receiver_check('purge_foreign_capture_tables_preserved',$purgeForeignAfter===$purgeForeignBefore);\n";
  const anchor=mode==='held'?" $producer->assertCurrent($wpdb);receiver_check('lease_clean_and_original_global_preserved'":" echo wp_json_encode(['phase'=>'g5_actual_purge_positive'";
  need(text.split(anchor).length===2,'G38_FOREIGN_READBACK_ANCHOR_CHANGED');move(anchor,foreign+anchor,'FOREIGN_SCOPE_READBACK');
 }
 let recovered=Buffer.from(text);for(const e of [...edits].reverse()){const b=Buffer.from(e.after);need(recovered.subarray(e.offset,e.offset+b.length).equals(b),'G38_REVERSE_ANCHOR');recovered=Buffer.concat([recovered.subarray(0,e.offset),Buffer.from(e.before),recovered.subarray(e.offset+b.length)]);}
 need(recovered.equals(original),'G38_REVERSE_FAILED');return {bytes:Buffer.from(text),receipt:{member,mode,preimage_sha256:sha(original),output_sha256:sha(Buffer.from(text)),reverse_verified:true,edits}};
}
/** Pure testable assembly. Inputs are detached bytes, not a filesystem destination. */
export function assembleActualPurgeAddon(packet,receiverInputs,pins){
 need(packet?.files instanceof Map&&packet.manifest?.predecessor_driver_sha256==='cad4718a78f229ebecb376575cf78166c1cfb8e2ab0c76109fcee56ad3ec97c9','G38_REVIEWED_DRIVER_REQUIRED');
 need(sha(packet.files.get('candidate/plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php'))==='87c2012acf8d27a93063bd7ace11ae33dec548837de3e29c2569274c0b1e7671'
  &&sha(packet.files.get('tests/outcome40-schema.json'))==='bf477cc0cc4a161775abd702777898c6046d5dfcf0f2ae0e86fe078a3a63d9df'
  &&sha(JSON.stringify(JSON.parse(packet.files.get('tests/intake26-headers.json').toString())))==='0dcac495bed4beda7a027c5d21d0d8b1caaa8a307e6eb815e3566c46f41369ca','G38_REVIEWED_CONTRACT_CHANGED');
 need(receiverInputs instanceof Map&&receiverInputs.size===RECEIVER_INPUT_PATHS.length,'G38_RECEIVER_INPUT_SET_INVALID');
 const files=new Map();for(const path of RECEIVER_INPUT_PATHS){const b=receiverInputs.get(path);need(Buffer.isBuffer(b)&&pins[path]?.sha256===sha(b)&&pins[path]?.bytes===b.length,'G38_RECEIVER_SOURCE_CHANGED');files.set(path,Buffer.from(b));}
 const derivations=[];
 for(const [old,b] of packet.files){const member=old==='tests/receiver-runtime-native.php'?PURGE_CASES.held.entry:old;
  const mode=member===PURGE_CASES.held.entry||member==='tests/native-extension.php'?'held':member===PURGE_CASES.positive.entry||member==='tests/native-positive.php'?'positive':null;
  const result=mode?transform(b,mode,member):{bytes:Buffer.from(b)};
  need(ACTUAL_PURGE_RUNTIME_PATHS.includes(member)&&!files.has(member),'G38_ADDON_FILESET_CHANGED');files.set(member,result.bytes);if(result.receipt)derivations.push(result.receipt);
 }
 files.set('tests/foreign-capture-snapshot.php',readFileSync(new URL('./tests/foreign-capture-snapshot.php',import.meta.url)));
 need(files.size===26,'G38_ADDON_FILESET_CHANGED');
 for(const [mode,c]of Object.entries(PURGE_CASES)){
  need(c.prefix.length<=41&&/^[a-z][a-z0-9_]+_$/.test(c.prefix),'G38_NAMESPACE_INVALID');
  const driver=files.get(c.entry).toString();need(driver.includes("$wpdb->prefix='"+c.prefix+"'")&&driver.includes(c.progress)&&driver.includes("realpath(__DIR__)!=='"+FIXED_PURGE_ROOT+"/tests'"),'G38_CASE_BINDING_INVALID');
 }
 const checks=mode=>{const ext=mode==='held'?'native-extension.php':'native-positive.php',driver=files.get(PURGE_CASES[mode].entry).toString();
  const actualHook="require __DIR__.'/"+ext+"';";need(driver.split(actualHook).length===2,'G38_INCLUDE_ORDER_ANCHOR_CHANGED');
  return [...driver.replace(actualHook,files.get('tests/'+ext).toString()).matchAll(/receiver_check\('([^']+)'/g)].map(m=>m[1]);};
 const manifest={schema:'bsre-actual-purge-runtime-synthetic-lab-v1',profile:'G38_ACTUAL_PURGE_ENGINEERING_ONLY',fixed_root:FIXED_PURGE_ROOT,
  cases:Object.fromEntries(Object.entries(PURGE_CASES).map(([mode,c])=>[mode,{...c,fresh_case_namespace_required:true,fresh_database_required:false,expected_checks:checks(mode)}])),
  predecessor_driver_sha256:packet.manifest.predecessor_driver_sha256,derivations,
  synthetic_only:true,native_executed:false,provider_accepted:false,production_authorized:false,
  files:Object.fromEntries([...files].map(([p,b])=>[p,{sha256:sha(b),bytes:b.length}]))};
 files.set('G38_BUILD.json',Buffer.from(JSON.stringify(manifest,null,2)+'\n'));
 return {files,manifest,synthetic_only:true,provider_accepted:false,production_authorized:false};
}
/** Source layout determines input root. No arguments, env or target override. */
export function buildActualPurgeNativeLab(){
 need(arguments.length===0,'G38_NO_ARGUMENTS');
 const pins=JSON.parse(readFileSync(new URL('./REVIEWED_RECEIVER_INPUTS.json',import.meta.url),'utf8'));
 const receiver=new Map(RECEIVER_INPUT_PATHS.map(p=>[p,readFileSync(new URL('../g5-receiver-runtime/'+p,import.meta.url))]));
 const packet=nativePacketFromInputs({driver:readFileSync(new URL('../g5-receiver-runtime/tests/receiver-runtime-native.php',import.meta.url)),
  captureRules:readFileSync(new URL('../g5-runtime-ports/candidate/plugin/includes/candidate/closed-enquiry-retention/CaptureRules.php',import.meta.url)),
  intakeSource:readFileSync(new URL('../../staging-lab/fixtures/receiver-v2/Code.gs',import.meta.url)),
  outcomeSchema:readFileSync(new URL('../../qualification-history/schema/outcome-register-schema.json',import.meta.url))});
 return assembleActualPurgeAddon(packet,receiver,pins);
}
