import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,mkdtempSync,mkdirSync,writeFileSync,rmSync} from 'node:fs';
import {resolve,join,dirname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {tmpdir} from 'node:os';
import {composeCoupledPackageV2,CONTRACT_V2} from './compose-v2.mjs';
import {digest,readRegularTree,RECONCILIATION} from './compose.mjs';
import {writeHeldPackageV2} from './write-held-package-v2.mjs';
const root=resolve(process.env.BSRE_SOURCE_ROOT||fileURLToPath(new URL('../../../',import.meta.url)));
const g4root=resolve(process.env.BSRE_G4_SOURCE_ROOT||root);
const pins=JSON.parse(readFileSync(new URL('./baseline-pins.json',import.meta.url)));
const g3SourceRaw=readFileSync(new URL('./g3-source-pins-v2.json',import.meta.url));
const g4SourceRaw=readFileSync(new URL('./g4-source-pins-v2.json',import.meta.url));
const originals=readRegularTree(join(root,'tools/staging-lab/fixtures/bsre-enquiries'),Object.keys(pins.members));
const entries=map=>[...map].map(([path,bytes])=>({path,bytes:Buffer.from(bytes)}));
const g3=await import(pathToFileURL(join(root,'tools/website-tracking/tracking-system/build-g3-profile-candidate.mjs')).href);
const g4=await import(pathToFileURL(join(g4root,'tools/website-tracking/tracking-system/build-native-page-context-candidate.mjs')).href);
const frame=await import(pathToFileURL(join(g4root,'tools/website-tracking/tracking-system/build-native-frame-candidate.mjs')).href);
const parent=await import(pathToFileURL(join(root,'tools/website-tracking/tracking-system/build-frame-delivery-candidate.mjs')).href);
const selection=(profile,source,raw)=>({schema:'bsre-coupled-selection-receipt-v2',profile,source_manifest_sha256:digest(source),manifest_sha256:digest(raw),deployment_prohibited:true});
function fixture(withG4=true){
  const from=originals.get('assets/lead.js').toString().match(/wa\\\.me\\\/([1-9][0-9]+)/)[1];
  const display=originals.get('templates/source/rent.html').toString().match(/<small>Speak with Black Swan<\/small>(\+[0-9 ]+)/)[1];
  const identity={from_digits:from,to_digits:'19995550123',from_display:display,to_display:'+1 999 555 0123'};
  const captured=new Map(entries(originals).map(r=>[r.path,r.bytes])),reviewed_counts={};
  const count=(text,find)=>text.split(find).length-1;
  for(const path of RECONCILIATION.slice(0,-1)){const text=originals.get(path).toString();
    reviewed_counts[path]={matcher:path==='assets/lead.js'?1:0,whatsapp:path==='assets/lead.js'?0:count(text,'https://wa.me/'+from),
      telephone:path==='assets/lead.js'?0:count(text,'tel:+'+from),display:path==='assets/lead.js'?0:count(text,display)};
    captured.set(path,Buffer.from(text.replaceAll(from,identity.to_digits).replaceAll(display,identity.to_display)));}
  const hub=digest(captured.get('templates/source/hub.html'));
  captured.set('includes/parent-isolation.php',Buffer.from(originals.get('includes/parent-isolation.php').toString()
    .replace(/const OWNED_HUB_SHA256 = '[a-f0-9]{64}';/,`const OWNED_HUB_SHA256 = '${hub}';`)));
  const base=g3.buildG3ProfileCandidate(readFileSync(join(root,'docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json')));
  const raw=Buffer.from(JSON.stringify(base)),files=new Map(base.files.map(r=>['plugin/'+r.path,Buffer.from(r.content_base64,'base64')]));
  const input={source_root:root,original:entries(originals),captured:entries(captured),identity,
    provenance:{original_zip_sha256:pins.original_zip_sha256,member_map_sha256:pins.member_map_sha256},
    receiver_original:readFileSync(join(root,'tools/staging-lab/fixtures/receiver-v2/Code.gs')),
    capture_binding:{review_ref:'SYNTHETIC_V2_REVIEW_ONLY',members:Object.fromEntries([...captured].map(([p,b])=>[p,digest(b)])),reviewed_counts},
    native_binding:{expected_body_sha256:hub,captured_body_sha256:hub},g3_base_manifest_bytes:raw,
    g3_selection_receipt:selection('G3_ROUTE_CONTEXT_ADMISSION_CLIENT_ONLY',g3SourceRaw,raw)};
  if(withG4){
    const preimages={
      'plugin/assets/lead.js':files.get('plugin/assets/lead.js'),
      'plugin/includes/presentation.php':files.get('plugin/includes/presentation.php'),
      'plugin/assets/google-measurement.js':Buffer.from(parent.buildFrameDeliveryCandidate(originals.get('assets/google-measurement.js'))),
      'plugin/assets/google-runtime.js':originals.get('assets/google-runtime.js')};
    const output={
      'plugin/assets/lead.js':g4.buildNativePageContextClient(preimages['plugin/assets/lead.js'].toString(),digest(preimages['plugin/assets/lead.js'])).output,
      'plugin/includes/presentation.php':g4.buildNativePageContextPresentation(preimages['plugin/includes/presentation.php'].toString(),digest(preimages['plugin/includes/presentation.php'])).output,
      'plugin/assets/google-measurement.js':frame.buildNativeFrameParent(preimages['plugin/assets/google-measurement.js'].toString(),digest(preimages['plugin/assets/google-measurement.js'])).output,
      'plugin/assets/google-runtime.js':frame.buildNativeFrameChild(preimages['plugin/assets/google-runtime.js'].toString(),digest(preimages['plugin/assets/google-runtime.js'])).output,
      'plugin/includes/candidate/tracking/NativePageContext.php':readFileSync(join(g4root,'tools/website-tracking/tracking-system/native-page-context/NativePageContext.php')),
      'plugin/includes/g3-profile/bootstrap.php':files.get('plugin/includes/g3-profile/bootstrap.php').toString()
        .replace("require_once __DIR__.'/route-context.php';","require_once __DIR__.'/../candidate/tracking/NativePageContext.php';\nrequire_once __DIR__.'/route-context.php';")};
    const manifest={schema:'bsre-g4-composition-selection-v2',profile:'G4_NATIVE_CLIENT_PARENT_CHILD_V2',source_manifest_sha256:digest(g4SourceRaw),
      preimages:Object.fromEntries(Object.entries(preimages).map(([p,b])=>[p,digest(b)])),
      outputs:Object.fromEntries(Object.entries(output).map(([p,b])=>[p,digest(b)])),deployment_prohibited:true};
    input.g4_manifest_bytes=Buffer.from(JSON.stringify(manifest));input.g4_source_root=g4root;
    input.g4_selection_receipt=selection(manifest.profile,g4SourceRaw,input.g4_manifest_bytes);
  }
  return input;
}
function repinG3(input,manifest){input.g3_base_manifest_bytes=Buffer.from(JSON.stringify(manifest));input.g3_selection_receipt.manifest_sha256=digest(input.g3_base_manifest_bytes);}
function repinG4(input,manifest){input.g4_manifest_bytes=Buffer.from(JSON.stringify(manifest));input.g4_selection_receipt.manifest_sha256=digest(input.g4_manifest_bytes);}
function addSyntheticCommentReview(input){
  const path='includes/parent-isolation.php',row=input.captured.find(r=>r.path===path),before=originals.get(path).toString();
  const old='// Exact native serialization reviewed on 22 October. No normalization or CMS writes.';
  const template='// Exact native serialization reviewed on 11 November (phone number updated to +<CURRENT_CONTACT_DISPLAY_WITHOUT_PLUS>). No normalization or CMS writes.';
  const next=template.replace('<CURRENT_CONTACT_DISPLAY_WITHOUT_PLUS>',input.identity.to_display.slice(1));
  row.bytes=Buffer.from(row.bytes.toString().replace(old,next));input.capture_binding.members[path]=digest(row.bytes);
  const review={schema:'bsre-private-capture-comment-engineering-review-v1',original_guard_sha256:pins.members[path],original_comment:old+'\n',captured_comment_template:template+'\n',
    original_offset:64,original_length:Buffer.byteLength(old),captured_length:Buffer.byteLength(next),comment_delta:Buffer.byteLength(next)-Buffer.byteLength(old),
    original_capture_preserved:true,no_baseline_repin:true,no_normalization:true,engineering_exception_authorized:true,
    human_approval:false,native_acceptance:false,provider_acceptance:false,production_authorized:false,ads_authorized:false,complete_profile_certified:false};
  const authority={authority:'owner_confirmed_business_destination',canonical_destination_sha256:digest(input.identity.to_digits),permitted_channels:['telephone','WhatsApp']};
  const record=Buffer.from(JSON.stringify(review)),owner=Buffer.from(JSON.stringify(authority));
  input.capture_guard_comment_review={review_record_bytes:record,review_record_sha256:digest(record),review_ref:'SYNTHETIC_AI_ONLY_COMMENT_POLICY',
    owner_authority_record_bytes:owner,owner_authority_record_sha256:digest(owner),captured_comment_sha256:digest(next),captured_guard_sha256:digest(row.bytes)};
  return {row,review,next,old};
}
test('V2 actual layout count67 removes8 obsolete paths, adds11 actual layout files plus2 G5 helpers',()=>{
  assert.equal(CONTRACT_V2.required_outputs.length,67);assert.equal(new Set(CONTRACT_V2.required_outputs).size,67);
  for(const path of CONTRACT_V2.v1_paths_retired)assert.ok(!CONTRACT_V2.required_outputs.includes(path));
  for(const path of [...CONTRACT_V2.actual_layout_paths_added,...CONTRACT_V2.g5_helper_paths_added])assert.ok(CONTRACT_V2.required_outputs.includes(path));
  assert.equal(CONTRACT_V2.no_complete_profile_certificate,true);
});
test('raw G3 independently verifies41 files; absent G4 is explicitly held without claiming child compatibility',async()=>{
  const result=await composeCoupledPackageV2(fixture(false));
  assert.equal(result.public_summary.output_count,42);assert.equal(result.public_summary.g3_base_files_independently_verified,41);
  assert.equal(result.public_summary.g4_before_contact_verified,false);assert.equal(result.public_summary.status,'PARTIAL_HELD_G4_DERIVATION_REQUIRED');
  assert.ok(result.files.get('plugin/assets/google-runtime.js').equals(originals.get('assets/google-runtime.js')));
  assert.equal(result.public_summary.complete_profile_certified,false);
});
test('G4 bound derivations precede contact with reverse ancestry; G3 flags and all8 closure survive',async()=>{
  const input=fixture(),result=await composeCoupledPackageV2(input),summary=result.public_summary;
  assert.equal(summary.g4_before_contact_verified,true);assert.equal(summary.output_count,43);assert.equal(summary.required_output_count,67);
  assert.equal(summary.missing_selected_outputs.length,24);assert.equal(summary.captured_unchanged,22);assert.equal(summary.captured_reconciled,8);
  const lead=result.files.get('plugin/assets/lead.js').toString();
  for(const text of ['X-BSRE-Admission','Admission proof unavailable','BSRENativePageContext','hasPendingEnquiry'])assert.ok(lead.includes(text));
  const ancestry=result.private_manifest.ancestry.find(r=>r.member==='assets/lead.js');
  assert.ok(ancestry.order.indexOf('G4-native-context')<ancestry.order.indexOf('typed-contact-overlay-v1'));assert.equal(ancestry.reverse_verified,true);
  assert.ok(result.private_manifest.g4_composition.stages.every(r=>r.reverse_verified));assert.equal(result.private_manifest.g4_composition.stages.length,5);
  const wp=result.files.get('plugin/assets/wordpress.js').toString();assert.ok(wp.includes('retentionAdmissionRequired: true'));assert.ok(wp.includes('purposeAttributionEndpoint: purposeEndpoint'));
  assert.ok(result.files.get('plugin/includes/g3-profile/bootstrap.php').toString().includes('/candidate/tracking/NativePageContext.php'));
  assert.ok(result.files.get('plugin/assets/google-runtime.js').toString().includes('bsre-native-page-context-v2'));
  assert.ok(!result.files.get('plugin/assets/google-runtime.js').equals(originals.get('assets/google-runtime.js')));
  assert.ok(result.files.get('plugin/assets/google-measurement.js').toString().includes('context_contract'));
  assert.equal(summary.deployment_prohibited,true);assert.equal(summary.complete_profile_certified,false);
  const text=JSON.stringify(summary);assert.ok(!text.includes(input.identity.to_digits));assert.ok(!text.includes(root));assert.ok(!text.includes(input.capture_binding.review_ref));
});
test('V2 G4 intermediates and bootstrap equal actual G34 builder before contact overlay',async()=>{
  const {buildG34ProfileCandidate}=await import(pathToFileURL(join(root,'tools/website-tracking/tracking-system/build-g34-profile-candidate.mjs')).href);
  const expected=buildG34ProfileCandidate(readFileSync(join(root,'docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json')));
  const files=new Map(expected.files.map(r=>['plugin/'+r.path,Buffer.from(r.content_base64,'base64')])),result=await composeCoupledPackageV2(fixture());
  for(const path of ['plugin/includes/g3-profile/bootstrap.php','plugin/includes/presentation.php','plugin/assets/google-measurement.js',
    'plugin/assets/google-runtime.js','plugin/includes/candidate/tracking/NativePageContext.php'])assert.ok(result.files.get(path).equals(files.get(path)),path);
  const client=result.private_manifest.ancestry.find(r=>r.member==='assets/lead.js');assert.equal(client.precontact_sha256,digest(files.get('plugin/assets/lead.js')));
  assert.ok(client.order.indexOf('G4-native-context')<client.order.indexOf('typed-contact-overlay-v1'));
});
test('rehashed changed G3 client/store/main cannot pass independent derivation',async()=>{
  for(const path of ['assets/lead.js','includes/g2-profile/purpose-store.php','bsre-enquiries.php']){
    const f=fixture(false),m=JSON.parse(f.g3_base_manifest_bytes),row=m.files.find(r=>r.path===path);
    const bytes=Buffer.concat([Buffer.from(row.content_base64,'base64'),Buffer.from('SYNTHETIC_DRIFT')]);row.content_base64=bytes.toString('base64');row.sha256=digest(bytes);repinG3(f,m);
    await assert.rejects(composeCoupledPackageV2(f),/V2_G3_ANCESTRY_CHANGED/);}
});
test('G3 source hash/selection mismatch, missing/duplicate member and unheld flags fail',async()=>{
  for(const mutate of [f=>f.g3_selection_receipt.source_manifest_sha256='0'.repeat(64),f=>f.g3_selection_receipt.manifest_sha256='0'.repeat(64),
    f=>{const m=JSON.parse(f.g3_base_manifest_bytes);m.files.pop();repinG3(f,m);},
    f=>{const m=JSON.parse(f.g3_base_manifest_bytes);m.files.push(m.files[0]);repinG3(f,m);},
    f=>{const m=JSON.parse(f.g3_base_manifest_bytes);m.complete_coupled_profile=true;repinG3(f,m);}]){
    const f=fixture(false);mutate(f);await assert.rejects(composeCoupledPackageV2(f),/V2_SELECTION_RECEIPT_CHANGED|V2_G3_ANCESTRY_CHANGED|DUPLICATE_MEMBER|V2_G3_MANIFEST_FLAGS/);}
});
test('G4 wrong input/output/child/source selection cannot silently overwrite owned outputs',async()=>{
  for(const mutate of [m=>m.preimages['plugin/assets/lead.js']='0'.repeat(64),m=>m.outputs['plugin/assets/lead.js']='0'.repeat(64),
    m=>m.outputs['plugin/assets/google-runtime.js']=pins.members['assets/google-runtime.js'],m=>delete m.outputs['plugin/assets/google-runtime.js'],
    m=>m.source_manifest_sha256='0'.repeat(64)]){const f=fixture(),m=JSON.parse(f.g4_manifest_bytes);mutate(m);repinG4(f,m);
    await assert.rejects(composeCoupledPackageV2(f),/V2_G4_PREIMAGE_CHANGED|V2_G4_OUTPUT_CHANGED|V2_G4_OUTPUT_SET|V2_G4_MANIFEST_CHANGED/);}
  for(const path of ['plugin/assets/lead.js','plugin/includes/presentation.php','plugin/assets/google-measurement.js','plugin/assets/google-runtime.js']){
    const f=fixture(),bytes=Buffer.from('SYNTHETIC_UNREVIEWED_OVERRIDE');f.selected_outputs=[{path,bytes}];f.selected_output_pins={[path]:digest(bytes)};
    await assert.rejects(composeCoupledPackageV2(f),/V2_OWNED_PATH_OVERRIDE/);}
});
test('V2 retains exact eight-member capture gates and immutable original pins',async()=>{
  for(const name of RECONCILIATION){const f=fixture(),row=f.captured.find(r=>r.path===name);row.bytes=Buffer.concat([row.bytes,Buffer.from('x')]);
    await assert.rejects(composeCoupledPackageV2(f),/CAPTURE_MEMBER_CHANGED/);}
});
test('required G5/domain additions remain external hard dependencies, supplied placeholders never grant certificate',async()=>{
  const f=fixture(),partial=await composeCoupledPackageV2(f);f.require_all_selected_outputs=true;
  await assert.rejects(composeCoupledPackageV2(f),/V2_SELECTED_OUTPUTS_INCOMPLETE/);
  f.selected_outputs=partial.public_summary.missing_selected_outputs.map(path=>({path,bytes:Buffer.from('SYNTHETIC_HELD_ONLY:'+path)}));
  f.selected_output_pins=Object.fromEntries(f.selected_outputs.map(r=>[r.path,digest(r.bytes)]));
  const result=await composeCoupledPackageV2(f);assert.equal(result.files.size,67);assert.equal(result.public_summary.status,'STRUCTURAL_HELD');
  assert.equal(result.public_summary.complete_profile_certified,false);assert.ok(result.public_summary.holds.includes('G5_OPERATIONAL_AUTHORITY_AND_CUSTODY_UNIMPLEMENTED'));
});
test('G4 builder source drift rejects independent selection before composition',async()=>{
  const temp=mkdtempSync(join(tmpdir(),'bsre-v2-g4-source-'));
  try{const manifest=JSON.parse(g4SourceRaw);for(const name of Object.keys(manifest.modules)){const dest=join(temp,name);mkdirSync(dirname(dest),{recursive:true});writeFileSync(dest,readFileSync(join(g4root,name)));}
    writeFileSync(join(temp,Object.keys(manifest.modules)[0]),'SYNTHETIC_MODULE_DRIFT');const f=fixture();f.g4_source_root=temp;
    await assert.rejects(composeCoupledPackageV2(f),/V2_SOURCE_PIN_CHANGED/);
  }finally{rmSync(temp,{recursive:true});}
});
test('V2 atomic writer accepts actual layout only as a private held V2 package',async()=>{
  const temp=mkdtempSync(join(tmpdir(),'bsre-v2-private-output-'));
  try{const a=join(temp,'a'),b=join(temp,'b');mkdirSync(a);mkdirSync(b);const result=await composeCoupledPackageV2(fixture());
    const output=join(temp,'held');writeHeldPackageV2(result,{destination:output,visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]});
    const manifest=JSON.parse(readFileSync(join(output,'PRIVATE_MANIFEST.json')));
    assert.equal(manifest.schema,'bsre-coupled-private-manifest-v2');assert.equal(manifest.summary.complete_profile_certified,false);
    assert.ok(readFileSync(join(output,'plugin/includes/g2-profile/shared-repository.php')).length>0);
    assert.throws(()=>writeHeldPackageV2(result,{destination:join(a,'overlap'),visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]}),/OUTPUT_ROOT_OVERLAP/);
    assert.throws(()=>writeHeldPackageV2({...result,private_manifest:{...result.private_manifest,schema:'bsre-coupled-private-manifest-v1'}},
      {destination:join(temp,'wrong'),visibility:'PRIVATE_OFFLINE_ONLY',input_roots:[a,b]}),/HELD_RESULT_REQUIRED/);
  }finally{rmSync(temp,{recursive:true});}
});
test('explicit reviewed capture-only comment view preserves all actual hashes and emits original comment',async()=>{
  const f=fixture(),{row,old}=addSyntheticCommentReview(f),raw=Buffer.from(row.bytes),result=await composeCoupledPackageV2(f);
  const proof=result.private_manifest.capture_guard_compatibility;
  assert.equal(proof.actual_raw_members.length,30);assert.equal(proof.capture_transform_spans.length,2);
  assert.equal(proof.actual_guard_sha256,digest(raw));assert.equal(proof.actual_capture_rewritten,false);assert.equal(proof.normalization_performed,false);
  assert.equal(proof.actual_raw_bytes-proof.compatibility_view_bytes,proof.comment_delta_bytes);assert.ok(row.bytes.equals(raw));
  const final=result.files.get('plugin/includes/parent-isolation.php').toString();assert.ok(final.includes(old));assert.ok(!final.includes('phone number updated'));
  const expected=originals.get('includes/parent-isolation.php').toString().replace(pins.members['templates/source/hub.html'],f.native_binding.expected_body_sha256);
  assert.equal(final,expected);assert.equal(result.public_summary.capture_guard_review_policy,'EXPLICIT_CAPTURE_ONLY_COMMENT_VIEW');
  const g=result.private_manifest.ancestry.find(r=>r.member==='includes/parent-isolation.php');assert.equal(g.captured_sha256,digest(raw));assert.equal(g.edit_counts.hub_binding,1);
});
test('strict V1 and unselected V2 still reject the same comment capture',async()=>{
  const f=fixture();addSyntheticCommentReview(f);delete f.capture_guard_comment_review;
  await assert.rejects(composeCoupledPackageV2(f),/CAPTURE_GUARD_CHANGED/);
});
for(const [name,mutate]of [
  ['other-comment',s=>s.replace('reviewed on 11 November','reviewed on 12 November')],
  ['php-close-tag',s=>s.replace('No normalization','?> No normalization')],
  ['wrong-target-digits',s=>s.replace('phone number updated to +1 999 555 0123','phone number updated to +1 999 555 0124')],
  ['same-digits-different-spacing',s=>s.replace('phone number updated to +1 999 555 0123','phone number updated to +19 995 550 123')],
  ['new-line',s=>s.replace('(phone number updated','\n(phone number updated')],
  ['nul-control-byte',s=>s.replace('(phone number updated','\x00(phone number updated')],
  ['unrelated-guard',s=>s+'\n// SYNTHETIC UNREVIEWED EXTRA COMMENT\n'],
])test('reviewed comment policy rejects '+name+' even when raw guard hash is rebound',async()=>{
  const f=fixture(),{row}=addSyntheticCommentReview(f);row.bytes=Buffer.from(mutate(row.bytes.toString()));
  f.capture_binding.members['includes/parent-isolation.php']=digest(row.bytes);f.capture_guard_comment_review.captured_guard_sha256=digest(row.bytes);
  await assert.rejects(composeCoupledPackageV2(f),/V2_CAPTURE_GUARD_UNRELATED_CHANGE/);
});
test('unreviewed or altered review/owner bindings cannot activate comment exception',async()=>{
  for(const mutate of [f=>f.capture_guard_comment_review.review_record_sha256='0'.repeat(64),
    f=>{const p=f.capture_guard_comment_review,r=JSON.parse(p.review_record_bytes);r.engineering_exception_authorized=false;p.review_record_bytes=Buffer.from(JSON.stringify(r));p.review_record_sha256=digest(p.review_record_bytes);},
    f=>{const p=f.capture_guard_comment_review,a=JSON.parse(p.owner_authority_record_bytes);a.canonical_destination_sha256='0'.repeat(64);p.owner_authority_record_bytes=Buffer.from(JSON.stringify(a));p.owner_authority_record_sha256=digest(p.owner_authority_record_bytes);}]){
    const f=fixture();addSyntheticCommentReview(f);mutate(f);await assert.rejects(composeCoupledPackageV2(f),/V2_CAPTURE_REVIEW_HASH|V2_CAPTURE_REVIEW_UNAUTHORIZED|V2_CAPTURE_COMMENT_AUTHORITY/);}
});
