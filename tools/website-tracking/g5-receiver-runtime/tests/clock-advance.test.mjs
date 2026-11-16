import assert from 'node:assert/strict';
import {createHmac,verify} from 'node:crypto';
import test from 'node:test';
import {createActualControlFixture,json,hash,signEvidence,TEST_PUBLIC,INTENT} from './control-fixture.mjs';

// Explicit synthetic service latency. The receiver's actual Date implementation reads
// state.clock; each authenticated RPC finishes one or two seconds after its request.
function latency(r,seconds=1,mutate) {
  const fetch=r.context.UrlFetchApp.fetch;
  r.context.UrlFetchApp.fetch=(url,options)=>{
    const response=fetch(url,options),request=JSON.parse(JSON.parse(options.payload).body);
    const outer=JSON.parse(response.getContentText()),body=JSON.parse(outer.body);
    r.state.clock+=seconds;
    body.issued_at=r.state.clock;body.expires_at=r.state.clock+60;
    if(body.result&&Object.hasOwn(body.result,'observed_at')){
      body.result.observed_at=r.state.clock;body.result.expires_at=r.state.clock+300;
    }
    if(request.operation==='attest_control_result'){
      const statement=body.result.statement;
      statement.issued_at=r.state.clock;statement.expires_at=r.state.clock+60;
      body.result=signEvidence(statement);
    }
    if(mutate)mutate(body,request,r.state.clock);
    const raw=json(body),mac=createHmac('sha256','synthetic-separate-authority-secret-0000000000000000')
      .update('bsre-receiver-authority-response-v1\n'+raw).digest('hex');
    return {getResponseCode:()=>200,getContentText:()=>json({body:raw,mac})};
  };
}
const held=value=>{assert.equal(value.accepted,false);assert.equal(value.code,'ACTUAL_CONTROL_HELD');};
test('actual signed inspection accepts replies issued after one and two elapsed local seconds',()=>{
  for(const seconds of [1,2]){
    const r=createActualControlFixture();latency(r,seconds);const began=r.state.clock;
    const reply=r.control();assert.equal(reply.statement.claims.result.state,'UNRETIRED');
    assert.ok(r.state.clock>=began+3*seconds);
    assert.equal(reply.statement.issued_at,r.state.clock);
    assert.equal(verify(null,Buffer.from(hash(reply.statement)),TEST_PUBLIC,Buffer.from(reply.signature,'base64')),true);
    assert.equal(r.rows[1][6],'QUEUED');assert.equal(r.mail.length,0);
  }
});
test('multi-RPC retirement exceeding five elapsed seconds preserves original authority deadlines',()=>{
  const r=createActualControlFixture(),authorization=structuredClone(r.ownerIntents.get(INTENT));
  latency(r,1);const began=r.state.clock;
  const reply=r.control('retire',{scope:r.knownScope,intent_digest:INTENT});
  assert.equal(reply.statement.claims.result.row_state,'RETIRED');assert.ok(r.state.clock-began>5);
  assert.deepEqual(r.ownerIntents.get(INTENT),authorization);
  const fence=JSON.parse(r.properties[r.context.actualNoCopyKey_(r.knownScope.request_id)]).body;
  assert.ok(fence.created_at>=authorization.approved_at&&fence.created_at<authorization.create_before);
  assert.equal(fence.expires_at,fence.created_at+2592000);assert.equal(r.mail.length,0);
});
test('post-I/O local clock still rejects future, stale, expired and wrong-challenge service replies',()=>{
  for(const change of [
    (body,request,now)=>{body.issued_at=now+1;},
    (body,request,now)=>{body.issued_at=now-31;},
    (body,request,now)=>{body.expires_at=now;},
    body=>{body.challenge='0'.repeat(64);},
  ]){
    const r=createActualControlFixture();latency(r,2,change);held(r.control());
    assert.equal(r.rows[1][6],'QUEUED');assert.equal(r.remote.revision,1);assert.equal(r.mail.length,0);
  }
});
test('elapsed I/O cannot renew the original nine-hundred-second create authority',()=>{
  const r=createActualControlFixture(),authorization=structuredClone(r.ownerIntents.get(INTENT));
  latency(r,400);held(r.control('retire',{scope:r.knownScope,intent_digest:INTENT}));
  assert.deepEqual(r.ownerIntents.get(INTENT),authorization);assert.equal(r.rows[1][6],'QUEUED');
  assert.equal(r.remote.revision,1);assert.equal(r.mail.length,0);
});
