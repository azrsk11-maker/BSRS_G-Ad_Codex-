import {test} from 'node:test';
import assert from 'node:assert/strict';
import {lab} from './receiver-lab.mjs';
import {createHmac} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

test('bridge snapshot observes queued and sent records without processing mail',()=>{
  const body=JSON.stringify(lab().payload());
  const timestamp=String(Date.now());
  const raw=JSON.stringify({version:1,timestamp,body,signature:createHmac('sha256','synthetic-key-'.repeat(4)).update(`v1\n${timestamp}\n${body}`).digest('hex')});
  const commands=[{op:'post',raw},{op:'snapshot'},{op:'snapshot'},{op:'outbox'},{op:'snapshot'}];
  const result=spawnSync(process.execPath,[fileURLToPath(new URL('./receiver-bridge.mjs',import.meta.url))],
    {input:commands.map(command=>JSON.stringify(command)).join('\n')+'\n',encoding:'utf8',timeout:10000,maxBuffer:1024*1024});
  assert.equal(result.status,0,result.stderr);
  const results=result.stdout.trim().split('\n').map(line=>JSON.parse(line));
  assert.equal(results.length,5);
  assert.equal(results[0].accepted,true);
  assert.deepEqual(results[1],results[2]);
  assert.equal(results[1].rows.length,1);
  assert.equal(results[1].rows[0][6],'QUEUED');
  assert.equal(results[1].mail.length,0);
  assert.equal(results[3].mail.length,1);
  assert.deepEqual(results[3],results[4]);
});

test('actual receiver preserves 26 columns and reuses normalized request receipt',()=>{const l=lab(),p=l.payload(),a=l.post(p);assert.equal(a.accepted,true);assert.equal(l.rows[1].length,26);assert.equal(l.rows[1][6],'QUEUED');assert.equal(l.mail.length,0);assert.deepEqual(l.post(p),a);assert.equal(l.rows.length,2);assert.deepEqual(l.post({...p,name:'  TEST synthetic  '}),a);assert.equal(l.post({...p,area:'Changed'}).code,'REQUEST_ID_CONFLICT');assert.equal(l.rows.length,2);});
test('authentication and contact permission fail before persistence',()=>{const l=lab(),p=l.payload();for(const changes of [{signature:'0'.repeat(64)},{version:2},{timestamp:'1000000000000'}])assert.equal(l.post(p,changes).code,'AUTH_FAILED');assert.equal(l.post({...p,contact_consent:false}).code,'VALIDATION_FAILED');assert.equal(l.rows.length,1);});
test('disabled routing and busy lock cannot append',()=>{const l=lab();l.properties.ROUTING_ENABLED='false';assert.equal(l.post(l.payload()).code,'ROUTING_DISABLED');l.properties.ROUTING_ENABLED='true';l.setBusy(true);assert.equal(l.post(l.payload()).code,'BUSY');assert.equal(l.rows.length,1);});
test('lost durable-write acknowledgement reconciles same ID without second append',()=>{const l=lab(),p=l.payload();l.failFlush();assert.equal(l.post(p).code,'ACCEPTANCE_UNCERTAIN_RETRY_SAME_ID');assert.equal(l.rows.length,2);assert.equal(l.post(p).accepted,true);assert.equal(l.rows.length,2);assert.equal(l.mail.length,0);});
test('outbox sends once then skips SENT on repeat processing',()=>{const l=lab();l.post(l.payload());l.context.processLeadOutbox();assert.equal(l.rows[1][6],'SENT');assert.equal(l.rows[1][7],1);assert.equal(l.mail.length,1);assert.equal(l.mail[0].to,'marketing@blackswanrealestate.ae');l.context.processLeadOutbox();assert.equal(l.mail.length,1);});
test('quota failure is pre-send retry, not ambiguous delivery',()=>{const l=lab();l.post(l.payload());l.setQuota(0);l.context.processLeadOutbox();assert.equal(l.rows[1][6],'RETRY_WAIT');assert.equal(l.rows[1][7],0);assert.equal(l.mail.length,0);l.rows[1][8]='';l.setQuota(100);l.context.processLeadOutbox();assert.equal(l.mail.length,1);assert.equal(l.rows[1][6],'SENT');});
test('provider exception after potential delivery stays AMBIGUOUS until reconciliation',()=>{const l=lab(),a=l.post(l.payload());l.setSendFault(true);l.context.processLeadOutbox();assert.equal(l.rows[1][6],'AMBIGUOUS');l.context.processLeadOutbox();assert.equal(l.mail.length,1);l.context.reconcileLeadEmail(a.lead_id,'confirmed_sent');assert.equal(l.rows[1][6],'SENT');l.context.processLeadOutbox();assert.equal(l.mail.length,1);});
test('stale SENDING is quarantined and confirmed-not-sent can be retried',()=>{const l=lab(),a=l.post(l.payload());l.rows[1][6]='SENDING';l.rows[1][25]=new Date(Date.now()-901000).toISOString();l.context.processLeadOutbox();assert.equal(l.rows[1][6],'AMBIGUOUS');assert.equal(l.mail.length,0);l.context.reconcileLeadEmail(a.lead_id,'confirmed_not_sent');l.context.processLeadOutbox();assert.equal(l.rows[1][6],'SENT');assert.equal(l.mail.length,1);});
test('duplicate stored identities require reconciliation rather than overwrite',()=>{const l=lab(),p=l.payload();l.post(p);l.rows.push([...l.rows[1]]);assert.equal(l.post(p).code,'DUPLICATE_ROWS_RECONCILE');assert.equal(l.rows.length,3);});
test('post-send commit failure is ambiguous and never blindly retried',()=>{const l=lab();l.post(l.payload());const flush=l.context.SpreadsheetApp.flush;let calls=0;l.context.SpreadsheetApp.flush=()=>{if(++calls===2)throw Error('synthetic post-send commit failure');return flush();};l.context.processLeadOutbox();assert.equal(l.rows[1][6],'AMBIGUOUS');assert.equal(l.mail.length,1);l.context.processLeadOutbox();assert.equal(l.mail.length,1);});
