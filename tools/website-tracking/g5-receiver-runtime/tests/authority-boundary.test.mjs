import assert from 'node:assert/strict';
import test from 'node:test';
import {createActualControlFixture,INTENT} from './control-fixture.mjs';
test('actual retirement requires the same actor as the independently registered durable intent before mutation',()=>{
 const r=createActualControlFixture(),before=structuredClone(r.rows);
 const reply=r.control('retire',{scope:r.knownScope,intent_digest:INTENT},{actor:'wp-user:8'});
 assert.equal(reply.code,'ACTUAL_CONTROL_HELD');assert.deepEqual(r.rows,before);
 assert.equal(r.remote.revision,1);assert.equal(r.mail.length,0);
 assert.equal(r.properties[r.context.actualNoCopyKey_(r.knownScope.request_id)],undefined);
});
test('separate actual algebra supplies no unauthorised retirement entry or null-intent path',()=>{
 const r=createActualControlFixture();assert.equal(typeof r.context.actualNoCopyRetire,'undefined');
 assert.throws(()=>r.context.actualNoCopyRetireLocked_(r.knownScope,null),/RETIREMENT_AUTHORITY_UNVERIFIED/);
 assert.equal(r.rows[1][6],'QUEUED');assert.equal(r.calls.length,0);
 assert.equal(typeof r.context.closedNoCopyRetire,'function','original guarded local capability remains intact');
});
