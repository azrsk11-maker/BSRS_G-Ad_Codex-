/** Offline prototype only: no DOM, cookies, HTTP, Google SDK, storage or production writes. */
import {createHash} from 'node:crypto';
const ORIGIN='https://blackswanrealestate.ae';
const SEGMENTS=new Set(['residential_offplan','residential_ready_secondary','residential_rental','commercial_offplan',
  'commercial_ready','commercial_leasing','seller_supply','landlord_supply']);
const EMIRATES=new Set(['dubai','abu_dhabi','sharjah','ajman','ras_al_khaimah','fujairah','umm_al_quwain']);
const BROWSER_EVENTS=new Set(['page_view','cta_click','phone_click','whatsapp_click','email_click','form_start','form_error',
  'brochure_download','floorplan_view','calculator_complete','comparison_complete','property_view','lp_to_main_site']);
const EVIDENCE_SOURCES={form_accepted:['server_confirmed'],viewing_request:['server_confirmed'],
  viewing_booked:['booking_or_authorized_ledger'],viewing_attended:['authorized_ledger'],
  conversation_verified:['provider_or_authorized_ledger'],qualified_lead:['authorized_ledger'],
  mandate_signed:['authorized_ledger'],offer_submitted:['authorized_ledger'],transaction_closed:['authorized_ledger'],
  commission_collected:['finance_ledger']};
const OFFLINE_EVENTS=new Set(['conversation_verified','qualified_lead','mandate_signed','offer_submitted','transaction_closed','commission_collected']);
const SPECIAL_CTA={phone:'phone_click',whatsapp:'whatsapp_click',email:'email_click'};
const CODE=/^[a-z][a-z0-9_-]{0,63}$/;
const ID=/^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;
const exactKeys=(object, allowed)=>Boolean(object)&&typeof object==='object'&&!Array.isArray(object)&&Object.keys(object).every(k=>allowed.includes(k));
function fail(code){throw new Error(code);}
function require(condition, code){if(!condition)fail(code);}
function code(value){return typeof value==='string'&&CODE.test(value);}
function id(value){return typeof value==='string'&&ID.test(value);}
function freeze(value){return JSON.parse(JSON.stringify(value));}

export function queryFreeUrl(value){
  require(typeof value==='string','URL_REQUIRED');let url;
  try{url=new URL(value,ORIGIN);}catch{fail('URL_INVALID');}
  require(url.origin===ORIGIN&&!url.username&&!url.password&&!url.search&&!url.hash,'URL_NOT_APPROVED');
  require(/^\/(?:lp\/bsre-c\d{4}\/|enquire\/(?:off-plan\/|resale\/|rent\/|sell\/|let\/)?)$/.test(url.pathname),'PAGE_ROUTE_NOT_REVIEWED');
  return url.href;
}

export function createRegistry(records){
  require(Array.isArray(records)&&records.length>0,'REVIEWED_REGISTRY_REQUIRED');
  const byKey=new Map(), pages=new Set(), paths=new Set();
  for(const raw of records){
    require(exactKeys(raw,['campaign_key','landing_page_id','path','page_version','page_family','property_destination','property_segment',
      'transaction_intent','language','ctas']),'UNKNOWN_REGISTRY_FIELD');
    require(/^BSRE-C\d{4}$/.test(raw.campaign_key)&&/^BSRE-LP\d{4}$/.test(raw.landing_page_id),'STABLE_CONTEXT_ID_REQUIRED');
    require(!byKey.has(raw.campaign_key)&&!pages.has(raw.landing_page_id),'DUPLICATE_CAMPAIGN_OR_PAGE');
    const url=queryFreeUrl(raw.path);require(!paths.has(url),'DEDICATED_PAGE_REQUIRED');
    require(/^\d+\.\d+\.\d+$/.test(raw.page_version)&&/^[A-Z]{2,8}$/.test(raw.page_family),'VERSION_AND_FAMILY_REQUIRED');
    require(EMIRATES.has(raw.property_destination)&&SEGMENTS.has(raw.property_segment),'PROPERTY_CONTEXT_REQUIRED');
    require(['buy','rent','sell','let','research'].includes(raw.transaction_intent)&&/^[a-z]{2}$/.test(raw.language),'INTENT_LANGUAGE_REQUIRED');
    require(Array.isArray(raw.ctas)&&raw.ctas.length>0,'CTA_REGISTRY_REQUIRED');const ctas=new Map();
    for(const cta of raw.ctas){
      require(exactKeys(cta,['cta_id','cta_type','cta_position','form_id','destination_key']),'UNKNOWN_CTA_FIELD');
      require(code(cta.cta_id)&&cta.cta_id.startsWith('bsre-')&&!ctas.has(cta.cta_id),'STABLE_UNIQUE_CTA_REQUIRED');
      require(['phone','whatsapp','email','form','link','brochure','floorplan','viewing','calculator','comparison'].includes(cta.cta_type),'CTA_TYPE_INVALID');
      require(['header','body','footer','sticky'].includes(cta.cta_position)&&code(cta.destination_key),'CTA_POSITION_DESTINATION_INVALID');
      require(cta.form_id===null||code(cta.form_id),'FORM_ID_INVALID');ctas.set(cta.cta_id,freeze(cta));
    }
    const {ctas:ignored,path,...context}=raw;
    byKey.set(raw.campaign_key,{context:freeze(context),url,ctas});pages.add(raw.landing_page_id);paths.add(url);
  }
  // Do not expose mutable registry Maps to callers.
  return Object.freeze({resolve(campaignKey){const row=byKey.get(campaignKey);return row?{
    context:freeze(row.context),url:row.url,ctas:new Map([...row.ctas].map(([k,v])=>[k,freeze(v)]))}:null;}});
}

export function permissionAllowed(consent,purpose,now=Date.now()){
  if(!exactKeys(consent,['verified','server_eligible','expires_at','analytics','advertising','ad_user_data','personalization','qa','admin']))return false;
  const flags=['verified','server_eligible','analytics','advertising','ad_user_data','personalization','qa','admin'];
  if(flags.some(flag=>typeof consent[flag]!=='boolean'))return false;
  const expiry=typeof consent.expires_at==='string'?Date.parse(consent.expires_at):NaN;
  return Number.isFinite(expiry)&&expiry>now&&consent.verified&&consent.server_eligible&&!consent.qa&&!consent.admin&&
    consent.personalization===false&&(purpose==='analytics'?consent.analytics:purpose==='advertising'&&consent.advertising);
}

export function captureClickIds(values,consent,now=Date.now()){
  require(exactKeys(values,['gclid','gbraid','wbraid']),'UNSUPPORTED_CLICK_IDENTIFIER');
  if(!permissionAllowed(consent,'advertising',now))return {};
  const output={};
  for(const [key,value] of Object.entries(values)){
    // Local conservative guard, not a claim about every Google platform's maximum length.
    require(typeof value==='string'&&/^[A-Za-z0-9_-]{1,512}$/.test(value),'UNSUPPORTED_OR_OVERSIZED_CLICK_IDENTIFIER');
    output[key]=value; // No lowercasing, trimming, truncation or reconstruction.
  }
  return output;
}

export function normalizeEvent(raw,registry){
  require(exactKeys(raw,['event','schema_version','campaign_key','landing_page_id','page_version','cta_id','navigation_id',
    'internal_event_id','receipt','evidence','requested_url','error_category']),'UNKNOWN_EVENT_FIELD');
  require(raw.schema_version===1&&id(raw.internal_event_id),'VERSION_AND_INTERNAL_EVENT_ID_REQUIRED');
  const page=registry.resolve(raw.campaign_key);require(page,'CAMPAIGN_NOT_REGISTERED');
  require(raw.landing_page_id===page.context.landing_page_id&&raw.page_version===page.context.page_version,'CONTEXT_MISMATCH');
  if(raw.requested_url!==undefined)require(queryFreeUrl(raw.requested_url)===page.url,'PAGE_URL_MISMATCH');
  let event=['bsre_lead_accepted','form_submit'].includes(raw.event)?'form_accepted':raw.event;
  require(BROWSER_EVENTS.has(event)||Object.hasOwn(EVIDENCE_SOURCES,event),'UNSUPPORTED_EVENT');
  let cta=null;if(raw.cta_id!==undefined){cta=page.ctas.get(raw.cta_id);require(cta,'CTA_NOT_REGISTERED');}
  if(['cta_click',...Object.values(SPECIAL_CTA)].includes(event)){
    require(cta,'CTA_REQUIRED');const special=SPECIAL_CTA[cta.cta_type];
    if(event==='cta_click'&&special)event=special;
    if(Object.values(SPECIAL_CTA).includes(event))require(event===special,'CTA_EVENT_TYPE_MISMATCH');
  }
  if(event==='page_view')require(id(raw.navigation_id),'NAVIGATION_ID_REQUIRED');
  if(event==='form_error')require(['required','format','permission','rate_limit','server_unavailable'].includes(raw.error_category),'SANITIZED_ERROR_REQUIRED');
  if(Object.hasOwn(EVIDENCE_SOURCES,event)){
    require(exactKeys(raw.evidence,['source','verified','reference'])&&raw.evidence.verified===true&&id(raw.evidence.reference)&&
      EVIDENCE_SOURCES[event].includes(raw.evidence.source),'AUTHORITATIVE_OUTCOME_EVIDENCE_REQUIRED');
  }
  if(event==='form_accepted'){
    const r=raw.receipt;
    require(exactKeys(r,['accepted','durable','lead_id','event_id','original_analytics','original_advertising','original_ad_user_data'])&&
      r.accepted===true&&r.durable===true&&id(r.lead_id)&&r.event_id===raw.internal_event_id&&
      typeof r.original_analytics==='boolean'&&typeof r.original_advertising==='boolean'&&typeof r.original_ad_user_data==='boolean','DURABLE_RECEIPT_REQUIRED');
  }else require(raw.receipt===undefined,'RECEIPT_EVENT_MISMATCH');
  return {event,internal_event_id:raw.internal_event_id,navigation_id:raw.navigation_id||null,
    parameters:{...page.context,page_location:page.url,...(cta||{}),...(event==='form_error'?{error_category:raw.error_category}:{})},
    original_permissions:raw.receipt?{analytics:raw.receipt.original_analytics,advertising:raw.receipt.original_advertising,
      ad_user_data:raw.receipt.original_ad_user_data}:null};
}

export class PrototypeLedger{
  #records=new Map();
  reserve(destination,event,identity,payload){
    return this.reserveBatch([{destination,event,identity,payload}])[0];
  }
  reserveBatch(candidates){
    const staged=new Map(this.#records), statuses=[];
    for(const {destination,event,identity,payload} of candidates){
      require(id(identity),'DEDUPE_ID_INVALID');const key=`${destination}:${event}:${identity}`;
      const digest=createHash('sha256').update(JSON.stringify(payload)).digest('hex');const previous=staged.get(key);
      if(previous){require(previous===digest,'SAME_ID_CHANGED_PAYLOAD_CONFLICT');statuses.push('duplicate_suppressed');}
      else{staged.set(key,digest);statuses.push('prepared_only_not_delivered');}
    }
    this.#records=staged;return statuses;
  }
}

export function prepareDestinations(raw,{registry,consent,mappings={},ledger,now=Date.now()}){
  require(ledger instanceof PrototypeLedger,'IDEMPOTENCY_LEDGER_REQUIRED');
  const normalized=normalizeEvent(raw,registry), output=[], withheld=[], candidates=[];
  const permitted=purpose=>permissionAllowed(consent,purpose,now)&&(!normalized.original_permissions||normalized.original_permissions[purpose]===true);
  if(OFFLINE_EVENTS.has(normalized.event))return {normalized_event:normalized.event,output,withheld:['REVIEWED_OFFLINE_ADAPTER_REQUIRED'],network_calls:0};
  const businessId=normalized.event==='page_view'?normalized.navigation_id:normalized.internal_event_id;
  if(permitted('analytics')){
    const mapping=mappings.ga4;
    require(mapping?.approved===true&&/^G-[A-Z0-9]{8,15}$/.test(mapping.measurement_id)&&id(mapping.evidence_ref)&&
      mapping.producer==='single_reviewed_web_producer','VERIFIED_GA4_MAPPING_REQUIRED');
    const payload={event_name:normalized.event==='form_accepted'?'generate_lead':normalized.event,parameters:normalized.parameters};
    output.push({destination:'ga4',payload});candidates.push({destination:mapping.measurement_id,event:normalized.event,identity:businessId,payload});
  }else withheld.push('ANALYTICS_NOT_PERMITTED');
  if(normalized.event==='form_accepted'&&permitted('advertising')&&consent.ad_user_data===true&&normalized.original_permissions.ad_user_data===true){
    const mapping=mappings.ads;
    require(mapping?.approved===true&&/^AW-\d{6,15}\/[A-Za-z0-9_-]{5,100}$/.test(mapping.send_to)&&id(mapping.evidence_ref)&&
      mapping.route==='native_web_only'&&mapping.supported_dedup_field==='transaction_id'&&mapping.secondary===true,
      'VERIFIED_ADS_ROUTE_AND_SUPPORTED_DEDUP_REQUIRED');
    require(normalized.internal_event_id.length<=64,'ADS_TRANSACTION_ID_OVERSIZED');
    // A transmitted opaque ID must not accidentally be a phone/email/free-text value.
    // Existing producers need reviewed compatibility; never rewrite an ID silently.
    require(/^bsre-event-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(normalized.internal_event_id),
      'OPAQUE_ADS_TRANSACTION_ID_REQUIRED');
    const payload={event_name:'conversion',send_to:mapping.send_to,transaction_id:normalized.internal_event_id};
    output.push({destination:'ads',payload});candidates.push({destination:mapping.send_to,event:normalized.event,identity:businessId,payload});
  }else withheld.push('ADS_NOT_PERMITTED_OR_EVENT_DIAGNOSTIC');
  // Validate every destination before atomically reserving this simulation's candidates.
  const statuses=ledger.reserveBatch(candidates);output.forEach((item,index)=>{item.status=statuses[index];});
  return {normalized_event:normalized.event,output,withheld,network_calls:0};
}
