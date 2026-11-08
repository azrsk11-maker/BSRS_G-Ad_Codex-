/** Offline report calculation only. No imports from live systems, writes or inferred finance policy. */
const UNKNOWN='UNKNOWN_SOURCE', SCALE=1000000;
const ID=/^[a-zA-Z][a-zA-Z0-9:_-]{0,100}$/;
const requiredPolicy={currency:'AED',timezone:'Asia/Dubai',commission_basis:'gross_cash_including_vat',
  refunds_basis:'net_of_vat',cost_basis:'separate_not_already_netted',media_basis:'actual_ads_cost_excluding_vat',
  allocation_model:'explicit_transaction_weights_ppm'};
const require=(condition,code)=>{if(!condition)throw new Error(code);};
const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&Object.keys(o).every(k=>keys.includes(k));
const stamp=value=>{
  require(typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value)),'TIMEZONE_AWARE_TIMESTAMP_REQUIRED');
  const parsed=Date.parse(value),offset=value.endsWith('Z')?0:(value.at(-6)==='-'?-1:1)*(Number(value.slice(-5,-3))*60+Number(value.slice(-2)));
  require(Math.abs(offset)<=14*60&&new Date(parsed+offset*60000).toISOString().slice(0,19)===value.slice(0,19),'INVALID_CALENDAR_DATE');
  return parsed;
};
const campaign=value=>{require(value===null||/^BSRE-C\d{4}$/.test(value),'CAMPAIGN_OR_EXPLICIT_UNKNOWN_REQUIRED');return value??UNKNOWN;};
function attribution(value,sourceClass=value===null?'unknown':'ads'){
  campaign(value);require(['ads','other','unknown'].includes(sourceClass),'SOURCE_CLASS_REQUIRED');
  require(sourceClass==='ads'||value===null,'NON_ADS_CAMPAIGN_CONFLICT');
  return sourceClass==='other'?'OTHER_SOURCE':sourceClass==='unknown'?UNKNOWN:value??'ADS_UNMAPPED';
}
const canonical=value=>JSON.stringify(value,(_,v)=>v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).sort(([a],[b])=>a.localeCompare(b))):v);
const amount=value=>{require(Number.isSafeInteger(value)&&value>=0&&value<=1e12,'NONNEGATIVE_MINOR_UNITS_REQUIRED');return value;};
const add=(a,b)=>{const sum=a+b;require(Number.isSafeInteger(sum),'AGGREGATE_OVERFLOW');return sum;};
function verified(row){require(row.verified===true&&ID.test(row.source_ref||''),'VERIFIED_SOURCE_REQUIRED');}
function unique(rows,key){
  const map=new Map();for(const row of rows){const k=key(row);const previous=map.get(k);
    if(previous)require(canonical(previous)===canonical(row),'DUPLICATE_ID_CONFLICT');else map.set(k,row);}
  return [...map.values()];
}
function allocate(value,weights){
  const rows=weights.map(({campaign_key,source_class,weight_ppm})=>{const product=BigInt(value)*BigInt(weight_ppm);
    return {key:attribution(campaign_key,source_class),amount:Number(product/BigInt(SCALE)),remainder:product%BigInt(SCALE)};});
  let rest=value-rows.reduce((s,r)=>s+r.amount,0);
  const order=[...rows].sort((a,b)=>{const aa=a.remainder<0n?-a.remainder:a.remainder,bb=b.remainder<0n?-b.remainder:b.remainder;
    return aa===bb?a.key.localeCompare(b.key):aa>bb?-1:1;});
  for(let i=0;rest!==0;i++){const delta=rest>0?1:-1;order[i%order.length].amount+=delta;rest-=delta;}
  return rows;
}

export function commercialReport(input,policy){
  const blockers=[];
  if(policy?.approved!==true||!ID.test(policy?.approval_ref||''))blockers.push('FINANCE_POLICY_APPROVAL_REQUIRED');
  for(const [key,value] of Object.entries(requiredPolicy))if(policy?.[key]!==value)blockers.push(`FINANCE_POLICY_${key.toUpperCase()}_REQUIRED`);
  if(input?.verified_export!==true||!ID.test(input?.source_ref||''))blockers.push('VERIFIED_SANITIZED_EXPORT_REQUIRED');
  for(const key of ['spend','transactions','collections','qualifications','opportunities'])if(input?.complete?.[key]!==true)blockers.push(`COMPLETE_${key.toUpperCase()}_SOURCE_REQUIRED`);
  if(blockers.length)return {status:'BLOCKED',blockers,metrics:null,network_calls:0,production_writes:0};
  require(exact(input,['verified_export','source_ref','complete','from','to','spend','transactions','collections','qualifications','opportunities']),'UNKNOWN_INPUT_FIELD');
  const from=stamp(input.from),to=stamp(input.to);require(from<to,'VALID_REPORT_WINDOW_REQUIRED');
  require([from,to].every(t=>(t+4*3600000)%86400000===0),'DUBAI_DAY_BOUNDARIES_REQUIRED_FOR_DAILY_SPEND');
  const inWindow=value=>{const date=stamp(value);return date>=from&&date<to;};
  for(const name of ['spend','transactions','collections','qualifications','opportunities'])require(Array.isArray(input[name])&&input[name].length<=10000,'BOUNDED_SOURCE_ROWS_REQUIRED');
  const rows=new Map();
  const get=key=>{if(!rows.has(key))rows.set(key,{campaign_key:key,media_spend_minor:0,first_ever_qualified_people:0,opportunities:0,
    allocated_collected_net_revenue_minor:0,allocated_contribution_before_acquisition_minor:0,allocated_nonmedia_acquisition_minor:0,
    allocated_transaction_weight_in_window_ppm:0,allocated_cash_receipt_transaction_weight_ppm:0});return rows.get(key);};
  const transactionMap=new Map();
  const transactions=unique(input.transactions,row=>{require(ID.test(row.transaction_ref||''),'TRANSACTION_ID_REQUIRED');return row.transaction_ref;});
  for(const row of transactions){
    require(exact(row,['transaction_ref','closed_at','allocations','verified','source_ref']),'UNKNOWN_TRANSACTION_FIELD');verified(row);stamp(row.closed_at);
    require(Array.isArray(row.allocations)&&row.allocations.length>0,'TRANSACTION_ALLOCATION_REQUIRED');const seen=new Set();let sum=0;
    for(const weight of row.allocations){require(exact(weight,['campaign_key','source_class','weight_ppm']),'UNKNOWN_ALLOCATION_FIELD');const key=attribution(weight.campaign_key,weight.source_class);
      require(!seen.has(key)&&Number.isInteger(weight.weight_ppm)&&weight.weight_ppm>0&&weight.weight_ppm<=SCALE,'ALLOCATION_WEIGHT_INVALID');seen.add(key);sum+=weight.weight_ppm;}
    require(sum===SCALE,'ALLOCATION_MUST_SUM_TO_ONE');transactionMap.set(row.transaction_ref,row);
    if(inWindow(row.closed_at))for(const w of row.allocations)get(attribution(w.campaign_key,w.source_class)).allocated_transaction_weight_in_window_ppm+=w.weight_ppm;
  }
  for(const row of unique(input.spend,row=>`${attribution(row.campaign_key,'ads')}:${row.date}`)){
    require(exact(row,['campaign_key','date','amount_minor','verified','source_ref']),'UNKNOWN_SPEND_FIELD');verified(row);
    require(typeof row.date==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(row.date),'DUBAI_SPEND_DATE_REQUIRED');
    const at=`${row.date}T00:00:00+04:00`;require(new Date(stamp(at)+4*3600000).toISOString().slice(0,10)===row.date,'INVALID_CALENDAR_DATE');
    const minor=amount(row.amount_minor);if(inWindow(at)){const target=get(attribution(row.campaign_key,'ads'));target.media_spend_minor=add(target.media_spend_minor,minor);}
  }
  const collectedTransactions=new Set();let collectedNet=0,contribution=0,nonmedia=0;
  for(const row of unique(input.collections,row=>{require(ID.test(row.record_id||''),'COLLECTION_RECORD_ID_REQUIRED');return row.record_id;})){
    require(exact(row,['record_id','transaction_ref','collected_at','gross_commission_minor','vat_minor','refund_minor','pass_through_minor',
      'agent_payout_minor','referral_payout_minor','direct_cost_minor','nonmedia_acquisition_minor','verified','source_ref']),'UNKNOWN_COLLECTION_FIELD');verified(row);
    const t=transactionMap.get(row.transaction_ref);require(t,'COLLECTION_TRANSACTION_MISSING');
    for(const key of ['gross_commission_minor','vat_minor','refund_minor','pass_through_minor','agent_payout_minor','referral_payout_minor','direct_cost_minor','nonmedia_acquisition_minor'])amount(row[key]);
    require(row.vat_minor<=row.gross_commission_minor,'VAT_EXCEEDS_GROSS_COMMISSION');
    if(!inWindow(row.collected_at))continue;
    const net=row.gross_commission_minor-row.vat_minor-row.refund_minor-row.pass_through_minor;
    const before=net-row.agent_payout_minor-row.referral_payout_minor-row.direct_cost_minor;
    collectedNet=add(collectedNet,net);contribution=add(contribution,before);nonmedia=add(nonmedia,row.nonmedia_acquisition_minor);
    for(const [value,field] of [[net,'allocated_collected_net_revenue_minor'],[before,'allocated_contribution_before_acquisition_minor'],
      [row.nonmedia_acquisition_minor,'allocated_nonmedia_acquisition_minor']])for(const allocation of allocate(value,t.allocations)){
        const target=get(allocation.key);target[field]=add(target[field],allocation.amount);
      }
    if(row.gross_commission_minor>0)collectedTransactions.add(row.transaction_ref);
  }
  for(const ref of collectedTransactions)for(const w of transactionMap.get(ref).allocations)get(attribution(w.campaign_key,w.source_class)).allocated_cash_receipt_transaction_weight_ppm+=w.weight_ppm;
  const persons=new Map(),uncertainPeople=new Set(),earliestVerified=new Map();let unresolved=0,notFirst=0;
  for(const row of unique(input.qualifications,row=>{require(ID.test(row.record_id||''),'QUALIFICATION_RECORD_ID_REQUIRED');return row.record_id;})){
    require(exact(row,['record_id','person_ref','qualified_at','campaign_key','source_class','first_ever_confirmed','history_verified','verified','source_ref']),'UNKNOWN_QUALIFICATION_FIELD');verified(row);
    require(ID.test(row.person_ref||'')&&typeof row.first_ever_confirmed==='boolean'&&typeof row.history_verified==='boolean','QUALIFICATION_HISTORY_REQUIRED');
    const at=stamp(row.qualified_at),sourceKey=attribution(row.campaign_key,row.source_class);
    if(!row.history_verified){unresolved++;uncertainPeople.add(row.person_ref);continue;}
    earliestVerified.set(row.person_ref,Math.min(earliestVerified.get(row.person_ref)??Infinity,at));
    if(!row.first_ever_confirmed){notFirst++;continue;}
    const previous=persons.get(row.person_ref);if(previous)require(stamp(previous.qualified_at)===at&&attribution(previous.campaign_key,previous.source_class)===sourceKey,'FIRST_QUALIFICATION_CONFLICT');
    else persons.set(row.person_ref,row);
  }
  for(const row of persons.values()){
    require(stamp(row.qualified_at)===earliestVerified.get(row.person_ref),'EARLIER_QUALIFICATION_CONTRADICTS_FIRST');
    if(!uncertainPeople.has(row.person_ref)&&inWindow(row.qualified_at))get(attribution(row.campaign_key,row.source_class)).first_ever_qualified_people++;
  }
  for(const row of unique(input.opportunities,row=>{require(ID.test(row.opportunity_ref||''),'OPPORTUNITY_ID_REQUIRED');return row.opportunity_ref;})){
    require(exact(row,['opportunity_ref','person_ref','created_at','campaign_key','source_class','verified','source_ref']),'UNKNOWN_OPPORTUNITY_FIELD');verified(row);
    require(ID.test(row.person_ref||''),'PERSON_REFERENCE_REQUIRED');const key=attribution(row.campaign_key,row.source_class);if(inWindow(row.created_at))get(key).opportunities++;
  }
  const campaigns=[...rows.values()].sort((a,b)=>a.campaign_key.localeCompare(b.campaign_key));
  const qualificationBySource={ads:0,other:0,unknown:0};
  for(const row of campaigns){row.post_acquisition_contribution_minor=add(add(row.allocated_contribution_before_acquisition_minor,-row.allocated_nonmedia_acquisition_minor),-row.media_spend_minor);
    const source=row.campaign_key==='OTHER_SOURCE'?'other':row.campaign_key===UNKNOWN?'unknown':'ads';
    qualificationBySource[source]+=row.first_ever_qualified_people;
    row.observed_period_spend_per_first_qualification_aed=source==='ads'&&row.first_ever_qualified_people?row.media_spend_minor/100/row.first_ever_qualified_people:null;}
  const totalMedia=campaigns.reduce((sum,row)=>add(sum,row.media_spend_minor),0);
  return {status:'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER',source_ref:input.source_ref,policy_approval_ref:policy.approval_ref,
    window:{from:input.from,to:input.to,end_exclusive:true,timezone:'Asia/Dubai'},currency:'AED',money_unit:'minor_units',campaigns,
    totals:{media_spend_minor:totalMedia,collected_net_revenue_minor:collectedNet,
      contribution_before_acquisition_minor:contribution,nonmedia_acquisition_minor:nonmedia,
      post_acquisition_contribution_minor:add(add(contribution,-nonmedia),-totalMedia),
      first_ever_qualified_people_by_source:qualificationBySource,
      observed_period_ads_spend_per_first_qualification_aed:qualificationBySource.ads?totalMedia/100/qualificationBySource.ads:null,
      transactions_closed_in_window:transactions.filter(t=>inWindow(t.closed_at)).length,
      transactions_with_cash_receipts_in_window:collectedTransactions.size,first_ever_qualified_people:campaigns.reduce((s,r)=>s+r.first_ever_qualified_people,0),
      opportunities:campaigns.reduce((s,r)=>s+r.opportunities,0)},
    exclusions:{unresolved_qualification_history:unresolved,people_held_for_unresolved_history:uncertainPeople.size,not_first_qualification:notFirst},
    metric_limits:['Period spend divided by period first qualifications is descriptive, not cohort CPQL.',
      'Cash-receipt transaction counts are not new collected customers and may recur in another installment period.',
      'Other source, genuinely unknown source and Ads with missing campaign mapping remain separate rows. Zero denominators return null. No pipeline value, property price, CAC or ROAS is inferred.'],
    network_calls:0,production_writes:0};
}
