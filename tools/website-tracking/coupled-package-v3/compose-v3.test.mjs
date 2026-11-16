import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,mkdirSync,writeFileSync,readdirSync,rmSync} from 'node:fs';
import {join,dirname} from 'node:path';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {composeCoupledCanonicalLeaseV3,assertHeldCandidateV3,CONTRACT_V3,digest} from './compose-v3.mjs';
import {writeHeldCanonicalV3} from './write-held-v3.mjs';
import {syntheticInput,SOURCE_ROOT} from './synthetic-input.mjs';
const pins=JSON.parse(readFileSync(new URL('./source-pins-v3.json',import.meta.url)));
const selection=result=>({profile:CONTRACT_V3.profile,...result.private_manifest.bindings,
  review_ref:'SYNTHETIC_EXPLICIT_M_P_REVIEW',diagnostic_only:true,deployment_prohibited:true,full_profile_complete:false});
function writeSelection(result){const s=selection(result);delete s.source_manifest_members;return s;}
test('closed V3 site paths preserve receiver and exact68available/70required with only2realports missing',()=>{
  assert.equal(CONTRACT_V3.available_paths.length,68);assert.equal(CONTRACT_V3.required_outputs.length,70);
  assert.equal(new Set(CONTRACT_V3.required_outputs).size,70);assert.equal(CONTRACT_V3.known_missing_real_ports.length,2);
  assert.ok(CONTRACT_V3.available_paths.includes('site/wp-content/db.php'));assert.ok(CONTRACT_V3.available_paths.includes('companion/receiver/Code.gs'));
  assert.ok(!CONTRACT_V3.available_paths.some(p=>p.startsWith('plugin/')));
});
test('actual V2/G35/domain builders produce64final source bindings and repeated M/P reversals',async()=>{
  const input=await syntheticInput(),result=await composeCoupledCanonicalLeaseV3(input),m=result.private_manifest;
  assert.equal(result.files.size,68);assert.equal(m.critical_G35_source_members.length,55);assert.equal(m.additional_nine_source_members.length,9);
  assert.equal(m.selected_domain_derivations.length,22);assert.equal(m.v2_private_manifest.outputs.length,65);
  assert.equal(m.v2_source_composer_sha256,pins.files['tools/website-tracking/coupled-package/compose-v2.mjs']);
  assert.equal(result.public_summary.native_v3_accepted,false);assert.equal(result.public_summary.complete_profile_certified,false);
  const manifest=JSON.parse(result.files.get(CONTRACT_V3.manifest_path));assert.equal(Object.keys(manifest.files).length,64);
  for(const [path,hash]of Object.entries(manifest.files))assert.equal(hash,digest(result.files.get(CONTRACT_V3.plugin_prefix+path)));
  assert.ok(!Object.hasOwn(manifest.files,CONTRACT_V3.producer_relative_path));assert.ok(!Object.hasOwn(manifest.files,CONTRACT_V3.manifest_relative_path));
  assert.ok(!Object.keys(manifest.files).some(p=>p.includes('receiver/Code.gs')||p==='db.php'));
  const dropin=result.files.get(CONTRACT_V3.dropin_path).toString(),producer=result.files.get(CONTRACT_V3.producer_path).toString();
  assert.equal(dropin.split(m.bindings.M).length-1,2);assert.equal(dropin.split(m.bindings.P).length-1,2);assert.equal(producer.split(m.bindings.M).length-1,1);
  assert.equal(m.template_derivation.all_template_bytes_reverse_to_accepted_G35,true);assert.equal(m.template_derivation.core_query_whitelist_byte_identical,true);
  assert.equal(m.template_derivation.profile_count_edits.producer.length,2);assert.equal(m.template_derivation.profile_count_edits.dropin.length,2);
  assert.equal(m.template_derivation.hash_binding_edits.dropin.length,4);assert.equal(assertHeldCandidateV3(result),true);
});
test('final postcontact client/templates are M-bound while receiver and V2 proofs stay exact',async()=>{
  const input=await syntheticInput({comment:true}),result=await composeCoupledCanonicalLeaseV3(input),m=result.private_manifest;
  const {composeCoupledPackageV2}=await import(pathToFileURL(join(SOURCE_ROOT,'tools/website-tracking/coupled-package/compose-v2.mjs')).href);
  // Re-run the unchanged actual V2 entry with exactly the source-derived selected members.
  const selected=m.selected_domain_derivations.map(row=>({path:row.path,bytes:result.files.get(CONTRACT_V3.plugin_prefix+row.path.slice(7))}));
  const independently=await composeCoupledPackageV2({...input.v2_input,selected_outputs:selected,
    selected_output_pins:Object.fromEntries(selected.map(row=>[row.path,digest(row.bytes)]))});
  for(const [path,bytes]of independently.files){if(path==='plugin/bsre-enquiries.php')assert.equal(digest(bytes),m.main_include.input_sha256);
    else assert.ok(result.files.get(path.startsWith('plugin/')?CONTRACT_V3.plugin_prefix+path.slice(7):path).equals(bytes),path);}
  const privateV2=m.v2_private_manifest;assert.equal(privateV2.ancestry.length,8);assert.ok(privateV2.ancestry.every(r=>r.reverse_verified));
  assert.equal(privateV2.capture_guard_compatibility.actual_raw_members.length,30);assert.equal(privateV2.capture_guard_compatibility.actual_capture_rewritten,false);
  const client=result.files.get(CONTRACT_V3.plugin_prefix+'assets/lead.js').toString();
  for(const token of ['BSRENativePageContext','X-BSRE-Admission','Admission proof unavailable'])assert.ok(client.includes(token));
  const clientProof=privateV2.ancestry.find(p=>p.member==='assets/lead.js');assert.ok(clientProof.order.indexOf('G4-native-context')<clientProof.order.indexOf('typed-contact-overlay-v1'));
  const guard=result.files.get(CONTRACT_V3.plugin_prefix+'includes/parent-isolation.php').toString();assert.ok(!guard.includes('phone number updated'));
  assert.equal(m.receiver_sha256,digest(result.files.get('companion/receiver/Code.gs')));
  assert.equal(m.receiver_sha256,privateV2.outputs.find(r=>r.path==='companion/receiver/Code.gs').sha256);
  assert.equal(m.main_include.reverse_verified,true);assert.equal(m.main_include.class_only,true);
  assert.equal(independently.files.size,65);
});
test('actual accepted templates recover exactly after all4profile/count and5M/P edits',async()=>{
  const result=await composeCoupledCanonicalLeaseV3(await syntheticInput()),m=result.private_manifest,b=m.bindings;
  const producerOriginal=readFileSync(join(SOURCE_ROOT,'tools/website-tracking/canonical-lease/CanonicalCaptureProducer.template.php'));
  const dropinOriginal=readFileSync(join(SOURCE_ROOT,'tools/website-tracking/canonical-lease/db.php'));
  let producer=result.files.get(CONTRACT_V3.producer_path).toString().replace(b.M,'__BSRE_CODE_MANIFEST_SHA256__');
  producer=producer.replace("MANIFEST_PROFILE='G36_COUPLED_CANONICAL_LEASE_V3'","MANIFEST_PROFILE='G35_CANONICAL_LEASE_CODE_ONLY'").replace("count($manifest['files'])!==64","count($manifest['files'])!==55");
  assert.ok(Buffer.from(producer).equals(producerOriginal));
  let dropin=result.files.get(CONTRACT_V3.dropin_path).toString();const replacements=[['__BSRE_CODE_MANIFEST_SHA256__',b.M],['__BSRE_BOUND_MANIFEST_SHA256__',b.M],['__BSRE_PRODUCER_SHA256__',b.P],['__BSRE_BOUND_PRODUCER_SHA256__',b.P]];
  // Positions in accepted template make duplicate values unambiguous.
  let expected=dropinOriginal.toString().replace("$bsreManifest['profile'] !== 'G35_CANONICAL_LEASE_CODE_ONLY'","$bsreManifest['profile'] !== 'G36_COUPLED_CANONICAL_LEASE_V3'").replace("count($bsreManifest['files']) !== 55","count($bsreManifest['files']) !== 64");
  for(const [marker,value]of replacements)expected=expected.replace(marker,value);assert.equal(dropin,expected);
});
test('different synthetic contact changes final M/P without repinning source or receiver',async()=>{
  const a=await composeCoupledCanonicalLeaseV3(await syntheticInput()),b=await composeCoupledCanonicalLeaseV3(await syntheticInput({digits:'19995550124',display:'+1 999 555 0124'}));
  assert.notEqual(a.private_manifest.bindings.M,b.private_manifest.bindings.M);assert.notEqual(a.private_manifest.bindings.P,b.private_manifest.bindings.P);
  assert.equal(a.private_manifest.source_pin_manifest_sha256,b.private_manifest.source_pin_manifest_sha256);
  assert.ok(a.files.get(CONTRACT_V3.receiver_path).equals(b.files.get(CONTRACT_V3.receiver_path)));
});
test('portable synthetic native site is67files and final hub bytes bind unchanged owned page26750 guard',async()=>{
  const result=await composeCoupledCanonicalLeaseV3(await syntheticInput({source_root:SOURCE_ROOT}));
  const site=[...result.files].filter(([p])=>p.startsWith('site/'));assert.equal(site.length,67);
  assert.equal(site.filter(([p])=>p.startsWith(CONTRACT_V3.plugin_prefix)).length,66);
  assert.ok(!site.some(([p])=>p.includes('companion/receiver')));
  const hub=result.files.get(CONTRACT_V3.plugin_prefix+'templates/source/hub.html'),guard=result.files.get(CONTRACT_V3.plugin_prefix+'includes/parent-isolation.php').toString();
  assert.equal(guard.match(/const OWNED_HUB_SHA256 = '([a-f0-9]{64})';/)[1],digest(hub));
  assert.ok(guard.includes('const OWNED_HUB_PAGE_ID = 26750;'));
  const manifest=JSON.parse(result.files.get(CONTRACT_V3.manifest_path));assert.equal(manifest.files['templates/source/hub.html'],digest(hub));
});
test('closed API rejects arbitrary source/output/manifest/callback overrides',async()=>{
  for(const [key,value]of [['selected_outputs',[]],['selected_output_pins',{}],['manifest',{}],['read',()=>Buffer.from('fake')],['require_all_selected_outputs',true]]){
    const f=await syntheticInput();f.v2_input[key]=value;await assert.rejects(composeCoupledCanonicalLeaseV3(f),/V3_EXTERNAL_SOURCE_OVERRIDE_FORBIDDEN/);}
  const f=await syntheticInput();f.files=new Map();await assert.rejects(composeCoupledCanonicalLeaseV3(f),/V3_CLOSED_INPUT_SHAPE/);
});
test('a missing or altered G3/G4 selection cannot be substituted by a held flags object',async()=>{
  const a=await syntheticInput();delete a.v2_input.g4_manifest_bytes;await assert.rejects(composeCoupledCanonicalLeaseV3(a),/V3_G4_SELECTION_REQUIRED/);
  const b=await syntheticInput();b.v2_input.g3_selection_receipt.manifest_sha256='0'.repeat(64);await assert.rejects(composeCoupledCanonicalLeaseV3(b),/V2_SELECTION_RECEIPT_CHANGED/);
});
test('every actual captured reconciliation member still fails closed on drift',async()=>{
  const names=['assets/lead.js','templates/source/off-plan.html','templates/source/resale.html','templates/source/rent.html','templates/source/sell.html','templates/source/let.html','templates/source/hub.html','includes/parent-isolation.php'];
  for(const name of names){const f=await syntheticInput(),row=f.v2_input.captured.find(r=>r.path===name);row.bytes=Buffer.concat([row.bytes,Buffer.from('x')]);
    await assert.rejects(composeCoupledCanonicalLeaseV3(f),/CAPTURE_MEMBER_CHANGED/);}
});
test('changed pinned V2/source/template bytes reject before arbitrary imports',async()=>{
  const temp=mkdtempSync(join(tmpdir(),'g36-source-drift-'));
  try{for(const path of Object.keys(pins.files)){const dest=join(temp,path);mkdirSync(dirname(dest),{recursive:true});writeFileSync(dest,readFileSync(join(SOURCE_ROOT,path)));}
    const f=await syntheticInput();f.source_root=temp;f.v2_input.source_root=temp;f.v2_input.g4_source_root=temp;
    const path='tools/website-tracking/canonical-lease/CanonicalCaptureProducer.template.php';writeFileSync(join(temp,path),'SYNTHETIC_UNREVIEWED_TEMPLATE');
    await assert.rejects(composeCoupledCanonicalLeaseV3(f),/V3_SOURCE_PIN_CHANGED/);
  }finally{rmSync(temp,{recursive:true});}
});
test('output validator rejects member/M/P tampering and public summary omits identities/hashes/paths',async()=>{
  const input=await syntheticInput(),result=await composeCoupledCanonicalLeaseV3(input),pub=JSON.stringify(result.public_summary);
  assert.ok(!pub.includes(input.v2_input.identity.to_digits));assert.ok(!pub.includes(SOURCE_ROOT));assert.ok(!/[a-f0-9]{64}/.test(pub));
  result.files.get(CONTRACT_V3.plugin_prefix+'assets/lead.js')[0]^=1;assert.throws(()=>assertHeldCandidateV3(result),/V3_OUTPUT_HASH_CHANGED/);
});
test('private writer requires separate exact Root M/P selection, disjoint roots and no overwrite',async()=>{
  const temp=mkdtempSync(join(tmpdir(),'g36-synthetic-write-'));
  try{const a=join(temp,'a'),b=join(temp,'b');mkdirSync(a);mkdirSync(b);const result=await composeCoupledCanonicalLeaseV3(await syntheticInput());
    const options={destination:join(temp,'held'),input_roots:[a,b],visibility:'PRIVATE_OFFLINE_ONLY'};
    assert.throws(()=>writeHeldCanonicalV3(result,options),/V3_ROOT_M_P_SELECTION_REQUIRED/);
    const bad=writeSelection(result);bad.P='0'.repeat(64);assert.throws(()=>writeHeldCanonicalV3(result,{...options,selection_binding:bad}),/V3_ROOT_M_P_SELECTION_REQUIRED/);
    assert.throws(()=>writeHeldCanonicalV3(result,{...options,destination:join(SOURCE_ROOT,'g36-never-write'),selection_binding:writeSelection(result)}),/V3_COMPOSE_SOURCE_OVERLAP/);
    assert.throws(()=>writeHeldCanonicalV3(result,{...options,destination:join(SOURCE_ROOT,'..g36-child'),selection_binding:writeSelection(result)}),/V3_COMPOSE_SOURCE_OVERLAP/);
    assert.throws(()=>writeHeldCanonicalV3({...result},{...options,destination:join(temp,'forged'),selection_binding:writeSelection(result)}),/V3_GENUINE_COMPOSE_RESULT_REQUIRED/);
    assert.throws(()=>writeHeldCanonicalV3(result,{...options,destination:join(a,'overlap'),selection_binding:writeSelection(result)}),/V3_OUTPUT_INPUT_OVERLAP/);
    assert.throws(()=>writeHeldCanonicalV3(result,{...options,destination:join(a,'..g36-child'),selection_binding:writeSelection(result)}),/V3_OUTPUT_INPUT_OVERLAP/);
    writeHeldCanonicalV3(result,{...options,selection_binding:writeSelection(result)});
    const manifest=JSON.parse(readFileSync(join(options.destination,'PRIVATE_MANIFEST.json')));assert.equal(manifest.outputs.length,68);assert.equal(manifest.summary.complete_profile_certified,false);
    assert.throws(()=>writeHeldCanonicalV3(result,{...options,selection_binding:writeSelection(result)}),/V3_NEW_OUTPUT_DIRECTORY_REQUIRED/);
    assert.deepEqual(readdirSync(temp).sort(),['a','b','held']);
  }finally{rmSync(temp,{recursive:true});}
});
