// Addendum 24.7: per-page evidence consistency, never authenticated acceptance.
import {pathToFileURL} from 'node:url';

export const PAGE_TEST_IDS = Object.freeze(Array.from({length:30}, (_, i) => `WT-${String(i+1).padStart(3,'0')}`)
  .filter(id => !['WT-001','WT-003','WT-004','WT-009','WT-027'].includes(id)));
const STATES = new Set(['NOT_EXECUTED','PARTIAL','PASS','FAIL','BLOCKED']);
const METHODS = new Set(['AUTHENTICATED_STAGING_ACCEPTANCE','AUTHENTICATED_CONFIGURATION_READBACK',
  'NATIVE_BROWSER_NETWORK','CONTROLLED_INTEGRATION','PUBLIC_HTTP_GET','LOCAL_UNIT_TEST']);
const COMPLETE_METHODS = new Set(['AUTHENTICATED_STAGING_ACCEPTANCE','NATIVE_BROWSER_NETWORK']);
const ID = /^[A-Za-z0-9][A-Za-z0-9:_-]{0,127}$/;
const LOGIN = /^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/;
const reviewerName = value => typeof value==='string' && value.trim()===value && value.length>0 && value.length<=128 && !/[\x00-\x1f\x7f]/.test(value);
const RESOURCE_KEYS = ['page_id','campaign_key','campaign_id','wordpress_page_id','url'];
const INVENTORY_KEYS = [...RESOURCE_KEYS,'gtm_container_id','gtm_version','ga4_web_stream_id','ga4_measurement_id',
  'conversion_action_mapping','cta_inventory'];
const PAGE_KEYS = [...RESOURCE_KEYS,'gtm_container_id','gtm_version','ga4_web_stream_id','ga4_measurement_id',
  'conversion_action_mapping','cta_inventory','results','journey_correlation','reviewer','method','observed_at_utc','valid_until_utc','evidence_ref'];
const CONFIG_KEYS = ['gtm_container_id','gtm_version','ga4_web_stream_id','ga4_measurement_id','conversion_action_mapping'];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const exact = (value, keys) => object(value) && Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value,key));
const matches = (pattern,value) => typeof value === 'string' && pattern.test(value);
const positive = value => Number.isSafeInteger(value) && value > 0;
function instant(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(value)) return null;
  const time=Date.parse(value);
  return Number.isFinite(time) && new Date(time).toISOString() === value.replace('Z','.000Z') ? time : null;
}
function destination(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\s\x00-\x1f\x7f]/.test(value)) return false;
  try {
    const url = new URL(value);
    return (url.protocol === 'https:' && !!url.hostname && !url.username && !url.password) ||
      (url.protocol === 'tel:' && /^tel:\+?[1-9][0-9-]{5,19}$/.test(value)) ||
      (url.protocol === 'mailto:' && /^mailto:[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(value));
  } catch { return false; }
}
function parseStrictJSON(text) {
  let at=0;
  const whitespace=()=>{while (at<text.length && /[\x20\t\r\n]/.test(text[at])) at++;};
  const string=()=>{
    const start=at++; if (text[start]!=='"') throw Error();
    while (at<text.length) {
      if (text[at]==='"') {at++;return JSON.parse(text.slice(start,at));}
      if (text[at]==='\\') at++;
      at++;
    }
    throw Error();
  };
  const scalar=/(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/y;
  const value=depth=>{
    if (depth>64) throw Error(); whitespace();
    if (text[at]==='"') {string();return;}
    if (text[at]==='{' || text[at]==='[') {
      const isObject=text[at++]==='{',end=isObject?'}':']',keys=new Set(); whitespace();
      if (text[at]===end) {at++;return;}
      while (true) {
        if (isObject) {whitespace();const key=string();if(keys.has(key))throw Error();keys.add(key);whitespace();if(text[at++]!==':')throw Error();}
        value(depth+1);whitespace();if(text[at]===end){at++;return;}if(text[at++]!==',')throw Error();
      }
    }
    scalar.lastIndex=at;const match=scalar.exec(text);if(!match)throw Error();at=scalar.lastIndex;
  };
  value(0);whitespace();if(at!==text.length)throw Error();
  return JSON.parse(text,(_key,item)=>{if(typeof item==='number' && !Number.isFinite(item))throw Error();return item;});
}

export function validateTrackingMatrix(matrix, context) {
  const errors=[]; let pending=0, completed=0;
  const need=(condition,code) => { if (!condition) errors.push(code); };
  const report=() => ({schema_version:1,matrix_consistent:errors.length===0,errors:[...new Set(errors)],
    page_count:Array.isArray(matrix?.pages)?matrix.pages.length:0,complete_page_count:completed,pending_result_count:pending,
    acceptance_complete:errors.length===0 && completed>0 && completed===matrix?.pages?.length,
    evidence_authenticated:false,execution_allowed:false,release_authorized:false});
  if (!exact(context,['proposal_sha256','commit','target_origin','resources','inventory','expected_tracking_ids','expected_gtm_version',
    'operator','pusher','created_at_utc','observed_at_utc','valid_until_utc'])) {
    need(false,'CONTEXT_SHAPE'); return report();
  }
  const created=instant(context.created_at_utc), observed=instant(context.observed_at_utc), expiry=instant(context.valid_until_utc);
  need(matches(/^[0-9a-f]{64}$/,context.proposal_sha256) && matches(/^[0-9a-f]{40}$/,context.commit),'CONTEXT_HASHES');
  need(context.target_origin==='https://blackswanrealestate.ae','MAIN_SITE_ORIGIN');
  need(matches(LOGIN,context.operator) && matches(LOGIN,context.pusher),'CONTEXT_IDENTITIES');
  need(exact(context.expected_tracking_ids,['gtm_container_id','ga4_web_stream_id','ga4_measurement_id']),'EXPECTED_TRACKING_IDS');
  need(context.expected_gtm_version===null || positive(context.expected_gtm_version),'EXPECTED_TRACKING_VERSION');
  need(created!==null && observed!==null && expiry!==null && created<=observed && observed<expiry,'CONTEXT_TIME');
  if (!Array.isArray(context.resources) || !context.resources.length || context.resources.length>360 ||
      !context.resources.every(row=>exact(row,RESOURCE_KEYS))) {
    need(false,'CONTEXT_RESOURCES'); return report();
  }
  for (const key of RESOURCE_KEYS) need(new Set(context.resources.map(row=>row[key])).size===context.resources.length,'DUPLICATE_RESOURCE:'+key);
  for (const row of context.resources) {
    need(matches(/^BSRE-LP(?:00[0-9]{2}|0[12][0-9]{2}|03[0-5][0-9]|0360)$/,row.page_id) && row.page_id!=='BSRE-LP0000' &&
      row.campaign_key==='BSRE-C'+row.page_id.slice(-4) && matches(/^[1-9][0-9]{5,19}$/,row.campaign_id) &&
      positive(row.wordpress_page_id) && matches(/^https:\/\/blackswanrealestate\.ae\/(?:[a-z0-9-]+\/)+$/,row.url),'RESOURCE_IDENTITY');
  }
  const inventory=context.inventory;
  if (!exact(inventory,['schema_version','target_origin','pages']) || inventory.schema_version!==1 ||
      inventory.target_origin!==context.target_origin || !Array.isArray(inventory.pages) ||
      inventory.pages.length!==context.resources.length || !inventory.pages.every(row=>exact(row,INVENTORY_KEYS)) ||
      new Set(inventory.pages.map(row=>row.page_id)).size!==inventory.pages.length) {
    need(false,'REVIEWED_PAGE_INVENTORY'); return report();
  }
  if (!exact(matrix,['schema_version','proposal_sha256','commit','target_origin','production_synthetic_conversions','pages'])) {
    need(false,'MATRIX_SHAPE'); return report();
  }
  need(matrix.schema_version===1 && matrix.production_synthetic_conversions===0,'MATRIX_SAFETY');
  for (const key of ['proposal_sha256','commit','target_origin']) need(matrix[key]===context[key],'MATRIX_SCOPE:'+key);
  if (!Array.isArray(matrix.pages) || matrix.pages.length!==context.resources.length || matrix.pages.length>360) {
    need(false,'EXACT_PAGE_COVERAGE'); return report();
  }
  need(new Set(matrix.pages.map(row=>row?.page_id)).size===matrix.pages.length,'DUPLICATE_PAGE');
  const pageEvidence=matrix.pages.map(row=>row?.evidence_ref).filter(value=>value!==null && value!==undefined);
  need(new Set(pageEvidence).size===pageEvidence.length,'REUSED_PAGE_EVIDENCE_REFERENCE');
  const journeys=matrix.pages.map(row=>row?.journey_correlation?.acceptance?.lead_sha256).filter(value=>typeof value==='string');
  need(new Set(journeys).size===journeys.length,'REUSED_PAGE_ACCEPTANCE_JOURNEY');
  let sharedConfiguration;
  for (const [index,page] of matrix.pages.entries()) {
    const prefix=`PAGE_${index+1}:`; const before=errors.length; let pagePending=0;
    const check=(condition,code)=>need(condition,prefix+code);
    if (!exact(page,PAGE_KEYS)) {check(false,'SHAPE'); continue;}
    const resource=context.resources.find(row=>row.page_id===page.page_id);
    check(resource && RESOURCE_KEYS.every(key=>page[key]===resource[key]),'EXACT_RESOURCE_BINDING');
    const expected=inventory.pages.find(row=>row.page_id===page.page_id);
    check(expected && RESOURCE_KEYS.every(key=>page[key]===expected[key]),'REVIEWED_INVENTORY_RESOURCE_BINDING');
    for (const [key,valid] of [
      ['gtm_container_id',value=>matches(/^GTM-[A-Z0-9]+$/,value)], ['gtm_version',positive],
      ['ga4_web_stream_id',value=>matches(/^[1-9][0-9]{0,19}$/,value)],
      ['ga4_measurement_id',value=>matches(/^G-[A-Z0-9]+$/,value)]]) {
      if (page[key]===null) pagePending++; else check(valid(page[key]),'CONFIGURATION:'+key);
    }
    const mapping=page.conversion_action_mapping;
    if (mapping===null) pagePending++;
    else check(exact(mapping,['operational_event','ga4_event','ads_action_id','ads_route']) &&
      mapping.operational_event==='form_accepted' && mapping.ga4_event==='generate_lead' &&
      matches(/^[1-9][0-9]{0,19}$/,mapping.ads_action_id) && mapping.ads_route==='NATIVE_ADS_SECONDARY','CANONICAL_ACCEPTED_MAPPING');
    check(expected?.conversion_action_mapping===null || exact(expected?.conversion_action_mapping,
      ['operational_event','ga4_event','ads_action_id','ads_route']),'REVIEWED_MAPPING_SHAPE');
    for (const key of CONFIG_KEYS) {
      const same = key==='conversion_action_mapping' ? object(mapping) && object(expected?.[key]) &&
        ['operational_event','ga4_event','ads_action_id','ads_route'].every(field=>mapping[field]===expected[key][field]) : page[key]===expected?.[key];
      check(same || (page[key]===null && expected?.[key]===null),'REVIEWED_CONFIGURATION:'+key);
    }
    for (const key of ['gtm_container_id','ga4_web_stream_id','ga4_measurement_id'])
      if (page[key]!==null) check(page[key]===context.expected_tracking_ids?.[key],'VERIFIED_TRACKING_ID:'+key);
    if (context.expected_gtm_version!==null && page.gtm_version!==null)
      check(page.gtm_version===context.expected_gtm_version,'PROPOSED_TRACKING_VERSION');
    const configuration=JSON.stringify(CONFIG_KEYS.map(key=>key==='conversion_action_mapping' && object(page[key]) ?
      ['operational_event','ga4_event','ads_action_id','ads_route'].map(field=>page[key][field]) : page[key]));
    if (sharedConfiguration===undefined) sharedConfiguration=configuration;
    else check(configuration===sharedConfiguration,'SHARED_MEASUREMENT_CONFIGURATION');
    if (!Array.isArray(page.results) || page.results.length!==PAGE_TEST_IDS.length ||
        !page.results.every(row=>exact(row,['test_id','status','evidence_ref'])) ||
        new Set(page.results.map(row=>row.test_id)).size!==PAGE_TEST_IDS.length ||
        !page.results.every(row=>PAGE_TEST_IDS.includes(row.test_id))) check(false,'EXACT_INDIVIDUAL_OUTCOMES');
    else for (const result of page.results) {
      check(STATES.has(result.status),'RESULT_STATUS');
      if (result.status!=='PASS') pagePending++;
      check(result.status==='NOT_EXECUTED' ? result.evidence_ref===null : matches(ID,result.evidence_ref),'RESULT_EVIDENCE');
    }
    if (!Array.isArray(page.cta_inventory) || !page.cta_inventory.length || page.cta_inventory.length>128 ||
        !page.cta_inventory.every(cta=>exact(cta,['cta_id','placement','destination','status','evidence_ref'])) ||
        new Set(page.cta_inventory.map(cta=>cta.cta_id)).size!==page.cta_inventory.length) check(false,'CTA_INVENTORY');
    else for (const cta of page.cta_inventory) {
      check(matches(ID,cta.cta_id) && matches(ID,cta.placement) && destination(cta.destination),'CTA_IDENTITY_DESTINATION');
      check(STATES.has(cta.status) && (cta.status==='NOT_EXECUTED' ? cta.evidence_ref===null : matches(ID,cta.evidence_ref)),'CTA_OUTCOME');
      if (cta.status!=='PASS') pagePending++;
    }
    const expectedCtas=expected?.cta_inventory;
    check(Array.isArray(expectedCtas) && expectedCtas.length>0 && expectedCtas.length<=128 &&
      expectedCtas.every(cta=>exact(cta,['cta_id','placement','destination'])) &&
      new Set(expectedCtas.map(cta=>cta.cta_id)).size===expectedCtas.length && Array.isArray(page.cta_inventory) &&
      page.cta_inventory.length===expectedCtas.length && expectedCtas.every(cta=>page.cta_inventory.some(actual=>
        object(actual) && ['cta_id','placement','destination'].every(key=>actual[key]===cta[key]))),'EXACT_REVIEWED_CTA_INVENTORY');
    const joined=['WT-014','WT-024','WT-025'].every(id=>Array.isArray(page.results) && page.results.some(row=>row?.test_id===id && row.status==='PASS'));
    if (page.journey_correlation!==null || joined) {
      const correlation=page.journey_correlation;
      check(exact(correlation,['acceptance','email','sheet']) && ['acceptance','email','sheet'].every(kind=>
        exact(correlation[kind],['lead_sha256','source_sha256']) && ['lead_sha256','source_sha256'].every(key=>
          matches(/^[0-9a-f]{64}$/,correlation[kind][key]) && correlation[kind][key]===correlation.acceptance[key])),
      'SAME_LEAD_AND_SOURCE_DELIVERY_CORRELATION');
    }
    const recorded=[...(Array.isArray(page.results)?page.results:[]),...(Array.isArray(page.cta_inventory)?page.cta_inventory:[])].some(row=>row?.status!=='NOT_EXECUTED');
    if (recorded) {
      check(reviewerName(page.reviewer) && METHODS.has(page.method) && matches(ID,page.evidence_ref),'REVIEW_EVIDENCE');
      check(typeof page.reviewer==='string' && typeof context.pusher==='string' &&
        context.pusher.toLowerCase()!==page.reviewer.toLowerCase(),'INDEPENDENT_PAGE_REVIEWER');
      const at=instant(page.observed_at_utc), until=instant(page.valid_until_utc);
      check(at!==null && until!==null && created!==null && observed!==null && expiry!==null && created<=at && at<=observed && until>=expiry,'EVIDENCE_TIME');
      if ((Array.isArray(page.results) && page.results.some(row=>row?.status==='PASS')) ||
          (Array.isArray(page.cta_inventory) && page.cta_inventory.some(row=>row?.status==='PASS')))
        check(COMPLETE_METHODS.has(page.method),'LIVE_JOURNEY_METHOD_REQUIRED');
    } else check(['reviewer','method','observed_at_utc','valid_until_utc','evidence_ref'].every(key=>page[key]===null),'UNEXECUTED_METADATA');
    pending+=pagePending;
    if (errors.length===before && pagePending===0) completed++;
  }
  return report();
}

// Stdin only; no filesystem reads, network, writes or evidence-body output.
if (process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  let total=0; const chunks=[];
  try {
    if (process.argv.length!==3 || process.argv[2]!=='--stdin') throw Error();
    for await (const chunk of process.stdin) {
      total+=chunk.length; if (total>4_000_000) throw Error(); chunks.push(chunk);
    }
    const input=parseStrictJSON(new TextDecoder('utf-8',{fatal:true}).decode(Buffer.concat(chunks)));
    if (!exact(input,['matrix','context'])) throw Error();
    const result=validateTrackingMatrix(input.matrix,input.context);
    console.log(JSON.stringify(result)); process.exitCode=result.matrix_consistent?0:1;
  } catch {
    console.log(JSON.stringify({matrix_consistent:false,acceptance_complete:false,evidence_authenticated:false,
      execution_allowed:false,release_authorized:false,errors:['INVALID_OR_OVERSIZED_MATRIX_INPUT']})); process.exitCode=2;
  }
}
