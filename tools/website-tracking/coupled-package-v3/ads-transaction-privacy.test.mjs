// Actual selected V3 client/parent/child in a synthetic VM; no sockets/browser/provider execution.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {test} from 'node:test';
import {syntheticInput} from './synthetic-input.mjs';
import {composeCoupledCanonicalLeaseV3} from './compose-v3.mjs';
import {createHash} from 'node:crypto';
import {runInNewContext} from 'node:vm';
import {performance} from 'node:perf_hooks';
import {SOURCE_ROOT as source} from './synthetic-input.mjs';
const result=await composeCoupledCanonicalLeaseV3(await syntheticInput({source_root:source}));
const prefix='site/wp-content/plugins/bsre-enquiries/assets/';
const files=Object.fromEntries(['lead.js','google-measurement.js','google-runtime.js'].map(name=>[name,result.files.get(prefix+name).toString('utf8')]));
const sha=value=>createHash('sha256').update(value).digest('hex');
const origin='https://blackswanrealestate.ae', path='/enquire/rent/';
async function run(eventId,{childSource=files['google-runtime.js'],replayAds=false}={}){
  const at=performance.now(),listeners=new Map(),formHandlers=new Map(),frames=[],tasks=[],posts=[],requests=[],bus=[],timers=new Map();
  let n=0,tid=0;const nonce='00000000-0000-4000-8000-000000000001';
  const snapshot={known:true,acknowledged:true,measurement_eligible:true,preferences:{analytics:true,ad_measurement:true},decision_version:'a'.repeat(32),notice_version:'SYNTHETIC'};
  const notify=async(name,event)=>{for(const fn of listeners.get(name)||[])await fn(event);};
  const button={dataset:{},textContent:'Submit'},status={dataset:{}};
  const fields={name:'SYNTHETIC local fixture',phone:'+971500000000',email:'fixture@example.invalid',country:'UAE',area:'SYNTHETIC',budget:'To discuss',timeline:'Immediate / move now',funding:'To discuss',property_type:'Apartment',property_details:'',authority:''};
  const form={dataset:{role:'tenant',landingPath:path},elements:{namedItem:key=>key==='contact_consent'?{checked:true}:key==='marketing_consent'?{checked:false}:{value:fields[key]||''}},
    querySelector:selector=>selector==='[data-bsre-status]'?status:button,reportValidity:()=>true,addEventListener:(name,fn)=>formHandlers.set(name,fn)};
  const store=new Map();
  const window={location:new URL(origin+path),crypto:{randomUUID:()=>++n===1?nonce:'00000000-0000-4000-8000-'+String(n).padStart(12,'0')},
    BSRELeadConfig:{endpoint:origin+'/wp-json/bsre/v1/lead',measurementEligible:true,retentionAdmissionRequired:true},
    BSRENativePageContextConfig:{schema:1,registry_revision:'SYNTHETIC-TEST-v2',company:'BlackSwan Real Estate',page_path:path,role:'tenant',page_context:{},forms:[],ctas:[]},
    BSREConsentBridge:{permissions:()=>({analytics:true,advertising:true}),measurementEligible:()=>true,getSnapshot:()=>snapshot,normalizeSnapshot:value=>value},
    sessionStorage:{getItem:key=>store.get(key)??null,setItem:(key,value)=>store.set(key,value),removeItem:key=>store.delete(key)},
    addEventListener:(name,fn)=>listeners.set(name,[...(listeners.get(name)||[]),fn]),dispatchEvent:event=>bus.push(event),
    CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail;}},setTimeout:fn=>{timers.set(++tid,fn);return tid;},clearTimeout:id=>timers.delete(id),
    async fetch(url,request){
      requests.push({kind:url.endsWith('/proof')?'proof':'lead'});
      if(url.endsWith('/proof')){const id='00000000-0000-4000-8000-000000000099',issued=Math.floor(Date.now()/1000);return{ok:true,json:async()=>({request_id:id,proof:id+'.'+issued+'.'+'b'.repeat(64),admission:{version:1,request_id:id,issued_at:issued,expires_at:issued+900,session_hash:'c'.repeat(64),generation:'d'.repeat(64),audience:'e'.repeat(64),signature:'f'.repeat(64)}})};}
      assert.equal(url,origin+'/wp-json/bsre/v1/lead');assert(request.headers['X-BSRE-Admission']);
      return{ok:true,status:200,json:async()=>({accepted:true,lead_id:'BSRE-00000000-0000-4000-8000-000000000098',event_id:eventId,measurement:snapshot})};
    }};
  const document={readyState:'complete',referrer:'',cookie:'',querySelector:()=>form,querySelectorAll:selector=>selector==='form[data-bsre-form]'?[form]:[],
    body:{appendChild:frame=>frames.push(frame)},createElement:()=>({setAttribute(){},remove(){this.removed=true;},contentWindow:{postMessage(){}}})};
  runInNewContext(files['lead.js'],{window,document,URL,AbortController},{timeout:2000});
  window.BSREGoogleConfig={enabled:true,analytics_enabled:true,advertising_enabled:true,config_version:'gm1-'+'a'.repeat(32),runtime_endpoint:origin+'/wp-json/bsre/v1/measurement/runtime'};
  runInNewContext(files['google-measurement.js'],{window,document,URL},{timeout:2000});
  for(const frame of frames){
    const purpose=new URL(frame.src).searchParams.get('purpose'),analytics=purpose==='analytics';let receive;
    const config={version:'1.0.0',enabled:true,purpose,origin,gtm_id:'GTM-TESTONLY',measurement_id:analytics?'G-TESTONLY':'',ads_send_to:analytics?'':'AW-999999999/TEST_ONLY',
      cookie_prefix:analytics?'bsre_enq_analytics':'bsre_enq_ads',status_endpoint:origin+'/wp-json/bsre/v1/measurement/status',config_version:window.BSREGoogleConfig.config_version,lease_seconds:30,lease_token:'ml1|'+(Math.floor(Date.now()/1000)+60)+'|'+'b'.repeat(64)};
    const proxy={get BSREMeasurement(){return window.BSREMeasurement;},get BSRENativePageContext(){return window.BSRENativePageContext;},location:window.location,
      postMessage:data=>tasks.push(()=>notify('message',{origin,source:frame.contentWindow,data:structuredClone(data)}))};
    const child={parent:proxy,location:{origin,replace(){}},setTimeout:()=>1,clearTimeout(){},setInterval:()=>1,clearInterval(){},addEventListener:(_,fn)=>{receive=fn;},
      fetch:async()=>({ok:true,json:async()=>({...config,ok:true})})};
    frame.contentWindow=child;frame.scripts=[];
    child.postMessage=(data,target)=>{assert.equal(target,origin);if(data.type==='bsre-runtime-event')posts.push(structuredClone(data));tasks.push(()=>receive({origin,source:proxy,data:structuredClone(data)}));};
    runInNewContext(childSource,{window:child,document:{getElementById:()=>({textContent:JSON.stringify(config)}),createElement:()=>({}),head:{appendChild:script=>frame.scripts.push(script)}},URL,AbortController},{timeout:2000});
  }
  async function pump(){let bound=0;while(tasks.length){assert(++bound<100);await tasks.shift()();}}
  await pump();
  for(const frame of frames){assert.equal(frame.contentWindow.BSREGoogleRuntime.activate(),true);frame.scripts[1].onload();}
  await pump();await formHandlers.get('submit')({preventDefault(){}});await pump();
  if(replayAds){
    const previous=posts.find(row=>row.purpose==='advertising'),frame=frames.find(row=>new URL(row.src).searchParams.get('purpose')==='advertising');
    assert(previous&&frame);frame.contentWindow.postMessage({...previous,sequence:previous.sequence+1},origin);await pump();
  }
  const commands=frames.flatMap(frame=>(frame.contentWindow.dataLayer||[]).filter(row=>row[0]==='event').map(row=>Array.from(row)));
  const sdkCommands=frames.flatMap(frame=>(frame.contentWindow.dataLayer||[]).map(row=>row.length===undefined?row:Array.from(row)));
  return{event_id:eventId,elapsed_ms:performance.now()-at,http_requests:requests.map(x=>x.kind),intake_success:button.dataset.complete=== 'true',
    canonical_accepted_count:bus.filter(x=>x.detail?.event==='bsre_lead_accepted').length,ads_posts:posts.filter(x=>x.purpose==='advertising').length,
    conversion_commands:commands.filter(x=>x[1]==='conversion').map(x=>({transaction_id:x[2].transaction_id,send_to:x[2].send_to})),
    ga4_generate_lead_commands:commands.filter(x=>x[1]==='generate_lead').length,sdk_commands:sdkCommands,network_calls:0};
}
const proof=result.private_manifest.ads_transaction_id_guard;
const oldChild=files['google-runtime.js'].replace(proof.after,proof.before);
const observations=[];
function record(name,row){
  observations.push({name,...row});
  if(process.env.BSRE_ADS_PRIVACY_RECEIPT)writeFileSync(process.env.BSRE_ADS_PRIVACY_RECEIPT,JSON.stringify({
    scope:'actual final G36 client/parent/child; synthetic HTTP/DOM/SDK boundaries; no native/browser/provider acceptance',
    source_sha256:Object.fromEntries(Object.entries(files).map(([name,bytes])=>[name,sha(bytes)])),
    guard:proof,network_calls:0,production_events:0,observations},null,2)+'\n','utf8');
}
test('selected child correction reverses to the exact accepted preimage; frozen inputs stay unchanged',()=>{
  assert.equal(sha(oldChild),proof.input_sha256);assert.equal(sha(files['google-runtime.js']),proof.output_sha256);
  assert.equal(proof.input_sha256,'d3a4017bee0f480f3dbfdf0d78a04584409773fd633f02f6ba7c4082b5372666');
  assert.equal(proof.reverse_verified,true);assert.equal(proof.invalid_id_policy,'DROP_OPTIONAL_ADS_DISPATCH_NO_REWRITE');
  assert.equal(result.public_summary.complete_profile_certified,false);assert.equal(result.public_summary.deployment_prohibited,true);
});
test('actual upstream receipt guard admits malformed numeric ID; selected child now denies its Ads command',async()=>{
  const id='971500000000';
  const old=await run(id,{childSource:oldChild});record('accepted-baseline-malformed-ack',old);
  assert.equal(old.intake_success,true);assert.equal(old.canonical_accepted_count,1);assert.equal(old.ads_posts,1);
  assert.equal(old.conversion_commands.length,1);assert.equal(old.conversion_commands[0].transaction_id,id);
  const corrected=await run(id);record('selected-correction-malformed-ack',corrected);
  assert.equal(corrected.intake_success,true);assert.equal(corrected.canonical_accepted_count,1);assert.equal(corrected.ads_posts,1);
  assert.equal(corrected.conversion_commands.length,0);assert.equal(corrected.ga4_generate_lead_commands,1);
  // The durable-acceptance occurrence still maps once to GA4, whose mapper
  // copies no receipt/correlation/private permission fields. The new predicate
  // only denies disclosure of the malformed ID through optional Ads dispatch.
  const publicCommands=JSON.stringify(corrected.sdk_commands);
  for(const privateValue of [id,'BSRE-00000000-0000-4000-8000-000000000098','fixture@example.invalid',
    'event_id','lead_id','decision_version','notice_version','X-BSRE-Admission'])assert.equal(publicCommands.includes(privateValue),false,privateValue);
});
test('both valid receiver UUID prefixes retain exact transaction IDs, intake and one GA4/Ads command',async()=>{
  for(const id of ['evt_00000000-0000-4000-8000-000000000002','bsre-event-00000000-0000-4000-8000-000000000003']){
    const row=await run(id,{replayAds:true});record('valid-receiver-id-same-child-replay',row);
    assert.equal(row.intake_success,true);assert.equal(row.canonical_accepted_count,1);
    assert.equal(row.ga4_generate_lead_commands,1);assert.equal(row.conversion_commands.length,1);
    assert.equal(row.conversion_commands[0].transaction_id,id);assert.equal(row.conversion_commands[0].send_to,'AW-999999999/TEST_ONLY');
  }
});
test('free text, malformed UUIDs and oversized receipt IDs never become Ads transaction IDs',async()=>{
  for(const id of ['PRIVATE_SYNTHETIC_RECEIPT','evt_00000000-0000-1000-8000-000000000002','evt_00000000-0000-4000-7000-000000000002','x'.repeat(65)]){
    const row=await run(id);record('unsupported-id',row);
    assert.equal(row.intake_success,true);assert.equal(row.ga4_generate_lead_commands,1);assert.equal(row.conversion_commands.length,0);
  }
});
