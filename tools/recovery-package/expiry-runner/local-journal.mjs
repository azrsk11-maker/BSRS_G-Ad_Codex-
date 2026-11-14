// Explicit synthetic POSIX storage; no scheduler, production admission or stale-lock recovery.
import {createHash,randomBytes} from 'node:crypto';
import {constants} from 'node:fs';
import {lstat,realpath,open,mkdir,readdir,rename,unlink,rmdir} from 'node:fs/promises';
import {resolve,join,basename} from 'node:path';
import {SOURCE} from '../package.mjs';
import {PURPOSE,LIMITS,initialState} from './runner.mjs';

export const LOCAL_FORMAT='SYNTHETIC_LOCAL_EXPIRY_JOURNAL_V1';
export const LOCAL_FILES=Object.freeze({identity:'SYNTHETIC_EXPIRY_JOURNAL_ID.json',state:'SYNTHETIC_EXPIRY_JOURNAL_STATE.json',lock:'.synthetic-expiry.lock'});
const RUN_ACK='USE_SYNTHETIC_LOCAL_JOURNAL',INIT_ACK='INITIALIZE_SYNTHETIC_LOCAL_JOURNAL';
const HASH=/^[a-f0-9]{64}$/,MAX_BYTES=LIMITS.stateBytes+2048;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const fail=code=>{throw Error(code);};
const need=(value,code)=>{if(!value)fail(code);};
const exact=(value,keys)=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&
 Object.keys(value).length===keys.length&&keys.every(key=>Object.hasOwn(value,key));
const clone=value=>JSON.parse(JSON.stringify(value));
const safeCodes=new Set(['JOURNAL_DISABLED','SYNTHETIC_JOURNAL_REQUIRED','LOCAL_JOURNAL_UNSUPPORTED',
 'JOURNAL_DIRECTORY_REQUIRED','JOURNAL_DIRECTORY_CHANGED','JOURNAL_DIRECTORY_UNRECONCILED',
 'JOURNAL_FILE_REQUIRED','JOURNAL_FILE_CHANGED','JOURNAL_IDENTITY_CHANGED','JOURNAL_STATE_INVALID',
 'JOURNAL_CURRENT_STATE_CHANGED','JOURNAL_LOCK_HELD','JOURNAL_LOCK_CHANGED','JOURNAL_TX_CLOSED',
 'JOURNAL_LOAD_REQUIRED','JOURNAL_CALLBACK_FAILED','JOURNAL_STORAGE_UNAVAILABLE']);
const sanitized=error=>Error(safeCodes.has(error?.message)?error.message:'JOURNAL_STORAGE_UNAVAILABLE');
const same=(a,b)=>a.dev===b.dev&&a.ino===b.ino;
const unchanged=(a,b)=>same(a,b)&&a.size===b.size&&a.mtimeMs===b.mtimeMs&&a.ctimeMs===b.ctimeMs;
const ownerDir=stat=>stat.isDirectory()&&!stat.isSymbolicLink()&&stat.uid===process.getuid()&&(stat.mode&0o7777)===0o700;
const ownerFile=stat=>stat.isFile()&&!stat.isSymbolicLink()&&stat.uid===process.getuid()&&(stat.mode&0o7777)===0o600&&stat.nlink===1;
function allowed(options,authorization){
 need(options?.enabled===true&&options.authorization===authorization,'JOURNAL_DISABLED');
 need((options.source??SOURCE)===SOURCE&&(options.purpose??PURPOSE)===PURPOSE,'SYNTHETIC_JOURNAL_REQUIRED');
 if(process.platform==='win32'||typeof process.getuid!=='function'||!constants.O_NOFOLLOW||!constants.O_DIRECTORY)
  fail('LOCAL_JOURNAL_UNSUPPORTED');
}
async function rootPath(directory,expected=null){
 need(typeof directory==='string','JOURNAL_DIRECTORY_REQUIRED');
 const path=resolve(directory);
 need(/^bsre-synthetic-expiry-journal-[A-Za-z0-9_-]{6,80}$/.test(basename(path)),'JOURNAL_DIRECTORY_REQUIRED');
 const stat=await lstat(path);
 need(ownerDir(stat)&&await realpath(path)===path,'JOURNAL_DIRECTORY_REQUIRED');
 if(expected)need(same(stat,expected),'JOURNAL_DIRECTORY_CHANGED');
 return {path,stat};
}
async function syncDirectory(path,expected){
 const fd=await open(path,constants.O_RDONLY|constants.O_DIRECTORY|constants.O_NOFOLLOW);
 try{const before=await fd.stat();need(ownerDir(before)&&same(before,expected),'JOURNAL_DIRECTORY_CHANGED');await fd.sync();need(ownerDir(await fd.stat()),'JOURNAL_DIRECTORY_CHANGED');}
 finally{await fd.close();}
}
async function readOwned(path,max=MAX_BYTES){
 const before=await lstat(path);need(ownerFile(before)&&before.size>0&&before.size<=max,'JOURNAL_FILE_REQUIRED');
 const fd=await open(path,constants.O_RDONLY|constants.O_NOFOLLOW);
 try{
  need(unchanged(before,await fd.stat()),'JOURNAL_FILE_CHANGED');
  const bytes=Buffer.alloc(before.size);let offset=0;
  while(offset<bytes.length){const result=await fd.read(bytes,offset,bytes.length-offset,offset);need(result.bytesRead>0,'JOURNAL_FILE_CHANGED');offset+=result.bytesRead;}
  need((await fd.read(Buffer.alloc(1),0,1,offset)).bytesRead===0,'JOURNAL_FILE_CHANGED');
  const after=await lstat(path);need(ownerFile(after)&&unchanged(before,after)&&unchanged(before,await fd.stat()),'JOURNAL_FILE_CHANGED');
  return {bytes,stat:after};
 }finally{await fd.close();}
}
async function writeNew(path,bytes){
 const fd=await open(path,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);
 try{
  const stat=await fd.stat();need(ownerFile(stat),'JOURNAL_FILE_REQUIRED');
  await fd.writeFile(bytes);await fd.sync();
  const after=await lstat(path);need(ownerFile(after)&&same(stat,after),'JOURNAL_FILE_CHANGED');
  return after;
 }finally{await fd.close();}
}
function json(bytes){try{return JSON.parse(bytes.toString('utf8'));}catch{fail('JOURNAL_STATE_INVALID');}}
/** Storage validates bounded JSON/root identity. The runner remains the business-schema authority. */
export function encodeLocalState(state){
 let nodes=0,bytes=0;
 const count=amount=>{bytes+=amount;need(bytes<=LIMITS.stateBytes,'JOURNAL_STATE_INVALID');};
 const stringBytes=value=>{
  need(value.length<=2048,'JOURNAL_STATE_INVALID');let size=Buffer.byteLength(value)+2;
  for(let i=0;i<value.length;i++){
   const code=value.charCodeAt(i);
   if(code<32)size+=5;else if(code===34||code===92)size++;
   else if(code>=0xd800&&code<=0xdbff){if(i+1<value.length&&value.charCodeAt(i+1)>=0xdc00&&value.charCodeAt(i+1)<=0xdfff)i++;else size+=3;}
   else if(code>=0xdc00&&code<=0xdfff)size+=3;
  }
  return size;
 };
 const copy=(value,depth=0)=>{
  need(++nodes<=20000&&depth<=12,'JOURNAL_STATE_INVALID');
  if(value===null){count(4);return value;}
  if(typeof value==='boolean'){count(value?4:5);return value;}
  if(typeof value==='string'){count(stringBytes(value));return value;}
  if(typeof value==='number'){need(Number.isSafeInteger(value),'JOURNAL_STATE_INVALID');count(String(value).length);return value;}
  need(typeof value==='object','JOURNAL_STATE_INVALID');
  const array=Array.isArray(value),prototype=Object.getPrototypeOf(value);
  need(array?(prototype===Array.prototype||prototype===null):(prototype===Object.prototype||prototype===null),'JOURNAL_STATE_INVALID');
  if(array){
   const length=Object.getOwnPropertyDescriptor(value,'length')?.value;
   need(Number.isInteger(length)&&length>=0&&length<=LIMITS.jobs,'JOURNAL_STATE_INVALID');
   const keys=Reflect.ownKeys(value);need(keys.length===length+1,'JOURNAL_STATE_INVALID');
   const result=[];Object.setPrototypeOf(result,null);count(2+Math.max(0,length-1));
   for(let i=0;i<length;i++){const d=Object.getOwnPropertyDescriptor(value,String(i));need(d&&Object.hasOwn(d,'value')&&d.enumerable,'JOURNAL_STATE_INVALID');result[i]=copy(d.value,depth+1);}
   return result;
  }
  const keys=Reflect.ownKeys(value);need(keys.length<=100,'JOURNAL_STATE_INVALID');
  const result=Object.create(null);count(2+Math.max(0,keys.length-1));
  for(const key of keys){
   need(typeof key==='string'&&key!=='toJSON'&&key.length<=128,'JOURNAL_STATE_INVALID');
   const d=Object.getOwnPropertyDescriptor(value,key);need(d&&Object.hasOwn(d,'value')&&d.enumerable,'JOURNAL_STATE_INVALID');
   count(stringBytes(key)+1);result[key]=copy(d.value,depth+1);
  }
  return result;
 };
 try{
  const captured=copy(state);
  need(exact(captured,['version','source','purpose','lastNowMs','jobs'])&&captured.version===1&&captured.source===SOURCE&&
   captured.purpose===PURPOSE&&Number.isSafeInteger(captured.lastNowMs)&&captured.lastNowMs>=0&&
   Array.isArray(captured.jobs)&&captured.jobs.length<=LIMITS.jobs,'JOURNAL_STATE_INVALID');
  const encoded=Buffer.from(JSON.stringify(captured));need(encoded.length<=LIMITS.stateBytes,'JOURNAL_STATE_INVALID');return encoded;
 }catch{fail('JOURNAL_STATE_INVALID');}
}
function envelope(state,journalId,generation){
 return Buffer.from(JSON.stringify({format:LOCAL_FORMAT,journalId,generation,stateSha256:digest(encodeLocalState(state)),state}));
}
function decode(bytes,journalId){
 const value=json(bytes);
 need(exact(value,['format','journalId','generation','stateSha256','state'])&&value.format===LOCAL_FORMAT&&
  value.journalId===journalId&&Number.isSafeInteger(value.generation)&&value.generation>0&&
  HASH.test(value.stateSha256)&&digest(encodeLocalState(value.state))===value.stateSha256,'JOURNAL_STATE_INVALID');
 return value;
}
function identityBytes(journalId){return Buffer.from(JSON.stringify({format:LOCAL_FORMAT,source:SOURCE,purpose:PURPOSE,journalId}));}
async function checkIdentity(root,journalId){
 const value=await readOwned(join(root.path,LOCAL_FILES.identity),2048);
 need(value.bytes.equals(identityBytes(journalId)),'JOURNAL_IDENTITY_CHANGED');return value;
}
async function contents(root,initial=false){
 const names=await readdir(root.path);
 const allowedNames=initial?[LOCAL_FILES.lock]:Object.values(LOCAL_FILES);
 need(names.every(name=>allowedNames.includes(name)),'JOURNAL_DIRECTORY_UNRECONCILED');
}
async function lock(root,journalId){
 const path=join(root.path,LOCAL_FILES.lock);
 try{await mkdir(path,{mode:0o700});}catch(error){if(error.code==='EEXIST')fail('JOURNAL_LOCK_HELD');throw error;}
 const stat=await lstat(path);need(ownerDir(stat),'JOURNAL_LOCK_CHANGED');
 const bytes=Buffer.from(JSON.stringify({format:LOCAL_FORMAT,journalId,token:randomBytes(32).toString('hex')}));
 // Failure before the owner record is verified leaves the lock for explicit reconciliation.
 const ownerStat=await writeNew(join(path,'owner.json'),bytes);await syncDirectory(path,stat);await syncDirectory(root.path,root.stat);
 const owner=await readOwned(join(path,'owner.json'),2048);
 need(unchanged(ownerStat,owner.stat)&&owner.bytes.equals(bytes)&&ownerDir(await lstat(path))&&same(await lstat(path),stat),'JOURNAL_LOCK_CHANGED');
 return {path,stat,bytes,ownerStat};
}
async function unlock(root,owned){
 await rootPath(root.path,root.stat);const current=await lstat(owned.path);
 need(ownerDir(current)&&same(current,owned.stat),'JOURNAL_LOCK_CHANGED');
 const owner=await readOwned(join(owned.path,'owner.json'),2048);
 need(unchanged(owned.ownerStat,owner.stat)&&owner.bytes.equals(owned.bytes),'JOURNAL_LOCK_CHANGED');
 need((await readdir(owned.path)).join('|')==='owner.json','JOURNAL_LOCK_CHANGED');
 need(same(await lstat(owned.path),owned.stat),'JOURNAL_LOCK_CHANGED');
 await unlink(join(owned.path,'owner.json'));await rmdir(owned.path);await syncDirectory(root.path,root.stat);
}

/** Initializes only a new empty pre-existing synthetic directory; never repairs partial state. */
export async function initializeLocalJournal(directory,options={}){
 let root,owned,retain=false;
 try{
  allowed(options,INIT_ACK);root=await rootPath(directory);need((await readdir(root.path)).length===0,'JOURNAL_DIRECTORY_UNRECONCILED');
  const journalId=randomBytes(32).toString('hex');owned=await lock(root,journalId);
  try{
   await contents(root,true);await writeNew(join(root.path,LOCAL_FILES.identity),identityBytes(journalId));
   await writeNew(join(root.path,LOCAL_FILES.state),envelope(initialState(),journalId,1));
   await rootPath(root.path,root.stat);await syncDirectory(root.path,root.stat);
   await checkIdentity(root,journalId);
   return {journalId,source:SOURCE,purpose:PURPOSE,productionAcceptance:false,providerCustodyAccepted:false};
  }catch(error){retain=true;throw error;}
 }catch(error){throw sanitized(error);}
 finally{if(owned&&!retain){try{await unlock(root,owned);}catch(error){throw sanitized(error);}}}
}

/** Real local storage only. Save acknowledgement follows file+directory fsync and readback. */
export function createLocalJournal(directory,options={}){
 const config=Object.freeze({...options});
 let remembered=null;
 return Object.freeze({source:SOURCE,purpose:PURPOSE,productionAcceptance:false,
  async exclusive(callback){
   let root,owned,retain=false,active=false,tail=Promise.resolve(),poison=null;
   try{
    allowed(config,RUN_ACK);need(typeof callback==='function'&&HASH.test(config.journalId),'SYNTHETIC_JOURNAL_REQUIRED');
    root=await rootPath(directory);owned=await lock(root,config.journalId);await contents(root);
    const id=await checkIdentity(root,config.journalId);
    let current=await readOwned(join(root.path,LOCAL_FILES.state));let value=decode(current.bytes,config.journalId);
    if(remembered)need(value.generation>remembered.generation||value.generation===remembered.generation&&digest(current.bytes)===remembered.digest,'JOURNAL_CURRENT_STATE_CHANGED');
    remembered={generation:value.generation,digest:digest(current.bytes)};
    let loaded=false;active=true;
    const enqueue=operation=>{
     if(!active)return Promise.reject(Error('JOURNAL_TX_CLOSED'));
     const next=tail.then(async()=>{if(poison)throw poison;try{return await operation();}catch(error){throw sanitized(error);}});
     tail=next.catch(error=>{poison=sanitized(error);});return next;
    };
    const tx=Object.freeze({load:()=>enqueue(async()=>{loaded=true;return clone(value.state);}),
     save:state=>{
      if(!active)return Promise.reject(Error('JOURNAL_TX_CLOSED'));
      let captured;
      try{captured=JSON.parse(encodeLocalState(state));}catch(error){return enqueue(async()=>{throw error;});}
      return enqueue(async()=>{
      need(loaded,'JOURNAL_LOAD_REQUIRED');
      need(value.generation<Number.MAX_SAFE_INTEGER,'JOURNAL_STATE_INVALID');
      await rootPath(root.path,root.stat);const nowId=await checkIdentity(root,config.journalId);
      need(unchanged(id.stat,nowId.stat),'JOURNAL_IDENTITY_CHANGED');
      const before=await readOwned(join(root.path,LOCAL_FILES.state));
      need(unchanged(current.stat,before.stat)&&before.bytes.equals(current.bytes),'JOURNAL_CURRENT_STATE_CHANGED');
      const bytes=envelope(captured,config.journalId,value.generation+1);
      const temp=join(root.path,'.synthetic-expiry.state-'+randomBytes(32).toString('hex')+'.tmp');
      const written=await writeNew(temp,bytes);await rootPath(root.path,root.stat);
      const last=await readOwned(join(root.path,LOCAL_FILES.state));
      need(unchanged(current.stat,last.stat)&&last.bytes.equals(current.bytes),'JOURNAL_CURRENT_STATE_CHANGED');
      await rename(temp,join(root.path,LOCAL_FILES.state));await syncDirectory(root.path,root.stat);
      current=await readOwned(join(root.path,LOCAL_FILES.state));
      need(same(written,current.stat)&&current.bytes.equals(bytes),'JOURNAL_CURRENT_STATE_CHANGED');
      value=decode(current.bytes,config.journalId);remembered={generation:value.generation,digest:digest(current.bytes)};
     });}});
    let result,callbackFailed=false;
    try{result=await callback(tx);}catch{callbackFailed=true;}
    active=false;await tail;
    if(poison){retain=true;throw poison;}
    need(!callbackFailed,'JOURNAL_CALLBACK_FAILED');return result;
   }catch(error){throw sanitized(error);}
   finally{
    active=false;
    if(owned&&!retain){try{await unlock(root,owned);}catch(error){throw sanitized(error);}}
   }
  }
 });
}
