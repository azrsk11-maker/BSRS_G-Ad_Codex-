import test from 'node:test';import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {acceptedSubmissionUrl,createRegistry,queryFreeUrl,permissionAllowed,captureClickIds,normalizeEvent,PrototypeLedger,prepareDestinations} from './contract.mjs';
const NOW=Date.parse('2026-11-07T05:30:00Z');
const record={campaign_key:'BSRE-C0001',landing_page_id:'BSRE-LP0001',path:'/lp/bsre-c0001/',page_version:'0.0.1',page_family:'DEV',
  property_destination:'dubai',property_segment:'residential_offplan',transaction_intent:'buy',language:'en',ctas:[
    {cta_id:'bsre-enquiry',cta_type:'form',cta_position:'body',form_id:'bsre-enquiry-form',destination_key:'enquiry-intake'},
    {cta_id:'bsre-phone',cta_type:'phone',cta_position:'sticky',form_id:null,destination_key:'approved-main-phone'}]};
const registry=createRegistry([record]);
const EVENT_ID='bsre-event-00000000-0000-4000-8000-000000000001';
const consent={verified:true,server_eligible:true,expires_at:'2026-11-08T00:00:00Z',analytics:true,advertising:true,
  ad_user_data:true,personalization:false,qa:false,admin:false};
// Fictional test IDs: no network call or claim that these are verified production destinations.
const mappings={ga4:{approved:true,measurement_id:'G-TESTONLY00',evidence_ref:'fixture-ga4',producer:'single_reviewed_web_producer'},
  ads:{approved:true,send_to:'AW-999999999/testonly',evidence_ref:'fixture-ads',route:'native_web_only',supported_dedup_field:'transaction_id',secondary:true}};
function raw(event='bsre_lead_accepted') {return {event,schema_version:1,campaign_key:record.campaign_key,landing_page_id:record.landing_page_id,
  page_version:record.page_version,internal_event_id:EVENT_ID,cta_id:'bsre-enquiry',
  receipt:{accepted:true,durable:true,lead_id:'QA-lead-001',event_id:EVENT_ID,original_analytics:true,original_advertising:true,original_ad_user_data:true},
  evidence:{source:'server_confirmed',verified:true,reference:'qa-durable-receipt'}};}
function options(overrides={}) {return {registry,consent:structuredClone(consent),mappings:structuredClone(mappings),ledger:new PrototypeLedger(),now:NOW,...overrides};}

test('preserved receiver event ID becomes the exact native Ads deduplication ID',()=>{
  const event=raw();
  const receiverId='evt_00000000-0000-4000-8000-000000000001';
  event.internal_event_id=receiverId;
  event.receipt.event_id=receiverId;
  const opts=options();
  const first=prepareDestinations(event,opts).output.find(item=>item.destination==='ads');
  assert.equal(first.payload.transaction_id,receiverId);
  assert.equal(first.status,'prepared_only_not_delivered');
  const retry=prepareDestinations(event,opts).output.find(item=>item.destination==='ads');
  assert.equal(retry.status,'duplicate_suppressed');
  assert.deepEqual(retry.payload,first.payload);
});

test('accepted enquiry binds a reviewed service route without leaking it to destinations',()=>{
  const [form,phone]=record.ctas;
  const resale={...form,cta_id:'bsre-resale-enquiry',form_id:'bsre-resale-form',submission_path:'/enquire/resale/'};
  const bound=createRegistry([{...record,ctas:[{...form,submission_path:'/enquire/off-plan/'},resale,phone]}]);
  const event=raw();
  event.requested_url=record.path;
  const wire=JSON.stringify({request_id:'synthetic-request',role:'off_plan',landing_page:'https://blackswanrealestate.ae/enquire/off-plan/'});
  const capture={request_id:'synthetic-request',state:'ACCEPTED',delivery_pending:0,uncertain:0,
    lead_id:event.receipt.lead_id,event_id:event.receipt.event_id,
    fingerprint:createHash('sha256').update(wire).digest('hex')};
  event.receipt.submission_url=acceptedSubmissionUrl(wire,capture,event.receipt);
  assert.throws(()=>acceptedSubmissionUrl(wire.replace('off-plan','resale'),capture,event.receipt),/FINGERPRINT_MISMATCH/);
  assert.throws(()=>acceptedSubmissionUrl(wire,{...capture,request_id:'different'},event.receipt),/REQUEST_MISMATCH/);
  assert.throws(()=>acceptedSubmissionUrl(wire,{...capture,delivery_pending:1},event.receipt),/WIRE_EVIDENCE_REQUIRED/);
  assert.throws(()=>acceptedSubmissionUrl(wire,capture,{...event.receipt,lead_id:'different'}),/WIRE_EVIDENCE_REQUIRED/);
  const normalized=normalizeEvent(event,bound);
  assert.equal(normalized.parameters.page_location,queryFreeUrl(record.path));
  assert.equal(normalized.private_submission_url,queryFreeUrl('/enquire/off-plan/'));
  const result=prepareDestinations(event,options({registry:bound}));
  assert.equal(result.output.length,2);
  assert.doesNotMatch(JSON.stringify(result.output),/submission_|enquire\/off-plan/);
  for(const submission_url of [undefined,'/enquire/resale/','https://wrong.example/enquire/off-plan/','/enquire/off-plan/?gclid=test']){
    assert.throws(()=>normalizeEvent({...event,receipt:{...event.receipt,submission_url}},bound),/SUBMISSION_ROUTE_MISMATCH|URL_NOT_APPROVED/);
  }
  assert.throws(()=>normalizeEvent(event,registry),/SUBMISSION_ROUTE_MISMATCH/);
  assert.throws(()=>normalizeEvent({...event,requested_url:'/enquire/off-plan/'},bound),/PAGE_URL_MISMATCH/);
  assert.throws(()=>normalizeEvent({...event,cta_id:resale.cta_id},bound),/SUBMISSION_ROUTE_MISMATCH/);
  for(const landing_page of ['/enquire/off-plan/','https://blackswanrealestate.ae/enquire/','https://blackswanrealestate.ae/enquire/resale/']){
    const wrongService=JSON.stringify({...JSON.parse(wire),landing_page});
    const wrongCapture={...capture,fingerprint:createHash('sha256').update(wrongService).digest('hex')};
    assert.throws(()=>acceptedSubmissionUrl(wrongService,wrongCapture,event.receipt),/SERVICE_ROUTE_MISMATCH/);
  }
  const resaleWire=wire.replace('off-plan','resale').replace('off_plan','resale');
  const resaleCapture={...capture,fingerprint:createHash('sha256').update(resaleWire).digest('hex')};
  const resaleEvent={...event,cta_id:resale.cta_id,receipt:{...event.receipt,
    submission_url:acceptedSubmissionUrl(resaleWire,resaleCapture,event.receipt)}};
  const resaleResult=prepareDestinations(resaleEvent,options({registry:bound}));
  assert.equal(resaleResult.output.length,2);
  assert.doesNotMatch(JSON.stringify(resaleResult.output),/submission_|enquire\/resale/);
});

test('Brand hub navigation stays separate from a downstream accepted rental enquiry',()=>{
  const [form]=record.ctas;
  const link={cta_id:'bsre-hub-rent',cta_type:'link',cta_position:'body',form_id:null,destination_key:'rent'};
  const tenantForm={...form,submission_path:'/enquire/rent/'};
  const hub={...record,path:'/enquire/',ctas:[link,tenantForm]};
  const opts=options({registry:createRegistry([hub])});
  const {receipt,evidence,...context}=raw();
  const click=prepareDestinations({...context,event:'cta_click',cta_id:link.cta_id,requested_url:hub.path},opts);
  assert.deepEqual(click.output.map(({destination,payload})=>[destination,payload.event_name]),[['ga4','cta_click']]);
  const accepted={...raw(),requested_url:hub.path,receipt:{...receipt,submission_url:'/enquire/rent/'}};
  assert.throws(()=>prepareDestinations({...accepted,cta_id:link.cta_id},opts),/SUBMISSION_ROUTE_MISMATCH/);
  const result=prepareDestinations(accepted,opts);
  assert.equal(result.output.find(row=>row.destination==='ga4').payload.parameters.page_location,queryFreeUrl('/enquire/'));
  assert.equal(result.output.find(row=>row.destination==='ads').payload.transaction_id,EVENT_ID);
  assert.doesNotMatch(JSON.stringify(result.output),/enquire\/rent/);
});

test('legacy accepted names adapt to one canonical event and keep internal metadata out of GA4',()=>{
  const result=prepareDestinations(raw(),options());assert.equal(result.normalized_event,'form_accepted');assert.equal(result.output.length,2);
  const ga4=result.output.find(o=>o.destination==='ga4');assert.equal(ga4.payload.event_name,'generate_lead');
  assert.doesNotMatch(JSON.stringify(ga4),/QA-lead|QA-accepted|original_analytics|reference/);assert.equal(result.network_calls,0);
  assert.equal(JSON.stringify(ga4).includes(EVENT_ID),false);
});
test('advertising-only permission captures exact identifiers and allows secondary native Ads without GA4',()=>{
  const c={...consent,analytics:false};const click={gclid:'Aa_z-09',gbraid:'ExactCase-1'};
  assert.deepEqual(captureClickIds(click,c,NOW),click);
  const result=prepareDestinations(raw(),options({consent:c}));assert.deepEqual(result.output.map(o=>o.destination),['ads']);
});
test('oversized, malformed and unsupported identifiers reject instead of trimming or truncating',()=>{
  for(const value of ['x'.repeat(513),' abc','a.b','contact@example.test'])assert.throws(()=>captureClickIds({gclid:value},consent,NOW),/UNSUPPORTED_OR_OVERSIZED/);
  assert.throws(()=>captureClickIds({email:'private@example.test'},consent,NOW),/UNSUPPORTED_CLICK/);
});
test('unknown, expired, QA, admin and withdrawn choices deny all measurement',()=>{
  for(const c of [{},{...consent,verified:false},{...consent,expires_at:'2026-11-06T00:00:00Z'},
    {...consent,qa:true},{...consent,admin:true},{...consent,analytics:false,advertising:false}]){
    assert.equal(prepareDestinations(raw(),options({consent:c})).output.length,0);assert.deepEqual(captureClickIds({gclid:'ExactCase'},c,NOW),{});
  }
  assert.equal(permissionAllowed({...consent,advertising:'true'},'advertising',NOW),false);
});
test('retry cannot upgrade the original capture permission',()=>{
  const event=raw();event.receipt.original_analytics=false;event.receipt.original_advertising=false;
  assert.equal(prepareDestinations(event,options()).output.length,0);
});
test('input field injection and query or external URL leak reject',()=>{
  for(const field of ['email','phone','free_text','page_referrer','utm_term'])assert.throws(()=>normalizeEvent({...raw(),[field]:'PRIVATE'},registry),/UNKNOWN_EVENT_FIELD/);
  for(const url of ['/lp/bsre-c0001/?email=private@example.test','https://other.example/','/lp/bsre-c0001/#token',
    '/lp/bsre-c0001/?','/enquire/rent/#','/private/../enquire/rent/',
    '/private/%2e%2e/enquire/rent/','//blackswanrealestate.ae/enquire/rent/',
    ' https://blackswanrealestate.ae/enquire/rent/','https://blackswanrealestate.ae:443/enquire/rent/']) {
    assert.throws(()=>queryFreeUrl(url),/URL_NOT_APPROVED/);
  }
  assert.equal(queryFreeUrl('/enquire/rent/'),queryFreeUrl('https://blackswanrealestate.ae/enquire/rent/'));
});
test('registry binds campaign page version and CTA, rejects accidental reuse',()=>{
  assert.throws(()=>normalizeEvent({...raw(),landing_page_id:'BSRE-LP0002'},registry),/CONTEXT_MISMATCH/);
  assert.throws(()=>normalizeEvent({...raw(),cta_id:'bsre-unknown'},registry),/CTA_NOT_REGISTERED/);
  assert.throws(()=>createRegistry([record,{...record,campaign_key:'BSRE-C0002',landing_page_id:'BSRE-LP0002'}]),/DEDICATED_PAGE/);
});
test('durable receipt is required for all legacy and v3 accepted aliases',()=>{
  for(const name of ['bsre_lead_accepted','form_submit','form_accepted']){
    const event=raw(name);event.receipt.durable=false;assert.throws(()=>normalizeEvent(event,registry),/DURABLE_RECEIPT/);
  }
});
test('retries and specialized/generic duplicates reuse one destination reservation',()=>{
  const opts=options();prepareDestinations(raw(),opts);const retry=prepareDestinations(raw('form_submit'),opts);
  assert.ok(retry.output.every(o=>o.status==='duplicate_suppressed'));
  const click={event:'cta_click',schema_version:1,campaign_key:record.campaign_key,landing_page_id:record.landing_page_id,
    page_version:record.page_version,cta_id:'bsre-phone',internal_event_id:'QA-click-001'};
  assert.equal(prepareDestinations(click,opts).normalized_event,'phone_click');
  assert.equal(prepareDestinations({...click,event:'phone_click'},opts).output[0].status,'duplicate_suppressed');
});
test('failed reservation batch leaves no additions and identical same-batch rows deduplicate',()=>{
  const ledger=new PrototypeLedger();
  const row={destination:'offline',event:'form_accepted',identity:'batch-event-01',payload:{value:1}};
  assert.throws(()=>ledger.reserveBatch([row,{...row,payload:{value:2}}]),/SAME_ID_CHANGED_PAYLOAD_CONFLICT/);
  assert.deepEqual(ledger.reserveBatch([row,row]),['prepared_only_not_delivered','duplicate_suppressed']);
  assert.throws(()=>ledger.reserveBatch([{...row,identity:'batch-event-02'},{...row,payload:{value:2}}]),/SAME_ID_CHANGED_PAYLOAD_CONFLICT/);
  assert.deepEqual(ledger.reserveBatch([{...row,identity:'batch-event-02'}]),['prepared_only_not_delivered']);
});

test('same event ID with changed body is a conflict',()=>{
  const ledger=new PrototypeLedger();ledger.reserve('ga4','form_accepted','QA-1',{page:'a'});
  assert.throws(()=>ledger.reserve('ga4','form_accepted','QA-1',{page:'b'}),/SAME_ID_CHANGED/);
});
test('custom event ID does not substitute for reviewed supported destination dedup mapping',()=>{
  const opts=options();opts.mappings.ads.supported_dedup_field='event_id';
  assert.throws(()=>prepareDestinations(raw(),opts),/SUPPORTED_DEDUP/);
  opts.mappings.ads.supported_dedup_field='transaction_id';
  assert.ok(prepareDestinations(raw(),opts).output.every(o=>o.status==='prepared_only_not_delivered'));
});
test('current ad-user-data grant cannot upgrade its originally refused purpose',()=>{
  const event=raw();event.receipt.original_ad_user_data=false;
  assert.deepEqual(prepareDestinations(event,options()).output.map(o=>o.destination),['ga4']);
});
test('phone-shaped or free-form receipt ID cannot enter the Ads transaction field',()=>{
  const event=raw();event.internal_event_id='971501234567';event.receipt.event_id=event.internal_event_id;
  assert.throws(()=>prepareDestinations(event,options()),/OPAQUE_ADS_TRANSACTION/);
});
test('clicks never establish calls, bookings, transactions or collected commission',()=>{
  for(const name of ['conversation_verified','viewing_booked','qualified_lead','transaction_closed','commission_collected']){
    const event={...raw(),event:name,receipt:undefined,evidence:{source:'browser',verified:true,reference:'qa-click'}};
    assert.throws(()=>normalizeEvent(event,registry),/AUTHORITATIVE_OUTCOME/);
  }
});
test('operational outcome with evidence remains held for reviewed offline adapter',()=>{
  const event={...raw(),event:'commission_collected',receipt:undefined,evidence:{source:'finance_ledger',verified:true,reference:'qa-finance-record'}};
  assert.deepEqual(prepareDestinations(event,options()).withheld,['REVIEWED_OFFLINE_ADAPTER_REQUIRED']);
});
test('page views deduplicate on actual navigation identity, never arbitrary event identity',()=>{
  const event={event:'page_view',schema_version:1,campaign_key:record.campaign_key,landing_page_id:record.landing_page_id,
    page_version:record.page_version,internal_event_id:'QA-view-001',navigation_id:'QA-nav-001'};
  const opts=options();prepareDestinations(event,opts);
  assert.equal(prepareDestinations({...event,internal_event_id:'QA-view-002'},opts).output[0].status,'duplicate_suppressed');
  assert.equal(prepareDestinations({...event,navigation_id:'QA-nav-002'},opts).output[0].status,'prepared_only_not_delivered');
});
