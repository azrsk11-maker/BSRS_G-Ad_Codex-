/** Fixed isolated-CI materializer. No deployment target, provider or G36 mutation. */
import {constants,lstatSync,realpathSync,mkdirSync,openSync,closeSync,fstatSync,readFileSync,writeFileSync,fsyncSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {buildActualPurgeNativeLab,ACTUAL_PURGE_RUNTIME_PATHS,PURGE_CASES} from '../website-tracking/g5-actual-purge-runtime/build-native-addon.mjs';

export const FIXED_ACTUAL_PURGE_RUNTIME_ROOT='/opt/lab/g5-actual-purge-runtime';
export {ACTUAL_PURGE_RUNTIME_PATHS};
const PROFILE='G38_ACTUAL_PURGE_ENGINEERING_ONLY',plans=new WeakMap();
const need=(ok,code)=>{if(!ok)throw Error(code);};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
function keys(value,expected,code){
 need(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype,code);
 need(Object.keys(value).sort().join('\n')===expected.slice().sort().join('\n'),code);
}
/** Pure consistency check and detached byte snapshot; this is not provider authority. */
export function planActualPurgeRuntimeLab(packet){
 keys(packet,['files','manifest','synthetic_only','provider_accepted','production_authorized'],'ACTUAL_PURGE_LAB_PACKET_INVALID');
 need(packet.synthetic_only===true&&packet.provider_accepted===false&&packet.production_authorized===false,'ACTUAL_PURGE_LAB_BOUNDARY_INVALID');
 need(packet.files instanceof Map&&packet.files.size===26,'ACTUAL_PURGE_LAB_FILESET_CHANGED');
 need([...packet.files.keys()].sort().join('\n')===ACTUAL_PURGE_RUNTIME_PATHS.slice().sort().join('\n'),'ACTUAL_PURGE_LAB_FILESET_CHANGED');
 const files=new Map();
 for(const path of ACTUAL_PURGE_RUNTIME_PATHS){
  const bytes=packet.files.get(path);need(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=2097152,'ACTUAL_PURGE_LAB_BYTES_INVALID');
  files.set(path,Buffer.from(bytes));
 }
 const raw=files.get('G38_BUILD.json').toString('utf8');let manifest;
 try{manifest=JSON.parse(raw);}catch{throw Error('ACTUAL_PURGE_LAB_MANIFEST_INVALID');}
 keys(manifest,['schema','profile','fixed_root','cases','predecessor_driver_sha256','derivations','synthetic_only','native_executed','provider_accepted','production_authorized','files'],'ACTUAL_PURGE_LAB_MANIFEST_INVALID');
 need(raw===JSON.stringify(manifest,null,2)+'\n','ACTUAL_PURGE_LAB_NONCANONICAL_OR_DUPLICATE_MANIFEST');
 need(manifest.schema==='bsre-actual-purge-runtime-synthetic-lab-v1'&&manifest.profile===PROFILE,'ACTUAL_PURGE_LAB_PROFILE_CHANGED');
 need(manifest.fixed_root===FIXED_ACTUAL_PURGE_RUNTIME_ROOT&&manifest.synthetic_only===true&&manifest.native_executed===false&&manifest.provider_accepted===false&&manifest.production_authorized===false,'ACTUAL_PURGE_LAB_BOUNDARY_INVALID');
 keys(manifest.cases,['held','positive'],'ACTUAL_PURGE_LAB_CASES_INVALID');
 for(const [mode,expected]of Object.entries(PURGE_CASES)){const c=manifest.cases[mode];keys(c,['prefix','progress','entry','phase','fresh_case_namespace_required','fresh_database_required','expected_checks'],'ACTUAL_PURGE_LAB_CASE_INVALID');need(c.prefix===expected.prefix&&c.progress===expected.progress&&c.entry===expected.entry&&c.phase===expected.phase&&c.fresh_case_namespace_required===true&&c.fresh_database_required===false,'ACTUAL_PURGE_LAB_CASE_CHANGED');const name=mode==='held'?'native-extension.php':'native-positive.php';const hook="require __DIR__+'/"+name+"';";const actualHook=hook.replace('__DIR__+','__DIR__.');const driver=files.get(c.entry).toString();need(driver.split(actualHook).length===2,'ACTUAL_PURGE_LAB_CHECKS_CHANGED');const checks=[...driver.replace(actualHook,files.get('tests/'+name).toString()).matchAll(/receiver_check\('([^']+)'/g)].map(m=>m[1]);need(Array.isArray(c.expected_checks)&&JSON.stringify(c.expected_checks)===JSON.stringify(checks)&&new Set(checks).size===checks.length,'ACTUAL_PURGE_LAB_CHECKS_CHANGED');}
 keys(manifest.files,ACTUAL_PURGE_RUNTIME_PATHS.filter(path=>path!=='G38_BUILD.json'),'ACTUAL_PURGE_LAB_MANIFEST_FILESET_CHANGED');
 need(JSON.stringify(packet.manifest)===JSON.stringify(manifest),'ACTUAL_PURGE_LAB_METADATA_CHANGED');
 for(const [path,binding]of Object.entries(manifest.files)){
  keys(binding,['sha256','bytes'],'ACTUAL_PURGE_LAB_FILE_BINDING_INVALID');
  const bytes=files.get(path);
  need(typeof binding.sha256==='string'&&/^[a-f0-9]{64}$/.test(binding.sha256)&&Number.isSafeInteger(binding.bytes)
   &&binding.bytes===bytes.length&&binding.sha256===sha(bytes),'ACTUAL_PURGE_LAB_FILE_BINDING_CHANGED');
 }
 const rows=Object.freeze([...files].map(([path,bytes])=>Object.freeze({path,sha256:sha(bytes),bytes:bytes.length})));
 const result=Object.freeze({schema:'bsre-fixed-actual-purge-runtime-lab-plan-v1',profile:PROFILE,target:FIXED_ACTUAL_PURGE_RUNTIME_ROOT,
  files:rows,manifest_sha256:sha(files.get('G38_BUILD.json')),synthetic_only:true,provider_accepted:false,production_authorized:false});
 plans.set(result,files);return result;
}
/** Returns a copy so tests/callers cannot mutate the plan's private bytes. */
export function actualPurgeRuntimeLabBytes(plan,path){
 const files=plans.get(plan);need(files instanceof Map&&files.has(path),'ACTUAL_PURGE_LAB_PLAN_INVALID');
 return Buffer.from(files.get(path));
}
function directory(path){
 const stat=lstatSync(path);
 need(stat.isDirectory()&&!stat.isSymbolicLink()&&realpathSync(path)===path,'ACTUAL_PURGE_LAB_DIRECTORY_UNSAFE');return stat;
}
function sameFile(path,stat){
 const current=lstatSync(path);
 need(current.isFile()&&!current.isSymbolicLink()&&current.nlink===1&&current.dev===stat.dev&&current.ino===stat.ino
  &&realpathSync(path)===path,'ACTUAL_PURGE_LAB_FILE_REPLACED');
}
function requireAbsent(path){
 try{lstatSync(path);}catch(error){if(error.code==='ENOENT')return;throw error;}
 throw Error('ACTUAL_PURGE_LAB_FRESH_DESTINATION_REQUIRED');
}
function child(path){
 need(ACTUAL_PURGE_RUNTIME_PATHS.includes(path)&&!path.includes('\\')&&!path.split('/').some(part=>!part||part==='.'||part==='..'),'ACTUAL_PURGE_LAB_PATH_INVALID');
 const result=join(FIXED_ACTUAL_PURGE_RUNTIME_ROOT,path);
 need(result.startsWith(FIXED_ACTUAL_PURGE_RUNTIME_ROOT+'/'),'ACTUAL_PURGE_LAB_PATH_INVALID');return result;
}
/** No arguments or destination overrides. Only the reviewed builder supplies bytes. */
export function writeFixedActualPurgeRuntimeLab(){
 need(arguments.length===0,'ACTUAL_PURGE_LAB_NO_ARGUMENTS');
 need(process.platform==='linux'&&typeof process.getuid==='function'&&process.getuid()===0,'ACTUAL_PURGE_LAB_BUILD_ROOT_REQUIRED');
 need(Number.isInteger(constants.O_NOFOLLOW),'ACTUAL_PURGE_LAB_NOFOLLOW_REQUIRED');
 const plan=planActualPurgeRuntimeLab(buildActualPurgeNativeLab());
 for(const path of ['/','/opt','/opt/lab'])directory(path);
 requireAbsent(FIXED_ACTUAL_PURGE_RUNTIME_ROOT);
 // Exclusive mkdir is the first side effect. A partial failed build is left held;
 // there is no overwrite, retry-in-place, recursive delete, move or G36 operation.
 mkdirSync(FIXED_ACTUAL_PURGE_RUNTIME_ROOT,{recursive:false,mode:0o755});directory(FIXED_ACTUAL_PURGE_RUNTIME_ROOT);
 const directories=new Set();
 for(const path of ACTUAL_PURGE_RUNTIME_PATHS){
  let relative=dirname(path);
  while(relative!=='.'){directories.add(relative);relative=dirname(relative);}
 }
 for(const relative of [...directories].sort((a,b)=>a.split('/').length-b.split('/').length||a.localeCompare(b))){
  const target=join(FIXED_ACTUAL_PURGE_RUNTIME_ROOT,relative);directory(dirname(target));
  mkdirSync(target,{recursive:false,mode:0o755});directory(target);
 }
 for(const row of plan.files){
  const path=child(row.path);directory(dirname(path));const bytes=actualPurgeRuntimeLabBytes(plan,row.path);
  need(bytes.length===row.bytes&&sha(bytes)===row.sha256,'ACTUAL_PURGE_LAB_SNAPSHOT_CHANGED');
  let fd;
  try{
   fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o644);
   writeFileSync(fd,bytes);fsyncSync(fd);const stat=fstatSync(fd);
   need(stat.isFile()&&stat.nlink===1&&stat.size===row.bytes,'ACTUAL_PURGE_LAB_WRITE_UNVERIFIED');sameFile(path,stat);
  }finally{if(fd!==undefined)closeSync(fd);}
 }
 for(const row of plan.files){
  const path=child(row.path);directory(dirname(path));let fd;
  try{
   fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW);const stat=fstatSync(fd);sameFile(path,stat);
   const bytes=readFileSync(fd);
   need(stat.size===row.bytes&&bytes.length===row.bytes&&sha(bytes)===row.sha256,'ACTUAL_PURGE_LAB_READBACK_CHANGED');
  }finally{if(fd!==undefined)closeSync(fd);}
 }
 return Object.freeze({schema:'bsre-fixed-actual-purge-runtime-lab-write-v1',profile:PROFILE,target:FIXED_ACTUAL_PURGE_RUNTIME_ROOT,
  files:plan.files,manifest_sha256:plan.manifest_sha256,fresh_destination_created:true,readback_hashes_verified:true,
  synthetic_only:true,native_executed:false,provider_accepted:false,production_authorized:false});
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 need(process.argv.length===2,'ACTUAL_PURGE_LAB_NO_ARGUMENTS');
 process.stdout.write(JSON.stringify(writeFixedActualPurgeRuntimeLab())+'\n');
}
