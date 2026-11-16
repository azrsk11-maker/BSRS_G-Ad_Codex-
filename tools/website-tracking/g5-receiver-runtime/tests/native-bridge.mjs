import assert from 'node:assert/strict';
import {createInterface} from 'node:readline';
import {createActualControlFixture,hash} from './control-fixture.mjs';
import {SELECTED_RECEIVER_SHA256} from '../build-candidate.mjs';

// Fixed local pipe fixture only. No HTTP server, credentials, Google client or
// provider endpoint is started. Every authority is visibly synthetic test code.
let fixture,lastControlRaw;
for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})){
 try{
  assert.ok(line.length>0&&line.length<=2097152);
  const message=JSON.parse(line);assert.ok(message&&typeof message==='object'&&!Array.isArray(message));
  let value;
  if(message.op==='init'){
   assert.equal(fixture,undefined);assert.ok(Number.isSafeInteger(message.now));
   fixture=createActualControlFixture({now:message.now,actor:message.actor,descriptor:message.descriptor,admissionHash:message.admission_hash});
   const output=fixture.context.ContentService.createTextOutput;
   fixture.context.ContentService.createTextOutput=text=>{lastControlRaw=text;return output(text);};
   const row=fixture.rows[1];
   value={source_hash:fixture.sourceHash,namespace:fixture.namespace,selected_bytes:50830,selected_sha256:SELECTED_RECEIVER_SHA256,
    identity:{request_id:row[0],lead_id:row[1],event_id:row[2],fingerprint:row[4],columns:row.length,email_status:row[6],email_attempts:row[7]}};
  }else{
   assert.ok(fixture,'SYNTHETIC_BRIDGE_NOT_INITIALIZED');
   if(message.now!==undefined){assert.ok(Number.isSafeInteger(message.now)&&message.now>=fixture.state.clock);fixture.state.clock=message.now;}
   if(message.op==='bind_scope'){
    const at=Date.parse(message.accepted_at_utc);assert.ok(Number.isFinite(at));
    assert.equal(new Date(at).toISOString(),message.accepted_at_utc);
    fixture.fixtureAgeAcceptanceBeforeApproval(at/1000);fixture.bindKnownScope(message.scope);value={bound:true};
   }else if(message.op==='control'){
    assert.equal(typeof message.raw,'string');assert.ok(message.raw.length<=65536);
    lastControlRaw=null;const reply=fixture.postControl(message.raw);
    assert.equal(typeof lastControlRaw,'string');value={reply,raw:lastControlRaw};
   }else if(message.op==='authorize_intent'){
    // Only the PHP fixed ReviewTransport calls this after verifying the current
    // independently signed anchor and decrypting the exact durable journal job.
    const claim=fixture.authorizeIntent(message.record);value={registered:true,intent_digest:claim.intent_digest};
   }else if(message.op==='stats'){
    const row=fixture.rows[1];
    value={rows:fixture.rows.length-1,columns:row.length,status:row[6],attempts:row[7],sent_at:row[10],send_started_at:row[25],
     mail:fixture.mail.length,intake_deletes:fixture.state.intakeDeletes,epoch_revision:fixture.remote.revision,
     rows_hash:hash(fixture.rows),authority_calls:fixture.calls.length};
   }else throw Error('SYNTHETIC_BRIDGE_OPERATION_INVALID');
  }
  process.stdout.write(JSON.stringify({ok:true,value})+'\n');
 }catch(error){
  // Never print raw control/journal material. A failed fixture operation cannot
  // masquerade as an accepted provider record.
  process.stdout.write(JSON.stringify({ok:false,error:'SYNTHETIC_RECEIVER_BRIDGE_HELD'})+'\n');
 }
}
