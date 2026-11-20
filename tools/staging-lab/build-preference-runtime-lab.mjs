/** Fixed isolated-CI materializer. No deployment target, provider or G36 mutation. */
import {constants,lstatSync,realpathSync,mkdirSync,openSync,closeSync,fstatSync,readFileSync,writeFileSync,fsyncSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {buildPreferenceAddon} from '../website-tracking/g5-preference-runtime/build-native-addon.mjs';

export const FIXED_PREFERENCE_RUNTIME_ROOT='/opt/lab/g37-pref';
export const PREFERENCE_RUNTIME_PATHS=Object.freeze([
 "runtime/ActualPreferenceRetention.php",
 "runtime/PreferenceAlgebra.php",
 "runtime/PreferenceAtomicStore.php",
 "runtime/PreferenceContracts.php",
 "runtime/PreferenceCustody.php",
 "runtime/preference-source.json",
 "FixturePorts.php",
 "native.php",
 "G37_BUILD.json"
]);
const PROFILE='G37_ACTUAL_PREFERENCE_ENGINEERING_ONLY',plans=new WeakMap();
const need=(ok,code)=>{if(!ok)throw Error(code);};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
function keys(value,expected,code){
 need(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype,code);
 need(Object.keys(value).sort().join('\n')===expected.slice().sort().join('\n'),code);
}
/** Pure closed-map adapter. Only the fixed G37 prefix can be stripped. */
export function buildPreferenceRuntimeLabPacket(){
 const addon=buildPreferenceAddon(),files=new Map();
 need(addon instanceof Map&&addon.size===8,'PREFERENCE_LAB_ADDON_INVALID');
 for(const [path,bytes]of addon){
  need(typeof path==='string'&&path.startsWith('g37-pref/'),'PREFERENCE_LAB_ADDON_PATH_INVALID');
  const relative=path.slice('g37-pref/'.length);
  need(PREFERENCE_RUNTIME_PATHS.includes(relative)&&relative!=='G37_BUILD.json'&&!files.has(relative),'PREFERENCE_LAB_ADDON_PATH_INVALID');
  need(Buffer.isBuffer(bytes),'PREFERENCE_LAB_BYTES_INVALID');files.set(relative,Buffer.from(bytes));
 }
 const manifest={schema:'bsre-preference-runtime-synthetic-lab-v1',profile:PROFILE,
  files:Object.fromEntries([...files].map(([path,bytes])=>[path,{sha256:sha(bytes),bytes:bytes.length}]))};
 files.set('G37_BUILD.json',Buffer.from(JSON.stringify(manifest,null,2)+'\n'));
 return {files,manifest,synthetic_only:true,provider_accepted:false,production_authorized:false};
}
/** Pure consistency check and detached byte snapshot; this is not provider authority. */
export function planPreferenceRuntimeLab(packet){
 keys(packet,['files','manifest','synthetic_only','provider_accepted','production_authorized'],'PREFERENCE_LAB_PACKET_INVALID');
 need(packet.synthetic_only===true&&packet.provider_accepted===false&&packet.production_authorized===false,'PREFERENCE_LAB_BOUNDARY_INVALID');
 need(packet.files instanceof Map&&packet.files.size===9,'PREFERENCE_LAB_FILESET_CHANGED');
 need([...packet.files.keys()].sort().join('\n')===PREFERENCE_RUNTIME_PATHS.slice().sort().join('\n'),'PREFERENCE_LAB_FILESET_CHANGED');
 const files=new Map();
 for(const path of PREFERENCE_RUNTIME_PATHS){
  const bytes=packet.files.get(path);need(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=2097152,'PREFERENCE_LAB_BYTES_INVALID');
  files.set(path,Buffer.from(bytes));
 }
 const raw=files.get('G37_BUILD.json').toString('utf8');let manifest;
 try{manifest=JSON.parse(raw);}catch{throw Error('PREFERENCE_LAB_MANIFEST_INVALID');}
 keys(manifest,['schema','profile','files'],'PREFERENCE_LAB_MANIFEST_INVALID');
 need(raw===JSON.stringify(manifest,null,2)+'\n','PREFERENCE_LAB_NONCANONICAL_OR_DUPLICATE_MANIFEST');
 need(manifest.schema==='bsre-preference-runtime-synthetic-lab-v1'&&manifest.profile===PROFILE,'PREFERENCE_LAB_PROFILE_CHANGED');
 keys(manifest.files,PREFERENCE_RUNTIME_PATHS.filter(path=>path!=='G37_BUILD.json'),'PREFERENCE_LAB_MANIFEST_FILESET_CHANGED');
 need(JSON.stringify(packet.manifest)===JSON.stringify(manifest),'PREFERENCE_LAB_METADATA_CHANGED');
 for(const [path,binding]of Object.entries(manifest.files)){
  keys(binding,['sha256','bytes'],'PREFERENCE_LAB_FILE_BINDING_INVALID');
  const bytes=files.get(path);
  need(typeof binding.sha256==='string'&&/^[a-f0-9]{64}$/.test(binding.sha256)&&Number.isSafeInteger(binding.bytes)
   &&binding.bytes===bytes.length&&binding.sha256===sha(bytes),'PREFERENCE_LAB_FILE_BINDING_CHANGED');
 }
 const rows=Object.freeze([...files].map(([path,bytes])=>Object.freeze({path,sha256:sha(bytes),bytes:bytes.length})));
 const result=Object.freeze({schema:'bsre-fixed-preference-runtime-lab-plan-v1',profile:PROFILE,target:FIXED_PREFERENCE_RUNTIME_ROOT,
  files:rows,manifest_sha256:sha(files.get('G37_BUILD.json')),synthetic_only:true,provider_accepted:false,production_authorized:false});
 plans.set(result,files);return result;
}
/** Returns a copy so tests/callers cannot mutate the plan's private bytes. */
export function preferenceRuntimeLabBytes(plan,path){
 const files=plans.get(plan);need(files instanceof Map&&files.has(path),'PREFERENCE_LAB_PLAN_INVALID');
 return Buffer.from(files.get(path));
}
function directory(path){
 const stat=lstatSync(path);
 need(stat.isDirectory()&&!stat.isSymbolicLink()&&realpathSync(path)===path,'PREFERENCE_LAB_DIRECTORY_UNSAFE');return stat;
}
function sameFile(path,stat){
 const current=lstatSync(path);
 need(current.isFile()&&!current.isSymbolicLink()&&current.nlink===1&&current.dev===stat.dev&&current.ino===stat.ino
  &&realpathSync(path)===path,'PREFERENCE_LAB_FILE_REPLACED');
}
function requireAbsent(path){
 try{lstatSync(path);}catch(error){if(error.code==='ENOENT')return;throw error;}
 throw Error('PREFERENCE_LAB_FRESH_DESTINATION_REQUIRED');
}
function child(path){
 need(PREFERENCE_RUNTIME_PATHS.includes(path)&&!path.includes('\\')&&!path.split('/').some(part=>!part||part==='.'||part==='..'),'PREFERENCE_LAB_PATH_INVALID');
 const result=join(FIXED_PREFERENCE_RUNTIME_ROOT,path);
 need(result.startsWith(FIXED_PREFERENCE_RUNTIME_ROOT+'/'),'PREFERENCE_LAB_PATH_INVALID');return result;
}
/** No arguments or destination overrides. Only the reviewed builder supplies bytes. */
export function writeFixedPreferenceRuntimeLab(){
 need(arguments.length===0,'PREFERENCE_LAB_NO_ARGUMENTS');
 need(process.platform==='linux'&&typeof process.getuid==='function'&&process.getuid()===0,'PREFERENCE_LAB_BUILD_ROOT_REQUIRED');
 need(Number.isInteger(constants.O_NOFOLLOW),'PREFERENCE_LAB_NOFOLLOW_REQUIRED');
 const plan=planPreferenceRuntimeLab(buildPreferenceRuntimeLabPacket());
 for(const path of ['/','/opt','/opt/lab'])directory(path);
 requireAbsent(FIXED_PREFERENCE_RUNTIME_ROOT);
 // Exclusive mkdir is the first side effect. A partial failed build is left held;
 // there is no overwrite, retry-in-place, recursive delete, move or G36 operation.
 mkdirSync(FIXED_PREFERENCE_RUNTIME_ROOT,{recursive:false,mode:0o755});directory(FIXED_PREFERENCE_RUNTIME_ROOT);
 const directories=new Set();
 for(const path of PREFERENCE_RUNTIME_PATHS){
  let relative=dirname(path);
  while(relative!=='.'){directories.add(relative);relative=dirname(relative);}
 }
 for(const relative of [...directories].sort((a,b)=>a.split('/').length-b.split('/').length||a.localeCompare(b))){
  const target=join(FIXED_PREFERENCE_RUNTIME_ROOT,relative);directory(dirname(target));
  mkdirSync(target,{recursive:false,mode:0o755});directory(target);
 }
 for(const row of plan.files){
  const path=child(row.path);directory(dirname(path));const bytes=preferenceRuntimeLabBytes(plan,row.path);
  need(bytes.length===row.bytes&&sha(bytes)===row.sha256,'PREFERENCE_LAB_SNAPSHOT_CHANGED');
  let fd;
  try{
   fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o644);
   writeFileSync(fd,bytes);fsyncSync(fd);const stat=fstatSync(fd);
   need(stat.isFile()&&stat.nlink===1&&stat.size===row.bytes,'PREFERENCE_LAB_WRITE_UNVERIFIED');sameFile(path,stat);
  }finally{if(fd!==undefined)closeSync(fd);}
 }
 for(const row of plan.files){
  const path=child(row.path);directory(dirname(path));let fd;
  try{
   fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW);const stat=fstatSync(fd);sameFile(path,stat);
   const bytes=readFileSync(fd);
   need(stat.size===row.bytes&&bytes.length===row.bytes&&sha(bytes)===row.sha256,'PREFERENCE_LAB_READBACK_CHANGED');
  }finally{if(fd!==undefined)closeSync(fd);}
 }
 return Object.freeze({schema:'bsre-fixed-preference-runtime-lab-write-v1',profile:PROFILE,target:FIXED_PREFERENCE_RUNTIME_ROOT,
  files:plan.files,manifest_sha256:plan.manifest_sha256,fresh_destination_created:true,readback_hashes_verified:true,
  synthetic_only:true,native_executed:false,provider_accepted:false,production_authorized:false});
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 need(process.argv.length===2,'PREFERENCE_LAB_NO_ARGUMENTS');
 process.stdout.write(JSON.stringify(writeFixedPreferenceRuntimeLab())+'\n');
}
