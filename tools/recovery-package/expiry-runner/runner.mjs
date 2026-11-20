// Disabled synthetic orchestration. No scheduler, provider client, mail or key store.
import {createHash} from 'node:crypto';
import {constants} from 'node:fs';
import {lstat,realpath,open} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {SOURCE,MAX_SNAPSHOT_BYTES,deleteExpiredOwnerOnlyPackage} from '../package.mjs';

export const PURPOSE='SYNTHETIC_RECOVERY_COPY_EXPIRY_V1';
export const LIMITS=Object.freeze({jobs:32,batch:8,attempts:3,retryMs:60000,stateBytes:131072});
const ACK='RUN_SYNTHETIC_EXPIRY_ONLY';
const HASH=/^[a-f0-9]{64}$/;
const NAME=/^SYNTHETIC_[A-Za-z0-9][A-Za-z0-9._-]{0,80}\.bsre$/;
const time=n=>Number.isSafeInteger(n)&&n>0&&n<=Number.MAX_SAFE_INTEGER-LIMITS.retryMs;
const hash=value=>createHash('sha256').update(value).digest('hex');
const fail=code=>{throw Error(code);};
const need=(condition,code)=>{if(!condition)fail(code);};
const exact=(value,keys)=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&
 Object.keys(value).sort().join('|')===[...keys].sort().join('|');
const clone=value=>JSON.parse(JSON.stringify(value));
const SAFE_ERRORS=new Set(['PACKAGE_IDENTITY_CHANGED','ABSENCE_WITHOUT_INTENT','INVALID_PROVIDER_RECEIPT',
 'OWNER_ONLY_FILESYSTEM_UNSUPPORTED','OWNER_ONLY_PATH_REQUIRED','OWNER_ONLY_DIRECTORY_REQUIRED',
 'OWNER_ONLY_FILE_REQUIRED','OWNER_ONLY_PATH_CHANGED','INVALID_RECOVERY_PACKAGE','RECOVERY_NOT_EXPIRED',
 'KEY_UNAVAILABLE','EXPIRY_PROVIDER_FAILURE']);

export function expiryJob({filename,packageSha256,expiresAtMs,source=SOURCE,purpose=PURPOSE}={}){
 need(source===SOURCE&&purpose===PURPOSE,'SYNTHETIC_PURPOSE_REQUIRED');
 need(typeof filename==='string'&&NAME.test(filename),'SYNTHETIC_BASENAME_REQUIRED');
 need(typeof packageSha256==='string'&&HASH.test(packageSha256)&&time(expiresAtMs),'INVALID_EXPIRY_MANIFEST');
 const manifest={source,purpose,filename,packageSha256,expiresAtMs};
 return Object.freeze({...manifest,id:hash(JSON.stringify(manifest))});
}
function checkJob(job){
 need(exact(job,['source','purpose','filename','packageSha256','expiresAtMs','id']),'INVALID_EXPIRY_MANIFEST');
 need(JSON.stringify(job)===JSON.stringify(expiryJob(job)),'INVALID_EXPIRY_MANIFEST');
}
export const initialState=()=>({version:1,source:SOURCE,purpose:PURPOSE,lastNowMs:0,jobs:[]});
function checkState(state){
 need(exact(state,['version','source','purpose','lastNowMs','jobs'])&&state.version===1&&
  state.source===SOURCE&&state.purpose===PURPOSE&&Number.isSafeInteger(state.lastNowMs)&&state.lastNowMs>=0&&
  Array.isArray(state.jobs)&&state.jobs.length<=LIMITS.jobs,'INVALID_EXPIRY_STATE');
 need(Buffer.byteLength(JSON.stringify(state))<=LIMITS.stateBytes,'EXPIRY_STATE_TOO_LARGE');
 const ids=new Set(),names=new Set();
 for(const row of state.jobs){
  need(exact(row,['job','status','attempts','nextAttemptMs','intentAtMs','lastError','completion','alert']),
   'INVALID_EXPIRY_STATE');checkJob(row.job);
  need(!ids.has(row.job.id)&&!names.has(row.job.filename),'DUPLICATE_EXPIRY_JOB');
  ids.add(row.job.id);names.add(row.job.filename);
  need(['PENDING','INTENT','RETRY','COMPLETE','HELD'].includes(row.status)&&Number.isInteger(row.attempts)&&
   row.attempts>=0&&row.attempts<=LIMITS.attempts&&time(row.nextAttemptMs)&&
   (row.intentAtMs===null||time(row.intentAtMs))&&(row.lastError===null||SAFE_ERRORS.has(row.lastError)),
   'INVALID_EXPIRY_STATE');
  need(row.nextAttemptMs>=row.job.expiresAtMs&&(row.intentAtMs===null||
   row.attempts>0&&row.intentAtMs>=row.job.expiresAtMs&&row.intentAtMs<=state.lastNowMs),'INVALID_EXPIRY_STATE');
  need(row.status!=='PENDING'||row.attempts===0&&row.intentAtMs===null,'INVALID_EXPIRY_STATE');
  need(row.status!=='INTENT'||row.attempts>0&&row.intentAtMs!==null,'INVALID_EXPIRY_STATE');
  need(!['RETRY','HELD'].includes(row.status)||row.attempts>0&&row.lastError!==null&&row.alert!==null,
   'INVALID_EXPIRY_STATE');
  need((row.status==='COMPLETE')===(row.completion!==null),'INVALID_EXPIRY_STATE');
  if(row.completion!==null)need(exact(row.completion,['kind','atMs'])&&
   ['AUTHENTICATED_EXPIRY_DELETED','ABSENCE_RECONCILED_AFTER_INTENT'].includes(row.completion.kind)&&
   time(row.completion.atMs)&&row.intentAtMs!==null&&row.completion.atMs>=row.intentAtMs&&
   row.completion.atMs<=state.lastNowMs&&row.lastError===null,'INVALID_EXPIRY_STATE');
  if(row.alert!==null)need(exact(row.alert,['id','code','attempt','createdAtMs','acknowledgedAtMs'])&&
   Number.isInteger(row.alert.attempt)&&row.alert.attempt>0&&row.alert.attempt<=row.attempts&&
   row.alert.id===hash(row.job.id+':'+row.alert.code+':'+row.alert.attempt)&&SAFE_ERRORS.has(row.alert.code)&&time(row.alert.createdAtMs)&&
   row.alert.createdAtMs<=state.lastNowMs&&(row.alert.acknowledgedAtMs===null||
    time(row.alert.acknowledgedAtMs)&&row.alert.acknowledgedAtMs>=row.alert.createdAtMs&&row.alert.acknowledgedAtMs<=state.lastNowMs),
   'INVALID_EXPIRY_STATE');
  need(row.completion===null||row.alert===null||row.alert.createdAtMs<=row.completion.atMs,'INVALID_EXPIRY_STATE');
 }
 return state;
}
function result(state,enabled,error=null){
 const rows=state?.jobs??[];
 return {scope:SOURCE,purpose:PURPOSE,mode:enabled?'SYNTHETIC_EXPLICIT_RUN':'PLAN_ONLY',
  status:error?'HOLD':!enabled?'PLAN_ONLY':rows.some(r=>r.status==='HELD')?'HOLD':
   rows.some(r=>r.status==='RETRY')?'RETRY':rows.some(r=>r.status!=='COMPLETE')?'PENDING':'COMPLETE',
  error,counts:{jobs:rows.length,complete:rows.filter(r=>r.status==='COMPLETE').length,
   retry:rows.filter(r=>r.status==='RETRY').length,held:rows.filter(r=>r.status==='HELD').length,
   pendingAlerts:rows.filter(r=>r.alert&&r.alert.acknowledgedAtMs===null).length},
  productionAcceptance:false,expirySchedulingAccepted:false,providerCustodyAccepted:false};
}
function requireJournal(journal){
 need(journal?.source===SOURCE&&journal?.purpose===PURPOSE&&typeof journal.exclusive==='function',
  'SYNTHETIC_JOURNAL_REQUIRED');
}
async function save(tx,state){checkState(state);await tx.save(clone(state));}
function failed(row,code,nowMs){
 row.lastError=code;
 row.status=row.attempts>=LIMITS.attempts||['PACKAGE_IDENTITY_CHANGED','ABSENCE_WITHOUT_INTENT'].includes(code)?'HELD':'RETRY';
 row.nextAttemptMs=nowMs+LIMITS.retryMs;
 if(row.alert===null||row.alert.acknowledgedAtMs!==null)row.alert={id:hash(row.job.id+':'+code+':'+row.attempts),
  code,attempt:row.attempts,createdAtMs:nowMs,acknowledgedAtMs:null};
}

/** Journal adapter must provide exclusive, durable load/save; no adapter is implied by a flag. */
export async function runExpiry({jobs=[],journal,provider,nowMs,enabled=false,authorization=null,
 source=SOURCE,purpose=PURPOSE,maxJobs=LIMITS.batch}={}){
 let state=null;
 try{
  need(source===SOURCE&&purpose===PURPOSE,'SYNTHETIC_PURPOSE_REQUIRED');
  need(time(nowMs)&&Array.isArray(jobs)&&jobs.length<=LIMITS.jobs,'INVALID_EXPIRY_REQUEST');
  for(const job of jobs)checkJob(job);
  need(Number.isInteger(maxJobs)&&maxJobs>0&&maxJobs<=LIMITS.batch,'INVALID_BATCH_LIMIT');
  if(!enabled)return result(null,false);
  need(enabled===true&&authorization===ACK,'EXPLICIT_SYNTHETIC_RUN_REQUIRED');
  requireJournal(journal);
  need(provider?.source===SOURCE&&provider?.purpose===PURPOSE&&typeof provider.inspect==='function'&&
   typeof provider.expire==='function','SYNTHETIC_PROVIDER_REQUIRED');
  return await journal.exclusive(async tx=>{
   need(typeof tx?.load==='function'&&typeof tx?.save==='function','SYNTHETIC_JOURNAL_REQUIRED');
   state=checkState(clone(await tx.load()));
   need(nowMs>=state.lastNowMs,'CLOCK_ROLLBACK');state.lastNowMs=nowMs;
   for(const job of jobs){
    const prior=state.jobs.find(row=>row.job.filename===job.filename);
    need(!prior||JSON.stringify(prior.job)===JSON.stringify(job),'EXPIRY_FILENAME_REUSE_FORBIDDEN');
    if(!prior)state.jobs.push({job:clone(job),status:'PENDING',attempts:0,nextAttemptMs:job.expiresAtMs,
     intentAtMs:null,lastError:null,completion:null,alert:null});
   }
   await save(tx,state); // Registration and clock are durable before any provider operation.
   let processed=0;
   for(const row of state.jobs){
    if(processed>=maxJobs)break;
    if(['COMPLETE','HELD'].includes(row.status)||nowMs<row.nextAttemptMs||nowMs<row.job.expiresAtMs)continue;
    processed++;
    let absent=false;
    try{
     const seen=await provider.inspect(clone(row.job));
     need(exact(seen,['state'])&&seen.state==='ABSENT'||
      exact(seen,['state','packageSha256'])&&seen.state==='PRESENT'&&HASH.test(seen.packageSha256),
      'INVALID_PROVIDER_RECEIPT');
     if(seen.state==='ABSENT'){
      need(row.intentAtMs!==null,'ABSENCE_WITHOUT_INTENT');
      absent=true;
     }else{
      need(seen.packageSha256===row.job.packageSha256,'PACKAGE_IDENTITY_CHANGED');
     }
    }catch(error){
     row.attempts=Math.min(row.attempts+1,LIMITS.attempts);
     failed(row,SAFE_ERRORS.has(error?.message)?error.message:'EXPIRY_PROVIDER_FAILURE',nowMs);
     await save(tx,state);continue;
    }
    if(absent){row.status='COMPLETE';row.completion={kind:'ABSENCE_RECONCILED_AFTER_INTENT',atMs:nowMs};row.lastError=null;await save(tx,state);continue;}
    if(row.attempts>=LIMITS.attempts){failed(row,'EXPIRY_PROVIDER_FAILURE',nowMs);await save(tx,state);continue;}
    row.attempts++;row.status='INTENT';row.intentAtMs??=nowMs;
    await save(tx,state); // Lost acknowledgement/restart always has a prior exact-file intent.
    try{
     const receipt=await provider.expire(clone(row.job),nowMs);
     need(exact(receipt,['deleted','expiresAtMs','productionAcceptance'])&&receipt.deleted===true&&
      receipt.expiresAtMs===row.job.expiresAtMs&&receipt.productionAcceptance===false,'INVALID_PROVIDER_RECEIPT');
     row.status='COMPLETE';row.completion={kind:'AUTHENTICATED_EXPIRY_DELETED',atMs:nowMs};row.lastError=null;
    }catch(error){failed(row,SAFE_ERRORS.has(error?.message)?error.message:'EXPIRY_PROVIDER_FAILURE',nowMs);}
    await save(tx,state);
   }
   return result(state,true);
  });
 }catch(error){
  const known=new Set(['SYNTHETIC_PURPOSE_REQUIRED','SYNTHETIC_BASENAME_REQUIRED','INVALID_EXPIRY_MANIFEST',
   'INVALID_EXPIRY_STATE','EXPIRY_STATE_TOO_LARGE','DUPLICATE_EXPIRY_JOB','INVALID_EXPIRY_REQUEST',
   'INVALID_BATCH_LIMIT','EXPLICIT_SYNTHETIC_RUN_REQUIRED','SYNTHETIC_JOURNAL_REQUIRED',
   'SYNTHETIC_PROVIDER_REQUIRED','CLOCK_ROLLBACK','EXPIRY_FILENAME_REUSE_FORBIDDEN']);
  return result(null,enabled===true,known.has(error?.message)?error.message:'JOURNAL_OR_RUN_UNAVAILABLE');
 }
}

/** An outbox acknowledgement, not delivery, mail, paging or proof anyone saw the alert. */
export async function acknowledgeAlert(journal,receiptId,{nowMs}={}){
 try{
  requireJournal(journal);need(typeof receiptId==='string'&&HASH.test(receiptId)&&time(nowMs),'INVALID_ALERT_ACK');
  return await journal.exclusive(async tx=>{
   const state=checkState(clone(await tx.load()));need(nowMs>=state.lastNowMs,'CLOCK_ROLLBACK');
   const row=state.jobs.find(item=>item.alert?.id===receiptId);need(row,'UNKNOWN_ALERT_RECEIPT');
   row.alert.acknowledgedAtMs??=nowMs;state.lastNowMs=nowMs;await save(tx,state);
   return {acknowledged:true,productionAcceptance:false,deliveryVerified:false};
  });
 }catch(error){
  const known=new Set(['SYNTHETIC_JOURNAL_REQUIRED','INVALID_ALERT_ACK','UNKNOWN_ALERT_RECEIPT','CLOCK_ROLLBACK']);
  return {acknowledged:false,error:known.has(error?.message)?error.message:'ALERT_ACK_UNAVAILABLE',
   productionAcceptance:false,deliveryVerified:false};
 }
}

async function privatePath(directory,job){
 checkJob(job);
 if(process.platform==='win32'||typeof process.getuid!=='function'||!constants.O_NOFOLLOW)
  fail('OWNER_ONLY_FILESYSTEM_UNSUPPORTED');
 need(typeof directory==='string','OWNER_ONLY_PATH_REQUIRED');
 const root=resolve(directory),dir=await lstat(root);
 need(dir.isDirectory()&&!dir.isSymbolicLink()&&dir.uid===process.getuid()&&(dir.mode&0o7777)===0o700&&
  await realpath(root)===root,'OWNER_ONLY_DIRECTORY_REQUIRED');
 return {root,dir,target:join(root,job.filename)};
}
/** Existing local synthetic cleanup only; assumes a trusted same-user process/OS. */
export function ownerFileProvider(directory,keyForJob){
 need(typeof keyForJob==='function','KEY_RESOLVER_REQUIRED');
 const provider={source:SOURCE,purpose:PURPOSE,
  async inspect(job){
   const {root,dir,target}=await privatePath(directory,job);
   let file;try{file=await lstat(target);}catch(error){
    if(error.code==='ENOENT'){
     const current=await privatePath(directory,job);need(current.dir.dev===dir.dev&&current.dir.ino===dir.ino,'OWNER_ONLY_PATH_CHANGED');
     return {state:'ABSENT'};
    }throw error;
   }
   need(file.isFile()&&!file.isSymbolicLink()&&file.uid===process.getuid()&&(file.mode&0o7777)===0o600&&
    file.nlink===1&&file.size>0&&file.size<=MAX_SNAPSHOT_BYTES+2048,'OWNER_ONLY_FILE_REQUIRED');
   const fd=await open(target,constants.O_RDONLY|constants.O_NOFOLLOW);
   try{
    const actual=await fd.stat();need(actual.dev===file.dev&&actual.ino===file.ino&&actual.size===file.size&&
     actual.isFile()&&actual.uid===file.uid&&(actual.mode&0o7777)===0o600&&actual.nlink===1,'OWNER_ONLY_PATH_CHANGED');
    const bytes=Buffer.alloc(file.size);let offset=0;
    while(offset<bytes.length){const {bytesRead}=await fd.read(bytes,offset,bytes.length-offset,offset);need(bytesRead>0,'OWNER_ONLY_PATH_CHANGED');offset+=bytesRead;}
    need((await fd.read(Buffer.alloc(1),0,1,offset)).bytesRead===0,'OWNER_ONLY_PATH_CHANGED');
    const after=await lstat(target),parent=await lstat(root);
    need(after.dev===file.dev&&after.ino===file.ino&&!after.isSymbolicLink()&&after.size===file.size&&
     after.uid===file.uid&&(after.mode&0o7777)===0o600&&after.nlink===1&&
     after.mtimeMs===file.mtimeMs&&after.ctimeMs===file.ctimeMs&&parent.dev===dir.dev&&parent.ino===dir.ino&&
     parent.uid===dir.uid&&(parent.mode&0o7777)===0o700&&await realpath(root)===root,'OWNER_ONLY_PATH_CHANGED');
    return {state:'PRESENT',packageSha256:hash(bytes)};
   }finally{await fd.close();}
  },
  async expire(job,nowMs){
   const seen=await provider.inspect(job);need(seen.state==='PRESENT'&&seen.packageSha256===job.packageSha256,'PACKAGE_IDENTITY_CHANGED');
   let key;try{key=await keyForJob(job.id);}catch{fail('KEY_UNAVAILABLE');}
   need(Buffer.isBuffer(key)&&key.length===32,'KEY_UNAVAILABLE');
   return deleteExpiredOwnerOnlyPackage(directory,job.filename,key,{nowMs});
  }};
 return Object.freeze(provider);
}
