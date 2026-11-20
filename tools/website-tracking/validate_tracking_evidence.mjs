/** Offline gate diagnostics. This tool never authorizes publication or changes test evidence. */
import {readFileSync, writeFileSync, realpathSync, statSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {resolve, dirname, basename, join} from 'node:path';

const STATUSES = new Set(['NOT_EXECUTED', 'PARTIAL', 'PASS', 'FAIL', 'BLOCKED']);
const METHODS = new Set(['NATIVE_ACCOUNT_READBACK', 'NATIVE_BROWSER_NETWORK', 'CONTROLLED_INTEGRATION',
  'RESTORE_REHEARSAL', 'OPERATIONAL_REVIEW', 'LOCAL_UNIT_TEST', 'PUBLIC_HTTP_GET']);
const CLICK_EVENTS = ['cta_click','phone_click','whatsapp_click','email_click'];
const OUTCOMES = ['conversation_verified','qualified_lead','mandate_signed','offer_submitted',
  'transaction_closed','commission_collected','viewing_booked','viewing_attended'];
const text = value => typeof value === 'string' && value.trim().length > 0;
const date = value => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$/.test(value) && Number.isFinite(Date.parse(value));

export function guardReportPath(inputPaths,outputPath) {
  const canonical = path => {
    const absolute=resolve(path);
    try { return realpathSync(absolute); }
    catch(error) { if(error.code!=='ENOENT')throw error;return join(realpathSync(dirname(absolute)),basename(absolute)); }
  };
  const fold = path => process.platform==='win32'?path.toLowerCase():path;
  const target=canonical(outputPath);
  let targetStat;try{targetStat=statSync(target);}catch(error){if(error.code!=='ENOENT')throw error;}
  for(const input of inputPaths){
    const source=canonical(input),sourceStat=statSync(source);
    if(fold(source)===fold(target)||(targetStat&&sourceStat.dev===targetStat.dev&&sourceStat.ino===targetStat.ino))
      throw new Error('REPORT_MUST_NOT_OVERWRITE_INPUT');
  }
}

export function validateTracking(contract, acceptance, evidence = null) {
  const errors = [];
  const require = (condition, message) => { if (!condition) errors.push(message); };
  require(contract?.site_scope === 'EXISTING_MAIN_SITE_AND_NATIVE_CAMPAIGN_PAGES', 'Native existing-site scope is required.');
  const constraints = [
    ['installation','verified_ids_only',true], ['installation','production_placeholder_ids_allowed',false],
    ['installation','one_installation_path_per_tag',true], ['privacy','pii_in_ga4_or_urls',false],
    ['privacy','raw_form_text_in_events',false], ['privacy','secrets_in_repository',false],
    ['attribution','internal_utm_retagging',false], ['attribution','unknown_values_fabricated',false],
    ['attribution','consent_or_click_id_required_to_enquire',false],
    ['deduplication','server_acceptance_before_lead_event',true],
    ['deduplication','durable_lead_id_required',true], ['deduplication','one_ads_route_per_business_event',true],
    ['deduplication','generic_and_specialized_cta_counts_summed',false],
    ['deduplication','custom_event_id_assumed_universal_dedup',false]
  ];
  for (const [section, name, value] of constraints) {
    require(contract?.[section]?.[name] === value, `${section}.${name} must be boolean ${value}.`);
  }
  const events = Array.isArray(contract?.events) ? contract.events : [];
  const eventNames = events.map(e => e.operational_event);
  require(eventNames.length > 0 && new Set(eventNames).size === eventNames.length, 'Event names must be present and unique.');
  for (const name of CLICK_EVENTS) {
    require(events.find(e => e.operational_event === name)?.bidding_treatment === 'diagnostic', `${name} must remain diagnostic.`);
  }
  const accepted = events.find(e => e.operational_event === 'form_accepted');
  require(accepted?.proposed_ga4_event === 'generate_lead' && accepted?.evidence_source === 'server_confirmed',
    'Accepted enquiry requires server-confirmed generate_lead mapping.');
  for (const name of OUTCOMES) {
    const event = events.find(e => e.operational_event === name);
    const expected = name === 'commission_collected' ? 'finance_ledger' : name === 'conversation_verified' ?
      'provider_or_authorized_ledger' : name === 'viewing_booked' ? 'booking_or_authorized_ledger' : 'authorized_ledger';
    require(event?.evidence_source === expected, `${name} requires ${expected}, not a browser click or missing source.`);
  }
  const tests = Array.isArray(acceptance?.tests) ? acceptance.tests : [];
  const ids = tests.map(t => t.test_id);
  require(ids.length === 32 && new Set(ids).size === 32 && ids.every(id => /^WT-(?:00[1-9]|0[12]\d|03[0-2])$/.test(id)),
    'All 32 unique source acceptance test IDs are required.');
  let rows = tests;
  if (evidence !== null) {
    rows = Array.isArray(evidence?.tests) ? evidence.tests : [];
    require(rows.length === ids.length && new Set(rows.map(t => t.test_id)).size === ids.length &&
      rows.every(t => ids.includes(t.test_id)), 'Evidence must preserve all source test IDs exactly once.');
    require(evidence?.production_synthetic_conversions === 0, 'Production synthetic conversion count must be explicitly zero.');
    require(evidence?.production_changes_performed === false, 'Phase 0 evidence must declare no production changes.');
    for (const row of rows) {
      require(STATUSES.has(row.status), `${row.test_id}: invalid status.`);
      if (['PASS','PARTIAL','FAIL'].includes(row.status)) {
        require(text(row.evidence_ref) && text(row.reviewer) && date(row.observed_at_utc) && METHODS.has(row.method),
          `${row.test_id}: recorded result needs evidence, reviewer, UTC observation and method.`);
      }
      if (row.status === 'PASS') {
        require(!['PUBLIC_HTTP_GET','LOCAL_UNIT_TEST'].includes(row.method),
          `${row.test_id}: isolated HTTP/unit evidence cannot close a complete live acceptance gate.`);
      }
    }
  } else {
    for (const row of rows) {
      require(row.status === 'NOT_EXECUTED' && row.evidence_ref === null && row.reviewer === null,
        `${row.test_id}: source test design must remain unexecuted; supply results separately.`);
    }
  }
  const pending = rows.filter(row => row.status !== 'PASS').map(row => row.test_id);
  return {schema_version: 1, valid: errors.length === 0, errors, test_count: rows.length,
    pass_count: rows.filter(row => row.status === 'PASS').length, pending_test_ids: pending,
    acceptance_complete: errors.length === 0 && pending.length === 0,
    release_authorized: false,
    authorization_note: 'Validation is not deployment, publication, Ads, budget or live-tracking approval.'};
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const [contractPath, testPath, evidencePath, reportPath] = process.argv.slice(2);
  if (!contractPath || !testPath) throw new Error('Usage: node validate_tracking_evidence.mjs contract.json acceptance.json [evidence.json|-] [report.json]');
  const parse = path => JSON.parse(readFileSync(path, 'utf8').replace(/^\uFEFF/, ''));
  const report = validateTracking(parse(contractPath), parse(testPath), evidencePath && evidencePath !== '-' ? parse(evidencePath) : null);
  if (reportPath) {
    guardReportPath([contractPath,testPath,...(evidencePath&&evidencePath!=='-'?[evidencePath]:[])],reportPath);
    writeFileSync(reportPath, JSON.stringify(report,null,2)+'\n');
  }
  console.log(JSON.stringify(report));
  process.exitCode = report.valid ? 0 : 1;
}
