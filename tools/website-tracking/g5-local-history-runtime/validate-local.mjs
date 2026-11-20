import {createHash,createPublicKey,verify} from 'node:crypto';
export const unresolved=Object.freeze(['AUTHORITATIVE_WHOLE_LEDGER_SCOPE_UNBOUND','INDEPENDENT_HISTORY_PRODUCER_NOT_ENROLLED','EXTERNAL_ANCHORS_HAVE_NO_AGGREGATE_READ_LEASE']);
const need=(v,c)=>{if(!v)throw Error(c);};
export const sha=b=>createHash('sha256').update(b).digest('hex');
export function sorted(v){if(Array.isArray(v))return v.map(sorted);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])]));return v;}
export const digest=v=>sha(JSON.stringify(sorted(v)));
const eq=(a,b)=>JSON.stringify(sorted(a))===JSON.stringify(sorted(b));
const keys=(o,k)=>need(o!==null&&typeof o==='object'&&!Array.isArray(o)&&eq(Object.keys(o).sort(),[...k].sort()),'G39_LOCAL_KEYS');
const hash=v=>need(typeof v==='string'&&/^[a-f0-9]{64}$/.test(v),'G39_LOCAL_HASH');
const uint=v=>need(Number.isSafeInteger(v)&&v>=0,'G39_LOCAL_UINT');
export function parseLocal(raw){need(typeof raw==='string'&&Buffer.byteLength(raw)<=2097152,'G39_LOCAL_SIZE');const v=JSON.parse(raw);need(JSON.stringify(v)===raw,'G39_LOCAL_CANONICAL_JSON');return v;}
export const zero=()=>({version:1,operation_revision:0,sequence:0,chain_hash:'0'.repeat(64),floor_sequence:0,floor_hash:'0'.repeat(64),floor_generation:0,compacted_at:0,state_hash:'0'.repeat(64)});
function anchor(a){
 keys(a,Object.keys(zero()));need(a.version===1,'G39_LOCAL_ANCHOR');
 for(const k of ['operation_revision','sequence','floor_sequence','floor_generation','compacted_at'])uint(a[k]);
 for(const k of ['chain_hash','floor_hash','state_hash'])hash(a[k]);
 const z='0'.repeat(64);
 need(a.floor_sequence<=a.sequence&&(a.sequence===0)===(a.chain_hash===z)&&(a.operation_revision===0)===(a.state_hash===z)&&
  (a.floor_generation!==0||(a.floor_sequence===0&&a.floor_hash===z&&a.compacted_at===0))&&
  (a.floor_generation===0||(a.floor_sequence>0&&a.compacted_at>0)),'G39_LOCAL_ANCHOR');
}
function admission(v,now){
 keys(v,['wp','receiver','source_hashes','restore_policy_hash','evidence_reference','evidence_hash','observed_at','expires_at']);
 hash(v.restore_policy_hash);hash(v.evidence_hash);need(typeof v.evidence_reference==='string'&&v.evidence_reference.length>0&&v.evidence_reference.length<=256&&!/[\x00-\x1f\x7f]/.test(v.evidence_reference)&&v.evidence_reference.trim()===v.evidence_reference,'G39_LOCAL_ADMISSION');
 need(Number.isSafeInteger(v.observed_at)&&Number.isSafeInteger(v.expires_at)&&v.observed_at<=now&&now<v.expires_at&&v.expires_at<=v.observed_at+300,'G39_LOCAL_ADMISSION_STALE');
 keys(v.source_hashes,['wp','receiver']);hash(v.source_hashes.wp);hash(v.source_hashes.receiver);
 for(const name of ['wp','receiver']){
  const g=v[name];keys(g,['contract','mode','generation','activated_at','max_age_seconds','audience',...(name==='wp'?['routes_installed','store_installed']:[])]);
  hash(g.generation);hash(g.audience);need(g.contract==='bsre-retention-admission-v1'&&g.mode==='ENFORCED'&&g.max_age_seconds===900&&Number.isSafeInteger(g.activated_at)&&g.activated_at>0&&g.activated_at<=now,'G39_LOCAL_ADMISSION');
  if(name==='wp')need(g.routes_installed===true&&g.store_installed===true,'G39_LOCAL_ADMISSION');
 }
 for(const k of ['generation','audience','activated_at'])need(v.wp[k]===v.receiver[k],'G39_LOCAL_ADMISSION');
 return digest({wp:v.wp,receiver:v.receiver,source_hashes:v.source_hashes,restore_policy_hash:v.restore_policy_hash});
}
/** Validates a local observation, never authorizes qualification, exports, enrollment or global history. */
export function validateLocalReceipt(v,context){
 keys(v,['schema','authority','base_scope','actor','observation_started_at','snapshot_started_at','elapsed_ms','snapshot_guard_sha256','observed_at','completed_at','expires_at','connection_id','journal','control_inventory','partitions','inputs','local_vetoes','unresolved_authority','digest']);
 const now=context.now;uint(now);hash(v.base_scope);hash(v.digest);
 need(v.schema==='bsre-g39-local-history-observation-v2'&&v.authority==='LOCAL_OBSERVATION_ONLY'&&eq(v.unresolved_authority,unresolved),'G39_LOCAL_AUTHORITY');
 const copy={...v};delete copy.digest;need(digest(copy)===v.digest,'G39_LOCAL_DIGEST');
 need(v.base_scope===context.base_scope&&v.actor===context.actor&&typeof v.actor==='string'&&/^wp-user:[1-9][0-9]*$/.test(v.actor),'G39_LOCAL_SCOPE');
 need(Number.isSafeInteger(v.observed_at)&&Number.isSafeInteger(v.expires_at)&&v.observed_at<=now&&now<v.expires_at&&v.expires_at<=v.observed_at+60,'G39_LOCAL_EXPIRED');
 uint(v.observation_started_at);uint(v.snapshot_started_at);uint(v.completed_at);uint(v.elapsed_ms);hash(v.snapshot_guard_sha256);
 need(v.observation_started_at>0&&v.observation_started_at<=v.snapshot_started_at&&v.snapshot_started_at<=v.observed_at&&v.observed_at<=v.completed_at&&v.completed_at<=now&&v.completed_at<v.observation_started_at+30&&v.elapsed_ms<30000&&v.expires_at<=v.observation_started_at+30,'G39_LOCAL_SNAPSHOT_STALE');
 need(typeof v.connection_id==='string'&&/^[1-9][0-9]*$/.test(v.connection_id),'G39_LOCAL_CONNECTION');
 keys(v.inputs,['ledger_sha256','ledger_bytes','admission_sha256','admission_configuration_sha256','admission']);
 need(Buffer.isBuffer(context.ledger_bytes)&&context.ledger_bytes.length===v.inputs.ledger_bytes&&sha(context.ledger_bytes)===v.inputs.ledger_sha256,'G39_LOCAL_LEDGER_BYTES');
 hash(v.inputs.admission_sha256);hash(v.inputs.admission_configuration_sha256);
 const configHash=admission(v.inputs.admission,now);
 need(digest(v.inputs.admission)===v.inputs.admission_sha256&&configHash===v.inputs.admission_configuration_sha256,'G39_LOCAL_ADMISSION_BINDING');
 const wp={...v.inputs.admission.wp};delete wp.routes_installed;delete wp.store_installed;
 need(eq(wp,context.admission_configuration),'G39_LOCAL_ADMISSION_BINDING');
 const j=v.journal;keys(j,['scope','anchor','cipher_sha256','incomplete','admission_floor']);keys(j.anchor,['revision','hash']);uint(j.anchor.revision);hash(j.anchor.hash);hash(j.cipher_sha256);
 need(j.scope===v.base_scope&&j.anchor.revision>0&&j.anchor.hash===j.cipher_sha256&&typeof j.incomplete==='boolean','G39_LOCAL_JOURNAL');
 if(j.admission_floor!==null)hash(j.admission_floor);
 const vetoes=[];if(j.incomplete)vetoes.push('SUBMITTED_JOURNAL_INCOMPLETE');if(j.admission_floor!==null&&j.admission_floor!==configHash)vetoes.push('SUBMITTED_ADMISSION_FLOOR_CONFLICT');
 need(Array.isArray(v.control_inventory)&&v.control_inventory.length<=256&&v.control_inventory.every(id=>typeof id==='string'&&/^[a-f0-9]{2}$/.test(id))&&new Set(v.control_inventory).size===v.control_inventory.length&&eq(v.control_inventory,[...v.control_inventory].sort()),'G39_LOCAL_CONTROL_DOMAIN');
 const inventory=new Set(v.control_inventory);
 need(Array.isArray(v.partitions)&&v.partitions.length===256,'G39_LOCAL_ALL_PARTITIONS');let earliest=v.inputs.admission.expires_at;const challenges=new Set();
 for(let i=0;i<256;i++){
  const p=v.partitions[i],part=i.toString(16).padStart(2,'0');keys(p,['partition','scope','observation','anchor','body_sha256','floor_generation','proofs']);
  const scope=sha('bsre-preference-runtime-v1|'+v.base_scope+'|partition:'+part);
  need(p.partition===part&&p.scope===scope,'G39_LOCAL_PARTITION_ORDER');anchor(p.anchor);uint(p.floor_generation);
  need(p.floor_generation===p.anchor.floor_generation,'G39_LOCAL_FLOOR');
  if(p.observation==='ZERO_ANCHOR_AND_PHYSICAL_ABSENCE')need(eq(p.anchor,zero())&&p.body_sha256===null&&p.floor_generation===0,'G39_LOCAL_ZERO');
  else{need(p.observation==='ANCHORED_LEDGER'&&p.anchor.operation_revision>0,'G39_LOCAL_STATE');hash(p.body_sha256);need(p.body_sha256===p.anchor.state_hash,'G39_LOCAL_STATE');}
  need((p.observation==='ANCHORED_LEDGER')===inventory.has(part),'G39_LOCAL_CONTROL_RECONCILIATION');
  if(p.floor_generation>0)vetoes.push('PREFERENCE_COMPACTED_HISTORY:'+part);
  need(Array.isArray(p.proofs)&&p.proofs.length===2,'G39_LOCAL_CURRENT_PROOF_COUNT');
  for(const e of p.proofs){
   keys(e,['key_id','statement','signature']);need(typeof e.key_id==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(e.key_id)&&typeof e.signature==='string','G39_LOCAL_PROOF');
   const s=e.statement;keys(s,['contract','service','operation','scope','source','actor','challenge','request_hash','issued_at','expires_at','claims']);
   need(s.contract==='bsre-preference-runtime-v1'&&s.service==='preference-anchor'&&s.operation==='CURRENT'&&s.scope===scope&&s.actor===v.actor&&eq(s.source,context.preference_source),'G39_LOCAL_PROOF_BINDING');
   hash(s.challenge);need(!challenges.has(s.challenge),'G39_LOCAL_REPLAY');challenges.add(s.challenge);
   const request={contract:s.contract,service:s.service,operation:s.operation,scope:s.scope,source:s.source,actor:s.actor,challenge:s.challenge,payload:[]};
   need(s.request_hash===digest(request),'G39_LOCAL_PROOF_REQUEST');
   need(Number.isSafeInteger(s.issued_at)&&Number.isSafeInteger(s.expires_at)&&s.issued_at<=v.observed_at&&s.issued_at<=now&&s.issued_at>=now-30&&now<s.expires_at&&s.expires_at<=s.issued_at+60,'G39_LOCAL_PROOF_FRESHNESS');
   keys(s.claims,['anchor']);need(eq(s.claims.anchor,p.anchor),'G39_LOCAL_PROOF_ANCHOR');
   // Explicit per-scope enrollment is caller configuration; a reusable public key implies no grant by itself.
   const rawKey=context.trusted_preference_keys?.[scope]?.[e.key_id];need(Buffer.isBuffer(rawKey)&&rawKey.length===32,'G39_LOCAL_SCOPE_NOT_ENROLLED');
   const sig=Buffer.from(e.signature,'base64');need(sig.length===64&&sig.toString('base64')===e.signature,'G39_LOCAL_SIGNATURE');
   const key=createPublicKey({key:Buffer.concat([Buffer.from('302a300506032b6570032100','hex'),rawKey]),format:'der',type:'spki'});
   need(verify(null,Buffer.from(digest(s)),key,sig),'G39_LOCAL_SIGNATURE');earliest=Math.min(earliest,s.expires_at,s.issued_at+30);
  }
 }
 need(v.expires_at<=earliest&&eq(v.local_vetoes,vetoes),'G39_LOCAL_VETO_OR_EXPIRY');
 return {kind:'VALIDATED_LOCAL_RECEIPT_ONLY',digest:v.digest,base_scope:v.base_scope,partitions:256,local_vetoes:[...vetoes],unresolved_authority:[...unresolved]};
}
