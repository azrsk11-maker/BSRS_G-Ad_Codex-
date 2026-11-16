/** Actual parent/child source in synthetic Node VMs. SDK scripts are descriptors only; no network/provider execution. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync,writeFileSync} from 'node:fs';
import {dirname,resolve,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {runInNewContext,Script} from 'node:vm';
import {performance} from 'node:perf_hooks';
import {buildNativeFrameParent,buildNativeFrameChild,reverseNativeFrame,ORIGINAL_RUNTIME_SHA256} from './build-native-frame-candidate.mjs';
import {buildNativePageContextClient,sha256} from './build-native-page-context-candidate.mjs';
const source=resolve(process.env.BSRE_G4_SOURCE_ROOT || join(dirname(fileURLToPath(import.meta.url)),'../../..'));
const read=path=>readFileSync(join(source,path),'utf8');
const fixtures='tools/staging-lab/fixtures/bsre-enquiries/assets/';
const {buildFrameDeliveryCandidate}=await import(pathToFileURL(join(source,'tools/website-tracking/tracking-system/build-frame-delivery-candidate.mjs')));
const {buildRetentionAdmissionClient}=await import(pathToFileURL(join(source,'tools/website-tracking/tracking-system/build-retention-admission-candidate.mjs')));
const oldParent=buildFrameDeliveryCandidate(Buffer.from(read(fixtures+'google-measurement.js'))),oldChild=read(fixtures+'google-runtime.js');
const parentCandidate=buildNativeFrameParent(oldParent,sha256(oldParent)),childCandidate=buildNativeFrameChild(oldChild);
const admission=buildRetentionAdmissionClient(Buffer.from(read(fixtures+'lead.js'))),lead=buildNativePageContextClient(admission,sha256(admission)).output;
const origin='https://blackswanrealestate.ae',nonce='00000000-0000-4000-8000-000000000001';
const samples=[],start=performance.now();
function save(){if(process.env.BSRE_G4_FRAME_RECEIPT)writeFileSync(process.env.BSRE_G4_FRAME_RECEIPT,JSON.stringify({scope:'actual source in synthetic Node VMs; script/lease doubles; no browser or SDK/provider acceptance',network_calls:0,elapsed_seconds:(performance.now()-start)/1000,parent_input_sha256:sha256(oldParent),parent_output_sha256:parentCandidate.output_sha256,original_child_sha256:sha256(oldChild),child_output_sha256:childCandidate.output_sha256,cases:samples},null,2)+'\n');}
function scenario(name,fn){test(name,async()=>{const at=performance.now();let failure;try{await fn();}catch(error){failure=error;}samples.push({name,status:failure?'FAIL':'PASS',elapsed_ms:performance.now()-at,...(failure?{error:String(failure)}:{})});save();if(failure)throw failure;});}
function metadata(path='/enquire/off-plan/') {return {schema:1,registry_revision:'SYNTHETIC-TEST-v2',company:'BlackSwan Real Estate',page_path:path,role:path.startsWith('/enquire/')?'off_plan':'unknown',page_context:{campaign_key:'BSRE-C0001',landing_page_id:'BSRE-LP0001',page_version:'0.0.1',page_family:'TEST',language:'en'},forms:[],ctas:[]};}
function fixture({v2=true,purpose='analytics',path='/enquire/off-plan/',config=metadata(path)}={}) {
  const listeners=new Map(),messages=[],frames=[],scripts=[],posts=[],connected=new Map(),timers=new Map();let timer=0,allow=true,statusCalls=0,uuid=0;
  const notify=(type,event)=>{for(const fn of listeners.get(type)||[])fn(event);};
  const parent={location:new URL(origin+path+'?email=PRIVATE%40example.invalid&campaign_key=BSRE-C9999'),BSRENativePageContextConfig:config,
    BSRELeadConfig:{measurementEligible:true},BSREConsentBridge:{measurementEligible:()=>true,permissions:()=>({analytics:allow,advertising:allow}),getSnapshot:()=>({known:true,acknowledged:true})},
    BSREGoogleConfig:{enabled:true,analytics_enabled:purpose==='analytics',advertising_enabled:purpose==='advertising',config_version:'gm1-'+'a'.repeat(32),runtime_endpoint:origin+'/wp-json/bsre/v1/measurement/runtime'},
    crypto:{randomUUID:()=>{uuid++;return uuid===1?nonce:'00000000-0000-4000-8000-'+String(uuid).padStart(12,'0');}},
    addEventListener:(name,fn)=>listeners.set(name,[...(listeners.get(name)||[]),fn]),dispatchEvent:event=>notify(event.type,event),
    CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail;}},setTimeout:fn=>{timers.set(++timer,fn);return timer;},clearTimeout:id=>timers.delete(id),
    postMessage:(data,target)=>{assert.equal(target,origin);messages.push(()=>notify('message',{origin,source:frames[0].contentWindow,data:structuredClone(data)}));}};
  const document={referrer:'',cookie:'',readyState:'loading',querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{},body:{appendChild:frame=>frames.push(frame)},
    createElement:()=>({contentWindow:{postMessage:()=>{}},setAttribute(){},remove(){}})};
  runInNewContext(lead,{window:parent,document,URL,URLSearchParams,Uint8Array,AbortController,structuredClone},{timeout:2000});
  const measurement=parent.BSREMeasurement;
  parent.BSREMeasurement=Object.freeze({...measurement,connect:(destination,fn)=>{connected.set(destination,fn);return measurement.connect(destination,fn);}});
  runInNewContext(v2?parentCandidate.output:oldParent,{window:parent,document,URL},{timeout:2000});
  const frame=frames[0];let receive;
  const runtimeConfig={version:'1.0.0',enabled:true,purpose,origin,gtm_id:'GTM-TESTONLY',measurement_id:purpose==='analytics'?'G-TESTONLY':'',ads_send_to:purpose==='advertising'?'AW-999999999/TEST_ONLY':'',cookie_prefix:purpose==='analytics'?'bsre_enq_analytics':'bsre_enq_ads',status_endpoint:origin+'/wp-json/bsre/v1/measurement/status',config_version:'gm1-'+'a'.repeat(32),lease_seconds:30,lease_token:'ml1|'+(Math.floor(Date.now()/1000)+60)+'|'+'b'.repeat(64)};
  const child={parent,location:{origin,replace:()=>{}},setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){},addEventListener:(type,fn)=>{assert.equal(type,'message');receive=fn;},
    fetch:async url=>{assert.equal(url,runtimeConfig.status_endpoint);statusCalls++;return{ok:true,json:async()=>({...runtimeConfig,ok:true})};}};
  const childDoc={getElementById:()=>({textContent:JSON.stringify(runtimeConfig)}),createElement:()=>({}),head:{appendChild:script=>scripts.push(script)}};
  if(frame)frame.contentWindow.postMessage=(data,target)=>{assert.equal(target,origin);posts.push(structuredClone(data));messages.push(()=>receive({origin,source:parent,data:structuredClone(data)}));};
  if(frame)runInNewContext(v2?childCandidate.output:oldChild,{window:child,document:childDoc,URL,AbortController},{timeout:2000});
  async function drain(){let guard=0;while(messages.length){assert(++guard<100);await messages.shift()();}}
  async function active(){await drain();assert.equal(scripts.length,1);assert.equal(child.BSREGoogleRuntime.activate(),true);assert.equal(scripts.length,2);scripts[1].onload();await drain();}
  const events=name=>(child.dataLayer||[]).filter(entry=>entry[0]==='event'&&(!name||entry[1]===name));
  const raw=(data,opts={})=>receive({origin:opts.origin||origin,source:opts.source||parent,data:structuredClone(data)});
  return{parent,child,frames,scripts,posts,connected,drain,active,events,raw,notify,config:runtimeConfig,denied:()=>{allow=false;},statusCalls:()=>statusCalls};
}
scenario('V2 exact parent/child composition parses and reverses; original pins unchanged',()=>{
  new Script(parentCandidate.output);new Script(childCandidate.output);assert.equal(reverseNativeFrame(parentCandidate),oldParent);assert.equal(reverseNativeFrame(childCandidate),oldChild);
  assert.equal(sha256(oldChild),ORIGINAL_RUNTIME_SHA256);assert.throws(()=>buildNativeFrameChild(oldChild.replace('receive(payload)','receive(changed)')),/PREIMAGE/);
});
scenario('diagnostic: unchanged V1 child silently rejects G4 phone and enriched accepted event',async()=>{
  const f=fixture({v2:false});await f.active();
  const plain={schema_version:'1.0.0',site_scope:'BSRE_REAL_ESTATE',page_path:'/enquire/off-plan/',role:'off_plan'};
  f.connected.get('ga4')({event_name:'form_start',parameters:plain});await f.drain();assert.equal(f.events('form_start').length,1);
  f.parent.BSRELead.trackContact('telephone','hero');
  const accepted=f.parent.BSREMeasurement.mapGA4({event:'form_submit',event_id:'TEST_ONLY_RECEIPT',page_path:plain.page_path,role:plain.role});
  assert.equal(f.connected.get('ga4')(accepted),true);await f.drain();assert.equal(f.events('phone_click').length,0);assert.equal(f.events('generate_lead').length,0);
  if(process.env.BSRE_G4_V1_DIAGNOSTIC)writeFileSync(process.env.BSRE_G4_V1_DIAGNOSTIC,JSON.stringify({status:'DIAGNOSTIC_FAILURE_NOT_ACCEPTANCE',baseline_control_events:1,mapped_phone_parent_posts:f.posts.filter(x=>x.payload?.event_name==='phone_click').length,child_phone_commands:0,enriched_accepted_parent_posted:true,child_accepted_commands:0,original_child_sha256:sha256(oldChild),network_calls:0},null,2)+'\n');
});
scenario('V2 actual lead -> parent -> child carries metadata and emits phone alias/page view once',async()=>{
  const f=fixture();await f.active();f.parent.BSRELead.trackContact('telephone','hero');await f.drain();
  assert.equal(f.events('phone_click').length,1);assert.equal(f.events('telephone_click').length,0);assert.equal(f.events('cta_click').length,0);assert.equal(f.events('page_view').length,1);
  for(const event of [f.events('phone_click')[0],f.events('page_view')[0]]){assert.equal(event[2].campaign_key,'BSRE-C0001');assert.equal(event[2].landing_page_id,'BSRE-LP0001');assert.equal(event[2].company,'BlackSwan Real Estate');assert.equal(event[2].page_location,origin+'/enquire/off-plan/');assert(!JSON.stringify(event).includes('PRIVATE'));assert(!JSON.stringify(event).includes('C9999'));}
  const replay=f.posts.find(x=>x.type==='bsre-runtime-event');await f.raw(replay);assert.equal(f.events('phone_click').length,1);
});
scenario('V2 queues mapped accepted representation once; repeated active does not repeat flush',async()=>{
  const f=fixture();const mapped=f.parent.BSREMeasurement.mapGA4({event:'form_submit',event_id:'TEST_ONLY_RECEIPT',page_path:'/enquire/off-plan/',role:'off_plan'});
  assert.equal(f.connected.get('ga4')(mapped),true);await f.active();assert.equal(f.events('generate_lead').length,1);
  f.notify('message',{origin,source:f.frames[0].contentWindow,data:{type:'bsre-runtime-active',version:'1.0.0',purpose:'analytics',nonce:f.posts[0].nonce}});await f.drain();assert.equal(f.events('generate_lead').length,1);
});
scenario('V2 rejects extra/PII metadata, mismatched approved values, missing fields and unreviewed paths',async()=>{
  const f=fixture();await f.active();const base=f.parent.BSREMeasurement.mapGA4({event:'form_start',event_id:'TEST_ONLY_START',page_path:'/enquire/off-plan/',role:'off_plan'});
  const mutations=[p=>p.email='PRIVATE@example.invalid',p=>p.page_location='https://example.invalid/PRIVATE',p=>p.campaign_key='BSRE-C9999',p=>p.page_path='/unreviewed/',p=>delete p.company,p=>p.role='seller',p=>p.cta_location='PRIVATE'];
  for(const mutate of mutations){const bad=structuredClone(base);mutate(bad.parameters);assert.equal(f.connected.get('ga4')(bad),true);await f.drain();}
  assert.equal(f.events('form_start').length,0);
});
scenario('V2 origin/nonce/source/sequence and stale registry guards remain enforced',async()=>{
  const f=fixture();await f.active();f.parent.BSRELead.trackContact('telephone','hero');await f.drain();const raw=structuredClone(f.posts.find(x=>x.payload));raw.sequence+=10;
  await f.raw({...raw,nonce:'wrong'});await f.raw(raw,{origin:'https://example.invalid'});await f.raw(raw,{source:{}});assert.equal(f.events('phone_click').length,1);
  f.parent.BSRENativePageContextConfig={...f.parent.BSRENativePageContextConfig,registry_revision:'SYNTHETIC-changed'};f.parent.BSRELead.trackContact('telephone','hero');await f.drain();assert.equal(f.events('phone_click').length,1);
});
scenario('V2 reviewed main-site path works; missing/unreviewed/PII context creates no frame',async()=>{
  const f=fixture({path:'/synthetic-contact/'});await f.active();assert.equal(f.events('page_view')[0][2].page_path,'/synthetic-contact/');
  assert.equal(fixture({config:null}).frames.length,0);assert.equal(fixture({path:'/arbitrary/',config:metadata('/enquire/off-plan/')}).frames.length,0);
  const bad=metadata();bad.page_context.email='PRIVATE@example.invalid';assert.equal(fixture({config:bad}).frames.length,0);
});
scenario('V2 withdrawal drops queued acceptance and existing Ads receipt dedup stays intact',async()=>{
  const f=fixture({purpose:'advertising'});const receipt={event_name:'accepted_enquiry',transaction_id:'TEST_ONLY_RECEIPT',page_path:'/enquire/off-plan/',role:'off_plan'};assert.equal(f.connected.get('ads')(receipt),true);await f.active();
  assert.equal(f.events('conversion').length,1);f.connected.get('ads')(receipt);await f.drain();assert.equal(f.events('conversion').length,1);
  const g=fixture();g.connected.get('ga4')({event_name:'generate_lead',parameters:{}});g.denied();g.notify('bsre:consent-will-change',{detail:{}});await g.drain();assert.equal(g.events('generate_lead').length,0);
});
