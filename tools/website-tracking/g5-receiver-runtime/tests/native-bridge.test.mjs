import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createInterface} from 'node:readline';
import {createHmac,verify} from 'node:crypto';
import {fileURLToPath} from 'node:url';
import test from 'node:test';
import {hash,json,NOW,TEST_PUBLIC} from './control-fixture.mjs';

async function bridge(run){
 const child=spawn(process.execPath,[fileURLToPath(new URL('./native-bridge.mjs',import.meta.url))],{stdio:['pipe','pipe','pipe']});
 let stderr='';child.stderr.on('data',data=>{stderr+=data;});const lines=createInterface({input:child.stdout})[Symbol.asyncIterator]();
 const exited=new Promise(resolve=>child.on('exit',resolve));
 const send=async value=>{child.stdin.write(JSON.stringify(value)+'\n');const line=await lines.next();assert.equal(line.done,false);return JSON.parse(line.value);};
 try{await run(send);}finally{child.stdin.end();assert.equal(await exited,0);assert.equal(stderr,'');}
}
const descriptor={contract:'bsre-retention-admission-v1',mode:'ENFORCED',generation:'a'.repeat(64),activated_at:Date.UTC(2022,0,1)/1000,max_age_seconds:900,audience:'b'.repeat(64)};
const control=(operation,body,number=1)=>{
 const env={control_contract:'bsre-receiver-control-v1',control_version:1,timestamp:NOW*1000,challenge:hash('native-bridge-'+number),operation,actor:'wp-user:37',body:json(body)};
 env.signature=createHmac('sha256','synthetic-secret-never-production-0000').update([env.control_contract,env.timestamp,env.challenge,env.operation,env.actor,env.body].join('\n')).digest('hex');return json(env);
};
test('fixed pipe bridge carries actual signed control proof from admitted Intake26 and durable registered intent',async()=>bridge(async send=>{
 const init=await send({op:'init',now:NOW,actor:'wp-user:37',descriptor,admission_hash:'d'.repeat(64)});assert.equal(init.ok,true);
 const id=init.value.identity;assert.equal(id.columns,26);assert.equal(id.email_attempts,0);assert.equal(init.value.selected_sha256,'00b62f1edc8996ab4f566a80155715a85f741bc5d68e7a0a54c94fc4ef2cbdc5');
 const before={schema_version:1,closure_id:id.request_id,revision:1,status:'CLOSED',request_id:id.request_id,lead_id:id.lead_id,event_id:id.event_id,accepted_at_utc:'2023-01-01T00:00:00Z',closed_at_utc:'2023-01-02T00:00:00Z',recorded_at_utc:'2023-01-03T00:00:00Z',reviewer:'wp-user:37',evidence_reference:'SYNTHETIC_RECEIVER_CLOSURE',evidence_hash:'a'.repeat(64),outcome_ids:[],mail_message_ids:[],email_status:'QUEUED'};
 const after={...before,revision:2,email_status:'RETIRED_NO_COPY'};
 const scope={contract:'bsre-closed-no-mail-copy-v1',closure_id:id.request_id,closure_revision:2,closure_hash:hash(after),request_id:id.request_id,lead_id:id.lead_id,event_id:id.event_id,fingerprint:id.fingerprint,admission_hash:'d'.repeat(64)};
 assert.deepEqual(await send({op:'bind_scope',scope,accepted_at_utc:'2023-01-01T00:00:00.000Z'}),{ok:true,value:{bound:true}});
 const inspection=await send({op:'control',now:NOW,raw:control('inspect',{scope})});
 assert.equal(inspection.value.raw,json(inspection.value.reply),'raw actual ContentService response must already be canonical');
 assert.equal(inspection.value.reply.statement.claims.result.state,'UNRETIRED');
 const plan={schema_version:1,contract:'bsre-owner-no-mail-retirement-v1',closure_id:id.request_id,actor:'wp-user:37',before,after,before_hash:hash(before),after_hash:hash(after),scope,admission_hash:'d'.repeat(64),inventory_hash:hash(inspection.value.reply),created_at:NOW,expires_at:NOW+900};plan.digest=hash(plan);
 const record={schema_version:1,contract:plan.contract,revision:1,plan,approved_at:NOW,recovery_until:NOW+2592000,phase:'INTENT_RECORDED',proof_hash:null,hold_codes:[]};
 const held=await send({op:'control',now:NOW,raw:control('retire',{scope,intent_digest:plan.digest},2)});assert.equal(held.value.reply.code,'ACTUAL_CONTROL_HELD');
 assert.deepEqual(await send({op:'authorize_intent',record,now:NOW}),{ok:true,value:{registered:true,intent_digest:plan.digest}});
 const retired=await send({op:'control',now:NOW,raw:control('retire',{scope,intent_digest:plan.digest},3)}),reply=retired.value.reply;
 assert.equal(reply.statement.contract,'bsre-actual-receiver-evidence-v1');assert.equal(reply.statement.source.receiver,init.value.source_hash);
 assert.equal(reply.statement.claims.result.row_state,'RETIRED');assert.equal(reply.statement.claims.intent_digest,plan.digest);
 assert.equal(verify(null,Buffer.from(hash(reply.statement)),TEST_PUBLIC,Buffer.from(reply.signature,'base64')),true);
 const stats=(await send({op:'stats'})).value;assert.equal(stats.rows,1);assert.equal(stats.mail,0);assert.equal(stats.intake_deletes,0);assert.equal(stats.status,'RETIRED_NO_COPY');assert.equal(stats.attempts,0);assert.equal(stats.epoch_revision,2);
 const cleanup=await send({op:'control',now:NOW,raw:control('prepare_cleanup',{scope},4)});assert.equal(cleanup.value.reply.code,'ACTUAL_CONTROL_HELD');
}));
test('fixed pipe bridge rejects operations before initialization without exposing raw material',async()=>bridge(async send=>{
 assert.deepEqual(await send({op:'control',raw:'private-looking-arbitrary-input'}),{ok:false,error:'SYNTHETIC_RECEIVER_BRIDGE_HELD'});
 assert.deepEqual(await send({op:'unknown'}),{ok:false,error:'SYNTHETIC_RECEIVER_BRIDGE_HELD'});
}));
