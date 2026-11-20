import test from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes,createHash} from 'node:crypto';
import {constants} from 'node:fs';
import {mkdtemp,chmod,readFile,writeFile,readdir,lstat,rm,unlink,symlink,link,open,rename} from 'node:fs/promises';
import {join,resolve,sep} from 'node:path';
import {tmpdir} from 'node:os';
import {fork} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {SOURCE,WINDOW_MS,writeOwnerOnlyPackage} from '../package.mjs';
import {PURPOSE,initialState,expiryJob,runExpiry,ownerFileProvider} from './runner.mjs';
import {initializeLocalJournal,createLocalJournal,encodeLocalState,LOCAL_FILES} from './local-journal.mjs';

const POSIX=process.platform!=='win32'&&typeof process.getuid==='function'&&Boolean(constants.O_NOFOLLOW&&constants.O_DIRECTORY);
const ACK={enabled:true,authorization:'USE_SYNTHETIC_LOCAL_JOURNAL'};
const INIT={enabled:true,authorization:'INITIALIZE_SYNTHETIC_LOCAL_JOURNAL'};
const CREATED=1700000000000,NOW=CREATED+WINDOW_MS;
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
const linuxTest=(name,run)=>test(name,{skip:!POSIX,timeout:20000},run);
async function directory(){const dir=await mkdtemp(join(tmpdir(),'bsre-synthetic-expiry-journal-'));await chmod(dir,0o700);return dir;}
async function cleanup(dir){assert.ok(resolve(dir).startsWith(resolve(tmpdir())+sep+'bsre-synthetic-expiry-journal-'));await rm(dir,{recursive:true,force:true});}
async function fixture(run){const dir=await directory();try{const id=await initializeLocalJournal(dir,INIT);await run(dir,id.journalId);}finally{await cleanup(dir);}}
const journal=(dir,journalId)=>createLocalJournal(dir,{...ACK,journalId});
async function envelope(dir){return JSON.parse(await readFile(join(dir,LOCAL_FILES.state),'utf8'));}
function child(mode,dir,journalId){return fork(fileURLToPath(new URL('./local-journal.worker.mjs',import.meta.url)),[mode,dir,journalId],{stdio:['ignore','ignore','ignore','ipc']});}
function message(child,kind){return new Promise((resolveMessage,reject)=>{
 const timer=setTimeout(()=>{clean();reject(Error('Synthetic child readiness timed out'));},8000);
 const onMessage=body=>{if(body?.kind===kind){clean();resolveMessage(body);}else if(body?.kind==='HELD'){clean();reject(Error('Synthetic child held before readiness'));}};
 const onExit=()=>{clean();reject(Error('Synthetic child exited before readiness'));};
 function clean(){clearTimeout(timer);child.off('message',onMessage);child.off('exit',onExit);}
 child.on('message',onMessage);child.once('exit',onExit);
 });}
function exited(child){return new Promise((resolveExit,reject)=>{
 if(child.exitCode!==null||child.signalCode!==null){resolveExit();return;}
 const timer=setTimeout(()=>{child.off('exit',onExit);reject(Error('Synthetic child exit timed out'));},8000);
 const onExit=()=>{clearTimeout(timer);resolveExit();};child.once('exit',onExit);
 });}
async function stop(child){if(child.exitCode===null&&child.signalCode===null){const ended=exited(child);child.kill('SIGKILL');await ended;}}

test('default-disabled initialization and transaction refuse before any path or callback effect',async()=>{
 await assert.rejects(initializeLocalJournal('PRIVATE_UNRESOLVED_PATH'),{message:'JOURNAL_DISABLED'});
 let called=false;await assert.rejects(createLocalJournal('PRIVATE_UNRESOLVED_PATH').exclusive(()=>{called=true;}),{message:'JOURNAL_DISABLED'});
 assert.equal(called,false);
});
test('scope and run acknowledgements cannot substitute for each other',async()=>{
 await assert.rejects(initializeLocalJournal('unused',ACK),{message:'JOURNAL_DISABLED'});
 await assert.rejects(createLocalJournal('unused',INIT).exclusive(()=>{}),{message:'JOURNAL_DISABLED'});
 await assert.rejects(initializeLocalJournal('unused',{...INIT,source:'REAL'}),{message:'SYNTHETIC_JOURNAL_REQUIRED'});
});
test('bounded data-only storage encoding preserves state and rejects cycles, accessors and objects',()=>{
 const state=initialState();assert.deepEqual(JSON.parse(encodeLocalState(state)),state);
 const cyclic=initialState();cyclic.jobs.push(cyclic);assert.throws(()=>encodeLocalState(cyclic),/JOURNAL_STATE_INVALID/);
 let invoked=false;const getter=initialState();Object.defineProperty(getter,'lastNowMs',{enumerable:true,get(){invoked=true;return 1;}});
 assert.throws(()=>encodeLocalState(getter),/JOURNAL_STATE_INVALID/);assert.equal(invoked,false);
 assert.throws(()=>encodeLocalState({...initialState(),jobs:[new Date()]}),/JOURNAL_STATE_INVALID/);
 assert.throws(()=>encodeLocalState({...initialState(),jobs:Array(33).fill({})}),/JOURNAL_STATE_INVALID/);
 assert.throws(()=>encodeLocalState({...initialState(),jobs:[{a:'x'.repeat(2049)}]}),/JOURNAL_STATE_INVALID/);
});
test('non-enumerable or inherited toJSON is never invoked and huge sparse lengths fail before serialization',()=>{
 let invoked=0;const state=initialState();Object.defineProperty(state,'toJSON',{value(){invoked++;return initialState();}});
 assert.throws(()=>encodeLocalState(state),/JOURNAL_STATE_INVALID/);
 const nested=initialState();const inherited=Object.create(Array.prototype);inherited.toJSON=()=>{invoked++;return [];};Object.setPrototypeOf(nested.jobs,inherited);
 assert.throws(()=>encodeLocalState(nested),/JOURNAL_STATE_INVALID/);assert.equal(invoked,0);
 const sparse=initialState();sparse.jobs.length=0xffffffff;assert.throws(()=>encodeLocalState(sparse),/JOURNAL_STATE_INVALID/);
 const holes=initialState();holes.jobs.length=3;assert.throws(()=>encodeLocalState(holes),/JOURNAL_STATE_INVALID/);
 const proxy=initialState();proxy.jobs.push(new Proxy({},{ownKeys(){throw Error('PRIVATE_PROXY_ERROR');}}));
 assert.throws(()=>encodeLocalState(proxy),{message:'JOURNAL_STATE_INVALID'});
});
test('Windows explicitly refuses the POSIX adapter before filesystem operations',async t=>{
 if(POSIX){t.skip('POSIX checks run below');return;}
 await assert.rejects(initializeLocalJournal('unused',INIT),{message:'LOCAL_JOURNAL_UNSUPPORTED'});
 await assert.rejects(journal('unused','a'.repeat(64)).exclusive(()=>{}),{message:'LOCAL_JOURNAL_UNSUPPORTED'});
});
linuxTest('actual owner modes, immutable journal ID, atomic state generations and fresh-instance load',()=>fixture(async(dir,id)=>{
 const before=await envelope(dir);assert.equal(before.generation,1);
 const j=journal(dir,id);let escaped;
 await j.exclusive(async tx=>{escaped=tx;const state=await tx.load();state.lastNowMs=1;await tx.save(state);state.lastNowMs=2;await tx.save(state);});
 assert.equal((await envelope(dir)).generation,3);assert.equal((await lstat(join(dir,LOCAL_FILES.state))).mode&0o7777,0o600);
 assert.equal((await lstat(join(dir,LOCAL_FILES.identity))).mode&0o7777,0o600);
 assert.equal((await lstat(dir)).mode&0o7777,0o700);assert.deepEqual((await readdir(dir)).sort(),[LOCAL_FILES.identity,LOCAL_FILES.state].sort());
 assert.equal(await journal(dir,id).exclusive(async tx=>(await tx.load()).lastNowMs),2);
 await assert.rejects(escaped.load(),{message:'JOURNAL_TX_CLOSED'});
 const bytes=await readFile(join(dir,LOCAL_FILES.state));await assert.rejects(initializeLocalJournal(dir,INIT),/JOURNAL_DIRECTORY_UNRECONCILED/);assert.deepEqual(await readFile(join(dir,LOCAL_FILES.state)),bytes);
}));
linuxTest('journal options are captured and cannot silently enable or retarget an instance',()=>fixture(async(dir,id)=>{
 const config={journalId:id};const disabled=createLocalJournal(dir,config);Object.assign(config,ACK);
 await assert.rejects(disabled.exclusive(()=>{}),/JOURNAL_DISABLED/);
 const active={...ACK,journalId:id};const j=createLocalJournal(dir,active);active.journalId='b'.repeat(64);
 assert.equal(await j.exclusive(async tx=>(await tx.load()).source),SOURCE);
}));
linuxTest('new process reads a previously acknowledged persistent state',()=>fixture(async(dir,id)=>{
 await journal(dir,id).exclusive(async tx=>{const s=await tx.load();s.lastNowMs=1234;await tx.save(s);});
 const worker=child('read',dir,id);try{const response=await message(worker,'READ');assert.equal(response.lastNowMs,1234);await exited(worker);assert.equal(worker.exitCode,0);}finally{await stop(worker);}
}));
linuxTest('actual second process is excluded while the first owns its lock',()=>fixture(async(dir,id)=>{
 const worker=child('hold',dir,id);try{
  await message(worker,'LOCKED');let called=false;
  await assert.rejects(journal(dir,id).exclusive(()=>{called=true;}),{message:'JOURNAL_LOCK_HELD'});assert.equal(called,false);
  const ended=exited(worker);worker.send({kind:'RELEASE'});await ended;assert.equal(worker.exitCode,0);
  assert.equal(await journal(dir,id).exclusive(async tx=>(await tx.load()).version),1);
 }finally{await stop(worker);}
}));
linuxTest('actual killed writer preserves acknowledged state and leaves a held lock, never TTL/PID recovery',()=>fixture(async(dir,id)=>{
 const worker=child('crash',dir,id);try{await message(worker,'SAVED');await stop(worker);
  assert.equal((await envelope(dir)).state.lastNowMs,CREATED);
  await assert.rejects(journal(dir,id).exclusive(()=>{}),{message:'JOURNAL_LOCK_HELD'});
  assert.ok((await lstat(join(dir,LOCAL_FILES.lock))).isDirectory());
 }finally{await stop(worker);}
}));
linuxTest('persisted intent precedes provider effects and lost acknowledgement reconciles after reopening',()=>fixture(async(dir,id)=>{
 const item=expiryJob({filename:'SYNTHETIC_LOST_ACK.bsre',packageSha256:'a'.repeat(64),expiresAtMs:NOW});let present=true,deletes=0;
 const provider={source:SOURCE,purpose:PURPOSE,inspect:async()=>present?{state:'PRESENT',packageSha256:item.packageSha256}:{state:'ABSENT'},
  expire:async()=>{const saved=await envelope(dir);assert.equal(saved.state.jobs[0].status,'INTENT');assert.equal(saved.state.jobs[0].job.id,item.id);present=false;deletes++;throw Error('SYNTHETIC_LOST_ACK');}};
 const options={jobs:[item],journal:journal(dir,id),provider,nowMs:NOW,enabled:true,authorization:'RUN_SYNTHETIC_EXPIRY_ONLY'};
 assert.equal((await runExpiry(options)).status,'RETRY');
 const result=await runExpiry({...options,jobs:[],journal:journal(dir,id),nowMs:NOW+60000});
 assert.equal(result.status,'COMPLETE');assert.equal(deletes,1);assert.equal(result.counts.pendingAlerts,1);
 assert.equal((await envelope(dir)).state.jobs[0].completion.kind,'ABSENCE_RECONCILED_AFTER_INTENT');assert.equal(result.productionAcceptance,false);
}));
linuxTest('unawaited queued save drains under the lock; callback failure does not roll back acknowledged state',()=>fixture(async(dir,id)=>{
 const j=journal(dir,id);await j.exclusive(async tx=>{const s=await tx.load();s.lastNowMs=4;void tx.save(s);s.lastNowMs=99;});
 assert.equal((await envelope(dir)).state.lastNowMs,4);
 await assert.rejects(j.exclusive(async tx=>{const s=await tx.load();s.lastNowMs=5;await tx.save(s);throw Error('PRIVATE_CALLBACK_CONTENT');}),{message:'JOURNAL_CALLBACK_FAILED'});
 assert.equal(await journal(dir,id).exclusive(async tx=>(await tx.load()).lastNowMs),5);
}));
linuxTest('missing, corrupt, oversized or wrong-identity state cannot invoke the provider callback',()=>fixture(async(dir,id)=>{
 const original=await readFile(join(dir,LOCAL_FILES.state));let calls=0;
 await assert.rejects(journal(dir,'f'.repeat(64)).exclusive(()=>calls++),/JOURNAL_IDENTITY_CHANGED/);
 for(const bytes of [Buffer.from('{INVALID'),Buffer.alloc(133121)]){
  await writeFile(join(dir,LOCAL_FILES.state),bytes);
  await assert.rejects(journal(dir,id).exclusive(()=>calls++),/^Error: JOURNAL_(STATE_INVALID|FILE_REQUIRED)$/);
 }
 await unlink(join(dir,LOCAL_FILES.state));await assert.rejects(journal(dir,id).exclusive(()=>calls++),{message:'JOURNAL_STORAGE_UNAVAILABLE'});
 assert.equal(calls,0);await writeFile(join(dir,LOCAL_FILES.state),original,{mode:0o600});
}));
linuxTest('state symlinks and hard links are refused without touching their targets',()=>fixture(async(dir,id)=>{
 const other=await directory();try{
  const original=await readFile(join(dir,LOCAL_FILES.state)),outside=join(other,'SYNTHETIC_TARGET');await writeFile(outside,original,{mode:0o600});
  await unlink(join(dir,LOCAL_FILES.state));await symlink(outside,join(dir,LOCAL_FILES.state));
  await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_FILE_REQUIRED/);assert.deepEqual(await readFile(outside),original);
  await unlink(join(dir,LOCAL_FILES.state));await link(outside,join(dir,LOCAL_FILES.state));
  await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_FILE_REQUIRED/);assert.deepEqual(await readFile(outside),original);
 }finally{await cleanup(other);}
}));
linuxTest('nonempty, ordinary-named and symlink directories are not initialized or repaired',()=>fixture(async(dir,id)=>{
 const other=await directory(),alias=other+'-alias';try{
  await writeFile(join(other,'SYNTHETIC_UNRELATED'),'SYNTHETIC ONLY',{mode:0o600});
  await assert.rejects(initializeLocalJournal(other,INIT),/JOURNAL_DIRECTORY_UNRECONCILED/);
  assert.deepEqual(await readdir(other),['SYNTHETIC_UNRELATED']);
  await symlink(dir,alias);await assert.rejects(journal(alias,id).exclusive(()=>{}),/JOURNAL_DIRECTORY_REQUIRED/);
  await assert.rejects(journal(tmpdir(),id).exclusive(()=>{}),/JOURNAL_DIRECTORY_REQUIRED/);
 }finally{await rm(alias,{force:true});await cleanup(other);}
}));
linuxTest('external state change poisons save and retains the lock before further operations',()=>fixture(async(dir,id)=>{
 let after=false;await assert.rejects(journal(dir,id).exclusive(async tx=>{
  const s=await tx.load();await writeFile(join(dir,LOCAL_FILES.state),'SYNTHETIC_CHANGED');
  try{await tx.save(s);}catch{}
  try{await tx.load();after=true;}catch{}
 }),/JOURNAL_CURRENT_STATE_CHANGED/);
 assert.equal(after,false);assert.equal(await readFile(join(dir,LOCAL_FILES.state),'utf8'),'SYNTHETIC_CHANGED');
 await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_LOCK_HELD/);
}));
linuxTest('simulated state-file fsync failure rejects acknowledgement and preserves old state with a held lock',t=>fixture(async(dir,id)=>{
 const before=await readFile(join(dir,LOCAL_FILES.state)),probe=await open(join(dir,LOCAL_FILES.state),'r');let effects=0;
 try{
  const prototype=Object.getPrototypeOf(probe),original=prototype.sync;
  await assert.rejects(journal(dir,id).exclusive(async tx=>{
   const state=await tx.load();state.lastNowMs=99;
   t.mock.method(prototype,'sync',async function(){if((await this.stat()).isFile())throw Error('PRIVATE_SIMULATED_FILE_FSYNC');return original.call(this);});
   await tx.save(state);effects++;
  }),{message:'JOURNAL_STORAGE_UNAVAILABLE'});
 }finally{t.mock.restoreAll();await probe.close();}
 assert.equal(effects,0);assert.deepEqual(await readFile(join(dir,LOCAL_FILES.state)),before);
 await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_LOCK_HELD/);
}));
linuxTest('simulated post-rename directory fsync failure leaves unacknowledged new bytes held for reconciliation',t=>fixture(async(dir,id)=>{
 const probe=await open(join(dir,LOCAL_FILES.state),'r');let effects=0;
 try{
  const prototype=Object.getPrototypeOf(probe),original=prototype.sync;
  await assert.rejects(journal(dir,id).exclusive(async tx=>{
   const state=await tx.load();state.lastNowMs=99;
   t.mock.method(prototype,'sync',async function(){if((await this.stat()).isDirectory())throw Error('PRIVATE_SIMULATED_DIRECTORY_FSYNC');return original.call(this);});
   await tx.save(state);effects++;
  }),{message:'JOURNAL_STORAGE_UNAVAILABLE'});
 }finally{t.mock.restoreAll();await probe.close();}
 assert.equal(effects,0);assert.equal((await envelope(dir)).state.lastNowMs,99);
 await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_LOCK_HELD/);
}));
linuxTest('a stale generation is held by the same journal instance; hashes are not external custody',()=>fixture(async(dir,id)=>{
 const old=await readFile(join(dir,LOCAL_FILES.state)),j=journal(dir,id);
 await j.exclusive(async tx=>{const s=await tx.load();s.lastNowMs=1;await tx.save(s);});
 await writeFile(join(dir,LOCAL_FILES.state),old);
 await assert.rejects(j.exclusive(()=>{}),/JOURNAL_CURRENT_STATE_CHANGED/);
}));
linuxTest('changed lock owner record is never deleted by cleanup',()=>fixture(async(dir,id)=>{
 const foreign=Buffer.from('SYNTHETIC_OTHER_LOCK_OWNER');
 await assert.rejects(journal(dir,id).exclusive(async()=>{await writeFile(join(dir,LOCAL_FILES.lock,'owner.json'),foreign);}),/JOURNAL_LOCK_CHANGED/);
 assert.deepEqual(await readFile(join(dir,LOCAL_FILES.lock,'owner.json')),foreign);
 await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_LOCK_HELD/);
}));
linuxTest('an identical-token replacement owner inode is never removed as the original lease',()=>fixture(async(dir,id)=>{
 let copied,oldInode,newInode;
 await assert.rejects(journal(dir,id).exclusive(async()=>{
  const owner=join(dir,LOCAL_FILES.lock,'owner.json'),replacement=join(dir,LOCAL_FILES.lock,'replacement.json');
  copied=await readFile(owner);oldInode=(await lstat(owner)).ino;
  await writeFile(replacement,copied,{mode:0o600,flag:'wx'});await rename(replacement,owner);newInode=(await lstat(owner)).ino;
 }),/JOURNAL_LOCK_CHANGED/);
 assert.notEqual(newInode,oldInode);assert.deepEqual(await readFile(join(dir,LOCAL_FILES.lock,'owner.json')),copied);
 await assert.rejects(journal(dir,id).exclusive(()=>{}),/JOURNAL_LOCK_HELD/);
}));
linuxTest('real synthetic encrypted expiry integrates with the persisted journal and preserves false admission flags',()=>fixture(async(dir,id)=>{
 const packages=await directory();try{
  const key=randomBytes(32),filename='SYNTHETIC_JOURNAL_INTEGRATION.bsre';
  await writeOwnerOnlyPackage(packages,filename,Buffer.from('SYNTHETIC ONLY'),key,{nowMs:CREATED,deletionLedgerWatermark:0});
  const item=expiryJob({filename,packageSha256:hash(await readFile(join(packages,filename))),expiresAtMs:NOW});
  const result=await runExpiry({jobs:[item],journal:journal(dir,id),provider:ownerFileProvider(packages,async()=>key),nowMs:NOW,enabled:true,authorization:'RUN_SYNTHETIC_EXPIRY_ONLY'});
  assert.equal(result.status,'COMPLETE');assert.equal(result.productionAcceptance,false);assert.equal(result.providerCustodyAccepted,false);assert.equal(result.expirySchedulingAccepted,false);
  await assert.rejects(lstat(join(packages,filename)),{code:'ENOENT'});
  assert.equal((await envelope(dir)).state.jobs[0].completion.kind,'AUTHENTICATED_EXPIRY_DELETED');
 }finally{await cleanup(packages);}
}));
