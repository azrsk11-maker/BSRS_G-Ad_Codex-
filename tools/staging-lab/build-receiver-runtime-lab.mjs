/** Fixed isolated-CI materializer. No deployment target, provider or G36 mutation. */
import {constants,lstatSync,realpathSync,mkdirSync,openSync,closeSync,fstatSync,readFileSync,writeFileSync,fsyncSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {dirname,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {buildReceiverRuntimeNativeLab} from '../website-tracking/g5-receiver-runtime/build-native-lab.mjs';

export const FIXED_RECEIVER_RUNTIME_ROOT='/opt/lab/g5-receiver-runtime';
export const RECEIVER_RUNTIME_PATHS=Object.freeze([
 'build-candidate.mjs','runtime/control.gs','runtime/no-copy.gs',
 'candidate/plugin/includes/candidate/receiver/ReceiverContracts.php',
 'candidate/plugin/includes/candidate/receiver/NoMailCopyAlgebra.php',
 'candidate/plugin/includes/candidate/receiver/ActualRetirementPort.php',
 'candidate/plugin/includes/candidate/receiver/ReceiverOperationalEvidence.php',
 'candidate/plugin/includes/candidate/receiver/ActualReceiverWorkflow.php',
 'candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php',
 'tests/control-fixture.mjs','tests/native-bridge.mjs','tests/receiver-runtime-native.php','CANDIDATE_BUILD.json',
]);
const PROFILE='G5_ACTUAL_RECEIVER_ENGINEERING_ONLY',plans=new WeakMap();
const need=(ok,code)=>{if(!ok)throw Error(code);};
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
function keys(value,expected,code){
 need(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype,code);
 need(Object.keys(value).sort().join('\n')===expected.slice().sort().join('\n'),code);
}
/** Pure consistency check and detached byte snapshot; this is not provider authority. */
export function planReceiverRuntimeLab(packet){
 keys(packet,['files','manifest','synthetic_only','provider_accepted','production_authorized'],'RECEIVER_LAB_PACKET_INVALID');
 need(packet.synthetic_only===true&&packet.provider_accepted===false&&packet.production_authorized===false,'RECEIVER_LAB_BOUNDARY_INVALID');
 need(packet.files instanceof Map&&packet.files.size===13,'RECEIVER_LAB_FILESET_CHANGED');
 need([...packet.files.keys()].sort().join('\n')===RECEIVER_RUNTIME_PATHS.slice().sort().join('\n'),'RECEIVER_LAB_FILESET_CHANGED');
 const files=new Map();
 for(const path of RECEIVER_RUNTIME_PATHS){
  const bytes=packet.files.get(path);need(Buffer.isBuffer(bytes)&&bytes.length>0&&bytes.length<=2097152,'RECEIVER_LAB_BYTES_INVALID');
  files.set(path,Buffer.from(bytes));
 }
 const raw=files.get('CANDIDATE_BUILD.json').toString('utf8');let manifest;
 try{manifest=JSON.parse(raw);}catch{throw Error('RECEIVER_LAB_MANIFEST_INVALID');}
 keys(manifest,['schema','profile','files'],'RECEIVER_LAB_MANIFEST_INVALID');
 need(raw===JSON.stringify(manifest,null,2)+'\n','RECEIVER_LAB_NONCANONICAL_OR_DUPLICATE_MANIFEST');
 need(manifest.schema==='bsre-receiver-runtime-synthetic-lab-v1'&&manifest.profile===PROFILE,'RECEIVER_LAB_PROFILE_CHANGED');
 keys(manifest.files,RECEIVER_RUNTIME_PATHS.filter(path=>path!=='CANDIDATE_BUILD.json'),'RECEIVER_LAB_MANIFEST_FILESET_CHANGED');
 need(JSON.stringify(packet.manifest)===JSON.stringify(manifest),'RECEIVER_LAB_METADATA_CHANGED');
 for(const [path,binding]of Object.entries(manifest.files)){
  keys(binding,['sha256','bytes'],'RECEIVER_LAB_FILE_BINDING_INVALID');
  const bytes=files.get(path);
  need(typeof binding.sha256==='string'&&/^[a-f0-9]{64}$/.test(binding.sha256)&&Number.isSafeInteger(binding.bytes)
   &&binding.bytes===bytes.length&&binding.sha256===sha(bytes),'RECEIVER_LAB_FILE_BINDING_CHANGED');
 }
 const rows=Object.freeze([...files].map(([path,bytes])=>Object.freeze({path,sha256:sha(bytes),bytes:bytes.length})));
 const result=Object.freeze({schema:'bsre-fixed-receiver-runtime-lab-plan-v1',profile:PROFILE,target:FIXED_RECEIVER_RUNTIME_ROOT,
  files:rows,manifest_sha256:sha(files.get('CANDIDATE_BUILD.json')),synthetic_only:true,provider_accepted:false,production_authorized:false});
 plans.set(result,files);return result;
}
/** Returns a copy so tests/callers cannot mutate the plan's private bytes. */
export function receiverRuntimeLabBytes(plan,path){
 const files=plans.get(plan);need(files instanceof Map&&files.has(path),'RECEIVER_LAB_PLAN_INVALID');
 return Buffer.from(files.get(path));
}
function directory(path){
 const stat=lstatSync(path);
 need(stat.isDirectory()&&!stat.isSymbolicLink()&&realpathSync(path)===path,'RECEIVER_LAB_DIRECTORY_UNSAFE');return stat;
}
function sameFile(path,stat){
 const current=lstatSync(path);
 need(current.isFile()&&!current.isSymbolicLink()&&current.nlink===1&&current.dev===stat.dev&&current.ino===stat.ino
  &&realpathSync(path)===path,'RECEIVER_LAB_FILE_REPLACED');
}
function requireAbsent(path){
 try{lstatSync(path);}catch(error){if(error.code==='ENOENT')return;throw error;}
 throw Error('RECEIVER_LAB_FRESH_DESTINATION_REQUIRED');
}
function child(path){
 need(RECEIVER_RUNTIME_PATHS.includes(path)&&!path.includes('\\')&&!path.split('/').some(part=>!part||part==='.'||part==='..'),'RECEIVER_LAB_PATH_INVALID');
 const result=join(FIXED_RECEIVER_RUNTIME_ROOT,path);
 need(result.startsWith(FIXED_RECEIVER_RUNTIME_ROOT+'/'),'RECEIVER_LAB_PATH_INVALID');return result;
}
/** No arguments or destination overrides. Only the reviewed builder supplies bytes. */
export function writeFixedReceiverRuntimeLab(){
 need(arguments.length===0,'RECEIVER_LAB_NO_ARGUMENTS');
 need(process.platform==='linux'&&typeof process.getuid==='function'&&process.getuid()===0,'RECEIVER_LAB_BUILD_ROOT_REQUIRED');
 need(Number.isInteger(constants.O_NOFOLLOW),'RECEIVER_LAB_NOFOLLOW_REQUIRED');
 const plan=planReceiverRuntimeLab(buildReceiverRuntimeNativeLab());
 for(const path of ['/','/opt','/opt/lab'])directory(path);
 requireAbsent(FIXED_RECEIVER_RUNTIME_ROOT);
 // Exclusive mkdir is the first side effect. A partial failed build is left held;
 // there is no overwrite, retry-in-place, recursive delete, move or G36 operation.
 mkdirSync(FIXED_RECEIVER_RUNTIME_ROOT,{recursive:false,mode:0o755});directory(FIXED_RECEIVER_RUNTIME_ROOT);
 const directories=new Set();
 for(const path of RECEIVER_RUNTIME_PATHS){
  let relative=dirname(path);
  while(relative!=='.'){directories.add(relative);relative=dirname(relative);}
 }
 for(const relative of [...directories].sort((a,b)=>a.split('/').length-b.split('/').length||a.localeCompare(b))){
  const target=join(FIXED_RECEIVER_RUNTIME_ROOT,relative);directory(dirname(target));
  mkdirSync(target,{recursive:false,mode:0o755});directory(target);
 }
 for(const row of plan.files){
  const path=child(row.path);directory(dirname(path));const bytes=receiverRuntimeLabBytes(plan,row.path);
  need(bytes.length===row.bytes&&sha(bytes)===row.sha256,'RECEIVER_LAB_SNAPSHOT_CHANGED');
  let fd;
  try{
   fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o644);
   writeFileSync(fd,bytes);fsyncSync(fd);const stat=fstatSync(fd);
   need(stat.isFile()&&stat.nlink===1&&stat.size===row.bytes,'RECEIVER_LAB_WRITE_UNVERIFIED');sameFile(path,stat);
  }finally{if(fd!==undefined)closeSync(fd);}
 }
 for(const row of plan.files){
  const path=child(row.path);directory(dirname(path));let fd;
  try{
   fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW);const stat=fstatSync(fd);sameFile(path,stat);
   const bytes=readFileSync(fd);
   need(stat.size===row.bytes&&bytes.length===row.bytes&&sha(bytes)===row.sha256,'RECEIVER_LAB_READBACK_CHANGED');
  }finally{if(fd!==undefined)closeSync(fd);}
 }
 return Object.freeze({schema:'bsre-fixed-receiver-runtime-lab-write-v1',profile:PROFILE,target:FIXED_RECEIVER_RUNTIME_ROOT,
  files:plan.files,manifest_sha256:plan.manifest_sha256,fresh_destination_created:true,readback_hashes_verified:true,
  synthetic_only:true,native_executed:false,provider_accepted:false,production_authorized:false});
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
 need(process.argv.length===2,'RECEIVER_LAB_NO_ARGUMENTS');
 process.stdout.write(JSON.stringify(writeFixedReceiverRuntimeLab())+'\n');
}
