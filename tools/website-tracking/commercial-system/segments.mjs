/** Offline, explicitly classified segment aggregates. Never authenticates a reviewer. */
import {createHash} from 'node:crypto';

export const COMMERCIAL_SEGMENTS=Object.freeze([
  'residential_purchase','offplan','residential_rental',
  'commercial_purchase','commercial_lease','owner_mandate_acquisition',
]);
const FIELDS=Object.freeze(['media_spend_minor','first_ever_qualified_people','opportunities',
  'allocated_collected_net_revenue_minor','allocated_contribution_before_acquisition_minor',
  'allocated_nonmedia_acquisition_minor','allocated_transaction_weight_in_window_ppm',
  'allocated_cash_receipt_transaction_weight_ppm']);
const ID=/^[a-zA-Z][a-zA-Z0-9:_-]{0,100}$/;
const identifier=value=>typeof value==='string'&&ID.test(value);
const exact=(value,keys)=>value!==null&&typeof value==='object'&&!Array.isArray(value)&&
  Object.keys(value).length===keys.length&&Object.keys(value).every(key=>keys.includes(key));
class SegmentError extends Error{}
const require=(condition,code)=>{if(!condition)throw new SegmentError(code);};
const empty=()=>Object.fromEntries(FIELDS.map(field=>[field,0]));
const add=(left,right)=>{const value=left+right;require(Number.isSafeInteger(value),'SEGMENT_AGGREGATE_OVERFLOW');return value;};

// JSON exports only. Reject getters, toJSON, undefined, sparse arrays and non-JSON
// values rather than letting serialization silently omit review-bound content.
function canonical(value,depth=0){
  require(depth<=32,'SEGMENT_JSON_DEPTH_LIMIT');
  if(value===null||typeof value==='string'||typeof value==='boolean')return JSON.stringify(value);
  if(typeof value==='number'){require(Number.isFinite(value),'SEGMENT_JSON_REQUIRED');return JSON.stringify(value);}
  require(value&&typeof value==='object','SEGMENT_JSON_REQUIRED');
  require(Object.getOwnPropertySymbols(value).length===0,'SEGMENT_JSON_REQUIRED');
  const descriptors=Object.getOwnPropertyDescriptors(value);
  if(Array.isArray(value)){
    require(Object.getPrototypeOf(value)===Array.prototype&&Object.keys(descriptors).length===value.length+1,
      'SEGMENT_JSON_REQUIRED');
    return '['+Array.from({length:value.length},(_,index)=>{
      const descriptor=descriptors[index];require(descriptor&&Object.hasOwn(descriptor,'value'),'SEGMENT_JSON_REQUIRED');
      return canonical(descriptor.value,depth+1);
    }).join(',')+']';
  }
  require(Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null,'SEGMENT_JSON_REQUIRED');
  return '{'+Object.keys(descriptors).sort().map(key=>{
    const descriptor=descriptors[key];require(descriptor.enumerable&&Object.hasOwn(descriptor,'value'),'SEGMENT_JSON_REQUIRED');
    return JSON.stringify(key)+':'+canonical(descriptor.value,depth+1);
  }).join(',')+'}';
}
function digest(domain,value,limit){
  const body=canonical(value);require(Buffer.byteLength(body,'utf8')<=limit,'SEGMENT_INPUT_SIZE_LIMIT');
  return createHash('sha256').update(domain+'\n'+body,'utf8').digest('hex');
}
/** Binding helpers do not approve, authenticate, store or transmit their input. */
export const segmentFinanceInputHash=input=>digest('bsre-segment-finance-input-v1',input,32*1024*1024);
export const segmentClassificationHash=document=>digest('bsre-segment-classification-v1',document,8*1024*1024);

function clock(value){
  require(typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+]00:00)$/.test(value),
    'SEGMENT_EXPLICIT_UTC_CLOCK_REQUIRED');
  const milliseconds=Date.parse(value);
  require(Number.isFinite(milliseconds)&&new Date(milliseconds).toISOString().slice(0,19)===value.slice(0,19),
    'SEGMENT_EXPLICIT_UTC_CLOCK_REQUIRED');
  return BigInt(milliseconds)*1000n+BigInt((/\.(\d+)/.exec(value)?.[1]??'').padEnd(6,'0').slice(3));
}

/** Internal additive journal, populated only by the already validated base calculation. */
export class SegmentUnits{
  constructor(){this.rows=new Map();this.hold=null;}
  add(entity,source,changes){
    if(this.hold)return;
    try{
      const key=canonical(entity);
      if(!this.rows.has(key)){
        require(this.rows.size<100000,'SEGMENT_ENTITY_LIMIT');
        this.rows.set(key,{entity,source,metrics:empty()});
      }
      const unit=this.rows.get(key);require(unit.source===source,'SEGMENT_SOURCE_CONFLICT');
      for(const [field,value] of Object.entries(changes)){
        require(FIELDS.includes(field)&&Number.isSafeInteger(value),'SEGMENT_METRIC_INVALID');
        unit.metrics[field]=add(unit.metrics[field],value);
      }
    }catch(error){this.hold=error instanceof SegmentError?error.message:'SEGMENT_JOURNAL_INVALID';this.rows.clear();}
  }
}

const held=code=>({status:'HELD',holds:[code],segments:null,source_truth_independently_verified:false,
  google_upload_supported:false,network_calls:0,production_writes:0});
export const heldSegmentReport=held;
function finish(metrics,ads,unresolved){
  return {...metrics,post_acquisition_contribution_minor:add(add(metrics.allocated_contribution_before_acquisition_minor,
    -metrics.allocated_nonmedia_acquisition_minor),-metrics.media_spend_minor),
    observed_period_ads_spend_per_first_qualification_aed:!unresolved&&ads.first_ever_qualified_people?
      ads.media_spend_minor/100/ads.first_ever_qualified_people:null};
}
const sourceClass=source=>source==='OTHER_SOURCE'?'other':source==='UNKNOWN_SOURCE'?'unknown':'ads';

export function buildSegmentReport(input,policy,document,now,base,journal){
  try{
    if(journal.hold)return held(journal.hold);
    const approval=policy.segment_classification;
    require(exact(approval,['approved','approval_ref','classification_sha256'])&&approval.approved===true&&
      identifier(approval.approval_ref)&&typeof approval.classification_sha256==='string'&&
      /^[0-9a-f]{64}$/.test(approval.classification_sha256),'SEGMENT_CLASSIFICATION_APPROVAL_REQUIRED');
    require(exact(document,['schema','verified_export','source_ref','finance_source_ref','finance_policy_approval_ref',
      'finance_input_sha256','from','to','reviewed_at_utc','valid_until_utc','rows']),
      'SEGMENT_CLASSIFICATION_FIELDS_INVALID');
    // Check the whole approved document before interpreting its classifications.
    const classificationHash=segmentClassificationHash(document);
    require(classificationHash===approval.classification_sha256,'SEGMENT_CLASSIFICATION_APPROVAL_HASH_MISMATCH');
    require(document.schema==='bsre-commercial-segment-classification-v1'&&document.verified_export===true&&
      identifier(document.source_ref),'SEGMENT_VERIFIED_CLASSIFICATION_EXPORT_REQUIRED');
    const inputHash=segmentFinanceInputHash(input);
    require(document.finance_source_ref===input.source_ref&&document.finance_policy_approval_ref===policy.approval_ref&&
      document.finance_input_sha256===inputHash&&document.from===input.from&&document.to===input.to,
      'SEGMENT_FINANCE_INPUT_BINDING_MISMATCH');
    const evaluated=clock(now),reviewed=clock(document.reviewed_at_utc),expires=clock(document.valid_until_utc);
    require(reviewed<=evaluated&&evaluated<expires,'SEGMENT_CLASSIFICATION_REVIEW_STALE_OR_FUTURE');
    require(Array.isArray(document.rows)&&document.rows.length<=100000,'SEGMENT_CLASSIFICATION_ROWS_REQUIRED');
    const classifications=new Map();
    for(const row of document.rows){
      require(exact(row,['entity','segment','evidence_ref'])&&identifier(row.evidence_ref),
        'SEGMENT_CLASSIFICATION_ROW_INVALID');
      require(row.segment!==null,'SEGMENT_UNKNOWN_CLASSIFICATION');
      require(COMMERCIAL_SEGMENTS.includes(row.segment),'SEGMENT_CLASSIFICATION_VALUE_INVALID');
      const key=canonical(row.entity);
      require(journal.rows.has(key),'SEGMENT_UNKNOWN_OR_OUT_OF_WINDOW_ENTITY');
      if(classifications.has(key))require(canonical(classifications.get(key))===canonical(row),
        'SEGMENT_CLASSIFICATION_CONFLICT');
      else classifications.set(key,row);
    }
    require(classifications.size===journal.rows.size,'SEGMENT_CLASSIFICATION_INCOMPLETE');
    const groups=new Map(COMMERCIAL_SEGMENTS.map(segment=>[segment,new Map()]));
    for(const [key,unit] of journal.rows){
      const sources=groups.get(classifications.get(key).segment);
      if(!sources.has(unit.source))sources.set(unit.source,empty());
      const metrics=sources.get(unit.source);
      for(const field of FIELDS)metrics[field]=add(metrics[field],unit.metrics[field]);
    }
    const unresolved=base.exclusions.people_held_for_unresolved_history>0;
    const segments=[...groups].map(([segment,sources])=>{
      const totals=empty(),byClass={ads:empty(),other:empty(),unknown:empty()};
      for(const [source,metrics] of sources)for(const field of FIELDS){
        totals[field]=add(totals[field],metrics[field]);
        const group=byClass[sourceClass(source)];group[field]=add(group[field],metrics[field]);
      }
      return {segment,...finish(totals,byClass.ads,unresolved),
        by_source_class:Object.fromEntries(Object.entries(byClass).map(([source,metrics])=>
          [source,finish(metrics,source==='ads'?metrics:empty(),unresolved)])),
        by_attribution_source:[...sources].sort(([left],[right])=>left.localeCompare(right)).map(([source,metrics])=>
          ({attribution_source:source,...finish(metrics,sourceClass(source)==='ads'&&source!=='ADS_UNMAPPED'?metrics:empty(),unresolved)}))};
    });
    // Conservation is checked per original attribution row as well as account-wide.
    const sourceTotals=new Map();
    for(const segment of segments)for(const row of segment.by_attribution_source){
      if(!sourceTotals.has(row.attribution_source))sourceTotals.set(row.attribution_source,empty());
      for(const field of FIELDS){const total=sourceTotals.get(row.attribution_source);total[field]=add(total[field],row[field]);}
    }
    for(const row of base.campaigns)for(const field of FIELDS)
      require((sourceTotals.get(row.campaign_key)?.[field]??0)===row[field],'SEGMENT_BASE_CONSERVATION_FAILED');
    require([...sourceTotals.keys()].every(source=>base.campaigns.some(row=>row.campaign_key===source)),
      'SEGMENT_BASE_CONSERVATION_FAILED');
    return {status:'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER',holds:[],segments,
      classification_evidence:{method:'CALLER_ASSERTED_HASH_BOUND_CLASSIFICATION_NOT_AUTHENTICATED',
        classification_approval_ref:approval.approval_ref,finance_policy_approval_ref:policy.approval_ref,
        finance_input_sha256:inputHash,classification_sha256:classificationHash,
        reviewed_at_utc:document.reviewed_at_utc,valid_until_utc:document.valid_until_utc,evaluated_at_utc:now,
        author_independently_verified:false,source_truth_independently_verified:false},
      conservation:{account_and_original_attribution_sources:true,transaction_counts_are_allocated_weights:true},
      metric_limits:['Period spend per first qualification is descriptive, not cohort CPQL or CAC.',
        'Transaction weights split one underlying transaction; segments do not each receive a full transaction.',
        'Whole audited qualification buckets require one evidence-supported segment; mixed or unknown buckets must be held.',
        'Classification approvals and source truth require caller custody and independent review; hashes do not authenticate them.'],
      source_truth_independently_verified:false,google_upload_supported:false,network_calls:0,production_writes:0};
  }catch(error){return held(error instanceof SegmentError?error.message:'SEGMENT_CLASSIFICATION_INPUT_INVALID');}
}
