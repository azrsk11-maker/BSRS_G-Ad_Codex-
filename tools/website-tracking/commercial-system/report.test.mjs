import test from 'node:test';import assert from 'node:assert/strict';import {commercialReport} from './report.mjs';
const policy={approved:true,approval_ref:'SYNTHETIC-DECISION',currency:'AED',timezone:'Asia/Dubai',commission_basis:'gross_cash_including_vat',
  refunds_basis:'net_of_vat',cost_basis:'separate_not_already_netted',media_basis:'actual_ads_cost_excluding_vat',allocation_model:'explicit_transaction_weights_ppm'};
const provenance={verified:true,source_ref:'SYNTHETIC-FIXTURE'};
function fixture(){return {verified_export:true,source_ref:'SYNTHETIC-FIXTURE',complete:{spend:true,transactions:true,collections:true,qualifications:true,opportunities:true},
  from:'2026-11-01T00:00:00+04:00',to:'2026-12-01T00:00:00+04:00',
  spend:[{campaign_key:'BSRE-C0001',date:'2026-11-07',amount_minor:10000,...provenance}],
  transactions:[{transaction_ref:'synthetic-transaction-1',closed_at:'2026-11-06T11:00:00+04:00',allocations:[
    {campaign_key:'BSRE-C0001',weight_ppm:500000},{campaign_key:'BSRE-C0002',weight_ppm:500000}],...provenance}],
  collections:[{record_id:'synthetic-collection-1',transaction_ref:'synthetic-transaction-1',collected_at:'2026-11-07T12:00:00+04:00',
    gross_commission_minor:105000,vat_minor:5000,refund_minor:1000,pass_through_minor:1000,agent_payout_minor:40000,
    referral_payout_minor:5000,direct_cost_minor:2000,nonmedia_acquisition_minor:1000,...provenance}],
  qualifications:[{record_id:'synthetic-qual-1',person_ref:'synthetic-person-1',qualified_at:'2026-11-02T12:00:00+04:00',campaign_key:'BSRE-C0001',first_ever_confirmed:true,history_verified:true,...provenance}],
  opportunities:[{opportunity_ref:'synthetic-opp-1',person_ref:'synthetic-person-1',created_at:'2026-11-02T12:00:00+04:00',campaign_key:'BSRE-C0001',...provenance}]};}
test('missing approved finance rules and incomplete sources block, never become zero revenue',()=>{
  assert.equal(commercialReport(fixture(),{}).metrics,null);const f=fixture();f.complete.collections=false;
  assert.equal(commercialReport(f,policy).status,'BLOCKED');
});
test('array identifiers cannot bypass source verification, attribution or deduplication',()=>{
  const f=fixture();
  assert.equal(commercialReport(f,{...policy,approval_ref:[policy.approval_ref]}).status,'BLOCKED');
  assert.equal(commercialReport({...f,source_ref:[f.source_ref]},policy).status,'BLOCKED');
  for(const [collection,field,error] of [
    ['spend','source_ref',/VERIFIED_SOURCE_REQUIRED/],
    ['spend','campaign_key',/CAMPAIGN_OR_EXPLICIT_UNKNOWN_REQUIRED/],
    ['collections','record_id',/COLLECTION_RECORD_ID_REQUIRED/],
    ['qualifications','person_ref',/QUALIFICATION_HISTORY_REQUIRED/],
    ['opportunities','opportunity_ref',/OPPORTUNITY_ID_REQUIRED/],
    ['transactions','transaction_ref',/TRANSACTION_ID_REQUIRED/],
  ]){
    const input=fixture();
    const row=input[collection][0];
    row[field]=[row[field]];
    assert.throws(()=>commercialReport(input,policy),error);
  }
});
test('commission excludes explicit VAT refund pass-through and separately accounted costs',()=>{
  const r=commercialReport(fixture(),policy);assert.equal(r.totals.collected_net_revenue_minor,98000);
  assert.equal(r.totals.contribution_before_acquisition_minor,51000);
  assert.equal(r.totals.post_acquisition_contribution_minor,40000);
  assert.equal(r.campaigns.reduce((s,c)=>s+c.post_acquisition_contribution_minor,0),40000);
  assert.equal(r.campaigns.reduce((s,c)=>s+c.allocated_collected_net_revenue_minor,0),98000);
  assert.equal(r.totals.transactions_closed_in_window,1);assert.equal(r.totals.transactions_with_cash_receipts_in_window,1);
});
test('repeated records and same buyer/seller transaction never double-count',()=>{
  const f=fixture();for(const name of ['spend','transactions','collections','opportunities'])f[name].push(structuredClone(f[name][0]));
  f.qualifications.push({...f.qualifications[0],record_id:'synthetic-qual-2'});
  const r=commercialReport(f,policy);assert.equal(r.totals.media_spend_minor,10000);assert.equal(r.totals.first_ever_qualified_people,1);
  assert.equal(r.totals.transactions_closed_in_window,1);assert.equal(r.totals.opportunities,1);
});
test('different spend amounts for same campaign/day conflict instead of add',()=>{
  const f=fixture();f.spend.push({...f.spend[0],amount_minor:9000});assert.throws(()=>commercialReport(f,policy),/DUPLICATE_ID_CONFLICT/);
});
test('allocations over one or duplicate campaign weight reject',()=>{
  const f=fixture();f.transactions[0].allocations[0].weight_ppm=600000;assert.throws(()=>commercialReport(f,policy),/SUM_TO_ONE/);
});
test('unknown source separate, uncertain history excluded, opportunities not person counts',()=>{
  const f=fixture();f.qualifications[0].campaign_key=null;f.qualifications.push({...f.qualifications[0],record_id:'synthetic-unknown-qual',person_ref:'synthetic-person-2',history_verified:false});
  f.opportunities.push({...f.opportunities[0],opportunity_ref:'synthetic-opp-2'});const r=commercialReport(f,policy);
  assert.equal(r.campaigns.find(c=>c.campaign_key==='UNKNOWN_SOURCE').first_ever_qualified_people,1);
  assert.equal(r.exclusions.unresolved_qualification_history,1);assert.equal(r.totals.opportunities,2);assert.equal(r.totals.first_ever_qualified_people,1);
});
test('property price cannot be introduced as brokerage revenue',()=>{
  const f=fixture();f.collections[0].property_price=100000000;assert.throws(()=>commercialReport(f,policy),/UNKNOWN_COLLECTION_FIELD/);
});
test('aware timestamps and valid Dubai calendar dates required',()=>{
  const f=fixture();f.from='2026-11-01T00:00:00';assert.throws(()=>commercialReport(f,policy),/TIMEZONE_AWARE/);
  const g=fixture();g.spend[0].date='2026-02-30';assert.throws(()=>commercialReport(g,policy),/INVALID_CALENDAR_DATE/);
  const h=fixture();h.collections[0].collected_at='2026-02-30T12:00:00+04:00';assert.throws(()=>commercialReport(h,policy),/INVALID_CALENDAR_DATE/);
  const partial=fixture();partial.from='2026-11-01T10:00:00+04:00';assert.throws(()=>commercialReport(partial,policy),/DUBAI_DAY_BOUNDARIES/);
});
test('installments count one cash-receipt transaction; contract date separate',()=>{
  const f=fixture();f.transactions[0].closed_at='2026-10-01T00:00:00+04:00';f.collections.push({...f.collections[0],record_id:'synthetic-installment-2'});
  const r=commercialReport(f,policy);assert.equal(r.totals.transactions_closed_in_window,0);assert.equal(r.totals.transactions_with_cash_receipts_in_window,1);
});
test('zero denominator is null, cents conserve across weighted allocation',()=>{
  const f=fixture();f.qualifications=[];f.collections[0].gross_commission_minor=105001;
  const r=commercialReport(f,policy);assert.ok(r.campaigns.every(c=>c.observed_period_spend_per_first_qualification_aed===null));
  assert.equal(r.campaigns.reduce((s,c)=>s+c.allocated_collected_net_revenue_minor,0),98001);
});
test('prior or inconsistent first-ever qualification cannot inflate counts',()=>{
  const f=fixture();f.qualifications[0].first_ever_confirmed=false;assert.equal(commercialReport(f,policy).totals.first_ever_qualified_people,0);
  const g=fixture();g.qualifications.push({...g.qualifications[0],record_id:'synthetic-qual-2',qualified_at:'2026-11-03T00:00:00+04:00'});
  assert.throws(()=>commercialReport(g,policy),/FIRST_QUALIFICATION_CONFLICT/);
  const h=fixture();h.qualifications.push({...h.qualifications[0],record_id:'synthetic-uncertain',history_verified:false});
  assert.equal(commercialReport(h,policy).totals.first_ever_qualified_people,0);
});
test('same first qualification instant with different offset is one person',()=>{
  const f=fixture();f.qualifications.push({...f.qualifications[0],record_id:'synthetic-qual-utc',qualified_at:'2026-11-02T08:00:00Z'});
  assert.equal(commercialReport(f,policy).totals.first_ever_qualified_people,1);
});
test('refund-only negative cash contribution conserves across allocations without a new collection count',()=>{
  const f=fixture();f.collections[0]={...f.collections[0],gross_commission_minor:0,vat_minor:0,refund_minor:1001,pass_through_minor:0,
    agent_payout_minor:0,referral_payout_minor:0,direct_cost_minor:0,nonmedia_acquisition_minor:0};
  const r=commercialReport(f,policy);assert.equal(r.totals.collected_net_revenue_minor,-1001);
  assert.equal(r.campaigns.reduce((s,c)=>s+c.allocated_collected_net_revenue_minor,0),-1001);assert.equal(r.totals.transactions_with_cash_receipts_in_window,0);
});
test('earlier verified repeat qualification disproves later claimed first-ever qualification',()=>{
  const f=fixture();f.qualifications.push({...f.qualifications[0],record_id:'synthetic-prior-repeat',qualified_at:'2026-10-01T12:00:00+04:00',first_ever_confirmed:false});
  assert.throws(()=>commercialReport(f,policy),/EARLIER_QUALIFICATION_CONTRADICTS_FIRST/);
  const valid=fixture();valid.qualifications.push({...valid.qualifications[0],record_id:'synthetic-later-repeat',qualified_at:'2026-11-03T12:00:00+04:00',first_ever_confirmed:false});
  assert.equal(commercialReport(valid,policy).totals.first_ever_qualified_people,1);
});
test('final contribution arithmetic fails rather than returning an unsafe number',()=>{
  const f=fixture();f.transactions[0].allocations=[{campaign_key:'BSRE-C0001',weight_ppm:1000000}];
  f.collections=Array.from({length:1800},(_,i)=>({...f.collections[0],record_id:`synthetic-overflow-${i}`,gross_commission_minor:0,vat_minor:0,
    refund_minor:1e12,pass_through_minor:1e12,agent_payout_minor:1e12,referral_payout_minor:1e12,direct_cost_minor:1e12,nonmedia_acquisition_minor:1e12}));
  assert.throws(()=>commercialReport(f,policy),/AGGREGATE_OVERFLOW/);
});
test('other-source and unknown qualifications stay distinct from unmapped Ads',()=>{
  const f=fixture();f.qualifications=[
    {...f.qualifications[0],record_id:'synthetic-other',person_ref:'synthetic-other-person',campaign_key:null,source_class:'other'},
    {...f.qualifications[0],record_id:'synthetic-unknown',person_ref:'synthetic-unknown-person',campaign_key:null,source_class:'unknown'},
    {...f.qualifications[0],record_id:'synthetic-unmapped-ad',person_ref:'synthetic-unmapped-person',campaign_key:null,source_class:'ads'}];
  f.spend[0].campaign_key=null;
  const r=commercialReport(f,policy);for(const key of ['OTHER_SOURCE','UNKNOWN_SOURCE','ADS_UNMAPPED'])assert.equal(r.campaigns.find(c=>c.campaign_key===key).first_ever_qualified_people,1);
  assert.equal(r.campaigns.find(c=>c.campaign_key==='ADS_UNMAPPED').media_spend_minor,10000);
  assert.equal(r.campaigns.find(c=>c.campaign_key==='ADS_UNMAPPED').observed_period_spend_per_first_qualification_aed,100);
  assert.deepEqual(r.totals.first_ever_qualified_people_by_source,{ads:1,other:1,unknown:1});
  assert.equal(r.totals.observed_period_ads_spend_per_first_qualification_aed,100);
  for(const key of ['OTHER_SOURCE','UNKNOWN_SOURCE'])assert.equal(r.campaigns.find(c=>c.campaign_key===key).observed_period_spend_per_first_qualification_aed,null);
  f.qualifications.pop();assert.equal(commercialReport(f,policy).totals.observed_period_ads_spend_per_first_qualification_aed,null);
  f.qualifications[0].campaign_key='BSRE-C0001';assert.throws(()=>commercialReport(f,policy),/NON_ADS_CAMPAIGN_CONFLICT/);
});
