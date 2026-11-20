import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import {buildPreferenceRuntimeLabPacket,FIXED_PREFERENCE_RUNTIME_ROOT,PREFERENCE_RUNTIME_PATHS,planPreferenceRuntimeLab,preferenceRuntimeLabBytes,writeFixedPreferenceRuntimeLab} from './build-preference-runtime-lab.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
function refresh(packet){packet.files.set('G37_BUILD.json',Buffer.from(JSON.stringify(packet.manifest,null,2)+'\n'));return packet;}
test('actual pure builder produces the complete closed9-file fixed preference plan',()=>{
 const packet=buildPreferenceRuntimeLabPacket(),plan=planPreferenceRuntimeLab(packet);
 assert.equal(plan.target,'/opt/lab/g37-pref');assert.equal(FIXED_PREFERENCE_RUNTIME_ROOT,plan.target);
 assert.equal(plan.files.length,9);assert.deepEqual(plan.files.map(row=>row.path),PREFERENCE_RUNTIME_PATHS);
 for(const row of plan.files){const bytes=preferenceRuntimeLabBytes(plan,row.path);assert.ok(bytes.equals(packet.files.get(row.path)));assert.equal(sha(bytes),row.sha256);assert.equal(bytes.length,row.bytes);}
 assert.equal(plan.provider_accepted,false);assert.equal(plan.production_authorized,false);
});
test('closed fileset rejects missing, extra, traversal, absolute, siblingG36 and Windows paths',()=>{
 for(const path of [null,'extra.php','../g36/wp-content/db.php','/opt/lab/g36/wp-content/db.php','runtime\\control.gs','runtime/../control.gs']){
  const packet=buildPreferenceRuntimeLabPacket();packet.files.delete('runtime/ActualPreferenceRetention.php');
  if(path!==null)packet.files.set(path,Buffer.from('unreviewed'));
  assert.throws(()=>planPreferenceRuntimeLab(packet),/PREFERENCE_LAB_FILESET_CHANGED/);
 }
});
test('content, byte lengths, manifest members and schema must match exact closed bindings',()=>{
 for(const change of [
  packet=>{packet.files.get('runtime/ActualPreferenceRetention.php')[0]^=1;},
  packet=>{packet.files.set('runtime/ActualPreferenceRetention.php','not-a-buffer');},
  packet=>{packet.manifest.files['runtime/ActualPreferenceRetention.php'].bytes++;refresh(packet);},
  packet=>{packet.manifest.files['runtime/ActualPreferenceRetention.php'].sha256='0'.repeat(64);refresh(packet);},
  packet=>{packet.manifest.files['runtime/ActualPreferenceRetention.php'].unknown=true;refresh(packet);},
  packet=>{packet.manifest.profile='unreviewed';refresh(packet);},
  packet=>{packet.manifest.files['unknown.php']={sha256:'0'.repeat(64),bytes:1};refresh(packet);},
 ]){const packet=buildPreferenceRuntimeLabPacket();change(packet);assert.throws(()=>planPreferenceRuntimeLab(packet),/PREFERENCE_LAB_/);}
});
test('duplicate-key and alternate raw manifest encodings never become an accepted plan',()=>{
 for(const change of [raw=>raw.replace('"schema":','"schema": "discarded",\n  "schema":'),raw=>raw.trim(),raw=>raw+'\n']){
  const packet=buildPreferenceRuntimeLabPacket();packet.files.set('G37_BUILD.json',Buffer.from(change(packet.files.get('G37_BUILD.json').toString())));
  assert.throws(()=>planPreferenceRuntimeLab(packet),/PREFERENCE_LAB_NONCANONICAL_OR_DUPLICATE_MANIFEST/);
 }
});
test('post-plan genuine buffer and rehashed metadata mutation cannot change detached plan bytes',()=>{
 const packet=buildPreferenceRuntimeLabPacket(),plan=planPreferenceRuntimeLab(packet),path='runtime/ActualPreferenceRetention.php';
 const original=preferenceRuntimeLabBytes(plan,path),originalHash=plan.files.find(row=>row.path===path).sha256;
 packet.files.set(path,Buffer.from('in-place rehash mutation'));
 packet.manifest.files[path]={sha256:sha(packet.files.get(path)),bytes:packet.files.get(path).length};refresh(packet);
 packet.manifest.profile='changed-after-plan';packet.production_authorized=true;
 assert.ok(preferenceRuntimeLabBytes(plan,path).equals(original));assert.equal(plan.files.find(row=>row.path===path).sha256,originalHash);
 assert.equal(plan.production_authorized,false);assert.equal(plan.profile,'G37_ACTUAL_PREFERENCE_ENGINEERING_ONLY');
});
test('returned buffers and frozen descriptors cannot mutate the private write snapshot',()=>{
 const plan=planPreferenceRuntimeLab(buildPreferenceRuntimeLabPacket()),path='runtime/ActualPreferenceRetention.php',bytes=preferenceRuntimeLabBytes(plan,path),hash=sha(bytes);
 bytes[0]^=1;assert.equal(sha(preferenceRuntimeLabBytes(plan,path)),hash);
 assert.throws(()=>{plan.target='/opt/lab/g36';},TypeError);
 assert.throws(()=>{plan.files[0].path='../g36';},TypeError);
 assert.throws(()=>{plan.files.push({path:'evil'});},TypeError);
 assert.throws(()=>preferenceRuntimeLabBytes({...plan},path),/PREFERENCE_LAB_PLAN_INVALID/);
});
test('production flags, foreign packet keys and caller-supplied write plans are rejected',()=>{
 for(const change of [packet=>{packet.synthetic_only=false;},packet=>{packet.provider_accepted=true;},packet=>{packet.production_authorized=true;},packet=>{packet.target='/opt/lab/g36';}]){
  const packet=buildPreferenceRuntimeLabPacket();change(packet);assert.throws(()=>planPreferenceRuntimeLab(packet),/PREFERENCE_LAB_/);
 }
 // Argument rejection precedes platform/root/filesystem checks: no path override
 // or untrusted externally supplied map can reach the fixed filesystem writer.
 assert.throws(()=>writeFixedPreferenceRuntimeLab({target:'/opt/lab/g36'}),/PREFERENCE_LAB_NO_ARGUMENTS/);
 assert.throws(()=>writeFixedPreferenceRuntimeLab(planPreferenceRuntimeLab(buildPreferenceRuntimeLabPacket())),/PREFERENCE_LAB_NO_ARGUMENTS/);
});
