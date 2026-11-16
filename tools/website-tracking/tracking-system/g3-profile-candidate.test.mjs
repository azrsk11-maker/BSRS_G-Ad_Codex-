import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {buildG3WordPressCandidate,buildG3ProfileCandidate} from './build-g3-profile-candidate.mjs';
import {buildG2ProfileCandidate} from './build-g2-profile-candidate.mjs';
import {buildRetentionAdmissionClient} from './build-retention-admission-candidate.mjs';
const fixture=new URL('../../staging-lab/fixtures/bsre-enquiries/',import.meta.url);
const original=readFileSync(new URL('assets/wordpress.js',fixture));
const script=buildG3WordPressCandidate(original).candidate;
const origin='https://blackswanrealestate.ae';
const valid=()=>({csrf_token:'1794800000.'+'a'.repeat(64),expires_in:7200,minimum_delay_ms:2100,measurement_eligible:true,
  transport:{contract:'bsre-profile-transport-v1',purpose_endpoint:origin+'/wp-json/bsre/v1/purpose-lead',admission_required:true}});
const flush=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
async function boot(responses=[valid()],override={}){
  const handlers={},intervals=[],events=[],calls=[],delays=[];
  const window={location:{origin},BSREWordPress:{contextEndpoint:origin+'/wp-json/bsre/v1/context',leadEndpoint:origin+'/wp-json/bsre/v1/lead',...override},
    fetch:async(url,args)=>{calls.push({url,args});const next=responses.shift();if(next instanceof Error)throw next;return {ok:true,json:async()=>next};},
    setTimeout:(fn,ms)=>{delays.push(ms);if(ms===2100)queueMicrotask(fn);return delays.length;},clearTimeout:()=>{},
    setInterval:fn=>intervals.push(fn),addEventListener:(name,fn)=>handlers[name]=fn,dispatchEvent:e=>events.push(e.type),
    CustomEvent:class{constructor(type){this.type=type;}}};
  vm.runInNewContext(script,{window,URL,AbortController});await flush();
  return {window,handlers,intervals,events,calls,delays};
}
test('immutable original and complete G2/admission ancestry are preserved',()=>{
  assert.throws(()=>buildG3WordPressCandidate(Buffer.concat([original,Buffer.from('\n')])),/SOURCE_CHANGED/);
  assert.throws(()=>buildG3WordPressCandidate(original.toString()),/SOURCE_CHANGED/);
  const audit=readFileSync(new URL('../../../docs/audit/INSTALLED_SOURCE_COMPARISON_2026-11-07.json',import.meta.url));
  const parent=buildG2ProfileCandidate(audit),child=buildG3ProfileCandidate(audit);
  const p=new Map(parent.files.map(r=>[r.path,r.content_base64])),c=new Map(child.files.map(r=>[r.path,r.content_base64]));
  assert.equal(c.size,41);assert.equal(child.deployment_prohibited,true);assert.equal(child.complete_coupled_profile,false);
  for(const [name,bytes] of p)if(!['bsre-enquiries.php','assets/lead.js','assets/wordpress.js'].includes(name))assert.equal(c.get(name),bytes,name);
  assert.equal(Buffer.from(c.get('assets/lead.js'),'base64').toString(),buildRetentionAdmissionClient(readFileSync(new URL('assets/lead.js',fixture))));
  const main=Buffer.from(c.get('bsre-enquiries.php'),'base64').toString();
  assert.ok(main.indexOf('/g2-profile/bootstrap.php')<main.indexOf('/g3-profile/bootstrap.php'));
});
test('validated server transport survives initial setup, timed refresh and pageshow',async()=>{
  const b=await boot([valid(),valid(),valid()]);
  for(const phase of ['initial','interval','pageshow']){
    if(phase==='interval'){await b.intervals[0]();await flush();}
    if(phase==='pageshow'){b.handlers.pageshow({persisted:true});await flush();}
    assert.equal(b.window.BSRELeadConfig.retentionAdmissionRequired,true);
    assert.equal(b.window.BSRELeadConfig.purposeAttributionEndpoint,origin+'/wp-json/bsre/v1/purpose-lead');
  }
  assert.equal(b.calls.length,3);assert.equal(b.events.length,3);assert.equal(b.delays.filter(n=>n===2100).length,3);
});
test('failed renewal clears previous purpose and admission configuration',async()=>{
  const b=await boot([valid(),new Error('offline')]);assert.ok(b.window.BSRELeadConfig.endpoint);
  await b.intervals[0]();await flush();assert.equal(b.window.BSRELeadConfig.endpoint,'');
  assert.equal(b.window.BSRELeadConfig.purposeAttributionEndpoint,undefined);assert.equal(b.events.length,1);
});
for(const [label,mutate] of [
  ['disabled',x=>x.transport.admission_required=false],['numeric',x=>x.transport.admission_required=1],
  ['wrong-contract',x=>x.transport.contract='other'],['extra-private-field',x=>x.transport.email='fixture@example.invalid'],
  ['foreign',x=>x.transport.purpose_endpoint='https://foreign.invalid/wp-json/bsre/v1/purpose-lead'],
  ['array-endpoint',x=>x.transport.purpose_endpoint=[x.transport.purpose_endpoint]],
  ['oversized-endpoint',x=>x.transport.purpose_endpoint+='x'.repeat(600)],
  ['query',x=>x.transport.purpose_endpoint+='?gclid=synthetic'],['fragment',x=>x.transport.purpose_endpoint+='#token'],
  ['wrong-route',x=>x.transport.purpose_endpoint=origin+'/wp-json/bsre/v1/lead'],['missing',x=>delete x.transport],
])test('unverified transport holds intake: '+label,async()=>{
  const response=valid();mutate(response);const b=await boot([response]);assert.equal(b.window.BSRELeadConfig.endpoint,'');assert.equal(b.events.length,0);
});
test('page flags and unknown response fields cannot override the server contract',async()=>{
  const response=valid();response.email='private@example.invalid';response.retentionAdmissionRequired=false;
  const b=await boot([response],{retentionAdmissionRequired:false,purposeAttributionEndpoint:'https://foreign.invalid/'});
  assert.equal(b.window.BSRELeadConfig.retentionAdmissionRequired,true);assert.equal(b.window.BSRELeadConfig.email,undefined);
  assert.equal(b.window.BSRELeadConfig.purposeAttributionEndpoint,origin+'/wp-json/bsre/v1/purpose-lead');
});
test('unowned bootstrap endpoint is rejected before fetching',async()=>{
  const b=await boot([valid()],{contextEndpoint:origin+'/wp-json/bsre/v1/context?token=bad'});assert.equal(b.calls.length,0);assert.equal(b.window.BSRELeadConfig.endpoint,'');
});
test('route ownership is explicit and cannot depend on admission registration early return',()=>{
  const source=readFileSync(new URL('./g3-route-context.php',import.meta.url),'utf8');
  assert.ok(source.includes('2000')&&source.includes("'callback'=>__NAMESPACE__.'\\\\'.$callback],true)"));
  assert.ok(!source.includes('E\\receive('));assert.ok(source.includes('PROFILE_UNAVAILABLE'));
  for(const name of ['receive_legacy','receive_purpose','proof','status']){
    const part=source.slice(source.indexOf('function '+name+'('));assert.ok(part.indexOf('if (!ready()) return held();')<part.indexOf('\n}'));
  }
});
