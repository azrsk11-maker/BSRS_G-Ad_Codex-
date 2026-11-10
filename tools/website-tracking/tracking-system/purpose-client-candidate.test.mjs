import {readFileSync} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {buildPurposeClientCandidate, buildPurposeStoreCandidate, buildPurposeIntakeCandidate} from './build-purpose-attribution-candidate.mjs';
import {buildPurposeRetention} from './build-purpose-retention-candidate.mjs';
import {lab} from '../../staging-lab/receiver-lab.mjs';

const root = new URL('../../staging-lab/fixtures/bsre-enquiries/', import.meta.url);
const source = readFileSync(new URL('assets/lead.js', root));
const candidate = buildPurposeClientCandidate(source);
const origin = 'https://blackswanrealestate.ae';
const notice = 'bsre-enquiry-consent-2026-10-19-v1';
function page({store = new Map(), path = '/enquire/rent/', now = Date.now(), decision = 'a'.repeat(32), enabled = true,
  analytics = true, advertising = true, reply} = {}) {
  const handlers = new Map(); const requests = []; const events = [];
  const fields = {name:'Synthetic purpose lab',phone:'+971500000000',email:'fixture@example.invalid',country:'UAE',area:'Synthetic',budget:'To discuss',timeline:'Immediate / move now',funding:'To discuss',property_type:'Apartment'};
  const button = {textContent:'Submit',dataset:{}}; const status = {dataset:{}};
  const form = {dataset:{role:'tenant',landingPath:'/enquire/rent/'}, reportValidity:()=>true,
    elements:{namedItem:key=>key==='contact_consent'?{checked:true}:{value:fields[key]||'',checked:false}},
    querySelector:key=>key==='[data-bsre-status]'?status:button, addEventListener:(key,value)=>handlers.set(key,value)};
  const snapshot = {known:true,acknowledged:true,measurement_eligible:true,decision_version:decision,notice_version:notice,
    preferences:{analytics,ad_measurement:advertising,personalization:false}};
  const window = {location:new URL(origin+path),crypto:{randomUUID},
    BSRELeadConfig:{endpoint:origin+'/wp-json/bsre/v1/lead',measurementEligible:true,
      ...(enabled?{purposeAttributionEndpoint:origin+'/wp-json/bsre/v1/purpose-lead'}:{})},
    BSREConsentBridge:{permissions:()=>({analytics,advertising}),measurementEligible:()=>true,getSnapshot:()=>snapshot,normalizeSnapshot:v=>v},
    sessionStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},
    addEventListener(){},dispatchEvent:e=>events.push(e),CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail;}},
    setTimeout(){},clearTimeout(){},async fetch(url,options){if(url.endsWith('/proof'))return{ok:false};requests.push({url,...options});return reply?reply(requests.length):{ok:true,json:async()=>({accepted:true,lead_id:'SYNTHETIC',event_id:'SYNTHETIC'})};}};
  const document = {readyState:'complete',referrer:'',querySelector:()=>form,querySelectorAll:q=>q==='form[data-bsre-form]'?[form]:[]};
  class Clock extends Date {static now(){return now;}}
  runInNewContext(candidate,{window,document,Date:Clock,URL,AbortController});
  return {store,requests,events,submit:()=>handlers.get('submit')({preventDefault(){}})};
}
test('source pins and derivation keep fixtures unchanged',()=>{
  const store=readFileSync(new URL('includes/consent-store.php',root));
  const plugin=readFileSync(new URL('bsre-enquiries.php',root));const consent=readFileSync(new URL('includes/consent.php',root));
  assert.match(buildPurposeStoreCandidate(store),/prepare_capture/);
  assert.match(buildPurposeIntakeCandidate(plugin,consent),/function receive_wire/);
  assert.throws(()=>buildPurposeStoreCandidate(Buffer.concat([store,Buffer.from(' ')])),/PURPOSE_SOURCE_CHANGED/);
  assert.throws(()=>buildPurposeIntakeCandidate(plugin,Buffer.concat([consent,Buffer.from(' ')])),/PURPOSE_SOURCE_CHANGED/);
});
test('retention and restore candidates preserve scoped existing logic and add history checks',()=>{
  for(const name of ['PreferenceRetirement','RetirementLedger']){
    const bytes=readFileSync(new URL('../../consent-retention/'+name+'.php',import.meta.url));
    const code=buildPurposeRetention(bytes,name);assert.match(code,/namespace BSRE\\PurposeRetention/);
    assert.match(code,/\$db->prefix\s*===\s*'purpose_retention_synthetic_'/);
    assert.match(code,/\$db->prefix\s*===\s*'purpose_retention_compaction_synthetic_'/);
    assert.match(code,/BSRE_RETENTION_LAB/);assert.match(code,/wp_get_environment_type\(\)\s*!==\s*'local'/);
    assert.match(code,/home_url\(\)\s*!==\s*'http:\/\/bsre\.invalid'/);
    assert.ok(!code.includes("'retention_synthetic_'"));
    assert.ok(!code.includes("'retention_compaction_synthetic_'"));
    assert.match(code,/BSRE_RETENTION_COMPACTION_ENABLED/);
    if(name==='RetirementLedger')assert.match(code,/assertRestoreReferences/);
    else assert.match(code,/purpose_retention_synthetic_/);
    assert.throws(()=>buildPurposeRetention(Buffer.concat([bytes,Buffer.from(' ')]),name),/SOURCE_CHANGED/);
  }
  const fixture=buildPurposeRetention(readFileSync(new URL('../../staging-lab/restore.php',import.meta.url)),'restore');
  assert.match(fixture,/Synthetic_Retention_Click/);assert.match(fixture,/purpose_retention_restore_rehearsal/);
  assert.match(fixture,/\$db->prefix='purpose_retention_synthetic_'/);
  assert.ok(!fixture.includes("'retention_synthetic_'"));
  for(const name of ['purpose_seed_has_all_four_fields','purpose_seed_input_hash_matches',
    'purpose_seed_has_nonempty_permitted_clicks','purpose_restore_keeps_exact_nonempty_sidecar',
    'nested_fixture_keeps_valid_primary_decision','nested_only_retired_touch_blocks_restore'])assert.ok(fixture.includes(name));
});
test('preserved receiver delivers twenty accepted rows in four bounded outbox batches',()=>{
  const receiver=lab();
  for(let index=0;index<20;index++)assert.equal(receiver.post(receiver.payload()).accepted,true);
  for(let batch=1;batch<=4;batch++){
    const result=receiver.context.processLeadOutbox();
    assert.equal(result.sent,5);assert.equal(receiver.mail.length,batch*5);
  }
  assert.equal(receiver.context.processLeadOutbox().sent,0);
  assert.equal(receiver.rows.length,21);assert.equal(receiver.mail.length,20);
  assert.equal(new Set(receiver.rows.slice(1).map(row=>row[1])).size,20);
});
test('full independent latest histories travel privately while wire retains original schema',async()=>{
  const store=new Map();const clock=Date.now()-10000;
  page({store,path:'/enquire/rent/?utm_source=A&gclid=Click_A&utm_id=Id_A&google_campaign_id=000123',now:clock});
  const later=page({store,path:'/enquire/rent/?utm_source=C&utm_id=Id_C',now:clock+5000,decision:'b'.repeat(32)});
  await later.submit();const sent=later.requests[0];assert.equal(sent.url,origin+'/wp-json/bsre/v1/purpose-lead');
  const envelope=JSON.parse(sent.body);const wire=JSON.parse(envelope.wire_body);const side=envelope.attribution;
  assert.equal(side.analytics.first.parameters.utm_source,'A');assert.equal(side.analytics.last.parameters.utm_source,'C');
  assert.equal(side.advertising.first.parameters.gclid,'Click_A');assert.equal(side.advertising.last.parameters.gclid,'Click_A');
  assert.equal(side.analytics.last.parameters.utm_id,'Id_C');assert.equal(side.advertising.first.parameters.google_campaign_id,'000123');
  assert.equal(side.analytics.first.decision_version,'a'.repeat(32));assert.equal(side.analytics.last.decision_version,'b'.repeat(32));
  assert.equal(wire.attribution.last.parameters.gclid,'Click_A');assert.equal(wire.attribution.last.parameters.utm_id,undefined);
  assert.equal(wire.attribution.last.capture_id,undefined);assert.equal(wire.attribution.last.decision_version,undefined);
  assert.ok(!JSON.stringify(later.events).includes('Click_A'));
});
test('disabled new endpoint keeps legacy transport available',async()=>{
  const p=page({enabled:false,path:'/enquire/rent/?gclid=Only_Click'});await p.submit();
  assert.equal(p.requests[0].url,origin+'/wp-json/bsre/v1/lead');assert.equal(JSON.parse(p.requests[0].body).wire_body,undefined);
});
test('new envelope including private history is immutable across same-ID retry',async()=>{
  const p=page({reply:async()=>({ok:false,status:503,json:async()=>({})})});await p.submit();await p.submit();
  assert.equal(p.requests.length,2);assert.equal(p.requests[0].body,p.requests[1].body);
});
test('analytics-only excludes click fields and advertising-only excludes analytics history',async()=>{
  for(const [analytics,advertising] of [[true,false],[false,true]]){
    const p=page({analytics,advertising,path:'/enquire/rent/?utm_source=S&gclid=Only_Click'});await p.submit();
    const s=JSON.parse(p.requests[0].body).attribution;
    assert.equal(s[analytics?'advertising':'analytics'].first,null);
    if(analytics) assert.equal(s.analytics.first.parameters.gclid,undefined);
    else assert.equal(s.advertising.first.referrer,'');
  }
});
