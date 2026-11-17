import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {posix} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {build} from '../website-tracking/g5-local-history-runtime/build-private.mjs';
import {planLocalHistoryRuntimeLab,localHistoryRuntimeLabBytes,writeFixedLocalHistoryRuntimeLab,FIXED_LOCAL_HISTORY_ROOT,FIXED_LOCAL_INPUT_ROOT,LOCAL_HISTORY_RUNTIME_PATHS} from './build-local-history-runtime-lab.mjs';

const sourceRoot=fileURLToPath(new URL('../../',import.meta.url));
const writerUrl=new URL('./build-local-history-runtime-lab.mjs',import.meta.url);
const moduleUrl=new URL('../website-tracking/g5-local-history-runtime/',import.meta.url);
const sha=b=>createHash('sha256').update(b).digest('hex');
const base=build(sourceRoot);
const expectations=JSON.parse(readFileSync(new URL('NATIVE_EXPECTATIONS.json',moduleUrl),'utf8'));
const inputMap=JSON.parse(readFileSync(new URL('MATERIALIZER_INPUT_MAP.json',moduleUrl),'utf8'));
const sourcePins=JSON.parse(readFileSync(new URL('SOURCE_PINS.json',moduleUrl),'utf8'));
const writer=readFileSync(writerUrl,'utf8');
const packet=()=>({files:new Map([...base.files].map(([p,b])=>[p,Buffer.from(b)])),manifest:structuredClone(base.manifest)});

test('fixed plan closes all25 files and26 source inputs with local authority only',()=>{
 const p=packet(),plan=planLocalHistoryRuntimeLab(p);
 assert.equal(plan.schema,'bsre-fixed-g39-local-history-runtime-lab-plan-v1');
 assert.equal(plan.profile,'G39_LOCAL_HISTORY_ENGINEERING_ONLY');
 assert.equal(plan.target,'/opt/lab/g39-history-local');assert.equal(FIXED_LOCAL_HISTORY_ROOT,plan.target);
 assert.equal(FIXED_LOCAL_INPUT_ROOT,'/opt/lab/g39-inputs');assert.equal(plan.source_inputs,26);
 assert.equal(plan.files.length,25);assert.equal(LOCAL_HISTORY_RUNTIME_PATHS.length,25);
 assert.equal(plan.synthetic_only,true);assert.equal(plan.local_scope_only,true);
 assert.equal(plan.provider_accepted,false);assert.equal(plan.production_authorized,false);
 assert.equal(plan.manifest_sha256,sha(p.files.get('G39_BUILD.json')));
 assert.equal(base.manifest.expected_checks.length,43);assert.equal(new Set(base.manifest.expected_checks).size,43);
 for(const row of plan.files){assert.deepEqual(Object.keys(row),['path','bytes','sha256']);assert.equal(row.bytes,p.files.get(row.path).length);assert.equal(row.sha256,sha(p.files.get(row.path)));assert.deepEqual(row,expectations.files[row.path]&&{path:row.path,...expectations.files[row.path]});}
});
test('closed packet rejects missing extra inherited and null-prototype metadata',()=>{
 for(const bad of [null,[],{files:base.files}, {...packet(),extra:true},Object.assign(Object.create(null),packet()),Object.assign(Object.create({inherited:true}),packet())])assert.throws(()=>planLocalHistoryRuntimeLab(bad),/G39_LAB_PACKET_INVALID/);
});
test('files require a Map and the exact closed count',()=>{
 const object=packet();object.files=Object.fromEntries(object.files);assert.throws(()=>planLocalHistoryRuntimeLab(object),/FILESET_CHANGED/);
 const missing=packet();missing.files.delete('tests/foreign-capture-snapshot.php');assert.throws(()=>planLocalHistoryRuntimeLab(missing),/FILESET_CHANGED/);
 const extra=packet();extra.files.set('extra.php',Buffer.from('extra'));assert.throws(()=>planLocalHistoryRuntimeLab(extra),/FILESET_CHANGED/);
});
test('same-count path substitution cannot introduce traversal or absolute outputs',()=>{
 for(const path of ['../escape.php','/opt/lab/escape.php','history\\escape.php','history/../escape.php','history//escape.php']){
  const p=packet(),first=p.files.keys().next().value;p.files.delete(first);p.files.set(path,Buffer.from('escape'));assert.throws(()=>planLocalHistoryRuntimeLab(p),/FILESET_CHANGED/);
 }
});
test('nonBuffer and changed-size bytes are rejected before planning',()=>{
 const path='history/LocalHistoryObserver.php';const typed=packet();typed.files.set(path,new Uint8Array(typed.files.get(path)));assert.throws(()=>planLocalHistoryRuntimeLab(typed),/BYTES_CHANGED/);
 const resized=packet();resized.files.set(path,Buffer.concat([resized.files.get(path),Buffer.from('\n')]));assert.throws(()=>planLocalHistoryRuntimeLab(resized),/BYTES_CHANGED/);
});
test('same-size tampering is rejected by pinned SHA256',()=>{
 const p=packet(),path='tests/foreign-capture-snapshot.php';p.files.get(path)[0]^=1;assert.throws(()=>planLocalHistoryRuntimeLab(p),/BYTES_CHANGED/);
});
test('malformed manifest bytes are rejected by the outer byte pin',()=>{
 const p=packet(),b=p.files.get('G39_BUILD.json');p.files.set('G39_BUILD.json',Buffer.alloc(b.length,123));assert.throws(()=>planLocalHistoryRuntimeLab(p),/BYTES_CHANGED/);
});
test('manifest changes cannot override packet bytes or engineering authority',()=>{
 for(const change of [m=>m.fixed_root='/tmp/other',m=>m.fixed_prefix='other_',m=>m.local_scope_only=false,m=>m.native_executed=true,m=>m.provider_accepted=true,m=>m.production_authorized=true,m=>m.expected_checks.pop(),m=>m.expected_checks[1]=m.expected_checks[0],m=>m.files['history/LocalHistoryObserver.php'].sha256='0'.repeat(64)]){
  const p=packet();change(p.manifest);assert.throws(()=>planLocalHistoryRuntimeLab(p),/MANIFEST_CHANGED/);
 }
});
test('map input order does not change the canonical plan order',()=>{
 const p=packet();p.files=new Map([...p.files].reverse());const plan=planLocalHistoryRuntimeLab(p);assert.deepEqual(plan.files.map(r=>r.path),LOCAL_HISTORY_RUNTIME_PATHS);
});
test('plan and every output row are immutable',()=>{
 const plan=planLocalHistoryRuntimeLab(packet());assert.equal(Object.isFrozen(plan),true);assert.equal(Object.isFrozen(plan.files),true);assert.equal(plan.files.every(Object.isFrozen),true);
 assert.throws(()=>{plan.target='/tmp/other';},TypeError);assert.throws(()=>plan.files.push({path:'extra'}),TypeError);assert.throws(()=>{plan.files[0].sha256='0'.repeat(64);},TypeError);
});
test('plan owns detached copies of every caller buffer',()=>{
 const p=packet(),plan=planLocalHistoryRuntimeLab(p);for(const b of p.files.values())b.fill(0);
 p.manifest.provider_accepted=true;p.files.clear();
 for(const row of plan.files){const b=localHistoryRuntimeLabBytes(plan,row.path);assert.equal(b.length,row.bytes);assert.equal(sha(b),row.sha256);}
 assert.equal(plan.provider_accepted,false);
});
test('each accessor returns another detached copy',()=>{
 const plan=planLocalHistoryRuntimeLab(packet()),path='history/LocalHistoryObserver.php';const first=localHistoryRuntimeLabBytes(plan,path),second=localHistoryRuntimeLabBytes(plan,path);
 assert.notStrictEqual(first,second);first.fill(120);assert.equal(sha(localHistoryRuntimeLabBytes(plan,path)),expectations.files[path].sha256);
});
test('forged or serialized plans have no private byte capability',()=>{
 const plan=planLocalHistoryRuntimeLab(packet());for(const forged of [{...plan},JSON.parse(JSON.stringify(plan)),Object.freeze({...plan}),Object.create(plan),null])assert.throws(()=>localHistoryRuntimeLabBytes(forged,'G39_BUILD.json'),/PLAN_INVALID/);
});
test('byte accessor rejects unknown absolute traversal and nonstring keys',()=>{
 const plan=planLocalHistoryRuntimeLab(packet());for(const path of ['../G39_BUILD.json','/opt/lab/g39-history-local/G39_BUILD.json','G39_BUILD.json/extra','__proto__',{},null])assert.throws(()=>localHistoryRuntimeLabBytes(plan,path),/PLAN_INVALID/);
});
test('plans from another module instance cannot borrow private byte storage',async()=>{
 const plan=planLocalHistoryRuntimeLab(packet()),other=await import(new URL('./build-local-history-runtime-lab.mjs?independent-plan-store',import.meta.url));
 assert.throws(()=>other.localHistoryRuntimeLabBytes(plan,'G39_BUILD.json'),/PLAN_INVALID/);
});

// Execute only extracted pure predicates; never invoke the filesystem writer.
function pureFunction(name){const marker='function '+name+'(',at=writer.indexOf(marker);assert.ok(at>=0);assert.equal(writer.indexOf(marker,at+1),-1);const end=writer.indexOf('\n}',at);assert.ok(end>at);return writer.slice(at,end+2);}
const need=(ok,code)=>{if(!ok)throw Error(code);};
const relativeGuard=Function('need','return ('+pureFunction('relative')+');')(need);
const mapStart=writer.indexOf("relative(path);need(path.startsWith('tools/')");
const mapEnd=writer.indexOf(",'G39_LAB_INPUT_MAP_INVALID');",mapStart)+",'G39_LAB_INPUT_MAP_INVALID');".length;
assert.ok(mapStart>=0&&mapEnd>mapStart);
const mapGuard=Function('relative','join','FIXED_LOCAL_INPUT_ROOT','need','return (path,row)=>{'+writer.slice(mapStart,mapEnd)+'};')(relativeGuard,posix.join,FIXED_LOCAL_INPUT_ROOT,need);

test('actual pure relative-path predicate rejects traversal and malformed paths',()=>{
 for(const path of ['',null,123,'/absolute','../escape','a/../b','a/./b','a//b','a/','a\\b'])assert.throws(()=>relativeGuard(path),/RELATIVE_PATH_INVALID/);
 for(const path of LOCAL_HISTORY_RUNTIME_PATHS)assert.equal(relativeGuard(path),path);
});
test('actual Linux input-map predicate binds tools namespace and fixed alias',()=>{
 const path='tools/closed-enquiry-retention/Workflow.php',good={...inputMap.files[path]};assert.doesNotThrow(()=>mapGuard(path,good));
 for(const row of [{...good,fixed_alias:'/tmp/alias'},{...good,image_source:'/etc/passwd'},{...good,image_source:'/opt/lab/../secret'},{...good,image_source:null}])assert.throws(()=>mapGuard(path,row),/INPUT_MAP_INVALID/);
 assert.throws(()=>mapGuard('not-tools/file.php',{...good,fixed_alias:posix.join(FIXED_LOCAL_INPUT_ROOT,'not-tools/file.php')}),/INPUT_MAP_INVALID/);
});
test('all26 map aliases retain source pin hashes without dropping review context',()=>{
 assert.equal(Object.keys(sourcePins.files).length,26);assert.deepEqual(Object.keys(inputMap.files).sort(),Object.keys(sourcePins.files).sort());
 for(const [path,row]of Object.entries(inputMap.files)){mapGuard(path,row);assert.equal(row.fixed_alias,posix.join(FIXED_LOCAL_INPUT_ROOT,path));assert.equal(row.sha256,sourcePins.files[path].sha256);assert.equal(row.bytes,sourcePins.files[path].bytes);}
 assert.equal(Object.values(inputMap.files).filter(r=>r.role==='BUILD_REQUIRED').length,21);assert.equal(Object.values(inputMap.files).filter(r=>r.role==='REVIEW_CONTEXT_STILL_PIN_REQUIRED').length,5);
});
test('writer remains a zero-argument fixed Linux image-build entry and is never invoked here',()=>{
 assert.equal(writeFixedLocalHistoryRuntimeLab.length,0);
 assert.match(writer,/need\(arguments\.length===0,'G39_LAB_NO_ARGUMENTS'\)/);
 assert.match(writer,/process\.platform==='linux'&&typeof process\.getuid==='function'&&process\.getuid\(\)===0/);
 assert.match(writer,/constants\.O_WRONLY\|constants\.O_CREAT\|constants\.O_EXCL\|constants\.O_NOFOLLOW/);
 assert.match(writer,/absent\(FIXED_LOCAL_INPUT_ROOT\);absent\(FIXED_LOCAL_HISTORY_ROOT\)/);
 assert.doesNotMatch(writer,/rmSync|unlinkSync|rmdirSync|execSync|spawnSync|process\.env/);
});
