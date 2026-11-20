// Single-use pipe bridge: only synthetic snapshot bytes and an ephemeral key.
import {randomBytes} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {sealPackage,openPackage} from './recovery-package/package.mjs';
const command=JSON.parse(readFileSync(0,'utf8'));
const key=randomBytes(32),snapshot=Buffer.from(command.raw,'utf8');
const encrypted=sealPackage(snapshot,key,{nowMs:command.nowMs,deletionLedgerWatermark:command.watermark});
const opened=openPackage(encrypted,key,{nowMs:command.nowMs});
if(!opened.snapshot.equals(snapshot)||opened.restoreAuthorized!==false)throw Error('Synthetic roundtrip failed');
process.stdout.write(JSON.stringify({metadata:opened.metadata,raw:opened.snapshot.toString('utf8'),restoreAuthorized:false}));
key.fill(0);
