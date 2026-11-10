// All IDs, CTAs and PASS records below are synthetic test data, never site evidence.
import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {PAGE_TEST_IDS,validateTrackingMatrix} from './validate_tracking_matrix.mjs';

function fixture(count=2) {
  const resources=Array.from({length:count},(_,i)=>i+1).map(n=>({page_id:`BSRE-LP${String(n).padStart(4,'0')}`,campaign_key:`BSRE-C${String(n).padStart(4,'0')}`,
    campaign_id:String(999000000+n),wordpress_page_id:999000+n,url:`https://blackswanrealestate.ae/synthetic-only-${n}/`}));
  const context={proposal_sha256:'a'.repeat(64),commit:'b'.repeat(40),target_origin:'https://blackswanrealestate.ae',resources,
    operator:'synthetic-operator',pusher:'synthetic-pusher',expected_gtm_version:2,
    expected_tracking_ids:{gtm_container_id:'GTM-SYNTHETIC',ga4_web_stream_id:'999999999',ga4_measurement_id:'G-SYNTHETIC'},
    created_at_utc:'2026-11-07T01:00:00Z',observed_at_utc:'2026-11-07T03:00:00Z',valid_until_utc:'2026-11-07T08:00:00Z'};
  const matrix={schema_version:1,proposal_sha256:context.proposal_sha256,commit:context.commit,target_origin:context.target_origin,
    production_synthetic_conversions:0,pages:resources.map(resource=>({...resource,gtm_container_id:'GTM-SYNTHETIC',gtm_version:2,
      ga4_web_stream_id:'999999999',ga4_measurement_id:'G-SYNTHETIC',conversion_action_mapping:{operational_event:'form_accepted',
        ga4_event:'generate_lead',ads_action_id:'99999999',ads_route:'NATIVE_ADS_SECONDARY'},
      cta_inventory:[{cta_id:'TEST_ONLY:cta',placement:'TEST_ONLY:hero',destination:resource.url,status:'PASS',evidence_ref:'TEST_ONLY:cta-evidence'}],
      results:PAGE_TEST_IDS.map(test_id=>({test_id,status:'PASS',evidence_ref:`TEST_ONLY:${resource.page_id}:${test_id}`})),
      journey_correlation:Object.fromEntries(['acceptance','email','sheet'].map(kind=>[kind,{
        lead_sha256:createHash('sha256').update('TEST_ONLY:lead:'+resource.page_id).digest('hex'),
        source_sha256:createHash('sha256').update('TEST_ONLY:source:'+resource.page_id).digest('hex')}])),
      reviewer:'synthetic-reviewer',method:'AUTHENTICATED_STAGING_ACCEPTANCE',observed_at_utc:'2026-11-07T02:00:00Z',
      valid_until_utc:'2026-11-07T08:00:00Z',evidence_ref:`TEST_ONLY:${resource.page_id}`}))};
  context.inventory={schema_version:1,target_origin:context.target_origin,pages:matrix.pages.map(page=>
    Object.fromEntries([...['page_id','campaign_key','campaign_id','wordpress_page_id','url','gtm_container_id','gtm_version',
      'ga4_web_stream_id','ga4_measurement_id','conversion_action_mapping'].map(key=>[key,structuredClone(page[key])]),
      ['cta_inventory',page.cta_inventory.map(({cta_id,placement,destination})=>({cta_id,placement,destination}))]]))};
  return {matrix,context};
}
const check=input=>validateTrackingMatrix(input.matrix,input.context);
test('two-page synthetic evidence is consistent but cannot authenticate or authorize',()=>{
  const result=check(fixture()); assert.equal(result.matrix_consistent,true);assert.equal(result.acceptance_complete,true);
  assert.equal(result.complete_page_count,2);assert.equal(result.evidence_authenticated,false);
  assert.equal(result.execution_allowed,false);assert.equal(result.release_authorized,false);
});
test('global PASS or page-ID lists cannot substitute for individual outcomes',()=>{
  for (const mutate of [x=>delete x.matrix.pages[0].results,x=>x.matrix.pages[0].results.pop(),
    x=>x.matrix.pages[0].results[0]=x.matrix.pages[0].results[1],x=>x.matrix.pages.pop()]) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('exact native identities and complete unique page membership are mandatory',()=>{
  for (const [key,value] of [['url','https://blackswanrealestate.ae/other/'],['wordpress_page_id',999999],
    ['campaign_id','999999999'],['campaign_key','BSRE-C0360'],['page_id','BSRE-LP0360']]) {
    const input=fixture();input.matrix.pages[0][key]=value;assert.equal(check(input).acceptance_complete,false,key);
  }
  const input=fixture();input.matrix.pages[1]=structuredClone(input.matrix.pages[0]);assert.equal(check(input).matrix_consistent,false);
});
test('one failed, partial, blocked or unexecuted page outcome keeps the whole cohort pending',()=>{
  for (const status of ['FAIL','PARTIAL','BLOCKED','NOT_EXECUTED']) {
    const input=fixture();Object.assign(input.matrix.pages[1].results[0],{status,evidence_ref:status==='NOT_EXECUTED'?null:'TEST_ONLY:pending'});
    const result=check(input);assert.equal(result.matrix_consistent,true);assert.equal(result.acceptance_complete,false);
    assert.equal(result.complete_page_count,1);assert.equal(result.pending_result_count,1);
  }
});
test('recorded results and CTA checks require their own evidence references',()=>{
  for (const mutate of [x=>x.matrix.pages[0].results[0].evidence_ref=null,x=>x.matrix.pages[0].cta_inventory[0].evidence_ref=null,
    x=>x.matrix.pages[0].reviewer=null,x=>x.matrix.pages[0].evidence_ref=null]) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('unknown configuration and entirely unexecuted evidence remain honestly pending',()=>{
  const input=fixture();for (const page of input.matrix.pages) {
    for (const key of ['gtm_container_id','gtm_version','ga4_web_stream_id','ga4_measurement_id','conversion_action_mapping',
      'reviewer','method','observed_at_utc','valid_until_utc','evidence_ref']) page[key]=null;
    page.journey_correlation=null;
    for (const result of [...page.results,...page.cta_inventory]) {result.status='NOT_EXECUTED';result.evidence_ref=null;}
  }
  for (const page of input.context.inventory.pages) for (const key of ['gtm_container_id','gtm_version','ga4_web_stream_id','ga4_measurement_id','conversion_action_mapping']) page[key]=null;
  const result=check(input);assert.equal(result.matrix_consistent,true);assert.equal(result.acceptance_complete,false);
});
test('HTTP, unit and configuration readbacks cannot close complete journey acceptance',()=>{
  for (const method of ['PUBLIC_HTTP_GET','LOCAL_UNIT_TEST','AUTHENTICATED_CONFIGURATION_READBACK','CONTROLLED_INTEGRATION']) {
    const input=fixture();input.matrix.pages[0].method=method;assert.equal(check(input).acceptance_complete,false);
  }
});
test('page evidence must precede aggregate review and cover its complete validity window',()=>{
  for (const [key,value] of [['observed_at_utc','2026-11-07T00:00:00Z'],['observed_at_utc','2026-11-07T04:00:00Z'],
    ['observed_at_utc','2026-02-30T02:00:00Z'],['valid_until_utc','2026-11-07T07:59:59Z']]) {
    const input=fixture();input.matrix.pages[0][key]=value;assert.equal(check(input).acceptance_complete,false);
  }
});
test('all configured CTA identities, destinations and outcomes must be complete',()=>{
  for (const mutate of [x=>x.matrix.pages[0].cta_inventory=[],x=>x.matrix.pages[0].cta_inventory.push(x.matrix.pages[0].cta_inventory[0]),
    x=>x.matrix.pages[0].cta_inventory[0].destination='javascript:alert(1)',x=>x.matrix.pages[0].cta_inventory[0].status='PARTIAL']) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('shared measurement, canonical acceptance and secondary-only route cannot drift',()=>{
  for (const mutate of [x=>x.matrix.pages[1].gtm_version=3,x=>x.matrix.pages[1].ga4_web_stream_id='888888888',
    x=>x.matrix.pages[0].conversion_action_mapping.ga4_event='form_start',
    x=>x.matrix.pages[0].conversion_action_mapping.ads_route='PRIMARY',x=>x.matrix.pages[0].gtm_version=true]) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('reviewed inventory prevents CTA omissions, cross-page swaps and wrong destinations',()=>{
  for (const mutate of [x=>x.matrix.pages[0].cta_inventory[0].destination=x.matrix.pages[1].url,
    x=>x.context.inventory.pages[0].cta_inventory.push({cta_id:'TEST_ONLY:omitted',placement:'TEST_ONLY:footer',destination:x.matrix.pages[0].url}),
    x=>{for(const page of x.matrix.pages)page.gtm_container_id='GTM-WRONG';},
    x=>{for(const page of x.matrix.pages)page.conversion_action_mapping.ads_action_id='88888888';},
    x=>x.context.expected_gtm_version=3,x=>x.context.inventory.pages[0].conversion_action_mapping.primary=true]) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('acceptance, email and Sheet must identify the same opaque Lead ID and source',()=>{
  for (const mutate of [x=>x.matrix.pages[0].journey_correlation=null,
    x=>x.matrix.pages[0].journey_correlation.sheet.lead_sha256='e'.repeat(64),
    x=>x.matrix.pages[0].journey_correlation.email.source_sha256='e'.repeat(64)]) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('known last-pusher self-review is rejected without requiring a GitHub reviewer account',()=>{
  const input=fixture();input.matrix.pages[0].reviewer='SYNTHETIC-PUSHER';assert.equal(check(input).acceptance_complete,false);
  input.matrix.pages[0].reviewer='Independent Staff Reviewer';assert.equal(check(input).acceptance_complete,true);
});
test('a copied successful page report or accepted journey cannot certify a second page',()=>{
  for (const mutate of [x=>x.matrix.pages[1].evidence_ref=x.matrix.pages[0].evidence_ref,
    x=>x.matrix.pages[1].journey_correlation=structuredClone(x.matrix.pages[0].journey_correlation)]) {
    const input=fixture();mutate(input);assert.equal(check(input).acceptance_complete,false);
  }
});
test('all 360 synthetic pages fit both release metadata and bounded CLI limits',t=>{
  const input=fixture(360);const matrixBytes=Buffer.byteLength(JSON.stringify(input.matrix));
  const inventoryBytes=Buffer.byteLength(JSON.stringify(input.context.inventory));const payloadBytes=Buffer.byteLength(JSON.stringify(input));
  assert.ok(matrixBytes<2_000_000);assert.ok(inventoryBytes<2_000_000);assert.ok(payloadBytes<4_000_000);
  const script=fileURLToPath(new URL('./validate_tracking_matrix.mjs',import.meta.url));
  const result=spawnSync(process.execPath,[script,'--stdin'],{input:JSON.stringify(input),encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).complete_page_count,360);
  t.diagnostic(`Synthetic boundary bytes: matrix=${matrixBytes}, inventory=${inventoryBytes}, CLI=${payloadBytes}`);
});
test('malformed shapes fail safely and error reports never reflect input bodies',()=>{
  for (const value of [null,[],{},'PRIVATE_CANARY',true]) {
    const input=fixture();input.matrix.pages[0].results=value;const result=check(input);
    assert.equal(result.acceptance_complete,false);assert.equal(JSON.stringify(result).includes('PRIVATE_CANARY'),false);
  }
  for (const value of [null,[],{},true]) assert.equal(validateTrackingMatrix(value,value).acceptance_complete,false);
});
test('bounded stdin CLI reports only sanitized validation results',()=>{
  const script=fileURLToPath(new URL('./validate_tracking_matrix.mjs',import.meta.url));
  const valid=spawnSync(process.execPath,[script,'--stdin'],{input:JSON.stringify(fixture()),encoding:'utf8'});
  assert.equal(valid.status,0,valid.stderr);assert.equal(JSON.parse(valid.stdout).acceptance_complete,true);
  assert.equal(valid.stdout.includes('synthetic-reviewer'),false);
  const duplicate=JSON.stringify(fixture()).replace('"schema_version":1','"schema_version":1,"schema_version":1');
  for (const input of ['PRIVATE_CANARY',JSON.stringify({...fixture(),unexpected:'PRIVATE_CANARY'}),duplicate,
    JSON.stringify(fixture()).replace('"gtm_version":2','"gtm_version":1e999'),' '.repeat(4_000_001)]) {
    const bad=spawnSync(process.execPath,[script,'--stdin'],{input,encoding:'utf8'});
    assert.notEqual(bad.status,0);assert.equal(JSON.parse(bad.stdout).acceptance_complete,false);
    assert.equal(bad.stdout.includes('PRIVATE_CANARY'),false);
  }
});
