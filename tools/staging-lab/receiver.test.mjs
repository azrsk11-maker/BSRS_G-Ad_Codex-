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


// Synthetic source-derived receiver coverage, not real Sheet/email durability.
const fiveRoleCases=[
  ['off_plan','off-plan','Within 1 month'],
  ['resale','resale','Within 1 month'],
  ['tenant','rent','Immediate / move now'],
  ['seller','sell','As soon as practical'],
  ['landlord','let','Vacant / available to discuss now'],
];
function rolePayload(l,role,slug,timeline){
  return {...l.payload(),role,timeline,
    landing_page:'https://blackswanrealestate.ae/enquire/'+slug+'/',
    ...(['seller','landlord'].includes(role)?{authority:'owner',property_details:'SYNTHETIC PROPERTY ONLY'}:{})};
}
test('all five wire-v1 role receipts bind exact Intake26 and simulated email identities',()=>{
  for(const [role,slug,timeline] of fiveRoleCases){
    const l=lab(), p=rolePayload(l,role,slug,timeline), receipt=l.post(p);
    assert.equal(receipt.accepted,true,role);
    const headers=Array.from(l.context.LEAD_HEADERS);
    assert.equal(headers.length,26);
    const row=Object.fromEntries(headers.map((name,index)=>[name,l.rows[1][index]]));
    assert.equal(row.request_id,p.request_id);
    assert.equal(row.lead_id,receipt.lead_id);assert.equal(row.event_id,receipt.event_id);
    assert.equal(row.role,role);assert.equal(row.landing_page,p.landing_page);
    assert.equal(row.email_status,'QUEUED');assert.equal(l.mail.length,0);
    const normalized=JSON.parse(row.payload_json);
    assert.equal(normalized.request_id,p.request_id);assert.equal(normalized.role,role);
    assert.equal(row.payload_sha256,l.context.hex_(l.context.Utilities.computeDigest('sha256',row.payload_json)));
    assert.deepEqual(l.post(p),receipt);assert.equal(l.rows.length,2);
    l.context.processLeadOutbox();assert.equal(l.mail.length,1);
    assert.equal(l.rows[1][headers.indexOf('email_status')],'SENT');
    const mail=l.mail[0];assert.ok(mail.subject.endsWith(receipt.lead_id));
    assert.ok(mail.body.startsWith('Lead ID: '+receipt.lead_id+'\nEvent ID: '+receipt.event_id+'\n'));
    const mailPayload=JSON.parse(mail.body.slice(mail.body.indexOf('\n\n')+2));
    assert.deepEqual(mailPayload,normalized);
    assert.ok(mail.body.includes('not yet sales qualified'));
    assert.deepEqual(l.post(p),receipt);l.context.processLeadOutbox();
    assert.equal(l.mail.length,1);assert.equal(l.rows.length,2);
    assert.equal(l.post({...p,area:'SYNTHETIC CONFLICT'}).code,'REQUEST_ID_CONFLICT');
    assert.equal(l.mail.length,1);assert.equal(l.rows.length,2);
  }
});
test('five-role outbox batch keeps a sixth receipt queued without losing identity',()=>{
  const l=lab(),receipts=[];
  for(const item of [...fiveRoleCases,fiveRoleCases[0]]){
    const receipt=l.post(rolePayload(l,...item));assert.equal(receipt.accepted,true);receipts.push(receipt);
  }
  assert.equal(new Set(receipts.map(x=>x.lead_id)).size,6);
  assert.equal(new Set(receipts.map(x=>x.event_id)).size,6);
  l.context.processLeadOutbox();assert.equal(l.mail.length,5);
  assert.deepEqual(l.rows.slice(1).map(row=>row[6]),['SENT','SENT','SENT','SENT','SENT','QUEUED']);
  l.context.processLeadOutbox();assert.equal(l.mail.length,6);
  for(const receipt of receipts)assert.equal(l.mail.filter(mail=>mail.subject.endsWith(receipt.lead_id)&&mail.body.includes('Event ID: '+receipt.event_id+'\n')).length,1);
  l.context.processLeadOutbox();assert.equal(l.mail.length,6);
});
