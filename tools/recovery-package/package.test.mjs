import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomBytes,createHash} from 'node:crypto';
import {mkdtemp,chmod,stat,readFile,rm,symlink,writeFile,mkdir} from 'node:fs/promises';
import {join,resolve} from 'node:path';
import {tmpdir} from 'node:os';
import {SOURCE,WINDOW_MS,MAX_SNAPSHOT_BYTES,sealPackage,openPackage,writeOwnerOnlyPackage,deleteExpiredOwnerOnlyPackage} from './package.mjs';
const now=Date.parse('2026-11-08T08:00:00Z');
const fixture=Buffer.from('{"kind":"SYNTHETIC_ONLY","state":[{"synthetic":true}],"history":[],"captures":[]}');
const key=randomBytes(32);
const seal=(bytes=fixture,watermark=4)=>sealPackage(bytes,key,{nowMs:now,deletionLedgerWatermark:watermark});
const open=bytes=>openPackage(bytes,key,{nowMs:now});
function editMetadata(bytes,change){
 const length=bytes.readUInt32BE(4),metadata=JSON.parse(bytes.subarray(8,8+length));change(metadata);
 const raw=Buffer.from(JSON.stringify(metadata)),prefix=Buffer.from(bytes.subarray(0,8));prefix.writeUInt32BE(raw.length,4);
 return Buffer.concat([prefix,raw,bytes.subarray(8+length)]);
}
test('round trip exact bytes, immutable digest and explicit nonauthorization',()=>{
 const encrypted=seal(),result=open(encrypted);
 assert.deepEqual(result.snapshot,fixture);
 assert.deepEqual(result.metadata,{version:1,source:SOURCE,createdAtMs:now,expiresAtMs:now+WINDOW_MS,snapshotSha256:createHash('sha256').update(fixture).digest('hex'),deletionLedgerWatermark:4});
 assert.equal(result.restoreAuthorized,false);assert.equal(Object.isFrozen(result.metadata),true);
 assert.equal(encrypted.includes(fixture),false);
});
test('random nonce changes otherwise identical packages',()=>assert.notDeepEqual(seal(),seal()));
test('expiry exact boundary and clock rollback deny plaintext',()=>{
 const bytes=seal();assert.deepEqual(openPackage(bytes,key,{nowMs:now+WINDOW_MS-1}).snapshot,fixture);
 for(const time of [now-1,now+WINDOW_MS,now+WINDOW_MS+1,NaN,Infinity,-1,1.5])assert.throws(()=>openPackage(bytes,key,{nowMs:time}),/INVALID_RECOVERY_PACKAGE/);
});
test('wrong key, ciphertext, nonce and tag tampering fail closed',()=>{
 const bytes=seal(),length=bytes.readUInt32BE(4);
 assert.throws(()=>openPackage(bytes,randomBytes(32),{nowMs:now}),/INVALID_RECOVERY_PACKAGE/);
 for(const offset of [8+length,20+length,bytes.length-1]){const altered=Buffer.from(bytes);altered[offset]^=1;assert.throws(()=>open(altered),/INVALID_RECOVERY_PACKAGE/);}
});
test('version, source, digest, watermark and time metadata are authenticated',()=>{
 for(const change of [m=>m.version=2,m=>m.source='OTHER',m=>m.snapshotSha256='a'.repeat(64),m=>m.deletionLedgerWatermark++,m=>m.createdAtMs--,m=>m.expiresAtMs++,m=>m.extra=true,m=>m.deletionLedgerWatermark='4'])assert.throws(()=>open(editMetadata(seal(),change)),/INVALID_RECOVERY_PACKAGE/);
});
test('duplicate/noncanonical metadata, malformed header and truncation rejected',()=>{
 const bytes=seal(),length=bytes.readUInt32BE(4),raw=bytes.subarray(8,8+length).toString();
 const duplicate=Buffer.from(raw.replace('"version":1','"version":1,"version":1')),prefix=Buffer.from(bytes.subarray(0,8));prefix.writeUInt32BE(duplicate.length,4);
 const badLength=Buffer.from(bytes);badLength.writeUInt32BE(0xffffffff,4);
 for(const bad of [Buffer.alloc(0),Buffer.from('not a package'),bytes.subarray(0,bytes.length-1),badLength,Buffer.concat([prefix,duplicate,bytes.subarray(8+length)]),Buffer.concat([bytes,Buffer.from('x')])])assert.throws(()=>open(bad),/INVALID_RECOVERY_PACKAGE/);
});
test('bounded buffers, key sizes and safe watermark inputs enforced',()=>{
 for(const bad of [Buffer.alloc(0),Buffer.alloc(MAX_SNAPSHOT_BYTES+1),'SYNTHETIC'])assert.throws(()=>seal(bad),/INVALID_RECOVERY_PACKAGE/);
 for(const badKey of [Buffer.alloc(0),Buffer.alloc(31),Buffer.alloc(33),'x'.repeat(32)])assert.throws(()=>sealPackage(fixture,badKey,{nowMs:now,deletionLedgerWatermark:0}),/INVALID_RECOVERY_PACKAGE/);
 for(const mark of [-1,0.5,NaN,Infinity,Number.MAX_SAFE_INTEGER+1,undefined,'0'])assert.throws(()=>sealPackage(fixture,key,{nowMs:now,deletionLedgerWatermark:mark}),/INVALID_RECOVERY_PACKAGE/);
 assert.equal(open(seal(fixture,0)).metadata.deletionLedgerWatermark,0);
 assert.throws(()=>open(Buffer.alloc(MAX_SNAPSHOT_BYTES+2049)),/INVALID_RECOVERY_PACKAGE/);
});
test('owner-only write rejects unsupported platform or enforces mode/overwrite/symlinks',async()=>{
 if(process.platform==='win32'){
  await assert.rejects(writeOwnerOnlyPackage('unused','snapshot.bsre',fixture,key,{nowMs:now,deletionLedgerWatermark:4}),/OWNER_ONLY_FILESYSTEM_UNSUPPORTED/);return;
 }
 const root=await mkdtemp(join(tmpdir(),'bsre-package-'));await chmod(root,0o700);
 try{
  const options={nowMs:now,deletionLedgerWatermark:4};
  const result=await writeOwnerOnlyPackage(root,'snapshot.bsre',fixture,key,options);
  assert.equal(result.productionAcceptance,false);assert.equal(result.expiresAtMs,now+WINDOW_MS);
  assert.equal((await stat(join(root,'snapshot.bsre'))).mode&0o7777,0o600);
  assert.deepEqual(open(await readFile(join(root,'snapshot.bsre'))).snapshot,fixture);
  await assert.rejects(writeOwnerOnlyPackage(root,'snapshot.bsre',fixture,key,options));
  await writeFile(join(root,'target'),Buffer.from('SYNTHETIC UNCHANGED'),{mode:0o600});
  await symlink(join(root,'target'),join(root,'link.bsre'));
  await assert.rejects(writeOwnerOnlyPackage(root,'link.bsre',fixture,key,options));
  assert.equal((await readFile(join(root,'target'))).toString(),'SYNTHETIC UNCHANGED');
  await assert.rejects(writeOwnerOnlyPackage(root,'../escape.bsre',fixture,key,options),/OWNER_ONLY_PATH_REQUIRED/);
  await chmod(root,0o755);await assert.rejects(writeOwnerOnlyPackage(root,'public.bsre',fixture,key,options),/OWNER_ONLY_DIRECTORY_REQUIRED/);
 }finally{
  assert.equal(resolve(root).startsWith(resolve(tmpdir())+ '/bsre-package-'),true);
  await rm(root,{recursive:true,force:true});
 }
});
test('explicit expiry cleanup authenticates, preserves early/tampered files and deletes only at expiry',async()=>{
 if(process.platform==='win32'){
  await assert.rejects(deleteExpiredOwnerOnlyPackage('unused','snapshot.bsre',key,{nowMs:now+WINDOW_MS}),/OWNER_ONLY_FILESYSTEM_UNSUPPORTED/);return;
 }
 const root=await mkdtemp(join(tmpdir(),'bsre-package-'));await chmod(root,0o700);
 try{
  const target=join(root,'expiry.bsre'),bytes=seal();await writeFile(target,bytes,{mode:0o600});
  await assert.rejects(deleteExpiredOwnerOnlyPackage(root,'expiry.bsre',key,{nowMs:now+WINDOW_MS-1}),/RECOVERY_NOT_EXPIRED/);
  assert.deepEqual(await readFile(target),bytes);
  await assert.rejects(deleteExpiredOwnerOnlyPackage(root,'expiry.bsre',randomBytes(32),{nowMs:now+WINDOW_MS}),/INVALID_RECOVERY_PACKAGE/);
  const tampered=Buffer.from(bytes);tampered[tampered.length-1]^=1;await writeFile(target,tampered);
  await assert.rejects(deleteExpiredOwnerOnlyPackage(root,'expiry.bsre',key,{nowMs:now+WINDOW_MS}),/INVALID_RECOVERY_PACKAGE/);
  assert.deepEqual(await readFile(target),tampered);
  await writeFile(target,bytes);await chmod(target,0o640);
  await assert.rejects(deleteExpiredOwnerOnlyPackage(root,'expiry.bsre',key,{nowMs:now+WINDOW_MS}),/OWNER_ONLY_FILE_REQUIRED/);
  await chmod(target,0o600);await symlink(target,join(root,'alias.bsre'));
  await assert.rejects(deleteExpiredOwnerOnlyPackage(root,'alias.bsre',key,{nowMs:now+WINDOW_MS}));
  assert.deepEqual(await readFile(target),bytes);
  const result=await deleteExpiredOwnerOnlyPackage(root,'expiry.bsre',key,{nowMs:now+WINDOW_MS});
  assert.deepEqual(result,{deleted:true,expiresAtMs:now+WINDOW_MS,productionAcceptance:false});
  await assert.rejects(stat(target),error=>error.code==='ENOENT');
  await assert.rejects(deleteExpiredOwnerOnlyPackage(root,'expiry.bsre',key,{nowMs:now+WINDOW_MS}));
 }finally{
  assert.equal(resolve(root).startsWith(resolve(tmpdir())+'/bsre-package-'),true);await rm(root,{recursive:true,force:true});
 }
});
test('write and expiry cleanup reject directory symlinks including ancestor components',async()=>{
 if(process.platform==='win32'){
  await assert.rejects(writeOwnerOnlyPackage('unused','x.bsre',fixture,key,{nowMs:now,deletionLedgerWatermark:0}),/OWNER_ONLY_FILESYSTEM_UNSUPPORTED/);return;
 }
 const root=await mkdtemp(join(tmpdir(),'bsre-package-'));await chmod(root,0o700);
 try{
  await mkdir(join(root,'real'),{mode:0o700});await mkdir(join(root,'real','nested'),{mode:0o700});await symlink(join(root,'real'),join(root,'alias'));
  for(const dir of [join(root,'alias'),join(root,'alias','nested')]){
   await assert.rejects(writeOwnerOnlyPackage(dir,'x.bsre',fixture,key,{nowMs:now,deletionLedgerWatermark:0}),/OWNER_ONLY_DIRECTORY_REQUIRED/);
   await assert.rejects(deleteExpiredOwnerOnlyPackage(dir,'x.bsre',key,{nowMs:now+WINDOW_MS}),/OWNER_ONLY_DIRECTORY_REQUIRED/);
  }
 }finally{
  assert.equal(resolve(root).startsWith(resolve(tmpdir())+'/bsre-package-'),true);await rm(root,{recursive:true,force:true});
 }
});
