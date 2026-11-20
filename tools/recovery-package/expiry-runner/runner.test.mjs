import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash,randomBytes} from 'node:crypto';
import {mkdtemp,chmod,readFile,lstat,symlink,rm} from 'node:fs/promises';
import {join,resolve,sep} from 'node:path';
import {tmpdir} from 'node:os';
import {SOURCE,WINDOW_MS,writeOwnerOnlyPackage} from '../package.mjs';
import {PURPOSE,LIMITS,expiryJob,initialState,runExpiry,acknowledgeAlert,ownerFileProvider} from './runner.mjs';

const CREATED=Date.parse('2026-11-10T10:00:00Z'),NOW=CREATED+WINDOW_MS;
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const clone=value=>JSON.parse(JSON.stringify(value));
const job=(name='ONE')=>expiryJob({filename:`SYNTHETIC_${name}.bsre`,packageSha256:'a'.repeat(64),expiresAtMs:NOW});
function backing(){return {state:initialState(),saves:0,busy:false,failSave:null};}
function journal(data){
 return {source:SOURCE,purpose:PURPOSE,exclusive:async operation=>{
  if(data.busy)throw Error('SYNTHETIC_JOURNAL_BUSY');data.busy=true;
  try{return await operation({load:async()=>clone(data.state),save:async state=>{
   data.saves++;if(data.saves===data.failSave)throw Error('PRIVATE STORAGE DETAILS');data.state=clone(state);
  }});}finally{data.busy=false;}
 }};
}
function provider(jobs=[job()]){
 const files=new Map(jobs.map(item=>[item.id,item.packageSha256]));
 return {source:SOURCE,purpose:PURPOSE,files,deleteCalls:0,inspectCalls:0,
  async inspect(item){this.inspectCalls++;return files.has(item.id)?{state:'PRESENT',packageSha256:files.get(item.id)}:{state:'ABSENT'};},
  async expire(item){this.deleteCalls++;files.delete(item.id);return {deleted:true,expiresAtMs:item.expiresAtMs,productionAcceptance:false};}
 };
}
function options(data,p,jobs=[job()],extra={}){
 return {journal:journal(data),provider:p,jobs,nowMs:NOW,enabled:true,
  authorization:'RUN_SYNTHETIC_EXPIRY_ONLY',...extra};
}

test('default plan-only makes no journal/provider/key call',async()=>{
 const data=backing(),p=provider();
 const result=await runExpiry(options(data,p,[job()],{enabled:false}));
 assert.equal(result.mode,'PLAN_ONLY');assert.equal(result.status,'PLAN_ONLY');assert.equal(data.saves,0);
 assert.equal(p.inspectCalls,0);assert.equal(p.deleteCalls,0);
 for(const flag of ['productionAcceptance','expirySchedulingAccepted','providerCustodyAccepted'])assert.equal(result[flag],false);
});
test('explicit synthetic purpose/authorization required before effects',async()=>{
 for(const change of [{source:'PRODUCTION'},{purpose:'MAIL_PURGE'},{authorization:null},{enabled:'yes'}]){
  const data=backing(),p=provider(),r=await runExpiry(options(data,p,[job()],change));
  assert.equal(r.status,'HOLD');assert.equal(p.inspectCalls,0);assert.equal(data.saves,0);
 }
});
test('escape, absolute path, ordinary names and changed manifest are rejected',async()=>{
 for(const filename of ['../SYNTHETIC_ESCAPE.bsre','/SYNTHETIC_ABS.bsre','C:\\SYNTHETIC_ABS.bsre','real-backup.bsre','SYNTHETIC_A/child.bsre'])
  assert.throws(()=>expiryJob({filename,packageSha256:'a'.repeat(64),expiresAtMs:NOW}),/SYNTHETIC_BASENAME_REQUIRED/);
 const altered={...job(),expiresAtMs:NOW-1},data=backing(),p=provider();
 assert.equal((await runExpiry(options(data,p,[altered]))).status,'HOLD');assert.equal(p.deleteCalls,0);
});
test('exact expiry persists intent before deletion and retries completed jobs idempotently',async()=>{
 const data=backing(),p=provider();
 const expire=p.expire.bind(p);p.expire=async item=>{
  assert.equal(data.state.jobs[0].status,'INTENT');assert.equal(data.state.jobs[0].job.id,item.id);return expire(item);
 };
 assert.equal((await runExpiry(options(data,p))).status,'COMPLETE');
 assert.equal(data.state.jobs[0].completion.kind,'AUTHENTICATED_EXPIRY_DELETED');assert.equal(p.deleteCalls,1);
 assert.equal((await runExpiry(options(data,p))).status,'COMPLETE');assert.equal(p.deleteCalls,1);
});
test('before-expiry jobs remain pending without inspecting/deleting',async()=>{
 const data=backing(),p=provider();const r=await runExpiry(options(data,p,[job()],{nowMs:NOW-1}));
 assert.equal(r.status,'PENDING');assert.equal(p.inspectCalls,0);assert.equal(p.deleteCalls,0);
});
test('deletion with lost acknowledgement reconciles absence after restart',async()=>{
 const data=backing(),p=provider();p.expire=async item=>{p.deleteCalls++;p.files.delete(item.id);throw Error('PRIVATE PROVIDER LOST ACK');};
 assert.equal((await runExpiry(options(data,p))).status,'RETRY');assert.equal(data.state.jobs[0].status,'RETRY');
 const restarted=journal(data);
 const r=await runExpiry({...options(data,p,[]),journal:restarted,nowMs:NOW+LIMITS.retryMs});
 assert.equal(r.status,'COMPLETE');assert.equal(data.state.jobs[0].completion.kind,'ABSENCE_RECONCILED_AFTER_INTENT');
 assert.equal(p.deleteCalls,1);assert.equal(r.counts.pendingAlerts,1);assert.equal(data.state.jobs[0].lastError,null);
});
test('journal completion-write loss restarts from durable intent without repeat deletion',async()=>{
 const data=backing(),p=provider();data.failSave=3;
 assert.equal((await runExpiry(options(data,p))).error,'JOURNAL_OR_RUN_UNAVAILABLE');
 assert.equal(data.state.jobs[0].status,'INTENT');assert.equal(p.deleteCalls,1);data.failSave=null;
 assert.equal((await runExpiry(options(data,p,[],{nowMs:NOW+1}))).status,'COMPLETE');
 assert.equal(data.state.jobs[0].completion.kind,'ABSENCE_RECONCILED_AFTER_INTENT');assert.equal(p.deleteCalls,1);
});
test('failed intent persistence prevents provider deletion',async()=>{
 const data=backing(),p=provider();data.failSave=2;
 assert.equal((await runExpiry(options(data,p))).status,'HOLD');assert.equal(p.deleteCalls,0);
 assert.equal(data.state.jobs[0].status,'PENDING');
});
test('absence without prior intent and changed identity hold without deletion',async()=>{
 for(const state of ['absent','changed']){
  const data=backing(),p=provider();if(state==='absent')p.files.clear();else p.files.set(job().id,'b'.repeat(64));
  const r=await runExpiry(options(data,p));assert.equal(r.status,'HOLD');assert.equal(p.deleteCalls,0);
  assert.equal(data.state.jobs[0].lastError,state==='absent'?'ABSENCE_WITHOUT_INTENT':'PACKAGE_IDENTITY_CHANGED');
 }
});
test('bounded retry/backoff stops after three failures with a pending alert receipt',async()=>{
 const data=backing(),p=provider();p.expire=async()=>{p.deleteCalls++;throw Error('PRIVATE FAILURE');};
 for(let attempt=0;attempt<3;attempt++)await runExpiry(options(data,p,[],{jobs:attempt?[]:[job()],nowMs:NOW+attempt*LIMITS.retryMs}));
 assert.equal(data.state.jobs[0].status,'HELD');assert.equal(p.deleteCalls,3);assert.equal(data.state.jobs[0].attempts,3);
 await runExpiry(options(data,p,[],{nowMs:NOW+10*LIMITS.retryMs}));assert.equal(p.deleteCalls,3);
 assert.equal(data.state.jobs[0].alert.acknowledgedAtMs,null);
});
test('backoff does not make an early retry call',async()=>{
 const data=backing(),p=provider();p.expire=async()=>{p.deleteCalls++;throw Error('SYNTHETIC');};
 await runExpiry(options(data,p));await runExpiry(options(data,p,[],{nowMs:NOW+LIMITS.retryMs-1}));assert.equal(p.deleteCalls,1);
});
test('failure alerts are acknowledged idempotently and a new failure gets a new receipt',async()=>{
 const data=backing(),p=provider();p.expire=async()=>{throw Error('PRIVATE');};
 await runExpiry(options(data,p));const first=data.state.jobs[0].alert.id;
 assert.equal((await acknowledgeAlert(journal(data),first,{nowMs:NOW})).deliveryVerified,false);
 await acknowledgeAlert(journal(data),first,{nowMs:NOW});
 await runExpiry(options(data,p,[],{nowMs:NOW+LIMITS.retryMs}));
 assert.notEqual(data.state.jobs[0].alert.id,first);assert.equal(data.state.jobs[0].alert.acknowledgedAtMs,null);
});
test('job and batch bounds are enforced without deleting excess work',async()=>{
 const jobs=Array.from({length:9},(_,i)=>job('ITEM'+i)),data=backing(),p=provider(jobs);
 const r=await runExpiry(options(data,p,jobs));assert.equal(r.counts.complete,8);assert.equal(r.status,'PENDING');
 assert.equal((await runExpiry(options(data,p,[],{maxJobs:9}))).error,'INVALID_BATCH_LIMIT');
 const many=Array.from({length:33},(_,i)=>job('TOO'+i));
 assert.equal((await runExpiry(options(backing(),provider(many),many))).status,'HOLD');
});
test('alert acknowledgement failures are sanitized and cannot acknowledge an unknown receipt',async()=>{
 const data=backing(),j=journal(data);
 assert.equal((await acknowledgeAlert(j,'b'.repeat(64),{nowMs:NOW})).error,'UNKNOWN_ALERT_RECEIPT');
 j.exclusive=async()=>{throw Error('PRIVATE JOURNAL OR KEY LOCATION');};
 const result=await acknowledgeAlert(j,'b'.repeat(64),{nowMs:NOW});
 assert.equal(result.error,'ALERT_ACK_UNAVAILABLE');assert.equal(JSON.stringify(result).includes('PRIVATE'),false);
});
test('clock rollback, filename reuse and corrupt persisted state hold',async()=>{
 const data=backing(),p=provider();await runExpiry(options(data,p));
 assert.equal((await runExpiry(options(data,p,[],{nowMs:NOW-1}))).error,'CLOCK_ROLLBACK');
 const reused=expiryJob({...job(),packageSha256:'b'.repeat(64)});
 assert.equal((await runExpiry(options(data,p,[reused]))).error,'EXPIRY_FILENAME_REUSE_FORBIDDEN');
 data.state.jobs[0].attempts=99;assert.equal((await runExpiry(options(data,p,[]))).error,'INVALID_EXPIRY_STATE');
});
test('future persisted completion is rejected without any provider effect',async()=>{
 const data=backing(),p=provider();await runExpiry(options(data,p));
 data.state.jobs[0].completion.atMs=NOW+1;
 const prior=clone(data.state),calls=[p.inspectCalls,p.deleteCalls],saves=data.saves;
 const result=await runExpiry(options(data,p,[]));
 assert.equal(result.status,'HOLD');assert.equal(result.error,'INVALID_EXPIRY_STATE');
 assert.deepEqual([p.inspectCalls,p.deleteCalls],calls);assert.equal(data.saves,saves);assert.deepEqual(data.state,prior);
 assert.equal(JSON.stringify(result).includes('SYNTHETIC_ONE'),false);
});
test('completed state cannot carry a current failure error',async()=>{
 const data=backing(),p=provider();await runExpiry(options(data,p));
 data.state.jobs[0].lastError='EXPIRY_PROVIDER_FAILURE';const calls=[p.inspectCalls,p.deleteCalls];
 assert.equal((await runExpiry(options(data,p,[]))).error,'INVALID_EXPIRY_STATE');
 assert.deepEqual([p.inspectCalls,p.deleteCalls],calls);
});
test('provider/journal failures and reports never echo private errors, names or keys',async()=>{
 const data=backing(),p=provider();p.inspect=async()=>{throw Error('PRIVATE_PROVIDER_KEY_SECRET');};
 const r=await runExpiry(options(data,p));
 assert.equal(r.status,'RETRY');assert.equal(JSON.stringify(r).includes('SYNTHETIC_ONE'),false);
 assert.equal(JSON.stringify(data.state).includes('PRIVATE_PROVIDER_KEY_SECRET'),false);
 const bad=journal(data);bad.exclusive=async()=>{throw Error('PRIVATE_STORE_PATH');};
 assert.equal((await runExpiry({...options(data,p),journal:bad})).error,'JOURNAL_OR_RUN_UNAVAILABLE');
});
test('serialized journal exclusivity prevents duplicate concurrent deletes',async()=>{
 const data=backing(),p=provider();let release;const gate=new Promise(resolveGate=>{release=resolveGate;});
 const expire=p.expire.bind(p);p.expire=async item=>{await gate;return expire(item);};
 const first=runExpiry(options(data,p));while(data.state.jobs[0]?.status!=='INTENT')await new Promise(r=>setTimeout(r,0));
 const second=await runExpiry(options(data,p));assert.equal(second.status,'HOLD');release();await first;assert.equal(p.deleteCalls,1);
});
test('local adapter refuses unsupported Windows or exercises real owner-file expiry and symlink guard',async()=>{
 const key=randomBytes(32),local=ownerFileProvider('unused',async()=>key);
 if(process.platform==='win32'){
  await assert.rejects(local.inspect(job()),/OWNER_ONLY_FILESYSTEM_UNSUPPORTED/);return;
 }
 const directory=await mkdtemp(join(tmpdir(),'bsre-expiry-runner-'));await chmod(directory,0o700);
 try{
  const filename='SYNTHETIC_LOCAL.bsre';await writeOwnerOnlyPackage(directory,filename,Buffer.from('SYNTHETIC ONLY'),key,{nowMs:CREATED,deletionLedgerWatermark:0});
  const bytes=await readFile(join(directory,filename));
  const task=expiryJob({filename,packageSha256:digest(bytes),expiresAtMs:NOW});
  const p=ownerFileProvider(directory,async()=>key),data=backing();
  await symlink(join(directory,filename),join(directory,'SYNTHETIC_LINK.bsre'));
  const linked=expiryJob({filename:'SYNTHETIC_LINK.bsre',packageSha256:digest(bytes),expiresAtMs:NOW});
  await assert.rejects(p.inspect(linked),/OWNER_ONLY_FILE_REQUIRED/);
  const r=await runExpiry(options(data,p,[task]));assert.equal(r.status,'COMPLETE');
  await assert.rejects(lstat(join(directory,filename)),{code:'ENOENT'});
 }finally{
  assert.ok(resolve(directory).startsWith(resolve(tmpdir())+sep+'bsre-expiry-runner-'));
  await rm(directory,{recursive:true,force:true});
 }
});
