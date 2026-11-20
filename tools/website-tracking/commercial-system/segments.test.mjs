import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
import {commercialReport,commercialReportBySegment,commercialReportFromHistoryBySegment} from './report.mjs';
import {readQualificationHistory} from './history-bridge.mjs';
import {COMMERCIAL_SEGMENTS,segmentFinanceInputHash,segmentClassificationHash} from './segments.mjs';

const NOW='2026-11-08T12:00:00Z';
const policy={approved:true,approval_ref:'SYNTHETIC-FINANCE-DECISION',currency:'AED',timezone:'Asia/Dubai',
  commission_basis:'gross_cash_including_vat',refunds_basis:'net_of_vat',cost_basis:'separate_not_already_netted',
  media_basis:'actual_ads_cost_excluding_vat',allocation_model:'explicit_transaction_weights_ppm'};
const provenance={verified:true,source_ref:'SYNTHETIC-FIXTURE'};
const mapping=(entity,segment)=>({entity,segment,evidence_ref:'SYNTHETIC-CLASSIFICATION-EVIDENCE'});
function emptyInput(){return {verified_export:true,source_ref:'SYNTHETIC-FINANCE',
  complete:{spend:true,transactions:true,collections:true,qualifications:true,opportunities:true},
  from:'2026-11-01T00:00:00+04:00',to:'2026-12-01T00:00:00+04:00',
  spend:[],transactions:[],collections:[],qualifications:[],opportunities:[]};}
function document(input,rows){return {schema:'bsre-commercial-segment-classification-v1',verified_export:true,
  source_ref:'SYNTHETIC-CLASSIFICATION-EXPORT',finance_source_ref:input.source_ref,
  finance_policy_approval_ref:policy.approval_ref,finance_input_sha256:segmentFinanceInputHash(input),
  from:input.from,to:input.to,reviewed_at_utc:'2026-11-08T11:00:00Z',valid_until_utc:'2026-11-08T13:00:00Z',rows};}
function approved(doc){return {...policy,segment_classification:{approved:true,
  approval_ref:'SYNTHETIC-SEGMENT-DECISION',classification_sha256:segmentClassificationHash(doc)}};}
function run(input,rows){const doc=document(input,rows);return commercialReportBySegment(input,approved(doc),doc,{now_utc:NOW});}
const segment=(report,name)=>report.segment_report.segments.find(row=>row.segment===name);
const baseOnly=report=>{const {segment_report,...base}=report;return base;};
function sixFixture(){
  const input=emptyInput(),rows=[];
  for(const [index,name] of COMMERCIAL_SEGMENTS.entries()){
    const n=index+1,campaign_key=`BSRE-C000${n}`,transaction_ref=`synthetic-transaction-${n}`,person_ref=`synthetic-person-${n}`,
      opportunity_ref=`synthetic-opportunity-${n}`,date='2026-11-07';
    input.spend.push({campaign_key,date,amount_minor:100*n,...provenance});
    input.transactions.push({transaction_ref,closed_at:'2026-11-06T12:00:00+04:00',
      allocations:[{campaign_key,weight_ppm:1000000}],...provenance});
    input.collections.push({record_id:`synthetic-receipt-${n}`,transaction_ref,collected_at:'2026-11-07T12:00:00+04:00',
      gross_commission_minor:11000*n,vat_minor:1000*n,refund_minor:100*n,pass_through_minor:100*n,
      agent_payout_minor:2000*n,referral_payout_minor:500*n,direct_cost_minor:300*n,nonmedia_acquisition_minor:200*n,...provenance});
    input.qualifications.push({record_id:`synthetic-qualification-${n}`,person_ref,qualified_at:'2026-11-02T12:00:00+04:00',
      campaign_key,first_ever_confirmed:true,history_verified:true,...provenance});
    input.opportunities.push({opportunity_ref,person_ref,created_at:'2026-11-02T12:00:00+04:00',campaign_key,...provenance});
    rows.push(mapping({kind:'spend',campaign_key,date},name),
      mapping({kind:'transaction_allocation',transaction_ref,campaign_key,source_class:'ads'},name),
      mapping({kind:'qualification',person_ref,campaign_key,source_class:'ads'},name),
      mapping({kind:'opportunity',opportunity_ref,campaign_key,source_class:'ads'},name));
  }
  return {input,rows};
}

test('six explicit segments calculate independently known economics and conserve unchanged base totals',()=>{
  const {input,rows}=sixFixture(),before=JSON.stringify(input),report=run(input,rows);
  assert.equal(report.segment_report.status,'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER');
  assert.deepEqual(baseOnly(report),commercialReport(input,policy));assert.equal(JSON.stringify(input),before);
  assert.deepEqual(COMMERCIAL_SEGMENTS,['residential_purchase','offplan','residential_rental',
    'commercial_purchase','commercial_lease','owner_mandate_acquisition']);
  for(const [index,name] of COMMERCIAL_SEGMENTS.entries()){
    const n=index+1,row=segment(report,name);
    assert.equal(row.media_spend_minor,100*n);assert.equal(row.allocated_collected_net_revenue_minor,9800*n);
    assert.equal(row.allocated_contribution_before_acquisition_minor,7000*n);
    assert.equal(row.allocated_nonmedia_acquisition_minor,200*n);assert.equal(row.post_acquisition_contribution_minor,6700*n);
    assert.equal(row.first_ever_qualified_people,1);assert.equal(row.opportunities,1);
    assert.equal(row.allocated_transaction_weight_in_window_ppm,1000000);
    assert.equal(row.allocated_cash_receipt_transaction_weight_ppm,1000000);
    assert.equal(row.observed_period_ads_spend_per_first_qualification_aed,n);
  }
  assert.equal(report.totals.media_spend_minor,2100);assert.equal(report.totals.post_acquisition_contribution_minor,140700);
  assert.equal(report.segment_report.source_truth_independently_verified,false);
  assert.equal(report.segment_report.google_upload_supported,false);
});

test('buyer and seller share exact rounding and one transaction without double costs or repeated receipts',()=>{
  const {input,rows}=sixFixture();
  for(const name of ['transactions','collections','qualifications','opportunities'])input[name]=input[name].slice(0,1);
  input.spend=input.spend.slice(0,2);input.spend[1].amount_minor=300;
  input.transactions[0].allocations=[{campaign_key:'BSRE-C0001',weight_ppm:500000},{campaign_key:'BSRE-C0002',weight_ppm:500000}];
  Object.assign(input.collections[0],{gross_commission_minor:105001,vat_minor:5000,refund_minor:1000,pass_through_minor:1000,
    agent_payout_minor:40000,referral_payout_minor:5000,direct_cost_minor:2000,nonmedia_acquisition_minor:1001});
  const classified=[...rows.slice(0,4),mapping({kind:'spend',campaign_key:'BSRE-C0002',date:'2026-11-07'},'owner_mandate_acquisition'),
    mapping({kind:'transaction_allocation',transaction_ref:'synthetic-transaction-1',campaign_key:'BSRE-C0002',source_class:'ads'},'owner_mandate_acquisition')];
  for(const name of ['spend','transactions','collections','opportunities'])input[name].push(structuredClone(input[name][0]));
  input.qualifications.push({...input.qualifications[0],record_id:'synthetic-repeat-same-person'});
  classified.push(structuredClone(classified[0]));
  const report=run(input,classified),buyer=segment(report,'residential_purchase'),seller=segment(report,'owner_mandate_acquisition');
  assert.equal(buyer.allocated_collected_net_revenue_minor,49001);assert.equal(seller.allocated_collected_net_revenue_minor,49000);
  assert.equal(buyer.post_acquisition_contribution_minor,24900);assert.equal(seller.post_acquisition_contribution_minor,24700);
  assert.equal(buyer.first_ever_qualified_people,1);assert.equal(seller.first_ever_qualified_people,0);
  assert.equal(buyer.allocated_transaction_weight_in_window_ppm,500000);assert.equal(seller.allocated_transaction_weight_in_window_ppm,500000);
  assert.equal(buyer.allocated_cash_receipt_transaction_weight_ppm,500000);assert.equal(seller.allocated_cash_receipt_transaction_weight_ppm,500000);
  assert.equal(report.totals.transactions_with_cash_receipts_in_window,1);assert.equal(report.totals.post_acquisition_contribution_minor,49600);
  assert.deepEqual(baseOnly(report),commercialReport(input,policy));
});

test('one campaign can have independently evidenced segments at stable entity and spend-day grain',()=>{
  const {input,rows}=sixFixture();
  for(const name of ['spend','qualifications','opportunities'])for(const row of input[name])row.campaign_key='BSRE-C0001';
  for(const transaction of input.transactions)transaction.allocations[0].campaign_key='BSRE-C0001';
  for(const [index,row] of input.spend.entries())row.date=`2026-11-${String(index+7).padStart(2,'0')}`;
  for(const row of rows){row.entity.campaign_key='BSRE-C0001';
    if(row.entity.kind==='spend')row.entity.date=input.spend[COMMERCIAL_SEGMENTS.indexOf(row.segment)].date;}
  const result=run(input,rows);
  assert.equal(result.campaigns.length,1);assert.equal(result.segment_report.status,'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER');
  for(const [index,name] of COMMERCIAL_SEGMENTS.entries())assert.equal(segment(result,name).post_acquisition_contribution_minor,6700*(index+1));
  assert.deepEqual(baseOnly(result),commercialReport(input,policy));
});

test('other, unknown and unmapped Ads preserve distinct sources within one segment',()=>{
  const input=emptyInput(),rows=[],name='commercial_lease';
  input.spend=[{campaign_key:null,date:'2026-11-07',amount_minor:300,...provenance}];
  rows.push(mapping({kind:'spend',campaign_key:null,date:'2026-11-07'},name));
  for(const source_class of ['ads','other','unknown']){
    const person_ref=`synthetic-${source_class}`;
    input.qualifications.push({record_id:`synthetic-qualification-${source_class}`,person_ref,campaign_key:null,source_class,
      qualified_at:'2026-11-02T12:00:00+04:00',first_ever_confirmed:true,history_verified:true,...provenance});
    rows.push(mapping({kind:'qualification',person_ref,campaign_key:null,source_class},name));
  }
  input.transactions=[{transaction_ref:'synthetic-mixed-source-transaction',closed_at:'2026-11-07T12:00:00+04:00',
    allocations:[{campaign_key:null,source_class:'ads',weight_ppm:333333},
      {campaign_key:null,source_class:'other',weight_ppm:333333},{campaign_key:null,source_class:'unknown',weight_ppm:333334}],...provenance}];
  input.collections=[{record_id:'synthetic-mixed-source-receipt',transaction_ref:'synthetic-mixed-source-transaction',
    collected_at:'2026-11-07T12:00:00+04:00',gross_commission_minor:101,vat_minor:0,refund_minor:0,pass_through_minor:0,
    agent_payout_minor:0,referral_payout_minor:0,direct_cost_minor:0,nonmedia_acquisition_minor:0,...provenance}];
  for(const source_class of ['ads','other','unknown'])rows.push(mapping({kind:'transaction_allocation',
    transaction_ref:'synthetic-mixed-source-transaction',campaign_key:null,source_class},name));
  const report=run(input,rows),row=segment(report,name);
  assert.deepEqual(row.by_attribution_source.map(value=>value.attribution_source),['ADS_UNMAPPED','OTHER_SOURCE','UNKNOWN_SOURCE']);
  assert.equal(row.first_ever_qualified_people,3);assert.equal(row.observed_period_ads_spend_per_first_qualification_aed,3);
  for(const group of ['ads','other','unknown'])assert.equal(row.by_source_class[group].first_ever_qualified_people,1);
  assert.equal(row.by_source_class.other.observed_period_ads_spend_per_first_qualification_aed,null);
  assert.equal(row.by_source_class.ads.allocated_collected_net_revenue_minor,34);
  assert.equal(row.by_source_class.other.allocated_collected_net_revenue_minor,33);
  assert.equal(row.by_source_class.unknown.allocated_collected_net_revenue_minor,34);
  assert.equal(row.by_source_class.unknown.media_spend_minor,0);assert.deepEqual(baseOnly(report),commercialReport(input,policy));
  rows[3].entity.source_class='ads';assert.deepEqual(run(input,rows).segment_report.holds,['SEGMENT_UNKNOWN_OR_OUT_OF_WINDOW_ENTITY']);
});

test('incomplete, conflicting, unknown and foreign classifications hold only segmented results',()=>{
  for(const [mutate,code] of [
    [rows=>rows.pop(),'SEGMENT_CLASSIFICATION_INCOMPLETE'],
    [rows=>rows.push({...rows[0],segment:'commercial_lease'}),'SEGMENT_CLASSIFICATION_CONFLICT'],
    [rows=>{rows[0].segment=null;},'SEGMENT_UNKNOWN_CLASSIFICATION'],
    [rows=>{rows[0].segment='made_up';},'SEGMENT_CLASSIFICATION_VALUE_INVALID'],
    [rows=>{rows[0].entity.campaign_key='BSRE-C9999';},'SEGMENT_UNKNOWN_OR_OUT_OF_WINDOW_ENTITY'],
  ]){
    const {input,rows}=sixFixture();mutate(rows);const result=run(input,rows);
    assert.equal(result.segment_report.status,'HELD');assert.equal(result.segment_report.segments,null);
    assert.deepEqual(result.segment_report.holds,[code]);assert.deepEqual(baseOnly(result),commercialReport(input,policy));
  }
});

test('explicit policy approval binds the exact classification, source, policy, finance bytes and clock',()=>{
  const {input,rows}=sixFixture(),doc=document(input,rows);
  assert.deepEqual(commercialReportBySegment(input,policy,doc,{now_utc:NOW}).segment_report.holds,['SEGMENT_CLASSIFICATION_APPROVAL_REQUIRED']);
  const weak={...policy,segment_classification:{reviewed:true}};
  assert.deepEqual(commercialReportBySegment(input,weak,doc,{now_utc:NOW}).segment_report.holds,['SEGMENT_CLASSIFICATION_APPROVAL_REQUIRED']);
  const bound=approved(doc);doc.rows[0].segment='commercial_lease';
  assert.deepEqual(commercialReportBySegment(input,bound,doc,{now_utc:NOW}).segment_report.holds,['SEGMENT_CLASSIFICATION_APPROVAL_HASH_MISMATCH']);
  for(const [field,value] of [['finance_source_ref','SYNTHETIC-DIFFERENT'],['finance_policy_approval_ref','SYNTHETIC-DIFFERENT'],
    ['finance_input_sha256','0'.repeat(64)],['from','2026-11-02T00:00:00+04:00']]){
    const changed=document(input,rows);changed[field]=value;
    assert.deepEqual(commercialReportBySegment(input,approved(changed),changed,{now_utc:NOW}).segment_report.holds,['SEGMENT_FINANCE_INPUT_BINDING_MISMATCH']);
  }
  const fresh=document(input,rows),freshPolicy=approved(fresh);input.spend[0].amount_minor++;
  assert.deepEqual(commercialReportBySegment(input,freshPolicy,fresh,{now_utc:NOW}).segment_report.holds,['SEGMENT_FINANCE_INPUT_BINDING_MISMATCH']);
  for(const now_utc of ['2026-11-08T10:59:59Z','2026-11-08T13:00:00Z']){
    const current=document(input,rows);
    assert.deepEqual(commercialReportBySegment(input,approved(current),current,{now_utc}).segment_report.holds,['SEGMENT_CLASSIFICATION_REVIEW_STALE_OR_FUTURE']);
  }
  const current=document(input,rows);
  assert.deepEqual(commercialReportBySegment(input,approved(current),current).segment_report.holds,['SEGMENT_EXPLICIT_UTC_CLOCK_REQUIRED']);
});

test('unresolved history withholds segmented ratios; no qualification consent or Google eligibility is invented',()=>{
  const {input,rows}=sixFixture();input.qualifications.push({...input.qualifications[0],
    record_id:'synthetic-unresolved-history',person_ref:'synthetic-different-person',history_verified:false});
  const result=run(input,rows);
  assert.ok(result.segment_report.segments.every(row=>row.observed_period_ads_spend_per_first_qualification_aed===null));
  assert.equal(result.totals.first_ever_qualified_people,6);assert.equal(result.segment_report.google_upload_supported,false);
});

test('zero qualification denominators stay null even with complete classifications and positive spend',()=>{
  const {input,rows}=sixFixture();input.qualifications=[];
  const result=run(input,rows.filter(row=>row.entity.kind!=='qualification'));
  assert.equal(result.segment_report.status,'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER');
  assert.ok(result.segment_report.segments.every(row=>row.media_spend_minor>0&&row.observed_period_ads_spend_per_first_qualification_aed===null));
});

test('source-row ratios require campaign linkage while complete segment Ads aggregates retain their ratio',()=>{
  const input=emptyInput(),name='offplan',rows=[mapping({kind:'spend',campaign_key:'BSRE-C0001',date:'2026-11-07'},name)];
  input.spend=[{campaign_key:'BSRE-C0001',date:'2026-11-07',amount_minor:10000,...provenance}];
  for(const [index,campaign_key,source_class] of [[1,'BSRE-C0001','ads'],[2,null,'ads'],[3,null,'other'],[4,null,'unknown']]){
    const person_ref=`synthetic-ratio-person-${index}`;
    input.qualifications.push({record_id:`synthetic-ratio-qualification-${index}`,person_ref,campaign_key,source_class,
      qualified_at:'2026-11-02T12:00:00+04:00',first_ever_confirmed:true,history_verified:true,...provenance});
    rows.push(mapping({kind:'qualification',person_ref,campaign_key,source_class},name));
  }
  const result=run(input,rows),row=segment(result,name);
  assert.equal(row.observed_period_ads_spend_per_first_qualification_aed,50);
  assert.equal(row.by_source_class.ads.observed_period_ads_spend_per_first_qualification_aed,50);
  assert.equal(row.by_attribution_source.find(value=>value.attribution_source==='BSRE-C0001').observed_period_ads_spend_per_first_qualification_aed,100);
  for(const key of ['ADS_UNMAPPED','OTHER_SOURCE','UNKNOWN_SOURCE'])
    assert.equal(row.by_attribution_source.find(value=>value.attribution_source===key).observed_period_ads_spend_per_first_qualification_aed,null);
  assert.deepEqual(baseOnly(result),commercialReport(input,policy));
});

test('no classification access before blocked base policy; original strict row schemas remain enforced',async()=>{
  const {input,rows}=sixFixture(),untouched=new Proxy({}, {get(){throw new Error('SYNTHETIC-SECRET-MUST-NOT-BE-READ');}});
  const result=commercialReportBySegment(input,{},untouched);
  assert.equal(result.status,'BLOCKED');assert.deepEqual(result.segment_report.holds,['SEGMENT_BASE_REPORT_BLOCKED']);
  assert.equal((await commercialReportFromHistoryBySegment(input,{},untouched,untouched)).status,'BLOCKED');
  input.spend[0].property_segment='residential_rental';assert.throws(()=>run(input,rows),/UNKNOWN_SPEND_FIELD/);
});

test('classification contact fields reject without echo; successful output contains aggregates and hashes only',()=>{
  const {input,rows}=sixFixture(),result=run(input,rows),serialized=JSON.stringify(result);
  for(const privateValue of ['synthetic-person-1','synthetic-transaction-1','synthetic-opportunity-1','SYNTHETIC-CLASSIFICATION-EVIDENCE'])
    assert.ok(!serialized.includes(privateValue));
  for(const mutate of [doc=>{doc.email='synthetic@example.test';},doc=>{doc.rows[0].phone='+971000000000';},
    doc=>{doc.rows[0].evidence_ref='synthetic@example.test';},doc=>{doc.rows[0].entity.email='synthetic@example.test';}]){
    const doc=document(input,structuredClone(rows));mutate(doc);
    const rejected=commercialReportBySegment(input,approved(doc),doc,{now_utc:NOW});
    assert.equal(rejected.segment_report.status,'HELD');assert.ok(!JSON.stringify(rejected).includes('synthetic@example.test'));
    assert.ok(!JSON.stringify(rejected).includes('+971000000000'));
  }
});

test('negative refunds conserve segments and installment receipts do not multiply transaction weights',()=>{
  const {input,rows}=sixFixture();input.collections.push({...input.collections[0],record_id:'synthetic-installment'});
  Object.assign(input.collections.at(-1),{gross_commission_minor:0,vat_minor:0,refund_minor:20001,pass_through_minor:0,
    agent_payout_minor:0,referral_payout_minor:0,direct_cost_minor:0,nonmedia_acquisition_minor:0});
  const result=run(input,rows),row=segment(result,'residential_purchase');
  assert.equal(row.allocated_collected_net_revenue_minor,-10201);assert.equal(row.post_acquisition_contribution_minor,-13301);
  assert.equal(row.allocated_cash_receipt_transaction_weight_ppm,1000000);
  assert.deepEqual(baseOnly(result),commercialReport(input,policy));
});

test('real pinned Python history supports explicit homogeneous buckets without inventing campaign mappings',async t=>{
  const python=process.env.BSRE_TEST_PYTHON??'python',directory=await mkdtemp(join(tmpdir(),'bsre-synthetic-segment-'));
  t.after(()=>rm(directory,{recursive:true,force:true}));
  const fixtures=fileURLToPath(new URL('../../qualification-history/',import.meta.url));
  const producer='import hashlib,json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'+
    'from test_commercial_integration import inputs_fixture,encoded,review_fixture;'+
    'ledger,source=inputs_fixture();lr=encoded(ledger);sr=encoded(source);br=encoded(review_fixture(lr,sr));'+
    'root=Path(sys.argv[2]);[(root/(name+".json")).write_bytes(raw) for name,raw in (("ledger",lr),("source",sr),("business",br))];'+
    'print(json.dumps({"python":sys.executable}))';
  const produced=spawnSync(python,['-B','-c',producer,fixtures,directory],{encoding:'utf8',timeout:10000,windowsHide:true});
  if(produced.error?.code==='ENOENT'||(process.env.BSRE_TEST_PYTHON===undefined&&produced.status===9009)){
    t.skip('Python is required for pinned audit integration; set BSRE_TEST_PYTHON to an existing trusted executable');return;
  }
  assert.equal(produced.status,0,'Synthetic history fixture producer must complete');
  const history={python:JSON.parse(produced.stdout).python,ledger_path:join(directory,'ledger.json'),
    source_review_path:join(directory,'source.json'),business_review_path:join(directory,'business.json'),now_utc:NOW};
  const audit=await readQualificationHistory(history,{fromDay:'2026-11-01',toDay:'2026-11-30'});
  const input=emptyInput();delete input.qualifications;input.qualification_audit=audit;
  input.spend=[{campaign_key:'BSRE-C0001',date:'2026-11-07',amount_minor:10000,...provenance}];
  const rows=[mapping({kind:'spend',campaign_key:'BSRE-C0001',date:'2026-11-07'},'offplan'),
    mapping({kind:'audited_qualification_bucket',day:'2026-11-01',source_class:'ads',native_campaign_id:'24372566774'},'offplan'),
    mapping({kind:'audited_qualification_bucket',day:'2026-11-03',source_class:'other',native_campaign_id:null},'residential_rental'),
    mapping({kind:'audited_qualification_bucket',day:'2026-11-04',source_class:'unknown',native_campaign_id:null},'commercial_lease')];
  const doc=document(input,rows),approvedPolicy=approved(doc),result=commercialReportBySegment(input,approvedPolicy,doc,{now_utc:NOW});
  assert.equal(result.segment_report.status,'CALCULATED_OFFLINE_NOT_RECONCILED_WITH_PROVIDER');
  const offplan=segment(result,'offplan');
  assert.equal(offplan.observed_period_ads_spend_per_first_qualification_aed,100);
  assert.equal(offplan.by_attribution_source.find(row=>row.attribution_source==='ADS_UNMAPPED').observed_period_ads_spend_per_first_qualification_aed,null);
  assert.equal(offplan.by_attribution_source.find(row=>row.attribution_source==='BSRE-C0001').observed_period_ads_spend_per_first_qualification_aed,null);
  assert.equal(segment(result,'residential_rental').by_source_class.other.first_ever_qualified_people,1);
  assert.equal(segment(result,'commercial_lease').by_source_class.unknown.first_ever_qualified_people,1);
  assert.equal(result.totals.first_ever_qualified_people,3);assert.ok(!JSON.stringify(result).includes('SYNTHETIC-PERSON'));
  const finance={...input};delete finance.qualification_audit;
  assert.deepEqual(await commercialReportFromHistoryBySegment(finance,approvedPolicy,history,doc),result);
  const handwritten={...input,qualification_audit:structuredClone(audit)};
  assert.throws(()=>commercialReportBySegment(handwritten,approvedPolicy,doc,{now_utc:NOW}),/EXECUTED_QUALIFICATION_AUDIT_REQUIRED/);
});
