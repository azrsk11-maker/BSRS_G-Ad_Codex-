import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,mkdirSync,readdirSync,rmSync,lstatSync} from 'node:fs';
import {join,dirname,resolve,basename} from 'node:path';
import {tmpdir} from 'node:os';
import {composeCoupledCanonicalLeaseV3,assertHeldCandidateV3,assertWriterDestinationV3,prepareHeldWriteV3,CONTRACT_V3,digest} from './compose-v3.mjs';
import {writeHeldCanonicalV3} from './write-held-v3.mjs';
import {syntheticInput,SOURCE_ROOT} from './synthetic-input.mjs';
const pins=JSON.parse(readFileSync(new URL('./source-pins-v3.json',import.meta.url)));
const make=async(root=SOURCE_ROOT)=>composeCoupledCanonicalLeaseV3(await syntheticInput({source_root:root}));
function temporary(){return mkdtempSync(join(tmpdir(),'g36-hardening-'));}
function cleanup(path){assert.equal(dirname(resolve(path)),resolve(tmpdir()));assert.ok(basename(path).startsWith('g36-hardening-'));assert.ok(lstatSync(path).isDirectory()&&!lstatSync(path).isSymbolicLink());rmSync(path,{recursive:true});}
function options(result,temp){
  const a=join(temp,'input-a'),b=join(temp,'input-b');mkdirSync(a);mkdirSync(b);
  const {source_manifest_members,...bindings}=result.private_manifest.bindings;
  return {destination:join(temp,'held'),input_roots:[a,b],visibility:'PRIVATE_OFFLINE_ONLY',selection_binding:{...bindings,
    review_ref:'SYNTHETIC_HARDENING_SELECTION_ONLY',diagnostic_only:true,deployment_prohibited:true,full_profile_complete:false}};
}
function rehash(result,path,addition='\n// SYNTHETIC REHASHED MUTATION ONLY\n'){
  result.files.set(path,Buffer.concat([result.files.get(path),Buffer.from(addition)]));
  const row=result.private_manifest.outputs.find(r=>r.path===path);row.bytes=result.files.get(path).length;row.sha256=digest(result.files.get(path));
  if(path===CONTRACT_V3.receiver_path)result.private_manifest.receiver_sha256=row.sha256;
  if(path===CONTRACT_V3.dropin_path)result.private_manifest.bindings.dropin_sha256=row.sha256;
}
function copiedSources(temp){
  const root=join(temp,'source');mkdirSync(root);assert.equal(Object.keys(pins.files).length,97);
  const paths=[...Object.keys(pins.files),'tools/staging-lab/fixtures/receiver-v2/Code.gs'];
  for(const path of paths){const dest=join(root,path);mkdirSync(dirname(dest),{recursive:true});writeFileSync(dest,readFileSync(join(SOURCE_ROOT,path)));}
  return root;
}
test('writer hardening preserves the already prepared synthetic G36 native M/P/dropin receipt',async()=>{
  const result=await make(),b=result.private_manifest.bindings;
  assert.equal(b.M,'5d8107cb2abc02c493b68290816368d57efae0d30d5d65693660c3c8b504db71');
  assert.equal(b.P,'9b6880972fc094ab0b3f7b10d2eea2d4109e1b13ec9c815299a14064fa41e40c');
  assert.equal(b.dropin_sha256,'7223236ea357446287ea7362b91a4d82dfa69490488a1e165ba6e6557960d6de');
  assert.equal(result.files.size,68);assert.equal(b.source_manifest_members,64);
});
test('genuine rehashed receiver counterexample is rejected by both validators and writer before output mutation',async()=>{
  const result=await make(),temp=temporary();
  try{
    const opt=options(result,temp),bindings={...result.private_manifest.bindings};rehash(result,CONTRACT_V3.receiver_path);
    assert.deepEqual(result.private_manifest.bindings,bindings);assert.equal(result.public_summary.receiver_bytes_preserved,true);
    assert.throws(()=>assertHeldCandidateV3(result),/V3_COMPOSE_RESULT_MUTATED/);
    assert.throws(()=>assertWriterDestinationV3(result,opt.destination),/V3_COMPOSE_RESULT_MUTATED/);
    assert.throws(()=>writeHeldCanonicalV3(result,opt),/V3_COMPOSE_RESULT_MUTATED/);
    assert.deepEqual(readdirSync(temp).sort(),['input-a','input-b']);
  }finally{cleanup(temp);}
});
test('coherently rehashed dropin cannot replace the composed output even with refreshed selection',async()=>{
  const result=await make(),temp=temporary();
  try{
    rehash(result,CONTRACT_V3.dropin_path);const opt=options(result,temp);
    assert.throws(()=>assertHeldCandidateV3(result),/V3_COMPOSE_RESULT_MUTATED/);
    assert.throws(()=>writeHeldCanonicalV3(result,opt),/V3_COMPOSE_RESULT_MUTATED/);
    assert.deepEqual(readdirSync(temp).sort(),['input-a','input-b']);
  }finally{cleanup(temp);}
});
test('nested private proof and source-pin metadata cannot be self-certified after composition',async()=>{
  for(const mutate of [r=>r.private_manifest.v2_private_manifest.ancestry[0].reverse_verified=false,
    r=>r.private_manifest.source_files[Object.keys(pins.files).at(-1)]='0'.repeat(64),
    r=>r.private_manifest.outputs.reverse()]){
    const result=await make();mutate(result);assert.throws(()=>assertHeldCandidateV3(result),/V3_COMPOSE_RESULT_MUTATED/);
  }
});
test('public metadata replacement retaining held flags is bound to its original digest',async()=>{
  const result=await make();result.public_summary={...result.public_summary,network_calls:1};
  assert.throws(()=>assertHeldCandidateV3(result),/V3_COMPOSE_RESULT_MUTATED/);
});
test('metadata getters and toJSON are rejected without executing their callbacks',async()=>{
  const result=await make(),hash=result.private_manifest.receiver_sha256;let calls=0;
  Object.defineProperty(result.private_manifest,'receiver_sha256',{enumerable:true,configurable:true,get(){calls++;return hash;}});
  assert.throws(()=>assertHeldCandidateV3(result),/V3_METADATA_DATA_REQUIRED/);assert.equal(calls,0);
  delete result.private_manifest.receiver_sha256;result.private_manifest.receiver_sha256=hash;
  result.private_manifest.toJSON=()=>{calls++;return {};};
  assert.throws(()=>assertHeldCandidateV3(result),/V3_METADATA_VALUE/);assert.equal(calls,0);
});
test('genuine file map membership and iteration provenance cannot be substituted',async()=>{
  const result=await make(),bytes=result.files.get(CONTRACT_V3.receiver_path);
  result.files.delete(CONTRACT_V3.receiver_path);result.files.set(CONTRACT_V3.receiver_path,bytes);
  assert.throws(()=>assertHeldCandidateV3(result),/V3_COMPOSE_RESULT_MUTATED/);
  const second=await make();second.files[Symbol.iterator]=function*(){yield* Map.prototype.entries.call(this);};
  assert.throws(()=>assertHeldCandidateV3(second),/V3_RESULT_MAP_REQUIRED/);
});
test('late rehashed result mutation through writer options is rechecked before creating temporary output',async()=>{
  const result=await make(),temp=temporary();
  try{
    const opt=options(result,temp),roots=opt.input_roots;let changed=false;
    Object.defineProperty(opt,'input_roots',{get(){if(!changed){changed=true;rehash(result,CONTRACT_V3.receiver_path);}return roots;}});
    assert.throws(()=>writeHeldCanonicalV3(result,opt),/V3_COMPOSE_RESULT_MUTATED/);
    assert.equal(changed,true);assert.deepEqual(readdirSync(temp).sort(),['input-a','input-b']);
  }finally{cleanup(temp);}
});
test('post-compose drift of the last of all97 source pins rejects before any writer output',async()=>{
  const temp=temporary();
  try{
    const root=copiedSources(temp),result=await make(root),out=join(temp,'output');mkdirSync(out);
    const opt=options(result,out),last=Object.keys(pins.files).at(-1);writeFileSync(join(root,last),'SYNTHETIC_SOURCE_DRIFT');
    assert.equal(assertHeldCandidateV3(result),true);
    assert.throws(()=>assertWriterDestinationV3(result,opt.destination),/V3_SOURCE_PIN_CHANGED/);
    assert.throws(()=>writeHeldCanonicalV3(result,opt),/V3_SOURCE_PIN_CHANGED/);
    assert.deepEqual(readdirSync(out).sort(),['input-a','input-b']);
  }finally{cleanup(temp);}
});
test('source drift after destination validation is rechecked immediately before first output mutation',async()=>{
  const temp=temporary();
  try{
    const root=copiedSources(temp),result=await make(root),out=join(temp,'output');mkdirSync(out);
    const opt=options(result,out),roots=opt.input_roots,last=Object.keys(pins.files).at(-1);let changed=false;
    Object.defineProperty(opt,'input_roots',{get(){if(!changed){changed=true;writeFileSync(join(root,last),'SYNTHETIC_LATE_SOURCE_DRIFT');}return roots;}});
    assert.throws(()=>writeHeldCanonicalV3(result,opt),/V3_SOURCE_PIN_CHANGED/);
    assert.equal(changed,true);assert.deepEqual(readdirSync(out).sort(),['input-a','input-b']);
  }finally{cleanup(temp);}
});
test('authorized write plans detach file buffers and original metadata from subsequent caller mutation',async()=>{
  const result=await make(),temp=temporary();
  try{
    const before=digest(result.files.get(CONTRACT_V3.receiver_path)),plan=prepareHeldWriteV3(result,join(temp,'held'));
    assert.equal(plan.files.size,68);rehash(result,CONTRACT_V3.receiver_path);
    result.private_manifest.v2_private_manifest.ancestry[0].reverse_verified=false;result.public_summary={...result.public_summary,network_calls:1};
    assert.equal(digest(plan.files.get(CONTRACT_V3.receiver_path)),before);
    assert.equal(plan.private_manifest.receiver_sha256,before);assert.equal(plan.public_summary.network_calls,0);
    assert.equal(plan.private_manifest.v2_private_manifest.ancestry[0].reverse_verified,true);
    assert.deepEqual(readdirSync(temp),[]);
  }finally{cleanup(temp);}
});
