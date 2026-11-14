// Synthetic recovery-package candidate. No provider, key store, restore or scheduler.
import {createCipheriv,createDecipheriv,createHash,randomBytes} from 'node:crypto';
import {constants} from 'node:fs';
import {lstat,realpath,open,unlink} from 'node:fs/promises';
import {join,resolve} from 'node:path';

export const SOURCE='SYNTHETIC_BSRE_LAB';
export const WINDOW_MS=30*24*60*60*1000;
export const MAX_SNAPSHOT_BYTES=8*1024*1024;
const MAGIC=Buffer.from('BSR1');
const FIELDS=['version','source','createdAtMs','expiresAtMs','snapshotSha256','deletionLedgerWatermark'];
const fail=()=>{throw Error('INVALID_RECOVERY_PACKAGE');};
const epoch=n=>Number.isSafeInteger(n)&&n>0&&n<=Number.MAX_SAFE_INTEGER-WINDOW_MS;
const watermark=n=>Number.isSafeInteger(n)&&n>=0;
const hash=bytes=>createHash('sha256').update(bytes).digest('hex');
function keyCheck(key){if(!Buffer.isBuffer(key)||key.length!==32)fail();}
function timeCheck(meta,nowMs,allowExpired=false){
 if(!epoch(nowMs)||!epoch(meta.createdAtMs)||meta.expiresAtMs!==meta.createdAtMs+WINDOW_MS||nowMs<meta.createdAtMs||(!allowExpired&&nowMs>=meta.expiresAtMs))fail();
}
function parse(bytes,nowMs,allowExpired=false){
 if(!Buffer.isBuffer(bytes)||bytes.length>MAX_SNAPSHOT_BYTES+2048||bytes.length<8+12+16+1||!bytes.subarray(0,4).equals(MAGIC))fail();
 const size=bytes.readUInt32BE(4);
 if(size<1||size>1024||bytes.length<=8+size+12+16||bytes.length-(8+size+12+16)>MAX_SNAPSHOT_BYTES)fail();
 const aad=bytes.subarray(0,8+size),raw=bytes.subarray(8,8+size);
 let meta;try{meta=JSON.parse(raw.toString('utf8'));}catch{fail();}
 if(meta===null||Array.isArray(meta)||typeof meta!=='object'||JSON.stringify(Object.keys(meta))!==JSON.stringify(FIELDS)||JSON.stringify(meta)!==raw.toString('utf8'))fail();
 if(meta.version!==1||meta.source!==SOURCE||!watermark(meta.deletionLedgerWatermark)||typeof meta.snapshotSha256!=='string'||!/^[a-f0-9]{64}$/.test(meta.snapshotSha256))fail();
 timeCheck(meta,nowMs,allowExpired);
 return {metadata:meta,aad,nonce:bytes.subarray(8+size,20+size),tag:bytes.subarray(20+size,36+size),ciphertext:bytes.subarray(36+size)};
}

/** Key must be newly generated/dedicated by the caller; never stored or logged here. */
export function sealPackage(snapshot,key,{nowMs=Date.now(),deletionLedgerWatermark}={}){
 keyCheck(key);
 if(!Buffer.isBuffer(snapshot)||snapshot.length<1||snapshot.length>MAX_SNAPSHOT_BYTES||!epoch(nowMs)||!watermark(deletionLedgerWatermark))fail();
 const metadata={version:1,source:SOURCE,createdAtMs:nowMs,expiresAtMs:nowMs+WINDOW_MS,snapshotSha256:hash(snapshot),deletionLedgerWatermark};
 const raw=Buffer.from(JSON.stringify(metadata)),prefix=Buffer.alloc(8);
 MAGIC.copy(prefix);prefix.writeUInt32BE(raw.length,4);
 const aad=Buffer.concat([prefix,raw]),nonce=randomBytes(12),cipher=createCipheriv('aes-256-gcm',key,nonce,{authTagLength:16});
 cipher.setAAD(aad);
 const encrypted=Buffer.concat([cipher.update(snapshot),cipher.final()]);
 return Buffer.concat([aad,nonce,cipher.getAuthTag(),encrypted]);
}

/** Authentication is not restore authorization: reconcile a fresh external ledger. */
export function openPackage(bytes,key,{nowMs=Date.now()}={}){
 keyCheck(key);
 return authenticate(bytes,key,nowMs,false);
}
function authenticate(bytes,key,nowMs,allowExpired){
 let update,final,snapshot;
 try{
  const p=parse(bytes,nowMs,allowExpired),decipher=createDecipheriv('aes-256-gcm',key,p.nonce,{authTagLength:16});
  decipher.setAAD(p.aad);decipher.setAuthTag(p.tag);
  update=decipher.update(p.ciphertext);final=decipher.final();snapshot=Buffer.concat([update,final]);
  update.fill(0);final.fill(0);
  if(hash(snapshot)!==p.metadata.snapshotSha256)fail();
  return {snapshot,metadata:Object.freeze(p.metadata),restoreAuthorized:false};
 }catch{update?.fill(0);final?.fill(0);snapshot?.fill(0);fail();}
}

async function ownerDirectory(directory,filename){
 if(process.platform==='win32'||typeof process.getuid!=='function'||!constants.O_NOFOLLOW)throw Error('OWNER_ONLY_FILESYSTEM_UNSUPPORTED');
 if(typeof directory!=='string'||typeof filename!=='string'||! /^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(filename))throw Error('OWNER_ONLY_PATH_REQUIRED');
 const path=resolve(directory),before=await lstat(path);
 if(!before.isDirectory()||before.isSymbolicLink()||before.uid!==process.getuid()||(before.mode&0o7777)!==0o700||await realpath(path)!==path)throw Error('OWNER_ONLY_DIRECTORY_REQUIRED');
 return {path,before,target:join(path,filename)};
}

/** POSIX only: existing owner-private directory, no symlinks, no overwrite.
 * Provider/OS identity and encryption-key custody remain separate acceptance gates.
 */
export async function writeOwnerOnlyPackage(directory,filename,snapshot,key,options){
 const {path,before,target}=await ownerDirectory(directory,filename);
 const bytes=sealPackage(snapshot,key,options),metadata=parse(bytes,options?.nowMs??Date.now()).metadata;
 const fd=await open(target,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);
 let identity;
 try{
  identity=await fd.stat();
  if(!identity.isFile()||identity.uid!==process.getuid()||(identity.mode&0o7777)!==0o600||identity.nlink!==1)throw Error('OWNER_ONLY_FILE_REQUIRED');
  await fd.writeFile(bytes);await fd.sync();
  const after=await lstat(path),file=await lstat(target);
  if(after.dev!==before.dev||after.ino!==before.ino||after.uid!==before.uid||(after.mode&0o7777)!==0o700||file.dev!==identity.dev||file.ino!==identity.ino||file.uid!==process.getuid()||file.isSymbolicLink()||file.nlink!==1||(file.mode&0o7777)!==0o600)throw Error('OWNER_ONLY_PATH_CHANGED');
  return {bytes:bytes.length,expiresAtMs:metadata.expiresAtMs,productionAcceptance:false};
 }catch(error){
  // Only remove the exact new inode this call opened; never follow a replaced path.
  try{const current=await lstat(target);if(identity&&current.dev===identity.dev&&current.ino===identity.ino)await unlink(target);}catch{}
  throw error;
 }finally{await fd.close();}
}

/** Explicit lab-only expiry cleanup; authenticates expired bytes without returning them.
 * This is not a provider scheduler or a hostile-same-user filesystem boundary.
 */
export async function deleteExpiredOwnerOnlyPackage(directory,filename,key,{nowMs=Date.now()}={}){
 const {path,before,target}=await ownerDirectory(directory,filename);keyCheck(key);
 const fd=await open(target,constants.O_RDONLY|constants.O_NOFOLLOW);
 try{
  const identity=await fd.stat();
  if(!identity.isFile()||identity.uid!==process.getuid()||(identity.mode&0o7777)!==0o600||identity.nlink!==1||identity.size<1||identity.size>MAX_SNAPSHOT_BYTES+2048)throw Error('OWNER_ONLY_FILE_REQUIRED');
  const bytes=Buffer.alloc(identity.size);let offset=0;
  while(offset<bytes.length){const {bytesRead}=await fd.read(bytes,offset,bytes.length-offset,offset);if(!bytesRead)throw Error('OWNER_ONLY_PATH_CHANGED');offset+=bytesRead;}
  if((await fd.read(Buffer.alloc(1),0,1,offset)).bytesRead!==0)throw Error('OWNER_ONLY_PATH_CHANGED');
  const result=authenticate(bytes,key,nowMs,true),expiresAtMs=result.metadata.expiresAtMs;
  result.snapshot.fill(0); // Expired plaintext never leaves this cleanup path.
  if(nowMs<expiresAtMs)throw Error('RECOVERY_NOT_EXPIRED');
  const after=await lstat(path),file=await lstat(target);
  if(after.dev!==before.dev||after.ino!==before.ino||after.uid!==before.uid||(after.mode&0o7777)!==0o700||await realpath(path)!==path||file.dev!==identity.dev||file.ino!==identity.ino||!file.isFile()||file.isSymbolicLink()||file.uid!==process.getuid()||(file.mode&0o7777)!==0o600||file.nlink!==1||file.size!==identity.size||file.mtimeMs!==identity.mtimeMs||file.ctimeMs!==identity.ctimeMs)throw Error('OWNER_ONLY_PATH_CHANGED');
  await unlink(target);
  return {deleted:true,expiresAtMs,productionAcceptance:false};
 }finally{await fd.close();}
}
