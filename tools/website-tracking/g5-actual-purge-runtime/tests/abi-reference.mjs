/** Executable review fixture ONLY. Published test key; no provider enrollment or network API. */
import {createPrivateKey,createPublicKey,sign,verify,createHash} from 'node:crypto';
export const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
export const digest=v=>createHash('sha256').update(canonical(v)).digest('hex');
const privateKey=createPrivateKey({key:Buffer.concat([Buffer.from('302e020100300506032b657004220420','hex'),Buffer.from('9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60d75a','hex')]),format:'der',type:'pkcs8'});
export const publicKey=createPublicKey(privateKey);
export function envelope(request,result,now){const statement={contract:'bsre-actual-purge-evidence-v1',actor:request.actor,policy:request.policy,source_hash:request.source_hash,operation:request.operation,challenge:request.challenge,request_hash:digest(request),issued_at:now,expires_at:now+30,result};return {key_id:'published-rfc8032-test-only',statement,signature:sign(null,Buffer.from(digest(statement)),privateKey).toString('base64')};}
export function verified(request,env,now){const s=env.statement;if(!s||s.contract!=='bsre-actual-purge-evidence-v1'||s.actor!==request.actor||s.policy!==request.policy||s.source_hash!==request.source_hash||s.operation!==request.operation||s.challenge!==request.challenge||s.request_hash!==digest(request)||s.issued_at>now||s.issued_at<now-30||s.expires_at<=now||s.expires_at>s.issued_at+60||!verify(null,Buffer.from(digest(s)),publicKey,Buffer.from(env.signature,'base64')))throw Error('UNVERIFIED');return s.result;}
/** Server contract must independently resolve exact approval/current anchor/providers, never trust booleans from client. */
export class AbiReviewFixture {
 constructor(){this.now=2000000000;this.approvals=new Map();this.currentJournal=null;this.currentSources=true;this.mailTrash=true;this.recovery=true;this.floor=true;this.afterRead=()=>{};this.removes=0;}
 approve(plan,action='PURGE',seconds=30){const grant={actor:'wp-user:7',action,plan_digest:digest(plan),approved_at:this.now,approval_expires_at:this.now+seconds};this.approvals.set(action+':'+grant.plan_digest,grant);return structuredClone(grant);}
 boundary(claim){const now=this.now,g=claim.grant,known=g&&this.approvals.get(g.action+':'+g.plan_digest);
  if(!known||canonical(known)!==canonical(g)||now<g.approved_at||now>=g.approval_expires_at||g.plan_digest!==digest(claim.plan)||g.action!==claim.action||!this.currentSources||!this.mailTrash||!this.recovery||!this.floor||canonical(this.currentJournal)!==canonical(claim.record))throw Error('CUSTODY_HELD');
  if(claim.action==='PURGE'&&claim.record&&claim.record.state!=='COMPLETE'&&now>=claim.record.started_at+2592000)throw Error('RECOVERY_EXPIRED');
 }
 remove(claim,store,binding,rows){if(store==='email')throw Error('MANUAL_ONLY');this.boundary(claim);const matches=claim.record.plan.resources.map((r,i)=>({r,i})).filter(({r})=>r.store===store&&canonical(r.binding)===canonical(binding));if(matches.length!==1||claim.record.steps[matches[0].i]!=='INTENT_RECORDED')throw Error('DURABLE_INTENT_REQUIRED');this.afterRead();this.boundary(claim);const key=binding.key;if(canonical(rows.get(key))!==canonical(binding))throw Error('BINDING_CHANGED');rows.delete(key);this.removes++;return {confirmed_absent:true,binding_hash:digest(binding)};}
}
