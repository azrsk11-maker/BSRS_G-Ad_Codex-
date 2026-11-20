import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdtempSync,mkdirSync,copyFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,dirname} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {currentInputProfile} from '../current-input-context.mjs';
import {build,buildCurrent,here,sha} from '../build-private.mjs';
import {writeFixedCurrentLocalHistoryRuntimeLab} from '../../../staging-lab/build-local-history-runtime-lab.mjs';

const source=fileURLToPath(new URL('../../../../',import.meta.url));
const queue='tools/qualified-export-source/source_queue.py';
const descriptor=JSON.parse(readFileSync(join(here,'CURRENT_INPUT_CONTEXT.json'),'utf8'));
const frozen=JSON.parse(readFileSync(join(here,'SOURCE_PINS.json'),'utf8'));
const mapRaw=readFileSync(join(here,'MATERIALIZER_INPUT_MAP.json'));
const pin=bytes=>({bytes:bytes.length,sha256:sha(bytes)});
const fix=`            # Fresh reviewed evidence can shorten an existing deadline into the
            # past. Erase that reservation now, before it could be rewritten as
            # a HELD row retaining an already-expired person/GCLID payload.
            expired.update(person for person, item in evaluated["candidates"].items()
                           if person in existing and when(item["retire_at"]) <= now)
`;
function temporary(run){
 const root=mkdtempSync(join(tmpdir(),'bsre-current-input-context-'));
 try{return run(root);}finally{rmSync(root,{recursive:true,force:true});}
}
async function descriptorFixture(mutate){
 const root=mkdtempSync(join(tmpdir(),'bsre-current-input-descriptor-'));
 try{
  for(const name of ['current-input-context.mjs','CURRENT_INPUT_CONTEXT.json','SOURCE_PINS.json','MATERIALIZER_INPUT_MAP.json'])copyFileSync(join(here,name),join(root,name));
  mutate(root);
  const module=await import(pathToFileURL(join(root,'current-input-context.mjs')).href);
  assert.throws(()=>module.currentInputProfile(),/G39_CONTEXT_/);
 }finally{rmSync(root,{recursive:true,force:true});}
}

test('current context changes exactly one reviewed input and grants no authority',()=>{
 const profile=currentInputProfile();
 assert.equal(Object.keys(profile.pins.files).length,26);
 assert.deepEqual(Object.keys(profile.pins.files).filter(path=>JSON.stringify(profile.pins.files[path])!==JSON.stringify(frozen.files[path])),[queue]);
 assert.deepEqual(profile.pins.files[queue],descriptor.change.after);
 assert.equal(profile.inputMap.files[queue].role,'REVIEW_CONTEXT_STILL_PIN_REQUIRED');
 assert.equal(profile.receipt.unchanged_input_count,25);
 assert.equal(profile.receipt.native_operational_behavior_changed,false);
 for(const key of ['current_head_native_accepted','production_authorized','export_authorized','provider_accepted','business_evidence_accepted','release_authorized'])assert.equal(profile.receipt[key],false);
 assert.equal(profile.receipt.descriptor_sha256,sha(readFileSync(join(here,'CURRENT_INPUT_CONTEXT.json'))));
});

test('historical pin and map bytes remain exact',()=>{
 assert.equal(sha(readFileSync(join(here,'SOURCE_PINS.json'))),descriptor.base.source_pins_sha256);
 assert.equal(sha(mapRaw),descriptor.base.input_map_sha256);
});

test('current builder and exact frozen profile produce identical25-file runtime bytes',()=>temporary(root=>{
 for(const path of Object.keys(frozen.files)){
  const target=join(root,path);mkdirSync(dirname(target),{recursive:true});copyFileSync(join(source,path),target);
 }
 const currentBytes=readFileSync(join(root,queue));assert.deepEqual(pin(currentBytes),descriptor.change.after);
 const oldText=currentBytes.toString('utf8').replace(fix,'');
 assert.notEqual(oldText,currentBytes.toString('utf8'));assert.deepEqual(pin(Buffer.from(oldText)),descriptor.change.before);
 writeFileSync(join(root,queue),oldText);
 const historical=build(root),current=buildCurrent(source);
 assert.equal(historical.files.size,25);assert.equal(current.files.size,25);
 assert.equal(current.manifest.expected_checks.length,43);
 for(const [path,bytes] of historical.files)assert.deepEqual(current.files.get(path),bytes,path);
 assert.equal(sha(current.files.get('G39_BUILD.json')),descriptor.invariants.native_manifest_sha256);
 assert.throws(()=>buildCurrent(root),/G39_SOURCE_PIN_CHANGED/);
 assert.throws(()=>build(source),/G39_SOURCE_PIN_CHANGED/);
}));

test('a changed unchanged-input fails current compilation before native preparation',()=>temporary(root=>{
 for(const path of Object.keys(frozen.files)){
  const target=join(root,path);mkdirSync(dirname(target),{recursive:true});copyFileSync(join(source,path),target);
 }
 const path=Object.keys(frozen.files).find(value=>value!==queue),target=join(root,path),bytes=readFileSync(target);
 bytes[0]^=1;writeFileSync(target,bytes);
 assert.throws(()=>buildCurrent(root),/G39_SOURCE_PIN_CHANGED/);
}));

test('descriptor rejects extra fields, alternate pins, scope changes and authority booleans',async()=>{
 for(const mutate of [value=>value.extra=true,value=>value.change.after.sha256='0'.repeat(64),
  value=>value.change.path='tools/other.py',value=>value.change.role='BUILD_REQUIRED',
  value=>value.authority.production_authorized=true,value=>value.base.input_count=25,
  value=>value.invariants.native_case_count=42])await descriptorFixture(root=>{
   const value=structuredClone(descriptor);mutate(value);writeFileSync(join(root,'CURRENT_INPUT_CONTEXT.json'),JSON.stringify(value));
  });
});

test('a historical base pin or map edit cannot be hidden by the current context',async()=>{
 for(const name of ['SOURCE_PINS.json','MATERIALIZER_INPUT_MAP.json'])await descriptorFixture(root=>{
  writeFileSync(join(root,name),Buffer.concat([readFileSync(join(root,name)),Buffer.from('\n')]));
 });
});

test('trusted current profile has no caller supplied override and returns frozen values',()=>{
 assert.throws(()=>currentInputProfile({path:'untrusted.json'}),/G39_CONTEXT_NO_ARGUMENTS/);
 const profile=currentInputProfile();assert.ok(Object.isFrozen(profile));assert.ok(Object.isFrozen(profile.pins.files[queue]));
 assert.throws(()=>{profile.pins.files[queue].bytes=1;},TypeError);
 assert.throws(()=>buildCurrent(source,{}),/G39_CURRENT_EXACT_SOURCE_ROOT_REQUIRED/);
});

test('explicit current writer rejects arguments before any filesystem operation',()=>{
 assert.equal(writeFixedCurrentLocalHistoryRuntimeLab.length,0);
 assert.throws(()=>writeFixedCurrentLocalHistoryRuntimeLab({}),/G39_LAB_NO_ARGUMENTS/);
});

test('unknown CLI context fails before entering the fixed Linux writer',()=>{
 const writer=fileURLToPath(new URL('../../../staging-lab/build-local-history-runtime-lab.mjs',import.meta.url));
 assert.throws(()=>execFileSync(process.execPath,[writer,'--input-context=unreviewed'],{stdio:'pipe'}),
  error=>error.status!==0&&error.stderr.toString().includes('G39_LAB_EXPLICIT_INPUT_CONTEXT_REQUIRED'));
});

test('Docker and host preflight explicitly select the current input context',()=>{
 const docker=readFileSync(join(source,'tools/staging-lab/Dockerfile'),'utf8');
 const workflow=readFileSync(join(source,'.github/workflows/isolated-wordpress-lab.yml'),'utf8');
 assert.equal(docker.split('build-local-history-runtime-lab.mjs --input-context=retention-expiry-v1').length-1,1);
 assert.ok(workflow.includes('tools/website-tracking/g5-local-history-runtime/tests/current-input-context.test.mjs'));
});
