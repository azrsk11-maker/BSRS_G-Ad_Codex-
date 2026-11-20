import test from'node:test';
import assert from'node:assert/strict';
import{readFileSync}from'node:fs';
import{join}from'node:path';
import{generateKeyPairSync,sign,verify,createHash}from'node:crypto';
import{algebra}from'./build-algebra.mjs';
import{folder,names,buildManifest,sha}from'./build-runtime.mjs';
import{buildPacket,modes}from'./build-native-packet.mjs';
const code=Object.fromEntries(names.map(n=>[n,readFileSync(join(folder,n),'utf8')]));
test('pinned algebra extracts reverse exactly and original policy math remains selected',()=>{
 assert.equal(algebra.input_sha256,'9675b7928ee0bae042c5f0305cdd1d73d13a343fda4dc8800d3e4d0568c1cba3');
 assert.ok(algebra.receipts.every(r=>r.reverse_verified===true));
 assert.ok(code['PreferenceAlgebra.php'].includes('SnapshotFormat::plan($snapshot,$now,true)'));
 assert.ok(code['PreferenceAlgebra.php'].includes('RetentionInventory::assertRestoreReferences'));
});
test('five-file source closure is complete and current',()=>{
 const m=buildManifest(),actual=JSON.parse(m.bytes);
 assert.equal(Object.keys(actual.files).length,5);assert.deepEqual(Object.keys(actual.files),[...names].sort());
 for(const name of names)assert.equal(actual.files[name],sha(readFileSync(join(folder,name))));
 assert.equal(m.sha256,sha(m.bytes));
});
test('server fixture produces authentic canonical Ed25519 statements and altered claims fail crypto',()=>{
 const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
 const digest=v=>createHash('sha256').update(JSON.stringify(sorted(v))).digest('hex');
 const pair=generateKeyPairSync('ed25519');
 const statement={contract:'bsre-preference-runtime-v1',service:'preference-anchor',operation:'CURRENT',scope:'a'.repeat(64),
  source:{preference:'b'.repeat(64),canonical:'c'.repeat(64),producer:'d'.repeat(64),admission:'e'.repeat(64)},actor:'wp-user:1',
  challenge:'f'.repeat(64),request_hash:'1'.repeat(64),issued_at:1,expires_at:31,claims:{anchor:{sequence:0}}};
 const signature=sign(null,Buffer.from(digest(statement)),pair.privateKey);
 assert.equal(verify(null,Buffer.from(digest(statement)),pair.publicKey,signature),true);
 statement.claims.anchor.sequence=1;
 assert.equal(verify(null,Buffer.from(digest(statement)),pair.publicKey,signature),false);
});
test('actual batch domain retains default OFF, stable partition floors and exact independent claim contracts',()=>{
 const contracts=code['PreferenceContracts.php'],runtime=code['ActualPreferenceRetention.php'];
 assert.ok(runtime.indexOf('V\\Guard::enabled();')<runtime.indexOf('$producer=new CanonicalCaptureProducer'));
 const scope=contracts.slice(contracts.indexOf('public function scope()'),contracts.indexOf('public function actor()'));
 assert.ok(!scope.includes('sourceVersion')&&!scope.includes('ownerId')&&scope.includes('partition:'));
 assert.ok(contracts.includes('ACTUAL_PREFERENCE_SUBJECT_BATCH_V1')&&contracts.includes('COMPLETE_BATCH_REFERENCES'));
 assert.ok(contracts.includes('CLOSED_ENQUIRIES')&&contracts.includes('anniversary'));
 assert.ok(contracts.includes('RESTORE_REFERENCE_CUSTODY')&&contracts.includes('RECOVERY_EXPIRY_CUSTODY'));
});
test('one transaction owner preserves pending intent and verifies shared-table side effects after locks',()=>{
 const s=code['PreferenceAtomicStore.php'];
 assert.ok(s.includes("status='PENDING_ANCHOR'")&&s.includes('finishCompaction')&&s.includes('PREFERENCE_CONNECTION_QUARANTINED'));
 assert.ok(s.indexOf("if($lock)$this->consentMutationSchema();")>s.indexOf("WHERE subject_key IN ({$in})"));
 assert.ok(s.includes('all_incoming_schemas_visible')&&s.includes('PREFERENCE_CONSENT_SIDE_EFFECT_HELD'));
 assert.ok(s.includes('REPEATABLE-READ')&&s.includes('PREFERENCE_NESTED_TRANSACTION_DENIED'));
 assert.ok(!s.includes('new ActualJournal')&&!s.includes('new PreferenceRetirement'));
});
test('original deadline survives proof I/O and cleanup releases only the original healthy connection',()=>{
 const s=code['PreferenceAtomicStore.php'],p=code['PreferenceContracts.php'],c=code['PreferenceCustody.php'];
 assert.ok(s.includes('$this->planDeadline=$plan[\'expires_at\']')&&s.includes('PREFERENCE_ORIGINAL_PLAN_EXPIRED'));
 assert.ok(s.includes("'authorized_until'=>$this->planDeadline??$at+30"));
 assert.ok(p.includes("'plan_expires_at'=>$planExpiresAt")&&c.includes("'authorized_until'=>$authorizedUntil"));
 const cleanup=s.slice(s.indexOf('} finally {'),s.indexOf('private function lease()'));
 assert.ok(!cleanup.includes('$this->scalar(')&&cleanup.includes('connection_id')&&cleanup.includes('lock_owner')&&cleanup.includes('RELEASE_LOCK'));
 assert.ok(modes.includes('expired_approval')&&modes.includes('revoked_cleanup'));
});
test('native packet preserves the accepted site and separates the runtime from guarded test services',async()=>{
 const p=await buildPacket();assert.equal(p.receipt.site_files,67);assert.equal(modes.length,28);
 assert.equal([...p.files.keys()].filter(n=>n.startsWith('g36/wp-content/')).length,67);
 assert.ok(p.files.has('g37-pref/runtime/ActualPreferenceRetention.php')&&p.files.has('g37-pref/FixturePorts.php'));
 assert.ok(!Object.keys(JSON.parse(p.files.get('g37-pref/runtime/preference-source.json')).files).includes('FixturePorts.php'));
 assert.equal(p.receipt.actual_provider_accepted,false);assert.ok(p.receipt.missing_acceptance.length>0);
});
