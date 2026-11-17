import test from 'node:test';import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';import {join} from 'node:path';
import {createPrivateKey,sign} from 'node:crypto';
import {here,build,deriveJournal,derivePreference,editExact} from '../build-private.mjs';
import {validateLocalReceipt,parseLocal,digest,sha,zero,unresolved} from '../validate-local.mjs';
const source=join(here,'../../..');
const pub=Buffer.from('d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a','hex');
const key=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.from('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60d','hex')]),format:'der',type:'pkcs8'});
const clone=v=>structuredClone(v);const stamp=v=>{delete v.digest;v.digest=digest(v);return v;};
const signProof=e=>{e.signature=sign(null,Buffer.from(digest(e.statement)),key).toString('base64');return e;};
function fixture(){
 const now=2000000000,base=sha('SYNTHETIC_G39_BASE'),actor='wp-user:1',ledger=readFileSync(join(here,'native/synthetic-ledger.json'));
 const config={contract:'bsre-retention-admission-v1',mode:'ENFORCED',generation:sha('generation'),activated_at:now-1000,max_age_seconds:900,audience:sha('audience')};
 const admission={wp:{...config,routes_installed:true,store_installed:true},receiver:{...config},source_hashes:{wp:sha('wp-source'),receiver:sha('receiver-source')},restore_policy_hash:sha('restore'),evidence_reference:'SYNTHETIC_G39_LOCAL_ONLY',evidence_hash:sha('evidence'),observed_at:now,expires_at:now+300};
 const configHash=digest({wp:admission.wp,receiver:admission.receiver,source_hashes:admission.source_hashes,restore_policy_hash:admission.restore_policy_hash});
 const context={now,base_scope:base,actor,ledger_bytes:ledger,admission_configuration:config,preference_source:{preference:sha('pref-source'),canonical:sha('canonical'),producer:sha('producer'),admission:digest(config)},trusted_preference_keys:{}};
 const partitions=Array.from({length:256},(_,i)=>{
  const partition=i.toString(16).padStart(2,'0'),scope=sha('bsre-preference-runtime-v1|'+base+'|partition:'+partition),a=zero();
  if(partition==='aa'){a.operation_revision=1;a.state_hash=sha('SYNTHETIC_AA_CIPHER');}
  context.trusted_preference_keys[scope]={'synthetic-rfc8032':pub};
  const proofs=[0,1].map(n=>{const request={contract:'bsre-preference-runtime-v1',service:'preference-anchor',operation:'CURRENT',scope,source:context.preference_source,actor,challenge:sha(partition+':'+n),payload:[]};return signProof({key_id:'synthetic-rfc8032',statement:{...request,payload:undefined,request_hash:digest(request),issued_at:now,expires_at:now+30,claims:{anchor:a}},signature:''});});
  for(const e of proofs)delete e.statement.payload;
  // Sign the exact closed statement after removing the request-only payload.
  for(const e of proofs)signProof(e);
  return {partition,scope,observation:partition==='aa'?'ANCHORED_LEDGER':'ZERO_ANCHOR_AND_PHYSICAL_ABSENCE',anchor:a,body_sha256:partition==='aa'?a.state_hash:null,floor_generation:0,proofs};
 });
 const v=stamp({schema:'bsre-g39-local-history-observation-v1',authority:'LOCAL_OBSERVATION_ONLY',base_scope:base,actor,observed_at:now,expires_at:now+30,connection_id:'123',journal:{scope:base,anchor:{revision:1,hash:sha('journal')},cipher_sha256:sha('journal'),incomplete:false,admission_floor:null},control_inventory:['aa'],partitions,inputs:{ledger_sha256:sha(ledger),ledger_bytes:ledger.length,admission_sha256:digest(admission),admission_configuration_sha256:configHash,admission},local_vetoes:[],unresolved_authority:[...unresolved]});
 return {v,context};
}
const initial=fixture();
function mutation(label,change,code){test(label,()=>{const v=clone(initial.v),context={...initial.context};change(v,context);stamp(v);assert.throws(()=>validateLocalReceipt(v,context),code);});}
test('complete synthetic local receipt validates but provides local scope only',()=>{const r=validateLocalReceipt(initial.v,initial.context);assert.equal(r.kind,'VALIDATED_LOCAL_RECEIPT_ONLY');assert.equal(r.partitions,256);assert.deepEqual(r.unresolved_authority,unresolved);assert.equal('history_marker_verified' in r,false);});
mutation('a single zero-floor partition cannot cover the namespace',v=>{v.partitions=v.partitions.slice(170,171);},/ALL_PARTITIONS/);
mutation('missing partition rejected',v=>{v.partitions.pop();},/ALL_PARTITIONS/);
mutation('duplicate partition rejected',v=>{v.partitions[1]=clone(v.partitions[0]);},/PARTITION_ORDER/);
mutation('partition reorder rejected',v=>{[v.partitions[1],v.partitions[2]]=[v.partitions[2],v.partitions[1]];},/PARTITION_ORDER/);
mutation('missing second current challenge rejected',v=>{v.partitions[0].proofs.pop();},/PROOF_COUNT/);
mutation('cross-partition proof rejected',v=>{v.partitions[1].proofs[0]=clone(v.partitions[0].proofs[0]);},/PROOF_BINDING/);
mutation('forged current signature rejected',v=>{v.partitions[0].proofs[0].signature=Buffer.alloc(64,120).toString('base64');},/SIGNATURE/);
mutation('expired current proof rejected',v=>{v.partitions[0].proofs[0].statement.expires_at=initial.context.now;},/PROOF_FRESHNESS/);
mutation('31-second-old current proof is rejected despite 29 seconds signed TTL',v=>{v.partitions[0].proofs[0].statement.issued_at=initial.context.now-31;v.partitions[0].proofs[0].statement.expires_at=initial.context.now+29;},/PROOF_FRESHNESS/);
mutation('out-of-domain physical id is rejected',v=>{v.control_inventory=['aa','gg'];},/CONTROL_DOMAIN/);
mutation('omitted initialized physical id is rejected',v=>{v.control_inventory=[];},/CONTROL_RECONCILIATION/);
mutation('duplicate physical id is rejected',v=>{v.control_inventory=['aa','aa'];},/CONTROL_DOMAIN/);
mutation('replayed current challenge rejected',v=>{v.partitions[0].proofs[1]=clone(v.partitions[0].proofs[0]);},/REPLAY/);
mutation('one reusable key does not enroll another partition',(_v,c)=>{c.trusted_preference_keys={...c.trusted_preference_keys};delete c.trusted_preference_keys[initial.v.partitions[255].scope];},/SCOPE_NOT_ENROLLED/);
mutation('partial zero is not exact zero',v=>{v.partitions[0].anchor.operation_revision=1;v.partitions[0].anchor.state_hash=sha('nonzero');},/ZERO/);
mutation('changed ledger bytes rejected',(_v,c)=>{c.ledger_bytes=Buffer.from('different');},/LEDGER_BYTES/);
mutation('stale admission rejected',v=>{v.inputs.admission.expires_at=initial.context.now;},/ADMISSION_STALE/);
mutation('future admission rejected',v=>{v.inputs.admission.observed_at=initial.context.now+1;},/ADMISSION_STALE/);
mutation('changed current admission configuration rejected',(_v,c)=>{c.admission_configuration={...c.admission_configuration,generation:sha('changed')};},/ADMISSION_BINDING/);
mutation('global authority promotion rejected',v=>{v.authority='WHOLE_BUSINESS_HISTORY_COMPLETE';},/AUTHORITY/);
mutation('unknown history-marker claim rejected',v=>{v.history_marker_verified=true;},/KEYS/);
mutation('missing local history veto rejected',v=>{v.journal.incomplete=true;},/VETO/);
test('observed incomplete journal remains a local veto',()=>{const v=clone(initial.v);v.journal.incomplete=true;v.local_vetoes=['SUBMITTED_JOURNAL_INCOMPLETE'];stamp(v);assert.deepEqual(validateLocalReceipt(v,initial.context).local_vetoes,v.local_vetoes);});
test('observed compacted preference remains a local veto',()=>{const v=clone(initial.v),p=v.partitions[170];Object.assign(p.anchor,{sequence:1,chain_hash:sha('floor'),floor_sequence:1,floor_hash:sha('floor'),floor_generation:1,compacted_at:initial.context.now-1});p.floor_generation=1;for(const e of p.proofs){e.statement.claims.anchor=p.anchor;signProof(e);}v.local_vetoes=['PREFERENCE_COMPACTED_HISTORY:aa'];stamp(v);assert.deepEqual(validateLocalReceipt(v,initial.context).local_vetoes,v.local_vetoes);});
test('duplicate malformed oversized and pretty JSON rejected',()=>{assert.throws(()=>parseLocal('{"a":1,"a":2}'),/CANONICAL_JSON/);assert.throws(()=>parseLocal('{bad'),SyntaxError);assert.throws(()=>parseLocal(' '.repeat(2097153)),/SIZE/);assert.throws(()=>parseLocal('{ "a": 1 }'),/CANONICAL_JSON/);});
test('pinned packet derives all original guard bodies reversibly',()=>{const p=build(source);assert.equal(p.files.size,25);assert.equal(p.manifest.expected_checks.length,35);for(const name of ['ActualReceiverJournal.php','ActualPurgeJournal.php','PreferenceAtomicStore.php','local-history-native.php'])assert.equal(p.manifest.derivations[name].reverse_verified,true);assert.equal(p.manifest.local_scope_only,true);});
test('accepted full foreign scanner is exact and covers complete keysets above1000',()=>{const p=build(source),path='tools/website-tracking/g5-actual-purge-runtime/tests/foreign-capture-snapshot.php';assert.deepEqual(p.files.get('tests/foreign-capture-snapshot.php'),readFileSync(join(source,path)));const code=p.files.get('tests/foreign-capture-snapshot.php').toString();assert.match(code,/while\(true\)/);assert.match(code,/ORDER BY BINARY request_id LIMIT 256/);assert.match(code,/\$seen!==\$expected/);const driver=p.files.get('tests/local-history-native.php').toString();assert.ok(driver.indexOf('$g39ForeignBefore=')<driver.indexOf('E\\install();'));assert.ok(driver.indexOf('$g39ForeignAfter=')>driver.indexOf("require __DIR__.'/native-history.php'"));assert.match(driver,/\$row\['rows'\]>=1100/);assert.equal(p.manifest.expected_checks.at(-1),'g39_all_foreign_capture_tables_preserved');});
test('all cut002 native names retain their relative order',()=>{const old=JSON.parse(readFileSync(join(here,'tests/cut002-native-checks.json'),'utf8')).expected_checks,newer=build(source).manifest.expected_checks;assert.deepEqual(newer.slice(0,old.length),old);assert.equal(newer.length,old.length+1);});
test('drifted old journal cleanup anchor is held',()=>{const p=readFileSync(join(source,'tools/website-tracking/g5-receiver-runtime/candidate/plugin/includes/candidate/closed-enquiry-retention/ActualReceiverJournal.php'));assert.throws(()=>deriveJournal(p.toString().replace('                if ($held) {','                if ($held || true) {')),/EDIT_ANCHOR/);});
test('drifted old preference lease anchor is held',()=>{const p=readFileSync(join(source,'tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/PreferenceAtomicStore.php'));assert.throws(()=>derivePreference(p.toString().replace('        if(!$this->leased||!$this->db->custodyIsActive()','        if(false||!$this->db->custodyIsActive()')),/EDIT_ANCHOR/);});
test('duplicate derivative anchors fail closed',()=>{assert.throws(()=>editExact(Buffer.from('twice twice'),[['duplicate','twice','replacement']]),/EDIT_ANCHOR/);});
test('borrowed read has no lock/custody owner operations or callback',()=>{const m=readFileSync(join(here,'edits/preference-history-methods.php.txt'),'utf8').replace(/\/\*\*[\s\S]*?\*\//g,'');assert.doesNotMatch(m,/GET_LOCK|RELEASE_LOCK|beginCustody|endCustody|callable/);const d=derivePreference(readFileSync(join(source,'tools/website-tracking/g5-preference-runtime/candidate/plugin/includes/candidate/retention/PreferenceAtomicStore.php'))).bytes.toString();assert.match(d,/if\(\$this->historyBorrowed\)Guard::fail\('G39_READ_ONLY_BORROW_NO_MUTATION'\)/);});
