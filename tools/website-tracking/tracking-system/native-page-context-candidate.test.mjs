/** Portable public synthetic context checks; no fixture writes or network. */
import assert from 'node:assert/strict';
import {test} from 'node:test';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {resolve,dirname,join} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {buildNativePageContextClient,buildNativePageContextPresentation,reverseNativePageContext,sha256} from './build-native-page-context-candidate.mjs';
const source=resolve(process.env.BSRE_G4_SOURCE_ROOT || join(dirname(fileURLToPath(import.meta.url)),'../../..'));
const read=path=>readFileSync(join(source,path),'utf8');
const plugin='tools/staging-lab/fixtures/bsre-enquiries/';
const original=read(plugin+'assets/lead.js'),presentation=read(plugin+'includes/presentation.php');
const {buildRetentionAdmissionClient}=await import(pathToFileURL(join(source,'tools/website-tracking/tracking-system/build-retention-admission-candidate.mjs')));
const admission=buildRetentionAdmissionClient(Buffer.from(original));
const client=buildNativePageContextClient(admission,sha256(admission));
const php=buildNativePageContextPresentation(presentation,sha256(presentation));
const check=(name,fn)=>test(name,fn);
let calls=0;
const fixture=()=>({schema:1,registry_revision:'SYNTHETIC-TEST-v1',company:'BlackSwan Real Estate',page_path:'/enquire/off-plan/',role:'off_plan',page_context:{campaign_key:'BSRE-C0001',landing_page_id:'BSRE-LP0001',page_version:'test-v1',page_family:'test-family',language:'en'},forms:['BSRE-TEST-ENQUIRY'],ctas:[{cta_id:'BSRE-TEST-HERO-PHONE',cta_type:'phone',cta_position:'hero',destination_key:'TEST_PHONE'},{cta_id:'BSRE-TEST-HERO-ORDINARY',cta_type:'ordinary',cta_position:'hero',destination_key:'TEST_MAIN'},{cta_id:'BSRE-TEST-TOOL',cta_type:'calculator',cta_position:'form',destination_key:'TEST_TOOL'}]});
function browser(config=fixture(),path=config?.page_path || '/enquire/off-plan/') {
  const events=[], handlers={}; let allowed=true;
  const window={BSRENativePageContextConfig:config,location:{protocol:'https:',origin:'https://example.invalid',href:'https://example.invalid'+path+'?campaign_key=BSRE-C9999&email=test@example.invalid',pathname:path},
    BSREConsentBridge:{measurementEligible:()=>true,permissions:()=>({analytics:allowed,advertising:allowed}),getSnapshot:()=>({known:true,acknowledged:true})},
    BSRELeadConfig:{measurementEligible:true},crypto:{randomUUID:()=> '00000000-0000-4000-8000-000000000001'},
    addEventListener:(name,fn)=>{handlers[name]=fn;},dispatchEvent:event=>events.push(event),CustomEvent:class {constructor(type,{detail}) {this.type=type;this.detail=detail;}},
    fetch:()=>{calls++;throw new Error('NETWORK_FORBIDDEN');}};
  const document={readyState:'loading',querySelector:()=>null,querySelectorAll:()=>[],addEventListener:()=>{}};
  vm.runInNewContext(client.output,{window,document,URL,URLSearchParams,console,Uint8Array,AbortController,structuredClone},{timeout:2000});
  return {window,events,deny:()=>{allowed=false;},handlers,port:window.BSRENativePageContext};
}
const round=value=>JSON.parse(JSON.stringify(value));
check('final admission-derived client composes, parses and reverses byte-exactly',()=>{
  new vm.Script(client.output); assert.equal(reverseNativePageContext(client),admission); assert.equal(client.edits.length,5);
  assert.match(client.output,/retentionAdmissionRequired/); assert.match(client.output,/purposeAttributionEndpoint/);
});
check('presentation extension reverses and preserves full server transport config input',()=>{
  assert.equal(reverseNativePageContext(php),presentation); assert.equal(php.edits.length,2);
  assert.match(php.output,/array_merge\(\['contextEndpoint' => '', 'leadEndpoint' => ''\], \$lead_config\)/);
  assert.match(php.output,/BSRENativePageContextConfig=/); assert.match(php.output,/catch \(\\Throwable/);
});
check('wrong preimage, missing anchor and repeated composition fail closed',()=>{
  assert.throws(()=>buildNativePageContextClient(admission,'0'.repeat(64)),/PREIMAGE/);
  const broken=admission.replace('  function safeCanonical(event) {','  function absent(event) {');
  assert.throws(()=>buildNativePageContextClient(broken,sha256(broken)),/ANCHOR/);
  assert.throws(()=>buildNativePageContextClient(client.output,sha256(client.output)),/ANCHOR/);
});
check('trusted current config is copied/frozen and ignores PII/campaign URL query',()=>{
  const b=browser(), c=b.port.current(); assert.equal(c.page_context.campaign_key,'BSRE-C0001'); assert(Object.isFrozen(c.page_context));
  assert(!JSON.stringify(c).includes('test@example.invalid')); assert(!JSON.stringify(c).includes('C9999'));
});
check('unreviewed current path, encoded or PII path and insecure context reject',()=>{
  for(const path of ['/unreviewed/','/person%40example.invalid/','/../','/1234567890/']) assert.equal(browser(fixture(),path).port.current(),null);
  const b=browser(); b.window.location.protocol='http:'; assert.equal(b.port.current(),null);
});
check('malformed/extra/PII config and arbitrary campaign metadata reject',()=>{
  const mutations=[c=>c.email='test@example.invalid',c=>c.page_context.email='test@example.invalid',c=>c.page_context.property_id='test@example.invalid',c=>c.page_context.project_id='https://example.invalid/',c=>c.page_context.campaign_key='arbitrary',c=>delete c.page_context.landing_page_id,c=>c.ctas[0].destination_url='tel:123',c=>c.ctas.push(c.ctas[0]),c=>c.forms.push(c.forms[0]),c=>c.page_context.form_text='private'];
  for(const mutate of mutations){const c=fixture();mutate(c);assert.equal(browser(c).port.current(),null);}
});
check('config rehydrates from current server assignment and stale page context is held',()=>{
  const b=browser(); assert.equal(b.port.current().page_context.page_version,'test-v1');
  const next=fixture(); next.page_context.page_version='test-v2'; b.window.BSRENativePageContextConfig=next;
  assert.equal(b.port.current().page_context.page_version,'test-v2'); b.window.location.pathname='/contact/'; assert.equal(b.port.current(),null);
});
check('all contract events have explicit operational/GA4 mapping and evidence dependency',()=>{
  const contract=JSON.parse(read('docs/google-ads/website_tracking_contract.json')); const b=browser();
  assert.equal(contract.events.length,23);
  for(const row of contract.events){const mapping=b.port.mapping(row.operational_event);assert(mapping,row.operational_event);assert.equal(mapping.operational_event,row.operational_event);assert.equal(mapping.ga4_event,row.proposed_ga4_event);assert.equal(mapping.evidence_source,row.evidence_source);}
  assert.equal(b.port.mapping('invented_event'),null); assert.equal(b.port.mapping('__proto__'),null);
});
check('legacy phone/form aliases reconcile once without changing canonical schema',()=>{
  const b=browser(); assert.equal(b.port.mapping('telephone_click').operational_event,'phone_click');
  assert.equal(b.port.mapping('form_submit').operational_event,'form_accepted');
  const sent=[]; assert.equal(b.window.BSREMeasurement.connect('ga4',payload=>sent.push(payload)),true);
  b.window.BSRELead.trackContact('telephone','hero'); assert.equal(sent.length,1); assert.equal(sent[0].event_name,'phone_click');
  assert.equal(b.events.length,1); assert.equal(b.events[0].detail.event,'telephone_click');
  assert.equal(sent[0].parameters.page_path,'/enquire/off-plan/'); assert.equal(sent[0].parameters.campaign_key,'BSRE-C0001');
  assert(!JSON.stringify(sent[0]).includes('event_id')); assert(!JSON.stringify(sent[0]).includes('decision_version'));
});
check('metadata projection excludes receipt, Lead ID, source histories and form text',()=>{
  const b=browser(), mapped=b.window.BSREMeasurement.mapGA4({event:'form_submit',event_id:'TEST_ONLY_event',page_path:'/enquire/off-plan/',role:'off_plan',lead_id:'PRIVATE_LEAD',email:'test@example.invalid',receipt:{foo:'private'},utm_source:'PRIVATE_SOURCE',message:'PRIVATE_TEXT'});
  assert.equal(mapped.event_name,'generate_lead');
  for(const key of ['event_id','lead_id','email','receipt','utm_source','message']) assert(!Object.hasOwn(mapped.parameters,key));
  assert.equal(b.window.BSREMeasurement.dispatch('ga4',{event:'form_submit',event_id:'TEST_ONLY_event',page_path:'/enquire/off-plan/',role:'off_plan'},()=>{throw new Error('must not dispatch');}),false);
});
check('specialized CTA supplies one canonical mapping; result/booking cannot be inferred from click',()=>{
  const b=browser(); assert.equal(b.port.clickMapping('BSRE-TEST-HERO-PHONE').event,'phone_click');
  assert.equal(b.port.clickMapping('BSRE-TEST-HERO-ORDINARY').event,'cta_click'); assert.equal(b.port.clickMapping('BSRE-TEST-TOOL'),null);
  assert.equal(b.port.clickMapping('BSRE-UNKNOWN'),null); assert.equal(b.port.component('form','BSRE-UNKNOWN'),null);
  assert.deepEqual(round(b.port.component('form','BSRE-TEST-ENQUIRY')),{form_id:'BSRE-TEST-ENQUIRY'});
});
check('reviewed main-site context maps current path without source reconstruction',()=>{
  const c=fixture(); c.page_path='/contact/';c.role='unknown'; const b=browser(c);
  const canonical={event:'form_start',event_id:'TEST_ONLY_start',page_path:'/contact/',role:'unknown'};
  assert.equal(b.window.BSREMeasurement.mapGA4(canonical).parameters.page_path,'/contact/');
  const invalid={...canonical,page_path:'/arbitrary/'}; assert.equal(b.window.BSREMeasurement.mapGA4(invalid),null);
  const histories=Object.freeze({analytics:Object.freeze({first:'A',latest:'B'}),advertising:null});
  const result=b.port.continuation(histories); assert.equal(result.permitted_histories,histories);assert.equal(result.current_page.page_path,'/contact/');
  assert.equal(b.port.continuation(null).permitted_histories,null); assert.equal(b.events.length,0);
});
check('optional context absent/invalid and denied measurement preserve existing intake surface',()=>{
  const b=browser(null); assert.equal(b.port.current(),null); assert.equal(typeof b.window.BSRELead.init,'function');
  assert.equal(b.window.BSREMeasurement.mapGA4({event:'telephone_click',event_id:'TEST_ONLY_legacy',page_path:'/enquire/',role:'unknown'}).event_name,'phone_click');
  const sent=[]; b.window.BSREMeasurement.connect('ga4',payload=>sent.push(payload)); b.deny(); b.window.BSRELead.trackContact('telephone','hero');assert.equal(sent.length,0);
});
check('version syntax supports reviewed semantic versions while malformed revisions reject',()=>{
  const c=fixture();c.page_context.page_version='0.0.1';assert.equal(browser(c).port.current().page_context.page_version,'0.0.1');
  for(const revision of [undefined,null,123,'test@example.invalid']){const bad=fixture();bad.registry_revision=revision;assert.equal(browser(bad).port.current(),null);}
});
check('signed request construction and accepted-response intake path remain byte-identical',()=>{
  const from=admission.indexOf('  function requestHeaders('), to=admission.indexOf('  function init()');
  assert(from>0 && to>from);assert.equal(client.output.slice(client.output.indexOf('  function requestHeaders('),client.output.indexOf('  function init()')),admission.slice(from,to));
});
