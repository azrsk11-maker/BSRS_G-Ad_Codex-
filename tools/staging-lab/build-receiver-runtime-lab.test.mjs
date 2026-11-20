import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import test from 'node:test';
import {buildReceiverRuntimeNativeLab} from '../website-tracking/g5-receiver-runtime/build-native-lab.mjs';
import {FIXED_RECEIVER_RUNTIME_ROOT,RECEIVER_RUNTIME_PATHS,planReceiverRuntimeLab,receiverRuntimeLabBytes,writeFixedReceiverRuntimeLab} from './build-receiver-runtime-lab.mjs';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
function refresh(packet){packet.files.set('CANDIDATE_BUILD.json',Buffer.from(JSON.stringify(packet.manifest,null,2)+'\n'));return packet;}
test('actual pure builder produces the complete closed13-file fixed receiver plan',()=>{
 const packet=buildReceiverRuntimeNativeLab(),plan=planReceiverRuntimeLab(packet);
 assert.equal(plan.target,'/opt/lab/g5-receiver-runtime');assert.equal(FIXED_RECEIVER_RUNTIME_ROOT,plan.target);
 assert.equal(plan.files.length,13);assert.deepEqual(plan.files.map(row=>row.path),RECEIVER_RUNTIME_PATHS);
 for(const row of plan.files){const bytes=receiverRuntimeLabBytes(plan,row.path);assert.ok(bytes.equals(packet.files.get(row.path)));assert.equal(sha(bytes),row.sha256);assert.equal(bytes.length,row.bytes);}
 assert.equal(plan.provider_accepted,false);assert.equal(plan.production_authorized,false);
});
test('closed fileset rejects missing, extra, traversal, absolute, siblingG36 and Windows paths',()=>{
 for(const path of [null,'extra.php','../g36/wp-content/db.php','/opt/lab/g36/wp-content/db.php','runtime\\control.gs','runtime/../control.gs']){
  const packet=buildReceiverRuntimeNativeLab();packet.files.delete('runtime/control.gs');
  if(path!==null)packet.files.set(path,Buffer.from('unreviewed'));
  assert.throws(()=>planReceiverRuntimeLab(packet),/RECEIVER_LAB_FILESET_CHANGED/);
 }
});
test('content, byte lengths, manifest members and schema must match exact closed bindings',()=>{
 for(const change of [
  packet=>{packet.files.get('runtime/control.gs')[0]^=1;},
  packet=>{packet.files.set('runtime/control.gs','not-a-buffer');},
  packet=>{packet.manifest.files['runtime/control.gs'].bytes++;refresh(packet);},
  packet=>{packet.manifest.files['runtime/control.gs'].sha256='0'.repeat(64);refresh(packet);},
  packet=>{packet.manifest.files['runtime/control.gs'].unknown=true;refresh(packet);},
  packet=>{packet.manifest.profile='unreviewed';refresh(packet);},
  packet=>{packet.manifest.files['unknown.php']={sha256:'0'.repeat(64),bytes:1};refresh(packet);},
 ]){const packet=buildReceiverRuntimeNativeLab();change(packet);assert.throws(()=>planReceiverRuntimeLab(packet),/RECEIVER_LAB_/);}
});
test('duplicate-key and alternate raw manifest encodings never become an accepted plan',()=>{
 for(const change of [raw=>raw.replace('"schema":','"schema": "discarded",\n  "schema":'),raw=>raw.trim(),raw=>raw+'\n']){
  const packet=buildReceiverRuntimeNativeLab();packet.files.set('CANDIDATE_BUILD.json',Buffer.from(change(packet.files.get('CANDIDATE_BUILD.json').toString())));
  assert.throws(()=>planReceiverRuntimeLab(packet),/RECEIVER_LAB_NONCANONICAL_OR_DUPLICATE_MANIFEST/);
 }
});
test('post-plan genuine buffer and rehashed metadata mutation cannot change detached plan bytes',()=>{
 const packet=buildReceiverRuntimeNativeLab(),plan=planReceiverRuntimeLab(packet),path='runtime/control.gs';
 const original=receiverRuntimeLabBytes(plan,path),originalHash=plan.files.find(row=>row.path===path).sha256;
 packet.files.set(path,Buffer.from('in-place rehash mutation'));
 packet.manifest.files[path]={sha256:sha(packet.files.get(path)),bytes:packet.files.get(path).length};refresh(packet);
 packet.manifest.profile='changed-after-plan';packet.production_authorized=true;
 assert.ok(receiverRuntimeLabBytes(plan,path).equals(original));assert.equal(plan.files.find(row=>row.path===path).sha256,originalHash);
 assert.equal(plan.production_authorized,false);assert.equal(plan.profile,'G5_ACTUAL_RECEIVER_ENGINEERING_ONLY');
});
test('returned buffers and frozen descriptors cannot mutate the private write snapshot',()=>{
 const plan=planReceiverRuntimeLab(buildReceiverRuntimeNativeLab()),path='runtime/control.gs',bytes=receiverRuntimeLabBytes(plan,path),hash=sha(bytes);
 bytes[0]^=1;assert.equal(sha(receiverRuntimeLabBytes(plan,path)),hash);
 assert.throws(()=>{plan.target='/opt/lab/g36';},TypeError);
 assert.throws(()=>{plan.files[0].path='../g36';},TypeError);
 assert.throws(()=>{plan.files.push({path:'evil'});},TypeError);
 assert.throws(()=>receiverRuntimeLabBytes({...plan},path),/RECEIVER_LAB_PLAN_INVALID/);
});
test('production flags, foreign packet keys and caller-supplied write plans are rejected',()=>{
 for(const change of [packet=>{packet.synthetic_only=false;},packet=>{packet.provider_accepted=true;},packet=>{packet.production_authorized=true;},packet=>{packet.target='/opt/lab/g36';}]){
  const packet=buildReceiverRuntimeNativeLab();change(packet);assert.throws(()=>planReceiverRuntimeLab(packet),/RECEIVER_LAB_/);
 }
 // Argument rejection precedes platform/root/filesystem checks: no path override
 // or untrusted externally supplied map can reach the fixed filesystem writer.
 assert.throws(()=>writeFixedReceiverRuntimeLab({target:'/opt/lab/g36'}),/RECEIVER_LAB_NO_ARGUMENTS/);
 assert.throws(()=>writeFixedReceiverRuntimeLab(planReceiverRuntimeLab(buildReceiverRuntimeNativeLab())),/RECEIVER_LAB_NO_ARGUMENTS/);
});
