// Actual composed client over a local pipe. All identities are synthetic.
import {readFileSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {buildPurposeClientCandidate} from '/opt/lab/tracking-system/build-purpose-attribution-candidate.mjs';
import {acceptedSubmissionUrl, createRegistry, prepareDestinations, PrototypeLedger} from '/opt/lab/tracking-system/contract.mjs';
import {createClientPage} from './client-page.mjs';
const client = buildPurposeClientCandidate(readFileSync('/opt/wordpress/wp-content/plugins/bsre-enquiries/assets/lead.js'));
const origin = 'https://blackswanrealestate.ae';
const input = createInterface({input:process.stdin,crlfDelay:Infinity});
let pending;
input.on('line',line=>{const current=pending;pending=null;if(!current)throw new Error('Unexpected reply');clearTimeout(current.timer);current.resolve(JSON.parse(line));});
input.on('close',()=>{if(pending){clearTimeout(pending.timer);pending.reject(new Error('Pipe closed'));pending=null;}});
function command(value){return new Promise((resolve,reject)=>{if(pending)throw new Error('Concurrent pipe call');pending={resolve,reject,timer:setTimeout(()=>reject(new Error('Pipe timeout')),15000)};process.stdout.write(JSON.stringify(value)+'\n');});}
const checks = {};
function check(name,condition){if(!condition)throw new Error(name);checks[name]=true;}
function verifySyntheticAdsProjection(receipt, submissionUrl){
  // Exercise the real receiver IDs with a fictional mapping and consent fixture.
  // The approved deployment mapping and its consent inputs are separate gates.
  const campaign={campaign_key:'BSRE-C0001',landing_page_id:'BSRE-LP0001',
    path:'/lp/bsre-c0001/',page_version:'0.0.1',page_family:'TEST',
    property_destination:'dubai',property_segment:'residential_offplan',transaction_intent:'buy',language:'en',
    ctas:[{cta_id:'bsre-test-form',cta_type:'form',cta_position:'body',form_id:'test-form',
      destination_key:'test-intake',submission_path:'/enquire/off-plan/'}]};
  const event={event:'bsre_lead_accepted',schema_version:1,campaign_key:campaign.campaign_key,
    landing_page_id:campaign.landing_page_id,page_version:campaign.page_version,cta_id:'bsre-test-form',
    internal_event_id:receipt.event_id,evidence:{source:'server_confirmed',verified:true,reference:'TEST_ONLY-durable'},
    receipt:{accepted:true,durable:true,lead_id:receipt.lead_id,event_id:receipt.event_id,
      original_analytics:false,original_advertising:true,original_ad_user_data:true,submission_url:submissionUrl}};
  const now=Date.now();
  const options={registry:createRegistry([campaign]),ledger:new PrototypeLedger(),now,
    consent:{verified:true,server_eligible:true,expires_at:new Date(now+60000).toISOString(),analytics:false,
      advertising:true,ad_user_data:true,personalization:false,qa:false,admin:false},
    mappings:{ads:{approved:true,send_to:'AW-999999999/testonly',evidence_ref:'TEST_ONLY-ads',
      route:'native_web_only',supported_dedup_field:'transaction_id',secondary:true}}};
  const first=prepareDestinations(event,options);
  const retry=prepareDestinations(event,options);
  check('actual_receiver_event_id_is_preserved_in_offline_ads_projection',first.network_calls===0&&
    first.output.length===1&&first.output[0].destination==='ads'&&
    first.output[0].payload.transaction_id===receipt.event_id&&first.output[0].status==='prepared_only_not_delivered');
  check('actual_receiver_event_id_suppresses_offline_retry',retry.network_calls===0&&
    retry.output.length===1&&retry.output[0].status==='duplicate_suppressed');
}
async function main(){
  for(const [slug,role,timeline] of [['off-plan','off_plan','Within 1 month'],['resale','resale','Within 1 month'],['rent','tenant','Immediate / move now'],['sell','seller','As soon as practical'],['let','landlord','Vacant / available to discuss now']]){
    for(const [label,analytics,advertising] of [['denied',false,false],['analytics',true,false],['advertising',false,true],['both',true,true]]){
      const key=slug+'_'+label;const setup=await command({op:'session',scenario:{slug,role,timeline,analytics,advertising}});const store=new Map();
      const options={client,origin,slug,role,timeline,csrf:setup.csrf,store,analytics,advertising,eligible:true,snapshot:setup.snapshot,
        name:'SYNTHETIC purpose '+key,purposeAttributionEndpoint:origin+'/wp-json/bsre/v1/purpose-lead',request:value=>command({op:'request',...value})};
      createClientPage({...options,locationPath:'/enquire/'+slug+'/?utm_source=FIRST&gclid=Exact_Click.A~9&utm_id=Private_ID&google_campaign_id=000123'});
      const page=createClientPage({...options,locationPath:'/enquire/'+slug+'/?utm_source=LATEST'});
      await page.submit();
      // One selected scenario loses the receiver acknowledgement and retries.
      if(!page.acceptedResponse?.body?.accepted){
        const reload=createClientPage({...options,blank:true});await reload.submit();
        check(key+'_blank_reload_recovers_original_receipt',reload.status.dataset.state==='success');
        await page.submit();
      }
      check(key+'_durable_receipt',page.acceptedResponse?.body?.accepted===true);
      check(key+'_private_metadata_absent_from_events',!JSON.stringify(page.events).includes('Exact_Click')&&!JSON.stringify(page.events).includes('Private_ID'));
      const request=page.requests.find(value=>value.url.endsWith('/purpose-lead'));
      check(key+'_uses_versioned_endpoint',!!request);
      const envelope=JSON.parse(request.request.body);
      check(key+'_analytics_original_and_latest',!analytics||(envelope.attribution.analytics.first.parameters.utm_source==='FIRST'&&envelope.attribution.analytics.last.parameters.utm_source==='LATEST'));
      check(key+'_advertising_click_retained',!advertising||envelope.attribution.advertising.last.parameters.gclid==='Exact_Click.A~9');
      const inspected=await command({op:'inspect',request_id:JSON.parse(envelope.wire_body).request_id});
      for(const [name,passed]of Object.entries(inspected.checks))check(key+'_'+name,passed===true);
      const receipt=page.acceptedResponse.body;
      const submissionUrl=acceptedSubmissionUrl(envelope.wire_body,inspected.synthetic_capture,receipt);
      check(key+'_accepted_wire_binds_exact_service',submissionUrl===origin+'/enquire/'+slug+'/');
      if(key==='off-plan_advertising')verifySyntheticAdsProjection(receipt,submissionUrl);
    }
  }
  await command({op:'complete',checks});
  input.close();
}
main().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;input.close();});
