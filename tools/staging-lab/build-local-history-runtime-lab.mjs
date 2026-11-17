/** Fixed disposable-lab materializer. No deployment, caller path or provider authority. */
import {constants,lstatSync,realpathSync,mkdirSync,openSync,closeSync,fstatSync,readFileSync,writeFileSync,fsyncSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {build,FIXED_ROOT,FIXED_PREFIX} from '../website-tracking/g5-local-history-runtime/build-private.mjs';

const moduleRoot=new URL('../website-tracking/g5-local-history-runtime/',import.meta.url);
const expected=JSON.parse(readFileSync(new URL('NATIVE_EXPECTATIONS.json',moduleRoot),'utf8'));
const inputMap=JSON.parse(readFileSync(new URL('MATERIALIZER_INPUT_MAP.json',moduleRoot),'utf8'));
const pins=JSON.parse(readFileSync(new URL('SOURCE_PINS.json',moduleRoot),'utf8'));
export const FIXED_LOCAL_HISTORY_ROOT='/opt/lab/g39-history-local';
export const FIXED_LOCAL_INPUT_ROOT='/opt/lab/g39-inputs';
export const LOCAL_HISTORY_RUNTIME_PATHS=Object.freeze(Object.keys(expected.files));
const plans=new WeakMap();
const sha=b=>createHash('sha256').update(b).digest('hex');
const need=(ok,code)=>{if(!ok)throw Error(code);};
function keys(value,names,code){
 need(value!==null&&typeof value==='object'&&!Array.isArray(value)&&Object.getPrototypeOf(value)===Object.prototype,code);
 need(Object.keys(value).sort().join('\n')===names.slice().sort().join('\n'),code);
}
function relative(path){
 need(typeof path==='string'&&path!==''&&!path.includes('\\')&&!path.startsWith('/')&&!path.split('/').some(x=>!x||x==='.'||x==='..'),'G39_LAB_RELATIVE_PATH_INVALID');
 return path;
}
export function planLocalHistoryRuntimeLab(packet){
 keys(packet,['files','manifest'],'G39_LAB_PACKET_INVALID');
 need(FIXED_ROOT===FIXED_LOCAL_HISTORY_ROOT&&FIXED_PREFIX==='g39_history_synthetic_','G39_LAB_FIXED_SCOPE_CHANGED');
 need(packet.files instanceof Map&&packet.files.size===LOCAL_HISTORY_RUNTIME_PATHS.length,'G39_LAB_FILESET_CHANGED');
 need(LOCAL_HISTORY_RUNTIME_PATHS.length===25&&Object.keys(expected.manifest.files).length===24,'G39_LAB_CLOSED_COUNT_CHANGED');
 need(JSON.stringify([...packet.files.keys()].sort())===JSON.stringify([...LOCAL_HISTORY_RUNTIME_PATHS].sort()),'G39_LAB_FILESET_CHANGED');
 const files=new Map();
 for(const path of LOCAL_HISTORY_RUNTIME_PATHS){
  relative(path);const b=packet.files.get(path),pin=expected.files[path];
  keys(pin,['bytes','sha256'],'G39_LAB_FILE_PIN_INVALID');
  need(Buffer.isBuffer(b)&&Number.isSafeInteger(pin.bytes)&&pin.bytes>=0&&b.length===pin.bytes&&sha(b)===pin.sha256,'G39_LAB_BYTES_CHANGED');
  files.set(path,Buffer.from(b));
 }
 const manifest=JSON.parse(files.get('G39_BUILD.json').toString('utf8'));
 need(JSON.stringify(manifest)===JSON.stringify(packet.manifest)&&JSON.stringify(manifest)===JSON.stringify(expected.manifest),'G39_LAB_MANIFEST_CHANGED');
 need(manifest.fixed_root===FIXED_LOCAL_HISTORY_ROOT&&manifest.fixed_prefix===FIXED_PREFIX&&manifest.local_scope_only===true&&manifest.native_executed===false&&manifest.provider_accepted===false&&manifest.production_authorized===false,'G39_LAB_AUTHORITY_CHANGED');
 need(manifest.expected_checks.length===43&&new Set(manifest.expected_checks).size===43,'G39_LAB_CASESET_CHANGED');
 for(const path of Object.keys(manifest.files)){
  const b=files.get(path),pin=manifest.files[path];need(Buffer.isBuffer(b)&&b.length===pin.bytes&&sha(b)===pin.sha256,'G39_LAB_INNER_BINDING_CHANGED');
 }
 const rows=Object.freeze([...files].map(([path,b])=>Object.freeze({path,bytes:b.length,sha256:sha(b)})));
 const plan=Object.freeze({schema:'bsre-fixed-g39-local-history-runtime-lab-plan-v1',profile:'G39_LOCAL_HISTORY_ENGINEERING_ONLY',target:FIXED_LOCAL_HISTORY_ROOT,source_inputs:Object.keys(inputMap.files).length,files:rows,manifest_sha256:sha(files.get('G39_BUILD.json')),synthetic_only:true,local_scope_only:true,provider_accepted:false,production_authorized:false});
 plans.set(plan,files);return plan;
}
export function localHistoryRuntimeLabBytes(plan,path){
 const files=plans.get(plan);need(files instanceof Map&&files.has(path),'G39_LAB_PLAN_INVALID');return Buffer.from(files.get(path));
}
function directory(path){
 const s=lstatSync(path);need(s.isDirectory()&&!s.isSymbolicLink()&&realpathSync(path)===path,'G39_LAB_DIRECTORY_UNSAFE');return s;
}
function parents(path){let p=dirname(path);const names=[];while(p!=='/'){names.push(p);p=dirname(p);}directory('/');for(const v of names.reverse())directory(v);}
function absent(path){try{lstatSync(path);}catch(e){if(e.code==='ENOENT')return;throw e;}throw Error('G39_LAB_FRESH_DESTINATION_REQUIRED');}
function fileBytes(path){
 parents(path);const before=lstatSync(path);need(before.isFile()&&!before.isSymbolicLink()&&before.nlink===1&&realpathSync(path)===path,'G39_LAB_INPUT_UNSAFE');
 const bytes=readFileSync(path),after=lstatSync(path);
 need(after.dev===before.dev&&after.ino===before.ino&&after.isFile()&&after.nlink===1&&after.size===bytes.length&&realpathSync(path)===path,'G39_LAB_INPUT_CHANGED');return bytes;
}
function tree(root,paths,bytesFor){
 absent(root);mkdirSync(root,{recursive:false,mode:0o755});directory(root);const dirs=new Set();
 for(const p of paths){relative(p);let d=dirname(p);while(d!=='.'){dirs.add(d);d=dirname(d);}}
 for(const d of [...dirs].sort((a,b)=>a.split('/').length-b.split('/').length||a.localeCompare(b))){const p=join(root,d);directory(dirname(p));mkdirSync(p,{recursive:false,mode:0o755});directory(p);}
 for(const name of paths){
  const path=join(root,name),bytes=bytesFor(name);directory(dirname(path));need(path.startsWith(root+'/'),'G39_LAB_PATH_ESCAPE');let fd;
  try{fd=openSync(path,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o644);writeFileSync(fd,bytes);fsyncSync(fd);const s=fstatSync(fd),current=lstatSync(path);need(s.isFile()&&s.nlink===1&&s.size===bytes.length&&current.dev===s.dev&&current.ino===s.ino&&realpathSync(path)===path,'G39_LAB_WRITE_UNVERIFIED');}
  finally{if(fd!==undefined)closeSync(fd);}
  need(readFileSync(path).equals(bytes),'G39_LAB_READBACK_CHANGED');
 }
}
/** Zero arguments, root-only image build, fixed new aliases and runtime. No overwrite/delete. */
export function writeFixedLocalHistoryRuntimeLab(){
 need(arguments.length===0,'G39_LAB_NO_ARGUMENTS');
 need(process.platform==='linux'&&typeof process.getuid==='function'&&process.getuid()===0,'G39_LAB_BUILD_ROOT_REQUIRED');
 need(Number.isInteger(constants.O_NOFOLLOW),'G39_LAB_NOFOLLOW_REQUIRED');
 for(const p of ['/','/opt','/opt/lab'])directory(p);absent(FIXED_LOCAL_INPUT_ROOT);absent(FIXED_LOCAL_HISTORY_ROOT);
 keys(inputMap.files,Object.keys(pins.files),'G39_LAB_SOURCE_FILESET_CHANGED');need(Object.keys(pins.files).length===26,'G39_LAB_SOURCE_COUNT_CHANGED');
 const inputs=new Map();
 for(const [path,row]of Object.entries(inputMap.files)){
  relative(path);need(path.startsWith('tools/')&&row.fixed_alias===join(FIXED_LOCAL_INPUT_ROOT,path)&&typeof row.image_source==='string'&&row.image_source.startsWith('/opt/lab/')&&!row.image_source.includes('/../'),'G39_LAB_INPUT_MAP_INVALID');
  const b=fileBytes(row.image_source),pin=pins.files[path];need(row.bytes===pin.bytes&&row.sha256===pin.sha256&&b.length===pin.bytes&&sha(b)===pin.sha256,'G39_LAB_SOURCE_PIN_CHANGED');inputs.set(path,b);
 }
 tree(FIXED_LOCAL_INPUT_ROOT,[...inputs.keys()],p=>inputs.get(p));
 const plan=planLocalHistoryRuntimeLab(build(FIXED_LOCAL_INPUT_ROOT));
 tree(FIXED_LOCAL_HISTORY_ROOT,LOCAL_HISTORY_RUNTIME_PATHS,p=>localHistoryRuntimeLabBytes(plan,p));
 for(const [path,row]of Object.entries(inputMap.files))need(fileBytes(row.image_source).equals(inputs.get(path)),'G39_LAB_ORIGINAL_INPUT_CHANGED');
 return plan;
}
if(process.argv[1]&&pathToFileURL(process.argv[1]).href===import.meta.url){
 need(process.argv.length===2,'G39_LAB_NO_ARGUMENTS');process.stdout.write(JSON.stringify(writeFixedLocalHistoryRuntimeLab())+'\n');
}
