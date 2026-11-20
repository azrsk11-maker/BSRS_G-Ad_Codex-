import test from 'node:test';
import assert from 'node:assert/strict';
import {validateTracking,guardReportPath} from './validate_tracking_evidence.mjs';
import {mkdtempSync,writeFileSync,readFileSync,linkSync,symlinkSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';import {join,resolve,sep,basename} from 'node:path';

function fixture() {
  return {contract: {
    site_scope:'EXISTING_MAIN_SITE_AND_NATIVE_CAMPAIGN_PAGES',
    installation:{verified_ids_only:true, production_placeholder_ids_allowed:false,one_installation_path_per_tag:true},
    privacy:{pii_in_ga4_or_urls:false,raw_form_text_in_events:false,secrets_in_repository:false},
    attribution:{internal_utm_retagging:false,unknown_values_fabricated:false,consent_or_click_id_required_to_enquire:false},
    deduplication:{server_acceptance_before_lead_event:true,durable_lead_id_required:true,one_ads_route_per_business_event:true,
      generic_and_specialized_cta_counts_summed:false,custom_event_id_assumed_universal_dedup:false},
    events:[...['cta_click','phone_click','whatsapp_click','email_click'].map(operational_event => ({operational_event,bidding_treatment:'diagnostic'})),
      {operational_event:'form_accepted',proposed_ga4_event:'generate_lead',evidence_source:'server_confirmed'},
      ...['conversation_verified','qualified_lead','mandate_signed','offer_submitted','transaction_closed','commission_collected','viewing_booked','viewing_attended']
        .map(operational_event=>({operational_event,evidence_source:operational_event==='commission_collected'?'finance_ledger':
          operational_event==='conversation_verified'?'provider_or_authorized_ledger':operational_event==='viewing_booked'?
            'booking_or_authorized_ledger':'authorized_ledger'}))]},
    acceptance:{tests:Array.from({length:32},(_,i)=>({test_id:`WT-${String(i+1).padStart(3,'0')}`,status:'NOT_EXECUTED',evidence_ref:null,reviewer:null}))}};
}
function evidenceOf(acceptance) {
  return {tests:structuredClone(acceptance.tests),production_synthetic_conversions:0,production_changes_performed:false};
}

test('unexecuted design validates but never becomes release approval', () => {
  const {contract,acceptance}=fixture(); const r=validateTracking(contract,acceptance);
  assert.equal(r.valid,true);assert.equal(r.acceptance_complete,false);assert.equal(r.release_authorized,false);
});
test('privacy and duplicate counting cannot be silently weakened', () => {
  const {contract,acceptance}=fixture();contract.privacy.pii_in_ga4_or_urls=true;
  contract.deduplication.generic_and_specialized_cta_counts_summed=true;
  assert.equal(validateTracking(contract,acceptance).errors.length,2);
});
test('string false does not satisfy boolean false', () => {
  const {contract,acceptance}=fixture();contract.attribution.internal_utm_retagging='false';
  assert.equal(validateTracking(contract,acceptance).valid,false);
});
test('browser click cannot establish financial or qualification outcome', () => {
  const {contract,acceptance}=fixture();contract.events.find(e=>e.operational_event==='commission_collected').evidence_source='browser';
  assert.equal(validateTracking(contract,acceptance).valid,false);
  delete contract.events.find(e=>e.operational_event==='commission_collected').evidence_source;
  assert.equal(validateTracking(contract,acceptance).valid,false);
});
test('missing acceptance and duplicate IDs fail', () => {
  const {contract,acceptance}=fixture();acceptance.tests[1].test_id=acceptance.tests[0].test_id;
  assert.equal(validateTracking(contract,acceptance).valid,false);
});
test('PASS requires evidence and cannot be derived from HTTP-only observations', () => {
  const {contract,acceptance}=fixture();const evidence=evidenceOf(acceptance);
  evidence.tests[0]={test_id:'WT-001',status:'PASS',evidence_ref:'public-audit.json',reviewer:'auditor',observed_at_utc:'2026-11-07T05:00:00Z',method:'PUBLIC_HTTP_GET'};
  assert.equal(validateTracking(contract,acceptance,evidence).valid,false);
  evidence.tests[0].status='PARTIAL';assert.equal(validateTracking(contract,acceptance,evidence).valid,true);
  evidence.tests[0].evidence_ref=null;assert.equal(validateTracking(contract,acceptance,evidence).valid,false);
});
test('synthetic production conversions fail even if tests otherwise pass', () => {
  const {contract,acceptance}=fixture();const evidence=evidenceOf(acceptance);evidence.production_synthetic_conversions=1;
  assert.equal(validateTracking(contract,acceptance,evidence).valid,false);
});
test('report paths cannot overwrite input through direct path, hardlink or symlink',t=>{
  const dir=mkdtempSync(join(tmpdir(),'bsre-output-guard-'));
  try{
    const source=join(dir,'source.json'),hard=join(dir,'hard.json'),sym=join(dir,'sym.json');writeFileSync(source,'ORIGINAL');
    assert.throws(()=>guardReportPath([source],join(dir,'.','source.json')),/REPORT_MUST_NOT_OVERWRITE_INPUT/);
    linkSync(source,hard);assert.throws(()=>guardReportPath([source],hard),/REPORT_MUST_NOT_OVERWRITE_INPUT/);
    try{symlinkSync(source,sym);assert.throws(()=>guardReportPath([source],sym),/REPORT_MUST_NOT_OVERWRITE_INPUT/);}
    catch(error){if(!['EPERM','EACCES','ENOTSUP'].includes(error.code))throw error;t.diagnostic('OS disallowed symlink creation; direct and hardlink cases verified.');}
    assert.doesNotThrow(()=>guardReportPath([source],join(dir,'report.json')));assert.equal(readFileSync(source,'utf8'),'ORIGINAL');
  }finally{
    const resolved=resolve(dir),root=resolve(tmpdir())+sep;
    assert.ok(resolved.startsWith(root)&&basename(resolved).startsWith('bsre-output-guard-'),'Cleanup target must remain the created task temp directory.');
    rmSync(resolved,{recursive:true,force:true});
  }
});
