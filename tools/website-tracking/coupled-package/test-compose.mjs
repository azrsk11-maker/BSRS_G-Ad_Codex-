import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, mkdtempSync, mkdirSync, writeFileSync, readdirSync, symlinkSync, rmSync} from 'node:fs';
import {resolve,join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {tmpdir} from 'node:os';
import {composeCoupledPackage, readRegularTree, memberMap, digest, RECONCILIATION, CONTRACT} from './compose.mjs';
import {writeHeldPackage} from './write-held-package.mjs';
const root=resolve(process.env.BSRE_SOURCE_ROOT || fileURLToPath(new URL('../../../',import.meta.url)));
const pins=JSON.parse(readFileSync(new URL('./baseline-pins.json',import.meta.url),'utf8'));
const originals=readRegularTree(join(root,'tools/staging-lab/fixtures/bsre-enquiries'),Object.keys(pins.members));
const toEntries=map=>[...map].map(([path,bytes])=>({path,bytes:Buffer.from(bytes)}));
const originalEntries=toEntries(originals);
const beforeOriginal=Object.fromEntries([...originals].map(([p,b])=>[p,digest(b)]));
// Reserved synthetic fixture identity. It is never sent to a provider.
const oldDigits=originals.get('assets/lead.js').toString().match(/wa\\\.me\\\/([1-9][0-9]+)/)?.[1];
const oldDisplay=originals.get('templates/source/rent.html').toString().match(/<small>Speak with Black Swan<\/small>(\+[0-9 ]+)/)?.[1];
assert.ok(oldDigits && oldDisplay,'PUBLIC_BASELINE_CONTACT_PATTERN');
const id={from_digits:oldDigits,to_digits:'19995550123',from_display:oldDisplay,to_display:'+1 999 555 0123'};
const occurrence=(s,v)=>s.split(v).length-1;
function fixture() {
  const captured=new Map(toEntries(originals).map(r=>[r.path,r.bytes])), reviewed_counts={};
  for(const name of RECONCILIATION.slice(0,-1)) {
    const s=originals.get(name).toString('utf8');
    reviewed_counts[name]={matcher:name==='assets/lead.js'?1:0,whatsapp:name==='assets/lead.js'?0:occurrence(s,'https://wa.me/'+oldDigits),
      telephone:name==='assets/lead.js'?0:occurrence(s,'tel:+'+oldDigits),display:name==='assets/lead.js'?0:occurrence(s,oldDisplay)};
    captured.set(name,Buffer.from(s.replaceAll(oldDigits,id.to_digits).replaceAll(oldDisplay,id.to_display)));
  }
  const hubHash=digest(captured.get('templates/source/hub.html'));
  captured.set('includes/parent-isolation.php',Buffer.from(originals.get('includes/parent-isolation.php').toString()
    .replace(/const OWNED_HUB_SHA256 = '[a-f0-9]{64}';/,`const OWNED_HUB_SHA256 = '${hubHash}';`)));
  return {source_root:root,original:toEntries(originals),captured:toEntries(captured),identity:{...id},
    provenance:{original_zip_sha256:pins.original_zip_sha256,member_map_sha256:pins.member_map_sha256},
    receiver_original:readFileSync(join(root,'tools/staging-lab/fixtures/receiver-v2/Code.gs')),
    capture_binding:{review_ref:'SYNTHETIC_REVIEW_ONLY',members:Object.fromEntries([...captured].map(([p,b])=>[p,digest(b)])),reviewed_counts},
    native_binding:{expected_body_sha256:hubHash,captured_body_sha256:hubHash}};
}
function mutateCapture(f,name,update,repin=false) { const row=f.captured.find(r=>r.path===name); row.bytes=update(row.bytes);
  if(repin)f.capture_binding.members[name]=digest(row.bytes); }
test('all8 closure retains admission ancestry, rental omission, frame, separate fenced receiver and held status',async()=>{
  const f=fixture(),result=await composeCoupledPackage(f),sum=result.public_summary;
  assert.equal(sum.captured_unchanged,22);assert.equal(sum.captured_reconciled,8);assert.equal(sum.output_count,31);
  assert.equal(sum.required_output_count,62);assert.equal(sum.status,'PARTIAL_HELD');assert.equal(sum.deployment_prohibited,true);
  assert.equal(sum.complete_profile_certified,false);assert.equal(sum.provider_calls,0);assert.equal(sum.network_calls,0);
  assert.equal(sum.missing_selected_outputs.length,34);
  const client=result.files.get('plugin/assets/lead.js').toString();
  for(const token of ['X-BSRE-Admission','Admission proof unavailable','attemptAdmission','purposeAttributionEndpoint','hasPendingEnquiry','receipt'])assert.ok(client.includes(token));
  const rent=result.files.get('plugin/templates/source/rent.html').toString();
  assert.ok(rent.includes('Choose when you need to move')); assert.ok(!rent.includes('This preview form cannot send'));
  const rentProof=result.private_manifest.ancestry.find(r=>r.member==='templates/source/rent.html');
  assert.equal(rentProof.edit_counts.display,f.capture_binding.reviewed_counts['templates/source/rent.html'].display-1);
  assert.ok(result.private_manifest.ancestry.every(r=>r.reverse_verified));
  assert.equal(result.private_manifest.ancestry.length,8);assert.equal(result.private_manifest.unchanged_capture_members.length,22);
  const companion=result.files.get('companion/receiver/Code.gs').toString();
  assert.ok(companion.includes('closedNoCopyAssertRequest_'));assert.equal(occurrence(companion,'function closedNoCopyGate_('),1);
  assert.ok(result.files.get('plugin/assets/google-runtime.js').equals(originals.get('assets/google-runtime.js')));
  assert.ok(!result.files.get('plugin/assets/google-measurement.js').equals(originals.get('assets/google-measurement.js')));
  const publicText=JSON.stringify(sum);assert.ok(!publicText.includes(id.to_digits));assert.ok(!publicText.includes(root));
  assert.ok(!publicText.includes(f.capture_binding.members['assets/lead.js']));
  assert.ok(!publicText.includes(f.capture_binding.review_ref));
});
for(const name of RECONCILIATION)test('reject one-byte capture drift: '+name,async()=>{
  const f=fixture();mutateCapture(f,name,b=>Buffer.concat([b,Buffer.from('x')]));await assert.rejects(composeCoupledPackage(f),/CAPTURE_MEMBER_CHANGED/);
});
test('repinned unrelated template bytes and guard logic still fail reviewed transform',async()=>{
  for(const name of ['templates/source/off-plan.html','includes/parent-isolation.php']) {const f=fixture();
    mutateCapture(f,name,b=>Buffer.concat([b,Buffer.from('x')]),true);await assert.rejects(composeCoupledPackage(f),/CAPTURE_UNRELATED_CHANGE|CAPTURE_GUARD_CHANGED/);}
});
test('stale guard and stale native expectation fail pairing',async()=>{
  const f=fixture();mutateCapture(f,'includes/parent-isolation.php',()=>originals.get('includes/parent-isolation.php'),true);
  await assert.rejects(composeCoupledPackage(f),/CAPTURE_CLASSIFICATION_CHANGED/);
  const next=fixture();next.native_binding.expected_body_sha256=pins.members['templates/source/hub.html'];
  await assert.rejects(composeCoupledPackage(next),/NATIVE_HUB_EXPECTATION_CHANGED/);
});
test('reject original, zip/map/receiver pin drift, truncated target binding and wrong counts',async()=>{
  for(const mutate of [
    f=>f.original[0].bytes[0]^=1,
    f=>f.provenance.original_zip_sha256='0'.repeat(64),
    f=>f.provenance.member_map_sha256='0'.repeat(64),
    f=>f.receiver_original[0]^=1,
    f=>f.capture_binding.members['assets/lead.js']='a',
    f=>f.capture_binding.reviewed_counts['assets/lead.js'].matcher=0,
    f=>f.original_zip_bytes=Buffer.from('SYNTHETIC_WRONG_ZIP'),
  ]){const f=fixture();mutate(f);await assert.rejects(composeCoupledPackage(f),/ORIGINAL_MEMBER_CHANGED|PROVENANCE_CHANGED|RECEIVER_ORIGINAL_CHANGED|CAPTURE_MEMBER_CHANGED|CAPTURE_EDIT_COUNTS_CHANGED|ORIGINAL_ARCHIVE_CHANGED/);}
});
test('reject missing, duplicate, collision, traversal and31st member before derivation',async()=>{
  for(const mutate of [f=>f.captured.pop(),f=>f.captured.push(f.captured[0]),
    f=>f.captured.push({path:f.captured[0].path.toUpperCase(),bytes:Buffer.from('x')}),
    f=>f.captured[0].path='../escape',f=>f.captured.push({path:'additional.php',bytes:Buffer.from('x')})]){
    const f=fixture();mutate(f);await assert.rejects(composeCoupledPackage(f),/MEMBER_SET_MISMATCH|DUPLICATE_MEMBER|UNSAFE_MEMBER_PATH/);}
});
test('encoding/newline drift and contact count changes are rejected even with repinned capture',async()=>{
  for(const alter of [b=>Buffer.from(b.toString().replaceAll('\n','\r\n')),b=>Buffer.concat([b,Buffer.from([255])])]){
    const f=fixture();mutateCapture(f,'templates/source/off-plan.html',alter,true);await assert.rejects(composeCoupledPackage(f),/CAPTURE_UNRELATED_CHANGE|INVALID_UTF8/);}
});
test('full selected-output requirement is hard failure; supplied outputs cannot replace owned client',async()=>{
  const f=fixture();f.require_all_selected_outputs=true;await assert.rejects(composeCoupledPackage(f),/SELECTED_OUTPUTS_INCOMPLETE/);
  const next=fixture();next.selected_outputs=[{path:'plugin/assets/lead.js',bytes:Buffer.from('purpose-only')}];
  next.selected_output_pins={'plugin/assets/lead.js':digest(next.selected_outputs[0].bytes)};
  await assert.rejects(composeCoupledPackage(next),/SELECTED_OUTPUT_COLLISION/);
});
test('external inputs require independent pins, remain HELD and fake deployment flags do not grant release',async()=>{
  const f=fixture(),path='plugin/assets/wordpress.js',bytes=Buffer.from('SYNTHETIC_HELD_EXTERNAL_COMPONENT');
  f.selected_outputs=[{path,bytes}];f.selected_output_pins={[path]:digest(bytes)};
  f.deployment_prohibited=false;f.publication_authorized=true;f.ads_changes_authorized=true;
  const result=await composeCoupledPackage(f);assert.equal(result.public_summary.deployment_prohibited,true);
  assert.equal(result.public_summary.publication_authorized,false);assert.equal(result.public_summary.ads_changes_authorized,false);
  assert.equal(result.public_summary.complete_profile_certified,false);assert.ok(!result.public_summary.missing_selected_outputs.includes(path));
  f.selected_output_pins[path]='0'.repeat(64);await assert.rejects(composeCoupledPackage(f),/SELECTED_OUTPUT_PIN_CHANGED/);
});
test('all62 structural outputs still cannot certify full profile or close native/release holds',async()=>{
  const f=fixture(),base=await composeCoupledPackage(f);
  f.selected_outputs=base.public_summary.missing_selected_outputs.map(path=>({path,bytes:Buffer.from('SYNTHETIC_HELD_UNACCEPTED_COMPONENT:'+path)}));
  f.selected_output_pins=Object.fromEntries(f.selected_outputs.map(r=>[r.path,digest(r.bytes)]));f.require_all_selected_outputs=true;
  const result=await composeCoupledPackage(f);assert.equal(result.files.size,62);assert.equal(result.public_summary.status,'STRUCTURAL_HELD');
  assert.equal(result.public_summary.complete_profile_certified,false);assert.equal(result.public_summary.deployment_prohibited,true);
  assert.equal(result.private_manifest.native_binding.acceptance,'PENDING_NATIVE_ACCEPTANCE');
  assert.ok(result.public_summary.holds.includes('SIGNED_RECEIVER_PROVIDER_AND_IMPORT_ACCEPTANCE'));
  assert.throws(()=>result.public_summary.holds.pop(),TypeError);
  result.private_manifest.modules[Object.keys(pins.modules)[0]]='0'.repeat(64);
  assert.equal((await composeCoupledPackage(fixture())).public_summary.status,'PARTIAL_HELD');
});
test('selected module drift cannot substitute an unpinned generator',async()=>{
  const temp=mkdtempSync(join(tmpdir(),'bsre-coupled-modules-'));
  try {for(const name of Object.keys(pins.modules)){const path=join(temp,...name.split('/'));mkdirSync(dirname(path),{recursive:true});writeFileSync(path,readFileSync(join(root,name)));}
    const changed=Object.keys(pins.modules)[0];writeFileSync(join(temp,changed),'SYNTHETIC_MODULE_DRIFT');
    const f=fixture();f.source_root=temp;await assert.rejects(composeCoupledPackage(f),/SOURCE_MODULE_PIN_CHANGED/);
  }finally{rmSync(temp,{recursive:true});}
});
test('atomic private write enforces disjoint roots, hash consistency, no overwrite and held manifest',async()=>{
  const temp=mkdtempSync(join(tmpdir(),'bsre-coupled-synthetic-'));
  try { const a=join(temp,'a'),b=join(temp,'b');mkdirSync(a);mkdirSync(b);
    const result=await composeCoupledPackage(fixture());
    assert.throws(()=>writeHeldPackage(result,{destination:join(a,'bad'),visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]}),/OUTPUT_ROOT_OVERLAP/);
    assert.throws(()=>writeHeldPackage(result,{destination:join(temp,'public'),visibility:'PUBLIC',input_roots:[a,b]}),/PRIVATE_OUTPUT_REQUIRED/);
    const output=join(temp,'held');writeHeldPackage(result,{destination:output,visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]});
    const manifest=JSON.parse(readFileSync(join(output,'PRIVATE_MANIFEST.json'),'utf8'));assert.equal(manifest.classification,'PRIVATE_DO_NOT_PUBLISH');
    assert.equal(manifest.summary.deployment_prohibited,true);assert.equal(manifest.outputs.length,31);
    assert.throws(()=>writeHeldPackage(result,{destination:output,visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]}),/NEW_OUTPUT_DIRECTORY_REQUIRED/);
    result.files.get('plugin/assets/lead.js')[0]^=1;
    assert.throws(()=>writeHeldPackage(result,{destination:join(temp,'tampered'),visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]}),/OUTPUT_MANIFEST_CHANGED/);
    assert.deepEqual(readdirSync(temp).sort(),['a','b','held']);
  }finally{rmSync(temp,{recursive:true});}
});
test('regular tree rejects links/junctions and inputs remain byte-identical',()=>{
  const temp=mkdtempSync(join(tmpdir(),'bsre-coupled-link-'));try{const target=join(temp,'target');mkdirSync(target);writeFileSync(join(target,'file'),'synthetic');
    const linked=join(temp,'linked');symlinkSync(target,linked,process.platform==='win32'?'junction':'dir');
    assert.throws(()=>readRegularTree(temp),/INPUT_LINK_PROHIBITED/);
  }finally{rmSync(temp,{recursive:true});}
  const after=readRegularTree(join(root,'tools/staging-lab/fixtures/bsre-enquiries'),Object.keys(pins.members));
  assert.deepEqual(Object.fromEntries([...after].map(([p,b])=>[p,digest(b)])),beforeOriginal);
});
