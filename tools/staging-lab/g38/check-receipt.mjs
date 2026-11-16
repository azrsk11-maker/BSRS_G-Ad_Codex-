import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
export const modes=Object.freeze(['choose_commit','choose_rollback','stage_commit','stage_rollback']);
export const waitFields=Object.freeze(['mechanism','real_wait','child_live','distinct_processes','distinct_connections','waiter','blocker','named_lock_owner','state_primary_wait','waiting_statement','polls','elapsed_ms','parent_pid','child_pid','parent_connection','child_connection','requesting_trx_id','blocking_trx_id','waiting_table','waiting_index','waiting_query','selected_database','database_prefix','canonical_class','canonical_bootstrapped','canonical_g2_same_object','custody_active','custody_connection','session_in_transaction','session_tx_isolation']);
const hash=v=>createHash('sha256').update(v).digest('hex');
export function expectedWaitQuery(mode) {
  if(!modes.includes(mode))throw new Error('G38_FIXED_MODE_REQUIRED');
  const table='g37_pref_'+hash('g38|'+mode).slice(0,12)+'_synthetic_bsre_consent_state';
  const subject='aa'+hash('SYNTHETIC_G38_'+mode).slice(0,62);
  return mode.startsWith('choose_')?`INSERT IGNORE INTO ${table} (subject_key,revision,receipt,analytics,ad_measurement,personalization,notice_version,changed_at,expires_at,uncertain) VALUES ('${subject}',0,'',0,0,0,'',0,0,1)`:`SELECT * FROM ${table} WHERE subject_key='${subject}' FOR UPDATE`;
}
export function validateWait(w,mode) {
  const fail=()=>{throw new Error('G38_RAW_WAIT_EVIDENCE_INVALID');};
  if(!modes.includes(mode))fail();
  if(!w||Object.keys(w).sort().join('|')!==[...waitFields].sort().join('|')||w.mechanism!=='INNODB_LOCK_WAITS'||['real_wait','child_live','distinct_processes','distinct_connections','state_primary_wait','canonical_bootstrapped','canonical_g2_same_object','custody_active'].some(k=>w[k]!==true))fail();
  for(const k of ['parent_pid','child_pid','parent_connection','child_connection','waiter','blocker','named_lock_owner'])if(!Number.isSafeInteger(w[k])||w[k]<1)fail();
  if(w.parent_pid===w.child_pid||w.parent_connection===w.child_connection||w.parent_connection!==w.blocker||w.child_connection!==w.waiter||w.named_lock_owner!==w.blocker||w.custody_connection!==String(w.blocker))fail();
  for(const k of ['requesting_trx_id','blocking_trx_id'])if(typeof w[k]!=='string'||!/^[1-9][0-9]{0,31}$/.test(w[k]))fail();
  if(w.requesting_trx_id===w.blocking_trx_id)fail();
  const prefix='g37_pref_'+hash('g38|'+mode).slice(0,12)+'_synthetic_',table=prefix+'bsre_consent_state';
  const expectedQuery=expectedWaitQuery(mode);
  const representations=[`bsre_synthetic.${table}`,`\`bsre_synthetic\`.\`${table}\``,`"bsre_synthetic"."${table}"`];
  if(w.selected_database!=='bsre_synthetic'||w.database_prefix!==prefix||typeof w.waiting_table!=='string'||Buffer.byteLength(w.waiting_table)>256||!representations.includes(w.waiting_table)||w.waiting_index!=='PRIMARY'||typeof w.waiting_query!=='string'||Buffer.byteLength(w.waiting_query)>2048||w.waiting_query!==expectedQuery||w.canonical_class!=='BSRE\\ClosedRetention\\LeaseBoundWpdb'||w.session_in_transaction!=='1'||w.session_tx_isolation!=='REPEATABLE-READ')fail();
  if(w.waiting_statement!==(mode.startsWith('choose_')?'INSERT_IGNORE_STATE':'SELECT_STATE_FOR_UPDATE')||!Number.isSafeInteger(w.polls)||w.polls<1||!Number.isFinite(w.elapsed_ms)||w.elapsed_ms<0||w.elapsed_ms>=4000)fail();
  return true;
}
export function validateReceipt(value) {
  const fail=()=>{throw new Error('G38_INCOMPLETE_NATIVE_RECEIPT');};
  if(!value||value.phase!=='g38_g2_retirement_race'||value.status!=='PASS'||!modes.includes(value.mode)||value.synthetic_only!==true||value.actual_provider_accepted!==false||value.production_authorized!==false||value.full_operational_retention_accepted!==false)fail();
  const required=['capture_matcher_rejects_identity_and_permission_corruption','exact_two_retirement_targets','observed_real_wait','exact_retirement_outcome','exact_child_outcome','retirement_audit_anchor_atomic','authenticated_ledger_exact_old_receipt','healthy_unknown_exact_original_input_preserved','unknown_retry_keeps_original_decision','canonical_lease_and_transaction_released','no_http_or_mail','bounded_duration'];
  if(value.mode.startsWith('choose_'))required.push('new_choice_exact_revision_and_permissions','old_history_retained_only_after_rollback');
  else required.push('known_stage_matches_retirement_winner',...(value.mode==='stage_rollback'?['staged_exact_original_input_preserved','known_retry_keeps_original_decision']:[]));
  if(!value.checks||Object.keys(value.checks).sort().join('|')!==required.sort().join('|')||Object.values(value.checks).some(ok=>ok!==true))fail();
  const isolation=['cli','non_root','loopback_only','no_routes','no_capabilities','no_new_privileges','readonly_application','database_already_started','no_docker_socket'];
  if(!value.runtime_isolation||Object.keys(value.runtime_isolation).sort().join('|')!==isolation.sort().join('|')||Object.values(value.runtime_isolation).some(ok=>ok!==true))fail();
  validateWait(value.wait,value.mode);
  return {mode:value.mode,checks:required.length,real_wait:true};
}
export function validateProfileLog(raw) {
  if(typeof raw!=='string'||Buffer.byteLength(raw)>16*1024*1024)throw new Error('G38_LOG_BOUND');
  const receipts=[];
  for(const line of raw.split(/\r?\n/)) {
    if(!line.startsWith('{'))continue;
    let v;try{v=JSON.parse(line);}catch{if(line.includes('g38_'))throw new Error('G38_MALFORMED_RECEIPT');continue;}
    if(v.phase==='g38_g2_race_diagnostic'||v.phase==='g38_check'&&v.pass!==true)throw new Error('G38_FAILED_NATIVE_TRIAL');
    if(v.phase==='g38_g2_retirement_race')receipts.push(validateReceipt(v));
  }
  if(receipts.length!==4||new Set(receipts.map(v=>v.mode)).size!==4)throw new Error('G38_FOUR_DISTINCT_MODES_REQUIRED');
  return {status:'PASS',modes:receipts.map(v=>v.mode),checks:receipts.reduce((n,v)=>n+v.checks,0),real_sql_waits:4,actual_provider_accepted:false};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  if(process.argv.length!==3)throw new Error('G38_ONE_PROFILE_LOG_REQUIRED');
  process.stdout.write(JSON.stringify(validateProfileLog(readFileSync(process.argv[2],'utf8')))+'\n');
}
